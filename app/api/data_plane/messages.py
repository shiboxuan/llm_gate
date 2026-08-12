"""
数据面 Messages API

提供 Anthropic 兼容的 Messages 接口，通过 Tool Token 认证。
适用于 Claude Code 等使用 Anthropic API 格式的工具。

v2.0 实现方式：
1. 原生转发模式 (api_type: anthropic_messages)
   - 直接转发到 Anthropic API，不做格式转换
   - 完整支持 Anthropic 所有特性（cache_control、extended thinking 等）

2. 格式转换模式 (api_type: openai_chat，默认)
   - 入口：接收 Anthropic Messages 格式请求
   - 转换：Anthropic 格式 → OpenAI 格式
   - 转发：实际发送到 /chat/completions 端点
   - 返回：OpenAI 响应 → Anthropic 格式

认证方式支持：
- x-api-key: <tool_token> (Anthropic 原生格式)
- Authorization: Bearer <tool_token> (兼容 OpenAI 格式)
"""
import codecs
import json
import time
import uuid
from typing import AsyncGenerator, Dict, Any, List, Optional

import httpx
from fastapi import APIRouter, Header, Request, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse

from app.config import get_settings
from app.core.exceptions import APIException, ProviderError
from app.core.error_codes import ErrorCode
from app.core.dependencies import get_proxy_service, get_usage_service
from app.core.timeout import get_stream_timeout, get_non_stream_timeout
from app.core.security import sanitize_for_log
from app.services.proxy_service import ProxyService, _open_upstream_stream
from app.services.usage_service import UsageService
from app.schemas.messages import MessagesRequest, TextContent, ImageContent, ToolUseContent, ToolResultContent
from app.schemas.chat import ChatCompletionRequest, Message, StreamOptions
from app.api.data_plane._utils import (
    StreamUsageCollector,
    record_usage_background,
    build_anthropic_stream_error_events,
    parse_sse_chunks_with_buffer,
    parse_upstream_error_body as _parse_anthropic_error_body,
)
from app.logger_mgr import get_logger

logger = get_logger("app.api.data_plane.messages")

router = APIRouter()


class StreamConversionState:
    """流式转换状态跟踪 - 用于跟踪 thinking、text 和 tool_use content block 的状态"""

    def __init__(self):
        self.thinking_block_started: bool = False  # thinking block 是否已开始
        self.thinking_block_index: int = 0  # thinking block 的索引
        self.thinking_block_closed: bool = False  # thinking block 是否已关闭
        self.text_block_started: bool = False  # text block 是否已开始
        self.text_block_index: int = 0  # text block 的索引
        self.text_block_closed: bool = False  # text block 是否已关闭
        self.next_block_index: int = 0  # 下一个 block 的索引
        self.tool_blocks: Dict[int, int] = {}  # tool_call index -> block index 的映射
        self.tool_blocks_closed: set = set()  # 已关闭的 tool block 索引集合


# ============ 格式转换函数 ============

def convert_anthropic_to_openai(messages_request: MessagesRequest) -> ChatCompletionRequest:
    """
    将 Anthropic Messages 请求转换为 OpenAI Chat Completion 请求
    
    转换规则：
    - system 字段 → messages 数组中的 system 消息
    - messages 数组保持 user/assistant 角色
    - max_tokens → max_tokens
    - stop_sequences → stop
    
    Args:
        messages_request: Anthropic 格式请求
        
    Returns:
        OpenAI 格式请求
    """
    openai_messages = []
    
    # 1. 处理 system 消息（Anthropic 独立字段 → OpenAI messages 数组）
    if messages_request.system:
        if isinstance(messages_request.system, str):
            openai_messages.append(Message(role="system", content=messages_request.system))
        elif isinstance(messages_request.system, list):
            # 多个 system block，合并为一个
            system_texts = []
            for block in messages_request.system:
                if isinstance(block, dict) and block.get("type") == "text":
                    system_texts.append(block.get("text", ""))
            if system_texts:
                openai_messages.append(Message(role="system", content="\n".join(system_texts)))
    
    # 2. 转换消息列表（注意：一条 Anthropic 消息可能转换为多条 OpenAI 消息）
    for msg in messages_request.messages:
        openai_msgs = _convert_anthropic_message_to_openai(msg)
        if openai_msgs:
            openai_messages.extend(openai_msgs)
    
    # 3. 构建 OpenAI 请求
    openai_request = ChatCompletionRequest(
        model=messages_request.model,
        messages=openai_messages,
        max_tokens=messages_request.max_tokens,
        temperature=messages_request.temperature,
        top_p=messages_request.top_p,
        stream=messages_request.stream,
        stop=messages_request.stop_sequences,
    )
    
    # 4. 处理流式选项（确保获取 usage）
    if messages_request.stream:
        openai_request.stream_options = StreamOptions(include_usage=True)
    
    # 5. 处理工具定义（Anthropic → OpenAI）
    # 注意：Anthropic 支持内置工具（如 web_search_20250305）和自定义工具
    # OpenAI 只支持自定义函数工具，内置工具会被跳过
    if messages_request.tools:
        openai_tools = []
        for tool in messages_request.tools:
            tool_dict = tool.model_dump() if hasattr(tool, 'model_dump') else tool
            # 跳过内置工具（没有 input_schema 的工具，如 web_search）
            if not tool_dict.get("input_schema"):
                logger.debug(f"Skipping built-in tool: {tool_dict.get('type') or tool_dict.get('name')}")
                continue
            openai_tool = {"type": "function", "function": {"name": tool_dict.get("name"), "description": tool_dict.get("description", ""), "parameters": tool_dict.get("input_schema", {})}}
            openai_tools.append(openai_tool)
        if openai_tools:
            openai_request.tools = openai_tools
    
    if messages_request.tool_choice:
        # Anthropic tool_choice: {"type": "auto"} / {"type": "any"} / {"type": "tool", "name": "xxx"}
        tc = messages_request.tool_choice
        if tc.get("type") == "auto":
            openai_request.tool_choice = "auto"
        elif tc.get("type") == "any":
            openai_request.tool_choice = "required"
        elif tc.get("type") == "tool":
            openai_request.tool_choice = {"type": "function", "function": {"name": tc.get("name")}}
    
    return openai_request


def _convert_anthropic_message_to_openai(anthropic_msg) -> List[Message]:
    """
    转换单条 Anthropic 消息为 OpenAI 格式
    
    注意：一条 Anthropic 消息可能转换为多条 OpenAI 消息，
    特别是包含多个 tool_result 的 user 消息。
    
    Args:
        anthropic_msg: Anthropic 消息对象
        
    Returns:
        OpenAI Message 对象列表
    """
    role = anthropic_msg.role
    content = anthropic_msg.content
    
    # 简单文本内容
    if isinstance(content, str):
        return [Message(role=role, content=content)]
    
    # 复杂内容（列表形式）
    if isinstance(content, list):
        # 检查是否包含 tool_use 或 tool_result（兼容 Pydantic 对象和 dict）
        has_tool_use = any(isinstance(c, ToolUseContent) or (isinstance(c, dict) and c.get("type") == "tool_use") for c in content)
        has_tool_result = any(isinstance(c, ToolResultContent) or (isinstance(c, dict) and c.get("type") == "tool_result") for c in content)
        
        if has_tool_use and role == "assistant":
            # Assistant 的 tool_use → OpenAI tool_calls
            tool_calls = []
            text_parts = []
            for block in content:
                if isinstance(block, ToolUseContent):
                    tool_calls.append({"id": block.id, "type": "function", "function": {"name": block.name, "arguments": json.dumps(block.input)}})
                elif isinstance(block, TextContent):
                    text_parts.append(block.text)
                elif isinstance(block, dict):
                    # 兼容原始 dict
                    if block.get("type") == "tool_use":
                        tool_calls.append({"id": block.get("id"), "type": "function", "function": {"name": block.get("name"), "arguments": json.dumps(block.get("input", {}))}})
                    elif block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
            text_content = "\n".join(text_parts) if text_parts else None
            return [Message(role="assistant", content=text_content, tool_calls=tool_calls if tool_calls else None)]
        
        if has_tool_result and role == "user":
            # User 的 tool_result → OpenAI tool 角色消息
            # 关键修复：每个 tool_result 都转换为独立的 tool 消息
            messages = []
            text_parts = []
            
            for block in content:
                if isinstance(block, ToolResultContent):
                    result_content = block.content
                    if isinstance(result_content, list):
                        # 提取文本内容
                        texts = [c.get("text", "") for c in result_content if isinstance(c, dict) and c.get("type") == "text"]
                        result_content = "\n".join(texts)
                    messages.append(Message(role="tool", content=str(result_content) if result_content else "", tool_call_id=block.tool_use_id))
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    # 兼容原始 dict
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        texts = [c.get("text", "") for c in result_content if isinstance(c, dict) and c.get("type") == "text"]
                        result_content = "\n".join(texts)
                    messages.append(Message(role="tool", content=str(result_content), tool_call_id=block.get("tool_use_id")))
                elif isinstance(block, TextContent):
                    text_parts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            
            # 如果还有普通文本内容，也要添加为 user 消息
            if text_parts:
                messages.append(Message(role="user", content="\n".join(text_parts)))
            
            return messages
        
        # 普通多内容块（如图片+文本）
        openai_content = []
        for block in content:
            if isinstance(block, TextContent):
                openai_content.append({"type": "text", "text": block.text})
            elif isinstance(block, ImageContent):
                if block.source.type == "base64":
                    openai_content.append({"type": "image_url", "image_url": {"url": f"data:{block.source.media_type};base64,{block.source.data}"}})
            elif isinstance(block, dict):
                # 兼容原始 dict
                block_type = block.get("type")
                if block_type == "text":
                    openai_content.append({"type": "text", "text": block.get("text", "")})
                elif block_type == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        openai_content.append({"type": "image_url", "image_url": {"url": f"data:{source.get('media_type')};base64,{source.get('data')}"}})
        
        if openai_content:
            return [Message(role=role, content=openai_content)]
    
    return []


def convert_openai_to_anthropic(openai_response: Dict[str, Any], model: str) -> Dict[str, Any]:
    """
    将 OpenAI Chat Completion 响应转换为 Anthropic Messages 响应
    
    Args:
        openai_response: OpenAI 格式响应
        model: 模型名称
        
    Returns:
        Anthropic 格式响应
    """
    # 提取 choice
    choices = openai_response.get("choices", [])
    if not choices:
        content = [{"type": "text", "text": ""}]
        stop_reason = "end_turn"
    else:
        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        
        # 转换 content
        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message.get("content")})
        
        # 转换 tool_calls
        if message.get("tool_calls"):
            for tc in message.get("tool_calls", []):
                func = tc.get("function", {})
                try:
                    input_data = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    input_data = {}
                content.append({"type": "tool_use", "id": tc.get("id"), "name": func.get("name"), "input": input_data})
        
        # 转换 stop_reason
        stop_reason_map = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "content_filter": "end_turn"}
        stop_reason = stop_reason_map.get(finish_reason, "end_turn")
    
    # 转换 usage
    openai_usage = openai_response.get("usage", {})
    anthropic_usage = {"input_tokens": openai_usage.get("prompt_tokens", 0), "output_tokens": openai_usage.get("completion_tokens", 0)}
    
    # 构建 Anthropic 响应
    anthropic_response = {
        "id": f"msg_{openai_response.get('id', uuid.uuid4().hex[:24])}",
        "type": "message",
        "role": "assistant",
        "content": content if content else [{"type": "text", "text": ""}],
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": anthropic_usage
    }
    
    return anthropic_response


def convert_openai_stream_chunk_to_anthropic(chunk: Dict[str, Any], index: int, message_id: str, model: str, state: Optional[StreamConversionState] = None) -> List[str]:
    """
    将 OpenAI 流式 chunk 转换为 Anthropic SSE 格式
    
    支持 OpenAI reasoning 模型（如 o1, o3）的 reasoning_content 字段，
    将其转换为 Anthropic 的 thinking content block。
    
    Args:
        chunk: OpenAI 流式 chunk
        index: chunk 索引
        message_id: 消息 ID
        model: 模型名称
        state: 流式转换状态（用于跟踪 thinking/text/tool block 状态）
        
    Returns:
        Anthropic SSE 事件字符串列表
    """
    events = []
    
    # 如果没有传入 state，创建一个临时的（向后兼容）
    if state is None:
        state = StreamConversionState()
    
    choices = chunk.get("choices", [])
    usage = chunk.get("usage")
    
    # 第一个 chunk：发送 message_start
    if index == 0:
        message_start = {"type": "message_start", "message": {"id": message_id, "type": "message", "role": "assistant", "content": [], "model": model, "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}}
        events.append(f"event: message_start\ndata: {json.dumps(message_start)}\n\n")
    
    # 处理 delta
    if choices:
        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")
        
        # 处理 reasoning_content (OpenAI o1/o3 等模型的深度思考内容)
        # 转换为 Anthropic 的 thinking content block
        reasoning_content = delta.get("reasoning_content")
        if reasoning_content:
            # 首次出现 thinking 内容时，发送 content_block_start
            if not state.thinking_block_started:
                state.thinking_block_index = state.next_block_index
                state.next_block_index += 1
                state.thinking_block_started = True
                thinking_block_start = {"type": "content_block_start", "index": state.thinking_block_index, "content_block": {"type": "thinking", "thinking": ""}}
                events.append(f"event: content_block_start\ndata: {json.dumps(thinking_block_start)}\n\n")
            
            # 发送 thinking delta
            thinking_delta = {"type": "content_block_delta", "index": state.thinking_block_index, "delta": {"type": "thinking_delta", "thinking": reasoning_content}}
            events.append(f"event: content_block_delta\ndata: {json.dumps(thinking_delta)}\n\n")
        
        # 处理普通文本内容
        content = delta.get("content")
        if content:
            # 如果有 thinking block 正在进行且未关闭，先关闭它
            if state.thinking_block_started and not state.thinking_block_closed:
                thinking_block_stop = {"type": "content_block_stop", "index": state.thinking_block_index}
                events.append(f"event: content_block_stop\ndata: {json.dumps(thinking_block_stop)}\n\n")
                state.thinking_block_closed = True
            
            # 首次出现 text 内容时，发送 content_block_start
            if not state.text_block_started:
                state.text_block_index = state.next_block_index
                state.next_block_index += 1
                state.text_block_started = True
                text_block_start = {"type": "content_block_start", "index": state.text_block_index, "content_block": {"type": "text", "text": ""}}
                events.append(f"event: content_block_start\ndata: {json.dumps(text_block_start)}\n\n")
            
            # 发送 text delta
            content_delta = {"type": "content_block_delta", "index": state.text_block_index, "delta": {"type": "text_delta", "text": content}}
            events.append(f"event: content_block_delta\ndata: {json.dumps(content_delta)}\n\n")
        
        # 工具调用
        if delta.get("tool_calls"):
            # 如果有 thinking block 正在进行且未关闭，先关闭它
            if state.thinking_block_started and not state.thinking_block_closed:
                thinking_block_stop = {"type": "content_block_stop", "index": state.thinking_block_index}
                events.append(f"event: content_block_stop\ndata: {json.dumps(thinking_block_stop)}\n\n")
                state.thinking_block_closed = True
            
            # 如果有 text block 正在进行且未关闭，先关闭它
            if state.text_block_started and not state.text_block_closed:
                text_block_stop = {"type": "content_block_stop", "index": state.text_block_index}
                events.append(f"event: content_block_stop\ndata: {json.dumps(text_block_stop)}\n\n")
                state.text_block_closed = True
            
            for tc in delta.get("tool_calls", []):
                tc_index = tc.get("index", 0)  # OpenAI tool_call 的索引
                func = tc.get("function", {})
                
                if tc.get("id"):  # 工具调用开始（有 id 表示新的工具调用）
                    tool_block_index = state.next_block_index
                    state.next_block_index += 1
                    state.tool_blocks[tc_index] = tool_block_index  # 记录 tool_call index 到 block index 的映射
                    tool_start = {"type": "content_block_start", "index": tool_block_index, "content_block": {"type": "tool_use", "id": tc.get("id"), "name": func.get("name", ""), "input": {}}}
                    events.append(f"event: content_block_start\ndata: {json.dumps(tool_start)}\n\n")
                
                if func.get("arguments"):
                    # 使用映射的 block index，如果没有映射则使用 next_block_index - 1
                    tool_block_index = state.tool_blocks.get(tc_index, state.next_block_index - 1)
                    tool_delta = {"type": "content_block_delta", "index": tool_block_index, "delta": {"type": "input_json_delta", "partial_json": func.get("arguments")}}
                    events.append(f"event: content_block_delta\ndata: {json.dumps(tool_delta)}\n\n")
        
        # 结束
        if finish_reason:
            # 关闭所有未关闭的 content block
            
            # 关闭 thinking block
            if state.thinking_block_started and not state.thinking_block_closed:
                thinking_block_stop = {"type": "content_block_stop", "index": state.thinking_block_index}
                events.append(f"event: content_block_stop\ndata: {json.dumps(thinking_block_stop)}\n\n")
                state.thinking_block_closed = True
            
            # 关闭 text block
            if state.text_block_started and not state.text_block_closed:
                text_block_stop = {"type": "content_block_stop", "index": state.text_block_index}
                events.append(f"event: content_block_stop\ndata: {json.dumps(text_block_stop)}\n\n")
                state.text_block_closed = True
            
            # 关闭所有 tool blocks
            for tc_index, tool_block_index in state.tool_blocks.items():
                if tool_block_index not in state.tool_blocks_closed:
                    tool_block_stop = {"type": "content_block_stop", "index": tool_block_index}
                    events.append(f"event: content_block_stop\ndata: {json.dumps(tool_block_stop)}\n\n")
                    state.tool_blocks_closed.add(tool_block_index)
            
            # 如果没有任何 block 被创建（空响应），创建一个空的 text block
            if not state.thinking_block_started and not state.text_block_started and not state.tool_blocks:
                empty_block_start = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
                events.append(f"event: content_block_start\ndata: {json.dumps(empty_block_start)}\n\n")
                empty_block_stop = {"type": "content_block_stop", "index": 0}
                events.append(f"event: content_block_stop\ndata: {json.dumps(empty_block_stop)}\n\n")
            
            stop_reason_map = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use"}
            anthropic_stop = stop_reason_map.get(finish_reason, "end_turn")
            
            message_delta = {"type": "message_delta", "delta": {"stop_reason": anthropic_stop, "stop_sequence": None}, "usage": {"output_tokens": usage.get("completion_tokens", 0) if usage else 0}}
            events.append(f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n")
            
            message_stop = {"type": "message_stop"}
            events.append(f"event: message_stop\ndata: {json.dumps(message_stop)}\n\n")
    
    # 最后的 usage chunk（没有 choices 只有 usage 的情况）
    if usage and not choices:
        message_delta = {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": usage.get("completion_tokens", 0)}}
        events.append(f"event: message_delta\ndata: {json.dumps(message_delta)}\n\n")
    
    return events


# ============ 辅助函数 ============

def extract_tool_token(authorization: Optional[str], x_api_key: Optional[str]) -> str:
    """
    从请求头中提取 Tool Token
    
    支持两种认证方式：
    1. x-api-key: <tool_token> (Anthropic 原生格式)
    2. Authorization: Bearer <tool_token> (OpenAI 兼容格式)
    """
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "").strip()
            if token:
                return token

    if x_api_key:
        return x_api_key.strip()
    
    raise APIException(code=ErrorCode.TOKEN_INVALID, message="Missing authentication. Expected x-api-key header or Authorization: Bearer <tool_token>")


async def create_anthropic_stream_from_openai(proxy_service: ProxyService, response: httpx.Response, collector: StreamUsageCollector, model: str) -> AsyncGenerator[bytes, None]:
    """
    从 OpenAI 流式响应创建 Anthropic 格式流式响应

    支持 OpenAI reasoning 模型（如 o1, o3）的 reasoning_content 字段，
    将其转换为 Anthropic 的 thinking content block。

    前置状态码检查由调用方通过 proxy_service.open_upstream_stream 完成；
    传入的 response 已是 2xx、仍持有连接，本函数在 finally 中 aclose。

    Args:
        proxy_service: 代理服务（仅用于 SSE 解析工具方法）
        response: 已打开的上游流式响应（状态码 < 400）
        collector: 用量收集器
        model: 模型名称

    Yields:
        Anthropic SSE 格式的响应数据块
    """
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    chunk_index = 0
    state = StreamConversionState()

    sse_buffer = ["", codecs.getincrementaldecoder("utf-8")()]

    try:
        try:
            async for chunk in response.aiter_bytes():
                parsed_list = proxy_service.parse_sse_chunks_with_buffer(chunk, sse_buffer)

                for parsed in parsed_list:
                    collector.add_chunk(parsed)
                    choices = parsed.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if delta.get("content"):
                            collector.full_response_text += delta.get("content")
                        if delta.get("reasoning_content"):
                            collector.full_thinking_text += delta.get("reasoning_content")
                    anthropic_events = convert_openai_stream_chunk_to_anthropic(parsed, chunk_index, message_id, model, state)
                    for event in anthropic_events:
                        yield event.encode("utf-8")
                    chunk_index += 1

            final_parsed_list = proxy_service.parse_sse_chunks_with_buffer(b"", sse_buffer, is_final=True)
            for parsed in final_parsed_list:
                collector.add_chunk(parsed)
                choices = parsed.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if delta.get("content"):
                        collector.full_response_text += delta.get("content")
                    if delta.get("reasoning_content"):
                        collector.full_thinking_text += delta.get("reasoning_content")
                anthropic_events = convert_openai_stream_chunk_to_anthropic(parsed, chunk_index, message_id, model, state)
                for event in anthropic_events:
                    yield event.encode("utf-8")
                chunk_index += 1

            collector.mark_complete()

        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.StreamError, httpx.ReadTimeout, httpx.WriteError) as e:
            logger.error(f"[OpenAI→Anthropic Stream] 上游流式连接中断: {type(e).__name__}: {e}")
            error_msg = f"upstream_stream_interrupted: {type(e).__name__}: {e}"
            collector.mark_error(error_msg)
            error_payload = build_anthropic_stream_error_events(
                error_type="upstream_stream_error",
                message="Upstream connection closed before stream completed"
            )
            yield error_payload
            return
        except Exception as e:
            # 响应头已 200 下发，raise 无法转为 JSON 错误响应，必须 yield 协议级兜底再 return
            logger.error(f"[OpenAI→Anthropic Stream] 未预期异常: {type(e).__name__}: {e}")
            collector.mark_error(f"upstream_stream_error: {type(e).__name__}: {e}")
            error_payload = build_anthropic_stream_error_events(
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


async def process_stream_usage(proxy_service: ProxyService, usage_service: UsageService, config: Dict[str, Any], collector: StreamUsageCollector, request_model: Optional[str]) -> None:
    """处理流式响应的用量记录"""
    try:
        import asyncio
        await asyncio.sleep(0.1)
        
        # DEBUG: 打印流式输出响应
        logger.debug(f"[Messages API] ========== 流式输出响应 ==========")
        # 打印 thinking 内容（如果有）
        if collector.full_thinking_text:
            logger.debug(f"[Messages API] Stream Thinking Text:\n{collector.full_thinking_text}")
        # 打印普通响应文本
        logger.debug(f"[Messages API] Stream Response Text:\n{collector.full_response_text}")
        
        if collector.error:
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = proxy_service.build_usage_record_data(config, error_usage, request_model=request_model, status="error", error_message=collector.error)
        else:
            usage = proxy_service.extract_usage_from_stream_chunks(collector.chunks)
            record_data = proxy_service.build_usage_record_data(config, usage, request_model=request_model, status="success")
        
        await usage_service.record_usage(record_data)
        logger.debug(f"Stream usage recorded: tool_id={record_data.get('tool_id')}, tokens={record_data.get('total_tokens')}")
        
    except Exception as e:
        logger.error(f"Failed to record stream usage: {e}")


# ============ Anthropic 原生转发函数 (v2.0) ============

def extract_anthropic_usage(response: Dict[str, Any]) -> Dict[str, int]:
    """
    从 Anthropic 响应中提取用量

    注意：Anthropic 的 cache tokens 也是实际消耗的 token，需要计入总量：
    - input_tokens: 普通输入 token
    - cache_creation_input_tokens: 首次缓存创建的 token（按正常价格计费）
    - cache_read_input_tokens: 从缓存读取的 token（按优惠价格计费，但仍是消耗）

    Args:
        response: Anthropic API 响应

    Returns:
        用量字典，包含 prompt_tokens, completion_tokens, total_tokens
    """
    usage = response.get("usage", {})

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0)
    cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)

    # prompt_tokens 应包含所有输入相关的 token（普通输入 + 缓存创建 + 缓存读取）
    prompt_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens

    result = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        # Anthropic 特有字段（保留原始值用于详细分析）
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens
    }
    return result


def extract_anthropic_stream_usage(chunks: List[Dict]) -> Dict[str, int]:
    """
    从 Anthropic 流式响应中提取用量

    注意：Anthropic 的 cache tokens 也是实际消耗的 token，需要计入总量：
    - input_tokens: 普通输入 token
    - cache_creation_input_tokens: 首次缓存创建的 token（按正常价格计费）
    - cache_read_input_tokens: 从缓存读取的 token（按优惠价格计费，但仍是消耗）

    Args:
        chunks: 流式响应 chunk 列表

    Returns:
        用量字典，包含 prompt_tokens, completion_tokens, total_tokens,
        cache_creation_input_tokens, cache_read_input_tokens
    """
    input_tokens = 0
    output_tokens = 0
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0

    for chunk in chunks:
        chunk_type = chunk.get("type")

        # message_start 包含 input_tokens 和 cache tokens
        if chunk_type == "message_start":
            message = chunk.get("message", {})
            msg_usage = message.get("usage", {})
            input_tokens = msg_usage.get("input_tokens", 0)
            cache_creation_input_tokens = msg_usage.get("cache_creation_input_tokens", 0)
            cache_read_input_tokens = msg_usage.get("cache_read_input_tokens", 0)

        # message_delta 包含 output_tokens
        elif chunk_type == "message_delta":
            delta_usage = chunk.get("usage", {})
            output_tokens = delta_usage.get("output_tokens", 0)

    # prompt_tokens 应包含所有输入相关的 token（普通输入 + 缓存创建 + 缓存读取）
    prompt_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens

    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        # Anthropic 特有字段（保留原始值用于详细分析）
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens
    }
    return usage


async def handle_anthropic_error(response_status: int, error_body: Any, upstream_url: str) -> None:
    """
    处理 Anthropic API 错误响应

    Args:
        response_status: HTTP 状态码
        error_body: 错误响应体（期望 dict，但对任意形状做防御）
        upstream_url: 实际上游 URL（必填），用于 ProviderError 的日志上下文，
                      不给默认值可让静态检查/测试早期暴露遗漏的调用点

    Raises:
        APIException: 转换后的异常
    """
    if not isinstance(error_body, dict):
        error_body = {"error": {"type": "unknown", "message": error_body if isinstance(error_body, str) else str(error_body)}}

    error_entry = error_body.get("error", {})
    if not isinstance(error_entry, dict):
        error_entry = {"type": "unknown", "message": str(error_entry)}

    error_type = error_entry.get("type", "unknown")
    error_message = error_entry.get("message", "Unknown error")

    if response_status == 401:
        raise APIException(code=ErrorCode.PROVIDER_KEY_INVALID, message=f"Anthropic authentication failed: {error_message}")
    elif response_status == 429:
        raise APIException(code=ErrorCode.RATE_LIMIT_EXCEEDED, message=f"Anthropic rate limit: {error_message}")
    else:
        raise ProviderError(upstream_status=response_status, upstream_response=json.dumps(error_body, ensure_ascii=False), upstream_url=upstream_url, request_context={"error_type": error_type, "error_message": error_message})


async def forward_anthropic_native_non_stream(http_client, url: str, headers: Dict[str, str], body: Dict[str, Any], config: Dict[str, Any], background_tasks: BackgroundTasks, usage_service: UsageService) -> JSONResponse:
    """
    非流式 Anthropic 原生请求转发
    
    Args:
        http_client: HTTP 客户端
        url: 请求 URL
        headers: 请求头
        body: 请求体
        config: 路由配置
        background_tasks: 后台任务
        usage_service: 用量服务
        
    Returns:
        JSONResponse: Anthropic 格式响应
    """
    upstream_status: Optional[int] = None
    upstream_body: Optional[str] = None
    try:
        response = await http_client.post(url, headers=headers, json=body, timeout=get_non_stream_timeout())
        upstream_status = response.status_code

        if response.status_code >= 400:
            error_text = response.text
            safe_error_text = sanitize_for_log(error_text, headers)
            upstream_body = safe_error_text
            # 从脱敏后的文本再解析，确保落到 ProviderError.data.upstream_response 的字典里不含原始 key
            error_body = _parse_anthropic_error_body(safe_error_text)

            logger.error(f"[Anthropic Native] API error: status={response.status_code}, body={safe_error_text[:500]}")

            # 记录错误用量
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = _build_anthropic_usage_record(config, error_usage, body.get("model"), "error", safe_error_text)
            background_tasks.add_task(record_usage_background, usage_service, record_data)

            await handle_anthropic_error(response.status_code, error_body, upstream_url=url)

        response_data = response.json()

        # 提取用量
        usage = extract_anthropic_usage(response_data)

        # 异步记录用量
        record_data = _build_anthropic_usage_record(config, usage, body.get("model"), "success")
        background_tasks.add_task(record_usage_background, usage_service, record_data)

        logger.debug(f"[Anthropic Native] Response: {json.dumps(response_data, ensure_ascii=False)[:500]}")

        return JSONResponse(content=response_data)

    except APIException:
        raise
    except ProviderError:
        raise
    except Exception as e:
        # 保留原始上游信息，避免 400 被 500 完全覆盖
        safe_upstream_body = sanitize_for_log(upstream_body or "", headers)
        logger.error(f"[Anthropic Native] Request failed: {e}, upstream_status={upstream_status}, upstream_body={safe_upstream_body[:500]}")
        error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        record_data = _build_anthropic_usage_record(config, error_usage, body.get("model"), "error", str(e))
        background_tasks.add_task(record_usage_background, usage_service, record_data)
        fallback_status = upstream_status if upstream_status and upstream_status >= 400 else 500
        fallback_response = upstream_body if upstream_body else str(e)
        raise ProviderError(upstream_status=fallback_status, upstream_response=fallback_response, upstream_url=url, request_context={"model": body.get("model"), "inner_error": str(e)})


async def forward_anthropic_native_stream(http_client, url: str, headers: Dict[str, str], body: Dict[str, Any], config: Dict[str, Any], background_tasks: BackgroundTasks, usage_service: UsageService) -> StreamingResponse:
    """
    流式 Anthropic 原生请求转发
    
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
        # 避免 chunk.decode(errors="replace") 把跨 TCP 边界的多字节字符替换成 U+FFFD
        sse_buffer: List[Any] = ["", codecs.getincrementaldecoder("utf-8")()]

        def _collect_events(events: List[Dict[str, Any]]) -> None:
            for data in events:
                collector.add_chunk(data)
                if data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        collector.full_response_text += delta.get("text", "")
                    elif delta.get("type") == "thinking_delta":
                        collector.full_thinking_text += delta.get("thinking", "")

        try:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    try:
                        events = parse_sse_chunks_with_buffer(chunk, sse_buffer)
                        _collect_events(events)
                    except Exception:
                        pass  # 用量收集失败不影响转发

                try:
                    final_events = parse_sse_chunks_with_buffer(b"", sse_buffer, is_final=True)
                    _collect_events(final_events)
                except Exception:
                    pass

                collector.mark_complete()

            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.StreamError, httpx.ReadTimeout, httpx.WriteError) as e:
                logger.error(
                    f"[Anthropic Native Stream] 上游流式连接中断\n"
                    f"├── upstream_url: {url}\n"
                    f"├── exception_type: {type(e).__name__}\n"
                    f"├── exception_message: {str(e)}\n"
                    f"└── request_model: {body.get('model')}"
                )
                error_msg = f"upstream_stream_interrupted: {type(e).__name__}: {e}"
                collector.mark_error(error_msg)
                error_payload = build_anthropic_stream_error_events(
                    error_type="upstream_stream_error",
                    message="Upstream connection closed before stream completed"
                )
                yield error_payload
                return
            except Exception as e:
                # 响应头已 200 下发，raise 会让客户端看到裸截断；yield 协议级兜底后 return
                logger.error(f"[Anthropic Native Stream] 未预期异常: {type(e).__name__}: {e}")
                collector.mark_error(f"upstream_stream_error: {type(e).__name__}: {e}")
                error_payload = build_anthropic_stream_error_events(
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
    background_tasks.add_task(_process_anthropic_stream_usage, config, collector, body.get("model"), usage_service)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", "Transfer-Encoding": "chunked"}
    )


async def _process_anthropic_stream_usage(config: Dict[str, Any], collector: StreamUsageCollector, request_model: Optional[str], usage_service: UsageService) -> None:
    """处理 Anthropic 流式响应的用量记录"""
    try:
        import asyncio
        await asyncio.sleep(0.1)
        
        logger.debug(f"[Anthropic Native Stream] ========== 流式输出响应 ==========")
        if collector.full_thinking_text:
            logger.debug(f"[Anthropic Native Stream] Thinking Text:\n{collector.full_thinking_text}")
        logger.debug(f"[Anthropic Native Stream] Response Text:\n{collector.full_response_text}")
        
        if collector.error:
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = _build_anthropic_usage_record(config, error_usage, request_model, "error", collector.error)
        else:
            usage = extract_anthropic_stream_usage(collector.chunks)
            record_data = _build_anthropic_usage_record(config, usage, request_model, "success")
        
        await usage_service.record_usage(record_data)
        logger.debug(f"[Anthropic Native Stream] Usage recorded: tool_id={record_data.get('tool_id')}, tokens={record_data.get('total_tokens')}")
        
    except Exception as e:
        logger.error(f"[Anthropic Native Stream] Failed to record usage: {e}")


def _build_anthropic_usage_record(config: Dict[str, Any], usage: Dict[str, int], request_model: Optional[str], status: str, error_message: Optional[str] = None) -> Dict[str, Any]:
    """构建 Anthropic 用量记录数据"""
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
        # Anthropic cache tokens
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "api_type": "anthropic_messages",  # v2.0 新增
        "status": status,
        "error_message": error_message
    }
    return record_data


# ============ API 端点 ============

@router.post("/messages")
async def create_message(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None, description="Bearer <tool_token>"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key", description="Anthropic 格式的 API Key"),
    anthropic_version: Optional[str] = Header(None, alias="anthropic-version", description="Anthropic API 版本"),
    anthropic_beta: Optional[str] = Header(None, alias="anthropic-beta", description="Anthropic Beta 功能标识"),
    proxy_service: ProxyService = Depends(get_proxy_service),
    usage_service: UsageService = Depends(get_usage_service)
):
    """
    Anthropic Messages API 端点 (v2.0)
    
    v2.0 支持两种模式：
    1. 原生转发模式 (api_type: anthropic_messages)
       - 直接转发到 Anthropic API，不做格式转换
       - 完整支持 Anthropic 所有特性（cache_control、extended thinking 等）
    
    2. 格式转换模式 (api_type: openai_chat，默认)
       - 接收 Anthropic Messages 格式请求，转换为 OpenAI 格式后转发
       - 然后将响应转换回 Anthropic 格式返回
    
    认证方式：
    - x-api-key: <tool_token> (Anthropic 原生格式，Claude Code 使用)
    - Authorization: Bearer <tool_token> (兼容格式)
    
    特性：
    - 自动记录 Token 用量
    - 支持流式和非流式响应
    """
    # 1. 提取并验证 Tool Token
    tool_token = extract_tool_token(authorization, x_api_key)
    
    # 2. 解析路由配置（缓存优先）
    config = await proxy_service.resolve_route_config(tool_token)
    if not config:
        raise APIException(code=ErrorCode.TOOL_TOKEN_INVALID)
    
    # 3. 获取 api_type（默认 openai_chat 向后兼容）
    api_type = config.get("api_type", "openai_chat")
    
    # 4. 解析请求体
    body = await request.json()
    
    # DEBUG: 打印输入请求
    logger.debug(f"[Messages API] ========== 输入请求 ==========")
    logger.debug(f"[Messages API] API Type: {api_type}")
    logger.debug(f"[Messages API] Model: {body.get('model')}, Stream: {body.get('stream', False)}")
    logger.debug(f"[Messages API] System: {body.get('system')!r}")
    logger.debug(f"[Messages API] Roles in messages: {[m.get('role') for m in body.get('messages', [])]}")
    logger.debug(f"[Messages API] Messages:\n{json.dumps(body.get('messages', []), ensure_ascii=False, indent=2)}")
    
    # 5. 根据 api_type 选择处理方式
    if api_type == "anthropic_messages":
        # ============ 原生转发模式 ============
        return await _forward_anthropic_native(request, body, config, anthropic_version, anthropic_beta, background_tasks, proxy_service, usage_service)
    else:
        # ============ 格式转换模式 (v1.x 兼容) ============
        return await _forward_with_conversion(request, body, config, background_tasks, proxy_service, usage_service)


async def _forward_anthropic_native(request: Request, body: Dict[str, Any], config: Dict[str, Any], anthropic_version: Optional[str], anthropic_beta: Optional[str], background_tasks: BackgroundTasks, proxy_service: ProxyService, usage_service: UsageService):
    """
    Anthropic Messages API 原生转发模式
    
    直接将请求转发到 Anthropic API，不做格式转换。
    完整支持 Anthropic 所有特性（cache_control、extended thinking 等）。
    
    支持两种认证模式：
    1. Bearer 认证代理（base_url 命中 anthropic_bearer_auth_markers 配置）：使用 Authorization: Bearer 格式，不需要 anthropic-version 头
    2. 官方 Anthropic API 或其他服务：使用 x-api-key 格式 + anthropic-version 头
    """
    logger.info(f"[Anthropic Native] Processing request with native forwarding mode")
    
    # 1. 构建目标 URL
    base_url = config["base_url"].rstrip("/")
    # 确保 URL 以 /messages 结尾
    if not base_url.endswith("/messages"):
        # 移除可能的 /chat/completions 后缀
        if base_url.endswith("/chat/completions"):
            base_url = base_url.rsplit("/chat/completions", 1)[0]
        base_url = base_url + "/messages"
    
    # 2. 判断是否使用 Bearer 认证（基于配置标记，兼容自建 Bearer 代理）
    _settings = get_settings()
    is_bearer_proxy = any(marker in base_url for marker in _settings.anthropic_bearer_auth_markers)

    # 3. 构建请求头（根据服务类型选择认证方式）
    if is_bearer_proxy:
        # Bearer 认证代理：不需要 anthropic-version 头
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        logger.debug(f"[Anthropic Native] Using Bearer auth for proxy")
    else:
        # 官方 Anthropic API：使用 x-api-key 认证
        headers = {
            "x-api-key": config["api_key"],
            "anthropic-version": anthropic_version or "2023-06-01",
            "Content-Type": "application/json"
        }
        logger.debug(f"[Anthropic Native] Using x-api-key auth for Anthropic API")
    
    # 透传 beta 头（所有上游都透传，由上游决定是否支持）
    if anthropic_beta:
        headers["anthropic-beta"] = anthropic_beta
    
    # 3. 覆盖模型（使用路由配置的模型）
    requested_model = body.get("model")
    body["model"] = config["model"]
    logger.info(f"[Anthropic Native] Model mapping: requested={requested_model!r} -> forwarded={config['model']!r}")

    # 4. 判断流式/非流式
    is_stream = body.get("stream", False)
    
    # 5. 获取 HTTP 客户端
    http_client = proxy_service.http_client
    
    if is_stream:
        return await forward_anthropic_native_stream(http_client, base_url, headers, body, config, background_tasks, usage_service)
    else:
        return await forward_anthropic_native_non_stream(http_client, base_url, headers, body, config, background_tasks, usage_service)


async def _forward_with_conversion(request: Request, body: Dict[str, Any], config: Dict[str, Any], background_tasks: BackgroundTasks, proxy_service: ProxyService, usage_service: UsageService):
    """
    Anthropic Messages API 格式转换模式 (v1.x 兼容)
    
    接收 Anthropic Messages 格式请求，转换为 OpenAI 格式后转发到 /chat/completions，
    然后将响应转换回 Anthropic 格式返回。
    """
    logger.info(f"[Messages API] Processing request with format conversion mode")
    
    # 1. 补全 base_url：确保是 /chat/completions 端点
    base_url = config["base_url"].rstrip("/")
    if not base_url.endswith("/chat/completions"):
        # 移除可能存在的 /messages 后缀
        if base_url.endswith("/messages"):
            base_url = base_url.rsplit("/messages", 1)[0]
        config["base_url"] = base_url + "/chat/completions"
    
    # 2. 解析为 MessagesRequest 对象
    messages_request = MessagesRequest(**body)
    
    # 3. 转换为 OpenAI 格式
    openai_request = convert_anthropic_to_openai(messages_request)
    
    # 4. 构建 Provider 请求
    url = config['base_url']
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    provider_request = proxy_service.build_provider_request(config, openai_request)
    
    # 5. 获取实际使用的模型（从配置中）
    actual_model = config.get("model", messages_request.model or "unknown")
    logger.info(f"[Messages API] Model mapping: requested={messages_request.model!r} -> forwarded={actual_model!r}")

    # 6. 转发请求并记录用量
    if messages_request.stream:
        # === 流式响应 ===
        collector = StreamUsageCollector()

        # 先打开上游连接并校验状态码：4xx/5xx 在此抛 ProviderError，由 exception handler 返回 JSON
        upstream_response = await proxy_service.open_upstream_stream(url, headers, provider_request)

        try:
            stream_gen = create_anthropic_stream_from_openai(proxy_service, upstream_response, collector, actual_model)
            background_tasks.add_task(process_stream_usage, proxy_service, usage_service, config, collector, messages_request.model)
            return StreamingResponse(
                stream_gen,
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", "Transfer-Encoding": "chunked"}
            )
        except Exception:
            await upstream_response.aclose()
            raise
    else:
        # === 非流式响应 ===
        try:
            # 转发到 OpenAI 格式端点
            openai_response = await proxy_service.forward_chat_completion(config, openai_request)
            
            # 转换为 Anthropic 格式
            anthropic_response = convert_openai_to_anthropic(openai_response, actual_model)
            
            # DEBUG: 打印输出响应
            logger.debug(f"[Messages API] ========== 输出响应 ==========")
            logger.debug(f"[Messages API] Response:\n{json.dumps(anthropic_response, ensure_ascii=False, indent=2)}")
            
            # 提取用量并异步记录
            usage = proxy_service.extract_usage_from_response(openai_response)
            record_data = proxy_service.build_usage_record_data(config, usage, request_model=messages_request.model, status="success")
            background_tasks.add_task(record_usage_background, usage_service, record_data)
            
            return JSONResponse(content=anthropic_response)
            
        except Exception as e:
            # 记录错误请求
            error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            record_data = proxy_service.build_usage_record_data(config, error_usage, request_model=messages_request.model, status="error", error_message=str(e))
            background_tasks.add_task(record_usage_background, usage_service, record_data)
            raise
