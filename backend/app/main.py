from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

PORT = int(os.getenv("BACKEND_PORT", 9000))

from .database import Base, engine
from .routers import session as session_router
from .routers import write as write_router
from .routers import content as content_router
from .routers import upload as upload_router
from .routers import generate as generate_router
from .routers import templates as templates_router
from .utils import err, ok, dt_str
from .database import SessionLocal

Base.metadata.create_all(bind=engine)

# 初始化默认模板
def init_default_template():
    try:
        db = SessionLocal()
        from .models import Template
        exists = db.query(Template).first()
        if not exists:
            t = Template(
                name="默认公文模板",
                filename="template.docx",
                description="默认公文模板（仿宋_GB2312、黑体等规范字体字号）",
                is_default=True,
            )
            db.add(t)
            db.commit()
            print("[init] 默认模板已初始化")
        db.close()
    except Exception as e:
        print(f"[init] 初始化默认模板失败: {e}")

init_default_template()

app = FastAPI(title="AI Writing Assistant Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router.router, prefix="/api")
app.include_router(write_router.router, prefix="/api")
app.include_router(content_router.router, prefix="/api")
app.include_router(upload_router.router, prefix="/api")
app.include_router(generate_router.router, prefix="/api")
app.include_router(templates_router.router, prefix="/api")

@app.get("/api/health")
def health():
    return ok({"timestamp": dt_str(datetime.now())}, "service is running")

DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="spa")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content=err(400, "参数错误"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=err(500, "服务器内部错误"))
