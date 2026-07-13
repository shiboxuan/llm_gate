"""
工具服务 - 工具相关业务逻辑

提供工具的CRUD操作和Token管理
使用 SQLAlchemy 2.0 async 直连 PostgreSQL
"""
from typing import Optional, List

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_current_time
from app.core.security import generate_tool_token, hash_tool_token
from app.db.orm import ToolORM
from app.models.tool import Tool, RouteConfig


class ToolService:
    """工具服务类

    使用 SQLAlchemy AsyncSession 进行数据库操作。
    """

    def __init__(self, session: AsyncSession):
        """初始化工具服务

        Args:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_tool_by_name(self, user_id: str, name: str) -> Optional[Tool]:
        """
        按名称获取工具（同一用户下 name 唯一）

        Args:
            user_id: 用户ID
            name: 工具名称

        Returns:
            Tool: 工具对象，不存在返回 None
        """
        result = await self.session.execute(select(ToolORM).where(ToolORM.user_id == user_id, ToolORM.name == name))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        tool = self._orm_to_tool(orm)
        return tool

    async def create_tool(self, user_id: str, tool_data: dict) -> tuple[Tool, str]:
        """
        创建工具

        Args:
            user_id: 用户ID
            tool_data: 工具数据字典，包含:
                - name: 工具名称

        Returns:
            tuple: (Tool对象, 明文Token) - 明文Token仅在创建时返回一次

        Raises:
            ValueError: 当同一用户下已存在同名工具时抛出，或创建失败时抛出
        """
        # 0. 检查 (user_id, name) 联合唯一约束
        tool_name = tool_data.get("name", "")
        existing = await self.get_tool_by_name(user_id, tool_name)
        if existing:
            raise ValueError(f"Tool with name '{tool_name}' already exists")

        # 1. 生成 Tool Token
        token = generate_tool_token()
        token_hash = hash_tool_token(token)

        # 2. 构造 ORM 对象并插入（routes 传 dict，JSONB 列自动处理）
        orm = ToolORM(
            user_id=user_id,
            name=tool_data.get("name", ""),
            description=tool_data.get("description", ""),
            token_hash=token_hash,
            api_type=tool_data.get("api_type", "openai_chat"),
            active_route_name=tool_data.get("active_route_name"),
            routes=tool_data.get("routes", {}),
            status=tool_data.get("status", 1),
        )
        self.session.add(orm)
        await self.session.commit()
        await self.session.refresh(orm)

        tool = self._orm_to_tool(orm)
        result = (tool, token)
        return result

    async def get_tool_by_id(self, tool_id: int) -> Optional[Tool]:
        """
        获取单个工具

        Args:
            tool_id: 工具ID

        Returns:
            Tool: 工具对象，不存在返回 None
        """
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        tool = self._orm_to_tool(orm)
        return tool

    async def get_tools_by_user(self, user_id: str) -> List[Tool]:
        """
        获取用户所有工具

        Args:
            user_id: 用户ID

        Returns:
            List[Tool]: 工具列表
        """
        result = await self.session.execute(select(ToolORM).where(ToolORM.user_id == user_id))
        orm_list = result.scalars().all()
        tools = []
        for orm in orm_list:
            tool = self._orm_to_tool(orm)
            tools.append(tool)
        return tools

    async def update_tool(self, tool_id: int, tool_data: dict) -> Optional[Tool]:
        """
        更新工具

        Args:
            tool_id: 工具ID
            tool_data: 要更新的数据字典，可包含:
                - name: 工具名称
                - active_route_name: 激活的路由名称
                - status: 工具状态

        Returns:
            Tool: 更新后的工具对象，工具不存在返回 None

        Raises:
            ValueError: 当更新名称时，新名称与同一用户下其他工具冲突时抛出
        """
        # 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 如果更新名称，检查 (user_id, name) 联合唯一约束
        new_name = tool_data.get("name")
        if new_name and new_name != orm.name:
            conflict = await self.get_tool_by_name(orm.user_id, new_name)
            if conflict:
                raise ValueError(f"Tool with name '{new_name}' already exists")

        # 更新属性（排除不可更新字段，routes 若是 dict 直接传）
        excluded_fields = ("id", "user_id", "token_hash", "created_at")
        for key, value in tool_data.items():
            if key not in excluded_fields:
                setattr(orm, key, value)
        orm.updated_at = get_current_time()

        await self.session.commit()
        await self.session.refresh(orm)

        tool = self._orm_to_tool(orm)
        return tool

    async def delete_tool(self, tool_id: int) -> bool:
        """
        删除工具

        Args:
            tool_id: 工具ID

        Returns:
            bool: 删除成功返回 True，工具不存在返回 False
        """
        result = await self.session.execute(delete(ToolORM).where(ToolORM.id == tool_id))
        await self.session.commit()
        success = result.rowcount > 0
        return success

    async def regenerate_tool_token(self, tool_id: int) -> tuple[Optional[Tool], Optional[str]]:
        """
        重新生成Token

        Args:
            tool_id: 工具ID

        Returns:
            tuple: (Tool对象, 新的明文Token)，工具不存在返回 (None, None)
        """
        # 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None, None

        # 生成新的 Token
        token = generate_tool_token()
        token_hash = hash_tool_token(token)

        # 更新 Token 哈希
        orm.token_hash = token_hash
        orm.updated_at = get_current_time()

        await self.session.commit()
        await self.session.refresh(orm)

        tool = self._orm_to_tool(orm)
        result = (tool, token)
        return result

    async def get_tool_by_token_hash(self, token_hash: str) -> Optional[Tool]:
        """
        通过Token哈希查询工具

        Args:
            token_hash: Tool Token 的 SHA-256 哈希值

        Returns:
            Tool: 工具对象，不存在返回 None
        """
        result = await self.session.execute(select(ToolORM).where(ToolORM.token_hash == token_hash))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        tool = self._orm_to_tool(orm)
        return tool

    async def get_tools_by_provider_key_name(self, user_id: str, provider_key_name: str) -> List[Tool]:
        """
        获取使用特定 Provider Key 名称的所有工具

        查找所有 routes 中包含指定 provider_key_name 的工具
        用于在更新或删除 Provider Key 时失效相关缓存

        Args:
            user_id: 用户ID
            provider_key_name: Provider Key 名称

        Returns:
            List[Tool]: 使用该 Provider Key 的工具列表
        """
        # 获取用户所有工具
        all_tools = await self.get_tools_by_user(user_id)

        # 过滤出使用该 provider_key_name 的工具
        matching_tools = []
        for tool in all_tools:
            for route_name, route_config in tool.routes.items():
                if route_config.provider_key_name == provider_key_name:
                    matching_tools.append(tool)
                    break  # 找到一个匹配就跳出，避免重复添加

        return matching_tools

    async def deactivate_tools_by_user(self, user_id: str) -> int:
        """
        批量停用用户的所有工具

        将用户所有工具的 status 置为 0（停用），用于用户离职时处理

        Args:
            user_id: 用户ID

        Returns:
            int: 停用的工具数量
        """
        result = await self.session.execute(
            update(ToolORM).where(ToolORM.user_id == user_id, ToolORM.status == 1).values(status=0, updated_at=get_current_time())
        )
        await self.session.commit()
        count = result.rowcount
        return count

    def _orm_to_tool(self, orm: ToolORM) -> Tool:
        """
        将 ORM 对象转换为 Tool 对象

        Args:
            orm: ToolORM 对象

        Returns:
            Tool: 工具对象
        """
        # routes 字段：JSONB 列读取时已是 dict
        routes = orm.routes or {}
        route_configs = {name: RouteConfig(**cfg) for name, cfg in routes.items()}

        tool = Tool(
            id=orm.id,
            user_id=orm.user_id,
            name=orm.name,
            description=orm.description or "",
            token_hash=orm.token_hash,
            api_type=orm.api_type or "openai_chat",
            active_route_name=orm.active_route_name,
            routes=route_configs,
            status=orm.status,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
        return tool
