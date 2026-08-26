from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentType = str
TaskType = Literal[
    "quick",
    "draft",
    "reference",
    "reply",
    "imitate",
    "revise_document",
    "revise_selection",
    "review",
    "format",
]
RunStatus = Literal[
    "queued", "running", "completed", "failed", "cancelled", "interrupted"
]


class CreateAgentRunRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    task_type: TaskType = "draft"
    document_type: DocumentType = Field(default="general", min_length=1, max_length=64)
    requirements: str = Field(default="", max_length=30000)
    skill_names: list[str] = Field(default_factory=list, max_length=8)
    source_file_ids: list[int] = Field(default_factory=list, max_length=20)
    base_article: str = Field(default="", max_length=200000)
    selection: dict[str, Any] | None = None
    use_kng: bool = False
    use_web_search: bool = False
    model_profile_id: str | None = Field(default=None, max_length=64)


class AgentRunView(BaseModel):
    run_id: str
    session_id: int
    task_type: str
    document_type: str
    model_profile_id: str
    status: str
    current_stage: str | None = None
    attempt: int
    cancel_requested: bool
    article_snapshot: str = ""
    final_article: str | None = None
    summary: str | None = None
    outcome: str = "document"
    base_version: int = 0
    applied_version: int | None = None
    activated_skills: list[str] = Field(default_factory=list)
    workflow_plan: dict[str, Any] = Field(default_factory=dict)
    references: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    issues: list[Any] = Field(default_factory=list)
    last_event_seq: int = 0
    error: dict[str, Any] | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class AgentEventView(BaseModel):
    id: int
    type: str
    run_id: str
    stage: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ModelProfileView(BaseModel):
    id: str
    label: str
    provider: str
    model: str
    enabled: bool
    capabilities: list[str]


class SkillView(BaseModel):
    name: str
    description: str
    status: Literal["ready", "degraded", "incompatible"]
    compatibility: str = ""
    missing_tools: list[str] = Field(default_factory=list)
    disabled_scripts: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    capability_level: Literal["instruction", "workflow"] = "instruction"
    managed: bool = True
    roles: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
