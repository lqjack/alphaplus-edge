# core/rate_limiter/token_bucket_limiter.py
import time
import time
from threading import Lock
from typing import Dict, Tuple
from .base import BaseRateLimiter
from core.tools.rate_limiter_config import RateLimiterConfig

class TokenBucketRateLimiter(BaseRateLimiter):
    """单机令牌桶限流器[2](@ref)"""
    
    def __init__(self, config: RateLimiterConfig):
        self.config = config
        self.buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self.locks: Dict[str, Lock] = {}
        self.global_lock = Lock()
    
    def _get_bucket(self, key: str) -> Tuple[float, float]:
        """获取或创建令牌桶"""
        with self.global_lock:
            if key not in self.locks:
                self.locks[key] = Lock()
            if key not in self.buckets:
                self.buckets[key] = (self.config.capacity, time.time())
        
        return self.buckets[key]
    
    def _refill_tokens(self, key: str, current_time: float) -> float:
        """补充令牌"""
        tokens, last_refill = self._get_bucket(key)
        
        # 计算需要补充的令牌数
        time_passed = current_time - last_refill
        tokens_to_add = time_passed * self.config.rate
        
        # 更新令牌数（不超过容量）
        new_tokens = min(self.config.capacity, tokens + tokens_to_add)
        self.buckets[key] = (new_tokens, current_time)
        
        return new_tokens
    
    def acquire(self, key: str, tokens: int = 1) -> bool:
        """获取令牌（阻塞方式）"""
        start_time = time.time()
        
        while True:
            if self.try_acquire(key, tokens, 0):
                return True
            
            # 等待一段时间再重试
            time.sleep(0.1)
            
            # 超时控制
            if time.time() - start_time > 30:  # 最大等待30秒
                return False
    
    def try_acquire(self, key: str, tokens: int = 1, timeout: float = 0) -> bool:
        """尝试获取令牌[2](@ref)"""
        if tokens > self.config.capacity:
            return False
        
        start_time = time.time()
        current_time = time.time()
        
        # 确保锁和桶都已初始化
        self._get_bucket(key)
        
        with self.locks[key]:
            available_tokens = self._refill_tokens(key, current_time)
            
            if available_tokens >= tokens:
                # 有足够令牌，直接消费
                self.buckets[key] = (
                    available_tokens - tokens, 
                    self.buckets[key][1]
                )
                return True
            elif timeout > 0:
                # 计算需要等待的时间
                tokens_needed = tokens - available_tokens
                wait_time = tokens_needed / self.config.rate
                
                if time.time() + wait_time - start_time <= timeout:
                    time.sleep(wait_time)
                    return self.try_acquire(key, tokens, timeout - wait_time)
            
            return False
    
    def get_remaining_tokens(self, key: str) -> int:
        """获取剩余令牌数"""
        current_time = time.time()
        with self.locks[key]:
            tokens = self._refill_tokens(key, current_time)
            return int(tokens)
