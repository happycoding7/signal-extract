"""
GitHub Discussions collector. Uses GraphQL API (REST does not expose Discussions).

Primary target: community/community — where GitHub users post feature requests,
workflow complaints, and upvote unmet needs. This is the single richest source
for marketplace opportunity signals.

Requires GITHUB_TOKEN with read:discussion scope.
"""

import logging
from datetime import datetime, timezone

import requests

from collectors.base import Collector
from config.settings import Config
from models import Item, Source
from storage.db import Storage

log = logging.getLogger(__name__)

GITHUB_GRAPHQL = "https://api.github.com/graphql"

DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(
      first: 25,
      after: $cursor,
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        id
        number
        title
        body
        url
        createdAt
        updatedAt
        upvoteCount
        comments {
          totalCount
        }
        category {
          name
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
        answer {
          id
        }
      }
    }
  }
}
"""


class GitHubDiscussionsCollector(Collector):
    """
    Collects GitHub Discussions from configured repos.

    Fetches 25 most recently updated discussions per repo.
    Filters by engagement: upvotes >= 3 OR comments >= 2.
    Unanswered + high-upvote = strong unmet need signal.
    """

    def __init__(self, storage: Storage, config: Config):
        super().__init__(storage)
        self._repos = config.github_discussions_repos
        self._token = config.github_token
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "signal-extract/0.1"
        if self._token and not self._token.startswith(("ghp_...", "your")):
            self._session.headers["Authorization"] = f"bearer {self._token}"
        self._session.headers["Content-Type"] = "application/json"

    def name(self) -> str:
        return "github_discussions"

    def collect(self) -> list[Item]:
        if not self._token or self._token.startswith(("ghp_...", "your")):
            log.warning(
                "GitHub Discussions collector requires a valid GITHUB_TOKEN. Skipping."
            )
            return []

        items: list[Item] = []
        for repo in self._repos:
            try:
                new_items = self._collect_repo(repo)
                items.extend(new_items)
            except Exception as e:
                log.warning(f"Discussions error for {repo}: {e}")
                continue

        return items

    def _collect_repo(self, repo: str) -> list[Item]:
        """Fetch recent discussions from one repo via GraphQL."""
        parts = repo.split("/")
        if len(parts) != 2:
            log.warning(f"Invalid repo format for discussions: {repo}")
            return []

        owner, repo_name = parts

        resp = self._session.post(
            GITHUB_GRAPHQL,
            json={
                "query": DISCUSSIONS_QUERY,
                "variables": {"owner": owner, "name": repo_name, "cursor": None},
            },
            timeout=20,
        )

        if resp.status_code == 401:
            log.warning(f"GraphQL auth failed for {repo}. Check GITHUB_TOKEN permissions.")
            return []
        if resp.status_code != 200:
            log.warning(f"GraphQL HTTP {resp.status_code} for {repo}")
            return []

        data = resp.json()
        if "errors" in data:
            msgs = [e.get("message", "") for e in data["errors"]]
            log.warning(f"GraphQL errors for {repo}: {msgs}")
            return []

        repository = data.get("data", {}).get("repository")
        if not repository:
            log.warning(f"No repository data returned for {repo}")
            return []

        nodes = repository.get("discussions", {}).get("nodes", [])
        items = []

        for disc in nodes:
            if disc is None:
                continue

            upvotes = disc.get("upvoteCount", 0)
            comment_count = disc.get("comments", {}).get("totalCount", 0)

            # Engagement filter: skip low-signal discussions
            if upvotes < 3 and comment_count < 2:
                continue

            disc_number = disc.get("number", 0)
            disc_id = f"{repo}:discussion:{disc_number}"

            body = disc.get("body", "") or ""
            if len(body) > 3000:
                body = body[:3000] + "\n[truncated]"

            category_data = disc.get("category") or {}
            category_name = category_data.get("name", "")

            label_nodes = disc.get("labels", {}).get("nodes", [])
            labels = [l.get("name", "") for l in label_nodes if l]

            has_answer = disc.get("answer") is not None

            collected_at = datetime.now(timezone.utc)
            created_at_str = disc.get("createdAt", "")
            if created_at_str:
                try:
                    collected_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            item = Item(
                source=Source.GITHUB_DISCUSSION,
                source_id=disc_id,
                url=disc.get("url", ""),
                title=f"[{repo}] Discussion #{disc_number}: {disc.get('title', '')}",
                body=body,
                metadata={
                    "repo": repo,
                    "discussion_number": disc_number,
                    "upvotes": upvotes,
                    "comments": comment_count,
                    "category": category_name,
                    "labels": labels,
                    "has_answer": has_answer,
                    "created_at": created_at_str,
                    "updated_at": disc.get("updatedAt", ""),
                },
                collected_at=collected_at,
            )

            if not self.storage.has_item(item.content_hash):
                items.append(item)

        return items
