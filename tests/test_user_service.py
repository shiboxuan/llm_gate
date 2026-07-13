"""
用户服务测试用例

测试 UserService 的所有方法
使用测试数据库（SQLAlchemy async session）进行测试
"""
import pytest

from app.services.user_service import UserService
from app.models.user import User
from app.core.security import hash_password


class TestUserService:
    """用户服务测试类"""

    @pytest.mark.asyncio
    async def test_get_user_by_id_exists(self, user_service):
        """测试通过ID查询存在的用户"""
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

        user = await user_service.get_user_by_id("user_001")

        assert user is not None
        assert isinstance(user, User)
        assert user.id == "user_001"
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_exists(self, user_service):
        """测试通过ID查询不存在的用户"""
        user = await user_service.get_user_by_id("not_exist_user")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_exists(self, user_service):
        """测试通过邮箱查询存在的用户"""
        user_data = {
            "id": "email_user_001",
            "username": "emailuser",
            "password_hash": hash_password("testpassword123"),
            "email": "emailuser@example.com",
            "is_admin": False,
            "status": 1
        }
        await user_service.create_user(user_data)

        user = await user_service.get_user_by_email("emailuser@example.com")

        assert user is not None
        assert isinstance(user, User)
        assert user.email == "emailuser@example.com"
        assert user.id == "email_user_001"

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_exists(self, user_service):
        """测试通过邮箱查询不存在的用户"""
        user = await user_service.get_user_by_email("notexist@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_username_exists(self, user_service):
        """测试通过用户名查询存在的用户"""
        user_data = {
            "id": "username_user_001",
            "username": "findme",
            "password_hash": hash_password("testpassword123"),
            "email": "findme@example.com",
            "is_admin": False,
            "status": 1
        }
        await user_service.create_user(user_data)

        user = await user_service.get_user_by_username("findme")

        assert user is not None
        assert isinstance(user, User)
        assert user.username == "findme"
        assert user.id == "username_user_001"

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_exists(self, user_service):
        """测试通过用户名查询不存在的用户"""
        user = await user_service.get_user_by_username("not_exist_username")

        assert user is None

    @pytest.mark.asyncio
    async def test_create_user(self, user_service):
        """测试创建用户"""
        user_data = {
            "username": "newuser",
            "password_hash": hash_password("newuserpassword123"),
            "email": "newuser@example.com",
            "is_admin": False,
            "status": 1
        }

        user = await user_service.create_user(user_data)

        assert user is not None
        assert isinstance(user, User)
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.status == 1  # 默认状态
        assert user.id.startswith("user_")  # 自动生成的ID

    @pytest.mark.asyncio
    async def test_create_user_with_custom_id(self, user_service):
        """测试使用自定义ID创建用户"""
        user_data = {
            "id": "custom_user_id",
            "username": "customuser",
            "password_hash": hash_password("custompassword123"),
            "email": "custom@example.com",
            "is_admin": False,
            "status": 1
        }

        user = await user_service.create_user(user_data)

        assert user is not None
        assert user.id == "custom_user_id"

    @pytest.mark.asyncio
    async def test_update_user(self, user_service):
        """测试更新用户信息"""
        # 先创建一个用户
        user_data = {
            "id": "update_test_user",
            "username": "updateuser",
            "password_hash": hash_password("updatepassword123"),
            "email": "update_test@example.com",
            "is_admin": False,
            "status": 1
        }
        await user_service.create_user(user_data)

        # 更新用户信息
        update_data = {"email": "updated@example.com", "is_admin": True}
        updated_user = await user_service.update_user("update_test_user", update_data)

        assert updated_user is not None
        assert updated_user.email == "updated@example.com"
        assert updated_user.is_admin is True
        assert updated_user.username == "updateuser"  # 未更新的字段保持不变

    @pytest.mark.asyncio
    async def test_update_user_not_exists(self, user_service):
        """测试更新不存在的用户"""
        update_data = {"email": "new@example.com"}
        updated_user = await user_service.update_user("not_exist_user_update", update_data)

        assert updated_user is None

    @pytest.mark.asyncio
    async def test_update_user_status(self, user_service):
        """测试更新用户状态"""
        # 先创建一个用户
        user_data = {
            "id": "status_test_user",
            "username": "statususer",
            "password_hash": hash_password("statuspassword123"),
            "email": "status_test@example.com",
            "is_admin": False,
            "status": 1
        }
        await user_service.create_user(user_data)

        # 更新状态为禁用
        updated_user = await user_service.update_user_status("status_test_user", 0)

        assert updated_user is not None
        assert updated_user.status == 0

        # 恢复状态为正常
        updated_user = await user_service.update_user_status("status_test_user", 1)

        assert updated_user is not None
        assert updated_user.status == 1

    @pytest.mark.asyncio
    async def test_update_user_status_not_exists(self, user_service):
        """测试更新不存在用户的状态"""
        updated_user = await user_service.update_user_status("not_exist_status_user", 0)

        assert updated_user is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
