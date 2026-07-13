"""
Redis 连接管理

提供异步 Redis 连接池和客户端管理
"""
import redis.asyncio as redis
from typing import Optional
from app.logger_mgr import get_logger

logger = get_logger("app.db.redis")


class RedisManager:
    """Redis 连接管理类"""
    
    def __init__(self):
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
    
    async def connect(self, url: str):
        """
        初始化 Redis 连接
        
        Args:
            url: Redis 连接 URL，如 redis://localhost:6379/0
        """
        try:
            self.pool = redis.ConnectionPool.from_url(
                url,
                decode_responses=True,
                max_connections=10
            )
            self.client = redis.Redis(connection_pool=self.pool)
            
            # 测试连接
            await self.client.ping()
            logger.info(f"Redis connected successfully to {url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    async def disconnect(self):
        """关闭 Redis 连接"""
        try:
            if self.client:
                await self.client.aclose()
                self.client = None
            if self.pool:
                await self.pool.disconnect()
                self.pool = None
            logger.info("Redis disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {str(e)}")
    
    def get_client(self) -> redis.Redis:
        """
        获取 Redis 客户端
        
        Returns:
            Redis 客户端实例
            
        Raises:
            RuntimeError: 当 Redis 未连接时
        """
        if not self.client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self.client
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 表示永不过期
            
        Returns:
            是否设置成功
        """
        client = self.get_client()
        if ttl:
            return await client.setex(key, ttl, value)
        return await client.set(key, value)
    
    async def get(self, key: str) -> Optional[str]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在时返回 None
        """
        client = self.get_client()
        return await client.get(key)
    
    async def delete(self, key: str) -> int:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            删除的键数量
        """
        client = self.get_client()
        return await client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            键是否存在
        """
        client = self.get_client()
        return await client.exists(key) > 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        设置键的过期时间
        
        Args:
            key: 缓存键
            ttl: 过期时间（秒）
            
        Returns:
            是否设置成功
        """
        client = self.get_client()
        return await client.expire(key, ttl)
    
    async def ttl(self, key: str) -> int:
        """
        获取键的剩余过期时间
        
        Args:
            key: 缓存键
            
        Returns:
            剩余秒数，-1 表示永不过期，-2 表示键不存在
        """
        client = self.get_client()
        return await client.ttl(key)


# 全局 Redis 管理器实例
redis_manager = RedisManager()
