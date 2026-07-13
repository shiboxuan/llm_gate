#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2026/2/25
# @Desc    : 统一业务异常模块

from typing import Any, Optional, Dict

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.error_codes import ErrorCode, ERROR_MESSAGES, get_http_status
from app.logger_mgr import get_logger

logger = get_logger("app.core.exceptions")

"""
统一业务异常模块

- APIException: 统一业务异常类
- ProviderError: Provider 上游错误异常类
- api_exception_handler: 全局异常处理器
- generic_exception_handler: 未捕获异常处理器

设计文档: docs/base/error_code_system.md
"""


class APIException(Exception):
    """统一业务异常类

    使用方式:
        raise APIException(
            code=ErrorCode.TOOL_NOT_FOUND,
            data={"tool_id": 123}
        )

    Attributes:
        code: 业务错误码 (ErrorCode 枚举值)
        message: 错误消息
        data: 附加错误详情
        http_status: 对应的 HTTP 状态码
    """

    def __init__(self, code: ErrorCode, message: str = None, data: Any = None, http_status: int = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.data = data
        # 优先使用传入的 http_status，否则从 HTTP_STATUS_MAP 查询
        self.http_status = http_status or get_http_status(code)
        super().__init__(self.message)


class ProviderError(APIException):
    """Provider 上游错误异常类
    
    当 Provider（上游 LLM 服务）返回错误时抛出此异常。
    携带完整的上游错误信息，便于问题诊断。
    
    使用方式:
        raise ProviderError(
            upstream_status=400,
            upstream_response='{"error": {"message": "Invalid model"}}',
            upstream_url="https://api.openai.com/v1/chat/completions",
            request_context={"model": "gpt-4", "messages_count": 5}
        )
    
    Attributes:
        upstream_status: 上游 HTTP 状态码
        upstream_response: 上游响应体（字符串，限制长度）
        upstream_url: 上游请求 URL
        request_context: 请求上下文（模型、消息数等）
    """
    
    # 上游状态码到 ErrorCode 的映射
    STATUS_CODE_MAP = {
        400: ErrorCode.PROVIDER_BAD_REQUEST,
        401: ErrorCode.PROVIDER_AUTH_ERROR,
        403: ErrorCode.PROVIDER_AUTH_ERROR,
        404: ErrorCode.PROVIDER_NOT_FOUND,
        429: ErrorCode.PROVIDER_RATE_LIMIT,
    }
    
    def __init__(
        self,
        upstream_status: int,
        upstream_response: str,
        upstream_url: str,
        request_context: Optional[Dict[str, Any]] = None,
        message: str = None
    ):
        self.upstream_status = upstream_status
        self.upstream_response = upstream_response[:2000] if upstream_response else ""  # 限制长度
        self.upstream_url = upstream_url
        self.request_context = request_context or {}
        
        # 根据上游状态码选择错误码
        if upstream_status in self.STATUS_CODE_MAP:
            code = self.STATUS_CODE_MAP[upstream_status]
        elif upstream_status >= 500:
            code = ErrorCode.PROVIDER_SERVER_ERROR
        else:
            code = ErrorCode.PROVIDER_ERROR
        
        # 构建详细错误消息
        if not message:
            message = f"Provider 返回 {upstream_status} 错误"
        
        # 构建错误数据
        data = {
            "upstream_status": upstream_status,
            "upstream_url": upstream_url,
            "upstream_response": self._parse_upstream_error(upstream_response),
            "request_context": request_context
        }
        
        super().__init__(code=code, message=message, data=data)
    
    def _parse_upstream_error(self, response: str) -> Any:
        """尝试解析上游错误响应为 JSON，失败则返回原字符串"""
        if not response:
            return None
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return response[:500]  # 返回截断的字符串
    
    def format_log_message(self, request_id: str = "unknown") -> str:
        """格式化日志消息，便于问题诊断
        
        Returns:
            格式化的多行日志字符串
        """
        lines = [
            f"[proxy_error] Provider 返回错误",
            f"├── request_id: {request_id}",
            f"├── upstream_url: {self.upstream_url}",
            f"├── upstream_status: {self.upstream_status}",
            f"├── upstream_response: {self.upstream_response[:500]}",
        ]
        
        if self.request_context:
            ctx = self.request_context
            if "model" in ctx:
                lines.append(f"├── request_model: {ctx['model']}")
            if "messages_count" in ctx:
                lines.append(f"├── request_messages_count: {ctx['messages_count']}")
            if "first_user_message" in ctx:
                lines.append(f"├── request_first_user_message: {ctx['first_user_message'][:100]}...")
        
        return "\n".join(lines)


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """全局异常处理器，注册到 FastAPI app

    注册方式:
        app.add_exception_handler(APIException, api_exception_handler)

    响应格式:
        {"code": 12001, "message": "工具不存在", "data": {"tool_id": 123}}
    """
    # 优先从 nginx 透传的头部获取真实 IP
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 特殊处理 ProviderError，使用增强的日志格式
    if isinstance(exc, ProviderError):
        log_message = exc.format_log_message(request_id)
        logger.error(
            f"{log_message}\n"
            f"├── endpoint: {request.method} {request.url.path}\n"
            f"└── client_ip: {client_ip}"
        )
    else:
        # 普通 APIException 的日志
        logger.warning(
            f"[APIException] {request.method} {request.url.path}\n"
            f"├── request_id: {request_id}\n"
            f"├── code: {exc.code}\n"
            f"├── message: {exc.message}\n"
            f"├── http_status: {exc.http_status}\n"
            f"└── client_ip: {client_ip}"
        )
    
    content = {"code": exc.code, "message": exc.message, "data": exc.data}
    return JSONResponse(status_code=exc.http_status, content=content)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的异常

    针对不同类型的异常提供增强的错误日志：
    - httpx.HTTPStatusError: 记录上游响应详情
    - httpx.TimeoutException: 记录超时信息
    - 其他异常: 记录基本错误信息

    注册方式:
        app.add_exception_handler(Exception, generic_exception_handler)

    响应格式:
        {"code": 10008, "message": "服务器内部错误", "data": null}
    """
    # 优先从 nginx 透传的头部获取真实 IP
    client_ip = (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 针对 httpx.HTTPStatusError 特殊处理（上游服务返回错误）
    if isinstance(exc, httpx.HTTPStatusError):
        # 获取上游响应体
        try:
            upstream_response = exc.response.text[:1000]
        except Exception:
            upstream_response = "<无法读取响应体>"
        
        logger.error(
            f"[upstream_error] Provider 请求失败\n"
            f"├── request_id: {request_id}\n"
            f"├── endpoint: {request.method} {request.url.path}\n"
            f"├── upstream_url: {exc.request.url}\n"
            f"├── upstream_status: {exc.response.status_code}\n"
            f"├── upstream_response: {upstream_response}\n"
            f"└── client_ip: {client_ip}"
        )
        
        # 返回更有意义的错误信息
        error_code = ProviderError.STATUS_CODE_MAP.get(
            exc.response.status_code,
            ErrorCode.PROVIDER_SERVER_ERROR if exc.response.status_code >= 500 else ErrorCode.PROVIDER_ERROR
        )
        content = {
            "code": error_code,
            "message": f"Provider 返回 {exc.response.status_code} 错误",
            "data": {
                "upstream_status": exc.response.status_code,
                "upstream_url": str(exc.request.url),
                "upstream_response": upstream_response
            }
        }
        return JSONResponse(status_code=get_http_status(error_code), content=content)
    
    # 针对 httpx.TimeoutException 特殊处理
    if isinstance(exc, httpx.TimeoutException):
        logger.error(
            f"[upstream_timeout] Provider 请求超时\n"
            f"├── request_id: {request_id}\n"
            f"├── endpoint: {request.method} {request.url.path}\n"
            f"└── client_ip: {client_ip}"
        )
        content = {
            "code": ErrorCode.PROXY_TIMEOUT,
            "message": "代理请求超时",
            "data": None
        }
        return JSONResponse(status_code=504, content=content)
    
    # 针对 httpx.ConnectError 特殊处理
    if isinstance(exc, httpx.ConnectError):
        logger.error(
            f"[upstream_connect_error] 无法连接到 Provider\n"
            f"├── request_id: {request_id}\n"
            f"├── endpoint: {request.method} {request.url.path}\n"
            f"├── error: {str(exc)}\n"
            f"└── client_ip: {client_ip}"
        )
        content = {
            "code": ErrorCode.PROXY_REQUEST_FAILED,
            "message": "无法连接到 Provider",
            "data": {"error": str(exc)}
        }
        return JSONResponse(status_code=502, content=content)
    
    # 其他未处理的异常
    logger.error(
        f"[unhandled_exception] 未处理的异常\n"
        f"├── request_id: {request_id}\n"
        f"├── endpoint: {request.method} {request.url.path}\n"
        f"├── exception_type: {type(exc).__name__}\n"
        f"├── exception_message: {str(exc)[:500]}\n"
        f"└── client_ip: {client_ip}",
        exc_info=True  # 只对未知异常打印完整堆栈
    )
    
    content = {"code": ErrorCode.INTERNAL_ERROR, "message": "服务器内部错误", "data": None}
    return JSONResponse(status_code=500, content=content)
