from __future__ import annotations

from .common import *

def create_finalize_node(context: AgentExecutionContext):
    async def finalize(state: WritingState):
        async def operation():
            unresolved = state.get("issues") or []
            warnings = list(state.get("warnings") or [])
            quality_gate: dict[str, Any] = {}
            if needs_revision(unresolved):
                warning = {
                    "code": "validation_unresolved",
                    "message": "正文仍有未完全解决的校验问题，请在编辑器中复核",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "finalize")
                if state.get("task_type") == "imitate" and state.get("reference_base_text"):
                    quality_gate = {
                        "block_apply": True,
                        "reason": "reference_copy_patch_has_errors",
                        "error_count": sum(1 for item in unresolved if item.get("severity") == "error"),
                    }
            labels = {"general": "公文", "notice": "通知", "regulation": "规章制度", "speech": "讲话稿"}
            task_labels = {
                "quick": "起草", "draft": "起草", "reference": "智能参考写作", "reply": "回函起草",
                "imitate": "底稿微调", "revise_document": "全文修改", "revise_selection": "选区修改",
                "review": "审查", "format": "版式处理",
            }
            summary = f"已完成{labels.get(state['document_type'], '公文')}{task_labels.get(state.get('task_type'), '处理')}"
            if state.get("references"):
                uploaded_count = sum(
                    1 for item in state["references"]
                    if isinstance(item, dict) and item.get("kind") == "uploaded_file"
                )
                knowledge_count = len(state["references"]) - uploaded_count
                source_parts = []
                if uploaded_count:
                    source_parts.append(f"{uploaded_count} 份上传材料")
                if knowledge_count:
                    source_parts.append(f"{knowledge_count} 条知识库来源")
                summary += "，使用 " + "、".join(source_parts)
            if quality_gate.get("block_apply"):
                summary += "；因底稿差异校验仍有严重问题，已保存为候选稿，未自动覆盖正文"
            final_article, heading_warnings = normalize_markdown_headings(state.get("draft", ""))
            if heading_warnings:
                warnings.extend(heading_warnings)
            outcome = "message" if state.get("task_type") == "review" else "document"
            if quality_gate.get("block_apply"):
                outcome = "proposal"
            return {
                "draft": final_article,
                "final_article": final_article,
                "summary": summary,
                "warnings": warnings,
                "outcome": outcome,
                "quality_gate": quality_gate,
            }

        return await _stage(context, "finalize", state, operation)
    return finalize

__all__ = ['create_finalize_node']
