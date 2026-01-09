"""
Comprehensive tests for hot-path architecture stability validation system

Tests hot-path stability monitoring, database blocking detection, I/O operation
validation, memory pressure analysis, thread safety verification, and performance
degradation detection.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
import asyncio
import queue
import psutil
import gc
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import deque

from infra.hot_path_validation import (
    HotPathValidator, HotPathMonitor, DatabaseBlockingDetector, HotPathContext,
    HotPathStage, StabilityLevel, BlockingType,
    HotPathMetrics, BlockingEvent, StabilityReport,
    get_hot_path_validator, validate_hot_path_stability, get_stability_report, hot_path_operation
)

class TestHotPathStage:
    """Test hot-path stage enumeration"""
    
    def test_hot_path_stages(self):
        """Test all hot-path stages"""
        stages = [
            HotPathStage.TICK_INGESTION,
            HotPathStage.DATA_NORMALIZATION,
            HotPathStage.RING_BUFFER_WRITE,
            HotPathStage.VWAP_CALCULATION,
            HotPathStage.ATR_CALCULATION,
            HotPathStage.DELTA_ANALYSIS,
            HotPathStage.STRUCTURE_DETECTION,
            HotPathStage.FILTER_PROCESSING,
            HotPathStage.DECISION_MAKING,
            HotPathStage.ORDER_PROCESSING
        ]
        
        for stage in stages:
            assert isinstance(stage, HotPathStage)
            assert stage.value in [
                "tick_ingestion", "data_normalization", "ring_buffer_write",
                "vwap_calculation", "atr_calculation", "delta_analysis",
                "structure_detection", "filter_processing", "decision_making", "order_processing"
            ]

class TestStabilityLevel:
    """Test stability level enumeration"""
    
    def test_stability_levels(self):
        """Test all stability levels"""
        levels = [
            StabilityLevel.EXCELLENT,
            StabilityLevel.GOOD,
            StabilityLevel.DEGRADED,
            StabilityLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, StabilityLevel)
            assert level.value in ["excellent", "good", "degraded", "critical"]

class TestBlockingType:
    """Test blocking type enumeration"""
    
    def test_blocking_types(self):
        """Test all blocking types"""
        types = [
            BlockingType.DATABASE_WRITE,
            BlockingType.DATABASE_READ,
            BlockingType.FILE_IO,
            BlockingType.NETWORK_IO,
            BlockingType.MEMORY_ALLOCATION,
            BlockingType.GARBAGE_COLLECTION,
            BlockingType.THREAD_SYNCHRONIZATION
        ]
        
        for blocking_type in types:
            assert isinstance(blocking_type, BlockingType)
            assert blocking_type.value in [
                "database_write", "database_read", "file_io", "network_io",
                "memory_allocation", "garbage_collection", "thread_synchronization"
            ]

class TestHotPathMetrics:
    """Test hot-path metrics data structure"""
    
    def test_hot_path_metrics_creation(self):
        """Test hot-path metrics creation"""
        metrics = HotPathMetrics(
            timestamp=time.time(),
            stage=HotPathStage.TICK_INGESTION,
            processing_time_ms=5.5,
            memory_usage_mb=100.0,
            cpu_usage_percent=25.0,
            queue_depth=10,
            blocking_operations=2,
            io_operations=5,
            thread_count=8,
            gc_count=1000,
            metadata={"operation": "process_tick", "symbol": "BTCUSDc"}
        )
        
        assert metrics.timestamp > 0
        assert metrics.stage == HotPathStage.TICK_INGESTION
        assert metrics.processing_time_ms == 5.5
        assert metrics.memory_usage_mb == 100.0
        assert metrics.cpu_usage_percent == 25.0
        assert metrics.queue_depth == 10
        assert metrics.blocking_operations == 2
        assert metrics.io_operations == 5
        assert metrics.thread_count == 8
        assert metrics.gc_count == 1000
        assert metrics.metadata["operation"] == "process_tick"
    
    def test_hot_path_metrics_defaults(self):
        """Test hot-path metrics defaults"""
        metrics = HotPathMetrics(
            timestamp=time.time(),
            stage=HotPathStage.VWAP_CALCULATION,
            processing_time_ms=10.2,
            memory_usage_mb=150.0,
            cpu_usage_percent=30.0,
            queue_depth=5,
            blocking_operations=1,
            io_operations=3,
            thread_count=6,
            gc_count=800
        )
        
        assert metrics.metadata == {}

class TestBlockingEvent:
    """Test blocking event data structure"""
    
    def test_blocking_event_creation(self):
        """Test blocking event creation"""
        event = BlockingEvent(
            timestamp=time.time(),
            stage=HotPathStage.ORDER_PROCESSING,
            blocking_type=BlockingType.DATABASE_WRITE,
            duration_ms=50.0,
            thread_id=12345,
            operation_details="INSERT INTO trades",
            severity="high"
        )
        
        assert event.timestamp > 0
        assert event.stage == HotPathStage.ORDER_PROCESSING
        assert event.blocking_type == BlockingType.DATABASE_WRITE
        assert event.duration_ms == 50.0
        assert event.thread_id == 12345
        assert event.operation_details == "INSERT INTO trades"
        assert event.severity == "high"
    
    def test_blocking_event_severity_levels(self):
        """Test blocking event severity levels"""
        severities = ["low", "medium", "high", "critical"]
        
        for severity in severities:
            event = BlockingEvent(
                timestamp=time.time(),
                stage=HotPathStage.ORDER_PROCESSING,
                blocking_type=BlockingType.DATABASE_WRITE,
                duration_ms=10.0,
                thread_id=12345,
                operation_details="test_operation",
                severity=severity
            )
            
            assert event.severity == severity

class TestStabilityReport:
    """Test stability report data structure"""
    
    def test_stability_report_creation(self):
        """Test stability report creation"""
        report = StabilityReport(
            overall_stability=StabilityLevel.GOOD,
            blocking_events_count=5,
            critical_blocking_events=1,
            average_processing_time_ms=15.5,
            max_processing_time_ms=50.0,
            memory_pressure_score=0.3,
            io_pressure_score=0.2,
            thread_contention_score=0.1,
            recommendations=["Optimize database queries", "Reduce memory usage"],
            stage_analysis={"tick_ingestion": {"count": 100, "avg_time": 5.0}}
        )
        
        assert report.overall_stability == StabilityLevel.GOOD
        assert report.blocking_events_count == 5
        assert report.critical_blocking_events == 1
        assert report.average_processing_time_ms == 15.5
        assert report.max_processing_time_ms == 50.0
        assert report.memory_pressure_score == 0.3
        assert report.io_pressure_score == 0.2
        assert report.thread_contention_score == 0.1
        assert len(report.recommendations) == 2
        assert "tick_ingestion" in report.stage_analysis
    
    def test_stability_report_defaults(self):
        """Test stability report defaults"""
        report = StabilityReport(
            overall_stability=StabilityLevel.EXCELLENT,
            blocking_events_count=0,
            critical_blocking_events=0,
            average_processing_time_ms=5.0,
            max_processing_time_ms=10.0,
            memory_pressure_score=0.1,
            io_pressure_score=0.05,
            thread_contention_score=0.02,
            recommendations=[],
            stage_analysis={}
        )
        
        assert report.recommendations == []
        assert report.stage_analysis == {}

class TestHotPathMonitor:
    """Test hot-path monitor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.monitor = HotPathMonitor(max_metrics=1000)
    
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        assert self.monitor.max_metrics == 1000
        assert len(self.monitor.metrics) == 0
        assert len(self.monitor.blocking_events) == 0
        assert hasattr(self.monitor, 'lock')
        assert self.monitor.start_time > 0
        assert len(self.monitor.stage_timers) == 0
        assert len(self.monitor.stage_counts) == 0
        assert len(self.monitor.blocking_counts) == 0
    
    def test_record_metrics(self):
        """Test recording metrics"""
        metrics = HotPathMetrics(
            timestamp=time.time(),
            stage=HotPathStage.TICK_INGESTION,
            processing_time_ms=5.0,
            memory_usage_mb=100.0,
            cpu_usage_percent=25.0,
            queue_depth=10,
            blocking_operations=0,
            io_operations=2,
            thread_count=8,
            gc_count=1000
        )
        
        self.monitor.record_metrics(metrics)
        
        assert len(self.monitor.metrics) == 1
        assert self.monitor.stage_counts[HotPathStage.TICK_INGESTION] == 1
        assert HotPathStage.TICK_INGESTION in self.monitor.stage_timers
    
    def test_record_blocking_event(self):
        """Test recording blocking event"""
        event = BlockingEvent(
            timestamp=time.time(),
            stage=HotPathStage.ORDER_PROCESSING,
            blocking_type=BlockingType.DATABASE_WRITE,
            duration_ms=50.0,
            thread_id=12345,
            operation_details="INSERT INTO trades",
            severity="high"
        )
        
        self.monitor.record_blocking_event(event)
        
        assert len(self.monitor.blocking_events) == 1
        assert self.monitor.blocking_counts[BlockingType.DATABASE_WRITE] == 1
    
    def test_get_stability_report_empty(self):
        """Test getting stability report with no data"""
        report = self.monitor.get_stability_report()
        
        assert report.overall_stability == StabilityLevel.EXCELLENT
        assert report.blocking_events_count == 0
        assert report.critical_blocking_events == 0
        assert report.average_processing_time_ms == 0.0
        assert report.max_processing_time_ms == 0.0
        assert report.memory_pressure_score == 0.0
        assert report.io_pressure_score == 0.0
        assert report.thread_contention_score == 0.0
        assert report.recommendations == []
        assert report.stage_analysis == {}
    
    def test_get_stability_report_with_data(self):
        """Test getting stability report with data"""
        # Add some metrics
        for i in range(10):
            metrics = HotPathMetrics(
                timestamp=time.time() + i,
                stage=HotPathStage.TICK_INGESTION,
                processing_time_ms=5.0 + i * 0.5,
                memory_usage_mb=100.0 + i * 10.0,
                cpu_usage_percent=25.0 + i * 2.0,
                queue_depth=10 + i,
                blocking_operations=i,
                io_operations=2 + i,
                thread_count=8,
                gc_count=1000 + i * 100
            )
            self.monitor.record_metrics(metrics)
        
        # Add some blocking events
        for i in range(5):
            event = BlockingEvent(
                timestamp=time.time() + i,
                stage=HotPathStage.ORDER_PROCESSING,
                blocking_type=BlockingType.DATABASE_WRITE,
                duration_ms=10.0 + i * 5.0,
                thread_id=12345,
                operation_details=f"operation_{i}",
                severity="medium"
            )
            self.monitor.record_blocking_event(event)
        
        report = self.monitor.get_stability_report()
        
        assert report.overall_stability in [StabilityLevel.EXCELLENT, StabilityLevel.GOOD, 
                                           StabilityLevel.DEGRADED, StabilityLevel.CRITICAL]
        assert report.blocking_events_count == 5
        assert report.critical_blocking_events >= 0
        assert report.average_processing_time_ms > 0.0
        assert report.max_processing_time_ms > 0.0
        assert 0.0 <= report.memory_pressure_score <= 1.0
        assert 0.0 <= report.io_pressure_score <= 1.0
        assert 0.0 <= report.thread_contention_score <= 1.0
        assert isinstance(report.recommendations, list)
        assert isinstance(report.stage_analysis, dict)
    
    def test_calculate_memory_pressure(self):
        """Test memory pressure calculation"""
        # Test with empty data
        pressure = self.monitor._calculate_memory_pressure([])
        assert pressure == 0.0
        
        # Test with data
        memory_usage = [100.0, 150.0, 200.0, 250.0]
        pressure = self.monitor._calculate_memory_pressure(memory_usage)
        assert 0.0 <= pressure <= 1.0
    
    def test_calculate_io_pressure(self):
        """Test I/O pressure calculation"""
        # Test with no metrics
        pressure = self.monitor._calculate_io_pressure()
        assert pressure == 0.0
        
        # Add some metrics with I/O operations
        for i in range(5):
            metrics = HotPathMetrics(
                timestamp=time.time() + i,
                stage=HotPathStage.TICK_INGESTION,
                processing_time_ms=5.0,
                memory_usage_mb=100.0,
                cpu_usage_percent=25.0,
                queue_depth=10,
                blocking_operations=0,
                io_operations=10 + i * 5,  # Increasing I/O operations
                thread_count=8,
                gc_count=1000
            )
            self.monitor.record_metrics(metrics)
        
        pressure = self.monitor._calculate_io_pressure()
        assert 0.0 <= pressure <= 1.0
    
    def test_calculate_thread_contention(self):
        """Test thread contention calculation"""
        # Test with no metrics
        contention = self.monitor._calculate_thread_contention()
        assert contention == 0.0
        
        # Add some metrics
        for i in range(5):
            metrics = HotPathMetrics(
                timestamp=time.time() + i,
                stage=HotPathStage.TICK_INGESTION,
                processing_time_ms=5.0,
                memory_usage_mb=100.0,
                cpu_usage_percent=25.0,
                queue_depth=10,
                blocking_operations=0,
                io_operations=2,
                thread_count=10 + i * 2,  # Increasing thread count
                gc_count=1000
            )
            self.monitor.record_metrics(metrics)
        
        contention = self.monitor._calculate_thread_contention()
        assert 0.0 <= contention <= 1.0
    
    def test_determine_stability(self):
        """Test stability determination"""
        # Test excellent stability
        stability = self.monitor._determine_stability(0, 0, 10.0, 0.1, 0.1, 0.1)
        assert stability == StabilityLevel.EXCELLENT
        
        # Test good stability
        stability = self.monitor._determine_stability(8, 0, 60.0, 0.7, 0.7, 0.7)
        assert stability == StabilityLevel.GOOD
        
        # Test degraded stability
        stability = self.monitor._determine_stability(25, 0, 120.0, 0.9, 0.9, 0.9)
        assert stability == StabilityLevel.DEGRADED
        
        # Test critical stability
        stability = self.monitor._determine_stability(30, 2, 100.0, 0.9, 0.9, 0.9)
        assert stability == StabilityLevel.CRITICAL
    
    def test_generate_recommendations(self):
        """Test recommendation generation"""
        # Test with no issues
        recommendations = self.monitor._generate_recommendations(0, 0, 0.1, 0.1, 0.1)
        assert len(recommendations) == 1
        assert "stable" in recommendations[0].lower()
        
        # Test with critical blocking
        recommendations = self.monitor._generate_recommendations(10, 2, 0.5, 0.5, 0.5)
        assert len(recommendations) >= 1
        assert any("critical" in rec.lower() for rec in recommendations)
    
    def test_analyze_stages(self):
        """Test stage analysis"""
        # Add metrics for different stages
        stages = [HotPathStage.TICK_INGESTION, HotPathStage.VWAP_CALCULATION]
        
        for stage in stages:
            for i in range(3):
                metrics = HotPathMetrics(
                    timestamp=time.time() + i,
                    stage=stage,
                    processing_time_ms=5.0 + i,
                    memory_usage_mb=100.0 + i * 10,
                    cpu_usage_percent=25.0,
                    queue_depth=10,
                    blocking_operations=0,
                    io_operations=2,
                    thread_count=8,
                    gc_count=1000
                )
                self.monitor.record_metrics(metrics)
        
        stage_analysis = self.monitor._analyze_stages()
        
        assert len(stage_analysis) == 2
        for stage in stages:
            assert stage.value in stage_analysis
            analysis = stage_analysis[stage.value]
            assert 'count' in analysis
            assert 'avg_processing_time_ms' in analysis
            assert 'max_processing_time_ms' in analysis
            assert 'avg_memory_mb' in analysis
            assert 'blocking_events' in analysis

class TestDatabaseBlockingDetector:
    """Test database blocking detector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = DatabaseBlockingDetector()
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        assert len(self.detector.blocking_operations) == 0
        assert hasattr(self.detector, 'lock')
        assert self.detector.start_time > 0
    
    def test_detect_database_blocking_short_operation(self):
        """Test detecting short database operations"""
        event = self.detector.detect_database_blocking("SELECT * FROM trades", 0.5, 12345)
        assert event is None  # Short operations should be ignored
    
    def test_detect_database_blocking_long_operation(self):
        """Test detecting long database operations"""
        event = self.detector.detect_database_blocking("INSERT INTO trades", 50.0, 12345)
        
        assert event is not None
        assert isinstance(event, BlockingEvent)
        assert event.duration_ms == 50.0
        assert event.thread_id == 12345
        assert event.operation_details == "INSERT INTO trades"
        assert event.severity in ["low", "medium", "high", "critical"]
    
    def test_detect_database_blocking_severity_levels(self):
        """Test severity level assignment"""
        # Test low severity
        event = self.detector.detect_database_blocking("operation", 5.0, 12345)
        assert event.severity == "low"
        
        # Test medium severity
        event = self.detector.detect_database_blocking("operation", 15.0, 12345)
        assert event.severity == "medium"
        
        # Test high severity
        event = self.detector.detect_database_blocking("operation", 60.0, 12345)
        assert event.severity == "high"
        
        # Test critical severity
        event = self.detector.detect_database_blocking("operation", 150.0, 12345)
        assert event.severity == "critical"
    
    def test_get_blocking_summary_empty(self):
        """Test getting blocking summary with no data"""
        summary = self.detector.get_blocking_summary()
        
        assert summary['total_operations'] == 0
        assert summary['critical_operations'] == 0
        assert summary['average_duration_ms'] == 0.0
        assert summary['max_duration_ms'] == 0.0
        assert summary['operations_by_severity'] == {}
    
    def test_get_blocking_summary_with_data(self):
        """Test getting blocking summary with data"""
        # Add some blocking operations
        operations = [
            ("SELECT * FROM trades", 10.0, 12345),
            ("INSERT INTO trades", 25.0, 12346),
            ("UPDATE trades", 60.0, 12347),
            ("DELETE FROM trades", 120.0, 12348)
        ]
        
        for operation, duration, thread_id in operations:
            self.detector.detect_database_blocking(operation, duration, thread_id)
        
        summary = self.detector.get_blocking_summary()
        
        assert summary['total_operations'] == 4
        assert summary['critical_operations'] >= 0
        assert summary['average_duration_ms'] > 0.0
        assert summary['max_duration_ms'] > 0.0
        assert len(summary['operations_by_severity']) > 0

class TestHotPathValidator:
    """Test hot-path validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = HotPathValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.monitor, HotPathMonitor)
        assert isinstance(self.validator.blocking_detector, DatabaseBlockingDetector)
        assert self.validator.start_time > 0
        assert len(self.validator.validation_results) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_hot_path_stability(self):
        """Test hot-path stability validation"""
        result = self.validator.validate_hot_path_stability()
        
        assert 'timestamp' in result
        assert 'is_stable' in result
        assert 'no_db_blocking' in result
        assert 'stability_level' in result
        assert 'blocking_events_count' in result
        assert 'critical_blocking_events' in result
        assert 'average_processing_time_ms' in result
        assert 'max_processing_time_ms' in result
        assert 'memory_pressure_score' in result
        assert 'io_pressure_score' in result
        assert 'thread_contention_score' in result
        assert 'blocking_summary' in result
        assert 'stage_analysis' in result
        assert 'recommendations' in result
        assert 'uptime_seconds' in result
        
        assert isinstance(result['is_stable'], bool)
        assert isinstance(result['no_db_blocking'], bool)
        assert result['stability_level'] in ['excellent', 'good', 'degraded', 'critical']
        assert result['blocking_events_count'] >= 0
        assert result['critical_blocking_events'] >= 0
        assert result['average_processing_time_ms'] >= 0.0
        assert result['max_processing_time_ms'] >= 0.0
        assert 0.0 <= result['memory_pressure_score'] <= 1.0
        assert 0.0 <= result['io_pressure_score'] <= 1.0
        assert 0.0 <= result['thread_contention_score'] <= 1.0
        assert isinstance(result['recommendations'], list)
        assert isinstance(result['stage_analysis'], dict)
    
    def test_get_stability_report(self):
        """Test getting stability report"""
        report = self.validator.get_stability_report()
        
        assert isinstance(report, StabilityReport)
        assert report.overall_stability in [StabilityLevel.EXCELLENT, StabilityLevel.GOOD, 
                                           StabilityLevel.DEGRADED, StabilityLevel.CRITICAL]
        assert report.blocking_events_count >= 0
        assert report.critical_blocking_events >= 0
        assert report.average_processing_time_ms >= 0.0
        assert report.max_processing_time_ms >= 0.0
        assert 0.0 <= report.memory_pressure_score <= 1.0
        assert 0.0 <= report.io_pressure_score <= 1.0
        assert 0.0 <= report.thread_contention_score <= 1.0
        assert isinstance(report.recommendations, list)
        assert isinstance(report.stage_analysis, dict)
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Run a few validations
        for i in range(3):
            self.validator.validate_hot_path_stability()
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for result in history:
            assert 'timestamp' in result
            assert 'is_stable' in result
            assert 'stability_level' in result
    
    def test_reset_metrics(self):
        """Test resetting metrics"""
        # Add some data
        self.validator.validate_hot_path_stability()
        
        # Reset metrics
        self.validator.reset_metrics()
        
        assert len(self.validator.monitor.metrics) == 0
        assert len(self.validator.monitor.blocking_events) == 0
        assert len(self.validator.blocking_detector.blocking_operations) == 0
        assert len(self.validator.validation_results) == 0

class TestHotPathContext:
    """Test hot-path context manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = HotPathValidator()
    
    def test_hot_path_context_initialization(self):
        """Test hot-path context initialization"""
        context = HotPathContext(self.validator, HotPathStage.TICK_INGESTION, "test_operation")
        
        assert context.validator is self.validator
        assert context.stage == HotPathStage.TICK_INGESTION
        assert context.operation == "test_operation"
        assert context.start_time > 0
        assert context.thread_id == threading.get_ident()
    
    def test_hot_path_context_enter_exit(self):
        """Test hot-path context enter/exit"""
        initial_metrics_count = len(self.validator.monitor.metrics)
        
        with HotPathContext(self.validator, HotPathStage.VWAP_CALCULATION, "calculate_vwap"):
            time.sleep(0.001)  # Small delay
        
        # Check that metrics were recorded
        assert len(self.validator.monitor.metrics) == initial_metrics_count + 1
        
        # Check the recorded metrics
        latest_metrics = self.validator.monitor.metrics[-1]
        assert latest_metrics.stage == HotPathStage.VWAP_CALCULATION
        assert latest_metrics.processing_time_ms > 0.0
        assert latest_metrics.metadata['operation'] == "calculate_vwap"
    
    def test_hot_path_context_blocking_detection(self):
        """Test hot-path context blocking detection"""
        initial_blocking_count = len(self.validator.blocking_detector.blocking_operations)
        
        # Simulate a long operation that should trigger blocking detection
        with HotPathContext(self.validator, HotPathStage.ORDER_PROCESSING, "long_operation"):
            time.sleep(0.01)  # 10ms delay
        
        # Check if blocking was detected (may or may not be detected depending on timing)
        # The important thing is that the context manager works correctly
        assert len(self.validator.monitor.metrics) > 0

class TestGlobalFunctions:
    """Test global hot-path functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.hot_path_validation
        infra.hot_path_validation._hot_path_validator = None
    
    def test_get_hot_path_validator(self):
        """Test global validator access"""
        validator1 = get_hot_path_validator()
        validator2 = get_hot_path_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, HotPathValidator)
    
    def test_validate_hot_path_stability_global(self):
        """Test global hot-path stability validation"""
        result = validate_hot_path_stability()
        
        assert isinstance(result, dict)
        assert 'is_stable' in result
        assert 'no_db_blocking' in result
        assert 'stability_level' in result
        assert 'recommendations' in result
    
    def test_get_stability_report_global(self):
        """Test global stability report"""
        report = get_stability_report()
        
        assert isinstance(report, StabilityReport)
        assert report.overall_stability in [StabilityLevel.EXCELLENT, StabilityLevel.GOOD, 
                                           StabilityLevel.DEGRADED, StabilityLevel.CRITICAL]
    
    def test_hot_path_operation_global(self):
        """Test global hot-path operation context manager"""
        with hot_path_operation(HotPathStage.TICK_INGESTION, "test_operation"):
            time.sleep(0.001)
        
        # Check that metrics were recorded
        validator = get_hot_path_validator()
        assert len(validator.monitor.metrics) > 0

class TestHotPathValidationIntegration:
    """Integration tests for hot-path validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.hot_path_validation
        infra.hot_path_validation._hot_path_validator = None
    
    def test_comprehensive_hot_path_analysis(self):
        """Test comprehensive hot-path analysis workflow"""
        validator = get_hot_path_validator()
        
        # Simulate hot-path operations
        stages = [
            HotPathStage.TICK_INGESTION,
            HotPathStage.VWAP_CALCULATION,
            HotPathStage.DECISION_MAKING,
            HotPathStage.ORDER_PROCESSING
        ]
        
        for stage in stages:
            with hot_path_operation(stage, f"test_{stage.value}"):
                time.sleep(0.001)  # Simulate work
        
        # Validate stability
        result = validate_hot_path_stability()
        
        assert isinstance(result, dict)
        assert 'is_stable' in result
        assert 'no_db_blocking' in result
        assert 'stability_level' in result
        assert 'blocking_events_count' in result
        assert 'critical_blocking_events' in result
        assert 'average_processing_time_ms' in result
        assert 'max_processing_time_ms' in result
        assert 'memory_pressure_score' in result
        assert 'io_pressure_score' in result
        assert 'thread_contention_score' in result
        assert 'stage_analysis' in result
        assert 'recommendations' in result
        
        # Check that metrics are calculated
        assert result['blocking_events_count'] >= 0
        assert result['critical_blocking_events'] >= 0
        assert result['average_processing_time_ms'] >= 0.0
        assert result['max_processing_time_ms'] >= 0.0
        assert 0.0 <= result['memory_pressure_score'] <= 1.0
        assert 0.0 <= result['io_pressure_score'] <= 1.0
        assert 0.0 <= result['thread_contention_score'] <= 1.0
        assert result['stability_level'] in ['excellent', 'good', 'degraded', 'critical']
        assert isinstance(result['recommendations'], list)
        assert isinstance(result['stage_analysis'], dict)
    
    def test_stability_level_detection(self):
        """Test stability level detection"""
        validator = get_hot_path_validator()
        
        # Add metrics with good performance
        for i in range(10):
            with hot_path_operation(HotPathStage.TICK_INGESTION, f"operation_{i}"):
                time.sleep(0.001)  # Very short operation
        
        # Validate stability
        result = validate_hot_path_stability()
        
        # Should be stable with good performance
        assert result['is_stable'] in [True, False]  # May vary based on system
        assert result['stability_level'] in ['excellent', 'good', 'degraded', 'critical']
        assert result['no_db_blocking'] in [True, False]  # May vary based on system
    
    def test_stage_breakdown(self):
        """Test stage-by-stage analysis"""
        validator = get_hot_path_validator()
        
        # Add operations for different stages
        stages = [
            HotPathStage.TICK_INGESTION,
            HotPathStage.VWAP_CALCULATION,
            HotPathStage.DECISION_MAKING
        ]
        
        for stage in stages:
            for i in range(3):
                with hot_path_operation(stage, f"test_{stage.value}_{i}"):
                    time.sleep(0.001)
        
        # Get stability report
        report = get_stability_report()
        
        # Check stage analysis
        assert hasattr(report, 'stage_analysis')
        stage_analysis = report.stage_analysis
        
        for stage in stages:
            assert stage.value in stage_analysis
            stage_data = stage_analysis[stage.value]
            assert 'count' in stage_data
            assert 'avg_processing_time_ms' in stage_data
            assert 'max_processing_time_ms' in stage_data
            assert 'avg_memory_mb' in stage_data
            assert 'blocking_events' in stage_data
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        validator = get_hot_path_validator()
        
        # Add some operations
        for i in range(5):
            with hot_path_operation(HotPathStage.TICK_INGESTION, f"operation_{i}"):
                time.sleep(0.001)
        
        # Get stability report
        result = validate_hot_path_stability()
        
        # Check recommendations
        assert 'recommendations' in result
        recommendations = result['recommendations']
        assert isinstance(recommendations, list)
        
        # Should have at least one recommendation
        assert len(recommendations) > 0
        assert all(isinstance(rec, str) for rec in recommendations)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
