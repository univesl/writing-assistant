from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    AgentCancelled,
    AgentExecutionContext,
    MaterialCardAnalysis,
    OutlinePlan,
    ReferenceStrategyResult,
    ReviewResult,
    WritingPlan,
    create_writing_node_bundle,
)
from .runtime.state import WritingState


def build_writing_graph(context: AgentExecutionContext):
    bundle = create_writing_node_bundle(context)
    nodes = bundle.nodes
    routes = bundle.routes

    builder = StateGraph(WritingState)
    for name, node in nodes.items():
        builder.add_node(name, node)

    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", routes["after_prepare"], {"skill": "load_skill"})
    builder.add_conditional_edges(
        "load_skill",
        routes["after_skill"],
        {
            "planning": "plan_writing",
            "draft": "draft",
            "review": "validate",
            "format": "finalize",
        },
    )
    builder.add_conditional_edges(
        "plan_writing",
        routes["after_planning"],
        {"retrieve": "retrieve", "draft": "draft"},
    )
    builder.add_edge("retrieve", "filter_evidence")
    builder.add_conditional_edges(
        "filter_evidence",
        routes["after_filter_evidence"],
        {"draft": "draft"},
    )
    builder.add_conditional_edges("draft", routes["after_draft"], {"validate": "validate"})
    builder.add_conditional_edges(
        "validate",
        routes["after_validate"],
        {"revise": "revise", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "revise",
        routes["after_revision"],
        {"material_review": "material_review", "validate": "validate"},
    )
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=context.checkpointer)


__all__ = [
    "AgentCancelled",
    "AgentExecutionContext",
    "MaterialCardAnalysis",
    "OutlinePlan",
    "ReferenceStrategyResult",
    "ReviewResult",
    "WritingPlan",
    "build_writing_graph",
]
