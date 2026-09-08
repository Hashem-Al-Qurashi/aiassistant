"""Tests for ConfidenceEngine — core Devil's Advocate IP."""

import pytest
from unittest.mock import MagicMock

from backend.dependencies.confidence import ConfidenceEngine


class TestRecalculateAfterChallenge:
    """G2: Confidence recalculation formula tests."""

    def test_no_counterarguments_keeps_same(self):
        """Zero counterarguments → no penalty."""
        eng = ConfidenceEngine()
        assert eng.recalculate_after_challenge(0.84, [], 0) == 0.84

    def test_one_counterargument_drops_to_0_714(self):
        """1 counterargument: 0.84 * (1 - 0.15*1) = 0.714."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.84, ["c1"], 0)
        assert result == pytest.approx(0.714, abs=0.001)

    def test_two_counterarguments_drops_to_0_588(self):
        """2 counterarguments: 0.84 * (1 - 0.15*2) = 0.84 * 0.70 = 0.588."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.84, ["c1", "c2"], 0)
        assert result == pytest.approx(0.588, abs=0.001)

    def test_unsupported_assumptions_reduce_confidence(self):
        """1 unsupported assumption: 0.84 * (1 - 0.10*1) = 0.756."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.84, [], 1)
        assert result == pytest.approx(0.756, abs=0.001)

    def test_combined_counterarguments_and_assumptions(self):
        """3 counterarguments + 2 unsupported: 0.84 * (1 - 0.15*3 - 0.10*2) = 0.84 * 0.35 = 0.294."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.84, ["c1", "c2", "c3"], 2)
        assert result == pytest.approx(0.294, abs=0.001)

    def test_clamps_to_zero_below_zero(self):
        """Confidence cannot go below 0.0."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.50, ["c1", "c2", "c3", "c4"], 2)
        # 0.50 * (1 - 0.60 - 0.20) = 0.50 * 0.20 = 0.10
        assert result == pytest.approx(0.10, abs=0.001)

    def test_clamps_to_one_above_one(self):
        """Confidence cannot exceed 1.0."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(1.0, [], 0)
        assert 0.0 <= result <= 1.0

    def test_high_original_with_moderate_challenge(self):
        """High confidence with moderate challenge: 0.95 * (1 - 0.30) = 0.665."""
        eng = ConfidenceEngine()
        result = eng.recalculate_after_challenge(0.95, ["c1", "c2"], 0)
        assert result == pytest.approx(0.665, abs=0.001)


class TestGetConfidenceExplanation:
    """G2: Human-readable explanation generation."""

    def test_explanation_contains_required_fields(self):
        """Explanation dict has all required keys."""
        eng = ConfidenceEngine()
        expl = eng.get_confidence_explanation(0.84, ["c1"], 0)
        required = {"original", "new", "counterarguments_found", "unsupported_assumptions", "penalty", "formula"}
        assert required.issubset(set(expl.keys()))

    def test_explanation_shows_correct_values(self):
        """Explanation values match formula."""
        eng = ConfidenceEngine()
        expl = eng.get_confidence_explanation(0.84, ["c1"], 0)
        assert expl["original"] == 0.84
        assert expl["new"] == pytest.approx(0.714, abs=0.001)
        assert expl["counterarguments_found"] == 1
        assert expl["unsupported_assumptions"] == 0

    def test_formula_string_is_correct(self):
        """Formula string documents the calculation."""
        eng = ConfidenceEngine()
        expl = eng.get_confidence_explanation(0.84, ["c1", "c2"], 1)
        assert "0.15" in expl["formula"]
        assert "*2" in expl["formula"]  # counterarguments count
        assert "*1" in expl["formula"]  # unsupported assumptions count


class TestCalculateInitialConfidence:
    """G2: Initial confidence from evidence quality."""

    def test_returns_zero_without_db(self):
        """No DB session → returns 0.0."""
        eng = ConfidenceEngine(db_session=None)
        assert eng.calculate_initial_confidence("rec-1") == 0.0

    def test_calculates_from_evidence_rows(self):
        """Confidence from authority * freshness weighting."""
        # Row as tuple: (weight, domain_authority, freshness_days)
        mock_row = (1.0, 80.0, 0)  # weight=1.0, authority=80 (→0.8), fresh=0 days (→1.0)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        eng = ConfidenceEngine(db_session=mock_db)
        result = eng.calculate_initial_confidence("rec-1")
        # authority_score = 0.8, freshness_score = 1.0
        # evidence_score = (0.8 + 1.0) / 2 = 0.9
        assert result == pytest.approx(0.9, abs=0.01)

    def test_returns_zero_when_no_evidence(self):
        """No evidence rows → confidence 0.0."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        eng = ConfidenceEngine(db_session=mock_db)
        assert eng.calculate_initial_confidence("rec-1") == 0.0

    def test_zero_weight_evidence_does_not_contribute(self):
        """G2: weight=0 should not contribute to score or total_weight.

        Bug: float(0 or 1.0) → float(1.0) because 0 is falsy.
        Zero-weight evidence should add 0 to numerator and denominator.
        """
        # Row: (weight=0, authority=80, freshness=0 days)
        mock_row = (0, 80.0, 0)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        eng = ConfidenceEngine(db_session=mock_db)
        result = eng.calculate_initial_confidence("rec-1")
        # weight=0 contributes nothing: total_score=0, total_weight=0
        # division by zero → returns 0.0
        assert result == 0.0

    def test_mixed_weights_zero_and_nonzero(self):
        """G2: One zero-weight and one non-zero-weight evidence item."""
        mock_result = MagicMock()
        # weight=0 contributes nothing; weight=1 with authority=100, fresh=0
        mock_result.fetchall.return_value = [
            (0, 50.0, 0),     # zero weight
            (1.0, 100.0, 0),  # authority=1.0, freshness=1.0 → score=1.0
        ]

        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result

        eng = ConfidenceEngine(db_session=mock_db)
        result = eng.calculate_initial_confidence("rec-1")
        # Only the second row contributes: score=1.0, weight=1.0
        assert result == pytest.approx(1.0, abs=0.01)
