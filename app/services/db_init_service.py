"""
数据库初始化服务

在应用启动时：
1. 创建所有表（IF NOT EXISTS，通过 SQLAlchemy metadata.create_all）
2. 预置管理员账户（若不存在则创建）
"""
import uuid
from typing import Optional

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db.orm import UserORM
from app.db.session import create_all, get_engine, get_session_factory, init_db
from app.logger_mgr import get_logger

logger = get_logger("app.services.db_init_service")


async def ensure_database_ready(start_year: Optional[int] = None, end_year: Optional[int] = None) -> bool:
    """确保数据库已就绪：建表 + 预置管理员

    在应用启动时调用此函数。如果数据库连接失败或建表失败，将抛出异常阻止应用启动。

    Args:
        start_year: 保留参数（兼容旧调用，不再使用分表）
        end_year: 保留参数（兼容旧调用，不再使用分表）

    Returns:
        bool: 是否成功

    Raises:
        Exception: 数据库初始化失败时抛出
    """
    # 确保 engine 已初始化（兼容直接调用，如 run.py 主进程在 lifespan 之前调用）
    try:
        get_engine()
    except RuntimeError:
        init_db()

    # 1. 创建所有表（IF NOT EXISTS）
    logger.info("开始数据库初始化：创建表（IF NOT EXISTS）")
    await create_all()
    logger.info("数据库表就绪")

    # 2. 预置管理员账户
    await _ensure_admin_user()
    logger.info("数据库初始化完成")
    return True


async def _ensure_admin_user() -> None:
    """确保预置管理员账户存在（首次启动时创建）"""
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 检查管理员是否已存在
        result = await session.execute(
            select(UserORM).where(UserORM.username == settings.admin_username)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.debug(f"管理员账户 {settings.admin_username} 已存在，跳过创建")
            return

        # 创建管理员
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        admin = UserORM(
            id=user_id,
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            email=None,
            is_admin=True,
            status=1,
        )
        session.add(admin)
        await session.commit()
        logger.info(f"已创建预置管理员账户: {settings.admin_username} (id={user_id})")
