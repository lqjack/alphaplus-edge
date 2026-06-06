# core/rate_limiter/base.py
from abc import ABC, abstractmethod
from typing import Optional
import time

class BaseRateLimiter(ABC):
    """限流器基础接口"""
    
    @abstractmethod
    def acquire(self, key: str, tokens: int = 1) -> bool:
        """获取令牌"""
        pass
    
    @abstractmethod
    def try_acquire(self, key: str, tokens: int = 1, timeout: float = 0) -> bool:
        """尝试获取令牌"""
        pass
    
    @abstractmethod
    def get_remaining_tokens(self, key: str) -> int:
        """获取剩余令牌数"""
        pass
