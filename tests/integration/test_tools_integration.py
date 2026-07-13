"""
工具管理 API 集成测试

测试真实 API 的工具 CRUD 和路由管理功能
仅在 develop 模式下运行：pytest tests/integration/ --test-mode=develop

测试前提：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启（数据写入 debug_ 前缀表）

特点：
1. 每个测试都打印测试点、请求参数、期望结果、实际结果
2. 使用随机数据生成，确保可重复运行
3. 支持 debug 和线上环境
"""
import pytest
from httpx import AsyncClient

from tests.integration.test_utils import (
    TestPrinter,
    TestStatus,
    RandomDataGenerator,
    TestDataFactory,
    AssertHelper
)


@pytest.mark.integration
@pytest.mark.develop_only
class TestToolsCRUDIntegration:
    """工具 CRUD 集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_tool(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_tool")
        
        # ===== 测试点: 创建新工具 =====
        TestPrinter.print_test_point(
            "创建新工具",
            "验证可以成功创建工具，并返回API Key"
        )
        
        tool_data = TestDataFactory.tool_data()
        
        TestPrinter.print_request(
            method="POST",
            url="/api/tools/",
            headers=develop_auth_headers,
            body=tool_data
        )
        
        TestPrinter.print_expected(
            {
                "status_code": 201,
                "has_id": True,
                "has_api_key": True,
                "api_key_starts_with_sk": True,
                "name": tool_data["name"],
                "status": 1,
                "routes": [],
                "active_route_name": None
            },
            "创建成功，返回工具信息和API Key"
        )
        
        response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 201, f"创建失败: {data}"
        assert "id" in data, "响应缺少 id"
        assert "api_key" in data, "响应缺少 api_key（创建时应返回）"
        assert data["api_key"].startswith("sk-"), f"API Key 应以 sk- 开头"
        assert data["name"] == tool_data["name"], "名称不匹配"
        assert data["status"] == 1, "状态应为1"
        assert data["routes"] == [], "新工具应没有路由"
        assert data["active_route_name"] is None, "新工具应没有激活路由"
        
        TestPrinter.print_result(TestStatus.PASS, f"工具创建成功，API Key: {data['api_key'][:15]}...")
    
    @pytest.mark.asyncio
    async def test_list_tools(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取工具列表"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_list_tools")
        
        # 先创建一个工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        assert create_response.status_code == 201
        created_tool = create_response.json()
        
        # ===== 测试点: 获取工具列表 =====
        TestPrinter.print_test_point(
            "获取工具列表",
            "验证可以获取当前用户的所有工具"
        )
        
        TestPrinter.print_request(
            method="GET",
            url="/api/tools/",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "is_list": True, "contains_created_tool": True},
            "返回列表，包含刚创建的工具"
        )
        
        response = await api_client.get("/api/tools/", headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"获取列表失败: {data}"
        assert isinstance(data, list), "响应应为列表"
        
        tool_ids = [t["id"] for t in data]
        assert created_tool["id"] in tool_ids, "刚创建的工具不在列表中"
        
        TestPrinter.print_result(TestStatus.PASS, f"成功获取列表，包含 {len(data)} 个工具")
    
    @pytest.mark.asyncio
    async def test_get_tool_detail(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取工具详情"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_tool_detail")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        created_tool = create_response.json()
        
        # ===== 测试点: 获取工具详情 =====
        TestPrinter.print_test_point(
            "获取工具详情",
            "验证可以通过ID获取工具详细信息"
        )
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/tools/{created_tool['id']}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {
                "status_code": 200,
                "id": created_tool["id"],
                "name": tool_data["name"],
                "api_key_not_exposed": True
            },
            "返回工具详情，但不返回API Key"
        )
        
        response = await api_client.get(f"/api/tools/{created_tool['id']}", headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"获取详情失败: {data}"
        assert data["id"] == created_tool["id"], "ID不匹配"
        assert data["name"] == tool_data["name"], "名称不匹配"
        # 详情不应返回 api_key
        assert "api_key" not in data or data.get("api_key") is None, "详情不应返回API Key"
        
        TestPrinter.print_result(TestStatus.PASS, "成功获取工具详情")
    
    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取不存在的工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_tool_not_found")
        
        # ===== 测试点: 获取不存在的工具 =====
        TestPrinter.print_test_point(
            "获取不存在的工具",
            "验证请求不存在的工具ID返回404"
        )
        
        non_existent_id = 999999
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/tools/{non_existent_id}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(404, "不存在的工具应返回404")
        
        response = await api_client.get(f"/api/tools/{non_existent_id}", headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, "正确返回404")
    
    @pytest.mark.asyncio
    async def test_update_tool(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试更新工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_update_tool")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        created_tool = create_response.json()
        
        # ===== 测试点: 更新工具 =====
        TestPrinter.print_test_point(
            "更新工具名称和描述",
            "验证可以更新工具的基本信息"
        )
        
        new_name = RandomDataGenerator.tool_name("updated")
        new_description = "更新后的描述内容"
        update_data = {
            "name": new_name,
            "description": new_description
        }
        
        TestPrinter.print_request(
            method="PUT",
            url=f"/api/tools/{created_tool['id']}",
            headers=develop_auth_headers,
            body=update_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "name": new_name, "description": new_description},
            "更新成功"
        )
        
        response = await api_client.put(
            f"/api/tools/{created_tool['id']}", 
            json=update_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"更新失败: {data}"
        assert data["name"] == new_name, "名称未更新"
        assert data["description"] == new_description, "描述未更新"
        
        TestPrinter.print_result(TestStatus.PASS, "工具更新成功")
    
    @pytest.mark.asyncio
    async def test_delete_tool(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试删除工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_delete_tool")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        created_tool = create_response.json()
        
        # ===== 测试点1: 删除工具 =====
        TestPrinter.print_test_point(
            "删除工具",
            "验证可以成功删除工具"
        )
        
        TestPrinter.print_request(
            method="DELETE",
            url=f"/api/tools/{created_tool['id']}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(204, "删除成功返回204")
        
        delete_response = await api_client.delete(
            f"/api/tools/{created_tool['id']}", 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual({}, delete_response.status_code)
        
        assert delete_response.status_code == 204, f"删除失败: {delete_response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "删除成功")
        
        # ===== 测试点2: 验证已删除 =====
        TestPrinter.print_test_point(
            "验证工具已删除",
            "确认删除后无法再获取该工具"
        )
        
        get_response = await api_client.get(
            f"/api/tools/{created_tool['id']}", 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual(get_response.json() if get_response.text else {}, get_response.status_code)
        
        assert get_response.status_code == 404, f"期望 404，实际: {get_response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "确认工具已删除")
    
    @pytest.mark.asyncio
    async def test_regenerate_tool_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试重新生成工具 API Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_regenerate_tool_key")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        original_key = create_response.json()["api_key"]
        tool_id = create_response.json()["id"]
        
        print(f"   原始 API Key: {original_key[:15]}...")
        
        # ===== 测试点: 重新生成Key =====
        TestPrinter.print_test_point(
            "重新生成工具API Key",
            "验证可以重新生成工具的API Key，新Key与旧Key不同"
        )
        
        TestPrinter.print_request(
            method="POST",
            url=f"/api/tools/{tool_id}/regenerate-key",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "has_new_api_key": True, "new_key_different": True},
            "返回新的API Key"
        )
        
        response = await api_client.post(
            f"/api/tools/{tool_id}/regenerate-key", 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"重新生成失败: {data}"
        new_key = data["api_key"]
        
        assert new_key != original_key, "新Key应与旧Key不同"
        assert new_key.startswith("sk-"), "新Key应以sk-开头"
        
        print(f"   新 API Key: {new_key[:15]}...")
        
        TestPrinter.print_result(TestStatus.PASS, "API Key重新生成成功")


@pytest.mark.integration
@pytest.mark.develop_only
class TestToolRoutesIntegration:
    """工具路由管理集成测试"""
    
    @pytest.mark.asyncio
    async def test_add_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试添加路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_add_route")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        # ===== 测试点: 添加路由 =====
        TestPrinter.print_test_point(
            "添加路由到工具",
            "验证可以为工具添加路由配置"
        )
        
        route_name = RandomDataGenerator.route_name("production")
        route_data = TestDataFactory.route_data(name=route_name, set_active=False)
        
        TestPrinter.print_request(
            method="POST",
            url=f"/api/tools/{tool_id}/routes",
            headers=develop_auth_headers,
            body=route_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "routes_count": 1, "route_name": route_name},
            "路由添加成功"
        )
        
        response = await api_client.post(
            f"/api/tools/{tool_id}/routes", 
            json=route_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"添加路由失败: {data}"
        assert len(data["routes"]) == 1, "应有1个路由"
        assert data["routes"][0]["name"] == route_name, "路由名称不匹配"
        assert data["routes"][0]["model"] == route_data["model"], "model不匹配"
        assert data["routes"][0]["base_url"] == route_data["base_url"], "base_url不匹配"
        
        TestPrinter.print_result(TestStatus.PASS, "路由添加成功")
    
    @pytest.mark.asyncio
    async def test_add_route_and_activate(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试添加路由并设为活跃"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_add_route_and_activate")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        # ===== 测试点: 添加路由并激活 =====
        TestPrinter.print_test_point(
            "添加路由并设为活跃",
            "验证可以添加路由同时设置为活跃路由"
        )
        
        route_name = RandomDataGenerator.route_name("default")
        route_data = TestDataFactory.route_data(name=route_name, set_active=True)
        
        TestPrinter.print_request(
            method="POST",
            url=f"/api/tools/{tool_id}/routes",
            headers=develop_auth_headers,
            body=route_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "active_route_name": route_name, "is_active": True},
            "路由添加并激活成功"
        )
        
        response = await api_client.post(
            f"/api/tools/{tool_id}/routes", 
            json=route_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"添加路由失败: {data}"
        assert data["active_route_name"] == route_name, "活跃路由名称不匹配"
        assert data["routes"][0]["is_active"] is True, "路由应标记为活跃"
        
        TestPrinter.print_result(TestStatus.PASS, "路由添加并激活成功")
    
    @pytest.mark.asyncio
    async def test_add_multiple_routes(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试添加多个路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_add_multiple_routes")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        # ===== 测试点: 添加多个路由 =====
        TestPrinter.print_test_point(
            "添加多个路由",
            "验证可以为工具添加多个不同的路由配置"
        )
        
        routes = [
            TestDataFactory.route_data(
                name=RandomDataGenerator.route_name("production"),
                provider="openai",
                model="gpt-4"
            ),
            TestDataFactory.route_data(
                name=RandomDataGenerator.route_name("development"),
                provider="openai",
                model="gpt-3.5-turbo"
            ),
            TestDataFactory.route_data(
                name=RandomDataGenerator.route_name("testing"),
                provider="anthropic",
                base_url="https://api.anthropic.com",
                model="claude-3-opus"
            ),
        ]
        
        route_names = [r["name"] for r in routes]
        print(f"   准备添加路由: {route_names}")
        
        TestPrinter.print_expected(
            {"status_code": 200, "routes_count": 3},
            "所有路由都应成功添加"
        )
        
        for route in routes:
            response = await api_client.post(
                f"/api/tools/{tool_id}/routes", 
                json=route, 
                headers=develop_auth_headers
            )
            assert response.status_code == 200, f"添加路由 {route['name']} 失败"
        
        # 验证所有路由
        tool_response = await api_client.get(f"/api/tools/{tool_id}", headers=develop_auth_headers)
        data = tool_response.json()
        
        TestPrinter.print_actual(data, tool_response.status_code)
        
        assert len(data["routes"]) == 3, f"应有3个路由，实际: {len(data['routes'])}"
        actual_route_names = [r["name"] for r in data["routes"]]
        for name in route_names:
            assert name in actual_route_names, f"路由 {name} 未找到"
        
        TestPrinter.print_result(TestStatus.PASS, "成功添加3个路由")
    
    @pytest.mark.asyncio
    async def test_add_duplicate_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试添加重复名称的路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_add_duplicate_route")
        
        # 创建工具
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        # 添加第一个路由
        route_name = RandomDataGenerator.route_name("production")
        route_data = TestDataFactory.route_data(name=route_name)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route_data, headers=develop_auth_headers)
        
        # ===== 测试点: 添加重复名称路由 =====
        TestPrinter.print_test_point(
            "添加重复名称的路由",
            "验证不能添加同名路由"
        )
        
        TestPrinter.print_request(
            method="POST",
            url=f"/api/tools/{tool_id}/routes",
            headers=develop_auth_headers,
            body=route_data
        )
        
        TestPrinter.print_expected(409, "重复名称应返回409（Conflict）")
        
        response = await api_client.post(
            f"/api/tools/{tool_id}/routes", 
            json=route_data, 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 409, f"期望 409，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, "正确拒绝重复名称路由")
    
    @pytest.mark.asyncio
    async def test_update_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试更新路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_update_route")
        
        # 创建工具并添加路由
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        route_name = RandomDataGenerator.route_name("production")
        route_data = TestDataFactory.route_data(name=route_name, model="gpt-4")
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route_data, headers=develop_auth_headers)
        
        # ===== 测试点: 更新路由 =====
        TestPrinter.print_test_point(
            "更新路由配置",
            "验证可以更新路由的模型配置"
        )
        
        update_data = {"model": "gpt-3.5-turbo"}
        
        TestPrinter.print_request(
            method="PUT",
            url=f"/api/tools/{tool_id}/routes/{route_name}",
            headers=develop_auth_headers,
            body=update_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "model": "gpt-3.5-turbo"},
            "模型更新成功"
        )
        
        response = await api_client.put(
            f"/api/tools/{tool_id}/routes/{route_name}", 
            json=update_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"更新失败: {data}"
        updated_route = next((r for r in data["routes"] if r["name"] == route_name), None)
        assert updated_route is not None, "路由未找到"
        assert updated_route["model"] == "gpt-3.5-turbo", "模型未更新"
        
        TestPrinter.print_result(TestStatus.PASS, "路由更新成功")
    
    @pytest.mark.asyncio
    async def test_delete_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试删除路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_delete_route")
        
        # 创建工具并添加两个路由，激活第一个
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        route1_name = RandomDataGenerator.route_name("production")
        route1 = TestDataFactory.route_data(name=route1_name, set_active=True)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route1, headers=develop_auth_headers)
        
        route2_name = RandomDataGenerator.route_name("development")
        route2 = TestDataFactory.route_data(name=route2_name)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route2, headers=develop_auth_headers)
        
        # ===== 测试点: 删除非活跃路由 =====
        TestPrinter.print_test_point(
            "删除非活跃路由",
            "验证可以删除非活跃的路由"
        )
        
        TestPrinter.print_request(
            method="DELETE",
            url=f"/api/tools/{tool_id}/routes/{route2_name}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(200, "删除非活跃路由成功")
        
        response = await api_client.delete(
            f"/api/tools/{tool_id}/routes/{route2_name}", 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"删除失败: {data}"
        route_names = [r["name"] for r in data["routes"]]
        assert route2_name not in route_names, "路由应被删除"
        assert route1_name in route_names, "活跃路由应保留"
        
        TestPrinter.print_result(TestStatus.PASS, "非活跃路由删除成功")
    
    @pytest.mark.asyncio
    async def test_delete_active_route_forbidden(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试删除活跃路由被禁止"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_delete_active_route_forbidden")
        
        # 创建工具并添加活跃路由
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        route_name = RandomDataGenerator.route_name("production")
        route_data = TestDataFactory.route_data(name=route_name, set_active=True)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route_data, headers=develop_auth_headers)
        
        # ===== 测试点: 尝试删除活跃路由 =====
        TestPrinter.print_test_point(
            "尝试删除活跃路由",
            "验证不能删除当前激活的路由"
        )
        
        TestPrinter.print_request(
            method="DELETE",
            url=f"/api/tools/{tool_id}/routes/{route_name}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(400, "删除活跃路由应返回400")
        
        response = await api_client.delete(
            f"/api/tools/{tool_id}/routes/{route_name}", 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 400, f"期望 400，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, "正确拒绝删除活跃路由")
    
    @pytest.mark.asyncio
    async def test_activate_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试切换激活路由"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_activate_route")
        
        # 创建工具并添加两个路由
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        tool_id = create_response.json()["id"]
        
        route1_name = RandomDataGenerator.route_name("production")
        route1 = TestDataFactory.route_data(name=route1_name, set_active=True)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route1, headers=develop_auth_headers)
        
        route2_name = RandomDataGenerator.route_name("development")
        route2 = TestDataFactory.route_data(name=route2_name)
        await api_client.post(f"/api/tools/{tool_id}/routes", json=route2, headers=develop_auth_headers)
        
        print(f"   当前激活路由: {route1_name}")
        print(f"   准备切换到: {route2_name}")
        
        # ===== 测试点: 切换激活路由 =====
        TestPrinter.print_test_point(
            "切换激活路由",
            "验证可以切换工具的激活路由"
        )
        
        TestPrinter.print_request(
            method="PUT",
            url=f"/api/tools/{tool_id}/activate/{route2_name}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "active_route_name": route2_name},
            "激活路由切换成功"
        )
        
        response = await api_client.put(
            f"/api/tools/{tool_id}/activate/{route2_name}", 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"切换失败: {data}"
        assert data["active_route_name"] == route2_name, "激活路由名称不匹配"
        
        # 验证 is_active 标志
        production_route = next((r for r in data["routes"] if r["name"] == route1_name), None)
        development_route = next((r for r in data["routes"] if r["name"] == route2_name), None)
        
        assert production_route["is_active"] is False, "原路由应标记为非活跃"
        assert development_route["is_active"] is True, "新路由应标记为活跃"
        
        TestPrinter.print_result(TestStatus.PASS, "激活路由切换成功")


@pytest.mark.integration
@pytest.mark.develop_only
class TestToolsAuthorizationIntegration:
    """工具授权集成测试"""
    
    @pytest.mark.asyncio
    async def test_access_without_auth(self, api_client: AsyncClient):
        """测试未认证访问工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_access_without_auth")
        
        # ===== 测试点: 未认证访问 =====
        TestPrinter.print_test_point(
            "未认证访问工具列表",
            "验证未携带Token的请求被拒绝"
        )
        
        TestPrinter.print_request(
            method="GET",
            url="/api/tools/"
        )
        
        TestPrinter.print_expected([401, 403], "未认证请求应被拒绝")
        
        response = await api_client.get("/api/tools/")
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code in (401, 403), f"期望 401 或 403，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_access_other_user_tool(self, api_client: AsyncClient):
        """测试访问其他用户的工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_access_other_user_tool")
        
        # 用户1 登录并创建工具
        user1_login = TestDataFactory.login_data()
        login_resp1 = await api_client.post("/api/auth/login", json=user1_login)
        token1 = login_resp1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        tool_data = TestDataFactory.tool_data()
        create_resp = await api_client.post("/api/tools/", json=tool_data, headers=headers1)
        tool_id = create_resp.json()["id"]
        
        print(f"   用户1创建了工具 ID: {tool_id}")
        
        # 用户2 登录
        user2_login = TestDataFactory.login_data()
        login_resp2 = await api_client.post("/api/auth/login", json=user2_login)
        token2 = login_resp2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # ===== 测试点: 用户2尝试访问用户1的工具 =====
        TestPrinter.print_test_point(
            "用户尝试访问其他用户的工具",
            "验证用户无法访问其他用户创建的工具"
        )
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/tools/{tool_id}",
            headers=headers2
        )
        
        TestPrinter.print_expected(404, "访问其他用户的工具应返回404")
        
        response = await api_client.get(f"/api/tools/{tool_id}", headers=headers2)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, "正确阻止跨用户访问")
    
    @pytest.mark.asyncio
    async def test_user_only_sees_own_tools(self, api_client: AsyncClient):
        """测试用户只能看到自己的工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_user_only_sees_own_tools")
        
        # 用户1 登录并创建工具
        user1_login = TestDataFactory.login_data()
        login_resp1 = await api_client.post("/api/auth/login", json=user1_login)
        token1 = login_resp1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        tool1_name = RandomDataGenerator.tool_name("user1")
        tool1_data = TestDataFactory.tool_data(name=tool1_name)
        await api_client.post("/api/tools/", json=tool1_data, headers=headers1)
        
        print(f"   用户1创建了工具: {tool1_name}")
        
        # 用户2 登录并创建工具
        user2_login = TestDataFactory.login_data()
        login_resp2 = await api_client.post("/api/auth/login", json=user2_login)
        token2 = login_resp2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        tool2_name = RandomDataGenerator.tool_name("user2")
        tool2_data = TestDataFactory.tool_data(name=tool2_name)
        await api_client.post("/api/tools/", json=tool2_data, headers=headers2)
        
        print(f"   用户2创建了工具: {tool2_name}")
        
        # ===== 测试点: 验证用户只能看到自己的工具 =====
        TestPrinter.print_test_point(
            "用户只能看到自己的工具",
            "验证列表接口返回的工具属于当前用户"
        )
        
        # 用户1 获取列表
        list_resp1 = await api_client.get("/api/tools/", headers=headers1)
        tools1 = list_resp1.json()
        tool_names_1 = [t["name"] for t in tools1]
        
        print(f"   用户1看到的工具: {tool_names_1}")
        
        assert tool1_name in tool_names_1, f"用户1应能看到自己的工具"
        assert tool2_name not in tool_names_1, f"用户1不应看到用户2的工具"
        
        # 用户2 获取列表
        list_resp2 = await api_client.get("/api/tools/", headers=headers2)
        tools2 = list_resp2.json()
        tool_names_2 = [t["name"] for t in tools2]
        
        print(f"   用户2看到的工具: {tool_names_2}")
        
        assert tool2_name in tool_names_2, f"用户2应能看到自己的工具"
        assert tool1_name not in tool_names_2, f"用户2不应看到用户1的工具"
        
        TestPrinter.print_result(TestStatus.PASS, "用户数据隔离验证成功")


@pytest.mark.integration
@pytest.mark.develop_only
class TestToolsValidationIntegration:
    """工具数据验证集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_tool_empty_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建空名称的工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_tool_empty_name")
        
        # ===== 测试点: 空名称 =====
        TestPrinter.print_test_point(
            "创建空名称的工具",
            "验证空名称被拒绝"
        )
        
        tool_data = {"name": "", "description": "测试描述"}
        
        TestPrinter.print_request(
            method="POST",
            url="/api/tools/",
            headers=develop_auth_headers,
            body=tool_data
        )
        
        TestPrinter.print_expected([400, 422], "空名称应返回验证错误")
        
        response = await api_client.post("/api/tools/", json=tool_data, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code in (400, 422), f"期望 400 或 422，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝空名称: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_create_duplicate_tool_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建重复名称的工具"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_duplicate_tool_name")
        
        # 先创建一个工具
        tool_name = RandomDataGenerator.tool_name()
        tool_data1 = TestDataFactory.tool_data(name=tool_name)
        response1 = await api_client.post("/api/tools/", json=tool_data1, headers=develop_auth_headers)
        assert response1.status_code == 201, f"第一次创建失败: {response1.json()}"
        
        # ===== 测试点: 重复名称 =====
        TestPrinter.print_test_point(
            "创建重复名称的工具",
            "验证同一用户下不能创建同名工具"
        )
        
        tool_data2 = TestDataFactory.tool_data(name=tool_name)
        
        TestPrinter.print_request(
            method="POST",
            url="/api/tools/",
            headers=develop_auth_headers,
            body=tool_data2
        )
        
        TestPrinter.print_expected([400, 409], "重复名称应返回错误")
        
        response2 = await api_client.post("/api/tools/", json=tool_data2, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response2.json() if response2.text else {}, response2.status_code)
        
        assert response2.status_code in (400, 409), f"期望 400 或 409，实际: {response2.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝重复名称: {response2.status_code}")
