"""
Provider Key 服务测试用例

测试 ProviderKeyService 的所有方法
使用 Mock 数据库进行测试
"""
import pytest

from app.models.provider_key import ProviderKey
from app.core.security import encrypt_api_key, decrypt_api_key
from app.config import get_settings


class TestProviderKeyService:
    """Provider Key 服务测试类"""
    
    @pytest.mark.asyncio
    async def test_create_provider_key(self, provider_key_service):
        """测试创建 Provider Key"""
        user_id = "user_001"
        key_data = {
            "name": "openai",
            "api_key": "sk-test-api-key-12345"
        }
        
        provider_key = await provider_key_service.create_provider_key(user_id, key_data)
        
        assert provider_key is not None
        assert isinstance(provider_key, ProviderKey)
        assert provider_key.user_id == user_id
        assert provider_key.name == "openai"
        assert provider_key.status == 1
        assert provider_key.api_key_encrypted is not None
        # 验证加密后的密钥不等于原始密钥
        assert provider_key.api_key_encrypted != "sk-test-api-key-12345"
    
    @pytest.mark.asyncio
    async def test_create_multiple_provider_keys(self, provider_key_service):
        """测试创建多个 Provider Key"""
        user_id = "user_001"
        
        # 创建 OpenAI key
        key1 = await provider_key_service.create_provider_key(user_id, {
            "name": "openai",
            "api_key": "sk-openai-key"
        })
        
        # 创建 Anthropic key
        key2 = await provider_key_service.create_provider_key(user_id, {
            "name": "anthropic",
            "api_key": "sk-anthropic-key"
        })
        
        assert key1 is not None
        assert key2 is not None
        assert key1.id != key2.id
        assert key1.name == "openai"
        assert key2.name == "anthropic"
    
    @pytest.mark.asyncio
    async def test_get_provider_keys_by_user(self, provider_key_service):
        """测试获取用户所有 Provider Key"""
        user_id = "user_001"
        
        # 创建多个 key
        await provider_key_service.create_provider_key(user_id, {"name": "key1", "api_key": "sk-1"})
        await provider_key_service.create_provider_key(user_id, {"name": "key2", "api_key": "sk-2"})
        await provider_key_service.create_provider_key(user_id, {"name": "key3", "api_key": "sk-3"})
        
        # 获取用户所有 key
        keys = await provider_key_service.get_provider_keys_by_user(user_id)
        
        assert len(keys) >= 3
        assert all(k.user_id == user_id for k in keys)
    
    @pytest.mark.asyncio
    async def test_get_provider_keys_by_user_empty(self, provider_key_service):
        """测试获取无 Provider Key 用户的密钥列表"""
        keys = await provider_key_service.get_provider_keys_by_user("user_no_keys")
        
        assert keys == []
    
    @pytest.mark.asyncio
    async def test_get_provider_key_by_id(self, provider_key_service):
        """测试通过ID获取 Provider Key"""
        user_id = "user_001"
        created_key = await provider_key_service.create_provider_key(user_id, {
            "name": "test_key",
            "api_key": "sk-test"
        })
        
        found_key = await provider_key_service.get_provider_key_by_id(created_key.id)
        
        assert found_key is not None
        assert found_key.id == created_key.id
        assert found_key.name == "test_key"
    
    @pytest.mark.asyncio
    async def test_get_provider_key_by_id_not_exists(self, provider_key_service):
        """测试通过ID获取不存在的 Provider Key"""
        found_key = await provider_key_service.get_provider_key_by_id(99999)
        
        assert found_key is None
    
    @pytest.mark.asyncio
    async def test_get_provider_key_by_name(self, provider_key_service):
        """测试通过用户ID和名称获取 Provider Key"""
        user_id = "user_001"
        await provider_key_service.create_provider_key(user_id, {
            "name": "openai",
            "api_key": "sk-openai-key"
        })
        
        found_key = await provider_key_service.get_provider_key_by_name(user_id, "openai")
        
        assert found_key is not None
        assert found_key.name == "openai"
        assert found_key.user_id == user_id
    
    @pytest.mark.asyncio
    async def test_get_provider_key_by_name_not_exists(self, provider_key_service):
        """测试通过名称获取不存在的 Provider Key"""
        found_key = await provider_key_service.get_provider_key_by_name("user_001", "nonexistent")
        
        assert found_key is None
    
    @pytest.mark.asyncio
    async def test_delete_provider_key(self, provider_key_service):
        """测试删除 Provider Key"""
        user_id = "user_001"
        created_key = await provider_key_service.create_provider_key(user_id, {
            "name": "to_delete",
            "api_key": "sk-to-delete"
        })
        
        result = await provider_key_service.delete_provider_key(created_key.id)
        
        assert result is True
        
        # 验证已删除
        found_key = await provider_key_service.get_provider_key_by_id(created_key.id)
        assert found_key is None
    
    @pytest.mark.asyncio
    async def test_delete_provider_key_not_exists(self, provider_key_service):
        """测试删除不存在的 Provider Key"""
        result = await provider_key_service.delete_provider_key(99999)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_decrypt_provider_key(self, provider_key_service):
        """测试解密 Provider Key"""
        user_id = "user_001"
        original_api_key = "sk-original-api-key-12345"
        created_key = await provider_key_service.create_provider_key(user_id, {
            "name": "decrypt_test",
            "api_key": original_api_key
        })
        
        # 解密
        decrypted = provider_key_service.decrypt_provider_key(created_key.api_key_encrypted)
        
        assert decrypted == original_api_key
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key(self, provider_key_service):
        """测试获取解密后的 API Key"""
        user_id = "user_001"
        original_api_key = "sk-decrypted-key-test"
        created_key = await provider_key_service.create_provider_key(user_id, {
            "name": "decrypted_test",
            "api_key": original_api_key
        })
        
        decrypted = await provider_key_service.get_decrypted_key(created_key.id)
        
        assert decrypted == original_api_key
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_not_exists(self, provider_key_service):
        """测试获取不存在的解密后的 API Key"""
        decrypted = await provider_key_service.get_decrypted_key(99999)
        
        assert decrypted is None
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_by_name(self, provider_key_service):
        """测试通过用户ID和名称获取解密后的 API Key"""
        user_id = "user_001"
        original_api_key = "sk-by-name-test-key"
        await provider_key_service.create_provider_key(user_id, {
            "name": "by_name_test",
            "api_key": original_api_key
        })
        
        decrypted = await provider_key_service.get_decrypted_key_by_name(user_id, "by_name_test")
        
        assert decrypted == original_api_key
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_by_name_not_exists(self, provider_key_service):
        """测试通过名称获取不存在的解密后的 API Key"""
        decrypted = await provider_key_service.get_decrypted_key_by_name("user_001", "nonexistent")
        
        assert decrypted is None
    
    @pytest.mark.asyncio
    async def test_encryption_decryption_consistency(self, provider_key_service):
        """测试加密和解密的一致性"""
        user_id = "user_001"
        test_keys = [
            "sk-simple-key",
            "sk-key-with-special-chars-!@#$%^&*()",
            "sk-very-long-key-" + "x" * 100,
            "sk-中文密钥测试",
        ]
        
        for original_key in test_keys:
            created = await provider_key_service.create_provider_key(user_id, {
                "name": f"test_{hash(original_key)}",
                "api_key": original_key
            })
            decrypted = provider_key_service.decrypt_provider_key(created.api_key_encrypted)
            assert decrypted == original_key, f"Failed for key: {original_key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
