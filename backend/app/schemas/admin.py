"""后台管理模块的 Pydantic 数据模型（schema 层）。

覆盖：管理员登录/资料、数据看板、用户管理、课程管理、评论审核、
动态管理、计划管理（只读）、实名认证审核。
"""
from __future__ import annotations

# 注意：下面三个模型里有名为 date 的字段，为避免「字段名与类型名撞车」，
# 日期类型统一用 _dt.date 的写法。
import datetime as _dt
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 评论审核动作与实名审核动作共用
AuditAction = Literal["approve", "reject"]


# ---------------------------------------------------------------- 管理员
class AdminLoginRequest(BaseModel):
    """管理员登录入参。"""

    username: str = Field(min_length=1, max_length=50, description="管理员用户名")
    password: str = Field(min_length=1, max_length=64, description="密码")

    @field_validator("username")
    @classmethod
    def _strip_username(cls, value: str) -> str:
        """用户名去首尾空白。"""
        return (value or "").strip()


class AdminOut(BaseModel):
    """管理员信息出参（不含密码哈希）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="管理员ID")
    username: str = Field(description="登录名")
    real_name: str | None = Field(default=None, description="真实姓名")
    role: str = Field(default="admin", description="角色 super/admin")
    is_active: bool = Field(default=True, description="是否启用")
    last_login_at: datetime | None = Field(default=None, description="最后登录时间")
    created_at: datetime | None = Field(default=None, description="创建时间")


class AdminLoginOut(BaseModel):
    """管理员登录出参：令牌 + 管理员信息。"""

    token: str = Field(description="访问令牌，前端放 Authorization: Bearer <token>")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=0, description="过期时间（秒）")
    admin: AdminOut = Field(description="当前管理员信息")


# ---------------------------------------------------------------- 数据看板
class DailyCountOut(BaseModel):
    """看板趋势数组里的一天：日期 + 数量。"""

    date: _dt.date = Field(description="日期")
    count: int = Field(default=0, description="当天数量")


class DashboardOut(BaseModel):
    """数据看板出参。"""

    total_users: int = Field(default=0, description="用户总数")
    today_new_users: int = Field(default=0, description="今日新增用户")
    total_courses: int = Field(default=0, description="课程总数")
    total_posts: int = Field(default=0, description="动态总数")
    total_plans: int = Field(default=0, description="训练计划总数")
    total_comments: int = Field(default=0, description="课程评论总数")
    pending_comments: int = Field(default=0, description="待审核评论数")
    today_checkins: int = Field(default=0, description="今日签到数")
    new_users_7d: list[DailyCountOut] = Field(default_factory=list, description="近 7 天新增用户数组")
    new_posts_7d: list[DailyCountOut] = Field(default_factory=list, description="近 7 天新增动态数组")


# ---------------------------------------------------------------- 用户管理
class AdminUserOut(BaseModel):
    """后台用户列表/详情出参（含签到次数、动态数）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    nickname: str | None = Field(default=None, description="昵称")
    avatar: str | None = Field(default=None, description="头像URL")
    phone: str | None = Field(default=None, description="手机号")
    email: str | None = Field(default=None, description="邮箱")
    gender: int = Field(default=0, description="性别 0未知 1男 2女")
    level: int = Field(default=1, description="用户等级")
    points: int = Field(default=0, description="总积分")
    is_verified: bool = Field(default=False, description="是否已实名认证")
    is_disabled: bool = Field(default=False, description="是否被封禁")
    created_at: datetime | None = Field(default=None, description="注册时间")
    checkin_count: int = Field(default=0, description="累计签到次数")
    post_count: int = Field(default=0, description="动态数")


class AdminUserUpdateRequest(BaseModel):
    """后台修改用户资料的入参：所有字段可选。"""

    nickname: str | None = Field(default=None, max_length=50, description="昵称")
    phone: str | None = Field(default=None, max_length=20, description="手机号")
    email: str | None = Field(default=None, max_length=120, description="邮箱")
    level: int | None = Field(default=None, ge=1, le=10, description="等级 1-10")
    points: int | None = Field(default=None, ge=0, description="总积分")
    is_disabled: bool | None = Field(default=None, description="是否禁用（封禁）")


class UserDisableRequest(BaseModel):
    """封禁 / 解封入参。"""

    disabled: bool = Field(description="True 封禁，False 解封")


class ResetPasswordRequest(BaseModel):
    """后台重置用户密码入参。"""

    new_password: str = Field(min_length=6, max_length=64, description="新密码，6-64 位")


# ---------------------------------------------------------------- 课程管理
class CourseCreateRequest(BaseModel):
    """后台新增课程入参。"""

    category_id: int = Field(ge=1, description="课程分类ID")
    title: str = Field(min_length=1, max_length=120, description="课程标题")
    subtitle: str | None = Field(default=None, max_length=200, description="副标题")
    cover: str | None = Field(default=None, max_length=255, description="封面图URL")
    video_url: str | None = Field(default=None, max_length=500, description="视频地址")
    duration_min: int = Field(default=20, ge=1, le=600, description="时长(分钟)")
    calories: int = Field(default=150, ge=0, le=5000, description="预计消耗(千卡)")
    difficulty: int = Field(default=1, ge=1, le=3, description="难度 1初级 2中级 3高级")
    equipment: str | None = Field(default=None, max_length=100, description="所需器械")
    body_parts: str | None = Field(default=None, max_length=100, description="锻炼部位，逗号分隔")
    description: str | None = Field(default=None, description="课程介绍")
    coach_name: str | None = Field(default=None, max_length=50, description="教练名")
    sort_order: int = Field(default=0, description="排序权重")

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        """标题去首尾空白，不允许空标题。"""
        text = (value or "").strip()
        if not text:
            raise ValueError("课程标题不能为空")
        return text


class CourseUpdateRequest(BaseModel):
    """后台编辑课程入参：所有字段可选，只改传入的字段。"""

    category_id: int | None = Field(default=None, ge=1, description="课程分类ID")
    title: str | None = Field(default=None, min_length=1, max_length=120, description="课程标题")
    subtitle: str | None = Field(default=None, max_length=200, description="副标题")
    cover: str | None = Field(default=None, max_length=255, description="封面图URL")
    video_url: str | None = Field(default=None, max_length=500, description="视频地址")
    duration_min: int | None = Field(default=None, ge=1, le=600, description="时长(分钟)")
    calories: int | None = Field(default=None, ge=0, le=5000, description="预计消耗(千卡)")
    difficulty: int | None = Field(default=None, ge=1, le=3, description="难度 1-3")
    equipment: str | None = Field(default=None, max_length=100, description="所需器械")
    body_parts: str | None = Field(default=None, max_length=100, description="锻炼部位")
    description: str | None = Field(default=None, description="课程介绍")
    coach_name: str | None = Field(default=None, max_length=50, description="教练名")
    sort_order: int | None = Field(default=None, description="排序权重")
    is_published: bool | None = Field(default=None, description="是否上架")


class CoursePublishRequest(BaseModel):
    """课程上架 / 下架入参。"""

    is_published: bool = Field(description="True 上架，False 下架")


class AdminCourseOut(BaseModel):
    """后台课程出参（含未上架课程）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="课程ID")
    category_id: int = Field(description="分类ID")
    category_name: str | None = Field(default=None, description="分类名称")
    title: str = Field(description="课程标题")
    subtitle: str | None = Field(default=None, description="副标题")
    cover: str | None = Field(default=None, description="封面图")
    video_url: str | None = Field(default=None, description="视频地址")
    duration_min: int = Field(default=20, description="时长(分钟)")
    calories: int = Field(default=150, description="预计消耗(千卡)")
    difficulty: int = Field(default=1, description="难度")
    equipment: str | None = Field(default=None, description="所需器械")
    body_parts: str | None = Field(default=None, description="锻炼部位")
    description: str | None = Field(default=None, description="课程介绍")
    coach_name: str | None = Field(default=None, description="教练名")
    view_count: int = Field(default=0, description="播放量")
    favorite_count: int = Field(default=0, description="收藏数")
    rating_avg: float = Field(default=0, description="平均评分")
    rating_count: int = Field(default=0, description="评分人数")
    is_published: bool = Field(default=True, description="是否上架")
    sort_order: int = Field(default=0, description="排序权重")
    created_at: datetime | None = Field(default=None, description="创建时间")


# ---------------------------------------------------------------- 评论审核
class CommentAuditRequest(BaseModel):
    """评论审核入参。"""

    action: AuditAction = Field(description="approve 通过 / reject 驳回")


class AdminCommentOut(BaseModel):
    """后台评论出参（带课程标题与用户昵称，方便运营审核）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="评论ID")
    course_id: int = Field(description="课程ID")
    course_title: str | None = Field(default=None, description="课程标题")
    user_id: int = Field(description="评论者用户ID")
    user_nickname: str | None = Field(default=None, description="评论者昵称")
    parent_id: int | None = Field(default=None, description="父评论ID")
    content: str = Field(description="评论内容")
    like_count: int = Field(default=0, description="点赞数")
    status: str = Field(default="approved", description="pending/approved/rejected")
    created_at: datetime | None = Field(default=None, description="评论时间")


# ---------------------------------------------------------------- 动态管理
class PostVisibilityRequest(BaseModel):
    """设置动态可见性入参。"""

    is_visible: bool = Field(description="True 恢复可见，False 隐藏")


class AdminPostOut(BaseModel):
    """后台动态出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="动态ID")
    user_id: int = Field(description="发布者ID")
    user_nickname: str | None = Field(default=None, description="发布者昵称")
    content: str = Field(description="正文")
    images: list[str] = Field(default_factory=list, description="图片URL数组")
    topic: str | None = Field(default=None, description="话题标签")
    location: str | None = Field(default=None, description="位置")
    like_count: int = Field(default=0, description="点赞数")
    comment_count: int = Field(default=0, description="评论数")
    view_count: int = Field(default=0, description="浏览数")
    is_top: bool = Field(default=False, description="是否置顶")
    is_visible: bool = Field(default=True, description="是否可见")
    created_at: datetime | None = Field(default=None, description="发布时间")


# ---------------------------------------------------------------- 计划管理（只读）
class AdminPlanOut(BaseModel):
    """后台计划出参（只读，含所属用户信息）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="计划ID")
    user_id: int = Field(description="所属用户ID")
    user_nickname: str | None = Field(default=None, description="所属用户昵称")
    name: str = Field(description="计划名称")
    description: str | None = Field(default=None, description="计划说明")
    goal: str = Field(default="keep_fit", description="目标")
    cycle_type: str = Field(default="weekly", description="周期类型")
    cycle_days: int = Field(default=7, description="周期天数")
    cover: str | None = Field(default=None, description="封面图")
    is_public: bool = Field(default=False, description="是否公开")
    is_template: bool = Field(default=False, description="是否模板")
    favorite_count: int = Field(default=0, description="被收藏次数")
    status: str = Field(default="active", description="active/archived")
    created_at: datetime | None = Field(default=None, description="创建时间")


# ---------------------------------------------------------------- 实名认证
class RealNameAuditRequest(BaseModel):
    """实名认证审核入参。"""

    action: AuditAction = Field(description="approve 通过 / reject 驳回")
    reject_reason: str | None = Field(default=None, max_length=200, description="驳回原因，驳回时必填")


class RealNameAuthOut(BaseModel):
    """实名认证申请出参。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="申请ID")
    user_id: int = Field(description="用户ID")
    username: str | None = Field(default=None, description="用户名")
    nickname: str | None = Field(default=None, description="昵称")
    real_name: str = Field(description="真实姓名")
    id_card: str = Field(description="身份证号（已脱敏）")
    status: str = Field(default="pending", description="pending/approved/rejected")
    reject_reason: str | None = Field(default=None, description="驳回原因")
    reviewed_at: datetime | None = Field(default=None, description="审核时间")
    created_at: datetime | None = Field(default=None, description="提交时间")


__all__ = [
    "AdminCommentOut",
    "AdminCourseOut",
    "AdminLoginOut",
    "AdminLoginRequest",
    "AdminOut",
    "AdminPlanOut",
    "AdminPostOut",
    "AdminUserOut",
    "AdminUserUpdateRequest",
    "AuditAction",
    "CommentAuditRequest",
    "CourseCreateRequest",
    "CoursePublishRequest",
    "CourseUpdateRequest",
    "DailyCountOut",
    "DashboardOut",
    "PostVisibilityRequest",
    "RealNameAuditRequest",
    "RealNameAuthOut",
    "ResetPasswordRequest",
    "UserDisableRequest",
]
