"""数据库引擎与会话管理。

- 生产环境使用 MySQL（pymysql 驱动），由 DATABASE_URL 指定；
- 本地演示默认回落到 SQLite，方便零配置启动；
- 提供 get_db() 依赖给所有路由使用，保证请求结束自动关闭会话。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.base import Base
from app.core.config import settings

# ---------- 引擎 ----------
if settings.is_sqlite:
    # SQLite 需要允许多线程访问（FastAPI 的线程池），并打开外键约束
    engine: Engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        """SQLite 默认不校验外键，这里手动打开，保证与 MySQL 行为一致。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        future=True,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=3600,
    )

# ---------- 会话工厂 ----------
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供一个数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """按模型定义创建所有表（开发/演示用；生产请使用 sql/schema_mysql.sql）。"""
    import app.models  # noqa: F401  确保所有模型已注册到 Base.metadata

    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "engine", "SessionLocal", "get_db", "init_db"]
