"""运动计划模块接口（/api/plans）。

包含：计划的增删改查、动作明细维护、模板库、分享码、收藏、打卡、完成统计、今日任务、提醒设置。

接口约定（与全局规范一致）：
- 成功统一 ``return ok(data)``；
- 业务错误统一 ``raise BadRequestError / NotFoundError / ForbiddenError / ConflictError``；
- 分页统一使用 ``page_params`` 依赖 + ``PageParams`` + ``paginate()`` + ``PageResult.build()``；
- 数据库访问一律 SQLAlchemy 2.0 风格（``select()`` + ``db.scalars() / db.execute().scalars()``）。

注意：本文件中的静态路径（``/my``、``/templates``、``/favorites``、``/checkin/today``、``/share/...``）
必须声明在 ``/{plan_id}`` 之前，否则会被动态路径抢先匹配。
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ok
from app.core.security import generate_share_code
from app.models.exercise import Exercise
from app.models.plan import (
    Plan,
    PlanCheckin,
    PlanFavorite,
    PlanItem,
    PlanReminder,
    PlanShare,
    PlanTemplate,
)
from app.models.user import User
from app.schemas.plan import (
    CheckinCalendarDayOut,
    PlanBriefOut,
    PlanCheckinOut,
    PlanCheckinRequest,
    PlanCheckinResultOut,
    PlanDetailOut,
    PlanFavoriteOut,
    PlanFavoriteResultOut,
    PlanItemOut,
    PlanItemRequest,
    PlanItemUpdateRequest,
    PlanPublishRequest,
    PlanReminderOut,
    PlanReminderRequest,
    PlanShareOut,
    PlanStatsOut,
    PlanTemplateOut,
    PlanUpdateRequest,
    ShareCreateRequest,
    TemplateDayOut,
    TemplateItemOut,
    TodayPlanOut,
)

router = APIRouter(prefix="/plans", tags=["运动计划"])

# 计划打卡奖励积分（区别于每日签到积分，单独固定 5 分）
PLAN_CHECKIN_POINTS = 5
# 打卡日历天数
CALENDAR_DAYS = 30


# ======================================================================
# 内部工具函数
# ======================================================================
def _get_plan(db: Session, plan_id: int) -> Plan:
    """取出计划，不存在则抛 404。"""
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise NotFoundError("训练计划不存在")
    return plan


def _get_owned_plan(db: Session, plan_id: int, user: User) -> Plan:
    """取出计划并校验归属：只有本人可以改/删/打卡/设提醒。"""
    plan = _get_plan(db, plan_id)
    if plan.user_id != user.id:
        raise ForbiddenError("只能操作自己的训练计划")
    return plan


def _get_visible_plan(db: Session, plan_id: int, viewer: User | None) -> Plan:
    """取出计划并校验可见性：本人或公开计划可看，否则 403。"""
    plan = _get_plan(db, plan_id)
    if not plan.is_public and (viewer is None or plan.user_id != viewer.id):
        raise ForbiddenError("该计划未公开，无权查看")
    return plan


def _ensure_exercise(db: Session, exercise_id: int) -> None:
    """校验动作库里确实存在该动作，避免写入无效 exercise_id。"""
    if db.get(Exercise, exercise_id) is None:
        raise BadRequestError(f"动作 {exercise_id} 不存在")


def _items_count_map(db: Session, plan_ids: list[int]) -> dict[int, int]:
    """一次分组查询取出多个计划的动作条数，避免列表接口 N+1。"""
    if not plan_ids:
        return {}
    rows = db.execute(
        select(PlanItem.plan_id, func.count(PlanItem.id))
        .where(PlanItem.plan_id.in_(plan_ids))
        .group_by(PlanItem.plan_id)
    ).all()
    return {int(plan_id): int(count) for plan_id, count in rows}


def _plan_brief(plan: Plan, items_count: int = 0) -> PlanBriefOut:
    """ORM 计划对象 -> 简要出参。"""
    out = PlanBriefOut.model_validate(plan)
    out.items_count = items_count
    return out


def _is_plan_favorited(db: Session, user: User | None, plan_id: int) -> bool:
    """当前用户是否收藏了该计划。"""
    if user is None:
        return False
    count = db.scalar(
        select(func.count())
        .select_from(PlanFavorite)
        .where(PlanFavorite.user_id == user.id, PlanFavorite.plan_id == plan_id)
    )
    return bool(count)


def _plan_detail(db: Session, plan: Plan, viewer: User | None) -> PlanDetailOut:
    """ORM 计划对象 -> 详情出参（含动作明细、是否本人、是否已收藏）。"""
    out = PlanDetailOut.model_validate(plan)
    # 明细按「第几天 + 当天排序」排列，保证前端渲染顺序稳定
    out.items.sort(key=lambda i: (i.day_index, i.sort_order, i.id or 0))
    out.items_count = len(out.items)
    out.is_owner = viewer is not None and plan.user_id == viewer.id
    out.is_favorited = _is_plan_favorited(db, viewer, plan.id)
    return out


def _create_items(db: Session, plan: Plan, items: list[PlanItemRequest]) -> None:
    """批量写入动作明细，sort_order 按天自动编号。

    参数：
        db: 数据库会话（调用方负责 commit）
        plan: 已 flush 出主键的计划
        items: 动作明细列表
    """
    cycle_days = plan.cycle_days or 7
    counter: dict[int, int] = {}
    for data in sorted(items, key=lambda x: x.day_index):
        if data.day_index > cycle_days:
            raise BadRequestError(f"动作的 day_index({data.day_index}) 不能超过计划周期天数 {cycle_days}")
        if data.exercise_id is not None:
            _ensure_exercise(db, data.exercise_id)
        counter[data.day_index] = counter.get(data.day_index, 0) + 1
        db.add(PlanItem(plan_id=plan.id, sort_order=counter[data.day_index], **data.model_dump()))


def _copy_plan(db: Session, source: Plan, target_user: User, name: str | None = None) -> Plan:
    """把一份计划复制到目标用户名下（用于分享导入）。"""
    plan = Plan(
        user_id=target_user.id,
        name=(name or source.name)[:100],
        description=source.description,
        goal=source.goal,
        cycle_type=source.cycle_type,
        cycle_days=source.cycle_days,
        cover=source.cover,
        is_public=False,  # 导入的计划默认不公开
    )
    db.add(plan)
    db.flush()
    for item in source.items:
        db.add(PlanItem(
            plan_id=plan.id,
            exercise_id=item.exercise_id,
            day_index=item.day_index,
            sort_order=item.sort_order,
            sets=item.sets,
            reps=item.reps,
            weight=item.weight,
            rest_seconds=item.rest_seconds,
            duration_min=item.duration_min,
            note=item.note,
        ))
    return plan


def _parse_items_json(raw: str | None) -> list[TemplateDayOut]:
    """把模板的 items_json 解析成结构化的按天动作列表。

    模板动作只存动作名称，使用模板时再按名称匹配动作库。
    解析失败或格式异常时返回空列表，保证接口不报 500。
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []

    days: list[TemplateDayOut] = []
    for group in data:
        if not isinstance(group, dict):
            continue
        try:
            day_index = int(group.get("day_index") or 1)
        except (TypeError, ValueError):
            day_index = 1
        raw_items = group.get("items") or []
        items: list[TemplateItemOut] = []
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                items.append(TemplateItemOut(
                    exercise=str(raw_item.get("exercise") or ""),
                    sets=int(raw_item.get("sets") or 3),
                    reps=int(raw_item.get("reps") or 12),
                    weight=raw_item.get("weight"),
                    rest_seconds=int(raw_item.get("rest_seconds") or 60),
                    duration_min=raw_item.get("duration_min"),
                    note=raw_item.get("note"),
                ))
        days.append(TemplateDayOut(day_index=day_index, items=items))
    days.sort(key=lambda d: d.day_index)
    return days


def _template_out(template: PlanTemplate) -> PlanTemplateOut:
    """ORM 模板对象 -> 出参（附带解析后的结构化 items）。"""
    days = _parse_items_json(template.items_json)
    out = PlanTemplateOut.model_validate(template)
    out.items = days
    out.items_count = sum(len(day.items) for day in days)
    return out


def _today_day_index(plan: Plan, today: date) -> int:
    """根据周期类型与星期几推算「今天」对应周期内第几天。

    - daily：每天都执行第 1 天的动作；
    - weekly：周一为第 1 天、周日为第 7 天，超过周期天数时按周期取余。
    """
    cycle_days = plan.cycle_days or 7
    if plan.cycle_type == "daily":
        return 1
    return (today.isoweekday() - 1) % cycle_days + 1


def _award_points(user: User, points: int) -> None:
    """给用户加积分，并按配置的等级门槛刷新等级。"""
    user.points = (user.points or 0) + points
    level = 1
    for index, threshold in enumerate(settings.LEVEL_THRESHOLDS, start=1):
        if user.points >= threshold:
            level = index
    user.level = level


def _get_share_by_code(db: Session, share_code: str) -> tuple[PlanShare, Plan]:
    """按分享码取分享记录与计划，校验存在性与有效期。"""
    share = db.scalars(
        select(PlanShare).where(PlanShare.share_code == share_code.strip().upper())
    ).first()
    if share is None:
        raise NotFoundError("分享码不存在或已失效")
    if share.expires_at is not None and share.expires_at < datetime.now():
        raise BadRequestError("分享码已过期")
    plan = db.get(Plan, share.plan_id)
    if plan is None:
        raise NotFoundError("分享的计划已被删除")
    return share, plan


# ======================================================================
# 一、计划本体
# ======================================================================
@router.post("/publish", summary="创建训练计划")
def publish_plan(payload: PlanPublishRequest, db: DbSession, user: CurrentUser) -> dict:
    """创建一份训练计划（含动作明细）。

    参数：
        payload: 计划名称/说明/目标/周期类型/周期天数/封面/是否公开，以及 items 动作明细列表
        db: 数据库会话
        user: 当前登录用户
    返回：
        统一响应外壳，data 为计划详情（含 items 与每个动作的名称、配图）
    """
    plan = Plan(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        goal=payload.goal,
        cycle_type=payload.cycle_type,
        cycle_days=payload.cycle_days,
        cover=payload.cover,
        is_public=payload.is_public,
        status="active",
    )
    db.add(plan)
    db.flush()  # 拿到 plan.id 供明细使用
    _create_items(db, plan, payload.items)
    db.commit()
    db.refresh(plan)
    return ok(_plan_detail(db, plan, user), message="计划创建成功")


@router.get("/my", summary="我的计划列表")
def my_plans(
    db: DbSession,
    user: CurrentUser,
    params: PageParams = Depends(page_params),
    status: str | None = Query(default=None, description="状态筛选 active/archived"),
) -> dict:
    """分页查询我创建的计划。

    参数：
        params: 分页参数（page / page_size）
        status: 可选，按计划状态筛选
    返回：
        分页结果，items 为计划简要信息（含动作条数）
    """
    stmt = select(Plan).where(Plan.user_id == user.id)
    if status:
        if status not in ("active", "archived"):
            raise BadRequestError("status 只能是 active 或 archived")
        stmt = stmt.where(Plan.status == status)
    stmt = stmt.order_by(Plan.created_at.desc(), Plan.id.desc())

    rows, total = paginate(db, stmt, params)
    counts = _items_count_map(db, [plan.id for plan in rows])
    items = [_plan_brief(plan, counts.get(plan.id, 0)) for plan in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/templates", summary="计划模板库列表")
def list_templates(
    db: DbSession,
    user: OptionalUser,
    params: PageParams = Depends(page_params),
    category: str | None = Query(default=None, description="分类筛选，如 新手/减脂/增肌"),
    goal: str | None = Query(default=None, description="目标筛选，如 lose_fat/gain_muscle"),
    difficulty: int | None = Query(default=None, ge=1, le=5, description="难度筛选 1-5"),
) -> dict:
    """分页查询计划模板，并把 items_json 解析成结构化 items 返回。

    参数：
        params: 分页参数
        category/goal/difficulty: 可选筛选条件
    返回：
        分页结果，items 为模板出参（含按天分组的动作明细）
    """
    stmt = select(PlanTemplate)
    if category:
        stmt = stmt.where(PlanTemplate.category == category)
    if goal:
        stmt = stmt.where(PlanTemplate.goal == goal)
    if difficulty is not None:
        stmt = stmt.where(PlanTemplate.difficulty == difficulty)
    stmt = stmt.order_by(PlanTemplate.use_count.desc(), PlanTemplate.id.desc())

    rows, total = paginate(db, stmt, params)
    items = [_template_out(template) for template in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/templates/{tid}", summary="计划模板详情")
def template_detail(db: DbSession, user: OptionalUser, tid: int = Path(..., ge=1, description="模板ID")) -> dict:
    """查看单个模板的详细信息（含解析后的动作明细）。

    参数：
        tid: 模板ID
    返回：
        data 为模板详情
    """
    template = db.get(PlanTemplate, tid)
    if template is None:
        raise NotFoundError("计划模板不存在")
    return ok(_template_out(template))


@router.post("/templates/{tid}/use", summary="使用模板创建我的计划")
def use_template(
    db: DbSession,
    user: CurrentUser,
    tid: int = Path(..., ge=1, description="模板ID"),
    name: str | None = Query(default=None, max_length=100, description="自定义计划名称，默认用模板名"),
) -> dict:
    """按模板生成一份属于我的计划。

    模板动作只存名称，这里按名称匹配 exercises 表拿 exercise_id；
    匹配不到时 exercise_id 置空，但把动作名保留到 note 里，避免信息丢失。
    模板 use_count 会 +1。

    参数：
        tid: 模板ID
        name: 可选的自定义计划名称
    返回：
        data 为新创建的计划详情
    """
    template = db.get(PlanTemplate, tid)
    if template is None:
        raise NotFoundError("计划模板不存在")

    days = _parse_items_json(template.items_json)
    # 一次性查出所有模板动作对应的动作ID，避免逐条查询
    names = {item.exercise for day in days for item in day.items if item.exercise}
    exercise_map: dict[str, int] = {}
    if names:
        rows = db.scalars(
            select(Exercise).where(Exercise.name.in_(names), Exercise.is_active.is_(True))
        ).all()
        for exercise in rows:
            exercise_map.setdefault(exercise.name, exercise.id)

    plan = Plan(
        user_id=user.id,
        name=(name or template.name)[:100],
        description=template.description,
        goal=template.goal,
        cycle_type=template.cycle_type,
        cycle_days=template.cycle_days,
        cover=template.cover,
        is_public=False,
        status="active",
    )
    db.add(plan)
    db.flush()

    cycle_days = plan.cycle_days or 7
    counter: dict[int, int] = {}
    unmatched = 0
    for day in days:
        day_index = min(max(day.day_index, 1), cycle_days)  # 防止模板数据超出周期天数
        for item in day.items:
            exercise_id = exercise_map.get(item.exercise)
            note = item.note
            if exercise_id is None:
                # 动作库没有同名动作：保留名称到备注，exercise_id 留空
                unmatched += 1
                note = f"模板动作：{item.exercise}" if item.exercise else note
            counter[day_index] = counter.get(day_index, 0) + 1
            db.add(PlanItem(
                plan_id=plan.id,
                exercise_id=exercise_id,
                day_index=day_index,
                sort_order=counter[day_index],
                sets=item.sets,
                reps=item.reps,
                weight=item.weight,
                rest_seconds=item.rest_seconds,
                duration_min=item.duration_min,
                note=note,
            ))

    template.use_count = (template.use_count or 0) + 1
    db.commit()
    db.refresh(plan)
    return ok(
        _plan_detail(db, plan, user),
        message=f"已按模板创建计划，{unmatched} 个动作未匹配到动作库" if unmatched else "已按模板创建计划",
    )


@router.get("/favorites", summary="我收藏的计划")
def my_favorite_plans(db: DbSession, user: CurrentUser, params: PageParams = Depends(page_params)) -> dict:
    """分页查询我收藏的计划（按收藏时间倒序）。

    参数：
        params: 分页参数
    返回：
        分页结果，items 为计划简要信息 + 收藏时间
    """
    stmt = (
        select(PlanFavorite)
        .where(PlanFavorite.user_id == user.id)
        .order_by(PlanFavorite.created_at.desc(), PlanFavorite.id.desc())
    )
    rows, total = paginate(db, stmt, params)

    plan_ids = [fav.plan_id for fav in rows]
    plan_map: dict[int, Plan] = {}
    if plan_ids:
        plans = db.scalars(select(Plan).where(Plan.id.in_(plan_ids))).all()
        plan_map = {plan.id: plan for plan in plans}
    counts = _items_count_map(db, plan_ids)

    items: list[PlanFavoriteOut] = []
    for fav in rows:
        plan = plan_map.get(fav.plan_id)
        if plan is None:  # 计划已被原作者删除，跳过脏数据
            continue
        out = PlanFavoriteOut(**PlanBriefOut.model_validate(plan).model_dump())
        out.items_count = counts.get(plan.id, 0)
        out.favorited_at = fav.created_at
        items.append(out)
    return ok(PageResult.build(items, total, params))


@router.get("/checkin/today", summary="今天该做的动作")
def today_plan_items(db: DbSession, user: CurrentUser) -> dict:
    """列出我今天要做的动作。

    根据每个进行中计划的 cycle_type（daily/weekly）与今天星期几算出 day_index，
    取出当天的动作明细，并标记今天是否已打卡；当天没有动作的计划标记为休息日。

    参数：
        无（当前用户由令牌解析）
    返回：
        data 为计划列表，每项含 plan_id、day_index、is_rest_day、checked_in、items
    """
    today = date.today()
    plans = db.scalars(
        select(Plan).where(Plan.user_id == user.id, Plan.status == "active").order_by(Plan.id.desc())
    ).all()
    # 今天已打卡的计划ID集合
    checked_ids = set(db.scalars(
        select(PlanCheckin.plan_id).where(
            PlanCheckin.user_id == user.id, PlanCheckin.checkin_date == today
        )
    ).all())

    results: list[TodayPlanOut] = []
    for plan in plans:
        day_index = _today_day_index(plan, today)
        day_items = sorted(
            [item for item in plan.items if item.day_index == day_index],
            key=lambda i: (i.sort_order, i.id or 0),
        )
        results.append(TodayPlanOut(
            plan_id=plan.id,
            plan_name=plan.name,
            cycle_type=plan.cycle_type,
            cycle_days=plan.cycle_days,
            day_index=day_index,
            date=today,
            is_rest_day=not day_items,
            checked_in=plan.id in checked_ids,
            items=[PlanItemOut.model_validate(item) for item in day_items],
        ))
    return ok(results)


@router.get("/share/{share_code}", summary="通过分享码查看计划")
def view_shared_plan(db: DbSession, user: OptionalUser, share_code: str = Path(..., description="分享码")) -> dict:
    """通过分享码查看别人分享的计划（校验过期，view_count +1）。

    参数：
        share_code: 分享码
    返回：
        data 含 share（分享信息）与 plan（计划详情）
    """
    share, plan = _get_share_by_code(db, share_code)
    share.view_count = (share.view_count or 0) + 1
    db.commit()
    return ok({"share": PlanShareOut.model_validate(share), "plan": _plan_detail(db, plan, user)})


@router.post("/share/{share_code}/import", summary="导入分享码对应的计划")
def import_shared_plan(db: DbSession, user: CurrentUser, share_code: str = Path(..., description="分享码")) -> dict:
    """把别人分享的计划复制一份到自己账号下（默认不公开）。

    参数：
        share_code: 分享码
    返回：
        data 为复制出来的计划详情
    """
    _, source = _get_share_by_code(db, share_code)
    plan = _copy_plan(db, source, user, name=f"{source.name}（导入）")
    db.commit()
    db.refresh(plan)
    return ok(_plan_detail(db, plan, user), message="计划已导入到我的计划")


@router.get("/{plan_id}", summary="计划详情")
def plan_detail(
    db: DbSession,
    user: OptionalUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """查看计划详情（含动作明细和每个动作的名称/配图）。

    非本人且非公开的计划返回 403。

    参数：
        plan_id: 计划ID
    返回：
        data 为计划详情（含 items、is_owner、is_favorited）
    """
    plan = _get_visible_plan(db, plan_id, user)
    return ok(_plan_detail(db, plan, user))


@router.put("/{plan_id}", summary="编辑计划")
def update_plan(
    payload: PlanUpdateRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """编辑自己的计划（仅本人）。

    ``items`` 一旦传入就整体替换原有动作明细。

    参数：
        payload: 需要修改的字段（字段可选）
        plan_id: 计划ID
    返回：
        data 为更新后的计划详情
    """
    plan = _get_owned_plan(db, plan_id, user)
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("items", None)  # items 不走 setattr，单独整体替换
    replace_items = payload.items is not None

    for field, value in fields.items():
        if value is not None:
            setattr(plan, field, value)

    # 周期天数缩小时，确保已有明细不会越界
    if not replace_items:
        max_day = db.scalar(select(func.max(PlanItem.day_index)).where(PlanItem.plan_id == plan.id)) or 0
        if int(max_day) > (plan.cycle_days or 7):
            raise BadRequestError(f"计划中已有第 {int(max_day)} 天的动作，周期天数不能小于该值")

    if replace_items:
        plan.items.clear()  # delete-orphan 会删除旧明细
        db.flush()
        _create_items(db, plan, payload.items or [])

    db.commit()
    db.refresh(plan)
    return ok(_plan_detail(db, plan, user), message="计划已更新")


@router.delete("/{plan_id}", summary="删除计划")
def delete_plan(db: DbSession, user: CurrentUser, plan_id: int = Path(..., ge=1, description="计划ID")) -> dict:
    """删除自己的计划（仅本人），明细/打卡随 ORM 级联删除。

    参数：
        plan_id: 计划ID
    返回：
        data 为删除结果
    """
    plan = _get_owned_plan(db, plan_id, user)
    db.delete(plan)
    db.commit()
    return ok({"deleted": True, "plan_id": plan_id}, message="计划已删除")


# ======================================================================
# 二、计划动作明细
# ======================================================================
@router.post("/{plan_id}/item", summary="计划添加一个动作")
def add_plan_item(
    payload: PlanItemRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """给计划追加一条动作安排（仅本人）。

    参数：
        payload: day_index / exercise_id / 组数次数 / 休息 / 时长 / 备注
        plan_id: 计划ID
    返回：
        data 为新建的动作明细
    """
    plan = _get_owned_plan(db, plan_id, user)
    cycle_days = plan.cycle_days or 7
    if payload.day_index > cycle_days:
        raise BadRequestError(f"day_index 不能超过计划周期天数 {cycle_days}")
    if payload.exercise_id is not None:
        _ensure_exercise(db, payload.exercise_id)

    max_sort = db.scalar(
        select(func.max(PlanItem.sort_order)).where(
            PlanItem.plan_id == plan.id, PlanItem.day_index == payload.day_index
        )
    ) or 0
    item = PlanItem(plan_id=plan.id, sort_order=int(max_sort) + 1, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return ok(PlanItemOut.model_validate(item), message="动作已添加")


@router.put("/{plan_id}/item/{item_id}", summary="修改计划中的一个动作")
def update_plan_item(
    payload: PlanItemUpdateRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
    item_id: int = Path(..., ge=1, description="动作明细ID"),
) -> dict:
    """修改某条动作安排（仅本人，只更新传入的字段）。

    参数：
        payload: 需要修改的字段
        plan_id: 计划ID
        item_id: 动作明细ID
    返回：
        data 为修改后的动作明细
    """
    plan = _get_owned_plan(db, plan_id, user)
    item = db.get(PlanItem, item_id)
    if item is None or item.plan_id != plan.id:
        raise NotFoundError("动作明细不存在")

    fields = payload.model_dump(exclude_unset=True)
    day_index = fields.get("day_index")
    if day_index is not None and day_index > (plan.cycle_days or 7):
        raise BadRequestError(f"day_index 不能超过计划周期天数 {plan.cycle_days}")
    exercise_id = fields.get("exercise_id")
    if exercise_id is not None:
        _ensure_exercise(db, exercise_id)

    for field, value in fields.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return ok(PlanItemOut.model_validate(item), message="动作安排已更新")


@router.delete("/{plan_id}/item/{item_id}", summary="删除计划中的一个动作")
def delete_plan_item(
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
    item_id: int = Path(..., ge=1, description="动作明细ID"),
) -> dict:
    """删除某条动作安排（仅本人）。

    参数：
        plan_id: 计划ID
        item_id: 动作明细ID
    返回：
        data 为删除结果
    """
    plan = _get_owned_plan(db, plan_id, user)
    item = db.get(PlanItem, item_id)
    if item is None or item.plan_id != plan.id:
        raise NotFoundError("动作明细不存在")
    db.delete(item)
    db.commit()
    return ok({"deleted": True, "item_id": item_id}, message="动作安排已删除")


# ======================================================================
# 三、分享
# ======================================================================
@router.post("/{plan_id}/share", summary="生成计划分享码")
def create_plan_share(
    payload: ShareCreateRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """为自己的计划生成分享码（仅本人）。

    已有未过期的分享码则直接复用，避免每次点分享都产生新码；
    ``expires_hours`` 为空表示永久有效。

    参数：
        payload: expires_hours 有效小时数，空表示永久
        plan_id: 计划ID
    返回：
        data 为分享信息（share_code / expires_at / view_count）
    """
    plan = _get_owned_plan(db, plan_id, user)
    now = datetime.now()

    # 复用未过期的分享码
    share = db.scalars(
        select(PlanShare)
        .where(
            PlanShare.plan_id == plan.id,
            or_(PlanShare.expires_at.is_(None), PlanShare.expires_at > now),
        )
        .order_by(PlanShare.id.desc())
    ).first()

    if share is None:
        code = ""
        for _ in range(10):  # 极小概率碰撞，最多重试 10 次
            candidate = generate_share_code()
            exists = db.scalar(
                select(func.count()).select_from(PlanShare).where(PlanShare.share_code == candidate)
            )
            if not exists:
                code = candidate
                break
        if not code:
            raise ConflictError("分享码生成失败，请稍后重试")
        share = PlanShare(
            plan_id=plan.id,
            share_code=code,
            expires_at=now + timedelta(hours=payload.expires_hours) if payload.expires_hours else None,
        )
        db.add(share)
        db.commit()
        db.refresh(share)

    return ok(PlanShareOut.model_validate(share), message="分享码已生成")


# ======================================================================
# 四、收藏
# ======================================================================
@router.post("/{plan_id}/favorite", summary="收藏计划")
def favorite_plan(db: DbSession, user: CurrentUser, plan_id: int = Path(..., ge=1, description="计划ID")) -> dict:
    """收藏一个计划（重复收藏返回 409，计划被收藏数 +1）。

    参数：
        plan_id: 计划ID
    返回：
        data 为收藏结果与最新收藏数
    """
    plan = _get_plan(db, plan_id)
    if not plan.is_public and plan.user_id != user.id:
        raise ForbiddenError("该计划未公开，无法收藏")
    if _is_plan_favorited(db, user, plan.id):
        raise ConflictError("你已经收藏过该计划")

    db.add(PlanFavorite(user_id=user.id, plan_id=plan.id))
    plan.favorite_count = (plan.favorite_count or 0) + 1
    db.commit()
    return ok(
        PlanFavoriteResultOut(plan_id=plan.id, is_favorited=True, favorite_count=plan.favorite_count),
        message="收藏成功",
    )


@router.delete("/{plan_id}/favorite", summary="取消收藏计划")
def unfavorite_plan(db: DbSession, user: CurrentUser, plan_id: int = Path(..., ge=1, description="计划ID")) -> dict:
    """取消收藏（收藏数 -1，且不会小于 0）。

    参数：
        plan_id: 计划ID
    返回：
        data 为取消结果与最新收藏数
    """
    plan = _get_plan(db, plan_id)
    favorite = db.scalars(
        select(PlanFavorite).where(PlanFavorite.user_id == user.id, PlanFavorite.plan_id == plan.id)
    ).first()
    if favorite is None:
        raise NotFoundError("你还没有收藏该计划")

    db.delete(favorite)
    plan.favorite_count = max((plan.favorite_count or 0) - 1, 0)
    db.commit()
    return ok(
        PlanFavoriteResultOut(plan_id=plan.id, is_favorited=False, favorite_count=plan.favorite_count),
        message="已取消收藏",
    )


# ======================================================================
# 五、打卡与统计
# ======================================================================
@router.post("/{plan_id}/checkin", summary="计划打卡")
def checkin_plan(
    payload: PlanCheckinRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """完成今天的计划打卡（仅本人；同一天同一计划重复打卡返回 409）。

    打卡成功会给用户加 5 积分，并按等级门槛刷新等级。

    参数：
        payload: day_index 今天完成的周期第几天、note 备注
        plan_id: 计划ID
    返回：
        data 含打卡记录、本次积分与账号总积分
    """
    plan = _get_owned_plan(db, plan_id, user)
    today = date.today()
    if payload.day_index > (plan.cycle_days or 7):
        raise BadRequestError(f"day_index 不能超过计划周期天数 {plan.cycle_days}")

    exists = db.scalar(
        select(func.count())
        .select_from(PlanCheckin)
        .where(
            PlanCheckin.user_id == user.id,
            PlanCheckin.plan_id == plan.id,
            PlanCheckin.checkin_date == today,
        )
    )
    if exists:
        raise ConflictError("今天已经打过卡了，明天再来吧")

    checkin = PlanCheckin(
        user_id=user.id,
        plan_id=plan.id,
        checkin_date=today,
        day_index=payload.day_index,
        completed=True,
        note=payload.note,
    )
    db.add(checkin)
    _award_points(user, PLAN_CHECKIN_POINTS)  # 计划打卡固定 +5 积分
    db.commit()
    db.refresh(checkin)
    db.refresh(user)
    return ok(
        PlanCheckinResultOut(
            checkin=PlanCheckinOut.model_validate(checkin),
            points_awarded=PLAN_CHECKIN_POINTS,
            total_points=user.points,
        ),
        message=f"打卡成功，积分 +{PLAN_CHECKIN_POINTS}",
    )


@router.get("/{plan_id}/checkin/records", summary="计划的打卡记录")
def plan_checkin_records(
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
    params: PageParams = Depends(page_params),
) -> dict:
    """分页查询某个计划的打卡记录（本人或公开计划可看）。

    参数：
        plan_id: 计划ID
        params: 分页参数
    返回：
        分页结果，items 为打卡记录
    """
    plan = _get_visible_plan(db, plan_id, user)
    stmt = (
        select(PlanCheckin)
        .where(PlanCheckin.plan_id == plan.id, PlanCheckin.user_id == user.id)
        .order_by(PlanCheckin.checkin_date.desc(), PlanCheckin.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    items = [PlanCheckinOut.model_validate(row) for row in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/{plan_id}/stats", summary="计划完成统计")
def plan_stats(db: DbSession, user: CurrentUser, plan_id: int = Path(..., ge=1, description="计划ID")) -> dict:
    """统计该计划的完成情况。

    统计口径：
    - total_checkins：总打卡次数（含同一天重复记录的兜底统计）；
    - week_checkins：本周（周一起算）打卡次数；
    - streak_days：连续打卡天数（今天没打则从昨天往前数）；
    - checked_days：按日期去重的打卡天数；
    - expected_days：计划执行天数 = 已过天数按 cycle_days 折算出的周期数 × 每周期需打卡天数；
    - complete_rate = checked_days / expected_days（上限 1）；
    - calendar：最近 30 天打卡日历。

    参数：
        plan_id: 计划ID
    返回：
        data 为统计结果
    """
    plan = _get_visible_plan(db, plan_id, user)
    today = date.today()

    # 按日期分组的打卡信息（去重后的日期 + 当天对应周期第几天）
    rows = db.execute(
        select(PlanCheckin.checkin_date, func.min(PlanCheckin.day_index))
        .where(PlanCheckin.user_id == user.id, PlanCheckin.plan_id == plan.id)
        .group_by(PlanCheckin.checkin_date)
        .order_by(PlanCheckin.checkin_date.desc())
    ).all()
    day_index_map = {row[0]: int(row[1] or 1) for row in rows}
    checked_set = set(day_index_map.keys())

    total_checkins = db.scalar(
        select(func.count())
        .select_from(PlanCheckin)
        .where(PlanCheckin.user_id == user.id, PlanCheckin.plan_id == plan.id)
    ) or 0

    week_start = today - timedelta(days=today.weekday())
    week_checkins = db.scalar(
        select(func.count())
        .select_from(PlanCheckin)
        .where(
            PlanCheckin.user_id == user.id,
            PlanCheckin.plan_id == plan.id,
            PlanCheckin.checkin_date >= week_start,
        )
    ) or 0

    # 连续打卡天数：今天已打卡从今天算起，否则从昨天算起
    streak = 0
    cursor = today if today in checked_set else today - timedelta(days=1)
    while cursor in checked_set:
        streak += 1
        cursor -= timedelta(days=1)

    # 完成率：每个周期需要打卡的天数 = 明细里出现过的不重复 day_index 数量
    training_days = db.scalar(
        select(func.count(func.distinct(PlanItem.day_index))).where(PlanItem.plan_id == plan.id)
    ) or 0
    training_days = int(training_days) or 1
    cycle_days = plan.cycle_days or 7
    start_date = plan.created_at.date() if plan.created_at else today
    elapsed_days = max((today - start_date).days + 1, 1)
    cycles = max(math.ceil(elapsed_days / cycle_days), 1)
    expected_days = max(cycles * training_days, 1)
    checked_days = len(checked_set)
    complete_rate = round(min(checked_days / expected_days, 1.0), 4)

    # 最近 30 天打卡日历
    calendar = [
        CheckinCalendarDayOut(
            date=day,
            checked=day in checked_set,
            day_index=day_index_map.get(day),
        )
        for day in (today - timedelta(days=offset) for offset in range(CALENDAR_DAYS - 1, -1, -1))
    ]

    return ok(PlanStatsOut(
        plan_id=plan.id,
        plan_name=plan.name,
        cycle_type=plan.cycle_type,
        cycle_days=cycle_days,
        total_checkins=int(total_checkins),
        week_checkins=int(week_checkins),
        streak_days=streak,
        checked_days=checked_days,
        expected_days=expected_days,
        complete_rate=complete_rate,
        complete_percent=round(complete_rate * 100, 2),
        calendar=calendar,
    ))


# ======================================================================
# 六、提醒设置
# ======================================================================
@router.post("/{plan_id}/reminder", summary="设置计划提醒")
def create_plan_reminder(
    payload: PlanReminderRequest,
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
) -> dict:
    """为计划新增一条提醒（仅本人）。

    同一计划同一提醒时间去重：已存在则更新 weekdays / enabled，避免重复推送。

    参数：
        payload: remind_time("HH:MM") / weekdays("1,2,3") / enabled
        plan_id: 计划ID
    返回：
        data 为提醒设置
    """
    plan = _get_owned_plan(db, plan_id, user)
    remind_time = datetime.strptime(payload.remind_time, "%H:%M").time()

    reminder = db.scalars(
        select(PlanReminder).where(
            PlanReminder.user_id == user.id,
            PlanReminder.plan_id == plan.id,
            PlanReminder.remind_time == remind_time,
        )
    ).first()
    if reminder is None:
        reminder = PlanReminder(
            user_id=user.id,
            plan_id=plan.id,
            remind_time=remind_time,
            weekdays=payload.weekdays,
            enabled=payload.enabled,
        )
        db.add(reminder)
    else:
        reminder.weekdays = payload.weekdays
        reminder.enabled = payload.enabled
    db.commit()
    db.refresh(reminder)
    return ok(PlanReminderOut.from_model(reminder), message="提醒已保存")


@router.get("/{plan_id}/reminder", summary="查看计划提醒设置")
def list_plan_reminders(
    db: DbSession, user: CurrentUser, plan_id: int = Path(..., ge=1, description="计划ID")
) -> dict:
    """查看自己在该计划下设置的所有提醒。

    参数：
        plan_id: 计划ID
    返回：
        data 为提醒列表
    """
    plan = _get_owned_plan(db, plan_id, user)
    rows = db.scalars(
        select(PlanReminder)
        .where(PlanReminder.user_id == user.id, PlanReminder.plan_id == plan.id)
        .order_by(PlanReminder.remind_time)
    ).all()
    return ok([PlanReminderOut.from_model(row) for row in rows])


@router.delete("/{plan_id}/reminder/{rid}", summary="删除计划提醒")
def delete_plan_reminder(
    db: DbSession,
    user: CurrentUser,
    plan_id: int = Path(..., ge=1, description="计划ID"),
    rid: int = Path(..., ge=1, description="提醒ID"),
) -> dict:
    """删除自己的某条提醒。

    参数：
        plan_id: 计划ID
        rid: 提醒ID
    返回：
        data 为删除结果
    """
    plan = _get_owned_plan(db, plan_id, user)
    reminder = db.get(PlanReminder, rid)
    if reminder is None or reminder.plan_id != plan.id or reminder.user_id != user.id:
        raise NotFoundError("提醒设置不存在")
    db.delete(reminder)
    db.commit()
    return ok({"deleted": True, "reminder_id": rid}, message="提醒已删除")
