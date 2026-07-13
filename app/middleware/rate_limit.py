"""
限流中间件

基于 Tool Token 的限流，使用 Redis 存储计数
支持滑动窗口算法和令牌桶算法
"""
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.redis import redis_manager
from app.core.security import hash_tool_token
from app.core.exceptions import APIException
from app.core.error_codes import ErrorCode


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件
    
    使用Redis实现滑动窗口限流算法
    """

    def __init__(self, app, requests_per_minute: int = 60, enabled: bool = True):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 窗口大小：60秒
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 仅对数据面接口进行限流
        if not self.enabled or not request.url.path.startswith("/v1"):
            response = await call_next(request)
            return response

        # 提取Tool Token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            response = await call_next(request)
            return response

        tool_token = auth_header.replace("Bearer ", "")
        token_hash = hash_tool_token(tool_token)

        # 检查限流
        is_allowed = await self._check_rate_limit(token_hash)
        if not is_allowed:
            raise APIException(code=ErrorCode.RATE_LIMIT_EXCEEDED)

        response = await call_next(request)
        return response

    async def _check_rate_limit(self, identifier: str) -> bool:
        """
        检查是否超过限流
        
        使用滑动窗口算法
        """
        try:
            redis = redis_manager.get_client()
        except RuntimeError:
            return True  # Redis不可用时不限流

        key = f"rate_limit:{identifier}"
        now = time.time()
        window_start = now - self.window_size

        # 使用Redis Pipeline提高性能
        pipe = redis.pipeline()

        # 1. 移除窗口外的记录
        pipe.zremrangebyscore(key, 0, window_start)

        # 2. 获取当前窗口内的请求数
        pipe.zcard(key)

        # 3. 添加当前请求
        pipe.zadd(key, {str(now): now})

        # 4. 设置过期时间
        pipe.expire(key, self.window_size + 1)

        results = await pipe.execute()
        request_count = results[1]

        is_allowed = request_count < self.requests_per_minute
        return is_allowed


class TokenBucketRateLimiter:
    """
    令牌桶限流器
    
    另一种限流实现方式
    """

    def __init__(self, capacity: int = 100, refill_rate: float = 10.0):
        """
        初始化令牌桶限流器
        
        Args:
            capacity: 桶容量
            refill_rate: 每秒补充的令牌数
        """
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def acquire(self, identifier: str) -> bool:
        """尝试获取令牌"""
        try:
            redis = redis_manager.get_client()
        except RuntimeError:
            return True

        key = f"token_bucket:{identifier}"
        now = time.time()

        # Lua脚本实现原子操作
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now
        
        -- 补充令牌
        local elapsed = now - last_refill
        local refilled = math.min(capacity, tokens + elapsed * refill_rate)
        
        -- 尝试消费一个令牌
        if refilled >= 1 then
            redis.call('HMSET', key, 'tokens', refilled - 1, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            redis.call('HMSET', key, 'tokens', refilled, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
            return 0
        end
        """

        result = await redis.eval(lua_script, 1, key, self.capacity, self.refill_rate, now)
        is_allowed = result == 1
        return is_allowed
