from fastapi import APIRouter, HTTPException, status

from ..schemas import (
    DocumentExtractionIn,
    DocumentExtractionOut,
    ExtractionModelListOut,
)
from ..services.document_processor import AVAILABLE_MODELS
from ..services.official_document_extractor import (
    DocumentParseError,
    UnsupportedFileTypeError,
    extract_from_base64,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/models", response_model=ExtractionModelListOut)
def list_extraction_models():
    """获取可用的字段提取模型列表"""
    return {"models": sorted(AVAILABLE_MODELS)}


@router.post("/extractions", response_model=DocumentExtractionOut, status_code=status.HTTP_201_CREATED)
def create_document_extraction(request: DocumentExtractionIn):
    """从 Base64 编码的文件内容提取公文字段"""
    try:
        return extract_from_base64(
            filename=request.filename,
            content_base64=request.content_base64,
            model_name=request.model_name,
            include_parsed_content=request.include_parsed_content,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
