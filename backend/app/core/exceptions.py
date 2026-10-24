"""全局异常处理器：把各类异常统一转换成 {code,message,data} 结构。"""
from __future__ import annotations

import logging

import jwt
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import ApiError, ErrorCode

logger = logging.getLogger("fittrack.error")


def _json(payload: dict, status_code: int) -> JSONResponse:
    """统一返回 JSONResponse，保证中文不被转义。"""
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册全部异常处理器。"""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        """业务异常：按异常自带的状态码返回。"""
        return _json({"code": exc.code, "message": exc.message, "data": None}, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """参数校验异常：把 pydantic 的报错压成一句人话。"""
        details: list[str] = []
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err.get("loc", ()) if p != "body")
            details.append(f"{loc}: {err.get('msg', 'invalid')}")
        message = "；".join(details[:5]) or "请求参数有误"
        return _json({"code": ErrorCode.BAD_REQUEST, "message": message, "data": None}, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(jwt.ExpiredSignatureError)
    async def _jwt_expired(request: Request, exc: jwt.ExpiredSignatureError) -> JSONResponse:
        """令牌过期。"""
        return _json({"code": ErrorCode.UNAUTHORIZED, "message": "登录已过期，请重新登录", "data": None},
                     status.HTTP_401_UNAUTHORIZED)

    @app.exception_handler(jwt.PyJWTError)
    async def _jwt_invalid(request: Request, exc: jwt.PyJWTError) -> JSONResponse:
        """令牌非法。"""
        return _json({"code": ErrorCode.UNAUTHORIZED, "message": "登录凭证无效", "data": None},
                     status.HTTP_401_UNAUTHORIZED)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """框架层 HTTP 异常（404/405 等）。"""
        code = {401: ErrorCode.UNAUTHORIZED, 403: ErrorCode.FORBIDDEN, 404: ErrorCode.NOT_FOUND}.get(
            exc.status_code, ErrorCode.BAD_REQUEST
        )
        return _json({"code": code, "message": str(exc.detail), "data": None}, exc.status_code)

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        """数据库唯一约束/外键冲突。"""
        logger.warning("integrity error: %s", exc.orig)
        return _json({"code": ErrorCode.CONFLICT, "message": "数据冲突：记录已存在或关联数据不存在", "data": None},
                     status.HTTP_409_CONFLICT)

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """其它数据库异常。"""
        logger.exception("database error: %s", exc)
        return _json({"code": ErrorCode.SERVER_ERROR, "message": "数据库操作失败", "data": None},
                     status.HTTP_500_INTERNAL_SERVER_ERROR)

    @app.exception_handler(Exception)
    async def _unknown_error(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未捕获异常，记录堆栈但只返回安全信息。"""
        logger.exception("unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return _json({"code": ErrorCode.SERVER_ERROR, "message": "服务器开小差了，请稍后再试", "data": None},
                     status.HTTP_500_INTERNAL_SERVER_ERROR)
