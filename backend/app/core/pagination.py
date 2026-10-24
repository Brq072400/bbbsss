"""分页工具：统一分页参数与分页结果结构。"""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class PageParams(BaseModel):
    """通用分页查询参数。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数，最大 100")

    @property
    def offset(self) -> int:
        """计算 SQL OFFSET。"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """计算 SQL LIMIT。"""
        return self.page_size


def page_params(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
) -> PageParams:
    """FastAPI 依赖：把 query 参数转成 PageParams。"""
    return PageParams(page=page, page_size=page_size)


class PageResult(BaseModel, Generic[T]):
    """分页返回结构。"""

    items: list[T] = Field(default_factory=list, description="当前页数据")
    total: int = Field(default=0, description="总条数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页条数")
    pages: int = Field(default=0, description="总页数")

    @classmethod
    def build(cls, items: Sequence[Any], total: int, params: PageParams) -> "PageResult[T]":
        """根据查询结果构造分页对象。"""
        pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
        return cls(items=list(items), total=total, page=params.page, page_size=params.page_size, pages=pages)


def paginate(db: Session, stmt: Select, params: PageParams) -> tuple[list[Any], int]:
    """执行分页查询，返回 (当前页记录, 总数)。"""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.offset(params.offset).limit(params.limit)).all()
    return list(rows), int(total)
