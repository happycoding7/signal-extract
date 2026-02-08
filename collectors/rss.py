"""
RSS/Atom feed collector. Uses feedparser.

Simple: fetch feeds, extract entries, dedup by ID.
"""

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import requests

from collectors.base import Collector
from config.settings import Config
from models import Item, Source
from storage.db import Storage

log = logging.getLogger(__name__)


class RSSCollector(Collector):
    def __init__(self, storage: Storage, config: Config):
        super().__init__(storage)
        self._feeds = config.rss_feeds
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "signal-extract/0.1"

    def name(self) -> str:
        return "rss"

    def collect(self) -> list[Item]:
        state = self.storage.get_collector_state(self.name())
        items: list[Item] = []

        for feed_url in self._feeds:
            try:
                items.extend(self._collect_feed(feed_url, state))
            except Exception as e:
                log.warning(f"RSS error for {feed_url}: {e}")
                continue

        self.storage.set_collector_state(self.name(), state)
        return items

    def _collect_feed(self, feed_url: str, state: dict) -> list[Item]:
        """Parse a single feed, return new entries."""
        # Use etag/modified for conditional requests
        etag = state.get(f"etag:{feed_url}", "")
        modified = state.get(f"modified:{feed_url}", "")

        feed = feedparser.parse(
            feed_url,
            etag=etag or None,
            modified=modified or None,
        )

        # Update conditional request headers for next time
        if hasattr(feed, "etag") and feed.etag:
            state[f"etag:{feed_url}"] = feed.etag
        if hasattr(feed, "modified") and feed.modified:
            state[f"modified:{feed_url}"] = feed.modified

        # Status 304 = not modified
        if hasattr(feed, "status") and feed.status == 304:
            return []

        items = []
        feed_title = feed.feed.get("title", feed_url) if feed.feed else feed_url

        for entry in feed.entries[:10]:  # cap per feed
            entry_id = entry.get("id") or entry.get("link") or entry.get("title", "")
            source_id = f"rss:{feed_url}:{entry_id}"

            # Extract body — prefer summary, fall back to content
            body = ""
            if entry.get("summary"):
                body = entry.summary
            elif entry.get("content"):
                body = entry.content[0].get("value", "")

            # Strip HTML tags (crude but sufficient for scoring)
            import re
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s+", " ", body).strip()

            if len(body) > 3000:
                body = body[:3000] + "\n[truncated]"

            # Parse published date
            published = datetime.now(timezone.utc)
            if entry.get("published_parsed"):
                try:
                    published = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                except (ValueError, OverflowError):
                    pass

            item = Item(
                source=Source.RSS,
                source_id=source_id,
                url=entry.get("link", ""),
                title=f"[{feed_title}] {entry.get('title', 'Untitled')}",
                body=body,
                metadata={
                    "feed_url": feed_url,
                    "feed_title": feed_title,
                    "author": entry.get("author", ""),
                    "published": published.isoformat(),
                },
                collected_at=published,
            )

            if not self.storage.has_item(item.content_hash):
                items.append(item)

        return items
