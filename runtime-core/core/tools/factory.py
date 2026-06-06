# core/rate_limiter/factory.py
from typing import Dict, Type
from .base import BaseRateLimiter
from .token_bucket_limiter import TokenBucketRateLimiter
from .redis_limiter import RedisRateLimiter
from core.tools.rate_limiter_config import RateLimiterConfig, RateLimiterStrategy

class RateLimiterFactory:
    """限流器工厂类[3](@ref)"""
    
    _strategies: Dict[RateLimiterStrategy, Type[BaseRateLimiter]] = {
        RateLimiterStrategy.TOKEN_BUCKET: TokenBucketRateLimiter,
        RateLimiterStrategy.FIXED_WINDOW: TokenBucketRateLimiter,  # 复用实现
        RateLimiterStrategy.REDIS_TOKEN_BUCKET: RedisRateLimiter,
    }
    
    @classmethod
    def create_limiter(cls, config: RateLimiterConfig) -> BaseRateLimiter:
        """创建限流器实例"""
        strategy_class = cls._strategies.get(config.strategy)
        if not strategy_class:
            raise ValueError(f"不支持的限流策略: {config.strategy}")
        
        return strategy_class(config)
    
    @classmethod
    def create_default_limiter(cls) -> BaseRateLimiter:
        """创建默认限流器"""
        config = RateLimiterConfig.from_env()
        return cls.create_limiter(config)