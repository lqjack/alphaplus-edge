"""
A robust caching system with support for expiration and multiple backends.
"""
import os
import pickle
import time
import threading
from pathlib import Path
from typing import Any, Optional, Union
import logging
from functools import wraps

logger = logging.getLogger(__name__)

import abc

class CacheBackend(abc.ABC):
    """Base class for cache backends using ABC for interface enforcement."""
    
    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
        
    @abc.abstractmethod
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache."""
        pass
        
    @abc.abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass

class MemoryCache(CacheBackend):
    """In-memory cache backend"""
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._cache.get(key)
            if item is None:
                return None
                
            value, expire_time = item
            if expire_time and time.time() > expire_time:
                del self._cache[key]
                return None
            return value
            
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        with self._lock:
            expire_time = time.time() + expire if expire else None
            self._cache[key] = (value, expire_time)
            return True
            
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

class DiskCache(CacheBackend):
    """Disk-based cache backend"""
    def __init__(self, cache_dir: Optional[str] = None):
        from core.tools.files import get_cache_directory
        self.cache_dir = Path(cache_dir or get_cache_directory()) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        
    def _get_cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{hash(key)}.cache"
        
    def get(self, key: str) -> Optional[Any]:
        cache_file = self._get_cache_path(key)
        if not cache_file.exists():
            return None
            
        try:
            with self._lock, open(cache_file, 'rb') as f:
                data = pickle.load(f)
                value, expire_time = data
                if expire_time and time.time() > expire_time:
                    cache_file.unlink(missing_ok=True)
                    return None
                return value
        except Exception as e:
            logger.warning(f"Failed to read cache {key}: {e}")
            return None
            
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        cache_file = self._get_cache_path(key)
        expire_time = time.time() + expire if expire else None
        data = (value, expire_time)
        
        try:
            with self._lock, open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            logger.warning(f"Failed to write cache {key}: {e}")
            return False
            
    def delete(self, key: str) -> bool:
        cache_file = self._get_cache_path(key)
        try:
            with self._lock:
                cache_file.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete cache {key}: {e}")
            return False

# Default cache backend (memory)
_default_backend = DiskCache()

def get_cache(key: str, backend: Optional[CacheBackend] = None) -> Optional[Any]:
    """
    Get cached value by key.
    
    Args:
        key: Cache key
        backend: Cache backend instance (default: memory cache)
        
    Returns:
        Cached value or None if not found/expired
    """
    backend = backend or _default_backend
    try:
        return backend.get(key)
    except Exception as e:
        logger.warning(f"Cache get failed for {key}: {e}")
        return None

def set_cache(
    key: str, 
    value: Any, 
    expire: Optional[int] = None, 
    backend: Optional[CacheBackend] = None
) -> bool:
    """
    Set cache value.
    
    Args:
        key: Cache key
        value: Value to cache
        expire: Expiration time in seconds
        backend: Cache backend instance (default: memory cache)
        
    Returns:
        True if successful, False otherwise
    """
    backend = backend or _default_backend
    try:
        return backend.set(key, value, expire)
    except Exception as e:
        logger.warning(f"Cache set failed for {key}: {e}")
        return False

def delete_cache(key: str, backend: Optional[CacheBackend] = None) -> bool:
    """
    Delete cached value.
    
    Args:
        key: Cache key
        backend: Cache backend instance (default: memory cache)
        
    Returns:
        True if successful, False otherwise
    """
    backend = backend or _default_backend
    try:
        return backend.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete failed for {key}: {e}")
        return False

def cached(
    expire: Optional[int] = None,
    key_func: Optional[callable] = None,
    backend: Optional[CacheBackend] = None
):
    """
    Decorator to cache function results.
    
    Args:
        expire: Cache expiration in seconds
        key_func: Function to generate cache key from args/kwargs
        backend: Cache backend instance
        
    Example:
        @cached(expire=3600)
        def expensive_function(param):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_func(*args, **kwargs) if key_func else \
                f"{func.__module__}.{func.__name__}:{args}:{kwargs}"
                
            cached_value = get_cache(cache_key, backend)
            if cached_value is not None:
                return cached_value
                
            result = func(*args, **kwargs)
            set_cache(cache_key, result, expire, backend)
            return result
        return wrapper
    return decorator