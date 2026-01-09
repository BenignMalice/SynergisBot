"""
Advanced Queue Monitoring System
Comprehensive queue monitoring with alarm functionality for system overload prevention
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import os
from collections import defaultdict, deque
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import queue as py_queue

logger = logging.getLogger(__name__)

class QueueStatus(Enum):
    """Queue status classifications."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OVERFLOW = "overflow"

class AlarmSeverity(Enum):
    """Alarm severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class QueueType(Enum):
    """Queue type classifications."""
    TICK_PROCESSING = "tick_processing"
    DATABASE_WRITE = "database_write"
    BINANCE_WEBSOCKET = "binance_websocket"
    MT5_INGESTION = "mt5_ingestion"
    VWAP_CALCULATION = "vwap_calculation"
    ATR_PROCESSING = "atr_processing"
    DELTA_ANALYSIS = "delta_analysis"
    MICRO_BOS = "micro_bos"
    SPREAD_FILTER = "spread_filter"
    EXIT_SIGNALS = "exit_signals"
    STOP_MANAGEMENT = "stop_management"
    TRADE_EXECUTION = "trade_execution"

@dataclass
class QueueThresholds:
    """Queue monitoring thresholds."""
    queue_type: QueueType
    warning_threshold: int = 100
    critical_threshold: int = 500
    overflow_threshold: int = 1000
    max_capacity: int = 2000
    check_interval_ms: int = 100
    alarm_cooldown_ms: int = 5000

@dataclass
class QueueMetrics:
    """Queue performance metrics."""
    queue_type: QueueType
    current_size: int = 0
    max_size: int = 0
    avg_size: float = 0.0
    processing_rate: float = 0.0
    wait_time_ms: float = 0.0
    overflow_count: int = 0
    last_overflow_time: float = 0.0
    status: QueueStatus = QueueStatus.HEALTHY
    last_update: float = 0.0

@dataclass
class AlarmEvent:
    """Alarm event data."""
    timestamp: float
    queue_type: QueueType
    severity: AlarmSeverity
    message: str
    current_size: int
    threshold: int
    metrics: Dict[str, Any]

class QueueMonitor:
    """Individual queue monitor for a specific queue type."""
    
    def __init__(self, thresholds: QueueThresholds):
        self.thresholds = thresholds
        self.metrics = QueueMetrics(queue_type=thresholds.queue_type)
        self.size_history = deque(maxlen=1000)  # Keep last 1000 measurements
        self.processing_times = deque(maxlen=100)  # Keep last 100 processing times
        self.alarm_callbacks: List[Callable] = []
        self.last_alarm_time = 0.0
        self.lock = threading.RLock()
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
    def start_monitoring(self):
        """Start queue monitoring."""
        with self.lock:
            if not self.is_monitoring:
                self.is_monitoring = True
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()
                logger.info(f"Started monitoring for {self.thresholds.queue_type.value}")
    
    def stop_monitoring(self):
        """Stop queue monitoring."""
        with self.lock:
            if self.is_monitoring:
                self.is_monitoring = False
                if self.monitor_thread:
                    self.monitor_thread.join(timeout=1.0)
                logger.info(f"Stopped monitoring for {self.thresholds.queue_type.value}")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                self._update_metrics()
                self._check_thresholds()
                time.sleep(self.thresholds.check_interval_ms / 1000.0)
            except Exception as e:
                logger.error(f"Error in monitor loop for {self.thresholds.queue_type.value}: {e}")
                time.sleep(1.0)
    
    def update_queue_size(self, size: int):
        """Update current queue size."""
        with self.lock:
            current_time = time.time()
            self.metrics.current_size = size
            self.metrics.max_size = max(self.metrics.max_size, size)
            self.metrics.last_update = current_time
            
            # Add to history
            self.size_history.append((current_time, size))
            
            # Update average size
            if len(self.size_history) > 0:
                self.metrics.avg_size = sum(size for _, size in self.size_history) / len(self.size_history)
            
            # Check thresholds immediately
            self._check_thresholds()
    
    def record_processing_time(self, processing_time_ms: float):
        """Record processing time for rate calculation."""
        with self.lock:
            self.processing_times.append(processing_time_ms)
            
            # Calculate processing rate (items per second)
            if len(self.processing_times) > 1:
                total_time = sum(self.processing_times)
                if total_time > 0:
                    self.metrics.processing_rate = len(self.processing_times) / (total_time / 1000.0)
                else:
                    self.metrics.processing_rate = 0.0
    
    def _update_metrics(self):
        """Update queue metrics."""
        with self.lock:
            current_time = time.time()
            
            # Calculate wait time based on queue size and processing rate
            if self.metrics.processing_rate > 0:
                self.metrics.wait_time_ms = (self.metrics.current_size / self.metrics.processing_rate) * 1000.0
            else:
                self.metrics.wait_time_ms = 0.0
    
    def _check_thresholds(self):
        """Check if queue exceeds thresholds and trigger alarms."""
        with self.lock:
            current_size = self.metrics.current_size
            current_time = time.time()
            
            # Check for overflow
            if current_size >= self.thresholds.overflow_threshold:
                self._trigger_alarm(
                    AlarmSeverity.EMERGENCY,
                    f"Queue overflow: {current_size} >= {self.thresholds.overflow_threshold}",
                    current_size,
                    self.thresholds.overflow_threshold
                )
                self.metrics.status = QueueStatus.OVERFLOW
                self.metrics.overflow_count += 1
                self.metrics.last_overflow_time = current_time
                
            # Check for critical threshold
            elif current_size >= self.thresholds.critical_threshold:
                self._trigger_alarm(
                    AlarmSeverity.CRITICAL,
                    f"Queue critical: {current_size} >= {self.thresholds.critical_threshold}",
                    current_size,
                    self.thresholds.critical_threshold
                )
                self.metrics.status = QueueStatus.CRITICAL
                
            # Check for warning threshold
            elif current_size >= self.thresholds.warning_threshold:
                self._trigger_alarm(
                    AlarmSeverity.WARNING,
                    f"Queue warning: {current_size} >= {self.thresholds.warning_threshold}",
                    current_size,
                    self.thresholds.warning_threshold
                )
                self.metrics.status = QueueStatus.WARNING
                
            else:
                self.metrics.status = QueueStatus.HEALTHY
    
    def _trigger_alarm(self, severity: AlarmSeverity, message: str, current_size: int, threshold: int):
        """Trigger alarm with cooldown protection."""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_alarm_time < (self.thresholds.alarm_cooldown_ms / 1000.0):
            return
        
        self.last_alarm_time = current_time
        
        # Create alarm event
        alarm_event = AlarmEvent(
            timestamp=current_time,
            queue_type=self.thresholds.queue_type,
            severity=severity,
            message=message,
            current_size=current_size,
            threshold=threshold,
            metrics=self.get_metrics_dict()
        )
        
        # Trigger callbacks
        for callback in self.alarm_callbacks:
            try:
                callback(alarm_event)
            except Exception as e:
                logger.error(f"Error in alarm callback: {e}")
    
    def add_alarm_callback(self, callback: Callable[[AlarmEvent], None]):
        """Add alarm callback."""
        self.alarm_callbacks.append(callback)
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get current metrics as dictionary."""
        with self.lock:
            return {
                'queue_type': self.metrics.queue_type.value,
                'current_size': self.metrics.current_size,
                'max_size': self.metrics.max_size,
                'avg_size': self.metrics.avg_size,
                'processing_rate': self.metrics.processing_rate,
                'wait_time_ms': self.metrics.wait_time_ms,
                'overflow_count': self.metrics.overflow_count,
                'last_overflow_time': self.metrics.last_overflow_time,
                'status': self.metrics.status.value,
                'last_update': self.metrics.last_update
            }
    
    def get_status(self) -> QueueStatus:
        """Get current queue status."""
        with self.lock:
            return self.metrics.status
    
    def reset_metrics(self):
        """Reset queue metrics."""
        with self.lock:
            self.metrics = QueueMetrics(queue_type=self.thresholds.queue_type)
            self.size_history.clear()
            self.processing_times.clear()

class QueueMonitoringManager:
    """Comprehensive queue monitoring management system."""
    
    def __init__(self):
        self.monitors: Dict[QueueType, QueueMonitor] = {}
        self.global_alarm_callbacks: List[Callable] = []
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        
        # Initialize default queue monitors
        self._initialize_default_monitors()
    
    def _initialize_default_monitors(self):
        """Initialize default queue monitors for all queue types."""
        default_thresholds = {
            QueueType.TICK_PROCESSING: QueueThresholds(
                queue_type=QueueType.TICK_PROCESSING,
                warning_threshold=50,
                critical_threshold=200,
                overflow_threshold=500,
                max_capacity=1000
            ),
            QueueType.DATABASE_WRITE: QueueThresholds(
                queue_type=QueueType.DATABASE_WRITE,
                warning_threshold=100,
                critical_threshold=300,
                overflow_threshold=600,
                max_capacity=1000
            ),
            QueueType.BINANCE_WEBSOCKET: QueueThresholds(
                queue_type=QueueType.BINANCE_WEBSOCKET,
                warning_threshold=20,
                critical_threshold=50,
                overflow_threshold=100,
                max_capacity=200
            ),
            QueueType.MT5_INGESTION: QueueThresholds(
                queue_type=QueueType.MT5_INGESTION,
                warning_threshold=30,
                critical_threshold=100,
                overflow_threshold=200,
                max_capacity=500
            ),
            QueueType.VWAP_CALCULATION: QueueThresholds(
                queue_type=QueueType.VWAP_CALCULATION,
                warning_threshold=40,
                critical_threshold=150,
                overflow_threshold=300,
                max_capacity=600
            ),
            QueueType.ATR_PROCESSING: QueueThresholds(
                queue_type=QueueType.ATR_PROCESSING,
                warning_threshold=30,
                critical_threshold=100,
                overflow_threshold=200,
                max_capacity=400
            ),
            QueueType.DELTA_ANALYSIS: QueueThresholds(
                queue_type=QueueType.DELTA_ANALYSIS,
                warning_threshold=25,
                critical_threshold=80,
                overflow_threshold=150,
                max_capacity=300
            ),
            QueueType.MICRO_BOS: QueueThresholds(
                queue_type=QueueType.MICRO_BOS,
                warning_threshold=20,
                critical_threshold=60,
                overflow_threshold=120,
                max_capacity=250
            ),
            QueueType.SPREAD_FILTER: QueueThresholds(
                queue_type=QueueType.SPREAD_FILTER,
                warning_threshold=15,
                critical_threshold=40,
                overflow_threshold=80,
                max_capacity=150
            ),
            QueueType.EXIT_SIGNALS: QueueThresholds(
                queue_type=QueueType.EXIT_SIGNALS,
                warning_threshold=10,
                critical_threshold=25,
                overflow_threshold=50,
                max_capacity=100
            ),
            QueueType.STOP_MANAGEMENT: QueueThresholds(
                queue_type=QueueType.STOP_MANAGEMENT,
                warning_threshold=15,
                critical_threshold=40,
                overflow_threshold=80,
                max_capacity=150
            ),
            QueueType.TRADE_EXECUTION: QueueThresholds(
                queue_type=QueueType.TRADE_EXECUTION,
                warning_threshold=5,
                critical_threshold=15,
                overflow_threshold=30,
                max_capacity=50
            )
        }
        
        for queue_type, thresholds in default_thresholds.items():
            self.add_queue_monitor(thresholds)
    
    def add_queue_monitor(self, thresholds: QueueThresholds):
        """Add a queue monitor for a specific queue type."""
        with self.lock:
            monitor = QueueMonitor(thresholds)
            self.monitors[thresholds.queue_type] = monitor
            
            # Add global alarm callback
            monitor.add_alarm_callback(self._handle_global_alarm)
            
            logger.info(f"Added queue monitor for {thresholds.queue_type.value}")
    
    def start_monitoring(self):
        """Start monitoring all queues."""
        with self.lock:
            if not self.is_monitoring:
                self.is_monitoring = True
                
                # Start all individual monitors
                for monitor in self.monitors.values():
                    monitor.start_monitoring()
                
                # Start global monitoring thread
                self.monitoring_thread = threading.Thread(target=self._global_monitor_loop, daemon=True)
                self.monitoring_thread.start()
                
                logger.info("Started queue monitoring for all queues")
    
    def stop_monitoring(self):
        """Stop monitoring all queues."""
        with self.lock:
            if self.is_monitoring:
                self.is_monitoring = False
                
                # Stop all individual monitors
                for monitor in self.monitors.values():
                    monitor.stop_monitoring()
                
                # Stop global monitoring thread
                if self.monitoring_thread:
                    self.monitoring_thread.join(timeout=2.0)
                
                logger.info("Stopped queue monitoring for all queues")
    
    def _global_monitor_loop(self):
        """Global monitoring loop for system-wide metrics."""
        while self.is_monitoring:
            try:
                self._update_global_metrics()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in global monitor loop: {e}")
                time.sleep(5.0)
    
    def _update_global_metrics(self):
        """Update global system metrics."""
        with self.lock:
            # Calculate system-wide metrics
            total_queues = len(self.monitors)
            healthy_queues = sum(1 for monitor in self.monitors.values() 
                               if monitor.get_status() == QueueStatus.HEALTHY)
            warning_queues = sum(1 for monitor in self.monitors.values() 
                               if monitor.get_status() == QueueStatus.WARNING)
            critical_queues = sum(1 for monitor in self.monitors.values() 
                                if monitor.get_status() == QueueStatus.CRITICAL)
            overflow_queues = sum(1 for monitor in self.monitors.values() 
                                if monitor.get_status() == QueueStatus.OVERFLOW)
            
            # Trigger system-wide alarms if needed
            if overflow_queues > 0:
                self._trigger_system_alarm(
                    AlarmSeverity.EMERGENCY,
                    f"System overflow: {overflow_queues} queues in overflow state"
                )
            elif critical_queues > 2:
                self._trigger_system_alarm(
                    AlarmSeverity.CRITICAL,
                    f"System critical: {critical_queues} queues in critical state"
                )
            elif warning_queues > 5:
                self._trigger_system_alarm(
                    AlarmSeverity.WARNING,
                    f"System warning: {warning_queues} queues in warning state"
                )
    
    def _trigger_system_alarm(self, severity: AlarmSeverity, message: str):
        """Trigger system-wide alarm."""
        current_time = time.time()
        
        alarm_event = AlarmEvent(
            timestamp=current_time,
            queue_type=QueueType.TICK_PROCESSING,  # Use a default type for system alarms
            severity=severity,
            message=message,
            current_size=0,
            threshold=0,
            metrics={'system_alarm': True}
        )
        
        for callback in self.global_alarm_callbacks:
            try:
                callback(alarm_event)
            except Exception as e:
                logger.error(f"Error in global alarm callback: {e}")
    
    def _handle_global_alarm(self, alarm_event: AlarmEvent):
        """Handle alarms from individual queue monitors."""
        # Log the alarm
        logger.warning(f"Queue alarm: {alarm_event.queue_type.value} - {alarm_event.severity.value}: {alarm_event.message}")
        
        # Forward to global callbacks
        for callback in self.global_alarm_callbacks:
            try:
                callback(alarm_event)
            except Exception as e:
                logger.error(f"Error in global alarm callback: {e}")
    
    def update_queue_size(self, queue_type: QueueType, size: int):
        """Update queue size for a specific queue type."""
        if queue_type in self.monitors:
            self.monitors[queue_type].update_queue_size(size)
    
    def record_processing_time(self, queue_type: QueueType, processing_time_ms: float):
        """Record processing time for a specific queue type."""
        if queue_type in self.monitors:
            self.monitors[queue_type].record_processing_time(processing_time_ms)
    
    def get_queue_status(self, queue_type: QueueType) -> Optional[QueueStatus]:
        """Get status for a specific queue."""
        if queue_type in self.monitors:
            return self.monitors[queue_type].get_status()
        return None
    
    def get_all_queue_metrics(self) -> Dict[str, Any]:
        """Get metrics for all queues."""
        with self.lock:
            metrics = {}
            for queue_type, monitor in self.monitors.items():
                metrics[queue_type.value] = monitor.get_metrics_dict()
            return metrics
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        with self.lock:
            total_queues = len(self.monitors)
            healthy_queues = sum(1 for monitor in self.monitors.values() 
                               if monitor.get_status() == QueueStatus.HEALTHY)
            warning_queues = sum(1 for monitor in self.monitors.values() 
                               if monitor.get_status() == QueueStatus.WARNING)
            critical_queues = sum(1 for monitor in self.monitors.values() 
                                if monitor.get_status() == QueueStatus.CRITICAL)
            overflow_queues = sum(1 for monitor in self.monitors.values() 
                                if monitor.get_status() == QueueStatus.OVERFLOW)
            
            return {
                'total_queues': total_queues,
                'healthy_queues': healthy_queues,
                'warning_queues': warning_queues,
                'critical_queues': critical_queues,
                'overflow_queues': overflow_queues,
                'system_health': 'healthy' if overflow_queues == 0 and critical_queues <= 1 else 'degraded',
                'timestamp': time.time()
            }
    
    def add_global_alarm_callback(self, callback: Callable[[AlarmEvent], None]):
        """Add global alarm callback."""
        self.global_alarm_callbacks.append(callback)
    
    def reset_all_metrics(self):
        """Reset metrics for all queues."""
        with self.lock:
            for monitor in self.monitors.values():
                monitor.reset_metrics()
            logger.info("Reset metrics for all queues")

# Global queue monitoring manager instance
queue_monitoring_manager = QueueMonitoringManager()

def get_queue_monitoring_manager() -> QueueMonitoringManager:
    """Get the global queue monitoring manager instance."""
    return queue_monitoring_manager

def start_queue_monitoring():
    """Start global queue monitoring."""
    queue_monitoring_manager.start_monitoring()

def stop_queue_monitoring():
    """Stop global queue monitoring."""
    queue_monitoring_manager.stop_monitoring()

def update_queue_size(queue_type: QueueType, size: int):
    """Update queue size for a specific queue type."""
    queue_monitoring_manager.update_queue_size(queue_type, size)

def record_processing_time(queue_type: QueueType, processing_time_ms: float):
    """Record processing time for a specific queue type."""
    queue_monitoring_manager.record_processing_time(queue_type, processing_time_ms)

def get_queue_status(queue_type: QueueType) -> Optional[QueueStatus]:
    """Get status for a specific queue."""
    return queue_monitoring_manager.get_queue_status(queue_type)

def get_system_status() -> Dict[str, Any]:
    """Get overall system status."""
    return queue_monitoring_manager.get_system_status()

if __name__ == "__main__":
    # Example usage
    manager = QueueMonitoringManager()
    
    # Add alarm callback
    def alarm_callback(alarm_event: AlarmEvent):
        print(f"ALARM: {alarm_event.severity.value} - {alarm_event.message}")
    
    manager.add_global_alarm_callback(alarm_callback)
    
    # Start monitoring
    manager.start_monitoring()
    
    # Simulate queue updates
    manager.update_queue_size(QueueType.TICK_PROCESSING, 150)
    manager.update_queue_size(QueueType.DATABASE_WRITE, 350)
    
    # Wait a bit
    time.sleep(2.0)
    
    # Get system status
    status = manager.get_system_status()
    print(f"System status: {json.dumps(status, indent=2)}")
    
    # Stop monitoring
    manager.stop_monitoring()
