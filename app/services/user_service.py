"""
用户服务 - 用户相关业务逻辑

提供用户的查询、创建、更新等操作
使用 SQLAlchemy 2.0 async 直连 PostgreSQL
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_current_time
from app.db.orm import UserORM
from app.models.user import User


class UserService:
    """用户服务类

    使用 SQLAlchemy AsyncSession 进行数据库操作。
    """

    def __init__(self, session: AsyncSession):
        """初始化用户服务

        Args:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        通过ID查询用户

        Args:
            user_id: 用户ID

        Returns:
            User: 用户对象，不存在返回 None
        """
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        user = User.model_validate(orm)
        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        通过用户名查询用户

        Args:
            username: 用户名

        Returns:
            User: 用户对象，不存在返回 None
        """
        result = await self.session.execute(select(UserORM).where(UserORM.username == username))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        user = User.model_validate(orm)
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        通过邮箱查询用户

        Args:
            email: 用户邮箱

        Returns:
            User: 用户对象，不存在返回 None
        """
        result = await self.session.execute(select(UserORM).where(UserORM.email == email))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        user = User.model_validate(orm)
        return user

    async def create_user(self, user_data: dict) -> User:
        """
        创建用户

        Args:
            user_data: 用户数据字典，包含:
                - id: 用户ID（可选，不提供则自动生成）
                - username: 用户名
                - password_hash: 密码哈希
                - email: 用户邮箱（可选）
                - is_admin: 是否管理员（可选，默认为 False）
                - status: 用户状态（可选，默认为1）

        Returns:
            User: 创建的用户对象

        Raises:
            ValueError: 创建失败时抛出异常
        """
        # 生成用户ID（如果未提供）
        if "id" not in user_data:
            user_data["id"] = f"user_{uuid.uuid4().hex[:8]}"

        orm = UserORM(
            id=user_data["id"],
            username=user_data.get("username", ""),
            password_hash=user_data.get("password_hash", ""),
            email=user_data.get("email"),
            is_admin=user_data.get("is_admin", False),
            status=user_data.get("status", 1),
        )
        self.session.add(orm)
        await self.session.commit()
        await self.session.refresh(orm)

        user = User.model_validate(orm)
        return user

    async def update_user(self, user_id: str, user_data: dict) -> Optional[User]:
        """
        更新用户信息

        Args:
            user_id: 用户ID
            user_data: 要更新的用户数据字典

        Returns:
            User: 更新后的用户对象，用户不存在返回 None
        """
        # 加载用户
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 更新属性（排除不可更新字段）
        for key, value in user_data.items():
            if key not in ("id", "created_at"):
                setattr(orm, key, value)
        orm.updated_at = get_current_time()

        await self.session.commit()
        await self.session.refresh(orm)

        user = User.model_validate(orm)
        return user

    async def update_user_status(self, user_id: str, status: int) -> Optional[User]:
        """
        更新用户状态

        Args:
            user_id: 用户ID
            status: 用户状态值（1=正常, 0=禁用等）

        Returns:
            User: 更新后的用户对象，用户不存在返回 None
        """
        user = await self.update_user(user_id, {"status": status})
        return user
