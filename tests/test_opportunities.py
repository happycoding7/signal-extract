"""
Tests for structured opportunity intelligence:
- JSON parsing and validation
- DB storage and queries
- API endpoint filters and validation
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Opportunity, EvidenceRef, Item, Source
from synthesizer.engine import (
    _extract_json_array,
    _validate_opportunity_dict,
    parse_opportunities_json,
    VALID_EFFORT_ESTIMATES,
)
from storage.db import Storage


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

def _make_valid_opportunity_dict(**overrides):
    """Factory for a valid opportunity dict."""
    base = {
        "id": "terraform-drift-detector",
        "title": "Terraform Drift Detector",
        "pain": "Teams lose track of infrastructure drift between planned and actual state.",
        "target_buyer": "DevOps lead",
        "solution_shape": "CLI + SaaS dashboard that continuously monitors Terraform state.",
        "market_type": "boring/growing",
        "effort_estimate": "1-2 weeks",
        "monetization": "Per-repo, $50-200/month per team.",
        "moat": "Deep integration with Terraform state files and cloud provider APIs.",
        "confidence": 75,
        "evidence": [
            {
                "source": "github_issue",
                "item_title": "Terraform drift detection is broken",
                "url": "https://github.com/hashicorp/terraform/issues/12345",
                "score": 65,
            }
        ],
        "competition_notes": "Spacelift and env0 exist but are expensive and complex.",
    }
    base.update(overrides)
    return base


def _make_valid_json_response(**overrides):
    """Build a raw JSON string like an LLM would return."""
    return json.dumps([_make_valid_opportunity_dict(**overrides)])


@pytest.fixture
def tmp_storage():
    """Create a temporary Storage instance for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        storage = Storage(db_path)
        yield storage
        storage.close()


@pytest.fixture
def populated_storage(tmp_storage):
    """Storage with some items and opportunities pre-loaded."""
    # Insert some items
    for i in range(5):
        item = Item(
            source=Source.GITHUB_ISSUE,
            source_id=f"test-{i}",
            url=f"https://example.com/{i}",
            title=f"Test item {i}",
            body=f"Body of test item {i}",
            score=50 + i * 10,
        )
        tmp_storage.insert_item(item)

    # Save a digest
    tmp_storage.save_digest("opportunities", "Test digest content", 5)

    # Create opportunities
    opps = [
        Opportunity(
            id="terraform-drift-detector",
            title="Terraform Drift Detector",
            pain="Infrastructure drift is a pain.",
            target_buyer="DevOps lead",
            solution_shape="CLI + dashboard for drift monitoring.",
            market_type="boring/growing",
            effort_estimate="1-2 weeks",
            monetization="Per-repo $100/mo.",
            moat="Deep Terraform integration.",
            confidence=82,
            evidence=[
                EvidenceRef(
                    source="github_issue",
                    item_title="Drift detection broken",
                    url="https://github.com/hashicorp/terraform/issues/123",
                    score=70,
                )
            ],
            competition_notes="Spacelift exists but is expensive.",
        ),
        Opportunity(
            id="secrets-rotation-saas",
            title="Secrets Rotation SaaS",
            pain="Manual secret rotation causes outages.",
            target_buyer="CISO",
            solution_shape="Automated secrets rotation service.",
            market_type="boring/growing",
            effort_estimate="month+",
            monetization="Platform fee $500/mo.",
            moat="Compliance certifications.",
            confidence=60,
            evidence=[
                EvidenceRef(
                    source="hacker_news",
                    item_title="Secrets management is broken",
                    url="https://news.ycombinator.com/item?id=999",
                    score=55,
                )
            ],
            competition_notes="Vault is complex, CyberArk is enterprise-only.",
        ),
    ]
    run_id = tmp_storage.save_opportunity_run(opps, item_count=5, digest_id=1)
    return tmp_storage, run_id


# ──────────────────────────────────────────────
# JSON extraction tests
# ──────────────────────────────────────────────

class TestExtractJsonArray:
    def test_plain_array(self):
        assert _extract_json_array('[{"a": 1}]') == '[{"a": 1}]'

    def test_with_markdown_fences(self):
        text = '```json\n[{"a": 1}]\n```'
        assert _extract_json_array(text) == '[{"a": 1}]'

    def test_with_surrounding_text(self):
        text = 'Here are the results:\n[{"a": 1}]\nDone.'
        assert _extract_json_array(text) == '[{"a": 1}]'

    def test_nested_arrays(self):
        text = '[{"a": [1, 2, 3]}, {"b": [4]}]'
        assert _extract_json_array(text) == text

    def test_empty_array(self):
        assert _extract_json_array("[]") == "[]"

    def test_no_array(self):
        with pytest.raises(ValueError, match="No JSON array"):
            _extract_json_array("just some text")

    def test_unbalanced_brackets(self):
        with pytest.raises(ValueError, match="Unbalanced"):
            _extract_json_array("[{incomplete")


# ──────────────────────────────────────────────
# Validation tests
# ──────────────────────────────────────────────

class TestValidateOpportunityDict:
    def test_valid(self):
        d = _make_valid_opportunity_dict()
        errors = _validate_opportunity_dict(d)
        assert errors == []

    def test_missing_required_field(self):
        d = _make_valid_opportunity_dict()
        del d["title"]
        errors = _validate_opportunity_dict(d)
        assert any("title" in e for e in errors)

    def test_empty_string_field(self):
        d = _make_valid_opportunity_dict(title="")
        errors = _validate_opportunity_dict(d)
        assert any("title" in e for e in errors)

    def test_confidence_out_of_range(self):
        d = _make_valid_opportunity_dict(confidence=150)
        errors = _validate_opportunity_dict(d)
        assert any("confidence" in e for e in errors)

    def test_confidence_negative(self):
        d = _make_valid_opportunity_dict(confidence=-5)
        errors = _validate_opportunity_dict(d)
        assert any("confidence" in e for e in errors)

    def test_confidence_not_number(self):
        d = _make_valid_opportunity_dict(confidence="high")
        errors = _validate_opportunity_dict(d)
        assert any("confidence" in e for e in errors)

    def test_invalid_effort_estimate(self):
        d = _make_valid_opportunity_dict(effort_estimate="3 months")
        errors = _validate_opportunity_dict(d)
        assert any("effort_estimate" in e for e in errors)

    def test_all_valid_effort_estimates(self):
        for effort in VALID_EFFORT_ESTIMATES:
            d = _make_valid_opportunity_dict(effort_estimate=effort)
            errors = _validate_opportunity_dict(d)
            assert errors == [], f"Failed for effort_estimate={effort}"

    def test_empty_evidence_array(self):
        d = _make_valid_opportunity_dict(evidence=[])
        errors = _validate_opportunity_dict(d)
        assert any("evidence" in e for e in errors)

    def test_evidence_missing_field(self):
        d = _make_valid_opportunity_dict(evidence=[{"source": "github_issue"}])
        errors = _validate_opportunity_dict(d)
        assert any("evidence" in e for e in errors)


# ──────────────────────────────────────────────
# Full parsing tests
# ──────────────────────────────────────────────

class TestParseOpportunitiesJson:
    def test_valid_single(self):
        raw = _make_valid_json_response()
        opps = parse_opportunities_json(raw)
        assert len(opps) == 1
        assert opps[0].id == "terraform-drift-detector"
        assert opps[0].confidence == 75
        assert len(opps[0].evidence) == 1

    def test_valid_with_markdown(self):
        raw = f"```json\n{_make_valid_json_response()}\n```"
        opps = parse_opportunities_json(raw)
        assert len(opps) == 1

    def test_empty_array(self):
        opps = parse_opportunities_json("[]")
        assert opps == []

    def test_multiple_opportunities(self):
        items = [
            _make_valid_opportunity_dict(id="opp-1", title="Opp 1"),
            _make_valid_opportunity_dict(id="opp-2", title="Opp 2"),
        ]
        raw = json.dumps(items)
        opps = parse_opportunities_json(raw)
        assert len(opps) == 2

    def test_partial_failure_keeps_valid(self):
        """If one opportunity fails validation, the rest should still parse."""
        items = [
            _make_valid_opportunity_dict(id="good-one"),
            {"id": "bad-one"},  # Missing required fields
        ]
        raw = json.dumps(items)
        opps = parse_opportunities_json(raw)
        assert len(opps) == 1
        assert opps[0].id == "good-one"

    def test_all_invalid_raises(self):
        """If all opportunities fail validation, raise ValueError."""
        items = [
            {"id": "bad-1"},
            {"id": "bad-2"},
        ]
        raw = json.dumps(items)
        with pytest.raises(ValueError, match="All .* opportunities failed"):
            parse_opportunities_json(raw)

    def test_invalid_json(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            parse_opportunities_json("not json at all")

    def test_competition_notes_optional(self):
        d = _make_valid_opportunity_dict()
        del d["competition_notes"]
        raw = json.dumps([d])
        opps = parse_opportunities_json(raw)
        assert len(opps) == 1
        assert opps[0].competition_notes == ""

    def test_evidence_score_defaults_to_zero(self):
        d = _make_valid_opportunity_dict()
        d["evidence"][0].pop("score", None)
        raw = json.dumps([d])
        opps = parse_opportunities_json(raw)
        assert opps[0].evidence[0].score == 0


# ──────────────────────────────────────────────
# Database tests
# ──────────────────────────────────────────────

class TestOpportunityDB:
    def test_save_and_retrieve(self, tmp_storage):
        opp = Opportunity(
            id="test-opp",
            title="Test Opportunity",
            pain="A test pain point.",
            target_buyer="CTO",
            solution_shape="A test solution.",
            market_type="boring/growing",
            effort_estimate="weekend",
            monetization="$100/mo",
            moat="Test moat.",
            confidence=90,
            evidence=[
                EvidenceRef(
                    source="hacker_news",
                    item_title="Test HN post",
                    url="https://example.com/hn/1",
                    score=80,
                )
            ],
        )
        run_id = tmp_storage.save_opportunity_run([opp], item_count=10)
        assert run_id is not None
        assert run_id > 0

        # Retrieve
        result = tmp_storage.get_opportunity_by_id("test-opp")
        assert result is not None
        assert result["id"] == "test-opp"
        assert result["confidence"] == 90
        assert result["target_buyer"] == "CTO"
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["source"] == "hacker_news"

    def test_get_opportunities_with_filters(self, populated_storage):
        storage, run_id = populated_storage

        # No filter
        results, total = storage.get_opportunities()
        assert total == 2
        assert len(results) == 2

        # Filter by confidence
        results, total = storage.get_opportunities(min_confidence=70)
        assert total == 1
        assert results[0]["id"] == "terraform-drift-detector"

        # Filter by buyer
        results, total = storage.get_opportunities(target_buyer="CISO")
        assert total == 1
        assert results[0]["id"] == "secrets-rotation-saas"

        # Filter by market
        results, total = storage.get_opportunities(market_type="boring")
        assert total == 2  # Both are boring/growing

    def test_get_opportunities_pagination(self, populated_storage):
        storage, _ = populated_storage

        results, total = storage.get_opportunities(limit=1, offset=0)
        assert total == 2
        assert len(results) == 1
        first_id = results[0]["id"]

        results, total = storage.get_opportunities(limit=1, offset=1)
        assert total == 2
        assert len(results) == 1
        assert results[0]["id"] != first_id

    def test_get_opportunity_by_id_not_found(self, tmp_storage):
        result = tmp_storage.get_opportunity_by_id("nonexistent")
        assert result is None

    def test_opportunity_trends(self, populated_storage):
        storage, run_id = populated_storage
        trends = storage.get_opportunity_trends()
        assert len(trends) == 2

        # Each trend should have exactly 1 data point (single run)
        for t in trends:
            assert len(t["data_points"]) == 1
            assert t["data_points"][0]["run_id"] == run_id

    def test_multiple_runs_create_trends(self, populated_storage):
        storage, first_run_id = populated_storage

        # Add a second run with updated confidence
        opps = [
            Opportunity(
                id="terraform-drift-detector",
                title="Terraform Drift Detector v2",
                pain="Still a pain.",
                target_buyer="DevOps lead",
                solution_shape="Updated solution.",
                market_type="boring/growing",
                effort_estimate="1-2 weeks",
                monetization="$200/mo",
                moat="Deeper integration.",
                confidence=90,
                evidence=[
                    EvidenceRef(
                        source="github_issue",
                        item_title="New drift issue",
                        url="https://github.com/hashicorp/terraform/issues/456",
                        score=75,
                    )
                ],
            ),
        ]
        second_run_id = storage.save_opportunity_run(opps, item_count=3)

        trends = storage.get_opportunity_trends()
        tf_trend = next(t for t in trends if t["id"] == "terraform-drift-detector")
        assert len(tf_trend["data_points"]) == 2
        assert tf_trend["data_points"][0]["confidence"] == 82
        assert tf_trend["data_points"][1]["confidence"] == 90


# ──────────────────────────────────────────────
# API tests
# ──────────────────────────────────────────────

class TestOpportunitiesAPI:
    @pytest.fixture
    def client(self, populated_storage):
        storage, _ = populated_storage
        # Get db_path from the storage connection
        db_path = Path(storage._conn.execute("PRAGMA database_list").fetchone()[2])
        storage.close()

        from api.server import create_app
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_list_opportunities(self, client):
        resp = client.get("/api/opportunities")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "opportunities" in data
        assert "total" in data
        assert data["total"] == 2

    def test_list_opportunities_filter_confidence(self, client):
        resp = client.get("/api/opportunities?min_confidence=70")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["opportunities"][0]["id"] == "terraform-drift-detector"

    def test_list_opportunities_filter_buyer(self, client):
        resp = client.get("/api/opportunities?buyer=CISO")
        data = resp.get_json()
        assert data["total"] == 1

    def test_list_opportunities_filter_market(self, client):
        resp = client.get("/api/opportunities?market_type=boring")
        data = resp.get_json()
        assert data["total"] == 2

    def test_list_opportunities_invalid_confidence(self, client):
        resp = client.get("/api/opportunities?min_confidence=abc")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_list_opportunities_confidence_out_of_range(self, client):
        resp = client.get("/api/opportunities?min_confidence=150")
        assert resp.status_code == 400

    def test_get_opportunity_by_id(self, client):
        resp = client.get("/api/opportunities/terraform-drift-detector")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "terraform-drift-detector"
        assert "evidence" in data
        assert len(data["evidence"]) >= 1

    def test_get_opportunity_not_found(self, client):
        resp = client.get("/api/opportunities/nonexistent-thing")
        assert resp.status_code == 404

    def test_opportunity_trends(self, client):
        resp = client.get("/api/opportunities/trends")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trends" in data
        assert len(data["trends"]) == 2

    def test_pagination(self, client):
        resp = client.get("/api/opportunities?limit=1&offset=0")
        data = resp.get_json()
        assert len(data["opportunities"]) == 1
        assert data["total"] == 2

    def test_invalid_limit(self, client):
        resp = client.get("/api/opportunities?limit=notanumber")
        assert resp.status_code == 400

    def test_invalid_offset(self, client):
        resp = client.get("/api/opportunities?offset=notanumber")
        assert resp.status_code == 400
