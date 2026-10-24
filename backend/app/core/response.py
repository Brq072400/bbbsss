"""统一响应封装与业务异常定义。

约定：所有接口都返回 Envelope 结构
    {"code": 0, "message": "success", "data": <业务数据>}
业务错误通过 ApiError 抛出，由全局异常处理器转成同样的结构，
同时保留正确的 HTTP 状态码，方便前端与网关识别。
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------- 错误码
class ErrorCode:
    """业务错误码常量（0 表示成功，其余按模块分段）。"""

    SUCCESS = 0
    BAD_REQUEST = 40000            # 参数错误
    UNAUTHORIZED = 40100           # 未登录 / 令牌无效
    FORBIDDEN = 40300              # 无权限
    NOT_FOUND = 40400              # 资源不存在
    CONFLICT = 40900               # 冲突（重复注册、重复收藏等）
    TOO_MANY_REQUESTS = 42900      # 请求过于频繁
    SERVER_ERROR = 50000           # 服务端异常


class ApiError(Exception):
    """业务异常：路由里直接 raise，由全局处理器统一转成响应。"""

    def __init__(self, message: str, code: int = ErrorCode.BAD_REQUEST, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(ApiError):
    """资源不存在（404）。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message, ErrorCode.NOT_FOUND, 404)


class UnauthorizedError(ApiError):
    """未认证或令牌过期（401）。"""

    def __init__(self, message: str = "请先登录") -> None:
        super().__init__(message, ErrorCode.UNAUTHORIZED, 401)


class ForbiddenError(ApiError):
    """已登录但无权限（403）。"""

    def __init__(self, message: str = "没有权限执行该操作") -> None:
        super().__init__(message, ErrorCode.FORBIDDEN, 403)


class ConflictError(ApiError):
    """资源冲突（409）。"""

    def __init__(self, message: str = "数据已存在") -> None:
        super().__init__(message, ErrorCode.CONFLICT, 409)


class BadRequestError(ApiError):
    """参数校验失败（400）。"""

    def __init__(self, message: str = "请求参数有误") -> None:
        super().__init__(message, ErrorCode.BAD_REQUEST, 400)


# ---------------------------------------------------------------- 响应结构
class Envelope(BaseModel, Generic[T]):
    """统一响应外壳。"""

    code: int = Field(default=0, description="业务码，0 成功")
    message: str = Field(default="success", description="提示信息")
    data: T | None = Field(default=None, description="业务数据")


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    """构造成功响应。"""
    return {"code": ErrorCode.SUCCESS, "message": message, "data": data}


def fail(message: str, code: int = ErrorCode.BAD_REQUEST) -> dict[str, Any]:
    """构造失败响应（仅用于异常处理器内部）。"""
    return {"code": code, "message": message, "data": None}
