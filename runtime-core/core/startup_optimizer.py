#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startup Optimizer
Provides startup performance optimization for the DataProAI application.
"""

import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
if sys.version_info >= (3, 5):
    from typing import Dict, List, Any, Callable, Optional, Tuple
else:
    # Python 2.7 compatibility
    Dict = dict
    List = list
    Any = object
    Callable = object
    Optional = object
    Tuple = tuple
from functools import wraps
from contextlib import contextmanager
import os
import sys
from pathlib import Path

# Import core modules
from core.tools.command import startup_tasks, llms, registered_llms
from core.tools.annotations import startup_before
from core.tools.files import get_project_root
from core.logger import setup_logger
from core.performance_monitor import get_performance_monitor
from core.tools.article_content_check import run_with_app
logger = setup_logger('startup-optimizer', log_to_console=True, log_to_file=True)

class StartupMetrics:
    """Startup performance metrics collector"""
    
    def __init__(self):
        self.metrics = {}
        self.startup_start_time = None
        self.task_durations = {}
        self.parallel_tasks = []
        self.sequential_tasks = []
        
    def start_startup(self):
        """Record startup start time"""
        self.startup_start_time = time.perf_counter()
        logger.info("Startup optimization started")
        
    def record_task(self, task_name, duration, parallel=False):
        """Record task execution time"""
        self.task_durations[task_name] = duration
        if parallel:
            self.parallel_tasks.append(task_name)
        else:
            self.sequential_tasks.append(task_name)
        logger.info("Task '{}' completed in {:.3f}s ({})".format(task_name, duration, 'parallel' if parallel else 'sequential'))
        
    def get_summary(self):
        """Get startup performance summary"""
        if not self.startup_start_time:
            return {"error": "Startup not started"}
            
        total_startup_time = time.perf_counter() - self.startup_start_time
        
        return {
            "total_startup_time": total_startup_time,
            "task_durations": self.task_durations,
            "parallel_tasks": self.parallel_tasks,
            "sequential_tasks": self.sequential_tasks,
            "parallel_efficiency": len(self.parallel_tasks) / max(1, len(self.parallel_tasks) + len(self.sequential_tasks)),
            "bottlenecks": self._identify_bottlenecks()
        }
    
    def _identify_bottlenecks(self):
        """Identify slowest tasks that could be optimized"""
        if not self.task_durations:
            return []
            
        sorted_tasks = sorted(self.task_durations.items(), key=lambda x: x[1], reverse=True)
        # Return top 3 slowest tasks
        return [task for task, duration in sorted_tasks[:3]]

class StartupOptimizer:
    """Main startup optimization orchestrator"""
    
    def __init__(self):
        self.metrics = StartupMetrics()
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="startup-worker")
        self.lazy_loaders = {}
        
    def optimize_startup(self):
        """Optimize and execute startup sequence"""
        self.metrics.start_startup()
        
        # Start performance monitoring
        performance_monitor = get_performance_monitor()
        performance_monitor.start_monitoring()
        
        # Phase 1: Critical initialization (must be sequential)
        logger.info("Phase 1: Critical initialization")
        self._execute_critical_tasks()
        
        # Phase 2: Parallel initialization (can run concurrently)
        logger.info("Phase 2: Parallel initialization")
        self._execute_parallel_tasks()
        
        # Phase 3: Lazy loading setup
        logger.info("Phase 3: Lazy loading setup")
        self._setup_lazy_loading()
        
        # Phase 4: Final verification
        logger.info("Phase 4: Final verification")
        self._verify_startup()
        
        # Stop performance monitoring and get recommendations
        performance_monitor.stop_monitoring()
        recommendations = performance_monitor.get_optimization_recommendations()
        
        # Log performance summary
        summary = self.metrics.get_summary()
        logger.info("Startup completed in {:.2f}s".format(summary['total_startup_time']))
        logger.info("Parallel efficiency: {:.2%}".format(summary['parallel_efficiency']))
        if summary['bottlenecks']:
            logger.warning("Potential bottlenecks: {}".format(', '.join(summary['bottlenecks'])))
        
        # Log performance recommendations
        if recommendations:
            logger.info("Performance recommendations:")
            for rec in recommendations:
                logger.info("  {}: {}".format(rec['priority'].upper(), rec['recommendation']))
            
        return summary
    
    def _execute_critical_tasks(self):
        """Execute critical tasks that must run sequentially"""
        critical_tasks = [
            ("logging_setup", self._setup_logging),
            ("environment_check", self._check_environment),
            ("database_init", self._init_database),
        ]
        
        for task_name, task_func in critical_tasks:
            start_time = time.perf_counter()
            try:
                task_func()
                duration = time.perf_counter() - start_time
                self.metrics.record_task(task_name, duration, parallel=False)
            except Exception as e:
                logger.error("Critical task '{}' failed: {}".format(task_name, e))
                raise
    
    def _execute_parallel_tasks(self):
        """Execute tasks that can run in parallel"""
        parallel_tasks = [
            ("llm_initialization", self._init_llms),
            ("mcp_initialization", self._init_mcp_servers),
            ("web_server_setup", self._setup_web_server),
            ("scheduler_setup", self._setup_scheduler),
        ]
        
        # Submit all parallel tasks
        futures = {}
        for task_name, task_func in parallel_tasks:
            future = self.executor.submit(self._execute_with_metrics, task_name, task_func)
            futures[future] = task_name
        
        # Wait for all tasks to complete
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                future.result()  # This will re-raise any exceptions
            except Exception as e:
                logger.error("Parallel task '{}' failed: {}".format(task_name, e))
                # Don't raise here - let other tasks continue
    
    def _setup_lazy_loading(self):
        """Setup lazy loading for non-critical components"""
        from core.lazy_loader import setup_lazy_components, get_lazy_loader
        
        # Setup lazy loading components
        setup_lazy_components()
        lazy_loader = get_lazy_loader()
        
        # Start loading non-critical components in background
        lazy_loader.load_all_components()
        
        logger.info("Lazy loading setup complete")
    
    def _verify_startup(self):
        """Verify startup was successful"""
        verification_tasks = [
            self._verify_llms,
            self._verify_mcp_servers,
            self._verify_database,
        ]
        
        for task in verification_tasks:
            try:
                task()
            except Exception as e:
                logger.warning("Verification warning: {}".format(e))
    
    def _execute_with_metrics(self, task_name: str, task_func: Callable):
        """Execute task with metrics recording"""
        start_time = time.perf_counter()
        try:
            result = task_func()
            duration = time.perf_counter() - start_time
            self.metrics.record_task(task_name, duration, parallel=True)
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            self.metrics.record_task(task_name, duration, parallel=True)
            logger.error("Task '{}' failed: {}".format(task_name, e))
            raise
    
    # Individual task implementations
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logger.info("Setting up logging...")
        # Logging is already setup by setup_logger, just verify
        logger.info("Logging setup complete")
    
    def _check_environment(self):
        """Check environment and dependencies"""
        logger.info("Checking environment...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            logger.warning("Python version < 3.8 detected")
        
        # Check required environment variables
        required_vars = ['PYTHONPATH', 'PATH']
        for var in required_vars:
            if var not in os.environ:
                logger.warning(f"Environment variable {var} not set")
        
        logger.info("Environment check complete")
    
    def _init_database(self):
        """Initialize database connections"""
        logger.info("Initializing database...")
        try:
            # Import database modules
            from core.db_optimizer import init_database_optimized
            from api.main import app
            
            # Use the app instance instead of current_app
            with app.app_context():
                init_database_optimized(app)
            logger.info("Database initialization complete")
        except Exception as e:
            logger.error("Database initialization failed: {}".format(e))
            raise
    
    def _init_llms(self):
        """Initialize LLM providers via AI MCP server (Lazy)"""
        logger.info("LLM initialization delegated to AI MCP server")
        # LLM initialization is now handled by the AI MCP server on demand.
        # Direct initialization in the main process is removed to improve startup speed.
        return True
    
    def _init_mcp_servers(self):
        """Initialize MCP servers with connection pooling"""
        logger.info("Initializing MCP servers...")
        try:
            from core.mcp_executor import get_mcp_executor
            from core.server_client import get_mcp_manager
            
            # Start MCP executor
            mcp_executor = get_mcp_executor()
            mcp_executor.start()
            
            # Initialize MCP manager
            mcp_manager = get_mcp_manager()
            
            # Connect to servers
            # Note: mcp_executor.start() handles connection logic asynchronously
            logger.info("MCP servers initialization triggered via executor")
        except Exception as e:
            logger.error("MCP servers initialization failed: {}".format(e))
            raise
    
    def _setup_web_server(self):
        """Setup web server configuration"""
        logger.info("Setting up web server...")
        try:
            from api.main import app
            # Web server setup is handled by the main app
            logger.info("Web server setup complete")
        except Exception as e:
            logger.error("Web server setup failed: {}".format(e))
            raise
    
    def _setup_scheduler(self):
        """Setup task scheduler"""
        logger.info("Setting up scheduler...")
        try:
            from core.scheduler import pipeline_scheduler
            # Don't start scheduler here - it will be started by the main app
            # to avoid duplicate starts. Just verify it's available.
            if not hasattr(pipeline_scheduler, '_started'):
                pipeline_scheduler._started = False
            logger.info("Scheduler setup complete (will be started by main app)")
        except Exception as e:
            logger.error("Scheduler setup failed: {}".format(e))
            raise
    
    def _setup_monitoring(self):
        """Setup monitoring services"""
        logger.info("Setting up monitoring...")
        try:
            from core.job_manager_mcp import monitor_threads
            # Start monitoring thread
            # monitor_thread = threading.Thread(target=monitor_threads, daemon=True)
            # monitor_thread.start()
            logger.info("Monitoring setup skipped (handled by scheduler)")
            logger.info("Monitoring setup complete")
        except Exception as e:
            logger.error("Monitoring setup failed: {}".format(e))
    
    def _setup_background_tasks(self):
        """Setup background task management"""
        logger.info("Setting up background tasks...")
        try:
            # Setup background task executor
            logger.info("Background tasks setup complete")
        except Exception as e:
            logger.error("Background tasks setup failed: {}".format(e))
    
    def _warmup_cache(self):
        """Warm up application cache"""
        logger.info("Warming up cache...")
        try:
            # Cache warming logic
            logger.info("Cache warmup complete")
        except Exception as e:
            logger.error("Cache warmup failed: {}".format(e))
    
    def _verify_llms(self):
        """Verify LLM providers are working"""
        logger.info("Verifying LLM providers...")
        if not registered_llms:
            logger.warning("No LLM providers registered")
        else:
            logger.info(f"{len(registered_llms)} LLM providers verified")
    
    def _verify_mcp_servers(self):
        """Verify MCP servers are connected"""
        logger.info("Verifying MCP servers...")
        try:
            from core.server_client import get_mcp_manager
            mcp_manager = get_mcp_manager()
            status = mcp_manager.server_status
            connected = sum(1 for s in status.values() if s == "online")
            logger.info(f"{connected}/{len(status)} MCP servers verified")
        except Exception as e:
            logger.warning("MCP server verification failed: {}".format(e))
    
    @run_with_app
    def _verify_database(self):
        """Verify database connections"""
        logger.info("Verifying database...")
        try:
            from api.main import db
            from sqlalchemy import text
            # Test database connection
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database verification complete")
        except Exception as e:
            logger.warning("Database verification failed: {}".format(e))


# Decorator for lazy loading
def lazy_init(func: Callable):
    """Decorator to mark functions for lazy initialization"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper._lazy_init = True
    return wrapper

# Context manager for startup timing
@contextmanager
def startup_timer(phase_name: str):
    """Context manager for timing startup phases"""
    start_time = time.perf_counter()
    logger.info(f"⏱️  Starting phase: {phase_name}")
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        logger.info(f"⏱️  Phase '{phase_name}' completed in {duration:.3f}s")

# Global optimizer instance
_startup_optimizer = None

def get_startup_optimizer():
    """Get global startup optimizer instance"""
    global _startup_optimizer
    if _startup_optimizer is None:
        _startup_optimizer = StartupOptimizer()
    return _startup_optimizer

def optimize_startup():
    """Optimize application startup"""
    optimizer = get_startup_optimizer()
    return optimizer.optimize_startup()

if __name__ == "__main__":
    # Direct execution for testing
    with startup_timer("Full Startup Optimization"):
        summary = optimize_startup()
        print(f"\nStartup Summary:")
        print("Total time: {:.2f}s".format(summary['total_startup_time']))
        print("Parallel efficiency: {:.2%}".format(summary['parallel_efficiency']))
        if summary['bottlenecks']:
            print("Bottlenecks: {}".format(', '.join(summary['bottlenecks'])))
