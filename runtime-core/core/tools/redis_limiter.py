# core/rate_limiter/redis_limiter.py
import time

from typing import Optional
from .base import BaseRateLimiter
from core.tools.rate_limiter_config import RateLimiterConfig

class RedisRateLimiter(BaseRateLimiter):
    """基于Redis的分布式限流器[1,2](@ref)"""
    
    def __init__(self, config: RateLimiterConfig):
        self.config = config
        import redis
        self.redis = redis.Redis(**config.redis_config)
        self.lua_scripts = {}
        self._load_lua_scripts()
    
    def _load_lua_scripts(self):
        """加载Lua脚本保证原子性[1](@ref)"""
        # 令牌桶算法Lua脚本
        token_bucket_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local tokens_requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        local cost = tonumber(ARGV[5])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = capacity
        local last_refill = now
        
        if bucket[1] then
            tokens = tonumber(bucket[1])
            last_refill = tonumber(bucket[2])
            
            -- 计算需要补充的令牌
            local time_passed = now - last_refill
            local tokens_to_add = time_passed * rate
            tokens = math.min(capacity, tokens + tokens_to_add)
            last_refill = now
        end
        
        local result = 0
        if tokens >= tokens_requested then
            tokens = tokens - tokens_requested
            result = 1
        end
        
        -- 更新桶状态
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
        redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
        
        return result
        """
        self.lua_scripts['token_bucket'] = self.redis.register_script(token_bucket_script)
        
        # 固定窗口算法Lua脚本[1](@ref)
        fixed_window_script = """
        local key = KEYS[1]
        local window = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local cost = tonumber(ARGV[3])
        
        local current = redis.call('GET', key)
        if current and tonumber(current) >= limit then
            return 0
        end
        
        local result = redis.call('INCRBY', key, cost)
        if tonumber(result) == cost then
            redis.call('EXPIRE', key, window)
        end
        
        return 1
        """
        self.lua_scripts['fixed_window'] = self.redis.register_script(fixed_window_script)
    
    def acquire(self, key: str, tokens: int = 1) -> bool:
        full_key = f"{self.config.redis_key_prefix}:{key}"
        
        if self.config.strategy == RateLimiterStrategy.REDIS_TOKEN_BUCKET:
            return self._acquire_token_bucket(full_key, tokens)
        else:
            return self._acquire_fixed_window(full_key, tokens)
    
    def _acquire_token_bucket(self, key: str, tokens: int) -> bool:
        """令牌桶算法获取[2](@ref)"""
        now = time.time()
        result = self.lua_scripts['token_bucket'](
            keys=[key],
            args=[self.config.rate, self.config.capacity, tokens, now, 1]
        )
        return bool(result)
    
    def _acquire_fixed_window(self, key: str, tokens: int) -> bool:
        """固定窗口算法获取[1](@ref)"""
        result = self.lua_scripts['fixed_window'](
            keys=[key],
            args=[self.config.time_window, self.config.capacity, tokens]
        )
        return bool(result)
    
    def try_acquire(self, key: str, tokens: int = 1, timeout: float = 0) -> bool:
        start_time = time.time()
        
        while True:
            if self.acquire(key, tokens):
                return True
            
            if timeout > 0 and (time.time() - start_time) >= timeout:
                return False
            
            time.sleep(0.1)
    
    def get_remaining_tokens(self, key: str) -> int:
        full_key = f"{self.config.redis_key_prefix}:{key}"
        
        if self.config.strategy == RateLimiterStrategy.REDIS_TOKEN_BUCKET:
            bucket = self.redis.hgetall(full_key)
            if bucket:
                return int(float(bucket.get(b'tokens', 0)))
            return self.config.capacity
        else:
            current = self.redis.get(full_key)
            remaining = self.config.capacity - (int(current) if current else 0)
            return max(0, remaining)
