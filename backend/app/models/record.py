"""运动记录模型：一次训练的汇总记录 + 每个动作的组次明细。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class WorkoutRecord(Base, TimestampMixin):
    """一次完整的训练打卡记录。"""

    __tablename__ = "workout_records"
    __table_args__ = {"comment": "运动记录表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, comment="用户ID")
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), comment="关联计划")
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), comment="关联课程")
    workout_date: Mapped[date] = mapped_column(Date, index=True, nullable=False, comment="训练日期")
    workout_type: Mapped[str] = mapped_column(String(30), default="strength", comment="类型 strength/cardio/stretch/hiit/yoga")
    title: Mapped[str | None] = mapped_column(String(100), comment="本次训练标题")
    duration_min: Mapped[int] = mapped_column(Integer, default=0, comment="总时长(分钟)")
    calories: Mapped[float] = mapped_column(Float, default=0, comment="消耗卡路里")
    feeling: Mapped[int] = mapped_column(Integer, default=3, comment="主观强度 1-5")
    note: Mapped[str | None] = mapped_column(Text, comment="训练备注")

    sets: Mapped[list["WorkoutSet"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="WorkoutSet.sort_order"
    )


class WorkoutSet(Base, TimestampMixin):
    """动作明细：某动作第几组、重量、次数。"""

    __tablename__ = "workout_sets"
    __table_args__ = {"comment": "运动组次明细表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("workout_records.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), comment="动作ID")
    exercise_name: Mapped[str | None] = mapped_column(String(100), comment="动作名快照(动作被删也能显示)")
    sort_order: Mapped[int] = mapped_column(Integer, default=1, comment="动作顺序")
    set_index: Mapped[int] = mapped_column(Integer, default=1, comment="第几组")
    weight: Mapped[float] = mapped_column(Float, default=0, comment="重量kg")
    reps: Mapped[int] = mapped_column(Integer, default=0, comment="次数")
    duration_sec: Mapped[int | None] = mapped_column(Integer, comment="有氧/静力动作时长(秒)")
    distance_km: Mapped[float | None] = mapped_column(Float, comment="跑步距离(公里)")
    note: Mapped[str | None] = mapped_column(String(200), comment="备注")

    record: Mapped[WorkoutRecord] = relationship(back_populates="sets")
