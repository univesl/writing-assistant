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
    llm_model: Optional[Literal["xhang", "qwen"]] = "xhang"


class WriteSaveIn(BaseModel):
    session_id: int
    content: str = Field(..., min_length=1)
    content_type: Literal["quick", "reply", "reference"]
    content_category: Optional[Literal["chat", "article"]] = "chat"
    role: Optional[Literal["user", "assistant"]] = "user"
    original_content: Optional[str] = None


class SaveArticleIn(BaseModel):
    session_id: int
    article_content: str = Field(..., min_length=1)
    article_title: Optional[str] = Field(default=None, max_length=255)
    original_content: Optional[str] = None


class FileUploadResponse(BaseModel):
    file_id: int
    session_id: int
    original_filename: str
    file_type: str
    status: str
    parsed: Optional[bool] = None
    extracted: Optional[bool] = None
    fields: Optional[dict] = None
    content_length: Optional[int] = None
    error: Optional[str] = None


class FileListResponse(BaseModel):
    file_id: int
    original_filename: str
    file_type: str
    status: str
    created_at: str
    updated_at: str
    fields: Optional[dict] = None


class UpdateFieldsIn(BaseModel):
    """更新字段请求"""
    fields: dict = Field(..., description="字段键值对")


class UpdateFieldsResponse(BaseModel):
    """更新字段响应"""
    file_id: int
    fields: dict
    updated_at: str


class DocumentExtractionIn(BaseModel):
    """公文字段提取请求"""
    filename: str = Field(..., min_length=1, description="文件名（含扩展名，如 report.pdf）")
    content_base64: str = Field(..., min_length=1, description="文件内容的 Base64 编码")
    model_name: str = Field(default="qwen2.5-72b", min_length=1, description="字段提取模型名称")
    include_parsed_content: bool = Field(default=False, description="是否返回解析后的正文内容")


class DocumentExtractionOut(BaseModel):
    """公文字段提取响应"""
    filename: str
    file_type: str
    model_name: str
    content_length: int
    fields: dict
    parsed_content: Optional[str] = None


class ExtractionModelListOut(BaseModel):
    """字段提取模型列表"""
    models: list[str]


# 回函生成请求
class ReplyGenerationRequest(BaseModel):
    session_id: int
    topic: str = ""
    requirements: str = ""
    original_content: str = ""
    extracted_fields: dict = {}
    model_name: str = "qwen2.5-72b"
    use_knowledge_base: bool = True
    top_k: int = 3


# 参考生成请求
class ReferenceGenerationRequest(BaseModel):
    session_id: int
    topic: str
    requirements: str = ""
    template_type: str = "general"
    reference_content: str = ""
    model_name: str = "qwen2.5-72b"
    use_knowledge_base: bool = True
    top_k: int = 3


# 参考写作请求（新增三模式）
class ReferenceWriteRequest(BaseModel):
    session_id: int
    reference_content: str = ""
    reference_filename: str = ""
    generate_type: str = "general"  # reply | imitate | general
    topic: str = ""
    requirements: str = ""
    template_type: str = "general"
    model_name: str = "qwen2.5-72b"
    use_knowledge_base: bool = True
    top_k: int = 3
