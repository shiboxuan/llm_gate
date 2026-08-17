"""
代理服务测试用例

测试 ProxyService 的所有方法
使用 Mock 依赖进行测试
"""
import codecs
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.proxy_service import ProxyService
from app.services.cache_service import CacheService
from app.services.tool_service import ToolService
from app.services.provider_key_service import ProviderKeyService
from app.schemas.chat import ChatCompletionRequest, Message
from app.models.tool import Tool, RouteConfig


class TestProxyService:
    """代理服务测试类"""
    
    @pytest.fixture
    def mock_http_client(self):
        """创建 Mock HTTP 客户端"""
        return AsyncMock(spec=httpx.AsyncClient)
    
    @pytest.fixture
    def mock_cache_service(self):
        """创建 Mock 缓存服务"""
        service = AsyncMock(spec=CacheService)
        service.get_route_config = AsyncMock(return_value=None)
        service.set_route_config = AsyncMock()
        service.build_route_config = MagicMock()
        return service
    
    @pytest.fixture
    def mock_tool_service(self):
        """创建 Mock 工具服务"""
        service = AsyncMock(spec=ToolService)
        service.get_tool_by_token_hash = AsyncMock(return_value=None)
        return service
    
    @pytest.fixture
    def mock_provider_key_service(self):
        """创建 Mock Provider Key 服务"""
        service = AsyncMock(spec=ProviderKeyService)
        service.get_decrypted_key_by_name = AsyncMock(return_value=None)
        return service
    
    @pytest.fixture
    def proxy_service(self, mock_http_client, mock_cache_service, mock_tool_service, mock_provider_key_service):
        """创建代理服务实例"""
        return ProxyService(
            http_client=mock_http_client,
            cache_service=mock_cache_service,
            tool_service=mock_tool_service,
            provider_key_service=mock_provider_key_service
        )
    
    @pytest.fixture
    def sample_route_config(self):
        """示例路由配置"""
        return {
            "tool_id": 1,
            "tool_name": "测试工具",
            "user_id": "user_001",
            "active_route_name": "default",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "api_path": "/chat/completions",
            "api_key": "sk-test-api-key"
        }
    
    @pytest.fixture
    def sample_chat_request(self):
        """示例聊天请求"""
        return ChatCompletionRequest(
            messages=[
                Message(role="user", content="Hello!")
            ],
            stream=False
        )
    
    # ==================== resolve_route_config 测试 ====================
    
    @pytest.mark.asyncio
    async def test_resolve_route_config_from_cache(self, proxy_service, mock_cache_service, sample_route_config):
        """测试从缓存获取路由配置"""
        tool_token = "sk-test-token"
        
        # 设置缓存命中
        mock_cache_service.get_route_config = AsyncMock(return_value=sample_route_config)
        
        result = await proxy_service.resolve_route_config(tool_token)
        
        assert result is not None
        assert result["tool_id"] == 1
        mock_cache_service.get_route_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_route_config_from_db(self, proxy_service, mock_cache_service, mock_tool_service, mock_provider_key_service, sample_route_config):
        """测试从数据库获取路由配置"""
        tool_token = "sk-test-token"
        
        # 设置缓存未命中
        mock_cache_service.get_route_config = AsyncMock(return_value=None)
        
        # 设置工具数据
        mock_tool = MagicMock(spec=Tool)
        mock_tool.status = 1
        mock_tool.active_route_name = "default"
        mock_tool.user_id = "user_001"
        mock_tool.id = 1
        mock_tool.name = "测试工具"
        mock_tool.api_type = "openai"
        mock_tool.routes = {
            "default": RouteConfig(
                provider="openai",
                base_url="https://api.openai.com/v1",
                model="gpt-4",
                provider_key_name="openai",
                api_path="/chat/completions"
            )
        }
        mock_tool_service.get_tool_by_token_hash = AsyncMock(return_value=mock_tool)
        
        # 设置 Provider Key
        mock_provider_key_service.get_decrypted_key_by_name = AsyncMock(return_value="sk-decrypted-key")
        
        # 设置 build_route_config 返回值
        mock_cache_service.build_route_config = MagicMock(return_value=sample_route_config)
        
        result = await proxy_service.resolve_route_config(tool_token)
        
        assert result is not None
        mock_tool_service.get_tool_by_token_hash.assert_called_once()
        mock_provider_key_service.get_decrypted_key_by_name.assert_called_once()
        mock_cache_service.set_route_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_resolve_route_config_tool_not_found(self, proxy_service, mock_cache_service, mock_tool_service):
        """测试工具不存在时返回 None"""
        tool_token = "sk-invalid-token"
        
        mock_cache_service.get_route_config = AsyncMock(return_value=None)
        mock_tool_service.get_tool_by_token_hash = AsyncMock(return_value=None)
        
        result = await proxy_service.resolve_route_config(tool_token)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_route_config_tool_disabled(self, proxy_service, mock_cache_service, mock_tool_service):
        """测试工具被禁用时返回 None"""
        tool_token = "sk-disabled-token"
        
        mock_cache_service.get_route_config = AsyncMock(return_value=None)
        
        mock_tool = MagicMock(spec=Tool)
        mock_tool.status = 0  # 禁用状态
        mock_tool_service.get_tool_by_token_hash = AsyncMock(return_value=mock_tool)
        
        result = await proxy_service.resolve_route_config(tool_token)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_route_config_no_active_route(self, proxy_service, mock_cache_service, mock_tool_service):
        """测试无激活路由时返回 None"""
        tool_token = "sk-no-route-token"
        
        mock_cache_service.get_route_config = AsyncMock(return_value=None)
        
        mock_tool = MagicMock(spec=Tool)
        mock_tool.status = 1
        mock_tool.active_route_name = None
        mock_tool.routes = {}
        mock_tool_service.get_tool_by_token_hash = AsyncMock(return_value=mock_tool)
        
        result = await proxy_service.resolve_route_config(tool_token)
        
        assert result is None
    
    # ==================== build_provider_request 测试 ====================
    
    def test_build_provider_request_basic(self, proxy_service, sample_route_config, sample_chat_request):
        """测试构建基本的 Provider 请求"""
        result = proxy_service.build_provider_request(sample_route_config, sample_chat_request)
        
        assert result["model"] == "gpt-4"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["stream"] is False
    
    def test_build_provider_request_uses_route_config_model(self, proxy_service, sample_route_config):
        """测试始终使用路由配置中的模型"""
        request = ChatCompletionRequest(
            model="gpt-3.5-turbo",
            messages=[Message(role="user", content="Hello!")]
        )
        
        result = proxy_service.build_provider_request(sample_route_config, request)
        
        assert result["model"] == "gpt-4"
    
    def test_build_provider_request_with_optional_params(self, proxy_service, sample_route_config):
        """测试构建包含可选参数的请求"""
        request = ChatCompletionRequest(
            messages=[Message(role="user", content="Hello!")],
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
            stream=True
        )
        
        result = proxy_service.build_provider_request(sample_route_config, request)
        
        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 100
        assert result["top_p"] == 0.9
        assert result["stream"] is True
    
    def test_build_provider_request_excludes_none_params(self, proxy_service, sample_route_config, sample_chat_request):
        """测试排除 None 参数"""
        result = proxy_service.build_provider_request(sample_route_config, sample_chat_request)
        
        # 这些参数应该不存在于结果中
        assert "temperature" not in result
        assert "max_tokens" not in result
        assert "stop" not in result

    def test_build_provider_request_stream_forces_include_usage(self, proxy_service, sample_route_config):
        """测试流式请求强制开启 include_usage"""
        request = ChatCompletionRequest(
            messages=[Message(role="user", content="Hello!")],
            stream=True
        )

        result = proxy_service.build_provider_request(sample_route_config, request)

        assert result["stream_options"]["include_usage"] is True

    def test_build_provider_request_stream_merges_client_stream_options(self, proxy_service, sample_route_config):
        """测试流式请求合并客户端 stream_options 且保留 include_usage"""
        request = ChatCompletionRequest(
            messages=[Message(role="user", content="Hello!")],
            stream=True,
            stream_options={"include_usage": False}
        )

        result = proxy_service.build_provider_request(sample_route_config, request)

        assert "stream_options" in result
        assert result["stream_options"]["include_usage"] is False
    
    # ==================== forward_chat_completion 测试 ====================
    
    @pytest.mark.asyncio
    async def test_forward_non_stream(self, proxy_service, mock_http_client, sample_route_config):
        """测试非流式转发"""
        request = ChatCompletionRequest(
            messages=[Message(role="user", content="Hello!")],
            stream=False
        )
        
        # Mock 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "Hi!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        
        result = await proxy_service.forward_chat_completion(sample_route_config, request)
        
        assert result is not None
        assert result["id"] == "chatcmpl-123"
        mock_http_client.post.assert_called_once()
    
    # ==================== extract_usage_from_response 测试 ====================
    
    def test_extract_usage_from_response(self, proxy_service):
        """测试从响应中提取 Token 用量"""
        response = {
            "id": "chatcmpl-123",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        
        usage = proxy_service.extract_usage_from_response(response)
        
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30
    
    def test_extract_usage_from_response_no_usage(self, proxy_service):
        """测试从无用量信息的响应中提取"""
        response = {
            "id": "chatcmpl-123",
            "choices": []
        }

        usage = proxy_service.extract_usage_from_response(response)

        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_parse_sse_chunks_with_buffer_handles_fragmented_usage_event(self, proxy_service):
        """测试 SSE usage 事件被拆包时仍能正确解析"""
        usage_payload = json.dumps({
            "id": "chatcmpl-123",
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18
            }
        })
        first_chunk = f"data: {usage_payload[:35]}".encode("utf-8")
        second_chunk = f"{usage_payload[35:]}\n\n".encode("utf-8")
        buffer = [""]

        first_result = proxy_service.parse_sse_chunks_with_buffer(first_chunk, buffer)
        second_result = proxy_service.parse_sse_chunks_with_buffer(second_chunk, buffer)

        assert first_result == []
        assert len(second_result) == 1
        assert second_result[0]["usage"]["total_tokens"] == 18
        assert buffer[0] == ""

    def test_parse_sse_chunks_with_buffer_handles_utf8_split_in_multibyte_char(self, proxy_service):
        """测试 UTF-8 多字节字符（中文）被 TCP 分片切断时能正确处理

        模拟场景：中文字符"你"的 UTF-8 编码为 3 字节 (0xE4 0xBD 0xA0)，
        TCP 分片可能在字节中间切断，此时旧实现会抛 UnicodeDecodeError 并丢数据。
        """
        payload = json.dumps({"choices": [{"delta": {"content": "你好世界"}}]}, ensure_ascii=False)
        full_message = f"data: {payload}\n\n".encode("utf-8")
        # 寻找一个在多字节字符中间的切点：第一个中文字符"你"的 3 字节中间
        # "data: {..." 前缀是 ASCII，然后 "你" 是 3 字节。
        # 注意：json.dumps 默认分隔符为 ": "（冒号后带空格），marker 需带空格才能匹配
        marker = '"content": "'.encode("utf-8")
        marker_end = full_message.index(marker) + len(marker)
        # 切在"你"的第 2 字节之后（即中间）
        split_point = marker_end + 2
        first_chunk = full_message[:split_point]
        second_chunk = full_message[split_point:]

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]

        # 第一个 chunk 末尾是不完整的多字节字符，不应抛错也不应解析出结果
        first_result = proxy_service.parse_sse_chunks_with_buffer(first_chunk, buffer)
        second_result = proxy_service.parse_sse_chunks_with_buffer(second_chunk, buffer)

        assert first_result == []
        assert len(second_result) == 1
        assert second_result[0]["choices"][0]["delta"]["content"] == "你好世界"
        assert buffer[0] == ""

    def test_parse_sse_chunks_with_buffer_handles_emoji_split(self, proxy_service):
        """测试 4 字节 emoji 被 TCP 分片切断时能正确处理

        emoji "😀" 的 UTF-8 编码为 4 字节 (0xF0 0x9F 0x98 0x80)。
        """
        payload = json.dumps({"choices": [{"delta": {"content": "hi 😀!"}}]}, ensure_ascii=False)
        full_message = f"data: {payload}\n\n".encode("utf-8")
        # 在 emoji 的第 2 字节和第 3 字节之间切断
        emoji_bytes = "😀".encode("utf-8")
        emoji_idx = full_message.index(emoji_bytes)
        split_point = emoji_idx + 2
        first_chunk = full_message[:split_point]
        second_chunk = full_message[split_point:]

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]

        first_result = proxy_service.parse_sse_chunks_with_buffer(first_chunk, buffer)
        second_result = proxy_service.parse_sse_chunks_with_buffer(second_chunk, buffer)

        assert first_result == []
        assert len(second_result) == 1
        assert second_result[0]["choices"][0]["delta"]["content"] == "hi 😀!"

    def test_parse_sse_chunks_with_buffer_backward_compatible_single_element_buffer(self, proxy_service):
        """测试传入旧格式的 [""] buffer 时向后兼容（自动补齐 decoder）"""
        payload = json.dumps({"choices": [{"delta": {"content": "ok"}}]})
        message = f"data: {payload}\n\n".encode("utf-8")

        buffer = [""]
        result = proxy_service.parse_sse_chunks_with_buffer(message, buffer)

        assert len(result) == 1
        assert result[0]["choices"][0]["delta"]["content"] == "ok"
        # 应已自动补齐 decoder 与解析失败警告标志
        assert len(buffer) == 3

    def test_parse_sse_chunks_with_buffer_is_final_flush(self, proxy_service):
        """测试 is_final=True 时能 flush 缓冲区中最后一条无结尾换行的消息"""
        payload = json.dumps({"choices": [{"delta": {"content": "tail"}}]})
        # 故意不加 \n\n 结尾
        message = f"data: {payload}".encode("utf-8")

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]

        # 普通调用：因末尾无分隔符，消息应被缓存，results 为空
        result1 = proxy_service.parse_sse_chunks_with_buffer(message, buffer)
        assert result1 == []
        assert buffer[0] != ""

        # is_final=True 调用：应 flush 出最后的消息
        result2 = proxy_service.parse_sse_chunks_with_buffer(b"", buffer, is_final=True)
        assert len(result2) == 1
        assert result2[0]["choices"][0]["delta"]["content"] == "tail"

    def test_parse_sse_chunks_with_buffer_handles_crlf_line_endings(self, proxy_service):
        """测试上游使用 CRLF 行分隔的 SSE 流仍能正确解析

        模拟中转网关返回 \r\n 行分隔 + \r\n\r\n 事件分隔的非标准（但 SSE 规范内）格式。
        """
        payload1 = json.dumps({"type": "content_block_delta", "index": 0})
        payload2 = json.dumps({"type": "content_block_delta", "index": 1})
        message = (
            f"event: content_block_delta\r\ndata: {payload1}\r\n\r\n"
            f"event: content_block_delta\r\ndata: {payload2}\r\n\r\n"
        ).encode("utf-8")

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]
        result = proxy_service.parse_sse_chunks_with_buffer(message, buffer)

        assert len(result) == 2
        assert result[0]["index"] == 0
        assert result[1]["index"] == 1

    def test_parse_sse_chunks_with_buffer_salvages_concatenated_events(self, proxy_service):
        """测试事件间缺少空行分隔（粘连）时能扫描式挽救完整 JSON 事件

        模拟场景：上游把两个事件挤在同一个 \\n\\n 分隔的 part 内，
        data 行结束后直接跟下一个 event 行（实际线上偶发的 Format 告警来源）。
        """
        payload1 = json.dumps({"delta": {"partial_json": "my", "type": "input_json_delta"}, "type": "content_block_delta", "index": 2})
        payload2 = json.dumps({"delta": {"partial_json": "Side", "type": "input_json_delta"}, "type": "content_block_delta", "index": 2})
        # 事件间无空行：data:{json1} 后直接跟 event:...\ndata:{json2}，整体以 \n\n 结尾
        message = (
            f"event:content_block_delta\ndata:{payload1}"
            f"event:content_block_delta\ndata:{payload2}\n\n"
        ).encode("utf-8")

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]
        result = proxy_service.parse_sse_chunks_with_buffer(message, buffer)

        # 两个事件都应被挽救，而不是 drop
        assert len(result) == 2
        assert result[0]["delta"]["partial_json"] == "my"
        assert result[1]["delta"]["partial_json"] == "Side"

    def test_parse_sse_chunks_with_buffer_salvage_keeps_truncated_part_in_buffer(self, proxy_service):
        """测试尾部不完整 part 仍走 buffer 暂存，不做 salvage（避免丢截断尾巴）"""
        payload1 = json.dumps({"a": 1})
        # 第二个 JSON 被截断，且整段不以 \n\n 结尾（last part）
        message = f"data:{payload1}data:{{\"b\": 2".encode("utf-8")

        buffer = ["", codecs.getincrementaldecoder("utf-8")()]
        result = proxy_service.parse_sse_chunks_with_buffer(message, buffer)

        # last part 且未结束：整体暂存，不提取 {a:1}（等拼接后完整解析）
        assert result == []
        assert "data:" in buffer[0]

        # 下个 chunk 补全第二个 JSON 并以分隔符结束
        second_chunk = "}}\n\n".encode("utf-8")
        result2 = proxy_service.parse_sse_chunks_with_buffer(second_chunk, buffer)
        assert len(result2) == 2
        assert result2[0] == {"a": 1}
        assert result2[1] == {"b": 2}

    def test_parse_sse_chunks_with_buffer_warns_only_once_per_request(self, proxy_service):
        """测试解析失败 WARNING 同一请求至多一条（降噪）"""
        # 两段完全损坏的数据（无任何可挽救 JSON），以 \n\n 分隔
        message = b"data: not-json-at-all\n\ndata: still-not-json\n\n"
        buffer = ["", codecs.getincrementaldecoder("utf-8")()]

        with patch("app.core.sse_parser.logger") as mock_logger:
            result = proxy_service.parse_sse_chunks_with_buffer(message, buffer)
            assert result == []
            # WARNING 只应触发一次，第二次失败降级为 DEBUG
            warning_calls = [c for c in mock_logger.warning.call_args_list]
            assert len(warning_calls) == 1
            # 警告标志已置位
            assert buffer[2] is True


    def test_extract_usage_from_stream_chunks_handles_multiple_events(self, proxy_service):
        """测试从多个流式事件中提取最后的 usage"""
        chunks = [
            {
                "id": "chatcmpl-123",
                "choices": [{"delta": {"content": "Hello"}}]
            },
            {
                "id": "chatcmpl-123",
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20
                }
            }
        ]

        usage = proxy_service.extract_usage_from_stream_chunks(chunks)

        assert usage["prompt_tokens"] == 12
        assert usage["completion_tokens"] == 8
        assert usage["total_tokens"] == 20

    # ==================== handle_non_stream_response 测试 ====================
    
    @pytest.mark.asyncio
    async def test_handle_non_stream_response(self, proxy_service):
        """测试处理非流式响应"""
        response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello!"}}]
        }
        
        result = await proxy_service.handle_non_stream_response(response)
        
        assert result == response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
