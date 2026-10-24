"""动作库模块（/exercises）：动作分类、动作列表、搜索、详情、相似推荐。

动作库是公共只读数据（由种子数据/后台维护），所以这里的接口不强制登录，
只过滤 is_active=True 的动作；详情接口会顺带把浏览数 +1。
路由顺序：/categories、/search、/filter/options、/category/{slug} 必须写在
/{exercise_id} 之前，否则会被当成动作ID匹配。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, NotFoundError, ok
from app.models.exercise import Exercise, ExerciseCategory
from app.schemas.exercise import (
    ExerciseBriefOut,
    ExerciseCategoryOut,
    ExerciseFilterOptionsOut,
    ExerciseOut,
    ExerciseRelatedOut,
    ExerciseSearchItemOut,
    ExerciseSearchResultOut,
)

router = APIRouter(prefix="/exercises", tags=["动作库"])

# 列表排序方式（值 -> 排序表达式）
SORT_OPTIONS: dict[str, tuple] = {
    "default": (Exercise.id.asc(),),
    "latest": (Exercise.id.desc(),),
    "popular": (Exercise.view_count.desc(), Exercise.id.asc()),
    "difficulty_asc": (Exercise.difficulty.asc(), Exercise.id.asc()),
    "difficulty_desc": (Exercise.difficulty.desc(), Exercise.id.asc()),
    "name": (Exercise.name.asc(),),
}

# 搜索匹配度：case 表达式的分值 -> 说明文案
MATCH_REASONS: dict[int, str] = {
    0: "名称完全匹配",
    1: "名称前缀匹配",
    2: "英文名完全匹配",
    3: "名称包含关键词",
    4: "英文名包含关键词",
    5: "关键词命中",
    9: "相关推荐",
}


def _brief(exercise: Exercise) -> ExerciseBriefOut:
    """把 ORM 动作对象转成精简出参。

    参数:
        exercise: Exercise 对象（category 由 joined 预加载）
    返回:
        ExerciseBriefOut
    """
    return ExerciseBriefOut(
        id=exercise.id,
        name=exercise.name,
        name_en=exercise.name_en,
        category_id=exercise.category_id,
        category_name=exercise.category.name if exercise.category is not None else None,
        equipment=exercise.equipment,
        difficulty=exercise.difficulty,
        image_url=exercise.image_url,
        gif_url=exercise.gif_url,
        primary_muscles=exercise.primary_muscles,
    )


def _detail(exercise: Exercise) -> ExerciseOut:
    """把 ORM 动作对象转成详情出参（含讲解、发力要点、易错提醒）。

    参数:
        exercise: Exercise 对象
    返回:
        ExerciseOut
    """
    category = exercise.category
    return ExerciseOut(
        **_brief(exercise).model_dump(),
        category_slug=category.slug if category is not None else None,
        secondary_muscles=exercise.secondary_muscles,
        description=exercise.description,
        key_points=exercise.key_points,
        common_mistakes=exercise.common_mistakes,
        tips=exercise.tips,
        keywords=exercise.keywords,
        view_count=exercise.view_count or 0,
        is_active=bool(exercise.is_active),
    )


def _load_categories(db: Session) -> list[ExerciseCategoryOut]:
    """查询全部分类并统计每个分类下的动作数量。

    参数:
        db: 数据库会话
    返回:
        按 sort_order 排序的分类列表，exercise_count 为启用状态的动作数
    """
    # 用 outerjoin + count 一次查出分类与动作数，避免逐个分类再查一遍
    rows = db.execute(
        select(ExerciseCategory, func.count(Exercise.id))
        .outerjoin(
            Exercise,
            and_(Exercise.category_id == ExerciseCategory.id, Exercise.is_active.is_(True)),
        )
        .group_by(ExerciseCategory.id)
        .order_by(ExerciseCategory.sort_order.asc(), ExerciseCategory.id.asc())
    ).all()
    return [
        ExerciseCategoryOut(
            id=category.id,
            name=category.name,
            slug=category.slug,
            body_part=category.body_part,
            sort_order=category.sort_order,
            exercise_count=int(count or 0),
        )
        for category, count in rows
    ]


def _keyword_filter(keyword: str):
    """构造"名称 / 英文名 / 关键词"的模糊匹配条件。

    参数:
        keyword: 用户输入的关键词
    返回:
        SQLAlchemy 条件表达式（三列任一包含关键词即命中）
    """
    like = f"%{keyword.strip().lower()}%"
    return or_(
        func.lower(Exercise.name).like(like),
        func.lower(func.coalesce(Exercise.name_en, "")).like(like),
        func.lower(func.coalesce(Exercise.keywords, "")).like(like),
    )


# ================================================================ 分类
@router.get("/categories", summary="动作分类列表")
def list_categories(db: DbSession) -> dict:
    """查询全部动作分类，并带上每个分类下的动作数量。

    参数:
        db: 数据库会话
    返回:
        统一响应，data 为分类列表（含 exercise_count）
    """
    return ok(_load_categories(db))


# ================================================================ 搜索
@router.get("/search", summary="搜索动作（带匹配度）")
def search_exercises(
    db: DbSession,
    keyword: str = Query(..., min_length=1, max_length=50, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=20, description="返回条数，最多 20"),
) -> dict:
    """按关键词搜索动作，名称完全匹配的排最前，最多返回 20 条。

    参数:
        keyword: 搜索关键词，匹配 name / name_en / keywords
        limit: 返回条数上限，最大 20
        db: 数据库会话
    返回:
        统一响应，data 为 {keyword, total, items}，items 按匹配度从高到低
    """
    kw = keyword.strip()
    if not kw:
        raise BadRequestError("搜索关键词不能为空")
    lowered = kw.lower()

    # 匹配度用 case 在数据库端算：分值越小越匹配，排序与截断都可以在 SQL 里完成
    name_l = func.lower(Exercise.name)
    name_en_l = func.lower(func.coalesce(Exercise.name_en, ""))
    keywords_l = func.lower(func.coalesce(Exercise.keywords, ""))
    like_all = f"%{lowered}%"
    rank = case(
        (name_l == lowered, 0),                    # 名称完全匹配优先
        (name_l.like(f"{lowered}%"), 1),           # 名称前缀匹配
        (name_en_l == lowered, 2),                 # 英文名完全匹配
        (name_l.like(like_all), 3),                # 名称包含
        (name_en_l.like(like_all), 4),             # 英文名包含
        (keywords_l.like(like_all), 5),            # 关键词命中
        else_=9,
    )

    rows = db.execute(
        select(Exercise, rank.label("rank"))
        .where(Exercise.is_active.is_(True), _keyword_filter(kw))
        .order_by(rank.asc(), Exercise.view_count.desc(), Exercise.id.asc())
        .limit(limit)
    ).all()

    items = []
    for exercise, score in rows:
        score = int(score)
        items.append(ExerciseSearchItemOut(
            **_brief(exercise).model_dump(),
            match_score=100 - score * 10,
            match_reason=MATCH_REASONS.get(score, "相关推荐"),
        ))
    return ok(ExerciseSearchResultOut(keyword=kw, total=len(items), items=items))


# ================================================================ 筛选项
@router.get("/filter/options", summary="动作列表可筛选的选项")
def filter_options(db: DbSession) -> dict:
    """返回动作列表可用的筛选项字典：所有分类、所有器械、难度 1-5。

    参数:
        db: 数据库会话
    返回:
        统一响应，data 为 {categories, equipments, difficulties}
    """
    equipments = [
        item
        for item in db.scalars(
            select(Exercise.equipment)
            .where(Exercise.is_active.is_(True), Exercise.equipment.is_not(None))
            .distinct()
            .order_by(Exercise.equipment.asc())
        ).all()
        if item
    ]
    data = ExerciseFilterOptionsOut(
        categories=_load_categories(db),
        equipments=equipments,
        difficulties=[1, 2, 3, 4, 5],
    )
    return ok(data)


# ================================================================ 列表
@router.get("", summary="动作列表（分页）")
@router.get("/", include_in_schema=False)
def list_exercises(
    db: DbSession,
    params: PageParams = Depends(page_params),
    category_id: int | None = Query(None, description="按分类ID筛选"),
    equipment: str | None = Query(None, description="按器械筛选，如 杠铃/哑铃/自重"),
    difficulty: int | None = Query(None, ge=1, le=5, description="按难度筛选 1-5"),
    keyword: str | None = Query(None, max_length=50, description="关键词，模糊搜索名称/英文名/关键词"),
    sort: str = Query("default", max_length=20, description="排序 default/latest/popular/difficulty_asc/difficulty_desc/name"),
) -> dict:
    """分页查询动作列表，支持分类、器械、难度、关键词筛选与多种排序。

    参数:
        params: 分页参数（page / page_size）
        category_id: 分类ID，可空
        equipment: 器械名，可空
        difficulty: 难度 1-5，可空
        keyword: 关键词，可空
        sort: 排序方式，默认 default，取值见 SORT_OPTIONS
        db: 数据库会话
    返回:
        统一响应，data 为分页结构，列表项为动作摘要
    """
    if sort not in SORT_OPTIONS:
        raise BadRequestError(f"sort 只能是：{'/'.join(SORT_OPTIONS)}")

    stmt = select(Exercise).where(Exercise.is_active.is_(True))
    if category_id:
        stmt = stmt.where(Exercise.category_id == category_id)
    if equipment:
        stmt = stmt.where(Exercise.equipment == equipment)
    if difficulty:
        stmt = stmt.where(Exercise.difficulty == difficulty)
    if keyword and keyword.strip():
        stmt = stmt.where(_keyword_filter(keyword))
    stmt = stmt.order_by(*SORT_OPTIONS[sort])

    rows, total = paginate(db, stmt, params)
    items = [_brief(exercise) for exercise in rows]
    return ok(PageResult[ExerciseBriefOut].build(items, total, params))


# ================================================================ 按分类 slug 查动作
@router.get("/category/{slug}", summary="按分类查动作（分页）")
def list_exercises_by_category(
    slug: str,
    db: DbSession,
    params: PageParams = Depends(page_params),
) -> dict:
    """按分类 slug 查询该分类下的动作（分页）。

    参数:
        slug: 分类英文标识，如 chest / back / legs
        params: 分页参数（page / page_size）
        db: 数据库会话
    返回:
        统一响应，data 为分页结构，列表项为动作摘要
    """
    category = db.scalars(select(ExerciseCategory).where(ExerciseCategory.slug == slug)).first()
    if category is None:
        raise NotFoundError("动作分类不存在")

    stmt = (
        select(Exercise)
        .where(Exercise.category_id == category.id, Exercise.is_active.is_(True))
        .order_by(Exercise.difficulty.asc(), Exercise.id.asc())
    )
    rows, total = paginate(db, stmt, params)
    items = [_brief(exercise) for exercise in rows]
    return ok(PageResult[ExerciseBriefOut].build(items, total, params))


# ================================================================ 详情
@router.get("/{exercise_id}", summary="动作详情")
def get_exercise(exercise_id: int, db: DbSession) -> dict:
    """查询动作详情（讲解、发力要点、易错提醒），并把浏览数 +1。

    参数:
        exercise_id: 动作ID
        db: 数据库会话
    返回:
        统一响应，data 为动作详情
    """
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or not exercise.is_active:
        raise NotFoundError("动作不存在或已下架")
    exercise.view_count = (exercise.view_count or 0) + 1
    db.commit()
    return ok(_detail(exercise))


# ================================================================ 相似推荐
@router.get("/{exercise_id}/related", summary="相似动作推荐")
def related_exercises(
    exercise_id: int,
    db: DbSession,
    limit: int = Query(6, ge=1, le=6, description="返回条数，最多 6 条"),
) -> dict:
    """推荐相似动作：同分类或同器械，最多 6 条，按浏览数与难度排序。

    参数:
        exercise_id: 当前动作ID
        limit: 返回条数上限，最大 6
        db: 数据库会话
    返回:
        统一响应，data 为 {base_id, items}
    """
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or not exercise.is_active:
        raise NotFoundError("动作不存在或已下架")

    conditions = [Exercise.category_id == exercise.category_id]
    if exercise.equipment:
        conditions.append(Exercise.equipment == exercise.equipment)

    rows = db.scalars(
        select(Exercise)
        .where(
            Exercise.id != exercise.id,
            Exercise.is_active.is_(True),
            or_(*conditions),
        )
        .order_by(Exercise.view_count.desc(), Exercise.difficulty.asc(), Exercise.id.asc())
        .limit(limit)
    ).all()
    return ok(ExerciseRelatedOut(base_id=exercise.id, items=[_brief(item) for item in rows]))
