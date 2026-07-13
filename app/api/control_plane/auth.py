"""
认证路由 - 注册、登录、用户信息管理

用户名 + 密码认证，密码使用 bcrypt 哈希存储，登录成功签发 JWT。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.core.security import create_access_token, hash_password, verify_password
from app.core.dependencies import get_current_user, get_user_service
from app.db.session import get_db
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=LoginResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_db)):
    """注册新用户（普通用户）

    - 用户名唯一，密码至少 8 位
    - 注册成功直接签发 JWT（无需再次登录）
    """
    user_service = UserService(session)

    # 检查用户名是否已存在
    existing = await user_service.get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 检查邮箱（如果提供）
    if req.email:
        existing_email = await user_service.get_user_by_email(str(req.email))
        if existing_email:
            raise HTTPException(status_code=409, detail="邮箱已被注册")

    # 创建用户
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(req.password)
    user = await user_service.create_user({
        "id": user_id,
        "username": req.username,
        "password_hash": password_hash,
        "email": str(req.email) if req.email else None,
        "is_admin": False,
        "status": 1,
    })

    # 签发 JWT
    access_token = create_access_token(data={"sub": user.id, "username": user.username, "is_admin": user.is_admin})
    user_response = UserResponse(id=user.id, username=user.username, email=user.email, is_admin=user.is_admin, status=user.status)
    response = LoginResponse(access_token=access_token, token_type="bearer", user=user_response)
    return response


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_db)):
    """用户名密码登录"""
    user_service = UserService(session)

    user = await user_service.get_user_by_username(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.status != 1:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    # 签发 JWT
    access_token = create_access_token(data={"sub": user.id, "username": user.username, "is_admin": user.is_admin})
    user_response = UserResponse(id=user.id, username=user.username, email=user.email, is_admin=user.is_admin, status=user.status)
    response = LoginResponse(access_token=access_token, token_type="bearer", user=user_response)
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)):
    """获取当前登录用户信息"""
    user_response = UserResponse(id=current_user.id, username=current_user.username, email=current_user.email, is_admin=current_user.is_admin, status=current_user.status)
    return user_response
