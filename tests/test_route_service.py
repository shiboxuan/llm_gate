"""
路由服务测试用例

测试 RouteService 的所有方法
使用 Mock 数据库进行测试
"""
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.orm import ToolORM
from app.models.tool import Tool, RouteConfig
from app.services.tool_service import ToolService


async def _fetch_persisted_routes(tool_id: int) -> dict:
    """用独立新 session/engine 查库，验证 routes 是否真正持久化。

    绕过当前 session 的 identity map 缓存，模拟“刷新页面重新查库”。
    回归 bug：add/update/delete_route 修改 JSONB 列后若未 flag_modified，
    SQLAlchemy 判定 no-net-change 不写库，当前 session 的内存对象已被改，
    但数据库未变——必须用独立 session 才能查出真实持久化状态。
    """
    db_url = os.environ.get(
        "LLM_GATE_TEST_DATABASE_URL",
        "postgresql+asyncpg://llm_gate:llm_gate@localhost:5432/llm_gate_test",
    )
    engine = create_async_engine(db_url)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(select(ToolORM).where(ToolORM.id == tool_id))
            orm = result.scalar_one_or_none()
            return dict(orm.routes) if orm and orm.routes else {}
    finally:
        await engine.dispose()


async def _create_test_user(user_service) -> str:
    """创建测试用户（写入数据库），返回 user_id。

    service 层测试需先在 DB 建用户，否则 create_tool 会因 user_id 外键约束失败。
    用唯一 username/email 避免唯一约束冲突，支持重复运行。
    """
    from app.core.security import hash_password
    suffix = uuid.uuid4().hex[:8]
    user = await user_service.create_user({
        "id": f"user_{uuid.uuid4().hex[:12]}",
        "username": f"repro_{suffix}",
        "password_hash": hash_password("testpass123"),
        "email": f"repro_{suffix}@example.com",
        "is_admin": False,
        "status": 1,
    })
    return user.id


class TestRouteService:
    """路由服务测试类"""
    
    @pytest_asyncio.fixture
    async def tool_with_routes(self, tool_service):
        """创建带路由的测试工具"""
        user_id = "user_001"
        tool_data = {
            "name": "路由测试工具",
            "routes": {
                "openai_route": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                }
            },
            "active_route_name": "openai_route"
        }
        tool, _ = await tool_service.create_tool(user_id, tool_data)
        return tool
    
    @pytest.mark.asyncio
    async def test_add_route(self, route_service, tool_service):
        """测试添加路由"""
        # 先创建一个工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "添加路由测试工具"})
        
        # 添加路由
        route_config = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4",
            provider_key_name="openai"
        )
        updated_tool = await route_service.add_route(tool.id, "default", route_config)
        
        assert updated_tool is not None
        assert "default" in updated_tool.routes
        assert updated_tool.routes["default"].base_url == "https://api.openai.com/v1/chat/completions"
        assert updated_tool.routes["default"].model == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_add_multiple_routes(self, route_service, tool_service):
        """测试添加多个路由"""
        # 先创建一个工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "多路由测试工具"})
        
        # 添加第一个路由
        route1 = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4",
            provider_key_name="openai"
        )
        await route_service.add_route(tool.id, "openai_route", route1)
        
        # 添加第二个路由
        route2 = RouteConfig(
            base_url="https://api.anthropic.com/v1/messages",
            model="claude-3-sonnet",
            provider_key_name="anthropic"
        )
        updated_tool = await route_service.add_route(tool.id, "anthropic_route", route2)
        
        assert updated_tool is not None
        assert len(updated_tool.routes) == 2
        assert "openai_route" in updated_tool.routes
        assert "anthropic_route" in updated_tool.routes
    
    @pytest.mark.asyncio
    async def test_add_route_tool_not_exists(self, route_service):
        """测试向不存在的工具添加路由"""
        route_config = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4",
            provider_key_name="openai"
        )
        result = await route_service.add_route(99999, "default", route_config)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_route(self, route_service, tool_with_routes):
        """测试更新路由"""
        tool = tool_with_routes
        
        # 更新路由配置
        new_route_config = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4-turbo",
            provider_key_name="openai"
        )
        updated_tool = await route_service.update_route(tool.id, "openai_route", new_route_config)
        
        assert updated_tool is not None
        assert updated_tool.routes["openai_route"].model == "gpt-4-turbo"
    
    @pytest.mark.asyncio
    async def test_update_route_not_exists(self, route_service, tool_with_routes):
        """测试更新不存在的路由"""
        tool = tool_with_routes
        
        new_route_config = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4-turbo",
            provider_key_name="openai"
        )
        result = await route_service.update_route(tool.id, "nonexistent_route", new_route_config)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_route_tool_not_exists(self, route_service):
        """测试更新不存在工具的路由"""
        new_route_config = RouteConfig(
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4-turbo",
            provider_key_name="openai"
        )
        result = await route_service.update_route(99999, "default", new_route_config)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_route(self, route_service, tool_service):
        """测试删除路由"""
        # 创建带多个路由的工具
        user_id = "user_001"
        tool_data = {
            "name": "删除路由测试工具",
            "routes": {
                "route1": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                },
                "route2": {
                    "base_url": "https://api.anthropic.com/v1/messages",
                    "model": "claude-3-sonnet",
                    "provider_key_name": "anthropic"
                }
            }
        }
        tool, _ = await tool_service.create_tool(user_id, tool_data)
        
        # 删除路由
        updated_tool = await route_service.delete_route(tool.id, "route1")
        
        assert updated_tool is not None
        assert "route1" not in updated_tool.routes
        assert "route2" in updated_tool.routes
    
    @pytest.mark.asyncio
    async def test_delete_route_clears_active_route(self, route_service, tool_with_routes):
        """测试删除激活的路由会清空 active_route_name"""
        tool = tool_with_routes
        
        # 删除当前激活的路由
        updated_tool = await route_service.delete_route(tool.id, "openai_route")
        
        assert updated_tool is not None
        assert "openai_route" not in updated_tool.routes
        assert updated_tool.active_route_name is None
    
    @pytest.mark.asyncio
    async def test_delete_route_not_exists(self, route_service, tool_with_routes):
        """测试删除不存在的路由"""
        tool = tool_with_routes
        
        result = await route_service.delete_route(tool.id, "nonexistent_route")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_activate_route(self, route_service, tool_service):
        """测试激活路由"""
        # 创建带多个路由的工具
        user_id = "user_001"
        tool_data = {
            "name": "激活路由测试工具",
            "routes": {
                "route1": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                },
                "route2": {
                    "base_url": "https://api.anthropic.com/v1/messages",
                    "model": "claude-3-sonnet",
                    "provider_key_name": "anthropic"
                }
            },
            "active_route_name": "route1"
        }
        tool, _ = await tool_service.create_tool(user_id, tool_data)
        
        # 激活另一个路由
        updated_tool = await route_service.activate_route(tool.id, "route2")
        
        assert updated_tool is not None
        assert updated_tool.active_route_name == "route2"
    
    @pytest.mark.asyncio
    async def test_activate_route_not_exists(self, route_service, tool_with_routes):
        """测试激活不存在的路由"""
        tool = tool_with_routes
        
        result = await route_service.activate_route(tool.id, "nonexistent_route")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_activate_route_tool_not_exists(self, route_service):
        """测试激活不存在工具的路由"""
        result = await route_service.activate_route(99999, "default")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_active_route(self, route_service, tool_with_routes):
        """测试获取激活的路由配置"""
        tool = tool_with_routes
        
        active_route = await route_service.get_active_route(tool.id)
        
        assert active_route is not None
        assert isinstance(active_route, RouteConfig)
        assert active_route.base_url == "https://api.openai.com/v1/chat/completions"
        assert active_route.model == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_get_active_route_no_active(self, route_service, tool_service):
        """测试获取无激活路由的工具的激活路由"""
        # 创建没有激活路由的工具
        user_id = "user_001"
        tool_data = {
            "name": "无激活路由工具",
            "routes": {
                "route1": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                }
            }
            # 没有设置 active_route_name
        }
        tool, _ = await tool_service.create_tool(user_id, tool_data)
        
        active_route = await route_service.get_active_route(tool.id)
        
        assert active_route is None
    
    @pytest.mark.asyncio
    async def test_get_active_route_tool_not_exists(self, route_service):
        """测试获取不存在工具的激活路由"""
        active_route = await route_service.get_active_route(99999)

        assert active_route is None

    # ==================== 持久化回归测试 ====================
    # 以下测试用独立新 session 查库，验证 add/update/delete_route 对 JSONB 列的修改
    # 真正写入数据库（而非仅停留在内存）。历史 bug：_parse_routes 对 dict 返回同一
    # 对象引用，orm.routes = routes 同对象赋值被 SQLAlchemy 判定为 no-net-change
    # 不写库，导致前端显示“添加成功”但刷新后路由消失。

    @pytest.mark.asyncio
    async def test_add_route_persists_to_db(self, route_service, tool_service, user_service):
        """回归：add_route 后必须真正持久化到数据库（独立 session 查库验证）"""
        user_id = await _create_test_user(user_service)
        tool, _ = await tool_service.create_tool(user_id, {
            "name": f"持久化测试_{uuid.uuid4().hex[:8]}",
            "routes": {
                "route_a": {"base_url": "https://a.example.com/v1", "model": "m-a", "provider_key_name": "k"}
            },
        })

        rc = RouteConfig(base_url="https://b.example.com/v1", model="m-b", provider_key_name="k")
        updated = await route_service.add_route(tool.id, "route_b", rc)

        # 修复前：commit 后 refresh(orm) 从库重载，而库未写入新路由，
        # 因此返回值本身也只剩 route_a（前端拿到 200 但列表无新路由=用户看到的"成功但没加上"）。
        # 修复后：返回值含两条。
        assert "route_a" in updated.routes
        assert "route_b" in updated.routes

        # 独立 session 查库：修复前这里只有 route_a（bug），修复后应有 route_b
        persisted = await _fetch_persisted_routes(tool.id)
        assert "route_a" in persisted
        assert "route_b" in persisted, "新增路由未持久化到数据库（JSONB dirty 检测 bug）"
        assert len(persisted) == 2

    @pytest.mark.asyncio
    async def test_update_route_persists_to_db(self, route_service, tool_service, user_service):
        """回归：update_route 后修改必须真正持久化到数据库"""
        user_id = await _create_test_user(user_service)
        tool, _ = await tool_service.create_tool(user_id, {
            "name": f"更新持久化_{uuid.uuid4().hex[:8]}",
            "routes": {
                "route_a": {"base_url": "https://a.example.com/v1", "model": "m-a", "provider_key_name": "k"}
            },
        })

        new_cfg = RouteConfig(base_url="https://a.example.com/v1", model="m-a-updated", provider_key_name="k")
        await route_service.update_route(tool.id, "route_a", new_cfg)

        persisted = await _fetch_persisted_routes(tool.id)
        assert persisted["route_a"]["model"] == "m-a-updated", "路由更新未持久化到数据库"

    @pytest.mark.asyncio
    async def test_delete_route_persists_to_db(self, route_service, tool_service, user_service):
        """回归：delete_route 后删除必须真正持久化到数据库"""
        user_id = await _create_test_user(user_service)
        tool, _ = await tool_service.create_tool(user_id, {
            "name": f"删除持久化_{uuid.uuid4().hex[:8]}",
            "routes": {
                "route_a": {"base_url": "https://a.example.com/v1", "model": "m-a", "provider_key_name": "k"},
                "route_b": {"base_url": "https://b.example.com/v1", "model": "m-b", "provider_key_name": "k"},
            },
        })

        await route_service.delete_route(tool.id, "route_a")

        persisted = await _fetch_persisted_routes(tool.id)
        assert "route_a" not in persisted, "路由删除未持久化（删除后刷新页面路由仍在）"
        assert "route_b" in persisted
        assert len(persisted) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
