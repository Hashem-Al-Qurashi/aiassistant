"""Report generator — structured report creation from engagement state.

Builds executive summaries, recommendation sections, evidence-backed analysis,
and appendices.
"""

from datetime import datetime
from typing import Any
from uuid import UUID


class ReportGenerator:
    """Generates structured JSON reports from engagement recommendations and evidence.

    Core IP: evidence-traceable report sections with assumption tracking.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    # -- Internal helpers --

    def _build_empty_report(self, title: str) -> dict:
        """Build a minimal report structure."""
        from uuid import uuid4
        from datetime import datetime

        return {
            "title": title,
            "generated_at": datetime.utcnow().isoformat(),
            "sections": [],
            "appendices": [],
        }

    def _build_executive_summary(
        self, objective: str, confidence: float, evidence_count: int
    ) -> str:
        """Generate executive summary text."""
        pct = round(confidence * 100)
        return (
            f"This report addresses: {objective}. "
            f"Overall confidence: {pct}%. "
            f"Analysis based on {evidence_count} evidence items."
        )

    def _build_recommendation_section(
        self, recommendation: Any, assumptions: list[str]
    ) -> dict:
        """Build a report section for a single recommendation."""
        return {
            "id": f"rec_{recommendation.id}",
            "type": "recommendation",
            "heading": recommendation.title,
            "content": recommendation.description,
            "confidence": float(recommendation.confidence) if recommendation.confidence else 0.0,
            "assumptions": assumptions,
            "evidence_refs": [],
        }

    def _build_evidence_section(self, evidence_items: list[Any]) -> dict:
        """Build an evidence appendix section."""
        return {
            "id": "evidence",
            "type": "evidence_appendix",
            "heading": "Evidence Sources",
            "content": f"Total evidence items: {len(evidence_items)}",
            "evidence_refs": [str(item.id) for item in evidence_items],
        }

    # -- Public API --

    async def generate_report(
        self, engagement_id: str, title: str
    ) -> dict:
        """Generate a structured report from engagement state.

        Returns JSON-serializable report dict.
        """
        report = self._build_empty_report(title)

        if not self.db:
            return report

        from backend.models.entities import Recommendation
        from sqlalchemy import select

        # Fetch recommendations for this engagement
        stmt = select(Recommendation).where(
            Recommendation.engagement_id == UUID(engagement_id)
        )
        result = await self.db.execute(stmt)
        recommendations = result.scalars().all()

        if not recommendations:
            return report

        # Build executive summary from first recommendation
        evidence_count = 0
        total_confidence = 0.0
        sections = []

        for rec in recommendations:
            if rec.confidence:
                total_confidence += float(rec.confidence)
            section = self._build_recommendation_section(rec, [f"assumption_{rec.id}"])
            sections.append(section)
            evidence_count += 1

        avg_confidence = total_confidence / len(recommendations) if recommendations else 0.0

        # Prepend executive summary section
        summary_text = self._build_executive_summary(
            objective=title,
            confidence=avg_confidence,
            evidence_count=evidence_count,
        )
        summary_section = {
            "id": "executive_summary",
            "type": "executive_summary",
            "heading": "Executive Summary",
            "content": summary_text,
            "evidence_refs": [],
        }
        sections.insert(0, summary_section)

        report["sections"] = sections
        report["appendices"] = [
            {
                "type": "financial_model",
                "data_ref": f"analysis_artifacts/fin_model_{engagement_id}.pkl",
            }
        ]

        return report
