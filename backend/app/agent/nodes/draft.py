from __future__ import annotations

from .common import *

def create_outline_node(context: AgentExecutionContext):
    async def outline(state: WritingState):
        async def operation():
            prompt = (
                "为下面的中文公文任务生成结构化提纲。不得补造事实。\n\n"
                f"文种：{state['document_type']}\n用户要求：{state.get('requirements', '')}\n\n"
                f"写作规划：{_draft_plan_text(state)}\n\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n\n"
                f"{WRITING_SOURCE_RULES}\n\n"
                f"{KNG_USAGE_RULES}\n\n"
                f"Skill：\n{_skill_text(state, 'outline')}\n\n已筛选证据：\n{_evidence_text(state)}"
            )
            plan = await context.model.complete_structured(
                [{"role": "user", "content": prompt}], OutlinePlan
            )
            return {"outline": plan.model_dump()}

        return await _stage(context, "outline", state, operation)
    return outline

def create_draft_node(context: AgentExecutionContext):
    async def draft(state: WritingState):
        async def operation():
            task_type = state.get("task_type", "draft")
            if task_type == "imitate":
                task_instruction = (
                    "按底稿微调方式处理。以主底稿为基础进行复制式修订，先保留完整结构，再只按修改清单改动；"
                    "未被用户明确要求修改的段落、句式、附件项和版记默认保留。"
                    "不要概括、不要重写、不要只写变更项。"
                )
            else:
                task_instruction = {
                    "quick": "从零起草一份中文公文。",
                    "draft": "从零起草一份中文公文。",
                    "reference": "按智能参考写作方式处理。逐份判断上传材料的内容、结构和风格用途，综合生成一篇新的公文；不得把多份材料机械拼成摘要。",
                    "reply": "针对上传来文逐项作出边界清楚的正式回复。",
                    "imitate": "按底稿微调方式处理。以主底稿为基础做最小必要修订。",
                    "revise_document": "按照用户要求修订现有全文，保留未要求修改的正确内容。",
                    "revise_selection": "只改写指定选区，输出选区的替换文本。",
                }.get(task_type, "完成当前中文公文写作任务。")
            source_rules = REFERENCE_COPY_PATCH_RULES if task_type == "imitate" else WRITING_SOURCE_RULES
            reference_context = build_reference_copy_patch_context(state)
            prompt = (
                f"{task_instruction}严格遵循 Skill，只使用用户要求和证据中的事实。"
                "缺失信息不要猜测。只输出 Markdown，不输出说明。\n\n"
                f"文种：{state['document_type']}\n用户要求：{state.get('requirements', '')}\n\n"
                f"写作规划：{_draft_plan_text(state)}\n\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n\n"
                f"{reference_context}"
                f"{source_rules}\n\n"
                f"{KNG_USAGE_RULES}\n\n"
                f"Skill：\n{_skill_text(state, 'draft')}\n\n已筛选证据：\n{_evidence_text(state)}\n\n"
                f"现有正文：\n{state.get('base_article', '')}\n\n"
                f"选区：\n{json.dumps(state.get('selection') or {}, ensure_ascii=False)}"
            )
            full_text = ""
            pending = ""
            last_flush = time.perf_counter()
            stream_public = task_type not in {"revise_document", "revise_selection"}
            async for chunk in context.model.stream_text([{"role": "user", "content": prompt}]):
                context.check_cancelled()
                full_text += chunk
                pending += chunk
                now = time.perf_counter()
                if stream_public and (len(pending) >= 256 or now - last_flush >= 0.18):
                    await context.update_draft(full_text)
                    await context.emit(
                        "content.delta", {"mode": "append", "content": pending}, "draft"
                    )
                    pending = ""
                    last_flush = now
            if pending and stream_public:
                await context.emit("content.delta", {"mode": "append", "content": pending}, "draft")
            generated = _strip_fence(full_text)
            if not generated:
                raise ValueError("Model returned an empty draft")
            if task_type != "revise_selection":
                generated, heading_warnings = normalize_markdown_headings(generated)
                if heading_warnings:
                    await context.emit("warning", {
                        "code": "heading_normalized",
                        "message": "已将正文中的明显一级标题规范为正文层级",
                        "details": heading_warnings,
                    }, "draft")
            selection_replacement = generated if task_type == "revise_selection" else ""
            article = _apply_selection(
                state.get("base_article", ""), state.get("selection") or {}, generated
            ) if task_type == "revise_selection" else generated
            await context.update_draft(article)
            return {"draft": article, "selection_replacement": selection_replacement}

        return await _stage(context, "draft", state, operation)
    return draft

__all__ = ['create_outline_node', 'create_draft_node']
