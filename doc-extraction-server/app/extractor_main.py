from datetime import datetime
import traceback as _tb
from pathlib import Path
import time

from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# 字段提取服务独立部署时，配置文件位于项目根目录；必须在导入路由和服务模块前加载。
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from .routers import official_document_extractions as official_document_extractions_router


app = FastAPI(
    title="Document Extraction Service",
    version="2.0.0",
    description="公文解析服务：文件/文本内容检查（透传上游二合一接口）+ 公文字段提取（LLM）。",
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


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    """请求耗时日志：时间 方法 路径 -> 状态码 耗毫秒。仅观测，不影响业务逻辑。"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(
        f"[访问] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"{request.method} {request.url.path} -> {response.status_code} {elapsed_ms:.0f}ms",
        flush=True,
    )
    return response


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
    # 记录未处理异常堆栈（此前 500 静默无日志，排障困难）
    print(f"[500] {request.method} {request.url.path} -> {type(exc).__name__}: {exc}", flush=True)
    _tb.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )
