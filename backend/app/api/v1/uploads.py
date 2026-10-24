"""通用图片上传接口。

社区发图、课程封面等都会用到；头像上传在用户模块里单独实现（会写回 user.avatar）。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.response import BadRequestError, ok

router = APIRouter(prefix="/uploads", tags=["上传"])

# 允许上传的子目录（与 lifespan 里预建的一致）
ALLOWED_SUBDIRS = {"avatars", "posts", "covers", "misc"}


def save_image(file: UploadFile, subdir: str = "misc") -> str:
    """保存一张图片并返回可访问 URL。

    参数:
        file: FastAPI 上传对象
        subdir: 目标子目录（avatars / posts / covers / misc）
    返回:
        形如 /static/uploads/misc/xxxx.png 的 URL
    """
    if subdir not in ALLOWED_SUBDIRS:
        raise BadRequestError("非法的上传目录")
    if file.content_type not in settings.allowed_image_types:
        raise BadRequestError(f"只支持这些图片格式：{settings.ALLOWED_IMAGE_TYPES}")

    data = file.file.read()
    if not data:
        raise BadRequestError("上传的文件为空")
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise BadRequestError(f"图片不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 用 uuid 重命名，避免中文名与重名问题
    suffix = Path(file.filename or "img.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{suffix}"
    target_dir = settings.UPLOAD_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_bytes(data)
    return f"{settings.UPLOAD_URL_PREFIX}/{subdir}/{filename}"


@router.post("/image", summary="上传图片（社区配图等）")
async def upload_image(file: UploadFile = File(..., description="图片文件"), user: CurrentUser = None) -> dict:
    """上传一张图片到 posts 目录，返回 URL。需要登录。"""
    url = save_image(file, "posts")
    return ok({"url": url})


@router.post("/images", summary="批量上传图片（最多 9 张）")
async def upload_images(files: list[UploadFile] = File(...), user: CurrentUser = None) -> dict:
    """一次上传多张图片，返回 URL 列表。需要登录。"""
    if len(files) > 9:
        raise BadRequestError("一次最多上传 9 张图片")
    urls = [save_image(f, "posts") for f in files]
    return ok({"urls": urls})
