"""
Performance Monitoring Component

Handles performance monitoring, timing, and resource usage tracking.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from contextlib import contextmanager
import threading

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None


class PerformanceMonitor:
    """Monitors performance metrics and resource usage"""
    
    def __init__(self):
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.performance_monitor")
        self.metrics_history: List[PerformanceMetrics] = []
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Performance thresholds
        self.max_duration_threshold = 30.0  # seconds
        self.max_memory_threshold = 500.0   # MB
        self.max_cpu_threshold = 80.0       # percentage
    
    def start_monitoring(self):
        """Start background performance monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        self.logger.info("Performance monitoring stopped")
    
    def _monitor_resources(self):
        """Background resource monitoring"""
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available, resource monitoring disabled")
            return
            
        while self.monitoring_active:
            try:
                # Get current process
                process = psutil.Process()
                
                # Get memory usage (MB)
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                # Get CPU usage percentage
                cpu_percent = process.cpu_percent()
                
                # Log warnings if thresholds exceeded
                if memory_mb > self.max_memory_threshold:
                    self.logger.warning(f"High memory usage detected: {memory_mb:.2f}MB")
                
                if cpu_percent > self.max_cpu_threshold:
                    self.logger.warning(f"High CPU usage detected: {cpu_percent:.2f}%")
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                time.sleep(5)
    
    @contextmanager
    def measure_operation(self, operation_name: str):
        """Context manager to measure operation performance"""
        start_time = time.time()
        start_memory = self._get_memory_usage()
        start_cpu = self._get_cpu_usage()
        
        error_message = None
        success = True
        
        try:
            self.logger.debug(f"Starting operation: {operation_name}")
            yield
            self.logger.debug(f"Completed operation: {operation_name}")
            
        except Exception as e:
            success = False
            error_message = str(e)
            self.logger.error(f"Operation failed: {operation_name} - {error_message}")
            raise
        
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()
            end_cpu = self._get_cpu_usage()
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            cpu_delta = end_cpu - start_cpu
            
            # Create metrics record
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_usage=memory_delta,
                cpu_usage=cpu_delta,
                success=success,
                error_message=error_message
            )
            
            # Store metrics
            self.metrics_history.append(metrics)
            
            # Log performance summary
            self._log_performance_summary(metrics)
            
            # Check for performance issues
            self._check_performance_issues(metrics)
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        if not PSUTIL_AVAILABLE:
            return 0.0
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        if not PSUTIL_AVAILABLE:
            return 0.0
        try:
            return psutil.cpu_percent()
        except Exception:
            return 0.0
    
    def _log_performance_summary(self, metrics: PerformanceMetrics):
        """Log performance summary for an operation"""
        status = "SUCCESS" if metrics.success else "FAILED"
        self.logger.info(
            f"Performance: {metrics.operation_name} - "
            f"Duration: {metrics.duration:.2f}s, "
            f"Memory: {metrics.memory_usage:.2f}MB, "
            f"CPU: {metrics.cpu_usage:.2f}%, "
            f"Status: {status}"
        )
    
    def _check_performance_issues(self, metrics: PerformanceMetrics):
        """Check for performance issues and log warnings"""
        issues = []
        
        if metrics.duration > self.max_duration_threshold:
            issues.append(f"Long duration: {metrics.duration:.2f}s")
        
        if abs(metrics.memory_usage) > (self.max_memory_threshold / 10):  # 50MB threshold
            issues.append(f"High memory usage: {metrics.memory_usage:.2f}MB")
        
        if abs(metrics.cpu_usage) > (self.max_cpu_threshold / 10):  # 8% threshold
            issues.append(f"High CPU usage: {metrics.cpu_usage:.2f}%")
        
        if not metrics.success:
            issues.append(f"Operation failed: {metrics.error_message}")
        
        if issues:
            self.logger.warning(f"Performance issues in {metrics.operation_name}: {', '.join(issues)}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics"""
        if not self.metrics_history:
            return {"error": "No performance data available"}
        
        total_operations = len(self.metrics_history)
        successful_operations = sum(1 for m in self.metrics_history if m.success)
        failed_operations = total_operations - successful_operations
        
        durations = [m.duration for m in self.metrics_history]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        
        memory_usage = [abs(m.memory_usage) for m in self.metrics_history]
        avg_memory = sum(memory_usage) / len(memory_usage)
        max_memory = max(memory_usage)
        
        cpu_usage = [abs(m.cpu_usage) for m in self.metrics_history]
        avg_cpu = sum(cpu_usage) / len(cpu_usage)
        max_cpu = max(cpu_usage)
        
        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": (successful_operations / total_operations) * 100,
            "duration_stats": {
                "average": avg_duration,
                "maximum": max_duration,
                "minimum": min_duration
            },
            "memory_stats": {
                "average": avg_memory,
                "maximum": max_memory
            },
            "cpu_stats": {
                "average": avg_cpu,
                "maximum": max_cpu
            }
        }
    
    def get_slow_operations(self, threshold: float = 5.0) -> List[PerformanceMetrics]:
        """Get operations that took longer than threshold seconds"""
        return [m for m in self.metrics_history if m.duration > threshold]
    
    def get_failed_operations(self) -> List[PerformanceMetrics]:
        """Get all failed operations"""
        return [m for m in self.metrics_history if not m.success]
    
    def clear_history(self):
        """Clear performance metrics history"""
        self.metrics_history.clear()
        self.logger.info("Performance metrics history cleared")

    def record_operation(self, operation_name: str, execution_time: float, success: bool):
        """Record operation performance metrics directly"""
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=0,  # Not available when called directly
            end_time=0,    # Not available when called directly
            duration=execution_time,
            memory_usage=0,  # Not available without context
            cpu_usage=0,     # Not available without context
            success=success,
            error_message=None if success else "Operation failed"
        )
        
        # Store metrics
        self.metrics_history.append(metrics)
        
        # Log performance summary
        self.logger.info(
            f"Performance: {operation_name} - "
            f"Duration: {execution_time:.3f}s, "
            f"Status: {'SUCCESS' if success else 'FAILED'}"
        )
    
    def export_metrics(self, filepath: str) -> bool:
        """Export performance metrics to file"""
        try:
            import json
            
            metrics_data = []
            for metrics in self.metrics_history:
                metrics_data.append({
                    "operation_name": metrics.operation_name,
                    "start_time": metrics.start_time,
                    "end_time": metrics.end_time,
                    "duration": metrics.duration,
                    "memory_usage": metrics.memory_usage,
                    "cpu_usage": metrics.cpu_usage,
                    "success": metrics.success,
                    "error_message": metrics.error_message
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Performance metrics exported to: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting performance metrics: {e}")
            return False