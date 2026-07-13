"""
路由服务测试用例

测试 RouteService 的所有方法
使用 Mock 数据库进行测试
"""
import pytest
import pytest_asyncio

from app.models.tool import Tool, RouteConfig
from app.services.tool_service import ToolService


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
