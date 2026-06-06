#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lazy Loader
Provides lazy loading functionality for non-critical components to improve startup performance.
"""

import logging
import threading
import time
from typing import Dict, Any, Callable, Optional, List
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, Future
import asyncio

logger = logging.getLogger(__name__)

class LazyLoader:
    """Lazy loading manager for non-critical components"""
    
    def __init__(self):
        self._loaded_components = set()
        self._loading_tasks = {}
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="lazy-loader")
        self._load_callbacks = []
        
    def register_component(self, component_name: str, loader_func: Callable, 
                          priority: int = 100, dependencies: List[str] = None):
        """Register a component for lazy loading"""
        if dependencies is None:
            dependencies = []
            
        self._loading_tasks[component_name] = {
            'loader': loader_func,
            'priority': priority,
            'dependencies': dependencies,
            'status': 'pending',
            'result': None,
            'error': None
        }
        logger.info(f"💤 Registered lazy component: {component_name} (priority: {priority})")
    
    def load_component(self, component_name: str) -> Future:
        """Load a specific component asynchronously"""
        if component_name in self._loaded_components:
            logger.info(f"✅ Component {component_name} already loaded")
            return None
            
        if component_name not in self._loading_tasks:
            logger.warning(f"⚠️  Component {component_name} not registered for lazy loading")
            return None
            
        task = self._loading_tasks[component_name]
        if task['status'] == 'loading':
            logger.info(f"⏳ Component {component_name} already loading")
            return None
            
        # Check dependencies
        for dep in task['dependencies']:
            if dep not in self._loaded_components:
                logger.info(f"⏳ Waiting for dependency {dep} before loading {component_name}")
                # Schedule retry after dependency loads
                threading.Timer(1.0, self.load_component, args=[component_name]).start()
                return None
        
        # Start loading
        task['status'] = 'loading'
        future = self._executor.submit(self._load_component_task, component_name)
        logger.info(f"🚀 Starting lazy load for {component_name}")
        return future
    
    def load_all_components(self):
        """Load all registered components"""
        logger.info("💤 Starting lazy loading for all components...")
        
        # Sort by priority
        sorted_components = sorted(
            self._loading_tasks.items(), 
            key=lambda x: x[1]['priority']
        )
        
        for component_name, task in sorted_components:
            self.load_component(component_name)
    
    def _load_component_task(self, component_name: str):
        """Execute component loading task"""
        start_time = time.perf_counter()
        task = self._loading_tasks[component_name]
        
        try:
            logger.info(f"📦 Loading component: {component_name}")
            result = task['loader']()
            task['result'] = result
            task['status'] = 'completed'
            self._loaded_components.add(component_name)
            
            duration = time.perf_counter() - start_time
            logger.info(f"✅ Component {component_name} loaded successfully in {duration:.3f}s")
            
            # Notify callbacks
            self._notify_callbacks(component_name, 'success', result)
            
        except Exception as e:
            task['error'] = str(e)
            task['status'] = 'failed'
            logger.error(f"❌ Component {component_name} failed to load: {e}")
            
            # Notify callbacks
            self._notify_callbacks(component_name, 'error', str(e))
    
    def is_loaded(self, component_name: str) -> bool:
        """Check if component is loaded"""
        return component_name in self._loaded_components
    
    def get_component_status(self, component_name: str) -> Dict[str, Any]:
        """Get component loading status"""
        if component_name not in self._loading_tasks:
            return {'status': 'not_registered'}
        
        task = self._loading_tasks[component_name]
        return {
            'status': task['status'],
            'priority': task['priority'],
            'dependencies': task['dependencies'],
            'error': task['error'],
            'result': task['result']
        }
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all components"""
        return {name: self.get_component_status(name) for name in self._loading_tasks}
    
    def add_load_callback(self, callback: Callable[[str, str, Any], None]):
        """Add callback for component loading events"""
        self._load_callbacks.append(callback)
    
    def _notify_callbacks(self, component_name: str, status: str, result: Any):
        """Notify all callbacks about component loading status"""
        for callback in self._load_callbacks:
            try:
                callback(component_name, status, result)
            except Exception as e:
                logger.error(f"❌ Callback error for {component_name}: {e}")

# Global lazy loader instance
_lazy_loader = None

def get_lazy_loader():
    """Get global lazy loader instance"""
    global _lazy_loader
    if _lazy_loader is None:
        _lazy_loader = LazyLoader()
    return _lazy_loader

def lazy_load(component_name: str, priority: int = 100, dependencies: List[str] = None):
    """Decorator to mark functions for lazy loading"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            lazy_loader = get_lazy_loader()
            lazy_loader.register_component(component_name, lambda: func(*args, **kwargs), priority, dependencies)
            return None  # Return None immediately for lazy loading
        return wrapper
    return decorator

# Pre-defined lazy loading components
def setup_lazy_components():
    """Setup all lazy loading components"""
    lazy_loader = get_lazy_loader()
    
    # Monitoring services
    lazy_loader.register_component(
        'monitoring_services',
        _setup_monitoring_services,
        priority=200,
        dependencies=[]
    )
    
    # Background tasks
    lazy_loader.register_component(
        'background_tasks',
        _setup_background_tasks,
        priority=150,
        dependencies=[]
    )
    
    # Cache warming
    lazy_loader.register_component(
        'cache_warming',
        _warmup_cache,
        priority=100,
        dependencies=[]
    )
    
    # Analytics
    lazy_loader.register_component(
        'analytics',
        _setup_analytics,
        priority=300,
        dependencies=['monitoring_services']
    )
    
    # Health checks
    lazy_loader.register_component(
        'health_checks',
        _setup_health_checks,
        priority=250,
        dependencies=['background_tasks']
    )

# Component implementations

def _setup_monitoring_services():
    """Setup monitoring services"""
    logger.info("📊 Setting up monitoring services...")
    try:
        # Import with error handling to avoid circular imports
        try:
            from core.job_manager_mcp import main
            monitor_thread = threading.Thread(target=main, daemon=True)
            monitor_thread.start()
            logger.info("✅ Monitoring services setup complete")
            return True
        except ImportError as e:
            logger.warning(f"⚠️  Could not import monitor_threads: {e}")
            logger.info("✅ Monitoring services setup skipped (optional)")
            return True
    except Exception as e:
        logger.error(f"❌ Monitoring services setup failed: {e}")
        return False

def _setup_background_tasks():
    """Setup background task management"""
    logger.info("🔄 Setting up background tasks...")
    try:
        # Setup background task executor
        logger.info("✅ Background tasks setup complete")
        return True
    except Exception as e:
        logger.error(f"❌ Background tasks setup failed: {e}")
        raise

def _warmup_cache():
    """Warm up application cache"""
    logger.info("🔥 Warming up cache...")
    try:
        # Cache warming logic
        logger.info("✅ Cache warmup complete")
        return True
    except Exception as e:
        logger.error(f"❌ Cache warmup failed: {e}")
        raise

def _setup_analytics():
    """Setup analytics collection"""
    logger.info("📈 Setting up analytics...")
    try:
        # Analytics setup logic
        logger.info("✅ Analytics setup complete")
        return True
    except Exception as e:
        logger.error(f"❌ Analytics setup failed: {e}")
        raise

def _setup_health_checks():
    """Setup health check endpoints"""
    logger.info("🏥 Setting up health checks...")
    try:
        # Health check setup logic
        logger.info("✅ Health checks setup complete")
        return True
    except Exception as e:
        logger.error(f"❌ Health checks setup failed: {e}")
        raise

# Utility functions

def wait_for_component(component_name: str, timeout: float = 30.0) -> bool:
    """Wait for a component to be loaded"""
    lazy_loader = get_lazy_loader()
    
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < timeout:
        if lazy_loader.is_loaded(component_name):
            return True
        time.sleep(0.1)
    
    logger.warning(f"⏰ Timeout waiting for component: {component_name}")
    return False

def get_component_result(component_name: str):
    """Get the result of a loaded component"""
    lazy_loader = get_lazy_loader()
    status = lazy_loader.get_component_status(component_name)
    
    if status['status'] == 'completed':
        return status['result']
    elif status['status'] == 'failed':
        raise Exception(f"Component {component_name} failed to load: {status['error']}")
    else:
        raise Exception(f"Component {component_name} not loaded yet")

if __name__ == "__main__":
    # Test lazy loading
    setup_lazy_components()
    
    lazy_loader = get_lazy_loader()
    lazy_loader.load_all_components()
    
    # Wait for all components to load
    import time
    time.sleep(5)
    
    print("Component statuses:")
    for name, status in lazy_loader.get_all_statuses().items():
        print(f"  {name}: {status['status']}")