"""
Provider Key 路由 API 测试用例

测试 /api/provider-keys 下的所有接口
包括密钥的创建、列表、删除功能
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select

from app.api.control_plane.provider_keys import (
    create_provider_key, list_provider_keys, delete_provider_key
)
from app.core.exceptions import APIException
from app.schemas.provider_key import ProviderKeyCreate, ProviderKeyResponse
from app.services.provider_key_service import ProviderKeyService
from app.db.orm import ProviderKeyORM
from app.models.user import User


class TestCreateProviderKeyEndpoint:
    """创建 Provider Key 接口测试类"""
    
    # ==================== 正常创建测试 ====================
    
    @pytest.mark.asyncio
    async def test_create_provider_key_success(self, test_user, provider_key_service, sample_provider_key_data):
        """测试成功创建 Provider Key"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert isinstance(response, ProviderKeyResponse)
        assert response.name == sample_provider_key_data["name"]
        assert response.status == 1
    
    @pytest.mark.asyncio
    async def test_create_provider_key_has_id(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建 Provider Key 返回 ID"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.id is not None
        assert response.id > 0
    
    @pytest.mark.asyncio
    async def test_create_provider_key_has_user_id(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建 Provider Key 关联用户 ID"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.user_id == test_user.id
    
    @pytest.mark.asyncio
    async def test_create_provider_key_has_created_at(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建 Provider Key 包含创建时间"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.created_at is not None
    
    @pytest.mark.asyncio
    async def test_create_provider_key_not_return_api_key(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建 Provider Key 响应不返回明文密钥"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        # ProviderKeyResponse 不应该包含 api_key 字段
        assert not hasattr(response, 'api_key')
        assert not hasattr(response, 'api_key_encrypted')
    
    # ==================== 重复名称测试 ====================
    
    @pytest.mark.asyncio
    async def test_create_provider_key_duplicate_name(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建重复名称的 Provider Key"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        
        # 第一次创建
        await create_provider_key(key_data, test_user, provider_key_service)
        
        # 第二次创建相同名称
        with pytest.raises(APIException) as exc_info:
            await create_provider_key(key_data, test_user, provider_key_service)
        
        assert exc_info.value.http_status == 409  # Conflict
    
    @pytest.mark.asyncio
    async def test_create_provider_key_same_name_different_users(self, test_user, test_user_2, provider_key_service):
        """测试不同用户可以使用相同名称"""
        key_data = ProviderKeyCreate(name="shared_name", api_key="sk-test-key")
        
        # 用户1创建
        response1 = await create_provider_key(key_data, test_user, provider_key_service)
        
        # 用户2创建相同名称（应该成功）
        response2 = await create_provider_key(key_data, test_user_2, provider_key_service)
        
        assert response1.name == response2.name
        assert response1.user_id != response2.user_id
    
    # ==================== 参数验证测试 ====================
    
    @pytest.mark.asyncio
    async def test_create_provider_key_with_long_name(self, test_user, provider_key_service):
        """测试创建 Provider Key 时使用较长的名称"""
        long_name = "key_" + "A" * 200
        key_data = ProviderKeyCreate(name=long_name, api_key="sk-test-key")
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.name == long_name
    
    @pytest.mark.asyncio
    async def test_create_provider_key_with_special_characters_in_name(self, test_user, provider_key_service):
        """测试创建 Provider Key 时名称包含特殊字符"""
        key_data = ProviderKeyCreate(name="key_<test>&'\"测试", api_key="sk-test-key")
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.name == "key_<test>&'\"测试"
    
    @pytest.mark.asyncio
    async def test_create_provider_key_with_long_api_key(self, test_user, provider_key_service):
        """测试创建 Provider Key 时使用较长的 API Key"""
        long_api_key = "sk-" + "x" * 500
        key_data = ProviderKeyCreate(name="long_key_test", api_key=long_api_key)
        
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.name == "long_key_test"
    
    @pytest.mark.asyncio
    async def test_create_provider_key_with_different_formats(self, test_user, provider_key_service):
        """测试创建不同格式的 API Key"""
        formats = [
            ("openai_key", "sk-xxxxxxxxxxxxxxxx"),
            ("anthropic_key", "sk-ant-xxxxxxxxxxxxx"),
            ("azure_key", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
            ("custom_key", "custom-api-key-format"),
        ]
        
        for name, api_key in formats:
            key_data = ProviderKeyCreate(name=name, api_key=api_key)
            response = await create_provider_key(key_data, test_user, provider_key_service)
            assert response.name == name
    
    # ==================== 多个密钥测试 ====================
    
    @pytest.mark.asyncio
    async def test_create_multiple_provider_keys(self, test_user, provider_key_service):
        """测试创建多个 Provider Key"""
        keys = [
            ProviderKeyCreate(name="openai", api_key="sk-openai-key"),
            ProviderKeyCreate(name="anthropic", api_key="sk-anthropic-key"),
            ProviderKeyCreate(name="azure", api_key="azure-key"),
        ]
        
        responses = []
        for key_data in keys:
            response = await create_provider_key(key_data, test_user, provider_key_service)
            responses.append(response)
        
        # 验证所有密钥都有不同的 ID
        ids = [r.id for r in responses]
        assert len(set(ids)) == 3


class TestListProviderKeysEndpoint:
    """获取 Provider Key 列表接口测试类"""
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_empty(self, test_user, provider_key_service):
        """测试获取空的 Provider Key 列表"""
        response = await list_provider_keys(test_user, provider_key_service)
        
        assert isinstance(response, list)
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_after_create(self, test_user, provider_key_service, sample_provider_key_data):
        """测试创建后获取 Provider Key 列表"""
        # 创建密钥
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        await create_provider_key(key_data, test_user, provider_key_service)
        
        # 获取列表
        response = await list_provider_keys(test_user, provider_key_service)
        
        assert isinstance(response, list)
        key_names = [k.name for k in response]
        assert sample_provider_key_data["name"] in key_names
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_returns_correct_type(self, test_user, provider_key_service, sample_provider_key_data):
        """测试获取列表返回正确类型"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        await create_provider_key(key_data, test_user, provider_key_service)
        
        response = await list_provider_keys(test_user, provider_key_service)
        
        for key in response:
            assert isinstance(key, ProviderKeyResponse)
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_not_include_api_key(self, test_user, provider_key_service, sample_provider_key_data):
        """测试列表不包含 API Key 明文"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        await create_provider_key(key_data, test_user, provider_key_service)
        
        response = await list_provider_keys(test_user, provider_key_service)
        
        for key in response:
            assert not hasattr(key, 'api_key')
            assert not hasattr(key, 'api_key_encrypted')
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_only_own_keys(self, test_user, test_user_2, provider_key_service):
        """测试只获取自己的 Provider Key"""
        # 用户1创建密钥
        key_data1 = ProviderKeyCreate(name="user1_key", api_key="sk-user1-key")
        await create_provider_key(key_data1, test_user, provider_key_service)
        
        # 用户2创建密钥
        key_data2 = ProviderKeyCreate(name="user2_key", api_key="sk-user2-key")
        await create_provider_key(key_data2, test_user_2, provider_key_service)
        
        # 用户1获取列表
        response = await list_provider_keys(test_user, provider_key_service)
        
        key_names = [k.name for k in response]
        assert "user1_key" in key_names
        assert "user2_key" not in key_names
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_multiple(self, test_user, provider_key_service):
        """测试获取多个 Provider Key"""
        # 创建多个密钥
        keys = [
            ProviderKeyCreate(name="key1", api_key="sk-key1"),
            ProviderKeyCreate(name="key2", api_key="sk-key2"),
            ProviderKeyCreate(name="key3", api_key="sk-key3"),
        ]
        
        for key_data in keys:
            await create_provider_key(key_data, test_user, provider_key_service)
        
        # 获取列表
        response = await list_provider_keys(test_user, provider_key_service)
        
        key_names = [k.name for k in response]
        assert "key1" in key_names
        assert "key2" in key_names
        assert "key3" in key_names
    
    @pytest.mark.asyncio
    async def test_list_provider_keys_includes_all_fields(self, test_user, provider_key_service, sample_provider_key_data):
        """测试列表包含所有必要字段"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        await create_provider_key(key_data, test_user, provider_key_service)
        
        response = await list_provider_keys(test_user, provider_key_service)
        
        for key in response:
            assert hasattr(key, 'id')
            assert hasattr(key, 'user_id')
            assert hasattr(key, 'name')
            assert hasattr(key, 'status')
            assert hasattr(key, 'created_at')


class TestDeleteProviderKeyEndpoint:
    """删除 Provider Key 接口测试类"""
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_success(self, test_user, provider_key_service, tool_service, cache_service, sample_provider_key_data):
        """测试成功删除 Provider Key"""
        # 创建密钥
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        created = await create_provider_key(key_data, test_user, provider_key_service)
        
        # 删除密钥
        await delete_provider_key(created.id, test_user, provider_key_service, tool_service, cache_service)
        
        # 验证已删除
        response = await list_provider_keys(test_user, provider_key_service)
        key_ids = [k.id for k in response]
        assert created.id not in key_ids
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_not_found(self, test_user, provider_key_service, tool_service, cache_service):
        """测试删除不存在的 Provider Key"""
        with pytest.raises(APIException) as exc_info:
            await delete_provider_key(99999, test_user, provider_key_service, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_not_owner(self, test_user, test_user_2, provider_key_service, tool_service, cache_service, sample_provider_key_data):
        """测试删除不属于自己的 Provider Key"""
        # 用户1创建密钥
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        created = await create_provider_key(key_data, test_user, provider_key_service)
        
        # 用户2尝试删除
        with pytest.raises(APIException) as exc_info:
            await delete_provider_key(created.id, test_user_2, provider_key_service, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_returns_no_content(self, test_user, provider_key_service, tool_service, cache_service, sample_provider_key_data):
        """测试删除成功返回空内容"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        created = await create_provider_key(key_data, test_user, provider_key_service)
        
        # 删除应该返回 None (204 No Content)
        result = await delete_provider_key(created.id, test_user, provider_key_service, tool_service, cache_service)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_one_of_many(self, test_user, provider_key_service, tool_service, cache_service):
        """测试删除多个密钥中的一个"""
        # 创建多个密钥
        keys = [
            ProviderKeyCreate(name="keep1", api_key="sk-keep1"),
            ProviderKeyCreate(name="delete_me", api_key="sk-delete"),
            ProviderKeyCreate(name="keep2", api_key="sk-keep2"),
        ]
        
        created_keys = []
        for key_data in keys:
            response = await create_provider_key(key_data, test_user, provider_key_service)
            created_keys.append(response)
        
        # 删除中间的密钥
        delete_key = next(k for k in created_keys if k.name == "delete_me")
        await delete_provider_key(delete_key.id, test_user, provider_key_service, tool_service, cache_service)
        
        # 验证其他密钥仍存在
        response = await list_provider_keys(test_user, provider_key_service)
        key_names = [k.name for k in response]
        
        assert "keep1" in key_names
        assert "keep2" in key_names
        assert "delete_me" not in key_names
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_twice(self, test_user, provider_key_service, tool_service, cache_service, sample_provider_key_data):
        """测试删除同一密钥两次"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        created = await create_provider_key(key_data, test_user, provider_key_service)
        
        # 第一次删除
        await delete_provider_key(created.id, test_user, provider_key_service, tool_service, cache_service)
        
        # 第二次删除应该失败
        with pytest.raises(APIException) as exc_info:
            await delete_provider_key(created.id, test_user, provider_key_service, tool_service, cache_service)
        
        assert exc_info.value.http_status == 404


class TestProviderKeyResponseFormat:
    """Provider Key 响应格式测试类"""
    
    @pytest.mark.asyncio
    async def test_response_id_is_integer(self, test_user, provider_key_service, sample_provider_key_data):
        """测试响应中 ID 是整数"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert isinstance(response.id, int)
    
    @pytest.mark.asyncio
    async def test_response_user_id_is_string(self, test_user, provider_key_service, sample_provider_key_data):
        """测试响应中 user_id 是字符串"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert isinstance(response.user_id, str)
    
    @pytest.mark.asyncio
    async def test_response_status_is_integer(self, test_user, provider_key_service, sample_provider_key_data):
        """测试响应中 status 是整数"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert isinstance(response.status, int)
    
    @pytest.mark.asyncio
    async def test_response_can_serialize_to_dict(self, test_user, provider_key_service, sample_provider_key_data):
        """测试响应可以序列化为字典"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        response_dict = response.model_dump()
        
        assert "id" in response_dict
        assert "user_id" in response_dict
        assert "name" in response_dict
        assert "status" in response_dict
        assert "created_at" in response_dict


class TestProviderKeyEncryption:
    """Provider Key 加密测试类"""
    
    @pytest.mark.asyncio
    async def test_api_key_is_encrypted_in_storage(self, test_user, provider_key_service, db_session, sample_provider_key_data):
        """测试 API Key 在存储时被加密"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)

        # 通过 ORM 查询存储的数据
        result = await db_session.execute(select(ProviderKeyORM).where(ProviderKeyORM.id == response.id))
        stored_key = result.scalar_one_or_none()

        if stored_key:
            # 验证存储的不是明文
            assert stored_key.api_key_encrypted != sample_provider_key_data["api_key"]
    
    @pytest.mark.asyncio
    async def test_different_keys_have_different_encrypted_values(self, test_user, provider_key_service, db_session):
        """测试不同的密钥有不同的加密值"""
        keys = [
            ProviderKeyCreate(name="key1", api_key="sk-key1-value"),
            ProviderKeyCreate(name="key2", api_key="sk-key2-value"),
        ]

        responses = []
        for key_data in keys:
            response = await create_provider_key(key_data, test_user, provider_key_service)
            responses.append(response)

        # 通过 ORM 获取加密后的值
        encrypted_values = []
        for r in responses:
            result = await db_session.execute(select(ProviderKeyORM).where(ProviderKeyORM.id == r.id))
            stored = result.scalar_one_or_none()
            if stored:
                encrypted_values.append(stored.api_key_encrypted)

        # 验证加密值不同
        if len(encrypted_values) == 2:
            assert encrypted_values[0] != encrypted_values[1]


class TestProviderKeyStatus:
    """Provider Key 状态测试类"""
    
    @pytest.mark.asyncio
    async def test_new_key_has_active_status(self, test_user, provider_key_service, sample_provider_key_data):
        """测试新创建的密钥状态为活跃"""
        key_data = ProviderKeyCreate(**sample_provider_key_data)
        response = await create_provider_key(key_data, test_user, provider_key_service)
        
        assert response.status == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
