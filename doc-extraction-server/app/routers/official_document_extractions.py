from fastapi import APIRouter, Body, HTTPException, status

from ..schemas import (
    DocumentFileGuardIn,
    DocumentFileGuardOut,
    DocumentTextGuardIn,
    DocumentTextGuardOut,
    DocumentExtractionIn,
    DocumentExtractionOut,
    BatchTextGuardIn,
    BatchItemOut,
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

# 对外规范端点（签发系统契约）：由 extractor_main 挂在 /api/v1/sign 下
sign_router = APIRouter(tags=["sign"])


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


@router.post("/text-guard", response_model=DocumentTextGuardOut)
def guard_document_text(request: DocumentTextGuardIn):
    """同时审查文本中的敏感内容和错别字/表述。"""
    try:
        return review_text(request.text)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentGuardError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/text-guard/batch", deprecated=True)
def batch_guard_text(request: BatchTextGuardIn):
    """批量文本审查（已废弃，请改用 /api/v1/sign/batch-submit）：逐条执行并按调用方 id 返回各自结果，单条失败不影响其他条。

    耗时与条目数线性相关（内部串行排队，每条约 2-4 秒），20 条约 40-80 秒，
    调用方超时建议 >= 300 秒。
    """
    ids = [item.id for item in request.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="items 中存在重复的 id")

    results: dict = {}
    for item in request.items:
        try:
            review = review_text(item.text)
            results[item.id] = BatchItemOut(success=True, error="", code=None, review=review)
        except DocumentParseError as exc:
            results[item.id] = BatchItemOut(success=False, error=str(exc), code="VALIDATION", review=None)
        except DocumentGuardError as exc:
            results[item.id] = BatchItemOut(success=False, error=str(exc), code="GUARD_UNAVAILABLE", review=None)
        except Exception:
            results[item.id] = BatchItemOut(success=False, error="服务内部错误", code="INTERNAL", review=None)
    return results


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


@sign_router.post("/batch-submit")
def sign_batch_submit(payload: dict[str, str] = Body(..., description="调用方自定义 id 到待审文本的映射")):
    """批量签发文本审查（对外规范端点）。

    请求：{"id1": "文本", "id2": "文本"}，id 为调用方自定义幂等键（响应按 id 回带结果）。
    响应：每个 id 下平铺审查字段（harmful*/highlight_spans/stage/issues/corrected/
    typo_check_error）；单条失败不影响其他条目，失败条目仅含 {"error": "..."}。

    限制：最多 20 条；id 长度 ≤ 64；文本 1..5000 字符。耗时与条目数线性相关
    （每条约 2-4 秒），调用方超时建议 >= 300 秒。
    """
    if not payload:
        raise HTTPException(status_code=422, detail="请求体不能为空")
    if len(payload) > 20:
        raise HTTPException(status_code=422, detail="最多支持 20 条")
    too_long_ids = [k for k in payload if len(k) > 64]
    if too_long_ids:
        raise HTTPException(status_code=422, detail=f"id 长度不能超过 64：{too_long_ids[:5]}")
    for key, value in payload.items():
        if not value.strip():
            raise HTTPException(status_code=422, detail=f"{key}：文本不能为空")
        if len(value) > 5000:
            raise HTTPException(status_code=422, detail=f"{key}：文本长度不能超过 5000")
    return {key: _review_flat(value) for key, value in payload.items()}
