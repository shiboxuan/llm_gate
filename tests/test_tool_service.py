"""
工具服务测试用例

测试 ToolService 的所有方法
使用 Mock 数据库进行测试
"""
import pytest

from app.models.tool import Tool, RouteConfig
from app.core.security import hash_tool_token


class TestToolService:
    """工具服务测试类"""
    
    @pytest.mark.asyncio
    async def test_create_tool(self, tool_service):
        """测试创建工具"""
        user_id = "user_001"
        tool_data = {"name": "测试工具"}
        
        tool, token = await tool_service.create_tool(user_id, tool_data)
        
        assert tool is not None
        assert isinstance(tool, Tool)
        assert tool.name == "测试工具"
        assert tool.user_id == user_id
        assert tool.status == 1
        assert tool.token_hash is not None
        
        # 验证 token 哈希是否正确
        assert token.startswith("sk-")
        assert tool.token_hash == hash_tool_token(token)
    
    @pytest.mark.asyncio
    async def test_create_tool_with_routes(self, tool_service):
        """测试创建带路由配置的工具"""
        user_id = "user_001"
        tool_data = {
            "name": "带路由工具",
            "routes": {
                "default": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                }
            },
            "active_route_name": "default"
        }
        
        tool, token = await tool_service.create_tool(user_id, tool_data)
        
        assert tool is not None
        assert tool.active_route_name == "default"
        assert "default" in tool.routes
        assert tool.routes["default"].base_url == "https://api.openai.com/v1/chat/completions"
        assert tool.routes["default"].model == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_get_tool_by_id_exists(self, tool_service):
        """测试通过ID查询存在的工具"""
        # 先创建工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "查询测试工具"})
        
        # 查询工具
        found_tool = await tool_service.get_tool_by_id(tool.id)
        
        assert found_tool is not None
        assert found_tool.id == tool.id
        assert found_tool.name == "查询测试工具"
    
    @pytest.mark.asyncio
    async def test_get_tool_by_id_not_exists(self, tool_service):
        """测试通过ID查询不存在的工具"""
        tool = await tool_service.get_tool_by_id(99999)
        
        assert tool is None
    
    @pytest.mark.asyncio
    async def test_get_tools_by_user(self, tool_service):
        """测试获取用户所有工具"""
        user_id = "user_001"
        
        # 创建多个工具
        await tool_service.create_tool(user_id, {"name": "工具1"})
        await tool_service.create_tool(user_id, {"name": "工具2"})
        await tool_service.create_tool(user_id, {"name": "工具3"})
        
        # 获取用户所有工具
        tools = await tool_service.get_tools_by_user(user_id)
        
        assert len(tools) >= 3
        assert all(t.user_id == user_id for t in tools)
    
    @pytest.mark.asyncio
    async def test_get_tools_by_user_empty(self, tool_service):
        """测试获取无工具用户的工具列表"""
        tools = await tool_service.get_tools_by_user("user_no_tools")
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_update_tool(self, tool_service):
        """测试更新工具"""
        # 先创建工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "原始工具名"})
        
        # 更新工具
        updated_tool = await tool_service.update_tool(tool.id, {"name": "更新后的工具名"})
        
        assert updated_tool is not None
        assert updated_tool.name == "更新后的工具名"
        assert updated_tool.id == tool.id
    
    @pytest.mark.asyncio
    async def test_update_tool_status(self, tool_service):
        """测试更新工具状态"""
        # 先创建工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "状态测试工具"})
        
        # 禁用工具
        updated_tool = await tool_service.update_tool(tool.id, {"status": 0})
        
        assert updated_tool is not None
        assert updated_tool.status == 0
        
        # 启用工具
        updated_tool = await tool_service.update_tool(tool.id, {"status": 1})
        
        assert updated_tool.status == 1
    
    @pytest.mark.asyncio
    async def test_update_tool_not_exists(self, tool_service):
        """测试更新不存在的工具"""
        updated_tool = await tool_service.update_tool(99999, {"name": "新名称"})
        
        assert updated_tool is None
    
    @pytest.mark.asyncio
    async def test_update_tool_cannot_change_token_hash(self, tool_service):
        """测试无法通过 update_tool 修改 token_hash"""
        # 先创建工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "Token保护测试"})
        original_token_hash = tool.token_hash
        
        # 尝试更新 token_hash（应该被忽略）
        updated_tool = await tool_service.update_tool(tool.id, {
            "name": "新名称",
            "token_hash": "malicious_token_hash"
        })
        
        assert updated_tool is not None
        assert updated_tool.name == "新名称"
        assert updated_tool.token_hash == original_token_hash
    
    @pytest.mark.asyncio
    async def test_delete_tool(self, tool_service):
        """测试删除工具"""
        # 先创建工具
        user_id = "user_001"
        tool, _ = await tool_service.create_tool(user_id, {"name": "待删除工具"})
        
        # 删除工具
        result = await tool_service.delete_tool(tool.id)
        
        assert result is True
        
        # 验证已删除
        found_tool = await tool_service.get_tool_by_id(tool.id)
        assert found_tool is None
    
    @pytest.mark.asyncio
    async def test_delete_tool_not_exists(self, tool_service):
        """测试删除不存在的工具"""
        result = await tool_service.delete_tool(99999)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_regenerate_tool_token(self, tool_service):
        """测试重新生成Token"""
        # 先创建工具
        user_id = "user_001"
        tool, original_token = await tool_service.create_tool(user_id, {"name": "Token重生测试"})
        original_token_hash = tool.token_hash
        
        # 重新生成 Token
        updated_tool, new_token = await tool_service.regenerate_tool_token(tool.id)
        
        assert updated_tool is not None
        assert new_token is not None
        assert new_token != original_token
        assert updated_tool.token_hash != original_token_hash
        assert updated_tool.token_hash == hash_tool_token(new_token)
    
    @pytest.mark.asyncio
    async def test_regenerate_tool_token_not_exists(self, tool_service):
        """测试重新生成不存在工具的Token"""
        tool, token = await tool_service.regenerate_tool_token(99999)
        
        assert tool is None
        assert token is None
    
    @pytest.mark.asyncio
    async def test_get_tool_by_token_hash(self, tool_service):
        """测试通过Token哈希查询工具"""
        # 先创建工具
        user_id = "user_001"
        tool, token = await tool_service.create_tool(user_id, {"name": "Token哈希查询测试"})
        
        # 通过 token hash 查询
        token_hash = hash_tool_token(token)
        found_tool = await tool_service.get_tool_by_token_hash(token_hash)
        
        assert found_tool is not None
        assert found_tool.id == tool.id
        assert found_tool.name == "Token哈希查询测试"
    
    @pytest.mark.asyncio
    async def test_get_tool_by_token_hash_not_exists(self, tool_service):
        """测试通过不存在的Token哈希查询工具"""
        tool = await tool_service.get_tool_by_token_hash("nonexistent_hash")
        
        assert tool is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
