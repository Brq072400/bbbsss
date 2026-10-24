"""运动课程模块的 Pydantic 数据模型（Pydantic v2）。

约定：
- 入参模型统一以 ``Request`` 结尾，出参模型统一以 ``Out`` 结尾；
- 出参模型全部开启 ``from_attributes``，可直接由 ORM 对象 ``model_validate`` 得到；
- 课程详情不直接返回 ``video_url``，播放地址统一走 ``GET /courses/{id}/video``。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ================================================================ 出参：分类
class CourseCategoryOut(BaseModel):
    """课程分类（含该分类下的课程数）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(description="分类名称")
    slug: str = Field(description="英文标识")
    icon: str | None = Field(default=None, description="分类图标")
    sort_order: int = Field(default=0, description="排序")
    course_count: int = Field(default=0, description="该分类下已上架的课程数")


# ================================================================ 出参：课程
class CourseBriefOut(BaseModel):
    """课程简要信息（列表用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str = Field(description="课程标题")
    subtitle: str | None = Field(default=None, description="副标题")
    cover: str | None = Field(default=None, description="封面图")
    category_id: int = Field(description="分类ID")
    category_name: str | None = Field(default=None, description="分类名称")
    duration_min: int = Field(description="时长（分钟）")
    calories: int = Field(description="预计消耗（千卡）")
    difficulty: int = Field(description="难度 1初级 2中级 3高级")
    equipment: str | None = Field(default=None, description="所需器械")
    body_parts: str | None = Field(default=None, description="锻炼部位，逗号分隔")
    coach_name: str | None = Field(default=None, description="教练名")
    view_count: int = Field(default=0, description="播放量")
    favorite_count: int = Field(default=0, description="收藏数")
    comment_count: int = Field(default=0, description="已审核通过的评论数")
    rating_avg: float = Field(default=0.0, description="平均评分")
    rating_count: int = Field(default=0, description="评分人数")
    is_favorited: bool = Field(default=False, description="当前用户是否已收藏")
    created_at: datetime | None = Field(default=None, description="发布时间")


class CourseDetailOut(CourseBriefOut):
    """课程详情（含介绍、是否已收藏、我的评分）。"""

    description: str | None = Field(default=None, description="课程介绍")
    is_published: bool = Field(default=True, description="是否上架")
    sort_order: int = Field(default=0, description="排序权重")
    my_score: int | None = Field(default=None, description="我的评分 1-5，未评分则为空")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class CourseFavoriteOut(CourseBriefOut):
    """我收藏的课程（在课程信息上附加收藏时间）。"""

    favorited_at: datetime | None = Field(default=None, description="收藏时间")


# ================================================================ 出参：播放地址
class CourseVideoOut(BaseModel):
    """课程播放信息（出参）。"""

    course_id: int = Field(description="课程ID")
    title: str = Field(description="课程标题")
    video_url: str = Field(description="播放地址")
    duration_min: int = Field(description="课程时长（分钟）")
    expires_at: datetime = Field(description="播放地址过期时间（生产环境为签名地址有效期）")


# ================================================================ 入参 / 出参：评分
class CourseRatingRequest(BaseModel):
    """给课程打分（入参）。"""

    score: int = Field(..., ge=1, le=5, description="评分 1-5 星")


class CourseRatingOut(BaseModel):
    """课程评分结果（出参）。"""

    course_id: int = Field(description="课程ID")
    my_score: int | None = Field(default=None, description="我的评分，未评分则为空")
    rating_avg: float = Field(default=0.0, description="课程平均分")
    rating_count: int = Field(default=0, description="评分人数")


# ================================================================ 入参 / 出参：评论
class CourseCommentRequest(BaseModel):
    """发表评论 / 回复（入参）。"""

    content: str = Field(..., min_length=3, max_length=500, description="评论内容 3-500 字")
    parent_id: int | None = Field(default=None, ge=1, description="父评论ID，用于回复（只允许一层）")


class CommentReplyOut(BaseModel):
    """评论回复（单条）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int = Field(description="评论人ID")
    user_name: str | None = Field(default=None, description="评论人昵称")
    user_avatar: str | None = Field(default=None, description="评论人头像")
    parent_id: int | None = Field(default=None, description="父评论ID")
    content: str = Field(description="评论内容")
    like_count: int = Field(default=0, description="点赞数")
    liked: bool = Field(default=False, description="当前用户是否已点赞")
    created_at: datetime | None = Field(default=None, description="评论时间")


class CourseCommentOut(CommentReplyOut):
    """一级评论（出参，带最多 3 条回复与回复总数）。"""

    course_id: int = Field(description="课程ID")
    status: str = Field(default="approved", description="审核状态 pending/approved/rejected")
    replies: list[CommentReplyOut] = Field(default_factory=list, description="前 3 条回复")
    reply_count: int = Field(default=0, description="回复总数")


# ================================================================ 出参：通用结果
class CourseFavoriteResultOut(BaseModel):
    """课程收藏/取消收藏的结果。"""

    course_id: int
    is_favorited: bool = Field(description="操作后是否处于已收藏状态")
    favorite_count: int = Field(default=0, description="课程当前收藏数")


class CommentLikeResultOut(BaseModel):
    """评论点赞/取消点赞的结果。"""

    comment_id: int
    liked: bool = Field(description="操作后是否处于已点赞状态")
    like_count: int = Field(default=0, description="评论当前点赞数")


__all__ = [
    "CourseCategoryOut",
    "CourseBriefOut",
    "CourseDetailOut",
    "CourseFavoriteOut",
    "CourseVideoOut",
    "CourseRatingRequest",
    "CourseRatingOut",
    "CourseCommentRequest",
    "CommentReplyOut",
    "CourseCommentOut",
    "CourseFavoriteResultOut",
    "CommentLikeResultOut",
]
