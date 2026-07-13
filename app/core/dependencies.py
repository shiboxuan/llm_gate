"""
FastAPI 依赖注入模块

提供服务实例、HTTP 客户端、数据库会话等依赖的工厂函数。
Service 类通过构造函数接收 AsyncSession，由 get_db 依赖注入。
"""
from typing import Optional

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import APIException
from app.core.security import verify_token
from app.db.redis import redis_manager
from app.db.session import get_db
from app.services.cache_service import CacheService
from app.services.connection_test_service import ConnectionTestService
from app.services.provider_key_service import ProviderKeyService
from app.services.proxy_service import ProxyService
from app.services.route_service import RouteService
from app.services.tool_service import ToolService
from app.services.usage_service import UsageCacheService, UsageService
from app.services.user_service import UserService


# ==================== HTTP 客户端管理 ====================

# 全局 HTTP 客户端（应用启动时初始化）
_http_client: Optional[httpx.AsyncClient] = None


async def init_http_client() -> None:
    """初始化全局 HTTP 客户端

    使用流式超时配置作为默认值（因为流式请求更常用）
    具体请求可以通过 get_stream_timeout() 或 get_non_stream_timeout() 覆盖
    """
    global _http_client
    settings = get_settings()
    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.proxy_timeout_connect,
            read=settings.proxy_timeout_read_stream,
            write=settings.proxy_timeout_write,
            pool=settings.proxy_timeout_pool
        )
    )


async def close_http_client() -> None:
    """关闭全局 HTTP 客户端"""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    """获取全局 HTTP 客户端

    Raises:
        RuntimeError: 客户端未初始化时抛出
    """
    if not _http_client:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


# ==================== 服务依赖 ====================

def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """获取用户服务依赖"""
    service = UserService(session)
    return service


def get_tool_service(session: AsyncSession = Depends(get_db)) -> ToolService:
    """获取工具服务依赖"""
    service = ToolService(session)
    return service


def get_route_service(session: AsyncSession = Depends(get_db)) -> RouteService:
    """获取路由服务依赖"""
    service = RouteService(session)
    return service


def get_provider_key_service(session: AsyncSession = Depends(get_db)) -> ProviderKeyService:
    """获取 Provider Key 服务依赖"""
    service = ProviderKeyService(session)
    return service


def get_cache_service() -> CacheService:
    """获取缓存服务依赖"""
    redis = redis_manager.get_client()
    service = CacheService(redis)
    return service


def get_proxy_service(session: AsyncSession = Depends(get_db)) -> ProxyService:
    """获取代理服务依赖

    Raises:
        RuntimeError: HTTP 客户端未初始化时抛出
    """
    http_client = get_http_client()
    cache_service = get_cache_service()
    tool_service = ToolService(session)
    provider_key_service = ProviderKeyService(session)
    service = ProxyService(http_client, cache_service, tool_service, provider_key_service)
    return service


def get_usage_service(session: AsyncSession = Depends(get_db)) -> UsageService:
    """获取用量统计服务依赖"""
    service = UsageService(session)
    return service


def get_usage_cache_service(session: AsyncSession = Depends(get_db)) -> UsageCacheService:
    """获取用量统计缓存服务依赖"""
    redis = redis_manager.get_client()
    usage_service = UsageService(session)
    service = UsageCacheService(redis, usage_service)
    return service


def get_connection_test_service() -> ConnectionTestService:
    """获取连接测试服务依赖

    Raises:
        RuntimeError: HTTP 客户端未初始化时抛出
    """
    http_client = get_http_client()
    service = ConnectionTestService(http_client)
    return service


# ==================== 认证依赖 ====================

# JWT Bearer 认证
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
):
    """获取当前登录用户

    从 JWT Token 中解析 user_id 并验证。

    Raises:
        APIException: Token 无效或用户不存在时抛出对应错误码
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise APIException(code=ErrorCode.TOKEN_INVALID)

    user_id = payload.get("sub")
    if not user_id:
        raise APIException(code=ErrorCode.TOKEN_INVALID)

    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise APIException(code=ErrorCode.USER_NOT_FOUND)

    if user.status != 1:
        raise APIException(code=ErrorCode.USER_DISABLED)

    return user
