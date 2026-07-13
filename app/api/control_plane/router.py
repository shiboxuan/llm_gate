"""
控制面总路由

注册所有控制面子路由，配置路由前缀 /api
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .tools import router as tools_router
from .provider_keys import router as provider_keys_router
from .usage import router as usage_router
from .test import router as test_router

control_plane_router = APIRouter(prefix="/api")

# 认证路由
control_plane_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

# 工具管理路由
control_plane_router.include_router(tools_router, prefix="/tools", tags=["Tools"])

# Provider Key路由
control_plane_router.include_router(provider_keys_router, prefix="/provider-keys", tags=["Provider Keys"])

# 用量统计路由（V2预留）
control_plane_router.include_router(usage_router, prefix="/usage", tags=["Usage"])

# 测试路由
control_plane_router.include_router(test_router, prefix="/test", tags=["Test"])
