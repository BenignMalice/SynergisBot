"""
Backpressure Management System
Implements intelligent backpressure handling to prevent system overload
Prioritizes critical operations (exits/stops) over context features
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import queue
import weakref

logger = logging.getLogger(__name__)

class Priority(Enum):
    """Operation priority levels"""
    CRITICAL = 1    # Exits, stops, circuit breakers
    HIGH = 2        # Trade decisions, risk management
    MEDIUM = 3      # Market structure analysis
    LOW = 4         # Context features, order book data
    BACKGROUND = 5  # Historical analysis, reporting

class BackpressureState(Enum):
    """Backpressure system states"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class Operation:
    """Represents a system operation with priority"""
    operation_id: str
    priority: Priority
    operation_type: str
    data: Any
    timestamp_ns: int
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None

@dataclass
class BackpressureConfig:
    """Configuration for backpressure management"""
    # Queue size thresholds
    normal_threshold: float = 0.5      # 50% of max queue size
    warning_threshold: float = 0.7     # 70% of max queue size
    critical_threshold: float = 0.85   # 85% of max queue size
    emergency_threshold: float = 0.95  # 95% of max queue size
    
    # Processing limits
    max_operations_per_cycle: int = 100
    cycle_timeout_ms: int = 10
    
    # Drop policies
    drop_low_priority_when_warning: bool = True
    drop_medium_priority_when_critical: bool = True
    drop_high_priority_when_emergency: bool = False  # Never drop high priority
    
    # Monitoring
    stats_window_size: int = 1000
    alert_threshold: float = 0.8

@dataclass
class BackpressureStats:
    """Statistics for backpressure management"""
    total_operations: int = 0
    processed_operations: int = 0
    dropped_operations: int = 0
    dropped_by_priority: Dict[Priority, int] = field(default_factory=dict)
    current_queue_sizes: Dict[str, int] = field(default_factory=dict)
    avg_processing_time_ns: float = 0.0
    max_processing_time_ns: float = 0.0
    backpressure_events: int = 0
    emergency_events: int = 0

class BackpressureManager:
    """
    Manages system backpressure with intelligent prioritization
    Ensures critical operations are never dropped
    """
    
    def __init__(self, config: Optional[BackpressureConfig] = None):
        self.config = config or BackpressureConfig()
        
        # Priority queues for different operation types
        self.queues: Dict[str, queue.PriorityQueue] = {
            'critical': queue.PriorityQueue(maxsize=1000),
            'high': queue.PriorityQueue(maxsize=2000),
            'medium': queue.PriorityQueue(maxsize=5000),
            'low': queue.PriorityQueue(maxsize=10000),
            'background': queue.PriorityQueue(maxsize=5000)
        }
        
        # Processing state
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # Statistics and monitoring
        self.stats = BackpressureStats()
        self.state = BackpressureState.NORMAL
        self.state_lock = threading.RLock()
        
        # Callbacks for state changes
        self.state_callbacks: List[Callable[[BackpressureState], None]] = []
        self.alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Performance tracking
        self.processing_times = deque(maxlen=self.config.stats_window_size)
        self.queue_depths = deque(maxlen=100)
        
        logger.info("BackpressureManager initialized")
    
    def start(self):
        """Start the backpressure manager"""
        if self.running:
            logger.warning("BackpressureManager already running")
            return
        
        self.running = True
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            name="BackpressureProcessor",
            daemon=True
        )
        self.processing_thread.start()
        
        logger.info("BackpressureManager started")
    
    def stop(self):
        """Stop the backpressure manager"""
        if not self.running:
            return
        
        self.running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
        
        logger.info("BackpressureManager stopped")
    
    def submit_operation(self, operation: Operation) -> bool:
        """
        Submit an operation for processing
        Returns True if queued successfully, False if dropped
        """
        try:
            # Determine queue based on priority
            queue_name = self._get_queue_name(operation.priority)
            
            # Check if we should drop this operation
            if self._should_drop_operation(operation):
                self.stats.dropped_operations += 1
                self.stats.dropped_by_priority[operation.priority] = \
                    self.stats.dropped_by_priority.get(operation.priority, 0) + 1
                return False
            
            # Add to appropriate queue
            priority_value = operation.priority.value
            self.queues[queue_name].put((priority_value, operation))
            
            self.stats.total_operations += 1
            return True
            
        except queue.Full:
            # Queue is full, drop operation
            self.stats.dropped_operations += 1
            self.stats.dropped_by_priority[operation.priority] = \
                self.stats.dropped_by_priority.get(operation.priority, 0) + 1
            return False
        except Exception as e:
            logger.error(f"Error submitting operation: {e}")
            return False
    
    def _get_queue_name(self, priority: Priority) -> str:
        """Get queue name for priority level"""
        if priority == Priority.CRITICAL:
            return 'critical'
        elif priority == Priority.HIGH:
            return 'high'
        elif priority == Priority.MEDIUM:
            return 'medium'
        elif priority == Priority.LOW:
            return 'low'
        else:
            return 'background'
    
    def _should_drop_operation(self, operation: Operation) -> bool:
        """Determine if an operation should be dropped based on current state"""
        with self.state_lock:
            current_state = self.state
            
            # Never drop critical operations
            if operation.priority == Priority.CRITICAL:
                return False
            
            # Drop low priority when in warning state
            if (current_state == BackpressureState.WARNING and 
                operation.priority == Priority.LOW and 
                self.config.drop_low_priority_when_warning):
                return True
            
            # Drop medium priority when in critical state
            if (current_state == BackpressureState.CRITICAL and 
                operation.priority == Priority.MEDIUM and 
                self.config.drop_medium_priority_when_critical):
                return True
            
            # Drop high priority only in emergency (if configured)
            if (current_state == BackpressureState.EMERGENCY and 
                operation.priority == Priority.HIGH and 
                self.config.drop_high_priority_when_emergency):
                return True
            
            return False
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                start_time = time.perf_counter_ns()
                
                # Process operations from all queues in priority order
                operations_processed = 0
                
                for queue_name in ['critical', 'high', 'medium', 'low', 'background']:
                    if operations_processed >= self.config.max_operations_per_cycle:
                        break
                    
                    queue_ops = self._process_queue(queue_name)
                    operations_processed += queue_ops
                
                # Update statistics
                end_time = time.perf_counter_ns()
                processing_time_ns = end_time - start_time
                self.processing_times.append(processing_time_ns)
                
                self.stats.processed_operations += operations_processed
                self._update_processing_stats(processing_time_ns)
                
                # Update backpressure state
                self._update_backpressure_state()
                
                # Update queue depth tracking
                self._update_queue_depths()
                
                # Brief pause to prevent CPU spinning
                time.sleep(0.001)  # 1ms pause
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(0.01)  # 10ms pause on error
    
    def _process_queue(self, queue_name: str) -> int:
        """Process operations from a specific queue"""
        operations_processed = 0
        queue_obj = self.queues[queue_name]
        
        try:
            while not queue_obj.empty() and operations_processed < self.config.max_operations_per_cycle:
                try:
                    # Get operation with timeout
                    priority_value, operation = queue_obj.get(timeout=0.001)
                    
                    # Process operation
                    self._process_operation(operation)
                    operations_processed += 1
                    
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error processing operation: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error processing queue {queue_name}: {e}")
        
        return operations_processed
    
    def _process_operation(self, operation: Operation):
        """Process a single operation"""
        try:
            # Execute operation callback if provided
            if operation.callback:
                operation.callback(operation.data)
            
            # Update operation statistics
            self.stats.processed_operations += 1
            
        except Exception as e:
            logger.error(f"Error processing operation {operation.operation_id}: {e}")
            
            # Retry logic
            if operation.retry_count < operation.max_retries:
                operation.retry_count += 1
                # Re-queue operation
                self.submit_operation(operation)
            else:
                logger.error(f"Operation {operation.operation_id} failed after {operation.max_retries} retries")
    
    def _update_backpressure_state(self):
        """Update backpressure state based on queue depths"""
        with self.state_lock:
            old_state = self.state
            
            # Calculate total queue utilization
            total_operations = sum(q.qsize() for q in self.queues.values())
            max_queue_size = sum(q.maxsize for q in self.queues.values())
            utilization = total_operations / max_queue_size if max_queue_size > 0 else 0.0
            
            # Determine new state
            if utilization >= self.config.emergency_threshold:
                new_state = BackpressureState.EMERGENCY
            elif utilization >= self.config.critical_threshold:
                new_state = BackpressureState.CRITICAL
            elif utilization >= self.config.warning_threshold:
                new_state = BackpressureState.WARNING
            else:
                new_state = BackpressureState.NORMAL
            
            # Update state if changed
            if new_state != old_state:
                self.state = new_state
                self._notify_state_change(new_state)
                
                if new_state == BackpressureState.EMERGENCY:
                    self.stats.emergency_events += 1
                elif new_state in [BackpressureState.CRITICAL, BackpressureState.WARNING]:
                    self.stats.backpressure_events += 1
    
    def _update_processing_stats(self, processing_time_ns: float):
        """Update processing statistics"""
        self.stats.avg_processing_time_ns = (
            (self.stats.avg_processing_time_ns * (self.stats.processed_operations - 1) + processing_time_ns) 
            / self.stats.processed_operations
        )
        self.stats.max_processing_time_ns = max(self.stats.max_processing_time_ns, processing_time_ns)
    
    def _update_queue_depths(self):
        """Update queue depth tracking"""
        current_depths = {
            queue_name: q.qsize() 
            for queue_name, q in self.queues.items()
        }
        
        self.stats.current_queue_sizes = current_depths
        self.queue_depths.append(current_depths)
    
    def _notify_state_change(self, new_state: BackpressureState):
        """Notify callbacks of state change"""
        for callback in self.state_callbacks:
            try:
                callback(new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
        
        # Send alert if threshold exceeded
        if new_state in [BackpressureState.CRITICAL, BackpressureState.EMERGENCY]:
            alert_data = {
                'state': new_state.value,
                'queue_sizes': dict(self.stats.current_queue_sizes),
                'utilization': self._get_utilization(),
                'timestamp': time.time()
            }
            
            for callback in self.alert_callbacks:
                try:
                    callback(f"Backpressure {new_state.value}", alert_data)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def _get_utilization(self) -> float:
        """Get current system utilization"""
        total_operations = sum(q.qsize() for q in self.queues.values())
        max_queue_size = sum(q.maxsize for q in self.queues.values())
        return total_operations / max_queue_size if max_queue_size > 0 else 0.0
    
    def add_state_callback(self, callback: Callable[[BackpressureState], None]):
        """Add callback for state changes"""
        self.state_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add callback for alerts"""
        self.alert_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics"""
        with self.state_lock:
            return {
                'state': self.state.value,
                'stats': {
                    'total_operations': self.stats.total_operations,
                    'processed_operations': self.stats.processed_operations,
                    'dropped_operations': self.stats.dropped_operations,
                    'dropped_by_priority': {
                        priority.value: count 
                        for priority, count in self.stats.dropped_by_priority.items()
                    },
                    'current_queue_sizes': dict(self.stats.current_queue_sizes),
                    'avg_processing_time_ms': self.stats.avg_processing_time_ns / 1_000_000,
                    'max_processing_time_ms': self.stats.max_processing_time_ns / 1_000_000,
                    'backpressure_events': self.stats.backpressure_events,
                    'emergency_events': self.stats.emergency_events
                },
                'utilization': self._get_utilization(),
                'config': {
                    'normal_threshold': self.config.normal_threshold,
                    'warning_threshold': self.config.warning_threshold,
                    'critical_threshold': self.config.critical_threshold,
                    'emergency_threshold': self.config.emergency_threshold
                }
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of backpressure system"""
        with self.state_lock:
            utilization = self._get_utilization()
            
            return {
                'healthy': self.state in [BackpressureState.NORMAL, BackpressureState.WARNING],
                'state': self.state.value,
                'utilization': utilization,
                'queue_sizes': dict(self.stats.current_queue_sizes),
                'processing_rate': self.stats.processed_operations / max(time.time(), 1),
                'drop_rate': self.stats.dropped_operations / max(self.stats.total_operations, 1)
            }
    
    def force_emergency_mode(self):
        """Force system into emergency mode (for testing)"""
        with self.state_lock:
            self.state = BackpressureState.EMERGENCY
            self._notify_state_change(BackpressureState.EMERGENCY)
    
    def reset_stats(self):
        """Reset statistics"""
        self.stats = BackpressureStats()
        self.processing_times.clear()
        self.queue_depths.clear()
        logger.info("Backpressure statistics reset")

# Global backpressure manager instance
_backpressure_manager: Optional[BackpressureManager] = None

def get_backpressure_manager() -> Optional[BackpressureManager]:
    """Get the global backpressure manager instance"""
    return _backpressure_manager

def initialize_backpressure_manager(config: Optional[BackpressureConfig] = None) -> BackpressureManager:
    """Initialize the global backpressure manager"""
    global _backpressure_manager
    _backpressure_manager = BackpressureManager(config)
    _backpressure_manager.start()
    return _backpressure_manager

def shutdown_backpressure_manager():
    """Shutdown the global backpressure manager"""
    global _backpressure_manager
    if _backpressure_manager:
        _backpressure_manager.stop()
        _backpressure_manager = None
