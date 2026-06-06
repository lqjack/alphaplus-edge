#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Monitor
Provides real-time performance monitoring and optimization suggestions.
"""

import logging
import time
import threading
import psutil
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from collections import deque
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_io_read: float
    disk_io_write: float
    network_sent: float
    network_recv: float
    active_threads: int
    active_connections: int

class PerformanceMonitor:
    """Real-time performance monitoring system"""
    
    def __init__(self, sample_interval: float = 5.0, history_size: int = 1000):
        self.sample_interval = sample_interval
        self.history_size = history_size
        self.metrics_history = deque(maxlen=history_size)
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks = []
        
        # Performance thresholds
        self.thresholds = {
            'cpu_high': 80.0,
            'cpu_critical': 95.0,
            'memory_high': 80.0,
            'memory_critical': 90.0,
            'disk_io_high': 100.0,  # MB/s
            'network_high': 50.0,   # MB/s
        }
        
        # Optimization suggestions
        self.suggestions = []
        
    def start_monitoring(self):
        """Start performance monitoring"""
        if self.monitoring:
            logger.warning("Performance monitoring already started")
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("📊 Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("📊 Performance monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        try:
            disk_io_prev = psutil.disk_io_counters()
            network_io_prev = psutil.net_io_counters()
        except Exception as e:
            logger.error(f"❌ Failed to initialize disk/network counters: {e}")
            return
        
        while self.monitoring:
            try:
                # Collect metrics
                metrics = self._collect_metrics(disk_io_prev, network_io_prev)
                self.metrics_history.append(metrics)
                
                # Check thresholds and generate suggestions
                self._check_thresholds(metrics)
                
                # Notify callbacks
                self._notify_callbacks(metrics)
                
                # Update previous values
                disk_io_prev = psutil.disk_io_counters()
                network_io_prev = psutil.net_io_counters()
                
                time.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(1.0)  # Short delay before retry
    
    def _collect_metrics(self, disk_io_prev, network_io_prev) -> PerformanceMetrics:
        """Collect current performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1.0)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / (1024 * 1024)
            
            # Disk I/O
            disk_io_curr = psutil.disk_io_counters()
            if disk_io_curr is not None:
                disk_read_rate = (disk_io_curr.read_bytes - disk_io_prev.read_bytes) / self.sample_interval / (1024 * 1024)
                disk_write_rate = (disk_io_curr.write_bytes - disk_io_prev.write_bytes) / self.sample_interval / (1024 * 1024)
            else:
                disk_read_rate = 0.0
                disk_write_rate = 0.0
            
            # Network I/O
            network_io_curr = psutil.net_io_counters()
            if network_io_curr is not None:
                network_sent_rate = (network_io_curr.bytes_sent - network_io_prev.bytes_sent) / self.sample_interval / (1024 * 1024)
                network_recv_rate = (network_io_curr.bytes_recv - network_io_prev.bytes_recv) / self.sample_interval / (1024 * 1024)
            else:
                network_sent_rate = 0.0
                network_recv_rate = 0.0
            
            # Thread count
            active_threads = threading.active_count()
            
            # Network connections (TCP)
            try:
                connections = len(psutil.net_connections(kind='tcp'))
            except Exception:
                connections = 0
            
            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_mb,
                disk_io_read=disk_read_rate,
                disk_io_write=disk_write_rate,
                network_sent=network_sent_rate,
                network_recv=network_recv_rate,
                active_threads=active_threads,
                active_connections=connections
            )
        except Exception as e:
            logger.error(f"❌ Error collecting metrics: {e}")
            # Return default metrics with error indicators
            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_mb=0.0,
                disk_io_read=0.0,
                disk_io_write=0.0,
                network_sent=0.0,
                network_recv=0.0,
                active_threads=0,
                active_connections=0
            )
    
    def _check_thresholds(self, metrics: PerformanceMetrics):
        """Check performance thresholds and generate optimization suggestions"""
        current_suggestions = []
        
        # CPU monitoring
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            current_suggestions.append({
                'type': 'critical',
                'component': 'CPU',
                'message': f"CPU usage critical: {metrics.cpu_percent:.1f}%",
                'suggestion': 'Consider reducing concurrent tasks or upgrading hardware'
            })
        elif metrics.cpu_percent > self.thresholds['cpu_high']:
            current_suggestions.append({
                'type': 'warning',
                'component': 'CPU',
                'message': f"CPU usage high: {metrics.cpu_percent:.1f}%",
                'suggestion': 'Monitor for performance degradation'
            })
        
        # Memory monitoring
        if metrics.memory_percent > self.thresholds['memory_critical']:
            current_suggestions.append({
                'type': 'critical',
                'component': 'Memory',
                'message': f"Memory usage critical: {metrics.memory_percent:.1f}%",
                'suggestion': 'Free up memory or increase available RAM'
            })
        elif metrics.memory_percent > self.thresholds['memory_high']:
            current_suggestions.append({
                'type': 'warning',
                'component': 'Memory',
                'message': f"Memory usage high: {metrics.memory_percent:.1f}%",
                'suggestion': 'Monitor for memory leaks'
            })
        
        # Disk I/O monitoring
        disk_io_total = metrics.disk_io_read + metrics.disk_io_write
        if disk_io_total > self.thresholds['disk_io_high']:
            current_suggestions.append({
                'type': 'warning',
                'component': 'Disk I/O',
                'message': f"High disk I/O: {disk_io_total:.1f} MB/s",
                'suggestion': 'Consider using faster storage or reducing I/O operations'
            })
        
        # Network I/O monitoring
        network_io_total = metrics.network_sent + metrics.network_recv
        if network_io_total > self.thresholds['network_high']:
            current_suggestions.append({
                'type': 'warning',
                'component': 'Network',
                'message': f"High network usage: {network_io_total:.1f} MB/s",
                'suggestion': 'Check for network bottlenecks'
            })
        
        # Thread monitoring
        if metrics.active_threads > 100:
            current_suggestions.append({
                'type': 'info',
                'component': 'Threads',
                'message': f"High thread count: {metrics.active_threads}",
                'suggestion': 'Consider thread pool optimization'
            })
        
        # Store suggestions
        if current_suggestions:
            self.suggestions.extend(current_suggestions)
            # Keep only recent suggestions
            if len(self.suggestions) > 100:
                self.suggestions = self.suggestions[-100:]
    
    def _notify_callbacks(self, metrics: PerformanceMetrics):
        """Notify registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"❌ Callback error: {e}")
    
    def add_callback(self, callback: Callable[[PerformanceMetrics], None]):
        """Add performance monitoring callback"""
        self.callbacks.append(callback)
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get latest performance metrics"""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_metrics_history(self, limit: Optional[int] = None) -> List[PerformanceMetrics]:
        """Get performance metrics history"""
        if limit:
            return list(self.metrics_history)[-limit:]
        return list(self.metrics_history)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.metrics_history:
            return {"error": "No metrics available"}
        
        recent_metrics = list(self.metrics_history)[-100:]  # Last 100 samples
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            "current": asdict(self.metrics_history[-1]),
            "summary": {
                "cpu_avg": sum(cpu_values) / len(cpu_values),
                "cpu_max": max(cpu_values),
                "cpu_min": min(cpu_values),
                "memory_avg": sum(memory_values) / len(memory_values),
                "memory_max": max(memory_values),
                "memory_min": min(memory_values),
                "sample_count": len(recent_metrics),
                "time_span": recent_metrics[-1].timestamp - recent_metrics[0].timestamp if len(recent_metrics) > 1 else 0
            },
            "suggestions": self.suggestions[-10:],  # Last 10 suggestions
            "thresholds": self.thresholds
        }
    
    def export_metrics(self, filepath: str):
        """Export metrics history to JSON file"""
        try:
            metrics_data = [asdict(m) for m in self.metrics_history]
            with open(filepath, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            logger.info(f"📊 Metrics exported to {filepath}")
        except Exception as e:
            logger.error(f"❌ Failed to export metrics: {e}")
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations based on historical data"""
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        # Analyze CPU patterns
        cpu_values = [m.cpu_percent for m in self.metrics_history]
        cpu_avg = sum(cpu_values) / len(cpu_values)
        cpu_max = max(cpu_values)
        
        if cpu_avg > 70:
            recommendations.append({
                "category": "CPU",
                "priority": "high" if cpu_avg > 85 else "medium",
                "issue": f"High average CPU usage: {cpu_avg:.1f}%",
                "recommendation": "Consider reducing concurrent tasks or upgrading CPU"
            })
        
        if cpu_max > 95:
            recommendations.append({
                "category": "CPU",
                "priority": "critical",
                "issue": f"CPU spikes detected: {cpu_max:.1f}%",
                "recommendation": "Investigate CPU-intensive operations"
            })
        
        # Analyze memory patterns
        memory_values = [m.memory_percent for m in self.metrics_history]
        memory_avg = sum(memory_values) / len(memory_values)
        memory_trend = memory_values[-1] - memory_values[0] if len(memory_values) > 1 else 0
        
        if memory_avg > 75:
            recommendations.append({
                "category": "Memory",
                "priority": "high" if memory_avg > 85 else "medium",
                "issue": f"High average memory usage: {memory_avg:.1f}%",
                "recommendation": "Optimize memory usage or increase RAM"
            })
        
        if memory_trend > 10:
            recommendations.append({
                "category": "Memory",
                "priority": "high",
                "issue": f"Memory usage increasing trend: {memory_trend:.1f}%",
                "recommendation": "Check for memory leaks"
            })
        
        # Analyze I/O patterns
        disk_io_values = [m.disk_io_read + m.disk_io_write for m in self.metrics_history]
        disk_io_avg = sum(disk_io_values) / len(disk_io_values)
        
        if disk_io_avg > 50:
            recommendations.append({
                "category": "Disk I/O",
                "priority": "medium",
                "issue": f"High average disk I/O: {disk_io_avg:.1f} MB/s",
                "recommendation": "Consider SSD upgrade or I/O optimization"
            })
        
        return recommendations

# Global performance monitor instance
_performance_monitor = None

def get_performance_monitor():
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

# Async performance monitor for web applications
class AsyncPerformanceMonitor(PerformanceMonitor):
    """Async version of performance monitor"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = asyncio.Event()
    
    async def start_monitoring(self):
        """Start async performance monitoring"""
        if self.monitoring:
            logger.warning("Performance monitoring already started")
            return
            
        self.monitoring = True
        self._stop_event.clear()
        asyncio.create_task(self._async_monitor_loop())
        logger.info("📊 Async performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop async performance monitoring"""
        self.monitoring = False
        self._stop_event.set()
        logger.info("📊 Async performance monitoring stopped")
    
    async def _async_monitor_loop(self):
        """Async monitoring loop"""
        try:
            disk_io_prev = psutil.disk_io_counters()
            network_io_prev = psutil.net_io_counters()
        except Exception as e:
            logger.error(f"❌ Failed to initialize disk/network counters: {e}")
            return
        
        while self.monitoring:
            try:
                # Collect metrics
                metrics = self._collect_metrics(disk_io_prev, network_io_prev)
                self.metrics_history.append(metrics)
                
                # Check thresholds and generate suggestions
                self._check_thresholds(metrics)
                
                # Notify callbacks
                self._notify_callbacks(metrics)
                
                # Update previous values
                disk_io_prev = psutil.disk_io_counters()
                network_io_prev = psutil.net_io_counters()
                
                await asyncio.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in async monitoring loop: {e}")
                await asyncio.sleep(1.0)

if __name__ == "__main__":
    # Test performance monitoring
    monitor = get_performance_monitor()
    monitor.start_monitoring()
    
    # Print metrics every 10 seconds
    def print_metrics(metrics):
        print(f"📊 CPU: {metrics.cpu_percent:.1f}% | Memory: {metrics.memory_percent:.1f}% | Threads: {metrics.active_threads}")
    
    monitor.add_callback(print_metrics)
    
    try:
        import time
        time.sleep(30)
    finally:
        monitor.stop_monitoring()
        
        # Print summary
        summary = monitor.get_performance_summary()
        print("\n📈 Performance Summary:")
        print(f"Average CPU: {summary['summary']['cpu_avg']:.1f}%")
        print(f"Average Memory: {summary['summary']['memory_avg']:.1f}%")
        print(f"Recommendations: {len(monitor.get_optimization_recommendations())}")