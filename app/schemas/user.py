"""
用户 Schema - API 请求验证与响应序列化
"""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$", description="用户名，3-32位字母数字下划线连字符")
    password: str = Field(..., min_length=8, max_length=128, description="密码，至少8位")
    email: Optional[EmailStr] = None


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str
    username: str
    email: Optional[str] = None
    is_admin: bool = False
    status: int


class LoginResponse(BaseModel):
    """登录/注册响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    """JWT Token 载荷"""
    sub: str                        # user_id
    username: Optional[str] = None
    is_admin: Optional[bool] = None
    exp: Optional[int] = None
