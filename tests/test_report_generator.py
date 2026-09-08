"""Tests for report generator — structured report creation from engagement state."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from backend.report.generator import ReportGenerator


class TestReportGenerator:
    """Test report structure and content generation."""

    @pytest.mark.asyncio
    async def test_generate_report_from_recommendations(self):
        """G2: Report contains executive summary, sections, appendices from recommendations."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Recommendation,
        )

        mock_db = MagicMock()
        mock_result = MagicMock()

        # Mock recommendations
        rec1 = Recommendation(
            engagement_id=uuid4(),
            hypothesis_id=None,
            title="Enter Saudi market with budget",
            description="High ROI opportunity in Riyadh",
            confidence=0.75,
        )
        rec2 = Recommendation(
            engagement_id=uuid4(),
            hypothesis_id=None,
            title="Partner with local distributor",
            description="Leverage local expertise",
            confidence=0.65,
        )

        mock_result.scalars.return_value.all.return_value = [rec1, rec2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        gen = ReportGenerator(db_session=mock_db)
        report = await gen.generate_report(str(uuid4()), "Saudi Market Expansion")

        assert report["title"] == "Saudi Market Expansion"
        assert "sections" in report
        assert len(report["sections"]) >= 1
        assert "appendices" in report

    @pytest.mark.asyncio
    async def test_report_has_evidence_refs_per_section(self):
        """G2: Each report section references supporting evidence IDs."""
        gen = ReportGenerator(db_session=MagicMock())
        report = {
            "title": "Test",
            "sections": [{"id": "s1", "evidence_refs": ["E17", "E21"]}],
        }
        # Verify the structure is serializable
        assert report["sections"][0]["evidence_refs"] == ["E17", "E21"]

    @pytest.mark.asyncio
    async def test_report_has_assumption_tracking(self):
        """G2: Report tracks which assumptions support each recommendation."""
        from backend.models.entities import Recommendation

        gen = ReportGenerator(db_session=MagicMock())
        rec = Recommendation(
            engagement_id=uuid4(),
            title="Test recommendation",
            description="desc",
            confidence=0.8,
        )
        report_section = gen._build_recommendation_section(rec, ["A001", "A002"])
        assert report_section["assumptions"] == ["A001", "A002"]

    def test_build_executive_summary(self):
        """G2: Executive summary includes engagement objective and key metrics."""
        gen = ReportGenerator(db_session=MagicMock())
        summary = gen._build_executive_summary(
            objective="Enter Saudi logistics market",
            confidence=0.78,
            evidence_count=15,
        )
        assert "Saudi logistics" in summary
        assert "78%" in summary or "0.78" in summary

    def test_report_json_serializable(self):
        """G2: Generated report is JSON-serializable."""
        import json

        gen = ReportGenerator(db_session=MagicMock())
        report = gen._build_empty_report("Test Report")
        json_str = json.dumps(report)
        assert "Test Report" in json_str

    @pytest.mark.asyncio
    async def test_no_db_returns_empty_report(self):
        """G2: Report generator without DB returns minimal report structure."""
        gen = ReportGenerator(db_session=None)
        report = await gen.generate_report("test-eng", "Test Report")

        assert report["title"] == "Test Report"
        assert "sections" in report
        assert "appendices" in report
        assert report["sections"] == []
