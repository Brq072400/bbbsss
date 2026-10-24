"""运动计划模块模型：用户计划、计划动作、模板库、分享、收藏、打卡、提醒。"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class Plan(Base, TimestampMixin):
    """用户自建训练计划。"""

    __tablename__ = "plans"
    __table_args__ = {"comment": "训练计划表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="所属用户")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="计划名称")
    description: Mapped[str | None] = mapped_column(Text, comment="计划说明")
    goal: Mapped[str] = mapped_column(String(30), default="keep_fit", comment="目标 增肌/减脂/塑形/康复/keep_fit")
    cycle_type: Mapped[str] = mapped_column(String(20), default="weekly", comment="周期类型 daily/weekly")
    cycle_days: Mapped[int] = mapped_column(Integer, default=7, comment="一个周期天数")
    cover: Mapped[str | None] = mapped_column(String(255), comment="封面图")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否公开分享")
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否另存为模板")
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, comment="被收藏次数")
    status: Mapped[str] = mapped_column(String(20), default="active", comment="active/archived")

    items: Mapped[list["PlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanItem.sort_order"
    )
    checkins: Mapped[list["PlanCheckin"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class PlanItem(Base, TimestampMixin):
    """计划中的一条训练安排（第几天做什么动作，做几组几次）。"""

    __tablename__ = "plan_items"
    __table_args__ = {"comment": "计划动作明细表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), comment="动作ID")
    day_index: Mapped[int] = mapped_column(Integer, default=1, comment="周期内第几天，从 1 开始")
    sort_order: Mapped[int] = mapped_column(Integer, default=1, comment="当天排序")
    sets: Mapped[int] = mapped_column(Integer, default=3, comment="组数")
    reps: Mapped[int] = mapped_column(Integer, default=12, comment="每组次数")
    weight: Mapped[float | None] = mapped_column(comment="建议重量kg")
    rest_seconds: Mapped[int] = mapped_column(Integer, default=60, comment="组间休息秒数")
    duration_min: Mapped[int | None] = mapped_column(Integer, comment="有氧时长分钟")
    note: Mapped[str | None] = mapped_column(String(200), comment="备注")

    plan: Mapped[Plan] = relationship(back_populates="items")
    exercise: Mapped["Exercise | None"] = relationship(lazy="joined")  # noqa: F821


class PlanTemplate(Base, TimestampMixin):
    """官方/用户贡献的计划模板（模板库）。"""

    __tablename__ = "plan_templates"
    __table_args__ = {"comment": "计划模板库"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称")
    category: Mapped[str] = mapped_column(String(30), default="general", comment="分类 减脂/增肌/HIIT/新手")
    goal: Mapped[str] = mapped_column(String(30), default="keep_fit", comment="目标")
    difficulty: Mapped[int] = mapped_column(Integer, default=1, comment="难度 1-5")
    cycle_type: Mapped[str] = mapped_column(String(20), default="weekly", comment="daily/weekly")
    cycle_days: Mapped[int] = mapped_column(Integer, default=7, comment="周期天数")
    cover: Mapped[str | None] = mapped_column(String(255), comment="封面")
    description: Mapped[str | None] = mapped_column(Text, comment="模板说明")
    items_json: Mapped[str | None] = mapped_column(Text, comment="模板动作明细(JSON)，轻量存储避免多表")
    use_count: Mapped[int] = mapped_column(Integer, default=0, comment="被使用次数")
    is_official: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否官方模板")


class PlanShare(Base, TimestampMixin):
    """计划分享记录（生成分享码，可设置有效期）。"""

    __tablename__ = "plan_shares"
    __table_args__ = {"comment": "计划分享表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    share_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, comment="分享码")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="过期时间，空表示永久")
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="被查看次数")


class PlanFavorite(Base, TimestampMixin):
    """用户收藏的计划。"""

    __tablename__ = "plan_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "plan_id", name="uq_plan_fav"),
        {"comment": "计划收藏表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)


class PlanCheckin(Base, TimestampMixin):
    """计划打卡：某天某个计划是否完成。"""

    __tablename__ = "plan_checkins"
    __table_args__ = (
        UniqueConstraint("user_id", "plan_id", "checkin_date", name="uq_plan_checkin"),
        {"comment": "计划打卡表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    checkin_date: Mapped[date] = mapped_column(Date, index=True, nullable=False, comment="打卡日期")
    day_index: Mapped[int] = mapped_column(Integer, default=1, comment="完成的是周期第几天")
    completed: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否完成")
    note: Mapped[str | None] = mapped_column(String(200), comment="打卡备注")

    plan: Mapped[Plan] = relationship(back_populates="checkins")


class PlanReminder(Base, TimestampMixin):
    """计划提醒设置。"""

    __tablename__ = "plan_reminders"
    __table_args__ = {"comment": "计划提醒表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    remind_time: Mapped[time] = mapped_column(Time, nullable=False, comment="每天提醒时间")
    weekdays: Mapped[str] = mapped_column(String(20), default="1,2,3,4,5,6,7", comment="周几提醒，逗号分隔")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, comment="上次触发时间")
