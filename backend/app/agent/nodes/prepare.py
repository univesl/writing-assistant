from __future__ import annotations

from .common import *

def create_prepare_node(context: AgentExecutionContext):
    async def prepare(state: WritingState):
        async def operation():
            document_type = state.get("document_type")
            if document_type not in STYLE_SKILLS and not state.get("skill_names"):
                raise ValueError(f"Unsupported document type: {document_type}")
            return {
                "evidence": [],
                "retrieval_plan": [],
                "raw_retrievals": [],
                "references": [],
                "warnings": [],
                "issues": [],
                "material_issues": [],
                "material_cards": [],
                "reference_mode": {
                    "reply": "reply",
                    "imitate": "base_tuning",
                    "reference": "synthesize",
                }.get(state.get("task_type", ""), ""),
                "reference_strategy": {},
                "reference_base_file_id": None,
                "reference_base_text": "",
                "reference_change_plan": {},
                "reference_working_copy": "",
                "reference_patch_log": [],
                "reference_supporting_file_ids": [],
                "source_bindings": [],
                "writing_plan": {},
                "selection_replacement": "",
                "revision_count": int(state.get("revision_count") or 0),
                "outline": {},
                "quality_gate": {},
                "use_web_search": bool(state.get("use_web_search")),
                "draft": state.get("base_article", "")
                if state.get("task_type") in {"review", "format"}
                else state.get("draft", ""),
            }

        return await _stage(context, "prepare", state, operation)
    return prepare

def create_load_skill_node(context: AgentExecutionContext):
    async def load_skill(state: WritingState):
        async def operation():
            requested = list(state.get("skill_names") or [])
            skill_name = requested[0] if requested else STYLE_SKILLS[state["document_type"]]
            supporting_names = requested[1:]
            for helper_skill in (REVIEW_SKILL, REFERENCE_ANALYSIS_SKILL if state.get("source_materials") else None):
                if helper_skill and helper_skill != skill_name and helper_skill not in supporting_names:
                    supporting_names.append(helper_skill)
            compiled = WorkflowCompiler(context.skills).compile(
                task_type=state.get("task_type", "draft"),
                primary_skill_name=skill_name,
                supporting_skill_names=supporting_names,
                use_kng=bool(state.get("use_kng")),
                use_web_search=bool(state.get("use_web_search")),
            )
            skill = compiled.primary_skill
            review_skill = next(
                (item for item in compiled.supporting_skills if item.name == REVIEW_SKILL),
                None,
            )
            if review_skill is None:
                review_skill = skill if skill.name == REVIEW_SKILL else context.skills.get(REVIEW_SKILL)
            for selected_skill in (skill, *compiled.supporting_skills):
                if selected_skill.status == "degraded":
                    await context.emit(
                        "warning",
                        {
                            "code": "skill_degraded",
                            "message": f"Skill {selected_skill.name} 中未注册的脚本保持禁用",
                        },
                        "skill",
                    )

            policy = dict(compiled.policy)
            guidance = {
                phase: _phase_references(context, skill, phase, state)
                for phase in ("planning", "outline", "draft", "validation", "revision")
            }
            review_body = "" if review_skill.name == skill.name else _skill_runtime_contract(review_skill)
            for phase in ("draft", "validation", "revision"):
                review_reference = _phase_references(context, review_skill, phase, state)
                guidance[phase] = "\n\n".join(
                    item
                    for item in (
                        guidance.get(phase),
                        review_body if phase != "draft" else "",
                        review_reference,
                    )
                    if item
                )
            activated_skills = [skill.name, *(item.name for item in compiled.supporting_skills)]
            for selected_skill in (skill, *compiled.supporting_skills):
                await context.emit(
                    "skill.activated",
                    {
                        "name": selected_skill.name,
                        "status": selected_skill.status,
                        "capability_level": selected_skill.capability_level,
                    },
                    "skill",
                )
            public_plan = {
                **compiled.public_view(),
                **(state.get("workflow_plan") or {}),
            }
            await context.emit("plan.ready", public_plan, "skill")
            return {
                "skill_name": skill.name,
                "skill_instructions": _skill_runtime_contract(skill),
                "skill_guidance": guidance,
                "workflow_policy": policy,
                "workflow_plan": public_plan,
                "activated_skills": activated_skills,
            }

        return await _stage(context, "skill", state, operation)
    return load_skill

__all__ = ['create_prepare_node', 'create_load_skill_node']
