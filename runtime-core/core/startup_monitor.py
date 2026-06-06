# -*- coding: utf-8 -*-
"""
Startup Performance Monitor
Monitors and reports startup performance metrics.
"""

import time
import logging
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

@dataclass
class StartupMetric:
    """Startup performance metric"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status: str = "running"  # running, completed, failed
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class StartupMonitor:
    """Startup performance monitoring system"""
    
    def __init__(self):
        self.metrics: Dict[str, StartupMetric] = {}
        self.startup_start_time: float = 0
        self._lock = threading.Lock()
        
    def start_monitoring(self):
        """Start monitoring startup process"""
        self.startup_start_time = time.time()
        logger.info("🚀 Startup performance monitoring started")
        
    def start_metric(self, name: str, metadata: Dict[str, Any] = None):
        """Start timing a metric"""
        with self._lock:
            metric = StartupMetric(
                name=name,
                start_time=time.time(),
                metadata=metadata or {}
            )
            self.metrics[name] = metric
            logger.info(f"⏱️  Started timing: {name}")
            
    def end_metric(self, name: str, status: str = "completed", error: str = None):
        """End timing a metric"""
        with self._lock:
            if name in self.metrics:
                metric = self.metrics[name]
                metric.end_time = time.time()
                metric.duration = metric.end_time - metric.start_time
                metric.status = status
                metric.error = error
                
                if status == "completed":
                    logger.info(f"✅ Completed {name} in {metric.duration:.2f}s")
                elif status == "failed":
                    logger.error(f"❌ Failed {name} after {metric.duration:.2f}s: {error}")
                else:
                    logger.warning(f"⚠️  {name} ended with status: {status}")
            else:
                logger.warning(f"Metric {name} not found for ending")
                
    def get_metric(self, name: str) -> Optional[StartupMetric]:
        """Get a specific metric"""
        return self.metrics.get(name)
        
    def get_all_metrics(self) -> Dict[str, StartupMetric]:
        """Get all metrics"""
        return self.metrics.copy()
        
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        total_startup_time = time.time() - self.startup_start_time
        
        completed_metrics = [m for m in self.metrics.values() if m.status == "completed"]
        failed_metrics = [m for m in self.metrics.values() if m.status == "failed"]
        
        # Sort by duration
        completed_metrics.sort(key=lambda x: x.duration, reverse=True)
        
        report = {
            "startup_time": total_startup_time,
            "total_metrics": len(self.metrics),
            "completed_metrics": len(completed_metrics),
            "failed_metrics": len(failed_metrics),
            "success_rate": len(completed_metrics) / len(self.metrics) if self.metrics else 0,
            "slowest_operations": [
                {
                    "name": m.name,
                    "duration": m.duration,
                    "percentage": (m.duration / total_startup_time) * 100 if total_startup_time > 0 else 0
                }
                for m in completed_metrics[:5]  # Top 5 slowest
            ],
            "metrics": [
                {
                    "name": m.name,
                    "duration": m.duration,
                    "status": m.status,
                    "error": m.error,
                    "metadata": m.metadata
                }
                for m in completed_metrics + failed_metrics
            ]
        }
        
        return report
        
    def print_performance_summary(self):
        """Print performance summary to logs"""
        report = self.get_performance_report()
        
        logger.info("=" * 60)
        logger.info("📊 STARTUP PERFORMANCE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total startup time: {report['startup_time']:.2f}s")
        logger.info(f"Success rate: {report['success_rate']:.1%}")
        logger.info(f"Completed operations: {report['completed_metrics']}")
        logger.info(f"Failed operations: {report['failed_metrics']}")
        
        if report['slowest_operations']:
            logger.info("\n🐌 SLOWEST OPERATIONS:")
            for i, op in enumerate(report['slowest_operations'], 1):
                logger.info(f"{i}. {op['name']}: {op['duration']:.2f}s ({op['percentage']:.1f}%)")
        
        logger.info("=" * 60)
        
    def save_performance_report(self, filename: str = None):
        """Save performance report to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"startup_performance_{timestamp}.json"
            
        import json
        report = self.get_performance_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        logger.info(f"📄 Performance report saved to: {filename}")

# 全局监控器实例
startup_monitor = StartupMonitor()

def monitor_startup_phase(phase_name: str):
    """Decorator to monitor startup phase"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            startup_monitor.start_metric(phase_name)
            try:
                result = func(*args, **kwargs)
                startup_monitor.end_metric(phase_name, "completed")
                return result
            except Exception as e:
                startup_monitor.end_metric(phase_name, "failed", str(e))
                raise
        return wrapper
    return decorator

def monitor_startup_task(task_name: str, metadata: Dict[str, Any] = None):
    """Context manager to monitor startup task"""
    class StartupTask:
        def __init__(self, name: str, metadata: Dict[str, Any] = None):
            self.name = name
            self.metadata = metadata or {}
            
        def __enter__(self):
            startup_monitor.start_metric(self.name, self.metadata)
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                startup_monitor.end_metric(self.name, "completed")
            else:
                startup_monitor.end_metric(self.name, "failed", str(exc_val))
                
    return StartupTask(task_name, metadata)

# 集成到现有系统
def init_startup_monitoring():
    """Initialize startup monitoring"""
    startup_monitor.start_monitoring()
    logger.info("🎯 Startup monitoring integration complete")
    
    # 注意：这里不直接替换函数，避免循环导入
    # 监控功能通过装饰器和上下文管理器在需要时使用
