import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

import app.models  # noqa: F401 - register SQLAlchemy models / 注册数据模型
from app.api.endpoints import badcases, dataset
from app.api.router import api_router
from app.core.config import settings
from app.db.database import Base, engine
from app.services.converter import (
    ConversionError,
    InvalidInputError,
    MissingDependencyError,
    UnsupportedConversionError,
    classify_error_type,
)
from app.services.error_severity import severity_for_error_type


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Bootstrap local resources / 启动时初始化 SQLite 与存储目录
    Base.metadata.create_all(bind=engine)
    for directory in ("uploads", "outputs", "datasets"):
        Path(settings.storage_root, directory).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Format conversion agent API / 格式转换与失败数据沉淀服务",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
# Badcase 浏览接口单独注册，便于后续独立演进数据集能力。
app.include_router(badcases.router, prefix="/api/badcases", tags=["badcases"])
# 数据集导出与概览接口保持独立，便于后续增加版本管理。
app.include_router(dataset.router, prefix="/api/dataset", tags=["dataset"])


def _json_error_response(
    request: Request,
    *,
    status_code: int,
    error: str,
    detail: Any,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造所有异常处理器共用的 JSON 响应。"""

    content = {
        "error": error,
        "detail": detail,
        "path": request.url.path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _log_500(request: Request, exc: BaseException) -> None:
    """记录 500 异常及完整 traceback。"""

    logger.error(
        "请求 %s 发生未处理的 500 异常",
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """把请求参数校验失败统一转换为 JSON。"""

    return _json_error_response(
        request,
        status_code=422,
        error="Request Validation Error",
        detail="请求参数校验失败",
        extra={"validation_errors": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """保留 HTTP 异常状态码，并补齐统一响应字段。"""

    if exc.status_code == 500:
        _log_500(request, exc)
    return _json_error_response(
        request,
        status_code=exc.status_code,
        error="Internal Server Error" if exc.status_code == 500 else "HTTP Error",
        detail=exc.detail,
        headers=exc.headers,
    )


@app.exception_handler(ConversionError)
async def handle_conversion_exception(request: Request, exc: ConversionError) -> JSONResponse:
    """按照转换异常类型返回对应状态码和错误分类。"""

    error_type = classify_error_type(exc)
    if isinstance(exc, (UnsupportedConversionError, InvalidInputError)) or error_type in {
        "image_encode_error",
        "unknown",
    }:
        status_code = 400
    elif isinstance(exc, MissingDependencyError):
        status_code = 503
    else:
        status_code = 500
    if status_code == 500:
        _log_500(request, exc)
    return _json_error_response(
        request,
        status_code=status_code,
        error=error_type,
        detail=str(exc),
        extra={
            "error_type": error_type,
            "severity": severity_for_error_type(error_type),
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """兜底捕获未处理异常，确保客户端始终收到 JSON 响应。"""

    _log_500(request, exc)
    return _json_error_response(
        request,
        status_code=500,
        error="Internal Server Error",
        detail="服务器处理请求时发生内部错误，请查看后端日志",
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}
