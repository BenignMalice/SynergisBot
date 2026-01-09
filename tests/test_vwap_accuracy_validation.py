"""
Comprehensive tests for VWAP accuracy validation system

Tests VWAP accuracy validation within ±0.1σ tolerance, real-time VWAP calculation
validation, historical VWAP accuracy assessment, session-anchored VWAP validation,
sigma band accuracy validation, multi-timeframe VWAP validation, statistical
significance testing, and performance benchmarking.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple
from collections import deque

from infra.vwap_accuracy_validation import (
    VWAPValidator, VWAPAccuracyValidator,
    VWAPAccuracyLevel, VWAPValidationStatus, VWAPSessionType,
    VWAPTick, VWAPCalculation, VWAPAccuracyMetrics, VWAPValidationReport,
    get_vwap_validator, validate_vwap_accuracy, validate_session_vwap,
    generate_vwap_validation_report, get_vwap_accuracy_summary
)

class TestVWAPAccuracyLevel:
    """Test VWAP accuracy level enumeration"""
    
    def test_accuracy_levels(self):
        """Test all accuracy levels"""
        levels = [
            VWAPAccuracyLevel.EXCELLENT,
            VWAPAccuracyLevel.GOOD,
            VWAPAccuracyLevel.ACCEPTABLE,
            VWAPAccuracyLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, VWAPAccuracyLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestVWAPValidationStatus:
    """Test VWAP validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            VWAPValidationStatus.PASSED,
            VWAPValidationStatus.WARNING,
            VWAPValidationStatus.FAILED,
            VWAPValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, VWAPValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestVWAPSessionType:
    """Test VWAP session type enumeration"""
    
    def test_session_types(self):
        """Test all session types"""
        types = [
            VWAPSessionType.FOREX,
            VWAPSessionType.CRYPTO,
            VWAPSessionType.METALS,
            VWAPSessionType.CUSTOM
        ]
        
        for session_type in types:
            assert isinstance(session_type, VWAPSessionType)
            assert session_type.value in ["forex", "crypto", "metals", "custom"]

class TestVWAPTick:
    """Test VWAP tick data structure"""
    
    def test_vwap_tick_creation(self):
        """Test VWAP tick creation"""
        tick = VWAPTick(
            timestamp=time.time(),
            price=50000.0,
            volume=1.5,
            symbol="BTCUSDc",
            source="mt5",
            session_id="session_001",
            metadata={"exchange": "MT5", "spread": 2.5}
        )
        
        assert tick.timestamp > 0
        assert tick.price == 50000.0
        assert tick.volume == 1.5
        assert tick.symbol == "BTCUSDc"
        assert tick.source == "mt5"
        assert tick.session_id == "session_001"
        assert tick.metadata["exchange"] == "MT5"
        assert tick.metadata["spread"] == 2.5
    
    def test_vwap_tick_defaults(self):
        """Test VWAP tick defaults"""
        tick = VWAPTick(
            timestamp=time.time(),
            price=100.0,
            volume=1.0,
            symbol="EURUSDc",
            source="binance",
            session_id="session_002"
        )
        
        assert tick.metadata == {}

class TestVWAPCalculation:
    """Test VWAP calculation data structure"""
    
    def test_vwap_calculation_creation(self):
        """Test VWAP calculation creation"""
        calculation = VWAPCalculation(
            timestamp=time.time(),
            vwap=50000.0,
            volume=1000.0,
            price_volume_sum=50000000.0,
            session_id="session_001",
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            sigma=100.0,
            upper_band=50200.0,
            lower_band=49800.0,
            accuracy_score=0.95,
            metadata={"tick_count": 1000, "session_duration": 3600}
        )
        
        assert calculation.timestamp > 0
        assert calculation.vwap == 50000.0
        assert calculation.volume == 1000.0
        assert calculation.price_volume_sum == 50000000.0
        assert calculation.session_id == "session_001"
        assert calculation.symbol == "BTCUSDc"
        assert calculation.session_type == VWAPSessionType.CRYPTO
        assert calculation.sigma == 100.0
        assert calculation.upper_band == 50200.0
        assert calculation.lower_band == 49800.0
        assert calculation.accuracy_score == 0.95
        assert calculation.metadata["tick_count"] == 1000
        assert calculation.metadata["session_duration"] == 3600
    
    def test_vwap_calculation_defaults(self):
        """Test VWAP calculation defaults"""
        calculation = VWAPCalculation(
            timestamp=time.time(),
            vwap=100.0,
            volume=100.0,
            price_volume_sum=10000.0,
            session_id="session_002",
            symbol="EURUSDc",
            session_type=VWAPSessionType.FOREX,
            sigma=1.0,
            upper_band=102.0,
            lower_band=98.0,
            accuracy_score=0.85
        )
        
        assert calculation.metadata == {}

class TestVWAPAccuracyMetrics:
    """Test VWAP accuracy metrics data structure"""
    
    def test_vwap_accuracy_metrics_creation(self):
        """Test VWAP accuracy metrics creation"""
        metrics = VWAPAccuracyMetrics(
            timestamp=time.time(),
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            deviation=5.0,
            deviation_sigma=0.05,
            accuracy_level=VWAPAccuracyLevel.EXCELLENT,
            validation_status=VWAPValidationStatus.PASSED,
            sample_size=1000,
            confidence_interval=(49995.0, 50015.0),
            metadata={"tolerance_sigma": 0.1, "validation_time": time.time()}
        )
        
        assert metrics.timestamp > 0
        assert metrics.symbol == "BTCUSDc"
        assert metrics.session_type == VWAPSessionType.CRYPTO
        assert metrics.expected_vwap == 50000.0
        assert metrics.calculated_vwap == 50005.0
        assert metrics.deviation == 5.0
        assert metrics.deviation_sigma == 0.05
        assert metrics.accuracy_level == VWAPAccuracyLevel.EXCELLENT
        assert metrics.validation_status == VWAPValidationStatus.PASSED
        assert metrics.sample_size == 1000
        assert metrics.confidence_interval == (49995.0, 50015.0)
        assert metrics.metadata["tolerance_sigma"] == 0.1
    
    def test_vwap_accuracy_metrics_defaults(self):
        """Test VWAP accuracy metrics defaults"""
        metrics = VWAPAccuracyMetrics(
            timestamp=time.time(),
            symbol="EURUSDc",
            session_type=VWAPSessionType.FOREX,
            expected_vwap=1.1000,
            calculated_vwap=1.1005,
            deviation=0.0005,
            deviation_sigma=0.1,
            accuracy_level=VWAPAccuracyLevel.GOOD,
            validation_status=VWAPValidationStatus.WARNING,
            sample_size=500,
            confidence_interval=(1.0995, 1.1005)
        )
        
        assert metrics.metadata == {}

class TestVWAPValidationReport:
    """Test VWAP validation report data structure"""
    
    def test_vwap_validation_report_creation(self):
        """Test VWAP validation report creation"""
        report = VWAPValidationReport(
            timestamp=time.time(),
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            overall_accuracy=0.95,
            accuracy_level=VWAPAccuracyLevel.EXCELLENT,
            validation_status=VWAPValidationStatus.PASSED,
            total_samples=1000,
            passed_samples=950,
            failed_samples=50,
            average_deviation=0.05,
            max_deviation=0.15,
            sigma_accuracy=0.95,
            recommendations=["VWAP accuracy validation passed successfully"],
            detailed_metrics=[],
            metadata={"tolerance_sigma": 0.1, "confidence_level": 0.95}
        )
        
        assert report.timestamp > 0
        assert report.symbol == "BTCUSDc"
        assert report.session_type == VWAPSessionType.CRYPTO
        assert report.overall_accuracy == 0.95
        assert report.accuracy_level == VWAPAccuracyLevel.EXCELLENT
        assert report.validation_status == VWAPValidationStatus.PASSED
        assert report.total_samples == 1000
        assert report.passed_samples == 950
        assert report.failed_samples == 50
        assert report.average_deviation == 0.05
        assert report.max_deviation == 0.15
        assert report.sigma_accuracy == 0.95
        assert len(report.recommendations) == 1
        assert report.detailed_metrics == []
        assert report.metadata["tolerance_sigma"] == 0.1
    
    def test_vwap_validation_report_defaults(self):
        """Test VWAP validation report defaults"""
        report = VWAPValidationReport(
            timestamp=time.time(),
            symbol="EURUSDc",
            session_type=VWAPSessionType.FOREX,
            overall_accuracy=0.85,
            accuracy_level=VWAPAccuracyLevel.GOOD,
            validation_status=VWAPValidationStatus.WARNING,
            total_samples=500,
            passed_samples=425,
            failed_samples=75,
            average_deviation=0.1,
            max_deviation=0.3,
            sigma_accuracy=0.85,
            recommendations=["VWAP accuracy validation passed with warnings"],
            detailed_metrics=[]
        )
        
        assert report.detailed_metrics == []
        assert report.metadata == {}

class TestVWAPAccuracyValidator:
    """Test VWAP accuracy validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = VWAPAccuracyValidator(tolerance_sigma=0.1)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.tolerance_sigma == 0.1
        assert len(self.validator.calculations) == 0
        assert len(self.validator.accuracy_metrics) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.min_sample_size == 100
        assert self.validator.confidence_level == 0.95
    
    def test_validate_vwap_accuracy_excellent(self):
        """Test VWAP accuracy validation with excellent accuracy"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50002.0,  # 0.02σ deviation
            sigma=100.0,
            sample_size=1000
        )
        
        assert metrics.symbol == "BTCUSDc"
        assert metrics.session_type == VWAPSessionType.CRYPTO
        assert metrics.expected_vwap == 50000.0
        assert metrics.calculated_vwap == 50002.0
        assert metrics.deviation == 2.0
        assert metrics.deviation_sigma == 0.02
        assert metrics.accuracy_level == VWAPAccuracyLevel.EXCELLENT
        assert metrics.validation_status == VWAPValidationStatus.PASSED
        assert metrics.sample_size == 1000
        assert len(metrics.confidence_interval) == 2
        assert metrics.metadata["tolerance_sigma"] == 0.1
    
    def test_validate_vwap_accuracy_good(self):
        """Test VWAP accuracy validation with good accuracy"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="EURUSDc",
            session_type=VWAPSessionType.FOREX,
            expected_vwap=1.1000,
            calculated_vwap=1.1008,  # 0.08σ deviation
            sigma=0.01,
            sample_size=500
        )
        
        assert metrics.accuracy_level == VWAPAccuracyLevel.GOOD
        assert metrics.validation_status == VWAPValidationStatus.PASSED
        assert abs(metrics.deviation_sigma - 0.08) < 0.001  # Allow for floating point precision
    
    def test_validate_vwap_accuracy_acceptable(self):
        """Test VWAP accuracy validation with acceptable accuracy"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="XAUUSDc",
            session_type=VWAPSessionType.METALS,
            expected_vwap=2000.0,
            calculated_vwap=2015.0,  # 0.15σ deviation
            sigma=100.0,
            sample_size=200
        )
        
        assert metrics.accuracy_level == VWAPAccuracyLevel.ACCEPTABLE
        assert metrics.validation_status == VWAPValidationStatus.WARNING
        assert metrics.deviation_sigma == 0.15
    
    def test_validate_vwap_accuracy_poor(self):
        """Test VWAP accuracy validation with poor accuracy"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="GBPUSDc",
            session_type=VWAPSessionType.FOREX,
            expected_vwap=1.2500,
            calculated_vwap=1.2600,  # 0.25σ deviation
            sigma=0.04,
            sample_size=100
        )
        
        assert metrics.accuracy_level == VWAPAccuracyLevel.POOR
        assert metrics.validation_status == VWAPValidationStatus.FAILED
        assert abs(metrics.deviation_sigma - 0.25) < 0.001  # Allow for floating point precision
    
    def test_validate_vwap_accuracy_failed(self):
        """Test VWAP accuracy validation with failed accuracy"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="USDJPYc",
            session_type=VWAPSessionType.FOREX,
            expected_vwap=150.0,
            calculated_vwap=155.0,  # 0.5σ deviation
            sigma=10.0,
            sample_size=50
        )
        
        assert metrics.validation_status == VWAPValidationStatus.FAILED
        assert metrics.deviation_sigma == 0.5
    
    def test_validate_session_vwap(self):
        """Test session VWAP validation"""
        # Create sample ticks
        ticks = []
        base_price = 50000.0
        base_volume = 1.0
        
        for i in range(100):
            tick = VWAPTick(
                timestamp=time.time() + i,
                price=base_price + (i % 10) * 10,  # Price variation
                volume=base_volume + (i % 5) * 0.1,  # Volume variation
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
            ticks.append(tick)
        
        calculation = self.validator.validate_session_vwap(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            ticks=ticks
        )
        
        assert calculation.symbol == "BTCUSDc"
        assert calculation.session_type == VWAPSessionType.CRYPTO
        assert calculation.vwap > 0
        assert calculation.volume > 0
        assert calculation.price_volume_sum > 0
        assert calculation.sigma > 0
        assert calculation.upper_band > calculation.vwap
        assert calculation.lower_band < calculation.vwap
        assert 0.0 <= calculation.accuracy_score <= 1.0
        assert calculation.metadata["tick_count"] == 100
    
    def test_validate_session_vwap_empty_ticks(self):
        """Test session VWAP validation with empty ticks"""
        with pytest.raises(ValueError, match="No ticks provided"):
            self.validator.validate_session_vwap(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                ticks=[]
            )
    
    def test_validate_session_vwap_zero_volume(self):
        """Test session VWAP validation with zero volume"""
        ticks = [
            VWAPTick(
                timestamp=time.time(),
                price=50000.0,
                volume=0.0,  # Zero volume
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
        ]
        
        with pytest.raises(ValueError, match="Total volume is zero"):
            self.validator.validate_session_vwap(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                ticks=ticks
            )
    
    def test_calculate_confidence_interval(self):
        """Test confidence interval calculation"""
        # Test with normal case
        interval = self.validator._calculate_confidence_interval(
            vwap=50000.0, sigma=100.0, sample_size=1000
        )
        
        assert len(interval) == 2
        assert interval[0] < 50000.0  # Lower bound
        assert interval[1] > 50000.0  # Upper bound
        assert interval[0] < interval[1]  # Lower < Upper
        
        # Test with small sample size
        interval_small = self.validator._calculate_confidence_interval(
            vwap=100.0, sigma=1.0, sample_size=1
        )
        
        assert interval_small == (100.0, 100.0)  # Should return same value
    
    def test_calculate_accuracy_score(self):
        """Test accuracy score calculation"""
        # Create ticks with normal distribution
        ticks = []
        vwap = 50000.0
        sigma = 100.0
        
        for i in range(1000):
            # Generate normally distributed prices
            price = vwap + np.random.normal(0, sigma)
            tick = VWAPTick(
                timestamp=time.time() + i,
                price=price,
                volume=1.0,
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
            ticks.append(tick)
        
        score = self.validator._calculate_accuracy_score(vwap, sigma, ticks)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be reasonably high for normal distribution
    
    def test_calculate_accuracy_score_zero_sigma(self):
        """Test accuracy score calculation with zero sigma"""
        ticks = [VWAPTick(
            timestamp=time.time(),
            price=50000.0,
            volume=1.0,
            symbol="BTCUSDc",
            source="mt5",
            session_id="session_001"
        )]
        
        score = self.validator._calculate_accuracy_score(50000.0, 0.0, ticks)
        assert score == 0.0
    
    def test_calculate_accuracy_score_empty_ticks(self):
        """Test accuracy score calculation with empty ticks"""
        score = self.validator._calculate_accuracy_score(50000.0, 100.0, [])
        assert score == 0.0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some accuracy metrics
        for i in range(10):
            metrics = VWAPAccuracyMetrics(
                timestamp=time.time() + i,
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,  # Small deviations
                deviation=abs(i * 5),
                deviation_sigma=abs(i * 5) / 100.0,
                accuracy_level=VWAPAccuracyLevel.EXCELLENT if i < 5 else VWAPAccuracyLevel.GOOD,
                validation_status=VWAPValidationStatus.PASSED,
                sample_size=1000,
                confidence_interval=(49995.0, 50015.0)
            )
            self.validator.accuracy_metrics.append(metrics)
        
        report = self.validator.generate_validation_report(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO
        )
        
        assert report.symbol == "BTCUSDc"
        assert report.session_type == VWAPSessionType.CRYPTO
        assert report.total_samples == 10
        assert report.passed_samples == 10
        assert report.failed_samples == 0
        assert report.overall_accuracy == 1.0
        assert report.accuracy_level in [VWAPAccuracyLevel.EXCELLENT, VWAPAccuracyLevel.GOOD, VWAPAccuracyLevel.ACCEPTABLE, VWAPAccuracyLevel.POOR]
        assert report.validation_status == VWAPValidationStatus.PASSED
        assert report.average_deviation >= 0.0
        assert report.max_deviation >= 0.0
        assert 0.0 <= report.sigma_accuracy <= 1.0
        assert len(report.recommendations) > 0
        assert len(report.detailed_metrics) == 10
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report(
            symbol="UNKNOWN",
            session_type=VWAPSessionType.CRYPTO
        )
        
        assert report.symbol == "UNKNOWN"
        assert report.session_type == VWAPSessionType.CRYPTO
        assert report.overall_accuracy == 0.0
        assert report.accuracy_level == VWAPAccuracyLevel.POOR
        assert report.validation_status == VWAPValidationStatus.FAILED
        assert report.total_samples == 0
        assert report.passed_samples == 0
        assert report.failed_samples == 0
        assert "No data available" in report.recommendations[0]
        assert report.detailed_metrics == []
    
    def test_generate_recommendations(self):
        """Test recommendations generation"""
        # Test failed validation
        recommendations = self.validator._generate_recommendations(
            overall_accuracy=0.5,
            average_deviation=0.5,
            accuracy_level=VWAPAccuracyLevel.POOR,
            validation_status=VWAPValidationStatus.FAILED
        )
        
        assert len(recommendations) > 0
        assert any("failed" in rec.lower() for rec in recommendations)
        assert any("deviation" in rec.lower() or "accuracy" in rec.lower() for rec in recommendations)
        
        # Test warning validation
        recommendations = self.validator._generate_recommendations(
            overall_accuracy=0.85,
            average_deviation=0.15,
            accuracy_level=VWAPAccuracyLevel.ACCEPTABLE,
            validation_status=VWAPValidationStatus.WARNING
        )
        
        assert len(recommendations) > 0
        assert any("warning" in rec.lower() for rec in recommendations)
        
        # Test passed validation
        recommendations = self.validator._generate_recommendations(
            overall_accuracy=0.98,
            average_deviation=0.05,
            accuracy_level=VWAPAccuracyLevel.EXCELLENT,
            validation_status=VWAPValidationStatus.PASSED
        )
        
        assert len(recommendations) > 0
        assert any("passed" in rec.lower() for rec in recommendations)
        assert any("excellent" in rec.lower() for rec in recommendations)
    
    def test_get_accuracy_summary(self):
        """Test accuracy summary"""
        # Test with no data
        summary = self.validator.get_accuracy_summary()
        assert summary["total_validations"] == 0
        
        # Add some metrics
        for i in range(5):
            metrics = VWAPAccuracyMetrics(
                timestamp=time.time() + i,
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 10,
                deviation=abs(i * 10),
                deviation_sigma=abs(i * 10) / 100.0,
                accuracy_level=VWAPAccuracyLevel.EXCELLENT if i < 2 else VWAPAccuracyLevel.GOOD,
                validation_status=VWAPValidationStatus.PASSED,
                sample_size=1000,
                confidence_interval=(49995.0, 50015.0)
            )
            self.validator.accuracy_metrics.append(metrics)
        
        summary = self.validator.get_accuracy_summary()
        
        assert summary["total_validations"] == 5
        assert summary["passed_validations"] == 5
        assert summary["pass_rate"] == 1.0
        assert "accuracy_level_distribution" in summary
        assert summary["average_deviation_sigma"] >= 0.0
        assert summary["max_deviation_sigma"] >= 0.0
        assert summary["tolerance_sigma"] == 0.1

class TestVWAPValidator:
    """Test VWAP validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = VWAPValidator(tolerance_sigma=0.1)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.accuracy_validator, VWAPAccuracyValidator)
        assert self.validator.accuracy_validator.tolerance_sigma == 0.1
        assert self.validator.start_time > 0
        assert len(self.validator.validation_reports) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_vwap_accuracy(self):
        """Test VWAP accuracy validation"""
        metrics = self.validator.validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            sigma=100.0,
            sample_size=1000
        )
        
        assert isinstance(metrics, VWAPAccuracyMetrics)
        assert metrics.symbol == "BTCUSDc"
        assert metrics.session_type == VWAPSessionType.CRYPTO
        assert metrics.expected_vwap == 50000.0
        assert metrics.calculated_vwap == 50005.0
    
    def test_validate_session_vwap(self):
        """Test session VWAP validation"""
        ticks = []
        for i in range(50):
            tick = VWAPTick(
                timestamp=time.time() + i,
                price=50000.0 + i * 10,
                volume=1.0 + i * 0.1,
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
            ticks.append(tick)
        
        calculation = self.validator.validate_session_vwap(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            ticks=ticks
        )
        
        assert isinstance(calculation, VWAPCalculation)
        assert calculation.symbol == "BTCUSDc"
        assert calculation.session_type == VWAPSessionType.CRYPTO
        assert calculation.vwap > 0
        assert calculation.volume > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some metrics first
        for i in range(3):
            self.validator.validate_vwap_accuracy(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,
                sigma=100.0,
                sample_size=1000
            )
        
        report = self.validator.generate_validation_report(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO
        )
        
        assert isinstance(report, VWAPValidationReport)
        assert report.symbol == "BTCUSDc"
        assert report.session_type == VWAPSessionType.CRYPTO
        assert report.total_samples == 3
        
        # Check that report was added to history
        assert len(self.validator.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            self.validator.validate_vwap_accuracy(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,
                sigma=100.0,
                sample_size=1000
            )
            self.validator.generate_validation_report(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO
            )
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, VWAPValidationReport)
    
    def test_get_accuracy_summary(self):
        """Test getting accuracy summary"""
        # Add some metrics
        for i in range(5):
            self.validator.validate_vwap_accuracy(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,
                sigma=100.0,
                sample_size=1000
            )
        
        summary = self.validator.get_accuracy_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        self.validator.validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            sigma=100.0,
            sample_size=1000
        )
        self.validator.generate_validation_report(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO
        )
        
        # Reset validations
        self.validator.reset_validations()
        
        assert len(self.validator.accuracy_validator.accuracy_metrics) == 0
        assert len(self.validator.accuracy_validator.calculations) == 0
        assert len(self.validator.validation_reports) == 0

class TestGlobalFunctions:
    """Test global VWAP functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.vwap_accuracy_validation
        infra.vwap_accuracy_validation._vwap_validator = None
    
    def test_get_vwap_validator(self):
        """Test global validator access"""
        validator1 = get_vwap_validator()
        validator2 = get_vwap_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, VWAPValidator)
    
    def test_validate_vwap_accuracy_global(self):
        """Test global VWAP accuracy validation"""
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            sigma=100.0,
            sample_size=1000
        )
        
        assert isinstance(metrics, VWAPAccuracyMetrics)
        assert metrics.symbol == "BTCUSDc"
        assert metrics.session_type == VWAPSessionType.CRYPTO
        assert metrics.expected_vwap == 50000.0
        assert metrics.calculated_vwap == 50005.0
    
    def test_validate_session_vwap_global(self):
        """Test global session VWAP validation"""
        ticks = []
        for i in range(20):
            tick = VWAPTick(
                timestamp=time.time() + i,
                price=50000.0 + i * 10,
                volume=1.0 + i * 0.1,
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
            ticks.append(tick)
        
        calculation = validate_session_vwap(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            ticks=ticks
        )
        
        assert isinstance(calculation, VWAPCalculation)
        assert calculation.symbol == "BTCUSDc"
        assert calculation.session_type == VWAPSessionType.CRYPTO
        assert calculation.vwap > 0
        assert calculation.volume > 0
    
    def test_generate_vwap_validation_report_global(self):
        """Test global VWAP validation report generation"""
        # Add some metrics first
        for i in range(3):
            validate_vwap_accuracy(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,
                sigma=100.0,
                sample_size=1000
            )
        
        report = generate_vwap_validation_report(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO
        )
        
        assert isinstance(report, VWAPValidationReport)
        assert report.symbol == "BTCUSDc"
        assert report.session_type == VWAPSessionType.CRYPTO
        assert report.total_samples == 3
    
    def test_get_vwap_accuracy_summary_global(self):
        """Test global VWAP accuracy summary"""
        # Add some metrics
        for i in range(5):
            validate_vwap_accuracy(
                symbol="BTCUSDc",
                session_type=VWAPSessionType.CRYPTO,
                expected_vwap=50000.0,
                calculated_vwap=50000.0 + i * 5,
                sigma=100.0,
                sample_size=1000
            )
        
        summary = get_vwap_accuracy_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestVWAPAccuracyValidationIntegration:
    """Integration tests for VWAP accuracy validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.vwap_accuracy_validation
        infra.vwap_accuracy_validation._vwap_validator = None
    
    def test_comprehensive_vwap_validation(self):
        """Test comprehensive VWAP validation workflow"""
        # Test multiple symbols and session types
        symbols = ["BTCUSDc", "EURUSDc", "XAUUSDc"]
        session_types = [VWAPSessionType.CRYPTO, VWAPSessionType.FOREX, VWAPSessionType.METALS]
        
        for symbol, session_type in zip(symbols, session_types):
            # Add multiple accuracy validations
            for i in range(10):
                metrics = validate_vwap_accuracy(
                    symbol=symbol,
                    session_type=session_type,
                    expected_vwap=50000.0 if symbol == "BTCUSDc" else 1.1000 if symbol == "EURUSDc" else 2000.0,
                    calculated_vwap=50000.0 + i * 5 if symbol == "BTCUSDc" else 1.1000 + i * 0.0001 if symbol == "EURUSDc" else 2000.0 + i * 2,
                    sigma=100.0 if symbol == "BTCUSDc" else 0.01 if symbol == "EURUSDc" else 10.0,
                    sample_size=1000
                )
                
                assert isinstance(metrics, VWAPAccuracyMetrics)
                assert metrics.symbol == symbol
                assert metrics.session_type == session_type
                assert metrics.validation_status in [VWAPValidationStatus.PASSED, VWAPValidationStatus.WARNING, VWAPValidationStatus.FAILED]
            
            # Generate validation report
            report = generate_vwap_validation_report(symbol, session_type)
            
            assert isinstance(report, VWAPValidationReport)
            assert report.symbol == symbol
            assert report.session_type == session_type
            assert report.total_samples == 10
            assert report.overall_accuracy >= 0.0
            assert report.accuracy_level in [VWAPAccuracyLevel.EXCELLENT, VWAPAccuracyLevel.GOOD, 
                                           VWAPAccuracyLevel.ACCEPTABLE, VWAPAccuracyLevel.POOR]
            assert report.validation_status in [VWAPValidationStatus.PASSED, VWAPValidationStatus.WARNING, VWAPValidationStatus.FAILED]
            assert len(report.recommendations) > 0
            assert len(report.detailed_metrics) == 10
    
    def test_session_vwap_validation_workflow(self):
        """Test session VWAP validation workflow"""
        # Create realistic tick data
        ticks = []
        base_price = 50000.0
        base_volume = 1.0
        
        for i in range(1000):
            # Generate realistic price movement
            price_change = np.random.normal(0, 50)  # Normal distribution
            price = base_price + price_change
            
            # Generate realistic volume
            volume = base_volume + np.random.exponential(0.5)
            
            tick = VWAPTick(
                timestamp=time.time() + i,
                price=price,
                volume=volume,
                symbol="BTCUSDc",
                source="mt5",
                session_id="session_001"
            )
            ticks.append(tick)
        
        # Validate session VWAP
        calculation = validate_session_vwap(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            ticks=ticks
        )
        
        assert isinstance(calculation, VWAPCalculation)
        assert calculation.symbol == "BTCUSDc"
        assert calculation.session_type == VWAPSessionType.CRYPTO
        assert calculation.vwap > 0
        assert calculation.volume > 0
        assert calculation.sigma > 0
        assert calculation.upper_band > calculation.vwap
        assert calculation.lower_band < calculation.vwap
        assert 0.0 <= calculation.accuracy_score <= 1.0
        assert calculation.metadata["tick_count"] == 1000
    
    def test_accuracy_tolerance_validation(self):
        """Test accuracy tolerance validation"""
        # Test within tolerance
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,  # 0.05σ deviation (within 0.1σ tolerance)
            sigma=100.0,
            sample_size=1000
        )
        
        assert metrics.validation_status == VWAPValidationStatus.PASSED
        assert metrics.accuracy_level in [VWAPAccuracyLevel.EXCELLENT, VWAPAccuracyLevel.GOOD]
        
        # Test at tolerance boundary
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50010.0,  # 0.1σ deviation (at tolerance boundary)
            sigma=100.0,
            sample_size=1000
        )
        
        assert metrics.validation_status == VWAPValidationStatus.PASSED
        assert metrics.accuracy_level in [VWAPAccuracyLevel.GOOD, VWAPAccuracyLevel.ACCEPTABLE]
        
        # Test beyond tolerance
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50020.0,  # 0.2σ deviation (beyond tolerance)
            sigma=100.0,
            sample_size=1000
        )
        
        assert metrics.validation_status == VWAPValidationStatus.WARNING
        assert metrics.accuracy_level in [VWAPAccuracyLevel.ACCEPTABLE, VWAPAccuracyLevel.POOR]
    
    def test_statistical_significance_validation(self):
        """Test statistical significance validation"""
        # Test with sufficient sample size
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            sigma=100.0,
            sample_size=1000  # Sufficient sample size
        )
        
        assert metrics.sample_size == 1000
        assert len(metrics.confidence_interval) == 2
        assert metrics.confidence_interval[0] < metrics.confidence_interval[1]
        
        # Test with insufficient sample size
        metrics = validate_vwap_accuracy(
            symbol="BTCUSDc",
            session_type=VWAPSessionType.CRYPTO,
            expected_vwap=50000.0,
            calculated_vwap=50005.0,
            sigma=100.0,
            sample_size=10  # Insufficient sample size
        )
        
        assert metrics.sample_size == 10
        # For small sample size, confidence interval should be calculated normally
        assert len(metrics.confidence_interval) == 2
        assert metrics.confidence_interval[0] < metrics.confidence_interval[1]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
