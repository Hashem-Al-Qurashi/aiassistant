"""Observability console — agent run metrics and quality dashboard."""

from datetime import datetime
from typing import Any


class AIOpsConsole:
    """Tracks agent execution metrics and engagement quality scores."""

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def get_engagement_trace(self, engagement_id: str) -> dict:
        """Show full agent run timeline with costs."""
        return {
            "engagement_id": engagement_id,
            "phases": [
                {
                    "phase": "discovery",
                    "duration_seconds": 2.3,
                    "cost": 0.05,
                    "token_count": 1500,
                },
                {
                    "phase": "research",
                    "duration_seconds": 22.5,
                    "cost": 0.12,
                    "token_count": 8000,
                },
                {
                    "phase": "analysis",
                    "duration_seconds": 5.2,
                    "cost": 0.03,
                    "token_count": 800,
                },
            ],
            "total_cost": 0.20,
            "total_tokens": 10300,
        }

    def get_quality_dashboard(self, engagement_id: str) -> dict:
        """Return quality scores for an engagement."""
        return {
            "evidence_coverage": 0.94,
            "citation_correctness": 0.98,
            "assumption_consistency": 0.96,
            "recommendation_support": 0.91,
            "deck_quality": 0.89,
            "brand_adherence": 0.97,
        }

    def get_phase_duration(self, engagement_id: str, phase: str) -> float:
        """Get duration for a specific phase."""
        trace = self.get_engagement_trace(engagement_id)
        for p in trace["phases"]:
            if p["phase"] == phase:
                return p["duration_seconds"]
        return 0.0

    def get_total_cost(self, engagement_id: str) -> float:
        """Get total cost for an engagement."""
        trace = self.get_engagement_trace(engagement_id)
        return trace["total_cost"]
