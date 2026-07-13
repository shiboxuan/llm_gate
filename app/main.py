"""
LLM Gate 应用入口

配置 FastAPI 应用，注册中间件、路由、异常处理器，并托管前端静态资源（单镜像部署）。
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.control_plane.router import control_plane_router
from app.api.data_plane.router import data_plane_router
from app.config import get_settings
from app.core.dependencies import close_http_client, init_http_client
from app.core.exceptions import APIException, api_exception_handler, generic_exception_handler
from app.db.redis import redis_manager
from app.db.session import close_db, init_db
from app.middleware.logging import LoggingMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware

settings = get_settings()

# 前端静态资源目录（单镜像部署时由 Dockerfile 将前端构建产物拷贝到 ./static）
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 1. 初始化数据库 engine 与 session 工厂
    init_db()
    # 2. 连接 Redis
    await redis_manager.connect(settings.redis_url)
    # 3. 初始化 HTTP 客户端
    await init_http_client()
    yield
    # 关闭
    await close_http_client()
    await redis_manager.disconnect()
    await close_db()


# ==================== 创建应用 ====================

app = FastAPI(
    title="LLM Gate",
    description="LLM API Gateway - 提供统一的 LLM API 代理和管理功能",
    version="2.0.0",
    lifespan=lifespan,
)


# ==================== 中间件注册（从外到内） ====================

# 1. 安全头部（最外层）
app.add_middleware(SecurityHeadersMiddleware)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# 3. 请求ID
app.add_middleware(RequestIDMiddleware)

# 4. 日志
app.add_middleware(LoggingMiddleware)


# ==================== 异常处理器注册 ====================

app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


# ==================== 路由注册 ====================

# 控制面路由 /api/*
app.include_router(control_plane_router)

# 数据面路由 /v1/*
app.include_router(data_plane_router)


# ==================== 健康检查 ====================

@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查接口"""
    result = {"status": "healthy", "app_name": settings.app_name, "app_env": settings.app_env}
    return result


# ==================== 前端静态资源托管（单镜像部署） ====================

if os.path.isdir(STATIC_DIR):
    # 托管 assets 等静态资源子目录
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 路由兜底：非 API/v1/health 的 GET 请求返回前端入口或静态文件"""
        # 排除已注册的 API 路径（保险起见，正常情况下不会到这里）
        if full_path.startswith(("api/", "v1/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not Found")
        # 优先返回实际存在的静态文件
        target = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        # 其余路径返回 index.html（SPA 客户端路由）
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Not Found")
else:
    @app.get("/", tags=["Health"])
    async def root():
        """根路径（无前端静态资源时）"""
        result = {"message": "Welcome to LLM Gate", "docs": "/docs"}
        return result
