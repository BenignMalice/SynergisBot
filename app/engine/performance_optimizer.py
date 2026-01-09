"""
Performance Optimizer
Advanced performance tuning and latency optimization for Phase 4
"""

import numpy as np
from numba import jit, prange, types
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging
import time
import threading
import psutil
import os
from dataclasses import dataclass
from enum import Enum
import asyncio
from collections import deque
import queue

logger = logging.getLogger(__name__)

class OptimizationLevel(Enum):
    """Performance optimization levels"""
    BASIC = "basic"
    ADVANCED = "advanced"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"

class PerformanceMetric(Enum):
    """Performance metrics to track"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    QUEUE_DEPTH = "queue_depth"
    CACHE_HIT_RATE = "cache_hit_rate"

@dataclass
class PerformanceProfile:
    """Performance profile for a component"""
    component_name: str
    symbol: str
    latency_p50: float
    latency_p95: float
    latency_p99: float
    throughput: float
    memory_usage: float
    cpu_usage: float
    queue_depth: int
    cache_hit_rate: float
    timestamp: int

class PerformanceOptimizer:
    """Advanced performance optimizer for trading system"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Performance configuration
        self.performance_config = symbol_config.get('performance_config', {})
        self.target_latency_p95 = self.performance_config.get('target_latency_p95', 200)  # ms
        self.max_memory_usage = self.performance_config.get('max_memory_usage', 500)  # MB
        self.max_cpu_usage = self.performance_config.get('max_cpu_usage', 80)  # %
        self.optimization_level = OptimizationLevel(self.performance_config.get('optimization_level', 'advanced'))
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.latency_histogram = deque(maxlen=1000)
        self.throughput_counter = 0
        self.last_throughput_time = time.time()
        
        # Optimization state
        self.optimization_active = False
        self.optimization_thread = None
        self.optimization_lock = threading.RLock()
        
        # System monitoring
        self.process = psutil.Process(os.getpid())
        self.system_monitor = SystemMonitor()
        
    @staticmethod
    @jit(nopython=True, cache=True, parallel=True)
    def optimize_vectorized_calculation(
        data: np.ndarray, 
        window_size: int,
        calculation_type: int  # 0=mean, 1=std, 2=min, 3=max
    ) -> np.ndarray:
        """Optimized vectorized calculation using Numba"""
        n = len(data)
        result = np.zeros(n, dtype=np.float32)
        
        for i in prange(n):
            start_idx = max(0, i - window_size + 1)
            window_data = data[start_idx:i+1]
            
            if calculation_type == 0:  # Mean
                result[i] = np.mean(window_data)
            elif calculation_type == 1:  # Std
                result[i] = np.std(window_data)
            elif calculation_type == 2:  # Min
                result[i] = np.min(window_data)
            elif calculation_type == 3:  # Max
                result[i] = np.max(window_data)
        
        return result
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def optimize_memory_access(
        data: np.ndarray,
        indices: np.ndarray
    ) -> np.ndarray:
        """Optimized memory access pattern"""
        result = np.zeros(len(indices), dtype=np.float32)
        
        for i in range(len(indices)):
            if 0 <= indices[i] < len(data):
                result[i] = data[indices[i]]
        
        return result
    
    def start_optimization(self):
        """Start performance optimization"""
        try:
            with self.optimization_lock:
                if not self.optimization_active:
                    self.optimization_active = True
                    self.optimization_thread = threading.Thread(target=self._optimization_loop, daemon=True)
                    self.optimization_thread.start()
                    logger.info(f"Performance optimization started for {self.symbol}")
                    
        except Exception as e:
            logger.error(f"Error starting optimization: {e}")
    
    def stop_optimization(self):
        """Stop performance optimization"""
        try:
            with self.optimization_lock:
                if self.optimization_active:
                    self.optimization_active = False
                    if self.optimization_thread:
                        self.optimization_thread.join(timeout=1.0)
                    logger.info(f"Performance optimization stopped for {self.symbol}")
                    
        except Exception as e:
            logger.error(f"Error stopping optimization: {e}")
    
    def _optimization_loop(self):
        """Main optimization loop"""
        while self.optimization_active:
            try:
                # Collect performance metrics
                profile = self._collect_performance_profile()
                self.performance_history.append(profile)
                
                # Analyze performance
                optimization_needed = self._analyze_performance(profile)
                
                if optimization_needed:
                    self._apply_optimizations(profile)
                
                # Sleep for optimization interval
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                time.sleep(5.0)  # Wait longer on error
    
    def _collect_performance_profile(self) -> PerformanceProfile:
        """Collect current performance profile"""
        try:
            # Get system metrics
            memory_usage = self.process.memory_info().rss / (1024 * 1024)  # MB
            cpu_usage = self.process.cpu_percent()
            
            # Calculate latency metrics
            if self.latency_histogram:
                latencies = np.array(list(self.latency_histogram))
                latency_p50 = np.percentile(latencies, 50)
                latency_p95 = np.percentile(latencies, 95)
                latency_p99 = np.percentile(latencies, 99)
            else:
                latency_p50 = latency_p95 = latency_p99 = 0.0
            
            # Calculate throughput
            current_time = time.time()
            time_diff = current_time - self.last_throughput_time
            if time_diff > 0:
                throughput = self.throughput_counter / time_diff
                self.throughput_counter = 0
                self.last_throughput_time = current_time
            else:
                throughput = 0.0
            
            return PerformanceProfile(
                component_name="performance_optimizer",
                symbol=self.symbol,
                latency_p50=latency_p50,
                latency_p95=latency_p95,
                latency_p99=latency_p99,
                throughput=throughput,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                queue_depth=0,  # Will be updated by specific components
                cache_hit_rate=0.0,  # Will be updated by specific components
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
            )
            
        except Exception as e:
            logger.error(f"Error collecting performance profile: {e}")
            return PerformanceProfile(
                component_name="performance_optimizer",
                symbol=self.symbol,
                latency_p50=0.0, latency_p95=0.0, latency_p99=0.0,
                throughput=0.0, memory_usage=0.0, cpu_usage=0.0,
                queue_depth=0, cache_hit_rate=0.0,
                timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
            )
    
    def _analyze_performance(self, profile: PerformanceProfile) -> bool:
        """Analyze performance and determine if optimization is needed"""
        try:
            # Check latency thresholds
            if profile.latency_p95 > self.target_latency_p95:
                logger.warning(f"Latency p95 {profile.latency_p95:.2f}ms exceeds target {self.target_latency_p95}ms")
                return True
            
            # Check memory usage
            if profile.memory_usage > self.max_memory_usage:
                logger.warning(f"Memory usage {profile.memory_usage:.2f}MB exceeds limit {self.max_memory_usage}MB")
                return True
            
            # Check CPU usage
            if profile.cpu_usage > self.max_cpu_usage:
                logger.warning(f"CPU usage {profile.cpu_usage:.2f}% exceeds limit {self.max_cpu_usage}%")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return False
    
    def _apply_optimizations(self, profile: PerformanceProfile):
        """Apply performance optimizations"""
        try:
            logger.info(f"Applying optimizations for {self.symbol} (level: {self.optimization_level.value})")
            
            if self.optimization_level == OptimizationLevel.BASIC:
                self._apply_basic_optimizations(profile)
            elif self.optimization_level == OptimizationLevel.ADVANCED:
                self._apply_advanced_optimizations(profile)
            elif self.optimization_level == OptimizationLevel.AGGRESSIVE:
                self._apply_aggressive_optimizations(profile)
            elif self.optimization_level == OptimizationLevel.MAXIMUM:
                self._apply_maximum_optimizations(profile)
                
        except Exception as e:
            logger.error(f"Error applying optimizations: {e}")
    
    def _apply_basic_optimizations(self, profile: PerformanceProfile):
        """Apply basic performance optimizations"""
        # Basic optimizations: memory cleanup, cache optimization
        pass
    
    def _apply_advanced_optimizations(self, profile: PerformanceProfile):
        """Apply advanced performance optimizations"""
        # Advanced optimizations: algorithm optimization, data structure tuning
        pass
    
    def _apply_aggressive_optimizations(self, profile: PerformanceProfile):
        """Apply aggressive performance optimizations"""
        # Aggressive optimizations: parallel processing, memory preallocation
        pass
    
    def _apply_maximum_optimizations(self, profile: PerformanceProfile):
        """Apply maximum performance optimizations"""
        # Maximum optimizations: all available optimizations
        pass
    
    def record_latency(self, latency_ms: float):
        """Record latency measurement"""
        self.latency_histogram.append(latency_ms)
        self.throughput_counter += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        try:
            if not self.performance_history:
                return {'symbol': self.symbol, 'status': 'no_data'}
            
            recent_profiles = list(self.performance_history)[-10:]  # Last 10 profiles
            
            avg_latency_p95 = np.mean([p.latency_p95 for p in recent_profiles])
            avg_throughput = np.mean([p.throughput for p in recent_profiles])
            avg_memory = np.mean([p.memory_usage for p in recent_profiles])
            avg_cpu = np.mean([p.cpu_usage for p in recent_profiles])
            
            return {
                'symbol': self.symbol,
                'avg_latency_p95': avg_latency_p95,
                'avg_throughput': avg_throughput,
                'avg_memory_usage': avg_memory,
                'avg_cpu_usage': avg_cpu,
                'optimization_active': self.optimization_active,
                'optimization_level': self.optimization_level.value,
                'profile_count': len(self.performance_history)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {'symbol': self.symbol, 'error': str(e)}

class SystemMonitor:
    """System-wide performance monitoring"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.system_metrics = deque(maxlen=100)
        
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / (1024 * 1024)  # MB
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = disk.free / (1024 * 1024)  # MB
            
            # Process metrics
            process_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
            process_cpu = self.process.cpu_percent()
            
            metrics = {
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_percent': memory_percent,
                'memory_available_mb': memory_available,
                'disk_percent': disk_percent,
                'disk_free_mb': disk_free,
                'process_memory_mb': process_memory,
                'process_cpu_percent': process_cpu
            }
            
            self.system_metrics.append(metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system performance summary"""
        try:
            if not self.system_metrics:
                return {'status': 'no_data'}
            
            recent_metrics = list(self.system_metrics)[-10:]  # Last 10 measurements
            
            avg_cpu = np.mean([m['cpu_percent'] for m in recent_metrics])
            avg_memory = np.mean([m['memory_percent'] for m in recent_metrics])
            avg_process_memory = np.mean([m['process_memory_mb'] for m in recent_metrics])
            avg_process_cpu = np.mean([m['process_cpu_percent'] for m in recent_metrics])
            
            return {
                'avg_cpu_percent': avg_cpu,
                'avg_memory_percent': avg_memory,
                'avg_process_memory_mb': avg_process_memory,
                'avg_process_cpu_percent': avg_process_cpu,
                'measurement_count': len(self.system_metrics),
                'status': 'healthy' if avg_cpu < 80 and avg_memory < 80 else 'warning'
            }
            
        except Exception as e:
            logger.error(f"Error getting system summary: {e}")
            return {'error': str(e)}

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'BTCUSDc',
        'performance_config': {
            'target_latency_p95': 200,
            'max_memory_usage': 500,
            'max_cpu_usage': 80,
            'optimization_level': 'advanced'
        }
    }
    
    # Create performance optimizer
    optimizer = PerformanceOptimizer(test_config)
    
    print("Testing Performance Optimizer:")
    
    # Start optimization
    optimizer.start_optimization()
    
    # Simulate some latency measurements
    for i in range(10):
        latency = np.random.normal(100, 20)  # Simulate latency around 100ms
        optimizer.record_latency(latency)
        time.sleep(0.1)
    
    # Get performance summary
    summary = optimizer.get_performance_summary()
    print(f"Performance Summary: {summary}")
    
    # Get system metrics
    system_monitor = SystemMonitor()
    system_metrics = system_monitor.get_system_metrics()
    print(f"System Metrics: {system_metrics}")
    
    # Stop optimization
    optimizer.stop_optimization()
    print("Performance optimization test completed")
