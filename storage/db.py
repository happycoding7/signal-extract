"""
SQLite storage. One file, one connection, no ORM.

Tables:
- items: collected content with scores
- collector_state: cursor/checkpoint per collector
- digests: generated outputs for reference
- opportunity_runs: each structured opportunity generation run
- opportunities: structured opportunity records
- opportunity_evidence: evidence links from opportunities to items
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from models import Item, Source, Opportunity, EvidenceRef


class Storage:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        """Create tables if they don't exist. No migration framework needed."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                content_hash TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                score INTEGER NOT NULL DEFAULT 0,
                collected_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_items_collected
                ON items(collected_at);
            CREATE INDEX IF NOT EXISTS idx_items_source
                ON items(source);
            CREATE INDEX IF NOT EXISTS idx_items_score
                ON items(score);

            CREATE TABLE IF NOT EXISTS collector_state (
                collector_name TEXT PRIMARY KEY,
                state TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                digest_type TEXT NOT NULL,
                content TEXT NOT NULL,
                item_count INTEGER NOT NULL,
                generated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS opportunity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                digest_id INTEGER,
                item_count INTEGER NOT NULL,
                opportunity_count INTEGER NOT NULL,
                generated_at TEXT NOT NULL,
                FOREIGN KEY (digest_id) REFERENCES digests(id)
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                pain TEXT NOT NULL,
                target_buyer TEXT NOT NULL,
                solution_shape TEXT NOT NULL,
                market_type TEXT NOT NULL,
                effort_estimate TEXT NOT NULL,
                monetization TEXT NOT NULL,
                moat TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                competition_notes TEXT NOT NULL DEFAULT '',
                generated_at TEXT NOT NULL,
                PRIMARY KEY (id, run_id),
                FOREIGN KEY (run_id) REFERENCES opportunity_runs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_opportunities_run
                ON opportunities(run_id);
            CREATE INDEX IF NOT EXISTS idx_opportunities_confidence
                ON opportunities(confidence);
            CREATE INDEX IF NOT EXISTS idx_opportunities_buyer
                ON opportunities(target_buyer);
            CREATE INDEX IF NOT EXISTS idx_opportunities_market
                ON opportunities(market_type);

            CREATE TABLE IF NOT EXISTS opportunity_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                item_title TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (opportunity_id, run_id) REFERENCES opportunities(id, run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_opportunity
                ON opportunity_evidence(opportunity_id, run_id);
        """)
        self._conn.commit()

    def insert_item(self, item: Item) -> bool:
        """
        Insert an item. Returns True if new, False if duplicate.
        Idempotent — duplicates are silently ignored.
        """
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO items
                   (content_hash, source, source_id, url, title, body, metadata, score, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.content_hash,
                    item.source.value,
                    item.source_id,
                    item.url,
                    item.title,
                    item.body,
                    json.dumps(item.metadata),
                    item.score,
                    item.collected_at.isoformat(),
                ),
            )
            self._conn.commit()
            return self._conn.execute(
                "SELECT changes()"
            ).fetchone()[0] > 0
        except sqlite3.Error:
            return False

    def insert_items(self, items: list[Item]) -> int:
        """Insert multiple items. Returns count of new items."""
        new_count = 0
        for item in items:
            if self.insert_item(item):
                new_count += 1
        return new_count

    def has_item(self, content_hash: str) -> bool:
        """Check if an item already exists."""
        row = self._conn.execute(
            "SELECT 1 FROM items WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def get_items_since(
        self,
        since: datetime,
        min_score: int = 0,
        source: Source | None = None,
    ) -> list[Item]:
        """Get items collected after a given time, optionally filtered."""
        query = "SELECT * FROM items WHERE collected_at >= ? AND score >= ?"
        params: list = [since.isoformat(), min_score]

        if source:
            query += " AND source = ?"
            params.append(source.value)

        query += " ORDER BY score DESC, collected_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_items_last_n_days(self, days: int, min_score: int = 0) -> list[Item]:
        """Convenience: get items from the last N days."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return self.get_items_since(since, min_score=min_score)

    def get_collector_state(self, collector_name: str) -> dict:
        """Get saved state for a collector (cursors, timestamps, etc.)."""
        row = self._conn.execute(
            "SELECT state FROM collector_state WHERE collector_name = ?",
            (collector_name,),
        ).fetchone()
        if row:
            return json.loads(row[0])
        return {}

    def set_collector_state(self, collector_name: str, state: dict):
        """Save collector state."""
        self._conn.execute(
            """INSERT INTO collector_state (collector_name, state, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(collector_name)
               DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at""",
            (collector_name, json.dumps(state)),
        )
        self._conn.commit()

    def save_digest(self, digest_type: str, content: str, item_count: int):
        """Save a generated digest for future reference."""
        self._conn.execute(
            "INSERT INTO digests (digest_type, content, item_count, generated_at) VALUES (?, ?, ?, ?)",
            (digest_type, content, item_count, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def get_stats(self) -> dict:
        """Basic stats for debugging."""
        total = self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        by_source = {}
        for row in self._conn.execute(
            "SELECT source, COUNT(*) as cnt FROM items GROUP BY source"
        ):
            by_source[row[0]] = row[1]
        return {"total_items": total, "by_source": by_source}

    # ── Opportunity storage ──

    def save_opportunity_run(
        self,
        opportunities: list[Opportunity],
        item_count: int,
        digest_id: int | None = None,
    ) -> int:
        """
        Save a structured opportunity run with all opportunities and evidence.
        Returns the run_id.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO opportunity_runs (digest_id, item_count, opportunity_count, generated_at) "
            "VALUES (?, ?, ?, ?)",
            (digest_id, item_count, len(opportunities), now),
        )
        run_id = cursor.lastrowid

        for opp in opportunities:
            self._conn.execute(
                """INSERT OR REPLACE INTO opportunities
                   (id, run_id, title, pain, target_buyer, solution_shape,
                    market_type, effort_estimate, monetization, moat,
                    confidence, competition_notes, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    opp.id, run_id, opp.title, opp.pain, opp.target_buyer,
                    opp.solution_shape, opp.market_type, opp.effort_estimate,
                    opp.monetization, opp.moat, opp.confidence,
                    opp.competition_notes, now,
                ),
            )
            for ev in opp.evidence:
                self._conn.execute(
                    """INSERT INTO opportunity_evidence
                       (opportunity_id, run_id, source, item_title, url, score)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (opp.id, run_id, ev.source, ev.item_title, ev.url, ev.score),
                )

        self._conn.commit()
        return run_id

    def get_opportunities(
        self,
        min_confidence: int = 0,
        target_buyer: str | None = None,
        market_type: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Query opportunities with filters. Returns (list_of_dicts, total_count).
        Each dict includes nested evidence array.
        """
        conditions = ["o.confidence >= ?"]
        params: list = [min_confidence]

        if target_buyer:
            conditions.append("LOWER(o.target_buyer) LIKE ?")
            params.append(f"%{target_buyer.lower()}%")
        if market_type:
            conditions.append("LOWER(o.market_type) LIKE ?")
            params.append(f"%{market_type.lower()}%")
        if since:
            conditions.append("o.generated_at >= ?")
            params.append(since)

        where = " AND ".join(conditions)

        total = self._conn.execute(
            f"SELECT COUNT(*) FROM opportunities o WHERE {where}", params
        ).fetchone()[0]

        rows = self._conn.execute(
            f"SELECT o.*, r.digest_id FROM opportunities o "
            f"JOIN opportunity_runs r ON o.run_id = r.id "
            f"WHERE {where} "
            f"ORDER BY o.confidence DESC, o.generated_at DESC "
            f"LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        results = []
        for row in rows:
            ev_rows = self._conn.execute(
                "SELECT source, item_title, url, score "
                "FROM opportunity_evidence "
                "WHERE opportunity_id = ? AND run_id = ?",
                (row["id"], row["run_id"]),
            ).fetchall()

            results.append({
                "id": row["id"],
                "run_id": row["run_id"],
                "title": row["title"],
                "pain": row["pain"],
                "target_buyer": row["target_buyer"],
                "solution_shape": row["solution_shape"],
                "market_type": row["market_type"],
                "effort_estimate": row["effort_estimate"],
                "monetization": row["monetization"],
                "moat": row["moat"],
                "confidence": row["confidence"],
                "competition_notes": row["competition_notes"],
                "generated_at": row["generated_at"],
                "digest_id": row["digest_id"],
                "evidence": [
                    {
                        "source": ev["source"],
                        "item_title": ev["item_title"],
                        "url": ev["url"],
                        "score": ev["score"],
                    }
                    for ev in ev_rows
                ],
            })

        return results, total

    def get_opportunity_by_id(self, opportunity_id: str) -> dict | None:
        """Get the latest version of an opportunity by its slug id."""
        row = self._conn.execute(
            "SELECT o.*, r.digest_id FROM opportunities o "
            "JOIN opportunity_runs r ON o.run_id = r.id "
            "WHERE o.id = ? ORDER BY o.generated_at DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()

        if not row:
            return None

        ev_rows = self._conn.execute(
            "SELECT source, item_title, url, score "
            "FROM opportunity_evidence "
            "WHERE opportunity_id = ? AND run_id = ?",
            (row["id"], row["run_id"]),
        ).fetchall()

        return {
            "id": row["id"],
            "run_id": row["run_id"],
            "title": row["title"],
            "pain": row["pain"],
            "target_buyer": row["target_buyer"],
            "solution_shape": row["solution_shape"],
            "market_type": row["market_type"],
            "effort_estimate": row["effort_estimate"],
            "monetization": row["monetization"],
            "moat": row["moat"],
            "confidence": row["confidence"],
            "competition_notes": row["competition_notes"],
            "generated_at": row["generated_at"],
            "digest_id": row["digest_id"],
            "evidence": [
                {
                    "source": ev["source"],
                    "item_title": ev["item_title"],
                    "url": ev["url"],
                    "score": ev["score"],
                }
                for ev in ev_rows
            ],
        }

    def get_opportunity_trends(self) -> list[dict]:
        """
        Get confidence trends per opportunity id across runs.
        Returns list of {id, title, data_points: [{run_id, confidence, generated_at}]}.
        """
        rows = self._conn.execute(
            "SELECT o.id, o.title, o.run_id, o.confidence, o.generated_at "
            "FROM opportunities o "
            "ORDER BY o.id, o.generated_at ASC"
        ).fetchall()

        trends: dict[str, dict] = {}
        for row in rows:
            oid = row["id"]
            if oid not in trends:
                trends[oid] = {
                    "id": oid,
                    "title": row["title"],
                    "data_points": [],
                }
            trends[oid]["data_points"].append({
                "run_id": row["run_id"],
                "confidence": row["confidence"],
                "generated_at": row["generated_at"],
            })
            # Keep title from latest run
            trends[oid]["title"] = row["title"]

        return list(trends.values())

    def _row_to_item(self, row: sqlite3.Row) -> Item:
        return Item(
            source=Source(row["source"]),
            source_id=row["source_id"],
            url=row["url"],
            title=row["title"],
            body=row["body"],
            metadata=json.loads(row["metadata"]),
            collected_at=datetime.fromisoformat(row["collected_at"]),
            score=row["score"],
        )

    def close(self):
        self._conn.close()
