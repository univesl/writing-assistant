from __future__ import annotations

from .common import *

def create_revise_node(context: AgentExecutionContext):
    async def revise(state: WritingState):
        async def operation():
            task_type = state.get("task_type")
            if task_type == "revise_selection":
                selected = str((state.get("selection") or {}).get("selected_markdown") or "")
                prompt = (
                    "只修订指定选区的 replacement。上下文只读，不得输出完整文章，不得改动选区外内容。"
                    "保留没有问题的选区内容，不得新增无依据事实。只输出新的 replacement Markdown。\n\n"
                    f"用户要求：{state.get('requirements', '')}\n"
                    f"问题：{json.dumps(state.get('issues') or [], ensure_ascii=False)}\n"
                    f"原选区：{selected}\n"
                    f"当前 replacement：{state.get('selection_replacement', '')}\n"
                    f"只读上下文：{json.dumps(state.get('selection') or {}, ensure_ascii=False)}\n"
                    f"Skill：{_skill_text(state, 'revision')}"
                )
                revised_replacement = _strip_fence(
                    await context.model.complete_text([{"role": "user", "content": prompt}])
                )
                if not revised_replacement:
                    raise ValueError("Model returned an empty selection revision")
                article = _apply_selection(
                    state.get("base_article", ""), state.get("selection") or {}, revised_replacement
                )
                await context.update_draft(article)
                return {
                    "draft": article,
                    "selection_replacement": revised_replacement,
                    "revision_count": int(state.get("revision_count") or 0) + 1,
                }
            reference_context = build_reference_copy_patch_context(state)
            source_rules = REFERENCE_COPY_PATCH_RULES if task_type == "imitate" else WRITING_SOURCE_RULES
            prompt = (
                "根据问题清单定向修订公文。保留正确内容，不得新增无依据事实。"
                "必须保留用户明确列出的全部事项，并输出有完整结尾的全文；"
                "除非问题清单明确要求删除，否则不得因修订而省略原有章节。只输出完整 Markdown 正文。\n\n"
                f"用户要求：{state.get('requirements', '')}\n\n"
                f"写作规划：{json.dumps(state.get('writing_plan') or {}, ensure_ascii=False)}\n\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n\n"
                f"{reference_context}"
                f"Skill：{_skill_text(state, 'revision')}\n\n"
                f"{source_rules}\n{KNG_USAGE_RULES}\n\n已筛选证据：{_evidence_text(state)}\n\n"
                f"问题：{json.dumps(state.get('issues') or [], ensure_ascii=False)}\n\n"
                f"原文：\n{state.get('draft', '')}"
            )
            revised = _strip_fence(await context.model.complete_text([{"role": "user", "content": prompt}]))
            if not revised:
                raise ValueError("Model returned an empty revision")
            revised, heading_warnings = normalize_markdown_headings(revised)
            original = state.get("draft", "")
            warnings = list(state.get("warnings") or [])
            if heading_warnings:
                warnings.append({
                    "code": "heading_normalized",
                    "message": "已将修订稿中的明显一级标题规范为正文层级",
                    "details": heading_warnings,
                })
            revision_count = int(state.get("revision_count") or 0) + 1
            if state.get("task_type") == "imitate" and state.get("reference_base_text"):
                base_text = str(state.get("reference_base_text") or "")
                original_guard = reference_copy_patch_guard_issues(
                    base_text, original, state.get("requirements", "")
                )
                revised_guard = reference_copy_patch_guard_issues(
                    base_text, revised, state.get("requirements", "")
                )
                original_errors = sum(1 for item in original_guard if item.get("severity") == "error")
                revised_errors = sum(1 for item in revised_guard if item.get("severity") == "error")
                if revised_errors > original_errors:
                    warning = {
                        "code": "revision_rejected_reference_base_regression",
                        "message": "修订稿相对主底稿的完整性更差，已保留上一版正文",
                    }
                    if not any(item.get("code") == warning["code"] for item in warnings):
                        warnings.append(warning)
                        await context.emit("warning", warning, "revision")
                    return {
                        "draft": original,
                        "warnings": warnings,
                        "revision_count": revision_count,
                    }
            if (
                original
                and len(revised) < len(original) * 0.7
                and not _allows_substantial_shortening(state.get("requirements", ""))
            ):
                warning = {
                    "code": "revision_rejected_incomplete",
                    "message": "修订稿内容异常缩短，已保留上一版完整正文",
                }
                if not any(item.get("code") == warning["code"] for item in warnings):
                    warnings.append(warning)
                    await context.emit("warning", warning, "revision")
                return {
                    "draft": original,
                    "warnings": warnings,
                    "revision_count": revision_count,
                }
            await context.update_draft(revised)
            if task_type not in {"revise_document", "revise_selection"}:
                await context.emit(
                    "content.delta", {"mode": "replace", "content": revised}, "revision"
                )
            return {"draft": revised, "warnings": warnings, "revision_count": revision_count}

        return await _stage(context, "revision", state, operation)
    return revise

__all__ = ['create_revise_node']
