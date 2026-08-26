from pydantic import BaseModel, Field
from typing import Literal, Optional


class SessionCreateIn(BaseModel):
    session_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class SessionRenameIn(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=255)


class WriteQuickIn(BaseModel):
    session_id: int
    mode: str = "quick"  # "quick" | "edit" | "reply" | "imitate" | "general_ref"
    style: str = "general"  # "notice" | "regulation" | "speech" | "general"
    user_requirements: str = ""
    reference_content: str = ""
    reference_filename: str = ""
    rag_content: str = ""
    rag_references: list = []
    quotes: list = []
    article_content: str = ""
    extracted_fields: dict = {}
    model_type: Optional[Literal["general", "creative"]] = "general"
    llm_model: Optional[Literal["xhang", "qwen"]] = "xhang"
    use_rag: bool = False


class WriteSelectionEditIn(BaseModel):
    """AI 局部修改请求；上下文只读，模型唯一可改范围仍是选区。"""

    session_id: int
    selected_markdown: str = Field(..., min_length=1, max_length=30000)
    document_title: str = Field(default="", max_length=300)
    section_heading: str = Field(default="", max_length=800)
    context_before: str = Field(default="", max_length=3000)
    context_after: str = Field(default="", max_length=3000)
    instruction: str = Field(..., min_length=1, max_length=4000)
    style: str = "general"
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
    # 允许保存空文章：当用户选中全文并执行“删除选区”时，
    # 空字符串是合法的最终编辑结果，不能让刷新后恢复旧内容。
    article_content: str = Field(..., min_length=0)
    article_title: Optional[str] = Field(default=None, max_length=255)
    original_content: Optional[str] = None
    base_version: Optional[int] = Field(default=None, ge=0)


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


class DocumentFileGuardIn(BaseModel):
    """文件内容审查请求"""
    filename: str = Field(..., min_length=1, description="文件名（含扩展名）")
    content_base64: str = Field(..., min_length=1, description="文件内容的 Base64 编码")


class DocumentFileGuardReview(BaseModel):
    """内容审查结果"""
    harmful: str
    harmful_type: str = "none"
    harmful_type_label: str = "无"
    harmful_reason: str = ""
    harmful_words: str = ""
    harmful_degree: str = "none"
    harmful_degree_label: str = "无"
    confidence: str = "low"
    confidence_label: str = "低"
    highlight_spans: list = []
    stage: Optional[str] = None


class DocumentFileGuardOut(BaseModel):
    """文件内容审查响应"""
    filename: str
    file_type: str
    content_length: int
    review: DocumentFileGuardReview


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


class TemplateOut(BaseModel):
    """模板列表输出"""
    template_id: int
    name: str
    filename: str
    description: str
    is_default: bool
    created_at: str


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


class TemplateOut(BaseModel):
    """模板列表输出"""
    template_id: int
    name: str
    filename: str
    description: str
    is_default: bool
    created_at: str


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


class TemplateOut(BaseModel):
    """模板列表输出"""
    template_id: int
    name: str
    filename: str
    description: str
    is_default: bool
    created_at: str
