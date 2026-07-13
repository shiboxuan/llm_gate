"""
数据面 Chat Completions API

提供 OpenAI 兼容的 Chat Completions 接口，通过 Tool Token 认证。
注意：数据面是高频接口，不校验用户 Token，只校验 Tool Token。
适用于 Cline、Cursor、Claude Code 等 IDE 工具场景。

V2: 增加 Token 用量记录功能
V2.1: 修复流式响应阻塞问题，优化用量收集逻辑
"""
import asyncio
import codecs
from typing import AsyncGenerator, Dict, Any, List, Optional

import httpx
from fastapi import APIRouter, Header, Request, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.exceptions import APIException, ProviderError
from app.core.error_codes import ErrorCode
from app.core.dependencies import get_proxy_service, get_usage_service
from app.services.proxy_service import ProxyService
from app.services.usage_service import UsageService
from app.schemas.chat import ChatCompletionRequest
from app.api.data_plane._utils import StreamUsageCollector, record_usage_background, build_openai_stream_error_events
from app.logger_mgr import get_logger

logger = get_logger("app.api.data_plane.chat")

router = APIRouter()


async def create_stream_generator(
    proxy_service: ProxyService,
    response: httpx.Response,
    collector: StreamUsageCollector
) -> AsyncGenerator[bytes, None]:
    """
    创建流式响应生成器

    生成器负责转发数据并收集 chunk，用量记录在生成器外部处理。
    前置状态码检查由调用方通过 proxy_service.open_upstream_stream 完成；
    传入的 response 已是 2xx、仍持有连接，本函数在 finally 中 aclose。

    Args:
        proxy_service: 代理服务（仅用于 SSE 解析工具方法）
        response: 已打开的上游流式响应（状态码 < 400）
        collector: 用量收集器

    Yields:
        响应数据块
    """
    sse_buffer = ["", codecs.getincrementaldecoder("utf-8")()]

    try:
        try:
            async for chunk in response.aiter_bytes():
                parsed_chunks = proxy_service.parse_sse_chunks_with_buffer(chunk, sse_buffer)
                for parsed in parsed_chunks:
                    collector.add_chunk(parsed)
                yield chunk

            final_parsed = proxy_service.parse_sse_chunks_with_buffer(b"", sse_buffer, is_final=True)
            for parsed in final_parsed:
                collector.add_chunk(parsed)

            collector.mark_complete()

        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.StreamError, httpx.ReadTimeout, httpx.WriteError) as e:
            logger.error(f"[Chat Stream] 上游流式连接中断: {type(e).__name__}: {e}")
            error_msg = f"upstream_stream_interrupted: {type(e).__name__}: {e}"
            collector.mark_error(error_msg)
            error_payload = build_openai_stream_error_events(
                error_type="upstream_stream_error",
                message="Upstream connection closed before stream completed"
            )
            yield error_payload
            return
        except Exception as e:
            logger.error(f"[Chat Stream] 未预期异常: {type(e).__name__}: {e}")
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


async def process_stream_usage(
    proxy_service: ProxyService,
    usage_service: UsageService,
    config: Dict[str, Any],
    collector: StreamUsageCollector,
    request_model: Optional[str]
) -> None:
    """
    处理流式响应的用量记录
    
    在流结束后调用，从收集器中提取用量并记录。
    
    Args:
        proxy_service: 代理服务
        usage_service: 用量服务
        config: 路由配置
        collector: 用量收集器
        request_model: 请求模型
    """
    try:
        # 等待一小段时间确保流已完全结束
        await asyncio.sleep(0.1)
        
        if collector.error:
            # 流发生错误
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = proxy_service.build_usage_record_data(
                config, error_usage,
                request_model=request_model,
                status="error",
                error_message=collector.error
            )
        else:
            # 流正常结束，提取用量
            usage = proxy_service.extract_usage_from_stream_chunks(collector.chunks)
            record_data = proxy_service.build_usage_record_data(
                config, usage,
                request_model=request_model,
                status="success"
            )
        
        await usage_service.record_usage(record_data)
        logger.debug(f"Stream usage recorded: tool_id={record_data.get('tool_id')}, tokens={record_data.get('total_tokens')}")
        
    except Exception as e:
        logger.error(f"Failed to record stream usage: {e}")


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(..., description="Bearer <tool_token>"),
    proxy_service: ProxyService = Depends(get_proxy_service),
    usage_service: UsageService = Depends(get_usage_service)
):
    """
    代理 Chat Completions 请求
    
    支持 OpenAI 兼容格式，将请求转发到配置的目标 Provider。
    支持流式和非流式响应。
    
    认证方式：
    - 仅需 Tool Token（在 Authorization Header 中）
    - 不需要用户 JWT Token
    - 适用于 Cline、Cursor、Claude Code 等 IDE 工具
    
    V2 特性：
    - 自动记录 Token 用量到数据库
    - 异步写入，不阻塞响应
    
    V2.1 修复：
    - 重构流式响应逻辑，解决多轮对话阻塞问题
    - 优化用量收集和记录时机
    """
    # 1. 提取并验证 Tool Token 格式
    if not authorization.startswith("Bearer "):
        raise APIException(
            code=ErrorCode.TOKEN_INVALID,
            message="Invalid authorization header format, expected: Bearer <tool_token>"
        )
    
    tool_token = authorization.replace("Bearer ", "").strip()
    if not tool_token:
        raise APIException(code=ErrorCode.TOKEN_INVALID, message="Tool token is empty")
    
    # 2. 解析路由配置（缓存优先，由 proxy_service 内部处理）
    config = await proxy_service.resolve_route_config(tool_token)
    if not config:
        raise APIException(code=ErrorCode.TOOL_TOKEN_INVALID)
    
    # 补全 base_url：如果用户配置的 URL 未包含 /chat/completions，则自动添加
    if not config["base_url"].rstrip("/").endswith("/chat/completions"):
        config["base_url"] = config["base_url"].rstrip("/") + "/chat/completions"
    
    # 3. 解析请求体
    body = await request.json()
    chat_request = ChatCompletionRequest(**body)
    
    # 4. 构建 Provider 请求
    url = config['base_url']
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }
    provider_request = proxy_service.build_provider_request(config, chat_request)
    
    # 5. 转发请求并记录用量
    if chat_request.stream:
        # === 流式响应 ===
        collector = StreamUsageCollector()

        # 先打开上游连接并校验状态码：4xx/5xx 在这里抛 ProviderError，由 exception handler 返回 JSON
        upstream_response = await proxy_service.open_upstream_stream(url, headers, provider_request)

        try:
            stream_gen = create_stream_generator(proxy_service, upstream_response, collector)
            background_tasks.add_task(
                process_stream_usage, proxy_service, usage_service, config, collector, chat_request.model
            )
            return StreamingResponse(
                stream_gen,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked"
                }
            )
        except Exception:
            await upstream_response.aclose()
            raise
    else:
        # === 非流式响应 ===
        try:
            response_data = await proxy_service.forward_chat_completion(config, chat_request)
            
            # 提取用量并异步记录
            usage = proxy_service.extract_usage_from_response(response_data)
            record_data = proxy_service.build_usage_record_data(
                config, usage,
                request_model=chat_request.model,
                status="success"
            )
            background_tasks.add_task(record_usage_background, usage_service, record_data)
            
            return JSONResponse(content=response_data)
            
        except Exception as e:
            # 记录错误请求
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = proxy_service.build_usage_record_data(
                config, error_usage,
                request_model=chat_request.model,
                status="error",
                error_message=str(e)
            )
            background_tasks.add_task(record_usage_background, usage_service, record_data)
            raise
