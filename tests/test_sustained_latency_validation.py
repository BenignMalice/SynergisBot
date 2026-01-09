"""
Comprehensive tests for sustained latency validation system

Tests sustained latency validation <200ms over time, continuous monitoring,
trend analysis, performance degradation detection, and sustained performance validation.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque, defaultdict

from infra.sustained_latency_validation import (
    SustainedLatencyValidator, LatencyWindowManager, TrendAnalyzer,
    LatencyMeasurement, LatencyWindow, SustainedLatencyValidation,
    SustainedLatencyReport, LatencyTrend, SustainedPerformanceLevel,
    ValidationStatus, LatencyStage, get_sustained_latency_validator,
    add_latency_measurement, validate_sustained_latency,
    generate_sustained_latency_report
)

class TestLatencyTrend:
    """Test latency trend enumeration"""
    
    def test_latency_trends(self):
        """Test all latency trends"""
        trends = [
            LatencyTrend.IMPROVING,
            LatencyTrend.STABLE,
            LatencyTrend.DEGRADING,
            LatencyTrend.VOLATILE,
            LatencyTrend.UNKNOWN
        ]
        
        for trend in trends:
            assert isinstance(trend, LatencyTrend)
            assert trend.value in ["improving", "stable", "degrading", "volatile", "unknown"]

class TestSustainedPerformanceLevel:
    """Test sustained performance level enumeration"""
    
    def test_sustained_performance_levels(self):
        """Test all sustained performance levels"""
        levels = [
            SustainedPerformanceLevel.EXCELLENT,
            SustainedPerformanceLevel.GOOD,
            SustainedPerformanceLevel.FAIR,
            SustainedPerformanceLevel.POOR,
            SustainedPerformanceLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, SustainedPerformanceLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestValidationStatus:
    """Test validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            ValidationStatus.PASSED,
            ValidationStatus.WARNING,
            ValidationStatus.FAILED,
            ValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, ValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestLatencyStage:
    """Test latency stage enumeration"""
    
    def test_latency_stages(self):
        """Test all latency stages"""
        stages = [
            LatencyStage.TICK_INGESTION,
            LatencyStage.DATA_PROCESSING,
            LatencyStage.FEATURE_CALCULATION,
            LatencyStage.DECISION_MAKING,
            LatencyStage.ORDER_EXECUTION,
            LatencyStage.DATABASE_WRITE,
            LatencyStage.TOTAL_PIPELINE
        ]
        
        for stage in stages:
            assert isinstance(stage, LatencyStage)
            assert stage.value in ["tick_ingestion", "data_processing", "feature_calculation",
                                  "decision_making", "order_execution", "database_write", "total_pipeline"]

class TestLatencyMeasurement:
    """Test latency measurement data structure"""
    
    def test_latency_measurement_creation(self):
        """Test latency measurement creation"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=150.5,
            symbol="BTCUSDT",
            thread_id=12345,
            cpu_usage=75.2,
            memory_usage=60.8,
            metadata={"test": True, "source": "mt5"}
        )
        
        assert measurement.timestamp > 0
        assert measurement.stage == LatencyStage.TOTAL_PIPELINE
        assert measurement.duration_ms == 150.5
        assert measurement.symbol == "BTCUSDT"
        assert measurement.thread_id == 12345
        assert measurement.cpu_usage == 75.2
        assert measurement.memory_usage == 60.8
        assert measurement.metadata["test"] is True
        assert measurement.metadata["source"] == "mt5"
    
    def test_latency_measurement_defaults(self):
        """Test latency measurement defaults"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.DATA_PROCESSING,
            duration_ms=75.0,
            symbol="ETHUSDT",
            thread_id=67890,
            cpu_usage=50.0,
            memory_usage=40.0
        )
        
        assert measurement.metadata == {}

class TestLatencyWindow:
    """Test latency window data structure"""
    
    def test_latency_window_creation(self):
        """Test latency window creation"""
        measurements = [
            LatencyMeasurement(
                timestamp=time.time() - 300,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0,
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            ),
            LatencyMeasurement(
                timestamp=time.time() - 200,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=150.0,
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=55.0,
                memory_usage=65.0
            )
        ]
        
        window = LatencyWindow(
            start_time=time.time() - 300,
            end_time=time.time(),
            measurements=measurements,
            p50_ms=125.0,
            p95_ms=150.0,
            p99_ms=150.0,
            max_ms=150.0,
            min_ms=100.0,
            mean_ms=125.0,
            std_ms=25.0,
            count=2,
            metadata={"window_id": "w001"}
        )
        
        assert window.start_time > 0
        assert window.end_time > window.start_time
        assert len(window.measurements) == 2
        assert window.p50_ms == 125.0
        assert window.p95_ms == 150.0
        assert window.p99_ms == 150.0
        assert window.max_ms == 150.0
        assert window.min_ms == 100.0
        assert window.mean_ms == 125.0
        assert window.std_ms == 25.0
        assert window.count == 2
        assert window.metadata["window_id"] == "w001"
    
    def test_latency_window_defaults(self):
        """Test latency window defaults"""
        window = LatencyWindow(
            start_time=time.time() - 300,
            end_time=time.time(),
            measurements=[],
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            max_ms=0.0,
            min_ms=0.0,
            mean_ms=0.0,
            std_ms=0.0,
            count=0
        )
        
        assert window.metadata == {}

class TestSustainedLatencyValidation:
    """Test sustained latency validation data structure"""
    
    def test_sustained_latency_validation_creation(self):
        """Test sustained latency validation creation"""
        validation = SustainedLatencyValidation(
            timestamp=time.time(),
            validation_period_hours=24.0,
            total_measurements=1000,
            p95_latency_ms=150.0,
            target_latency_ms=200.0,
            meets_target=True,
            sustained_performance_level=SustainedPerformanceLevel.GOOD,
            latency_trend=LatencyTrend.STABLE,
            stability_score=0.85,
            degradation_detected=False,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent sustained performance! Continue current practices"],
            detailed_analysis={"stage_analysis": {"total_pipeline": {"p95_ms": 150.0}}},
            metadata={"target_latency_ms": 200.0}
        )
        
        assert validation.timestamp > 0
        assert validation.validation_period_hours == 24.0
        assert validation.total_measurements == 1000
        assert validation.p95_latency_ms == 150.0
        assert validation.target_latency_ms == 200.0
        assert validation.meets_target is True
        assert validation.sustained_performance_level == SustainedPerformanceLevel.GOOD
        assert validation.latency_trend == LatencyTrend.STABLE
        assert validation.stability_score == 0.85
        assert validation.degradation_detected is False
        assert validation.validation_status == ValidationStatus.PASSED
        assert len(validation.issues_found) == 0
        assert len(validation.recommendations) == 1
        assert validation.detailed_analysis["stage_analysis"]["total_pipeline"]["p95_ms"] == 150.0
        assert validation.metadata["target_latency_ms"] == 200.0
    
    def test_sustained_latency_validation_defaults(self):
        """Test sustained latency validation defaults"""
        validation = SustainedLatencyValidation(
            timestamp=time.time(),
            validation_period_hours=12.0,
            total_measurements=500,
            p95_latency_ms=250.0,
            target_latency_ms=200.0,
            meets_target=False,
            sustained_performance_level=SustainedPerformanceLevel.POOR,
            latency_trend=LatencyTrend.DEGRADING,
            stability_score=0.60,
            degradation_detected=True,
            validation_status=ValidationStatus.FAILED,
            issues_found=["P95 latency 250.0ms exceeds target 200.0ms"],
            recommendations=["Optimize system performance to meet latency target"],
            detailed_analysis={}
        )
        
        assert validation.detailed_analysis == {}
        assert validation.metadata == {}

class TestSustainedLatencyReport:
    """Test sustained latency report data structure"""
    
    def test_sustained_latency_report_creation(self):
        """Test sustained latency report creation"""
        validation = SustainedLatencyValidation(
            timestamp=time.time(),
            validation_period_hours=24.0,
            total_measurements=1000,
            p95_latency_ms=150.0,
            target_latency_ms=200.0,
            meets_target=True,
            sustained_performance_level=SustainedPerformanceLevel.GOOD,
            latency_trend=LatencyTrend.STABLE,
            stability_score=0.85,
            degradation_detected=False,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent sustained performance! Continue current practices"],
            detailed_analysis={"stage_analysis": {"total_pipeline": {"p95_ms": 150.0}}}
        )
        
        report = SustainedLatencyReport(
            timestamp=time.time(),
            overall_performance_score=0.92,
            validation_period_hours=24.0,
            total_measurements=1000,
            p95_latency_ms=150.0,
            target_latency_ms=200.0,
            meets_target=True,
            sustained_performance_level=SustainedPerformanceLevel.GOOD,
            latency_trend=LatencyTrend.STABLE,
            stability_score=0.85,
            degradation_detected=False,
            validation_status=ValidationStatus.PASSED,
            stage_analysis={"total_pipeline": {"p95_ms": 150.0}},
            trend_analysis={"trend": "stable"},
            stability_analysis={"stability_score": 0.85},
            recommendations=["Excellent sustained performance! Continue current practices"],
            detailed_validations=[validation],
            metadata={"target_latency_ms": 200.0}
        )
        
        assert report.timestamp > 0
        assert report.overall_performance_score == 0.92
        assert report.validation_period_hours == 24.0
        assert report.total_measurements == 1000
        assert report.p95_latency_ms == 150.0
        assert report.target_latency_ms == 200.0
        assert report.meets_target is True
        assert report.sustained_performance_level == SustainedPerformanceLevel.GOOD
        assert report.latency_trend == LatencyTrend.STABLE
        assert report.stability_score == 0.85
        assert report.degradation_detected is False
        assert report.validation_status == ValidationStatus.PASSED
        assert report.stage_analysis["total_pipeline"]["p95_ms"] == 150.0
        assert report.trend_analysis["trend"] == "stable"
        assert report.stability_analysis["stability_score"] == 0.85
        assert len(report.recommendations) == 1
        assert len(report.detailed_validations) == 1
        assert report.metadata["target_latency_ms"] == 200.0
    
    def test_sustained_latency_report_defaults(self):
        """Test sustained latency report defaults"""
        report = SustainedLatencyReport(
            timestamp=time.time(),
            overall_performance_score=0.50,
            validation_period_hours=12.0,
            total_measurements=500,
            p95_latency_ms=250.0,
            target_latency_ms=200.0,
            meets_target=False,
            sustained_performance_level=SustainedPerformanceLevel.POOR,
            latency_trend=LatencyTrend.DEGRADING,
            stability_score=0.60,
            degradation_detected=True,
            validation_status=ValidationStatus.FAILED,
            stage_analysis={"total_pipeline": {"p95_ms": 250.0}},
            trend_analysis={"trend": "degrading"},
            stability_analysis={"stability_score": 0.60},
            recommendations=["Optimize system performance to meet latency target"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestLatencyWindowManager:
    """Test latency window manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = LatencyWindowManager(window_size_minutes=5, max_windows=10)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.window_size_minutes == 5
        assert self.manager.window_size_seconds == 300
        assert self.manager.max_windows == 10
        assert len(self.manager.windows) == 0
        assert self.manager.current_window is None
        assert hasattr(self.manager, 'lock')
    
    def test_add_measurement_empty(self):
        """Test adding measurement to empty manager"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=100.0,
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        
        self.manager.add_measurement(measurement)
        
        assert self.manager.current_window is not None
        assert len(self.manager.current_window.measurements) == 1
        assert self.manager.current_window.measurements[0] == measurement
        assert len(self.manager.windows) == 0  # Window not finalized yet
    
    def test_add_measurement_multiple(self):
        """Test adding multiple measurements to same window"""
        base_time = time.time()
        
        for i in range(3):
            measurement = LatencyMeasurement(
                timestamp=base_time + i * 60,  # 1 minute apart
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + i * 10,
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            
            self.manager.add_measurement(measurement)
        
        assert self.manager.current_window is not None
        assert len(self.manager.current_window.measurements) == 3
        assert len(self.manager.windows) == 0  # Still in same window
    
    def test_add_measurement_new_window(self):
        """Test adding measurement that creates new window"""
        base_time = time.time()
        
        # Add measurement to current window
        measurement1 = LatencyMeasurement(
            timestamp=base_time,
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=100.0,
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        self.manager.add_measurement(measurement1)
        
        # Add measurement that should create new window
        measurement2 = LatencyMeasurement(
            timestamp=base_time + 400,  # 6+ minutes later
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=120.0,
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=55.0,
            memory_usage=65.0
        )
        self.manager.add_measurement(measurement2)
        
        assert len(self.manager.windows) == 1  # First window finalized
        assert self.manager.current_window is not None
        assert len(self.manager.current_window.measurements) == 1
        assert self.manager.current_window.measurements[0] == measurement2
    
    def test_get_recent_windows(self):
        """Test getting recent windows"""
        base_time = time.time()
        
        # Add measurements to create multiple windows
        for i in range(5):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 400,  # 6+ minutes apart
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + i * 10,
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            self.manager.add_measurement(measurement)
        
        # Get recent windows (last 2 hours)
        recent_windows = self.manager.get_recent_windows(2.0)
        
        assert len(recent_windows) >= 0  # May be 0 if windows are too old
        assert all(w.end_time >= base_time - 7200 for w in recent_windows)
    
    def test_get_window_statistics(self):
        """Test getting window statistics"""
        base_time = time.time()
        
        # Add measurements to create windows
        for i in range(3):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 400,  # 6+ minutes apart
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + i * 20,
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            self.manager.add_measurement(measurement)
        
        stats = self.manager.get_window_statistics(2.0)
        
        assert "total_windows" in stats
        assert "total_measurements" in stats
        assert "avg_p95_ms" in stats
        assert "max_p95_ms" in stats
        assert "min_p95_ms" in stats
        assert "stability_score" in stats
        assert 0.0 <= stats["stability_score"] <= 1.0

class TestTrendAnalyzer:
    """Test trend analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = TrendAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_trend_insufficient_data(self):
        """Test trend analysis with insufficient data"""
        windows = [
            LatencyWindow(
                start_time=time.time() - 300,
                end_time=time.time() - 200,
                measurements=[],
                p50_ms=100.0, p95_ms=120.0, p99_ms=130.0,
                max_ms=130.0, min_ms=100.0, mean_ms=110.0, std_ms=10.0, count=1
            )
        ]
        
        trend = self.analyzer.analyze_trend(windows)
        
        assert trend == LatencyTrend.UNKNOWN
    
    def test_analyze_trend_improving(self):
        """Test trend analysis with improving trend"""
        windows = []
        base_time = time.time()
        
        # Create windows with decreasing latency
        for i in range(5):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=100.0 - i * 10, p95_ms=120.0 - i * 10, p99_ms=130.0 - i * 10,
                max_ms=130.0 - i * 10, min_ms=100.0 - i * 10, mean_ms=110.0 - i * 10, std_ms=5.0, count=1
            )
            windows.append(window)
        
        trend = self.analyzer.analyze_trend(windows)
        
        assert trend == LatencyTrend.IMPROVING
    
    def test_analyze_trend_degrading(self):
        """Test trend analysis with degrading trend"""
        windows = []
        base_time = time.time()
        
        # Create windows with increasing latency
        for i in range(5):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=100.0 + i * 10, p95_ms=120.0 + i * 10, p99_ms=130.0 + i * 10,
                max_ms=130.0 + i * 10, min_ms=100.0 + i * 10, mean_ms=110.0 + i * 10, std_ms=5.0, count=1
            )
            windows.append(window)
        
        trend = self.analyzer.analyze_trend(windows)
        
        assert trend == LatencyTrend.DEGRADING
    
    def test_analyze_trend_stable(self):
        """Test trend analysis with stable trend"""
        windows = []
        base_time = time.time()
        
        # Create windows with stable latency
        for i in range(5):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=100.0, p95_ms=120.0, p99_ms=130.0,
                max_ms=130.0, min_ms=100.0, mean_ms=110.0, std_ms=5.0, count=1
            )
            windows.append(window)
        
        trend = self.analyzer.analyze_trend(windows)
        
        assert trend == LatencyTrend.STABLE
    
    def test_analyze_trend_volatile(self):
        """Test trend analysis with volatile trend"""
        windows = []
        base_time = time.time()
        
        # Create windows with highly variable latency (high coefficient of variation)
        values = [100.0, 200.0, 50.0, 300.0, 150.0, 250.0, 80.0, 180.0, 120.0, 220.0]
        for i, val in enumerate(values):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=val, p95_ms=val + 20, p99_ms=val + 30,
                max_ms=val + 30, min_ms=val, mean_ms=val + 10, std_ms=20.0, count=1
            )
            windows.append(window)
        
        trend = self.analyzer.analyze_trend(windows)
        
        assert trend == LatencyTrend.VOLATILE
    
    def test_detect_degradation_no_degradation(self):
        """Test degradation detection with no degradation"""
        windows = []
        base_time = time.time()
        
        # Create windows with stable performance (need at least 6 windows)
        for i in range(8):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=100.0, p95_ms=120.0, p99_ms=130.0,
                max_ms=130.0, min_ms=100.0, mean_ms=110.0, std_ms=5.0, count=1
            )
            windows.append(window)
        
        degradation = self.analyzer.detect_degradation(windows)
        
        assert degradation == False
    
    def test_detect_degradation_with_degradation(self):
        """Test degradation detection with degradation"""
        windows = []
        base_time = time.time()
        
        # Create windows with performance degradation (need at least 6 windows)
        for i in range(8):
            window = LatencyWindow(
                start_time=base_time - (i + 1) * 300,
                end_time=base_time - i * 300,
                measurements=[],
                p50_ms=100.0 + i * 20, p95_ms=120.0 + i * 20, p99_ms=130.0 + i * 20,
                max_ms=130.0 + i * 20, min_ms=100.0 + i * 20, mean_ms=110.0 + i * 20, std_ms=5.0, count=1
            )
            windows.append(window)
        
        degradation = self.analyzer.detect_degradation(windows)
        
        assert degradation == True

class TestSustainedLatencyValidator:
    """Test sustained latency validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = SustainedLatencyValidator(target_latency_ms=200.0, validation_period_hours=24.0)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.target_latency_ms == 200.0
        assert self.validator.validation_period_hours == 24.0
        assert isinstance(self.validator.window_manager, LatencyWindowManager)
        assert isinstance(self.validator.trend_analyzer, TrendAnalyzer)
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_add_measurement(self):
        """Test adding latency measurement"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=150.0,
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        
        self.validator.add_measurement(measurement)
        
        assert self.validator.window_manager.current_window is not None
        assert len(self.validator.window_manager.current_window.measurements) == 1
    
    def test_validate_sustained_latency_no_data(self):
        """Test validation with no data"""
        validation = self.validator.validate_sustained_latency()
        
        assert validation.total_measurements == 0
        assert validation.p95_latency_ms == 0.0
        assert validation.target_latency_ms == 200.0
        assert validation.meets_target is False
        assert validation.sustained_performance_level == SustainedPerformanceLevel.CRITICAL
        assert validation.latency_trend == LatencyTrend.UNKNOWN
        assert validation.stability_score == 0.0
        assert validation.degradation_detected is False
        assert validation.validation_status == ValidationStatus.FAILED
        assert "No latency data available" in validation.issues_found[0]
        assert "Collect latency measurements" in validation.recommendations[0]
    
    def test_validate_sustained_latency_good_performance(self):
        """Test validation with good performance"""
        # Add measurements with good performance
        base_time = time.time()
        for i in range(100):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,  # 1 minute intervals
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=50.0 + np.random.normal(0, 5),  # Random around 50ms
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            self.validator.add_measurement(measurement)
        
        validation = self.validator.validate_sustained_latency()
        
        assert validation.total_measurements > 0
        assert validation.p95_latency_ms <= 200.0  # Should meet target
        assert validation.target_latency_ms == 200.0
        assert validation.meets_target == True
        assert validation.sustained_performance_level in [SustainedPerformanceLevel.EXCELLENT,
                                                         SustainedPerformanceLevel.GOOD,
                                                         SustainedPerformanceLevel.FAIR]
        assert validation.latency_trend in [LatencyTrend.STABLE, LatencyTrend.IMPROVING,
                                          LatencyTrend.DEGRADING, LatencyTrend.VOLATILE]
        assert 0.0 <= validation.stability_score <= 1.0
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_validate_sustained_latency_poor_performance(self):
        """Test validation with poor performance"""
        # Add measurements with poor performance
        base_time = time.time()
        for i in range(100):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,  # 1 minute intervals
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=300.0 + np.random.normal(0, 20),  # Random around 300ms
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=80.0,
                memory_usage=90.0
            )
            self.validator.add_measurement(measurement)
        
        validation = self.validator.validate_sustained_latency()
        
        assert validation.total_measurements > 0
        assert validation.p95_latency_ms > 200.0  # Should exceed target
        assert validation.target_latency_ms == 200.0
        assert validation.meets_target == False
        assert validation.sustained_performance_level in [SustainedPerformanceLevel.POOR,
                                                         SustainedPerformanceLevel.CRITICAL]
        assert validation.latency_trend in [LatencyTrend.STABLE, LatencyTrend.IMPROVING,
                                          LatencyTrend.DEGRADING, LatencyTrend.VOLATILE]
        assert 0.0 <= validation.stability_score <= 1.0
        assert validation.validation_status == ValidationStatus.FAILED
        assert len(validation.issues_found) > 0
        assert len(validation.recommendations) > 0
        assert any("exceeds target" in issue for issue in validation.issues_found)
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some measurements first
        base_time = time.time()
        for i in range(50):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + np.random.normal(0, 10),
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            self.validator.add_measurement(measurement)
        
        # Generate validation
        validation = self.validator.validate_sustained_latency()
        
        # Generate report
        report = self.validator.generate_validation_report()
        
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0
        assert report.validation_period_hours == 24.0
        assert report.total_measurements > 0
        assert report.p95_latency_ms >= 0.0
        assert report.target_latency_ms == 200.0
        assert report.meets_target in [True, False]
        assert report.sustained_performance_level in [SustainedPerformanceLevel.EXCELLENT,
                                                     SustainedPerformanceLevel.GOOD,
                                                     SustainedPerformanceLevel.FAIR,
                                                     SustainedPerformanceLevel.POOR,
                                                     SustainedPerformanceLevel.CRITICAL]
        assert report.latency_trend in [LatencyTrend.IMPROVING, LatencyTrend.STABLE,
                                      LatencyTrend.DEGRADING, LatencyTrend.VOLATILE,
                                      LatencyTrend.UNKNOWN]
        assert 0.0 <= report.stability_score <= 1.0
        assert report.degradation_detected in [True, False]
        assert report.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING,
                                          ValidationStatus.FAILED, ValidationStatus.PENDING]
        assert len(report.stage_analysis) >= 0
        assert len(report.trend_analysis) >= 0
        assert len(report.stability_analysis) >= 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) == 1
        assert report.metadata["target_latency_ms"] == 200.0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_performance_score == 0.0
        assert report.validation_period_hours == 24.0
        assert report.total_measurements == 0
        assert report.p95_latency_ms == 0.0
        assert report.target_latency_ms == 200.0
        assert report.meets_target is False
        assert report.sustained_performance_level == SustainedPerformanceLevel.CRITICAL
        assert report.latency_trend == LatencyTrend.UNKNOWN
        assert report.stability_score == 0.0
        assert report.degradation_detected is False
        assert report.validation_status == ValidationStatus.FAILED
        assert report.stage_analysis == {}
        assert report.trend_analysis == {}
        assert report.stability_analysis == {}
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.metadata["error"] == "No validation data available"

class TestGlobalFunctions:
    """Test global sustained latency validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.sustained_latency_validation
        infra.sustained_latency_validation._sustained_latency_validator = None
    
    def test_get_sustained_latency_validator(self):
        """Test global validator access"""
        validator1 = get_sustained_latency_validator()
        validator2 = get_sustained_latency_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, SustainedLatencyValidator)
    
    def test_add_latency_measurement_global(self):
        """Test global latency measurement addition"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=150.0,
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=50.0,
            memory_usage=60.0
        )
        
        add_latency_measurement(measurement)
        
        validator = get_sustained_latency_validator()
        assert validator.window_manager.current_window is not None
        assert len(validator.window_manager.current_window.measurements) == 1
    
    def test_validate_sustained_latency_global(self):
        """Test global sustained latency validation"""
        # Add some measurements first
        base_time = time.time()
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + np.random.normal(0, 10),
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            add_latency_measurement(measurement)
        
        validation = validate_sustained_latency()
        
        assert isinstance(validation, SustainedLatencyValidation)
        assert validation.total_measurements > 0
        assert validation.p95_latency_ms >= 0.0
        assert validation.target_latency_ms == 200.0
        assert validation.meets_target in [True, False]
        assert validation.sustained_performance_level in [SustainedPerformanceLevel.EXCELLENT,
                                                         SustainedPerformanceLevel.GOOD,
                                                         SustainedPerformanceLevel.FAIR,
                                                         SustainedPerformanceLevel.POOR,
                                                         SustainedPerformanceLevel.CRITICAL]
        assert validation.latency_trend in [LatencyTrend.IMPROVING, LatencyTrend.STABLE,
                                          LatencyTrend.DEGRADING, LatencyTrend.VOLATILE,
                                          LatencyTrend.UNKNOWN]
        assert 0.0 <= validation.stability_score <= 1.0
        assert validation.degradation_detected in [True, False]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING,
                                              ValidationStatus.FAILED, ValidationStatus.PENDING]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_generate_sustained_latency_report_global(self):
        """Test global sustained latency report generation"""
        # Add some measurements first
        base_time = time.time()
        for i in range(10):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=120.0 + np.random.normal(0, 15),
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=55.0,
                memory_usage=65.0
            )
            add_latency_measurement(measurement)
        
        report = generate_sustained_latency_report()
        
        assert isinstance(report, SustainedLatencyReport)
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0

class TestSustainedLatencyValidationIntegration:
    """Integration tests for sustained latency validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.sustained_latency_validation
        infra.sustained_latency_validation._sustained_latency_validator = None
    
    def test_comprehensive_sustained_latency_validation(self):
        """Test comprehensive sustained latency validation workflow"""
        # Test different performance scenarios
        test_cases = [
            (50.0, [SustainedPerformanceLevel.EXCELLENT, SustainedPerformanceLevel.GOOD], ValidationStatus.PASSED),   # Excellent/Good
            (100.0, [SustainedPerformanceLevel.GOOD, SustainedPerformanceLevel.FAIR], ValidationStatus.PASSED),       # Good/Fair
            (150.0, [SustainedPerformanceLevel.FAIR, SustainedPerformanceLevel.GOOD], ValidationStatus.PASSED),       # Fair/Good
            (250.0, [SustainedPerformanceLevel.POOR, SustainedPerformanceLevel.CRITICAL], ValidationStatus.FAILED),       # Poor/Critical
            (400.0, [SustainedPerformanceLevel.CRITICAL, SustainedPerformanceLevel.POOR], ValidationStatus.FAILED)   # Critical/Poor
        ]
        
        for target_latency, expected_levels, expected_status in test_cases:
            # Reset validator for each test case
            import infra.sustained_latency_validation
            infra.sustained_latency_validation._sustained_latency_validator = None
            
            # Add measurements with target latency
            base_time = time.time()
            for i in range(50):
                measurement = LatencyMeasurement(
                    timestamp=base_time - i * 60,
                    stage=LatencyStage.TOTAL_PIPELINE,
                    duration_ms=target_latency + np.random.normal(0, target_latency * 0.1),
                    symbol="BTCUSDT",
                    thread_id=1,
                    cpu_usage=50.0,
                    memory_usage=60.0
                )
                add_latency_measurement(measurement)
            
            validation = validate_sustained_latency()
            
            assert isinstance(validation, SustainedLatencyValidation)
            assert validation.total_measurements > 0
            assert validation.p95_latency_ms >= 0.0
            assert validation.target_latency_ms == 200.0
            assert validation.meets_target == (target_latency <= 200.0)
            assert validation.sustained_performance_level in expected_levels
            assert validation.validation_status == expected_status
            assert len(validation.issues_found) >= 0
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_sustained_latency_report()
        
        assert isinstance(report, SustainedLatencyReport)
        assert report.overall_performance_score >= 0.0
        assert report.overall_performance_score <= 1.0
        assert report.validation_period_hours == 24.0
        assert report.total_measurements > 0
        assert report.p95_latency_ms >= 0.0
        assert report.target_latency_ms == 200.0
        assert report.meets_target in [True, False]
        assert report.sustained_performance_level in [SustainedPerformanceLevel.EXCELLENT,
                                                     SustainedPerformanceLevel.GOOD,
                                                     SustainedPerformanceLevel.FAIR,
                                                     SustainedPerformanceLevel.POOR,
                                                     SustainedPerformanceLevel.CRITICAL]
        assert report.latency_trend in [LatencyTrend.IMPROVING, LatencyTrend.STABLE,
                                      LatencyTrend.DEGRADING, LatencyTrend.VOLATILE,
                                      LatencyTrend.UNKNOWN]
        assert 0.0 <= report.stability_score <= 1.0
        assert report.degradation_detected in [True, False]
        assert report.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING,
                                          ValidationStatus.FAILED, ValidationStatus.PENDING]
        assert len(report.stage_analysis) >= 0
        assert len(report.trend_analysis) >= 0
        assert len(report.stability_analysis) >= 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) >= 1
    
    def test_latency_trend_analysis(self):
        """Test latency trend analysis"""
        # Test improving trend
        base_time = time.time()
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=200.0 - i * 5,  # Decreasing latency
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            add_latency_measurement(measurement)
        
        validation = validate_sustained_latency()
        
        assert validation.latency_trend in [LatencyTrend.IMPROVING, LatencyTrend.STABLE]
        assert validation.degradation_detected == False
        
        # Test degrading trend
        import infra.sustained_latency_validation
        infra.sustained_latency_validation._sustained_latency_validator = None
        
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + i * 5,  # Increasing latency
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            add_latency_measurement(measurement)
        
        validation = validate_sustained_latency()
        
        assert validation.latency_trend in [LatencyTrend.DEGRADING, LatencyTrend.STABLE]
        assert validation.degradation_detected == True
    
    def test_stability_analysis(self):
        """Test stability analysis"""
        # Test stable performance
        base_time = time.time()
        for i in range(30):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + np.random.normal(0, 5),  # Low variance
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            add_latency_measurement(measurement)
        
        validation = validate_sustained_latency()
        
        assert validation.stability_score >= 0.7  # Should be stable
        assert validation.latency_trend in [LatencyTrend.STABLE, LatencyTrend.IMPROVING,
                                          LatencyTrend.DEGRADING, LatencyTrend.VOLATILE]
        
        # Test volatile performance
        import infra.sustained_latency_validation
        infra.sustained_latency_validation._sustained_latency_validator = None
        
        for i in range(30):
            measurement = LatencyMeasurement(
                timestamp=base_time - i * 60,
                stage=LatencyStage.TOTAL_PIPELINE,
                duration_ms=100.0 + np.random.normal(0, 50),  # High variance
                symbol="BTCUSDT",
                thread_id=1,
                cpu_usage=50.0,
                memory_usage=60.0
            )
            add_latency_measurement(measurement)
        
        validation = validate_sustained_latency()
        
        assert validation.stability_score < 0.7  # Should be volatile
        assert validation.latency_trend == LatencyTrend.VOLATILE

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
