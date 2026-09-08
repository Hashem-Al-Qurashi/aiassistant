"""LangGraph consulting agent — core state machine and orchestration.

4-phase flow: Discovery → Research → Analysis → Recommendation → Challenge
State persists engagement context between phases via LangGraph checkpoints.
"""

import json
from typing import TypedDict, Any, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from backend.dependencies.tracer import DependencyTracer
from backend.dependencies.confidence import ConfidenceEngine


class EngagementState(TypedDict):
    """Persistent state carried through the 4-phase agent loop."""

    engagement_id: str
    org_id: Optional[str]
    phase: str  # discovery | research | analysis | recommendation | challenge | done
    messages: list  # Chat history
    objectives: dict  # Discovery map data
    evidence: list[str]  # EvidenceItem IDs
    hypotheses: list[dict]  # Hypothesis objects
    recommendations: list[dict]  # Recommendation objects
    assumptions: dict[str, str]  # {assumption_id: value}
    dependency_graph: dict  # Node traversal paths
    challenge_results: list[dict]  # Devil's Advocate outputs
    error: Optional[str]
    metadata: dict  # Cost tracking, token usage


# Phase ordering
PHASE_ORDER = {
    "discovery": "research",
    "research": "analysis",
    "analysis": "recommendation",
    "recommendation": "challenge",
    "challenge": "done",
    "done": END,
}


class ConsultingAgent:
    """Single consulting agent with 4-phase state machine.

    Replaces 11 specialized agents with structured tools per phase.
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=openai_api_key,
        )
        self.tracer = DependencyTracer()
        self.confidence_engine = ConfidenceEngine()
        self.checkpointer = MemorySaver()

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(EngagementState)

        # Phase nodes
        workflow.add_node("discovery", self._discovery_phase)
        workflow.add_node("research", self._research_phase)
        workflow.add_node("analysis", self._analysis_phase)
        workflow.add_node("recommendation", self._recommendation_phase)
        workflow.add_node("challenge", self._challenge_phase)

        # Conditional edges for phase routing
        workflow.add_conditional_edges(
            "discovery",
            self._route_to_next_phase,
            {"research": "research"},
        )
        workflow.add_conditional_edges(
            "research",
            self._route_to_next_phase,
            {"analysis": "analysis"},
        )
        workflow.add_conditional_edges(
            "analysis",
            self._route_to_next_phase,
            {"recommendation": "recommendation"},
        )
        workflow.add_conditional_edges(
            "recommendation",
            self._route_to_next_phase,
            {"challenge": "challenge"},
        )
        workflow.add_conditional_edges(
            "challenge",
            self._route_to_next_phase,
            {"done": END},
        )

        workflow.set_entry_point("discovery")

        return workflow.compile(checkpointer=self.checkpointer)

    def _route_to_next_phase(self, state: EngagementState) -> str:
        """Determine next phase based on current phase and completion."""
        if state.get("error"):
            return END

        current = state.get("phase", "discovery")
        next_phase = PHASE_ORDER.get(current)

        if next_phase == END:
            return "done"

        return next_phase

    async def _discovery_phase(self, state: EngagementState) -> EngagementState:
        """Phase 1: Discovery — generate targeted questions based on engagement objective."""
        if state.get("phase") != "discovery":
            # Allow transition from start
            if not state.get("phase"):
                state["phase"] = "discovery"
            else:
                return state

        objective = state.get("objectives", {}).get("objective", "")
        org_context = state.get("objectives", {}).get("org_context", "")

        system_prompt = SystemMessage(content=(
            "You are a senior strategy consultant conducting discovery for an AI "
            "consulting engagement. Your job is to generate targeted, high-impact "
            "questions that will shape the research agenda. Ask questions that "
            "reveal hidden assumptions and critical constraints.\n\n"
            "Return JSON: {\"questions\": [{\"text\": \"...\", \"impact\": \"high|medium|low\", "
            "\"category\": \"market|competition|tech|ops|finance|risk\"}]}"
        ))

        prompt = f"Objective: {objective}\nOrg Context: {org_context}"
        messages = [system_prompt, HumanMessage(content=prompt)]

        response = await self.llm.ainvoke(messages)
        state["messages"].append(HumanMessage(content=prompt))
        state["messages"].append(AIMessage(content=response.content))

        try:
            data = json.loads(response.content)
            state["objectives"]["questions"] = data.get("questions", [])
            state["phase"] = "research"
        except json.JSONDecodeError:
            state["error"] = "Failed to parse discovery phase response"
            state["objectives"]["questions"] = []
            state["phase"] = "research"

        return state

    async def _research_phase(self, state: EngagementState) -> EngagementState:
        """Phase 2: Research — gather evidence for discovery questions."""
        questions = state.get("objectives", {}).get("questions", [])
        state["phase"] = "analysis"

        if not questions:
            return state

        # Generate search queries for each question
        system_prompt = SystemMessage(content=(
            "You are a research analyst. For each question, generate 2-3 specific "
            "search queries that will find relevant evidence. Return JSON: "
            "({\"queries\": [{\"question_index\": 0, \"query\": \"...\"}]})"
        ))

        prompt = f"Questions: {json.dumps(questions)}"
        messages = [system_prompt, HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        state["messages"].append(HumanMessage(content=prompt))
        state["messages"].append(AIMessage(content=response.content))

        try:
            data = json.loads(response.content)
            state["objectives"]["search_queries"] = data.get("queries", [])
        except json.JSONDecodeError:
            state["objectives"]["search_queries"] = []

        # Evidence gathering happens via evidence_ledger tool (called externally)
        # For now, mark phase complete
        state["phase"] = "analysis"
        return state

    async def _analysis_phase(self, state: EngagementState) -> EngagementState:
        """Phase 3: Analysis — generate hypotheses from evidence."""
        evidence_ids = state.get("evidence", [])
        state["phase"] = "recommendation"

        if not evidence_ids:
            return state

        system_prompt = SystemMessage(content=(
            "You are a strategic analyst. Based on the evidence gathered, generate "
            "testable hypotheses. Each hypothesis should be specific, measurable, "
            "and backed by evidence. Return JSON: "
            "({\"hypotheses\": [{\"title\": \"...\", \"description\": \"...\", "
            "\"confidence\": 0.8, \"supporting_evidence\": [\"E01\", \"E02\"]}]})"
        ))

        evidence_summary = f"Evidence items collected: {len(evidence_ids)}"
        messages = [system_prompt, HumanMessage(content=evidence_summary)]
        response = await self.llm.ainvoke(messages)
        state["messages"].append(HumanMessage(content=evidence_summary))
        state["messages"].append(AIMessage(content=response.content))

        try:
            data = json.loads(response.content)
            state["hypotheses"] = data.get("hypotheses", [])
        except json.JSONDecodeError:
            state["hypotheses"] = []

        state["phase"] = "recommendation"
        return state

    async def _recommendation_phase(self, state: EngagementState) -> EngagementState:
        """Phase 4: Recommendation — generate options from hypotheses."""
        hypotheses = state.get("hypotheses", [])
        state["phase"] = "challenge"

        if not hypotheses:
            return state

        system_prompt = SystemMessage(content=(
            "You are a strategy consultant. Based on the hypotheses, generate 3-5 "
            "concrete, actionable recommendations. Each should link to supporting "
            "hypotheses and include a confidence score. Return JSON: "
            "({\"recommendations\": [{\"title\": \"...\", \"description\": \"...\", "
            "\"hypothesis_id\": \"H1\", \"confidence\": 0.84}]})"
        ))

        prompt = f"Hypotheses: {json.dumps(hypotheses)}"
        messages = [system_prompt, HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        state["messages"].append(HumanMessage(content=prompt))
        state["messages"].append(AIMessage(content=response.content))

        try:
            data = json.loads(response.content)
            state["recommendations"] = data.get("recommendations", [])
        except json.JSONDecodeError:
            state["recommendations"] = []

        state["phase"] = "challenge"
        return state

    async def _challenge_phase(self, state: EngagementState) -> EngagementState:
        """Phase 5: Challenge — Devil's Advocate mode."""
        recommendations = state.get("recommendations", [])
        state["phase"] = "done"

        if not recommendations:
            return state

        system_prompt = SystemMessage(content=(
            "You are a Devil's Advocate. For each recommendation, find counterarguments "
            "and identify unsupported assumptions. Return JSON: "
            "({\"challenges\": [{\"recommendation_id\": \"R1\", "
            "\"counterarguments\": [\"...\", \"...\"], "
            "\"unsupported_assumptions\": [\"...\"]}]})"
        ))

        prompt = f"Recommendations: {json.dumps(recommendations)}"
        messages = [system_prompt, HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        state["messages"].append(HumanMessage(content=prompt))
        state["messages"].append(AIMessage(content=response.content))

        try:
            data = json.loads(response.content)
            state["challenge_results"] = data.get("challenges", [])
        except json.JSONDecodeError:
            state["challenge_results"] = []

        # Recalculate confidence for each recommendation
        for rec in state["recommendations"]:
            rec_id = rec.get("id", "")
            challenge = next(
                (c for c in state["challenge_results"] if c.get("recommendation_id") == rec_id),
                None,
            )
            if challenge:
                original = rec.get("confidence", 0.5)
                new_conf = self.confidence_engine.recalculate_after_challenge(
                    original,
                    challenge.get("counterarguments", []),
                    len(challenge.get("unsupported_assumptions", [])),
                )
                rec["confidence_before_challenge"] = original
                rec["confidence"] = new_conf
                rec["challenge_results"] = challenge

        state["phase"] = "done"
        return state

    async def run(
        self,
        engagement_id: str,
        obj: str,
        org_context: str = "",
        thread_id: str = "default",
    ) -> EngagementState:
        """Run the full 5-phase consulting workflow.

        Args:
            engagement_id: UUID of the engagement
            obj: Engagement objective
            org_context: Organization context for discovery
            thread_id: LangGraph thread ID for checkpointing

        Returns:
            Final EngagementState with all phases complete
        """
        from langgraph.types import StateSnapshot

        initial_state: EngagementState = {
            "engagement_id": engagement_id,
            "org_id": None,
            "phase": "discovery",
            "messages": [],
            "objectives": {
                "objective": obj,
                "org_context": org_context,
            },
            "evidence": [],
            "hypotheses": [],
            "recommendations": [],
            "assumptions": {},
            "dependency_graph": {},
            "challenge_results": [],
            "error": None,
            "metadata": {
                "total_tokens": 0,
                "estimated_cost": 0.0,
                "phases_completed": [],
            },
        }

        config = {"configurable": {"thread_id": thread_id}}

        # Run via stream — each event is the state after a node runs
        final_state: EngagementState = initial_state
        async for event in self.graph.astream(initial_state, config):
            # LangGraph astream yields dicts keyed by node name
            # e.g. {"discovery": {...state...}}
            for node_name, node_state in event.items():
                if node_state is not None:
                    final_state = node_state
                    phase = node_state.get("phase")
                    if phase and phase not in final_state["metadata"]["phases_completed"]:
                        final_state["metadata"]["phases_completed"].append(phase)

                    if node_state.get("error"):
                        final_state["error"] = node_state["error"]
                        break

        return final_state
