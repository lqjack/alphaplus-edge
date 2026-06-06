import time
import threading
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

class RateLimiter:
    """限流器核心类，提供信号量和令牌桶两种策略"""
    
    _instances = {} # 用于实现限流器的单例模式，确保同一配置的装饰器共享一个限流器
    _lock = threading.Lock()

    def __new__(cls, strategy='semaphore', max_workers=50, rate=10, capacity=10):
        # 实现单例模式，保证相同参数的限流器是同一个实例
        key = (strategy, max_workers, rate, capacity)
        if key not in cls._instances:
            with cls._lock:
                if key not in cls._instances:
                    cls._instances[key] = super(RateLimiter, cls).__new__(cls)
                    cls._instances[key]._initialized = False
        return cls._instances[key]

    def __init__(self, strategy='semaphore', max_workers=50, rate=10, capacity=10):
        if getattr(self, '_initialized', False):
            return
            
        self.strategy = strategy
        self.max_workers = max_workers
        self.rate = rate  # 令牌生成速率（个/秒）
        self.capacity = capacity  # 令牌桶容量
        self.tokens = capacity  # 当前令牌数量
        self.last_check = time.time() # 上次令牌更新时间戳
        self._lock = threading.Lock() # 保护令牌桶操作的锁
        
        if strategy == 'semaphore':
            # 使用线程池限制并发数[1,5](@ref)
            self.semaphore = threading.Semaphore(max_workers)
        elif strategy == 'token_bucket':
            # 令牌桶算法相关初始化[7](@ref)
            pass
            
        self._initialized = True

    def acquire(self):
        """获取许可"""
        if self.strategy == 'semaphore':
            return self.semaphore.acquire(blocking=False)
        elif self.strategy == 'token_bucket':
            return self._token_bucket_acquire()
        return True

    def release(self):
        """释放许可（仅信号量策略需要）"""
        if self.strategy == 'semaphore':
            self.semaphore.release()

    def _token_bucket_acquire(self):
        """令牌桶算法实现[7](@ref)"""
        with self._lock:
            now = time.time()
            time_passed = now - self.last_check
            self.last_check = now
            
            # 计算这段时间内生成的令牌数
            new_tokens = time_passed * self.rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

def rate_limit(strategy='semaphore', max_workers=50, rate=10, capacity=10):
    """
    限流装饰器工厂函数
    
    参数:
        strategy: 限流策略，'semaphore'（信号量）或'token_bucket'（令牌桶）
        max_workers: 信号量策略下的最大并发数
        rate: 令牌桶策略的令牌生成速率（个/秒）
        capacity: 令牌桶的容量
    """
    limiter = RateLimiter(strategy, max_workers, rate, capacity)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not limiter.acquire():
                # 获取许可失败时抛出异常或等待
                raise Exception(f"Rate limit exceeded for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # 信号量策略需要手动释放
                if strategy == 'semaphore':
                    limiter.release()
        return wrapper
    return decorator