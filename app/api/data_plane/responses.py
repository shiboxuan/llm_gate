"""
数据面 OpenAI Responses API

提供 OpenAI Responses API 接口，通过 Tool Token 认证。
支持 OpenAI Responses API 的原生转发，包括内置工具（web_search、code_interpreter）、
自定义函数工具、流式/非流式响应等功能。

v2.0 实现方式：
- 原生转发模式 (api_type: openai_responses)
  - 直接转发到 OpenAI Responses API，不做格式转换
  - 完整支持 OpenAI Responses API 所有特性

认证方式：
- Authorization: Bearer <tool_token>
"""
import codecs
import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Header, Request, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.exceptions import APIException, ProviderError
from app.core.error_codes import ErrorCode
from app.core.dependencies import get_proxy_service, get_usage_service
from app.core.timeout import get_stream_timeout, get_non_stream_timeout
from app.core.sse_parser import parse_sse_chunks_with_buffer
from app.core.security import sanitize_for_log
from app.services.proxy_service import ProxyService, _open_upstream_stream
from app.services.usage_service import UsageService
from app.api.data_plane._utils import (
    StreamUsageCollector,
    record_usage_background,
    build_openai_stream_error_events,
    parse_upstream_error_body,
)
from app.logger_mgr import get_logger

logger = get_logger("app.api.data_plane.responses")

router = APIRouter()


# ============ 用量提取函数 ============

def extract_responses_usage(response: Dict[str, Any]) -> Dict[str, int]:
    """
    从 OpenAI Responses API 响应中提取用量

    OpenAI Responses API 使用 input_tokens/output_tokens 命名

    Args:
        response: OpenAI Responses API 响应

    Returns:
        用量字典，包含 prompt_tokens, completion_tokens, total_tokens, cached_tokens
    """
    usage = response.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    # OpenAI Responses API cache tokens（来自 input_token_details）
    input_details = usage.get("input_token_details") or {}
    cached_tokens = input_details.get("cached_tokens", 0)

    # 如果没有 total_tokens，手动计算
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    result = {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
    }
    return result


def extract_responses_stream_usage(chunks: List[Dict]) -> Dict[str, int]:
    """
    从 OpenAI Responses API 流式响应中提取用量

    在流式响应中，用量信息通常在 response.done 事件中

    Args:
        chunks: 流式响应 chunk 列表

    Returns:
        用量字典，包含 prompt_tokens, completion_tokens, total_tokens, cached_tokens
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

    for chunk in chunks:
        # response.done 事件包含完整 usage
        chunk_type = chunk.get("type")
        if chunk_type == "response.done" or "usage" in chunk:
            chunk_usage = chunk.get("usage", {})
            if chunk_usage:
                usage["prompt_tokens"] = chunk_usage.get("input_tokens", 0)
                usage["completion_tokens"] = chunk_usage.get("output_tokens", 0)
                usage["total_tokens"] = chunk_usage.get("total_tokens", 0)

                # OpenAI Responses API cache tokens（来自 input_token_details）
                input_details = chunk_usage.get("input_token_details") or {}
                usage["cached_tokens"] = input_details.get("cached_tokens", 0)

                # 如果没有 total_tokens，手动计算
                if usage["total_tokens"] == 0:
                    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

    return usage


# ============ 用量记录构建函数 ============

def _build_responses_usage_record(config: Dict[str, Any], usage: Dict[str, int], request_model: Optional[str], status: str, error_message: Optional[str] = None) -> Dict[str, Any]:
    """
    构建 OpenAI Responses API 用量记录数据

    Args:
        config: 路由配置
        usage: 用量信息
        request_model: 请求模型
        status: 请求状态
        error_message: 错误信息（可选）

    Returns:
        用量记录数据字典
    """
    record_data = {
        "user_id": config.get("user_id"),
        "tool_id": config.get("tool_id"),
        "route_name": config.get("active_route_name"),
        "provider_key_name": config.get("provider_key_name"),
        "model": config.get("model"),
        "base_url": config.get("base_url"),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        # OpenAI cache tokens
        "cached_tokens": usage.get("cached_tokens", 0),
        "api_type": "openai_responses",
        "status": status,
        "error_message": error_message
    }
    return record_data


# ============ 错误处理函数 ============

async def handle_openai_responses_error(response_status: int, error_body: Any, url: str) -> None:
    """
    处理 OpenAI Responses API 错误响应

    Args:
        response_status: HTTP 状态码
        error_body: 错误响应体（期望 dict，但对任意形状做防御）
        url: 请求 URL

    Raises:
        APIException 或 ProviderError: 转换后的异常
    """
    if not isinstance(error_body, dict):
        error_body = {"error": {"type": "unknown", "message": error_body if isinstance(error_body, str) else str(error_body)}}

    error = error_body.get("error", {})
    if not isinstance(error, dict):
        error = {"type": "unknown", "message": str(error)}

    error_type = error.get("type", "unknown")
    error_message = error.get("message", "Unknown error")
    error_code = error.get("code", "unknown")
    
    logger.error(f"[OpenAI Responses] API error: status={response_status}, type={error_type}, code={error_code}, message={error_message}")
    
    if response_status == 401:
        raise APIException(code=ErrorCode.PROVIDER_AUTH_ERROR, message=f"OpenAI authentication failed: {error_message}")
    elif response_status == 429:
        raise APIException(code=ErrorCode.PROVIDER_RATE_LIMIT, message=f"OpenAI rate limit: {error_message}")
    elif response_status == 400:
        raise APIException(code=ErrorCode.PROVIDER_BAD_REQUEST, message=f"OpenAI bad request: {error_message}")
    elif response_status == 404:
        raise APIException(code=ErrorCode.PROVIDER_NOT_FOUND, message=f"OpenAI resource not found: {error_message}")
    else:
        raise ProviderError(upstream_status=response_status, upstream_response=json.dumps(error_body), upstream_url=url, request_context={"error_type": error_type, "error_code": error_code, "error_message": error_message})


# ============ 非流式转发函数 ============

async def forward_responses_non_stream(http_client: httpx.AsyncClient, url: str, headers: Dict[str, str], body: Dict[str, Any], config: Dict[str, Any], background_tasks: BackgroundTasks, usage_service: UsageService) -> JSONResponse:
    """
    非流式 OpenAI Responses API 转发
    
    Args:
        http_client: HTTP 客户端
        url: 请求 URL
        headers: 请求头
        body: 请求体
        config: 路由配置
        background_tasks: 后台任务
        usage_service: 用量服务
        
    Returns:
        JSONResponse: OpenAI Responses API 格式响应
    """
    try:
        response = await http_client.post(url, headers=headers, json=body, timeout=get_non_stream_timeout())

        if response.status_code >= 400:
            error_text = response.text
            safe_error_text = sanitize_for_log(error_text, headers)
            # 从脱敏文本再解析，避免上游回显 API Key 落进 ProviderError.data.upstream_response
            error_body = parse_upstream_error_body(safe_error_text)

            logger.error(f"[OpenAI Responses] API error: status={response.status_code}, body={safe_error_text[:500]}")

            # 记录错误用量
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = _build_responses_usage_record(config, error_usage, body.get("model"), "error", safe_error_text)
            background_tasks.add_task(record_usage_background, usage_service, record_data)

            await handle_openai_responses_error(response.status_code, error_body, url)
        
        response_data = response.json()
        
        # 提取用量
        usage = extract_responses_usage(response_data)
        
        # 异步记录用量
        record_data = _build_responses_usage_record(config, usage, body.get("model"), "success")
        background_tasks.add_task(record_usage_background, usage_service, record_data)
        
        logger.debug(f"[OpenAI Responses] Response: {json.dumps(response_data, ensure_ascii=False)[:500]}")
        
        return JSONResponse(content=response_data)
        
    except APIException:
        raise
    except ProviderError:
        raise
    except httpx.TimeoutException as e:
        logger.error(f"[OpenAI Responses] Request timeout: {e}")
        error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        record_data = _build_responses_usage_record(config, error_usage, body.get("model"), "error", f"Request timeout: {str(e)}")
        background_tasks.add_task(record_usage_background, usage_service, record_data)
        raise APIException(code=ErrorCode.PROXY_TIMEOUT, message=f"OpenAI Responses API timeout: {str(e)}")
    except Exception as e:
        logger.error(f"[OpenAI Responses] Request failed: {e}")
        error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        record_data = _build_responses_usage_record(config, error_usage, body.get("model"), "error", str(e))
        background_tasks.add_task(record_usage_background, usage_service, record_data)
        raise ProviderError(upstream_status=500, upstream_response=str(e), upstream_url=url, request_context={"model": body.get("model")})


# ============ 流式转发函数 ============

async def forward_responses_stream(http_client: httpx.AsyncClient, url: str, headers: Dict[str, str], body: Dict[str, Any], config: Dict[str, Any], background_tasks: BackgroundTasks, usage_service: UsageService) -> StreamingResponse:
    """
    流式 OpenAI Responses API 转发
    
    Args:
        http_client: HTTP 客户端
        url: 请求 URL
        headers: 请求头
        body: 请求体
        config: 路由配置
        background_tasks: 后台任务
        usage_service: 用量服务
        
    Returns:
        StreamingResponse: 流式响应
    """
    collector = StreamUsageCollector()

    # 前置：打开上游连接并校验状态码。4xx/5xx 时在这里抛 ProviderError，
    # 此时尚未构造 StreamingResponse，exception handler 能正常返回 JSON。
    try:
        response = await _open_upstream_stream(http_client, url, headers, body)
    except ProviderError as e:
        collector.mark_error(e.upstream_response or str(e))
        raise

    async def stream_generator():
        # SSE 解析缓冲区：buffer[0]=字符残留, buffer[1]=UTF-8 增量 decoder
        # 用 aiter_bytes + parse_sse_chunks_with_buffer 保证 UTF-8 多字节字符跨 TCP 分片
        # 不会被 decode(errors="replace") 替换成 U+FFFD
        sse_buffer: List[Any] = ["", codecs.getincrementaldecoder("utf-8")()]

        def _collect_events(events: List[Dict[str, Any]]) -> None:
            for data in events:
                collector.add_chunk(data)
                if data.get("type") == "response.content_part.delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        collector.full_response_text += delta.get("text", "")

        try:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    try:
                        events = parse_sse_chunks_with_buffer(chunk, sse_buffer)
                        _collect_events(events)
                    except Exception:
                        pass

                try:
                    final_events = parse_sse_chunks_with_buffer(b"", sse_buffer, is_final=True)
                    _collect_events(final_events)
                except Exception:
                    pass

                collector.mark_complete()

            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.StreamError, httpx.ReadTimeout, httpx.WriteError) as e:
                logger.error(
                    f"[OpenAI Responses Stream] 上游流式连接中断\n"
                    f"├── upstream_url: {url}\n"
                    f"├── exception_type: {type(e).__name__}\n"
                    f"├── exception_message: {str(e)}\n"
                    f"└── request_model: {body.get('model')}"
                )
                error_msg = f"upstream_stream_interrupted: {type(e).__name__}: {e}"
                collector.mark_error(error_msg)
                error_payload = build_openai_stream_error_events(
                    error_type="upstream_stream_error",
                    message="Upstream connection closed before stream completed"
                )
                yield error_payload
                return
            except httpx.TimeoutException as e:
                logger.error(f"[OpenAI Responses Stream] Request timeout: {type(e).__name__}: {e}")
                collector.mark_error(f"upstream_stream_timeout: {type(e).__name__}: {e}")
                error_payload = build_openai_stream_error_events(
                    error_type="upstream_stream_error",
                    message="Upstream timeout while streaming response"
                )
                yield error_payload
                return
            except Exception as e:
                logger.error(f"[OpenAI Responses Stream] 未预期异常: {type(e).__name__}: {e}")
                collector.mark_error(f"upstream_stream_error: {type(e).__name__}: {e}")
                error_payload = build_openai_stream_error_events(
                    error_type="upstream_stream_error",
                    message="Unexpected error while streaming upstream response"
                )
                yield error_payload
                return
        finally:
            try:
                await response.aclose()
            except Exception:
                pass

    # 后台任务记录用量
    background_tasks.add_task(_process_responses_stream_usage, config, collector, body.get("model"), usage_service)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", "Transfer-Encoding": "chunked"}
    )


async def _process_responses_stream_usage(config: Dict[str, Any], collector: StreamUsageCollector, request_model: Optional[str], usage_service: UsageService) -> None:
    """
    处理 OpenAI Responses API 流式响应的用量记录
    
    Args:
        config: 路由配置
        collector: 用量收集器
        request_model: 请求模型
        usage_service: 用量服务
    """
    try:
        import asyncio
        await asyncio.sleep(0.1)
        
        logger.debug(f"[OpenAI Responses Stream] ========== 流式输出响应 ==========")
        logger.debug(f"[OpenAI Responses Stream] Response Text:\n{collector.full_response_text}")
        
        if collector.error:
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = _build_responses_usage_record(config, error_usage, request_model, "error", collector.error)
        else:
            usage = extract_responses_stream_usage(collector.chunks)
            record_data = _build_responses_usage_record(config, usage, request_model, "success")
        
        await usage_service.record_usage(record_data)
        logger.debug(f"[OpenAI Responses Stream] Usage recorded: tool_id={record_data.get('tool_id')}, tokens={record_data.get('total_tokens')}")
        
    except Exception as e:
        logger.error(f"[OpenAI Responses Stream] Failed to record usage: {e}")


# ============ API 端点 ============

@router.post("/responses")
async def create_response(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(..., description="Bearer <tool_token>"),
    openai_beta: Optional[str] = Header(None, alias="OpenAI-Beta", description="OpenAI Beta 功能标识"),
    proxy_service: ProxyService = Depends(get_proxy_service),
    usage_service: UsageService = Depends(get_usage_service)
):
    """
    OpenAI Responses API 代理端点
    
    支持 OpenAI Responses API 格式，将请求转发到配置的目标 Provider。
    仅当 api_type 为 openai_responses 时使用此端点。
    
    特性：
    - 支持内置工具（web_search_preview、code_interpreter）
    - 支持自定义函数工具
    - 支持流式和非流式响应
    - 自动记录 Token 用量
    
    认证方式：
    - Authorization: Bearer <tool_token>
    """
    # 1. 提取并验证 Tool Token
    if not authorization.startswith("Bearer "):
        raise APIException(code=ErrorCode.TOKEN_INVALID, message="Invalid authorization header format. Expected: Bearer <tool_token>")
    
    tool_token = authorization.replace("Bearer ", "").strip()
    if not tool_token:
        raise APIException(code=ErrorCode.TOKEN_INVALID, message="Tool token is empty")
    
    # 2. 解析路由配置
    config = await proxy_service.resolve_route_config(tool_token)
    if not config:
        raise APIException(code=ErrorCode.TOOL_TOKEN_INVALID)
    
    # 3. 验证 api_type
    api_type = config.get("api_type", "openai_chat")
    if api_type != "openai_responses":
        raise APIException(code=ErrorCode.ROUTE_NOT_FOUND, message=f"This endpoint requires api_type 'openai_responses', got '{api_type}'. Please use /v1/chat/completions for openai_chat type or configure your route with api_type='openai_responses'.")
    
    # 4. 获取原始请求体
    body = await request.json()
    
    # DEBUG: 打印输入请求
    logger.debug(f"[OpenAI Responses] ========== 输入请求 ==========")
    logger.debug(f"[OpenAI Responses] API Type: {api_type}")
    logger.debug(f"[OpenAI Responses] Model: {body.get('model')}, Stream: {body.get('stream', False)}")
    logger.debug(f"[OpenAI Responses] Input: {json.dumps(body.get('input', ''), ensure_ascii=False)[:500]}")
    if body.get('tools'):
        logger.debug(f"[OpenAI Responses] Tools: {json.dumps(body.get('tools', []), ensure_ascii=False)}")
    
    # 5. 构建目标 URL
    base_url = config["base_url"].rstrip("/")
    # 移除可能存在的其他端点后缀
    for suffix in ["/chat/completions", "/messages", "/completions"]:
        if base_url.endswith(suffix):
            base_url = base_url[:-len(suffix)]
            break
    # 确保以 /responses 结尾
    if not base_url.endswith("/responses"):
        base_url = base_url + "/responses"
    
    # 6. 覆盖模型（使用路由配置的模型）
    body["model"] = config["model"]
    
    # 7. 构建请求头
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }
    
    # 透传 beta header
    if openai_beta:
        headers["OpenAI-Beta"] = openai_beta
    
    # 8. 判断流式/非流式
    is_stream = body.get("stream", False)
    
    # 9. 获取 HTTP 客户端
    http_client = proxy_service.http_client
    
    if is_stream:
        return await forward_responses_stream(http_client, base_url, headers, body, config, background_tasks, usage_service)
    else:
        return await forward_responses_non_stream(http_client, base_url, headers, body, config, background_tasks, usage_service)