"""
Writer-Critic Loop implemented as a LangGraph StateGraph.

Flow:
  synthesize → critique → (approved? → publish) or (retry < max? → synthesize) or (publish with warning)
"""

from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from agent_service.agents.critic import critique
from agent_service.agents.synthesizer import synthesize
from agent_service.models import ReportType, SynthesisRequest

load_dotenv()

MAX_RETRIES = 2


class PipelineState(TypedDict):
    # Inputs
    report_type: str
    period_start: str
    period_end: str
    items: list[dict]
    signals: list[dict]
    # Working state
    draft_title: str
    draft_content: str
    item_ids: list[int]
    feedback: str
    retry_count: int
    # Outputs
    final_title: str
    final_content: str
    quality_score: float
    critic_feedback: dict
    approved: bool


def synthesize_node(state: PipelineState) -> dict:
    """Generate or revise a report draft."""
    from datetime import date

    request = SynthesisRequest(
        report_type=ReportType(state["report_type"]),
        period_start=date.fromisoformat(state["period_start"]),
        period_end=date.fromisoformat(state["period_end"]),
        items=state["items"],
        signals=state.get("signals", []),
        feedback=state.get("feedback", ""),
    )
    result = synthesize(request)

    return {
        "draft_title": result.title,
        "draft_content": result.content_md,
        "item_ids": result.item_ids,
    }


def critique_node(state: PipelineState) -> dict:
    """Review the current draft."""
    result = critique(
        title=state["draft_title"],
        report_type=state["report_type"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        content=state["draft_content"],
        items=state["items"],
    )

    return {
        "quality_score": result.overall_score,
        "critic_feedback": result.scores.model_dump(),
        "feedback": result.feedback,
        "approved": result.approved,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def publish_node(state: PipelineState) -> dict:
    """Finalize the report for publishing."""
    return {
        "final_title": state["draft_title"],
        "final_content": state["draft_content"],
    }


def should_retry(state: PipelineState) -> str:
    """Decide whether to revise, publish, or force-publish."""
    if state.get("approved", False):
        return "publish"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "force_publish"
    return "revise"


# ─── Build the graph ─────────────────────────────────────

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("synthesize", synthesize_node)
    graph.add_node("critique", critique_node)
    graph.add_node("publish", publish_node)

    graph.set_entry_point("synthesize")
    graph.add_edge("synthesize", "critique")

    graph.add_conditional_edges(
        "critique",
        should_retry,
        {
            "publish": "publish",
            "force_publish": "publish",
            "revise": "synthesize",
        },
    )

    graph.add_edge("publish", END)

    return graph.compile()


# Compiled graph instance
report_pipeline = build_pipeline()
