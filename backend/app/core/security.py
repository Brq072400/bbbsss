"""安全相关工具：密码哈希、JWT 签发与校验、验证码生成。

密码哈希使用标准库 PBKDF2-HMAC-SHA256（20 万次迭代 + 随机盐），
无需 bcrypt/passlib 等第三方依赖，任何 Python 3.9+ 环境可直接运行。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.core.config import settings

TokenType = Literal["user", "admin"]


# ---------------------------------------------------------------- 密码
def hash_password(password: str) -> str:
    """生成密码哈希，格式：pbkdf2_sha256$迭代次数$盐(base64)$摘要(base64)。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, settings.PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        settings.PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配（使用常数时间比较，防时序攻击）。"""
    try:
        algorithm, iterations, salt_b64, digest_b64 = hashed.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- JWT
def create_access_token(subject: str | int, token_type: TokenType = "user", extra: dict[str, Any] | None = None) -> str:
    """签发 JWT。subject 为账号主键，token_type 区分普通用户与管理员。"""
    minutes = settings.ADMIN_JWT_EXPIRE_MINUTES if token_type == "admin" else settings.JWT_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT，失败时抛出 jwt 的异常（由上层统一捕获）。"""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------- 验证码
def generate_code(length: int = 6) -> str:
    """生成纯数字验证码（短信/邮件用）。"""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_share_code(length: int = 8) -> str:
    """生成计划分享码（大写字母 + 数字，去除易混淆字符）。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------- 脱敏
def mask_phone(phone: str | None) -> str:
    """手机号脱敏：138****8000。"""
    if not phone or len(phone) < 7:
        return phone or ""
    return f"{phone[:3]}****{phone[-4:]}"


def mask_id_card(id_card: str | None) -> str:
    """身份证脱敏：110***********1234。"""
    if not id_card or len(id_card) < 8:
        return id_card or ""
    return f"{id_card[:3]}{'*' * (len(id_card) - 7)}{id_card[-4:]}"
