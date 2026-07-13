"""
Provider Key 服务 - 密钥管理业务逻辑

提供 Provider Key 的创建、查询、删除和加解密功能
使用 SQLAlchemy 2.0 async 直连 PostgreSQL
"""
from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import encrypt_api_key, decrypt_api_key
from app.db.orm import ProviderKeyORM
from app.models.provider_key import ProviderKey


class ProviderKeyService:
    """Provider Key 服务类

    使用 SQLAlchemy AsyncSession 进行数据库操作。
    """

    def __init__(self, session: AsyncSession):
        """初始化 Provider Key 服务

        Args:
            session: SQLAlchemy 异步会话
        """
        self.settings = get_settings()
        self.session = session

    async def create_provider_key(self, user_id: str, key_data: dict) -> ProviderKey:
        """
        创建 Provider Key（AES 加密存储）

        Args:
            user_id: 用户ID
            key_data: 密钥数据字典，包含:
                - name: 密钥名称（同时代表供应商）
                - api_key: API密钥明文
                - status: 状态（可选，默认为1）

        Returns:
            ProviderKey: 创建的密钥对象

        Raises:
            ValueError: 创建失败时抛出异常
        """
        # 加密 API Key
        encrypted_key = encrypt_api_key(key_data["api_key"], self.settings.aes_secret_key)

        orm = ProviderKeyORM(
            user_id=user_id,
            name=key_data.get("name", ""),
            api_key_encrypted=encrypted_key,
            status=key_data.get("status", 1),
        )
        self.session.add(orm)
        await self.session.commit()
        await self.session.refresh(orm)

        provider_key = ProviderKey.model_validate(orm)
        return provider_key

    async def get_provider_keys_by_user(self, user_id: str) -> List[ProviderKey]:
        """
        获取用户所有密钥

        Args:
            user_id: 用户ID

        Returns:
            List[ProviderKey]: 密钥列表
        """
        result = await self.session.execute(select(ProviderKeyORM).where(ProviderKeyORM.user_id == user_id))
        orm_list = result.scalars().all()
        keys = []
        for orm in orm_list:
            key = ProviderKey.model_validate(orm)
            keys.append(key)
        return keys

    async def get_provider_key_by_id(self, key_id: int) -> Optional[ProviderKey]:
        """
        通过ID获取密钥

        Args:
            key_id: 密钥ID

        Returns:
            ProviderKey: 密钥对象，不存在返回 None
        """
        result = await self.session.execute(select(ProviderKeyORM).where(ProviderKeyORM.id == key_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        provider_key = ProviderKey.model_validate(orm)
        return provider_key

    async def get_provider_key_by_name(self, user_id: str, name: str) -> Optional[ProviderKey]:
        """
        按名称获取密钥（同一用户下 name 唯一）

        Args:
            user_id: 用户ID
            name: 密钥名称（同时代表供应商）

        Returns:
            ProviderKey: 密钥对象，不存在返回 None
        """
        result = await self.session.execute(select(ProviderKeyORM).where(ProviderKeyORM.user_id == user_id, ProviderKeyORM.name == name))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        provider_key = ProviderKey.model_validate(orm)
        return provider_key

    async def update_provider_key(self, key_id: int, key_data: dict) -> Optional[ProviderKey]:
        """
        更新 Provider Key

        Args:
            key_id: 密钥ID
            key_data: 要更新的数据字典，可包含:
                - api_key: 新的API密钥明文（如果提供，会重新加密存储）
                - status: 密钥状态

        Returns:
            ProviderKey: 更新后的密钥对象，不存在返回 None
        """
        # 加载密钥
        result = await self.session.execute(select(ProviderKeyORM).where(ProviderKeyORM.id == key_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 更新属性（排除不可更新字段）
        excluded_fields = ("id", "user_id", "name", "created_at")
        has_update = False
        for key, value in key_data.items():
            if key not in excluded_fields:
                if key == "api_key":
                    # 如果更新 api_key，需要加密
                    encrypted_key = encrypt_api_key(value, self.settings.aes_secret_key)
                    orm.api_key_encrypted = encrypted_key
                    has_update = True
                else:
                    setattr(orm, key, value)
                    has_update = True

        if not has_update:
            # 没有可更新的字段
            provider_key = ProviderKey.model_validate(orm)
            return provider_key

        await self.session.commit()
        await self.session.refresh(orm)

        provider_key = ProviderKey.model_validate(orm)
        return provider_key

    async def delete_provider_key(self, key_id: int) -> bool:
        """
        删除密钥

        Args:
            key_id: 密钥ID

        Returns:
            bool: 是否删除成功
        """
        result = await self.session.execute(delete(ProviderKeyORM).where(ProviderKeyORM.id == key_id))
        await self.session.commit()
        success = result.rowcount > 0
        return success

    def decrypt_provider_key(self, encrypted_key: str) -> str:
        """
        解密密钥

        Args:
            encrypted_key: 加密后的密钥字符串

        Returns:
            str: 解密后的 API Key 明文
        """
        decrypted = decrypt_api_key(encrypted_key, self.settings.aes_secret_key)
        return decrypted

    async def get_decrypted_key(self, key_id: int) -> Optional[str]:
        """
        获取解密后的 API Key（仅供内部使用，如代理转发）

        Args:
            key_id: 密钥ID

        Returns:
            str: 解密后的 API Key 明文，不存在返回 None
        """
        provider_key = await self.get_provider_key_by_id(key_id)
        if not provider_key:
            return None
        decrypted = self.decrypt_provider_key(provider_key.api_key_encrypted)
        return decrypted

    async def get_decrypted_key_by_name(self, user_id: str, name: str) -> Optional[str]:
        """
        通过用户ID和名称获取解密后的 API Key（仅供内部使用，如代理转发）

        Args:
            user_id: 用户ID
            name: 密钥名称（同时代表供应商）

        Returns:
            str: 解密后的 API Key 明文，不存在返回 None
        """
        provider_key = await self.get_provider_key_by_name(user_id, name)
        if not provider_key:
            return None
        decrypted = self.decrypt_provider_key(provider_key.api_key_encrypted)
        return decrypted
