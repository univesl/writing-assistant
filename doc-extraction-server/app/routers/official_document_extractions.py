from fastapi import APIRouter, HTTPException, status

from ..schemas import (
    DocumentFileGuardIn,
    DocumentFileGuardOut,
    DocumentTextGuardIn,
    DocumentTextGuardOut,
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


@router.post("/text-guard", response_model=DocumentTextGuardOut)
def guard_document_text(request: DocumentTextGuardIn):
    """同时审查文本中的敏感内容和错别字/表述。"""
    try:
        return review_text(request.text)
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentGuardError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
