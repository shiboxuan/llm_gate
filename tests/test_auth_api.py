"""
认证路由 API 测试用例

测试 /api/auth 下的所有接口
包括注册、登录、获取当前用户信息等功能
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from app.api.control_plane.auth import login, register, get_current_user_info
from app.schemas.user import RegisterRequest, LoginRequest, LoginResponse, UserResponse
from app.services.user_service import UserService
from app.models.user import User
from app.core.security import create_access_token, verify_token, hash_password
from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode


class TestRegisterEndpoint:
    """注册接口测试类"""

    # ==================== 正常注册测试 ====================

    @pytest.mark.asyncio
    async def test_register_new_user_success(self, db_session, sample_register_data):
        """测试新用户注册成功"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)

        assert isinstance(response, LoginResponse)
        assert response.access_token is not None
        assert len(response.access_token) > 0
        assert response.token_type == "bearer"

        assert response.user.username == sample_register_data["username"]
        assert response.user.email == sample_register_data["email"]
        assert response.user.status == 1

    @pytest.mark.asyncio
    async def test_register_generates_valid_jwt_token(self, db_session, sample_register_data):
        """测试注册生成的 JWT Token 有效"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)

        payload = verify_token(response.access_token)
        assert payload is not None
        assert "sub" in payload
        assert "username" in payload
        assert payload["username"] == sample_register_data["username"]

    @pytest.mark.asyncio
    async def test_register_auto_generates_user_id(self, db_session, sample_register_data):
        """测试注册时自动生成 user_id"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)

        assert response.user.id.startswith("user_")
        assert len(response.user.id) > 5

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, db_session, sample_register_data):
        """测试注册重复用户名"""
        register_request = RegisterRequest(**sample_register_data)

        # 第一次注册
        await register(register_request, db_session)

        # 第二次注册相同用户名
        with pytest.raises(HTTPException) as exc_info:
            await register(register_request, db_session)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_register_with_long_username(self, db_session):
        """测试注册时使用较长的用户名"""
        long_username = "user_" + "a" * 20
        register_data = {
            "username": long_username,
            "password": "longuserpassword123",
            "email": "longuser@example.com"
        }
        register_request = RegisterRequest(**register_data)

        response = await register(register_request, db_session)

        assert response.user.username == long_username

    @pytest.mark.asyncio
    async def test_register_with_email(self, db_session):
        """测试注册时带邮箱"""
        register_data = {
            "username": "emailuser",
            "password": "emailpassword123",
            "email": "user@example.cn"
        }
        register_request = RegisterRequest(**register_data)

        response = await register(register_request, db_session)

        assert response.user.email == "user@example.cn"

    @pytest.mark.asyncio
    async def test_register_without_email(self, db_session):
        """测试注册时不带邮箱"""
        register_data = {
            "username": "noemailuser",
            "password": "noemailpassword123"
        }
        register_request = RegisterRequest(**register_data)

        response = await register(register_request, db_session)

        assert response.user.email is None

    # ==================== Token 验证测试 ====================

    @pytest.mark.asyncio
    async def test_register_token_contains_user_id_in_sub(self, db_session, sample_register_data):
        """测试注册 Token 中的 sub 字段包含 user_id"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)
        payload = verify_token(response.access_token)

        assert payload["sub"] == response.user.id

    @pytest.mark.asyncio
    async def test_register_token_contains_exp_claim(self, db_session, sample_register_data):
        """测试注册 Token 包含过期时间声明"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)
        payload = verify_token(response.access_token)

        assert "exp" in payload
        assert payload["exp"] > 0

    @pytest.mark.asyncio
    async def test_register_token_contains_iat_claim(self, db_session, sample_register_data):
        """测试注册 Token 包含签发时间声明"""
        register_request = RegisterRequest(**sample_register_data)

        response = await register(register_request, db_session)
        payload = verify_token(response.access_token)

        assert "iat" in payload
        assert payload["iat"] > 0


class TestLoginEndpoint:
    """登录接口测试类"""

    @pytest.mark.asyncio
    async def test_login_success(self, db_session):
        """测试已注册用户登录成功"""
        # 先注册用户
        register_data = {
            "username": "loginuser",
            "password": "loginpassword123",
            "email": "loginuser@example.com"
        }
        register_request = RegisterRequest(**register_data)
        await register(register_request, db_session)

        # 登录
        login_data = {"username": "loginuser", "password": "loginpassword123"}
        login_request = LoginRequest(**login_data)

        response = await login(login_request, db_session)

        assert isinstance(response, LoginResponse)
        assert response.access_token is not None
        assert response.token_type == "bearer"
        assert response.user.username == "loginuser"
        assert response.user.status == 1

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, db_session):
        """测试密码错误时登录失败"""
        # 先注册用户
        register_data = {
            "username": "wrongpwuser",
            "password": "correctpassword123",
            "email": "wrongpw@example.com"
        }
        register_request = RegisterRequest(**register_data)
        await register(register_request, db_session)

        # 用错误密码登录
        login_data = {"username": "wrongpwuser", "password": "wrongpassword123"}
        login_request = LoginRequest(**login_data)

        with pytest.raises(HTTPException) as exc_info:
            await login(login_request, db_session)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, db_session):
        """测试登录不存在的用户"""
        login_data = {"username": "nonexistent_user", "password": "somepassword123"}
        login_request = LoginRequest(**login_data)

        with pytest.raises(HTTPException) as exc_info:
            await login(login_request, db_session)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_disabled_user(self, db_session, user_service):
        """测试被禁用用户登录失败"""
        # 先注册用户
        register_data = {
            "username": "disabledlogin",
            "password": "disabledpassword123",
            "email": "disabledlogin@example.com"
        }
        register_request = RegisterRequest(**register_data)
        reg_response = await register(register_request, db_session)

        # 禁用用户
        await user_service.update_user_status(reg_response.user.id, 0)

        # 尝试登录
        login_data = {"username": "disabledlogin", "password": "disabledpassword123"}
        login_request = LoginRequest(**login_data)

        with pytest.raises(HTTPException) as exc_info:
            await login(login_request, db_session)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_login_generates_valid_jwt_token(self, db_session):
        """测试登录生成的 JWT Token 有效"""
        # 先注册
        register_data = {
            "username": "jwtuser",
            "password": "jwtpassword123",
            "email": "jwtuser@example.com"
        }
        register_request = RegisterRequest(**register_data)
        await register(register_request, db_session)

        # 登录
        login_data = {"username": "jwtuser", "password": "jwtpassword123"}
        login_request = LoginRequest(**login_data)

        response = await login(login_request, db_session)

        payload = verify_token(response.access_token)
        assert payload is not None
        assert "sub" in payload
        assert "username" in payload
        assert payload["username"] == "jwtuser"

    @pytest.mark.asyncio
    async def test_login_same_user_multiple_times(self, db_session):
        """测试同一用户多次登录"""
        import asyncio

        # 先注册
        register_data = {
            "username": "multilogin",
            "password": "multiloginpassword123",
            "email": "multilogin@example.com"
        }
        register_request = RegisterRequest(**register_data)
        await register(register_request, db_session)

        login_data = {"username": "multilogin", "password": "multiloginpassword123"}
        login_request = LoginRequest(**login_data)

        # 第一次登录
        response1 = await login(login_request, db_session)
        user_id1 = response1.user.id

        await asyncio.sleep(1.1)

        # 第二次登录
        response2 = await login(login_request, db_session)
        user_id2 = response2.user.id

        # 验证两次登录返回相同的 user_id
        assert user_id1 == user_id2
        # Token 应该不同（因为时间戳不同）
        assert response1.access_token != response2.access_token


class TestGetCurrentUserEndpoint:
    """获取当前用户信息接口测试类"""

    # ==================== 正常获取用户信息测试 ====================

    @pytest.mark.asyncio
    async def test_get_me_success(self, test_user):
        """测试成功获取当前用户信息"""
        response = await get_current_user_info(test_user)

        assert isinstance(response, UserResponse)
        assert response.id == test_user.id
        assert response.username == test_user.username
        assert response.email == test_user.email
        assert response.is_admin == test_user.is_admin

    @pytest.mark.asyncio
    async def test_get_me_returns_all_fields(self, test_user):
        """测试获取用户信息返回所有必要字段"""
        response = await get_current_user_info(test_user)

        assert hasattr(response, 'id')
        assert hasattr(response, 'username')
        assert hasattr(response, 'email')
        assert hasattr(response, 'is_admin')
        assert hasattr(response, 'status')

    @pytest.mark.asyncio
    async def test_get_me_status_active(self, test_user):
        """测试获取活跃用户的状态"""
        response = await get_current_user_info(test_user)

        assert response.status == 1

    # ==================== 用户状态测试 ====================

    @pytest.mark.asyncio
    async def test_get_me_response_format(self, test_user):
        """测试获取用户信息响应格式正确"""
        response = await get_current_user_info(test_user)

        response_dict = response.model_dump()

        assert "id" in response_dict
        assert "username" in response_dict
        assert "email" in response_dict
        assert "is_admin" in response_dict
        assert "status" in response_dict


class TestAuthDependencies:
    """认证依赖测试类"""

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, user_service, db_session):
        """测试使用有效 Token 获取当前用户"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # 先创建用户
        user_data = {
            "id": "user_001",
            "username": "testuser",
            "password_hash": hash_password("testpassword123"),
            "email": "test@example.com",
            "is_admin": False,
            "status": 1
        }
        await user_service.create_user(user_data)

        # 创建有效的 token
        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # 获取当前用户
        user = await get_current_user(credentials, user_service)

        assert user is not None
        assert user.id == "user_001"

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, user_service):
        """测试使用无效 Token 获取当前用户抛出异常"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_token")

        with pytest.raises(APIException) as exc_info:
            await get_current_user(credentials, user_service)

        assert exc_info.value.code == ErrorCode.TOKEN_INVALID

    @pytest.mark.asyncio
    async def test_get_current_user_with_nonexistent_user(self, user_service):
        """测试 Token 中的用户不存在时抛出异常"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # 创建指向不存在用户的 token
        token = create_access_token(data={"sub": "nonexistent_user", "username": "ghost", "is_admin": False})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(APIException) as exc_info:
            await get_current_user(credentials, user_service)

        assert exc_info.value.code == ErrorCode.USER_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_current_user_with_disabled_user(self, user_service, db_session):
        """测试被禁用用户获取信息时抛出异常"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # 先创建一个禁用的用户
        user_data = {
            "id": "disabled_user_123",
            "username": "disabled_123",
            "password_hash": hash_password("disabledpassword123"),
            "email": "disabled123@example.com",
            "is_admin": False,
            "status": 0  # 禁用状态
        }
        await user_service.create_user(user_data)

        # 创建指向禁用用户的 token
        token = create_access_token(data={"sub": "disabled_user_123", "username": "disabled_123", "is_admin": False})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(APIException) as exc_info:
            await get_current_user(credentials, user_service)

        assert exc_info.value.code == ErrorCode.USER_DISABLED

    @pytest.mark.asyncio
    async def test_get_current_user_token_missing_sub(self, user_service):
        """测试 Token 缺少 sub 字段时抛出异常"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # 创建缺少 sub 的 token
        token = create_access_token(data={"username": "testuser"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(APIException) as exc_info:
            await get_current_user(credentials, user_service)

        assert exc_info.value.code == ErrorCode.TOKEN_INVALID


class TestTokenSecurity:
    """Token 安全性测试类"""

    def test_verify_token_valid(self):
        """测试验证有效 Token"""
        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False})
        payload = verify_token(token)

        assert payload is not None
        assert payload["sub"] == "user_001"

    def test_verify_token_invalid(self):
        """测试验证无效 Token"""
        payload = verify_token("invalid_token_string")

        assert payload is None

    def test_verify_token_tampered(self):
        """测试验证被篡改的 Token"""
        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False})
        # 篡改 token
        tampered_token = token[:-5] + "xxxxx"

        payload = verify_token(tampered_token)

        assert payload is None

    def test_verify_token_expired(self):
        """测试验证过期 Token"""
        from datetime import timedelta

        # 创建已过期的 token
        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False}, expires_delta=timedelta(seconds=-10))
        payload = verify_token(token)

        assert payload is None

    def test_create_token_with_custom_expiry(self):
        """测试创建自定义过期时间的 Token"""
        from datetime import timedelta

        token = create_access_token(data={"sub": "user_001", "username": "testuser", "is_admin": False}, expires_delta=timedelta(hours=24))
        payload = verify_token(token)

        assert payload is not None
        assert "exp" in payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
