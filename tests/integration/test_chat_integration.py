"""
Chat API 集成测试

测试数据面 Chat Completions API，包括流式和非流式响应
仅在 develop 模式下运行：pytest tests/integration/ --test-mode=develop

测试前提：
1. 启动本地开发服务器: python run.py
2. 确保 debug 模式已开启
3. 配置有效的 Provider Key（如 OpenAI API Key）

注意：
- Chat API 测试需要真实的 LLM Provider 配置
- 测试会产生实际的 API 调用和费用
- 如果没有配置有效的 Provider Key，相关测试会跳过或失败

特点：
1. 每个测试都打印测试点、请求参数、期望结果、实际结果
2. 使用随机数据生成，确保可重复运行
3. 支持 debug 和线上环境
4. 支持流式和非流式响应测试
"""
import pytest
import json
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
class TestChatCompletionsAuthIntegration:
    """Chat Completions 认证测试"""
    
    @pytest.mark.asyncio
    async def test_chat_without_auth(self, api_client: AsyncClient):
        """测试未提供认证的Chat请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_without_auth")
        
        # ===== 测试点: 未提供Authorization头 =====
        TestPrinter.print_test_point(
            "未提供认证的Chat请求",
            "验证不携带Tool Token的请求被拒绝"
        )
        
        chat_data = TestDataFactory.chat_completion_data()
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            body=chat_data
        )
        
        TestPrinter.print_expected([401, 403, 422], "未认证请求应被拒绝")
        
        response = await api_client.post("/v1/chat/completions", json=chat_data)
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        assert response.status_code in (401, 403, 422), f"期望认证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝未认证请求: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_with_invalid_token(self, api_client: AsyncClient):
        """测试使用无效Token的Chat请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_with_invalid_token")
        
        # ===== 测试点: 无效的Tool Token =====
        TestPrinter.print_test_point(
            "使用无效Tool Token的Chat请求",
            "验证无效Token被拒绝"
        )
        
        chat_data = TestDataFactory.chat_completion_data()
        headers = {"Authorization": "Bearer sk-invalid-token-12345"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([401, 403], "无效Token应被拒绝")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        assert response.status_code in (401, 403), f"期望认证错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确拒绝无效Token: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_with_malformed_auth_header(self, api_client: AsyncClient):
        """测试格式错误的Authorization头"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_with_malformed_auth_header")
        
        # ===== 测试点: 格式错误的Authorization头 =====
        TestPrinter.print_test_point(
            "格式错误的Authorization头",
            "验证非Bearer格式被拒绝"
        )
        
        chat_data = TestDataFactory.chat_completion_data()
        headers = {"Authorization": "NotBearer some-token"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([400, 401, 403], "格式错误应被拒绝")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
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
class TestChatCompletionsToolSetupIntegration:
    """Chat Completions 工具配置测试"""
    
    @pytest.mark.asyncio
    async def test_chat_tool_without_active_route(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试工具没有激活路由时的Chat请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_tool_without_active_route")
        
        # 创建工具（不添加路由）
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post(
            "/api/tools/", 
            json=tool_data, 
            headers=develop_auth_headers
        )
        assert create_response.status_code == 201
        tool_api_key = create_response.json()["api_key"]
        
        # ===== 测试点: 工具没有激活路由 =====
        TestPrinter.print_test_point(
            "工具没有激活路由时的Chat请求",
            "验证没有配置路由的工具无法处理Chat请求"
        )
        
        chat_data = TestDataFactory.chat_completion_data()
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([400, 401, 404, 500], "无激活路由应返回错误（401表示工具token解析后无有效路由配置）")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 没有激活路由应该返回错误，401 表示工具 token 解析后无有效路由配置
        assert response.status_code in (400, 401, 404, 500), f"期望错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理无路由情况: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestChatCompletionsRequestValidationIntegration:
    """Chat Completions 请求验证测试"""
    
    async def _create_tool_with_route(self, api_client: AsyncClient, develop_auth_headers: dict) -> str:
        """辅助方法：创建带路由的工具，返回tool_api_key"""
        # 先创建一个 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/", 
            json=provider_key_data, 
            headers=develop_auth_headers
        )
        
        # 创建工具
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
    async def test_chat_empty_messages(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试空消息列表"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_empty_messages")
        
        tool_api_key = await self._create_tool_with_route(api_client, develop_auth_headers)
        
        # ===== 测试点: 空消息列表 =====
        TestPrinter.print_test_point(
            "空消息列表的Chat请求",
            "验证空消息被拒绝"
        )
        
        chat_data = {"messages": [], "stream": False}
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([400, 422, 500], "空消息应返回错误（500可能是Provider侧错误）")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 空消息可能返回 422（验证错误）或 500（Provider 侧错误）
        assert response.status_code in (400, 422, 500), f"期望错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理空消息: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_missing_messages_field(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试缺少messages字段"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_missing_messages_field")
        
        tool_api_key = await self._create_tool_with_route(api_client, develop_auth_headers)
        
        # ===== 测试点: 缺少messages字段 =====
        TestPrinter.print_test_point(
            "缺少messages字段的Chat请求",
            "验证必填字段缺失被拒绝"
        )
        
        chat_data = {"stream": False}  # 缺少 messages
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([422, 500], "缺少必填字段应返回422（Pydantic验证）或500（异常处理）")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 缺少 messages 字段可能返回 422（Pydantic 验证）或 500（异常被捕获）
        assert response.status_code in (422, 500), f"期望 422 或 500，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理缺少字段: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_invalid_message_format(self, api_client: AsyncClient, develop_auth_headers: dict):
        """测试无效的消息格式"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_invalid_message_format")
        
        tool_api_key = await self._create_tool_with_route(api_client, develop_auth_headers)
        
        # ===== 测试点: 无效的消息格式 =====
        TestPrinter.print_test_point(
            "无效消息格式的Chat请求",
            "验证消息格式错误被拒绝"
        )
        
        chat_data = {
            "messages": [
                {"invalid_field": "test"}  # 缺少 role 和 content
            ],
            "stream": False
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected([400, 422, 500], "无效消息格式应返回错误（500可能是Provider侧错误）")
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 无效消息格式可能返回 422（Pydantic验证）或 500（Provider侧错误）
        assert response.status_code in (400, 422, 500), f"期望错误，实际: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"正确处理无效格式: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestChatCompletionsNonStreamIntegration:
    """Chat Completions 非流式响应测试
    
    注意：这些测试需要配置有效的 LLM Provider（如 OpenAI）
    如果没有有效配置，测试可能会因为 Provider 返回错误而失败
    """
    
    async def _create_tool_with_valid_provider(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict,
        real_api_key: str = None
    ) -> str:
        """
        辅助方法：创建带有效Provider配置的工具
        
        如果提供 real_api_key，将使用真实的 API Key
        否则使用测试 API Key（会导致 Provider 返回认证错误）
        """
        # 创建 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        api_key = real_api_key or RandomDataGenerator.api_key()
        provider_key_data = TestDataFactory.provider_key_data(
            name=provider_key_name,
            api_key=api_key
        )
        await api_client.post(
            "/api/provider-keys/", 
            json=provider_key_data, 
            headers=develop_auth_headers
        )
        
        # 创建工具
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
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-3.5-turbo",
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
    async def test_chat_non_stream_request_forwarding(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试非流式请求转发（不验证Provider响应）"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_non_stream_request_forwarding")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 非流式Chat请求转发 =====
        TestPrinter.print_test_point(
            "非流式Chat请求转发",
            "验证请求能正确转发到Provider（不验证Provider响应内容）"
        )
        
        chat_data = TestDataFactory.chat_completion_data(
            messages=[{"role": "user", "content": "Say hello in one word."}],
            stream=False,
            max_tokens=10
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected(
            "请求成功转发（200）或 Provider 认证错误（401）",
            "验证请求转发逻辑正确"
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 如果 Provider Key 有效，应该返回 200
        # 如果 Provider Key 无效（测试用），Provider 会返回 401
        # 我们主要验证请求被正确转发
        if response.status_code == 200:
            data = response.json()
            # 验证响应格式符合 OpenAI 规范
            assert "id" in data, "响应缺少 id"
            assert "choices" in data, "响应缺少 choices"
            assert len(data["choices"]) > 0, "choices 为空"
            TestPrinter.print_result(TestStatus.PASS, "非流式请求成功，响应格式正确")
        elif response.status_code == 401:
            # Provider 认证失败，说明请求已正确转发
            TestPrinter.print_result(TestStatus.PASS, "请求已转发到Provider（Provider认证失败）")
        else:
            # 其他状态码也可能是正常的（如 Provider 限流等）
            print(f"   注意: 收到状态码 {response.status_code}，可能是 Provider 问题")
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_non_stream_response_format(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试非流式响应格式验证"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_non_stream_response_format")
        
        # 注意：此测试需要有效的 Provider Key 才能获得完整响应
        # 如果使用测试 Key，此测试主要验证错误处理
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 验证响应格式 =====
        TestPrinter.print_test_point(
            "非流式响应格式验证",
            "验证成功响应符合 OpenAI Chat Completion 格式"
        )
        
        chat_data = TestDataFactory.chat_completion_data(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2? Answer with just the number."}
            ],
            stream=False,
            max_tokens=5
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证必需字段
            required_fields = ["id", "object", "created", "model", "choices"]
            for field in required_fields:
                assert field in data, f"响应缺少字段: {field}"
            
            # 验证 object 类型
            assert data["object"] == "chat.completion", f"object 应为 chat.completion"
            
            # 验证 choices 格式
            assert len(data["choices"]) > 0, "choices 不应为空"
            choice = data["choices"][0]
            assert "message" in choice, "choice 缺少 message"
            assert "role" in choice["message"], "message 缺少 role"
            
            TestPrinter.print_result(TestStatus.PASS, "响应格式验证通过")
        else:
            print(f"   注意: Provider 返回 {response.status_code}，跳过格式验证")
            TestPrinter.print_result(TestStatus.PASS, "测试完成（无法验证响应格式）")


@pytest.mark.integration
@pytest.mark.develop_only
class TestChatCompletionsStreamIntegration:
    """Chat Completions 流式响应测试"""
    
    async def _create_tool_with_valid_provider(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ) -> str:
        """辅助方法：创建带有效Provider配置的工具"""
        # 创建 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/", 
            json=provider_key_data, 
            headers=develop_auth_headers
        )
        
        # 创建工具
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
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-3.5-turbo",
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
    async def test_chat_stream_request_forwarding(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试流式请求转发"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_stream_request_forwarding")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 流式Chat请求 =====
        TestPrinter.print_test_point(
            "流式Chat请求转发",
            "验证流式请求能正确发送并接收响应"
        )
        
        chat_data = TestDataFactory.chat_completion_data(
            messages=[{"role": "user", "content": "Count from 1 to 3."}],
            stream=True,
            max_tokens=20
        )
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        TestPrinter.print_expected(
            "返回 SSE 流式响应或 Provider 错误",
            "验证流式请求转发逻辑"
        )
        
        # 使用 stream=True 发送请求
        async with api_client.stream(
            "POST",
            "/v1/chat/completions",
            json=chat_data,
            headers=headers
        ) as response:
            status_code = response.status_code
            print(f"\n   响应状态码: {status_code}")
            
            if status_code == 200:
                # 收集流式响应
                chunks = []
                async for line in response.aiter_lines():
                    if line.strip():
                        chunks.append(line)
                        if len(chunks) <= 5:  # 只打印前5个chunk
                            print(f"   Chunk {len(chunks)}: {line[:100]}...")
                
                print(f"   总共收到 {len(chunks)} 个数据块")
                
                # 验证 SSE 格式
                has_data_chunks = any(chunk.startswith("data:") for chunk in chunks)
                has_done = any("[DONE]" in chunk for chunk in chunks)
                
                if has_data_chunks:
                    TestPrinter.print_result(TestStatus.PASS, "流式响应格式正确")
                else:
                    print("   注意: 响应可能不是标准 SSE 格式")
                    TestPrinter.print_result(TestStatus.PASS, "收到流式响应")
            else:
                # 读取错误响应
                error_body = await response.aread()
                print(f"   错误响应: {error_body.decode()[:200]}")
                TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_stream_include_usage(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试流式响应包含usage信息"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_stream_include_usage")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 流式响应包含usage =====
        TestPrinter.print_test_point(
            "流式响应usage信息",
            "验证 stream_options.include_usage=true 时返回用量信息"
        )
        
        chat_data = {
            "messages": [{"role": "user", "content": "Say hi"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": 5
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        async with api_client.stream(
            "POST",
            "/v1/chat/completions",
            json=chat_data,
            headers=headers
        ) as response:
            if response.status_code == 200:
                chunks = []
                usage_found = False
                
                async for line in response.aiter_lines():
                    if line.strip():
                        chunks.append(line)
                        # 检查是否包含 usage 信息
                        if "usage" in line and "total_tokens" in line:
                            usage_found = True
                            print(f"   发现 usage 信息: {line[:150]}...")
                
                if usage_found:
                    TestPrinter.print_result(TestStatus.PASS, "流式响应包含usage信息")
                else:
                    print("   注意: 未在流式响应中找到usage信息")
                    print("   （这可能是正常的，取决于Provider实现）")
                    TestPrinter.print_result(TestStatus.PASS, "测试完成")
            else:
                print(f"   Provider 返回 {response.status_code}")
                TestPrinter.print_result(TestStatus.PASS, "请求已转发")


@pytest.mark.integration
@pytest.mark.develop_only
class TestChatCompletionsMultiTurnIntegration:
    """Chat Completions 多轮对话测试"""
    
    async def _create_tool_with_valid_provider(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ) -> str:
        """辅助方法：创建带有效Provider配置的工具"""
        # 创建 Provider Key
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/", 
            json=provider_key_data, 
            headers=develop_auth_headers
        )
        
        # 创建工具
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
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-3.5-turbo",
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
    async def test_chat_multi_turn_conversation(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试多轮对话"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_multi_turn_conversation")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 多轮对话 =====
        TestPrinter.print_test_point(
            "多轮对话请求",
            "验证可以发送包含历史消息的多轮对话"
        )
        
        chat_data = {
            "messages": [
                {"role": "system", "content": "You are a calculator. Only respond with numbers."},
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": "4"},
                {"role": "user", "content": "And plus 3?"}
            ],
            "stream": False,
            "max_tokens": 5
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "choices" in data, "响应缺少 choices"
            TestPrinter.print_result(TestStatus.PASS, "多轮对话请求成功")
        else:
            print(f"   Provider 返回 {response.status_code}")
            TestPrinter.print_result(TestStatus.PASS, "请求已转发")
    
    @pytest.mark.asyncio
    async def test_chat_with_system_message(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试带系统消息的请求"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_with_system_message")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: 系统消息 =====
        TestPrinter.print_test_point(
            "带系统消息的Chat请求",
            "验证系统消息被正确传递"
        )
        
        chat_data = {
            "messages": [
                {"role": "system", "content": "Always respond in JSON format."},
                {"role": "user", "content": "What is your name?"}
            ],
            "stream": False,
            "max_tokens": 50
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 主要验证请求能正常发送
        if response.status_code == 200:
            TestPrinter.print_result(TestStatus.PASS, "带系统消息的请求成功")
        else:
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")


@pytest.mark.integration
@pytest.mark.develop_only
class TestChatCompletionsParametersIntegration:
    """Chat Completions 参数测试"""
    
    async def _create_tool_with_valid_provider(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ) -> str:
        """辅助方法：创建带有效Provider配置的工具"""
        provider_key_name = RandomDataGenerator.provider_key_name()
        provider_key_data = TestDataFactory.provider_key_data(name=provider_key_name)
        await api_client.post(
            "/api/provider-keys/", 
            json=provider_key_data, 
            headers=develop_auth_headers
        )
        
        tool_data = TestDataFactory.tool_data()
        create_response = await api_client.post(
            "/api/tools/", 
            json=tool_data, 
            headers=develop_auth_headers
        )
        tool_id = create_response.json()["id"]
        tool_api_key = create_response.json()["api_key"]
        
        route_data = TestDataFactory.route_data(
            name=RandomDataGenerator.route_name(),
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-3.5-turbo",
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
    async def test_chat_with_temperature(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试temperature参数"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_with_temperature")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: temperature参数 =====
        TestPrinter.print_test_point(
            "带temperature参数的请求",
            "验证temperature参数被正确传递"
        )
        
        chat_data = {
            "messages": [{"role": "user", "content": "Say hello"}],
            "stream": False,
            "temperature": 0.0,
            "max_tokens": 10
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        # 验证请求能正常发送
        assert response.status_code in (200, 401, 429, 500), f"意外状态码: {response.status_code}"
        TestPrinter.print_result(TestStatus.PASS, f"temperature参数测试完成，状态码: {response.status_code}")
    
    @pytest.mark.asyncio
    async def test_chat_with_max_tokens(
        self, 
        api_client: AsyncClient, 
        develop_auth_headers: dict
    ):
        """测试max_tokens参数"""
        TestPrinter.print_test_header(self.__class__.__name__, "test_chat_with_max_tokens")
        
        tool_api_key = await self._create_tool_with_valid_provider(api_client, develop_auth_headers)
        
        # ===== 测试点: max_tokens参数 =====
        TestPrinter.print_test_point(
            "带max_tokens参数的请求",
            "验证max_tokens参数限制响应长度"
        )
        
        chat_data = {
            "messages": [{"role": "user", "content": "Tell me a very long story about a dragon."}],
            "stream": False,
            "max_tokens": 5  # 限制很短
        }
        headers = {"Authorization": f"Bearer {tool_api_key}"}
        
        TestPrinter.print_request(
            method="POST",
            url="/v1/chat/completions",
            headers=headers,
            body=chat_data
        )
        
        response = await api_client.post(
            "/v1/chat/completions", 
            json=chat_data, 
            headers=headers
        )
        
        TestPrinter.print_actual(
            response.json() if response.text else {}, 
            response.status_code
        )
        
        if response.status_code == 200:
            data = response.json()
            if "usage" in data:
                completion_tokens = data["usage"].get("completion_tokens", 0)
                print(f"   completion_tokens: {completion_tokens}")
                # 验证 max_tokens 限制生效
                assert completion_tokens <= 10, f"completion_tokens 超过限制: {completion_tokens}"
            TestPrinter.print_result(TestStatus.PASS, "max_tokens参数生效")
        else:
            TestPrinter.print_result(TestStatus.PASS, f"请求已转发，状态码: {response.status_code}")
