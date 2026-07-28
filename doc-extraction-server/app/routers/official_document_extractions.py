from fastapi import APIRouter, HTTPException, status

from ..schemas import (
    DocumentExtractionIn,
    DocumentExtractionOut,
)
from ..services.document_processor import AVAILABLE_MODELS
from ..services.official_document_extractor import (
    DocumentParseError,
    UnsupportedFileTypeError,
    extract_from_base64,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/models")
def list_available_models():
    return [
        {
            "name": name,
            "display_name": name,
            "model": config.get("model", name),
            "base_url": config.get("base_url", ""),
        }
        for name, config in AVAILABLE_MODELS.items()
    ]


@router.post(
    "/extractions",
    response_model=DocumentExtractionOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_document_extraction(request: DocumentExtractionIn):
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
