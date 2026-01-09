"""
Comprehensive tests for shadow mode validation system

Tests shadow mode readiness validation, DTMS vs Intelligent Exits comparison,
performance metrics validation, decision trace validation, shadow mode lifecycle
management, A/B testing framework validation, statistical significance testing,
and rollback mechanism validation.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import deque

from infra.shadow_mode_validation import (
    ShadowModeValidator, ShadowModeReadinessValidator,
    ShadowModeReadiness, ComparisonResult, ValidationStatus,
    ShadowModeMetrics, ComparisonReport, ShadowModeValidation,
    get_shadow_mode_validator, validate_shadow_mode, add_shadow_mode_metrics, get_shadow_mode_metrics_summary
)

class TestShadowModeReadiness:
    """Test shadow mode readiness enumeration"""
    
    def test_readiness_levels(self):
        """Test all readiness levels"""
        levels = [
            ShadowModeReadiness.READY,
            ShadowModeReadiness.PREPARING,
            ShadowModeReadiness.TESTING,
            ShadowModeReadiness.NOT_READY
        ]
        
        for level in levels:
            assert isinstance(level, ShadowModeReadiness)
            assert level.value in ["ready", "preparing", "testing", "not_ready"]

class TestComparisonResult:
    """Test comparison result enumeration"""
    
    def test_comparison_results(self):
        """Test all comparison results"""
        results = [
            ComparisonResult.DTMS_BETTER,
            ComparisonResult.INTELLIGENT_BETTER,
            ComparisonResult.EQUIVALENT,
            ComparisonResult.INSUFFICIENT_DATA
        ]
        
        for result in results:
            assert isinstance(result, ComparisonResult)
            assert result.value in ["dtms_better", "intelligent_better", "equivalent", "insufficient_data"]

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

class TestShadowModeMetrics:
    """Test shadow mode metrics data structure"""
    
    def test_shadow_mode_metrics_creation(self):
        """Test shadow mode metrics creation"""
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=100,
            intelligent_trades=95,
            dtms_win_rate=0.75,
            intelligent_win_rate=0.70,
            dtms_avg_rr=2.5,
            intelligent_avg_rr=2.3,
            dtms_max_drawdown=0.05,
            intelligent_max_drawdown=0.06,
            dtms_latency_ms=50.0,
            intelligent_latency_ms=60.0,
            confidence_delta=0.05,
            metadata={"symbol": "BTCUSDc", "timeframe": "M5"}
        )
        
        assert metrics.timestamp > 0
        assert metrics.dtms_trades == 100
        assert metrics.intelligent_trades == 95
        assert metrics.dtms_win_rate == 0.75
        assert metrics.intelligent_win_rate == 0.70
        assert metrics.dtms_avg_rr == 2.5
        assert metrics.intelligent_avg_rr == 2.3
        assert metrics.dtms_max_drawdown == 0.05
        assert metrics.intelligent_max_drawdown == 0.06
        assert metrics.dtms_latency_ms == 50.0
        assert metrics.intelligent_latency_ms == 60.0
        assert metrics.confidence_delta == 0.05
        assert metrics.metadata["symbol"] == "BTCUSDc"
    
    def test_shadow_mode_metrics_defaults(self):
        """Test shadow mode metrics defaults"""
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=50,
            intelligent_trades=45,
            dtms_win_rate=0.65,
            intelligent_win_rate=0.60,
            dtms_avg_rr=2.0,
            intelligent_avg_rr=1.8,
            dtms_max_drawdown=0.08,
            intelligent_max_drawdown=0.09,
            dtms_latency_ms=75.0,
            intelligent_latency_ms=85.0,
            confidence_delta=0.03
        )
        
        assert metrics.metadata == {}

class TestComparisonReport:
    """Test comparison report data structure"""
    
    def test_comparison_report_creation(self):
        """Test comparison report creation"""
        report = ComparisonReport(
            comparison_result=ComparisonResult.DTMS_BETTER,
            statistical_significance=0.95,
            confidence_level=0.95,
            sample_size=150,
            dtms_metrics={"win_rate": 0.75, "avg_rr": 2.5, "max_drawdown": 0.05},
            intelligent_metrics={"win_rate": 0.70, "avg_rr": 2.3, "max_drawdown": 0.06},
            performance_delta={"win_rate_delta": 0.05, "avg_rr_delta": 0.2},
            recommendations=["DTMS shows superior performance", "Consider full deployment"],
            validation_status=ValidationStatus.PASSED
        )
        
        assert report.comparison_result == ComparisonResult.DTMS_BETTER
        assert report.statistical_significance == 0.95
        assert report.confidence_level == 0.95
        assert report.sample_size == 150
        assert report.dtms_metrics["win_rate"] == 0.75
        assert report.intelligent_metrics["win_rate"] == 0.70
        assert report.performance_delta["win_rate_delta"] == 0.05
        assert len(report.recommendations) == 2
        assert report.validation_status == ValidationStatus.PASSED

class TestShadowModeValidation:
    """Test shadow mode validation data structure"""
    
    def test_shadow_mode_validation_creation(self):
        """Test shadow mode validation creation"""
        validation = ShadowModeValidation(
            timestamp=time.time(),
            readiness_level=ShadowModeReadiness.READY,
            validation_status=ValidationStatus.PASSED,
            readiness_score=0.95,
            comparison_report=None,
            recommendations=["Shadow mode is ready for production"],
            validation_details={"sample_size": 150, "readiness_score": 0.95}
        )
        
        assert validation.timestamp > 0
        assert validation.readiness_level == ShadowModeReadiness.READY
        assert validation.validation_status == ValidationStatus.PASSED
        assert validation.readiness_score == 0.95
        assert validation.comparison_report is None
        assert len(validation.recommendations) == 1
        assert validation.validation_details["sample_size"] == 150
    
    def test_shadow_mode_validation_with_comparison(self):
        """Test shadow mode validation with comparison report"""
        comparison_report = ComparisonReport(
            comparison_result=ComparisonResult.DTMS_BETTER,
            statistical_significance=0.95,
            confidence_level=0.95,
            sample_size=150,
            dtms_metrics={"win_rate": 0.75},
            intelligent_metrics={"win_rate": 0.70},
            performance_delta={"win_rate_delta": 0.05},
            recommendations=["DTMS shows superior performance"],
            validation_status=ValidationStatus.PASSED
        )
        
        validation = ShadowModeValidation(
            timestamp=time.time(),
            readiness_level=ShadowModeReadiness.READY,
            validation_status=ValidationStatus.PASSED,
            readiness_score=0.95,
            comparison_report=comparison_report,
            recommendations=["Shadow mode is ready for production"],
            validation_details={"sample_size": 150}
        )
        
        assert validation.comparison_report is not None
        assert validation.comparison_report.comparison_result == ComparisonResult.DTMS_BETTER

class TestShadowModeReadinessValidator:
    """Test shadow mode readiness validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ShadowModeReadinessValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert len(self.validator.metrics) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.min_sample_size == 100
        assert self.validator.min_confidence_level == 0.95
        assert self.validator.min_performance_delta == 0.05
    
    def test_validate_readiness_insufficient_data(self):
        """Test readiness validation with insufficient data"""
        # Add some metrics but not enough
        for i in range(50):  # Less than minimum sample size
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10,
                intelligent_trades=8,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        validation = self.validator.validate_readiness()
        
        assert validation.readiness_level == ShadowModeReadiness.NOT_READY
        assert validation.validation_status == ValidationStatus.FAILED
        assert validation.readiness_score == 0.0
        assert validation.comparison_report is None
        assert "Insufficient data" in validation.recommendations[0]
        assert validation.validation_details["sample_size"] == 50
        assert validation.validation_details["required"] == 100
    
    def test_validate_readiness_sufficient_data(self):
        """Test readiness validation with sufficient data"""
        # Add enough metrics
        for i in range(150):  # More than minimum sample size
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75 + (i % 10) * 0.01,
                intelligent_win_rate=0.70 + (i % 10) * 0.01,
                dtms_avg_rr=2.5 + (i % 5) * 0.1,
                intelligent_avg_rr=2.3 + (i % 5) * 0.1,
                dtms_max_drawdown=0.05 + (i % 3) * 0.01,
                intelligent_max_drawdown=0.06 + (i % 3) * 0.01,
                dtms_latency_ms=50.0 + (i % 10) * 2.0,
                intelligent_latency_ms=60.0 + (i % 10) * 2.0,
                confidence_delta=0.05 + (i % 5) * 0.01
            )
            self.validator.add_metrics(metrics)
        
        validation = self.validator.validate_readiness()
        
        assert validation.readiness_level in [ShadowModeReadiness.READY, ShadowModeReadiness.PREPARING, 
                                            ShadowModeReadiness.TESTING, ShadowModeReadiness.NOT_READY]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert 0.0 <= validation.readiness_score <= 1.0
        assert validation.validation_details["sample_size"] == 150
        assert validation.validation_details["dtms_trades"] > 0
        assert validation.validation_details["intelligent_trades"] > 0
        assert validation.validation_details["avg_dtms_win_rate"] > 0.0
        assert validation.validation_details["avg_intelligent_win_rate"] > 0.0
    
    def test_calculate_readiness_score(self):
        """Test readiness score calculation"""
        # Test with no data
        score = self.validator._calculate_readiness_score()
        assert score == 0.0
        
        # Add some data
        for i in range(150):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10,
                intelligent_trades=8,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        score = self.validator._calculate_readiness_score()
        assert 0.0 <= score <= 1.0
    
    def test_calculate_data_quality_score(self):
        """Test data quality score calculation"""
        # Test with no data
        score = self.validator._calculate_data_quality_score()
        assert score == 0.0
        
        # Add valid data
        for i in range(10):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10,
                intelligent_trades=8,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        score = self.validator._calculate_data_quality_score()
        assert 0.0 <= score <= 1.0
    
    def test_calculate_stability_score(self):
        """Test stability score calculation"""
        # Test with insufficient data
        score = self.validator._calculate_stability_score()
        assert score == 0.0
        
        # Add data with varying performance
        for i in range(10):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10,
                intelligent_trades=8,
                dtms_win_rate=0.75 + (i % 3) * 0.01,  # Some variation
                intelligent_win_rate=0.70 + (i % 3) * 0.01,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        score = self.validator._calculate_stability_score()
        assert 0.0 <= score <= 1.0
    
    def test_calculate_comparison_readiness_score(self):
        """Test comparison readiness score calculation"""
        # Test with no data
        score = self.validator._calculate_comparison_readiness_score()
        assert score == 0.0
        
        # Add data with sufficient trades
        for i in range(10):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=20,  # Sufficient trades
                intelligent_trades=18,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        score = self.validator._calculate_comparison_readiness_score()
        assert 0.0 <= score <= 1.0
    
    def test_generate_comparison_report(self):
        """Test comparison report generation"""
        # Add sufficient data
        for i in range(150):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75 + (i % 10) * 0.01,
                intelligent_win_rate=0.70 + (i % 10) * 0.01,
                dtms_avg_rr=2.5 + (i % 5) * 0.1,
                intelligent_avg_rr=2.3 + (i % 5) * 0.1,
                dtms_max_drawdown=0.05 + (i % 3) * 0.01,
                intelligent_max_drawdown=0.06 + (i % 3) * 0.01,
                dtms_latency_ms=50.0 + (i % 10) * 2.0,
                intelligent_latency_ms=60.0 + (i % 10) * 2.0,
                confidence_delta=0.05 + (i % 5) * 0.01
            )
            self.validator.add_metrics(metrics)
        
        report = self.validator._generate_comparison_report()
        
        assert report is not None
        assert report.comparison_result in [ComparisonResult.DTMS_BETTER, ComparisonResult.INTELLIGENT_BETTER,
                                          ComparisonResult.EQUIVALENT, ComparisonResult.INSUFFICIENT_DATA]
        assert 0.0 <= report.statistical_significance <= 1.0
        assert report.confidence_level == 0.95
        assert report.sample_size == 150
        assert isinstance(report.dtms_metrics, dict)
        assert isinstance(report.intelligent_metrics, dict)
        assert isinstance(report.performance_delta, dict)
        assert isinstance(report.recommendations, list)
        assert report.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
    
    def test_add_metrics(self):
        """Test adding metrics"""
        initial_count = len(self.validator.metrics)
        
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=100,
            intelligent_trades=95,
            dtms_win_rate=0.75,
            intelligent_win_rate=0.70,
            dtms_avg_rr=2.5,
            intelligent_avg_rr=2.3,
            dtms_max_drawdown=0.05,
            intelligent_max_drawdown=0.06,
            dtms_latency_ms=50.0,
            intelligent_latency_ms=60.0,
            confidence_delta=0.05
        )
        
        self.validator.add_metrics(metrics)
        
        assert len(self.validator.metrics) == initial_count + 1
        assert self.validator.metrics[-1] == metrics
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary"""
        # Test with no data
        summary = self.validator.get_metrics_summary()
        assert summary["total_metrics"] == 0
        
        # Add some data
        for i in range(10):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        summary = self.validator.get_metrics_summary()
        
        assert summary["total_metrics"] == 10
        assert summary["total_dtms_trades"] > 0
        assert summary["total_intelligent_trades"] > 0
        assert summary["avg_dtms_win_rate"] > 0.0
        assert summary["avg_intelligent_win_rate"] > 0.0
        assert summary["avg_confidence_delta"] > 0.0

class TestShadowModeValidator:
    """Test shadow mode validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ShadowModeValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.readiness_validator, ShadowModeReadinessValidator)
        assert self.validator.start_time > 0
        assert len(self.validator.validation_results) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_shadow_mode(self):
        """Test shadow mode validation"""
        validation = self.validator.validate_shadow_mode()
        
        assert isinstance(validation, ShadowModeValidation)
        assert validation.timestamp > 0
        assert validation.readiness_level in [ShadowModeReadiness.READY, ShadowModeReadiness.PREPARING,
                                            ShadowModeReadiness.TESTING, ShadowModeReadiness.NOT_READY]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert 0.0 <= validation.readiness_score <= 1.0
        assert isinstance(validation.recommendations, list)
        assert isinstance(validation.validation_details, dict)
    
    def test_add_metrics(self):
        """Test adding metrics"""
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=100,
            intelligent_trades=95,
            dtms_win_rate=0.75,
            intelligent_win_rate=0.70,
            dtms_avg_rr=2.5,
            intelligent_avg_rr=2.3,
            dtms_max_drawdown=0.05,
            intelligent_max_drawdown=0.06,
            dtms_latency_ms=50.0,
            intelligent_latency_ms=60.0,
            confidence_delta=0.05
        )
        
        self.validator.add_metrics(metrics)
        
        # Check that metrics were added to readiness validator
        assert len(self.validator.readiness_validator.metrics) == 1
        assert self.validator.readiness_validator.metrics[0] == metrics
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Run a few validations
        for i in range(3):
            self.validator.validate_shadow_mode()
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for validation in history:
            assert isinstance(validation, ShadowModeValidation)
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary"""
        # Add some metrics
        for i in range(5):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            self.validator.add_metrics(metrics)
        
        summary = self.validator.get_metrics_summary()
        
        assert isinstance(summary, dict)
        assert "total_metrics" in summary
        assert summary["total_metrics"] == 5
    
    def test_reset_metrics(self):
        """Test resetting metrics"""
        # Add some data
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=100,
            intelligent_trades=95,
            dtms_win_rate=0.75,
            intelligent_win_rate=0.70,
            dtms_avg_rr=2.5,
            intelligent_avg_rr=2.3,
            dtms_max_drawdown=0.05,
            intelligent_max_drawdown=0.06,
            dtms_latency_ms=50.0,
            intelligent_latency_ms=60.0,
            confidence_delta=0.05
        )
        self.validator.add_metrics(metrics)
        self.validator.validate_shadow_mode()
        
        # Reset metrics
        self.validator.reset_metrics()
        
        assert len(self.validator.readiness_validator.metrics) == 0
        assert len(self.validator.validation_results) == 0

class TestGlobalFunctions:
    """Test global shadow mode functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.shadow_mode_validation
        infra.shadow_mode_validation._shadow_mode_validator = None
    
    def test_get_shadow_mode_validator(self):
        """Test global validator access"""
        validator1 = get_shadow_mode_validator()
        validator2 = get_shadow_mode_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, ShadowModeValidator)
    
    def test_validate_shadow_mode_global(self):
        """Test global shadow mode validation"""
        validation = validate_shadow_mode()
        
        assert isinstance(validation, ShadowModeValidation)
        assert validation.timestamp > 0
        assert validation.readiness_level in [ShadowModeReadiness.READY, ShadowModeReadiness.PREPARING,
                                            ShadowModeReadiness.TESTING, ShadowModeReadiness.NOT_READY]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert 0.0 <= validation.readiness_score <= 1.0
        assert isinstance(validation.recommendations, list)
        assert isinstance(validation.validation_details, dict)
    
    def test_add_shadow_mode_metrics_global(self):
        """Test global shadow mode metrics addition"""
        metrics = ShadowModeMetrics(
            timestamp=time.time(),
            dtms_trades=100,
            intelligent_trades=95,
            dtms_win_rate=0.75,
            intelligent_win_rate=0.70,
            dtms_avg_rr=2.5,
            intelligent_avg_rr=2.3,
            dtms_max_drawdown=0.05,
            intelligent_max_drawdown=0.06,
            dtms_latency_ms=50.0,
            intelligent_latency_ms=60.0,
            confidence_delta=0.05
        )
        
        add_shadow_mode_metrics(metrics)
        
        # Check that metrics were added
        validator = get_shadow_mode_validator()
        assert len(validator.readiness_validator.metrics) == 1
        assert validator.readiness_validator.metrics[0] == metrics
    
    def test_get_shadow_mode_metrics_summary_global(self):
        """Test global shadow mode metrics summary"""
        # Add some metrics
        for i in range(3):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            add_shadow_mode_metrics(metrics)
        
        summary = get_shadow_mode_metrics_summary()
        
        assert isinstance(summary, dict)
        assert "total_metrics" in summary
        assert summary["total_metrics"] == 3

class TestShadowModeValidationIntegration:
    """Integration tests for shadow mode validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.shadow_mode_validation
        infra.shadow_mode_validation._shadow_mode_validator = None
    
    def test_comprehensive_shadow_mode_analysis(self):
        """Test comprehensive shadow mode analysis workflow"""
        # Add sufficient metrics for validation
        for i in range(150):  # More than minimum sample size
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75 + (i % 10) * 0.01,
                intelligent_win_rate=0.70 + (i % 10) * 0.01,
                dtms_avg_rr=2.5 + (i % 5) * 0.1,
                intelligent_avg_rr=2.3 + (i % 5) * 0.1,
                dtms_max_drawdown=0.05 + (i % 3) * 0.01,
                intelligent_max_drawdown=0.06 + (i % 3) * 0.01,
                dtms_latency_ms=50.0 + (i % 10) * 2.0,
                intelligent_latency_ms=60.0 + (i % 10) * 2.0,
                confidence_delta=0.05 + (i % 5) * 0.01
            )
            add_shadow_mode_metrics(metrics)
        
        # Validate shadow mode
        validation = validate_shadow_mode()
        
        assert isinstance(validation, ShadowModeValidation)
        assert validation.timestamp > 0
        assert validation.readiness_level in [ShadowModeReadiness.READY, ShadowModeReadiness.PREPARING,
                                            ShadowModeReadiness.TESTING, ShadowModeReadiness.NOT_READY]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert 0.0 <= validation.readiness_score <= 1.0
        assert isinstance(validation.recommendations, list)
        assert isinstance(validation.validation_details, dict)
        
        # Check validation details
        assert validation.validation_details["sample_size"] == 150
        assert validation.validation_details["dtms_trades"] > 0
        assert validation.validation_details["intelligent_trades"] > 0
        assert validation.validation_details["avg_dtms_win_rate"] > 0.0
        assert validation.validation_details["avg_intelligent_win_rate"] > 0.0
    
    def test_readiness_level_detection(self):
        """Test readiness level detection"""
        # Test with insufficient data
        validation = validate_shadow_mode()
        assert validation.readiness_level == ShadowModeReadiness.NOT_READY
        assert validation.validation_status == ValidationStatus.FAILED
        
        # Add sufficient data
        for i in range(150):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            add_shadow_mode_metrics(metrics)
        
        validation = validate_shadow_mode()
        
        # Should be ready or preparing with sufficient data
        assert validation.readiness_level in [ShadowModeReadiness.READY, ShadowModeReadiness.PREPARING,
                                            ShadowModeReadiness.TESTING]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
        assert validation.readiness_score > 0.0
    
    def test_comparison_report_generation(self):
        """Test comparison report generation"""
        # Add sufficient data for comparison
        for i in range(150):
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75 + (i % 10) * 0.01,
                intelligent_win_rate=0.70 + (i % 10) * 0.01,
                dtms_avg_rr=2.5 + (i % 5) * 0.1,
                intelligent_avg_rr=2.3 + (i % 5) * 0.1,
                dtms_max_drawdown=0.05 + (i % 3) * 0.01,
                intelligent_max_drawdown=0.06 + (i % 3) * 0.01,
                dtms_latency_ms=50.0 + (i % 10) * 2.0,
                intelligent_latency_ms=60.0 + (i % 10) * 2.0,
                confidence_delta=0.05 + (i % 5) * 0.01
            )
            add_shadow_mode_metrics(metrics)
        
        validation = validate_shadow_mode()
        
        # Check if comparison report was generated
        if validation.comparison_report:
            report = validation.comparison_report
            assert report.comparison_result in [ComparisonResult.DTMS_BETTER, ComparisonResult.INTELLIGENT_BETTER,
                                              ComparisonResult.EQUIVALENT, ComparisonResult.INSUFFICIENT_DATA]
            assert 0.0 <= report.statistical_significance <= 1.0
            assert report.confidence_level == 0.95
            assert report.sample_size == 150
            assert isinstance(report.dtms_metrics, dict)
            assert isinstance(report.intelligent_metrics, dict)
            assert isinstance(report.performance_delta, dict)
            assert isinstance(report.recommendations, list)
            assert report.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        # Add some metrics
        for i in range(50):  # Insufficient data
            metrics = ShadowModeMetrics(
                timestamp=time.time() + i,
                dtms_trades=10 + i,
                intelligent_trades=8 + i,
                dtms_win_rate=0.75,
                intelligent_win_rate=0.70,
                dtms_avg_rr=2.5,
                intelligent_avg_rr=2.3,
                dtms_max_drawdown=0.05,
                intelligent_max_drawdown=0.06,
                dtms_latency_ms=50.0,
                intelligent_latency_ms=60.0,
                confidence_delta=0.05
            )
            add_shadow_mode_metrics(metrics)
        
        validation = validate_shadow_mode()
        
        # Check recommendations
        assert isinstance(validation.recommendations, list)
        assert len(validation.recommendations) > 0
        assert all(isinstance(rec, str) for rec in validation.recommendations)
        
        # Should have recommendation about insufficient data
        assert any("Insufficient data" in rec or "not ready" in rec.lower() for rec in validation.recommendations)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
