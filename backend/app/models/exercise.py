"""动作库模型：动作分类与动作详情（配图、讲解、发力要点、易错提醒）。"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class ExerciseCategory(Base, TimestampMixin):
    """动作分类（按肌群/部位）。"""

    __tablename__ = "exercise_categories"
    __table_args__ = {"comment": "动作分类表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="分类名称")
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="英文标识")
    body_part: Mapped[str | None] = mapped_column(String(30), comment="主要部位 胸/背/腿/肩/手臂/核心/全身")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")


class Exercise(Base, TimestampMixin):
    """动作库条目。"""

    __tablename__ = "exercises"
    __table_args__ = {"comment": "动作库表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("exercise_categories.id"), index=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="动作名称")
    name_en: Mapped[str | None] = mapped_column(String(100), comment="英文名/别名，供搜索")
    equipment: Mapped[str | None] = mapped_column(String(50), comment="器械 杠铃/哑铃/自重/弹力带/器械")
    difficulty: Mapped[int] = mapped_column(Integer, default=1, index=True, comment="难度 1-5")
    image_url: Mapped[str | None] = mapped_column(String(255), comment="动作配图")
    gif_url: Mapped[str | None] = mapped_column(String(255), comment="动作动图/视频")
    description: Mapped[str | None] = mapped_column(Text, comment="动作讲解")
    key_points: Mapped[str | None] = mapped_column(Text, comment="发力要点")
    common_mistakes: Mapped[str | None] = mapped_column(Text, comment="易错提醒")
    primary_muscles: Mapped[str | None] = mapped_column(String(120), comment="主要发力肌群")
    secondary_muscles: Mapped[str | None] = mapped_column(String(120), comment="协同肌群")
    tips: Mapped[str | None] = mapped_column(Text, comment="呼吸与节奏提示")
    keywords: Mapped[str | None] = mapped_column(String(255), comment="搜索关键词，逗号分隔")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览数")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, comment="是否启用")

    category: Mapped[ExerciseCategory] = relationship(lazy="joined")
