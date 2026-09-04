from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from ...services.kng_rag_service import get_kng_rag_service
from ..linter import lint_document, needs_revision, normalize_markdown_headings
from ..model_registry import ChatModelAdapter
from ..reference import (
    REFERENCE_COPY_PATCH_RULES,
    build_reference_copy_patch_context,
    lint_reference_copy_patch,
    normalize_reference_copy_patch,
    reference_copy_patch_guard_issues,
)
from ..prompts.draft import WRITING_SOURCE_RULES
from ..prompts.review import KNG_USAGE_RULES
from ..skill_registry import SkillRegistry
from ..runtime.state import WritingState
from ..web_search import search_web
from ..workflow import WorkflowCompiler


DEFAULT_WRITING_SKILL = "buaa-official-content-writer"
STYLE_SKILLS = {
    "general": DEFAULT_WRITING_SKILL,
    "notice": DEFAULT_WRITING_SKILL,
    "regulation": DEFAULT_WRITING_SKILL,
    "speech": DEFAULT_WRITING_SKILL,
}
REVIEW_SKILL = DEFAULT_WRITING_SKILL
REFERENCE_ANALYSIS_SKILL = DEFAULT_WRITING_SKILL
MAX_KNG_QUERIES = min(6, max(1, int(os.getenv("KNG_MAX_QUERIES_PER_RUN", "6"))))
MAX_WEB_QUERIES = min(4, max(1, int(os.getenv("WEB_SEARCH_MAX_QUERIES_PER_RUN", "4"))))
KNG_QUERY_CONCURRENCY = min(2, max(1, int(os.getenv("KNG_QUERY_CONCURRENCY", "2"))))
MATERIAL_ANALYSIS_CONCURRENCY = min(
    2, max(1, int(os.getenv("REFERENCE_ANALYSIS_CONCURRENCY", "2")))
)

_GENERIC_SOURCE_TERMS = {
    "关于", "通知", "规定", "办法", "工作", "要求", "管理", "制度", "流程",
    "学校", "大学", "北航", "当前", "有关", "进一步", "做好", "加强", "提供",
    "查找", "查询", "包括", "相关", "方面", "进行", "获取", "了解", "特别",
    "重点", "安全", "文件", "实施", "细则", "建设",
}
_DOCUMENT_TYPE_REFERENCES = {
    "notice": "references/doc_types/notice.md",
    "regulation": "references/doc_types/regulation.md",
}
_TASK_TYPE_REFERENCES = {
    "reply": "references/doc_types/letter.md",
}

class AgentCancelled(asyncio.CancelledError):
    pass


class OutlinePlan(BaseModel):
    title: str = Field(default="", max_length=300)
    sections: list[str] = Field(default_factory=list, max_length=12)


class WritingPlan(BaseModel):
    document_subtype: str = Field(default="", max_length=120)
    purpose: str = Field(default="", max_length=500)
    audience: str = Field(default="", max_length=500)
    confirmed_facts: list[str] = Field(default_factory=list, max_length=30)
    must_cover: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    tone: str = Field(default="", max_length=300)
    structure_strategy: str = Field(default="", max_length=1200)
    material_cards: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    reference_strategy: dict[str, Any] = Field(default_factory=dict)
    retrieval_tasks: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    outline: dict[str, Any] = Field(default_factory=dict)
    target_shape: dict[str, Any] = Field(default_factory=dict)


class MaterialCardAnalysis(BaseModel):
    topic: str = Field(default="", max_length=500)
    document_kind: str = Field(default="", max_length=120)
    intended_audience: str = Field(default="", max_length=300)
    content_excerpts: list[str] = Field(default_factory=list, max_length=16)
    structure_functions: list[str] = Field(default_factory=list, max_length=16)
    style_traits: list[str] = Field(default_factory=list, max_length=12)
    irrelevant_topics: list[str] = Field(default_factory=list, max_length=12)
    unsafe_instructions: list[str] = Field(default_factory=list, max_length=8)
    ambiguities: list[str] = Field(default_factory=list, max_length=12)


class MaterialUsePlan(BaseModel):
    file_id: int = Field(gt=0)
    roles: list[str] = Field(default_factory=list, max_length=6)
    priority: str = Field(pattern="^(primary|supporting|background|excluded)$")
    use_scope: str = Field(default="", max_length=800)
    required_points: list[str] = Field(default_factory=list, max_length=16)
    excluded_points: list[str] = Field(default_factory=list, max_length=16)


class SectionSourcePlan(BaseModel):
    section_purpose: str = Field(min_length=1, max_length=300)
    file_ids: list[int] = Field(default_factory=list, max_length=8)


class ReferenceStrategyResult(BaseModel):
    target_document_type: str = Field(pattern="^(general|notice|regulation|speech)$")
    document_subtype: str = Field(default="", max_length=120)
    material_plans: list[MaterialUsePlan] = Field(default_factory=list, max_length=20)
    structure_source_file_ids: list[int] = Field(default_factory=list, max_length=8)
    section_sources: list[SectionSourcePlan] = Field(default_factory=list, max_length=16)
    style_guidance: list[str] = Field(default_factory=list, max_length=12)
    conflicts: list[str] = Field(default_factory=list, max_length=12)
    missing_information: list[str] = Field(default_factory=list, max_length=12)


class RetrievalTask(BaseModel):
    purpose: str = Field(min_length=1, max_length=300)
    query: str = Field(min_length=1, max_length=2000)
    evidence_needs: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    backend: str = Field(default="kng", pattern="^(kng|web|both)$")


class RetrievalPlan(BaseModel):
    tasks: list[RetrievalTask] = Field(default_factory=list)


class FilteredEvidenceItem(BaseModel):
    query_index: int = Field(ge=0)
    relevance: str = Field(pattern="^(direct|partial)$")
    content: str = Field(min_length=1, max_length=12000)
    source_refs: list[str] = Field(default_factory=list)


class EvidenceFilterResult(BaseModel):
    items: list[FilteredEvidenceItem] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    code: str = Field(max_length=64)
    severity: str = Field(pattern="^(warning|error)$")
    message: str = Field(max_length=500)
    suggestion: str = Field(default="", max_length=500)


class ReviewResult(BaseModel):
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=12)


@dataclass
class AgentExecutionContext:
    model: ChatModelAdapter
    skills: SkillRegistry
    checkpointer: Any
    emit: Callable[[str, dict[str, Any], str | None], Awaitable[None]]
    persist_state: Callable[[WritingState, str], Awaitable[None]]
    update_draft: Callable[[str], Awaitable[None]]
    is_cancelled: Callable[[], bool]

    def check_cancelled(self):
        if self.is_cancelled():
            raise AgentCancelled()


def _strip_fence(text: str) -> str:
    stripped = (text or "").strip()
    match = re.fullmatch(r"```(?:markdown|md)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def _evidence_text(state: WritingState) -> str:
    evidence = state.get("evidence") or []
    if not evidence:
        return "没有可用知识库材料。只可使用用户明确提供的信息。"
    rendered = []
    for item in evidence:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        sources = item.get("sources") or []
        source_text = "；".join(str(source) for source in sources if source)
        if item.get("kind") == "uploaded_reference":
            roles = "＋".join(item.get("roles") or ["内容"])
            rendered.append(f"【上传材料摘录｜{source_text or '未命名'}｜用途：{roles}】\n{content}")
        elif source_text:
            rendered.append(f"【已筛选知识库证据｜来源：{source_text}】\n{content}")
        else:
            rendered.append(content)
    return "\n\n".join(rendered)


def _reference_strategy_text(state: WritingState) -> str:
    strategy = state.get("reference_strategy") or {}
    if not strategy:
        return "无上传材料使用方案。"
    return json.dumps(strategy, ensure_ascii=False)


def _draft_plan_text(state: WritingState) -> str:
    """Expose only role-allowed material facts to drafting and review prompts."""
    plan = dict(state.get("writing_plan") or {})
    strategy = state.get("reference_strategy") or {}
    role_map = {
        int(item.get("file_id")): set(_normalize_material_roles(item.get("roles") or []))
        for item in strategy.get("material_plans") or []
        if item.get("file_id")
    }
    safe_cards = []
    for card in plan.get("material_cards") or []:
        item = dict(card)
        file_id = int(item.get("file_id") or 0)
        if "content" not in role_map.get(file_id, set()):
            item["content_excerpts"] = []
        item.pop("unsafe_instructions", None)
        safe_cards.append(item)
    if "material_cards" in plan:
        plan["material_cards"] = safe_cards
    return json.dumps(plan, ensure_ascii=False)


def _is_exact_excerpt(excerpt: str, source: str) -> bool:
    candidate = _normalize_text(excerpt)
    return bool(candidate) and candidate in _normalize_text(source)


def _normalize_material_roles(roles: list[str]) -> list[str]:
    allowed = {"content", "structure", "style", "background", "negative_example", "irrelevant"}
    normalized = []
    for role in roles:
        role = _normalize_text(role).lower()
        if role in allowed and role not in normalized:
            normalized.append(role)
    return normalized


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_tasks(plan: RetrievalPlan) -> list[dict[str, Any]]:
    tasks = []
    seen = set()
    for task in plan.tasks:
        query = _normalize_text(task.query)
        if not query or query.casefold() in seen:
            continue
        seen.add(query.casefold())
        tasks.append({
            "purpose": _normalize_text(task.purpose),
            "query": query,
            "evidence_needs": [_normalize_text(item) for item in task.evidence_needs if _normalize_text(item)],
            "exclusions": [_normalize_text(item) for item in task.exclusions if _normalize_text(item)],
            "backend": task.backend,
        })
    return tasks


def _normalize_task_dicts(items: Any) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items or []:
        if not isinstance(raw, dict):
            continue
        query = _normalize_text(raw.get("query"))
        if not query or query.casefold() in seen:
            continue
        backend = str(raw.get("backend") or "kng").strip().lower()
        if backend not in {"kng", "web", "both"}:
            backend = "kng"
        seen.add(query.casefold())
        tasks.append({
            "purpose": _normalize_text(raw.get("purpose")),
            "query": query,
            "evidence_needs": [_normalize_text(item) for item in raw.get("evidence_needs") or [] if _normalize_text(item)],
            "exclusions": [_normalize_text(item) for item in raw.get("exclusions") or [] if _normalize_text(item)],
            "backend": backend,
        })
    return tasks


def _merge_task_budget(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge similar retrieval intents to the per-backend safety budgets."""
    groups: dict[str, list[dict[str, Any]]] = {"kng": [], "web": [], "both": []}
    for task in tasks:
        groups.setdefault(task.get("backend", "kng"), []).append(task)
    merged: list[dict[str, Any]] = []
    for backend, items in groups.items():
        limit = MAX_KNG_QUERIES if backend in {"kng", "both"} else MAX_WEB_QUERIES
        while len(items) > limit:
            left = items.pop()
            right = items.pop()
            items.append({
                "purpose": "；".join(item["purpose"] for item in (right, left) if item.get("purpose")),
                "query": "；".join(item["query"] for item in (right, left)),
                "evidence_needs": list(dict.fromkeys(right.get("evidence_needs", []) + left.get("evidence_needs", []))),
                "exclusions": list(dict.fromkeys(right.get("exclusions", []) + left.get("exclusions", []))),
                "backend": backend,
            })
        merged.extend(items)
    return merged


def _fallback_material_plan(state: WritingState) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create a conservative reference plan when the single planning call fails."""
    cards: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    requirements = str(state.get("requirements") or "")
    for index, material in enumerate(state.get("source_materials") or [], 1):
        file_id = int(material.get("file_id") or index)
        filename = str(material.get("filename") or "未命名")
        lower = filename.lower()
        roles = ["content"]
        if any(term in requirements for term in (filename, f"第{index}份", f"第 {index} 份")):
            if "骨架" in requirements or "结构" in requirements:
                roles = ["structure", "content"]
        elif "风格" in lower or "语气" in requirements:
            roles = ["style"]
        elif "骨架" in lower or "结构" in lower:
            roles = ["structure"]
        cards.append({
            "file_id": file_id,
            "filename": filename,
            "upload_index": index,
            "topic": "",
            "document_kind": "",
            "intended_audience": "",
            "content_excerpts": [str(material.get("content") or "")[:4000]],
            "structure_functions": [],
            "style_traits": [],
            "irrelevant_topics": [],
            "unsafe_instructions": [],
            "ambiguities": ["材料角色规划不可用，已按文件名和用户要求保守处理"],
        })
        plans.append({
            "file_id": file_id,
            "roles": roles,
            "priority": "primary" if index == 1 else "supporting",
            "use_scope": "仅使用与当前要求直接相关的内容",
            "required_points": [],
            "excluded_points": [],
        })
    strategy = {
        "target_document_type": state.get("document_type", "general"),
        "document_subtype": "",
        "material_plans": plans,
        "structure_source_file_ids": [p["file_id"] for p in plans if "structure" in p["roles"]],
        "section_sources": [],
        "style_guidance": [],
        "conflicts": [],
        "missing_information": [],
    }
    return cards, strategy


def _reference_id(value: str) -> str | None:
    match = re.match(r"^\s*\[(\d+)\]", value or "")
    return match.group(1) if match else None


def _resolve_reference(candidate: str, available: list[str]) -> str | None:
    normalized = _normalize_text(candidate)
    if not normalized:
        return None
    for reference in available:
        if _normalize_text(reference).casefold() == normalized.casefold():
            return reference
    candidate_id = _reference_id(normalized)
    if candidate_id:
        for reference in available:
            if _reference_id(reference) == candidate_id:
                return reference
    normalized_without_id = re.sub(r"^\s*\[\d+\]\s*", "", normalized).casefold()
    for reference in available:
        reference_without_id = re.sub(r"^\s*\[\d+\]\s*", "", _normalize_text(reference)).casefold()
        if normalized_without_id and normalized_without_id == reference_without_id:
            return reference
    return None


def _specific_topic_terms(value: Any) -> set[str]:
    """Extract lexical signals used only to reject obviously unrelated source titles."""
    normalized = _normalize_text(value).casefold()
    terms = set(re.findall(r"[a-z0-9]{3,}", normalized))
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", normalized):
        for size in (2, 3, 4):
            terms.update(segment[index:index + size] for index in range(len(segment) - size + 1))
    return {term for term in terms if term not in _GENERIC_SOURCE_TERMS}


def _reference_matches_task(reference: str, task: dict[str, Any]) -> bool:
    """A title may reject an obvious mismatch, but can never prove an evidence claim."""
    task_text = " ".join([
        str(task.get("purpose") or ""),
        str(task.get("query") or ""),
        *(str(item) for item in task.get("evidence_needs") or []),
    ])
    task_terms = _specific_topic_terms(task_text)
    reference_terms = _specific_topic_terms(reference)
    if not task_terms or not reference_terms:
        return True
    return bool(task_terms & reference_terms)


def _apply_selection(base_article: str, selection: dict[str, Any], replacement: str) -> str:
    selected = str(selection.get("selected_markdown") or "")
    if not selected:
        raise ValueError("Selection edit requires selected_markdown")
    if base_article.count(selected) != 1:
        raise ValueError("Selected text is no longer unique in the base article")
    return base_article.replace(selected, replacement, 1)


def _allows_substantial_shortening(requirements: str) -> bool:
    return bool(re.search(r"压缩|精简|缩短|删减|不超过\s*\d+|控制在\s*\d+", requirements or ""))


def _skill_text(state: WritingState, phase: str) -> str:
    parts = [state.get("skill_instructions", "")]
    guidance = (state.get("skill_guidance") or {}).get(phase, "")
    if guidance:
        parts.append(guidance)
    return "\n\n".join(part for part in parts if part)


def _skill_runtime_contract(skill) -> str:
    lines = [
        f"Skill：{skill.name}",
        f"用途：{skill.description}",
    ]
    if skill.compatibility:
        lines.append(f"适配范围：{skill.compatibility}")
    return "\n".join(lines)


def _phase_references(context: AgentExecutionContext, skill, phase: str, state: WritingState | None = None) -> str:
    app_metadata = skill.metadata.get("writing-assistant")
    if not isinstance(app_metadata, dict):
        app_metadata = skill.metadata
    workflow = app_metadata.get("workflow") or {}
    routes = workflow.get("references") or {}
    configured = routes.get(phase) or []
    selected = [configured] if isinstance(configured, str) else list(configured)
    if state and phase in {"planning", "outline", "draft", "validation", "revision"}:
        task_reference = _TASK_TYPE_REFERENCES.get(str(state.get("task_type") or ""))
        document_reference = _DOCUMENT_TYPE_REFERENCES.get(str(state.get("document_type") or ""))
        for reference in (task_reference, document_reference):
            if reference and reference in skill.resources and reference not in selected:
                selected.append(reference)
    references = context.skills.read_text_resources(skill, relative_paths=selected)
    return "\n\n".join(f"## {name}\n{content}" for name, content in references)


async def _stage(
    context: AgentExecutionContext,
    stage: str,
    state: WritingState,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    context.check_cancelled()
    started = time.perf_counter()
    await context.emit("stage.started", {"label": stage}, stage)
    updates = await operation()
    merged: WritingState = {**state, **updates}
    await context.persist_state(merged, stage)
    await context.emit(
        "stage.completed",
        {"label": stage, "duration_ms": round((time.perf_counter() - started) * 1000)},
        stage,
    )
    return updates


__all__ = [name for name in globals() if not name.startswith("__")]
