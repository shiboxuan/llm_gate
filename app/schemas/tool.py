"""
工具 Schema - Tool Pydantic Schemas v3.0
用于API请求验证和响应序列化

v3.0 变更: api_type 提升至 Tool 级别
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.models.tool import ApiType
from app.schemas.route import RouteResponse


class ToolCreate(BaseModel):
    """创建工具请求 v3.0"""
    name: str = Field(..., min_length=1, description="工具名称，不能为空")
    description: str = ""
    api_type: ApiType = "openai_chat"  # v3.0: Tool 级别的 API 类型


class ToolUpdate(BaseModel):
    """更新工具请求 v3.0"""
    name: Optional[str] = None
    description: Optional[str] = None
    api_type: Optional[ApiType] = None  # v3.0: 可更新 api_type
    active_route_name: Optional[str] = None
    status: Optional[int] = None


class ToolResponse(BaseModel):
    """工具响应 v3.0（包含 routes）"""
    id: int
    user_id: str
    name: str
    description: str = ""
    api_type: ApiType = "openai_chat"  # v3.0: Tool 级别的 API 类型
    active_route_name: Optional[str] = None
    routes: List[RouteResponse] = []
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ToolListResponse(BaseModel):
    """工具列表响应"""
    tools: List[ToolResponse]
    total: int


class ToolTokenResponse(BaseModel):
    """包含明文 Token 的响应 v3.0（仅创建时返回）"""
    id: int
    user_id: str
    name: str
    description: str = ""
    api_type: ApiType = "openai_chat"  # v3.0: Tool 级别的 API 类型
    api_key: str                     # 明文 API Key（仅创建时返回一次）
    active_route_name: Optional[str] = None
    routes: List[RouteResponse] = []
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
