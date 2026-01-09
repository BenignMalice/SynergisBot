"""
Rollback Mechanism System

This module implements a comprehensive rollback mechanism that automatically
rolls back system changes if any breaker triggers twice within a 5-day window.
This provides critical production safety and risk management capabilities.

Key Features:
- Automatic rollback detection and execution
- Breaker trigger tracking and analysis
- 5-day window monitoring
- System state restoration
- Risk assessment and mitigation
- Production safety guarantees
"""

import time
import json
import logging
import threading
import shutil
import os
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
import pickle
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger(__name__)

class RollbackStatus(Enum):
    """Rollback mechanism status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"

class BreakerType(Enum):
    """Types of circuit breakers"""
    LATENCY = "latency"
    DRAWDOWN = "drawdown"
    QUEUE_BACKPRESSURE = "queue_backpressure"
    DATA_QUALITY = "data_quality"
    SYSTEM_HEALTH = "system_health"
    PERFORMANCE = "performance"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"

class RollbackTrigger(Enum):
    """Rollback trigger conditions"""
    BREAKER_DOUBLE_TRIGGER = "breaker_double_trigger"
    MANUAL_INITIATION = "manual_initiation"
    SYSTEM_FAILURE = "system_failure"
    DATA_CORRUPTION = "data_corruption"
    SECURITY_BREACH = "security_breach"

class RollbackPriority(Enum):
    """Rollback priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class BreakerEvent:
    """Circuit breaker trigger event"""
    timestamp: float
    breaker_type: BreakerType
    severity: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[float] = None

@dataclass
class RollbackPoint:
    """System rollback point"""
    point_id: str
    timestamp: float
    description: str
    system_state: Dict[str, Any]
    configuration_snapshot: Dict[str, Any]
    database_snapshot: Optional[str] = None
    file_backups: Dict[str, str] = field(default_factory=dict)
    checksum: str = ""
    priority: RollbackPriority = RollbackPriority.MEDIUM

@dataclass
class RollbackOperation:
    """Rollback operation details"""
    operation_id: str
    timestamp: float
    trigger: RollbackTrigger
    rollback_point: RollbackPoint
    status: RollbackStatus
    progress: float = 0.0
    error_message: Optional[str] = None
    execution_time: float = 0.0
    affected_components: List[str] = field(default_factory=list)

@dataclass
class RollbackMetrics:
    """Rollback system metrics"""
    total_rollbacks: int = 0
    successful_rollbacks: int = 0
    failed_rollbacks: int = 0
    avg_rollback_time: float = 0.0
    breaker_trigger_count: int = 0
    double_trigger_count: int = 0
    last_rollback_time: Optional[float] = None
    rollback_points_created: int = 0
    rollback_points_used: int = 0

class BreakerTracker:
    """Tracks circuit breaker events and triggers"""
    
    def __init__(self, window_days: int = 5):
        self.window_days = window_days
        self.window_seconds = window_days * 24 * 3600
        self.breaker_events: Dict[BreakerType, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.double_triggers: List[Tuple[BreakerType, float]] = []
        self.lock = threading.RLock()
    
    def record_breaker_event(self, breaker_type: BreakerType, severity: str, 
                            message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a circuit breaker event"""
        timestamp = time.time()
        
        with self.lock:
            event = BreakerEvent(
                timestamp=timestamp,
                breaker_type=breaker_type,
                severity=severity,
                message=message,
                metadata=metadata or {}
            )
            
            self.breaker_events[breaker_type].append(event)
            
            # Check for double trigger within window
            if self._is_double_trigger(breaker_type, timestamp):
                self.double_triggers.append((breaker_type, timestamp))
                logger.warning(f"Double trigger detected for {breaker_type.value} at {timestamp}")
    
    def _is_double_trigger(self, breaker_type: BreakerType, timestamp: float) -> bool:
        """Check if this is a double trigger within the window"""
        cutoff_time = timestamp - self.window_seconds
        events = self.breaker_events[breaker_type]
        
        # Count events within window
        recent_events = [e for e in events if e.timestamp >= cutoff_time]
        
        # Check for high severity events (potential triggers)
        high_severity_events = [
            e for e in recent_events 
            if e.severity in ['high', 'critical', 'emergency']
        ]
        
        return len(high_severity_events) >= 2
    
    def get_breaker_statistics(self) -> Dict[str, Any]:
        """Get breaker statistics"""
        with self.lock:
            stats = {
                'total_events': sum(len(events) for events in self.breaker_events.values()),
                'double_triggers': len(self.double_triggers),
                'breaker_types': len(self.breaker_events),
                'window_days': self.window_days
            }
            
            # Add per-breaker statistics
            for breaker_type, events in self.breaker_events.items():
                stats[f'{breaker_type.value}_events'] = len(events)
                if events:
                    stats[f'{breaker_type.value}_latest'] = events[-1].timestamp
            
            return stats
    
    def get_recent_double_triggers(self, hours: int = 24) -> List[Tuple[BreakerType, float]]:
        """Get recent double triggers within specified hours"""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            return [
                (breaker_type, timestamp) 
                for breaker_type, timestamp in self.double_triggers
                if timestamp >= cutoff_time
            ]

class SystemStateManager:
    """Manages system state snapshots and restoration"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = backup_dir
        self.rollback_points: Dict[str, RollbackPoint] = {}
        self.lock = threading.RLock()
        
        # Ensure backup directory exists
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_rollback_point(self, description: str, 
                            system_state: Dict[str, Any],
                            configuration: Dict[str, Any],
                            priority: RollbackPriority = RollbackPriority.MEDIUM) -> RollbackPoint:
        """Create a system rollback point"""
        point_id = f"rb_{int(time.time())}_{hashlib.md5(description.encode()).hexdigest()[:8]}"
        timestamp = time.time()
        
        # Create configuration snapshot
        config_snapshot = self._deep_copy_dict(configuration)
        
        # Create system state snapshot
        state_snapshot = self._deep_copy_dict(system_state)
        
        # Calculate checksum
        checksum = self._calculate_checksum(state_snapshot, config_snapshot)
        
        rollback_point = RollbackPoint(
            point_id=point_id,
            timestamp=timestamp,
            description=description,
            system_state=state_snapshot,
            configuration_snapshot=config_snapshot,
            checksum=checksum,
            priority=priority
        )
        
        with self.lock:
            self.rollback_points[point_id] = rollback_point
        
        # Save to disk
        self._save_rollback_point(rollback_point)
        
        return rollback_point
    
    def _deep_copy_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of dictionary data"""
        return pickle.loads(pickle.dumps(data))
    
    def _calculate_checksum(self, state: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Calculate checksum for rollback point"""
        combined_data = {
            'state': state,
            'config': config,
            'timestamp': time.time()
        }
        
        data_str = json.dumps(combined_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _save_rollback_point(self, rollback_point: RollbackPoint) -> None:
        """Save rollback point to disk"""
        file_path = os.path.join(self.backup_dir, f"{rollback_point.point_id}.json")
        
        # Convert to serializable format
        data = asdict(rollback_point)
        data['timestamp'] = rollback_point.timestamp
        data['priority'] = rollback_point.priority.value  # Convert enum to string
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_rollback_point(self, point_id: str) -> Optional[RollbackPoint]:
        """Get rollback point by ID"""
        with self.lock:
            return self.rollback_points.get(point_id)
    
    def get_latest_rollback_point(self) -> Optional[RollbackPoint]:
        """Get the latest rollback point"""
        with self.lock:
            if not self.rollback_points:
                return None
            
            latest_point = max(
                self.rollback_points.values(),
                key=lambda x: x.timestamp
            )
            return latest_point
    
    def list_rollback_points(self, limit: Optional[int] = None) -> List[RollbackPoint]:
        """List rollback points"""
        with self.lock:
            points = list(self.rollback_points.values())
            points.sort(key=lambda x: x.timestamp, reverse=True)
            
            if limit:
                return points[:limit]
            return points
    
    def restore_system_state(self, rollback_point: RollbackPoint) -> bool:
        """Restore system to a rollback point"""
        try:
            # Validate rollback point
            if not self._validate_rollback_point(rollback_point):
                logger.error(f"Invalid rollback point: {rollback_point.point_id}")
                return False
            
            # Restore system state
            self._restore_system_state(rollback_point.system_state)
            
            # Restore configuration
            self._restore_configuration(rollback_point.configuration_snapshot)
            
            # Restore database if available
            if rollback_point.database_snapshot:
                self._restore_database(rollback_point.database_snapshot)
            
            # Restore files if available
            for file_path, backup_path in rollback_point.file_backups.items():
                self._restore_file(file_path, backup_path)
            
            logger.info(f"Successfully restored system to rollback point: {rollback_point.point_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore system state: {e}")
            return False
    
    def _validate_rollback_point(self, rollback_point: RollbackPoint) -> bool:
        """Validate rollback point integrity"""
        # Check if point exists
        if rollback_point.point_id not in self.rollback_points:
            return False
        
        # Verify checksum
        expected_checksum = self._calculate_checksum(
            rollback_point.system_state,
            rollback_point.configuration_snapshot
        )
        
        return rollback_point.checksum == expected_checksum
    
    def _restore_system_state(self, system_state: Dict[str, Any]) -> None:
        """Restore system state"""
        # This would be implemented based on specific system requirements
        # For now, we'll log the restoration
        logger.info(f"Restoring system state: {len(system_state)} components")
        
        # Example restoration logic (would be system-specific)
        for component, state in system_state.items():
            logger.info(f"Restoring component {component}: {state}")
    
    def _restore_configuration(self, configuration: Dict[str, Any]) -> None:
        """Restore configuration"""
        logger.info(f"Restoring configuration: {len(configuration)} settings")
        
        # Example configuration restoration (would be system-specific)
        for setting, value in configuration.items():
            logger.info(f"Restoring setting {setting}: {value}")
    
    def _restore_database(self, database_snapshot: str) -> None:
        """Restore database from snapshot"""
        logger.info(f"Restoring database from snapshot: {database_snapshot}")
        
        # Example database restoration (would be system-specific)
        if os.path.exists(database_snapshot):
            # Copy snapshot to active database
            shutil.copy2(database_snapshot, "active_database.db")
            logger.info("Database restored successfully")
        else:
            logger.error(f"Database snapshot not found: {database_snapshot}")
    
    def _restore_file(self, file_path: str, backup_path: str) -> None:
        """Restore file from backup"""
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
            logger.info(f"File restored: {file_path}")
        else:
            logger.error(f"Backup file not found: {backup_path}")

class RollbackMechanism:
    """Main rollback mechanism system"""
    
    def __init__(self, window_days: int = 5, backup_dir: str = "backups"):
        self.window_days = window_days
        self.backup_dir = backup_dir
        self.status = RollbackStatus.ACTIVE
        self.breaker_tracker = BreakerTracker(window_days)
        self.state_manager = SystemStateManager(backup_dir)
        self.rollback_operations: List[RollbackOperation] = []
        self.metrics = RollbackMetrics()
        self.lock = threading.RLock()
        
        # Callbacks
        self.on_rollback_triggered: Optional[Callable[[RollbackTrigger], None]] = None
        self.on_rollback_started: Optional[Callable[[RollbackOperation], None]] = None
        self.on_rollback_completed: Optional[Callable[[RollbackOperation], None]] = None
        self.on_rollback_failed: Optional[Callable[[RollbackOperation], None]] = None
    
    def set_callbacks(self,
                      on_rollback_triggered: Optional[Callable[[RollbackTrigger], None]] = None,
                      on_rollback_started: Optional[Callable[[RollbackOperation], None]] = None,
                      on_rollback_completed: Optional[Callable[[RollbackOperation], None]] = None,
                      on_rollback_failed: Optional[Callable[[RollbackOperation], None]] = None) -> None:
        """Set callback functions for rollback events"""
        self.on_rollback_triggered = on_rollback_triggered
        self.on_rollback_started = on_rollback_started
        self.on_rollback_completed = on_rollback_completed
        self.on_rollback_failed = on_rollback_failed
    
    def record_breaker_event(self, breaker_type: BreakerType, severity: str, 
                           message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a circuit breaker event"""
        self.breaker_tracker.record_breaker_event(breaker_type, severity, message, metadata)
        
        # Check if this triggers a rollback
        if self._should_trigger_rollback(breaker_type):
            self._trigger_rollback(RollbackTrigger.BREAKER_DOUBLE_TRIGGER, breaker_type)
    
    def _should_trigger_rollback(self, breaker_type: BreakerType) -> bool:
        """Check if breaker event should trigger rollback"""
        if self.status != RollbackStatus.ACTIVE:
            return False
        
        # Check for double triggers in recent events
        recent_double_triggers = self.breaker_tracker.get_recent_double_triggers(hours=24)
        
        # Check if this breaker type has double triggered
        for trigger_type, trigger_time in recent_double_triggers:
            if trigger_type == breaker_type:
                return True
        
        return False
    
    def _trigger_rollback(self, trigger: RollbackTrigger, breaker_type: Optional[BreakerType] = None) -> None:
        """Trigger a rollback operation"""
        if self.status not in [RollbackStatus.ACTIVE, RollbackStatus.INACTIVE]:
            logger.warning(f"Rollback already in progress, ignoring trigger: {trigger.value}")
            return
        
        logger.warning(f"Rollback triggered: {trigger.value}")
        
        # Call rollback triggered callback
        if self.on_rollback_triggered:
            try:
                self.on_rollback_triggered(trigger)
            except Exception as e:
                logger.error(f"Error in on_rollback_triggered callback: {e}")
        
        # Get latest rollback point
        rollback_point = self.state_manager.get_latest_rollback_point()
        if not rollback_point:
            logger.error("No rollback point available for rollback")
            return
        
        # Create rollback operation
        operation = self._create_rollback_operation(trigger, rollback_point, breaker_type)
        
        # Execute rollback
        self._execute_rollback(operation)
    
    def _create_rollback_operation(self, trigger: RollbackTrigger, 
                                  rollback_point: RollbackPoint,
                                  breaker_type: Optional[BreakerType] = None) -> RollbackOperation:
        """Create a rollback operation"""
        operation_id = f"rollback_{int(time.time())}_{hashlib.md5(str(trigger.value).encode()).hexdigest()[:8]}"
        
        operation = RollbackOperation(
            operation_id=operation_id,
            timestamp=time.time(),
            trigger=trigger,
            rollback_point=rollback_point,
            status=RollbackStatus.EXECUTING,
            affected_components=self._get_affected_components(rollback_point)
        )
        
        with self.lock:
            self.rollback_operations.append(operation)
            self.metrics.total_rollbacks += 1
        
        return operation
    
    def _get_affected_components(self, rollback_point: RollbackPoint) -> List[str]:
        """Get list of affected components for rollback"""
        components = []
        
        # Add system state components
        components.extend(rollback_point.system_state.keys())
        
        # Add configuration components
        components.extend(rollback_point.configuration_snapshot.keys())
        
        # Add file components
        components.extend(rollback_point.file_backups.keys())
        
        return list(set(components))  # Remove duplicates
    
    def _execute_rollback(self, operation: RollbackOperation) -> None:
        """Execute rollback operation"""
        start_time = time.time()
        
        try:
            # Call rollback started callback
            if self.on_rollback_started:
                try:
                    self.on_rollback_started(operation)
                except Exception as e:
                    logger.error(f"Error in on_rollback_started callback: {e}")
            
            # Update status
            operation.status = RollbackStatus.EXECUTING
            self.status = RollbackStatus.EXECUTING
            
            # Execute rollback
            success = self.state_manager.restore_system_state(operation.rollback_point)
            
            # Update operation
            operation.execution_time = time.time() - start_time
            
            if success:
                operation.status = RollbackStatus.COMPLETED
                operation.progress = 100.0
                self.metrics.successful_rollbacks += 1
                
                # Call rollback completed callback
                if self.on_rollback_completed:
                    try:
                        self.on_rollback_completed(operation)
                    except Exception as e:
                        logger.error(f"Error in on_rollback_completed callback: {e}")
                
                logger.info(f"Rollback completed successfully: {operation.operation_id}")
            else:
                operation.status = RollbackStatus.FAILED
                operation.error_message = "Rollback execution failed"
                self.metrics.failed_rollbacks += 1
                
                # Call rollback failed callback
                if self.on_rollback_failed:
                    try:
                        self.on_rollback_failed(operation)
                    except Exception as e:
                        logger.error(f"Error in on_rollback_failed callback: {e}")
                
                logger.error(f"Rollback failed: {operation.operation_id}")
            
            # Update system status
            self.status = RollbackStatus.ACTIVE if success else RollbackStatus.FAILED
            
        except Exception as e:
            operation.status = RollbackStatus.FAILED
            operation.error_message = str(e)
            operation.execution_time = time.time() - start_time
            self.metrics.failed_rollbacks += 1
            self.status = RollbackStatus.FAILED
            
            logger.error(f"Rollback execution error: {e}")
    
    def create_rollback_point(self, description: str, 
                            system_state: Dict[str, Any],
                            configuration: Dict[str, Any],
                            priority: RollbackPriority = RollbackPriority.MEDIUM) -> RollbackPoint:
        """Create a new rollback point"""
        rollback_point = self.state_manager.create_rollback_point(
            description, system_state, configuration, priority
        )
        
        with self.lock:
            self.metrics.rollback_points_created += 1
        
        logger.info(f"Created rollback point: {rollback_point.point_id}")
        return rollback_point
    
    def get_rollback_status(self) -> Dict[str, Any]:
        """Get current rollback status"""
        with self.lock:
            return {
                'status': self.status.value,
                'total_rollbacks': self.metrics.total_rollbacks,
                'successful_rollbacks': self.metrics.successful_rollbacks,
                'failed_rollbacks': self.metrics.failed_rollbacks,
                'avg_rollback_time': self.metrics.avg_rollback_time,
                'breaker_events': self.breaker_tracker.get_breaker_statistics(),
                'rollback_points': len(self.state_manager.rollback_points),
                'recent_double_triggers': len(self.breaker_tracker.get_recent_double_triggers())
            }
    
    def get_rollback_history(self, limit: Optional[int] = None) -> List[RollbackOperation]:
        """Get rollback operation history"""
        with self.lock:
            operations = list(self.rollback_operations)
            operations.sort(key=lambda x: x.timestamp, reverse=True)
            
            if limit:
                return operations[:limit]
            return operations
    
    def get_available_rollback_points(self) -> List[RollbackPoint]:
        """Get available rollback points"""
        return self.state_manager.list_rollback_points()
    
    def check_rollback_criteria(self) -> Tuple[bool, str]:
        """
        Check if rollback criteria are met
        
        Returns:
            Tuple[bool, str]: (should_rollback, reason)
        """
        try:
            with self.lock:
                # Check if any breaker type has triggered twice in the window
                for breaker_type in BreakerType:
                    if self._should_trigger_rollback(breaker_type):
                        return True, f"Breaker {breaker_type.value} triggered twice in {self.window_days} days"
                
                # Check if system is in a critical state
                if self.status == RollbackStatus.TRIGGERED:
                    return True, "System already in rollback triggered state"
                
                return False, "No rollback criteria met"
                
        except Exception as e:
            logger.error(f"Error checking rollback criteria: {e}")
            return False, f"Error checking criteria: {e}"

    def manual_rollback(self, rollback_point_id: str) -> bool:
        """Manually trigger rollback to specific point"""
        rollback_point = self.state_manager.get_rollback_point(rollback_point_id)
        if not rollback_point:
            logger.error(f"Rollback point not found: {rollback_point_id}")
            return False
        
        # Create manual rollback operation
        operation = self._create_rollback_operation(
            RollbackTrigger.MANUAL_INITIATION, 
            rollback_point
        )
        
        # Execute rollback
        self._execute_rollback(operation)
        
        return operation.status == RollbackStatus.COMPLETED

# Global rollback mechanism
_rollback_mechanism: Optional[RollbackMechanism] = None

def get_rollback_mechanism() -> RollbackMechanism:
    """Get global rollback mechanism instance"""
    global _rollback_mechanism
    if _rollback_mechanism is None:
        _rollback_mechanism = RollbackMechanism()
    return _rollback_mechanism

def record_breaker_event(breaker_type: BreakerType, severity: str, 
                        message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Record a circuit breaker event"""
    mechanism = get_rollback_mechanism()
    mechanism.record_breaker_event(breaker_type, severity, message, metadata)

def create_rollback_point(description: str, 
                         system_state: Dict[str, Any],
                         configuration: Dict[str, Any],
                         priority: RollbackPriority = RollbackPriority.MEDIUM) -> RollbackPoint:
    """Create a rollback point"""
    mechanism = get_rollback_mechanism()
    return mechanism.create_rollback_point(description, system_state, configuration, priority)

def get_rollback_status() -> Dict[str, Any]:
    """Get rollback mechanism status"""
    mechanism = get_rollback_mechanism()
    return mechanism.get_rollback_status()

def manual_rollback(rollback_point_id: str) -> bool:
    """Manually trigger rollback"""
    mechanism = get_rollback_mechanism()
    return mechanism.manual_rollback(rollback_point_id)

if __name__ == "__main__":
    # Example usage
    mechanism = get_rollback_mechanism()
    
    # Create a rollback point
    system_state = {
        'database': 'active',
        'cache': 'warm',
        'connections': 10
    }
    
    configuration = {
        'max_connections': 100,
        'timeout': 30,
        'retry_count': 3
    }
    
    rollback_point = create_rollback_point(
        "Initial system state",
        system_state,
        configuration
    )
    
    print(f"Created rollback point: {rollback_point.point_id}")
    
    # Record some breaker events
    record_breaker_event(
        BreakerType.LATENCY,
        "high",
        "Latency exceeded threshold",
        {"latency_ms": 500}
    )
    
    # Get status
    status = get_rollback_status()
    print(f"Rollback status: {json.dumps(status, indent=2)}")
