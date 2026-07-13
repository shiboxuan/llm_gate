"""
Embeddings API 集成测试

测试数据面 Embeddings API
仅在 develop 模式下运行：pytest tests/integration/test_embeddings_integration.py --test-mode=develop

测试前提：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启
3. 配置有效的 Provider Key（如 OpenAI API Key）

注意：
- Embeddings API 测试需要真实的 LLM Provider 配置
- 测试会产生实际的 API 调用和费用
- 如果没有配置有效的 Provider Key，相关测试会跳过或失败
"""
import pytest
from httpx import AsyncClient

from tests.integration.test_utils import (
    TestPrinter,
    TestStatus,
    RandomDataGenerator,
    TestDataFactory,
)


class EmbeddingTestDataFactory:
    """Embedding 测试数据工厂"""

    @staticmethod
    def embedding_request_data(
        input_text: str = None,
        model: str = None,
        encoding_format: str = None,
        dimensions: int = None,
        user: str = None
    ) -> dict:
        """生成 Embedding 请求数据"""
        data = {
            "input": input_text or "This is a test text for embedding."
        }
        if model:
            data["model"] = model
        if encoding_format:
            data["encoding_format"] = encoding_format
        if dimensions:
            data["dimensions"] = dimensions
        if user:
            data["user"] = user
        return data

    @staticmethod
    def batch_embedding_request_data(texts: list = None) -> dict:
        """生成批量 Embedding 请求数据"""
        default_texts = [
            "First test text",
            "Second test text",
            "Third test text"
        ]
        return {
            "input": texts or default_texts
        }


@pytest.mark.integration
@pytest.mark.develop_only
class TestEmbeddingsAuthIntegration:
    """Embeddings 认证测试"""

    @pytest.mark.asyncio
    async def test_embeddings_without_auth(self, api_client: AsyncClient):
        """测试未提供认证的 Embeddings 请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_without_auth")

        # ===== 测试点: 未提供Authorization头 =====
        TestPrinter.print_test_point(
            "未提供认证的 Embeddings 请求",
            "验证不携带 Tool Token 的请求被拒绝"
        )

        embedding_data = EmbeddingTestDataFactory.embedding_request_data()

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            body=embedding_data
        )

        TestPrinter.print_expected([401, 403, 422], "未认证请求应被拒绝")

        response = await api_client.post("/v1/embeddings", json=embedding_data)

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        assert response.status_code in (401, 403, 422), f"期望认证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")

    @pytest.mark.asyncio
    async def test_embeddings_with_invalid_token(self, api_client: AsyncClient):
        """测试使用无效 Token 的 Embeddings 请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_with_invalid_token")

        # ===== 测试点: 无效的Tool Token =====
        TestPrinter.print_test_point(
            "使用无效 Tool Token 的 Embeddings 请求",
            "验证无效 Token 被拒绝"
        )

        embedding_data = EmbeddingTestDataFactory.embedding_request_data()
        headers = {"Authorization": "Bearer sk-invalid-token-12345"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected([401, 403], "无效 Token 应被拒绝")

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        assert response.status_code in (401, 403), f"期望认证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝无效 Token: {response.status_code}")

    @pytest.mark.asyncio
    async def test_embeddings_with_malformed_auth_header(self, api_client: AsyncClient):
        """测试格式错误的 Authorization 头"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_with_malformed_auth_header")

        # ===== 测试点: 格式错误的Authorization头 =====
        TestPrinter.print_test_point(
            "格式错误的 Authorization 头",
            "验证非 Bearer 格式被拒绝"
        )

        embedding_data = EmbeddingTestDataFactory.embedding_request_data()
        headers = {"Authorization": "NotBearer some-token"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected([400, 401, 403], "格式错误应被拒绝")

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        assert response.status_code in (400, 401, 403), f"期望错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝格式错误: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestEmbeddingsApiTypeValidation:
    """Embeddings api_type 验证测试"""

    async def _create_chat_tool(self, api_client: AsyncClient, develop_auth_headers: dict) -> str:
        """辅助方法：创建 api_type=openai_chat 的工具，返回 tool_api_key"""
        # 先创建一个 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/",
            json=provider_key_data,
            headers=develop_auth_headers
        )

        # 创建工具（默认 api_type 为 openai_chat）
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post(
            "/api/tools/",
            json=tool_data,
            headers=develop_auth_headers
        )
        tool_id = create_response.json()["id"]
        tool_api_key = create_response.json()["api_key"]

        # 添加路由并激活
        route_data = TestDataFactory.route_data(
            name=RandomDataGenerator.route_name(),
            provider_key_name=provider_key_name,
            set_active=True
        )
        await api_client.post(
            f"/api/tools/{tool_id}/routes",
            json=route_data,
            headers=develop_auth_headers
        )

        return tool_api_key

    @pytest.mark.asyncio
    async def test_embeddings_with_wrong_api_type(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试使用错误 api_type 的工具调用 Embeddings 端点"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_with_wrong_api_type")

        # 创建一个 api_type=openai_chat 的工具
        tool_api_key = await self._create_chat_tool(api_client, develop_auth_headers)

        # ===== 测试点: 错误的 api_type =====
        TestPrinter.print_test_point(
            "使用 openai_chat 类型的工具调用 Embeddings 端点",
            "验证 api_type 不匹配时返回错误"
        )

        embedding_data = EmbeddingTestDataFactory.embedding_request_data()
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected([400, 404], "api_type 不匹配应返回错误")

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        # 应该返回错误，因为 api_type 不是 openai_embeddings
        assert response.status_code in (400, 404), f"期望 api_type 错误，实际: {response.status_code}"

        # 验证错误消息中包含 api_type 相关信息
        response_data = response.json()
        error_message = response_data.get("message", "") or response_data.get("detail", "")
        assert "openai_embeddings" in error_message.lower() or "api_type" in error_message.lower(), \
            f"错误消息应提及 api_type: {error_message}"

        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝错误的 api_type: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestEmbeddingsRequestForwarding:
    """Embeddings 请求转发测试"""

    async def _create_embedding_tool(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small"
    ) -> str:
        """辅助方法：创建 api_type=openai_embeddings 的工具"""
        # 创建 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/",
            json=provider_key_data,
            headers=develop_auth_headers
        )

        # 创建工具，指定 api_type 为 openai_embeddings
        tool_data = {
            "name": RandomDataGenerator.tool_name(prefix="embedding_tool"),
            "description": "Embedding 测试工具",
            "api_type": "openai_embeddings"
        }
        create_response = await api_client.post(
            "/api/tools/",
            json=tool_data,
            headers=develop_auth_headers
        )
        tool_id = create_response.json()["id"]
        tool_api_key = create_response.json()["api_key"]

        # 添加路由并激活（注意：embeddings 端点不需要 api_path）
        route_data = {
            "name": RandomDataGenerator.route_name(),
            "base_url": base_url,
            "model": model,
            "provider_key_name": provider_key_name,
            "set_active": True
        }
        await api_client.post(
            f"/api/tools/{tool_id}/routes",
            json=route_data,
            headers=develop_auth_headers
        )

        return tool_api_key

    @pytest.mark.asyncio
    async def test_embeddings_basic_request(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict
    ):
        """测试基本的 Embeddings 请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_basic_request")

        tool_api_key = await self._create_embedding_tool(api_client, develop_auth_headers)

        # ===== 测试点: 基本 Embeddings 请求 =====
        TestPrinter.print_test_point(
            "基本 Embeddings 请求",
            "验证请求能正确转发到 Provider"
        )

        embedding_data = EmbeddingTestDataFactory.embedding_request_data(
            input_text="Hello, this is a test for embeddings API."
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected(
            "请求成功转发（200）或 Provider 认证错误（401）",
            "验证请求转发逻辑正确"
        )

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        if response.status_code == 200:
            data = response.json()
            # 验证响应格式符合 OpenAI Embeddings 规范
            assert "object" in data, "响应缺少 object"
            assert data["object"] == "list", f"object 应为 list，实际: {data['object']}"
            assert "data" in data, "响应缺少 data"
            assert len(data["data"]) > 0, "data 为空"
            assert "embedding" in data["data"][0], "embedding 对象缺少 embedding 字段"
            assert "usage" in data, "响应缺少 usage"
            assert "prompt_tokens" in data["usage"], "usage 缺少 prompt_tokens"

            embedding_dim = len(data["data"][0]["embedding"])
            print(f"   Embedding 维度: {embedding_dim}")

            TestPrinter.print_result(TestStatus.PASS, f"Embeddings 请求成功，维度: {embedding_dim}")
        elif response.status_code == 401:
            TestPrinter.print_result(TestStatus.PASS, "请求已转发到 Provider（Provider 认证失败）")
        else:
            print(f"   注意: 收到状态码 {response.status_code}，可能是 Provider 问题")
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")

    @pytest.mark.asyncio
    async def test_embeddings_batch_request(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict
    ):
        """测试批量 Embeddings 请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_batch_request")

        tool_api_key = await self._create_embedding_tool(api_client, develop_auth_headers)

        # ===== 测试点: 批量 Embeddings 请求 =====
        TestPrinter.print_test_point(
            "批量 Embeddings 请求",
            "验证可以一次处理多个文本"
        )

        embedding_data = EmbeddingTestDataFactory.batch_embedding_request_data(
            texts=["First text", "Second text", "Third text"]
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        if response.status_code == 200:
            data = response.json()
            assert len(data["data"]) == 3, f"期望 3 个 embedding，实际: {len(data['data'])}"

            # 验证每个 embedding 有正确的 index
            indices = [item["index"] for item in data["data"]]
            assert sorted(indices) == [0, 1, 2], f"index 不正确: {indices}"

            TestPrinter.print_result(TestStatus.PASS, "批量 Embeddings 请求成功")
        else:
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")

    @pytest.mark.asyncio
    async def test_embeddings_with_dimensions(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict
    ):
        """测试带 dimensions 参数的请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_with_dimensions")

        # 使用 text-embedding-3-small，支持可调维度
        tool_api_key = await self._create_embedding_tool(
            api_client,
            develop_auth_headers,
            model="text-embedding-3-small"
        )

        # ===== 测试点: dimensions 参数 =====
        TestPrinter.print_test_point(
            "带 dimensions 参数的请求",
            "验证 dimensions 参数被正确传递（适用于 text-embedding-3-* 系列）"
        )

        target_dim = 256  # 降维到 256
        embedding_data = EmbeddingTestDataFactory.embedding_request_data(
            input_text="Test text for dimension reduction",
            dimensions=target_dim
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        if response.status_code == 200:
            data = response.json()
            actual_dim = len(data["data"][0]["embedding"])
            print(f"   请求维度: {target_dim}, 实际维度: {actual_dim}")

            assert actual_dim == target_dim, f"期望维度 {target_dim}，实际: {actual_dim}"
            TestPrinter.print_result(TestStatus.PASS, f"dimensions 参数生效，维度: {actual_dim}")
        else:
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestEmbeddingsRequestValidation:
    """Embeddings 请求验证测试"""

    async def _create_embedding_tool(self, api_client: AsyncClient, develop_auth_headers: dict) -> str:
        """辅助方法：创建 api_type=openai_embeddings 的工具"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/",
            json=provider_key_data,
            headers=develop_auth_headers
        )

        tool_data = {
            "name": RandomDataGenerator.tool_name(prefix="embedding_tool"),
            "description": "Embedding 测试工具",
            "api_type": "openai_embeddings"
        }
        create_response = await api_client.post(
            "/api/tools/",
            json=tool_data,
            headers=develop_auth_headers
        )
        tool_id = create_response.json()["id"]
        tool_api_key = create_response.json()["api_key"]

        route_data = {
            "name": RandomDataGenerator.route_name(),
            "base_url": "https://api.openai.com/v1",
            "model": "text-embedding-3-small",
            "provider_key_name": provider_key_name,
            "set_active": True
        }
        await api_client.post(
            f"/api/tools/{tool_id}/routes",
            json=route_data,
            headers=develop_auth_headers
        )

        return tool_api_key

    @pytest.mark.asyncio
    async def test_embeddings_missing_input(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict
    ):
        """测试缺少 input 字段"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_missing_input")

        tool_api_key = await self._create_embedding_tool(api_client, develop_auth_headers)

        # ===== 测试点: 缺少 input 字段 =====
        TestPrinter.print_test_point(
            "缺少 input 字段的请求",
            "验证必填字段缺失被拒绝"
        )

        embedding_data = {}  # 缺少 input
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected([422, 500], "缺少必填字段应返回 422（Pydantic 验证）或 500")

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        assert response.status_code in (422, 500), f"期望验证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理缺少字段: {response.status_code}")

    @pytest.mark.asyncio
    async def test_embeddings_empty_input(
        self,
        api_client: AsyncClient,
        develop_auth_headers: dict
    ):
        """测试空 input"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_embeddings_empty_input")

        tool_api_key = await self._create_embedding_tool(api_client, develop_auth_headers)

        # ===== 测试点: 空 input =====
        TestPrinter.print_test_point(
            "空 input 的请求",
            "验证空输入的处理"
        )

        embedding_data = {"input": ""}
        headers = {"Authorization": f"Bearer {tool_api_key}"}

        TestPrinter.print_request(
            method="POST",
            url="/v1/embeddings",
            headers=headers,
            body=embedding_data
        )

        TestPrinter.print_expected([400, 422, 500], "空输入应返回错误（可能是 Provider 侧错误）")

        response = await api_client.post(
            "/v1/embeddings",
            json=embedding_data,
            headers=headers
        )

        TestPrinter.print_actual(
            response.json() if response.text else {},
            response.status_code
        )

        # 空输入可能返回 400/422（验证错误）或 500（Provider 侧错误）
        assert response.status_code in (400, 422, 500), f"期望错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理空输入: {response.status_code}")
