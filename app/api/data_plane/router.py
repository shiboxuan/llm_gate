"""
数据面 API 路由

数据面 API 用于 LLM 请求代理，提供 OpenAI 和 Anthropic 兼容接口。
通过 Tool Token 认证，不需要用户 JWT Token。

支持的接口：
- /v1/chat/completions - OpenAI Chat Completions API（适用于 Cline、Cursor 等）
- /v1/messages - Anthropic Messages API（适用于 Claude Code 等）
- /v1/responses - OpenAI Responses API（支持内置工具、Background Mode 等）
- /v1/embeddings - OpenAI Embeddings API（适用于 RAG、语义搜索等）
"""
from fastapi import APIRouter

from app.api.data_plane.chat import router as chat_router
from app.api.data_plane.messages import router as messages_router
from app.api.data_plane.responses import router as responses_router
from app.api.data_plane.embeddings import router as embeddings_router

data_plane_router = APIRouter(prefix="/v1")

# Chat Completions 路由（OpenAI 兼容）
data_plane_router.include_router(chat_router, tags=["Chat Completions"])

# Messages 路由（Anthropic 兼容）
data_plane_router.include_router(messages_router, tags=["Messages"])

# Responses 路由（OpenAI Responses API）
data_plane_router.include_router(responses_router, tags=["Responses"])

# Embeddings 路由（OpenAI 兼容）
data_plane_router.include_router(embeddings_router, tags=["Embeddings"])
