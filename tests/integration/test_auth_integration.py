"""
认证 API 集成测试

测试真实 API 的认证功能
仅在 develop 模式下运行：pytest tests/integration/ --test-mode=develop

测试前提：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启（LLM_GATE_DEBUG=true）

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
class TestAuthRegisterIntegration:
    """注册接口集成测试"""

    @pytest.mark.asyncio
    async def test_register_new_user(self, api_client: AsyncClient):
        """测试新用户注册"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_register_new_user")

        # ===== 测试点1: 新用户注册 =====
        TestPrinter.print_test_point(
            "新用户注册",
            "验证系统能创建新用户并返回有效Token"
        )

        # 准备请求数据
        register_data = TestDataFactory.register_data()

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/register",
            body=register_data
        )

        TestPrinter.print_expected(
            {
                "status_code": 200,
                "has_access_token": True,
                "token_type": "bearer",
                "user.username": register_data["username"],
                "user.status": 1
            },
            "新用户注册成功，返回JWT Token和用户信息"
        )

        # 发送请求
        response = await api_client.post("/api/auth/register", json=register_data)
        data = response.json()

        TestPrinter.print_actual(data, response.status_code)

        # 断言
        assert response.status_code == 200, f"注册失败: {data}"
        assert "access_token" in data, "响应缺少 access_token"
        assert "token_type" in data, "响应缺少 token_type"
        assert "user" in data, "响应缺少 user"
        assert data["token_type"] == "bearer", f"token_type 应为 bearer，实际: {data['token_type']}"

        user = data["user"]
        assert user["username"] == register_data["username"], "username 不匹配"
        assert user["status"] == 1, f"用户状态应为 1，实际: {user['status']}"

        TestPrinter.print_result(TestStatus.PASS, "新用户注册成功，所有字段验证通过")

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, api_client: AsyncClient):
        """测试注册重复用户名"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_register_duplicate_username")

        register_data = TestDataFactory.register_data()

        # 第一次注册
        response1 = await api_client.post("/api/auth/register", json=register_data)
        assert response1.status_code == 200, f"第一次注册失败: {response1.json()}"

        # 第二次注册相同用户名
        TestPrinter.print_test_point(
            "重复用户名注册",
            "验证重复用户名返回 409"
        )

        response2 = await api_client.post("/api/auth/register", json=register_data)

        TestPrinter.print_actual(response2.json() if response2.text else {}, response2.status_code)

        assert response2.status_code == 409, f"期望 409，实际: {response2.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回 409 冲突错误")


@pytest.mark.integration
@pytest.mark.develop_only
class TestAuthLoginIntegration:
    """登录接口集成测试"""

    @pytest.mark.asyncio
    async def test_login_after_register(self, api_client: AsyncClient):
        """测试注册后登录"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_login_after_register")

        # 先注册用户
        register_data = TestDataFactory.register_data()
        reg_response = await api_client.post("/api/auth/register", json=register_data)
        assert reg_response.status_code == 200, f"注册失败: {reg_response.json()}"
        user_id = reg_response.json()["user"]["id"]

        # ===== 测试点: 使用注册的凭据登录 =====
        TestPrinter.print_test_point(
            "注册后登录",
            "验证注册的凭据可以成功登录并返回同一用户"
        )

        login_data = {
            "username": register_data["username"],
            "password": register_data["password"]
        }

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/login",
            body=login_data
        )

        TestPrinter.print_expected(
            {"status_code": 200, "user.id": user_id},
            "登录应返回同一用户"
        )

        response = await api_client.post("/api/auth/login", json=login_data)
        data = response.json()

        TestPrinter.print_actual(data, response.status_code)

        assert response.status_code == 200, f"登录失败: {data}"
        assert data["user"]["id"] == user_id, f"用户ID不一致"
        TestPrinter.print_result(TestStatus.PASS, f"验证成功，同一用户ID: {data['user']['id']}")

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, api_client: AsyncClient):
        """测试密码错误登录失败"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_login_wrong_password")

        # 先注册用户
        register_data = TestDataFactory.register_data()
        await api_client.post("/api/auth/register", json=register_data)

        # 用错误密码登录
        TestPrinter.print_test_point(
            "密码错误登录",
            "验证密码错误时返回 401"
        )

        login_data = {
            "username": register_data["username"],
            "password": "wrongpassword123"
        }

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/login",
            body=login_data
        )

        TestPrinter.print_expected(401, "密码错误应返回 401")

        response = await api_client.post("/api/auth/login", json=login_data)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 401, f"期望 401，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回 401 认证失败")

    @pytest.mark.asyncio
    async def test_login_invalid_data_missing_fields(self, api_client: AsyncClient):
        """测试无效登录数据 - 缺少必填字段"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_login_invalid_data_missing_fields")

        # ===== 测试点1: 缺少 password =====
        TestPrinter.print_test_point(
            "缺少必填字段",
            "验证请求缺少 password 时返回 422"
        )

        invalid_data = {
            "username": RandomDataGenerator.username()
            # 缺少 password
        }

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/login",
            body=invalid_data
        )

        TestPrinter.print_expected(422, "缺少必填字段应返回 422 验证错误")

        response = await api_client.post("/api/auth/login", json=invalid_data)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 422, f"期望 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回 422 验证错误")

    @pytest.mark.asyncio
    async def test_login_invalid_data_empty_username(self, api_client: AsyncClient):
        """测试无效登录数据 - 空用户名"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_login_invalid_data_empty_username")

        # ===== 测试点: 空 username =====
        TestPrinter.print_test_point(
            "空 username",
            "验证 username 为空字符串时的处理"
        )

        invalid_data = {
            "username": "",
            "password": "somepassword123"
        }

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/login",
            body=invalid_data
        )

        TestPrinter.print_expected([400, 422], "空 username 应返回错误")

        response = await api_client.post("/api/auth/login", json=invalid_data)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        # 可能返回 400 或 422，取决于验证逻辑
        assert response.status_code in (400, 422), f"期望 400 或 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确返回错误状态码: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestAuthMeIntegration:
    """获取当前用户信息接口集成测试"""

    @pytest.mark.asyncio
    async def test_get_me_success(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试成功获取当前用户信息"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_me_success")

        # ===== 测试点: 使用有效Token获取用户信息 =====
        TestPrinter.print_test_point(
            "使用有效Token获取用户信息",
            "验证携带有效JWT Token可以获取当前用户信息"
        )

        TestPrinter.print_request(
            method="GET",
            url="/api/auth/me",
            headers=develop_auth_headers
        )

        TestPrinter.print_expected(
            {
                "status_code": 200,
                "has_id": True,
                "has_username": True,
                "has_email": True,
                "has_is_admin": True,
                "has_status": True
            },
            "返回当前用户完整信息"
        )

        response = await api_client.get("/api/auth/me", headers=develop_auth_headers)
        data = response.json()

        TestPrinter.print_actual(data, response.status_code)

        assert response.status_code == 200, f"获取用户信息失败: {data}"

        required_fields = ["id", "username", "email", "is_admin", "status"]
        for field in required_fields:
            assert field in data, f"响应缺少字段: {field}"

        TestPrinter.print_result(TestStatus.PASS, "成功获取用户信息，所有必填字段存在")

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, api_client: AsyncClient):
        """测试未提供 Token 获取用户信息"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_me_no_token")

        # ===== 测试点: 不携带Token访问 =====
        TestPrinter.print_test_point(
            "不携带Token访问受保护接口",
            "验证未认证请求被拒绝"
        )

        TestPrinter.print_request(
            method="GET",
            url="/api/auth/me",
            headers={}
        )

        TestPrinter.print_expected([401, 403], "未认证请求应返回 401 或 403")

        response = await api_client.get("/api/auth/me")

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code in (401, 403), f"期望 401 或 403，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, api_client: AsyncClient):
        """测试无效 Token 获取用户信息"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_me_invalid_token")

        # ===== 测试点: 使用无效Token =====
        TestPrinter.print_test_point(
            "使用无效Token访问",
            "验证无效Token被拒绝"
        )

        invalid_headers = {"Authorization": "Bearer invalid_token_12345"}

        TestPrinter.print_request(
            method="GET",
            url="/api/auth/me",
            headers=invalid_headers
        )

        TestPrinter.print_expected(401, "无效Token应返回 401")

        response = await api_client.get("/api/auth/me", headers=invalid_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 401, f"期望 401，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确拒绝无效Token")

    @pytest.mark.asyncio
    async def test_get_me_malformed_token(self, api_client: AsyncClient):
        """测试格式错误的 Token"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_get_me_malformed_token")

        # ===== 测试点: 格式错误的Authorization头 =====
        TestPrinter.print_test_point(
            "格式错误的Authorization头",
            "验证非Bearer格式的Token被拒绝"
        )

        malformed_headers = {"Authorization": "NotBearer some_token"}

        TestPrinter.print_request(
            method="GET",
            url="/api/auth/me",
            headers=malformed_headers
        )

        TestPrinter.print_expected([401, 403], "格式错误应返回认证失败")

        response = await api_client.get("/api/auth/me", headers=malformed_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code in (401, 403), f"期望 401 或 403，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理格式错误的Token: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestAuthTokenIntegration:
    """Token 相关集成测试"""

    @pytest.mark.asyncio
    async def test_token_validity(self, api_client: AsyncClient):
        """测试 Token 有效性"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_token_validity")

        # ===== 测试点1: 注册获取Token =====
        TestPrinter.print_test_point(
            "注册获取Token",
            "验证注册接口返回有效Token"
        )

        register_data = TestDataFactory.register_data()

        TestPrinter.print_request(
            method="POST",
            url="/api/auth/register",
            body=register_data
        )

        reg_response = await api_client.post("/api/auth/register", json=register_data)
        reg_result = reg_response.json()

        TestPrinter.print_actual(reg_result, reg_response.status_code)

        assert reg_response.status_code == 200, f"注册失败: {reg_result}"
        token = reg_result["access_token"]
        TestPrinter.print_result(TestStatus.PASS, f"获取Token成功: {token[:20]}...")

        # ===== 测试点2: 使用Token访问受保护资源 =====
        TestPrinter.print_test_point(
            "使用Token访问受保护资源",
            "验证获取的Token可用于认证"
        )

        headers = {"Authorization": f"Bearer {token}"}

        TestPrinter.print_request(
            method="GET",
            url="/api/auth/me",
            headers=headers
        )

        TestPrinter.print_expected(
            {"status_code": 200, "username": register_data["username"]},
            "Token应能成功认证并返回正确用户"
        )

        me_response = await api_client.get("/api/auth/me", headers=headers)
        me_result = me_response.json()

        TestPrinter.print_actual(me_result, me_response.status_code)

        assert me_response.status_code == 200, f"Token认证失败: {me_result}"
        assert me_result["username"] == register_data["username"], "用户信息不匹配"

        TestPrinter.print_result(TestStatus.PASS, "Token有效，认证成功")

    @pytest.mark.asyncio
    async def test_token_reuse(self, api_client: AsyncClient):
        """测试 Token 可重复使用"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_token_reuse")

        # 注册获取 Token
        register_data = TestDataFactory.register_data()
        reg_response = await api_client.post("/api/auth/register", json=register_data)
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ===== 测试点: 多次使用同一Token =====
        TestPrinter.print_test_point(
            "多次使用同一Token",
            "验证Token可以多次复用"
        )

        request_count = 3
        TestPrinter.print_expected(
            {"每次请求状态码": 200, "请求次数": request_count},
            "同一Token应可多次使用"
        )

        for i in range(request_count):
            response = await api_client.get("/api/auth/me", headers=headers)
            print(f"   第 {i+1} 次请求: 状态码 {response.status_code}")
            assert response.status_code == 200, f"第 {i+1} 次请求失败"

        TestPrinter.print_result(TestStatus.PASS, f"Token成功复用 {request_count} 次")

    @pytest.mark.asyncio
    async def test_different_users_different_tokens(self, api_client: AsyncClient):
        """测试不同用户获取不同Token"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_different_users_different_tokens")

        # ===== 测试点: 不同用户的Token隔离 =====
        TestPrinter.print_test_point(
            "不同用户的Token隔离",
            "验证每个用户获取独立的Token，且Token只能访问自己的信息"
        )

        # 用户1注册
        user1_data = TestDataFactory.register_data()
        response1 = await api_client.post("/api/auth/register", json=user1_data)
        token1 = response1.json()["access_token"]
        user1_id = response1.json()["user"]["id"]

        # 用户2注册
        user2_data = TestDataFactory.register_data()
        response2 = await api_client.post("/api/auth/register", json=user2_data)
        token2 = response2.json()["access_token"]
        user2_id = response2.json()["user"]["id"]

        print(f"   用户1 ID: {user1_id}, Token: {token1[:15]}...")
        print(f"   用户2 ID: {user2_id}, Token: {token2[:15]}...")

        # 验证Token不同
        assert token1 != token2, "两个用户的Token应该不同"

        # 验证各自Token只能访问自己的信息
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        me1 = await api_client.get("/api/auth/me", headers=headers1)
        me2 = await api_client.get("/api/auth/me", headers=headers2)

        assert me1.json()["id"] == user1_id, "Token1应该返回用户1的信息"
        assert me2.json()["id"] == user2_id, "Token2应该返回用户2的信息"

        TestPrinter.print_result(TestStatus.PASS, "用户Token隔离验证成功")
