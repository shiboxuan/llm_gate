"""
Provider Key 模型 - ProviderKey Pydantic 模型
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class ProviderKey(BaseModel):
    """Provider Key 模型，用于数据库代理响应映射"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: str
    name: str                    # 密钥名称（同时代表供应商，如 openai, anthropic, azure）
    api_key_encrypted: str
    status: int = 1
    created_at: Optional[datetime] = None
