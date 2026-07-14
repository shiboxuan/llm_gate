"""
LLM Gate 应用入口

配置 FastAPI 应用，注册中间件、路由、异常处理器，并托管前端静态资源（单镜像部署）。
"""
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
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


# index.html 模板缓存（进程内只读一次），用于向前端注入运行时配置
_INDEX_HTML_TEMPLATE: str | None = None


def _render_index_html(template: str, api_base_url: str) -> str:
    """将运行时配置注入 index.html 模板。

    把占位符 __LLM_GATE_RUNTIME_CONFIG__ 替换为 JSON（{"apiBaseUrl": ...}），
    供前端新手引导弹窗展示「后端 API 地址」。该值仅用于展示，不影响实际请求路由。
    将 `<` 转义为 \\u003c，防止值中潜在的 </script> 破坏 script 标签。
    """
    runtime_json = json.dumps({"apiBaseUrl": api_base_url}).replace("<", "\\u003c")
    return template.replace("__LLM_GATE_RUNTIME_CONFIG__", runtime_json, 1)


def _get_index_html() -> str | None:
    """读取并缓存 index.html 模板，返回注入运行时配置后的完整 HTML。

    模板在进程内只读一次；每次调用用当前 settings.public_api_base_url 重新渲染。
    无 index.html（如开发模式未构建前端）时返回 None。
    """
    global _INDEX_HTML_TEMPLATE
    if _INDEX_HTML_TEMPLATE is None:
        index_path = os.path.join(STATIC_DIR, "index.html")
        if not os.path.isfile(index_path):
            return None
        with open(index_path, "r", encoding="utf-8") as f:
            _INDEX_HTML_TEMPLATE = f.read()
    return _render_index_html(_INDEX_HTML_TEMPLATE, settings.public_api_base_url)


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
        # 其余路径返回 index.html（SPA 客户端路由），并注入运行时配置
        index_html = _get_index_html()
        if index_html is not None:
            return HTMLResponse(index_html)
        raise HTTPException(status_code=404, detail="Not Found")
else:
    @app.get("/", tags=["Health"])
    async def root():
        """根路径（无前端静态资源时）"""
        result = {"message": "Welcome to LLM Gate", "docs": "/docs"}
        return result
