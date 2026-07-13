"""
缓存服务测试用例

测试 CacheService 的所有方法
使用 Mock Redis 进行测试
"""
import pytest
import json
from unittest.mock import AsyncMock


class TestCacheService:
    """缓存服务测试类"""
    
    @pytest.mark.asyncio
    async def test_get_route_config_exists(self, cache_service, mock_redis):
        """测试获取存在的路由配置缓存"""
        token_hash = "test_token_hash_123"
        cached_config = {
            "tool_id": 1,
            "tool_name": "测试工具",
            "user_id": "user_001",
            "provider_key_name": "openai",
            "base_url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4",
            "api_key": "sk-test-key"
        }
        
        # 设置 mock 返回值
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_config))
        
        result = await cache_service.get_route_config(token_hash)
        
        assert result is not None
        assert result["tool_id"] == 1
        assert result["provider_key_name"] == "openai"
        mock_redis.get.assert_called_once_with(f"route_config:{token_hash}")
    
    @pytest.mark.asyncio
    async def test_get_route_config_not_exists(self, cache_service, mock_redis):
        """测试获取不存在的路由配置缓存"""
        token_hash = "nonexistent_hash"
        
        # 设置 mock 返回 None
        mock_redis.get = AsyncMock(return_value=None)
        
        result = await cache_service.get_route_config(token_hash)
        
        assert result is None
        mock_redis.get.assert_called_once_with(f"route_config:{token_hash}")
    
    @pytest.mark.asyncio
    async def test_set_route_config(self, cache_service, mock_redis):
        """测试设置路由配置缓存"""
        token_hash = "test_token_hash_456"
        config = {
            "tool_id": 2,
            "tool_name": "另一个工具",
            "provider_key_name": "anthropic"
        }
        
        await cache_service.set_route_config(token_hash, config)
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"route_config:{token_hash}"
        assert call_args[0][2] == json.dumps(config)
    
    @pytest.mark.asyncio
    async def test_set_route_config_with_custom_ttl(self, cache_service, mock_redis):
        """测试使用自定义 TTL 设置路由配置缓存"""
        token_hash = "test_token_hash_789"
        config = {"tool_id": 3}
        custom_ttl = 7200
        
        await cache_service.set_route_config(token_hash, config, ttl=custom_ttl)
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_invalidate_route_config(self, cache_service, mock_redis):
        """测试使路由配置缓存失效"""
        token_hash = "test_token_hash_to_delete"
        
        await cache_service.invalidate_route_config(token_hash)
        
        mock_redis.delete.assert_called_once_with(f"route_config:{token_hash}")
    
    def test_build_route_config(self, cache_service):
        """测试构建路由配置数据结构"""
        tool = {
            "id": 1,
            "name": "测试工具",
            "user_id": "user_001",
            "active_route_name": "default",
            "routes": {
                "default": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                }
            }
        }
        provider_key = "sk-decrypted-api-key"
        
        config = cache_service.build_route_config(tool, provider_key)
        
        assert config["tool_id"] == 1
        assert config["tool_name"] == "测试工具"
        assert config["user_id"] == "user_001"
        assert config["active_route_name"] == "default"
        assert config["provider_key_name"] == "openai"
        assert config["base_url"] == "https://api.openai.com/v1/chat/completions"
        assert config["model"] == "gpt-4"
        assert config["api_key"] == provider_key
    
    def test_build_route_config_no_active_route(self, cache_service):
        """测试构建无激活路由的配置"""
        tool = {
            "id": 2,
            "name": "无激活路由工具",
            "user_id": "user_002",
            "active_route_name": None,
            "routes": {}
        }
        provider_key = "sk-key"
        
        config = cache_service.build_route_config(tool, provider_key)
        
        assert config["tool_id"] == 2
        assert config["active_route_name"] is None
        assert config["provider_key_name"] is None
        assert config["base_url"] is None
    
    def test_build_route_config_missing_active_route(self, cache_service):
        """测试构建激活路由名称不存在于 routes 中的配置"""
        tool = {
            "id": 3,
            "name": "路由不匹配工具",
            "user_id": "user_003",
            "active_route_name": "nonexistent",
            "routes": {
                "default": {
                    "base_url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4",
                    "provider_key_name": "openai"
                }
            }
        }
        provider_key = "sk-key"
        
        config = cache_service.build_route_config(tool, provider_key)
        
        assert config["active_route_name"] == "nonexistent"
        assert config["provider_key_name"] is None  # 因为找不到 nonexistent 路由
    
    @pytest.mark.asyncio
    async def test_cache_key_prefix(self, cache_service, mock_redis):
        """测试缓存键前缀"""
        token_hash = "test_hash"
        
        # 验证 get 使用正确的前缀
        mock_redis.get = AsyncMock(return_value=None)
        await cache_service.get_route_config(token_hash)
        mock_redis.get.assert_called_with("route_config:test_hash")
        
        # 验证 delete 使用正确的前缀
        await cache_service.invalidate_route_config(token_hash)
        mock_redis.delete.assert_called_with("route_config:test_hash")
    
    @pytest.mark.asyncio
    async def test_json_serialization(self, cache_service, mock_redis):
        """测试 JSON 序列化和反序列化"""
        token_hash = "json_test_hash"
        complex_config = {
            "tool_id": 1,
            "nested": {
                "key": "value",
                "list": [1, 2, 3]
            },
            "unicode": "中文测试",
            "number": 123.456,
            "boolean": True,
            "null": None
        }
        
        # 测试序列化（set）
        await cache_service.set_route_config(token_hash, complex_config)
        call_args = mock_redis.setex.call_args
        serialized = call_args[0][2]
        
        # 验证可以正确反序列化
        deserialized = json.loads(serialized)
        assert deserialized == complex_config
        
        # 测试反序列化（get）
        mock_redis.get = AsyncMock(return_value=json.dumps(complex_config))
        result = await cache_service.get_route_config(token_hash)
        assert result == complex_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
