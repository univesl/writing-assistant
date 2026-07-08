from pydantic import BaseModel, Field
from typing import Optional


class DocumentExtractionIn(BaseModel):
    filename: str = Field(..., min_length=1, description="文件名（含扩展名，如 report.pdf）")
    content_base64: str = Field(..., min_length=1, description="文件内容的 Base64 编码")
    model_name: str = Field(default="qwen2.5-72b", min_length=1, description="字段提取模型名称")
    include_parsed_content: bool = Field(default=False, description="是否返回解析后的正文内容")


class DocumentExtractionOut(BaseModel):
    filename: str
    file_type: str
    content_length: int
    fields: dict
    parsed_content: Optional[str] = None