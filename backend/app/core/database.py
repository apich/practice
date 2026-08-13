"""异步 SQLAlchemy 引擎、会话工厂与 declarative base.

基于 SQLAlchemy 2.0 异步 ORM，提供：
- Base: 所有 ORM 模型的 declarative base
- AsyncEngine / AsyncSession 工厂
- FastAPI 依赖注入 (get_db)
- 表创建 (create_tables)

默认使用 SQLite（零配置开发），生产环境通过 DATABASE_URL 环境变量
切换到 PostgreSQL（asyncpg 驱动）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.core.config import Settings


# ===== Declarative Base =====


class Base(DeclarativeBase):
    """Declarative base for all ORM models in the platform."""

    pass


# ===== 全局引擎与会话工厂（延迟初始化）=====
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    """创建异步数据库引擎.

    Args:
        settings: 应用配置

    Returns:
        AsyncEngine 实例
    """
    url = settings.effective_database_url

    # SQLite 不支持 pool_size / max_overflow / pool_recycle 参数
    if url.startswith("sqlite"):
        return create_async_engine(
            url,
            echo=settings.database_echo,
        )

    return create_async_engine(
        url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=True,
    )


def init_db(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """初始化数据库引擎与会话工厂.

    应在应用启动时调用一次。

    Args:
        settings: 应用配置（为 None 时自动获取全局单例）

    Returns:
        异步会话工厂
    """
    global _engine, _session_factory

    if settings is None:
        settings = get_settings()

    _engine = create_engine(settings)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _session_factory


def get_engine() -> AsyncEngine:
    """获取全局数据库引擎.

    Raises:
        RuntimeError: 引擎未初始化
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取全局会话工厂.

    Raises:
        RuntimeError: 会话工厂未初始化
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call init_db() first."
        )
    return _session_factory


# 保留向后兼容的别名
async_session_factory = None  # type: ignore[assignment]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话.

    自动管理会话生命周期，请求结束自动关闭。

    用法::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """关闭数据库引擎，释放连接池.

    应在应用关闭时调用。
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None


async def create_tables() -> None:
    """创建所有已注册的表（开发环境用）.

    生产环境应使用 Alembic 迁移。导入所有模型模块以确保
    它们的表注册到 Base.metadata 上。
    """
    from app.auth import models as _auth_models  # noqa: F401
    from app.publish import models as _publish_models  # noqa: F401

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
