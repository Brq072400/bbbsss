"""SQLAlchemy 声明式基类与公共字段混入。

所有模型继承 Base，并复用 TimestampMixin（创建/更新时间），
保证每张表都有统一的时间字段。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """全局声明式基类。"""

    # 允许使用 dataclass 风格的 Mapped[] 注解
    __abstract__ = True


class TimestampMixin:
    """给模型加上创建时间与更新时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
        comment="更新时间",
    )


class PKMixin:
    """自增主键。"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
