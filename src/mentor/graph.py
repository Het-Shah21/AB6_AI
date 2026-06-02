"""LangGraph assembly for the 8-stage mentor cycle.

Topology:

  prior_info -> observe -> analyze -> inference -> interpret
                                                    |
                                                    v
                                                intelligence
                                                    |
                                                    v
                          +-- HITL interrupt -- intervention
                                                    |
                                                    v
                                                feedback -> END

The graph is compiled with a `MemorySaver` checkpointer and
`interrupt_before=["intervention"]` so cycles that require human
approval are paused and can be resumed via `Command(resume=...)`.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.mentor.stages import (
    analyze,
    feedback,
    inference,
    intelligence,
    interpret,
    intervention,
    observe,
    prior_info,
)
from src.mentor.state import MentorState


def _continue_router(state: dict[str, Any]) -> str:
    """After interpret, route based on whether we have candidates."""
    interpreted = state.get("interpreted") or {}
    if not interpreted.get("candidate_actions"):
        return "feedback"
    return "intelligence"


def _policy_router(state: dict[str, Any]) -> str:
    """After intelligence, always go to intervention (the interrupt
    lives inside the intervention node itself)."""
    return "intervention"


def build_graph() -> StateGraph:
    g = StateGraph(MentorState)
    g.add_node("prior_info", prior_info.run)
    g.add_node("observe", observe.run)
    g.add_node("analyze", analyze.run)
    g.add_node("inference", inference.run)
    g.add_node("interpret", interpret.run)
    g.add_node("intelligence", intelligence.run)
    g.add_node("intervention", intervention.run)
    g.add_node("feedback", feedback.run)

    g.add_edge(START, "prior_info")
    g.add_edge("prior_info", "observe")
    g.add_edge("observe", "analyze")
    g.add_edge("analyze", "inference")
    g.add_edge("inference", "interpret")
    g.add_conditional_edges(
        "interpret",
        _continue_router,
        {"intelligence": "intelligence", "feedback": "feedback"},
    )
    g.add_edge("intelligence", "intervention")
    g.add_edge("intervention", "feedback")
    g.add_edge("feedback", END)
    return g


_compiled = None


def get_compiled_graph():
    global _compiled
    if _compiled is None:
        g = build_graph()
        _compiled = g.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["intervention"],
        )
    return _compiled
