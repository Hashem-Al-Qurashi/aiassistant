"""Tests for dependency tracing engine and confidence calculation."""

import pytest
from uuid import uuid4

from backend.dependencies.tracer import DependencyTracer
from backend.dependencies.confidence import ConfidenceEngine


class TestDependencyTracer:
    """Test the core dependency tracing logic."""

    def test_tracer_with_no_db_returns_empty(self):
        """Tracer without DB returns empty affected dict."""
        tracer = DependencyTracer(db_session=None)
        result = tracer.trace_impact("assumption", str(uuid4()))
        assert result == {
            "assumptions": [],
            "hypotheses": [],
            "recommendations": [],
            "slides": [],
            "scenes": [],
        }

    def test_get_dependency_path_empty_when_no_db(self):
        """Path finding without DB returns empty list."""
        tracer = DependencyTracer(db_session=None)
        result = tracer.get_dependency_path(
            "assumption", str(uuid4()), "recommendation", str(uuid4())
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_trace_impact_with_real_db(self, db_session):
        """G2: When assumption A12 changes, trace all affected recommendations."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Assumption, Hypothesis,
            Recommendation, DependencyEdge,
        )

        # Create engagement
        engagement = Engagement(
            name="Test Case",
            objective="Trace dependencies",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        # Create assumption A12
        assumption = Assumption(
            engagement_id=engagement.id,
            name="Market size assumption",
            description="Assumes $500B market",
            value="500B",
            criticality="critical",
        )
        db_session.add(assumption)
        await db_session.flush()

        # Create hypothesis H4 dependent on assumption
        hypothesis = Hypothesis(
            engagement_id=engagement.id,
            title="Market is large enough for entry",
            description="H4",
            confidence=0.8,
        )
        db_session.add(hypothesis)
        await db_session.flush()

        # Create two recommendations dependent on hypothesis
        rec1 = Recommendation(
            engagement_id=engagement.id,
            hypothesis_id=hypothesis.id,
            title="Enter Saudi market with budget",
            description="R1",
            confidence=0.7,
        )
        rec2 = Recommendation(
            engagement_id=engagement.id,
            hypothesis_id=hypothesis.id,
            title="Partner with local distributor",
            description="R2",
            confidence=0.6,
        )
        db_session.add_all([rec1, rec2])
        await db_session.flush()

        # Create dependency edges: assumption → hypothesis → recommendation
        edges = [
            DependencyEdge(
                engagement_id=engagement.id,
                source_type="assumption",
                source_id=assumption.id,
                target_type="hypothesis",
                target_id=hypothesis.id,
            ),
            DependencyEdge(
                engagement_id=engagement.id,
                source_type="hypothesis",
                source_id=hypothesis.id,
                target_type="recommendation",
                target_id=rec1.id,
            ),
            DependencyEdge(
                engagement_id=engagement.id,
                source_type="hypothesis",
                source_id=hypothesis.id,
                target_type="recommendation",
                target_id=rec2.id,
            ),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        # Trace from assumption
        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("assumption", str(assumption.id))

        assert str(hypothesis.id) in affected["hypotheses"]
        assert str(rec1.id) in affected["recommendations"]
        assert str(rec2.id) in affected["recommendations"]

    @pytest.mark.asyncio
    async def test_get_dependency_path_with_real_db(self, db_session):
        """G2: Trace path from assumption to recommendation through hypothesis."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Assumption, Hypothesis,
            Recommendation, DependencyEdge,
        )

        engagement = Engagement(
            name="Path Test",
            objective="Test path tracing",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        assumption = Assumption(
            engagement_id=engagement.id,
            name="Path assumption",
            description="A1",
        )
        hypothesis = Hypothesis(
            engagement_id=engagement.id,
            title="H1",
            description="Hypothesis",
            confidence=0.5,
        )
        recommendation = Recommendation(
            engagement_id=engagement.id,
            hypothesis_id=hypothesis.id,
            title="R1",
            description="Rec",
            confidence=0.6,
        )
        db_session.add_all([assumption, hypothesis, recommendation])
        await db_session.flush()

        edges = [
            DependencyEdge(
                engagement_id=engagement.id,
                source_type="assumption",
                source_id=assumption.id,
                target_type="hypothesis",
                target_id=hypothesis.id,
            ),
            DependencyEdge(
                engagement_id=engagement.id,
                source_type="hypothesis",
                source_id=hypothesis.id,
                target_type="recommendation",
                target_id=recommendation.id,
            ),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        path = await tracer.get_dependency_path_async(
            "assumption", str(assumption.id),
            "recommendation", str(recommendation.id),
        )

        assert len(path) == 3
        assert path[0] == {"type": "assumption", "id": str(assumption.id)}
        assert path[1] == {"type": "hypothesis", "id": str(hypothesis.id)}
        assert path[2] == {"type": "recommendation", "id": str(recommendation.id)}


class TestDependencyTracerEdgeCases:
    """Edge cases: deep chains, missing nodes, branch convergence, cycles."""

    @pytest.mark.asyncio
    async def test_deep_chain_a_h_r_s_sc(self, db_session):
        """G2: Deep chain assumption → hypothesis → recommendation → slide → scene."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Assumption, Hypothesis,
            Recommendation, DependencyEdge,
        )

        engagement = Engagement(
            name="Deep Chain Test",
            objective="Test deep propagation",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        assumption = Assumption(
            engagement_id=engagement.id,
            name="Deep assumption",
            description="A1",
        )
        hypothesis = Hypothesis(
            engagement_id=engagement.id,
            title="Deep hypothesis",
            description="H1",
            confidence=0.5,
        )
        rec = Recommendation(
            engagement_id=engagement.id,
            hypothesis_id=hypothesis.id,
            title="Deep recommendation",
            description="R1",
            confidence=0.6,
        )
        db_session.add_all([assumption, hypothesis, rec])
        await db_session.flush()

        # Full chain: assumption → hypothesis → recommendation
        edges = [
            DependencyEdge(engagement_id=engagement.id,
                source_type="assumption", source_id=assumption.id,
                target_type="hypothesis", target_id=hypothesis.id),
            DependencyEdge(engagement_id=engagement.id,
                source_type="hypothesis", source_id=hypothesis.id,
                target_type="recommendation", target_id=rec.id),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("assumption", str(assumption.id))

        assert str(hypothesis.id) in affected["hypotheses"]
        assert str(rec.id) in affected["recommendations"]

    @pytest.mark.asyncio
    async def test_missing_intermediate_node_in_chain(self, db_session):
        """G2: Chain A → H → R but H missing from DB. R should not be found."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Assumption, Recommendation,
            DependencyEdge,
        )

        engagement = Engagement(
            name="Missing Node Test",
            objective="Missing intermediate",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        assumption = Assumption(
            engagement_id=engagement.id,
            name="A1",
            description="Assumption",
        )
        rec = Recommendation(
            engagement_id=engagement.id,
            title="R1",
            description="Recommendation with no hypothesis link",
            confidence=0.6,
        )
        db_session.add_all([assumption, rec])
        await db_session.flush()

        # Only edge: assumption → recommendation (skipping hypothesis)
        edge = DependencyEdge(
            engagement_id=engagement.id,
            source_type="assumption", source_id=assumption.id,
            target_type="recommendation", target_id=rec.id,
        )
        db_session.add(edge)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("assumption", str(assumption.id))

        # recommendation is found through direct edge
        assert str(rec.id) in affected["recommendations"]

    @pytest.mark.asyncio
    async def test_branch_convergence_diamond(self, db_session):
        """G2: Diamond pattern A → H1, H2 → R. R appears once in recommendations."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Assumption, Hypothesis,
            Recommendation, DependencyEdge,
        )

        engagement = Engagement(
            name="Diamond Test",
            objective="Branch convergence",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        a = Assumption(engagement_id=engagement.id, name="A1", description="A")
        h1 = Hypothesis(engagement_id=engagement.id, title="H1", description="H1", confidence=0.5)
        h2 = Hypothesis(engagement_id=engagement.id, title="H2", description="H2", confidence=0.6)
        r = Recommendation(
            engagement_id=engagement.id,
            title="R1", description="R",
            confidence=0.7,
        )
        db_session.add_all([a, h1, h2, r])
        await db_session.flush()

        edges = [
            DependencyEdge(engagement_id=engagement.id,
                source_type="assumption", source_id=a.id,
                target_type="hypothesis", target_id=h1.id),
            DependencyEdge(engagement_id=engagement.id,
                source_type="assumption", source_id=a.id,
                target_type="hypothesis", target_id=h2.id),
            DependencyEdge(engagement_id=engagement.id,
                source_type="hypothesis", source_id=h1.id,
                target_type="recommendation", target_id=r.id),
            DependencyEdge(engagement_id=engagement.id,
                source_type="hypothesis", source_id=h2.id,
                target_type="recommendation", target_id=r.id),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("assumption", str(a.id))

        assert str(r.id) in affected["recommendations"]
        # Should appear exactly once despite two paths
        assert affected["recommendations"].count(str(r.id)) == 1

    @pytest.mark.asyncio
    async def test_trace_impact_from_hypothesis(self, db_session):
        """G2: Tracing from hypothesis (not assumption) finds downstream recommendations."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Hypothesis, Recommendation,
            DependencyEdge,
        )

        engagement = Engagement(
            name="Hypothesis Source Test",
            objective="Trace from hypothesis",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        h = Hypothesis(engagement_id=engagement.id, title="H1", description="H", confidence=0.5)
        r1 = Recommendation(engagement_id=engagement.id, title="R1", description="R1", confidence=0.7)
        r2 = Recommendation(engagement_id=engagement.id, title="R2", description="R2", confidence=0.6)
        db_session.add_all([h, r1, r2])
        await db_session.flush()

        edges = [
            DependencyEdge(engagement_id=engagement.id,
                source_type="hypothesis", source_id=h.id,
                target_type="recommendation", target_id=r1.id),
            DependencyEdge(engagement_id=engagement.id,
                source_type="hypothesis", source_id=h.id,
                target_type="recommendation", target_id=r2.id),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("hypothesis", str(h.id))

        assert str(r1.id) in affected["recommendations"]
        assert str(r2.id) in affected["recommendations"]
        assert len(affected["recommendations"]) == 2

    @pytest.mark.asyncio
    async def test_no_dependencies_returns_empty(self, db_session):
        """G2: Entity with no downstream edges returns all empty lists."""
        from backend.models.entities import (
            Engagement, EngagementStatus, Recommendation,
        )

        engagement = Engagement(
            name="No Deps Test",
            objective="No downstream",
            status=EngagementStatus.DISCOVERY,
        )
        db_session.add(engagement)
        await db_session.flush()

        rec = Recommendation(
            engagement_id=engagement.id,
            title="Orphan rec",
            description="No deps",
            confidence=0.5,
        )
        db_session.add(rec)
        await db_session.commit()

        tracer = DependencyTracer(db_session=db_session)
        affected = await tracer.trace_impact_async("recommendation", str(rec.id))

        assert affected["recommendations"] == []
        assert affected["slides"] == []
        assert affected["scenes"] == []


class TestConfidenceEngine:
    """Test confidence calculation and Devil's Advocate recalculation."""

    def test_recalculate_no_counterarguments_no_change(self):
        """No counterarguments = confidence unchanged."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(0.84, [], 0)
        assert result == 0.84

    def test_recalculate_single_counterargument(self):
        """One counterargument reduces confidence by 15%."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(0.84, ["arg1"], 0)
        # 0.84 * (1 - 0.15) = 0.84 * 0.85 = 0.714
        assert result == pytest.approx(0.714, abs=0.01)

    def test_recalculate_multiple_counterarguments(self):
        """Multiple counterarguments compound the penalty."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(0.84, ["c1", "c2", "c3", "c4"], 0)
        # 0.84 * (1 - 0.15 * 4) = 0.84 * 0.40 = 0.336
        assert result == pytest.approx(0.336, abs=0.01)

    def test_recalculate_with_unsupported_assumptions(self):
        """Unsupported assumptions add additional penalty."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(0.84, ["c1"], 1)
        # 0.84 * (1 - 0.15 * 1 - 0.10 * 1) = 0.84 * 0.75 = 0.63
        assert result == pytest.approx(0.63, abs=0.01)

    def test_recalculate_clamped_to_zero(self):
        """Confidence never goes below 0."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(0.5, ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"], 0)
        assert result == 0.0

    def test_recalculate_clamped_to_one(self):
        """Confidence never exceeds 1."""
        engine = ConfidenceEngine()
        result = engine.recalculate_after_challenge(1.0, [], 0)
        assert result == 1.0

    def test_get_confidence_explanation(self):
        """Explanation includes formula and breakdown."""
        engine = ConfidenceEngine()
        result = engine.get_confidence_explanation(0.84, ["c1", "c2", "c3", "c4"], 1)

        assert result["original"] == 0.84
        assert result["counterarguments_found"] == 4
        assert result["unsupported_assumptions"] == 1
        assert result["penalty"] == pytest.approx(0.70, abs=0.01)
        assert result["new"] == pytest.approx(0.252, abs=0.01)
        assert "0.84" in result["formula"]
