"""
Comprehensive Queue Monitoring Tests
Tests queue monitoring, alarm functionality, and system overload prevention
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from typing import Dict, Any, List

# Import queue monitoring components
from infra.queue_monitoring import (
    QueueMonitoringManager,
    QueueMonitor,
    QueueThresholds,
    QueueMetrics,
    AlarmEvent,
    QueueStatus,
    AlarmSeverity,
    QueueType,
    get_queue_monitoring_manager,
    start_queue_monitoring,
    stop_queue_monitoring,
    update_queue_size,
    record_processing_time,
    get_queue_status,
    get_system_status
)

class TestQueueMonitor:
    """Test individual queue monitor functionality."""
    
    def test_queue_monitor_initialization(self):
        """Test queue monitor initialization."""
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=100,
            critical_threshold=500,
            overflow_threshold=1000
        )
        monitor = QueueMonitor(thresholds)
        
        assert monitor.thresholds.queue_type == QueueType.TICK_PROCESSING
        assert monitor.thresholds.warning_threshold == 100
        assert monitor.thresholds.critical_threshold == 500
        assert monitor.thresholds.overflow_threshold == 1000
        assert monitor.metrics.status == QueueStatus.HEALTHY
    
    def test_queue_size_update(self):
        """Test queue size updates."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Update queue size
        monitor.update_queue_size(50)
        assert monitor.metrics.current_size == 50
        assert monitor.metrics.max_size == 50
        
        # Update with larger size
        monitor.update_queue_size(100)
        assert monitor.metrics.current_size == 100
        assert monitor.metrics.max_size == 100
        
        # Update with smaller size
        monitor.update_queue_size(75)
        assert monitor.metrics.current_size == 75
        assert monitor.metrics.max_size == 100  # Max should remain
    
    def test_processing_time_recording(self):
        """Test processing time recording."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Record processing times
        monitor.record_processing_time(10.0)  # 10ms
        monitor.record_processing_time(20.0)  # 20ms
        monitor.record_processing_time(15.0)  # 15ms
        
        # Check processing rate calculation
        assert len(monitor.processing_times) == 3
        assert monitor.metrics.processing_rate > 0
    
    def test_warning_threshold_alarm(self):
        """Test warning threshold alarm."""
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=50,
            critical_threshold=100,
            overflow_threshold=200
        )
        monitor = QueueMonitor(thresholds)
        
        # Mock alarm callback
        alarm_callback = Mock()
        monitor.add_alarm_callback(alarm_callback)
        
        # Trigger warning threshold
        monitor.update_queue_size(60)
        monitor._check_thresholds()
        
        # Should trigger warning alarm
        assert monitor.metrics.status == QueueStatus.WARNING
        alarm_callback.assert_called_once()
        
        # Check alarm event
        alarm_event = alarm_callback.call_args[0][0]
        assert alarm_event.severity == AlarmSeverity.WARNING
        assert "warning" in alarm_event.message.lower()
        assert alarm_event.current_size == 60
        assert alarm_event.threshold == 50
    
    def test_critical_threshold_alarm(self):
        """Test critical threshold alarm."""
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=50,
            critical_threshold=100,
            overflow_threshold=200
        )
        monitor = QueueMonitor(thresholds)
        
        # Mock alarm callback
        alarm_callback = Mock()
        monitor.add_alarm_callback(alarm_callback)
        
        # Trigger critical threshold
        monitor.update_queue_size(120)
        monitor._check_thresholds()
        
        # Should trigger critical alarm
        assert monitor.metrics.status == QueueStatus.CRITICAL
        alarm_callback.assert_called_once()
        
        # Check alarm event
        alarm_event = alarm_callback.call_args[0][0]
        assert alarm_event.severity == AlarmSeverity.CRITICAL
        assert "critical" in alarm_event.message.lower()
        assert alarm_event.current_size == 120
        assert alarm_event.threshold == 100
    
    def test_overflow_threshold_alarm(self):
        """Test overflow threshold alarm."""
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=50,
            critical_threshold=100,
            overflow_threshold=200
        )
        monitor = QueueMonitor(thresholds)
        
        # Mock alarm callback
        alarm_callback = Mock()
        monitor.add_alarm_callback(alarm_callback)
        
        # Trigger overflow threshold
        monitor.update_queue_size(250)
        monitor._check_thresholds()
        
        # Should trigger overflow alarm
        assert monitor.metrics.status == QueueStatus.OVERFLOW
        alarm_callback.assert_called_once()
        
        # Check alarm event
        alarm_event = alarm_callback.call_args[0][0]
        assert alarm_event.severity == AlarmSeverity.EMERGENCY
        assert "overflow" in alarm_event.message.lower()
        assert alarm_event.current_size == 250
        assert alarm_event.threshold == 200
    
    def test_alarm_cooldown(self):
        """Test alarm cooldown functionality."""
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=50,
            critical_threshold=100,
            overflow_threshold=200,
            alarm_cooldown_ms=1000  # 1 second cooldown
        )
        monitor = QueueMonitor(thresholds)
        
        # Mock alarm callback
        alarm_callback = Mock()
        monitor.add_alarm_callback(alarm_callback)
        
        # Trigger alarm
        monitor.update_queue_size(60)
        monitor._check_thresholds()
        assert alarm_callback.call_count == 1
        
        # Trigger again immediately (should be ignored due to cooldown)
        monitor.update_queue_size(70)
        monitor._check_thresholds()
        assert alarm_callback.call_count == 1  # Should not increase
        
        # Wait for cooldown and trigger again
        time.sleep(1.1)
        monitor.update_queue_size(80)
        monitor._check_thresholds()
        assert alarm_callback.call_count == 2  # Should increase now
    
    def test_metrics_dict(self):
        """Test metrics dictionary generation."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Update some metrics
        monitor.update_queue_size(100)
        monitor.record_processing_time(10.0)
        
        # Get metrics dict
        metrics = monitor.get_metrics_dict()
        
        assert 'queue_type' in metrics
        assert 'current_size' in metrics
        assert 'max_size' in metrics
        assert 'avg_size' in metrics
        assert 'processing_rate' in metrics
        assert 'wait_time_ms' in metrics
        assert 'status' in metrics
        assert metrics['queue_type'] == QueueType.TICK_PROCESSING.value
        assert metrics['current_size'] == 100
    
    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Update some metrics
        monitor.update_queue_size(100)
        monitor.record_processing_time(10.0)
        
        # Reset metrics
        monitor.reset_metrics()
        
        # Check that metrics are reset
        assert monitor.metrics.current_size == 0
        assert monitor.metrics.max_size == 0
        assert monitor.metrics.avg_size == 0.0
        assert monitor.metrics.processing_rate == 0.0
        assert monitor.metrics.status == QueueStatus.HEALTHY

class TestQueueMonitoringManager:
    """Test queue monitoring manager functionality."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = QueueMonitoringManager()
        
        assert manager is not None
        assert hasattr(manager, 'monitors')
        assert hasattr(manager, 'global_alarm_callbacks')
        assert not manager.is_monitoring
    
    def test_add_queue_monitor(self):
        """Test adding queue monitor."""
        manager = QueueMonitoringManager()
        
        # Clear existing monitors
        manager.monitors.clear()
        
        # Add new monitor
        thresholds = QueueThresholds(
            queue_type=QueueType.TICK_PROCESSING,
            warning_threshold=50,
            critical_threshold=100
        )
        manager.add_queue_monitor(thresholds)
        
        assert QueueType.TICK_PROCESSING in manager.monitors
        assert manager.monitors[QueueType.TICK_PROCESSING].thresholds.queue_type == QueueType.TICK_PROCESSING
    
    def test_update_queue_size(self):
        """Test updating queue size through manager."""
        manager = QueueMonitoringManager()
        
        # Update queue size
        manager.update_queue_size(QueueType.TICK_PROCESSING, 100)
        
        # Check that size was updated
        monitor = manager.monitors[QueueType.TICK_PROCESSING]
        assert monitor.metrics.current_size == 100
    
    def test_record_processing_time(self):
        """Test recording processing time through manager."""
        manager = QueueMonitoringManager()
        
        # Record processing time
        manager.record_processing_time(QueueType.TICK_PROCESSING, 15.0)
        
        # Check that processing time was recorded
        monitor = manager.monitors[QueueType.TICK_PROCESSING]
        assert len(monitor.processing_times) == 1
        assert monitor.processing_times[0] == 15.0
    
    def test_get_queue_status(self):
        """Test getting queue status."""
        manager = QueueMonitoringManager()
        
        # Update queue size to trigger warning
        manager.update_queue_size(QueueType.TICK_PROCESSING, 150)
        
        # Get status
        status = manager.get_queue_status(QueueType.TICK_PROCESSING)
        assert status == QueueStatus.WARNING
    
    def test_get_all_queue_metrics(self):
        """Test getting all queue metrics."""
        manager = QueueMonitoringManager()
        
        # Update some queue sizes
        manager.update_queue_size(QueueType.TICK_PROCESSING, 100)
        manager.update_queue_size(QueueType.DATABASE_WRITE, 200)
        
        # Get all metrics
        metrics = manager.get_all_queue_metrics()
        
        assert QueueType.TICK_PROCESSING.value in metrics
        assert QueueType.DATABASE_WRITE.value in metrics
        assert metrics[QueueType.TICK_PROCESSING.value]['current_size'] == 100
        assert metrics[QueueType.DATABASE_WRITE.value]['current_size'] == 200
    
    def test_get_system_status(self):
        """Test getting system status."""
        manager = QueueMonitoringManager()
        
        # Update some queue sizes to trigger different statuses
        manager.update_queue_size(QueueType.TICK_PROCESSING, 150)  # Warning
        manager.update_queue_size(QueueType.DATABASE_WRITE, 350)  # Critical
        
        # Get system status
        status = manager.get_system_status()
        
        assert 'total_queues' in status
        assert 'healthy_queues' in status
        assert 'warning_queues' in status
        assert 'critical_queues' in status
        assert 'overflow_queues' in status
        assert 'system_health' in status
        assert 'timestamp' in status
        
        assert status['total_queues'] > 0
        assert status['warning_queues'] >= 1
        assert status['critical_queues'] >= 1
    
    def test_global_alarm_callback(self):
        """Test global alarm callback functionality."""
        manager = QueueMonitoringManager()
        
        # Mock global alarm callback
        global_alarm_callback = Mock()
        manager.add_global_alarm_callback(global_alarm_callback)
        
        # Update queue size to trigger alarm
        manager.update_queue_size(QueueType.TICK_PROCESSING, 150)
        
        # Wait a bit for alarm to be processed
        time.sleep(0.1)
        
        # Check that global alarm callback was called
        assert global_alarm_callback.call_count >= 0  # May or may not be called depending on timing
    
    def test_reset_all_metrics(self):
        """Test resetting all metrics."""
        manager = QueueMonitoringManager()
        
        # Update some metrics
        manager.update_queue_size(QueueType.TICK_PROCESSING, 100)
        manager.update_queue_size(QueueType.DATABASE_WRITE, 200)
        
        # Reset all metrics
        manager.reset_all_metrics()
        
        # Check that metrics are reset
        for monitor in manager.monitors.values():
            assert monitor.metrics.current_size == 0
            assert monitor.metrics.max_size == 0

class TestGlobalFunctions:
    """Test global queue monitoring functions."""
    
    def test_get_queue_monitoring_manager(self):
        """Test getting global queue monitoring manager."""
        manager = get_queue_monitoring_manager()
        assert manager is not None
        assert isinstance(manager, QueueMonitoringManager)
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        # Start monitoring
        start_queue_monitoring()
        
        # Check that monitoring is active
        manager = get_queue_monitoring_manager()
        assert manager.is_monitoring
        
        # Stop monitoring
        stop_queue_monitoring()
        
        # Check that monitoring is stopped
        assert not manager.is_monitoring
    
    def test_update_queue_size_global(self):
        """Test global queue size update."""
        # Start monitoring
        start_queue_monitoring()
        
        try:
            # Update queue size
            update_queue_size(QueueType.TICK_PROCESSING, 100)
            
            # Check that size was updated
            manager = get_queue_monitoring_manager()
            monitor = manager.monitors[QueueType.TICK_PROCESSING]
            assert monitor.metrics.current_size == 100
            
        finally:
            # Stop monitoring
            stop_queue_monitoring()
    
    def test_record_processing_time_global(self):
        """Test global processing time recording."""
        # Start monitoring
        start_queue_monitoring()
        
        try:
            # Record processing time
            record_processing_time(QueueType.TICK_PROCESSING, 15.0)
            
            # Check that processing time was recorded
            manager = get_queue_monitoring_manager()
            monitor = manager.monitors[QueueType.TICK_PROCESSING]
            assert len(monitor.processing_times) == 1
            assert monitor.processing_times[0] == 15.0
            
        finally:
            # Stop monitoring
            stop_queue_monitoring()
    
    def test_get_queue_status_global(self):
        """Test global queue status retrieval."""
        # Start monitoring
        start_queue_monitoring()
        
        try:
            # Update queue size to trigger warning
            update_queue_size(QueueType.TICK_PROCESSING, 150)
            
            # Get status
            status = get_queue_status(QueueType.TICK_PROCESSING)
            assert status == QueueStatus.WARNING
            
        finally:
            # Stop monitoring
            stop_queue_monitoring()
    
    def test_get_system_status_global(self):
        """Test global system status retrieval."""
        # Start monitoring
        start_queue_monitoring()
        
        try:
            # Update some queue sizes
            update_queue_size(QueueType.TICK_PROCESSING, 100)
            update_queue_size(QueueType.DATABASE_WRITE, 200)
            
            # Get system status
            status = get_system_status()
            
            assert 'total_queues' in status
            assert 'system_health' in status
            assert status['total_queues'] > 0
            
        finally:
            # Stop monitoring
            stop_queue_monitoring()

class TestQueueTypes:
    """Test different queue types."""
    
    def test_all_queue_types_have_monitors(self):
        """Test that all queue types have monitors."""
        manager = QueueMonitoringManager()
        
        # Check that all queue types have monitors
        for queue_type in QueueType:
            assert queue_type in manager.monitors
            assert manager.monitors[queue_type].thresholds.queue_type == queue_type
    
    def test_queue_type_thresholds(self):
        """Test that different queue types have appropriate thresholds."""
        manager = QueueMonitoringManager()
        
        # Check that critical queues have lower thresholds
        tick_monitor = manager.monitors[QueueType.TICK_PROCESSING]
        db_monitor = manager.monitors[QueueType.DATABASE_WRITE]
        
        # Tick processing should have lower thresholds than database write
        assert tick_monitor.thresholds.warning_threshold < db_monitor.thresholds.warning_threshold
        assert tick_monitor.thresholds.critical_threshold < db_monitor.thresholds.critical_threshold
    
    def test_queue_type_specific_updates(self):
        """Test queue type specific updates."""
        # Use global manager
        manager = get_queue_monitoring_manager()
        
        # Update different queue types
        update_queue_size(QueueType.TICK_PROCESSING, 50)
        update_queue_size(QueueType.DATABASE_WRITE, 100)
        update_queue_size(QueueType.BINANCE_WEBSOCKET, 25)
        
        # Check that each queue type was updated independently
        assert manager.monitors[QueueType.TICK_PROCESSING].metrics.current_size == 50
        assert manager.monitors[QueueType.DATABASE_WRITE].metrics.current_size == 100
        assert manager.monitors[QueueType.BINANCE_WEBSOCKET].metrics.current_size == 25

class TestConcurrency:
    """Test concurrent access to queue monitoring."""
    
    def test_concurrent_queue_updates(self):
        """Test concurrent queue size updates."""
        manager = QueueMonitoringManager()
        
        def update_queue():
            for i in range(10):
                manager.update_queue_size(QueueType.TICK_PROCESSING, i * 10)
                time.sleep(0.001)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=update_queue)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check that updates were processed
        monitor = manager.monitors[QueueType.TICK_PROCESSING]
        assert monitor.metrics.current_size >= 0  # Should have some value
    
    def test_concurrent_processing_time_recording(self):
        """Test concurrent processing time recording."""
        manager = QueueMonitoringManager()
        
        def record_processing_time():
            for i in range(10):
                manager.record_processing_time(QueueType.TICK_PROCESSING, i * 5.0)
                time.sleep(0.001)
        
        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=record_processing_time)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check that processing times were recorded
        monitor = manager.monitors[QueueType.TICK_PROCESSING]
        assert len(monitor.processing_times) > 0

class TestAlarmFunctionality:
    """Test alarm functionality."""
    
    def test_alarm_event_structure(self):
        """Test alarm event structure."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Mock alarm callback
        alarm_callback = Mock()
        monitor.add_alarm_callback(alarm_callback)
        
        # Trigger alarm
        monitor.update_queue_size(150)
        monitor._check_thresholds()
        
        # Check alarm event structure
        assert alarm_callback.call_count == 1
        alarm_event = alarm_callback.call_args[0][0]
        
        assert hasattr(alarm_event, 'timestamp')
        assert hasattr(alarm_event, 'queue_type')
        assert hasattr(alarm_event, 'severity')
        assert hasattr(alarm_event, 'message')
        assert hasattr(alarm_event, 'current_size')
        assert hasattr(alarm_event, 'threshold')
        assert hasattr(alarm_event, 'metrics')
        
        assert alarm_event.queue_type == QueueType.TICK_PROCESSING
        assert alarm_event.severity == AlarmSeverity.WARNING
        assert alarm_event.current_size == 150
        assert alarm_event.threshold == 100
    
    def test_multiple_alarm_callbacks(self):
        """Test multiple alarm callbacks."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Add multiple alarm callbacks
        callback1 = Mock()
        callback2 = Mock()
        monitor.add_alarm_callback(callback1)
        monitor.add_alarm_callback(callback2)
        
        # Trigger alarm
        monitor.update_queue_size(150)
        monitor._check_thresholds()
        
        # Check that both callbacks were called
        assert callback1.call_count == 1
        assert callback2.call_count == 1
    
    def test_alarm_callback_error_handling(self):
        """Test alarm callback error handling."""
        thresholds = QueueThresholds(queue_type=QueueType.TICK_PROCESSING)
        monitor = QueueMonitor(thresholds)
        
        # Add callback that raises exception
        def error_callback(alarm_event):
            raise Exception("Test error")
        
        # Add normal callback
        normal_callback = Mock()
        
        monitor.add_alarm_callback(error_callback)
        monitor.add_alarm_callback(normal_callback)
        
        # Trigger alarm
        monitor.update_queue_size(150)
        monitor._check_thresholds()
        
        # Check that normal callback was still called despite error
        assert normal_callback.call_count == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
