"""运动记录模块（/records）：训练记录的增删改查 + 训练数据统计。

业务约定：
1. 所有接口都需要登录，数据按 user_id 隔离，只能查看/修改/删除自己的记录；
   别人的记录一律当作"无权操作"，用 ForbiddenError 挡住。
2. 明细（WorkoutSet）保存时会把动作名称快照写入 exercise_name，
   即使动作库里的动作被删除，历史记录依然能正常展示。
3. 路由顺序很重要：/statistics/* 这些固定路径必须注册在 /{record_id} 之前，
   否则 "statistics" 会被当成 record_id 去解析 int 而报错。
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ForbiddenError, NotFoundError, ok
from app.models.exercise import Exercise
from app.models.record import WorkoutRecord, WorkoutSet
from app.schemas.record import (
    WORKOUT_TYPE_NAMES,
    WORKOUT_TYPES,
    DailyWorkoutStatOut,
    MonthlyStatisticsOut,
    SummaryStatisticsOut,
    TrendPointOut,
    TrendStatisticsOut,
    WeeklyStatisticsOut,
    WeeklyStatItemOut,
    WorkoutExerciseGroupOut,
    WorkoutRecordBriefOut,
    WorkoutRecordDetailOut,
    WorkoutRecordRequest,
    WorkoutRecordUpdateRequest,
    WorkoutSetOut,
    WorkoutSetRequest,
    WorkoutTypeStatOut,
)

router = APIRouter(prefix="/records", tags=["运动记录"])


# ================================================================ 通用小工具
def days_in_month(year: int, month: int) -> int:
    """返回指定年月的天数。

    参数:
        year: 年份，如 2025
        month: 月份 1-12
    返回:
        该月的天数（28-31）。用 date + timedelta 推算，不依赖 calendar 模块。
    """
    first_of_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return (first_of_next - timedelta(days=1)).day


def month_range(year: int, month: int) -> tuple[date, date]:
    """返回某个月的起止日期（闭区间）。

    参数:
        year: 年份
        month: 月份
    返回:
        (该月第一天, 该月最后一天)
    """
    start = date(year, month, 1)
    return start, start + timedelta(days=days_in_month(year, month) - 1)


def iso_week_start(day: date) -> date:
    """返回某天所在 ISO 周（周一为第一天）的周一日期。

    参数:
        day: 任意日期
    返回:
        该 ISO 周的周一
    """
    return day - timedelta(days=day.isoweekday() - 1)


def calc_streak_days(db: Session, user_id: int, today: date | None = None) -> int:
    """计算连续训练天数。

    参数:
        db: 数据库会话
        user_id: 用户ID
        today: 基准日期，默认今天
    返回:
        连续训练天数。今天还没练时从昨天开始往前数（当天没练不算断签），
        所以"昨天练了、今天还没练"时仍然返回从昨天起算的连续天数。
    """
    today = today or date.today()
    rows = db.scalars(
        select(WorkoutRecord.workout_date)
        .where(WorkoutRecord.user_id == user_id, WorkoutRecord.workout_date <= today)
        .group_by(WorkoutRecord.workout_date)
    ).all()
    trained = set(rows)
    if not trained:
        return 0
    cursor = today if today in trained else today - timedelta(days=1)
    streak = 0
    while cursor in trained:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _check_workout_type(value: str | None, field: str = "workout_type") -> None:
    """校验运动类型是否合法，非法则抛 BadRequestError。

    参数:
        value: 待校验的类型值
        field: 出错时提示用的字段名
    返回:
        None（校验通过）
    """
    if value is not None and value not in WORKOUT_TYPES:
        raise BadRequestError(f"{field} 只能是：{'/'.join(WORKOUT_TYPES)}")


def _get_own_record(db: Session, record_id: int, user_id: int) -> WorkoutRecord:
    """按 ID 取当前用户的训练记录，不存在或无权限时抛异常。

    参数:
        db: 数据库会话
        record_id: 记录ID
        user_id: 当前用户ID
    返回:
        WorkoutRecord 对象
    """
    record = db.get(WorkoutRecord, record_id)
    if record is None:
        raise NotFoundError("运动记录不存在")
    if record.user_id != user_id:
        raise ForbiddenError("无权操作他人的运动记录")
    return record


def _resolve_exercise_names(db: Session, items: list[WorkoutSetRequest]) -> dict[int, str]:
    """批量查询请求里引用到的动作名称，用于写入快照。

    参数:
        db: 数据库会话
        items: 请求里的明细列表
    返回:
        {动作ID: 动作名称}。请求里引用但库里不存在的动作，会在调用处以 400 报错。
    """
    ids = {item.exercise_id for item in items if item.exercise_id}
    if not ids:
        return {}
    rows = db.execute(select(Exercise.id, Exercise.name).where(Exercise.id.in_(ids))).all()
    return {int(row[0]): row[1] for row in rows}


def _build_sets(db: Session, items: list[WorkoutSetRequest]) -> list[WorkoutSet]:
    """把请求里的明细列表转换成 ORM 对象（含动作名称快照与动作顺序）。

    参数:
        db: 数据库会话
        items: 请求里的明细列表
    返回:
        WorkoutSet 对象列表（尚未加入会话）
    """
    names = _resolve_exercise_names(db, items)
    missing = sorted({item.exercise_id for item in items if item.exercise_id and item.exercise_id not in names})
    if missing:
        raise BadRequestError(f"动作不存在：{missing}")

    result: list[WorkoutSet] = []
    order_map: dict[object, int] = {}  # 同一个动作的所有组共用一个 sort_order
    for item in items:
        key: object = item.exercise_id if item.exercise_id else (item.exercise_name or "custom")
        if key not in order_map:
            order_map[key] = len(order_map) + 1
        # 快照优先取动作库里的正式名称（防止前端传错），没有动作ID时用前端传的名字
        snapshot = names.get(item.exercise_id) if item.exercise_id else None
        result.append(
            WorkoutSet(
                exercise_id=item.exercise_id,
                exercise_name=snapshot or (item.exercise_name or "自定义动作"),
                sort_order=order_map[key],
                set_index=item.set_index,
                weight=item.weight,
                reps=item.reps,
                duration_sec=item.duration_sec,
                distance_km=item.distance_km,
                note=item.note,
            )
        )
    return result


def _group_sets(sets: list[WorkoutSetOut]) -> list[WorkoutExerciseGroupOut]:
    """把明细按动作分组，供详情页展示。

    参数:
        sets: 已按动作顺序排好序的明细出参
    返回:
        分组列表，每组带组数、总次数、总容量（重量×次数）
    """
    groups: dict[tuple[int | None, str | None], WorkoutExerciseGroupOut] = {}
    for row in sets:
        key = (row.exercise_id, row.exercise_name)
        group = groups.get(key)
        if group is None:
            group = WorkoutExerciseGroupOut(
                exercise_id=row.exercise_id, exercise_name=row.exercise_name
            )
            groups[key] = group
        group.sets.append(row)
        group.set_count += 1
        group.total_reps += row.reps or 0
        group.total_volume_kg = round(group.total_volume_kg + (row.weight or 0) * (row.reps or 0), 1)
    return list(groups.values())


def _base_fields(record: WorkoutRecord) -> dict:
    """把记录对象转成出参公共字段字典（列表、创建、详情复用）。

    参数:
        record: WorkoutRecord 对象
    返回:
        可直接用于构造各层出参的字典
    """
    return {
        "id": record.id,
        "workout_date": record.workout_date,
        "workout_type": record.workout_type,
        "workout_type_text": WORKOUT_TYPE_NAMES.get(record.workout_type, record.workout_type),
        "title": record.title,
        "duration_min": record.duration_min or 0,
        "calories": round(float(record.calories or 0), 1),
        "feeling": record.feeling or 3,
        "note": record.note,
        "plan_id": record.plan_id,
        "course_id": record.course_id,
        "created_at": record.created_at,
    }


def _to_detail(record: WorkoutRecord) -> WorkoutRecordDetailOut:
    """把记录对象转成详情出参（含明细与按动作分组）。

    参数:
        record: WorkoutRecord 对象（sets 需已加载）
    返回:
        WorkoutRecordDetailOut
    """
    ordered = sorted(record.sets, key=lambda s: (s.sort_order or 0, s.set_index or 0, s.id or 0))
    sets = [WorkoutSetOut.model_validate(s) for s in ordered]
    exercise_count = len({(s.exercise_id, s.exercise_name) for s in sets})
    return WorkoutRecordDetailOut(
        **_base_fields(record),
        sets=sets,
        groups=_group_sets(sets),
        exercise_count=exercise_count,
        set_count=len(sets),
    )


# ================================================================ 记录：增
@router.post("", summary="创建一条训练记录")
@router.post("/", include_in_schema=False)
def create_record(payload: WorkoutRecordRequest, db: DbSession, user: CurrentUser) -> dict:
    """创建一条训练记录（可同时带动作明细）。

    参数:
        payload: 训练记录入参，workout_date 不传则取今天；sets 里每项为一组明细
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为记录详情（含明细与按动作分组）
    """
    _check_workout_type(payload.workout_type)
    record = WorkoutRecord(
        user_id=user.id,
        plan_id=payload.plan_id,
        course_id=payload.course_id,
        workout_date=payload.workout_date or date.today(),
        workout_type=payload.workout_type,
        title=payload.title,
        duration_min=payload.duration_min,
        calories=payload.calories,
        feeling=payload.feeling,
        note=payload.note,
    )
    # 明细一次性挂到关系上，由 cascade 统一保存（exercise_name 已写入快照）
    record.sets = _build_sets(db, payload.sets)
    db.add(record)
    db.commit()
    return ok(_to_detail(record))


# ================================================================ 记录：列表
@router.get("", summary="我的运动记录（分页）")
@router.get("/", include_in_schema=False)
def list_records(
    db: DbSession,
    user: CurrentUser,
    params: PageParams = Depends(page_params),
    start_date: date | None = Query(None, description="开始日期（含）"),
    end_date: date | None = Query(None, description="结束日期（含）"),
    workout_type: str | None = Query(None, description="按运动类型筛选"),
) -> dict:
    """分页查询我的运动记录，按训练日期倒序。

    参数:
        params: 分页参数（page / page_size）
        start_date: 开始日期（含），可空
        end_date: 结束日期（含），可空
        workout_type: 运动类型筛选，可空
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为分页结构，列表项带动作数量（exercise_count）与总组数
    """
    _check_workout_type(workout_type)
    if start_date and end_date and start_date > end_date:
        raise BadRequestError("开始日期不能晚于结束日期")

    stmt = select(WorkoutRecord).where(WorkoutRecord.user_id == user.id)
    if start_date:
        stmt = stmt.where(WorkoutRecord.workout_date >= start_date)
    if end_date:
        stmt = stmt.where(WorkoutRecord.workout_date <= end_date)
    if workout_type:
        stmt = stmt.where(WorkoutRecord.workout_type == workout_type)
    stmt = stmt.order_by(WorkoutRecord.workout_date.desc(), WorkoutRecord.id.desc())

    records, total = paginate(db, stmt, params)

    # 单独一次聚合查出本页记录的"动作数量 / 组数"，避免逐条查询（N+1）
    counts: dict[int, tuple[int, int]] = {}
    record_ids = [r.id for r in records]
    if record_ids:
        rows = db.execute(
            select(
                WorkoutSet.record_id,
                func.count(func.distinct(WorkoutSet.exercise_name)),
                func.count(WorkoutSet.id),
            )
            .where(WorkoutSet.record_id.in_(record_ids))
            .group_by(WorkoutSet.record_id)
        ).all()
        counts = {int(row[0]): (int(row[1] or 0), int(row[2] or 0)) for row in rows}

    items = []
    for record in records:
        exercise_count, set_count = counts.get(record.id, (0, 0))
        items.append(WorkoutRecordBriefOut(
            **_base_fields(record), exercise_count=exercise_count, set_count=set_count
        ))
    return ok(PageResult[WorkoutRecordBriefOut].build(items, total, params))


# ================================================================ 统计（必须写在 /{record_id} 之前）
@router.get("/statistics/monthly", summary="按月统计训练数据")
def statistics_monthly(
    db: DbSession,
    user: CurrentUser,
    year: int | None = Query(None, ge=2000, le=2100, description="年份，默认今年"),
    month: int | None = Query(None, ge=1, le=12, description="月份，默认本月"),
) -> dict:
    """按月统计训练数据：次数、时长、消耗、按类型分组、按天分布。

    参数:
        year: 年份，默认今年
        month: 月份 1-12，默认本月
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为月度统计（按天数组长度 = 当月天数，无记录补 0）
    """
    today = date.today()
    year = year or today.year
    month = month or today.month
    start, end = month_range(year, month)
    days = days_in_month(year, month)
    where = (WorkoutRecord.user_id == user.id, WorkoutRecord.workout_date.between(start, end))

    # 总量用一条 SQL 聚合（count / sum），避免把整月记录拉回内存
    total_count, total_duration, total_calories = db.execute(
        select(
            func.count(WorkoutRecord.id),
            func.coalesce(func.sum(WorkoutRecord.duration_min), 0),
            func.coalesce(func.sum(WorkoutRecord.calories), 0.0),
        ).where(*where)
    ).one()

    # 按运动类型分组
    type_rows = db.execute(
        select(
            WorkoutRecord.workout_type,
            func.count(WorkoutRecord.id),
            func.coalesce(func.sum(WorkoutRecord.duration_min), 0),
            func.coalesce(func.sum(WorkoutRecord.calories), 0.0),
        )
        .where(*where)
        .group_by(WorkoutRecord.workout_type)
        .order_by(func.count(WorkoutRecord.id).desc())
    ).all()

    # 按天分组，再把没训练的日子补 0
    day_rows = db.execute(
        select(
            WorkoutRecord.workout_date,
            func.count(WorkoutRecord.id),
            func.coalesce(func.sum(WorkoutRecord.duration_min), 0),
            func.coalesce(func.sum(WorkoutRecord.calories), 0.0),
        )
        .where(*where)
        .group_by(WorkoutRecord.workout_date)
    ).all()
    day_map = {row[0]: (int(row[1] or 0), int(row[2] or 0), round(float(row[3] or 0), 1)) for row in day_rows}

    daily = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        count, duration, calories = day_map.get(day, (0, 0, 0.0))
        daily.append(DailyWorkoutStatOut(date=day, count=count, duration_min=duration, calories=calories))

    total_count = int(total_count or 0)
    data = MonthlyStatisticsOut(
        year=year,
        month=month,
        days_in_month=days,
        total_count=total_count,
        total_duration_min=int(total_duration or 0),
        total_calories=round(float(total_calories or 0), 1),
        avg_duration_min=round(float(total_duration or 0) / total_count, 1) if total_count else 0.0,
        workout_types=[
            WorkoutTypeStatOut(
                workout_type=row[0],
                workout_type_text=WORKOUT_TYPE_NAMES.get(row[0], row[0]),
                count=int(row[1] or 0),
                duration_min=int(row[2] or 0),
                calories=round(float(row[3] or 0), 1),
            )
            for row in type_rows
        ],
        daily=daily,
    )
    return ok(data)


@router.get("/statistics/weekly", summary="按周统计训练数据")
def statistics_weekly(
    db: DbSession,
    user: CurrentUser,
    weeks: int = Query(4, ge=1, le=52, description="统计最近几周（含本周）"),
) -> dict:
    """按 ISO 周统计最近 N 周的训练次数 / 时长 / 消耗。

    参数:
        weeks: 统计周数，默认 4，含本周
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为按周列表（从早到晚，无记录的周补 0）
    """
    today = date.today()
    this_monday = iso_week_start(today)
    first_monday = this_monday - timedelta(weeks=weeks - 1)

    # 周粒度跨库日期函数差异较大（SQLite/MySQL 不一致），这里一次性取出窗口内的记录，
    # 再用 isocalendar() 在 Python 里按 ISO 周聚合，周数最多 52，数据量可控。
    rows = db.execute(
        select(WorkoutRecord.workout_date, WorkoutRecord.duration_min, WorkoutRecord.calories).where(
            WorkoutRecord.user_id == user.id,
            WorkoutRecord.workout_date >= first_monday,
            WorkoutRecord.workout_date <= today,
        )
    ).all()

    buckets: dict[date, list] = {}
    for row_date, duration, calories in rows:
        monday = iso_week_start(row_date)
        bucket = buckets.setdefault(monday, [0, 0, 0.0, set()])
        bucket[0] += 1
        bucket[1] += int(duration or 0)
        bucket[2] += float(calories or 0)
        bucket[3].add(row_date)

    items = []
    for offset in range(weeks):
        monday = first_monday + timedelta(weeks=offset)
        bucket = buckets.get(monday, [0, 0, 0.0, set()])
        iso = monday.isocalendar()
        items.append(WeeklyStatItemOut(
            week_label=f"{iso.year}-W{iso.week:02d}",
            year=iso.year,
            week=iso.week,
            start_date=monday,
            end_date=monday + timedelta(days=6),
            count=bucket[0],
            duration_min=bucket[1],
            calories=round(bucket[2], 1),
            workout_days=len(bucket[3]),
        ))
    return ok(WeeklyStatisticsOut(weeks=weeks, items=items))


@router.get("/statistics/summary", summary="训练数据总览")
def statistics_summary(db: DbSession, user: CurrentUser) -> dict:
    """训练数据总览：累计次数/时长/消耗、连续训练天数、本月与本周次数。

    参数:
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为总览数据
    """
    today = date.today()
    month_start, month_end = month_range(today.year, today.month)
    week_start = iso_week_start(today)
    week_end = week_start + timedelta(days=6)

    # 用 case 把"累计 / 本月 / 本周"三类计数压进同一条 SQL
    row = db.execute(
        select(
            func.count(WorkoutRecord.id),
            func.coalesce(func.sum(WorkoutRecord.duration_min), 0),
            func.coalesce(func.sum(WorkoutRecord.calories), 0.0),
            func.coalesce(func.sum(case((WorkoutRecord.workout_date.between(month_start, month_end), 1), else_=0)), 0),
            func.coalesce(func.sum(case((WorkoutRecord.workout_date.between(week_start, week_end), 1), else_=0)), 0),
            func.max(WorkoutRecord.workout_date),
        ).where(WorkoutRecord.user_id == user.id)
    ).one()

    data = SummaryStatisticsOut(
        total_count=int(row[0] or 0),
        total_duration_min=int(row[1] or 0),
        total_calories=round(float(row[2] or 0), 1),
        streak_days=calc_streak_days(db, user.id, today),
        month_count=int(row[3] or 0),
        week_count=int(row[4] or 0),
        last_workout_date=row[5],
    )
    return ok(data)


@router.get("/statistics/trend", summary="最近 N 天每日训练趋势")
def statistics_trend(
    db: DbSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="统计最近几天（含今天）"),
) -> dict:
    """每日训练趋势：返回 date / duration / calories 数组，无记录的日期补 0。

    参数:
        days: 统计天数，默认 30
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为按日期升序的趋势点数组
    """
    today = date.today()
    start = today - timedelta(days=days - 1)
    rows = db.execute(
        select(
            WorkoutRecord.workout_date,
            func.count(WorkoutRecord.id),
            func.coalesce(func.sum(WorkoutRecord.duration_min), 0),
            func.coalesce(func.sum(WorkoutRecord.calories), 0.0),
        )
        .where(
            WorkoutRecord.user_id == user.id,
            WorkoutRecord.workout_date.between(start, today),
        )
        .group_by(WorkoutRecord.workout_date)
    ).all()
    day_map = {row[0]: (int(row[1] or 0), int(row[2] or 0), round(float(row[3] or 0), 1)) for row in rows}

    points = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        count, duration, calories = day_map.get(day, (0, 0, 0.0))
        points.append(TrendPointOut(date=day, count=count, duration_min=duration, calories=calories))
    return ok(TrendStatisticsOut(days=days, start_date=start, end_date=today, points=points))


# ================================================================ 记录：详情 / 修改 / 删除
@router.get("/{record_id}", summary="训练记录详情")
def get_record(record_id: int, db: DbSession, user: CurrentUser) -> dict:
    """查询一条训练记录详情，含全部明细并按动作分组。

    参数:
        record_id: 记录ID
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为记录详情（sets 为原始明细，groups 为按动作分组）
    """
    record = _get_own_record(db, record_id, user.id)
    return ok(_to_detail(record))


@router.put("/{record_id}", summary="修改训练记录")
def update_record(record_id: int, payload: WorkoutRecordUpdateRequest, db: DbSession, user: CurrentUser) -> dict:
    """修改训练记录，只更新传上来的字段；sets 传了就整体替换。

    参数:
        record_id: 记录ID
        payload: 修改入参（全部字段可选）
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为修改后的记录详情
    """
    record = _get_own_record(db, record_id, user.id)
    data = payload.model_dump(exclude_unset=True, exclude={"sets"})
    if "workout_type" in data:
        _check_workout_type(data["workout_type"])

    for field, value in data.items():
        # workout_date 传空时保持原值，避免把日期改成 NULL
        if field == "workout_date" and value is None:
            continue
        setattr(record, field, value)

    if payload.sets is not None:
        # 传了明细就整体替换：先清空旧明细（delete-orphan 会级联删除），再挂上新的
        new_sets = _build_sets(db, payload.sets)
        record.sets.clear()
        db.flush()
        record.sets.extend(new_sets)

    db.commit()
    return ok(_to_detail(record))


@router.delete("/{record_id}", summary="删除训练记录")
def delete_record(record_id: int, db: DbSession, user: CurrentUser) -> dict:
    """删除一条训练记录（明细随 cascade 一起删除）。

    参数:
        record_id: 记录ID
        db: 数据库会话
        user: 当前登录用户
    返回:
        统一响应，data 为 {"deleted": True, "id": 记录ID}
    """
    record = _get_own_record(db, record_id, user.id)
    db.delete(record)
    db.commit()
    return ok({"deleted": True, "id": record_id})
