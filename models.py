"""
Core data types. No behavior, just shapes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib


class Source(Enum):
    GITHUB_RELEASE = "github_release"
    GITHUB_ISSUE = "github_issue"
    GITHUB_DISCUSSION = "github_discussion"
    HACKER_NEWS = "hacker_news"
    RSS = "rss"
    NVD_CVE = "nvd_cve"


@dataclass
class Item:
    """A single piece of collected content."""
    source: Source
    source_id: str          # unique within source (e.g., GH release tag, HN id)
    url: str
    title: str
    body: str               # main content, plain text
    metadata: dict = field(default_factory=dict)  # source-specific data
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: int = 0          # signal score, 0-100, set by filter

    @property
    def content_hash(self) -> str:
        """Deterministic hash for dedup. Based on source + source_id."""
        raw = f"{self.source.value}:{self.source_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        return f"Item({self.source.value}, {self.title[:50]}, score={self.score})"


@dataclass
class Digest:
    """Output of synthesis."""
    digest_type: str        # "daily" | "weekly" | "opportunities"
    content: str            # the rendered digest text
    item_count: int         # how many items went into it
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvidenceRef:
    """A reference from an opportunity back to a collected item."""
    source: str             # e.g. "github_issue", "hacker_news"
    item_title: str
    url: str
    score: int

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "item_title": self.item_title,
            "url": self.url,
            "score": self.score,
        }


@dataclass
class Opportunity:
    """A structured, machine-readable enterprise opportunity."""
    id: str                         # stable slug, e.g. "terraform-drift-detector"
    title: str
    pain: str
    target_buyer: str
    solution_shape: str
    market_type: str                # e.g. "boring/growing", "hype/crowded"
    effort_estimate: str            # "weekend" | "1-2 weeks" | "month+"
    monetization: str
    moat: str
    confidence: int                 # 0-100
    evidence: list[EvidenceRef] = field(default_factory=list)
    competition_notes: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: int | None = None       # links to opportunity_runs.id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pain": self.pain,
            "target_buyer": self.target_buyer,
            "solution_shape": self.solution_shape,
            "market_type": self.market_type,
            "effort_estimate": self.effort_estimate,
            "monetization": self.monetization,
            "moat": self.moat,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "competition_notes": self.competition_notes,
            "generated_at": self.generated_at.isoformat(),
            "run_id": self.run_id,
        }


@dataclass
class QAResult:
    """Output of a Q&A query."""
    question: str
    answer: str
    sources_used: int
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
