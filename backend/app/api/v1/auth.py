# ---------------------------------------------------------------------------
# 本模块导出的路由变量名：router
#   router = APIRouter(prefix="/auth", tags=["认证"])
# 汇总做法：from app.api.v1 import auth  ->  api_router.include_router(auth.router)
# 最终路径前缀：settings.API_PREFIX + /auth，例如 /api/auth/register
# ---------------------------------------------------------------------------
"""认证模块路由：注册、登录、退出、令牌刷新、密码重置、手机号绑定、修改密码。

说明：
- 登录态使用无状态 JWT（见 app.core.security.create_access_token），
  令牌里只放 ``sub=user.id`` 与 ``type="user"``，服务端不保存会话；
- 验证码统一落在 ``sms_codes`` 表，通过 scene 区分用途：
  ``reset_password``（忘记密码）与 ``bind_phone``（绑定手机号），有效期 10 分钟；
- 演示环境把验证码直接返回给前端，生产环境必须删除该字段并改由短信/邮件网关下发。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, OptionalUser, get_client_ip
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ok
from app.core.security import create_access_token, generate_code, hash_password, mask_phone, verify_password
from app.models.user import SmsCode, User
from app.schemas.user import (
    AuthOut,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PhoneBindConfirmRequest,
    PhoneBindRequest,
    RegisterRequest,
    SmsCodeOut,
    UserOut,
)

logger = logging.getLogger("fittrack.api.auth")

router = APIRouter(prefix="/auth", tags=["认证"])

# ---------------------------------------------------------------- 常量
MIN_PASSWORD_LENGTH = 6           # 密码最小长度
SMS_CODE_TTL_MINUTES = 10         # 验证码有效期（分钟）
RESET_SCENE = "reset_password"    # 验证码用途：重置密码
BIND_SCENE = "bind_phone"         # 验证码用途：绑定手机号
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")   # 中国大陆手机号


# ==================================================================== 内部工具
def _check_password_strength(password: str) -> None:
    """校验密码强度，不足 6 位时抛出 400。

    参数：
        password: 明文密码。
    返回：
        无返回值；校验通过则静默返回。
    """
    if password is None or len(password) < MIN_PASSWORD_LENGTH:
        raise BadRequestError(f"密码至少需要 {MIN_PASSWORD_LENGTH} 位")
    if len(password) > 64:
        raise BadRequestError("密码长度不能超过 64 位")


def _validate_phone(phone: str) -> None:
    """校验手机号格式（11 位大陆号码），不合法时抛出 400。

    参数：
        phone: 待校验手机号。
    返回：
        无返回值；校验通过则静默返回。
    """
    if not PHONE_PATTERN.match(phone or ""):
        raise BadRequestError("手机号格式不正确")


def _issue_token(user: User) -> AuthOut:
    """为指定用户签发访问令牌并组装返回结构。

    参数：
        user: 已通过校验的用户 ORM 对象。
    返回：
        AuthOut：包含 token / access_token / token_type / expires_in / user。
    """
    token = create_access_token(user.id, "user")
    return AuthOut(
        token=token,
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


def _find_by_account(db: DbSession, account: str) -> User | None:
    """按用户名或手机号查找用户。

    参数：
        db: 数据库会话。
        account: 用户名或手机号。
    返回：
        匹配到的 User，找不到返回 None。
    """
    stmt = select(User).where((User.username == account) | (User.phone == account))
    return db.scalars(stmt).first()


def _create_sms_code(db: DbSession, target: str, scene: str) -> SmsCode:
    """作废旧验证码并生成一条新的 6 位验证码。

    参数：
        db: 数据库会话（调用方负责 commit）。
        target: 接收方（手机号或邮箱）。
        scene: 用途标识，reset_password / bind_phone。
    返回：
        新建的 SmsCode 对象（已 add 到会话，尚未 commit）。
    """
    # 同一接收方同一用途的旧验证码立即失效，避免旧码仍可用
    for old in db.scalars(
        select(SmsCode).where(SmsCode.target == target, SmsCode.scene == scene, SmsCode.used.is_(False))
    ).all():
        old.used = True

    sms = SmsCode(
        target=target,
        code=generate_code(6),
        scene=scene,
        expires_at=datetime.now() + timedelta(minutes=SMS_CODE_TTL_MINUTES),
        used=False,
    )
    db.add(sms)
    db.flush()
    logger.info("生成验证码：target=%s scene=%s code=%s", target, scene, sms.code)
    return sms


def _consume_sms_code(db: DbSession, target: str, scene: str, code: str) -> SmsCode:
    """校验并消费验证码（标记为已使用）。

    参数：
        db: 数据库会话（调用方负责 commit）。
        target: 接收方（手机号或邮箱）。
        scene: 用途标识。
        code: 用户提交的验证码。
    返回：
        校验通过的 SmsCode 对象（used 已置为 True）。
    异常：
        BadRequestError：未获取验证码 / 已过期 / 已使用 / 验证码不正确。
    """
    sms = db.scalars(
        select(SmsCode)
        .where(SmsCode.target == target, SmsCode.scene == scene, SmsCode.used.is_(False))
        .order_by(SmsCode.id.desc())
        .limit(1)
    ).first()
    if sms is None:
        raise BadRequestError("验证码不存在或已被使用，请重新获取")
    if sms.expires_at <= datetime.now():
        raise BadRequestError("验证码已过期，请重新获取")
    if not code or code.strip() != sms.code:
        raise BadRequestError("验证码不正确")
    sms.used = True
    return sms


# ==================================================================== 注册 / 登录
@router.post("/register", summary="注册新用户")
def register(payload: RegisterRequest, db: DbSession) -> dict:
    """注册新用户。

    参数：
        payload: RegisterRequest，包含用户名、密码与可选昵称/手机号/邮箱。
        db: 数据库会话。
    返回：
        ok(AuthOut)：注册成功后直接下发令牌与用户信息。
    异常：
        BadRequestError：密码强度不足、用户名过短。
        ConflictError：用户名或手机号已被占用。
    """
    _check_password_strength(payload.password)

    username = payload.username.strip()
    if len(username) < 3:
        raise BadRequestError("用户名至少需要 3 个字符")
    if db.scalars(select(User).where(User.username == username)).first() is not None:
        raise ConflictError("用户名已被占用，请换一个")

    phone = (payload.phone or "").strip() or None
    if phone is not None:
        _validate_phone(phone)
        if db.scalars(select(User).where(User.phone == phone)).first() is not None:
            raise ConflictError("该手机号已被注册")

    email = (payload.email or "").strip() or None
    if email is not None and db.scalars(select(User).where(User.email == email)).first() is not None:
        raise ConflictError("该邮箱已被注册")

    nickname = (payload.nickname or "").strip() or username
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        nickname=nickname,
        phone=phone,
        email=email,
        gender=0,
        points=0,
        level=1,
        is_verified=False,
        is_disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("新用户注册成功：%s(id=%s)", user.username, user.id)
    return ok(_issue_token(user), message="注册成功")


@router.post("/login", summary="登录（用户名或手机号 + 密码）")
def login(payload: LoginRequest, db: DbSession, request: Request) -> dict:
    """账号密码登录。

    参数：
        payload: LoginRequest，account 可以是用户名也可以是手机号。
        db: 数据库会话。
        request: 原始请求，用于记录登录 IP。
    返回：
        ok(AuthOut)：令牌 + 用户信息。
    异常：
        UnauthorizedError：账号不存在或密码错误。
        ForbiddenError：账号已被禁用。
    """
    account = payload.account.strip()
    if not account:
        raise BadRequestError("请输入用户名或手机号")

    user = _find_by_account(db, account)
    if user is None or not verify_password(payload.password, user.password_hash):
        # 两种情况返回同一句提示，避免暴露账号是否存在
        raise UnauthorizedError("账号或密码错误")
    if user.is_disabled:
        raise ForbiddenError("账号已被禁用，请联系客服")

    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)

    logger.info("用户登录成功：%s(id=%s) ip=%s", user.username, user.id, get_client_ip(request))
    return ok(_issue_token(user), message="登录成功")


@router.post("/logout", summary="退出登录")
def logout(user: OptionalUser, request: Request) -> dict:
    """退出登录（无状态 JWT：服务端只记日志，令牌由前端丢弃）。

    参数：
        user: 可选登录用户，携带令牌时会记录到日志。
        request: 原始请求，用于记录来源 IP。
    返回：
        ok({"logout": True})。
    """
    ip = get_client_ip(request)
    if user is not None:
        logger.info("用户退出登录：%s(id=%s) ip=%s", user.username, user.id, ip)
    else:
        logger.info("匿名退出登录请求 ip=%s", ip)
    return ok({"logout": True}, message="已退出登录")


@router.get("/me", summary="当前登录用户信息")
def read_me(current_user: CurrentUser) -> dict:
    """获取当前登录用户信息。

    参数：
        current_user: 由 CurrentUser 依赖注入的当前用户。
    返回：
        ok(UserOut)：当前用户的基础资料。
    """
    return ok(UserOut.model_validate(current_user))


@router.post("/refresh", summary="刷新访问令牌")
def refresh_token(current_user: CurrentUser) -> dict:
    """用当前（未过期的）令牌换一个新令牌。

    参数：
        current_user: 由 CurrentUser 依赖注入的当前用户（旧令牌必须有效）。
    返回：
        ok(AuthOut)：新令牌 + 用户信息。
    """
    return ok(_issue_token(current_user), message="令牌已刷新")


# ==================================================================== 密码重置
@router.post("/password/reset/request", summary="请求重置密码（发送验证码）")
def request_password_reset(payload: PasswordResetRequest, db: DbSession) -> dict:
    """忘记密码第一步：按手机号或邮箱发送 6 位验证码。

    参数：
        payload: PasswordResetRequest，phone 与 email 至少填一个。
        db: 数据库会话。
    返回：
        ok(SmsCodeOut)：target / scene / code / expires_in。
        注意：返回 code 仅为演示环境方便测试；生产环境必须调用短信网关或邮件服务下发，
        并从响应中删除 code 字段。
    异常：
        BadRequestError：phone 与 email 都没填。
        NotFoundError：手机号/邮箱未注册。
    """
    phone = (payload.phone or "").strip() or None
    email = (payload.email or "").strip() or None
    if phone is None and email is None:
        raise BadRequestError("请提供手机号或邮箱")

    target: str | None = None
    user: User | None = None
    if phone is not None:
        _validate_phone(phone)
        user = db.scalars(select(User).where(User.phone == phone)).first()
        target = phone
    if user is None and email is not None:
        user = db.scalars(select(User).where(User.email == email)).first()
        target = email
    if user is None or target is None:
        raise NotFoundError("该手机号/邮箱尚未注册")
    if user.is_disabled:
        raise ForbiddenError("账号已被禁用，请联系客服")

    sms = _create_sms_code(db, target, RESET_SCENE)
    db.commit()

    # 生产环境：改为 sms_gateway.send(target, sms.code)，不要把验证码返回给前端
    logger.info("重置密码验证码已生成：user=%s target=%s", user.username, target)
    return ok(
        SmsCodeOut(
            target=mask_phone(target) if phone is not None else target,
            scene=RESET_SCENE,
            code=sms.code,
            expires_in=SMS_CODE_TTL_MINUTES * 60,
        ),
        message="验证码已发送",
    )


@router.post("/password/reset/confirm", summary="用验证码重置密码")
def confirm_password_reset(payload: PasswordResetConfirmRequest, db: DbSession) -> dict:
    """忘记密码第二步：校验验证码并设置新密码。

    参数：
        payload: PasswordResetConfirmRequest，含 code、new_password 与手机号/邮箱之一。
        db: 数据库会话。
    返回：
        ok({"reset": True})。
    异常：
        BadRequestError：验证码错误/过期/已使用，或新密码强度不足。
        NotFoundError：手机号/邮箱未注册。
    """
    _check_password_strength(payload.new_password)

    target = (payload.phone or "").strip() or (payload.email or "").strip()
    if not target:
        raise BadRequestError("请提供手机号或邮箱")

    user = db.scalars(select(User).where((User.phone == target) | (User.email == target))).first()
    if user is None:
        raise NotFoundError("该手机号/邮箱尚未注册")

    _consume_sms_code(db, target, RESET_SCENE, payload.code)

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    logger.info("用户重置密码成功：%s(id=%s)", user.username, user.id)
    return ok({"reset": True}, message="密码重置成功，请使用新密码登录")


# ==================================================================== 手机号绑定
@router.post("/phone/bind/request", summary="绑定手机号第一步：发送验证码")
def request_bind_phone(payload: PhoneBindRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """绑定手机号第一步：向目标手机号发送验证码（需登录）。

    参数：
        payload: PhoneBindRequest，phone 为待绑定手机号。
        current_user: 当前登录用户。
        db: 数据库会话。
    返回：
        ok(SmsCodeOut)：target（脱敏）/ scene / code / expires_in。
        注意：code 仅演示环境返回，生产环境应由短信网关下发。
    异常：
        BadRequestError：手机号格式不正确，或已是本人手机号。
        ConflictError：该手机号已被其他账号绑定。
    """
    phone = payload.phone.strip()
    _validate_phone(phone)

    if current_user.phone == phone:
        raise BadRequestError("该手机号已经是你的绑定手机号")
    others = db.scalars(select(User).where(User.phone == phone, User.id != current_user.id)).first()
    if others is not None:
        raise ConflictError("该手机号已被其他账号绑定")

    sms = _create_sms_code(db, phone, BIND_SCENE)
    db.commit()

    logger.info("绑定手机号验证码已生成：user=%s phone=%s", current_user.username, mask_phone(phone))
    return ok(
        SmsCodeOut(
            target=mask_phone(phone),
            scene=BIND_SCENE,
            code=sms.code,
            expires_in=SMS_CODE_TTL_MINUTES * 60,
        ),
        message="验证码已发送",
    )


@router.post("/phone/bind/confirm", summary="绑定手机号第二步：校验验证码并写入")
def confirm_bind_phone(payload: PhoneBindConfirmRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """绑定手机号第二步：校验验证码后把手机号写入用户资料（需登录）。

    参数：
        payload: PhoneBindConfirmRequest，phone + code。
        current_user: 当前登录用户。
        db: 数据库会话。
    返回：
        ok(UserOut)：绑定成功后的用户信息。
    异常：
        BadRequestError：手机号格式不正确或验证码校验失败。
        ConflictError：该手机号已被其他账号绑定。
    """
    phone = payload.phone.strip()
    _validate_phone(phone)

    others = db.scalars(select(User).where(User.phone == phone, User.id != current_user.id)).first()
    if others is not None:
        raise ConflictError("该手机号已被其他账号绑定")

    _consume_sms_code(db, phone, BIND_SCENE, payload.code)

    current_user.phone = phone
    db.commit()
    db.refresh(current_user)

    logger.info("用户绑定手机号成功：%s(id=%s) phone=%s", current_user.username, current_user.id, mask_phone(phone))
    return ok(UserOut.model_validate(current_user), message="手机号绑定成功")


# ==================================================================== 修改密码
@router.put("/password/change", summary="修改密码（需登录）")
def change_password(payload: PasswordChangeRequest, current_user: CurrentUser, db: DbSession) -> dict:
    """已登录用户修改密码，需要校验原密码。

    参数：
        payload: PasswordChangeRequest，old_password + new_password。
        current_user: 当前登录用户。
        db: 数据库会话。
    返回：
        ok({"changed": True})。
    异常：
        BadRequestError：原密码不正确、新密码强度不足或新旧密码相同。
    """
    if not verify_password(payload.old_password, current_user.password_hash):
        raise BadRequestError("原密码不正确")
    _check_password_strength(payload.new_password)
    if payload.old_password == payload.new_password:
        raise BadRequestError("新密码不能与原密码相同")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    logger.info("用户修改密码成功：%s(id=%s)", current_user.username, current_user.id)
    return ok({"changed": True}, message="密码修改成功")


__all__ = ["router"]
