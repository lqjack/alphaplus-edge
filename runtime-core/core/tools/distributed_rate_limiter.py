# core/decorators/distributed_rate_limiter.py
import functools
import inspect
from typing import Callable, Optional
from core.tools.factory import RateLimiterFactory
from core.tools.rate_limiter_config import RateLimiterConfig

def distributed_rate_limiter(
    key: Optional[str] = None,
    strategy: Optional[str] = None,
    rate: Optional[float] = None,
    capacity: Optional[int] = None,
    time_window: Optional[int] = None
):
    """
    分布式限流装饰器[3,4](@ref)
    
    参数:
        key: 限流键，默认为函数名
        strategy: 限流策略
        rate: 令牌生成速率
        capacity: 桶容量
        time_window: 时间窗口
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _rate_limit_wrapper(func, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _rate_limit_wrapper(func, *args, **kwargs)
        
        def _rate_limit_wrapper(func, *args, **kwargs):
            # 获取配置
            config = RateLimiterConfig.from_env()
            
            # 覆盖装饰器参数
            if strategy:
                from core.config.rate_limiter_config import RateLimiterStrategy
                config.strategy = RateLimiterStrategy(strategy)
            if rate:
                config.rate = rate
            if capacity:
                config.capacity = capacity
            if time_window:
                config.time_window = time_window
            
            # 生成限流键
            limiter_key = key or f"{func.__module__}.{func.__name__}"
            
            # 创建限流器
            limiter = RateLimiterFactory.create_limiter(config)
            
            # 尝试获取令牌
            if inspect.iscoroutinefunction(func):
                async def async_inner():
                    if not await limiter.try_acquire(limiter_key):
                        from core.exceptions import RateLimitExceededError
                        raise RateLimitExceededError("Rate limit exceeded")
                    return await func(*args, **kwargs)
                return async_inner()
            else:
                import asyncio
                if not asyncio.run(limiter.try_acquire(limiter_key)):
                    from core.exceptions import RateLimitExceededError
                    raise RateLimitExceededError("Rate limit exceeded")
                return func(*args, **kwargs)
        
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    return decorator