"""
Test suite for Windows scheduling optimizations.
Tests thread priorities, high-resolution timing, and Windows-specific features.
"""

import pytest
import time
import threading
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.windows_scheduling import (
    WindowsScheduler, 
    SchedulingConfig, 
    ThreadPriority, 
    HighResolutionTimer,
    ThreadManager,
    initialize_windows_scheduling,
    cleanup_windows_scheduling
)

class TestSchedulingConfig:
    """Test SchedulingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SchedulingConfig()
        assert config.process_priority == "HIGH"
        assert config.affinity_mask is None
        assert config.hot_path_priority == ThreadPriority.REALTIME
        assert config.data_ingestion_priority == ThreadPriority.HIGHEST
        assert config.database_priority == ThreadPriority.ABOVE_NORMAL
        assert config.monitoring_priority == ThreadPriority.NORMAL
        assert config.use_high_res_timer is True
        assert config.timer_resolution_us == 1000
        assert config.working_set_size_mb == 1024
        assert config.page_priority == "HIGH"
        assert config.prevent_sleep is True
        assert config.disable_power_throttling is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SchedulingConfig(
            process_priority="REALTIME",
            affinity_mask=1,
            hot_path_priority=ThreadPriority.HIGHEST,
            use_high_res_timer=False,
            prevent_sleep=False
        )
        assert config.process_priority == "REALTIME"
        assert config.affinity_mask == 1
        assert config.hot_path_priority == ThreadPriority.HIGHEST
        assert config.use_high_res_timer is False
        assert config.prevent_sleep is False

class TestThreadPriority:
    """Test ThreadPriority enum."""
    
    def test_priority_values(self):
        """Test thread priority enum values."""
        assert ThreadPriority.LOWEST.value == 1
        assert ThreadPriority.BELOW_NORMAL.value == 2
        assert ThreadPriority.NORMAL.value == 3
        assert ThreadPriority.ABOVE_NORMAL.value == 4
        assert ThreadPriority.HIGHEST.value == 5
        assert ThreadPriority.REALTIME.value == 6

class TestHighResolutionTimer:
    """Test HighResolutionTimer class."""
    
    def test_timer_initialization(self):
        """Test timer initialization."""
        timer = HighResolutionTimer()
        assert timer.start_time is None
        assert timer.end_time is None

    def test_timer_operations(self):
        """Test timer start/stop operations."""
        timer = HighResolutionTimer()
        
        # Test start
        timer.start()
        assert timer.start_time is not None
        assert timer.end_time is None
        
        # Test stop
        timer.stop()
        assert timer.end_time is not None
        assert timer.end_time >= timer.start_time

    def test_elapsed_time_calculations(self):
        """Test elapsed time calculations."""
        timer = HighResolutionTimer()
        
        # Test with no start time
        assert timer.elapsed_ns() == 0
        assert timer.elapsed_ms() == 0.0
        assert timer.elapsed_us() == 0.0
        
        # Test with start but no stop
        timer.start()
        time.sleep(0.001)  # 1ms
        elapsed_ns = timer.elapsed_ns()
        elapsed_ms = timer.elapsed_ms()
        elapsed_us = timer.elapsed_us()
        
        assert elapsed_ns > 0
        assert elapsed_ms > 0
        assert elapsed_us > 0
        # Allow for small floating point precision differences
        assert abs(elapsed_ms - (elapsed_ns / 1_000_000)) < 0.01
        # Allow for small floating point precision differences
        assert abs(elapsed_us - (elapsed_ns / 1_000)) < 10.0
        
        # Test with stop
        timer.stop()
        final_elapsed_ns = timer.elapsed_ns()
        assert final_elapsed_ns >= elapsed_ns

    def test_timer_precision(self):
        """Test timer precision for high-frequency operations."""
        timer = HighResolutionTimer()
        
        # Test multiple rapid measurements
        measurements = []
        for _ in range(10):
            timer.start()
            # Simulate some work
            _ = sum(range(1000))
            timer.stop()
            measurements.append(timer.elapsed_ns())
        
        # All measurements should be positive
        assert all(m > 0 for m in measurements)
        
        # Measurements should be reasonably consistent
        avg_time = sum(measurements) / len(measurements)
        assert avg_time > 0

class TestWindowsScheduler:
    """Test WindowsScheduler class."""
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        assert scheduler.config == config
        assert scheduler.original_process_priority is None
        assert scheduler.original_affinity is None
        assert scheduler.original_timer_resolution is None
        assert scheduler.thread_priorities == {}
        assert scheduler._initialized is False

    @patch('app.core.windows_scheduling.WINDOWS_AVAILABLE', False)
    def test_initialization_non_windows(self):
        """Test initialization on non-Windows platform."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        result = scheduler.initialize()
        assert result is False
        assert scheduler._initialized is False

    @patch('app.core.windows_scheduling.WINDOWS_AVAILABLE', True)
    @patch('app.core.windows_scheduling.win32api')
    @patch('app.core.windows_scheduling.psutil')
    def test_initialization_windows(self, mock_psutil, mock_win32api):
        """Test initialization on Windows platform."""
        # Mock Windows API calls
        mock_win32api.GetCurrentProcess.return_value = MagicMock()
        mock_win32api.SetPriorityClass.return_value = None
        mock_win32api.timeBeginPeriod.return_value = None
        mock_win32api.SetThreadExecutionState.return_value = None
        
        # Mock psutil
        mock_process = MagicMock()
        mock_process.cpu_affinity.return_value = [0, 1, 2, 3]
        mock_psutil.Process.return_value = mock_process
        mock_psutil.cpu_count.return_value = 4
        
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        result = scheduler.initialize()
        assert result is True
        assert scheduler._initialized is True

    def test_get_high_res_timestamp(self):
        """Test high-resolution timestamp functions."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        # Test timestamp functions
        timestamp_ns = scheduler.get_high_res_timestamp()
        timestamp_ms = scheduler.get_high_res_timestamp_ms()
        
        assert isinstance(timestamp_ns, int)
        assert isinstance(timestamp_ms, float)
        assert timestamp_ns > 0
        assert timestamp_ms > 0

    def test_set_thread_priority_non_windows(self):
        """Test setting thread priority on non-Windows platform."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        result = scheduler.set_thread_priority("test_thread", ThreadPriority.HIGHEST)
        assert result is False

    @patch('app.core.windows_scheduling.WINDOWS_AVAILABLE', True)
    @patch('app.core.windows_scheduling.win32api')
    def test_set_thread_priority_windows(self, mock_win32api):
        """Test setting thread priority on Windows platform."""
        mock_win32api.GetCurrentThread.return_value = MagicMock()
        mock_win32api.SetThreadPriority.return_value = None
        
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        scheduler._initialized = True
        
        result = scheduler.set_thread_priority("test_thread", ThreadPriority.HIGHEST)
        assert result is True
        assert "test_thread" in scheduler.thread_priorities

    def test_get_status(self):
        """Test getting scheduler status."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        
        status = scheduler.get_status()
        
        assert "platform" in status
        assert "windows_available" in status
        assert "initialized" in status
        assert "config" in status
        assert "thread_priorities" in status
        
        assert status["platform"] == sys.platform
        assert status["initialized"] is False
        assert status["thread_priorities"] == {}

class TestThreadManager:
    """Test ThreadManager class."""
    
    def test_thread_manager_initialization(self):
        """Test thread manager initialization."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        manager = ThreadManager(scheduler)
        
        assert manager.scheduler == scheduler
        assert manager.thread_registry == {}

    def test_register_thread(self):
        """Test thread registration."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        manager = ThreadManager(scheduler)
        
        # Create a test thread
        def test_func():
            time.sleep(0.1)
        
        thread = threading.Thread(target=test_func, name="test_thread")
        manager.register_thread("test_thread", thread, ThreadPriority.HIGHEST)
        
        assert "test_thread" in manager.thread_registry
        assert manager.thread_registry["test_thread"] == thread

    def test_get_thread_status(self):
        """Test getting thread status."""
        config = SchedulingConfig()
        scheduler = WindowsScheduler(config)
        manager = ThreadManager(scheduler)
        
        # Create and register a test thread
        def test_func():
            time.sleep(0.1)
        
        thread = threading.Thread(target=test_func, name="test_thread")
        manager.register_thread("test_thread", thread, ThreadPriority.HIGHEST)
        
        status = manager.get_thread_status()
        
        assert "test_thread" in status
        assert "alive" in status["test_thread"]
        assert "daemon" in status["test_thread"]
        assert "name" in status["test_thread"]
        assert "ident" in status["test_thread"]

class TestGlobalFunctions:
    """Test global scheduler functions."""
    
    def test_initialize_windows_scheduling(self):
        """Test global scheduler initialization."""
        config = SchedulingConfig()
        scheduler = initialize_windows_scheduling(config)
        
        assert isinstance(scheduler, WindowsScheduler)
        assert scheduler.config == config

    def test_get_scheduler(self):
        """Test getting global scheduler."""
        config = SchedulingConfig()
        scheduler = initialize_windows_scheduling(config)
        
        from app.core.windows_scheduling import get_scheduler
        retrieved_scheduler = get_scheduler()
        assert retrieved_scheduler == scheduler

    def test_cleanup_windows_scheduling(self):
        """Test global scheduler cleanup."""
        config = SchedulingConfig()
        scheduler = initialize_windows_scheduling(config)
        
        cleanup_windows_scheduling()
        from app.core.windows_scheduling import get_scheduler
        assert get_scheduler() is None

class TestIntegration:
    """Integration tests for Windows scheduling."""
    
    def test_timer_precision_integration(self):
        """Test timer precision in realistic scenarios."""
        timer = HighResolutionTimer()
        
        # Test multiple rapid measurements
        measurements = []
        for _ in range(100):
            timer.start()
            # Simulate some computational work
            _ = sum(i * i for i in range(100))
            timer.stop()
            measurements.append(timer.elapsed_ns())
        
        # All measurements should be positive
        assert all(m > 0 for m in measurements)
        
        # Calculate statistics
        avg_time = sum(measurements) / len(measurements)
        min_time = min(measurements)
        max_time = max(measurements)
        
        # Basic sanity checks
        assert avg_time > 0
        assert min_time > 0
        assert max_time >= min_time
        
        # Variability should be reasonable (not too much jitter)
        variance = sum((m - avg_time) ** 2 for m in measurements) / len(measurements)
        std_dev = variance ** 0.5
        cv = std_dev / avg_time if avg_time > 0 else 0
        
        # Coefficient of variation should be reasonable (< 3.0 for most cases)
        assert cv < 3.0

    def test_thread_priority_mapping(self):
        """Test thread priority enum mapping."""
        priorities = [
            ThreadPriority.LOWEST,
            ThreadPriority.BELOW_NORMAL,
            ThreadPriority.NORMAL,
            ThreadPriority.ABOVE_NORMAL,
            ThreadPriority.HIGHEST,
            ThreadPriority.REALTIME
        ]
        
        for priority in priorities:
            assert isinstance(priority.value, int)
            assert 1 <= priority.value <= 6

    def test_config_validation(self):
        """Test configuration validation."""
        # Test valid configurations
        valid_configs = [
            SchedulingConfig(process_priority="HIGH"),
            SchedulingConfig(process_priority="REALTIME"),
            SchedulingConfig(affinity_mask=1),
            SchedulingConfig(affinity_mask=15),  # 4 CPUs
            SchedulingConfig(use_high_res_timer=True),
            SchedulingConfig(use_high_res_timer=False),
        ]
        
        for config in valid_configs:
            scheduler = WindowsScheduler(config)
            assert scheduler.config == config

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
