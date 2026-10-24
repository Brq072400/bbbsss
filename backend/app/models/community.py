"""社区模块模型：动态、图片、点赞、评论、关注关系。"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class Post(Base, TimestampMixin):
    """社区动态（文字 + 图片）。"""

    __tablename__ = "posts"
    __table_args__ = {"comment": "社区动态表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="发布者")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文字内容")
    images: Mapped[str | None] = mapped_column(Text, comment="图片URL，逗号分隔")
    topic: Mapped[str | None] = mapped_column(String(50), comment="话题标签")
    location: Mapped[str | None] = mapped_column(String(100), comment="位置")
    workout_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("workout_records.id", ondelete="SET NULL"), comment="关联训练记录"
    )
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, comment="评论数")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览数")
    is_top: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否置顶")
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可见(管理员可隐藏)")

    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821
    comments: Mapped[list["PostComment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class PostLike(Base, TimestampMixin):
    """动态点赞。"""

    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_post_like"), {"comment": "动态点赞表"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)


class PostComment(Base, TimestampMixin):
    """动态评论，支持回复。"""

    __tablename__ = "post_comments"
    __table_args__ = {"comment": "动态评论表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("post_comments.id", ondelete="CASCADE"), comment="父评论")
    reply_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), comment="回复谁")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")

    post: Mapped[Post] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")  # noqa: F821


class Follow(Base, TimestampMixin):
    """关注关系：follower 关注 following。"""

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follow"),
        {"comment": "关注关系表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="关注者")
    following_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="被关注者")
