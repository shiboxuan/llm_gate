"""
Provider Keys API 集成测试

测试真实 API 的 Provider Key 管理功能
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
class TestProviderKeysCRUDIntegration:
    """Provider Keys CRUD 集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_provider_key")
        
        # ===== 测试点: 创建新的Provider Key =====
        TestPrinter.print_test_point(
            "创建新的Provider Key",
            "验证可以成功创建Provider Key，API Key应被加密存储"
        )
        
        key_data = TestDataFactory.provider_key_data()
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data
        )
        
        TestPrinter.print_expected(
            {
                "status_code": 201,
                "has_id": True,
                "has_name": True,
                "name": key_data["name"],
                "status": 1,
                "api_key_not_exposed": True
            },
            "创建成功，返回Key信息，但不返回明文API Key"
        )
        
        response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 201, f"创建失败: {data}"
        assert "id" in data, "响应缺少 id"
        assert "name" in data, "响应缺少 name"
        assert data["name"] == key_data["name"], f"name 不匹配"
        assert data["status"] == 1, f"status 应为 1"
        # API Key 应该被加密存储，不应返回明文
        assert "api_key" not in data or data.get("api_key") != key_data["api_key"], "API Key 不应以明文返回"
        
        TestPrinter.print_result(TestStatus.PASS, "Provider Key 创建成功")
    
    @pytest.mark.asyncio
    async def test_create_provider_key_with_special_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建带特殊字符名称的 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_provider_key_with_special_name")
        
        # ===== 测试点: 特殊字符名称 =====
        TestPrinter.print_test_point(
            "创建带特殊字符的名称",
            "验证名称支持下划线、连字符等特殊字符"
        )
        
        special_name = f"openai-prod_v2_{RandomDataGenerator.unique_id()}"
        key_data = TestDataFactory.provider_key_data(name=special_name)
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 201, "name": special_name},
            "特殊字符名称应被接受"
        )
        
        response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 201, f"创建失败: {data}"
        assert data["name"] == special_name, f"名称不匹配"
        
        TestPrinter.print_result(TestStatus.PASS, "特殊字符名称创建成功")
    
    @pytest.mark.asyncio
    async def test_list_provider_keys(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取 Provider Keys 列表"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_list_provider_keys")
        
        # 先创建一个 Key
        key_data = TestDataFactory.provider_key_data()
        create_response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        assert create_response.status_code == 201
        created_key = create_response.json()
        
        # ===== 测试点: 获取Key列表 =====
        TestPrinter.print_test_point(
            "获取Provider Keys列表",
            "验证可以获取当前用户的所有Keys"
        )
        
        TestPrinter.print_request(
            method="GET",
            url="/api/provider-keys/",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "is_list": True, "contains_created_key": True},
            "返回列表，包含刚创建的Key"
        )
        
        response = await api_client.get("/api/provider-keys/", headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"获取列表失败: {data}"
        assert isinstance(data, list), "响应应为列表"
        
        key_ids = [k["id"] for k in data]
        assert created_key["id"] in key_ids, f"刚创建的Key不在列表中"
        
        TestPrinter.print_result(TestStatus.PASS, f"成功获取列表，包含 {len(data)} 个Keys")
    
    @pytest.mark.asyncio
    async def test_get_provider_key_detail(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取 Provider Key 详情"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_provider_key_detail")
        
        # 创建 Key
        key_data = TestDataFactory.provider_key_data()
        create_response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        created_key = create_response.json()
        
        # ===== 测试点: 获取Key详情 =====
        TestPrinter.print_test_point(
            "获取Provider Key详情",
            "验证可以通过ID获取Key详细信息"
        )
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/provider-keys/{created_key['id']}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "id": created_key["id"], "name": key_data["name"]},
            "返回正确的Key详情"
        )
        
        response = await api_client.get(f"/api/provider-keys/{created_key['id']}", headers=develop_auth_headers)
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"获取详情失败: {data}"
        assert data["id"] == created_key["id"], "ID 不匹配"
        assert data["name"] == key_data["name"], "名称不匹配"
        
        TestPrinter.print_result(TestStatus.PASS, "成功获取Key详情")
    
    @pytest.mark.asyncio
    async def test_get_provider_key_not_found(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试获取不存在的 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_provider_key_not_found")
        
        # ===== 测试点: 获取不存在的Key =====
        TestPrinter.print_test_point(
            "获取不存在的Provider Key",
            "验证请求不存在的Key ID返回404"
        )
        
        non_existent_id = 999999
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/provider-keys/{non_existent_id}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(404, "不存在的Key应返回404")
        
        response = await api_client.get(f"/api/provider-keys/{non_existent_id}", headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        
        TestPrinter.print_result(TestStatus.PASS, "正确返回404")
    
    @pytest.mark.asyncio
    async def test_update_provider_key_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试更新 Provider Key 名称"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_update_provider_key_name")
        
        # 创建 Key
        key_data = TestDataFactory.provider_key_data()
        create_response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        created_key = create_response.json()
        
        # ===== 测试点: 更新Key名称 =====
        TestPrinter.print_test_point(
            "更新Provider Key名称",
            "验证可以更新Key的名称"
        )
        
        new_name = RandomDataGenerator.provider_key_name("updated")
        update_data = {"name": new_name}
        
        TestPrinter.print_request(
            method="PUT",
            url=f"/api/provider-keys/{created_key['id']}",
            headers=develop_auth_headers,
            body=update_data
        )
        
        TestPrinter.print_expected(
            {"status_code": 200, "name": new_name},
            "名称更新成功"
        )
        
        response = await api_client.put(
            f"/api/provider-keys/{created_key['id']}", 
            json=update_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"更新失败: {data}"
        assert data["name"] == new_name, f"名称未更新"
        
        TestPrinter.print_result(TestStatus.PASS, "名称更新成功")
    
    @pytest.mark.asyncio
    async def test_update_provider_key_api_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试更新 Provider Key 的 API Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_update_provider_key_api_key")
        
        # 创建 Key
        key_data = TestDataFactory.provider_key_data()
        create_response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        created_key = create_response.json()
        
        # ===== 测试点: 更新API Key =====
        TestPrinter.print_test_point(
            "更新Provider Key的API Key",
            "验证可以更新Key的API密钥"
        )
        
        new_api_key = RandomDataGenerator.api_key()
        update_data = {"api_key": new_api_key}
        
        TestPrinter.print_request(
            method="PUT",
            url=f"/api/provider-keys/{created_key['id']}",
            headers=develop_auth_headers,
            body=update_data
        )
        
        TestPrinter.print_expected(200, "API Key更新成功，但不返回明文")
        
        response = await api_client.put(
            f"/api/provider-keys/{created_key['id']}", 
            json=update_data, 
            headers=develop_auth_headers
        )
        data = response.json()
        
        TestPrinter.print_actual(data, response.status_code)
        
        assert response.status_code == 200, f"更新失败: {data}"
        # API Key 更新成功，但不应返回明文
        assert "api_key" not in data or data.get("api_key") != new_api_key, "更新后也不应返回明文API Key"
        
        TestPrinter.print_result(TestStatus.PASS, "API Key更新成功")
    
    @pytest.mark.asyncio
    async def test_delete_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试删除 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_delete_provider_key")
        
        # 创建 Key
        key_data = TestDataFactory.provider_key_data()
        create_response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        created_key = create_response.json()
        
        # ===== 测试点1: 删除Key =====
        TestPrinter.print_test_point(
            "删除Provider Key",
            "验证可以成功删除Key"
        )
        
        TestPrinter.print_request(
            method="DELETE",
            url=f"/api/provider-keys/{created_key['id']}",
            headers=develop_auth_headers
        )
        
        TestPrinter.print_expected(204, "删除成功返回204")
        
        delete_response = await api_client.delete(
            f"/api/provider-keys/{created_key['id']}", 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual({}, delete_response.status_code)
        
        assert delete_response.status_code == 204, f"删除失败: {delete_response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "删除成功")
        
        # ===== 测试点2: 验证已删除 =====
        TestPrinter.print_test_point(
            "验证Key已删除",
            "确认删除后无法再获取该Key"
        )
        
        TestPrinter.print_expected(404, "已删除的Key应返回404")
        
        get_response = await api_client.get(
            f"/api/provider-keys/{created_key['id']}", 
            headers=develop_auth_headers
        )
        
        TestPrinter.print_actual(get_response.json() if get_response.text else {}, get_response.status_code)
        
        assert get_response.status_code == 404, f"期望 404，实际: {get_response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "确认Key已删除")


@pytest.mark.integration
@pytest.mark.develop_only
class TestProviderKeysValidationIntegration:
    """Provider Keys 数据验证集成测试"""
    
    @pytest.mark.asyncio
    async def test_create_key_empty_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建空名称的 Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_key_empty_name")
        
        # ===== 测试点: 空名称 =====
        TestPrinter.print_test_point(
            "创建空名称的Provider Key",
            "验证空名称被拒绝"
        )
        
        key_data = {
            "name": "",
            "api_key": RandomDataGenerator.api_key()
        }
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data
        )
        
        TestPrinter.print_expected([400, 422], "空名称应返回验证错误")
        
        response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code in (400, 422), f"期望 400 或 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝空名称: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_create_key_empty_api_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建空 API Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_key_empty_api_key")
        
        # ===== 测试点: 空API Key =====
        TestPrinter.print_test_point(
            "创建空API Key的Provider Key",
            "验证空API Key被拒绝"
        )
        
        key_data = {
            "name": RandomDataGenerator.provider_key_name(),
            "api_key": ""
        }
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data
        )
        
        TestPrinter.print_expected([400, 422], "空API Key应返回验证错误")
        
        response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code in (400, 422), f"期望 400 或 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝空API Key: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_create_key_missing_fields(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建时缺少必填字段"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_key_missing_fields")
        
        # ===== 测试点: 缺少api_key字段 =====
        TestPrinter.print_test_point(
            "缺少必填字段api_key",
            "验证缺少api_key时返回422"
        )
        
        key_data = {
            "name": RandomDataGenerator.provider_key_name()
            # 缺少 api_key
        }
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data
        )
        
        TestPrinter.print_expected(422, "缺少必填字段应返回422")
        
        response = await api_client.post("/api/provider-keys/", json=key_data, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 422, f"期望 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回422验证错误")
    
    @pytest.mark.asyncio
    async def test_create_duplicate_key_name(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试创建重复名称的Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_create_duplicate_key_name")
        
        # 先创建一个Key
        key_name = RandomDataGenerator.provider_key_name()
        key_data1 = TestDataFactory.provider_key_data(name=key_name)
        response1 = await api_client.post("/api/provider-keys/", json=key_data1, headers=develop_auth_headers)
        assert response1.status_code == 201, f"第一次创建失败: {response1.json()}"
        
        # ===== 测试点: 重复名称 =====
        TestPrinter.print_test_point(
            "创建重复名称的Provider Key",
            "验证同一用户下不能创建同名Key"
        )
        
        key_data2 = TestDataFactory.provider_key_data(name=key_name)
        
        TestPrinter.print_request(
            method="POST",
            url="/api/provider-keys/",
            headers=develop_auth_headers,
            body=key_data2
        )
        
        TestPrinter.print_expected([400, 409], "重复名称应返回错误")
        
        response2 = await api_client.post("/api/provider-keys/", json=key_data2, headers=develop_auth_headers)
        
        TestPrinter.print_actual(response2.json() if response2.text else {}, response2.status_code)
        
        assert response2.status_code in (400, 409), f"期望 400 或 409，实际: {response2.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝重复名称: {response2.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestProviderKeysAuthorizationIntegration:
    """Provider Keys 授权集成测试"""
    
    @pytest.mark.asyncio
    async def test_access_without_auth(self, api_client: AsyncClient):
        """测试未认证访问 Provider Keys"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_access_without_auth")
        
        # ===== 测试点: 未认证访问 =====
        TestPrinter.print_test_point(
            "未认证访问Provider Keys列表",
            "验证未携带Token的请求被拒绝"
        )
        
        TestPrinter.print_request(
            method="GET",
            url="/api/provider-keys/"
        )
        
        TestPrinter.print_expected([401, 403], "未认证请求应被拒绝")
        
        response = await api_client.get("/api/provider-keys/")
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code in (401, 403), f"期望 401 或 403，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_access_other_user_key(self, api_client: AsyncClient):
        """测试访问其他用户的 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_access_other_user_key")
        
        # 用户1 登录并创建 Key
        user1_login = TestDataFactory.login_data()
        login_resp1 = await api_client.post("/api/auth/login", json=user1_login)
        token1 = login_resp1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        key_data = TestDataFactory.provider_key_data()
        create_resp = await api_client.post("/api/provider-keys/", json=key_data, headers=headers1)
        key_id = create_resp.json()["id"]
        
        print(f"   用户1创建了Key ID: {key_id}")
        
        # 用户2 登录
        user2_login = TestDataFactory.login_data()
        login_resp2 = await api_client.post("/api/auth/login", json=user2_login)
        token2 = login_resp2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # ===== 测试点: 用户2尝试访问用户1的Key =====
        TestPrinter.print_test_point(
            "用户尝试访问其他用户的Key",
            "验证用户无法访问其他用户创建的Key"
        )
        
        TestPrinter.print_request(
            method="GET",
            url=f"/api/provider-keys/{key_id}",
            headers=headers2
        )
        
        TestPrinter.print_expected(404, "访问其他用户的Key应返回404")
        
        response = await api_client.get(f"/api/provider-keys/{key_id}", headers=headers2)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确阻止跨用户访问")
    
    @pytest.mark.asyncio
    async def test_delete_other_user_key(self, api_client: AsyncClient):
        """测试删除其他用户的 Provider Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_delete_other_user_key")
        
        # 用户1 登录并创建 Key
        user1_login = TestDataFactory.login_data()
        login_resp1 = await api_client.post("/api/auth/login", json=user1_login)
        token1 = login_resp1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        key_data = TestDataFactory.provider_key_data()
        create_resp = await api_client.post("/api/provider-keys/", json=key_data, headers=headers1)
        key_id = create_resp.json()["id"]
        
        print(f"   用户1创建了Key ID: {key_id}")
        
        # 用户2 登录
        user2_login = TestDataFactory.login_data()
        login_resp2 = await api_client.post("/api/auth/login", json=user2_login)
        token2 = login_resp2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # ===== 测试点: 用户2尝试删除用户1的Key =====
        TestPrinter.print_test_point(
            "用户尝试删除其他用户的Key",
            "验证用户无法删除其他用户创建的Key"
        )
        
        TestPrinter.print_request(
            method="DELETE",
            url=f"/api/provider-keys/{key_id}",
            headers=headers2
        )
        
        TestPrinter.print_expected(404, "删除其他用户的Key应返回404")
        
        response = await api_client.delete(f"/api/provider-keys/{key_id}", headers=headers2)
        
        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)
        
        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        
        # 验证 Key 未被删除（用户1仍能访问）
        verify_response = await api_client.get(f"/api/provider-keys/{key_id}", headers=headers1)
        assert verify_response.status_code == 200, "Key不应被删除"
        
        TestPrinter.print_result(TestStatus.PASS, "正确阻止跨用户删除，Key仍存在")


@pytest.mark.integration
@pytest.mark.develop_only
class TestProviderKeysMultipleUsersIntegration:
    """Provider Keys 多用户场景集成测试"""
    
    @pytest.mark.asyncio
    async def test_user_only_sees_own_keys(self, api_client: AsyncClient):
        """测试用户只能看到自己的 Keys"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_user_only_sees_own_keys")
        
        # 用户1 登录并创建 Key
        user1_login = TestDataFactory.login_data()
        login_resp1 = await api_client.post("/api/auth/login", json=user1_login)
        token1 = login_resp1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        key_name_1 = RandomDataGenerator.provider_key_name("user1")
        key_data1 = TestDataFactory.provider_key_data(name=key_name_1)
        await api_client.post("/api/provider-keys/", json=key_data1, headers=headers1)
        
        print(f"   用户1创建了Key: {key_name_1}")
        
        # 用户2 登录并创建 Key
        user2_login = TestDataFactory.login_data()
        login_resp2 = await api_client.post("/api/auth/login", json=user2_login)
        token2 = login_resp2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        key_name_2 = RandomDataGenerator.provider_key_name("user2")
        key_data2 = TestDataFactory.provider_key_data(name=key_name_2)
        await api_client.post("/api/provider-keys/", json=key_data2, headers=headers2)
        
        print(f"   用户2创建了Key: {key_name_2}")
        
        # ===== 测试点: 验证用户只能看到自己的Keys =====
        TestPrinter.print_test_point(
            "用户只能看到自己的Keys",
            "验证列表接口返回的Keys属于当前用户"
        )
        
        # 用户1 获取列表
        list_resp1 = await api_client.get("/api/provider-keys/", headers=headers1)
        keys1 = list_resp1.json()
        key_names_1 = [k["name"] for k in keys1]
        
        print(f"   用户1看到的Keys: {key_names_1}")
        
        TestPrinter.print_expected(
            {"user1_sees_own_key": True, "user1_not_sees_user2_key": True},
            "用户1应看到自己的Key，不应看到用户2的Key"
        )
        
        assert key_name_1 in key_names_1, f"用户1应能看到自己的Key: {key_name_1}"
        assert key_name_2 not in key_names_1, f"用户1不应看到用户2的Key: {key_name_2}"
        
        # 用户2 获取列表
        list_resp2 = await api_client.get("/api/provider-keys/", headers=headers2)
        keys2 = list_resp2.json()
        key_names_2 = [k["name"] for k in keys2]
        
        print(f"   用户2看到的Keys: {key_names_2}")
        
        assert key_name_2 in key_names_2, f"用户2应能看到自己的Key: {key_name_2}"
        assert key_name_1 not in key_names_2, f"用户2不应看到用户1的Key: {key_name_1}"
        
        TestPrinter.print_result(TestStatus.PASS, "用户数据隔离验证成功")
