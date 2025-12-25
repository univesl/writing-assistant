from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, engine
from .routers import session as session_router
from .routers import write as write_router
from .routers import content as content_router
from .utils import err, ok, dt_str

Base.metadata.create_all(bind=engine)

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


@app.get("/api/health")
def health():
    return ok({"timestamp": dt_str(datetime.now())}, "service is running")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content=err(400, "参数错误"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=err(500, "服务器内部错误"))
