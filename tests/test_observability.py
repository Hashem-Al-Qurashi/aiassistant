"""Tests for observability console — agent metrics and quality dashboard."""

import pytest
from backend.observability import AIOpsConsole


class TestAIOpsConsole:
    """Test observability metrics and quality scoring."""

    def test_get_engagement_trace(self):
        """G2: Engagement trace shows phase durations, costs, token counts."""
        console = AIOpsConsole()
        trace = console.get_engagement_trace("test-eng-1")

        assert trace["engagement_id"] == "test-eng-1"
        assert "phases" in trace
        assert len(trace["phases"]) >= 1
        assert "total_cost" in trace

    def test_phase_has_duration_and_cost(self):
        """G2: Each phase has duration_seconds, cost, token_count."""
        console = AIOpsConsole()
        trace = console.get_engagement_trace("test-eng")

        phase = trace["phases"][0]
        assert "duration_seconds" in phase
        assert "cost" in phase
        assert "token_count" in phase

    def test_get_quality_dashboard(self):
        """G2: Quality dashboard returns all metric categories."""
        console = AIOpsConsole()
        dashboard = console.get_quality_dashboard("test-eng")

        assert "evidence_coverage" in dashboard
        assert "citation_correctness" in dashboard
        assert "assumption_consistency" in dashboard
        assert "recommendation_support" in dashboard

    def test_quality_scores_in_range(self):
        """G2: Quality scores are floats in [0.0, 1.0]."""
        console = AIOpsConsole()
        dashboard = console.get_quality_dashboard("test-eng")

        for key, value in dashboard.items():
            assert isinstance(value, float)
            assert 0.0 <= value <= 1.0

    def test_get_phase_duration(self):
        """G2: Phase duration lookup for specific phase."""
        console = AIOpsConsole()
        duration = console.get_phase_duration("test-eng", "discovery")

        assert isinstance(duration, float)
        assert duration > 0

    def test_get_total_cost(self):
        """G2: Total cost retrieval."""
        console = AIOpsConsole()
        cost = console.get_total_cost("test-eng")

        assert isinstance(cost, float)
        assert cost > 0
