from typing import Any, TypedDict


class WritingState(TypedDict, total=False):
    run_id: str
    session_id: int
    task_type: str
    document_type: str
    requirements: str
    skill_names: list[str]
    source_file_ids: list[int]
    source_materials: list[dict[str, Any]]
    material_cards: list[dict[str, Any]]
    reference_mode: str
    reference_strategy: dict[str, Any]
    reference_base_file_id: int | None
    reference_base_text: str
    reference_change_plan: dict[str, Any]
    reference_working_copy: str
    reference_patch_log: list[dict[str, Any]]
    reference_supporting_file_ids: list[int]
    source_bindings: list[dict[str, Any]]
    writing_plan: dict[str, Any]
    base_article: str
    selection: dict[str, Any]
    use_kng: bool
    use_web_search: bool
    model_profile_id: str
    skill_name: str
    skill_instructions: str
    skill_guidance: dict[str, str]
    workflow_policy: dict[str, Any]
    workflow_plan: dict[str, Any]
    activated_skills: list[str]
    retrieval_plan: list[dict[str, Any]]
    raw_retrievals: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    references: list[Any]
    warnings: list[dict[str, Any]]
    outline: dict[str, Any]
    draft: str
    issues: list[dict[str, Any]]
    material_issues: list[dict[str, Any]]
    selection_replacement: str
    revision_count: int
    final_article: str
    summary: str
    outcome: str
    quality_gate: dict[str, Any]
