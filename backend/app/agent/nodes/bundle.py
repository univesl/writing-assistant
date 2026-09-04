from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .common import AgentExecutionContext, WritingState, needs_revision
from .draft import create_draft_node, create_outline_node
from .finalize import create_finalize_node
from .planning import create_plan_writing_node
from .prepare import create_load_skill_node, create_prepare_node
from .reference import create_material_analysis_node, create_reference_strategy_node
from .retrieval import create_filter_evidence_node, create_plan_retrieval_node, create_retrieve_node
from .review import create_material_review_node, create_validate_node
from .revision import create_revise_node


@dataclass(frozen=True)
class WritingNodeBundle:
    nodes: dict[str, Callable[[WritingState], Awaitable[dict[str, Any]]]]
    routes: dict[str, Callable[[WritingState], str]]

def after_prepare(state: WritingState):
    return "skill"

def after_skill(state: WritingState):
    task_type = state.get("task_type", "draft")
    if task_type == "review":
        return "review"
    if task_type == "format":
        return "format"
    if task_type in {"revise_document", "revise_selection"}:
        return "draft"
    return "planning"

def after_planning(state: WritingState):
    if state.get("retrieval_plan") and (state.get("use_kng") or state.get("use_web_search")):
        return "retrieve"
    return "draft"

def after_filter_evidence(state: WritingState):
    return "draft"

def after_validate(state: WritingState):
    if state.get("task_type") == "review":
        return "finalize"
    revision_limit = min(1, int(state.get("workflow_policy", {}).get("max_revisions", 1)))
    if needs_revision(state.get("issues") or []) and int(state.get("revision_count") or 0) < revision_limit:
        return "revise"
    return "finalize"

def after_draft(state: WritingState):
    return "validate"

def after_revision(state: WritingState):
    return "validate"


def create_writing_node_bundle(context: AgentExecutionContext) -> WritingNodeBundle:
    return WritingNodeBundle(
        nodes={
            "prepare": create_prepare_node(context),
            "material_analysis": create_material_analysis_node(context),
            "reference_strategy": create_reference_strategy_node(context),
            "load_skill": create_load_skill_node(context),
            "plan_writing": create_plan_writing_node(context),
            "plan_retrieval": create_plan_retrieval_node(context),
            "retrieve": create_retrieve_node(context),
            "filter_evidence": create_filter_evidence_node(context),
            "outline": create_outline_node(context),
            "draft": create_draft_node(context),
            "material_review": create_material_review_node(context),
            "validate": create_validate_node(context),
            "revise": create_revise_node(context),
            "finalize": create_finalize_node(context),
        },
        routes={
            "after_prepare": after_prepare,
            "after_skill": after_skill,
            "after_planning": after_planning,
            "after_filter_evidence": after_filter_evidence,
            "after_draft": after_draft,
            "after_validate": after_validate,
            "after_revision": after_revision,
        },
    )


__all__ = ["WritingNodeBundle", "create_writing_node_bundle"]
