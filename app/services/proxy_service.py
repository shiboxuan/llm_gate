"""
代理服务模块

提供 LLM 代理请求转发功能，支持流式和非流式两种响应模式
Service 层通过构造函数接收 http_client 依赖，不在内部创建

V2: 增加 Token 用量记录功能
V3: 增加 Anthropic Messages API 支持，兼容 Claude Code（格式转换模式）
V4: 增强错误日志，捕获上游 Provider 完整错误信息
"""
import asyncio
import codecs
import json
from typing import AsyncGenerator, Dict, Any, Optional, List

import httpx

from app.core.security import hash_tool_token, sanitize_for_log
from app.core.exceptions import ProviderError
from app.core.timeout import get_stream_timeout, get_non_stream_timeout
from app.core.sse_parser import parse_sse_chunks_with_buffer as _parse_sse_chunks_with_buffer
from app.services.cache_service import CacheService
from app.services.tool_service import ToolService
from app.services.provider_key_service import ProviderKeyService
from app.schemas.chat import ChatCompletionRequest
from app.logger_mgr import get_logger

logger = get_logger("app.services.proxy_service")


async def _open_upstream_stream(
    http_client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    request: Dict[str, Any],
    request_context: Optional[Dict[str, Any]] = None,
) -> httpx.Response:
    """
    打开上游流式请求并完成前置状态码检查。

    独立函数，可供 ProxyService 和其他流式转发函数复用。
    调用方负责在结束时 `await response.aclose()`。

    Args:
        http_client: HTTP 客户端
        url: 请求 URL
        headers: 请求头
        request: 请求体字典
        request_context: 请求上下文（用于错误日志），不传则自动构建

    Returns:
        已打开、状态码 < 400 的 httpx.Response

    Raises:
        ProviderError: 上游返回 >= 400 或 httpx.HTTPStatusError
    """
    if request_context is None:
        request_context = {"model": request.get("model")}

    req = http_client.build_request("POST", url, headers=headers, json=request, timeout=get_stream_timeout())
    response = await http_client.send(req, stream=True)
    try:
        if response.status_code >= 400:
            error_body = await response.aread()
            error_text = error_body.decode("utf-8", errors="replace")
            safe_error_text = sanitize_for_log(error_text, headers)
            logger.error(
                f"[proxy_error] Provider 流式请求返回错误\n"
                f"├── upstream_url: {url}\n"
                f"├── upstream_status: {response.status_code}\n"
                f"├── upstream_response: {safe_error_text[:500]}\n"
                f"├── request_model: {request.get('model')}\n"
                f"└── request_messages_count: {len(request.get('messages', []))}"
            )
            await response.aclose()
            raise ProviderError(
                upstream_status=response.status_code,
                upstream_response=safe_error_text,
                upstream_url=url,
                request_context=request_context,
            )
    except ProviderError:
        raise
    except httpx.HTTPStatusError as e:
        error_text = e.response.text if hasattr(e.response, "text") else str(e)
        safe_error_text = sanitize_for_log(error_text, headers)
        logger.error(
            f"[proxy_error] Provider 流式请求 HTTPStatusError\n"
            f"├── upstream_url: {url}\n"
            f"├── upstream_status: {e.response.status_code}\n"
            f"├── upstream_response: {safe_error_text[:500]}\n"
            f"├── request_model: {request.get('model')}\n"
            f"└── request_messages_count: {len(request.get('messages', []))}"
        )
        await response.aclose()
        raise ProviderError(
            upstream_status=e.response.status_code,
            upstream_response=safe_error_text,
            upstream_url=url,
            request_context=request_context,
        )
    except Exception:
        await response.aclose()
        raise

    return response


class ProxyService:
    """代理服务类
    
    提供 LLM 代理请求转发功能
    """
    
    def __init__(self, http_client: httpx.AsyncClient, cache_service: CacheService, tool_service: ToolService, provider_key_service: ProviderKeyService):
        """
        初始化代理服务
        
        Args:
            http_client: HTTP 异步客户端
            cache_service: 缓存服务实例
            tool_service: 工具服务实例
            provider_key_service: Provider Key 服务实例
        """
        self.http_client = http_client
        self.cache_service = cache_service
        self.tool_service = tool_service
        self.provider_key_service = provider_key_service
    
    async def resolve_route_config(self, tool_token: str) -> Optional[Dict[str, Any]]:
        """
        解析路由配置
        
        流程：
        1. 计算 Token 哈希
        2. 先查缓存
        3. 缓存未命中查数据库
        4. 解密 Provider Key
        5. 写入缓存
        
        Args:
            tool_token: 工具令牌（明文）
            
        Returns:
            路由配置字典，不存在或无效时返回 None
        """
        # 1. 计算 Token 哈希
        token_hash = hash_tool_token(tool_token)
        
        # 2. 先查缓存
        cached_config = await self.cache_service.get_route_config(token_hash)
        if cached_config:
            return cached_config
        
        # 3. 缓存未命中，查数据库
        tool = await self.tool_service.get_tool_by_token_hash(token_hash)
        if not tool:
            return None
        
        # 检查工具状态
        if tool.status != 1:
            return None
        
        # 检查是否有激活的路由
        if not tool.active_route_name or not tool.routes:
            return None
        
        active_route = tool.routes.get(tool.active_route_name)
        if not active_route:
            return None
        
        # 4. 获取并解密 Provider Key
        provider_key = await self.provider_key_service.get_decrypted_key_by_name(tool.user_id, active_route.provider_key_name)
        if not provider_key:
            return None
        
        # 5. 构建路由配置（v3.0: 包含 Tool 级别的 api_type）
        tool_dict = {
            "id": tool.id,
            "name": tool.name,
            "user_id": tool.user_id,
            "api_type": tool.api_type,  # v3.0: Tool 级别的 api_type
            "active_route_name": tool.active_route_name,
            "routes": {name: route.model_dump() for name, route in tool.routes.items()}
        }
        config = self.cache_service.build_route_config(tool_dict, provider_key)
        
        # 6. 写入缓存
        await self.cache_service.set_route_config(token_hash, config)
        
        return config
    
    def build_provider_request(self, config: Dict[str, Any], request: ChatCompletionRequest) -> Dict[str, Any]:
        """
        构建发往 Provider 的请求
        
        Args:
            config: 路由配置字典
            request: 聊天请求对象
            
        Returns:
            发往 Provider 的请求字典
        """
        # 使用路由配置中的模型
        model = config.get("model") or ""
        
        # 构建基本请求
        provider_request = {
            "model": model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": request.stream
        }
        
        # 检测是否需要使用 max_completion_tokens 而非 max_tokens
        # 某些新模型（如 gpt-5.x, o1, o3, o4 系列）不支持 max_tokens 参数
        models_requiring_max_completion_tokens = ["gpt-5", "o1", "o3", "o4"]
        use_max_completion_tokens = any(
            model.lower().startswith(prefix) 
            for prefix in models_requiring_max_completion_tokens
        )
        
        # 添加可选参数（只添加非 None 的参数）
        # 注意：max_tokens 需要特殊处理，不在此列表中
        optional_params = ["temperature", "top_p", "n", "stop", "presence_penalty", "frequency_penalty", "logit_bias", "user", "functions", "function_call", "tools", "tool_choice", "response_format", "seed"]
        for param in optional_params:
            value = getattr(request, param, None)
            if value is not None:
                provider_request[param] = value
        
        # 处理 max_tokens / max_completion_tokens 参数
        if request.max_tokens is not None:
            if use_max_completion_tokens:
                # 新模型使用 max_completion_tokens
                provider_request["max_completion_tokens"] = request.max_tokens
            else:
                # 传统模型使用 max_tokens
                provider_request["max_tokens"] = request.max_tokens
        
        # 处理 stream_options（OpenAI 格式，用于在流式响应中获取 usage）
        # 强制添加 include_usage=True 以确保获取 usage 信息
        if request.stream:
            stream_options = {"include_usage": True}
            # 如果客户端有其他 stream_options，合并它们
            if request.stream_options:
                client_options = request.stream_options.model_dump(exclude_none=True)
                stream_options.update(client_options)
            provider_request["stream_options"] = stream_options

        return provider_request
    
    async def forward_chat_completion(self, config: Dict[str, Any], request: ChatCompletionRequest):
        """
        转发聊天请求到目标 Provider
        
        Args:
            config: 路由配置字典
            request: 聊天请求对象
            
        Returns:
            流式模式返回 AsyncGenerator，非流式模式返回响应字典
        """
        url = config['base_url']
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        # 构建发往 Provider 的请求
        provider_request = self.build_provider_request(config, request)
        
        if request.stream:
            response = self._forward_stream(url, headers, provider_request)
            return response
        else:
            response = await self._forward_non_stream(url, headers, provider_request)
            return response
    
    async def _forward_stream(self, url: str, headers: Dict[str, str], request: Dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """
        流式转发
        
        Args:
            url: 请求 URL
            headers: 请求头
            request: 请求体字典
            
        Yields:
            响应数据块
            
        Raises:
            ProviderError: 当 Provider 返回错误时
        """
        try:
            async with self.http_client.stream("POST", url, headers=headers, json=request, timeout=get_stream_timeout()) as response:
                if response.status_code >= 400:
                    # 读取错误响应体
                    error_body = await response.aread()
                    error_text = error_body.decode("utf-8", errors="replace")

                    # 构建请求上下文
                    request_context = self._build_request_context(request)

                    # 记录错误日志（对 error_text 做 API Key 脱敏，防止上游回显请求头时泄露）
                    safe_error_text = sanitize_for_log(error_text, headers)
                    logger.error(
                        f"[proxy_error] Provider 流式请求返回错误\n"
                        f"├── upstream_url: {url}\n"
                        f"├── upstream_status: {response.status_code}\n"
                        f"├── upstream_response: {safe_error_text[:500]}\n"
                        f"├── request_model: {request.get('model')}\n"
                        f"└── request_messages_count: {len(request.get('messages', []))}"
                    )

                    raise ProviderError(
                        upstream_status=response.status_code,
                        upstream_response=safe_error_text,
                        upstream_url=url,
                        request_context=request_context
                    )

                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.HTTPStatusError as e:
            # 处理 raise_for_status() 抛出的异常（兼容旧代码）
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            request_context = self._build_request_context(request)

            safe_error_text = sanitize_for_log(error_text, headers)
            logger.error(
                f"[proxy_error] Provider 流式请求 HTTPStatusError\n"
                f"├── upstream_url: {url}\n"
                f"├── upstream_status: {e.response.status_code}\n"
                f"├── upstream_response: {safe_error_text[:500]}\n"
                f"├── request_model: {request.get('model')}\n"
                f"└── request_messages_count: {len(request.get('messages', []))}"
            )

            raise ProviderError(
                upstream_status=e.response.status_code,
                upstream_response=safe_error_text,
                upstream_url=url,
                request_context=request_context
            )
        # 中断类异常（RemoteProtocolError/ReadError/ReadTimeout/...）不在此 catch，
        # 保持原生 httpx 异常向上冒泡。调用方（已经在 yielding）负责 yield 协议级兜底
        # 并打一次结构化日志；避免"底层 catch + raise" 叠加上层 catch 产生双层日志。

    async def _forward_non_stream(self, url: str, headers: Dict[str, str], request: Dict[str, Any]) -> Dict[str, Any]:
        """
        非流式转发
        
        Args:
            url: 请求 URL
            headers: 请求头
            request: 请求体字典
            
        Returns:
            响应字典
            
        Raises:
            ProviderError: 当 Provider 返回错误时
        """
        response = await self.http_client.post(url, headers=headers, json=request, timeout=get_non_stream_timeout())

        # 检查响应状态码
        if response.status_code >= 400:
            error_text = response.text
            request_context = self._build_request_context(request)

            # 记录详细错误日志（对 error_text 做 API Key 脱敏）
            safe_error_text = sanitize_for_log(error_text, headers)
            logger.error(
                f"[proxy_error] Provider 非流式请求返回错误\n"
                f"├── upstream_url: {url}\n"
                f"├── upstream_status: {response.status_code}\n"
                f"├── upstream_response: {safe_error_text[:500]}\n"
                f"├── request_model: {request.get('model')}\n"
                f"└── request_messages_count: {len(request.get('messages', []))}"
            )
            
            raise ProviderError(
                upstream_status=response.status_code,
                upstream_response=safe_error_text,
                upstream_url=url,
                request_context=request_context
            )

        result = response.json()
        return result
    
    def _build_request_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        从请求中提取上下文信息，用于错误日志
        
        Args:
            request: 请求体字典
            
        Returns:
            请求上下文字典
        """
        context = {
            "model": request.get("model"),
            "messages_count": len(request.get("messages", [])),
            "stream": request.get("stream", False),
        }
        
        # 提取第一条用户消息（用于调试）
        messages = request.get("messages", [])
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    context["first_user_message"] = content[:200]
                elif isinstance(content, list):
                    # 多模态消息，提取文本部分
                    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    if texts:
                        context["first_user_message"] = texts[0][:200]
                break
        
        return context
    
    async def handle_stream_response(self, response: AsyncGenerator[bytes, None]) -> AsyncGenerator[bytes, None]:
        """
        处理流式响应
        
        直接转发流式数据，保持 SSE 格式
        
        Args:
            response: 流式响应生成器
            
        Yields:
            响应数据块
        """
        async for chunk in response:
            yield chunk
    
    async def handle_non_stream_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理非流式响应
        
        Args:
            response: 响应字典
            
        Returns:
            处理后的响应字典
        """
        # 直接返回响应，可以在此处添加额外处理逻辑
        return response
    
    def extract_usage_from_response(self, response: Dict[str, Any]) -> Dict[str, int]:
        """
        从非流式响应中提取 Token 用量

        Args:
            response: 响应字典

        Returns:
            用量字典，包含 prompt_tokens, completion_tokens, total_tokens, cached_tokens
        """
        usage = response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # OpenAI cache tokens（来自 prompt_tokens_details）
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = prompt_details.get("cached_tokens", 0)

        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
        }
        return result
    
    def extract_usage_from_stream_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        从流式响应的 chunks 中提取 Token 用量

        不同 Provider 的流式响应格式不同：
        - OpenAI: 最后一个 chunk 可能包含 usage（需要开启 stream_options）
        - Anthropic: 在 message_stop 事件中包含 usage

        Args:
            chunks: 流式响应 chunk 列表

        Returns:
            用量字典，包含 prompt_tokens, completion_tokens, total_tokens, cached_tokens
        """
        default_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}

        # 从后往前查找包含 usage 的 chunk
        for chunk in reversed(chunks):
            if "usage" in chunk and chunk["usage"]:
                usage = chunk["usage"]
                prompt_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)

                # OpenAI cache tokens（来自 prompt_tokens_details）
                prompt_details = usage.get("prompt_tokens_details") or {}
                cached_tokens = prompt_details.get("cached_tokens", 0)

                # 如果没有 total_tokens，计算它
                if total_tokens == 0:
                    total_tokens = prompt_tokens + completion_tokens

                result = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cached_tokens": cached_tokens,
                }
                return result

        return default_usage
    
    def build_usage_record_data(self, config: Dict[str, Any], usage: Dict[str, int], request_model: Optional[str] = None, status: str = "success", error_message: Optional[str] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        构建用量记录数据

        Args:
            config: 路由配置字典
            usage: Token 用量字典（可选包含 cache_creation_input_tokens, cache_read_input_tokens, cached_tokens）
            request_model: 请求中指定的模型（可选，如果为 None 使用配置中的模型）
            status: 请求状态（success/error）
            error_message: 错误信息（可选）
            request_id: 请求 ID（可选）

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
            # Anthropic cache tokens（OpenAI 等其他 provider 默认为 0）
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            # OpenAI cache tokens（Anthropic 等其他 provider 默认为 0）
            "cached_tokens": usage.get("cached_tokens", 0),
            "request_id": request_id,
            "status": status,
            "error_message": error_message
        }
        return record_data
    
    def parse_sse_chunk(self, chunk_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        解析 SSE 格式的 chunk（单条消息，向后兼容）
        
        Args:
            chunk_bytes: 原始 chunk 字节
            
        Returns:
            解析后的字典，解析失败返回 None
        """
        try:
            chunk_str = chunk_bytes.decode("utf-8").strip()
            # 跳过空行和注释
            if not chunk_str or chunk_str.startswith(":"):
                return None
            # 处理 SSE 格式: data: {...}
            if chunk_str.startswith("data:"):
                data_str = chunk_str[5:].strip()
                # 跳过 [DONE] 标记
                if data_str == "[DONE]":
                    return None
                parsed = json.loads(data_str)
                return parsed
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    
    def parse_sse_chunks_with_buffer(self, chunk_bytes: bytes, buffer: List[Any], is_final: bool = False) -> List[Dict[str, Any]]:
        """
        解析 SSE 格式的 chunk，薄包装以保持原有调用签名不变。

        实际实现位于 app.api.data_plane._utils.parse_sse_chunks_with_buffer。
        """
        return _parse_sse_chunks_with_buffer(chunk_bytes, buffer, is_final=is_final)
    
    async def open_upstream_stream(self, url: str, headers: Dict[str, str], request: Dict[str, Any]) -> httpx.Response:
        """
        打开上游流式请求并完成前置状态码检查。

        调用方负责在结束时 `await response.aclose()`。如果上游返回 4xx/5xx，
        本方法会把错误体读完、关闭连接并抛出 `ProviderError` —— 此时还没有任何
        字节下发给客户端，FastAPI 的 exception handler 能把它转成 JSONResponse。
        """
        request_context = self._build_request_context(request)
        return await _open_upstream_stream(self.http_client, url, headers, request, request_context)

