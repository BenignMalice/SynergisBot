"""
Comprehensive tests for rollback mechanism system

Tests automatic rollback detection, breaker trigger tracking,
system state restoration, and production safety capabilities.
"""

import pytest
import time
import json
import threading
import os
import shutil
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.rollback_mechanism import (
    RollbackMechanism, BreakerTracker, SystemStateManager,
    RollbackStatus, BreakerType, RollbackTrigger, RollbackPriority,
    BreakerEvent, RollbackPoint, RollbackOperation, RollbackMetrics,
    get_rollback_mechanism, record_breaker_event, create_rollback_point,
    get_rollback_status, manual_rollback
)

class TestRollbackStatus:
    """Test rollback status enumeration"""
    
    def test_rollback_statuses(self):
        """Test all rollback statuses"""
        statuses = [
            RollbackStatus.ACTIVE,
            RollbackStatus.INACTIVE,
            RollbackStatus.TRIGGERED,
            RollbackStatus.EXECUTING,
            RollbackStatus.COMPLETED,
            RollbackStatus.FAILED,
            RollbackStatus.DISABLED
        ]
        
        for status in statuses:
            assert isinstance(status, RollbackStatus)
            assert status.value in [
                "active", "inactive", "triggered", "executing",
                "completed", "failed", "disabled"
            ]

class TestBreakerType:
    """Test breaker type enumeration"""
    
    def test_breaker_types(self):
        """Test all breaker types"""
        types = [
            BreakerType.LATENCY,
            BreakerType.DRAWDOWN,
            BreakerType.QUEUE_BACKPRESSURE,
            BreakerType.DATA_QUALITY,
            BreakerType.SYSTEM_HEALTH,
            BreakerType.PERFORMANCE,
            BreakerType.ERROR_RATE,
            BreakerType.MEMORY_USAGE,
            BreakerType.CPU_USAGE
        ]
        
        for breaker_type in types:
            assert isinstance(breaker_type, BreakerType)
            assert breaker_type.value in [
                "latency", "drawdown", "queue_backpressure", "data_quality",
                "system_health", "performance", "error_rate", "memory_usage", "cpu_usage"
            ]

class TestRollbackTrigger:
    """Test rollback trigger enumeration"""
    
    def test_rollback_triggers(self):
        """Test all rollback triggers"""
        triggers = [
            RollbackTrigger.BREAKER_DOUBLE_TRIGGER,
            RollbackTrigger.MANUAL_INITIATION,
            RollbackTrigger.SYSTEM_FAILURE,
            RollbackTrigger.DATA_CORRUPTION,
            RollbackTrigger.SECURITY_BREACH
        ]
        
        for trigger in triggers:
            assert isinstance(trigger, RollbackTrigger)
            assert trigger.value in [
                "breaker_double_trigger", "manual_initiation", "system_failure",
                "data_corruption", "security_breach"
            ]

class TestRollbackPriority:
    """Test rollback priority enumeration"""
    
    def test_rollback_priorities(self):
        """Test all rollback priorities"""
        priorities = [
            RollbackPriority.LOW,
            RollbackPriority.MEDIUM,
            RollbackPriority.HIGH,
            RollbackPriority.CRITICAL,
            RollbackPriority.EMERGENCY
        ]
        
        for priority in priorities:
            assert isinstance(priority, RollbackPriority)
            assert priority.value in ["low", "medium", "high", "critical", "emergency"]

class TestBreakerEvent:
    """Test breaker event data structure"""
    
    def test_breaker_event_creation(self):
        """Test breaker event creation"""
        event = BreakerEvent(
            timestamp=time.time(),
            breaker_type=BreakerType.LATENCY,
            severity="high",
            message="Latency exceeded threshold",
            metadata={"latency_ms": 500},
            resolved=False,
            resolution_time=None
        )
        
        assert event.timestamp > 0
        assert event.breaker_type == BreakerType.LATENCY
        assert event.severity == "high"
        assert event.message == "Latency exceeded threshold"
        assert event.metadata["latency_ms"] == 500
        assert event.resolved is False
        assert event.resolution_time is None
    
    def test_breaker_event_defaults(self):
        """Test breaker event defaults"""
        event = BreakerEvent(
            timestamp=time.time(),
            breaker_type=BreakerType.DRAWDOWN,
            severity="critical",
            message="Drawdown exceeded limit"
        )
        
        assert event.metadata == {}
        assert event.resolved is False
        assert event.resolution_time is None

class TestRollbackPoint:
    """Test rollback point data structure"""
    
    def test_rollback_point_creation(self):
        """Test rollback point creation"""
        system_state = {"database": "active", "cache": "warm"}
        configuration = {"max_connections": 100, "timeout": 30}
        
        point = RollbackPoint(
            point_id="test_point_1",
            timestamp=time.time(),
            description="Test rollback point",
            system_state=system_state,
            configuration_snapshot=configuration,
            database_snapshot="backup.db",
            file_backups={"config.json": "backup_config.json"},
            checksum="abc123",
            priority=RollbackPriority.HIGH
        )
        
        assert point.point_id == "test_point_1"
        assert point.timestamp > 0
        assert point.description == "Test rollback point"
        assert point.system_state == system_state
        assert point.configuration_snapshot == configuration
        assert point.database_snapshot == "backup.db"
        assert point.file_backups["config.json"] == "backup_config.json"
        assert point.checksum == "abc123"
        assert point.priority == RollbackPriority.HIGH
    
    def test_rollback_point_defaults(self):
        """Test rollback point defaults"""
        point = RollbackPoint(
            point_id="test_point_2",
            timestamp=time.time(),
            description="Test rollback point 2",
            system_state={"test": "value"},
            configuration_snapshot={"setting": "value"}
        )
        
        assert point.database_snapshot is None
        assert point.file_backups == {}
        assert point.checksum == ""
        assert point.priority == RollbackPriority.MEDIUM

class TestRollbackOperation:
    """Test rollback operation data structure"""
    
    def test_rollback_operation_creation(self):
        """Test rollback operation creation"""
        rollback_point = RollbackPoint(
            point_id="test_point",
            timestamp=time.time(),
            description="Test point",
            system_state={"test": "value"},
            configuration_snapshot={"setting": "value"}
        )
        
        operation = RollbackOperation(
            operation_id="test_operation_1",
            timestamp=time.time(),
            trigger=RollbackTrigger.BREAKER_DOUBLE_TRIGGER,
            rollback_point=rollback_point,
            status=RollbackStatus.EXECUTING,
            progress=50.0,
            error_message="Test error",
            execution_time=1.5,
            affected_components=["database", "cache"]
        )
        
        assert operation.operation_id == "test_operation_1"
        assert operation.timestamp > 0
        assert operation.trigger == RollbackTrigger.BREAKER_DOUBLE_TRIGGER
        assert operation.rollback_point == rollback_point
        assert operation.status == RollbackStatus.EXECUTING
        assert operation.progress == 50.0
        assert operation.error_message == "Test error"
        assert operation.execution_time == 1.5
        assert operation.affected_components == ["database", "cache"]
    
    def test_rollback_operation_defaults(self):
        """Test rollback operation defaults"""
        rollback_point = RollbackPoint(
            point_id="test_point",
            timestamp=time.time(),
            description="Test point",
            system_state={"test": "value"},
            configuration_snapshot={"setting": "value"}
        )
        
        operation = RollbackOperation(
            operation_id="test_operation_2",
            timestamp=time.time(),
            trigger=RollbackTrigger.MANUAL_INITIATION,
            rollback_point=rollback_point,
            status=RollbackStatus.ACTIVE
        )
        
        assert operation.progress == 0.0
        assert operation.error_message is None
        assert operation.execution_time == 0.0
        assert operation.affected_components == []

class TestBreakerTracker:
    """Test breaker tracker"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.tracker = BreakerTracker(window_days=5)
    
    def test_tracker_initialization(self):
        """Test tracker initialization"""
        assert self.tracker.window_days == 5
        assert self.tracker.window_seconds == 5 * 24 * 3600
        assert len(self.tracker.breaker_events) == 0
        assert len(self.tracker.double_triggers) == 0
        assert hasattr(self.tracker, 'lock')
    
    def test_record_breaker_event(self):
        """Test recording breaker events"""
        self.tracker.record_breaker_event(
            BreakerType.LATENCY,
            "high",
            "Latency exceeded threshold",
            {"latency_ms": 500}
        )
        
        assert len(self.tracker.breaker_events[BreakerType.LATENCY]) == 1
        
        event = self.tracker.breaker_events[BreakerType.LATENCY][0]
        assert event.breaker_type == BreakerType.LATENCY
        assert event.severity == "high"
        assert event.message == "Latency exceeded threshold"
        assert event.metadata["latency_ms"] == 500
    
    def test_double_trigger_detection(self):
        """Test double trigger detection"""
        # Record first high severity event
        self.tracker.record_breaker_event(
            BreakerType.LATENCY,
            "high",
            "First latency event"
        )
        
        # Record second high severity event (should trigger double trigger)
        self.tracker.record_breaker_event(
            BreakerType.LATENCY,
            "critical",
            "Second latency event"
        )
        
        # Should have double trigger
        assert len(self.tracker.double_triggers) == 1
        assert self.tracker.double_triggers[0][0] == BreakerType.LATENCY
    
    def test_get_breaker_statistics(self):
        """Test getting breaker statistics"""
        # Record some events
        self.tracker.record_breaker_event(BreakerType.LATENCY, "high", "Event 1")
        self.tracker.record_breaker_event(BreakerType.DRAWDOWN, "critical", "Event 2")
        
        stats = self.tracker.get_breaker_statistics()
        
        assert stats['total_events'] == 2
        assert stats['double_triggers'] >= 0
        assert stats['breaker_types'] == 2
        assert stats['window_days'] == 5
        assert 'latency_events' in stats
        assert 'drawdown_events' in stats
    
    def test_get_recent_double_triggers(self):
        """Test getting recent double triggers"""
        # Record events that should create double triggers
        for i in range(3):
            self.tracker.record_breaker_event(
                BreakerType.LATENCY,
                "high",
                f"Event {i}"
            )
        
        recent_triggers = self.tracker.get_recent_double_triggers(hours=24)
        
        # Should have at least one double trigger
        assert len(recent_triggers) >= 1
        assert all(trigger[0] == BreakerType.LATENCY for trigger in recent_triggers)

class TestSystemStateManager:
    """Test system state manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SystemStateManager(backup_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.backup_dir == self.temp_dir
        assert len(self.manager.rollback_points) == 0
        assert hasattr(self.manager, 'lock')
        assert os.path.exists(self.temp_dir)
    
    def test_create_rollback_point(self):
        """Test creating rollback point"""
        system_state = {"database": "active", "cache": "warm"}
        configuration = {"max_connections": 100, "timeout": 30}
        
        point = self.manager.create_rollback_point(
            "Test rollback point",
            system_state,
            configuration,
            RollbackPriority.HIGH
        )
        
        assert point.point_id.startswith("rb_")
        assert point.timestamp > 0
        assert point.description == "Test rollback point"
        assert point.system_state == system_state
        assert point.configuration_snapshot == configuration
        assert point.priority == RollbackPriority.HIGH
        assert point.checksum != ""
        
        # Should be stored
        assert point.point_id in self.manager.rollback_points
    
    def test_get_rollback_point(self):
        """Test getting rollback point"""
        system_state = {"test": "value"}
        configuration = {"setting": "value"}
        
        point = self.manager.create_rollback_point(
            "Test point",
            system_state,
            configuration
        )
        
        retrieved_point = self.manager.get_rollback_point(point.point_id)
        assert retrieved_point is not None
        assert retrieved_point.point_id == point.point_id
        assert retrieved_point.system_state == system_state
    
    def test_get_rollback_point_not_found(self):
        """Test getting non-existent rollback point"""
        point = self.manager.get_rollback_point("non_existent_id")
        assert point is None
    
    def test_get_latest_rollback_point(self):
        """Test getting latest rollback point"""
        # Create multiple points
        for i in range(3):
            time.sleep(0.01)  # Ensure different timestamps
            self.manager.create_rollback_point(
                f"Point {i}",
                {"test": f"value{i}"},
                {"setting": f"value{i}"}
            )
        
        latest_point = self.manager.get_latest_rollback_point()
        assert latest_point is not None
        assert latest_point.description == "Point 2"  # Last created
    
    def test_list_rollback_points(self):
        """Test listing rollback points"""
        # Create multiple points
        for i in range(5):
            self.manager.create_rollback_point(
                f"Point {i}",
                {"test": f"value{i}"},
                {"setting": f"value{i}"}
            )
        
        points = self.manager.list_rollback_points()
        assert len(points) == 5
        
        # Test with limit
        limited_points = self.manager.list_rollback_points(limit=3)
        assert len(limited_points) == 3
    
    def test_restore_system_state(self):
        """Test restoring system state"""
        system_state = {"database": "active", "cache": "warm"}
        configuration = {"max_connections": 100}
        
        point = self.manager.create_rollback_point(
            "Test point",
            system_state,
            configuration
        )
        
        # Mock the restoration methods and validation
        with patch.object(self.manager, '_restore_system_state') as mock_restore_state, \
             patch.object(self.manager, '_restore_configuration') as mock_restore_config, \
             patch.object(self.manager, '_validate_rollback_point', return_value=True):
            
            success = self.manager.restore_system_state(point)
            
            assert success is True
            mock_restore_state.assert_called_once_with(system_state)
            mock_restore_config.assert_called_once_with(configuration)

class TestRollbackMechanism:
    """Test rollback mechanism"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.mechanism = RollbackMechanism(window_days=5, backup_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_mechanism_initialization(self):
        """Test mechanism initialization"""
        assert self.mechanism.window_days == 5
        assert self.mechanism.backup_dir == self.temp_dir
        assert self.mechanism.status == RollbackStatus.ACTIVE
        assert isinstance(self.mechanism.breaker_tracker, BreakerTracker)
        assert isinstance(self.mechanism.state_manager, SystemStateManager)
        assert len(self.mechanism.rollback_operations) == 0
        assert isinstance(self.mechanism.metrics, RollbackMetrics)
    
    def test_record_breaker_event(self):
        """Test recording breaker events"""
        self.mechanism.record_breaker_event(
            BreakerType.LATENCY,
            "high",
            "Latency exceeded threshold",
            {"latency_ms": 500}
        )
        
        # Should be recorded in breaker tracker
        assert len(self.mechanism.breaker_tracker.breaker_events[BreakerType.LATENCY]) == 1
    
    def test_create_rollback_point(self):
        """Test creating rollback point"""
        system_state = {"database": "active"}
        configuration = {"max_connections": 100}
        
        point = self.mechanism.create_rollback_point(
            "Test point",
            system_state,
            configuration,
            RollbackPriority.HIGH
        )
        
        assert point.description == "Test point"
        assert point.system_state == system_state
        assert point.configuration_snapshot == configuration
        assert point.priority == RollbackPriority.HIGH
        
        # Should update metrics
        assert self.mechanism.metrics.rollback_points_created == 1
    
    def test_get_rollback_status(self):
        """Test getting rollback status"""
        status = self.mechanism.get_rollback_status()
        
        assert 'status' in status
        assert 'total_rollbacks' in status
        assert 'successful_rollbacks' in status
        assert 'failed_rollbacks' in status
        assert 'avg_rollback_time' in status
        assert 'breaker_events' in status
        assert 'rollback_points' in status
        assert 'recent_double_triggers' in status
    
    def test_get_rollback_history(self):
        """Test getting rollback history"""
        # Create some rollback operations
        for i in range(3):
            operation = RollbackOperation(
                operation_id=f"operation_{i}",
                timestamp=time.time() + i,
                trigger=RollbackTrigger.MANUAL_INITIATION,
                rollback_point=RollbackPoint(
                    point_id=f"point_{i}",
                    timestamp=time.time(),
                    description=f"Point {i}",
                    system_state={"test": f"value{i}"},
                    configuration_snapshot={"setting": f"value{i}"}
                ),
                status=RollbackStatus.COMPLETED
            )
            self.mechanism.rollback_operations.append(operation)
        
        history = self.mechanism.get_rollback_history()
        assert len(history) == 3
        
        # Test with limit
        limited_history = self.mechanism.get_rollback_history(limit=2)
        assert len(limited_history) == 2
    
    def test_get_available_rollback_points(self):
        """Test getting available rollback points"""
        # Create some rollback points
        for i in range(3):
            self.mechanism.create_rollback_point(
                f"Point {i}",
                {"test": f"value{i}"},
                {"setting": f"value{i}"}
            )
        
        points = self.mechanism.get_available_rollback_points()
        assert len(points) == 3
    
    def test_manual_rollback(self):
        """Test manual rollback"""
        # Create a rollback point
        point = self.mechanism.create_rollback_point(
            "Test point",
            {"database": "active"},
            {"max_connections": 100}
        )
        
        # Mock the restoration
        with patch.object(self.mechanism.state_manager, 'restore_system_state', return_value=True):
            success = self.mechanism.manual_rollback(point.point_id)
            assert success is True
    
    def test_manual_rollback_invalid_point(self):
        """Test manual rollback with invalid point"""
        success = self.mechanism.manual_rollback("non_existent_id")
        assert success is False
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_triggered = Mock()
        on_started = Mock()
        on_completed = Mock()
        on_failed = Mock()
        
        self.mechanism.set_callbacks(
            on_rollback_triggered=on_triggered,
            on_rollback_started=on_started,
            on_rollback_completed=on_completed,
            on_rollback_failed=on_failed
        )
        
        assert self.mechanism.on_rollback_triggered == on_triggered
        assert self.mechanism.on_rollback_started == on_started
        assert self.mechanism.on_rollback_completed == on_completed
        assert self.mechanism.on_rollback_failed == on_failed

class TestGlobalFunctions:
    """Test global rollback mechanism functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global mechanism
        import infra.rollback_mechanism
        infra.rollback_mechanism._rollback_mechanism = None
    
    def test_get_rollback_mechanism(self):
        """Test global rollback mechanism access"""
        mechanism1 = get_rollback_mechanism()
        mechanism2 = get_rollback_mechanism()
        
        # Should return same instance
        assert mechanism1 is mechanism2
        assert isinstance(mechanism1, RollbackMechanism)
    
    def test_record_breaker_event_global(self):
        """Test global breaker event recording"""
        record_breaker_event(
            BreakerType.LATENCY,
            "high",
            "Global latency event",
            {"latency_ms": 500}
        )
        
        mechanism = get_rollback_mechanism()
        events = mechanism.breaker_tracker.breaker_events[BreakerType.LATENCY]
        assert len(events) == 1
        assert events[0].message == "Global latency event"
    
    def test_create_rollback_point_global(self):
        """Test global rollback point creation"""
        system_state = {"database": "active"}
        configuration = {"max_connections": 100}
        
        point = create_rollback_point(
            "Global test point",
            system_state,
            configuration,
            RollbackPriority.HIGH
        )
        
        assert point.description == "Global test point"
        assert point.system_state == system_state
        assert point.configuration_snapshot == configuration
        assert point.priority == RollbackPriority.HIGH
    
    def test_get_rollback_status_global(self):
        """Test global rollback status"""
        status = get_rollback_status()
        
        assert 'status' in status
        assert 'total_rollbacks' in status
        assert 'successful_rollbacks' in status
        assert 'failed_rollbacks' in status
    
    def test_manual_rollback_global(self):
        """Test global manual rollback"""
        # Create a rollback point
        point = create_rollback_point(
            "Global test point",
            {"database": "active"},
            {"max_connections": 100}
        )
        
        # Mock the restoration
        mechanism = get_rollback_mechanism()
        with patch.object(mechanism.state_manager, 'restore_system_state', return_value=True):
            success = manual_rollback(point.point_id)
            assert success is True

class TestRollbackIntegration:
    """Integration tests for rollback mechanism"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global mechanism
        import infra.rollback_mechanism
        infra.rollback_mechanism._rollback_mechanism = None
    
    def test_comprehensive_rollback_workflow(self):
        """Test comprehensive rollback workflow"""
        # Create rollback point
        system_state = {"database": "active", "cache": "warm"}
        configuration = {"max_connections": 100, "timeout": 30}
        
        point = create_rollback_point(
            "Initial system state",
            system_state,
            configuration,
            RollbackPriority.HIGH
        )
        
        assert point is not None
        assert point.system_state == system_state
        assert point.configuration_snapshot == configuration
        
        # Record breaker events
        record_breaker_event(BreakerType.LATENCY, "high", "First latency event")
        record_breaker_event(BreakerType.LATENCY, "critical", "Second latency event")
        
        # Get status
        status = get_rollback_status()
        assert status['total_rollbacks'] >= 0
        assert status['rollback_points'] >= 1
        
        # Test manual rollback
        mechanism = get_rollback_mechanism()
        with patch.object(mechanism.state_manager, 'restore_system_state', return_value=True):
            success = manual_rollback(point.point_id)
            assert success is True
    
    def test_breaker_double_trigger_workflow(self):
        """Test breaker double trigger workflow"""
        # Record multiple high severity events for same breaker
        for i in range(3):
            record_breaker_event(
                BreakerType.DRAWDOWN,
                "high",
                f"Drawdown event {i}",
                {"drawdown": 0.05 + i * 0.01}
            )
        
        # Get status
        status = get_rollback_status()
        assert status['recent_double_triggers'] >= 1
        
        # Check breaker statistics
        mechanism = get_rollback_mechanism()
        breaker_stats = mechanism.breaker_tracker.get_breaker_statistics()
        assert breaker_stats['total_events'] == 3
        assert breaker_stats['double_triggers'] >= 1
    
    def test_rollback_point_management(self):
        """Test rollback point management"""
        # Create multiple rollback points
        points = []
        for i in range(5):
            point = create_rollback_point(
                f"Point {i}",
                {"test": f"value{i}"},
                {"setting": f"value{i}"},
                RollbackPriority.MEDIUM
            )
            points.append(point)
        
        # Get available points
        mechanism = get_rollback_mechanism()
        available_points = mechanism.get_available_rollback_points()
        assert len(available_points) == 5
        
        # Test getting specific point
        retrieved_point = mechanism.state_manager.get_rollback_point(points[0].point_id)
        assert retrieved_point is not None
        assert retrieved_point.point_id == points[0].point_id
    
    def test_rollback_operation_tracking(self):
        """Test rollback operation tracking"""
        # Create rollback point
        point = create_rollback_point(
            "Test point",
            {"database": "active"},
            {"max_connections": 100}
        )
        
        # Mock rollback execution
        mechanism = get_rollback_mechanism()
        with patch.object(mechanism.state_manager, 'restore_system_state', return_value=True):
            success = manual_rollback(point.point_id)
            assert success is True
        
        # Check operation history
        history = mechanism.get_rollback_history()
        assert len(history) >= 1
        
        operation = history[0]
        assert operation.rollback_point.point_id == point.point_id
        assert operation.trigger == RollbackTrigger.MANUAL_INITIATION
    
    def test_rollback_error_handling(self):
        """Test rollback error handling"""
        # Test with invalid rollback point
        success = manual_rollback("non_existent_id")
        assert success is False
        
        # Test with valid point but failed restoration
        point = create_rollback_point(
            "Test point",
            {"database": "active"},
            {"max_connections": 100}
        )
        
        mechanism = get_rollback_mechanism()
        with patch.object(mechanism.state_manager, 'restore_system_state', return_value=False):
            success = manual_rollback(point.point_id)
            assert success is False
    
    def test_rollback_metrics_tracking(self):
        """Test rollback metrics tracking"""
        # Create rollback point
        point = create_rollback_point(
            "Test point",
            {"database": "active"},
            {"max_connections": 100}
        )
        
        # Get initial metrics
        mechanism = get_rollback_mechanism()
        initial_rollbacks = mechanism.metrics.total_rollbacks
        
        # Perform rollback
        with patch.object(mechanism.state_manager, 'restore_system_state', return_value=True):
            success = manual_rollback(point.point_id)
            assert success is True
        
        # Check metrics updated
        assert mechanism.metrics.total_rollbacks > initial_rollbacks
        assert mechanism.metrics.rollback_points_created >= 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
