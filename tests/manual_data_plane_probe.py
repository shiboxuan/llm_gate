#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据面接口手工冒烟脚本

不走 pytest，直接执行；用于生产/预发环境快速验证 /v1/* 三个接口的行为：
  - /v1/chat/completions   (OpenAI Chat)
  - /v1/messages           (Anthropic Messages)
  - /v1/responses          (OpenAI Responses)

覆盖三组场景：
  A. Happy path：非流式 + 流式
  B. Tool Token 异常：空 / 非 Bearer 前缀 / Bearer 后跟垃圾 token
  C. 流式客户端主动中断：读几个 chunk 后 close，观察服务端结构化日志

使用方式：
  1) 在下方 "USER HARDCODE" 区填入 TOOL_TOKEN_* 等常量
  2) 确保网关在 BASE_URL 监听
  3) python tests/manual_data_plane_probe.py
"""
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx


# ======================== 配置（从环境变量读取）========================
# 通过环境变量 LLM_GATE_PROBE_TOKEN_* 传入 Tool Token，避免硬编码。
BASE_URL = os.environ.get("LLM_GATE_PROBE_BASE_URL", "http://127.0.0.1:9981")

# 三个 Tool Token，分别对应三条路由；如果路由 api_type 可以混用，填同一个也行
TOOL_TOKEN_OPENAI = os.environ.get("LLM_GATE_PROBE_TOKEN_OPENAI", "")
TOOL_TOKEN_ANTHROPIC = os.environ.get("LLM_GATE_PROBE_TOKEN_ANTHROPIC", "")
TOOL_TOKEN_RESPONSES = os.environ.get("LLM_GATE_PROBE_TOKEN_RESPONSES", "")

# 各接口对应路由下的 model 字段（网关会覆盖成 config 里的 model，但请求体仍需合法）
VALID_MODEL_OPENAI = "gpt-4o-mini"
VALID_MODEL_ANTHROPIC = "claude-3-5-haiku-20241022"
VALID_MODEL_RESPONSES = "gpt-4o-mini"

SAMPLE_PROMPT = "Say hi in five words."

# 请求超时（秒）；流式中断场景使用更短值快速返回
REQUEST_TIMEOUT = 30.0
STREAM_ABORT_MAX_CHUNKS = 2  # 读到第 N 个 chunk 后主动 close
# ================================================================


# ======================== Output helpers ========================

SEPARATOR = "=" * 80
SUBSEP = "-" * 80


def _fmt_headers(h: Dict[str, str]) -> str:
    # 对敏感头做本地打印脱敏；避免把用户硬编码的 token 明文刷到屏幕
    redacted = {}
    for k, v in h.items():
        if k.lower() in ("authorization", "x-api-key") and v:
            redacted[k] = v[:10] + "...***"
        else:
            redacted[k] = v
    return json.dumps(redacted, ensure_ascii=False)


def _fmt_body(obj: Any, limit: int = 1500) -> str:
    if obj is None:
        return "<none>"
    if isinstance(obj, (bytes, bytearray)):
        try:
            s = obj.decode("utf-8", errors="replace")
        except Exception:
            s = repr(obj)
    elif isinstance(obj, str):
        s = obj
    else:
        try:
            s = json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            s = repr(obj)
    if len(s) > limit:
        s = s[:limit] + f"\n... <truncated, total {len(s)} chars>"
    return s


def _print_case_header(idx: int, group: str, name: str, method: str, path: str) -> None:
    print()
    print(SEPARATOR)
    print(f"[{idx:02d}] {group} | {name}")
    print(SEPARATOR)
    print(f"{method} {BASE_URL}{path}")


def _print_request(headers: Dict[str, str], body: Any) -> None:
    print(f"Headers: {_fmt_headers(headers)}")
    print(f"Body:    {_fmt_body(body)}")
    print(SUBSEP)


def _print_response(status: int, headers: Dict[str, str], body: Any) -> None:
    print(f"Status:  {status}")
    print(f"Headers: {_fmt_headers(dict(headers))}")
    print(f"Body:    {_fmt_body(body)}")


# ======================== Case framework ========================

@dataclass
class CaseResult:
    idx: int
    group: str
    name: str
    passed: bool
    note: str = ""


RESULTS: List[CaseResult] = []
CASE_COUNTER = 0


def _next_idx() -> int:
    global CASE_COUNTER
    CASE_COUNTER += 1
    return CASE_COUNTER


def _record(idx: int, group: str, name: str, passed: bool, note: str = "") -> None:
    RESULTS.append(CaseResult(idx=idx, group=group, name=name, passed=passed, note=note))
    verdict = "PASS" if passed else "FAIL"
    marker = "OK " if passed else "!! "
    print(f"Verdict: [{marker}] {verdict}   {note}")


def _run(fn: Callable[[int], Tuple[bool, str]], group: str, name: str) -> None:
    idx = _next_idx()
    try:
        passed, note = fn(idx)
    except Exception as e:
        print(f"\n!!! Case [{idx}] raised an exception:")
        traceback.print_exc()
        _record(idx, group, name, False, f"exception: {type(e).__name__}: {e}")
        return
    _record(idx, group, name, passed, note)


# ======================== HTTP helpers ========================

def _bearer(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _post_json(path: str, headers: Dict[str, str], body: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Tuple[int, Dict[str, str], Any]:
    url = f"{BASE_URL}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
    try:
        parsed: Any = resp.json()
    except Exception:
        parsed = resp.text
    return resp.status_code, dict(resp.headers), parsed


def _stream_full(path: str, headers: Dict[str, str], body: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Tuple[int, Dict[str, str], List[str]]:
    """读完整流式响应，返回所有 SSE text 片段（按 TCP chunk 切分）。"""
    url = f"{BASE_URL}{path}"
    chunks: List[str] = []
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", url, headers=headers, json=body) as resp:
            status = resp.status_code
            hdrs = dict(resp.headers)
            for raw in resp.iter_bytes():
                if raw:
                    chunks.append(raw.decode("utf-8", errors="replace"))
    return status, hdrs, chunks


def _stream_abort(path: str, headers: Dict[str, str], body: Dict[str, Any], max_chunks: int = STREAM_ABORT_MAX_CHUNKS) -> Tuple[int, Dict[str, str], List[str], str]:
    """模拟客户端在读到前几个 chunk 后主动断开。"""
    url = f"{BASE_URL}{path}"
    chunks: List[str] = []
    note = ""
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            with client.stream("POST", url, headers=headers, json=body) as resp:
                status = resp.status_code
                hdrs = dict(resp.headers)
                if status >= 400:
                    # 没进流式成功路径，直接读完 body
                    body_bytes = b""
                    for b in resp.iter_bytes():
                        body_bytes += b
                    chunks.append(body_bytes.decode("utf-8", errors="replace"))
                    return status, hdrs, chunks, "upstream-4xx-before-stream"
                count = 0
                for raw in resp.iter_bytes():
                    if raw:
                        chunks.append(raw.decode("utf-8", errors="replace"))
                        count += 1
                        if count >= max_chunks:
                            note = f"client aborted after {count} chunks"
                            # 直接 break 让 context manager 关闭连接
                            break
                return status, hdrs, chunks, note
    except httpx.RemoteProtocolError as e:
        return -1, {}, chunks, f"RemoteProtocolError on read: {e}"


# ======================== Payload builders ========================

def _openai_chat_body(model: str, stream: bool) -> Dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": SAMPLE_PROMPT}],
        "stream": stream,
        "max_tokens": 64,
    }
    return body


def _anthropic_body(model: str, stream: bool) -> Dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": 64,
        "stream": stream,
        "messages": [{"role": "user", "content": SAMPLE_PROMPT}],
    }
    return body


def _responses_body(model: str, stream: bool) -> Dict[str, Any]:
    body = {
        "model": model,
        "input": SAMPLE_PROMPT,
        "stream": stream,
    }
    return body


# ======================== Scenario implementations ========================

# ---------- Group A: Happy path ----------

def case_chat_happy_non_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "chat.completions non-stream", "POST", "/v1/chat/completions")
    headers = _bearer(TOOL_TOKEN_OPENAI)
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, resp)
    ok = status == 200 and isinstance(resp, dict) and "choices" in resp
    return ok, "status=200 & has choices" if ok else f"status={status}"


def case_chat_happy_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "chat.completions stream", "POST", "/v1/chat/completions")
    headers = _bearer(TOOL_TOKEN_OPENAI)
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks = _stream_full("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    ok = status == 200 and any("data:" in c for c in chunks) and any("[DONE]" in c for c in chunks)
    return ok, f"chunks={len(chunks)}"


def case_messages_happy_non_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "messages non-stream", "POST", "/v1/messages")
    headers = _bearer(TOOL_TOKEN_ANTHROPIC)
    body = _anthropic_body(VALID_MODEL_ANTHROPIC, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/messages", headers, body)
    _print_response(status, hdrs, resp)
    ok = status == 200 and isinstance(resp, dict) and ("content" in resp or "choices" in resp)
    return ok, "status=200" if ok else f"status={status}"


def case_messages_happy_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "messages stream", "POST", "/v1/messages")
    headers = _bearer(TOOL_TOKEN_ANTHROPIC)
    body = _anthropic_body(VALID_MODEL_ANTHROPIC, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks = _stream_full("/v1/messages", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    # Anthropic 流式：事件里会有 event: message_start / message_stop
    joined = "".join(chunks)
    ok = status == 200 and ("message_start" in joined or "data:" in joined)
    return ok, f"chunks={len(chunks)}"


def case_responses_happy_non_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "responses non-stream", "POST", "/v1/responses")
    headers = _bearer(TOOL_TOKEN_RESPONSES)
    body = _responses_body(VALID_MODEL_RESPONSES, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/responses", headers, body)
    _print_response(status, hdrs, resp)
    ok = status == 200 and isinstance(resp, dict)
    return ok, "status=200" if ok else f"status={status}"


def case_responses_happy_stream(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "A.Happy", "responses stream", "POST", "/v1/responses")
    headers = _bearer(TOOL_TOKEN_RESPONSES)
    body = _responses_body(VALID_MODEL_RESPONSES, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks = _stream_full("/v1/responses", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    ok = status == 200 and any("data:" in c for c in chunks)
    return ok, f"chunks={len(chunks)}"


# ---------- Group B: Tool Token 异常 ----------

def case_token_empty(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "B.Token", "empty Authorization", "POST", "/v1/chat/completions")
    headers = {"Authorization": "", "Content-Type": "application/json"}
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, resp)
    # FastAPI 对缺失的 required Header 会返回 422；空字符串则进入 handler 后抛 TOKEN_INVALID
    ok = status in (401, 422)
    return ok, f"status={status}"


def case_token_non_bearer(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "B.Token", "non-Bearer prefix", "POST", "/v1/chat/completions")
    headers = {"Authorization": "Basic dXNlcjpwYXNz", "Content-Type": "application/json"}
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, resp)
    # 期望 TOKEN_INVALID (10005 → 401)
    ok = status == 401 and isinstance(resp, dict) and resp.get("code") == 10005
    return ok, f"status={status}, code={resp.get('code') if isinstance(resp, dict) else '?'}"


def case_token_garbage(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "B.Token", "Bearer <garbage>", "POST", "/v1/chat/completions")
    headers = _bearer("sk-garbage-nope-nope-nope")
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=False)
    _print_request(headers, body)
    status, hdrs, resp = _post_json("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, resp)
    # 期望 TOOL_TOKEN_INVALID (12003 → 401)
    ok = status == 401 and isinstance(resp, dict) and resp.get("code") == 12003
    return ok, f"status={status}, code={resp.get('code') if isinstance(resp, dict) else '?'}"


# ---------- Group C: 流式客户端中断 ----------

def case_chat_stream_abort(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "C.Abort", "chat stream client-abort", "POST", "/v1/chat/completions")
    headers = _bearer(TOOL_TOKEN_OPENAI)
    body = _openai_chat_body(VALID_MODEL_OPENAI, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks, note = _stream_abort("/v1/chat/completions", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    # 成功判定：拿到 200 且读到了至少 1 个 chunk；客户端主动 close 不应崩溃
    ok = status == 200 and len(chunks) >= 1
    return ok, f"chunks={len(chunks)}, {note}; 请回 server log 确认 generator 结束日志"


def case_messages_stream_abort(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "C.Abort", "messages stream client-abort", "POST", "/v1/messages")
    headers = _bearer(TOOL_TOKEN_ANTHROPIC)
    body = _anthropic_body(VALID_MODEL_ANTHROPIC, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks, note = _stream_abort("/v1/messages", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    ok = status == 200 and len(chunks) >= 1
    return ok, f"chunks={len(chunks)}, {note}; 请回 server log 确认 generator 结束日志"


def case_responses_stream_abort(idx: int) -> Tuple[bool, str]:
    _print_case_header(idx, "C.Abort", "responses stream client-abort", "POST", "/v1/responses")
    headers = _bearer(TOOL_TOKEN_RESPONSES)
    body = _responses_body(VALID_MODEL_RESPONSES, stream=True)
    _print_request(headers, body)
    status, hdrs, chunks, note = _stream_abort("/v1/responses", headers, body)
    _print_response(status, hdrs, "".join(chunks))
    ok = status == 200 and len(chunks) >= 1
    return ok, f"chunks={len(chunks)}, {note}; 请回 server log 确认 generator 结束日志"


# ======================== Main ========================

CASES: List[Tuple[str, str, Callable[[int], Tuple[bool, str]]]] = [
    ("A.Happy", "chat non-stream", case_chat_happy_non_stream),
    ("A.Happy", "chat stream", case_chat_happy_stream),
    ("A.Happy", "messages non-stream", case_messages_happy_non_stream),
    ("A.Happy", "messages stream", case_messages_happy_stream),
    ("A.Happy", "responses non-stream", case_responses_happy_non_stream),
    ("A.Happy", "responses stream", case_responses_happy_stream),
    ("B.Token", "empty", case_token_empty),
    ("B.Token", "non-Bearer", case_token_non_bearer),
    ("B.Token", "garbage", case_token_garbage),
    ("C.Abort", "chat stream abort", case_chat_stream_abort),
    ("C.Abort", "messages stream abort", case_messages_stream_abort),
    ("C.Abort", "responses stream abort", case_responses_stream_abort),
]


def _check_constants() -> Optional[str]:
    missing = []
    for name in ("TOOL_TOKEN_OPENAI", "TOOL_TOKEN_ANTHROPIC", "TOOL_TOKEN_RESPONSES"):
        val = globals().get(name, "")
        if not val or "REPLACE-ME" in val:
            missing.append(name)
    if missing:
        return "以下常量尚未填写: " + ", ".join(missing)
    return None


def main() -> int:
    print()
    print(SEPARATOR)
    print(" 数据面接口手工冒烟脚本")
    print(f" BASE_URL = {BASE_URL}")
    print(SEPARATOR)

    warn = _check_constants()
    if warn:
        print(f"⚠️  {warn}")
        print("   B / C / D 场景仍会跑（想验证 token 异常的场景），但 A 组会失败。\n")

    for group, name, fn in CASES:
        _run(fn, group, name)

    # 汇总
    print()
    print(SEPARATOR)
    print(" 汇总")
    print(SEPARATOR)
    width = max((len(r.name) for r in RESULTS), default=10)
    for r in RESULTS:
        mark = "PASS" if r.passed else "FAIL"
        print(f"  [{r.idx:02d}] {r.group:<14} {r.name:<{width}}  {mark}   {r.note}")
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r.passed)
    print(SUBSEP)
    print(f"  Total: {total}, Passed: {passed}, Failed: {total - passed}")
    print(SEPARATOR)
    print()
    print("注意：")
    print("  - C 组客户端主动 close 不会触发服务端 yield 兜底事件（那是给上游中断的），")
    print("    主要验证服务端不会因客户端断开报未捕获异常；看 server 日志里有无 stacktrace 即可。")
    print()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
