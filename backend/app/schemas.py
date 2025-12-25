from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class SessionCreateIn(BaseModel):
    session_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class SessionRenameIn(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=255)


class WriteQuickIn(BaseModel):
    session_id: int
    prompt: str = Field(..., min_length=1)
    model_type: Optional[Literal["general", "creative"]] = "general"


class WriteStepIn(BaseModel):
    session_id: int
    product_name: str = Field(..., min_length=1)
    selling_points: List[str] = Field(default_factory=list)
    style: Literal["simple", "vivid", "formal"] = "simple"
    length: Literal["short", "medium", "long"] = "medium"


class WritePolishIn(BaseModel):
    session_id: int
    content: str = Field(..., min_length=1)
    polish_type: Literal["check", "optimize", "expand"]


class WriteSaveIn(BaseModel):
    session_id: int
    content: str = Field(..., min_length=1)
    content_type: Literal["quick", "step", "polish"]
    original_content: Optional[str] = None
