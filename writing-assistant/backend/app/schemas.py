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
