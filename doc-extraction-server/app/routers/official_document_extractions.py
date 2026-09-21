from fastapi import APIRouter, HTTPException, Request, status

from ..schemas import (
    DocumentFileGuardIn,
    DocumentFileGuardOut,
    DocumentExtractionIn,
    DocumentExtractionOut,
)
from ..services.official_document_extractor import (
    DocumentGuardError,
    DocumentParseError,
    UnsupportedFileTypeError,
    extract_from_base64,
    guard_file_from_base64,
    review_text,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extractions", response_model=DocumentExtractionOut, status_code=status.HTTP_201_CREATED)
def create_document_extraction(request: DocumentExtractionIn):
    """从 Base64 编码的文件内容提取公文字段"""
    try:
        return extract_from_base64(
            filename=request.filename,
            content_base64=request.content_base64,
            include_parsed_content=request.include_parsed_content,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/file-guard", response_model=DocumentFileGuardOut)
def guard_document_file(request: DocumentFileGuardIn):
    """解析 Base64 文件并审查正文，不保存解析内容。"""
    try:
        return guard_file_from_base64(
            filename=request.filename,
            content_base64=request.content_base64,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentGuardError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _review_flat(text: str) -> dict:
    """单条审查并把审查字段平铺返回；失败时返回 {"error": ...}。"""
    try:
        return review_text(text)
    except DocumentParseError as exc:
        return {"error": str(exc)}
    except DocumentGuardError as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "服务内部错误"}


@router.post("/text-guard")
async def guard_document_text(request: Request):
    """同时审查文本中的敏感内容和错别字/表述。

    同一入口支持两种请求形态（按请求体结构自动区分）：
    - 单条：{"text": "待审查文本"}（请求体仅含 text 一个键），返回平铺的审查结果，
      与既有调用方完全兼容；
    - 批量：{"自定义id1": "文本1", "自定义id2": "文本2"}，最多 20 条，文本 1..5000 字符；
      响应按相同 id 回带各自的审查字段，单条失败不影响其他条目，失败条目仅含 {"error": "原因"}。
      批量耗时随条目数线性增长（每条约 2-4 秒），调用方超时建议 >= 300 秒。
    """
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="请求体必须是 JSON 对象") from exc

    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=422, detail="请求体不能为空")

    # 单条模式：请求体仅含 text 一个键（保持既有调用方的行为不变）
    if set(payload.keys()) == {"text"}:
        text = payload["text"]
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=400, detail="审查内容不能为空")
        try:
            return review_text(text)
        except DocumentParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DocumentGuardError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    # 批量模式：{自定义id: 待审文本}
    if len(payload) > 20:
        raise HTTPException(status_code=422, detail="最多支持 20 条")
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            raise HTTPException(status_code=422, detail="id 必须为非空字符串")
        if len(key) > 64:
            raise HTTPException(status_code=422, detail=f"{key}：id 长度不能超过 64")
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=422, detail=f"{key}：文本不能为空")
        if len(value) > 5000:
            raise HTTPException(status_code=422, detail=f"{key}：文本长度不能超过 5000")
    return {key: _review_flat(value) for key, value in payload.items()}
