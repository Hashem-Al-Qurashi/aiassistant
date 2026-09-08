"""Confidence scoring and recalculation engine.

Core IP: Devil's Advocate challenge mode recalculates confidence scores
using the formula: new = original * (1 - 0.15 * counterarguments + 0.10 * unsupported_assumptions)
"""

from typing import Any


class ConfidenceEngine:
    """Handles confidence scores for recommendations.

    Initial confidence is based on evidence quality.
    Post-challenge confidence applies Devil's Advocate penalty.
    """

    # Penalty weights per the specification
    COUNTERARGUMENT_PENALTY = 0.15
    UNSUPPORTED_ASSUMPTION_PENALTY = 0.10

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def calculate_initial_confidence(self, recommendation_id: str) -> float:
        """Calculate initial confidence based on supporting evidence quality.

        Score = average of evidence authority * freshness * relevance, weighted by evidence weight.
        Returns float 0.0-1.0.
        """
        if not self.db:
            return 0.0

        from sqlalchemy import text

        stmt = text("""
            SELECT
                he.weight,
                s.domain_authority,
                EXTRACT(DAY FROM (NOW() - s.scraped_at)) AS freshness_days
            FROM recommendation r
            JOIN hypothesis_evidence he ON r.hypothesis_id = he.hypothesis_id
            JOIN evidence_items ei ON he.evidence_item_id = ei.id
            JOIN sources s ON ei.source_id = s.id
            WHERE r.id = :rec_id::uuid
        """)
        result = self.db.execute(stmt, {"rec_id": recommendation_id})

        rows = result.fetchall()
        if not rows:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for weight, authority, freshness_days in rows:
            authority_val = float(authority) if authority is not None else 0.0
            freshness_val = float(freshness_days) if freshness_days is not None else 365
            authority_score = min(authority_val / 100.0, 1.0)
            freshness_score = max(0.0, 1.0 - freshness_val / 365.0)
            evidence_score = (authority_score + freshness_score) / 2.0
            weight_val = float(weight) if weight is not None else 1.0
            total_score += evidence_score * weight_val
            total_weight += weight_val

        if total_weight == 0:
            return 0.0

        return round(total_score / total_weight, 4)

    def recalculate_after_challenge(
        self,
        original_confidence: float,
        counterarguments: list[str],
        unsupported_assumptions: int,
    ) -> float:
        """Recalculate confidence after Devil's Advocate challenge.

        Formula: new = original * (1 - 0.15 * counterarguments + 0.10 * unsupported_assumptions)
        Clamps to [0.0, 1.0].
        """
        penalty = (
            self.COUNTERARGUMENT_PENALTY * len(counterarguments)
            + self.UNSUPPORTED_ASSUMPTION_PENALTY * unsupported_assumptions
        )
        new_confidence = original_confidence * (1.0 - penalty)
        return max(0.0, min(1.0, round(new_confidence, 4)))

    def get_confidence_explanation(
        self,
        original_confidence: float,
        counterarguments: list[str],
        unsupported_assumptions: int,
    ) -> dict:
        """Generate human-readable explanation of confidence recalculation."""
        penalty = (
            self.COUNTERARGUMENT_PENALTY * len(counterarguments)
            + self.UNSUPPORTED_ASSUMPTION_PENALTY * unsupported_assumptions
        )
        new_confidence = max(0.0, min(1.0, round(original_confidence * (1.0 - penalty), 4)))

        return {
            "original": round(original_confidence, 4),
            "new": new_confidence,
            "counterarguments_found": len(counterarguments),
            "unsupported_assumptions": unsupported_assumptions,
            "penalty": round(penalty, 4),
            "formula": f"{original_confidence} * (1 - {self.COUNTERARGUMENT_PENALTY}*{len(counterarguments)} + {self.UNSUPPORTED_ASSUMPTION_PENALTY}*{unsupported_assumptions})",
        }
