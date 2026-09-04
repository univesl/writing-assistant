from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .change_plan import STABLE_REFERENCE_SECTIONS, extract_section_map


_LAZY_REFERENCE_RE = re.compile(
    r"(继续按照|参照|按)(?:第[一二三四五六七八九十百0-9]+届|上届|原)(?:[^。；\n]{0,20})(?:通知|执行|办理|要求)"
)
_PLACEHOLDER_RE = re.compile(r"待补充|待定|待明确|〔待补充〕|\[待补充")
_REQUIRED_REFERENCE_SECTIONS = (
    "指导思想",
    "组织机构",
    "时间安排",
    "申报工作",
    "评审工作",
    "交流活动",
    "工作要求",
)


def lint_reference_copy_patch(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("task_type") != "imitate":
        return []
    base_text = str(state.get("reference_base_text") or "")
    draft_text = str(state.get("draft") or "")
    requirements = str(state.get("requirements") or "")
    if not base_text or not draft_text:
        return []

    issues: list[dict[str, Any]] = []
    missing = [heading for heading in _REQUIRED_REFERENCE_SECTIONS if heading not in draft_text]
    if missing:
        issues.append(_issue(
            "reference_base_sections_missing",
            f"底稿修订式参考写作缺少主底稿中的章节：{'、'.join(missing)}",
            "error",
            "补回主底稿章节，未明确变更处保留原文",
        ))
    if "关于举办" in draft_text and "关于启动" in base_text:
        issues.append(_issue(
            "reference_base_title_changed",
            "标题用语由主底稿的“关于启动”误改为“关于举办”",
            "error",
            "恢复主底稿标题用语，仅替换届次等变量",
        ))
    if _LAZY_REFERENCE_RE.search(draft_text):
        issues.append(_issue(
            "reference_base_lazy_inheritance",
            "正文用“继续按照/参照/按上届执行”等概括句替代了主底稿具体内容",
            "error",
            "展开并保留主底稿对应章节的具体表述",
        ))
    if _PLACEHOLDER_RE.search(draft_text):
        issues.append(_issue(
            "reference_base_placeholder",
            "底稿修订式参考写作中出现待补充或待定占位",
            "error",
            "能从主底稿或用户变更清单确定的字段不得改成占位",
        ))
    if len(draft_text) < len(base_text) * 0.85 and not _allows_substantial_shortening(requirements):
        issues.append(_issue(
            "reference_base_length_short",
            "输出明显短于主底稿，可能发生了摘要化或漏段",
            "error",
            "以主底稿全文为基础补回未变更段落",
        ))

    base_attachments = _attachment_count(base_text)
    draft_attachments = _attachment_count(draft_text)
    if (
        base_attachments
        and draft_attachments < base_attachments
        and not re.search(r"删除|删去|减少|精简附件", requirements)
    ):
        issues.append(_issue(
            "reference_base_attachments_missing",
            f"附件数量少于主底稿（主底稿 {base_attachments} 项，当前 {draft_attachments} 项）",
            "error",
            "在主底稿附件清单基础上替换或追加，不要只列新增附件",
        ))

    base_sections = extract_section_map(base_text)
    draft_sections = extract_section_map(draft_text)
    for heading in STABLE_REFERENCE_SECTIONS:
        if heading not in base_sections or heading not in draft_sections:
            continue
        if _section_similarity(base_sections[heading], draft_sections[heading]) < 0.65:
            issues.append(_issue(
                f"reference_base_{heading}_rewritten",
                f"“{heading}”章节与主底稿差异过大，疑似被概括重写",
                "error",
                "未明确要求修改的稳定章节应保留主底稿原文，只做必要变量替换",
            ))
    return issues


def reference_copy_patch_guard_issues(
    base_text: str,
    candidate: str,
    requirements: str,
) -> list[dict[str, Any]]:
    return lint_reference_copy_patch({
        "task_type": "imitate",
        "reference_base_text": base_text,
        "draft": candidate,
        "requirements": requirements,
    })


def _attachment_count(text: str) -> int:
    attachment_index = (text or "").find("附件")
    scope = text[attachment_index:] if attachment_index >= 0 else text or ""
    return len(re.findall(r"(?m)^\s*\d+[.、]\s*", scope))


def _section_similarity(left: str, right: str) -> float:
    return SequenceMatcher(
        None,
        _normalize_for_similarity(left),
        _normalize_for_similarity(right),
    ).ratio()


def _normalize_for_similarity(text: str) -> str:
    normalized = re.sub(r"\s+", "", text or "")
    normalized = re.sub(r"第[一二三四五六七八九十百两0-9]+届", "第X届", normalized)
    normalized = re.sub(r"20\d{2}年\d{1,2}月\d{1,2}日?", "X年X月X日", normalized)
    return normalized


def _allows_substantial_shortening(requirements: str) -> bool:
    return bool(re.search(r"压缩|精简|缩短|删减|不超过\s*\d+|控制在\s*\d+", requirements or ""))


def _issue(code: str, message: str, severity: str = "warning", suggestion: str = "") -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
        "source": "reference_base_linter",
    }
