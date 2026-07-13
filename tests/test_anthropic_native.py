"""
Anthropic Messages 原生接口测试

测试 v2.0 新增的 Anthropic Messages API 原生转发功能。
包含：
- api_type 字段的兼容性测试
- 原生转发模式测试
- 格式转换模式测试
- 用量提取测试
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.tool import RouteConfig, ApiType
from app.services.cache_service import CacheService
from app.api.data_plane.messages import (
    extract_anthropic_usage,
    extract_anthropic_stream_usage,
    _build_anthropic_usage_record,
    _parse_anthropic_error_body,
    handle_anthropic_error,
)
from app.core.exceptions import APIException, ProviderError
from app.core.error_codes import ErrorCode


# ==================== RouteConfig 模型测试 ====================

class TestRouteConfigApiType:
    """RouteConfig 模型 api_type 字段测试"""
    
    def test_default_api_type(self):
        """测试 api_type 默认值为 openai_chat"""
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            provider_key_name="openai_key"
        )
        assert config.api_type == "openai_chat"
    
    def test_explicit_openai_chat(self):
        """测试显式设置 api_type 为 openai_chat"""
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            provider_key_name="openai_key",
            api_type="openai_chat"
        )
        assert config.api_type == "openai_chat"
    
    def test_anthropic_messages_type(self):
        """测试设置 api_type 为 anthropic_messages"""
        config = RouteConfig(
            base_url="https://api.anthropic.com/v1",
            model="claude-3-5-sonnet-20241022",
            provider_key_name="anthropic_key",
            api_type="anthropic_messages"
        )
        assert config.api_type == "anthropic_messages"
    
    def test_none_api_type_defaults_to_openai_chat(self):
        """测试 api_type 为 None 时默认设为 openai_chat"""
        # 模拟从数据库读取的旧数据（没有 api_type 字段）
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            provider_key_name="openai_key",
            api_type=None
        )
        assert config.api_type == "openai_chat"
    
    def test_model_dump_includes_api_type(self):
        """测试 model_dump 包含 api_type 字段"""
        config = RouteConfig(
            base_url="https://api.anthropic.com/v1",
            model="claude-3-5-sonnet-20241022",
            provider_key_name="anthropic_key",
            api_type="anthropic_messages"
        )
        data = config.model_dump()
        assert "api_type" in data
        assert data["api_type"] == "anthropic_messages"
    
    def test_from_dict_without_api_type(self):
        """测试从不包含 api_type 的字典创建 RouteConfig"""
        # 模拟从数据库读取的旧格式数据
        old_format_data = {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "provider_key_name": "openai_key"
        }
        config = RouteConfig(**old_format_data)
        assert config.api_type == "openai_chat"


# ==================== CacheService 测试 ====================

class TestCacheServiceApiType:
    """CacheService api_type 字段测试"""
    
    def test_build_route_config_with_api_type(self, mock_redis):
        """测试 build_route_config 包含 api_type"""
        cache_service = CacheService(mock_redis)
        
        tool = {
            "id": 1,
            "name": "test_tool",
            "user_id": "user_001",
            "active_route_name": "claude-route",
            "routes": {
                "claude-route": {
                    "base_url": "https://api.anthropic.com/v1",
                    "model": "claude-3-5-sonnet-20241022",
                    "provider_key_name": "anthropic_key",
                    "api_type": "anthropic_messages"
                }
            }
        }
        
        config = cache_service.build_route_config(tool, "sk-ant-xxxxx")
        
        assert "api_type" in config
        assert config["api_type"] == "anthropic_messages"
    
    def test_build_route_config_default_api_type(self, mock_redis):
        """测试 build_route_config 对旧数据使用默认 api_type"""
        cache_service = CacheService(mock_redis)
        
        # 旧格式数据，没有 api_type
        tool = {
            "id": 1,
            "name": "test_tool",
            "user_id": "user_001",
            "active_route_name": "default",
            "routes": {
                "default": {
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4",
                    "provider_key_name": "openai_key"
                }
            }
        }
        
        config = cache_service.build_route_config(tool, "sk-xxxxx")
        
        assert "api_type" in config
        assert config["api_type"] == "openai_chat"


# ==================== Anthropic 用量提取测试 ====================

class TestAnthropicUsageExtraction:
    """Anthropic 用量提取函数测试"""
    
    def test_extract_anthropic_usage_basic(self):
        """测试基本用量提取"""
        response = {
            "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50
            }
        }
        
        usage = extract_anthropic_usage(response)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
    
    def test_extract_anthropic_usage_with_cache(self):
        """测试包含 cache 信息的用量提取"""
        response = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 1500,
                "cache_read_input_tokens": 0
            }
        }
        
        usage = extract_anthropic_usage(response)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["cache_creation_input_tokens"] == 1500
        assert usage["cache_read_input_tokens"] == 0
    
    def test_extract_anthropic_usage_empty(self):
        """测试空响应的用量提取"""
        response = {}
        
        usage = extract_anthropic_usage(response)
        
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0
    
    def test_extract_anthropic_stream_usage(self):
        """测试流式响应的用量提取"""
        chunks = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": "claude-3-5-sonnet-20241022",
                    "stop_reason": None,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 0
                    }
                }
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""}
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"}
            },
            {
                "type": "content_block_stop",
                "index": 0
            },
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 15}
            },
            {
                "type": "message_stop"
            }
        ]
        
        usage = extract_anthropic_stream_usage(chunks)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 15
        assert usage["total_tokens"] == 115
    
    def test_extract_anthropic_stream_usage_empty(self):
        """测试空 chunks 列表的用量提取"""
        chunks = []

        usage = extract_anthropic_stream_usage(chunks)

        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_extract_anthropic_stream_usage_with_cache(self):
        """测试流式响应中 cache tokens 的提取"""
        chunks = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": "claude-3-5-sonnet-20241022",
                    "stop_reason": None,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 2000,
                        "cache_read_input_tokens": 500
                    }
                }
            },
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 25}
            },
            {
                "type": "message_stop"
            }
        ]

        usage = extract_anthropic_stream_usage(chunks)

        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 25
        assert usage["total_tokens"] == 125
        assert usage["cache_creation_input_tokens"] == 2000
        assert usage["cache_read_input_tokens"] == 500


# ==================== 用量记录构建测试 ====================

class TestBuildAnthropicUsageRecord:
    """Anthropic 用量记录构建测试"""
    
    def test_build_usage_record_success(self):
        """测试成功请求的用量记录构建"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "claude-route",
            "provider_key_name": "anthropic_key",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "https://api.anthropic.com/v1/messages"
        }
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
        
        record = _build_anthropic_usage_record(config, usage, "claude-3-5-sonnet-20241022", "success")
        
        assert record["user_id"] == "user_001"
        assert record["tool_id"] == 1
        assert record["route_name"] == "claude-route"
        assert record["model"] == "claude-3-5-sonnet-20241022"
        assert record["prompt_tokens"] == 100
        assert record["completion_tokens"] == 50
        assert record["total_tokens"] == 150
        assert record["api_type"] == "anthropic_messages"
        assert record["status"] == "success"
        assert record["error_message"] is None
    
    def test_build_usage_record_error(self):
        """测试错误请求的用量记录构建"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "claude-route",
            "provider_key_name": "anthropic_key",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "https://api.anthropic.com/v1/messages"
        }
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        record = _build_anthropic_usage_record(config, usage, "claude-3-5-sonnet-20241022", "error", "Rate limit exceeded")

        assert record["status"] == "error"
        assert record["error_message"] == "Rate limit exceeded"
        assert record["api_type"] == "anthropic_messages"

    def test_build_usage_record_with_cache(self):
        """测试包含 cache tokens 的用量记录构建"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "claude-route",
            "provider_key_name": "anthropic_key",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "https://api.anthropic.com/v1/messages"
        }
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cache_creation_input_tokens": 1500,
            "cache_read_input_tokens": 800
        }

        record = _build_anthropic_usage_record(config, usage, "claude-3-5-sonnet-20241022", "success")

        assert record["prompt_tokens"] == 100
        assert record["completion_tokens"] == 50
        assert record["total_tokens"] == 150
        assert record["cache_creation_input_tokens"] == 1500
        assert record["cache_read_input_tokens"] == 800
        assert record["api_type"] == "anthropic_messages"

    def test_build_usage_record_without_cache_defaults_to_zero(self):
        """测试没有 cache tokens 的用量记录默认为 0"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "claude-route",
            "provider_key_name": "anthropic_key",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "https://api.anthropic.com/v1/messages"
        }
        # 模拟 OpenAI 格式的 usage（没有 cache 字段）
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }

        record = _build_anthropic_usage_record(config, usage, "claude-3-5-sonnet-20241022", "success")

        assert record["cache_creation_input_tokens"] == 0
        assert record["cache_read_input_tokens"] == 0


# ==================== 工具测试 Fixtures ====================

@pytest.fixture
def test_tool_anthropic():
    """创建使用 Anthropic 原生模式的测试工具"""
    from app.models.tool import Tool, RouteConfig
    
    tool = Tool(
        id=10,
        user_id="user_001",
        name="Claude工具",
        description="使用 Anthropic Messages API 的工具",
        token_hash="hash_anthropic123",
        active_route_name="claude-native",
        routes={
            "claude-native": RouteConfig(
                base_url="https://api.anthropic.com/v1",
                model="claude-3-5-sonnet-20241022",
                provider_key_name="anthropic_key",
                api_type="anthropic_messages"
            )
        },
        status=1
    )
    return tool


@pytest.fixture
def test_tool_openai_conversion():
    """创建使用格式转换模式的测试工具"""
    from app.models.tool import Tool, RouteConfig
    
    tool = Tool(
        id=11,
        user_id="user_001",
        name="OpenAI工具",
        description="使用格式转换模式的工具",
        token_hash="hash_openai123",
        active_route_name="gpt4-route",
        routes={
            "gpt4-route": RouteConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4",
                provider_key_name="openai_key",
                api_type="openai_chat"
            )
        },
        status=1
    )
    return tool


# ==================== 兼容性测试 ====================

class TestBackwardCompatibility:
    """向后兼容性测试"""
    
    def test_old_route_config_format(self):
        """测试旧版路由配置格式（无 api_type）仍然有效"""
        old_config = {
            "base_url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4",
            "provider_key_name": "openai_key"
        }
        
        # 应该能正常创建 RouteConfig，api_type 默认为 openai_chat
        config = RouteConfig(**old_config)
        
        assert config.base_url == "https://api.openai.com/v1/chat/completions"
        assert config.model == "gpt-4"
        assert config.provider_key_name == "openai_key"
        assert config.api_type == "openai_chat"
    
    def test_tool_with_mixed_routes(self):
        """测试工具包含不同 api_type 的多个路由"""
        from app.models.tool import Tool, RouteConfig
        
        tool = Tool(
            id=12,
            user_id="user_001",
            name="混合工具",
            description="包含多种 API 类型的路由",
            token_hash="hash_mixed123",
            active_route_name="openai-route",
            routes={
                "openai-route": RouteConfig(
                    base_url="https://api.openai.com/v1",
                    model="gpt-4",
                    provider_key_name="openai_key",
                    api_type="openai_chat"
                ),
                "claude-route": RouteConfig(
                    base_url="https://api.anthropic.com/v1",
                    model="claude-3-5-sonnet-20241022",
                    provider_key_name="anthropic_key",
                    api_type="anthropic_messages"
                )
            },
            status=1
        )
        
        assert tool.routes["openai-route"].api_type == "openai_chat"
        assert tool.routes["claude-route"].api_type == "anthropic_messages"


# ==================== API 类型验证测试 ====================

class TestApiTypeValidation:
    """API 类型验证测试"""
    
    def test_valid_api_types(self):
        """测试所有有效的 api_type 值"""
        valid_types = ["openai_chat", "openai_responses", "anthropic_messages", "gemini_generate"]
        
        for api_type in valid_types:
            config = RouteConfig(
                base_url="https://example.com",
                model="test-model",
                provider_key_name="test_key",
                api_type=api_type
            )
            assert config.api_type == api_type
    
    def test_invalid_api_type(self):
        """测试无效的 api_type 值"""
        with pytest.raises(ValueError):
            RouteConfig(
                base_url="https://example.com",
                model="test-model",
                provider_key_name="test_key",
                api_type="invalid_type"
            )


# ==================== 错误响应解析测试（回归 2026-04-17 生产事故） ====================

class TestParseAnthropicErrorBody:
    """上游错误响应解析的形状兼容性测试"""

    def test_nested_json_message_merges_inner_error(self):
        """生产复现：error.message 是嵌套 JSON 字符串，应合并内层 error"""
        inner = {
            "type": "error",
            "request_id": "req_xxx",
            "error": {"type": "invalid_request_error", "message": "output_config.format: Extra inputs are not permitted"}
        }
        body = {"type": "error", "error": {"type": "invalid_request_error", "message": json.dumps(inner)}}
        result = _parse_anthropic_error_body(json.dumps(body))
        assert result["error"]["type"] == "invalid_request_error"
        assert "output_config.format" in result["error"]["message"]

    def test_json_string_literal_double_encoded(self):
        """上游返回 JSON 字符串字面量（双层 encode）"""
        inner = {"error": {"type": "invalid_request_error", "message": "bad"}}
        # 双层 encode：先 dumps inner 得到字符串，再 dumps 得到带引号的字符串字面量
        text = json.dumps(json.dumps(inner))
        result = _parse_anthropic_error_body(text)
        assert isinstance(result, dict)
        assert result["error"]["message"] == "bad"

    def test_plain_string_literal(self):
        """上游返回普通 JSON 字符串字面量，无法再解析为 dict"""
        text = json.dumps("some plain error")
        result = _parse_anthropic_error_body(text)
        assert result == {"error": {"type": "unknown", "message": "some plain error"}}

    def test_invalid_json(self):
        """上游返回非法 JSON（纯文本）"""
        result = _parse_anthropic_error_body("Gateway Timeout")
        assert result == {"error": {"type": "unknown", "message": "Gateway Timeout"}}

    def test_standard_error_dict(self):
        """标准 Anthropic 错误 dict，保持原样"""
        body = {"error": {"type": "rate_limit_error", "message": "slow down"}}
        result = _parse_anthropic_error_body(json.dumps(body))
        assert result["error"]["type"] == "rate_limit_error"
        assert result["error"]["message"] == "slow down"

    def test_json_list_wrapped(self):
        """上游返回 JSON list，应包装"""
        result = _parse_anthropic_error_body(json.dumps([1, 2, 3]))
        assert result["error"]["type"] == "unknown"
        assert "[1, 2, 3]" in result["error"]["message"]


class TestHandleAnthropicErrorDefense:
    """handle_anthropic_error 对非 dict error_body 的防御（回归 'str' object has no attribute 'get'）"""

    @pytest.mark.asyncio
    async def test_str_error_body_does_not_raise_attribute_error(self):
        """error_body 是 str 时，不应抛 AttributeError，而应转成 ProviderError"""
        with pytest.raises(ProviderError) as exc_info:
            await handle_anthropic_error(400, "some raw error text", "https://api.example.com/messages")
        assert exc_info.value.upstream_status == 400
        assert "some raw error text" in exc_info.value.upstream_response

    @pytest.mark.asyncio
    async def test_none_error_body(self):
        """error_body 是 None 也应安全处理"""
        with pytest.raises(ProviderError):
            await handle_anthropic_error(400, None, "https://api.example.com/messages")

    @pytest.mark.asyncio
    async def test_error_entry_not_dict(self):
        """error_body['error'] 是字符串时应归一化"""
        with pytest.raises(ProviderError) as exc_info:
            await handle_anthropic_error(400, {"error": "just a string"}, "https://api.example.com/messages")
        assert exc_info.value.upstream_status == 400

    @pytest.mark.asyncio
    async def test_401_maps_to_key_invalid(self):
        """401 仍然映射到 PROVIDER_KEY_INVALID"""
        with pytest.raises(APIException) as exc_info:
            await handle_anthropic_error(401, {"error": {"type": "authentication_error", "message": "bad key"}}, "https://api.example.com/messages")
        assert exc_info.value.code == ErrorCode.PROVIDER_KEY_INVALID

    @pytest.mark.asyncio
    async def test_429_maps_to_rate_limit(self):
        """429 仍然映射到 RATE_LIMIT_EXCEEDED"""
        with pytest.raises(APIException) as exc_info:
            await handle_anthropic_error(429, {"error": {"type": "rate_limit_error", "message": "slow down"}}, "https://api.example.com/messages")
        assert exc_info.value.code == ErrorCode.RATE_LIMIT_EXCEEDED


# ==================== SSE 断流兜底事件测试 ====================

class TestStreamErrorHelpers:
    """_utils.py 中 SSE 断流兜底 helper 的格式校验"""

    def test_build_anthropic_stream_error_events_contains_error_and_stop(self):
        from app.api.data_plane._utils import build_anthropic_stream_error_events

        payload = build_anthropic_stream_error_events("upstream_stream_error", "peer closed connection")

        assert isinstance(payload, bytes)
        text = payload.decode("utf-8")
        assert "event: error" in text
        assert "event: message_stop" in text
        assert "upstream_stream_error" in text
        assert "peer closed connection" in text
        # 两个 SSE 事件，各以 \n\n 结尾
        assert text.count("\n\n") >= 2

    def test_build_openai_stream_error_events_contains_error_and_done(self):
        from app.api.data_plane._utils import build_openai_stream_error_events

        payload = build_openai_stream_error_events("upstream_stream_error", "peer closed connection")

        assert isinstance(payload, bytes)
        text = payload.decode("utf-8")
        assert "upstream_stream_error" in text
        assert "peer closed connection" in text
        assert "[DONE]" in text
        assert text.count("\n\n") >= 2


class TestForwardAnthropicNativeStreamInterruption:
    """验证 forward_anthropic_native_stream 遇到上游流式中断时注入协议级 error 事件"""

    @pytest.mark.asyncio
    async def test_remote_protocol_error_injects_error_events(self):
        """上游在 aiter_bytes 中途抛 RemoteProtocolError 时，客户端应收到 error + message_stop 且不见裸异常"""
        import httpx
        from fastapi import BackgroundTasks
        from app.api.data_plane.messages import forward_anthropic_native_stream

        normal_chunk = b"event: message_start\ndata: {\"type\":\"message_start\"}\n\n"

        async def aiter_bytes_interrupted():
            yield normal_chunk
            raise httpx.RemoteProtocolError("peer closed connection without sending complete message body")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = MagicMock(return_value=aiter_bytes_interrupted())
        mock_response.aclose = AsyncMock()

        mock_http_client = MagicMock()
        mock_http_client.build_request = MagicMock(return_value=MagicMock())
        mock_http_client.send = AsyncMock(return_value=mock_response)

        background_tasks = BackgroundTasks()
        mock_usage_service = AsyncMock()
        mock_usage_service.record_usage = AsyncMock()

        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "default",
            "provider_key_name": "anthropic_key",
            "model": "claude-sonnet-4-5",
            "base_url": "https://api.anthropic.com/v1",
        }

        response = await forward_anthropic_native_stream(
            http_client=mock_http_client,
            url="https://api.anthropic.com/v1/messages",
            headers={},
            body={"model": "claude-sonnet-4-5"},
            config=config,
            background_tasks=background_tasks,
            usage_service=mock_usage_service,
        )

        collected = []
        async for chunk in response.body_iterator:
            collected.append(chunk)

        full = b"".join(collected)
        assert normal_chunk in full
        assert b"event: error" in full
        assert b"event: message_stop" in full
        assert b"upstream_stream_error" in full


class TestChatStreamInterruption:
    """验证 chat.create_stream_generator 遇到上游流式中断时注入 OpenAI 协议级 error + [DONE]"""

    @pytest.mark.asyncio
    async def test_remote_protocol_error_injects_error_and_done(self):
        import httpx
        from app.api.data_plane.chat import create_stream_generator
        from app.api.data_plane._utils import StreamUsageCollector

        normal_chunk = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'

        async def aiter_bytes_interrupted():
            yield normal_chunk
            raise httpx.RemoteProtocolError("peer closed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = MagicMock(return_value=aiter_bytes_interrupted())
        mock_response.aclose = AsyncMock()

        mock_proxy = MagicMock()
        mock_proxy.parse_sse_chunks_with_buffer = MagicMock(return_value=[])

        collector = StreamUsageCollector()

        chunks = []
        async for out in create_stream_generator(mock_proxy, mock_response, collector):
            chunks.append(out)

        full = b"".join(chunks)
        assert normal_chunk in full
        assert b"upstream_stream_error" in full
        assert b"[DONE]" in full
        assert collector.error is not None
        assert "upstream_stream_interrupted" in collector.error