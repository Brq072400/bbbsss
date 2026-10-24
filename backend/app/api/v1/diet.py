"""饮食模块接口。

包含：食物库（分页/分类/详情/自定义新增/删除）、饮食记录（新增/查询/按天汇总/
修改/删除）、区间统计。

营养换算规则：食物库的营养数据都是「每 100 克」，所以
    本次摄入 = 食物营养 × (amount_g / 100)
换算结果直接落库（快照），这样即使食物库数据后续被修改，历史记录也不会变。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ok
from app.models.diet import DietRecord, Food
from app.schemas.diet import (
    MEAL_LABELS,
    MEAL_ORDER,
    DEFAULT_TARGET_CALORIES,
    DEFAULT_TARGET_CARBOHYDRATE,
    DEFAULT_TARGET_FAT,
    DEFAULT_TARGET_PROTEIN,
    DailyCaloriesOut,
    DaySummaryOut,
    DietRecordCreateRequest,
    DietRecordOut,
    DietRecordUpdateRequest,
    DietStatsOut,
    FoodCategoryOut,
    FoodCreateRequest,
    FoodOut,
    MealGroupOut,
    MealType,
    percent_of,
)

router = APIRouter(prefix="/diet", tags=["饮食"])


# ---------------------------------------------------------------- 内部工具
def _calc_nutrition(food: Food | None, amount_g: float) -> tuple[float, float, float, float]:
    """按食用量换算一条记录的热量与三大营养素。

    参数:
        food: 食物库对象；仅填了自定义 food_name 时为 None。
        amount_g: 食用量（克）。
    返回:
        (热量千卡, 蛋白质g, 脂肪g, 碳水g)，保留 2 位小数；食物为空时全部为 0。
    """
    if food is None:
        return 0.0, 0.0, 0.0, 0.0
    factor = float(amount_g) / 100.0
    return (
        round((food.calories or 0) * factor, 2),
        round((food.protein or 0) * factor, 2),
        round((food.fat or 0) * factor, 2),
        round((food.carbohydrate or 0) * factor, 2),
    )


def _get_own_record(db: Session, record_id: int, user_id: int) -> DietRecord:
    """取一条属于自己的饮食记录，不存在抛 404，非本人抛 403。

    参数:
        db: 数据库会话。
        record_id: 记录ID。
        user_id: 当前登录用户ID。
    返回:
        DietRecord ORM 对象。
    """
    record = db.get(DietRecord, record_id)
    if record is None:
        raise NotFoundError("饮食记录不存在")
    if record.user_id != user_id:
        raise ForbiddenError("只能操作自己的饮食记录")
    return record


# ---------------------------------------------------------------- 食物库
@router.get("/foods", summary="食物库分页")
def list_foods(
    db: DbSession,
    params: PageParams = Depends(page_params),
    category: str | None = Query(None, max_length=30, description="按分类筛选"),
    keyword: str | None = Query(None, max_length=50, description="按名称模糊搜索"),
) -> dict[str, Any]:
    """分页查询食物库，常用食物（is_common=True）排在前面。

    参数:
        params: 分页参数。
        category: 分类筛选，可选。
        keyword: 名称关键字，可选。
        db: 数据库会话。
    返回:
        统一响应，data 为 PageResult[FoodOut]。
    """
    stmt = select(Food)
    if category:
        stmt = stmt.where(Food.category == category)
    if keyword and keyword.strip():
        stmt = stmt.where(Food.name.like(f"%{keyword.strip()}%"))
    # is_common 优先（常用食物供前端快捷选择），再按分类与ID稳定排序
    stmt = stmt.order_by(Food.is_common.desc(), Food.category.asc(), Food.id.asc())
    rows, total = paginate(db, stmt, params)
    items = [FoodOut.model_validate(food) for food in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/foods/categories", summary="食物分类及数量")
def list_food_categories(db: DbSession) -> dict[str, Any]:
    """获取食物分类列表及每个分类下的食物数量。

    参数:
        db: 数据库会话。
    返回:
        统一响应，data 为 FoodCategoryOut 列表（按数量倒序）。
    """
    rows = db.execute(
        select(Food.category, func.count(Food.id)).group_by(Food.category).order_by(func.count(Food.id).desc())
    ).all()
    items = [FoodCategoryOut(category=category or "others", count=int(count)) for category, count in rows]
    return ok(items)


@router.get("/foods/{food_id}", summary="食物详情")
def get_food(food_id: int, db: DbSession) -> dict[str, Any]:
    """按ID查询食物详情（每 100 克营养数据）。

    参数:
        food_id: 食物ID。
        db: 数据库会话。
    返回:
        统一响应，data 为 FoodOut。
    """
    food = db.get(Food, food_id)
    if food is None:
        raise NotFoundError("食物不存在")
    return ok(FoodOut.model_validate(food))


@router.post("/foods", summary="新增自定义食物")
def create_food(req: FoodCreateRequest, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """新增一条自定义食物（is_common=False，created_by=当前用户）。

    参数:
        req: 食物名称与每 100 克营养数据。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 FoodOut；同一用户重复创建同名食物抛 409。
    """
    duplicated = db.scalar(select(Food.id).where(Food.name == req.name, Food.created_by == current.id))
    if duplicated is not None:
        raise ConflictError("你已经创建过同名食物")
    food = Food(**req.model_dump(), is_common=False, created_by=current.id)
    db.add(food)
    db.commit()
    db.refresh(food)
    return ok(FoodOut.model_validate(food))


@router.delete("/foods/{food_id}", summary="删除自己创建的食物")
def delete_food(food_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """删除自己创建的自定义食物（系统食物不可删除）。

    参数:
        food_id: 食物ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为删除结果。
    """
    food = db.get(Food, food_id)
    if food is None:
        raise NotFoundError("食物不存在")
    if food.created_by != current.id:
        raise ForbiddenError("只能删除自己创建的食物")
    db.delete(food)
    db.commit()
    return ok({"food_id": food_id, "deleted": True})


# ---------------------------------------------------------------- 饮食记录
@router.post("/records", summary="添加饮食记录")
def create_record(req: DietRecordCreateRequest, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """添加一条饮食记录，自动按 amount_g/100 换算热量与三大营养素并落库。

    参数:
        req: 日期（默认今天）、餐次、食物（food_id 或 food_name 二选一）、食用量、备注。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 DietRecordOut。
    """
    amount = float(req.amount_g)
    food: Food | None = None
    if req.food_id is not None:
        food = db.get(Food, req.food_id)
        if food is None:
            raise NotFoundError("食物不存在")
        food_name = food.name
    else:
        food_name = (req.food_name or "").strip()
        if not food_name:
            raise BadRequestError("food_id 与 food_name 必须二选一")

    calories, protein, fat, carbohydrate = _calc_nutrition(food, amount)
    record = DietRecord(
        user_id=current.id,
        diet_date=req.diet_date or date.today(),
        meal_type=req.meal_type,
        food_id=food.id if food is not None else None,
        food_name=food_name,
        amount_g=amount,
        calories=calories,
        protein=protein,
        fat=fat,
        carbohydrate=carbohydrate,
        note=req.note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ok(DietRecordOut.model_validate(record))


@router.get("/records", summary="我的饮食记录（分页）")
def list_records(
    db: DbSession,
    current: CurrentUser,
    params: PageParams = Depends(page_params),
    on_date: date | None = Query(None, alias="date", description="只看某一天"),
    start_date: date | None = Query(None, description="区间开始日期"),
    end_date: date | None = Query(None, description="区间结束日期"),
    meal_type: MealType | None = Query(None, description="按餐次筛选"),
) -> dict[str, Any]:
    """分页查询自己的饮食记录，支持按单日、日期区间、餐次筛选。

    参数:
        params: 分页参数。
        on_date: 指定某一天（优先级最高）。
        start_date / end_date: 日期区间。
        meal_type: 餐次筛选。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 PageResult[DietRecordOut]。
    """
    stmt = select(DietRecord).where(DietRecord.user_id == current.id)
    if on_date is not None:
        stmt = stmt.where(DietRecord.diet_date == on_date)
    else:
        if start_date is not None:
            stmt = stmt.where(DietRecord.diet_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DietRecord.diet_date <= end_date)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise BadRequestError("start_date 不能晚于 end_date")
    if meal_type:
        stmt = stmt.where(DietRecord.meal_type == meal_type)
    stmt = stmt.order_by(DietRecord.diet_date.desc(), DietRecord.id.desc())
    rows, total = paginate(db, stmt, params)
    items = [DietRecordOut.model_validate(record) for record in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/records/day", summary="某天饮食汇总")
def day_summary(
    db: DbSession,
    current: CurrentUser,
    on_date: date | None = Query(None, alias="date", description="统计日期，默认今天"),
) -> dict[str, Any]:
    """统计某一天的饮食：按餐次分组 + 全天合计 + 占建议摄入百分比。

    建议摄入默认取 2000 千卡（见 schemas.diet.DEFAULT_TARGET_* 的注释），
    后续如需个性化，可在这里改用「按用户目标计算」的推荐值。

    参数:
        on_date: 统计日期，默认今天。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 DaySummaryOut。
    """
    target_day = on_date or date.today()
    records = list(
        db.scalars(
            select(DietRecord)
            .where(DietRecord.user_id == current.id, DietRecord.diet_date == target_day)
            .order_by(DietRecord.id.asc())
        ).all()
    )

    groups: dict[str, list[DietRecord]] = {meal: [] for meal in MEAL_ORDER}
    for record in records:
        groups.setdefault(record.meal_type, []).append(record)

    total_calories = round(sum(record.calories or 0 for record in records), 2)
    total_protein = round(sum(record.protein or 0 for record in records), 2)
    total_fat = round(sum(record.fat or 0 for record in records), 2)
    total_carbohydrate = round(sum(record.carbohydrate or 0 for record in records), 2)

    # 固定按 早餐→午餐→晚餐→加餐 顺序输出，前端渲染顺序稳定
    meals = [
        MealGroupOut(
            meal_type=meal,
            meal_label=MEAL_LABELS.get(meal, meal),
            total_calories=round(sum(record.calories or 0 for record in groups.get(meal, [])), 2),
            items=[DietRecordOut.model_validate(record) for record in groups.get(meal, [])],
        )
        for meal in MEAL_ORDER
    ]

    summary = DaySummaryOut(
        date=target_day,
        target_calories=DEFAULT_TARGET_CALORIES,
        target_protein=DEFAULT_TARGET_PROTEIN,
        target_fat=DEFAULT_TARGET_FAT,
        target_carbohydrate=DEFAULT_TARGET_CARBOHYDRATE,
        total_calories=total_calories,
        total_protein=total_protein,
        total_fat=total_fat,
        total_carbohydrate=total_carbohydrate,
        calorie_percent=percent_of(total_calories, DEFAULT_TARGET_CALORIES),
        protein_percent=percent_of(total_protein, DEFAULT_TARGET_PROTEIN),
        fat_percent=percent_of(total_fat, DEFAULT_TARGET_FAT),
        carbohydrate_percent=percent_of(total_carbohydrate, DEFAULT_TARGET_CARBOHYDRATE),
        record_count=len(records),
        meals=meals,
    )
    return ok(summary)


@router.put("/records/{record_id}", summary="修改饮食记录")
def update_record(
    record_id: int, req: DietRecordUpdateRequest, db: DbSession, current: CurrentUser
) -> dict[str, Any]:
    """修改自己的饮食记录；改 amount_g 时自动重算热量与三大营养素。

    参数:
        record_id: 记录ID。
        req: 待修改字段（全部可选）。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为修改后的 DietRecordOut。
    """
    record = _get_own_record(db, record_id, current.id)
    data = req.model_dump(exclude_unset=True)

    if data.get("diet_date") is not None:
        record.diet_date = data["diet_date"]
    if data.get("meal_type"):
        record.meal_type = data["meal_type"]
    if "note" in data:
        record.note = data["note"]
    if data.get("food_name"):
        record.food_name = data["food_name"].strip()
    if data.get("amount_g") is not None:
        record.amount_g = float(data["amount_g"])
        # 有 food_id 时按食物库重算，纯自定义食物则保持营养值为 0
        food = db.get(Food, record.food_id) if record.food_id else None
        record.calories, record.protein, record.fat, record.carbohydrate = _calc_nutrition(food, record.amount_g)

    db.commit()
    db.refresh(record)
    return ok(DietRecordOut.model_validate(record))


@router.delete("/records/{record_id}", summary="删除饮食记录")
def delete_record(record_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """删除自己的饮食记录。

    参数:
        record_id: 记录ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为删除结果。
    """
    record = _get_own_record(db, record_id, current.id)
    db.delete(record)
    db.commit()
    return ok({"record_id": record_id, "deleted": True})


# ---------------------------------------------------------------- 统计
@router.get("/stats", summary="饮食区间统计")
def diet_stats(
    db: DbSession,
    current: CurrentUser,
    start_date: date | None = Query(None, description="开始日期，默认 6 天前"),
    end_date: date | None = Query(None, description="结束日期，默认今天"),
) -> dict[str, Any]:
    """统计一个日期区间内的饮食情况：每日热量数组、三大营养素合计、平均每日热量。

    参数:
        start_date: 开始日期，默认 end_date - 6 天（即近 7 天）。
        end_date: 结束日期，默认今天。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 DietStatsOut（区间内没有记录的日期补 0，便于前端画折线图）。
    """
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))
    if start > end:
        raise BadRequestError("start_date 不能晚于 end_date")
    if (end - start).days > 366:
        raise BadRequestError("统计区间不能超过一年")

    records = list(
        db.scalars(
            select(DietRecord).where(
                DietRecord.user_id == current.id,
                DietRecord.diet_date >= start,
                DietRecord.diet_date <= end,
            )
        ).all()
    )

    # 先按日期初始化桶，保证缺失日期也出现在数组里
    buckets: dict[date, dict[str, float]] = {}
    cursor = start
    while cursor <= end:
        buckets[cursor] = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbohydrate": 0.0}
        cursor += timedelta(days=1)

    total_calories = total_protein = total_fat = total_carbohydrate = 0.0
    for record in records:
        bucket = buckets.get(record.diet_date)
        if bucket is not None:
            bucket["calories"] += record.calories or 0
            bucket["protein"] += record.protein or 0
            bucket["fat"] += record.fat or 0
            bucket["carbohydrate"] += record.carbohydrate or 0
        total_calories += record.calories or 0
        total_protein += record.protein or 0
        total_fat += record.fat or 0
        total_carbohydrate += record.carbohydrate or 0

    day_count = len(buckets) or 1
    stats = DietStatsOut(
        start_date=start,
        end_date=end,
        days=[DailyCaloriesOut(date=day, calories=round(value["calories"], 2)) for day, value in buckets.items()],
        total_calories=round(total_calories, 2),
        total_protein=round(total_protein, 2),
        total_fat=round(total_fat, 2),
        total_carbohydrate=round(total_carbohydrate, 2),
        avg_daily_calories=round(total_calories / day_count, 2),
        record_count=len(records),
    )
    return ok(stats)
