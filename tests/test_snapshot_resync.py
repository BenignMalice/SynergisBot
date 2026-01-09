"""
Comprehensive tests for snapshot re-sync system

Tests gap detection, re-sync strategy selection, operation execution,
metrics collection, and data integrity recovery.
"""

import pytest
import time
import asyncio
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from infra.snapshot_resync import (
    SnapshotResync, GapDetector, ResyncStrategySelector,
    ResyncConfig, GapInfo, ResyncOperation, ResyncMetrics,
    GapType, ResyncStrategy, ResyncStatus,
    get_snapshot_resync, process_sequence, get_resync_metrics,
    get_gap_statistics
)

class TestGapType:
    """Test gap type enumeration"""
    
    def test_gap_types(self):
        """Test all gap types"""
        gap_types = [
            GapType.MISSING_SEQUENCE,
            GapType.DUPLICATE_SEQUENCE,
            GapType.OUT_OF_ORDER,
            GapType.TIMEOUT_GAP,
            GapType.CONNECTION_LOST
        ]
        
        for gap_type in gap_types:
            assert isinstance(gap_type, GapType)
            assert gap_type.value in [
                "missing_sequence", "duplicate_sequence", "out_of_order",
                "timeout_gap", "connection_lost"
            ]

class TestResyncStrategy:
    """Test re-sync strategy enumeration"""
    
    def test_resync_strategies(self):
        """Test all re-sync strategies"""
        strategies = [
            ResyncStrategy.IGNORE,
            ResyncStrategy.REQUEST_SNAPSHOT,
            ResyncStrategy.REQUEST_PARTIAL,
            ResyncStrategy.FULL_RESYNC,
            ResyncStrategy.RESTART_STREAM
        ]
        
        for strategy in strategies:
            assert isinstance(strategy, ResyncStrategy)
            assert strategy.value in [
                "ignore", "request_snapshot", "request_partial",
                "full_resync", "restart_stream"
            ]

class TestResyncStatus:
    """Test re-sync status enumeration"""
    
    def test_resync_statuses(self):
        """Test all re-sync statuses"""
        statuses = [
            ResyncStatus.PENDING,
            ResyncStatus.IN_PROGRESS,
            ResyncStatus.COMPLETED,
            ResyncStatus.FAILED,
            ResyncStatus.CANCELLED
        ]
        
        for status in statuses:
            assert isinstance(status, ResyncStatus)
            assert status.value in [
                "pending", "in_progress", "completed", "failed", "cancelled"
            ]

class TestResyncConfig:
    """Test re-sync configuration"""
    
    def test_resync_config_creation(self):
        """Test re-sync configuration creation"""
        config = ResyncConfig(
            max_gap_size=1000,
            gap_timeout_ms=5000,
            resync_timeout_ms=30000,
            max_resync_attempts=3,
            snapshot_request_delay_ms=1000,
            partial_request_size=100,
            full_resync_threshold=100,
            enable_auto_resync=True,
            enable_metrics=True,
            gap_detection_window=10000
        )
        
        assert config.max_gap_size == 1000
        assert config.gap_timeout_ms == 5000
        assert config.resync_timeout_ms == 30000
        assert config.max_resync_attempts == 3
        assert config.snapshot_request_delay_ms == 1000
        assert config.partial_request_size == 100
        assert config.full_resync_threshold == 100
        assert config.enable_auto_resync is True
        assert config.enable_metrics is True
        assert config.gap_detection_window == 10000
    
    def test_resync_config_defaults(self):
        """Test re-sync configuration defaults"""
        config = ResyncConfig()
        
        assert config.max_gap_size == 1000
        assert config.gap_timeout_ms == 5000
        assert config.resync_timeout_ms == 30000
        assert config.max_resync_attempts == 3
        assert config.snapshot_request_delay_ms == 1000
        assert config.partial_request_size == 100
        assert config.full_resync_threshold == 100
        assert config.enable_auto_resync is True
        assert config.enable_metrics is True
        assert config.gap_detection_window == 10000

class TestGapInfo:
    """Test gap information data structure"""
    
    def test_gap_info_creation(self):
        """Test gap info creation"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=103,
            gap_size=3,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="medium",
            description="Missing 3 sequence(s)"
        )
        
        assert gap_info.gap_type == GapType.MISSING_SEQUENCE
        assert gap_info.expected_sequence == 100
        assert gap_info.received_sequence == 103
        assert gap_info.gap_size == 3
        assert gap_info.timestamp > 0
        assert gap_info.symbol == "BTCUSDc"
        assert gap_info.severity == "medium"
        assert gap_info.description == "Missing 3 sequence(s)"

class TestResyncOperation:
    """Test re-sync operation data structure"""
    
    def test_resync_operation_creation(self):
        """Test re-sync operation creation"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=103,
            gap_size=3,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="medium",
            description="Missing 3 sequence(s)"
        )
        
        operation = ResyncOperation(
            operation_id="test_123",
            gap_info=gap_info,
            strategy=ResyncStrategy.REQUEST_SNAPSHOT,
            status=ResyncStatus.PENDING,
            start_time=time.time(),
            max_attempts=3
        )
        
        assert operation.operation_id == "test_123"
        assert operation.gap_info == gap_info
        assert operation.strategy == ResyncStrategy.REQUEST_SNAPSHOT
        assert operation.status == ResyncStatus.PENDING
        assert operation.start_time > 0
        assert operation.end_time is None
        assert operation.attempts == 0
        assert operation.max_attempts == 3
        assert operation.error_message is None
        assert operation.data_recovered == 0
        assert operation.data_lost == 0

class TestResyncMetrics:
    """Test re-sync metrics data structure"""
    
    def test_resync_metrics_creation(self):
        """Test re-sync metrics creation"""
        metrics = ResyncMetrics(
            total_gaps_detected=10,
            total_resync_operations=5,
            successful_resyncs=4,
            failed_resyncs=1,
            data_recovered=1000,
            data_lost=50,
            avg_resync_time_ms=250.0,
            last_resync_time=time.time(),
            gaps_by_type={"missing_sequence": 8, "out_of_order": 2},
            resyncs_by_strategy={"request_snapshot": 3, "request_partial": 2}
        )
        
        assert metrics.total_gaps_detected == 10
        assert metrics.total_resync_operations == 5
        assert metrics.successful_resyncs == 4
        assert metrics.failed_resyncs == 1
        assert metrics.data_recovered == 1000
        assert metrics.data_lost == 50
        assert metrics.avg_resync_time_ms == 250.0
        assert metrics.last_resync_time > 0
        assert metrics.gaps_by_type["missing_sequence"] == 8
        assert metrics.resyncs_by_strategy["request_snapshot"] == 3
    
    def test_resync_metrics_defaults(self):
        """Test re-sync metrics defaults"""
        metrics = ResyncMetrics()
        
        assert metrics.total_gaps_detected == 0
        assert metrics.total_resync_operations == 0
        assert metrics.successful_resyncs == 0
        assert metrics.failed_resyncs == 0
        assert metrics.data_recovered == 0
        assert metrics.data_lost == 0
        assert metrics.avg_resync_time_ms == 0.0
        assert metrics.last_resync_time == 0.0
        assert len(metrics.gaps_by_type) == 0
        assert len(metrics.resyncs_by_strategy) == 0

class TestGapDetector:
    """Test gap detection functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ResyncConfig(gap_detection_window=100)
        self.detector = GapDetector(self.config)
    
    def test_gap_detector_initialization(self):
        """Test gap detector initialization"""
        assert self.detector.config == self.config
        assert len(self.detector.sequence_history) == 0
        assert len(self.detector.gap_thresholds) == 4
        assert self.detector.gap_thresholds['low'] == 1
        assert self.detector.gap_thresholds['medium'] == 10
        assert self.detector.gap_thresholds['high'] == 100
        assert self.detector.gap_thresholds['critical'] == 1000
    
    def test_no_gap_detection(self):
        """Test no gap detection for sequential sequences"""
        # Sequential sequences should not trigger gaps
        gap_info = self.detector.detect_gap(100, 100, "BTCUSDc", time.time())
        assert gap_info is None
        
        gap_info = self.detector.detect_gap(101, 101, "BTCUSDc", time.time())
        assert gap_info is None
    
    def test_missing_sequence_gap(self):
        """Test missing sequence gap detection"""
        gap_info = self.detector.detect_gap(100, 103, "BTCUSDc", time.time())
        
        assert gap_info is not None
        assert gap_info.gap_type == GapType.MISSING_SEQUENCE
        assert gap_info.expected_sequence == 100
        assert gap_info.received_sequence == 103
        assert gap_info.gap_size == 3
        assert gap_info.symbol == "BTCUSDc"
        assert gap_info.severity == "medium"  # Gap size 3 is medium severity
        assert "Missing 3 sequence(s)" in gap_info.description
    
    def test_out_of_order_gap(self):
        """Test out-of-order sequence gap detection"""
        gap_info = self.detector.detect_gap(103, 100, "BTCUSDc", time.time())
        
        assert gap_info is not None
        assert gap_info.gap_type == GapType.OUT_OF_ORDER
        assert gap_info.expected_sequence == 103
        assert gap_info.received_sequence == 100
        assert gap_info.gap_size == 3
        assert gap_info.severity == "medium"  # Gap size 3 is medium severity
        assert "Out-of-order sequence" in gap_info.description
    
    def test_duplicate_sequence_gap(self):
        """Test duplicate sequence gap detection"""
        # First sequence
        gap_info = self.detector.detect_gap(100, 100, "BTCUSDc", time.time())
        assert gap_info is None
        
        # Duplicate sequence
        gap_info = self.detector.detect_gap(101, 100, "BTCUSDc", time.time())
        
        assert gap_info is not None
        assert gap_info.gap_type == GapType.OUT_OF_ORDER  # Classified as out-of-order
        assert gap_info.expected_sequence == 101
        assert gap_info.received_sequence == 100
        assert gap_info.gap_size == 1
    
    def test_severity_assessment(self):
        """Test severity assessment for different gap sizes"""
        # Low severity
        gap_info = self.detector.detect_gap(100, 101, "BTCUSDc", time.time())
        assert gap_info.severity == "low"
        
        # Medium severity
        gap_info = self.detector.detect_gap(100, 110, "BTCUSDc", time.time())
        assert gap_info.severity == "medium"
        
        # High severity
        gap_info = self.detector.detect_gap(100, 200, "BTCUSDc", time.time())
        assert gap_info.severity == "high"
        
        # Critical severity
        gap_info = self.detector.detect_gap(100, 1100, "BTCUSDc", time.time())
        assert gap_info.severity == "critical"
    
    def test_gap_statistics(self):
        """Test gap statistics collection"""
        # Add some sequences with gaps
        self.detector.detect_gap(100, 100, "BTCUSDc", time.time())  # No gap
        self.detector.detect_gap(101, 101, "BTCUSDc", time.time())  # No gap
        self.detector.detect_gap(102, 105, "BTCUSDc", time.time())  # Gap
        self.detector.detect_gap(105, 105, "BTCUSDc", time.time())  # No gap
        
        stats = self.detector.get_gap_statistics()
        
        assert stats['total_sequences'] == 4
        assert stats['gaps_detected'] == 1
        assert stats['gap_rate'] == 0.25
        assert stats['window_size'] == 100

class TestResyncStrategySelector:
    """Test re-sync strategy selection"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ResyncConfig()
        self.selector = ResyncStrategySelector(self.config)
    
    def test_strategy_selector_initialization(self):
        """Test strategy selector initialization"""
        assert self.selector.config == self.config
        assert len(self.selector.strategy_rules) == 5  # 5 gap types
        assert GapType.MISSING_SEQUENCE in self.selector.strategy_rules
        assert GapType.DUPLICATE_SEQUENCE in self.selector.strategy_rules
        assert GapType.OUT_OF_ORDER in self.selector.strategy_rules
        assert GapType.TIMEOUT_GAP in self.selector.strategy_rules
        assert GapType.CONNECTION_LOST in self.selector.strategy_rules
    
    def test_missing_sequence_strategies(self):
        """Test strategy selection for missing sequences"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=101,
            gap_size=1,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="low",
            description="Missing 1 sequence(s)"
        )
        
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.IGNORE
        
        # Medium severity
        gap_info.severity = "medium"
        gap_info.gap_size = 10
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_PARTIAL
        
        # High severity
        gap_info.severity = "high"
        gap_info.gap_size = 100
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_SNAPSHOT
        
        # Critical severity
        gap_info.severity = "critical"
        gap_info.gap_size = 1000
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.FULL_RESYNC
    
    def test_duplicate_sequence_strategies(self):
        """Test strategy selection for duplicate sequences"""
        gap_info = GapInfo(
            gap_type=GapType.DUPLICATE_SEQUENCE,
            expected_sequence=100,
            received_sequence=100,
            gap_size=0,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="low",
            description="Duplicate sequence"
        )
        
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.IGNORE
        
        # High severity
        gap_info.severity = "high"
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_PARTIAL
        
        # Critical severity
        gap_info.severity = "critical"
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_SNAPSHOT
    
    def test_timeout_gap_strategies(self):
        """Test strategy selection for timeout gaps"""
        gap_info = GapInfo(
            gap_type=GapType.TIMEOUT_GAP,
            expected_sequence=100,
            received_sequence=100,
            gap_size=0,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="low",
            description="Timeout gap"
        )
        
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_PARTIAL
        
        # Critical severity
        gap_info.severity = "critical"
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.RESTART_STREAM
    
    def test_connection_lost_strategies(self):
        """Test strategy selection for connection lost"""
        gap_info = GapInfo(
            gap_type=GapType.CONNECTION_LOST,
            expected_sequence=100,
            received_sequence=100,
            gap_size=0,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="low",
            description="Connection lost"
        )
        
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.REQUEST_SNAPSHOT
        
        # Critical severity
        gap_info.severity = "critical"
        strategy = self.selector.select_strategy(gap_info)
        assert strategy == ResyncStrategy.RESTART_STREAM

class TestSnapshotResync:
    """Test snapshot re-sync system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ResyncConfig(
            max_gap_size=1000,
            enable_auto_resync=False  # Disable for testing
        )
        self.resync = SnapshotResync(self.config)
    
    def test_resync_initialization(self):
        """Test re-sync system initialization"""
        assert self.resync.config == self.config
        assert isinstance(self.resync.gap_detector, GapDetector)
        assert isinstance(self.resync.strategy_selector, ResyncStrategySelector)
        assert len(self.resync.active_operations) == 0
        assert len(self.resync.completed_operations) == 0
        assert isinstance(self.resync.metrics, ResyncMetrics)
    
    def test_process_sequence_no_gap(self):
        """Test processing sequence with no gap"""
        operation = self.resync.process_sequence(100, "BTCUSDc", 100, time.time())
        assert operation is None
    
    def test_process_sequence_with_gap(self):
        """Test processing sequence with gap"""
        operation = self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        
        assert operation is not None
        assert operation.gap_info.gap_type == GapType.MISSING_SEQUENCE
        assert operation.gap_info.expected_sequence == 100
        assert operation.gap_info.received_sequence == 103
        assert operation.gap_info.symbol == "BTCUSDc"
        assert operation.strategy == ResyncStrategy.REQUEST_PARTIAL  # Low severity
        assert operation.status == ResyncStatus.PENDING
        assert operation.operation_id is not None
    
    def test_process_sequence_ignore_strategy(self):
        """Test processing sequence with ignore strategy"""
        # Create a very small gap that should be ignored
        operation = self.resync.process_sequence(101, "BTCUSDc", 100, time.time())
        
        # Gap size 1 should be ignored (low severity) and return None
        assert operation is None
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_gap_detected = Mock()
        on_resync_started = Mock()
        on_resync_completed = Mock()
        on_resync_failed = Mock()
        
        self.resync.set_callbacks(
            on_gap_detected=on_gap_detected,
            on_resync_started=on_resync_started,
            on_resync_completed=on_resync_completed,
            on_resync_failed=on_resync_failed
        )
        
        assert self.resync.on_gap_detected == on_gap_detected
        assert self.resync.on_resync_started == on_resync_started
        assert self.resync.on_resync_completed == on_resync_completed
        assert self.resync.on_resync_failed == on_resync_failed
    
    def test_get_active_operations(self):
        """Test getting active operations"""
        # Create some operations
        operation1 = self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        operation2 = self.resync.process_sequence(106, "ETHUSDc", 104, time.time())
        
        active_operations = self.resync.get_active_operations()
        assert len(active_operations) == 2
        assert operation1 in active_operations
        assert operation2 in active_operations
    
    def test_get_completed_operations(self):
        """Test getting completed operations"""
        # Initially no completed operations
        completed = self.resync.get_completed_operations()
        assert len(completed) == 0
        
        # After operations complete, they should appear here
        # (This would require actual execution of operations)
    
    def test_get_metrics(self):
        """Test getting re-sync metrics"""
        # Process some sequences
        self.resync.process_sequence(100, "BTCUSDc", 100, time.time())  # No gap
        self.resync.process_sequence(103, "BTCUSDc", 101, time.time())  # Gap
        
        metrics = self.resync.get_metrics()
        assert isinstance(metrics, ResyncMetrics)
        assert metrics.total_gaps_detected >= 1
        assert metrics.total_resync_operations >= 1
    
    def test_get_gap_statistics(self):
        """Test getting gap statistics"""
        # Process some sequences
        self.resync.process_sequence(100, "BTCUSDc", 100, time.time())
        self.resync.process_sequence(103, "BTCUSDc", 101, time.time())
        
        stats = self.resync.get_gap_statistics()
        assert isinstance(stats, dict)
        assert 'total_sequences' in stats
        assert 'gaps_detected' in stats
        assert 'gap_rate' in stats
        assert 'window_size' in stats
    
    def test_cancel_operation(self):
        """Test cancelling an operation"""
        # Create an operation
        operation = self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        operation_id = operation.operation_id
        
        # Cancel the operation
        success = self.resync.cancel_operation(operation_id)
        assert success is True
        
        # Check that operation is no longer active
        active_operations = self.resync.get_active_operations()
        assert len(active_operations) == 0
        
        # Try to cancel non-existent operation
        success = self.resync.cancel_operation("non_existent")
        assert success is False
    
    def test_reset_metrics(self):
        """Test resetting metrics"""
        # Process some sequences to create metrics
        self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        
        # Reset metrics
        self.resync.reset_metrics()
        
        # Check that metrics are reset
        metrics = self.resync.get_metrics()
        assert metrics.total_gaps_detected == 0
        assert metrics.total_resync_operations == 0
        assert len(self.resync.active_operations) == 0
        assert len(self.resync.completed_operations) == 0

class TestResyncIntegration:
    """Integration tests for re-sync system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ResyncConfig(enable_auto_resync=False)
        self.resync = SnapshotResync(self.config)
    
    @pytest.mark.asyncio
    async def test_resync_operation_execution(self):
        """Test re-sync operation execution"""
        # Create an operation
        operation = self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        
        # Manually execute the operation
        success = await self.resync._execute_strategy(operation)
        assert success is True
        assert operation.data_recovered > 0
    
    @pytest.mark.asyncio
    async def test_request_snapshot_strategy(self):
        """Test request snapshot strategy"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=103,
            gap_size=3,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="high",
            description="Missing 3 sequence(s)"
        )
        
        operation = ResyncOperation(
            operation_id="test_123",
            gap_info=gap_info,
            strategy=ResyncStrategy.REQUEST_SNAPSHOT,
            status=ResyncStatus.PENDING,
            start_time=time.time()
        )
        
        success = await self.resync._request_snapshot(operation)
        assert success is True
        assert operation.data_recovered == 3
    
    @pytest.mark.asyncio
    async def test_request_partial_strategy(self):
        """Test request partial strategy"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=103,
            gap_size=3,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="medium",
            description="Missing 3 sequence(s)"
        )
        
        operation = ResyncOperation(
            operation_id="test_123",
            gap_info=gap_info,
            strategy=ResyncStrategy.REQUEST_PARTIAL,
            status=ResyncStatus.PENDING,
            start_time=time.time()
        )
        
        success = await self.resync._request_partial(operation)
        assert success is True
        assert operation.data_recovered > 0
    
    @pytest.mark.asyncio
    async def test_full_resync_strategy(self):
        """Test full resync strategy"""
        gap_info = GapInfo(
            gap_type=GapType.MISSING_SEQUENCE,
            expected_sequence=100,
            received_sequence=103,
            gap_size=3,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="critical",
            description="Missing 3 sequence(s)"
        )
        
        operation = ResyncOperation(
            operation_id="test_123",
            gap_info=gap_info,
            strategy=ResyncStrategy.FULL_RESYNC,
            status=ResyncStatus.PENDING,
            start_time=time.time()
        )
        
        success = await self.resync._full_resync(operation)
        assert success is True
        assert operation.data_recovered == 3
    
    @pytest.mark.asyncio
    async def test_restart_stream_strategy(self):
        """Test restart stream strategy"""
        gap_info = GapInfo(
            gap_type=GapType.CONNECTION_LOST,
            expected_sequence=100,
            received_sequence=100,
            gap_size=0,
            timestamp=time.time(),
            symbol="BTCUSDc",
            severity="critical",
            description="Connection lost"
        )
        
        operation = ResyncOperation(
            operation_id="test_123",
            gap_info=gap_info,
            strategy=ResyncStrategy.RESTART_STREAM,
            status=ResyncStatus.PENDING,
            start_time=time.time()
        )
        
        success = await self.resync._restart_stream(operation)
        assert success is True
        assert operation.data_recovered == 0
    
    def test_comprehensive_gap_processing(self):
        """Test comprehensive gap processing"""
        # Process various gap scenarios
        sequences = [
            (100, 100, "BTCUSDc"),  # No gap
            (101, 101, "BTCUSDc"),  # No gap
            (102, 105, "BTCUSDc"),  # Missing sequence gap
            (105, 105, "BTCUSDc"),  # No gap
            (106, 104, "ETHUSDc"),  # Out-of-order gap
            (104, 104, "ETHUSDc"),  # No gap
        ]
        
        operations = []
        for received, expected, symbol in sequences:
            operation = self.resync.process_sequence(
                received, symbol, expected, time.time()
            )
            if operation:
                operations.append(operation)
        
        # Should have detected gaps
        assert len(operations) >= 2  # At least 2 gaps detected
        
        # Check metrics
        metrics = self.resync.get_metrics()
        assert metrics.total_gaps_detected >= 2
        assert metrics.total_resync_operations >= 2
    
    def test_callback_integration(self):
        """Test callback integration"""
        on_gap_detected_called = False
        on_resync_started_called = False
        
        def on_gap_detected(gap_info):
            nonlocal on_gap_detected_called
            on_gap_detected_called = True
        
        def on_resync_started(operation):
            nonlocal on_resync_started_called
            on_resync_started_called = True
        
        self.resync.set_callbacks(
            on_gap_detected=on_gap_detected,
            on_resync_started=on_resync_started
        )
        
        # Process a sequence with gap
        operation = self.resync.process_sequence(103, "BTCUSDc", 100, time.time())
        
        # Callbacks should be called
        assert on_gap_detected_called is True
        # on_resync_started would be called during actual execution

class TestGlobalFunctions:
    """Test global re-sync functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global instance
        import infra.snapshot_resync
        infra.snapshot_resync._snapshot_resync = None
    
    def test_get_snapshot_resync(self):
        """Test global snapshot resync access"""
        resync1 = get_snapshot_resync()
        resync2 = get_snapshot_resync()
        
        # Should return same instance
        assert resync1 is resync2
        assert isinstance(resync1, SnapshotResync)
    
    def test_process_sequence_global(self):
        """Test global sequence processing"""
        # Process sequence with gap
        operation = process_sequence(103, "BTCUSDc", 100, time.time())
        
        assert operation is not None
        assert operation.gap_info.symbol == "BTCUSDc"
        assert operation.gap_info.expected_sequence == 100
        assert operation.gap_info.received_sequence == 103
    
    def test_get_resync_metrics_global(self):
        """Test global metrics retrieval"""
        # Process some sequences
        process_sequence(100, "BTCUSDc", 100, time.time())
        process_sequence(103, "BTCUSDc", 101, time.time())
        
        metrics = get_resync_metrics()
        assert isinstance(metrics, ResyncMetrics)
        assert metrics.total_gaps_detected >= 1
    
    def test_get_gap_statistics_global(self):
        """Test global gap statistics"""
        # Process some sequences
        process_sequence(100, "BTCUSDc", 100, time.time())
        process_sequence(103, "BTCUSDc", 101, time.time())
        
        stats = get_gap_statistics()
        assert isinstance(stats, dict)
        assert 'total_sequences' in stats
        assert 'gaps_detected' in stats
        assert 'gap_rate' in stats

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
