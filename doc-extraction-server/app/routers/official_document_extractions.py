from fastapi import APIRouter, HTTPException, status

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


@router.post("/text-guard/batch")
def batch_guard_text(request: BatchTextGuardIn):
    """批量文本审查：逐条执行并按调用方 id 返回各自结果，单条失败不影响其他条。

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
