"""
日志中间件

记录请求信息（方法、路径、耗时）和响应状态码
区分控制面和数据面日志
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logger_mgr import get_logger

logger = get_logger("app.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录请求开始时间
        start_time = time.time()

        # 获取请求信息
        method = request.method
        path = request.url.path
        # 优先从 nginx 透传的头部获取真实 IP
        client_ip = (
            request.headers.get("X-Real-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        # 区分控制面和数据面
        plane = "data_plane" if path.startswith("/v1") else "control_plane"

        # 处理请求
        try:
            response = await call_next(request)

            # 计算耗时
            process_time = (time.time() - start_time) * 1000  # 毫秒

            # 记录日志
            logger.info(
                f"[{plane}] {method} {path} - Status: {response.status_code} - Time: {process_time:.2f}ms - IP: {client_ip}",
                extra={
                    "plane": plane,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time, 2),
                    "client_ip": client_ip,
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

            # 添加响应头
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            return response

        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"[{plane}] {method} {path} - Error: {str(e)} - Time: {process_time:.2f}ms - IP: {client_ip}",
                exc_info=True,
                extra={
                    "plane": plane,
                    "method": method,
                    "path": path,
                    "process_time_ms": round(process_time, 2),
                    "client_ip": client_ip,
                    "request_id": getattr(request.state, "request_id", None),
                },
            )
            raise


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # 将request_id存储在request.state中
        request.state.request_id = request_id

        # 处理请求
        response = await call_next(request)

        # 在响应头中返回request_id
        response.headers["X-Request-ID"] = request_id

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头部中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # 添加安全头部
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' "
            "https://api.iconify.design "
            "https://api.simplesvg.com "
            "https://api.unisvg.com; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:"
        )

        return response
