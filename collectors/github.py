"""
GitHub collector. Watches releases and high-signal issues for configured repos.

Uses the GitHub REST API. No GraphQL — simpler, sufficient for this use case.
"""

import logging
from datetime import datetime, timezone

import requests

from collectors.base import Collector
from config.settings import Config
from models import Item, Source
from storage.db import Storage

log = logging.getLogger(__name__)


class GitHubCollector(Collector):
    def __init__(self, storage: Storage, config: Config):
        super().__init__(storage)
        self._repos = config.github_repos
        self._session = requests.Session()
        self._token = config.github_token
        if self._token and not self._token.startswith(("ghp_...", "your")):
            self._session.headers["Authorization"] = f"token {self._token}"
        self._session.headers["Accept"] = "application/vnd.github.v3+json"
        self._session.headers["User-Agent"] = "signal-extract/0.1"
        self._auth_failed = False

    def name(self) -> str:
        return "github"

    def _request(self, url: str, params: dict | None = None) -> requests.Response | None:
        """Make a GitHub API request. Falls back to unauthenticated on 401."""
        resp = self._session.get(url, params=params, timeout=15)

        if resp.status_code == 401 and "Authorization" in self._session.headers:
            if not self._auth_failed:
                log.warning("GitHub token rejected (401). Falling back to unauthenticated.")
                self._auth_failed = True
                del self._session.headers["Authorization"]
            resp = self._session.get(url, params=params, timeout=15)

        if resp.status_code != 200:
            log.warning(f"GitHub API {url}: HTTP {resp.status_code}")
            return None

        return resp

    def collect(self) -> list[Item]:
        state = self.storage.get_collector_state(self.name())
        items: list[Item] = []

        for repo in self._repos:
            try:
                items.extend(self._collect_releases(repo, state))
                items.extend(self._collect_issues(repo, state))
            except requests.RequestException as e:
                log.warning(f"GitHub API error for {repo}: {e}")
                continue

        # Update state with current timestamp
        state["last_collected"] = datetime.now(timezone.utc).isoformat()
        self.storage.set_collector_state(self.name(), state)

        return items

    def _collect_releases(self, repo: str, state: dict) -> list[Item]:
        """Fetch recent releases. Only return ones we haven't seen."""
        url = f"https://api.github.com/repos/{repo}/releases"
        resp = self._request(url, params={"per_page": 5})
        if resp is None:
            return []

        items = []
        seen_key = f"releases_seen_{repo}"
        seen = set(state.get(seen_key, []))

        for release in resp.json():
            tag = release.get("tag_name", "")
            release_id = f"{repo}:{tag}"

            if release_id in seen:
                continue

            body = release.get("body", "") or ""
            # Truncate very long release notes
            if len(body) > 3000:
                body = body[:3000] + "\n[truncated]"

            item = Item(
                source=Source.GITHUB_RELEASE,
                source_id=release_id,
                url=release.get("html_url", ""),
                title=f"[{repo}] Release {tag}",
                body=body,
                metadata={
                    "repo": repo,
                    "tag": tag,
                    "prerelease": release.get("prerelease", False),
                    "created_at": release.get("created_at", ""),
                },
            )

            if not self.storage.has_item(item.content_hash):
                items.append(item)
                seen.add(release_id)

        state[seen_key] = list(seen)[-50:]  # keep last 50 to bound state size
        return items

    def _collect_issues(self, repo: str, state: dict) -> list[Item]:
        """
        Fetch recently updated issues with high engagement.
        We care about issues that indicate pain, not feature requests.
        """
        since = state.get("last_collected", "2024-01-01T00:00:00Z")
        url = f"https://api.github.com/repos/{repo}/issues"
        resp = self._request(url, params={
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since,
            "per_page": 15,
        })
        if resp is None:
            return []

        items = []
        for issue in resp.json():
            # Skip pull requests (GitHub API returns them as issues)
            if "pull_request" in issue:
                continue

            # Only care about issues with meaningful engagement
            reactions = issue.get("reactions", {}).get("total_count", 0)
            comments = issue.get("comments", 0)
            if reactions < 5 and comments < 3:
                continue

            issue_id = f"{repo}:issue:{issue['number']}"
            body = issue.get("body", "") or ""
            if len(body) > 2000:
                body = body[:2000] + "\n[truncated]"

            labels = [l.get("name", "") for l in issue.get("labels", [])]

            item = Item(
                source=Source.GITHUB_ISSUE,
                source_id=issue_id,
                url=issue.get("html_url", ""),
                title=f"[{repo}] #{issue['number']}: {issue.get('title', '')}",
                body=body,
                metadata={
                    "repo": repo,
                    "issue_number": issue["number"],
                    "state": issue.get("state", ""),
                    "reactions": reactions,
                    "comments": comments,
                    "labels": labels,
                },
            )

            if not self.storage.has_item(item.content_hash):
                items.append(item)

        return items
