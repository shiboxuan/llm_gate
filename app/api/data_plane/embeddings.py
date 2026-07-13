"""
数据面 Embeddings API

提供 OpenAI 兼容的 Embeddings 接口，通过 Tool Token 认证。
注意：数据面是高频接口，不校验用户 Token，只校验 Tool Token。
适用于 RAG、语义搜索等 embedding 场景。

支持的 Provider：
- OpenAI: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
- Deepseek: jina-embeddings-v2-base-code, jina-embeddings-v2-base-zh, bge-m3
- Qwen: text-embedding-v4/v3/v2/v1
"""
from typing import Dict, Any

from fastapi import APIRouter, Header, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode
from app.core.dependencies import get_proxy_service, get_usage_service
from app.services.proxy_service import ProxyService
from app.services.usage_service import UsageService
from app.schemas.embedding import EmbeddingRequest
from app.api.data_plane._utils import record_usage_background
from app.logger_mgr import get_logger

logger = get_logger("app.api.data_plane.embeddings")

router = APIRouter()


@router.post("/embeddings")
async def create_embedding(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(..., description="Bearer <tool_token>"),
    proxy_service: ProxyService = Depends(get_proxy_service),
    usage_service: UsageService = Depends(get_usage_service)
):
    """
    代理 Embeddings 请求

    支持 OpenAI 兼容格式，将请求转发到配置的目标 Provider。
    Embeddings 仅支持非流式响应。

    认证方式：
    - 仅需 Tool Token（在 Authorization Header 中）
    - 不需要用户 JWT Token
    - 要求 Tool 的 api_type 为 "openai_embeddings"

    特性：
    - 自动记录 Token 用量到数据库
    - 支持 dimensions 参数（适用于 text-embedding-3-* 系列）
    """
    # 1. 提取并验证 Tool Token 格式
    if not authorization.startswith("Bearer "):
        raise APIException(
            code=ErrorCode.TOKEN_INVALID,
            message="Invalid authorization header format, expected: Bearer <tool_token>"
        )

    tool_token = authorization.replace("Bearer ", "").strip()
    if not tool_token:
        raise APIException(code=ErrorCode.TOKEN_INVALID, message="Tool token is empty")

    # 2. 解析路由配置（缓存优先，由 proxy_service 内部处理）
    config = await proxy_service.resolve_route_config(tool_token)
    if not config:
        raise APIException(code=ErrorCode.TOOL_TOKEN_INVALID)

    # 3. 验证 api_type
    api_type = config.get("api_type", "openai_chat")
    if api_type != "openai_embeddings":
        raise APIException(
            code=ErrorCode.ROUTE_NOT_FOUND,
            message=f"This endpoint requires api_type 'openai_embeddings', got '{api_type}'"
        )

    # 4. 补全 base_url：如果用户配置的 URL 未包含 /embeddings，则自动添加
    base_url = config["base_url"].rstrip("/")
    if not base_url.endswith("/embeddings"):
        url = f"{base_url}/embeddings"
    else:
        url = base_url

    # 5. 解析请求体
    body = await request.json()
    embedding_request = EmbeddingRequest(**body)

    # 6. 构建 Provider 请求
    provider_request: Dict[str, Any] = {
        "input": embedding_request.input,
        "model": config.get("model"),
    }

    # 添加可选参数
    if embedding_request.encoding_format:
        provider_request["encoding_format"] = embedding_request.encoding_format
    if embedding_request.dimensions:
        provider_request["dimensions"] = embedding_request.dimensions
    if embedding_request.user:
        provider_request["user"] = embedding_request.user

    # 7. 构建请求头
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }

    # 8. 转发请求（非流式）
    try:
        response_data = await proxy_service._forward_non_stream(url, headers, provider_request)

        # 提取用量并异步记录
        # Embeddings 的 usage 格式：prompt_tokens, total_tokens（无 completion_tokens）
        raw_usage = response_data.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("prompt_tokens", 0),
            "completion_tokens": 0,  # Embeddings 没有 completion tokens
            "total_tokens": raw_usage.get("total_tokens", 0),
        }

        record_data = proxy_service.build_usage_record_data(
            config, usage,
            request_model=embedding_request.model,
            status="success"
        )
        background_tasks.add_task(record_usage_background, usage_service, record_data)

        return JSONResponse(content=response_data)

    except Exception as e:
        # 记录错误请求
        error_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        record_data = proxy_service.build_usage_record_data(
            config, error_usage,
            request_model=embedding_request.model,
            status="error",
            error_message=str(e)
        )
        background_tasks.add_task(record_usage_background, usage_service, record_data)
        raise
