"""
Order Flow Performance Monitor (Phase 4.1)

Monitors resource usage and performance metrics for Phase 1-3 components.
"""

import logging
import time
import threading
from typing import Dict, Any, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    tick_engine_count: int
    metrics_cache_size: int
    cache_hit_rate: float
    avg_metrics_latency_ms: float
    order_flow_checks_per_second: float


class OrderFlowPerformanceMonitor:
    """
    Monitors performance of order flow components.
    
    Phase 4.1: Tracks resource usage and performance metrics for:
    - Tick-by-tick delta engine
    - Order flow metrics calculation
    - Pattern classification
    - Exit management
    """
    
    def __init__(self):
        """Initialize performance monitor"""
        self.enabled = PSUTIL_AVAILABLE
        self.metrics_history = deque(maxlen=100)  # Last 100 snapshots
        self.metrics_lock = threading.Lock()
        
        # Performance counters
        self.metrics_cache_hits = 0
        self.metrics_cache_misses = 0
        self.metrics_call_count = 0
        self.metrics_total_latency_ms = 0.0
        self.order_flow_check_count = 0
        self.last_check_time = time.time()
        
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available - performance monitoring disabled")
        else:
            logger.info("Phase 4.1: Order Flow Performance Monitor initialized")
    
    def record_metrics_call(self, cached: bool, latency_ms: float):
        """
        Record a metrics call for performance tracking.
        
        Args:
            cached: Whether result was from cache
            latency_ms: Call latency in milliseconds
        """
        with self.metrics_lock:
            self.metrics_call_count += 1
            self.metrics_total_latency_ms += latency_ms
            
            if cached:
                self.metrics_cache_hits += 1
            else:
                self.metrics_cache_misses += 1
    
    def record_order_flow_check(self):
        """Record an order flow condition check"""
        with self.metrics_lock:
            self.order_flow_check_count += 1
    
    def get_performance_metrics(
        self,
        tick_engine_count: int = 0,
        metrics_cache_size: int = 0
    ) -> Optional[PerformanceMetrics]:
        """
        Get current performance metrics snapshot.
        
        Args:
            tick_engine_count: Number of active tick engines
            metrics_cache_size: Size of metrics cache
        
        Returns:
            PerformanceMetrics or None if monitoring disabled
        """
        if not self.enabled:
            return None
        
        try:
            # Get system metrics
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
            
            # Calculate cache hit rate
            total_cache_requests = self.metrics_cache_hits + self.metrics_cache_misses
            cache_hit_rate = (
                (self.metrics_cache_hits / total_cache_requests * 100)
                if total_cache_requests > 0 else 0.0
            )
            
            # Calculate average latency
            avg_latency_ms = (
                (self.metrics_total_latency_ms / self.metrics_call_count)
                if self.metrics_call_count > 0 else 0.0
            )
            
            # Calculate checks per second
            current_time = time.time()
            time_elapsed = current_time - self.last_check_time
            checks_per_second = (
                (self.order_flow_check_count / time_elapsed)
                if time_elapsed > 0 else 0.0
            )
            
            metrics = PerformanceMetrics(
                timestamp=current_time,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                tick_engine_count=tick_engine_count,
                metrics_cache_size=metrics_cache_size,
                cache_hit_rate=cache_hit_rate,
                avg_metrics_latency_ms=avg_latency_ms,
                order_flow_checks_per_second=checks_per_second
            )
            
            # Store in history
            with self.metrics_lock:
                self.metrics_history.append(metrics)
            
            return metrics
            
        except Exception as e:
            logger.debug(f"Error collecting performance metrics: {e}")
            return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary statistics.
        
        Returns:
            Dict with performance summary
        """
        if not self.enabled or len(self.metrics_history) == 0:
            return {
                "enabled": False,
                "message": "Performance monitoring not available or no data"
            }
        
        with self.metrics_lock:
            recent_metrics = list(self.metrics_history)[-10:]  # Last 10 snapshots
            
            if not recent_metrics:
                return {"enabled": True, "data_points": 0}
            
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_mb for m in recent_metrics) / len(recent_metrics)
            avg_cache_hit_rate = sum(m.cache_hit_rate for m in recent_metrics) / len(recent_metrics)
            avg_latency = sum(m.avg_metrics_latency_ms for m in recent_metrics) / len(recent_metrics)
            
            return {
                "enabled": True,
                "data_points": len(recent_metrics),
                "avg_cpu_percent": avg_cpu,
                "avg_memory_mb": avg_memory,
                "avg_cache_hit_rate": avg_cache_hit_rate,
                "avg_metrics_latency_ms": avg_latency,
                "total_metrics_calls": self.metrics_call_count,
                "cache_hits": self.metrics_cache_hits,
                "cache_misses": self.metrics_cache_misses,
                "order_flow_checks": self.order_flow_check_count
            }
    
    def reset_counters(self):
        """Reset performance counters (useful for testing)"""
        with self.metrics_lock:
            self.metrics_cache_hits = 0
            self.metrics_cache_misses = 0
            self.metrics_call_count = 0
            self.metrics_total_latency_ms = 0.0
            self.order_flow_check_count = 0
            self.last_check_time = time.time()
