"""FitTrack 应用入口。

启动：uvicorn app.main:app --reload --port 8000
文档：http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.response import ok

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fittrack")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子：建表、准备上传目录、创建默认管理员。"""
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (settings.UPLOAD_DIR / "avatars").mkdir(parents=True, exist_ok=True)
    (settings.UPLOAD_DIR / "posts").mkdir(parents=True, exist_ok=True)
    init_db()
    from app.services.bootstrap import ensure_default_admin, ensure_seed_data

    ensure_default_admin()
    ensure_seed_data()
    logger.info("%s v%s 启动完成", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """构建 FastAPI 实例（工厂函数，便于测试）。"""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="FitTrack 健身系统后端接口：用户、计划、课程、记录、动作库、统计、社区、饮食、后台管理",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 跨域：开发阶段允许全部来源，生产请改成具体域名
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    # 静态文件：上传的头像/图片（先确保目录存在，否则 StaticFiles 挂载会失败）
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    application.mount(
        settings.UPLOAD_URL_PREFIX,
        StaticFiles(directory=str(settings.UPLOAD_DIR)),
        name="uploads",
    )

    # 业务路由
    application.include_router(api_router, prefix=settings.API_PREFIX)

    @application.get("/", tags=["系统"], summary="健康检查")
    async def health() -> dict:
        """返回服务基本信息，用于探活。"""
        return ok({
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "api_prefix": settings.API_PREFIX,
        })

    return application


app = create_app()
