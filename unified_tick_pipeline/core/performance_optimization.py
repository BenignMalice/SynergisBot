"""
Performance Optimization for Unified Tick Pipeline
Memory management, CPU optimization, and sleep recovery engine
"""

import asyncio
import logging
import psutil
import gc
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
import weakref
import tracemalloc
import sys

logger = logging.getLogger(__name__)

class OptimizationLevel(Enum):
    """Performance optimization levels"""
    AGGRESSIVE = "aggressive"  # Maximum optimization, may reduce functionality
    BALANCED = "balanced"      # Balanced optimization
    CONSERVATIVE = "conservative"  # Minimal optimization, preserve all functionality

class MemoryState(Enum):
    """Memory usage states"""
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    RECOVERY = "recovery"

class SleepState(Enum):
    """System sleep states"""
    AWAKE = "awake"
    SLEEPING = "sleeping"
    WAKING = "waking"
    RECOVERING = "recovering"

@dataclass
class MemoryMetrics:
    """Memory usage metrics"""
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    peak_memory: int
    gc_objects: int
    timestamp: datetime

@dataclass
class CPUMetrics:
    """CPU usage metrics"""
    cpu_percent: float
    cpu_count: int
    load_average: Tuple[float, float, float]
    context_switches: int
    interrupts: int
    timestamp: datetime

@dataclass
class SleepMetrics:
    """Sleep/wake cycle metrics"""
    last_sleep_time: Optional[datetime]
    last_wake_time: Optional[datetime]
    sleep_duration: Optional[timedelta]
    data_gaps: List[Tuple[datetime, datetime]]
    recovery_actions: List[str]
    timestamp: datetime

class PerformanceOptimization:
    """
    Performance Optimization for Unified Tick Pipeline
    
    Features:
    - Memory management with automatic cleanup and optimization
    - CPU usage optimization with intelligent task scheduling
    - Sleep recovery engine for laptop sleep/wake cycles
    - Gap-fill logic for data continuity during interruptions
    - Resource optimization with dynamic allocation
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_active = False
        
        # Optimization settings
        self.optimization_level = OptimizationLevel(self.config.get('optimization_level', 'balanced'))
        self.memory_thresholds = self.config.get('memory_thresholds', {
            'high': 80.0,
            'critical': 90.0,
            'recovery': 70.0
        })
        self.cpu_thresholds = self.config.get('cpu_thresholds', {
            'high': 80.0,
            'critical': 95.0
        })
        
        # State tracking
        self.memory_state = MemoryState.NORMAL
        self.sleep_state = SleepState.AWAKE
        self.last_optimization = None
        
        # Metrics storage
        self.memory_metrics: List[MemoryMetrics] = []
        self.cpu_metrics: List[CPUMetrics] = []
        self.sleep_metrics: SleepMetrics = SleepMetrics(
            last_sleep_time=None,
            last_wake_time=None,
            sleep_duration=None,
            data_gaps=[],
            recovery_actions=[],
            timestamp=datetime.now(timezone.utc)
        )
        
        # Memory management
        self.memory_tracker = tracemalloc.start() if self.config.get('enable_memory_tracking', True) else None
        self.weak_refs: List[weakref.ref] = []
        self.cache_cleanup_threshold = self.config.get('cache_cleanup_threshold', 1000)
        
        # Sleep recovery
        self.sleep_detection_enabled = self.config.get('sleep_detection_enabled', True)
        self.gap_fill_enabled = self.config.get('gap_fill_enabled', True)
        self.max_gap_duration = timedelta(minutes=self.config.get('max_gap_duration_minutes', 30))
        
        # Performance metrics
        self.performance_metrics = {
            'memory_cleanups': 0,
            'cpu_optimizations': 0,
            'sleep_recoveries': 0,
            'gap_fills': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'gc_collections': 0,
            'memory_leaks_detected': 0,
            'optimization_cycles': 0,
            'error_count': 0
        }
        
        logger.info("PerformanceOptimization initialized")
    
    async def initialize(self):
        """Initialize performance optimization"""
        try:
            logger.info("🔧 Initializing performance optimization...")
            
            # Start memory monitoring
            await self._start_memory_monitoring()
            
            # Start CPU monitoring
            await self._start_cpu_monitoring()
            
            # Start sleep detection
            if self.sleep_detection_enabled:
                await self._start_sleep_detection()
            
            # Start optimization cycles
            await self._start_optimization_cycles()
            
            self.is_active = True
            logger.info("✅ Performance optimization initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize performance optimization: {e}")
            raise
    
    async def stop(self):
        """Stop performance optimization"""
        try:
            logger.info("🛑 Stopping performance optimization...")
            self.is_active = False
            
            # Stop memory tracking
            if self.memory_tracker:
                tracemalloc.stop()
            
            logger.info("✅ Performance optimization stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping performance optimization: {e}")
    
    async def _start_memory_monitoring(self):
        """Start memory monitoring"""
        try:
            # Start memory monitoring task
            asyncio.create_task(self._memory_monitoring_loop())
            
            logger.info("✅ Memory monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting memory monitoring: {e}")
    
    async def _start_cpu_monitoring(self):
        """Start CPU monitoring"""
        try:
            # Start CPU monitoring task
            asyncio.create_task(self._cpu_monitoring_loop())
            
            logger.info("✅ CPU monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting CPU monitoring: {e}")
    
    async def _start_sleep_detection(self):
        """Start sleep detection"""
        try:
            # Start sleep detection task
            asyncio.create_task(self._sleep_detection_loop())
            
            logger.info("✅ Sleep detection started")
            
        except Exception as e:
            logger.error(f"❌ Error starting sleep detection: {e}")
    
    async def _start_optimization_cycles(self):
        """Start optimization cycles"""
        try:
            # Start optimization task
            asyncio.create_task(self._optimization_loop())
            
            logger.info("✅ Optimization cycles started")
            
        except Exception as e:
            logger.error(f"❌ Error starting optimization cycles: {e}")
    
    async def _memory_monitoring_loop(self):
        """Memory monitoring loop"""
        while self.is_active:
            try:
                # Collect memory metrics
                metrics = await self._collect_memory_metrics()
                self.memory_metrics.append(metrics)
                
                # Keep only recent metrics (last 100)
                if len(self.memory_metrics) > 100:
                    self.memory_metrics = self.memory_metrics[-100:]
                
                # Check memory thresholds
                await self._check_memory_thresholds(metrics)
                
                # Update memory state
                await self._update_memory_state(metrics)
                
                await asyncio.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in memory monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _cpu_monitoring_loop(self):
        """CPU monitoring loop"""
        while self.is_active:
            try:
                # Collect CPU metrics
                metrics = await self._collect_cpu_metrics()
                self.cpu_metrics.append(metrics)
                
                # Keep only recent metrics (last 100)
                if len(self.cpu_metrics) > 100:
                    self.cpu_metrics = self.cpu_metrics[-100:]
                
                # Check CPU thresholds
                await self._check_cpu_thresholds(metrics)
                
                await asyncio.sleep(5)  # Monitor every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in CPU monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _sleep_detection_loop(self):
        """Sleep detection loop"""
        last_check = datetime.now(timezone.utc)
        
        while self.is_active:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Check for sleep/wake cycles
                await self._detect_sleep_cycle(last_check, current_time)
                
                last_check = current_time
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"❌ Error in sleep detection loop: {e}")
                await asyncio.sleep(1)
    
    async def _optimization_loop(self):
        """Optimization loop"""
        while self.is_active:
            try:
                # Perform optimization based on current state
                await self._perform_optimization()
                
                # Update optimization timestamp
                self.last_optimization = datetime.now(timezone.utc)
                self.performance_metrics['optimization_cycles'] += 1
                
                # Sleep based on optimization level
                sleep_duration = self._get_optimization_sleep_duration()
                await asyncio.sleep(sleep_duration)
                
            except Exception as e:
                logger.error(f"❌ Error in optimization loop: {e}")
                await asyncio.sleep(30)
    
    async def _collect_memory_metrics(self) -> MemoryMetrics:
        """Collect current memory metrics"""
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            
            # Get garbage collector info
            gc_stats = gc.get_stats()
            gc_objects = sum(stat['collected'] for stat in gc_stats)
            
            return MemoryMetrics(
                total_memory=memory.total,
                available_memory=memory.available,
                used_memory=memory.used,
                memory_percent=memory.percent,
                peak_memory=memory.used,  # Current usage as peak for now
                gc_objects=gc_objects,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"❌ Error collecting memory metrics: {e}")
            return MemoryMetrics(
                total_memory=0,
                available_memory=0,
                used_memory=0,
                memory_percent=0.0,
                peak_memory=0,
                gc_objects=0,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _collect_cpu_metrics(self) -> CPUMetrics:
        """Collect current CPU metrics"""
        try:
            # Get CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Get load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                load_avg = (0.0, 0.0, 0.0)
            
            # Get context switches and interrupts
            try:
                ctx_switches = psutil.cpu_stats().ctx_switches
                interrupts = psutil.cpu_stats().interrupts
            except AttributeError:
                ctx_switches = 0
                interrupts = 0
            
            return CPUMetrics(
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                load_average=load_avg,
                context_switches=ctx_switches,
                interrupts=interrupts,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"❌ Error collecting CPU metrics: {e}")
            return CPUMetrics(
                cpu_percent=0.0,
                cpu_count=1,
                load_average=(0.0, 0.0, 0.0),
                context_switches=0,
                interrupts=0,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _check_memory_thresholds(self, metrics: MemoryMetrics):
        """Check memory thresholds and trigger optimization"""
        try:
            if metrics.memory_percent >= self.memory_thresholds['critical']:
                await self._handle_critical_memory()
            elif metrics.memory_percent >= self.memory_thresholds['high']:
                await self._handle_high_memory()
            
        except Exception as e:
            logger.error(f"❌ Error checking memory thresholds: {e}")
    
    async def _check_cpu_thresholds(self, metrics: CPUMetrics):
        """Check CPU thresholds and trigger optimization"""
        try:
            if metrics.cpu_percent >= self.cpu_thresholds['critical']:
                await self._handle_critical_cpu()
            elif metrics.cpu_percent >= self.cpu_thresholds['high']:
                await self._handle_high_cpu()
            
        except Exception as e:
            logger.error(f"❌ Error checking CPU thresholds: {e}")
    
    async def _handle_critical_memory(self):
        """Handle critical memory usage"""
        try:
            logger.warning("🚨 Critical memory usage detected")
            
            # Aggressive memory cleanup
            await self._aggressive_memory_cleanup()
            
            # Force garbage collection
            await self._force_garbage_collection()
            
            # Clear caches
            await self._clear_all_caches()
            
            self.performance_metrics['memory_cleanups'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling critical memory: {e}")
    
    async def _handle_high_memory(self):
        """Handle high memory usage"""
        try:
            logger.warning("⚠️ High memory usage detected")
            
            # Moderate memory cleanup
            await self._moderate_memory_cleanup()
            
            # Trigger garbage collection
            await self._trigger_garbage_collection()
            
            self.performance_metrics['memory_cleanups'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling high memory: {e}")
    
    async def _handle_critical_cpu(self):
        """Handle critical CPU usage"""
        try:
            logger.warning("🚨 Critical CPU usage detected")
            
            # Defer non-critical tasks
            await self._defer_non_critical_tasks()
            
            # Optimize CPU usage
            await self._optimize_cpu_usage()
            
            self.performance_metrics['cpu_optimizations'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling critical CPU: {e}")
    
    async def _handle_high_cpu(self):
        """Handle high CPU usage"""
        try:
            logger.warning("⚠️ High CPU usage detected")
            
            # Moderate CPU optimization
            await self._moderate_cpu_optimization()
            
            self.performance_metrics['cpu_optimizations'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling high CPU: {e}")
    
    async def _detect_sleep_cycle(self, last_check: datetime, current_time: datetime):
        """Detect sleep/wake cycles"""
        try:
            time_diff = (current_time - last_check).total_seconds()
            
            # If time difference is too large, system was sleeping
            if time_diff > 5:  # More than 5 seconds gap indicates sleep
                await self._handle_sleep_cycle(last_check, current_time)
            
        except Exception as e:
            logger.error(f"❌ Error detecting sleep cycle: {e}")
    
    async def _handle_sleep_cycle(self, sleep_time: datetime, wake_time: datetime):
        """Handle sleep/wake cycle"""
        try:
            logger.info(f"💤 Sleep cycle detected: {sleep_time} -> {wake_time}")
            
            # Update sleep metrics
            self.sleep_metrics.last_sleep_time = sleep_time
            self.sleep_metrics.last_wake_time = wake_time
            self.sleep_metrics.sleep_duration = wake_time - sleep_time
            self.sleep_metrics.timestamp = wake_time
            
            # Set sleep state
            self.sleep_state = SleepState.WAKING
            
            # Perform sleep recovery
            await self._perform_sleep_recovery(sleep_time, wake_time)
            
            # Update state
            self.sleep_state = SleepState.AWAKE
            self.performance_metrics['sleep_recoveries'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling sleep cycle: {e}")
    
    async def _perform_sleep_recovery(self, sleep_time: datetime, wake_time: datetime):
        """Perform sleep recovery actions"""
        try:
            logger.info("🔄 Performing sleep recovery...")
            
            # Check for data gaps
            gap_duration = wake_time - sleep_time
            if gap_duration > self.max_gap_duration:
                logger.warning(f"⚠️ Long sleep duration detected: {gap_duration}")
                # Handle long sleep - may need to reconnect to data feeds
                await self._handle_long_sleep_recovery(sleep_time, wake_time)
            else:
                # Handle normal sleep recovery
                await self._handle_normal_sleep_recovery(sleep_time, wake_time)
            
            # Record recovery actions
            self.sleep_metrics.recovery_actions.append(f"sleep_recovery_{wake_time.isoformat()}")
            
        except Exception as e:
            logger.error(f"❌ Error performing sleep recovery: {e}")
    
    async def _handle_long_sleep_recovery(self, sleep_time: datetime, wake_time: datetime):
        """Handle long sleep recovery"""
        try:
            logger.info("🔄 Handling long sleep recovery...")
            
            # Record data gap
            self.sleep_metrics.data_gaps.append((sleep_time, wake_time))
            
            # Trigger gap fill if enabled
            if self.gap_fill_enabled:
                await self._trigger_gap_fill(sleep_time, wake_time)
                self.performance_metrics['gap_fills'] += 1
            
            # Reconnect to data feeds
            await self._reconnect_data_feeds()
            
            # Clear stale data
            await self._clear_stale_data()
            
        except Exception as e:
            logger.error(f"❌ Error handling long sleep recovery: {e}")
    
    async def _handle_normal_sleep_recovery(self, sleep_time: datetime, wake_time: datetime):
        """Handle normal sleep recovery"""
        try:
            logger.info("🔄 Handling normal sleep recovery...")
            
            # Quick recovery actions
            await self._quick_recovery()
            
        except Exception as e:
            logger.error(f"❌ Error handling normal sleep recovery: {e}")
    
    async def _trigger_gap_fill(self, sleep_time: datetime, wake_time: datetime):
        """Trigger gap fill for missing data"""
        try:
            logger.info(f"🔧 Triggering gap fill: {sleep_time} -> {wake_time}")
            
            # Implementation would request historical data to fill gaps
            # This is a placeholder for the actual gap fill logic
            
        except Exception as e:
            logger.error(f"❌ Error triggering gap fill: {e}")
    
    async def _reconnect_data_feeds(self):
        """Reconnect to data feeds after sleep"""
        try:
            logger.info("🔌 Reconnecting to data feeds...")
            
            # Implementation would reconnect to Binance, MT5, etc.
            # This is a placeholder for the actual reconnection logic
            
        except Exception as e:
            logger.error(f"❌ Error reconnecting data feeds: {e}")
    
    async def _clear_stale_data(self):
        """Clear stale data after sleep"""
        try:
            logger.info("🧹 Clearing stale data...")
            
            # Clear old cache entries
            await self._clear_old_cache_entries()
            
            # Clear old metrics
            await self._clear_old_metrics()
            
        except Exception as e:
            logger.error(f"❌ Error clearing stale data: {e}")
    
    async def _quick_recovery(self):
        """Quick recovery actions"""
        try:
            logger.info("⚡ Performing quick recovery...")
            
            # Light cleanup
            await self._light_cleanup()
            
        except Exception as e:
            logger.error(f"❌ Error in quick recovery: {e}")
    
    async def _perform_optimization(self):
        """Perform optimization based on current state"""
        try:
            # Memory optimization
            if self.memory_state == MemoryState.HIGH:
                await self._moderate_memory_cleanup()
            elif self.memory_state == MemoryState.CRITICAL:
                await self._aggressive_memory_cleanup()
            
            # CPU optimization
            if self.cpu_metrics:
                latest_cpu = self.cpu_metrics[-1]
                if latest_cpu.cpu_percent > 70:
                    await self._moderate_cpu_optimization()
            
            # Cache optimization
            await self._optimize_caches()
            
        except Exception as e:
            logger.error(f"❌ Error performing optimization: {e}")
    
    # Memory management methods
    async def _aggressive_memory_cleanup(self):
        """Aggressive memory cleanup"""
        try:
            logger.info("🧹 Performing aggressive memory cleanup...")
            
            # Force garbage collection
            await self._force_garbage_collection()
            
            # Clear all caches
            await self._clear_all_caches()
            
            # Clear old metrics
            await self._clear_old_metrics()
            
            # Clear weak references
            await self._clear_weak_references()
            
        except Exception as e:
            logger.error(f"❌ Error in aggressive memory cleanup: {e}")
    
    async def _moderate_memory_cleanup(self):
        """Moderate memory cleanup"""
        try:
            logger.info("🧹 Performing moderate memory cleanup...")
            
            # Trigger garbage collection
            await self._trigger_garbage_collection()
            
            # Clear old caches
            await self._clear_old_caches()
            
        except Exception as e:
            logger.error(f"❌ Error in moderate memory cleanup: {e}")
    
    async def _force_garbage_collection(self):
        """Force garbage collection"""
        try:
            # Force collection of all generations
            collected = gc.collect()
            self.performance_metrics['gc_collections'] += 1
            logger.debug(f"🗑️ Garbage collection: {collected} objects collected")
            
        except Exception as e:
            logger.error(f"❌ Error in force garbage collection: {e}")
    
    async def _trigger_garbage_collection(self):
        """Trigger garbage collection"""
        try:
            # Collect generation 0 and 1
            collected = gc.collect()
            self.performance_metrics['gc_collections'] += 1
            logger.debug(f"🗑️ Garbage collection: {collected} objects collected")
            
        except Exception as e:
            logger.error(f"❌ Error in trigger garbage collection: {e}")
    
    async def _clear_all_caches(self):
        """Clear all caches"""
        try:
            # Implementation would clear all system caches
            logger.debug("🧹 Clearing all caches")
            
        except Exception as e:
            logger.error(f"❌ Error clearing all caches: {e}")
    
    async def _clear_old_caches(self):
        """Clear old cache entries"""
        try:
            # Implementation would clear old cache entries
            logger.debug("🧹 Clearing old cache entries")
            
        except Exception as e:
            logger.error(f"❌ Error clearing old caches: {e}")
    
    async def _clear_old_metrics(self):
        """Clear old metrics"""
        try:
            # Keep only recent metrics
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            # Clear old memory metrics
            self.memory_metrics = [m for m in self.memory_metrics if m.timestamp >= cutoff_time]
            
            # Clear old CPU metrics
            self.cpu_metrics = [m for m in self.cpu_metrics if m.timestamp >= cutoff_time]
            
            logger.debug("🧹 Cleared old metrics")
            
        except Exception as e:
            logger.error(f"❌ Error clearing old metrics: {e}")
    
    async def _clear_weak_references(self):
        """Clear weak references"""
        try:
            # Clear dead weak references
            self.weak_refs = [ref for ref in self.weak_refs if ref() is not None]
            logger.debug("🧹 Cleared dead weak references")
            
        except Exception as e:
            logger.error(f"❌ Error clearing weak references: {e}")
    
    # CPU optimization methods
    async def _optimize_cpu_usage(self):
        """Optimize CPU usage"""
        try:
            logger.info("🔧 Optimizing CPU usage...")
            
            # Defer non-critical tasks
            await self._defer_non_critical_tasks()
            
            # Reduce task frequency
            await self._reduce_task_frequency()
            
        except Exception as e:
            logger.error(f"❌ Error optimizing CPU usage: {e}")
    
    async def _moderate_cpu_optimization(self):
        """Moderate CPU optimization"""
        try:
            logger.info("🔧 Performing moderate CPU optimization...")
            
            # Add cooldown to prevent repeated optimizations
            import time
            current_time = time.time()
            last_optimization = self.performance_metrics.get('last_cpu_optimization', 0)
            
            if current_time - last_optimization < 60:  # 1 minute cooldown
                logger.debug("⏳ CPU optimization on cooldown, skipping...")
                return
            
            self.performance_metrics['last_cpu_optimization'] = current_time
            
            # Light task deferral
            await self._light_task_deferral()
            
            # Reduce monitoring frequency temporarily
            await self._reduce_monitoring_frequency()
            
        except Exception as e:
            logger.error(f"❌ Error in moderate CPU optimization: {e}")
    
    async def _defer_non_critical_tasks(self):
        """Defer non-critical tasks"""
        try:
            # Implementation would defer non-critical tasks
            logger.debug("⏸️ Deferring non-critical tasks")
            
        except Exception as e:
            logger.error(f"❌ Error deferring non-critical tasks: {e}")
    
    async def _reduce_task_frequency(self):
        """Reduce task frequency"""
        try:
            # Implementation would reduce task frequency
            logger.debug("⏸️ Reducing task frequency")
            
        except Exception as e:
            logger.error(f"❌ Error reducing task frequency: {e}")
    
    async def _light_task_deferral(self):
        """Light task deferral"""
        try:
            logger.debug("⏸️ Light task deferral")
            
            # Reduce task processing frequency
            if hasattr(self, 'task_processor'):
                self.task_processor.processing_interval = min(
                    self.task_processor.processing_interval * 1.5, 10.0
                )
                logger.debug(f"📉 Increased task processing interval to {self.task_processor.processing_interval}s")
            
            # Reduce monitoring frequency
            if hasattr(self, 'monitoring_interval'):
                self.monitoring_interval = min(self.monitoring_interval * 1.2, 5.0)
                logger.debug(f"📉 Increased monitoring interval to {self.monitoring_interval}s")
            
        except Exception as e:
            logger.error(f"❌ Error in light task deferral: {e}")
    
    async def _reduce_monitoring_frequency(self):
        """Reduce monitoring frequency to save CPU"""
        try:
            # Increase sleep intervals for monitoring tasks
            if hasattr(self, 'monitoring_tasks'):
                for task in self.monitoring_tasks:
                    if hasattr(task, 'interval'):
                        task.interval = min(task.interval * 1.3, 10.0)
            
            logger.debug("📉 Reduced monitoring frequency")
            
        except Exception as e:
            logger.error(f"❌ Error reducing monitoring frequency: {e}")
    
    # Cache optimization methods
    async def _optimize_caches(self):
        """Optimize caches"""
        try:
            # Implementation would optimize cache usage
            logger.debug("🔧 Optimizing caches")
            
        except Exception as e:
            logger.error(f"❌ Error optimizing caches: {e}")
    
    async def _clear_old_cache_entries(self):
        """Clear old cache entries"""
        try:
            # Implementation would clear old cache entries
            logger.debug("🧹 Clearing old cache entries")
            
        except Exception as e:
            logger.error(f"❌ Error clearing old cache entries: {e}")
    
    # Helper methods
    async def _update_memory_state(self, metrics: MemoryMetrics):
        """Update memory state based on metrics"""
        try:
            if metrics.memory_percent >= self.memory_thresholds['critical']:
                self.memory_state = MemoryState.CRITICAL
            elif metrics.memory_percent >= self.memory_thresholds['high']:
                self.memory_state = MemoryState.HIGH
            else:
                self.memory_state = MemoryState.NORMAL
            
        except Exception as e:
            logger.error(f"❌ Error updating memory state: {e}")
    
    def _get_optimization_sleep_duration(self) -> float:
        """Get optimization sleep duration based on level"""
        if self.optimization_level == OptimizationLevel.AGGRESSIVE:
            return 30.0  # 30 seconds
        elif self.optimization_level == OptimizationLevel.BALANCED:
            return 60.0  # 1 minute
        else:  # CONSERVATIVE
            return 120.0  # 2 minutes
    
    async def _light_cleanup(self):
        """Light cleanup actions"""
        try:
            # Light garbage collection
            gc.collect()
            
            # Clear some old metrics
            if len(self.memory_metrics) > 50:
                self.memory_metrics = self.memory_metrics[-50:]
            
            if len(self.cpu_metrics) > 50:
                self.cpu_metrics = self.cpu_metrics[-50:]
            
        except Exception as e:
            logger.error(f"❌ Error in light cleanup: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get performance optimization status"""
        return {
            'is_active': self.is_active,
            'optimization_level': self.optimization_level.value,
            'memory_state': self.memory_state.value,
            'sleep_state': self.sleep_state.value,
            'memory_metrics_count': len(self.memory_metrics),
            'cpu_metrics_count': len(self.cpu_metrics),
            'sleep_metrics': {
                'last_sleep_time': self.sleep_metrics.last_sleep_time.isoformat() if self.sleep_metrics.last_sleep_time else None,
                'last_wake_time': self.sleep_metrics.last_wake_time.isoformat() if self.sleep_metrics.last_wake_time else None,
                'sleep_duration': str(self.sleep_metrics.sleep_duration) if self.sleep_metrics.sleep_duration else None,
                'data_gaps': len(self.sleep_metrics.data_gaps),
                'recovery_actions': len(self.sleep_metrics.recovery_actions)
            },
            'performance_metrics': self.performance_metrics,
            'memory_thresholds': self.memory_thresholds,
            'cpu_thresholds': self.cpu_thresholds,
            'last_optimization': self.last_optimization.isoformat() if self.last_optimization else None
        }
