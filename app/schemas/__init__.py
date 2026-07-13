"""
Pydantic Schemas 模块
导出所有 API 请求/响应 Schema
"""

# User Schemas
from app.schemas.user import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    LoginResponse,
    TokenPayload,
)

# Route Schemas
from app.schemas.route import (
    RouteConfigSchema,
    RouteCreate,
    RouteUpdate,
    RouteResponse,
)

# Tool Schemas
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolListResponse,
    ToolTokenResponse,
)

# Provider Key Schemas
from app.schemas.provider_key import (
    ProviderKeyCreate,
    ProviderKeyUpdate,
    ProviderKeyResponse,
    ProviderKeyListResponse,
)

# Chat Schemas
from app.schemas.chat import (
    Message,
    FunctionCall,
    ToolCall,
    ChatCompletionRequest,
    Usage,
    ChoiceMessage,
    Choice,
    ChatCompletionResponse,
    DeltaMessage,
    StreamChoice,
    ChatCompletionStreamResponse,
)

# Usage Schemas (V2)
from app.schemas.usage import (
    TimeRangeEnum,
    UsageQueryParams,
    RequestStatsResponse,
    TokenStatsResponse,
    RouteUsageDetailResponse,
    ToolUsageResponse,
    UsageOverviewResponse,
    DailyUsageResponse,
    UsageTrendResponse,
)

__all__ = [
    # User
    "RegisterRequest",
    "LoginRequest",
    "UserResponse",
    "LoginResponse",
    "TokenPayload",
    # Route
    "RouteConfigSchema",
    "RouteCreate",
    "RouteUpdate",
    "RouteResponse",
    # Tool
    "ToolCreate",
    "ToolUpdate",
    "ToolResponse",
    "ToolListResponse",
    "ToolTokenResponse",
    # Provider Key
    "ProviderKeyCreate",
    "ProviderKeyUpdate",
    "ProviderKeyResponse",
    "ProviderKeyListResponse",
    # Chat
    "Message",
    "FunctionCall",
    "ToolCall",
    "ChatCompletionRequest",
    "Usage",
    "ChoiceMessage",
    "Choice",
    "ChatCompletionResponse",
    "DeltaMessage",
    "StreamChoice",
    "ChatCompletionStreamResponse",
    # Usage (V2)
    "TimeRangeEnum",
    "UsageQueryParams",
    "RequestStatsResponse",
    "TokenStatsResponse",
    "RouteUsageDetailResponse",
    "ToolUsageResponse",
    "ApiPathUsageResponse",
    "UsageOverviewResponse",
    "DailyUsageResponse",
    "UsageTrendResponse",
]
