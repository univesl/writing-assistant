from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .skill_registry import SkillDescriptor, SkillRegistry, SkillValidationError
from .tool_registry import ToolRegistry, get_tool_registry


TASK_ALIASES = {"quick": "draft"}
TASK_STAGES: dict[str, tuple[str, ...]] = {
    "draft": ("prepare", "skill", "planning", "draft", "validation", "finalize"),
    "reference": ("prepare", "skill", "planning", "retrieval", "evidence_filter", "draft", "validation", "finalize"),
    "reply": ("prepare", "skill", "planning", "retrieval", "evidence_filter", "draft", "validation", "finalize"),
    "imitate": ("prepare", "skill", "planning", "retrieval", "evidence_filter", "draft", "validation", "finalize"),
    "revise_document": ("prepare", "skill", "draft", "validation", "finalize"),
    "revise_selection": ("prepare", "skill", "draft", "validation", "finalize"),
    "review": ("prepare", "skill", "validation", "finalize"),
    "format": ("prepare", "skill", "format", "finalize"),
}


@dataclass(frozen=True)
class CompiledWorkflow:
    task_type: str
    primary_skill: SkillDescriptor
    supporting_skills: tuple[SkillDescriptor, ...]
    stages: tuple[str, ...]
    tools: tuple[str, ...]
    policy: dict[str, Any]

    def public_view(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "skills": [self.primary_skill.name, *(skill.name for skill in self.supporting_skills)],
            "stages": list(self.stages),
            "tools": list(self.tools),
            "policy": dict(self.policy),
        }


class WorkflowCompiler:
    """Compile a Skill into a bounded writing workflow.

    A Skill may select optional phases and server-owned tools.  It cannot add
    executable nodes or remove the mandatory preparation, validation and
    persistence envelope.
    """

    def __init__(self, skills: SkillRegistry, tools: ToolRegistry | None = None):
        self.skills = skills
        self.tools = tools or get_tool_registry()

    @staticmethod
    def _app_metadata(skill: SkillDescriptor) -> dict[str, Any]:
        nested = skill.metadata.get("writing-assistant")
        if isinstance(nested, dict):
            return nested
        # Backward compatibility for the first generation of bundled Skills.
        return skill.metadata

    def compile(
        self,
        *,
        task_type: str,
        primary_skill_name: str,
        supporting_skill_names: Iterable[str] = (),
        use_kng: bool = False,
        use_web_search: bool = False,
    ) -> CompiledWorkflow:
        normalized_task = TASK_ALIASES.get(task_type, task_type)
        if normalized_task not in TASK_STAGES:
            raise SkillValidationError(f"Unsupported writing task: {task_type}")

        primary = self.skills.get(primary_skill_name)
        supporting = tuple(self.skills.get(name) for name in supporting_skill_names)
        metadata = self._app_metadata(primary)
        declared_tasks = metadata.get("task-types") or metadata.get("task_types") or []
        if isinstance(declared_tasks, str):
            declared_tasks = [declared_tasks]
        if declared_tasks and normalized_task not in declared_tasks:
            raise SkillValidationError(
                f"Skill {primary.name} does not support task type {normalized_task}"
            )

        workflow = metadata.get("workflow") if isinstance(metadata.get("workflow"), dict) else {}
        outline_policy = str(workflow.get("outline", "required"))
        max_revisions = min(1, max(0, int(workflow.get("max-revisions", 1))))
        model_review = bool(workflow.get("model-review", True))

        stages = list(TASK_STAGES[normalized_task])
        if not (use_kng or use_web_search):
            stages = [stage for stage in stages if stage not in {"retrieval", "evidence_filter"}]

        requested_tools = set(primary.allowed_tools)
        for skill in supporting:
            requested_tools.update(skill.allowed_tools)
        if use_kng:
            requested_tools.add("kng_search")
        if use_web_search:
            requested_tools.add("web_search")
        unavailable = sorted(requested_tools - self.tools.names())
        if unavailable:
            raise SkillValidationError(
                f"Workflow requests unavailable built-in tools: {', '.join(unavailable)}"
            )

        return CompiledWorkflow(
            task_type=normalized_task,
            primary_skill=primary,
            supporting_skills=supporting,
            stages=tuple(stages),
            tools=tuple(sorted(requested_tools)),
            policy={
                "outline": "embedded_in_planning",
                "model_review": model_review,
                "max_revisions": max_revisions,
            },
        )
