"""饮食模块模型：常用食物库 + 每日饮食记录。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin


class Food(Base, TimestampMixin):
    """常用食物库（每 100 克营养数据）。"""

    __tablename__ = "foods"
    __table_args__ = {"comment": "食物库表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="食物名称")
    category: Mapped[str] = mapped_column(String(30), default="others", index=True, comment="分类 主食/肉蛋/蔬菜/水果/乳品/零食")
    unit: Mapped[str] = mapped_column(String(20), default="100g", comment="计量单位描述")
    calories: Mapped[float] = mapped_column(Float, default=0, comment="每100g热量(千卡)")
    protein: Mapped[float] = mapped_column(Float, default=0, comment="蛋白质g")
    fat: Mapped[float] = mapped_column(Float, default=0, comment="脂肪g")
    carbohydrate: Mapped[float] = mapped_column(Float, default=0, comment="碳水g")
    fiber: Mapped[float] = mapped_column(Float, default=0, comment="膳食纤维g")
    sodium: Mapped[float] = mapped_column(Float, default=0, comment="钠mg")
    is_common: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否常用(前端快捷选择)")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), comment="自定义食物创建者")


class DietRecord(Base, TimestampMixin):
    """一条饮食记录。"""

    __tablename__ = "diet_records"
    __table_args__ = {"comment": "饮食记录表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    diet_date: Mapped[date] = mapped_column(Date, index=True, nullable=False, comment="日期")
    meal_type: Mapped[str] = mapped_column(String(20), default="breakfast", comment="breakfast/lunch/dinner/snack")
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"), comment="食物ID")
    food_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="食物名称快照")
    amount_g: Mapped[float] = mapped_column(Float, default=100, comment="食用量(克)")
    calories: Mapped[float] = mapped_column(Float, default=0, comment="本次摄入热量(千卡)")
    protein: Mapped[float] = mapped_column(Float, default=0, comment="蛋白质g")
    fat: Mapped[float] = mapped_column(Float, default=0, comment="脂肪g")
    carbohydrate: Mapped[float] = mapped_column(Float, default=0, comment="碳水g")
    note: Mapped[str | None] = mapped_column(String(200), comment="备注")

    food: Mapped[Food | None] = relationship(lazy="joined")
