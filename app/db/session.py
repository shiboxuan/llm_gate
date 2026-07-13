"""
SQLAlchemy 异步数据库会话管理

提供 async engine、AsyncSession 工厂和 FastAPI 依赖注入函数。
应用启动时调用 init_db()，关闭时调用 close_db()。
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.orm import Base

_engine = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """获取全局 engine（未初始化时抛异常）"""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 session 工厂（未初始化时抛异常）"""
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database session factory not initialized. Call init_db() first.")
    return _AsyncSessionLocal


def init_db() -> None:
    """初始化数据库 engine 和 session 工厂（应用启动时调用一次）"""
    global _engine, _AsyncSessionLocal
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    _AsyncSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def create_all() -> None:
    """创建所有表（IF NOT EXISTS）"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库 engine（应用关闭时调用）"""
    global _engine, _AsyncSessionLocal
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _AsyncSessionLocal = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供数据库会话，请求结束自动关闭"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
