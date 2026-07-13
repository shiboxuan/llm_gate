"""
连接测试 API 集成测试

测试 POST /api/test/connection 接口，验证 LLM Provider 连通性测试功能。
仅在 develop 模式下运行：pytest tests/integration/ --test-mode=develop

测试前提：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启
3. 配置有效的 Provider Key（如 OpenAI API Key）

注意：
- 这些测试需要真实的 LLM Provider 配置
- 测试会产生实际的 API 调用和费用
"""
import pytest
from httpx import AsyncClient

from tests.integration.test_utils import TestPrinter, TestStatus, RandomDataGenerator, TestDataFactory


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestAuthIntegration:
    """连接测试 API 认证测试"""

    @pytest.mark.asyncio
    async def test_connection_test_without_auth(self, api_client: AsyncClient):
        """测试未提供认证的连接测试请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_without_auth")

        TestPrinter.print_test_point("未提供认证的连接测试请求", "验证不携带 JWT Token 的请求被拒绝")

        data = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "provider_key_name": "test_key"
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", body=data)
        TestPrinter.print_expected([401, 403], "未认证请求应被拒绝")

        response = await api_client.post("/api/test/connection", json=data)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code in (401, 403), f"期望认证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")

    @pytest.mark.asyncio
    async def test_connection_test_invalid_api_type(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试无效的 api_type"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_invalid_api_type")

        TestPrinter.print_test_point("无效的 api_type", "验证无效的 api_type 返回 422 验证错误")

        data = {
            "api_type": "invalid_type",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "provider_key_name": "test_key"
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(422, "无效的 api_type 应返回 422 验证错误")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 422, f"期望 422，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回 422 验证错误")


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestProviderKeyIntegration:
    """连接测试 Provider Key 测试"""

    @pytest.mark.asyncio
    async def test_connection_test_provider_key_not_found(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试 Provider Key 不存在"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_provider_key_not_found")

        TestPrinter.print_test_point("Provider Key 不存在", "验证使用不存在的 Provider Key 返回 404")

        data = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "provider_key_name": f"nonexistent_key_{RandomDataGenerator.unique_id()}"
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(404, "Provider Key 不存在应返回 404")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 404, f"期望 404，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, "正确返回 404 Provider Key 不存在")


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestOpenAIChatIntegration:
    """连接测试 OpenAI Chat API 测试"""

    async def _create_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict, api_key: str) -> str:
        """辅助方法：创建 Provider Key，返回 key name"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name, api_key=api_key)
        response = await api_client.post("/api/provider-keys/", json=provider_key_data, headers=develop_auth_headers)
        assert response.status_code == 201, f"创建 Provider Key 失败: {response.text}"
        return provider_key_name

    @pytest.mark.asyncio
    async def test_connection_test_openai_chat_success(self, api_client: AsyncClient, develop_auth_headers: dict, request):
        """测试 OpenAI Chat 连接成功

        需要配置有效的 OpenAI API Key
        """
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_openai_chat_success")

        # 从 pytest 命令行获取 API Key
        openai_api_key = request.config.getoption("--openai-api-key", default=None)
        if not openai_api_key:
            pytest.skip("需要通过 --openai-api-key 参数提供有效的 OpenAI API Key")

        TestPrinter.print_test_point("OpenAI Chat 连接测试成功", "验证使用有效配置可以成功连接 OpenAI Chat API")

        # 创建 Provider Key
        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, openai_api_key)

        data = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "连接测试应成功，返回 success=true")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is True, f"期望 success=True，实际: {result.get('success')}"
        assert result["message"] == "连接成功", f"期望 message='连接成功'，实际: {result.get('message')}"
        assert result["latency_ms"] >= 0, f"latency_ms 应大于等于 0"

        TestPrinter.print_result(TestStatus.PASS, f"OpenAI Chat 连接成功，延迟: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_connection_test_openai_chat_invalid_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试 OpenAI Chat 使用无效 API Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_openai_chat_invalid_key")

        TestPrinter.print_test_point("OpenAI Chat 无效 API Key", "验证使用无效 API Key 返回认证失败")

        # 创建一个使用无效 API Key 的 Provider Key
        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, "sk-invalid-key-12345")

        data = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "请求应返回 200，但 success=false 且包含认证错误信息")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is False, f"期望 success=False，实际: {result.get('success')}"
        assert result["error_code"] == "AUTH_ERROR", f"期望 error_code='AUTH_ERROR'，实际: {result.get('error_code')}"

        TestPrinter.print_result(TestStatus.PASS, f"正确返回认证失败: {result['message']}")

    @pytest.mark.asyncio
    async def test_connection_test_openai_chat_invalid_model(self, api_client: AsyncClient, develop_auth_headers: dict, request):
        """测试 OpenAI Chat 使用无效模型名称"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_openai_chat_invalid_model")

        openai_api_key = request.config.getoption("--openai-api-key", default=None)
        if not openai_api_key:
            pytest.skip("需要通过 --openai-api-key 参数提供有效的 OpenAI API Key")

        TestPrinter.print_test_point("OpenAI Chat 无效模型", "验证使用不存在的模型返回错误")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, openai_api_key)

        data = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "nonexistent-model-12345",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "请求应返回 200，但 success=false 且包含模型错误信息")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is False, f"期望 success=False，实际: {result.get('success')}"
        # 模型不存在可能返回 400 Bad Request 或 404 Not Found
        assert result["error_code"] in ["BAD_REQUEST", "NOT_FOUND"], f"期望 BAD_REQUEST 或 NOT_FOUND，实际: {result.get('error_code')}"

        TestPrinter.print_result(TestStatus.PASS, f"正确返回模型错误: {result['message']}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestOpenAIEmbeddingsIntegration:
    """连接测试 OpenAI Embeddings API 测试"""

    async def _create_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict, api_key: str) -> str:
        """辅助方法：创建 Provider Key，返回 key name"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name, api_key=api_key)
        response = await api_client.post("/api/provider-keys/", json=provider_key_data, headers=develop_auth_headers)
        assert response.status_code == 201, f"创建 Provider Key 失败: {response.text}"
        return provider_key_name

    @pytest.mark.asyncio
    async def test_connection_test_openai_embeddings_success(self, api_client: AsyncClient, develop_auth_headers: dict, request):
        """测试 OpenAI Embeddings 连接成功"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_openai_embeddings_success")

        openai_api_key = request.config.getoption("--openai-api-key", default=None)
        if not openai_api_key:
            pytest.skip("需要通过 --openai-api-key 参数提供有效的 OpenAI API Key")

        TestPrinter.print_test_point("OpenAI Embeddings 连接测试成功", "验证使用有效配置可以成功连接 OpenAI Embeddings API")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, openai_api_key)

        data = {
            "api_type": "openai_embeddings",
            "base_url": "https://api.openai.com/v1",
            "model": "text-embedding-3-small",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "连接测试应成功，返回 success=true")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is True, f"期望 success=True，实际: {result.get('success')}"

        TestPrinter.print_result(TestStatus.PASS, f"OpenAI Embeddings 连接成功，延迟: {result['latency_ms']}ms")


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestAnthropicIntegration:
    """连接测试 Anthropic Messages API 测试"""

    async def _create_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict, api_key: str) -> str:
        """辅助方法：创建 Provider Key，返回 key name"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name, api_key=api_key)
        response = await api_client.post("/api/provider-keys/", json=provider_key_data, headers=develop_auth_headers)
        assert response.status_code == 201, f"创建 Provider Key 失败: {response.text}"
        return provider_key_name

    @pytest.mark.asyncio
    async def test_connection_test_anthropic_messages_success(self, api_client: AsyncClient, develop_auth_headers: dict, request):
        """测试 Anthropic Messages 连接成功"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_anthropic_messages_success")

        anthropic_api_key = request.config.getoption("--anthropic-api-key", default=None)
        if not anthropic_api_key:
            pytest.skip("需要通过 --anthropic-api-key 参数提供有效的 Anthropic API Key")

        TestPrinter.print_test_point("Anthropic Messages 连接测试成功", "验证使用有效配置可以成功连接 Anthropic Messages API")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, anthropic_api_key)

        data = {
            "api_type": "anthropic_messages",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-haiku-20240307",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "连接测试应成功，返回 success=true")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is True, f"期望 success=True，实际: {result.get('success')}"

        TestPrinter.print_result(TestStatus.PASS, f"Anthropic Messages 连接成功，延迟: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_connection_test_anthropic_invalid_key(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试 Anthropic Messages 使用无效 API Key"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_anthropic_invalid_key")

        TestPrinter.print_test_point("Anthropic Messages 无效 API Key", "验证使用无效 API Key 返回认证失败")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, "sk-ant-invalid-key-12345")

        data = {
            "api_type": "anthropic_messages",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-haiku-20240307",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "请求应返回 200，但 success=false 且包含认证错误信息")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is False, f"期望 success=False，实际: {result.get('success')}"
        assert result["error_code"] == "AUTH_ERROR", f"期望 error_code='AUTH_ERROR'，实际: {result.get('error_code')}"

        TestPrinter.print_result(TestStatus.PASS, f"正确返回认证失败: {result['message']}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestConnectionTestTimeoutIntegration:
    """连接测试超时测试"""

    async def _create_provider_key(self, api_client: AsyncClient, develop_auth_headers: dict, api_key: str) -> str:
        """辅助方法：创建 Provider Key，返回 key name"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name, api_key=api_key)
        response = await api_client.post("/api/provider-keys/", json=provider_key_data, headers=develop_auth_headers)
        assert response.status_code == 201, f"创建 Provider Key 失败: {response.text}"
        return provider_key_name

    @pytest.mark.asyncio
    async def test_connection_test_connect_timeout(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试连接超时"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_connect_timeout")

        TestPrinter.print_test_point("连接超时测试", "验证连接不可达的 URL 返回超时错误")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, "sk-test-key")

        data = {
            "api_type": "openai_chat",
            "base_url": "https://10.255.255.1",  # 不可达的 IP
            "model": "gpt-4o",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "请求应返回 200，但 success=false 且包含超时错误信息")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers, timeout=60.0)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is False, f"期望 success=False，实际: {result.get('success')}"
        assert result["error_code"] in ["CONNECT_TIMEOUT", "CONNECT_ERROR"], f"期望超时或连接错误，实际: {result.get('error_code')}"

        TestPrinter.print_result(TestStatus.PASS, f"正确返回超时错误: {result['message']}")

    @pytest.mark.asyncio
    async def test_connection_test_invalid_url(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试无效 URL"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_connection_test_invalid_url")

        TestPrinter.print_test_point("无效 URL 测试", "验证使用无效的 base_url 返回连接错误")

        provider_key_name = await self._create_provider_key(api_client, develop_auth_headers, "sk-test-key")

        data = {
            "api_type": "openai_chat",
            "base_url": "https://invalid-domain-that-does-not-exist-12345.com",
            "model": "gpt-4o",
            "provider_key_name": provider_key_name
        }

        TestPrinter.print_request(method="POST", url="/api/test/connection", headers=develop_auth_headers, body=data)
        TestPrinter.print_expected(200, "请求应返回 200，但 success=false 且包含连接错误信息")

        response = await api_client.post("/api/test/connection", json=data, headers=develop_auth_headers, timeout=30.0)

        TestPrinter.print_actual(response.json() if response.text else {}, response.status_code)

        assert response.status_code == 200, f"期望 200，实际: {response.status_code}"
        result = response.json()
        assert result["success"] is False, f"期望 success=False，实际: {result.get('success')}"
        assert result["error_code"] in ["CONNECT_ERROR", "CONNECT_TIMEOUT"], f"期望连接错误，实际: {result.get('error_code')}"

        TestPrinter.print_result(TestStatus.PASS, f"正确返回连接错误: {result['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--test-mode=develop"])
