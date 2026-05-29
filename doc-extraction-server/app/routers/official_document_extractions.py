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


@router.post("/extractions", response_model=DocumentExtractionOut, status_code=status.HTTP_201_CREATED)
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