"""依赖注入：从请求中解析当前登录用户 / 管理员。

令牌通过 Authorization: Bearer <token> 传递。
普通用户令牌 type=user，管理员令牌 type=admin，两者互不通用。
"""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import Admin, User

# auto_error=False：没有令牌时返回 None，方便做"可选登录"接口
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _decode(credentials: HTTPAuthorizationCredentials | None, expected: str) -> dict:
    """解析令牌并校验类型，失败抛出 401。"""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("登录凭证无效") from exc
    if payload.get("type") != expected:
        raise ForbiddenError("令牌类型不匹配")
    return payload


def get_current_user(db: DbSession, credentials: Credentials) -> User:
    """必须登录的普通用户。"""
    payload = _decode(credentials, "user")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise UnauthorizedError("账号不存在")
    if user.is_disabled:
        raise ForbiddenError("账号已被禁用，请联系客服")
    return user


def get_optional_user(db: DbSession, credentials: Credentials) -> User | None:
    """可选登录：没令牌返回 None，有令牌则校验（用于"是否已点赞/收藏"这类字段）。"""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = _decode(credentials, "user")
    except (UnauthorizedError, ForbiddenError):
        return None
    user = db.get(User, int(payload["sub"]))
    if user is None or user.is_disabled:
        return None
    return user


def get_current_admin(db: DbSession, credentials: Credentials) -> Admin:
    """必须登录的后台管理员。"""
    payload = _decode(credentials, "admin")
    admin = db.get(Admin, int(payload["sub"]))
    if admin is None:
        raise UnauthorizedError("管理员账号不存在")
    if not admin.is_active:
        raise ForbiddenError("管理员账号已停用")
    return admin


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def get_client_ip(request: Request) -> str:
    """取客户端 IP（优先 X-Forwarded-For，兼容反向代理部署）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
