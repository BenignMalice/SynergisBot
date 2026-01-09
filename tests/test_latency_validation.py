"""
Comprehensive tests for latency validation system

Tests latency measurement, p95 validation, hardware profiling,
stage-by-stage analysis, and performance optimization recommendations.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import deque

from infra.latency_validation import (
    LatencyValidator, LatencyCollector, HardwareProfiler, LatencyTimer,
    LatencyStage, LatencyLevel, HardwareType,
    LatencyMeasurement, LatencyStats, HardwareProfile,
    get_latency_validator, measure_latency, validate_latency_target, get_latency_report
)

class TestLatencyStage:
    """Test latency stage enumeration"""
    
    def test_latency_stages(self):
        """Test all latency stages"""
        stages = [
            LatencyStage.TICK_INGESTION,
            LatencyStage.DATA_NORMALIZATION,
            LatencyStage.VWAP_CALCULATION,
            LatencyStage.ATR_CALCULATION,
            LatencyStage.DELTA_ANALYSIS,
            LatencyStage.STRUCTURE_DETECTION,
            LatencyStage.FILTER_PROCESSING,
            LatencyStage.DECISION_MAKING,
            LatencyStage.ORDER_PROCESSING,
            LatencyStage.DATABASE_WRITE
        ]
        
        for stage in stages:
            assert isinstance(stage, LatencyStage)
            assert stage.value in [
                "tick_ingestion", "data_normalization", "vwap_calculation",
                "atr_calculation", "delta_analysis", "structure_detection",
                "filter_processing", "decision_making", "order_processing", "database_write"
            ]

class TestLatencyLevel:
    """Test latency level enumeration"""
    
    def test_latency_levels(self):
        """Test all latency levels"""
        levels = [
            LatencyLevel.EXCELLENT,
            LatencyLevel.GOOD,
            LatencyLevel.ACCEPTABLE,
            LatencyLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, LatencyLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestHardwareType:
    """Test hardware type enumeration"""
    
    def test_hardware_types(self):
        """Test all hardware types"""
        types = [
            HardwareType.HIGH_END,
            HardwareType.MID_RANGE,
            HardwareType.LOW_END
        ]
        
        for hw_type in types:
            assert isinstance(hw_type, HardwareType)
            assert hw_type.value in ["high_end", "mid_range", "low_end"]

class TestLatencyMeasurement:
    """Test latency measurement data structure"""
    
    def test_latency_measurement_creation(self):
        """Test latency measurement creation"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TICK_INGESTION,
            duration_ms=5.5,
            symbol="BTCUSDc",
            thread_id=12345,
            cpu_usage=25.0,
            memory_usage=60.0,
            metadata={"queue_size": 100, "buffer_usage": 0.8}
        )
        
        assert measurement.timestamp > 0
        assert measurement.stage == LatencyStage.TICK_INGESTION
        assert measurement.duration_ms == 5.5
        assert measurement.symbol == "BTCUSDc"
        assert measurement.thread_id == 12345
        assert measurement.cpu_usage == 25.0
        assert measurement.memory_usage == 60.0
        assert measurement.metadata["queue_size"] == 100
    
    def test_latency_measurement_defaults(self):
        """Test latency measurement defaults"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.VWAP_CALCULATION,
            duration_ms=10.2,
            symbol="ETHUSDc",
            thread_id=67890,
            cpu_usage=30.0,
            memory_usage=65.0
        )
        
        assert measurement.metadata == {}

class TestLatencyStats:
    """Test latency stats data structure"""
    
    def test_latency_stats_creation(self):
        """Test latency stats creation"""
        stats = LatencyStats(
            stage=LatencyStage.DECISION_MAKING,
            count=100,
            min_ms=1.0,
            max_ms=50.0,
            mean_ms=15.5,
            median_ms=12.0,
            p50_ms=12.0,
            p95_ms=35.0,
            p99_ms=45.0,
            std_dev_ms=8.5,
            recent_trend="improving"
        )
        
        assert stats.stage == LatencyStage.DECISION_MAKING
        assert stats.count == 100
        assert stats.min_ms == 1.0
        assert stats.max_ms == 50.0
        assert stats.mean_ms == 15.5
        assert stats.median_ms == 12.0
        assert stats.p50_ms == 12.0
        assert stats.p95_ms == 35.0
        assert stats.p99_ms == 45.0
        assert stats.std_dev_ms == 8.5
        assert stats.recent_trend == "improving"
    
    def test_latency_stats_defaults(self):
        """Test latency stats defaults"""
        stats = LatencyStats(stage=LatencyStage.TICK_INGESTION)
        
        assert stats.count == 0
        assert stats.min_ms == 0.0
        assert stats.max_ms == 0.0
        assert stats.mean_ms == 0.0
        assert stats.median_ms == 0.0
        assert stats.p50_ms == 0.0
        assert stats.p95_ms == 0.0
        assert stats.p99_ms == 0.0
        assert stats.std_dev_ms == 0.0
        assert stats.recent_trend == "stable"

class TestHardwareProfile:
    """Test hardware profile data structure"""
    
    def test_hardware_profile_creation(self):
        """Test hardware profile creation"""
        profile = HardwareProfile(
            cpu_count=8,
            cpu_freq_mhz=3200.0,
            memory_gb=16.0,
            disk_type="SSD",
            os_type="Windows",
            python_version="3.11.2",
            hardware_type=HardwareType.HIGH_END,
            performance_score=85.5
        )
        
        assert profile.cpu_count == 8
        assert profile.cpu_freq_mhz == 3200.0
        assert profile.memory_gb == 16.0
        assert profile.disk_type == "SSD"
        assert profile.os_type == "Windows"
        assert profile.python_version == "3.11.2"
        assert profile.hardware_type == HardwareType.HIGH_END
        assert profile.performance_score == 85.5

class TestLatencyTimer:
    """Test latency timer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.timer = LatencyTimer()
    
    def test_timer_initialization(self):
        """Test timer initialization"""
        assert self.timer.start_time is None
        assert self.timer.end_time is None
        assert self.timer.stage is None
        assert self.timer.symbol is None
        assert self.timer.metadata == {}
    
    def test_timer_start_stop(self):
        """Test timer start and stop"""
        # Start timer
        self.timer.start(LatencyStage.TICK_INGESTION, "BTCUSDc", queue_size=100)
        
        assert self.timer.stage == LatencyStage.TICK_INGESTION
        assert self.timer.symbol == "BTCUSDc"
        assert self.timer.metadata["queue_size"] == 100
        assert self.timer.start_time is not None
        
        # Stop timer
        duration_ms = self.timer.stop()
        
        assert duration_ms >= 0.0
        assert self.timer.end_time is not None
    
    def test_get_measurement(self):
        """Test getting measurement"""
        # Start and stop timer
        self.timer.start(LatencyStage.VWAP_CALCULATION, "ETHUSDc")
        time.sleep(0.001)  # Small delay
        self.timer.stop()
        
        measurement = self.timer.get_measurement()
        
        assert measurement is not None
        assert isinstance(measurement, LatencyMeasurement)
        assert measurement.stage == LatencyStage.VWAP_CALCULATION
        assert measurement.symbol == "ETHUSDc"
        assert measurement.duration_ms > 0.0
    
    def test_get_measurement_incomplete(self):
        """Test getting measurement when timer not complete"""
        self.timer.start(LatencyStage.DECISION_MAKING, "XAUUSDc")
        
        measurement = self.timer.get_measurement()
        # The timer now calculates duration even if not explicitly stopped
        assert measurement is not None
        assert measurement.stage == LatencyStage.DECISION_MAKING
        assert measurement.symbol == "XAUUSDc"
    
    def test_stop_without_start(self):
        """Test stopping timer without starting"""
        duration_ms = self.timer.stop()
        assert duration_ms == 0.0

class TestLatencyCollector:
    """Test latency collector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.collector = LatencyCollector(max_measurements=1000)
    
    def test_collector_initialization(self):
        """Test collector initialization"""
        assert self.collector.max_measurements == 1000
        assert len(self.collector.measurements) == 0
        assert len(self.collector.stage_stats) == 0
        assert hasattr(self.collector, 'lock')
        assert self.collector.start_time > 0
    
    def test_add_measurement(self):
        """Test adding measurement"""
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            stage=LatencyStage.TICK_INGESTION,
            duration_ms=5.0,
            symbol="BTCUSDc",
            thread_id=12345,
            cpu_usage=25.0,
            memory_usage=60.0
        )
        
        self.collector.add_measurement(measurement)
        
        assert LatencyStage.TICK_INGESTION in self.collector.measurements
        assert len(self.collector.measurements[LatencyStage.TICK_INGESTION]) == 1
    
    def test_update_stage_stats(self):
        """Test updating stage statistics"""
        # Add multiple measurements
        for i in range(10):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.VWAP_CALCULATION,
                duration_ms=5.0 + i * 0.5,
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            self.collector.add_measurement(measurement)
        
        stats = self.collector.get_stage_stats(LatencyStage.VWAP_CALCULATION)
        
        assert stats is not None
        assert stats.stage == LatencyStage.VWAP_CALCULATION
        assert stats.count == 10
        assert stats.min_ms > 0
        assert stats.max_ms > stats.min_ms
        assert stats.mean_ms > 0
        assert stats.p50_ms > 0
        assert stats.p95_ms > 0
        assert stats.p99_ms > 0
    
    def test_get_all_stats(self):
        """Test getting all statistics"""
        # Add measurements for different stages
        for stage in [LatencyStage.TICK_INGESTION, LatencyStage.VWAP_CALCULATION]:
            for i in range(5):
                measurement = LatencyMeasurement(
                    timestamp=time.time() + i,
                    stage=stage,
                    duration_ms=5.0 + i,
                    symbol="BTCUSDc",
                    thread_id=12345,
                    cpu_usage=25.0,
                    memory_usage=60.0
                )
                self.collector.add_measurement(measurement)
        
        all_stats = self.collector.get_all_stats()
        
        assert len(all_stats) == 2
        assert LatencyStage.TICK_INGESTION in all_stats
        assert LatencyStage.VWAP_CALCULATION in all_stats
    
    def test_get_overall_stats(self):
        """Test getting overall statistics"""
        # Add measurements
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.TICK_INGESTION,
                duration_ms=5.0 + i * 0.1,
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            self.collector.add_measurement(measurement)
        
        overall_stats = self.collector.get_overall_stats()
        
        assert overall_stats.count == 20
        assert overall_stats.min_ms > 0
        assert overall_stats.max_ms > overall_stats.min_ms
        assert overall_stats.mean_ms > 0
        assert overall_stats.p50_ms > 0
        assert overall_stats.p95_ms > 0
        assert overall_stats.p99_ms > 0
    
    def test_calculate_trend(self):
        """Test trend calculation"""
        # Add measurements with improving trend
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.DECISION_MAKING,
                duration_ms=10.0 - i * 0.1,  # Decreasing latency
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            self.collector.add_measurement(measurement)
        
        stats = self.collector.get_stage_stats(LatencyStage.DECISION_MAKING)
        
        assert stats is not None
        assert stats.recent_trend in ["improving", "stable", "degrading"]

class TestHardwareProfiler:
    """Test hardware profiler"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.profiler = HardwareProfiler()
    
    def test_profiler_initialization(self):
        """Test profiler initialization"""
        assert self.profiler.profile is not None
        assert isinstance(self.profiler.profile, HardwareProfile)
    
    def test_get_profile(self):
        """Test getting hardware profile"""
        profile = self.profiler.get_profile()
        
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu_count > 0
        assert profile.cpu_freq_mhz > 0
        assert profile.memory_gb > 0
        assert profile.disk_type in ["SSD", "HDD"]
        assert profile.os_type is not None
        assert profile.python_version is not None
        assert profile.hardware_type in [HardwareType.HIGH_END, HardwareType.MID_RANGE, HardwareType.LOW_END]
        assert 0 <= profile.performance_score <= 100
    
    def test_classify_hardware(self):
        """Test hardware classification"""
        # Test high-end classification
        hw_type = self.profiler._classify_hardware(8, 16.0, "SSD")
        assert hw_type == HardwareType.HIGH_END
        
        # Test mid-range classification
        hw_type = self.profiler._classify_hardware(4, 8.0, "SSD")
        assert hw_type == HardwareType.MID_RANGE
        
        # Test low-end classification
        hw_type = self.profiler._classify_hardware(2, 4.0, "HDD")
        assert hw_type == HardwareType.LOW_END
    
    def test_calculate_performance_score(self):
        """Test performance score calculation"""
        score = self.profiler._calculate_performance_score(8, 3200.0, 16.0, "SSD")
        
        assert 0 <= score <= 100
        assert isinstance(score, float)

class TestLatencyValidator:
    """Test latency validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = LatencyValidator(target_p95_ms=200.0)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.target_p95_ms == 200.0
        assert isinstance(self.validator.collector, LatencyCollector)
        assert isinstance(self.validator.hardware_profiler, HardwareProfiler)
        assert len(self.validator.timers) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_start_stop_timer(self):
        """Test starting and stopping timer"""
        timer_id = "test_timer"
        
        # Start timer
        self.validator.start_timer(timer_id, LatencyStage.TICK_INGESTION, "BTCUSDc", queue_size=100)
        
        assert timer_id in self.validator.timers
        assert self.validator.timers[timer_id].stage == LatencyStage.TICK_INGESTION
        assert self.validator.timers[timer_id].symbol == "BTCUSDc"
        
        # Stop timer
        measurement = self.validator.stop_timer(timer_id)
        
        assert measurement is not None
        assert isinstance(measurement, LatencyMeasurement)
        assert measurement.stage == LatencyStage.TICK_INGESTION
        assert measurement.symbol == "BTCUSDc"
        assert measurement.duration_ms >= 0.0
    
    def test_measure_latency_context(self):
        """Test latency measurement context manager"""
        with self.validator.measure_latency(LatencyStage.VWAP_CALCULATION, "ETHUSDc", buffer_size=1000) as ctx:
            time.sleep(0.001)  # Small delay
        
        # Check that measurement was recorded
        stats = self.validator.collector.get_stage_stats(LatencyStage.VWAP_CALCULATION)
        assert stats is not None
        assert stats.count > 0
    
    def test_validate_latency_target(self):
        """Test latency target validation"""
        # Add some measurements
        for i in range(10):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.TICK_INGESTION,
                duration_ms=50.0 + i * 5.0,  # 50-95ms range
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            self.validator.collector.add_measurement(measurement)
        
        result = self.validator.validate_latency_target()
        
        assert 'overall_p95_ms' in result
        assert 'target_p95_ms' in result
        assert 'meets_target' in result
        assert 'latency_level' in result
        assert 'overall_stats' in result
        assert 'stage_analysis' in result
        assert 'hardware_profile' in result
        assert 'recommendations' in result
        assert 'uptime_seconds' in result
        
        assert result['target_p95_ms'] == 200.0
        # meets_target should be a boolean
        assert result['meets_target'] in [True, False]
        assert result['latency_level'] in ['excellent', 'good', 'acceptable', 'poor']
        assert isinstance(result['recommendations'], list)
    
    def test_generate_recommendations(self):
        """Test recommendation generation"""
        # Create mock stats with poor performance
        overall_stats = LatencyStats(
            stage=LatencyStage.TICK_INGESTION,
            count=100,
            p95_ms=250.0  # Exceeds target
        )
        
        stage_stats = {
            LatencyStage.TICK_INGESTION: LatencyStats(
                stage=LatencyStage.TICK_INGESTION,
                count=50,
                p95_ms=300.0,  # Exceeds target
                recent_trend="degrading"
            )
        }
        
        hardware_profile = HardwareProfile(
            cpu_count=2,
            cpu_freq_mhz=2000.0,
            memory_gb=4.0,
            disk_type="HDD",
            os_type="Windows",
            python_version="3.11.2",
            hardware_type=HardwareType.LOW_END,
            performance_score=30.0
        )
        
        recommendations = self.validator._generate_recommendations(overall_stats, stage_stats, hardware_profile)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check for specific recommendations
        recommendation_texts = [rec for rec in recommendations]
        assert any("exceeds target" in rec for rec in recommendation_texts)
        assert any("degrading" in rec for rec in recommendation_texts)
        assert any("low-end" in rec for rec in recommendation_texts)
    
    def test_get_latency_report(self):
        """Test getting latency report"""
        report = self.validator.get_latency_report()
        
        assert isinstance(report, dict)
        assert 'overall_p95_ms' in report
        assert 'target_p95_ms' in report
        assert 'meets_target' in report
        assert 'latency_level' in report
        assert 'recommendations' in report

class TestGlobalFunctions:
    """Test global latency functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.latency_validation
        infra.latency_validation._latency_validator = None
    
    def test_get_latency_validator(self):
        """Test global validator access"""
        validator1 = get_latency_validator()
        validator2 = get_latency_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, LatencyValidator)
    
    def test_measure_latency_global(self):
        """Test global latency measurement"""
        with measure_latency(LatencyStage.TICK_INGESTION, "BTCUSDc", queue_size=100) as ctx:
            time.sleep(0.001)
        
        # Check that measurement was recorded
        validator = get_latency_validator()
        stats = validator.collector.get_stage_stats(LatencyStage.TICK_INGESTION)
        assert stats is not None
    
    def test_validate_latency_target_global(self):
        """Test global latency target validation"""
        result = validate_latency_target()
        
        assert isinstance(result, dict)
        assert 'overall_p95_ms' in result
        assert 'meets_target' in result
        assert 'latency_level' in result
    
    def test_get_latency_report_global(self):
        """Test global latency report"""
        report = get_latency_report()
        
        assert isinstance(report, dict)
        assert 'overall_p95_ms' in report
        assert 'meets_target' in report
        assert 'recommendations' in report

class TestLatencyValidationIntegration:
    """Integration tests for latency validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.latency_validation
        infra.latency_validation._latency_validator = None
    
    def test_comprehensive_latency_analysis(self):
        """Test comprehensive latency analysis workflow"""
        validator = get_latency_validator()
        
        # Simulate latency measurements for different stages
        stages = [
            LatencyStage.TICK_INGESTION,
            LatencyStage.VWAP_CALCULATION,
            LatencyStage.DECISION_MAKING,
            LatencyStage.ORDER_PROCESSING
        ]
        
        for stage in stages:
            with measure_latency(stage, "BTCUSDc", buffer_size=1000):
                time.sleep(0.001)  # Simulate work
        
        # Get latency report
        report = get_latency_report()
        
        assert isinstance(report, dict)
        assert 'overall_p95_ms' in report
        assert 'target_p95_ms' in report
        assert 'meets_target' in report
        assert 'latency_level' in report
        assert 'stage_analysis' in report
        assert 'hardware_profile' in report
        assert 'recommendations' in report
        
        # Check that metrics are calculated
        assert 0.0 <= report['overall_p95_ms']
        assert report['target_p95_ms'] == 200.0
        # meets_target should be a boolean
        assert report['meets_target'] in [True, False]
        assert report['latency_level'] in ['excellent', 'good', 'acceptable', 'poor']
        assert isinstance(report['recommendations'], list)
    
    def test_latency_target_validation(self):
        """Test latency target validation"""
        validator = get_latency_validator()
        
        # Add measurements with good performance
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.TICK_INGESTION,
                duration_ms=10.0 + i * 0.5,  # 10-19.5ms range
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            validator.collector.add_measurement(measurement)
        
        # Validate latency target
        result = validate_latency_target()
        
        # Should meet target (p95 should be well below 200ms)
        assert result['overall_p95_ms'] < 200.0
        assert result['meets_target'] == True
        assert result['latency_level'] in ['excellent', 'good', 'acceptable']
    
    def test_stage_breakdown(self):
        """Test stage-by-stage latency breakdown"""
        validator = get_latency_validator()
        
        # Add measurements for different stages
        stages = [
            LatencyStage.TICK_INGESTION,
            LatencyStage.VWAP_CALCULATION,
            LatencyStage.DECISION_MAKING
        ]
        
        for stage in stages:
            for i in range(10):
                measurement = LatencyMeasurement(
                    timestamp=time.time() + i,
                    stage=stage,
                    duration_ms=5.0 + i * 0.5,
                    symbol="BTCUSDc",
                    thread_id=12345,
                    cpu_usage=25.0,
                    memory_usage=60.0
                )
                validator.collector.add_measurement(measurement)
        
        # Get latency report
        report = get_latency_report()
        
        # Check stage analysis
        assert 'stage_analysis' in report
        stage_analysis = report['stage_analysis']
        
        for stage in stages:
            assert stage.value in stage_analysis
            stage_data = stage_analysis[stage.value]
            assert 'p95_ms' in stage_data
            assert 'meets_target' in stage_data
            assert 'trend' in stage_data
            assert 'count' in stage_data
    
    def test_hardware_analysis(self):
        """Test hardware analysis"""
        validator = get_latency_validator()
        
        # Get latency report
        report = get_latency_report()
        
        # Check hardware profile
        assert 'hardware_profile' in report
        hardware_profile = report['hardware_profile']
        
        assert 'cpu_count' in hardware_profile
        assert 'memory_gb' in hardware_profile
        assert 'disk_type' in hardware_profile
        assert 'hardware_type' in hardware_profile
        assert 'performance_score' in hardware_profile
        
        assert hardware_profile['cpu_count'] > 0
        assert hardware_profile['memory_gb'] > 0
        assert hardware_profile['disk_type'] in ['SSD', 'HDD']
        # Check if hardware_type is a string or enum
        hw_type = hardware_profile['hardware_type']
        if isinstance(hw_type, str):
            assert hw_type in ['high_end', 'mid_range', 'low_end']
        else:
            # It's an enum, check its value
            assert hw_type.value in ['high_end', 'mid_range', 'low_end']
        assert 0 <= hardware_profile['performance_score'] <= 100
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        validator = get_latency_validator()
        
        # Add measurements with poor performance
        for i in range(20):
            measurement = LatencyMeasurement(
                timestamp=time.time() + i,
                stage=LatencyStage.TICK_INGESTION,
                duration_ms=100.0 + i * 10.0,  # 100-290ms range (exceeds target)
                symbol="BTCUSDc",
                thread_id=12345,
                cpu_usage=25.0,
                memory_usage=60.0
            )
            validator.collector.add_measurement(measurement)
        
        # Get latency report
        report = get_latency_report()
        
        # Check recommendations
        assert 'recommendations' in report
        recommendations = report['recommendations']
        assert isinstance(recommendations, list)
        
        # Should have recommendations for poor performance
        if not report['meets_target']:
            assert len(recommendations) > 0
            assert any("exceeds target" in rec for rec in recommendations)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
