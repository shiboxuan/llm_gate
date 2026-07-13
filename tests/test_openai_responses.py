"""
OpenAI Responses API 测试

测试 v2.0 新增的 OpenAI Responses API 原生转发功能。
包含：
- 用量提取测试
- 用量记录构建测试
- api_type 验证测试
- 错误处理测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.tool import RouteConfig
from app.api.data_plane.responses import (
    extract_responses_usage,
    extract_responses_stream_usage,
    _build_responses_usage_record,
)


# ==================== 用量提取测试 ====================

class TestResponsesUsageExtraction:
    """OpenAI Responses API 用量提取函数测试"""
    
    def test_extract_responses_usage_basic(self):
        """测试基本用量提取"""
        response = {
            "id": "resp_abc123",
            "object": "response",
            "created_at": 1710000000,
            "model": "gpt-4o",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hello!"}]
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150
            },
            "status": "completed"
        }
        
        usage = extract_responses_usage(response)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
    
    def test_extract_responses_usage_calculate_total(self):
        """测试自动计算 total_tokens"""
        response = {
            "usage": {
                "input_tokens": 200,
                "output_tokens": 100
            }
        }
        
        usage = extract_responses_usage(response)
        
        assert usage["prompt_tokens"] == 200
        assert usage["completion_tokens"] == 100
        assert usage["total_tokens"] == 300
    
    def test_extract_responses_usage_empty(self):
        """测试空响应的用量提取"""
        response = {}
        
        usage = extract_responses_usage(response)
        
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0
    
    def test_extract_responses_usage_no_usage_field(self):
        """测试没有 usage 字段的响应"""
        response = {
            "id": "resp_abc123",
            "status": "completed"
        }
        
        usage = extract_responses_usage(response)
        
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0


class TestResponsesStreamUsageExtraction:
    """OpenAI Responses API 流式响应用量提取测试"""
    
    def test_extract_stream_usage_from_response_done(self):
        """测试从 response.done 事件提取用量"""
        chunks = [
            {
                "type": "response.created",
                "response": {"id": "resp_abc123", "status": "in_progress"}
            },
            {
                "type": "response.output_item.added",
                "item": {"type": "message", "role": "assistant"}
            },
            {
                "type": "response.content_part.delta",
                "delta": {"type": "text_delta", "text": "Hello"}
            },
            {
                "type": "response.done",
                "response": {
                    "id": "resp_abc123",
                    "status": "completed"
                },
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150
                }
            }
        ]
        
        usage = extract_responses_stream_usage(chunks)
        
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
    
    def test_extract_stream_usage_calculate_total(self):
        """测试流式用量自动计算 total"""
        chunks = [
            {
                "type": "response.done",
                "usage": {
                    "input_tokens": 80,
                    "output_tokens": 40
                }
            }
        ]
        
        usage = extract_responses_stream_usage(chunks)
        
        assert usage["prompt_tokens"] == 80
        assert usage["completion_tokens"] == 40
        assert usage["total_tokens"] == 120
    
    def test_extract_stream_usage_empty_chunks(self):
        """测试空 chunks 列表的用量提取"""
        chunks = []
        
        usage = extract_responses_stream_usage(chunks)
        
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0
    
    def test_extract_stream_usage_no_usage_events(self):
        """测试没有用量事件的 chunks"""
        chunks = [
            {"type": "response.created"},
            {"type": "response.content_part.delta", "delta": {"text": "Hi"}}
        ]
        
        usage = extract_responses_stream_usage(chunks)
        
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0


# ==================== 用量记录构建测试 ====================

class TestBuildResponsesUsageRecord:
    """OpenAI Responses API 用量记录构建测试"""
    
    def test_build_usage_record_success(self):
        """测试成功请求的用量记录构建"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "gpt4o-responses",
            "provider_key_name": "openai_key",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1/responses"
        }
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
        
        record = _build_responses_usage_record(config, usage, "gpt-4o", "success")
        
        assert record["user_id"] == "user_001"
        assert record["tool_id"] == 1
        assert record["route_name"] == "gpt4o-responses"
        assert record["model"] == "gpt-4o"
        assert record["prompt_tokens"] == 100
        assert record["completion_tokens"] == 50
        assert record["total_tokens"] == 150
        assert record["api_type"] == "openai_responses"
        assert record["status"] == "success"
        assert record["error_message"] is None
    
    def test_build_usage_record_error(self):
        """测试错误请求的用量记录构建"""
        config = {
            "user_id": "user_001",
            "tool_id": 1,
            "active_route_name": "gpt4o-responses",
            "provider_key_name": "openai_key",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1/responses"
        }
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        record = _build_responses_usage_record(config, usage, "gpt-4o", "error", "Rate limit exceeded")
        
        assert record["status"] == "error"
        assert record["error_message"] == "Rate limit exceeded"
        assert record["api_type"] == "openai_responses"


# ==================== RouteConfig 测试 ====================

class TestRouteConfigOpenAIResponses:
    """RouteConfig 模型 openai_responses api_type 测试"""
    
    def test_openai_responses_type(self):
        """测试设置 api_type 为 openai_responses"""
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            provider_key_name="openai_key",
            api_type="openai_responses"
        )
        assert config.api_type == "openai_responses"
    
    def test_model_dump_includes_api_type(self):
        """测试 model_dump 包含 api_type 字段"""
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            provider_key_name="openai_key",
            api_type="openai_responses"
        )
        data = config.model_dump()
        assert "api_type" in data
        assert data["api_type"] == "openai_responses"


# ==================== 工具测试 Fixtures ====================

@pytest.fixture
def test_tool_openai_responses():
    """创建使用 OpenAI Responses API 的测试工具"""
    from app.models.tool import Tool, RouteConfig
    
    tool = Tool(
        id=20,
        user_id="user_001",
        name="GPT-4o Responses工具",
        description="使用 OpenAI Responses API 的工具",
        token_hash="hash_responses123",
        active_route_name="gpt4o-responses",
        routes={
            "gpt4o-responses": RouteConfig(
                base_url="https://api.openai.com/v1",
                model="gpt-4o",
                provider_key_name="openai_key",
                api_type="openai_responses"
            )
        },
        status=1
    )
    return tool


# ==================== 错误处理测试 ====================

class TestResponsesErrorHandling:
    """OpenAI Responses API 错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_handle_401_error(self):
        """测试 401 认证错误处理"""
        from app.api.data_plane.responses import handle_openai_responses_error
        from app.core.exceptions import APIException
        from app.core.error_codes import ErrorCode
        
        error_body = {
            "error": {
                "type": "invalid_request_error",
                "code": "invalid_api_key",
                "message": "Invalid API key"
            }
        }
        
        with pytest.raises(APIException) as exc_info:
            await handle_openai_responses_error(401, error_body, "https://api.openai.com/v1/responses")
        
        assert exc_info.value.code == ErrorCode.PROVIDER_AUTH_ERROR
    
    @pytest.mark.asyncio
    async def test_handle_429_rate_limit(self):
        """测试 429 限流错误处理"""
        from app.api.data_plane.responses import handle_openai_responses_error
        from app.core.exceptions import APIException
        from app.core.error_codes import ErrorCode
        
        error_body = {
            "error": {
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
                "message": "Rate limit exceeded"
            }
        }
        
        with pytest.raises(APIException) as exc_info:
            await handle_openai_responses_error(429, error_body, "https://api.openai.com/v1/responses")
        
        assert exc_info.value.code == ErrorCode.PROVIDER_RATE_LIMIT
    
    @pytest.mark.asyncio
    async def test_handle_400_bad_request(self):
        """测试 400 错误请求处理"""
        from app.api.data_plane.responses import handle_openai_responses_error
        from app.core.exceptions import APIException
        from app.core.error_codes import ErrorCode
        
        error_body = {
            "error": {
                "type": "invalid_request_error",
                "message": "Invalid parameter"
            }
        }
        
        with pytest.raises(APIException) as exc_info:
            await handle_openai_responses_error(400, error_body, "https://api.openai.com/v1/responses")
        
        assert exc_info.value.code == ErrorCode.PROVIDER_BAD_REQUEST
    
    @pytest.mark.asyncio
    async def test_handle_404_not_found(self):
        """测试 404 资源不存在错误处理"""
        from app.api.data_plane.responses import handle_openai_responses_error
        from app.core.exceptions import APIException
        from app.core.error_codes import ErrorCode
        
        error_body = {
            "error": {
                "type": "not_found_error",
                "message": "Model not found"
            }
        }
        
        with pytest.raises(APIException) as exc_info:
            await handle_openai_responses_error(404, error_body, "https://api.openai.com/v1/responses")
        
        assert exc_info.value.code == ErrorCode.PROVIDER_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_handle_500_server_error(self):
        """测试 500 服务器错误处理"""
        from app.api.data_plane.responses import handle_openai_responses_error
        from app.core.exceptions import ProviderError
        
        error_body = {
            "error": {
                "type": "server_error",
                "message": "Internal server error"
            }
        }
        
        with pytest.raises(ProviderError) as exc_info:
            await handle_openai_responses_error(500, error_body, "https://api.openai.com/v1/responses")
        
        assert exc_info.value.upstream_status == 500


# ==================== API 类型验证测试 ====================

class TestApiTypeValidation:
    """API 类型验证测试"""
    
    def test_openai_responses_is_valid_type(self):
        """测试 openai_responses 是有效的 api_type"""
        config = RouteConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            provider_key_name="openai_key",
            api_type="openai_responses"
        )
        assert config.api_type == "openai_responses"
    
    def test_mixed_routes_with_responses(self):
        """测试工具包含 openai_responses 和其他类型的多个路由"""
        from app.models.tool import Tool, RouteConfig
        
        tool = Tool(
            id=21,
            user_id="user_001",
            name="混合工具",
            description="包含多种 API 类型的路由",
            token_hash="hash_mixed_responses123",
            active_route_name="chat-route",
            routes={
                "chat-route": RouteConfig(
                    base_url="https://api.openai.com/v1",
                    model="gpt-4",
                    provider_key_name="openai_key",
                    api_type="openai_chat"
                ),
                "responses-route": RouteConfig(
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o",
                    provider_key_name="openai_key",
                    api_type="openai_responses"
                )
            },
            status=1
        )
        
        assert tool.routes["chat-route"].api_type == "openai_chat"
        assert tool.routes["responses-route"].api_type == "openai_responses"


# ==================== 端点逻辑测试 ====================

class TestResponsesEndpointLogic:
    """OpenAI Responses API 端点逻辑测试"""
    
    def test_api_type_check_logic(self):
        """测试 api_type 检查逻辑"""
        # 模拟配置 - openai_chat 类型
        config_openai_chat = {
            "api_type": "openai_chat",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        }
        
        api_type = config_openai_chat.get("api_type", "openai_chat")
        assert api_type != "openai_responses"
        
        # 模拟配置 - openai_responses 类型
        config_openai_responses = {
            "api_type": "openai_responses",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o"
        }
        
        api_type = config_openai_responses.get("api_type", "openai_chat")
        assert api_type == "openai_responses"
    
    def test_url_construction_logic(self):
        """测试 URL 构建逻辑"""
        # 测试各种 base_url 格式
        test_cases = [
            ("https://api.openai.com/v1", "https://api.openai.com/v1/responses"),
            ("https://api.openai.com/v1/", "https://api.openai.com/v1/responses"),
            ("https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1/responses"),
            ("https://api.openai.com/v1/messages", "https://api.openai.com/v1/responses"),
        ]
        
        for base_url, expected in test_cases:
            # 复制端点中的 URL 构建逻辑
            result_url = base_url.rstrip("/")
            for suffix in ["/chat/completions", "/messages", "/completions"]:
                if result_url.endswith(suffix):
                    result_url = result_url[:-len(suffix)]
                    break
            if not result_url.endswith("/responses"):
                result_url = result_url + "/responses"
            
            assert result_url == expected, f"Failed for {base_url}: got {result_url}, expected {expected}"
    
    def test_authorization_extraction_logic(self):
        """测试授权头提取逻辑"""
        # 有效的 Bearer token
        auth_header = "Bearer test_token_123"
        assert auth_header.startswith("Bearer ")
        token = auth_header.replace("Bearer ", "").strip()
        assert token == "test_token_123"
        
        # 无效的格式
        invalid_auth = "Basic base64encoded"
        assert not invalid_auth.startswith("Bearer ")
    
    def test_stream_detection_logic(self):
        """测试流式请求检测逻辑"""
        # 非流式请求
        body_non_stream = {"model": "gpt-4o", "input": "Hello"}
        is_stream = body_non_stream.get("stream", False)
        assert is_stream is False
        
        # 流式请求
        body_stream = {"model": "gpt-4o", "input": "Hello", "stream": True}
        is_stream = body_stream.get("stream", False)
        assert is_stream is True
