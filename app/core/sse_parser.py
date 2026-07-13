#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Desc    : SSE 流式响应解析工具（中立层）

"""
SSE 解析工具（中立层）

data_plane 在流式 generator 内需要解析 chunk 以提取 usage；service 层在转发流式响应时
也需要同一套逻辑。将该工具放到 app.core 中立层，可避免 app.services 反向依赖
app.api.data_plane 造成的分层反转与潜在循环导入。
"""
import codecs
import json
from typing import Any, Dict, List

from app.logger_mgr import get_logger

logger = get_logger("app.core.sse_parser")


def parse_sse_chunks_with_buffer(chunk_bytes: bytes, buffer: List[Any], is_final: bool = False) -> List[Dict[str, Any]]:
    """
    解析 SSE 格式的 chunk，支持多条消息和跨 chunk 的不完整消息

    使用缓冲区来处理被 TCP 分片拆分的 SSE 消息。
    缓冲区是请求级别的局部变量，每个请求独立，不会混淆不同用户的数据。

    buffer 结构：
        buffer[0]: str，已解码但未成消息的字符残留
        buffer[1]: IncrementalDecoder，字节级增量解码器（处理 UTF-8 多字节字符
                  被 TCP 分片切断的场景；如缺失会自动创建以向后兼容旧调用）

    Args:
        chunk_bytes: 原始 chunk 字节
        buffer: 用于存储不完整消息的缓冲区列表
               推荐传入 ["", codecs.getincrementaldecoder("utf-8")()] 初始化
               为向后兼容，也可传入 [""]，函数会原地补齐 decoder
        is_final: 是否为流的最后一次调用，True 时会 flush decoder 内部残留字节

    Returns:
        解析成功的字典列表
    """
    results: List[Dict[str, Any]] = []
    if len(buffer) < 2:
        buffer.append(codecs.getincrementaldecoder("utf-8")())
    decoder = buffer[1]

    try:
        chunk_str = decoder.decode(chunk_bytes, final=is_final)
    except UnicodeDecodeError as e:
        logger.warning(f"SSE chunk decode error: {e}")
        return results

    if not chunk_str and not buffer[0]:
        return results

    if buffer[0]:
        chunk_str = buffer[0] + chunk_str
        buffer[0] = ""

    # 旧实现用 chunk_str.rstrip().endswith("\n") 检测结尾分隔符，但 rstrip 已剥掉尾部 \n，
    # 使 endswith("\n") 永远为 False，导致"最后一段是否暂存"判断退化为"只要不是 final 就暂存"。
    # 这里直接查原串是否以 \n\n 结尾。
    chunk_ends_with_delimiter = chunk_str.endswith("\n\n")

    parts = chunk_str.split("\n\n")

    for i, part in enumerate(parts):
        part = part.strip()
        if not part or part.startswith(":"):
            continue

        is_last_part = (i == len(parts) - 1)

        if is_last_part and not chunk_ends_with_delimiter and not is_final:
            buffer[0] = part
            continue

        if part.startswith("data:"):
            data_str = part[5:].strip()
            if data_str == "[DONE]":
                continue
            try:
                parsed = json.loads(data_str)
                results.append(parsed)
            except json.JSONDecodeError:
                # 只有真正的"尾部不完整段"才写回 buffer；非 last-part 已被 \n\n 完整分隔
                # 仍失败说明这段损坏，写回只会累积脏 buffer 污染后续解析。
                if is_last_part and not is_final:
                    buffer[0] = part
                else:
                    logger.warning(f"SSE chunk JSON decode failed, dropping: {part[:200]}")
        else:
            data_idx = part.find("data:")
            if data_idx != -1:
                data_str = part[data_idx + 5:].strip()
                if data_str and data_str != "[DONE]":
                    try:
                        parsed = json.loads(data_str)
                        results.append(parsed)
                    except json.JSONDecodeError:
                        if is_last_part and not is_final:
                            buffer[0] = part[data_idx:]
                        else:
                            logger.warning(f"SSE chunk JSON decode failed (mid), dropping: {part[:200]}")

    return results
