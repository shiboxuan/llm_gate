"""
路由服务 - 路由配置相关业务逻辑

提供路由的增删改查和激活操作
使用 SQLAlchemy 2.0 async 直连 PostgreSQL
"""
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_current_time
from app.db.orm import ToolORM
from app.models.tool import Tool, RouteConfig


class RouteService:
    """路由服务类

    使用 SQLAlchemy AsyncSession 进行数据库操作。
    """

    def __init__(self, session: AsyncSession):
        """初始化路由服务

        Args:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def add_route(self, tool_id: int, route_name: str, route_config: RouteConfig, order: int = None) -> Optional[Tool]:
        """
        添加路由

        Args:
            tool_id: 工具ID
            route_name: 路由名称
            route_config: 路由配置
            order: 排序值，不传则自动计算（当前最大值 + 1）

        Returns:
            Tool: 更新后的工具对象，工具不存在返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取现有路由配置
        routes = self._parse_routes(orm.routes) or {}

        # 3. 计算 order：如果未提供，则为当前最大值 + 1
        if order is None:
            max_order = max((r.get("order", 0) for r in routes.values()), default=-1)
            order = max_order + 1

        # 4. 添加新路由（包含 order）
        route_dict = route_config.model_dump()
        route_dict["order"] = order
        routes[route_name] = route_dict

        # 5. 更新数据库（routes 传 dict，JSONB 列自动处理）
        orm.routes = routes
        # routes 是 JSONB 列：_parse_routes 对 dict 返回同一对象引用，
        # 直接赋值回 orm.routes 会被 SQLAlchemy 判定为 no-net-change 不写库，
        # 必须显式 flag_modified 标记 dirty，否则新增/修改/删除的路由不会持久化。
        flag_modified(orm, "routes")
        orm.updated_at = get_current_time()
        await self.session.commit()
        await self.session.refresh(orm)

        # 6. 返回更新后的工具
        tool = self._orm_to_tool(orm)
        return tool

    async def update_route(self, tool_id: int, route_name: str, route_config: RouteConfig) -> Optional[Tool]:
        """
        更新路由

        Args:
            tool_id: 工具ID
            route_name: 路由名称
            route_config: 新的路由配置

        Returns:
            Tool: 更新后的工具对象，工具不存在或路由不存在返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取现有路由配置
        routes = self._parse_routes(orm.routes) or {}

        # 3. 检查路由是否存在
        if route_name not in routes:
            return None

        # 4. 更新路由
        routes[route_name] = route_config.model_dump()

        # 5. 更新数据库
        orm.routes = routes
        # routes 是 JSONB 列：_parse_routes 对 dict 返回同一对象引用，
        # 直接赋值回 orm.routes 会被 SQLAlchemy 判定为 no-net-change 不写库，
        # 必须显式 flag_modified 标记 dirty，否则新增/修改/删除的路由不会持久化。
        flag_modified(orm, "routes")
        orm.updated_at = get_current_time()
        await self.session.commit()
        await self.session.refresh(orm)

        # 6. 返回更新后的工具
        tool = self._orm_to_tool(orm)
        return tool

    async def delete_route(self, tool_id: int, route_name: str) -> Optional[Tool]:
        """
        删除路由

        Args:
            tool_id: 工具ID
            route_name: 路由名称

        Returns:
            Tool: 更新后的工具对象，工具不存在或路由不存在返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取现有路由配置
        routes = self._parse_routes(orm.routes) or {}

        # 3. 检查路由是否存在
        if route_name not in routes:
            return None

        # 4. 删除路由
        del routes[route_name]

        # 5. 如果删除的是激活的路由，清空 active_route_name
        if orm.active_route_name == route_name:
            orm.active_route_name = None

        # 6. 更新数据库
        orm.routes = routes
        # routes 是 JSONB 列：_parse_routes 对 dict 返回同一对象引用，
        # 直接赋值回 orm.routes 会被 SQLAlchemy 判定为 no-net-change 不写库，
        # 必须显式 flag_modified 标记 dirty，否则新增/修改/删除的路由不会持久化。
        flag_modified(orm, "routes")
        orm.updated_at = get_current_time()
        await self.session.commit()
        await self.session.refresh(orm)

        # 7. 返回更新后的工具
        tool = self._orm_to_tool(orm)
        return tool

    async def activate_route(self, tool_id: int, route_name: str) -> Optional[Tool]:
        """
        激活路由

        Args:
            tool_id: 工具ID
            route_name: 要激活的路由名称

        Returns:
            Tool: 更新后的工具对象，工具不存在或路由不存在返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取现有路由配置
        routes = self._parse_routes(orm.routes) or {}

        # 3. 检查路由是否存在
        if route_name not in routes:
            return None

        # 4. 更新激活的路由名称
        orm.active_route_name = route_name
        orm.updated_at = get_current_time()
        await self.session.commit()
        await self.session.refresh(orm)

        # 5. 返回更新后的工具
        tool = self._orm_to_tool(orm)
        return tool

    async def reorder_routes(self, tool_id: int, orders: dict) -> Optional[Tool]:
        """
        批量更新路由排序

        Args:
            tool_id: 工具ID
            orders: 路由排序字典 {route_name: new_order}

        Returns:
            Tool: 更新后的工具对象，工具不存在返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取现有路由配置
        routes = self._parse_routes(orm.routes) or {}

        # 3. 更新每个路由的 order
        for route_name, new_order in orders.items():
            if route_name in routes:
                routes[route_name]["order"] = new_order

        # 4. 更新数据库
        orm.routes = routes
        # routes 是 JSONB 列：_parse_routes 对 dict 返回同一对象引用，
        # 直接赋值回 orm.routes 会被 SQLAlchemy 判定为 no-net-change 不写库，
        # 必须显式 flag_modified 标记 dirty，否则新增/修改/删除的路由不会持久化。
        flag_modified(orm, "routes")
        orm.updated_at = get_current_time()
        await self.session.commit()
        await self.session.refresh(orm)

        # 5. 返回更新后的工具
        tool = self._orm_to_tool(orm)
        return tool

    async def get_active_route(self, tool_id: int) -> Optional[RouteConfig]:
        """
        获取激活的路由配置

        Args:
            tool_id: 工具ID

        Returns:
            RouteConfig: 激活的路由配置，工具不存在或无激活路由返回 None
        """
        # 1. 加载工具
        result = await self.session.execute(select(ToolORM).where(ToolORM.id == tool_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        # 2. 获取激活的路由名称
        active_route_name = orm.active_route_name
        if not active_route_name:
            return None

        # 3. 获取路由配置
        routes = self._parse_routes(orm.routes) or {}
        if active_route_name not in routes:
            return None

        # 4. 返回激活的路由配置
        route_config = RouteConfig(**routes[active_route_name])
        return route_config

    def _parse_routes(self, routes) -> dict:
        """
        解析路由配置

        Args:
            routes: 路由配置（可能是 JSON 字符串或字典，ORM 读出来是字典）

        Returns:
            dict: 路由配置字典
        """
        if isinstance(routes, str):
            try:
                result = json.loads(routes)
                return result
            except json.JSONDecodeError:
                return {}
        if isinstance(routes, dict):
            return routes
        return {}

    def _orm_to_tool(self, orm: ToolORM) -> Tool:
        """
        将 ORM 对象转换为 Tool 对象

        Args:
            orm: ToolORM 对象

        Returns:
            Tool: 工具对象
        """
        # routes 字段：JSONB 列读取时已是 dict
        routes = self._parse_routes(orm.routes) or {}
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
