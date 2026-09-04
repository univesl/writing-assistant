from __future__ import annotations

import re
from typing import Any

from .base_selector import date_label, edition_label, target_edition_label


_SECTION_HEADING_RE = re.compile(
    r"(?m)^\s*(?:#{1,6}\s*)?(?P<num>[一二三四五六七八九十百]+)、(?P<title>[^\n#]+?)\s*$"
)
STABLE_REFERENCE_SECTIONS = ("指导思想", "评审工作", "交流活动", "工作要求")


def build_reference_change_plan(
    state: dict[str, Any],
    base_material: dict[str, Any] | None,
    base_text: str,
) -> dict[str, Any]:
    requirements = str(state.get("requirements") or "")
    requirement_text = normalize_text(requirements)
    base_filename = str((base_material or {}).get("filename") or "")
    base_edition = edition_label(base_filename) or edition_label(base_text)
    requirement_edition = target_edition_label(requirement_text)
    base_date = date_label(base_text)
    requirement_date = date_label(requirement_text)

    section_matches = [
        {
            "section": heading,
            "instruction": "按用户要求修改该章节，未提到部分保留原文",
        }
        for heading in extract_section_map(base_text).keys()
        if heading and heading in requirement_text
    ]
    if not section_matches:
        section_matches.append({
            "section": "全文",
            "instruction": "只修改用户明确提到的内容，其余章节、段落和附件默认保留原文",
        })

    global_replace: list[dict[str, Any]] = []
    if base_edition and requirement_edition and base_edition != requirement_edition:
        global_replace.append({
            "from": f"第{base_edition}届",
            "to": f"第{requirement_edition}届",
            "reason": "届次更新",
        })
    if base_date and requirement_date and base_date != requirement_date:
        global_replace.append({
            "from": base_date,
            "to": requirement_date,
            "reason": "显式日期更新",
        })

    keep_rules = [
        "未提到的章节、段落、附件、版记默认保留原文",
        "只修改用户明确点名的部分，不要整篇重写",
        "结构顺序尽量沿用主底稿",
    ]
    if base_edition and requirement_edition and base_edition != requirement_edition:
        keep_rules.append("只替换届次等稳定变量，不要顺手改写正文")

    attachment_patch = ["附件清单默认沿用主底稿；只有用户明确要求时再增删改附件"]
    if "附件" in base_text:
        attachment_patch.append("附件正文按主底稿格式保留，必要时只做局部替换")

    forbidden_changes = [
        "不要把底稿概括成摘要",
        "不要把未提到的章节改写成新稿内容",
        "不要丢失主底稿章节顺序和附件结构",
        f"稳定章节默认保留：{'、'.join(STABLE_REFERENCE_SECTIONS)}",
    ]
    return {
        "base_file_id": int((base_material or {}).get("file_id") or 0) or None,
        "base_filename": base_filename,
        "base_edition": base_edition,
        "target_edition": requirement_edition,
        "base_date": base_date,
        "target_date": requirement_date,
        "global_replace": global_replace,
        "section_patch": section_matches,
        "attachment_patch": attachment_patch,
        "keep_rules": keep_rules,
        "forbidden_changes": forbidden_changes,
        "summary": (
            f"以{base_filename or '主底稿'}为底稿复制后局部修改"
            if base_filename
            else "以主底稿复制后局部修改"
        ),
    }


def apply_global_replacements(
    text: str,
    change_plan: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    patched = str(text or "")
    log: list[dict[str, Any]] = []
    for item in change_plan.get("global_replace") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("from") or "")
        target = str(item.get("to") or "")
        if not source or source == target or source not in patched:
            continue
        patched = patched.replace(source, target)
        log.append({
            "kind": "global_replace",
            "from": source,
            "to": target,
            "reason": str(item.get("reason") or ""),
        })
    return patched, log


def extract_section_map(text: str) -> dict[str, str]:
    matches = list(_SECTION_HEADING_RE.finditer(text or ""))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
