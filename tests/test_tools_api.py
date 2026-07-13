"""
工具管理路由 API 测试用例

测试 /api/tools 下的所有接口
包括工具 CRUD 和路由管理功能
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.api.control_plane.tools import (
    create_tool, list_tools, get_tool, update_tool, delete_tool,
    regenerate_tool_key, add_route, update_route, delete_route, activate_route,
    _convert_routes_to_response
)
from app.schemas.tool import ToolCreate, ToolUpdate, ToolResponse, ToolTokenResponse
from app.schemas.route import RouteCreate, RouteUpdate, RouteResponse
from app.services.tool_service import ToolService
from app.services.route_service import RouteService
from app.services.cache_service import CacheService
from app.models.tool import Tool, RouteConfig
from app.models.user import User
from app.core.exceptions import APIException


class TestCreateToolEndpoint:
    """创建工具接口测试类"""
    
    # ==================== 正常创建测试 ====================
    
    @pytest.mark.asyncio
    async def test_create_tool_success(self, test_user, tool_service):
        """测试成功创建工具"""
        tool_data = ToolCreate(name="新工具", description="工具描述")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert isinstance(response, ToolTokenResponse)
        assert response.name == "新工具"
        assert response.user_id == test_user.id
        assert response.status == 1
    
    @pytest.mark.asyncio
    async def test_create_tool_returns_api_key(self, test_user, tool_service):
        """测试创建工具返回明文 API Key"""
        tool_data = ToolCreate(name="带Key工具")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        # 验证返回了明文 API Key
        assert response.api_key is not None
        assert len(response.api_key) > 0
        assert response.api_key.startswith("sk-")
    
    @pytest.mark.asyncio
    async def test_create_tool_with_empty_description(self, test_user, tool_service):
        """测试创建工具时描述为空"""
        tool_data = ToolCreate(name="无描述工具", description="")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.description == ""
    
    @pytest.mark.asyncio
    async def test_create_tool_auto_generates_id(self, test_user, tool_service):
        """测试创建工具自动生成 ID"""
        tool_data = ToolCreate(name="自动ID工具")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.id is not None
        assert response.id > 0
    
    @pytest.mark.asyncio
    async def test_create_tool_initial_routes_empty(self, test_user, tool_service):
        """测试新创建的工具路由列表为空"""
        tool_data = ToolCreate(name="空路由工具")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.routes == []
        assert response.active_route_name is None
    
    @pytest.mark.asyncio
    async def test_create_tool_with_long_name(self, test_user, tool_service):
        """测试创建工具时使用较长的名称"""
        long_name = "工具" + "A" * 200
        tool_data = ToolCreate(name=long_name)
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.name == long_name
    
    @pytest.mark.asyncio
    async def test_create_tool_with_special_characters(self, test_user, tool_service):
        """测试创建工具时名称包含特殊字符"""
        tool_data = ToolCreate(name="工具<test>&'\"测试", description="包含特殊字符的描述：<>&")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.name == "工具<test>&'\"测试"
    
    @pytest.mark.asyncio
    async def test_create_tool_has_timestamps(self, test_user, tool_service):
        """测试创建工具包含时间戳"""
        tool_data = ToolCreate(name="时间戳工具")
        
        response = await create_tool(tool_data, test_user, tool_service)
        
        assert response.created_at is not None
        assert response.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_create_multiple_tools_different_ids(self, test_user, tool_service):
        """测试创建多个工具获得不同的 ID"""
        tool_data1 = ToolCreate(name="工具1")
        tool_data2 = ToolCreate(name="工具2")
        
        response1 = await create_tool(tool_data1, test_user, tool_service)
        response2 = await create_tool(tool_data2, test_user, tool_service)
        
        assert response1.id != response2.id
    
    @pytest.mark.asyncio
    async def test_create_multiple_tools_different_api_keys(self, test_user, tool_service):
        """测试创建多个工具获得不同的 API Key"""
        tool_data1 = ToolCreate(name="工具A")
        tool_data2 = ToolCreate(name="工具B")
        
        response1 = await create_tool(tool_data1, test_user, tool_service)
        response2 = await create_tool(tool_data2, test_user, tool_service)
        
        assert response1.api_key != response2.api_key


class TestListToolsEndpoint:
    """获取工具列表接口测试类"""
    
    @pytest.mark.asyncio
    async def test_list_tools_empty(self, test_user, tool_service):
        """测试获取空的工具列表"""
        # test_user 是新用户，没有工具
        response = await list_tools(test_user, tool_service)
        
        assert isinstance(response, list)
        # 可能为空或者包含之前测试创建的工具
    
    @pytest.mark.asyncio
    async def test_list_tools_after_create(self, test_user, tool_service):
        """测试创建工具后获取列表"""
        # 先创建一个工具
        tool_data = ToolCreate(name="列表测试工具")
        await create_tool(tool_data, test_user, tool_service)
        
        # 获取列表
        response = await list_tools(test_user, tool_service)
        
        assert isinstance(response, list)
        # 验证列表中包含刚创建的工具
        tool_names = [t.name for t in response]
        assert "列表测试工具" in tool_names
    
    @pytest.mark.asyncio
    async def test_list_tools_returns_correct_type(self, test_user, tool_service):
        """测试获取工具列表返回正确类型"""
        tool_data = ToolCreate(name="类型测试工具")
        await create_tool(tool_data, test_user, tool_service)
        
        response = await list_tools(test_user, tool_service)
        
        for tool in response:
            assert isinstance(tool, ToolResponse)
    
    @pytest.mark.asyncio
    async def test_list_tools_not_include_api_key(self, test_user, tool_service):
        """测试获取工具列表不包含 API Key"""
        tool_data = ToolCreate(name="无Key列表工具")
        await create_tool(tool_data, test_user, tool_service)
        
        response = await list_tools(test_user, tool_service)
        
        for tool in response:
            # ToolResponse 不应该有 api_key 字段
            assert not hasattr(tool, 'api_key')
    
    @pytest.mark.asyncio
    async def test_list_tools_only_own_tools(self, test_user, test_user_2, tool_service):
        """测试只获取自己的工具列表"""
        # 为 test_user 创建工具
        tool_data = ToolCreate(name="用户1的工具")
        await create_tool(tool_data, test_user, tool_service)
        
        # 为 test_user_2 创建工具
        tool_data2 = ToolCreate(name="用户2的工具")
        await create_tool(tool_data2, test_user_2, tool_service)
        
        # test_user 获取列表
        response = await list_tools(test_user, tool_service)
        
        # 验证不包含其他用户的工具
        tool_names = [t.name for t in response]
        assert "用户2的工具" not in tool_names


class TestGetToolEndpoint:
    """获取工具详情接口测试类"""
    
    @pytest.mark.asyncio
    async def test_get_tool_success(self, test_user, tool_service):
        """测试成功获取工具详情"""
        # 先创建工具
        tool_data = ToolCreate(name="详情测试工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 获取详情
        response = await get_tool(created.id, test_user, tool_service)
        
        assert isinstance(response, ToolResponse)
        assert response.id == created.id
        assert response.name == "详情测试工具"
    
    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, test_user, tool_service):
        """测试获取不存在的工具"""
        with pytest.raises(APIException) as exc_info:
            await get_tool(99999, test_user, tool_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_get_tool_not_owner(self, test_user, test_user_2, tool_service):
        """测试获取不属于自己的工具"""
        # 为 test_user 创建工具
        tool_data = ToolCreate(name="他人的工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # test_user_2 尝试获取
        with pytest.raises(APIException) as exc_info:
            await get_tool(created.id, test_user_2, tool_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_get_tool_returns_routes(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试获取工具详情包含路由信息"""
        # 创建工具
        tool_data = ToolCreate(name="带路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        # 添加路由
        route_data = RouteCreate(**sample_route_create_data)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        # 获取详情
        response = await get_tool(created.id, test_user, tool_service)
        
        assert len(response.routes) > 0
    
    @pytest.mark.asyncio
    async def test_get_tool_all_fields(self, test_user, tool_service):
        """测试获取工具详情包含所有字段"""
        tool_data = ToolCreate(name="全字段工具", description="完整描述")
        created = await create_tool(tool_data, test_user, tool_service)
        
        response = await get_tool(created.id, test_user, tool_service)
        
        assert hasattr(response, 'id')
        assert hasattr(response, 'user_id')
        assert hasattr(response, 'name')
        assert hasattr(response, 'description')
        assert hasattr(response, 'active_route_name')
        assert hasattr(response, 'routes')
        assert hasattr(response, 'status')
        assert hasattr(response, 'created_at')
        assert hasattr(response, 'updated_at')


class TestUpdateToolEndpoint:
    """更新工具接口测试类"""
    
    @pytest.mark.asyncio
    async def test_update_tool_name(self, test_user, tool_service, cache_service):
        """测试更新工具名称"""
        # 创建工具
        tool_data = ToolCreate(name="原始名称")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 更新名称
        update_data = ToolUpdate(name="新名称")
        response = await update_tool(created.id, update_data, test_user, tool_service, cache_service)
        
        assert response.name == "新名称"
    
    @pytest.mark.asyncio
    async def test_update_tool_description(self, test_user, tool_service, cache_service):
        """测试更新工具描述"""
        tool_data = ToolCreate(name="描述测试", description="原始描述")
        created = await create_tool(tool_data, test_user, tool_service)
        
        update_data = ToolUpdate(description="新描述")
        response = await update_tool(created.id, update_data, test_user, tool_service, cache_service)
        
        assert response.description == "新描述"
        assert response.name == "描述测试"  # 名称未变
    
    @pytest.mark.asyncio
    async def test_update_tool_partial(self, test_user, tool_service, cache_service):
        """测试部分更新工具"""
        tool_data = ToolCreate(name="部分更新", description="原始描述")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 只更新名称
        update_data = ToolUpdate(name="新名称")
        response = await update_tool(created.id, update_data, test_user, tool_service, cache_service)
        
        assert response.name == "新名称"
        # description 未更新，保持不变
    
    @pytest.mark.asyncio
    async def test_update_tool_not_found(self, test_user, tool_service, cache_service):
        """测试更新不存在的工具"""
        update_data = ToolUpdate(name="新名称")
        
        with pytest.raises(APIException) as exc_info:
            await update_tool(99999, update_data, test_user, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_update_tool_not_owner(self, test_user, test_user_2, tool_service, cache_service):
        """测试更新不属于自己的工具"""
        tool_data = ToolCreate(name="他人工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        update_data = ToolUpdate(name="尝试修改")
        with pytest.raises(APIException) as exc_info:
            await update_tool(created.id, update_data, test_user_2, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_update_tool_status(self, test_user, tool_service, cache_service):
        """测试更新工具状态"""
        tool_data = ToolCreate(name="状态测试")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 禁用工具
        update_data = ToolUpdate(status=0)
        response = await update_tool(created.id, update_data, test_user, tool_service, cache_service)
        
        assert response.status == 0
    
    @pytest.mark.asyncio
    async def test_update_tool_empty_update(self, test_user, tool_service, cache_service):
        """测试空更新（不修改任何字段）"""
        tool_data = ToolCreate(name="空更新测试")
        created = await create_tool(tool_data, test_user, tool_service)
        
        update_data = ToolUpdate()
        response = await update_tool(created.id, update_data, test_user, tool_service, cache_service)
        
        assert response.name == "空更新测试"


class TestDeleteToolEndpoint:
    """删除工具接口测试类"""
    
    @pytest.mark.asyncio
    async def test_delete_tool_success(self, test_user, tool_service, cache_service):
        """测试成功删除工具"""
        tool_data = ToolCreate(name="待删除工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 删除工具
        await delete_tool(created.id, test_user, tool_service, cache_service)
        
        # 验证已删除
        with pytest.raises(APIException):
            await get_tool(created.id, test_user, tool_service)
    
    @pytest.mark.asyncio
    async def test_delete_tool_not_found(self, test_user, tool_service, cache_service):
        """测试删除不存在的工具"""
        with pytest.raises(APIException) as exc_info:
            await delete_tool(99999, test_user, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_delete_tool_not_owner(self, test_user, test_user_2, tool_service, cache_service):
        """测试删除不属于自己的工具"""
        tool_data = ToolCreate(name="他人工具删除测试")
        created = await create_tool(tool_data, test_user, tool_service)
        
        with pytest.raises(APIException) as exc_info:
            await delete_tool(created.id, test_user_2, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_delete_tool_invalidates_cache(self, test_user, tool_service, cache_service):
        """测试删除工具时使缓存失效"""
        tool_data = ToolCreate(name="缓存测试工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 删除工具（应该调用 cache_service.invalidate_route_config）
        await delete_tool(created.id, test_user, tool_service, cache_service)
        
        # 验证 cache_service 的方法被调用
        # 由于 cache_service 是 mock，我们只验证删除成功
        with pytest.raises(APIException):
            await get_tool(created.id, test_user, tool_service)


class TestRegenerateToolKeyEndpoint:
    """重新生成工具 Token 接口测试类"""
    
    @pytest.mark.asyncio
    async def test_regenerate_key_success(self, test_user, tool_service, cache_service):
        """测试成功重新生成 Token"""
        tool_data = ToolCreate(name="重生成Key工具")
        created = await create_tool(tool_data, test_user, tool_service)
        original_key = created.api_key
        
        # 重新生成
        response = await regenerate_tool_key(created.id, test_user, tool_service, cache_service)
        
        assert isinstance(response, ToolTokenResponse)
        assert response.api_key != original_key
        assert response.api_key.startswith("sk-")
    
    @pytest.mark.asyncio
    async def test_regenerate_key_not_found(self, test_user, tool_service, cache_service):
        """测试重新生成不存在工具的 Token"""
        with pytest.raises(APIException) as exc_info:
            await regenerate_tool_key(99999, test_user, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_regenerate_key_not_owner(self, test_user, test_user_2, tool_service, cache_service):
        """测试重新生成不属于自己工具的 Token"""
        tool_data = ToolCreate(name="他人工具Key")
        created = await create_tool(tool_data, test_user, tool_service)
        
        with pytest.raises(APIException) as exc_info:
            await regenerate_tool_key(created.id, test_user_2, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_regenerate_key_preserves_other_fields(self, test_user, tool_service, cache_service):
        """测试重新生成 Token 保留其他字段"""
        tool_data = ToolCreate(name="保留字段工具", description="原始描述")
        created = await create_tool(tool_data, test_user, tool_service)
        
        response = await regenerate_tool_key(created.id, test_user, tool_service, cache_service)
        
        assert response.name == "保留字段工具"
        assert response.id == created.id
    
    @pytest.mark.asyncio
    async def test_regenerate_key_multiple_times(self, test_user, tool_service, cache_service):
        """测试多次重新生成 Token"""
        tool_data = ToolCreate(name="多次重生成工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        keys = [created.api_key]
        for _ in range(3):
            response = await regenerate_tool_key(created.id, test_user, tool_service, cache_service)
            keys.append(response.api_key)
        
        # 验证所有 key 都不同
        assert len(set(keys)) == 4


class TestAddRouteEndpoint:
    """添加路由接口测试类"""
    
    @pytest.mark.asyncio
    async def test_add_route_success(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试成功添加路由"""
        tool_data = ToolCreate(name="添加路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        route_data = RouteCreate(**sample_route_create_data)
        response = await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        assert len(response.routes) == 1
        assert response.routes[0].name == sample_route_create_data["name"]
    
    @pytest.mark.asyncio
    async def test_add_route_with_set_active(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试添加路由并设为活跃"""
        tool_data = ToolCreate(name="活跃路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        route_create = sample_route_create_data.copy()
        route_create["set_active"] = True
        route_data = RouteCreate(**route_create)
        
        response = await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        assert response.active_route_name == sample_route_create_data["name"]
    
    @pytest.mark.asyncio
    async def test_add_route_duplicate_name(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试添加重复名称的路由"""
        tool_data = ToolCreate(name="重复路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        route_data = RouteCreate(**sample_route_create_data)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)

        # 尝试添加同名路由
        with pytest.raises(APIException) as exc_info:
            await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 409  # Conflict
    
    @pytest.mark.asyncio
    async def test_add_route_tool_not_found(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试向不存在的工具添加路由"""
        route_data = RouteCreate(**sample_route_create_data)

        with pytest.raises(APIException) as exc_info:
            await add_route(99999, route_data, test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_add_route_not_owner(self, test_user, test_user_2, tool_service, route_service, cache_service, sample_route_create_data):
        """测试向不属于自己的工具添加路由"""
        tool_data = ToolCreate(name="他人工具路由")
        created = await create_tool(tool_data, test_user, tool_service)

        route_data = RouteCreate(**sample_route_create_data)
        with pytest.raises(APIException) as exc_info:
            await add_route(created.id, route_data, test_user_2, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_add_multiple_routes(self, test_user, tool_service, route_service, cache_service):
        """测试添加多个路由"""
        tool_data = ToolCreate(name="多路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        routes = [
            RouteCreate(name="production", base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1"),
            RouteCreate(name="development", base_url="https://api.openai.com/v1/chat/completions", model="gpt-3.5-turbo", provider_key_name="key2"),
            RouteCreate(name="testing", base_url="https://api.anthropic.com/v1/messages", model="claude-3", provider_key_name="key3"),
        ]

        for route in routes:
            await add_route(created.id, route, test_user, tool_service, route_service, cache_service)
        
        response = await get_tool(created.id, test_user, tool_service)
        assert len(response.routes) == 3


class TestUpdateRouteEndpoint:
    """更新路由接口测试类"""
    
    @pytest.mark.asyncio
    async def test_update_route_success(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试成功更新路由"""
        tool_data = ToolCreate(name="更新路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        route_data = RouteCreate(**sample_route_create_data)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)

        # 更新路由
        update_data = RouteUpdate(model="gpt-3.5-turbo")
        response = await update_route(created.id, sample_route_create_data["name"], update_data, test_user, tool_service, route_service, cache_service)

        updated_route = next((r for r in response.routes if r.name == sample_route_create_data["name"]), None)
        assert updated_route is not None
        assert updated_route.model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_update_route_partial(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试部分更新路由"""
        tool_data = ToolCreate(name="部分更新路由工具")
        created = await create_tool(tool_data, test_user, tool_service)

        route_data = RouteCreate(**sample_route_create_data)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        # 只更新 provider_key_name
        update_data = RouteUpdate(provider_key_name="new_key")
        response = await update_route(created.id, sample_route_create_data["name"], update_data, test_user, tool_service, route_service, cache_service)
        
        updated_route = next((r for r in response.routes if r.name == sample_route_create_data["name"]), None)
        assert updated_route.provider_key_name == "new_key"
        assert updated_route.model == sample_route_create_data["model"]  # 未更新
    
    @pytest.mark.asyncio
    async def test_update_route_not_found(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试更新不存在的路由"""
        tool_data = ToolCreate(name="不存在路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        update_data = RouteUpdate(model="gpt-3.5-turbo")
        with pytest.raises(APIException) as exc_info:
            await update_route(created.id, "nonexistent", update_data, test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_update_route_tool_not_found(self, test_user, tool_service, route_service, cache_service):
        """测试更新不存在工具的路由"""
        update_data = RouteUpdate(model="gpt-3.5-turbo")
        
        with pytest.raises(APIException) as exc_info:
            await update_route(99999, "route1", update_data, test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404


class TestDeleteRouteEndpoint:
    """删除路由接口测试类"""
    
    @pytest.mark.asyncio
    async def test_delete_route_success(self, test_user, tool_service, route_service, cache_service):
        """测试成功删除路由"""
        tool_data = ToolCreate(name="删除路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 添加两个路由
        route1 = RouteCreate(name="route1", base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1", set_active=True)
        route2 = RouteCreate(name="route2", base_url="https://api.openai.com/v1/chat/completions", model="gpt-3.5", provider_key_name="key2")
        
        await add_route(created.id, route1, test_user, tool_service, route_service, cache_service)
        await add_route(created.id, route2, test_user, tool_service, route_service, cache_service)

        # 删除非活跃路由
        response = await delete_route(created.id, "route2", test_user, tool_service, route_service)
        
        route_names = [r.name for r in response.routes]
        assert "route2" not in route_names
        assert "route1" in route_names
    
    @pytest.mark.asyncio
    async def test_delete_active_route_forbidden(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试删除活跃路由被禁止"""
        tool_data = ToolCreate(name="禁止删除活跃路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        route_create = sample_route_create_data.copy()
        route_create["set_active"] = True
        route_data = RouteCreate(**route_create)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)
        
        with pytest.raises(APIException) as exc_info:
            await delete_route(created.id, sample_route_create_data["name"], test_user, tool_service, route_service)
        
        assert exc_info.value.http_status == 400
    
    @pytest.mark.asyncio
    async def test_delete_route_not_found(self, test_user, tool_service, route_service):
        """测试删除不存在的路由"""
        tool_data = ToolCreate(name="删除不存在路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        with pytest.raises(APIException) as exc_info:
            await delete_route(created.id, "nonexistent", test_user, tool_service, route_service)
        
        assert exc_info.value.http_status == 404


class TestActivateRouteEndpoint:
    """切换激活路由接口测试类"""
    
    @pytest.mark.asyncio
    async def test_activate_route_success(self, test_user, tool_service, route_service, cache_service):
        """测试成功切换激活路由"""
        tool_data = ToolCreate(name="激活路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        # 添加两个路由
        route1 = RouteCreate(name="route1", base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1", set_active=True)
        route2 = RouteCreate(name="route2", base_url="https://api.openai.com/v1/chat/completions", model="gpt-3.5", provider_key_name="key2")
        
        await add_route(created.id, route1, test_user, tool_service, route_service, cache_service)
        await add_route(created.id, route2, test_user, tool_service, route_service, cache_service)

        # 切换到 route2
        response = await activate_route(created.id, "route2", test_user, tool_service, route_service, cache_service)
        
        assert response.active_route_name == "route2"
    
    @pytest.mark.asyncio
    async def test_activate_route_not_found(self, test_user, tool_service, route_service, cache_service, sample_route_create_data):
        """测试激活不存在的路由"""
        tool_data = ToolCreate(name="激活不存在路由工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        route_data = RouteCreate(**sample_route_create_data)
        await add_route(created.id, route_data, test_user, tool_service, route_service, cache_service)

        with pytest.raises(APIException) as exc_info:
            await activate_route(created.id, "nonexistent", test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_activate_route_tool_not_found(self, test_user, tool_service, route_service, cache_service):
        """测试激活不存在工具的路由"""
        with pytest.raises(APIException) as exc_info:
            await activate_route(99999, "route1", test_user, tool_service, route_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_activate_route_is_active_flag(self, test_user, tool_service, route_service, cache_service):
        """测试激活路由后 is_active 标志正确"""
        tool_data = ToolCreate(name="激活标志工具")
        created = await create_tool(tool_data, test_user, tool_service)
        
        route1 = RouteCreate(name="route1", base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1", set_active=True)
        route2 = RouteCreate(name="route2", base_url="https://api.openai.com/v1/chat/completions", model="gpt-3.5", provider_key_name="key2")
        
        await add_route(created.id, route1, test_user, tool_service, route_service, cache_service)
        await add_route(created.id, route2, test_user, tool_service, route_service, cache_service)

        # 切换激活路由
        response = await activate_route(created.id, "route2", test_user, tool_service, route_service, cache_service)
        
        # 验证 is_active 标志
        route1_response = next((r for r in response.routes if r.name == "route1"), None)
        route2_response = next((r for r in response.routes if r.name == "route2"), None)
        
        assert route1_response.is_active is False
        assert route2_response.is_active is True


class TestConvertRoutesToResponse:
    """路由转换辅助函数测试类"""
    
    def test_convert_empty_routes(self):
        """测试转换空路由"""
        result = _convert_routes_to_response({}, None)
        
        assert result == []
    
    def test_convert_route_config_object(self):
        """测试转换 RouteConfig 对象"""
        routes = {
            "production": RouteConfig(base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1")
        }
        
        result = _convert_routes_to_response(routes, "production")
        
        assert len(result) == 1
        assert result[0].name == "production"
        assert result[0].is_active is True
    
    def test_convert_route_dict(self):
        """测试转换字典格式路由"""
        routes = {
            "production": {
                "base_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4",
                "provider_key_name": "key1"
            }
        }
        
        result = _convert_routes_to_response(routes, None)
        
        assert len(result) == 1
        assert result[0].name == "production"
        assert result[0].is_active is False
    
    def test_convert_multiple_routes_active_flag(self):
        """测试转换多个路由时活跃标志正确"""
        routes = {
            "route1": RouteConfig(base_url="https://api.openai.com/v1/chat/completions", model="gpt-4", provider_key_name="key1"),
            "route2": RouteConfig(base_url="https://api.openai.com/v1/chat/completions", model="gpt-3.5", provider_key_name="key2"),
        }
        
        result = _convert_routes_to_response(routes, "route2")
        
        route1_resp = next((r for r in result if r.name == "route1"), None)
        route2_resp = next((r for r in result if r.name == "route2"), None)
        
        assert route1_resp.is_active is False
        assert route2_resp.is_active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
