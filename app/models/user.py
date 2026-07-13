"""
用户模型 - User Pydantic 模型（用于 service 层数据传递）
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    """用户模型，注册登录用户"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    password_hash: str = ""
    email: Optional[str] = None
    is_admin: bool = False
    status: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
