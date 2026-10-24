"""运动课程模块接口（/api/courses）。

包含：课程分类、课程列表/详情、播放地址、收藏、评分、评论（含回复与点赞）、相关推荐。

接口约定（与全局规范一致）：
- 成功统一 ``return ok(data)``；
- 业务错误统一 ``raise BadRequestError / NotFoundError / ForbiddenError / ConflictError``；
- 分页统一使用 ``page_params`` 依赖 + ``PageParams`` + ``paginate()`` + ``PageResult.build()``；
- 数据库访问一律 SQLAlchemy 2.0 风格（``select()`` + ``db.scalars() / db.execute().scalars()``）。

注意：静态路径（``/categories``、``/list``、``/favorites``、``/comment/...``）必须声明在
``/{course_id}`` 之前，否则会被动态路径抢先匹配。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ok
from app.models.course import (
    Course,
    CourseCategory,
    CourseComment,
    CourseCommentLike,
    CourseFavorite,
    CourseRating,
)
from app.models.user import User
from app.schemas.course import (
    CommentLikeResultOut,
    CommentReplyOut,
    CourseBriefOut,
    CourseCategoryOut,
    CourseCommentOut,
    CourseCommentRequest,
    CourseDetailOut,
    CourseFavoriteOut,
    CourseFavoriteResultOut,
    CourseRatingOut,
    CourseRatingRequest,
    CourseVideoOut,
)

router = APIRouter(prefix="/courses", tags=["运动课程"])

# 课程详情里每条一级评论展示的回复条数
REPLY_PREVIEW_LIMIT = 3
# 相关课程推荐条数
RELATED_LIMIT = 6
# 演示环境播放地址有效期（生产环境应由对象存储生成带签名的临时地址）
VIDEO_URL_TTL_HOURS = 2


# ======================================================================
# 内部工具函数
# ======================================================================
def _get_course(db: Session, course_id: int) -> Course:
    """取出课程，不存在则抛 404。"""
    course = db.get(Course, course_id)
    if course is None:
        raise NotFoundError("课程不存在")
    return course


def _get_published_course(db: Session, course_id: int) -> Course:
    """取出课程并校验已上架。"""
    course = _get_course(db, course_id)
    if not course.is_published:
        raise BadRequestError("课程未上架，暂不可用")
    return course


def _approved_comment_count_map(db: Session, course_ids: list[int]) -> dict[int, int]:
    """一次分组查询统计多门课程「审核通过」的评论数，避免 N+1。"""
    if not course_ids:
        return {}
    rows = db.execute(
        select(CourseComment.course_id, func.count(CourseComment.id))
        .where(CourseComment.course_id.in_(course_ids), CourseComment.status == "approved")
        .group_by(CourseComment.course_id)
    ).all()
    return {int(course_id): int(count) for course_id, count in rows}


def _favorite_course_ids(db: Session, user: User | None, course_ids: list[int]) -> set[int]:
    """返回当前用户在这些课程里已收藏的课程ID集合。"""
    if user is None or not course_ids:
        return set()
    rows = db.scalars(
        select(CourseFavorite.course_id).where(
            CourseFavorite.user_id == user.id, CourseFavorite.course_id.in_(course_ids)
        )
    ).all()
    return {int(course_id) for course_id in rows}


def _course_brief(course: Course, favorited: bool = False, comment_count: int = 0) -> CourseBriefOut:
    """ORM 课程对象 -> 简要出参（补充分类名、是否已收藏、评论数）。"""
    out = CourseBriefOut.model_validate(course)
    out.category_name = course.category.name if course.category else None
    out.is_favorited = favorited
    out.comment_count = comment_count
    return out


def _course_briefs(db: Session, courses: list[Course], user: User | None) -> list[CourseBriefOut]:
    """批量组装课程简要出参（收藏状态、评论数走批量查询）。"""
    course_ids = [course.id for course in courses]
    favorited = _favorite_course_ids(db, user, course_ids)
    comment_counts = _approved_comment_count_map(db, course_ids)
    return [
        _course_brief(course, course.id in favorited, comment_counts.get(course.id, 0))
        for course in courses
    ]


def _reply_out(comment: CourseComment, liked_ids: set[int]) -> CommentReplyOut:
    """ORM 评论对象 -> 回复出参。"""
    out = CommentReplyOut.model_validate(comment)
    out.user_name = comment.user.display_name if comment.user else None
    out.user_avatar = comment.user.avatar if comment.user else None
    out.liked = comment.id in liked_ids
    return out


def _comment_out(comment: CourseComment, liked_ids: set[int]) -> CourseCommentOut:
    """ORM 评论对象 -> 一级评论出参。"""
    out = CourseCommentOut.model_validate(comment)
    out.user_name = comment.user.display_name if comment.user else None
    out.user_avatar = comment.user.avatar if comment.user else None
    out.liked = comment.id in liked_ids
    return out


def _liked_comment_ids(db: Session, user: User | None, comment_ids: list[int]) -> set[int]:
    """返回当前用户已点赞的评论ID集合。"""
    if user is None or not comment_ids:
        return set()
    rows = db.scalars(
        select(CourseCommentLike.comment_id).where(
            CourseCommentLike.user_id == user.id, CourseCommentLike.comment_id.in_(comment_ids)
        )
    ).all()
    return {int(comment_id) for comment_id in rows}


# ======================================================================
# 一、分类与列表
# ======================================================================
@router.get("/categories", summary="课程分类列表")
def list_categories(db: DbSession, user: OptionalUser) -> dict:
    """课程分类列表，含每个分类下已上架的课程数。

    参数：
        无（登录可选，便于前端统一处理）
    返回：
        data 为分类列表
    """
    categories = db.scalars(
        select(CourseCategory)
        .where(CourseCategory.is_active.is_(True))
        .order_by(CourseCategory.sort_order, CourseCategory.id)
    ).all()
    rows = db.execute(
        select(Course.category_id, func.count(Course.id))
        .where(Course.is_published.is_(True))
        .group_by(Course.category_id)
    ).all()
    counts = {int(category_id): int(count) for category_id, count in rows}

    items: list[CourseCategoryOut] = []
    for category in categories:
        out = CourseCategoryOut.model_validate(category)
        out.course_count = counts.get(category.id, 0)
        items.append(out)
    return ok(items)


@router.get("/list", summary="课程列表")
def list_courses(
    db: DbSession,
    user: OptionalUser,
    params: PageParams = Depends(page_params),
    category_id: int | None = Query(default=None, ge=1, description="分类ID"),
    difficulty: int | None = Query(default=None, ge=1, le=5, description="难度 1-5"),
    keyword: str | None = Query(default=None, max_length=50, description="标题关键词（模糊匹配）"),
    sort: str = Query(default="hot", description="排序：hot 最热 / new 最新 / rating 评分最高"),
) -> dict:
    """课程列表（分页）。

    参数：
        params: 分页参数
        category_id: 分类筛选
        difficulty: 难度筛选
        keyword: 按标题模糊搜索
        sort: hot 按播放量 / new 按发布时间 / rating 按评分
    返回：
        分页结果，items 为课程简要信息（含是否已收藏）
    """
    if sort not in ("hot", "new", "rating"):
        raise BadRequestError("sort 只能是 hot、new、rating")

    stmt = select(Course).where(Course.is_published.is_(True))
    if category_id is not None:
        stmt = stmt.where(Course.category_id == category_id)
    if difficulty is not None:
        stmt = stmt.where(Course.difficulty == difficulty)
    if keyword:
        stmt = stmt.where(Course.title.like(f"%{keyword.strip()}%"))

    if sort == "new":
        stmt = stmt.order_by(Course.created_at.desc(), Course.id.desc())
    elif sort == "rating":
        stmt = stmt.order_by(Course.rating_avg.desc(), Course.rating_count.desc(), Course.id.desc())
    else:  # hot
        stmt = stmt.order_by(Course.view_count.desc(), Course.favorite_count.desc(), Course.id.desc())

    rows, total = paginate(db, stmt, params)
    items = _course_briefs(db, rows, user)
    return ok(PageResult.build(items, total, params))


@router.get("/favorites", summary="我收藏的课程")
def my_favorite_courses(db: DbSession, user: CurrentUser, params: PageParams = Depends(page_params)) -> dict:
    """分页查询我收藏的课程（按收藏时间倒序）。

    参数：
        params: 分页参数
    返回：
        分页结果，items 为课程简要信息 + 收藏时间
    """
    stmt = (
        select(CourseFavorite)
        .where(CourseFavorite.user_id == user.id)
        .order_by(CourseFavorite.created_at.desc(), CourseFavorite.id.desc())
    )
    rows, total = paginate(db, stmt, params)

    course_ids = [favorite.course_id for favorite in rows]
    course_map: dict[int, Course] = {}
    if course_ids:
        courses = db.scalars(select(Course).where(Course.id.in_(course_ids))).all()
        course_map = {course.id: course for course in courses}
    briefs = {brief.id: brief for brief in _course_briefs(db, list(course_map.values()), user)}

    items: list[CourseFavoriteOut] = []
    for favorite in rows:
        brief = briefs.get(favorite.course_id)
        if brief is None:  # 课程已被删除，跳过脏数据
            continue
        out = CourseFavoriteOut(**brief.model_dump())
        out.favorited_at = favorite.created_at
        items.append(out)
    return ok(PageResult.build(items, total, params))


# ======================================================================
# 二、评论点赞 / 删除（静态路径，必须放在 /{course_id} 之前）
# ======================================================================
@router.delete("/comment/{comment_id}", summary="删除自己的评论")
def delete_comment(
    db: DbSession, user: CurrentUser, comment_id: int = Path(..., ge=1, description="评论ID")
) -> dict:
    """删除评论。

    简单起见只允许删除本人发表的评论（管理员删除走后台接口）；
    删除父评论时其回复会随外键级联删除。

    参数：
        comment_id: 评论ID
    返回：
        data 为删除结果
    """
    comment = db.get(CourseComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")
    if comment.user_id != user.id:
        raise ForbiddenError("只能删除自己的评论")
    db.delete(comment)
    db.commit()
    return ok({"deleted": True, "comment_id": comment_id}, message="评论已删除")


@router.post("/comment/{comment_id}/like", summary="给评论点赞")
def like_comment(db: DbSession, user: CurrentUser, comment_id: int = Path(..., ge=1, description="评论ID")) -> dict:
    """给评论点赞（重复点赞返回 409，like_count +1）。

    参数：
        comment_id: 评论ID
    返回：
        data 为点赞结果与最新点赞数
    """
    comment = db.get(CourseComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")

    exists = db.scalar(
        select(func.count())
        .select_from(CourseCommentLike)
        .where(CourseCommentLike.user_id == user.id, CourseCommentLike.comment_id == comment.id)
    )
    if exists:
        raise ConflictError("你已经点过赞了")

    db.add(CourseCommentLike(user_id=user.id, comment_id=comment.id))
    comment.like_count = (comment.like_count or 0) + 1
    db.commit()
    return ok(
        CommentLikeResultOut(comment_id=comment.id, liked=True, like_count=comment.like_count),
        message="点赞成功",
    )


@router.delete("/comment/{comment_id}/like", summary="取消评论点赞")
def unlike_comment(db: DbSession, user: CurrentUser, comment_id: int = Path(..., ge=1, description="评论ID")) -> dict:
    """取消评论点赞（like_count -1，且不会小于 0）。

    参数：
        comment_id: 评论ID
    返回：
        data 为取消结果与最新点赞数
    """
    comment = db.get(CourseComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")

    like = db.scalars(
        select(CourseCommentLike).where(
            CourseCommentLike.user_id == user.id, CourseCommentLike.comment_id == comment.id
        )
    ).first()
    if like is None:
        raise NotFoundError("你还没有给该评论点赞")

    db.delete(like)
    comment.like_count = max((comment.like_count or 0) - 1, 0)
    db.commit()
    return ok(
        CommentLikeResultOut(comment_id=comment.id, liked=False, like_count=comment.like_count),
        message="已取消点赞",
    )


# ======================================================================
# 三、课程详情、播放地址、相关推荐
# ======================================================================
@router.get("/{course_id}", summary="课程详情")
def course_detail(
    db: DbSession, user: OptionalUser, course_id: int = Path(..., ge=1, description="课程ID")
) -> dict:
    """课程详情（含分类名、是否已收藏、我的评分），同时把播放量 +1。

    参数：
        course_id: 课程ID
    返回：
        data 为课程详情（播放地址请调用 /courses/{id}/video）
    """
    course = _get_course(db, course_id)
    if not course.is_published:
        raise ForbiddenError("课程未上架，暂不可查看")

    course.view_count = (course.view_count or 0) + 1
    db.commit()
    db.refresh(course)

    out = CourseDetailOut.model_validate(course)
    out.category_name = course.category.name if course.category else None
    out.comment_count = _approved_comment_count_map(db, [course.id]).get(course.id, 0)
    out.is_favorited = course.id in _favorite_course_ids(db, user, [course.id])
    if user is not None:
        score = db.scalar(
            select(CourseRating.score).where(
                CourseRating.user_id == user.id, CourseRating.course_id == course.id
            )
        )
        out.my_score = int(score) if score is not None else None
    return ok(out)


@router.get("/{course_id}/video", summary="获取课程视频播放地址")
def course_video(
    db: DbSession, user: OptionalUser, course_id: int = Path(..., ge=1, description="课程ID")
) -> dict:
    """获取课程播放地址（校验课程已上架）。

    说明：演示环境直接返回数据库里存的 video_url，并给一个过期时间字段占位。
    生产环境应改为：向对象存储/CDN 申请带签名、带有效期的临时播放地址
    （如 OSS/COS 私有 Bucket 的 STS 签名 URL、或 HLS 的加密临时 Token），
    不要把原始地址直接暴露给客户端，避免视频被盗链。

    参数：
        course_id: 课程ID
    返回：
        data 含 video_url、时长与播放地址过期时间
    """
    course = _get_published_course(db, course_id)
    if not course.video_url:
        raise NotFoundError("该课程暂未上传视频")
    return ok(CourseVideoOut(
        course_id=course.id,
        title=course.title,
        video_url=course.video_url,
        duration_min=course.duration_min,
        expires_at=datetime.now() + timedelta(hours=VIDEO_URL_TTL_HOURS),
    ))


@router.get("/{course_id}/related", summary="相关课程推荐")
def related_courses(
    db: DbSession,
    user: OptionalUser,
    course_id: int = Path(..., ge=1, description="课程ID"),
    limit: int = Query(default=RELATED_LIMIT, ge=1, le=20, description="返回条数，默认 6"),
) -> dict:
    """同分类下的相关课程推荐（按播放量倒序，排除自己，最多 6 条）。

    参数：
        course_id: 当前课程ID
        limit: 返回条数，默认 6
    返回：
        data 为课程简要信息列表
    """
    course = _get_course(db, course_id)
    rows = db.scalars(
        select(Course)
        .where(
            Course.is_published.is_(True),
            Course.category_id == course.category_id,
            Course.id != course.id,
        )
        .order_by(Course.view_count.desc(), Course.id.desc())
        .limit(min(limit, RELATED_LIMIT))
    ).all()
    return ok(_course_briefs(db, list(rows), user))


# ======================================================================
# 四、收藏
# ======================================================================
@router.post("/{course_id}/favorite", summary="收藏课程")
def favorite_course(db: DbSession, user: CurrentUser, course_id: int = Path(..., ge=1, description="课程ID")) -> dict:
    """收藏课程（重复收藏返回 409，favorite_count +1）。

    参数：
        course_id: 课程ID
    返回：
        data 为收藏结果与最新收藏数
    """
    course = _get_course(db, course_id)
    if course.id in _favorite_course_ids(db, user, [course.id]):
        raise ConflictError("你已经收藏过该课程")

    db.add(CourseFavorite(user_id=user.id, course_id=course.id))
    course.favorite_count = (course.favorite_count or 0) + 1
    db.commit()
    return ok(
        CourseFavoriteResultOut(
            course_id=course.id, is_favorited=True, favorite_count=course.favorite_count
        ),
        message="收藏成功",
    )


@router.delete("/{course_id}/favorite", summary="取消收藏课程")
def unfavorite_course(
    db: DbSession, user: CurrentUser, course_id: int = Path(..., ge=1, description="课程ID")
) -> dict:
    """取消收藏课程（favorite_count -1，且不会小于 0）。

    参数：
        course_id: 课程ID
    返回：
        data 为取消结果与最新收藏数
    """
    course = _get_course(db, course_id)
    favorite = db.scalars(
        select(CourseFavorite).where(
            CourseFavorite.user_id == user.id, CourseFavorite.course_id == course.id
        )
    ).first()
    if favorite is None:
        raise NotFoundError("你还没有收藏该课程")

    db.delete(favorite)
    course.favorite_count = max((course.favorite_count or 0) - 1, 0)
    db.commit()
    return ok(
        CourseFavoriteResultOut(
            course_id=course.id, is_favorited=False, favorite_count=course.favorite_count
        ),
        message="已取消收藏",
    )


# ======================================================================
# 五、评分
# ======================================================================
@router.post("/{course_id}/rating", summary="给课程打分")
def rate_course(
    payload: CourseRatingRequest,
    db: DbSession,
    user: CurrentUser,
    course_id: int = Path(..., ge=1, description="课程ID"),
) -> dict:
    """给课程打分（1-5 星）；已打过分则更新，并重新计算平均分与评分人数。

    参数：
        payload: score 1-5
        course_id: 课程ID
    返回：
        data 含我的评分、课程平均分与评分人数
    """
    course = _get_course(db, course_id)
    rating = db.scalars(
        select(CourseRating).where(
            CourseRating.user_id == user.id, CourseRating.course_id == course.id
        )
    ).first()
    if rating is None:
        db.add(CourseRating(user_id=user.id, course_id=course.id, score=payload.score))
    else:
        rating.score = payload.score
    db.flush()  # 先落库，保证下面的聚合包含本次评分

    avg, count = db.execute(
        select(func.avg(CourseRating.score), func.count(CourseRating.id)).where(
            CourseRating.course_id == course.id
        )
    ).one()
    course.rating_avg = round(float(avg or 0), 2)
    course.rating_count = int(count or 0)
    db.commit()
    return ok(
        CourseRatingOut(
            course_id=course.id,
            my_score=payload.score,
            rating_avg=course.rating_avg,
            rating_count=course.rating_count,
        ),
        message="评分已保存",
    )


@router.get("/{course_id}/rating", summary="我的评分")
def my_rating(db: DbSession, user: CurrentUser, course_id: int = Path(..., ge=1, description="课程ID")) -> dict:
    """查看我对某门课程的评分（未评分时 my_score 为空）。

    参数：
        course_id: 课程ID
    返回：
        data 含我的评分、课程平均分与评分人数
    """
    course = _get_course(db, course_id)
    score = db.scalar(
        select(CourseRating.score).where(
            CourseRating.user_id == user.id, CourseRating.course_id == course.id
        )
    )
    return ok(CourseRatingOut(
        course_id=course.id,
        my_score=int(score) if score is not None else None,
        rating_avg=course.rating_avg or 0.0,
        rating_count=course.rating_count or 0,
    ))


# ======================================================================
# 六、评论
# ======================================================================
@router.post("/{course_id}/comment", summary="发表课程评论")
def create_comment(
    payload: CourseCommentRequest,
    db: DbSession,
    user: CurrentUser,
    course_id: int = Path(..., ge=1, description="课程ID"),
) -> dict:
    """发表评论或回复。

    参数：
        payload: content 3-500 字；parent_id 可选，用于回复
        course_id: 课程ID
    返回：
        data 为新建评论（status 为 pending）

    说明：
    - 回复只允许一层：parent_id 必须指向一级评论，不能回复二级回复；
    - 新评论 status="pending"，需后台审核通过后才会在评论列表公开显示
      （因此课程的评论数按 status="approved" 实时统计）。
    """
    course = _get_course(db, course_id)
    parent: CourseComment | None = None
    if payload.parent_id is not None:
        parent = db.get(CourseComment, payload.parent_id)
        if parent is None or parent.course_id != course.id:
            raise NotFoundError("要回复的评论不存在")
        if parent.parent_id is not None:
            raise BadRequestError("回复只支持一层，请回复一级评论")

    comment = CourseComment(
        course_id=course.id,
        user_id=user.id,
        parent_id=parent.id if parent else None,
        content=payload.content.strip(),
        like_count=0,
        status="pending",  # 待审核，通过后才公开
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    out = _comment_out(comment, set())
    out.replies = []
    out.reply_count = 0
    return ok(out, message="评论已提交，审核通过后公开显示")


@router.get("/{course_id}/comments", summary="课程评论列表")
def list_comments(
    db: DbSession,
    user: OptionalUser,
    course_id: int = Path(..., ge=1, description="课程ID"),
    params: PageParams = Depends(page_params),
) -> dict:
    """课程评论分页列表（只返回审核通过的评论）。

    一级评论分页，每条附带最多 3 条回复和回复总数，并标记当前用户是否已点赞。

    参数：
        course_id: 课程ID
        params: 分页参数
    返回：
        分页结果，items 为一级评论（含 replies、reply_count、liked）
    """
    course = _get_course(db, course_id)

    stmt = (
        select(CourseComment)
        .where(
            CourseComment.course_id == course.id,
            CourseComment.parent_id.is_(None),  # 只分页一级评论
            CourseComment.status == "approved",
        )
        .order_by(CourseComment.created_at.desc(), CourseComment.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    parent_ids = [comment.id for comment in rows]

    # 一次性取出这些一级评论下的全部回复（已审核），在内存里分组、截断、计数
    replies_map: dict[int, list[CourseComment]] = {}
    reply_count_map: dict[int, int] = {}
    all_replies: list[CourseComment] = []
    if parent_ids:
        all_replies = list(db.scalars(
            select(CourseComment)
            .where(CourseComment.parent_id.in_(parent_ids), CourseComment.status == "approved")
            .order_by(CourseComment.created_at.asc(), CourseComment.id.asc())
        ).all())
        for reply in all_replies:
            replies_map.setdefault(reply.parent_id, []).append(reply)
            reply_count_map[reply.parent_id] = reply_count_map.get(reply.parent_id, 0) + 1

    liked_ids = _liked_comment_ids(db, user, parent_ids + [reply.id for reply in all_replies])

    items: list[CourseCommentOut] = []
    for comment in rows:
        out = _comment_out(comment, liked_ids)
        preview = replies_map.get(comment.id, [])[:REPLY_PREVIEW_LIMIT]
        out.replies = [_reply_out(reply, liked_ids) for reply in preview]
        out.reply_count = reply_count_map.get(comment.id, 0)
        items.append(out)
    return ok(PageResult.build(items, total, params))
