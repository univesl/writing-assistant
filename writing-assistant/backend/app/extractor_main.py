from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import official_document_extractions as official_document_extractions_router


app = FastAPI(
    title="Document Extraction Service",
    version="2.0.0",
    description="公文字段提取服务，通过 RESTful API 接收 Base64 编码文件并返回 JSON 提取结果。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(official_document_extractions_router.router, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "official-document-extractor",
        "timestamp": datetime.now().isoformat(),
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求参数校验失败",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )
