# core/config/rate_limiter_config.py
import os
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

class RateLimiterStrategy(Enum):
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    REDIS_TOKEN_BUCKET = "redis_token_bucket"

@dataclass
class RateLimiterConfig:
    strategy: RateLimiterStrategy
    max_workers: int
    rate: float  # 每秒允许的请求数
    capacity: int  # 桶容量
    time_window: int  # 时间窗口(秒)
    cluster_enabled: bool
    redis_key_prefix: str
    redis_config: Dict[str, Any]
    
    @classmethod
    def from_env(cls) -> 'RateLimiterConfig':
        """从环境变量加载配置"""
        return cls(
            strategy=RateLimiterStrategy(
                os.getenv('RATE_LIMITER_STRATEGY', 'token_bucket')
            ),
            max_workers=int(os.getenv('RATE_LIMITER_MAX_WORKERS', '50')),
            rate=float(os.getenv('RATE_LIMITER_RATE', '10')),
            capacity=int(os.getenv('RATE_LIMITER_CAPACITY', '20')),
            time_window=int(os.getenv('RATE_LIMITER_TIME_WINDOW', '60')),
            cluster_enabled=os.getenv('RATE_LIMITER_CLUSTER_ENABLED', 'false').lower() == 'true',
            redis_key_prefix=os.getenv('RATE_LIMITER_REDIS_KEY_PREFIX', 'rate_limiter'),
            redis_config={
                'host': os.getenv('REDIS_HOST', 'localhost'),
                'port': int(os.getenv('REDIS_PORT', '6379')),
                'password': os.getenv('REDIS_PASSWORD', ''),
                'db': int(os.getenv('REDIS_DB', '0')),
                'decode_responses': True
            }
        )