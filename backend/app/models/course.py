"""运动课程模型：分类、课程、收藏、评分、评论、评论点赞。"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class CourseCategory(Base, TimestampMixin):
    """课程分类：力量、有氧、拉伸、HIIT、瑜伽……"""

    __tablename__ = "course_categories"
    __table_args__ = {"comment": "课程分类表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="分类名称")
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="英文标识")
    icon: Mapped[str | None] = mapped_column(String(255), comment="分类图标")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")


class Course(Base, TimestampMixin):
    """课程：视频地址、难度、时长、消耗等。"""

    __tablename__ = "courses"
    __table_args__ = {"comment": "运动课程表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("course_categories.id"), index=True, comment="分类ID")
    title: Mapped[str] = mapped_column(String(120), nullable=False, comment="课程标题")
    subtitle: Mapped[str | None] = mapped_column(String(200), comment="副标题")
    cover: Mapped[str | None] = mapped_column(String(255), comment="封面图")
    video_url: Mapped[str | None] = mapped_column(String(500), comment="视频地址(m3u8/mp4)")
    duration_min: Mapped[int] = mapped_column(Integer, default=20, comment="时长(分钟)")
    calories: Mapped[int] = mapped_column(Integer, default=150, comment="预计消耗(千卡)")
    difficulty: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="难度 1初级 2中级 3高级")
    equipment: Mapped[str | None] = mapped_column(String(100), comment="所需器械")
    body_parts: Mapped[str | None] = mapped_column(String(100), comment="锻炼部位，逗号分隔")
    description: Mapped[str | None] = mapped_column(Text, comment="课程介绍")
    coach_name: Mapped[str | None] = mapped_column(String(50), comment="教练名")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="播放量")
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, comment="收藏数")
    rating_avg: Mapped[float] = mapped_column(Float, default=0, comment="平均评分")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, comment="评分人数")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="是否上架")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序权重")

    category: Mapped[CourseCategory] = relationship(lazy="joined")
    comments: Mapped[list["CourseComment"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseFavorite(Base, TimestampMixin):
    """课程收藏。"""

    __tablename__ = "course_favorites"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_course_fav"), {"comment": "课程收藏表"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)


class CourseRating(Base, TimestampMixin):
    """课程打分（1-5 星，每人每课程一条）。"""

    __tablename__ = "course_ratings"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_course_rating"), {"comment": "课程评分表"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 1-5")


class CourseComment(Base, TimestampMixin):
    """课程评论，支持一级回复（parent_id 指向父评论）。"""

    __tablename__ = "course_comments"
    __table_args__ = {"comment": "课程评论表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("course_comments.id", ondelete="CASCADE"), comment="父评论ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    like_count: Mapped[int] = mapped_column(Integer, default=0, comment="点赞数")
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True, comment="pending/approved/rejected 审核状态")

    course: Mapped[Course] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821


class CourseCommentLike(Base, TimestampMixin):
    """评论点赞。"""

    __tablename__ = "course_comment_likes"
    __table_args__ = (UniqueConstraint("user_id", "comment_id", name="uq_comment_like"), {"comment": "评论点赞表"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("course_comments.id", ondelete="CASCADE"), index=True)
