#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author  : LLM Gate
# @Date    : 2026/3/9
# @Desc    : 数据面 API 公共工具类

"""
数据面 API 公共工具模块

提供 chat.py 和 messages.py 共用的工具类和函数
"""
import json
from typing import Dict, Any, List, Optional

from app.core.sse_parser import parse_sse_chunks_with_buffer
from app.services.usage_service import UsageService
from app.logger_mgr import get_logger

logger = get_logger("app.api.data_plane._utils")

# 从中立层 re-export，保持旧调用点 from app.api.data_plane._utils import parse_sse_chunks_with_buffer 兼容
__all__ = [
    "StreamUsageCollector",
    "record_usage_background",
    "build_anthropic_stream_error_events",
    "build_openai_stream_error_events",
    "parse_sse_chunks_with_buffer",
    "parse_upstream_error_body",
]


class StreamUsageCollector:
    """
    流式响应用量收集器
    
    用于在流式响应过程中收集 chunk 数据，
    并在流结束后提取用量信息。
    
    扩展功能：
    - full_response_text: 收集完整响应文本用于调试（messages.py 使用）
    - full_thinking_text: 收集完整 thinking 文本用于调试（messages.py 使用）
    """
    
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.is_complete: bool = False
        self.error: Optional[str] = None
        self.full_response_text: str = ""  # 收集完整响应文本用于调试
        self.full_thinking_text: str = ""  # 收集完整 thinking 文本用于调试
    
    def add_chunk(self, parsed_chunk: Optional[Dict[str, Any]]) -> None:
        """添加解析后的 chunk"""
        if parsed_chunk:
            self.chunks.append(parsed_chunk)
    
    def mark_complete(self) -> None:
        """标记流已完成"""
        self.is_complete = True
    
    def mark_error(self, error_msg: str) -> None:
        """标记流发生错误"""
        self.error = error_msg
        self.is_complete = True


async def record_usage_background(usage_service: UsageService, record_data: Dict[str, Any]) -> None:
    """
    后台任务：记录用量

    Args:
        usage_service: 用量统计服务
        record_data: 用量记录数据
    """
    try:
        await usage_service.record_usage(record_data)
        logger.debug(f"Usage recorded: tool_id={record_data.get('tool_id')}, tokens={record_data.get('total_tokens')}")
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")


def build_anthropic_stream_error_events(error_type: str, message: str) -> bytes:
    """
    构造 Anthropic SSE 断流兜底事件：error + message_stop。

    当上游在流式传输中途断开连接，此 helper 生成协议级错误事件，
    让客户端能识别错误原因并正常关闭流，而不是看到裸 TCP 断连。
    """
    error_payload = {"type": "error", "error": {"type": error_type, "message": message}}
    error_event = f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
    stop_event = "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
    payload = (error_event + stop_event).encode("utf-8")
    return payload


def build_openai_stream_error_events(error_type: str, message: str) -> bytes:
    """
    构造 OpenAI SSE 断流兜底事件：error chunk + [DONE]。

    当上游在流式传输中途断开连接，此 helper 生成协议级错误事件，
    让客户端能识别错误原因并正常关闭流，而不是看到裸 TCP 断连。
    """
    error_payload = {"error": {"type": error_type, "message": message}}
    error_chunk = f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
    done_chunk = "data: [DONE]\n\n"
    payload = (error_chunk + done_chunk).encode("utf-8")
    return payload


def parse_upstream_error_body(error_text: str) -> Dict[str, Any]:
    """将上游错误响应文本归一化为 {"error": {...}} 形式的 dict

    覆盖四种形状：
    - 标准 dict（可能 error.message 是嵌套 JSON 字符串，合并进 error）
    - JSON 字符串字面量（双层 encode，再解一次）
    - 非法 JSON（直接包装为 message）
    - 其他合法 JSON 类型（list/number/null，包装为 message）
    """
    try:
        parsed = json.loads(error_text)
    except (ValueError, TypeError):
        result = {"error": {"type": "unknown", "message": error_text}}
        return result

    if isinstance(parsed, str):
        try:
            reparsed = json.loads(parsed)
        except (ValueError, TypeError):
            reparsed = None
        if isinstance(reparsed, dict):
            parsed = reparsed
        else:
            result = {"error": {"type": "unknown", "message": parsed}}
            return result

    if not isinstance(parsed, dict):
        result = {"error": {"type": "unknown", "message": error_text}}
        return result

    error_entry = parsed.get("error")
    if isinstance(error_entry, dict):
        inner_message = error_entry.get("message")
        if isinstance(inner_message, str):
            stripped = inner_message.lstrip()
            if stripped.startswith("{"):
                try:
                    inner_parsed = json.loads(inner_message)
                except (ValueError, TypeError):
                    inner_parsed = None
                if isinstance(inner_parsed, dict):
                    inner_error = inner_parsed.get("error")
                    if isinstance(inner_error, dict):
                        parsed["error"] = inner_error

    return parsed
