#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Desc    : SSE 流式响应解析工具（中立层）

"""
SSE 解析工具（中立层）

data_plane 在流式 generator 内需要解析 chunk 以提取 usage；service 层在转发流式响应时
也需要同一套逻辑。将该工具放到 app.core 中立层，可避免 app.services 反向依赖
app.api.data_plane 造成的分层反转与潜在循环导入。

容错设计（针对中转网关的非标准 SSE 输出）：
1. 行分隔符归一化：SSE 规范允许 \r\n / \n / \r 三种行分隔，统一归一为 \n 后再按
   空行切分，兼容上游使用 CRLF 行分隔导致 split("\n\n") 失效的场景
   （JSON data 值中不允许出现裸 CR/LF，必须转义，归一化不会破坏数据）。
2. 事件粘连挽救：上游事件间缺少空行分隔（\n\n）时，多个事件会粘连进同一个
   part 导致 json.loads 失败。此时用 raw_decode 扫描式提取所有完整 JSON 对象，
   挽救被丢弃的事件（仅对确认不会再拼接的 part 执行；尾部不完整 part 仍走
   buffer 暂存逻辑，避免丢失截断尾巴）。
3. 警告降噪：同一请求（buffer 生命周期内）解析失败 WARNING 至多打印一条，
   其余降级为 DEBUG，避免生产日志刷屏。
"""
import codecs
import json
from typing import Any, Dict, List

from app.logger_mgr import get_logger

logger = get_logger("app.core.sse_parser")

_JSON_DECODER = json.JSONDecoder()


def _salvage_json_objects(text: str) -> List[Dict[str, Any]]:
    """从粘连或非标准的 SSE 片段中扫描式提取所有完整 JSON 对象。

    依次定位 '{' 并用 raw_decode 增量解析：成功一个收集一个并跳到该对象末尾
    继续扫描；失败（如被截断的半个 JSON）则跳过该 '{' 继续向后找。
    """
    objects: List[Dict[str, Any]] = []
    idx = 0
    text_len = len(text)
    while idx < text_len:
        brace = text.find("{", idx)
        if brace == -1:
            break
        try:
            obj, end = _JSON_DECODER.raw_decode(text, brace)
            if isinstance(obj, dict):
                objects.append(obj)
            idx = end
        except json.JSONDecodeError:
            idx = brace + 1
    return objects


def _report_parse_failure(buffer: List[Any], tag: str, part: str) -> None:
    """解析失败日志：同一请求至多一条 WARNING，其余降级为 DEBUG（降噪）。"""
    if not buffer[2]:
        buffer[2] = True
        logger.warning(f"SSE chunk JSON decode failed {tag}, dropping: {part[:200]}")
    else:
        logger.debug(f"SSE chunk JSON decode failed {tag} (suppressed), dropping: {part[:200]}")


def parse_sse_chunks_with_buffer(chunk_bytes: bytes, buffer: List[Any], is_final: bool = False) -> List[Dict[str, Any]]:
    """
    解析 SSE 格式的 chunk，支持多条消息和跨 chunk 的不完整消息

    使用缓冲区来处理被 TCP 分片拆分的 SSE 消息。
    缓冲区是请求级别的局部变量，每个请求独立，不会混淆不同用户的数据。

    buffer 结构：
        buffer[0]: str，已解码但未成消息的字符残留
        buffer[1]: IncrementalDecoder，字节级增量解码器（处理 UTF-8 多字节字符
                  被 TCP 分片切断的场景；如缺失会自动创建以向后兼容旧调用）
        buffer[2]: bool，本请求是否已打印过解析失败 WARNING（降噪用；
                  如缺失会自动补齐为 False，向后兼容旧调用）

    Args:
        chunk_bytes: 原始 chunk 字节
        buffer: 用于存储不完整消息的缓冲区列表
               推荐传入 ["", codecs.getincrementaldecoder("utf-8")()] 初始化
               为向后兼容，也可传入 [""]，函数会原地补齐 decoder 与警告标志
        is_final: 是否为流的最后一次调用，True 时会 flush decoder 内部残留字节

    Returns:
        解析成功的字典列表
    """
    results: List[Dict[str, Any]] = []
    if len(buffer) < 2:
        buffer.append(codecs.getincrementaldecoder("utf-8")())
    if len(buffer) < 3:
        buffer.append(False)
    decoder = buffer[1]

    try:
        chunk_str = decoder.decode(chunk_bytes, final=is_final)
    except UnicodeDecodeError as e:
        logger.warning(f"SSE chunk decode error: {e}")
        return results

    # 行分隔符归一化：\r\n 与孤立 \r 统一为 \n（见模块 docstring 容错设计第 1 条）
    chunk_str = chunk_str.replace("\r\n", "\n").replace("\r", "\n")

    if not chunk_str and not buffer[0]:
        return results

    if buffer[0]:
        chunk_str = buffer[0] + chunk_str
        buffer[0] = ""

    # 直接查原串是否以 \n\n 结尾，用于区分"最后一段是否暂存"。
    chunk_ends_with_delimiter = chunk_str.endswith("\n\n")

    parts = chunk_str.split("\n\n")

    for i, part in enumerate(parts):
        raw_part = part  # 未 strip 的原始片段：尾部空白可能属于 JSON 字符串值内部
        part = part.strip()
        if not part or part.startswith(":"):
            continue

        is_last_part = (i == len(parts) - 1)

        if is_last_part and not chunk_ends_with_delimiter and not is_final:
            # 暂存原始片段（保留尾部空白）：strip 会吃掉如 "content": "hi 末尾的空格
            # 等字符串值内部字符，导致下个 chunk 拼接后内容损坏（如 "hi😀!"）。
            buffer[0] = raw_part
            continue

        if part.startswith("data:"):
            data_str = part[5:].strip()
            if data_str == "[DONE]":
                continue
            try:
                results.append(json.loads(data_str))
            except json.JSONDecodeError:
                if is_last_part and not is_final:
                    # 尾部不完整段：可能被 TCP 截断，写回 buffer 等待下个 chunk 拼接。
                    # 不做 salvage，避免提取了前半段完整对象却丢掉截断尾巴。
                    buffer[0] = raw_part
                else:
                    # 完整分隔的 part 解析失败：多为多事件粘连，扫描式挽救
                    salvaged = _salvage_json_objects(data_str)
                    if salvaged:
                        results.extend(salvaged)
                        logger.debug(f"SSE salvage: recovered {len(salvaged)} events from non-standard SSE part")
                    else:
                        _report_parse_failure(buffer, "", part)
        else:
            data_idx = part.find("data:")
            if data_idx != -1:
                data_str = part[data_idx + 5:].strip()
                if data_str and data_str != "[DONE]":
                    try:
                        results.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        if is_last_part and not is_final:
                            buffer[0] = raw_part[data_idx:]
                        else:
                            salvaged = _salvage_json_objects(data_str)
                            if salvaged:
                                results.extend(salvaged)
                                logger.debug(f"SSE salvage: recovered {len(salvaged)} events from non-standard SSE part")
                            else:
                                _report_parse_failure(buffer, "(mid)", part)

    return results
