"""社区模块的 Pydantic 数据模型（schema 层）。

约定：
- 所有入参统一命名 XxxRequest，出参统一命名 XxxOut；
- 出参都带 ``model_config = ConfigDict(from_attributes=True)``，可直接由 ORM 对象校验；
- 数据库里 ``Post.images`` 是「逗号分隔的字符串」，对外统一暴露成 ``list[str]``，
  由下面两个小工具函数负责转换，路由层只需调用它们。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.pagination import PageResult


# ---------------------------------------------------------------- 工具函数
def split_images(raw: str | None) -> list[str]:
    """把数据库里「逗号分隔」的图片字符串转成图片 URL 列表。

    参数:
        raw: Post.images 字段原始值，例如 "/a.jpg,/b.jpg"，可为 None。
    返回:
        图片 URL 列表，空值返回空列表。
    """
    if not raw:
        return []
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def join_images(images: list[str] | None) -> str | None:
    """把图片 URL 列表拼成「逗号分隔」字符串，用于写入 Post.images。

    参数:
        images: 前端传入的图片 URL 列表，可为 None。
    返回:
        逗号分隔字符串；列表为空时返回 None（数据库存 NULL）。
    """
    if not images:
        return None
    cleaned = [str(url).strip() for url in images if str(url).strip()]
    return ",".join(cleaned) or None


# ---------------------------------------------------------------- 作者 / 用户
class AuthorBrief(BaseModel):
    """动态、评论的作者简要信息（列表页只带这几个字段，避免暴露隐私）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    nickname: str | None = Field(default=None, description="昵称")
    display_name: str = Field(default="", description="展示名：昵称优先，其次用户名")
    avatar: str | None = Field(default=None, description="头像URL")
    level: int = Field(default=1, description="用户等级")


class UserCardOut(BaseModel):
    """用户卡片：粉丝/关注列表、搜索结果里的一项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    nickname: str | None = Field(default=None, description="昵称")
    display_name: str = Field(default="", description="展示名：昵称优先，其次用户名")
    avatar: str | None = Field(default=None, description="头像URL")
    signature: str | None = Field(default=None, description="个性签名")
    level: int = Field(default=1, description="用户等级")
    is_verified: bool = Field(default=False, description="是否已实名认证")
    is_following: bool = Field(default=False, description="当前登录用户是否已关注TA")


class UserProfileOut(UserCardOut):
    """用户主页：在用户卡片基础上追加动态数、粉丝数、关注数等统计。"""

    gender: int = Field(default=0, description="性别 0未知 1男 2女")
    city: str | None = Field(default=None, description="城市")
    points: int = Field(default=0, description="总积分")
    post_count: int = Field(default=0, description="动态数")
    follower_count: int = Field(default=0, description="粉丝数")
    following_count: int = Field(default=0, description="关注数")
    created_at: datetime | None = Field(default=None, description="注册时间")


# ---------------------------------------------------------------- 动态
class PostCreateRequest(BaseModel):
    """发布动态的入参。"""

    content: str = Field(min_length=1, max_length=2000, description="动态正文，1-2000 字")
    images: list[str] = Field(default_factory=list, max_length=9, description="图片URL列表，最多 9 张")
    topic: str | None = Field(default=None, max_length=50, description="话题标签，可选")
    location: str | None = Field(default=None, max_length=100, description="位置，可选")

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        """去掉正文首尾空白，并禁止「全是空格」的内容。"""
        text = (value or "").strip()
        if not text:
            raise ValueError("动态内容不能为空")
        return text

    @field_validator("topic", "location")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        """空字符串统一转成 None，避免入库出现空串。"""
        if value is None:
            return None
        text = value.strip()
        return text or None


class PostOut(BaseModel):
    """动态出参：列表与详情共用（详情使用子类 PostDetailOut）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="动态ID")
    user_id: int = Field(description="发布者用户ID")
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
    author: AuthorBrief | None = Field(default=None, description="作者信息")
    is_liked: bool = Field(default=False, description="当前登录用户是否已点赞")


class PostDetailOut(PostOut):
    """动态详情：额外告诉前端「我是否关注了作者」。"""

    is_followed: bool = Field(default=False, description="当前登录用户是否已关注作者")


class LikeResultOut(BaseModel):
    """点赞 / 取消点赞后的结果。"""

    post_id: int = Field(description="动态ID")
    like_count: int = Field(description="最新点赞数")
    is_liked: bool = Field(description="当前是否已点赞")


class FollowResultOut(BaseModel):
    """关注 / 取消关注后的结果。"""

    user_id: int = Field(description="被关注用户ID")
    is_following: bool = Field(description="当前是否已关注")
    follower_count: int = Field(default=0, description="被关注用户的最新粉丝数")


class FeedPageOut(PageResult[PostOut]):
    """关注流分页结果。

    ``empty=True`` 表示当前用户还没有关注任何人，此时 items 是「推荐动态」，
    前端可以据此展示「去关注更多人」的引导文案。
    """

    empty: bool = Field(default=False, description="是否因为未关注任何人而返回推荐动态")


# ---------------------------------------------------------------- 评论
class CommentCreateRequest(BaseModel):
    """发表评论 / 回复的入参。"""

    content: str = Field(min_length=1, max_length=500, description="评论内容，1-500 字")
    parent_id: int | None = Field(default=None, ge=1, description="父评论ID，回复时传")

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        """去掉首尾空白，禁止空评论。"""
        text = (value or "").strip()
        if not text:
            raise ValueError("评论内容不能为空")
        return text


class CommentReplyOut(BaseModel):
    """二级回复（挂在某条一级评论下面的回复）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="评论ID")
    post_id: int = Field(description="所属动态ID")
    parent_id: int | None = Field(default=None, description="父评论ID")
    user_id: int = Field(description="评论者用户ID")
    content: str = Field(description="评论内容")
    reply_to_user_id: int | None = Field(default=None, description="被回复的用户ID")
    reply_to_nickname: str | None = Field(default=None, description="被回复用户展示名，前端渲染 @某人")
    created_at: datetime | None = Field(default=None, description="评论时间")
    author: AuthorBrief | None = Field(default=None, description="评论者信息")


class CommentOut(CommentReplyOut):
    """一级评论：附带最多 3 条回复预览与回复总数。"""

    like_count: int = Field(default=0, description="点赞数")
    replies: list[CommentReplyOut] = Field(default_factory=list, description="最多 3 条回复")
    reply_count: int = Field(default=0, description="回复总数")


__all__ = [
    "AuthorBrief",
    "CommentCreateRequest",
    "CommentOut",
    "CommentReplyOut",
    "FeedPageOut",
    "FollowResultOut",
    "LikeResultOut",
    "PostCreateRequest",
    "PostDetailOut",
    "PostOut",
    "UserCardOut",
    "UserProfileOut",
    "join_images",
    "split_images",
]
