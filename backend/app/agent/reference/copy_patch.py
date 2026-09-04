from __future__ import annotations

import json
from typing import Any

from .base_selector import material_content_by_id, select_reference_base_material
from .change_plan import apply_global_replacements, build_reference_change_plan, normalize_text


REFERENCE_COPY_PATCH_RULES = """【底稿微调规则】
主底稿全文是本次正文基础。先保留整篇结构，再只按用户明确提到的修改点动手。未被点名的章节、段落、附件、版记默认保留原文。禁止把主底稿改写成摘要、提纲或多材料拼接稿。"""

_MATERIAL_ROLES = {"content", "structure", "style", "background", "negative_example", "irrelevant"}


def build_reference_copy_patch_context(state: dict[str, Any]) -> str:
    if state.get("task_type") != "imitate":
        return ""
    base_text = str(state.get("reference_base_text") or "")
    working_copy = str(state.get("reference_working_copy") or "")
    if not base_text and not working_copy:
        return ""
    change_plan = state.get("reference_change_plan") or {}
    change_plan_text = (
        json.dumps(change_plan, ensure_ascii=False)
        if change_plan
        else "无单独修改清单，默认仅保留主底稿并做最小必要替换。"
    )
    patch_log = json.dumps(state.get("reference_patch_log") or [], ensure_ascii=False)
    return (
        "【底稿微调上下文】\n"
        "请把主底稿当作正文基础，只对修改清单中明确提到的地方动手；"
        "未提到的章节、段落、附件和版记默认保留原文，不要压缩成摘要，不要重新起草一篇新文。\n\n"
        f"主底稿文件ID：{state.get('reference_base_file_id')}\n"
        f"主底稿全文：\n{base_text}\n\n"
        f"工作稿：\n{working_copy or base_text}\n\n"
        f"修改清单：\n{change_plan_text}\n\n"
        f"已执行补丁：\n{patch_log}\n"
    )


def normalize_reference_copy_patch(
    state: dict[str, Any],
    writing_plan: dict[str, Any],
    material_cards: list[dict[str, Any]],
    strategy: dict[str, Any],
) -> dict[str, Any]:
    if state.get("task_type") != "imitate":
        return _empty_update(material_cards, strategy)

    materials = list(state.get("source_materials") or [])
    base_material = select_reference_base_material(str(state.get("requirements") or ""), materials)
    if not base_material:
        return _empty_update(material_cards, strategy)

    base_file_id = int(base_material.get("file_id") or 0)
    base_text = material_content_by_id(materials).get(base_file_id, "")
    change_plan = build_reference_change_plan(state, base_material, base_text)
    working_copy, patch_log = apply_global_replacements(base_text, change_plan)

    cards_by_id = _cards_by_id(material_cards)
    for material in materials:
        file_id = int(material.get("file_id") or 0)
        if not file_id:
            continue
        card = cards_by_id.setdefault(file_id, _default_material_card(material))
        card.setdefault("filename", material.get("filename", "未命名"))
        if file_id == base_file_id:
            card["content_excerpts"] = [working_copy or base_text] if (working_copy or base_text) else []
            card.setdefault("structure_functions", [])
            card.setdefault("style_traits", [])

    plans_by_id = _plans_by_id(strategy)
    source_bindings: list[dict[str, Any]] = []
    supporting_ids: list[int] = []
    for material in materials:
        file_id = int(material.get("file_id") or 0)
        if not file_id:
            continue

        plan = plans_by_id.setdefault(file_id, _default_material_plan(file_id))
        is_base = file_id == base_file_id
        if is_base:
            roles = [role for role in _normalize_material_roles(plan.get("roles") or []) if role != "irrelevant"]
            roles = list(dict.fromkeys([*roles, "content", "structure", "style"]))
            plan.update({
                "roles": roles,
                "priority": "primary",
                "use_scope": "作为底稿微调的主底稿全文使用；未明确变更处默认保留原文",
            })
            binding_role = "base_template"
        else:
            roles = _normalize_material_roles(plan.get("roles") or []) or ["structure", "style"]
            plan.update({
                "roles": roles,
                "priority": plan.get("priority")
                if plan.get("priority") in {"primary", "supporting", "background"}
                else "supporting",
                "use_scope": plan.get("use_scope") or "仅辅助判断结构、风格或差异，不直接覆盖主底稿事实",
            })
            binding_role = "style_reference" if any(role in roles for role in ("structure", "style")) else "background"
            supporting_ids.append(file_id)

        source_bindings.append({
            "file_id": file_id,
            "role": binding_role,
            "priority": plan["priority"],
            "pass_full_text": is_base,
            "allowed_fact_scope": ["主底稿全文"] if is_base else ["结构", "风格"],
        })

    normalized_strategy = dict(strategy or {})
    normalized_strategy["target_document_type"] = (
        normalized_strategy.get("target_document_type") or state.get("document_type", "general")
    )
    normalized_strategy["material_plans"] = list(plans_by_id.values())
    normalized_strategy["reference_base_file_id"] = base_file_id
    writing_plan["material_cards"] = list(cards_by_id.values())
    writing_plan["reference_strategy"] = normalized_strategy
    return {
        "reference_base_file_id": base_file_id,
        "reference_base_text": base_text,
        "reference_change_plan": change_plan,
        "reference_working_copy": working_copy or base_text,
        "reference_patch_log": patch_log,
        "reference_supporting_file_ids": supporting_ids,
        "source_bindings": source_bindings,
        "material_cards": list(cards_by_id.values()),
        "reference_strategy": normalized_strategy,
    }


def _empty_update(
    material_cards: list[dict[str, Any]],
    strategy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "material_cards": material_cards,
        "reference_strategy": strategy,
        "reference_change_plan": {},
        "reference_working_copy": "",
        "reference_patch_log": [],
    }


def _normalize_material_roles(roles: list[str]) -> list[str]:
    normalized: list[str] = []
    for role in roles:
        role = normalize_text(role).lower()
        if role in _MATERIAL_ROLES and role not in normalized:
            normalized.append(role)
    return normalized


def _cards_by_id(material_cards: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(card.get("file_id") or 0): dict(card)
        for card in material_cards or []
        if card.get("file_id")
    }


def _plans_by_id(strategy: dict[str, Any]) -> dict[int, dict[str, Any]]:
    raw_plans = strategy.get("material_plans") if isinstance(strategy, dict) else []
    return {
        int(plan.get("file_id") or 0): dict(plan)
        for plan in raw_plans or []
        if isinstance(plan, dict) and plan.get("file_id")
    }


def _default_material_card(material: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_id": int(material.get("file_id") or 0),
        "filename": material.get("filename", "未命名"),
        "content_excerpts": [],
        "structure_functions": [],
        "style_traits": [],
    }


def _default_material_plan(file_id: int) -> dict[str, Any]:
    return {
        "file_id": file_id,
        "roles": [],
        "priority": "supporting",
        "use_scope": "",
        "required_points": [],
        "excluded_points": [],
    }
