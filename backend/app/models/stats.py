"""数据统计模型：体重/体脂记录（BMI 由身高体重实时计算，不入库）。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin


class BodyMetric(Base, TimestampMixin):
    """身体数据记录（每人每天一条）。"""

    __tablename__ = "body_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "metric_date", name="uq_metric_user_date"),
        {"comment": "身体数据记录表"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True, nullable=False, comment="记录日期")
    weight: Mapped[float | None] = mapped_column(Float, comment="体重kg")
    body_fat: Mapped[float | None] = mapped_column(Float, comment="体脂率%")
    muscle_mass: Mapped[float | None] = mapped_column(Float, comment="肌肉量kg")
    waist: Mapped[float | None] = mapped_column(Float, comment="腰围cm")
    chest: Mapped[float | None] = mapped_column(Float, comment="胸围cm")
    hip: Mapped[float | None] = mapped_column(Float, comment="臀围cm")
    note: Mapped[str | None] = mapped_column(String(200), comment="备注")
