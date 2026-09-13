from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 - register SQLAlchemy models / 注册数据模型
from app.api.endpoints import badcases, dataset
from app.api.router import api_router
from app.core.config import settings
from app.db.database import Base, engine


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


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}
