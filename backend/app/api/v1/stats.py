"""数据统计模块（/stats）：身体数据、BMI、体重/体脂趋势、卡路里收支、训练频率、数据看板。

业务约定：
1. 所有接口都需要登录，数据按 user_id 隔离；
2. BMI 不落库，用"体重 + 身高"实时算；身高优先取用户资料里的 height；
3. 卡路里收支的"消耗"= 当天训练记录消耗 + 基础代谢估算（Mifflin-St Jeor 公式），
   体重/身高/年龄/性别任一缺失时用 1800 千卡兜底，并在返回里标注 estimated=true；
4. 日期工具（当月天数 / ISO 周一 / 连续训练天数）复用 records 模块的实现，避免重复代码。
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.v1.records import calc_streak_days, days_in_month, iso_week_start, month_range
from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ForbiddenError, NotFoundError, ok
from app.models.diet import DietRecord
from app.models.record import WorkoutRecord
from app.models.stats import BodyMetric
from app.models.user import CheckinRecord, User
from app.schemas.stats import (
    BmiOut,
    BmiRecordItemOut,
    BmiRecordsOut,
    BodyFatTrendOut,
    BodyFatTrendPointOut,
    BodyMetricOut,
    BodyMetricRequest,
    CaloriesBalanceDayOut,
    CaloriesBalanceMonthOut,
    CaloriesBalanceOut,
    DashboardOut,
    FrequencyOut,
    FrequencyWeekItemOut,
    WeightTrendOut,
    WeightTrendPointOut,
)

router = APIRouter(prefix="/stats", tags=["数据统计"])

# 兜底基础代谢（千卡）：体重/身高/年龄/性别缺数据时使用
FALLBACK_BMR = 1800.0

# 身体数据里可用于"是否空记录"判断的字段
METRIC_FIELDS: tuple[str, ...] = ("weight", "body_fat", "muscle_mass", "waist", "chest", "hip")


# ================================================================ 计算小工具
def _calc_bmi(weight_kg: float, height_cm: float) -> float:
    """按 BMI = 体重(kg) / 身高(m)² 计算 BMI。

    参数:
        weight_kg: 体重（千克）
        height_cm: 身高（厘米）
    返回:
        BMI 值，保留 1 位小数
    """
    height_m = height_cm / 100
    return round(weight_kg / (height_m * height_m), 1)


def _bmi_level(bmi: float) -> tuple[str, str]:
    """按中国成人 BMI 标准给出分级与建议文案。

    参数:
        bmi: BMI 值
    返回:
        (分级, 建议)。分级：偏瘦<18.5 / 正常18.5-23.9 / 偏胖24-27.9 / 肥胖>=28
    """
    if bmi < 18.5:
        return "偏瘦", "体重偏轻，建议增加优质蛋白与碳水摄入，配合力量训练循序渐进地增肌。"
    if bmi < 24:
        return "正常", "体重在健康区间，保持规律训练与均衡饮食就好。"
    if bmi < 28:
        return "偏胖", "体重略高，建议每周 3-5 次有氧配合力量训练，并控制精制碳水与油脂摄入。"
    return "肥胖", "体重偏高，建议先以低冲击有氧（快走/游泳）减重，必要时咨询专业营养师。"


def _latest_weight(db: Session, user_id: int) -> float | None:
    """取用户最近一次记录的体重。

    参数:
        db: 数据库会话
        user_id: 用户ID
    返回:
        最新体重kg，没有记录时返回 None
    """
    value = db.scalar(
        select(BodyMetric.weight)
        .where(BodyMetric.user_id == user_id, BodyMetric.weight.is_not(None))
        .order_by(BodyMetric.metric_date.desc(), BodyMetric.id.desc())
        .limit(1)
    )
    return float(value) if value else None


def _basal_metabolism(db: Session, user: User) -> tuple[float, bool, str]:
    """用 Mifflin-St Jeor 公式估算基础代谢。

    公式：
        男性 BMR = 10×体重 + 6.25×身高 - 5×年龄 + 5
        女性 BMR = 10×体重 + 6.25×身高 - 5×年龄 - 161
    参数:
        db: 数据库会话
        user: 当前用户（提供身高/生日/性别）
    返回:
        (基础代谢千卡, 是否兜底估算, 估算说明)。体重/身高/年龄/性别缺任意一项时
        直接返回 FALLBACK_BMR 并标记为估算。
    """
    today = date.today()
    weight = _latest_weight(db, user.id)
    height = float(user.height) if user.height else None
    age: int | None = None
    if user.birthday:
        age = today.year - user.birthday.year - ((today.month, today.day) < (user.birthday.month, user.birthday.day))
        if age <= 0:
            age = None

    missing: list[str] = []
    if not weight:
        missing.append("体重")
    if not height:
        missing.append("身高")
    if not age:
        missing.append("年龄")
    if user.gender not in (1, 2):
        missing.append("性别")
    if missing:
        return FALLBACK_BMR, True, f"缺少{'/'.join(missing)}数据，基础代谢按 {int(FALLBACK_BMR)} 千卡兜底估算"

    base = 10 * weight + 6.25 * height - 5 * age
    bmr = base + 5 if user.gender == 1 else base - 161
    return round(bmr, 1), False, (
        f"按 Mifflin-St Jeor 公式估算（体重 {round(weight, 1)}kg / 身高 {round(height, 1)}cm / 年龄 {age}岁）"
    )


def _balance_advice(balance: float) -> tuple[str, str, str]:
    """根据当日热量收支差值给出状态与建议。

    参数:
        balance: 摄入 - 总消耗（正数为盈余）
    返回:
        (状态码, 状态中文, 建议文案)
    """
    if balance > 500:
        return "surplus", "热量盈余", "今天摄入明显高于消耗，注意控制加餐与含糖饮料，明天可以补一次有氧。"
    if balance > 0:
        return "surplus", "轻微盈余", "今天略有盈余，属于正常波动，保持规律训练即可。"
    if balance >= -300:
        return "balanced", "收支均衡", "摄入与消耗接近平衡，继续保持这份节奏。"
    return "deficit", "热量赤字", "今天热量缺口较大，减脂期可以接受，但别长期过低，注意补足蛋白质避免掉肌肉。"


def _get_own_metric(db: Session, metric_id: int, user_id: int) -> BodyMetric:
    """按 ID 取当前用户的身体数据，不存在或无权限时抛异常。

    参数:
        db: 数据库会话
        metric_id: 身体数据ID
        user_id: 当前用户ID
    返回:
        BodyMetric 对象
    """
    metric = db.get(BodyMetric, metric_id)
    if metric is None:
        raise NotFoundError("身体数据不存在")
    if metric.user_id != user_id:
        raise ForbiddenError("无权操作他人的身体数据")
    return metric


# ================================================================ 身体数据
@router.post("/body", summary="记录身体数据")
def create_body_metric(payload: BodyMetricRequest, db: DbSession, user: CurrentUser) -> dict:
    """记录一条身体数据（同一用户同一天只保留一条，已存在则更新）。

    参数:
        payload: 身体数据入参，metric_date 不传默认今天
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为保存后的身体数据
    """
    metric_date = payload.metric_date or date.today()
    data = payload.model_dump(exclude_unset=True, exclude={"metric_date"})

    existing = db.scalars(
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id, BodyMetric.metric_date == metric_date)
        .order_by(BodyMetric.id.desc())
    ).first()

    if existing is None:
        # 新建时至少要有一种身体数据，避免存进一条空记录
        if not any(getattr(payload, field) is not None for field in METRIC_FIELDS):
            raise BadRequestError("请至少填写一项身体数据（体重/体脂/肌肉量/围度）")
        metric = BodyMetric(user_id=user.id, metric_date=metric_date, **data)
        db.add(metric)
        db.commit()
        return ok(BodyMetricOut.model_validate(metric))

    # 已存在则只覆盖传上来的字段（没传的保持原值）
    if not data:
        raise BadRequestError("没有需要更新的字段")
    for field, value in data.items():
        setattr(existing, field, value)
    db.commit()
    return ok(BodyMetricOut.model_validate(existing), message="当天记录已更新")


@router.get("/body", summary="身体数据（分页）")
def list_body_metrics(db: DbSession, user: CurrentUser, params: PageParams = Depends(page_params)) -> dict:
    """分页查询我的身体数据，按记录日期倒序。

    参数:
        params: 分页参数（page / page_size）
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为分页结构
    """
    stmt = (
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id)
        .order_by(BodyMetric.metric_date.desc(), BodyMetric.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    items = [BodyMetricOut.model_validate(row) for row in rows]
    return ok(PageResult[BodyMetricOut].build(items, total, params))


@router.get("/body/latest", summary="最新一条身体数据")
def latest_body_metric(db: DbSession, user: CurrentUser) -> dict:
    """查询我最新的一条身体数据。

    参数:
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为最新身体数据；没有任何记录时 data 为 null
    """
    metric = db.scalars(
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id)
        .order_by(BodyMetric.metric_date.desc(), BodyMetric.id.desc())
        .limit(1)
    ).first()
    return ok(BodyMetricOut.model_validate(metric) if metric is not None else None)


@router.delete("/body/{metric_id}", summary="删除一条身体数据")
def delete_body_metric(metric_id: int, db: DbSession, user: CurrentUser) -> dict:
    """删除我的一条身体数据。

    参数:
        metric_id: 身体数据ID
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 {"deleted": True, "id": 身体数据ID}
    """
    metric = _get_own_metric(db, metric_id, user.id)
    db.delete(metric)
    db.commit()
    return ok({"deleted": True, "id": metric_id})


# ================================================================ BMI
@router.get("/bmi", summary="计算 BMI")
def calc_bmi(
    db: DbSession,
    user: CurrentUser,
    weight: float = Query(..., gt=0, le=500, description="体重kg"),
    height: float | None = Query(None, gt=0, le=300, description="身高cm，不传则用个人资料里的身高"),
) -> dict:
    """计算 BMI，返回数值、分级、建议与距离目标体重的差值。

    参数:
        weight: 体重（千克）
        height: 身高（厘米），不传则取用户资料里的 height
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 BMI 结果（bmi / level / advice / diff_to_target 等）
    """
    height_cm = float(height) if height else (float(user.height) if user.height else None)
    if not height_cm:
        raise BadRequestError("缺少身高数据，请先在个人资料里填写身高，或用 height 参数传入")

    bmi = _calc_bmi(weight, height_cm)
    level, advice = _bmi_level(bmi)
    height_m = height_cm / 100
    target_weight = float(user.target_weight) if user.target_weight else None
    data = BmiOut(
        weight=round(weight, 1),
        height=round(height_cm, 1),
        bmi=bmi,
        level=level,
        advice=advice,
        target_weight=round(target_weight, 1) if target_weight else None,
        # 正数表示还要减重多少，负数表示还能增重多少
        diff_to_target=round(weight - target_weight, 1) if target_weight else None,
        ideal_weight_min=round(18.5 * height_m * height_m, 1),
        ideal_weight_max=round(23.9 * height_m * height_m, 1),
    )
    return ok(data)


@router.get("/bmi/records", summary="我的 BMI 历史")
def bmi_records(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(365, ge=1, le=1825, description="最多返回多少条（按日期取最近 N 条）"),
) -> dict:
    """用身体数据里的体重 + 用户身高，计算我的 BMI 历史。

    参数:
        limit: 最多返回条数，默认最近 365 条
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 {height, count, items}，items 按日期升序
    """
    height = float(user.height) if user.height else None
    if not height:
        raise BadRequestError("缺少身高数据，请先在个人资料里填写身高后再查看 BMI 历史")

    # 先按日期倒序取最近 N 条，再翻转成升序返回，避免一次拉全量
    rows = db.scalars(
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id, BodyMetric.weight.is_not(None))
        .order_by(BodyMetric.metric_date.desc(), BodyMetric.id.desc())
        .limit(limit)
    ).all()
    items = [
        BmiRecordItemOut(
            date=row.metric_date,
            weight=round(float(row.weight), 1),
            bmi=_calc_bmi(float(row.weight), height),
        )
        for row in reversed(rows)
    ]
    return ok(BmiRecordsOut(height=round(height, 1), count=len(items), items=items))


# ================================================================ 趋势
@router.get("/trend/weight", summary="体重趋势")
def weight_trend(
    db: DbSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="统计最近几天（含今天）"),
) -> dict:
    """体重趋势：返回日期 + 体重，缺失日期不补点。

    参数:
        days: 统计天数，默认 30
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 {days, count, change, points}
    """
    start = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(BodyMetric.metric_date, BodyMetric.weight)
        .where(
            BodyMetric.user_id == user.id,
            BodyMetric.weight.is_not(None),
            BodyMetric.metric_date >= start,
        )
        .order_by(BodyMetric.metric_date.asc(), BodyMetric.id.asc())
    ).all()
    points = [WeightTrendPointOut(date=row[0], weight=round(float(row[1]), 1)) for row in rows]
    change = round(points[-1].weight - points[0].weight, 1) if len(points) >= 2 else 0.0
    return ok(WeightTrendOut(days=days, start_date=start, count=len(points), change=change, points=points))


@router.get("/trend/body-fat", summary="体脂趋势")
def body_fat_trend(
    db: DbSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="统计最近几天（含今天）"),
) -> dict:
    """体脂趋势：返回日期 + 体脂率，缺失日期不补点。

    参数:
        days: 统计天数，默认 30
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 {days, count, change, points}
    """
    start = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(BodyMetric.metric_date, BodyMetric.body_fat)
        .where(
            BodyMetric.user_id == user.id,
            BodyMetric.body_fat.is_not(None),
            BodyMetric.metric_date >= start,
        )
        .order_by(BodyMetric.metric_date.asc(), BodyMetric.id.asc())
    ).all()
    points = [BodyFatTrendPointOut(date=row[0], body_fat=round(float(row[1]), 1)) for row in rows]
    change = round(points[-1].body_fat - points[0].body_fat, 1) if len(points) >= 2 else 0.0
    return ok(BodyFatTrendOut(days=days, start_date=start, count=len(points), change=change, points=points))


# ================================================================ 卡路里收支
@router.get("/calories/balance", summary="当天卡路里收支")
def calories_balance(
    db: DbSession,
    user: CurrentUser,
    day: date | None = Query(None, alias="date", description="统计日期，默认今天"),
) -> dict:
    """当天卡路里收支：摄入（饮食记录合计） - 消耗（训练合计 + 基础代谢估算）。

    参数:
        day: 统计日期，默认今天（query 名称为 date）
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为摄入/消耗/差值/建议，estimated 表示基础代谢是否兜底估算
    """
    target = day or date.today()
    intake = float(db.scalar(
        select(func.coalesce(func.sum(DietRecord.calories), 0.0)).where(
            DietRecord.user_id == user.id, DietRecord.diet_date == target
        )
    ) or 0)
    workout_calories = float(db.scalar(
        select(func.coalesce(func.sum(WorkoutRecord.calories), 0.0)).where(
            WorkoutRecord.user_id == user.id, WorkoutRecord.workout_date == target
        )
    ) or 0)
    bmr, estimated, note = _basal_metabolism(db, user)

    total_burn = round(workout_calories + bmr, 1)
    balance = round(intake - total_burn, 1)
    status, status_text, advice = _balance_advice(balance)

    data = CaloriesBalanceOut(
        date=target,
        intake=round(intake, 1),
        workout_calories=round(workout_calories, 1),
        basal_metabolism=round(bmr, 1),
        total_burn=total_burn,
        balance=balance,
        status=status,
        status_text=status_text,
        advice=advice,
        estimated=estimated,
        estimate_note=note,
    )
    return ok(data)


@router.get("/calories/balance/month", summary="当月每天的卡路里收支")
def calories_balance_month(
    db: DbSession,
    user: CurrentUser,
    year: int | None = Query(None, ge=2000, le=2100, description="年份，默认今年"),
    month: int | None = Query(None, ge=1, le=12, description="月份，默认本月"),
) -> dict:
    """当月每天的卡路里收支数组（无记录的日期补 0）。

    参数:
        year: 年份，默认今年
        month: 月份 1-12，默认本月
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为月度收支（items 长度 = 当月天数）
    """
    today = date.today()
    year = year or today.year
    month = month or today.month
    start, end = month_range(year, month)
    days = days_in_month(year, month)

    # 摄入与消耗各用一条 "group by 日期" 的聚合 SQL 拿到，再在 Python 里按天补齐
    intake_rows = db.execute(
        select(DietRecord.diet_date, func.coalesce(func.sum(DietRecord.calories), 0.0))
        .where(DietRecord.user_id == user.id, DietRecord.diet_date.between(start, end))
        .group_by(DietRecord.diet_date)
    ).all()
    burn_rows = db.execute(
        select(WorkoutRecord.workout_date, func.coalesce(func.sum(WorkoutRecord.calories), 0.0))
        .where(WorkoutRecord.user_id == user.id, WorkoutRecord.workout_date.between(start, end))
        .group_by(WorkoutRecord.workout_date)
    ).all()
    intake_map = {row[0]: float(row[1] or 0) for row in intake_rows}
    burn_map = {row[0]: float(row[1] or 0) for row in burn_rows}

    # 基础代谢按"当前最新体重"估算，整月统一一个值（同一月内体重变化对结论影响很小）
    bmr, estimated, note = _basal_metabolism(db, user)

    items: list[CaloriesBalanceDayOut] = []
    total_intake = 0.0
    total_burn = 0.0
    for offset in range(days):
        day = start + timedelta(days=offset)
        intake = round(intake_map.get(day, 0.0), 1)
        workout_calories = round(burn_map.get(day, 0.0), 1)
        day_burn = round(workout_calories + bmr, 1)
        total_intake += intake
        total_burn += day_burn
        items.append(CaloriesBalanceDayOut(
            date=day,
            intake=intake,
            workout_calories=workout_calories,
            basal_metabolism=round(bmr, 1),
            total_burn=day_burn,
            balance=round(intake - day_burn, 1),
        ))

    data = CaloriesBalanceMonthOut(
        year=year,
        month=month,
        days_in_month=days,
        total_intake=round(total_intake, 1),
        total_burn=round(total_burn, 1),
        estimated=estimated,
        estimate_note=note,
        items=items,
    )
    return ok(data)


# ================================================================ 训练频率
@router.get("/frequency", summary="训练频率统计")
def workout_frequency(
    db: DbSession,
    user: CurrentUser,
    weeks: int = Query(8, ge=1, le=52, description="统计最近几周（含本周）"),
) -> dict:
    """训练频率统计：最近 N 个 ISO 周的训练天数、总次数、平均每次时长。

    参数:
        weeks: 统计周数，默认 8，含本周
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为按周列表（从早到晚）
    """
    today = date.today()
    first_monday = iso_week_start(today) - timedelta(weeks=weeks - 1)

    # 周粒度按 ISO 周聚合：跨库日期函数差异大，这里取回窗口内记录后在 Python 里聚合
    rows = db.execute(
        select(WorkoutRecord.workout_date, WorkoutRecord.duration_min).where(
            WorkoutRecord.user_id == user.id,
            WorkoutRecord.workout_date >= first_monday,
            WorkoutRecord.workout_date <= today,
        )
    ).all()

    buckets: dict[date, list] = {}
    for row_date, duration in rows:
        monday = iso_week_start(row_date)
        bucket = buckets.setdefault(monday, [0, 0, set()])
        bucket[0] += 1
        bucket[1] += int(duration or 0)
        bucket[2].add(row_date)

    items: list[FrequencyWeekItemOut] = []
    for offset in range(weeks):
        monday = first_monday + timedelta(weeks=offset)
        bucket = buckets.get(monday, [0, 0, set()])
        iso = monday.isocalendar()
        count, duration = bucket[0], bucket[1]
        items.append(FrequencyWeekItemOut(
            week_label=f"{iso.year}-W{iso.week:02d}",
            year=iso.year,
            week=iso.week,
            start_date=monday,
            end_date=monday + timedelta(days=6),
            workout_days=len(bucket[2]),
            total_count=count,
            total_duration_min=duration,
            avg_duration_min=round(duration / count, 1) if count else 0.0,
        ))
    return ok(FrequencyOut(weeks=weeks, items=items))


# ================================================================ 数据看板
@router.get("/dashboard", summary="个人数据看板")
def dashboard(db: DbSession, user: CurrentUser) -> dict:
    """个人数据看板：一次请求聚合首页需要的全部数据。

    参数:
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 包含：最新体重/体脂/BMI、本月训练次数/时长/消耗、
        连续训练天数、本周饮食摄入、今天是否已签到
    """
    today = date.today()
    month_start, month_end = month_range(today.year, today.month)
    week_start = iso_week_start(today)
    week_end = week_start + timedelta(days=6)

    # 1) 最新身体数据
    latest = db.scalars(
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id)
        .order_by(BodyMetric.metric_date.desc(), BodyMetric.id.desc())
        .limit(1)
    ).first()
    height = float(user.height) if user.height else None
    bmi: float | None = None
    bmi_level: str | None = None
    if latest is not None and latest.weight and height:
        bmi = _calc_bmi(float(latest.weight), height)
        bmi_level, _ = _bmi_level(bmi)

    # 2) 本月 / 本周训练数据：用 case 把三组汇总压进一条 SQL
    in_month = WorkoutRecord.workout_date.between(month_start, month_end)
    in_week = WorkoutRecord.workout_date.between(week_start, week_end)
    month_count, month_duration, month_calories, week_count = db.execute(
        select(
            func.coalesce(func.sum(case((in_month, 1), else_=0)), 0),
            func.coalesce(func.sum(case((in_month, WorkoutRecord.duration_min), else_=0)), 0),
            func.coalesce(func.sum(case((in_month, WorkoutRecord.calories), else_=0.0)), 0.0),
            func.coalesce(func.sum(case((in_week, 1), else_=0)), 0),
        ).where(WorkoutRecord.user_id == user.id)
    ).one()

    # 3) 连续训练天数
    streak_days = calc_streak_days(db, user.id, today)

    # 4) 饮食摄入：本周与今天
    week_diet = float(db.scalar(
        select(func.coalesce(func.sum(DietRecord.calories), 0.0)).where(
            DietRecord.user_id == user.id, DietRecord.diet_date.between(week_start, today)
        )
    ) or 0)
    today_diet = float(db.scalar(
        select(func.coalesce(func.sum(DietRecord.calories), 0.0)).where(
            DietRecord.user_id == user.id, DietRecord.diet_date == today
        )
    ) or 0)

    # 5) 今天是否已签到（查 CheckinRecord）
    checkin = db.scalars(
        select(CheckinRecord)
        .where(CheckinRecord.user_id == user.id, CheckinRecord.checkin_date == today)
        .limit(1)
    ).first()

    data = DashboardOut(
        nickname=user.nickname or user.username,
        level=user.level or 1,
        points=user.points or 0,
        height=round(height, 1) if height else None,
        target_weight=round(float(user.target_weight), 1) if user.target_weight else None,
        latest_metric_date=latest.metric_date if latest is not None else None,
        weight=round(float(latest.weight), 1) if latest is not None and latest.weight else None,
        body_fat=round(float(latest.body_fat), 1) if latest is not None and latest.body_fat else None,
        muscle_mass=round(float(latest.muscle_mass), 1) if latest is not None and latest.muscle_mass else None,
        bmi=bmi,
        bmi_level=bmi_level,
        month_workout_count=int(month_count or 0),
        month_workout_duration_min=int(month_duration or 0),
        month_workout_calories=round(float(month_calories or 0), 1),
        week_workout_count=int(week_count or 0),
        streak_days=streak_days,
        week_diet_calories=round(week_diet, 1),
        today_diet_calories=round(today_diet, 1),
        checked_in_today=checkin is not None,
        checkin_streak=checkin.streak if checkin is not None else 0,
    )
    return ok(data)
