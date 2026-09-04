from __future__ import annotations

from .common import *

def create_material_review_node(context: AgentExecutionContext):
    async def review_material_use(state: WritingState):
        async def operation():
            if not state.get("source_materials"):
                return {"material_issues": []}
            prompt = (
                "审查新稿是否正确执行上传材料使用方案。只报告明确且可操作的问题，不输出思维过程。"
                "重点检查：用户指定重点材料是否实际使用；content 重要事项是否遗漏或歪曲；"
                "structure/style 材料中的人名、单位、日期、数字和旧任务事实是否误入正文；"
                "background/irrelevant 是否写入正文；是否出现材料摘要拼接、明显大段照抄或语气突变；"
                "正文新增具体事实是否能追溯到用户要求、content 摘录或已筛选 KnG 证据。\n\n"
                f"用户要求：{state.get('requirements', '')}\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n"
                f"允许的事实摘录：{_evidence_text(state)}\n\n"
                f"正文：\n{state.get('draft', '')}"
            )
            try:
                review = await context.model.complete_structured(
                    [{"role": "user", "content": prompt}], ReviewResult
                )
                issues = [
                    {**issue.model_dump(), "source": "material_review"}
                    for issue in review.issues
                ]
                return {"material_issues": issues}
            except Exception:
                warning = {
                    "code": "material_review_unavailable",
                    "message": "材料使用审查不可用，请复核各参考文件的实际使用情况",
                }
                warnings = list(state.get("warnings") or [])
                warnings.append(warning)
                await context.emit("warning", warning, "material_review")
                return {"material_issues": [], "warnings": warnings}

        return await _stage(context, "material_review", state, operation)
    return review_material_use

def create_validate_node(context: AgentExecutionContext):
    async def validate(state: WritingState):
        async def operation():
            selection_task = state.get("task_type") == "revise_selection"
            deterministic = [] if selection_task else lint_document(
                state["document_type"], state.get("requirements", ""), state.get("draft", "")
            )
            if not selection_task:
                deterministic.extend(lint_reference_copy_patch(state))
            review_target = (
                state.get("selection_replacement", "") if selection_task else state.get("draft", "")
            )
            reference_context = build_reference_copy_patch_context(state)
            source_rules = REFERENCE_COPY_PATCH_RULES if state.get("task_type") == "imitate" else WRITING_SOURCE_RULES
            review_prompt = (
                "审查下面公文是否违反用户要求、Skill 或证据边界。只报告明确且可操作的问题；"
                "不得输出隐藏推理。\n\n"
                f"用户要求：{state.get('requirements', '')}\n"
                f"写作规划：{_draft_plan_text(state)}\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n"
                f"{reference_context}"
                "参考写作还必须检查：用户指定重点材料是否实际使用；content材料的重要事项是否遗漏或歪曲；"
                "structure/style材料中的旧人名、单位、日期、数字和任务事实是否误入；background/irrelevant材料"
                "是否被写入；正文是否出现多份材料摘要拼接或明显照抄。\n"
                f"Skill：{_skill_text(state, 'validation')}\n"
                f"{source_rules}\n{KNG_USAGE_RULES}\n已筛选证据：{_evidence_text(state)}\n\n"
                + (
                    "当前任务是选区修改，只审查 replacement 本身以及它与只读上下文的衔接；"
                    "不得要求或建议修改选区之外的正文。\n"
                    f"只读上下文：{json.dumps(state.get('selection') or {}, ensure_ascii=False)}\n"
                    f"replacement：\n{review_target}"
                    if selection_task
                    else f"正文：\n{review_target}"
                )
            )
            model_issues = []
            if (state.get("workflow_policy", {}).get("model_review", True)):
                try:
                    review = await context.model.complete_structured(
                        [{"role": "user", "content": review_prompt}], ReviewResult
                    )
                    model_issues = [
                        {**issue.model_dump(), "source": "model_review"} for issue in review.issues
                    ]
                except Exception:
                    await context.emit(
                        "warning",
                        {"code": "model_review_unavailable", "message": "模型审阅不可用，已保留规则校验结果"},
                        "validation",
                    )
            issues = list(state.get("material_issues") or []) + deterministic + model_issues
            return {"issues": issues}

        return await _stage(context, "validation", state, operation)
    return validate

__all__ = ['create_material_review_node', 'create_validate_node']
