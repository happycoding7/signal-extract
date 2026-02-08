"""
Read-only API server for the signal-extract web UI.
Reads from the existing SQLite database. Never writes.

Run: python main.py serve
"""

import json
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory


def _parse_int(value: str | None, default: int, name: str) -> tuple[int, str | None]:
    """Parse an integer query param. Returns (value, error_message)."""
    if value is None:
        return default, None
    try:
        return int(value), None
    except (ValueError, TypeError):
        return default, f"Invalid value for '{name}': expected integer, got '{value}'"


def create_app(db_path: Path, static_folder: Path | None = None):
    if static_folder and static_folder.exists():
        app = Flask(__name__, static_folder=str(static_folder), static_url_path="")
    else:
        app = Flask(__name__)

    # ── CORS for development ──
    @app.after_request
    def add_cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return response

    def get_db():
        """Open a read-only connection."""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ── API Routes ──

    @app.route("/api/digests")
    def list_digests():
        digest_type = request.args.get("type")

        conn = get_db()
        try:
            if digest_type:
                rows = conn.execute(
                    "SELECT id, digest_type, content, item_count, generated_at "
                    "FROM digests WHERE digest_type = ? ORDER BY generated_at DESC",
                    (digest_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, digest_type, content, item_count, generated_at "
                    "FROM digests ORDER BY generated_at DESC"
                ).fetchall()

            digests = [
                {
                    "id": row["id"],
                    "digest_type": row["digest_type"],
                    "content": row["content"],
                    "item_count": row["item_count"],
                    "generated_at": row["generated_at"],
                }
                for row in rows
            ]
            return jsonify({"digests": digests})
        finally:
            conn.close()

    @app.route("/api/digests/<int:digest_id>")
    def get_digest(digest_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, digest_type, content, item_count, generated_at "
                "FROM digests WHERE id = ?",
                (digest_id,),
            ).fetchone()

            if not row:
                return jsonify({"error": "Digest not found"}), 404

            return jsonify({
                "id": row["id"],
                "digest_type": row["digest_type"],
                "content": row["content"],
                "item_count": row["item_count"],
                "generated_at": row["generated_at"],
            })
        finally:
            conn.close()

    @app.route("/api/items")
    def list_items():
        source = request.args.get("source")
        min_score = int(request.args.get("min_score", "0"))
        since = request.args.get("since", "")
        limit = min(int(request.args.get("limit", "50")), 200)
        offset = int(request.args.get("offset", "0"))

        conn = get_db()
        try:
            conditions = ["score >= ?"]
            params: list = [min_score]

            if source:
                conditions.append("source = ?")
                params.append(source)

            if since:
                conditions.append("collected_at >= ?")
                params.append(since)

            where = " AND ".join(conditions)

            # Get total count
            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM items WHERE {where}", params
            ).fetchone()
            total = count_row["cnt"]

            # Get items
            rows = conn.execute(
                f"SELECT content_hash, source, source_id, url, title, body, "
                f"metadata, score, collected_at "
                f"FROM items WHERE {where} "
                f"ORDER BY score DESC, collected_at DESC "
                f"LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

            items = []
            for row in rows:
                items.append({
                    "content_hash": row["content_hash"],
                    "source": row["source"],
                    "source_id": row["source_id"],
                    "url": row["url"],
                    "title": row["title"],
                    "body": row["body"][:500],  # Truncate for list view
                    "metadata": json.loads(row["metadata"]),
                    "score": row["score"],
                    "collected_at": row["collected_at"],
                })

            return jsonify({
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        finally:
            conn.close()

    @app.route("/api/stats")
    def get_stats():
        conn = get_db()
        try:
            total_items = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
            total_digests = conn.execute("SELECT COUNT(*) as cnt FROM digests").fetchone()["cnt"]

            by_source = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) as cnt FROM items GROUP BY source"
            ):
                by_source[row["source"]] = row["cnt"]

            by_digest_type = {}
            for row in conn.execute(
                "SELECT digest_type, COUNT(*) as cnt FROM digests GROUP BY digest_type"
            ):
                by_digest_type[row["digest_type"]] = row["cnt"]

            latest_row = conn.execute(
                "SELECT MAX(collected_at) as latest FROM items"
            ).fetchone()
            latest_collection = latest_row["latest"] if latest_row["latest"] else None

            # Score distribution
            score_dist = {}
            for row in conn.execute("""
                SELECT
                    CASE
                        WHEN score BETWEEN 0 AND 20 THEN '0-20'
                        WHEN score BETWEEN 21 AND 40 THEN '21-40'
                        WHEN score BETWEEN 41 AND 60 THEN '41-60'
                        WHEN score BETWEEN 61 AND 80 THEN '61-80'
                        WHEN score BETWEEN 81 AND 100 THEN '81-100'
                    END as bucket,
                    COUNT(*) as cnt
                FROM items GROUP BY bucket
            """):
                if row["bucket"]:
                    score_dist[row["bucket"]] = row["cnt"]

            return jsonify({
                "total_items": total_items,
                "total_digests": total_digests,
                "by_source": by_source,
                "by_digest_type": by_digest_type,
                "latest_collection": latest_collection,
                "score_distribution": score_dist,
            })
        finally:
            conn.close()

    # ── Opportunity Routes ──

    @app.route("/api/opportunities")
    def list_opportunities():
        """List structured opportunities with filters."""
        # Validate integer params
        min_confidence, err = _parse_int(request.args.get("min_confidence"), 0, "min_confidence")
        if err:
            return jsonify({"error": err}), 400

        limit_raw, err = _parse_int(request.args.get("limit"), 50, "limit")
        if err:
            return jsonify({"error": err}), 400
        limit = min(limit_raw, 200)

        offset, err = _parse_int(request.args.get("offset"), 0, "offset")
        if err:
            return jsonify({"error": err}), 400

        # Validate min_confidence range
        if not (0 <= min_confidence <= 100):
            return jsonify({"error": "min_confidence must be between 0 and 100"}), 400

        buyer = request.args.get("buyer")
        market_type = request.args.get("market_type")
        since = request.args.get("since")

        conn = get_db()
        try:
            conditions = ["o.confidence >= ?"]
            params: list = [min_confidence]

            if buyer:
                conditions.append("LOWER(o.target_buyer) LIKE ?")
                params.append(f"%{buyer.lower()}%")
            if market_type:
                conditions.append("LOWER(o.market_type) LIKE ?")
                params.append(f"%{market_type.lower()}%")
            if since:
                conditions.append("o.generated_at >= ?")
                params.append(since)

            where = " AND ".join(conditions)

            total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM opportunities o WHERE {where}", params
            ).fetchone()["cnt"]

            rows = conn.execute(
                f"SELECT o.*, r.digest_id FROM opportunities o "
                f"JOIN opportunity_runs r ON o.run_id = r.id "
                f"WHERE {where} "
                f"ORDER BY o.confidence DESC, o.generated_at DESC "
                f"LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

            results = []
            for row in rows:
                ev_rows = conn.execute(
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

            return jsonify({
                "opportunities": results,
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        finally:
            conn.close()

    @app.route("/api/opportunities/trends")
    def opportunity_trends():
        """Get confidence trends for opportunities across runs."""
        conn = get_db()
        try:
            rows = conn.execute(
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
                trends[oid]["title"] = row["title"]

            return jsonify({"trends": list(trends.values())})
        finally:
            conn.close()

    @app.route("/api/opportunities/<opportunity_id>")
    def get_opportunity(opportunity_id):
        """Get the latest version of an opportunity by slug."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT o.*, r.digest_id FROM opportunities o "
                "JOIN opportunity_runs r ON o.run_id = r.id "
                "WHERE o.id = ? ORDER BY o.generated_at DESC LIMIT 1",
                (opportunity_id,),
            ).fetchone()

            if not row:
                return jsonify({"error": "Opportunity not found"}), 404

            ev_rows = conn.execute(
                "SELECT source, item_title, url, score "
                "FROM opportunity_evidence "
                "WHERE opportunity_id = ? AND run_id = ?",
                (row["id"], row["run_id"]),
            ).fetchall()

            return jsonify({
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
        finally:
            conn.close()

    # ── Static file serving (production) ──

    @app.route("/")
    def serve_index():
        if static_folder and static_folder.exists():
            return send_from_directory(str(static_folder), "index.html")
        return jsonify({
            "message": "signal-extract API",
            "endpoints": [
                "/api/digests",
                "/api/items",
                "/api/stats",
                "/api/opportunities",
                "/api/opportunities/trends",
                "/api/opportunities/<id>",
            ],
            "note": "No frontend built. Run 'cd web && npm run build' for the UI.",
        })

    @app.route("/<path:path>")
    def serve_static(path):
        if static_folder and static_folder.exists():
            # Try to serve the file, fall back to index.html for SPA routing
            file_path = static_folder / path
            if file_path.exists():
                return send_from_directory(str(static_folder), path)
            return send_from_directory(str(static_folder), "index.html")
        return jsonify({"error": "Not found"}), 404

    return app
