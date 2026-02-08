"""
Synthesis engine. Takes stored items + LLM provider, produces digests.
"""

import json
import logging
import re

from llm.provider import LLMProvider, LLMError
from models import Item, Digest, QAResult, Opportunity, EvidenceRef
from storage.db import Storage
from synthesizer.prompts import (
    DAILY_SYSTEM, DAILY_USER,
    WEEKLY_SYSTEM, WEEKLY_USER,
    QA_SYSTEM, QA_USER,
    OPPORTUNITY_SYSTEM, OPPORTUNITY_USER,
    STRUCTURED_OPPORTUNITY_SYSTEM, STRUCTURED_OPPORTUNITY_USER,
    STRUCTURED_OPPORTUNITY_REPAIR,
)

log = logging.getLogger(__name__)


def _format_items_for_prompt(items: list[Item], max_items: int = 30) -> str:
    """Format items into a text block for the LLM prompt."""
    if not items:
        return "(no items collected)"

    lines = []
    for item in items[:max_items]:
        lines.append(
            f"[score={item.score}] [{item.source.value}] {item.title}\n"
            f"  URL: {item.url}\n"
            f"  {item.body[:500]}\n"
        )
    return "\n---\n".join(lines)


def _extract_json_array(text: str) -> str:
    """
    Extract a JSON array from LLM response text.
    Handles markdown code fences, leading/trailing text, etc.
    """
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = text.strip()

    # Find the outermost [ ... ]
    start = text.find("[")
    if start == -1:
        raise ValueError("No JSON array found in response")

    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        raise ValueError("Unbalanced brackets in JSON array")

    return text[start:end]


VALID_EFFORT_ESTIMATES = {"weekend", "1-2 weeks", "month+"}


def _validate_opportunity_dict(d: dict) -> list[str]:
    """Validate a single opportunity dict. Returns list of error messages."""
    errors = []
    required_str_fields = [
        "id", "title", "pain", "target_buyer", "solution_shape",
        "market_type", "effort_estimate", "monetization", "moat",
    ]
    for field in required_str_fields:
        if field not in d or not isinstance(d[field], str) or not d[field].strip():
            errors.append(f"Missing or empty required field: {field}")

    if "confidence" not in d:
        errors.append("Missing field: confidence")
    elif not isinstance(d["confidence"], (int, float)):
        errors.append(f"confidence must be an integer, got {type(d['confidence']).__name__}")
    elif not (0 <= d["confidence"] <= 100):
        errors.append(f"confidence must be 0-100, got {d['confidence']}")

    if "effort_estimate" in d and d.get("effort_estimate") not in VALID_EFFORT_ESTIMATES:
        errors.append(
            f"effort_estimate must be one of {VALID_EFFORT_ESTIMATES}, "
            f"got '{d.get('effort_estimate')}'"
        )

    if "evidence" not in d or not isinstance(d["evidence"], list):
        errors.append("Missing or invalid field: evidence (must be array)")
    elif len(d["evidence"]) == 0:
        errors.append("evidence array must have at least 1 entry")
    else:
        for i, ev in enumerate(d["evidence"]):
            if not isinstance(ev, dict):
                errors.append(f"evidence[{i}] must be an object")
                continue
            for ef in ["source", "item_title", "url"]:
                if ef not in ev or not isinstance(ev[ef], str) or not ev[ef].strip():
                    errors.append(f"evidence[{i}] missing field: {ef}")

    return errors


def parse_opportunities_json(raw_text: str) -> list[Opportunity]:
    """
    Parse LLM JSON response into a list of Opportunity objects.
    Raises ValueError with a descriptive message on failure.
    """
    json_str = _extract_json_array(raw_text)
    data = json.loads(json_str)

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    opportunities = []
    all_errors = []

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            all_errors.append(f"Item {i}: expected object, got {type(item).__name__}")
            continue

        errors = _validate_opportunity_dict(item)
        if errors:
            all_errors.append(f"Item {i} ({item.get('id', '?')}): {'; '.join(errors)}")
            continue

        evidence = []
        for ev in item.get("evidence", []):
            evidence.append(EvidenceRef(
                source=ev.get("source", ""),
                item_title=ev.get("item_title", ""),
                url=ev.get("url", ""),
                score=int(ev.get("score", 0)),
            ))

        opportunities.append(Opportunity(
            id=item["id"],
            title=item["title"],
            pain=item["pain"],
            target_buyer=item["target_buyer"],
            solution_shape=item["solution_shape"],
            market_type=item["market_type"],
            effort_estimate=item["effort_estimate"],
            monetization=item["monetization"],
            moat=item["moat"],
            confidence=int(item["confidence"]),
            evidence=evidence,
            competition_notes=item.get("competition_notes", ""),
        ))

    if all_errors and not opportunities:
        raise ValueError(
            f"All {len(data)} opportunities failed validation:\n" +
            "\n".join(all_errors)
        )
    elif all_errors:
        log.warning(
            f"{len(all_errors)} opportunities failed validation (kept {len(opportunities)}):\n" +
            "\n".join(all_errors)
        )

    return opportunities


class Synthesizer:
    def __init__(self, llm: LLMProvider, storage: Storage):
        self._llm = llm
        self._storage = storage

    def daily_digest(self) -> Digest | None:
        """Generate daily digest from today's items."""
        items = self._storage.get_items_last_n_days(days=1, min_score=40)

        if not items:
            log.info("No items to digest today")
            return Digest(
                digest_type="daily",
                content="No clear opportunities today.",
                item_count=0,
            )

        formatted = _format_items_for_prompt(items, max_items=20)
        prompt = DAILY_USER.format(items=formatted)

        try:
            response = self._llm.complete(
                system_prompt=DAILY_SYSTEM,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=1000,
            )
            log.info(
                f"Daily digest: {response.input_tokens} in, "
                f"{response.output_tokens} out ({response.model})"
            )
        except LLMError as e:
            log.error(f"LLM error during daily digest: {e}")
            return None

        digest = Digest(
            digest_type="daily",
            content=response.text,
            item_count=len(items),
        )

        self._storage.save_digest("daily", digest.content, digest.item_count)
        return digest

    def weekly_synthesis(self) -> Digest | None:
        """Generate weekly synthesis from this week's items."""
        items = self._storage.get_items_last_n_days(days=7, min_score=30)

        if not items:
            log.info("No items for weekly synthesis")
            return Digest(
                digest_type="weekly",
                content="Quiet week. No notable marketplace signals.",
                item_count=0,
            )

        formatted = _format_items_for_prompt(items, max_items=40)
        prompt = WEEKLY_USER.format(items=formatted)

        try:
            response = self._llm.complete(
                system_prompt=WEEKLY_SYSTEM,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=1500,
            )
            log.info(
                f"Weekly synthesis: {response.input_tokens} in, "
                f"{response.output_tokens} out ({response.model})"
            )
        except LLMError as e:
            log.error(f"LLM error during weekly synthesis: {e}")
            return None

        digest = Digest(
            digest_type="weekly",
            content=response.text,
            item_count=len(items),
        )

        self._storage.save_digest("weekly", digest.content, digest.item_count)
        return digest

    def opportunity_report(self) -> Digest | None:
        """
        Generate a deep marketplace opportunity report (free-text).
        Uses a 14-day window to accumulate enough data for pattern detection.
        """
        items = self._storage.get_items_last_n_days(days=14, min_score=35)

        if not items:
            log.info("No items for opportunity report")
            return Digest(
                digest_type="opportunities",
                content="Not enough data for opportunity analysis. "
                        "Run 'collect' first and wait for data to accumulate.",
                item_count=0,
            )

        formatted = _format_items_for_prompt(items, max_items=50)
        prompt = OPPORTUNITY_USER.format(items=formatted)

        try:
            response = self._llm.complete(
                system_prompt=OPPORTUNITY_SYSTEM,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2000,
            )
            log.info(
                f"Opportunity report: {response.input_tokens} in, "
                f"{response.output_tokens} out ({response.model})"
            )
        except LLMError as e:
            log.error(f"LLM error during opportunity report: {e}")
            return None

        digest = Digest(
            digest_type="opportunities",
            content=response.text,
            item_count=len(items),
        )

        self._storage.save_digest("opportunities", digest.content, digest.item_count)
        return digest

    def structured_opportunity_report(self) -> list[Opportunity] | None:
        """
        Generate structured (JSON) opportunity report.
        Returns list of Opportunity objects, or None on failure.

        Strategy: attempt JSON parse, retry once with repair prompt on failure.
        Also saves a free-text digest and the structured data to DB.
        """
        items = self._storage.get_items_last_n_days(days=14, min_score=35)

        if not items:
            log.info("No items for structured opportunity report")
            return []

        formatted = _format_items_for_prompt(items, max_items=50)
        prompt = STRUCTURED_OPPORTUNITY_USER.format(items=formatted)

        # First attempt
        try:
            response = self._llm.complete(
                system_prompt=STRUCTURED_OPPORTUNITY_SYSTEM,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=3000,
            )
            log.info(
                f"Structured opportunity report: {response.input_tokens} in, "
                f"{response.output_tokens} out ({response.model})"
            )
        except LLMError as e:
            log.error(f"LLM error during structured opportunity report: {e}")
            return None

        raw_text = response.text

        # Parse attempt 1
        try:
            opportunities = parse_opportunities_json(raw_text)
        except (ValueError, json.JSONDecodeError) as first_error:
            log.warning(f"First JSON parse failed: {first_error}. Attempting repair.")

            # Retry with repair prompt
            repair_prompt = STRUCTURED_OPPORTUNITY_REPAIR.format(
                error=str(first_error),
                raw=raw_text[:500],
            )
            try:
                repair_response = self._llm.complete(
                    system_prompt=STRUCTURED_OPPORTUNITY_SYSTEM,
                    user_prompt=repair_prompt,
                    temperature=0.1,
                    max_tokens=3000,
                )
                raw_text = repair_response.text
                opportunities = parse_opportunities_json(raw_text)
                log.info("Repair succeeded.")
            except (ValueError, json.JSONDecodeError, LLMError) as second_error:
                log.error(
                    f"Structured opportunity report failed after retry: {second_error}\n"
                    f"Raw LLM output (first 300 chars): {response.text[:300]}"
                )
                return None

        if not opportunities:
            log.info("LLM returned no qualifying opportunities")
            return []

        # Save a free-text digest alongside the structured data
        text_summary = _opportunities_to_text(opportunities)
        self._storage.save_digest("opportunities", text_summary, len(items))

        # Get the digest_id we just created
        digest_row = self._storage._conn.execute(
            "SELECT id FROM digests ORDER BY id DESC LIMIT 1"
        ).fetchone()
        digest_id = digest_row[0] if digest_row else None

        # Save structured data
        run_id = self._storage.save_opportunity_run(
            opportunities, item_count=len(items), digest_id=digest_id,
        )

        # Attach run_id to returned objects
        for opp in opportunities:
            opp.run_id = run_id

        log.info(f"Saved {len(opportunities)} structured opportunities (run_id={run_id})")
        return opportunities

    def ask(self, question: str, days: int = 7) -> QAResult | None:
        """Answer a question based on recent items."""
        items = self._storage.get_items_last_n_days(days=days, min_score=20)

        formatted = _format_items_for_prompt(items, max_items=30)
        prompt = QA_USER.format(items=formatted, question=question, days=days)

        try:
            response = self._llm.complete(
                system_prompt=QA_SYSTEM,
                user_prompt=prompt,
                temperature=0.4,
                max_tokens=1500,
            )
        except LLMError as e:
            log.error(f"LLM error during Q&A: {e}")
            return None

        return QAResult(
            question=question,
            answer=response.text,
            sources_used=len(items),
        )


def _opportunities_to_text(opportunities: list[Opportunity]) -> str:
    """Convert structured opportunities to a human-readable text summary."""
    lines = []
    for i, opp in enumerate(opportunities, 1):
        lines.append(f"{i}. {opp.title} (confidence: {opp.confidence}/100)")
        lines.append(f"   PAIN: {opp.pain}")
        lines.append(f"   TARGET BUYER: {opp.target_buyer}")
        lines.append(f"   SOLUTION: {opp.solution_shape}")
        lines.append(f"   MARKET: {opp.market_type}")
        lines.append(f"   EFFORT: {opp.effort_estimate}")
        lines.append(f"   MONETIZATION: {opp.monetization}")
        lines.append(f"   MOAT: {opp.moat}")
        if opp.competition_notes:
            lines.append(f"   COMPETITION: {opp.competition_notes}")
        if opp.evidence:
            lines.append(f"   EVIDENCE ({len(opp.evidence)} sources):")
            for ev in opp.evidence:
                lines.append(f"     - [{ev.source}] {ev.item_title}")
                lines.append(f"       {ev.url}")
        lines.append("")
    return "\n".join(lines)
