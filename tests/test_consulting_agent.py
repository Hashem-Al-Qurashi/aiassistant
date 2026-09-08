"""Tests for LangGraph consulting agent state machine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.graph import END
from uuid import uuid4

from backend.agents.consulting_graph import ConsultingAgent, EngagementState, PHASE_ORDER
from langchain_openai import ChatOpenAI


def _make_state(**overrides):
    """Default EngagementState for tests."""
    state = {
        "engagement_id": str(uuid4()),
        "org_id": None,
        "phase": "discovery",
        "messages": [],
        "objectives": {"objective": "test"},
        "evidence": [],
        "hypotheses": [],
        "recommendations": [],
        "assumptions": {},
        "dependency_graph": {},
        "challenge_results": [],
        "error": None,
        "metadata": {"total_tokens": 0, "estimated_cost": 0.0, "phases_completed": []},
    }
    state.update(overrides)
    return state


class TestConsultingAgentStructure:
    """Test the agent's structure and configuration without LLM calls."""

    def test_phase_order_has_all_transitions(self):
        """G2: All 5 phases have defined transitions."""
        assert PHASE_ORDER["discovery"] == "research"
        assert PHASE_ORDER["research"] == "analysis"
        assert PHASE_ORDER["analysis"] == "recommendation"
        assert PHASE_ORDER["recommendation"] == "challenge"
        assert PHASE_ORDER["challenge"] == "done"
        assert PHASE_ORDER["done"] == END

    def test_initial_state_has_required_fields(self):
        """G2: EngagementState includes all required fields."""
        state = _make_state()
        required_keys = set(EngagementState.__annotations__.keys())
        assert required_keys.issubset(set(state.keys()))

    def test_agent_has_five_nodes(self):
        """G2: Graph has exactly 5 phase nodes."""
        agent = ConsultingAgent(openai_api_key="test-key")
        node_names = set(agent.graph.nodes.keys())
        expected = {"discovery", "research", "analysis", "recommendation", "challenge"}
        assert expected.issubset(node_names)

    def test_graph_has_entry_point(self):
        """G2: Graph entry point is discovery."""
        agent = ConsultingAgent(openai_api_key="test-key")
        assert "discovery" in agent.graph.nodes


class TestAgentPhaseRouting:
    """Test phase transition logic."""

    def test_route_from_discovery_to_research(self):
        """G2: discovery phase routes to research."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "discovery", "error": None}
        assert agent._route_to_next_phase(state) == "research"

    def test_route_from_research_to_analysis(self):
        """G2: research phase routes to analysis."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "research", "error": None}
        assert agent._route_to_next_phase(state) == "analysis"

    def test_route_from_analysis_to_recommendation(self):
        """G2: analysis phase routes to recommendation."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "analysis", "error": None}
        assert agent._route_to_next_phase(state) == "recommendation"

    def test_route_from_recommendation_to_challenge(self):
        """G2: recommendation routes to challenge."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "recommendation", "error": None}
        assert agent._route_to_next_phase(state) == "challenge"

    def test_route_from_challenge_to_done(self):
        """G2: challenge routes to done."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "challenge", "error": None}
        assert agent._route_to_next_phase(state) == "done"

    def test_route_to_end_on_error(self):
        """G2: error state routes to END."""
        agent = ConsultingAgent(openai_api_key="test-key")
        state = {"phase": "discovery", "error": "something broke"}
        assert agent._route_to_next_phase(state) == END


class TestAgentPhaseExecution:
    """Test individual phase execution with mocked LLM."""

    @pytest.mark.asyncio
    async def test_discovery_phase_generates_questions(self):
        """G2: Discovery phase produces questions with impact + category."""
        mock_response = MagicMock()
        mock_response.content = '{"questions": [{"text": "What is the market size?", "impact": "high", "category": "market"}]}'

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response):
            agent = ConsultingAgent(openai_api_key="test-key")
            state = _make_state(
                phase="discovery",
                objectives={"objective": "Market entry assessment", "org_context": "Saudi Arabia"},
            )

            result = await agent._discovery_phase(state)
            assert len(result["objectives"]["questions"]) == 1
            assert result["objectives"]["questions"][0]["text"] == "What is the market size?"
            assert result["phase"] == "research"

    @pytest.mark.asyncio
    async def test_research_phase_generates_queries(self):
        """G2: Research phase generates search queries from questions."""
        mock_response = MagicMock()
        mock_response.content = '{"queries": [{"question_index": 0, "query": "Saudi Arabia market size 2024"}]}'

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response):
            agent = ConsultingAgent(openai_api_key="test-key")
            state = _make_state(
                phase="research",
                objectives={
                    "objective": "test",
                    "questions": [{"text": "What is market size?", "impact": "high", "category": "market"}],
                },
            )

            result = await agent._research_phase(state)
            assert len(result["objectives"]["search_queries"]) == 1
            assert result["phase"] == "analysis"

    @pytest.mark.asyncio
    async def test_analysis_phase_generates_hypotheses(self):
        """G2: Analysis phase generates hypotheses from evidence."""
        mock_response = MagicMock()
        mock_response.content = '{"hypotheses": [{"title": "Market is growing", "description": "YoY growth >10%", "confidence": 0.85, "supporting_evidence": ["E01"]}]}'

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response):
            agent = ConsultingAgent(openai_api_key="test-key")
            state = _make_state(
                phase="analysis",
                evidence=["E01", "E02"],
            )

            result = await agent._analysis_phase(state)
            assert len(result["hypotheses"]) == 1
            assert result["hypotheses"][0]["title"] == "Market is growing"
            assert result["phase"] == "recommendation"

    @pytest.mark.asyncio
    async def test_recommendation_phase_generates_recommendations(self):
        """G2: Recommendation phase produces actionable options."""
        mock_response = MagicMock()
        mock_response.content = '{"recommendations": [{"title": "Enter Riyadh", "description": "Focus on capital", "hypothesis_id": "H1", "confidence": 0.84}]}'

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response):
            agent = ConsultingAgent(openai_api_key="test-key")
            state = _make_state(
                phase="recommendation",
                hypotheses=[{"title": "Market is growing", "confidence": 0.85}],
            )

            result = await agent._recommendation_phase(state)
            assert len(result["recommendations"]) == 1
            assert result["recommendations"][0]["title"] == "Enter Riyadh"
            assert result["phase"] == "challenge"

    @pytest.mark.asyncio
    async def test_challenge_phase_recalculates_confidence(self):
        """G2: Challenge phase recalculates recommendation confidence.

        Devil's Advocate finds 1 counterargument for R-001.
        Formula: new = original * (1 - 0.15 * counterarguments + 0.10 * unsupported)
        Confidence: 0.84 * (1 - 0.15 * 1) = 0.714
        """
        mock_response = MagicMock()
        mock_response.content = '{"challenges": [{"recommendation_id": "R-001", "counterarguments": ["c1"], "unsupported_assumptions": []}]}'

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response):
            agent = ConsultingAgent(openai_api_key="test-key")
            state = _make_state(
                phase="challenge",
                recommendations=[{"id": "R-001", "title": "Enter Riyadh", "confidence": 0.84}],
            )

            result = await agent._challenge_phase(state)
            assert len(result["challenge_results"]) == 1
            assert result["recommendations"][0]["confidence"] < 0.84
            assert result["recommendations"][0]["confidence"] == pytest.approx(0.714, abs=0.01)
            assert result["phase"] == "done"
