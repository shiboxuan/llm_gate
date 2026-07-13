"""
Provider Key Schema - ProviderKey Pydantic Schemas
用于API请求验证和响应序列化
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProviderKeyCreate(BaseModel):
    """创建密钥请求"""
    name: str = Field(..., min_length=1, description="密钥名称，不能为空")  # 密钥名称（同时代表供应商，如 openai, anthropic, azure）
    api_key: str = Field(..., min_length=1, description="API密钥明文，不能为空")  # API密钥明文（仅创建时传入）


class ProviderKeyUpdate(BaseModel):
    """更新密钥请求"""
    name: Optional[str] = Field(None, min_length=1, description="密钥名称，不能为空")  # 密钥名称
    api_key: Optional[str] = Field(None, min_length=1, description="API密钥明文，不能为空")  # 新的API密钥明文
    status: Optional[int] = None


class ProviderKeyResponse(BaseModel):
    """密钥响应（不含明文）"""
    id: int
    user_id: str
    name: str
    status: int
    created_at: Optional[datetime] = None


class ProviderKeyListResponse(BaseModel):
    """密钥列表响应"""
    keys: List[ProviderKeyResponse]
    total: int
