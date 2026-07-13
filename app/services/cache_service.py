"""
缓存服务模块

提供路由配置缓存的读写操作，基于 Redis 实现
Service 层通过构造函数接收 redis 客户端依赖，不在内部获取
"""
import json
from typing import Optional, Dict, Any

from redis.asyncio import Redis

from app.config import get_settings


class CacheService:
    """缓存服务类
    
    提供路由配置的缓存读写和失效操作
    """
    
    def __init__(self, redis: Redis):
        """
        初始化缓存服务
        
        Args:
            redis: Redis 客户端
        """
        self.redis = redis
        self.settings = get_settings()
        self.prefix = "route_config:"
    
    async def get_route_config(self, tool_token_hash: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取路由配置
        
        Args:
            tool_token_hash: 工具令牌的哈希值
            
        Returns:
            路由配置字典，不存在时返回 None
        """
        key = f"{self.prefix}{tool_token_hash}"
        data = await self.redis.get(key)
        if not data:
            return None
        config = json.loads(data)
        return config
    
    async def set_route_config(self, tool_token_hash: str, config: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        设置路由配置缓存
        
        Args:
            tool_token_hash: 工具令牌的哈希值
            config: 路由配置字典
            ttl: 缓存过期时间（秒），None 时使用默认配置
        """
        key = f"{self.prefix}{tool_token_hash}"
        cache_ttl = ttl or self.settings.redis_cache_ttl
        await self.redis.setex(key, cache_ttl, json.dumps(config))
    
    async def invalidate_route_config(self, tool_token_hash: str) -> None:
        """
        使路由配置缓存失效
        
        Args:
            tool_token_hash: 工具令牌的哈希值
        """
        key = f"{self.prefix}{tool_token_hash}"
        await self.redis.delete(key)
    
    async def invalidate_route_configs_batch(self, tool_token_hashes: list[str]) -> None:
        """
        批量使路由配置缓存失效
        
        Args:
            tool_token_hashes: 工具令牌哈希值列表
        """
        if not tool_token_hashes:
            return
        keys = [f"{self.prefix}{token_hash}" for token_hash in tool_token_hashes]
        await self.redis.delete(*keys)
    
    async def invalidate_all_route_configs(self) -> int:
        """
        使所有路由配置缓存失效
        
        注意：此方法会删除所有路由配置缓存，谨慎使用
        
        Returns:
            int: 删除的缓存数量
        """
        pattern = f"{self.prefix}*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)
        return len(keys)
    
    def build_route_config(self, tool: Dict[str, Any], provider_key: str) -> Dict[str, Any]:
        """
        构建缓存数据结构 v3.0

        根据工具配置和解密后的 API 密钥构建完整的路由配置

        Args:
            tool: 工具配置字典，包含 id, name, user_id, api_type, routes, active_route_name 等字段
            provider_key: 解密后的 API 密钥

        Returns:
            路由配置字典，包含代理请求所需的全部信息
        """
        active_route_name = tool.get("active_route_name")
        routes = tool.get("routes", {})
        active_route = routes.get(active_route_name, {})

        config = {
            "tool_id": tool.get("id"),
            "tool_name": tool.get("name"),
            "user_id": tool.get("user_id"),
            "active_route_name": active_route_name,
            "provider_key_name": active_route.get("provider_key_name"),
            "base_url": active_route.get("base_url"),
            "model": active_route.get("model"),
            "api_type": tool.get("api_type", "openai_chat"),  # v3.0: 从 Tool 级别获取
            "api_key": provider_key
        }
        return config
