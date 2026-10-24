"""后台管理模块接口。

全部接口（除 /login 外）都使用 CurrentAdmin 依赖，令牌 type 必须是 admin，
普通用户令牌无法访问；管理员接口不做 CurrentUser 校验，也不允许代用户操作数据。

包含：登录/资料、数据看板、用户管理、课程管理、评论审核、动态管理、
计划管理（只读）、实名认证审核。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentAdmin, DbSession
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ok
from app.core.security import create_access_token, hash_password, verify_password
from app.models.community import Post
from app.models.course import Course, CourseCategory, CourseComment
from app.models.plan import Plan
from app.models.user import Admin, CheckinRecord, RealNameAuth, User
from app.schemas.admin import (
    AdminCommentOut,
    AdminCourseOut,
    AdminLoginOut,
    AdminLoginRequest,
    AdminOut,
    AdminPlanOut,
    AdminPostOut,
    AdminUserOut,
    AdminUserUpdateRequest,
    CommentAuditRequest,
    CourseCreateRequest,
    CoursePublishRequest,
    CourseUpdateRequest,
    DailyCountOut,
    DashboardOut,
    PostVisibilityRequest,
    RealNameAuditRequest,
    RealNameAuthOut,
    ResetPasswordRequest,
    UserDisableRequest,
)
from app.schemas.community import split_images

router = APIRouter(prefix="/admin", tags=["后台管理"])

# 课程编辑时允许显式传 null 来清空的文本字段
COURSE_NULLABLE_TEXT = {"subtitle", "cover", "video_url", "equipment", "body_parts", "description", "coach_name"}
# 用户编辑时允许显式传 null/空 来清空的文本字段
USER_NULLABLE_TEXT = {"nickname", "phone", "email"}


# ---------------------------------------------------------------- 内部工具
def _count(db: Session, model: Any, *conditions: Any) -> int:
    """通用跨表计数：SELECT COUNT(*) FROM model WHERE conditions。

    参数:
        db: 数据库会话。
        model: 目标 ORM 模型。
        conditions: 可选过滤条件。
    返回:
        记录数（整数，永不为 None）。
    """
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return int(db.scalar(stmt) or 0)


def _course_out(course: Course) -> AdminCourseOut:
    """把 Course 转成后台课程出参（补上分类名称）。

    参数:
        course: 课程 ORM 对象（category 关系已 joined 加载）。
    返回:
        AdminCourseOut。
    """
    out = AdminCourseOut.model_validate(course)
    out.category_name = course.category.name if course.category else None
    return out


def _admin_post_out(post: Post) -> AdminPostOut:
    """把 Post 转成后台动态出参（图片字符串转数组、补发布者昵称）。

    参数:
        post: 动态 ORM 对象。
    返回:
        AdminPostOut。
    """
    return AdminPostOut(
        id=post.id,
        user_id=post.user_id,
        user_nickname=(post.user.nickname or post.user.username) if post.user else None,
        content=post.content,
        images=split_images(post.images),
        topic=post.topic,
        location=post.location,
        like_count=post.like_count or 0,
        comment_count=post.comment_count or 0,
        view_count=post.view_count or 0,
        is_top=bool(post.is_top),
        is_visible=bool(post.is_visible),
        created_at=post.created_at,
    )


def _admin_comment_out(comment: CourseComment) -> AdminCommentOut:
    """把课程评论转成后台审核出参（补课程标题与用户昵称）。

    参数:
        comment: 课程评论 ORM 对象。
    返回:
        AdminCommentOut。
    """
    out = AdminCommentOut.model_validate(comment)
    out.course_title = comment.course.title if comment.course else None
    out.user_nickname = (comment.user.nickname or comment.user.username) if comment.user else None
    return out


def _admin_user_out(db: Session, user: User) -> AdminUserOut:
    """把 User 转成后台用户出参（补签到次数与动态数）。

    参数:
        db: 数据库会话。
        user: 用户 ORM 对象。
    返回:
        AdminUserOut。
    """
    out = AdminUserOut.model_validate(user)
    out.checkin_count = _count(db, CheckinRecord, CheckinRecord.user_id == user.id)
    out.post_count = _count(db, Post, Post.user_id == user.id)
    return out


def _realname_out(auth: RealNameAuth, user: User | None) -> RealNameAuthOut:
    """把实名认证申请转成出参（补用户名/昵称）。

    参数:
        auth: 实名认证 ORM 对象。
        user: 对应用户，可为 None。
    返回:
        RealNameAuthOut。
    """
    out = RealNameAuthOut.model_validate(auth)
    out.username = user.username if user else None
    out.nickname = user.nickname if user else None
    return out


# ---------------------------------------------------------------- 登录 / 资料
@router.post("/login", summary="管理员登录")
def admin_login(req: AdminLoginRequest, db: DbSession) -> dict[str, Any]:
    """管理员登录，成功后返回 type=admin 的访问令牌。

    参数:
        req: 管理员用户名与密码。
        db: 数据库会话。
    返回:
        统一响应，data 为 AdminLoginOut（token + 管理员信息）；
        用户名或密码错误抛 401，账号停用抛 403。
    """
    admin = db.scalar(select(Admin).where(Admin.username == req.username))
    if admin is None or not verify_password(req.password, admin.password_hash):
        raise UnauthorizedError("用户名或密码错误")
    if not admin.is_active:
        raise ForbiddenError("管理员账号已停用")

    admin.last_login_at = datetime.now()
    db.commit()
    db.refresh(admin)
    token = create_access_token(admin.id, "admin")
    data = AdminLoginOut(
        token=token,
        token_type="bearer",
        expires_in=settings.ADMIN_JWT_EXPIRE_MINUTES * 60,
        admin=AdminOut.model_validate(admin),
    )
    return ok(data)


@router.get("/profile", summary="当前管理员信息")
def admin_profile(admin: CurrentAdmin) -> dict[str, Any]:
    """获取当前登录管理员的资料。

    参数:
        admin: 当前管理员（由 CurrentAdmin 依赖注入）。
    返回:
        统一响应，data 为 AdminOut。
    """
    return ok(AdminOut.model_validate(admin))


# ---------------------------------------------------------------- 数据看板
@router.get("/dashboard", summary="数据看板")
def dashboard(db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """后台首页数据看板：总量指标 + 近 7 天趋势。

    参数:
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 DashboardOut。
    """
    today = date.today()
    today_start = datetime.combine(today, time.min)
    tomorrow_start = datetime.combine(today + timedelta(days=1), time.min)
    start_7d = today - timedelta(days=6)

    new_users_7d: list[DailyCountOut] = []
    new_posts_7d: list[DailyCountOut] = []
    for offset in range(7):
        day = start_7d + timedelta(days=offset)
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day + timedelta(days=1), time.min)
        new_users_7d.append(
            DailyCountOut(
                date=day,
                count=_count(db, User, User.created_at >= day_start, User.created_at < day_end),
            )
        )
        new_posts_7d.append(
            DailyCountOut(
                date=day,
                count=_count(db, Post, Post.created_at >= day_start, Post.created_at < day_end),
            )
        )

    data = DashboardOut(
        total_users=_count(db, User),
        today_new_users=_count(db, User, User.created_at >= today_start, User.created_at < tomorrow_start),
        total_courses=_count(db, Course),
        total_posts=_count(db, Post),
        total_plans=_count(db, Plan),
        total_comments=_count(db, CourseComment),
        pending_comments=_count(db, CourseComment, CourseComment.status == "pending"),
        today_checkins=_count(db, CheckinRecord, CheckinRecord.checkin_date == today),
        new_users_7d=new_users_7d,
        new_posts_7d=new_posts_7d,
    )
    return ok(data)


# ---------------------------------------------------------------- 用户管理
@router.get("/users", summary="用户管理列表")
def list_users(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    keyword: str | None = Query(None, max_length=50, description="用户名/昵称/手机号 模糊搜索"),
    is_disabled: bool | None = Query(None, description="按封禁状态筛选"),
) -> dict[str, Any]:
    """分页查询用户，返回基本信息 + 签到次数 + 动态数。

    参数:
        params: 分页参数。
        keyword: 关键字（用户名/昵称/手机号）。
        is_disabled: 是否封禁筛选。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[AdminUserOut]。
    """
    stmt = select(User)
    if keyword and keyword.strip():
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(User.username.like(pattern), User.nickname.like(pattern), User.phone.like(pattern))
        )
    if is_disabled is not None:
        stmt = stmt.where(User.is_disabled.is_(is_disabled))
    stmt = stmt.order_by(User.id.desc())
    rows, total = paginate(db, stmt, params)

    # 批量统计签到次数与动态数，避免逐行查询
    ids = [user.id for user in rows]
    checkin_map: dict[int, int] = {}
    post_map: dict[int, int] = {}
    if ids:
        checkin_rows = db.execute(
            select(CheckinRecord.user_id, func.count(CheckinRecord.id))
            .where(CheckinRecord.user_id.in_(ids))
            .group_by(CheckinRecord.user_id)
        ).all()
        checkin_map = {user_id: int(count) for user_id, count in checkin_rows}
        post_rows = db.execute(
            select(Post.user_id, func.count(Post.id)).where(Post.user_id.in_(ids)).group_by(Post.user_id)
        ).all()
        post_map = {user_id: int(count) for user_id, count in post_rows}

    items: list[AdminUserOut] = []
    for user in rows:
        out = AdminUserOut.model_validate(user)
        out.checkin_count = checkin_map.get(user.id, 0)
        out.post_count = post_map.get(user.id, 0)
        items.append(out)
    return ok(PageResult.build(items, total, params))


@router.put("/users/{user_id}", summary="修改用户资料")
def update_user(
    user_id: int, req: AdminUserUpdateRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """修改用户昵称、手机号、邮箱、等级、积分、封禁状态。

    参数:
        user_id: 用户ID。
        req: 待修改字段（全部可选）。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为修改后的 AdminUserOut。
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")

    data = req.model_dump(exclude_unset=True)
    phone = data.get("phone")
    if phone and db.scalar(select(User.id).where(User.phone == phone, User.id != user.id)) is not None:
        raise ConflictError("手机号已被其它用户占用")
    email = data.get("email")
    if email and db.scalar(select(User.id).where(User.email == email, User.id != user.id)) is not None:
        raise ConflictError("邮箱已被其它用户占用")

    for field, value in data.items():
        if field in USER_NULLABLE_TEXT:
            # 空字符串/None 都按「清空」处理
            setattr(user, field, (value.strip() or None) if isinstance(value, str) else value)
        elif value is not None:
            setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return ok(_admin_user_out(db, user))


@router.post("/users/{user_id}/disable", summary="封禁/解封用户")
def disable_user(user_id: int, req: UserDisableRequest, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """封禁或解封用户（封禁后该用户无法调用需要登录的接口）。

    参数:
        user_id: 用户ID。
        req: disabled=True 封禁，False 解封。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 {user_id, is_disabled}。
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    user.is_disabled = bool(req.disabled)
    db.commit()
    db.refresh(user)
    return ok({"user_id": user.id, "is_disabled": bool(user.is_disabled)})


@router.post("/users/{user_id}/reset-password", summary="重置用户密码")
def reset_user_password(
    user_id: int, req: ResetPasswordRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """管理员重置某个用户的登录密码。

    参数:
        user_id: 用户ID。
        req: 新密码（6-64 位）。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为重置结果。
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return ok({"user_id": user.id, "reset": True})


@router.delete("/users/{user_id}", summary="删除用户")
def delete_user(user_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """删除用户（关联数据由数据库外键级联清理）。

    参数:
        user_id: 用户ID。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为删除结果。
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    db.delete(user)
    db.commit()
    return ok({"user_id": user_id, "deleted": True})


# ---------------------------------------------------------------- 课程管理
@router.get("/courses", summary="课程管理列表")
def list_courses(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    keyword: str | None = Query(None, max_length=50, description="标题模糊搜索"),
    category_id: int | None = Query(None, description="按分类筛选"),
    is_published: bool | None = Query(None, description="按上架状态筛选"),
) -> dict[str, Any]:
    """分页查询课程（包含未上架课程）。

    参数:
        params: 分页参数。
        keyword: 标题关键字。
        category_id: 分类ID。
        is_published: 上架状态。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[AdminCourseOut]。
    """
    stmt = select(Course)
    if keyword and keyword.strip():
        stmt = stmt.where(Course.title.like(f"%{keyword.strip()}%"))
    if category_id is not None:
        stmt = stmt.where(Course.category_id == category_id)
    if is_published is not None:
        stmt = stmt.where(Course.is_published.is_(is_published))
    stmt = stmt.order_by(Course.sort_order.asc(), Course.id.desc())
    rows, total = paginate(db, stmt, params)
    items = [_course_out(course) for course in rows]
    return ok(PageResult.build(items, total, params))


@router.post("/courses", summary="新增课程")
def create_course(req: CourseCreateRequest, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """后台新增一门课程（默认上架）。

    参数:
        req: 课程信息。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为新建课程的 AdminCourseOut。
    """
    if db.get(CourseCategory, req.category_id) is None:
        raise NotFoundError("课程分类不存在")
    course = Course(**req.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return ok(_course_out(course))


@router.put("/courses/{course_id}", summary="编辑课程")
def update_course(
    course_id: int, req: CourseUpdateRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """编辑课程信息（只更新传入的字段）。

    参数:
        course_id: 课程ID。
        req: 待修改字段（全部可选）。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为修改后的 AdminCourseOut。
    """
    course = db.get(Course, course_id)
    if course is None:
        raise NotFoundError("课程不存在")

    data = req.model_dump(exclude_unset=True)
    if data.get("category_id") is not None and db.get(CourseCategory, data["category_id"]) is None:
        raise NotFoundError("课程分类不存在")

    for field, value in data.items():
        # 数值字段不允许置 None（数据库 NOT NULL），文本字段允许显式清空
        if value is not None or field in COURSE_NULLABLE_TEXT:
            setattr(course, field, value)

    db.commit()
    db.refresh(course)
    return ok(_course_out(course))


@router.delete("/courses/{course_id}", summary="删除课程")
def delete_course(course_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """删除课程（其评论、收藏、评分由外键级联清理）。

    参数:
        course_id: 课程ID。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为删除结果。
    """
    course = db.get(Course, course_id)
    if course is None:
        raise NotFoundError("课程不存在")
    db.delete(course)
    db.commit()
    return ok({"course_id": course_id, "deleted": True})


@router.post("/courses/{course_id}/publish", summary="课程上架/下架")
def publish_course(
    course_id: int, req: CoursePublishRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """上架或下架课程。

    参数:
        course_id: 课程ID。
        req: is_published=True 上架，False 下架。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 {course_id, is_published}。
    """
    course = db.get(Course, course_id)
    if course is None:
        raise NotFoundError("课程不存在")
    course.is_published = bool(req.is_published)
    db.commit()
    db.refresh(course)
    return ok({"course_id": course.id, "is_published": bool(course.is_published)})


# ---------------------------------------------------------------- 评论审核
@router.get("/comments", summary="评论审核列表")
def list_comments(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    status: str | None = Query(None, pattern="^(pending|approved|rejected)$", description="审核状态"),
    course_id: int | None = Query(None, description="按课程筛选"),
) -> dict[str, Any]:
    """分页查询课程评论，用于后台审核。

    参数:
        params: 分页参数。
        status: 审核状态 pending/approved/rejected。
        course_id: 课程ID。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[AdminCommentOut]。
    """
    stmt = select(CourseComment)
    if status:
        stmt = stmt.where(CourseComment.status == status)
    if course_id is not None:
        stmt = stmt.where(CourseComment.course_id == course_id)
    stmt = stmt.order_by(CourseComment.created_at.desc(), CourseComment.id.desc())
    rows, total = paginate(db, stmt, params)
    items = [_admin_comment_out(comment) for comment in rows]
    return ok(PageResult.build(items, total, params))


@router.post("/comments/{comment_id}/audit", summary="审核评论")
def audit_comment(
    comment_id: int, req: CommentAuditRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """审核课程评论：通过置为 approved，驳回置为 rejected。

    参数:
        comment_id: 评论ID。
        req: action=approve|reject。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为审核后的 AdminCommentOut。
    """
    comment = db.get(CourseComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")
    comment.status = "approved" if req.action == "approve" else "rejected"
    db.commit()
    db.refresh(comment)
    return ok(_admin_comment_out(comment))


@router.delete("/comments/{comment_id}", summary="删除评论")
def delete_comment(comment_id: int, db: DbSession, admin: CurrentAdmin) -> dict[str, Any]:
    """后台删除课程评论（违规内容）。

    参数:
        comment_id: 评论ID。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为删除结果。
    """
    comment = db.get(CourseComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")
    db.delete(comment)
    db.commit()
    return ok({"comment_id": comment_id, "deleted": True})


# ---------------------------------------------------------------- 动态管理
@router.get("/posts", summary="动态管理列表")
def list_posts(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    keyword: str | None = Query(None, max_length=50, description="内容关键字"),
    is_visible: bool | None = Query(None, description="按可见性筛选"),
) -> dict[str, Any]:
    """分页查询社区动态（含已隐藏的动态），可隐藏/恢复。

    参数:
        params: 分页参数。
        keyword: 内容关键字。
        is_visible: 可见性筛选。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[AdminPostOut]。
    """
    stmt = select(Post)
    if keyword and keyword.strip():
        stmt = stmt.where(Post.content.like(f"%{keyword.strip()}%"))
    if is_visible is not None:
        stmt = stmt.where(Post.is_visible.is_(is_visible))
    stmt = stmt.order_by(Post.id.desc())
    rows, total = paginate(db, stmt, params)
    items = [_admin_post_out(post) for post in rows]
    return ok(PageResult.build(items, total, params))


@router.post("/posts/{post_id}/visibility", summary="设置动态可见性")
def set_post_visibility(
    post_id: int, req: PostVisibilityRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """隐藏或恢复一条动态。

    参数:
        post_id: 动态ID。
        req: is_visible=True 恢复，False 隐藏。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 {post_id, is_visible}。
    """
    post = db.get(Post, post_id)
    if post is None:
        raise NotFoundError("动态不存在")
    post.is_visible = bool(req.is_visible)
    db.commit()
    db.refresh(post)
    return ok({"post_id": post.id, "is_visible": bool(post.is_visible)})


# ---------------------------------------------------------------- 计划管理（只读）
@router.get("/plans", summary="计划管理列表")
def list_plans(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    keyword: str | None = Query(None, max_length=50, description="计划名称关键字"),
    goal: str | None = Query(None, max_length=30, description="按目标筛选"),
) -> dict[str, Any]:
    """分页查询用户训练计划（只读，含所属用户信息）。

    参数:
        params: 分页参数。
        keyword: 计划名称关键字。
        goal: 目标筛选。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[AdminPlanOut]。
    """
    stmt = select(Plan)
    if keyword and keyword.strip():
        stmt = stmt.where(Plan.name.like(f"%{keyword.strip()}%"))
    if goal:
        stmt = stmt.where(Plan.goal == goal)
    stmt = stmt.order_by(Plan.id.desc())
    rows, total = paginate(db, stmt, params)

    user_ids = list({plan.user_id for plan in rows})
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    items: list[AdminPlanOut] = []
    for plan in rows:
        out = AdminPlanOut.model_validate(plan)
        owner = users.get(plan.user_id)
        out.user_nickname = (owner.nickname or owner.username) if owner else None
        items.append(out)
    return ok(PageResult.build(items, total, params))


# ---------------------------------------------------------------- 实名认证
@router.get("/realnames", summary="实名认证申请列表")
def list_realnames(
    db: DbSession,
    admin: CurrentAdmin,
    params: PageParams = Depends(page_params),
    status: str | None = Query(None, pattern="^(pending|approved|rejected)$", description="审核状态"),
) -> dict[str, Any]:
    """分页查询实名认证申请。

    参数:
        params: 分页参数。
        status: 审核状态筛选。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为 PageResult[RealNameAuthOut]。
    """
    stmt = select(RealNameAuth)
    if status:
        stmt = stmt.where(RealNameAuth.status == status)
    stmt = stmt.order_by(RealNameAuth.created_at.desc(), RealNameAuth.id.desc())
    rows, total = paginate(db, stmt, params)

    user_ids = [auth.user_id for auth in rows]
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    items = [_realname_out(auth, users.get(auth.user_id)) for auth in rows]
    return ok(PageResult.build(items, total, params))


@router.post("/realname/{auth_id}/audit", summary="实名认证审核")
def audit_realname(
    auth_id: int, req: RealNameAuditRequest, db: DbSession, admin: CurrentAdmin
) -> dict[str, Any]:
    """审核实名认证申请：通过时把 user.is_verified 置为 True。

    参数:
        auth_id: 实名认证申请ID。
        req: action=approve|reject，驳回时 reject_reason 必填。
        db: 数据库会话。
        admin: 当前管理员。
    返回:
        统一响应，data 为审核后的 RealNameAuthOut。
    """
    auth = db.get(RealNameAuth, auth_id)
    if auth is None:
        raise NotFoundError("实名认证申请不存在")

    user = db.get(User, auth.user_id)
    if req.action == "approve":
        auth.status = "approved"
        auth.reject_reason = None
        if user is not None:
            user.is_verified = True
    else:
        reason = (req.reject_reason or "").strip()
        if not reason:
            raise BadRequestError("驳回时必须填写驳回原因")
        auth.status = "rejected"
        auth.reject_reason = reason[:200]
        if user is not None:
            user.is_verified = False

    auth.reviewed_at = datetime.now()
    db.commit()
    db.refresh(auth)
    return ok(_realname_out(auth, user))
