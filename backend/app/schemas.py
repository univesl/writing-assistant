from pydantic import BaseModel, Field
from typing import Literal, Optional


class SessionCreateIn(BaseModel):
    session_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class SessionRenameIn(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=255)


class WriteQuickIn(BaseModel):
    session_id: int
    prompt: str = Field(..., min_length=1)
    model_type: Optional[Literal["general", "creative"]] = "general"


class WriteSaveIn(BaseModel):
    session_id: int
    content: str = Field(..., min_length=1)
    content_type: Literal["quick"]
    original_content: Optional[str] = None
