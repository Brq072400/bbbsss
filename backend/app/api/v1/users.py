# ---------------------------------------------------------------------------
# 本模块导出的路由变量名：router
#   router = APIRouter(prefix="/users", tags=["用户"])
# 汇总做法：from app.api.v1 import users  ->  api_router.include_router(users.router)
# 最终路径前缀：settings.API_PREFIX + /users，例如 /api/users/profile
# ---------------------------------------------------------------------------
"""用户中心路由：个人资料、头像上传、等级、签到日历、消息通知、实名认证。

约定：
- 全部接口都要求登录，统一使用 ``CurrentUser`` 依赖取当前用户；
- 统一返回 ``ok(data)``，业务错误抛 BadRequestError / ConflictError / NotFoundError；
- 时间统一 ``datetime.now()``（无时区），日期统一 ``date.today()``，与模型 DateTime/Date 对齐。
"""
from __future__ import annotations

import calendar
import logging
import re
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, NotFoundError, ok
from app.core.security import mask_id_card
from app.models.user import CheckinRecord, Notification, RealNameAuth, User
from app.schemas.user import (
    AvatarOut,
    CalendarDayOut,
    CheckinCalendarOut,
    CheckinOut,
    CheckinStatsOut,
    LevelOut,
    LevelRuleOut,
    LevelRulesOut,
    NotificationOut,
    ProfileOut,
    ProfileUpdateRequest,
    RealNameOut,
    RealNameRequest,
    UnreadCountOut,
    UserOut,
)

logger = logging.getLogger("fittrack.api.users")

router = APIRouter(prefix="/users", tags=["用户"])

# ---------------------------------------------------------------- 常量
LEVEL_TITLES: list[str] = [
    "新手", "入门", "初级", "进阶", "中级", "高级", "精英", "大师", "王者", "传奇", "巅峰",
]
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ID_CARD_PATTERN = re.compile(r"^(\d{15}|\d{17}[\dXx])$")
# MIME 与落盘后缀的映射（settings.allowed_image_types 是准入白名单）
IMAGE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
AVATAR_SUBDIR = "avatars"


# ==================================================================== 等级 / 签到 工具
def _thresholds() -> list[int]:
    """返回升序去重后的等级积分门槛列表（首位保证为 0）。

    参数：
        无。
    返回：
        list[int]，例如 [0, 100, 300, ...]。
    """
    values = sorted({int(points) for points in settings.LEVEL_THRESHOLDS})
    if not values:
        return [0]
    if values[0] != 0:
        values.insert(0, 0)
    return values


def _level_title(level: int) -> str:
    """取等级对应的称号。

    参数：
        level: 等级（从 1 开始）。
    返回：
        称号字符串，超出预置范围时返回 "Lv.{level}"。
    """
    if 1 <= level <= len(LEVEL_TITLES):
        return LEVEL_TITLES[level - 1]
    return f"Lv.{level}"


def calc_level(points: int) -> int:
    """按累计积分计算用户等级。

    参数：
        points: 累计积分。
    返回：
        int：等级，最低 1，最高 len(settings.LEVEL_THRESHOLDS)。
    """
    values = _thresholds()
    level = 1
    for index, threshold in enumerate(values):
        if points >= threshold:
            level = index + 1
    return min(level, len(values))


def _level_bounds(level: int) -> tuple[int, int | None]:
    """取某等级的积分区间左闭右开边界。

    参数：
        level: 等级（从 1 开始）。
    返回：
        (当前等级起点积分, 下一等级门槛)；已满级时第二项为 None。
    """
    values = _thresholds()
    index = min(max(level, 1), len(values)) - 1
    current_min = values[index]
    next_min = values[index + 1] if index + 1 < len(values) else None
    return current_min, next_min


def _points_to_next_level(points: int) -> int:
    """计算距离下一等级还差多少积分。

    参数：
        points: 累计积分。
    返回：
        int：差值；已满级返回 0。
    """
    _, next_min = _level_bounds(calc_level(points))
    if next_min is None:
        return 0
    return max(next_min - points, 0)


def _latest_checkin(db: Session, user_id: int) -> CheckinRecord | None:
    """取用户最近一条签到记录。

    参数：
        db: 数据库会话。
        user_id: 用户ID。
    返回：
        CheckinRecord 或 None。
    """
    stmt = (
        select(CheckinRecord)
        .where(CheckinRecord.user_id == user_id)
        .order_by(CheckinRecord.checkin_date.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _current_streak(db: Session, user_id: int) -> int:
    """当前连续签到天数（最后签到必须是今天或昨天，否则断签归零）。

    参数：
        db: 数据库会话。
        user_id: 用户ID。
    返回：
        int：连续签到天数，未签到或已断签为 0。
    """
    latest = _latest_checkin(db, user_id)
    if latest is None:
        return 0
    today = date.today()
    if latest.checkin_date in (today, today - timedelta(days=1)):
        return int(latest.streak)
    return 0


def _has_checkin(db: Session, user_id: int, day: date) -> bool:
    """判断用户某天是否已签到。

    参数：
        db: 数据库会话。
        user_id: 用户ID。
        day: 目标日期。
    返回：
        bool。
    """
    stmt = select(CheckinRecord.id).where(
        CheckinRecord.user_id == user_id, CheckinRecord.checkin_date == day
    )
    return db.scalars(stmt).first() is not None


def _count_checkins(db: Session, user_id: int, start: date | None = None, end: date | None = None) -> int:
    """统计用户签到天数，可按日期区间过滤。

    参数：
        db: 数据库会话。
        user_id: 用户ID。
        start: 起始日期（含），None 表示不限。
        end: 结束日期（含），None 表示不限。
    返回：
        int：签到天数。
    """
    stmt = select(func.count()).select_from(CheckinRecord).where(CheckinRecord.user_id == user_id)
    if start is not None:
        stmt = stmt.where(CheckinRecord.checkin_date >= start)
    if end is not None:
        stmt = stmt.where(CheckinRecord.checkin_date <= end)
    return int(db.scalar(stmt) or 0)


def _month_range(year: int, month: int) -> tuple[date, date]:
    """取某年某月的首尾日期。

    参数：
        year: 年份。
        month: 月份 1-12。
    返回：
        (当月 1 号, 当月最后一天)。
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _build_profile(db: Session, user: User) -> ProfileOut:
    """组装"我的资料"出参：基础信息 + 等级进度 + 签到统计。

    参数：
        db: 数据库会话。
        user: 当前用户。
    返回：
        ProfileOut。
    """
    base = UserOut.model_validate(user).model_dump()
    level = calc_level(user.points or 0)
    _, next_min = _level_bounds(level)
    today = date.today()
    first_day, last_day = _month_range(today.year, today.month)

    return ProfileOut(
        **base,
        next_level_points=next_min,
        points_to_next_level=_points_to_next_level(user.points or 0),
        max_level=len(_thresholds()),
        checkin_total=_count_checkins(db, user.id),
        checkin_streak=_current_streak(db, user.id),
        checkin_month=_count_checkins(db, user.id, first_day, last_day),
        today_checked=_has_checkin(db, user.id, today),
    )


# ==================================================================== 个人资料
@router.get("/profile", summary="我的资料")
def get_profile(db: DbSession, current_user: CurrentUser) -> dict:
    """获取当前登录用户的完整资料。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(ProfileOut)：基础资料 + 等级/积分/下一等级所需积分 + 签到统计。
    """
    return ok(_build_profile(db, current_user))


@router.put("/profile", summary="修改个人资料")
def update_profile(payload: ProfileUpdateRequest, db: DbSession, current_user: CurrentUser) -> dict:
    """修改当前登录用户的资料（只更新传入的字段）。

    参数：
        payload: ProfileUpdateRequest，昵称/性别/生日/身高/目标体重/签名/城市/邮箱。
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(ProfileOut)：修改后的完整资料。
    异常：
        BadRequestError：没有可修改字段、昵称为空、邮箱格式错误、生日晚于今天。
        ConflictError：邮箱已被其他账号使用。
    """
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise BadRequestError("没有需要修改的内容")

    # ---- 昵称：不允许改成空白 ----
    if "nickname" in data:
        nickname = (data["nickname"] or "").strip()
        if not nickname:
            raise BadRequestError("昵称不能为空")
        data["nickname"] = nickname

    # ---- 个性签名 / 城市：空白等同于清空 ----
    for text_field in ("signature", "city"):
        if text_field in data:
            value = (data[text_field] or "").strip()
            data[text_field] = value or None

    # ---- 生日：不能晚于今天 ----
    if "birthday" in data and data["birthday"] is not None:
        if data["birthday"] > date.today():
            raise BadRequestError("生日不能晚于今天")

    # ---- 邮箱：格式校验 + 唯一性校验，空串表示解绑邮箱 ----
    if "email" in data:
        raw_email = data["email"]
        email = str(raw_email).strip() if raw_email is not None else ""
        if not email:
            data["email"] = None
        else:
            if not EMAIL_PATTERN.match(email):
                raise BadRequestError("邮箱格式不正确")
            exists = db.scalars(select(User).where(User.email == email, User.id != current_user.id)).first()
            if exists is not None:
                raise ConflictError("该邮箱已被其他账号使用")
            data["email"] = email

    # ---- 落库 ----
    for field_name, field_value in data.items():
        setattr(current_user, field_name, field_value)
    db.commit()
    db.refresh(current_user)

    logger.info("用户修改资料：%s(id=%s) 字段=%s", current_user.username, current_user.id, list(data))
    return ok(_build_profile(db, current_user), message="资料已更新")


@router.post("/avatar", summary="上传头像")
async def upload_avatar(
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="头像图片，支持 jpg/png/webp/gif，最大 5MB"),
) -> dict:
    """上传头像并写回用户资料。

    参数：
        current_user: 当前登录用户。
        db: 数据库会话。
        file: UploadFile，MIME 必须是 settings.allowed_image_types 之一，
              大小不得超过 settings.MAX_UPLOAD_SIZE。
    返回：
        ok(AvatarOut)：可访问 URL（{UPLOAD_URL_PREFIX}/avatars/{filename}）、文件名、大小。
    异常：
        BadRequestError：MIME 不在白名单、文件为空、文件过大。
    """
    content_type = (file.content_type or "").lower()
    if content_type not in settings.allowed_image_types:
        allowed = "、".join(sorted(settings.allowed_image_types))
        raise BadRequestError(f"只支持以下图片格式：{allowed}")

    content = await file.read()
    if not content:
        raise BadRequestError("上传的图片内容为空")
    if len(content) > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise BadRequestError(f"图片大小不能超过 {max_mb:.0f}MB")

    extension = IMAGE_EXTENSIONS.get(content_type) or Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{extension}"

    avatar_dir = settings.UPLOAD_DIR / AVATAR_SUBDIR
    avatar_dir.mkdir(parents=True, exist_ok=True)
    (avatar_dir / filename).write_bytes(content)

    url = f"{settings.UPLOAD_URL_PREFIX}/{AVATAR_SUBDIR}/{filename}"
    current_user.avatar = url
    db.commit()
    db.refresh(current_user)

    logger.info("用户上传头像：%s(id=%s) -> %s", current_user.username, current_user.id, url)
    return ok(AvatarOut(url=url, avatar=url, filename=filename, size=len(content)), message="头像上传成功")


# ==================================================================== 等级
@router.get("/level", summary="我的等级信息")
def get_level(current_user: CurrentUser) -> dict:
    """查询当前用户的等级、积分与升级进度。

    参数：
        current_user: 当前登录用户。
    返回：
        ok(LevelOut)：等级、称号、积分、当前级起点、下一级门槛、还差多少分、进度百分比。
    """
    points = current_user.points or 0
    level = calc_level(points)
    current_min, next_min = _level_bounds(level)
    max_level = len(_thresholds())

    if next_min is None:
        to_next = 0
        progress = 100.0
    else:
        to_next = max(next_min - points, 0)
        span = max(next_min - current_min, 1)
        progress = round(min(max((points - current_min) / span, 0.0), 1.0) * 100, 2)

    return ok(
        LevelOut(
            level=level,
            title=_level_title(level),
            points=points,
            level_min_points=current_min,
            next_level_points=next_min,
            points_to_next_level=to_next,
            is_max_level=next_min is None,
            progress=progress,
            max_level=max_level,
        )
    )


@router.get("/level/rules", summary="等级规则说明")
def get_level_rules() -> dict:
    """返回完整的等级规则（所有等级区间 + 签到积分规则）。

    参数：
        无。
    返回：
        ok(LevelRulesOut)：max_level、签到积分参数、各等级区间列表。
    """
    values = _thresholds()
    rules: list[LevelRuleOut] = []
    for index, min_points in enumerate(values):
        level = index + 1
        max_points = values[index + 1] - 1 if index + 1 < len(values) else None
        if max_points is None:
            description = f"累计积分 {min_points} 分及以上"
        else:
            description = f"累计积分 {min_points} - {max_points} 分"
        rules.append(
            LevelRuleOut(
                level=level,
                title=_level_title(level),
                min_points=min_points,
                max_points=max_points,
                description=description,
            )
        )

    return ok(
        LevelRulesOut(
            max_level=len(values),
            checkin_points=settings.CHECKIN_POINTS,
            checkin_streak_bonus=settings.CHECKIN_STREAK_BONUS,
            checkin_streak_bonus_cap=settings.CHECKIN_STREAK_BONUS_CAP,
            rules=rules,
        )
    )


# ==================================================================== 签到
@router.post("/checkin", summary="每日签到")
def do_checkin(db: DbSession, current_user: CurrentUser) -> dict:
    """每日签到：当天只能签一次，按连续天数发放积分并刷新等级。

    积分规则：
        基础积分 = settings.CHECKIN_POINTS
        连续奖励 = min((streak - 1) * settings.CHECKIN_STREAK_BONUS, settings.CHECKIN_STREAK_BONUS_CAP)
        本次积分 = 基础积分 + 连续奖励

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(CheckinOut)：签到日期、连续天数、本次积分、累计总积分、等级。
    异常：
        ConflictError：今天已经签到过（409）。
    """
    today = date.today()
    if _has_checkin(db, current_user.id, today):
        raise ConflictError("今天已经签到过了，明天再来吧")

    yesterday = today - timedelta(days=1)
    previous = db.scalars(
        select(CheckinRecord).where(
            CheckinRecord.user_id == current_user.id, CheckinRecord.checkin_date == yesterday
        )
    ).first()
    streak = int(previous.streak) + 1 if previous is not None else 1

    bonus = min((streak - 1) * settings.CHECKIN_STREAK_BONUS, settings.CHECKIN_STREAK_BONUS_CAP)
    points_awarded = settings.CHECKIN_POINTS + bonus

    db.add(
        CheckinRecord(
            user_id=current_user.id,
            checkin_date=today,
            streak=streak,
            points_awarded=points_awarded,
        )
    )
    current_user.points = (current_user.points or 0) + points_awarded
    current_user.level = calc_level(current_user.points)
    db.commit()
    db.refresh(current_user)

    logger.info(
        "用户签到：%s(id=%s) 连续=%d 积分=+%d 总分=%d",
        current_user.username, current_user.id, streak, points_awarded, current_user.points,
    )
    return ok(
        CheckinOut(
            checkin_date=today,
            streak=streak,
            points_awarded=points_awarded,
            bonus=bonus,
            points=current_user.points,
            level=current_user.level,
        ),
        message=f"签到成功，已连续签到 {streak} 天",
    )


@router.get("/checkin/calendar", summary="签到日历")
def get_checkin_calendar(
    db: DbSession,
    current_user: CurrentUser,
    year: int | None = Query(default=None, ge=1970, le=2999, description="年份，默认当年"),
    month: int | None = Query(default=None, ge=1, le=12, description="月份，默认当月"),
) -> dict:
    """查询某个自然月的签到日历。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
        year: 年份，不传取当年。
        month: 月份，不传取当月。
    返回：
        ok(CheckinCalendarOut)：当月每一天的签到情况、当月连续天数序列、当月签到天数。
    异常：
        BadRequestError：月份非法。
    """
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month
    if not 1 <= target_month <= 12:
        raise BadRequestError("月份必须在 1-12 之间")

    first_day, last_day = _month_range(target_year, target_month)
    records = db.scalars(
        select(CheckinRecord).where(
            CheckinRecord.user_id == current_user.id,
            CheckinRecord.checkin_date >= first_day,
            CheckinRecord.checkin_date <= last_day,
        )
    ).all()
    by_date = {record.checkin_date: record for record in records}

    days: list[CalendarDayOut] = []
    for day_number in range(1, last_day.day + 1):
        current_day = date(target_year, target_month, day_number)
        record = by_date.get(current_day)
        days.append(
            CalendarDayOut(
                date=current_day,
                day=day_number,
                checked=record is not None,
                streak=record.streak if record is not None else 0,
                points_awarded=record.points_awarded if record is not None else 0,
                is_today=current_day == today,
            )
        )

    streak_list = [by_date[key].streak for key in sorted(by_date)]
    return ok(
        CheckinCalendarOut(
            year=target_year,
            month=target_month,
            days=days,
            streak_list=streak_list,
            checked_days=len(records),
            today_checked=today in by_date,
        )
    )


@router.get("/checkin/stats", summary="签到统计")
def get_checkin_stats(db: DbSession, current_user: CurrentUser) -> dict:
    """统计当前用户的签到情况。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(CheckinStatsOut)：当前连续天数、累计天数、本月天数、最近签到日期、今天是否已签到。
    """
    today = date.today()
    first_day, last_day = _month_range(today.year, today.month)
    latest = _latest_checkin(db, current_user.id)

    return ok(
        CheckinStatsOut(
            current_streak=_current_streak(db, current_user.id),
            total_days=_count_checkins(db, current_user.id),
            month_days=_count_checkins(db, current_user.id, first_day, last_day),
            last_checkin_date=latest.checkin_date if latest is not None else None,
            today_checked=_has_checkin(db, current_user.id, today),
        )
    )


# ==================================================================== 消息通知
@router.get("/notifications", summary="我的通知列表（分页）")
def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    params: Annotated[PageParams, Depends(page_params)],
    only_unread: bool = Query(default=False, description="是否只看未读"),
) -> dict:
    """分页查询当前用户的站内通知。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
        params: 分页参数（page / page_size），由 page_params 依赖注入。
        only_unread: 为 True 时只返回未读通知。
    返回：
        ok(PageResult[NotificationOut])：items / total / page / page_size / pages。
    """
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if only_unread:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())

    rows, total = paginate(db, stmt, params)
    result: PageResult[NotificationOut] = PageResult[NotificationOut].build(
        [NotificationOut.model_validate(row) for row in rows], total, params
    )
    return ok(result)


@router.get("/notifications/unread-count", summary="未读通知数量")
def get_unread_count(db: DbSession, current_user: CurrentUser) -> dict:
    """统计当前用户的未读通知数量。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(UnreadCountOut)：unread 未读条数。
    """
    total = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )
    return ok(UnreadCountOut(unread=int(total or 0)))


@router.post("/notifications/read-all", summary="全部通知标记已读")
def read_all_notifications(db: DbSession, current_user: CurrentUser) -> dict:
    """把当前用户的全部未读通知标记为已读。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok({"updated": 本次更新的条数})。
    """
    cursor = db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()

    updated = int(cursor.rowcount or 0)
    logger.info("用户全部已读：%s(id=%s) 更新=%d", current_user.username, current_user.id, updated)
    return ok({"updated": updated}, message="全部通知已标记为已读")


@router.post("/notifications/{nid}/read", summary="标记单条通知已读")
def read_notification(nid: int, db: DbSession, current_user: CurrentUser) -> dict:
    """把指定通知标记为已读。

    参数：
        nid: 通知ID。
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok({"id": nid, "is_read": True})。
    异常：
        NotFoundError：通知不存在或不属于当前用户（404）。
    """
    notification = db.scalars(
        select(Notification).where(Notification.id == nid, Notification.user_id == current_user.id)
    ).first()
    if notification is None:
        raise NotFoundError("通知不存在")

    if not notification.is_read:
        notification.is_read = True
        db.commit()
    return ok({"id": notification.id, "is_read": True}, message="已标记为已读")


@router.delete("/notifications/{nid}", summary="删除单条通知")
def delete_notification(nid: int, db: DbSession, current_user: CurrentUser) -> dict:
    """删除指定通知。

    参数：
        nid: 通知ID。
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok({"deleted": nid})。
    异常：
        NotFoundError：通知不存在或不属于当前用户（404）。
    """
    notification = db.scalars(
        select(Notification).where(Notification.id == nid, Notification.user_id == current_user.id)
    ).first()
    if notification is None:
        raise NotFoundError("通知不存在")

    db.delete(notification)
    db.commit()

    logger.info("用户删除通知：%s(id=%s) nid=%s", current_user.username, current_user.id, nid)
    return ok({"deleted": nid}, message="通知已删除")


# ==================================================================== 实名认证
def _validate_real_name_payload(payload: RealNameRequest) -> tuple[str, str]:
    """校验实名认证入参，返回 (真实姓名, 明文身份证号)。

    参数：
        payload: RealNameRequest。
    返回：
        (real_name, id_card) 清洗后的明文值。
    异常：
        BadRequestError：姓名为空或身份证格式不合法。
    """
    real_name = (payload.real_name or "").strip()
    id_card = (payload.id_card or "").strip().upper()
    if not real_name:
        raise BadRequestError("请填写真实姓名")
    if not ID_CARD_PATTERN.match(id_card):
        raise BadRequestError("身份证号格式不正确")
    return real_name, id_card


@router.post("/realname", summary="提交实名认证")
def submit_realname(payload: RealNameRequest, db: DbSession, current_user: CurrentUser) -> dict:
    """提交实名认证申请（身份证号脱敏后入库，状态置为 pending）。

    参数：
        payload: RealNameRequest，real_name + id_card。
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(RealNameOut)：认证状态与脱敏后的信息。
    异常：
        BadRequestError：姓名或身份证格式不合法。
        ConflictError：已通过认证或正在审核中（409）。
    """
    real_name, id_card = _validate_real_name_payload(payload)

    existing = db.scalars(select(RealNameAuth).where(RealNameAuth.user_id == current_user.id)).first()
    if existing is not None:
        if existing.status == "approved":
            raise ConflictError("实名认证已通过，无需重复提交")
        if existing.status == "pending":
            raise ConflictError("实名认证正在审核中，请耐心等待")
        # 被驳回的申请允许在本接口重新提交（效果同 /realname/resubmit）
        existing.real_name = real_name
        existing.id_card = mask_id_card(id_card)
        existing.status = "pending"
        existing.reject_reason = None
        existing.reviewed_at = None
        db.commit()
        db.refresh(existing)
        logger.info("用户重新提交实名认证：%s(id=%s)", current_user.username, current_user.id)
        return ok(RealNameOut.model_validate(existing), message="实名认证已重新提交，请等待审核")

    record = RealNameAuth(
        user_id=current_user.id,
        real_name=real_name,
        id_card=mask_id_card(id_card),
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info("用户提交实名认证：%s(id=%s)", current_user.username, current_user.id)
    return ok(RealNameOut.model_validate(record), message="实名认证已提交，请等待审核")


@router.get("/realname", summary="查询我的实名认证状态")
def get_realname(db: DbSession, current_user: CurrentUser) -> dict:
    """查询当前用户的实名认证状态。

    参数：
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(RealNameOut)：status 为 none 表示从未提交，其余为 pending/approved/rejected。
    """
    record = db.scalars(select(RealNameAuth).where(RealNameAuth.user_id == current_user.id)).first()
    if record is None:
        return ok(RealNameOut(status="none"), message="尚未提交实名认证")
    return ok(RealNameOut.model_validate(record))


@router.post("/realname/resubmit", summary="被驳回后重新提交实名认证")
def resubmit_realname(payload: RealNameRequest, db: DbSession, current_user: CurrentUser) -> dict:
    """实名认证被驳回后重新提交（仅 rejected 状态可调用）。

    参数：
        payload: RealNameRequest，real_name + id_card。
        db: 数据库会话。
        current_user: 当前登录用户。
    返回：
        ok(RealNameOut)：重置为 pending 的认证记录。
    异常：
        NotFoundError：从未提交过实名认证（404）。
        BadRequestError：当前状态不是 rejected（400）。
    """
    record = db.scalars(select(RealNameAuth).where(RealNameAuth.user_id == current_user.id)).first()
    if record is None:
        raise NotFoundError("还没有提交过实名认证，请先提交")
    if record.status != "rejected":
        raise BadRequestError("只有被驳回的实名认证才能重新提交")

    real_name, id_card = _validate_real_name_payload(payload)
    record.real_name = real_name
    record.id_card = mask_id_card(id_card)
    record.status = "pending"
    record.reject_reason = None
    record.reviewed_at = None
    db.commit()
    db.refresh(record)

    logger.info("用户重新提交实名认证：%s(id=%s)", current_user.username, current_user.id)
    return ok(RealNameOut.model_validate(record), message="实名认证已重新提交，请等待审核")


__all__ = ["router"]
