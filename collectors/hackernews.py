"""
Hacker News collector. Uses the official Firebase API for top stories
and the Algolia HN Search API for keyword-targeted searches.

Strategy:
- Fetch top stories above a score threshold
- Search for stories matching marketplace-relevant keywords
- No scraping, no auth required for either API
"""

import logging
from datetime import datetime, timezone

import requests

from collectors.base import Collector
from config.settings import Config
from models import Item, Source
from storage.db import Storage

log = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"
HN_SEARCH_API = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsCollector(Collector):
    def __init__(self, storage: Storage, config: Config):
        super().__init__(storage)
        self._min_score = config.hn_min_score
        self._max_items = config.hn_max_items
        self._search_keywords = config.hn_search_keywords
        self._search_min_score = config.hn_search_min_score
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "signal-extract/0.1"

    def name(self) -> str:
        return "hackernews"

    def collect(self) -> list[Item]:
        items: list[Item] = []

        # Broad: top stories
        try:
            items.extend(self._collect_top_stories())
        except requests.RequestException as e:
            log.warning(f"HN top stories error: {e}")

        # Targeted: keyword search via Algolia
        seen_ids = {item.source_id for item in items}
        for keyword in self._search_keywords:
            try:
                for item in self._search_stories(keyword):
                    if item.source_id not in seen_ids:
                        items.append(item)
                        seen_ids.add(item.source_id)
            except requests.RequestException as e:
                log.warning(f"HN search error for '{keyword}': {e}")

        return items

    def _collect_top_stories(self) -> list[Item]:
        """Fetch top stories, filter by score threshold."""
        resp = self._session.get(f"{HN_API}/topstories.json", timeout=15)
        if resp.status_code != 200:
            return []

        story_ids = resp.json()[:self._max_items]
        items = []

        for story_id in story_ids:
            try:
                item = self._fetch_story(story_id)
                if item:
                    items.append(item)
            except requests.RequestException:
                continue

        return items

    def _fetch_story(self, story_id: int) -> Item | None:
        """Fetch a single story and convert to Item if it meets criteria."""
        resp = self._session.get(f"{HN_API}/item/{story_id}.json", timeout=10)
        if resp.status_code != 200:
            return None

        story = resp.json()
        if not story or story.get("type") != "story":
            return None

        score = story.get("score", 0)
        if score < self._min_score:
            return None

        hn_id = f"hn:{story_id}"

        item = Item(
            source=Source.HACKER_NEWS,
            source_id=hn_id,
            url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            title=story.get("title", ""),
            body=story.get("text", "") or "",
            metadata={
                "hn_id": story_id,
                "score": score,
                "comments": story.get("descendants", 0),
                "by": story.get("by", ""),
                "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
            },
        )

        if self.storage.has_item(item.content_hash):
            return None

        return item

    def _search_stories(self, keyword: str) -> list[Item]:
        """
        Search HN via Algolia API for stories matching a keyword.
        Free, no auth, 10k requests/hour rate limit.
        """
        resp = self._session.get(
            HN_SEARCH_API,
            params={
                "query": keyword,
                "tags": "story",
                "numericFilters": f"points>{self._search_min_score}",
                "hitsPerPage": 10,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            log.warning(f"HN search API HTTP {resp.status_code} for '{keyword}'")
            return []

        hits = resp.json().get("hits", [])
        items = []

        for hit in hits:
            object_id = hit.get("objectID", "")
            if not object_id:
                continue

            hn_id = f"hn:{object_id}"

            # Check dedup before building full item
            check_item = Item(
                source=Source.HACKER_NEWS,
                source_id=hn_id,
                url="", title="", body="",
            )
            if self.storage.has_item(check_item.content_hash):
                continue

            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            story_text = hit.get("story_text") or ""
            if len(story_text) > 3000:
                story_text = story_text[:3000] + "\n[truncated]"

            item = Item(
                source=Source.HACKER_NEWS,
                source_id=hn_id,
                url=story_url,
                title=hit.get("title", ""),
                body=story_text,
                metadata={
                    "hn_id": int(object_id) if object_id.isdigit() else 0,
                    "score": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                    "by": hit.get("author", ""),
                    "hn_url": f"https://news.ycombinator.com/item?id={object_id}",
                    "search_keyword": keyword,
                },
            )

            items.append(item)

        return items
