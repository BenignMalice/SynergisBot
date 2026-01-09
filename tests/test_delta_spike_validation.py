"""
Comprehensive tests for delta spike validation system

Tests delta spike detection validation >90% accuracy, real-time delta spike
detection validation, historical delta spike accuracy assessment, precision and
recall validation, false positive/negative analysis, market movement correlation
validation, statistical significance testing, and performance benchmarking.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque

from infra.delta_spike_validation import (
    DeltaSpikeDetectionValidator, DeltaSpikeValidator,
    DeltaSpikeAccuracyLevel, DeltaSpikeValidationStatus, DeltaSpikeType, DeltaSpikeStrength,
    DeltaTick, DeltaSpike, DeltaSpikeValidation, DeltaSpikeValidationReport,
    get_delta_spike_validator, validate_delta_spike_detection,
    generate_delta_spike_validation_report, get_delta_spike_validation_summary
)

class TestDeltaSpikeAccuracyLevel:
    """Test delta spike accuracy level enumeration"""
    
    def test_accuracy_levels(self):
        """Test all accuracy levels"""
        levels = [
            DeltaSpikeAccuracyLevel.EXCELLENT,
            DeltaSpikeAccuracyLevel.GOOD,
            DeltaSpikeAccuracyLevel.ACCEPTABLE,
            DeltaSpikeAccuracyLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, DeltaSpikeAccuracyLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestDeltaSpikeValidationStatus:
    """Test delta spike validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            DeltaSpikeValidationStatus.PASSED,
            DeltaSpikeValidationStatus.WARNING,
            DeltaSpikeValidationStatus.FAILED,
            DeltaSpikeValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, DeltaSpikeValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestDeltaSpikeType:
    """Test delta spike type enumeration"""
    
    def test_spike_types(self):
        """Test all spike types"""
        types = [
            DeltaSpikeType.BUY_SPIKE,
            DeltaSpikeType.SELL_SPIKE,
            DeltaSpikeType.NEUTRAL,
            DeltaSpikeType.MIXED
        ]
        
        for spike_type in types:
            assert isinstance(spike_type, DeltaSpikeType)
            assert spike_type.value in ["buy_spike", "sell_spike", "neutral", "mixed"]

class TestDeltaSpikeStrength:
    """Test delta spike strength enumeration"""
    
    def test_spike_strengths(self):
        """Test all spike strengths"""
        strengths = [
            DeltaSpikeStrength.WEAK,
            DeltaSpikeStrength.MODERATE,
            DeltaSpikeStrength.STRONG,
            DeltaSpikeStrength.EXTREME
        ]
        
        for strength in strengths:
            assert isinstance(strength, DeltaSpikeStrength)
            assert strength.value in ["weak", "moderate", "strong", "extreme"]

class TestDeltaTick:
    """Test delta tick data structure"""
    
    def test_delta_tick_creation(self):
        """Test delta tick creation"""
        tick = DeltaTick(
            timestamp=time.time(),
            price=50000.0,
            volume=1.5,
            direction=1,  # Buy
            symbol="BTCUSDc",
            source="mt5",
            session_id="session_001",
            metadata={"exchange": "MT5", "spread": 2.5}
        )
        
        assert tick.timestamp > 0
        assert tick.price == 50000.0
        assert tick.volume == 1.5
        assert tick.direction == 1
        assert tick.symbol == "BTCUSDc"
        assert tick.source == "mt5"
        assert tick.session_id == "session_001"
        assert tick.metadata["exchange"] == "MT5"
        assert tick.metadata["spread"] == 2.5
    
    def test_delta_tick_defaults(self):
        """Test delta tick defaults"""
        tick = DeltaTick(
            timestamp=time.time(),
            price=100.0,
            volume=1.0,
            direction=-1,  # Sell
            symbol="EURUSDc",
            source="binance",
            session_id="session_002"
        )
        
        assert tick.metadata == {}

class TestDeltaSpike:
    """Test delta spike data structure"""
    
    def test_delta_spike_creation(self):
        """Test delta spike creation"""
        spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001",
            metadata={"detection_method": "volume_analysis", "market_condition": "volatile"}
        )
        
        assert spike.timestamp > 0
        assert spike.start_time < spike.end_time
        assert spike.spike_type == DeltaSpikeType.BUY_SPIKE
        assert spike.spike_strength == DeltaSpikeStrength.STRONG
        assert spike.volume_delta == 1000.0
        assert spike.price_change == 50.0
        assert spike.confidence == 0.95
        assert spike.symbol == "BTCUSDc"
        assert spike.session_id == "session_001"
        assert spike.metadata["detection_method"] == "volume_analysis"
        assert spike.metadata["market_condition"] == "volatile"
    
    def test_delta_spike_defaults(self):
        """Test delta spike defaults"""
        spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 30,
            end_time=time.time(),
            spike_type=DeltaSpikeType.SELL_SPIKE,
            spike_strength=DeltaSpikeStrength.MODERATE,
            volume_delta=500.0,
            price_change=-25.0,
            confidence=0.85,
            symbol="EURUSDc",
            session_id="session_002"
        )
        
        assert spike.metadata == {}

class TestDeltaSpikeValidation:
    """Test delta spike validation data structure"""
    
    def test_delta_spike_validation_creation(self):
        """Test delta spike validation creation"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = DeltaSpikeValidation(
            timestamp=time.time(),
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike,
            is_correct=True,
            accuracy_score=0.95,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            false_positive=False,
            false_negative=False,
            validation_status=DeltaSpikeValidationStatus.PASSED,
            metadata={"validation_time": time.time()}
        )
        
        assert validation.timestamp > 0
        assert validation.symbol == "BTCUSDc"
        assert validation.expected_spike == expected_spike
        assert validation.detected_spike == detected_spike
        assert validation.is_correct is True
        assert validation.accuracy_score == 0.95
        assert validation.precision == 1.0
        assert validation.recall == 1.0
        assert validation.f1_score == 1.0
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.validation_status == DeltaSpikeValidationStatus.PASSED
        assert validation.metadata["validation_time"] > 0
    
    def test_delta_spike_validation_defaults(self):
        """Test delta spike validation defaults"""
        validation = DeltaSpikeValidation(
            timestamp=time.time(),
            symbol="EURUSDc",
            expected_spike=None,
            detected_spike=None,
            is_correct=True,
            accuracy_score=1.0,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            false_positive=False,
            false_negative=False,
            validation_status=DeltaSpikeValidationStatus.PASSED
        )
        
        assert validation.metadata == {}

class TestDeltaSpikeValidationReport:
    """Test delta spike validation report data structure"""
    
    def test_delta_spike_validation_report_creation(self):
        """Test delta spike validation report creation"""
        report = DeltaSpikeValidationReport(
            timestamp=time.time(),
            symbol="BTCUSDc",
            overall_accuracy=0.95,
            precision=0.92,
            recall=0.98,
            f1_score=0.95,
            accuracy_level=DeltaSpikeAccuracyLevel.EXCELLENT,
            validation_status=DeltaSpikeValidationStatus.PASSED,
            total_validations=100,
            correct_detections=95,
            false_positives=3,
            false_negatives=2,
            true_positives=93,
            true_negatives=2,
            spike_type_accuracy={"buy_spike": 0.96, "sell_spike": 0.94},
            strength_accuracy={"strong": 0.95, "moderate": 0.90},
            recommendations=["Delta spike detection validation passed successfully"],
            detailed_validations=[],
            metadata={"accuracy_threshold": 0.90, "confidence_level": 0.95}
        )
        
        assert report.timestamp > 0
        assert report.symbol == "BTCUSDc"
        assert report.overall_accuracy == 0.95
        assert report.precision == 0.92
        assert report.recall == 0.98
        assert report.f1_score == 0.95
        assert report.accuracy_level == DeltaSpikeAccuracyLevel.EXCELLENT
        assert report.validation_status == DeltaSpikeValidationStatus.PASSED
        assert report.total_validations == 100
        assert report.correct_detections == 95
        assert report.false_positives == 3
        assert report.false_negatives == 2
        assert report.true_positives == 93
        assert report.true_negatives == 2
        assert report.spike_type_accuracy["buy_spike"] == 0.96
        assert report.strength_accuracy["strong"] == 0.95
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["accuracy_threshold"] == 0.90
    
    def test_delta_spike_validation_report_defaults(self):
        """Test delta spike validation report defaults"""
        report = DeltaSpikeValidationReport(
            timestamp=time.time(),
            symbol="EURUSDc",
            overall_accuracy=0.85,
            precision=0.80,
            recall=0.90,
            f1_score=0.85,
            accuracy_level=DeltaSpikeAccuracyLevel.GOOD,
            validation_status=DeltaSpikeValidationStatus.WARNING,
            total_validations=50,
            correct_detections=42,
            false_positives=5,
            false_negatives=3,
            true_positives=40,
            true_negatives=2,
            spike_type_accuracy={"buy_spike": 0.85},
            strength_accuracy={"moderate": 0.80},
            recommendations=["Delta spike detection validation passed with warnings"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestDeltaSpikeValidator:
    """Test delta spike validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DeltaSpikeValidator(accuracy_threshold=0.90)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.accuracy_threshold == 0.90
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.min_sample_size == 100
        assert self.validator.confidence_level == 0.95
    
    def test_validate_delta_spike_detection_correct(self):
        """Test delta spike detection validation with correct detection"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike
        )
        
        assert validation.symbol == "BTCUSDc"
        assert validation.expected_spike == expected_spike
        assert validation.detected_spike == detected_spike
        assert validation.is_correct is True
        assert validation.accuracy_score > 0.9
        assert validation.precision == 1.0
        assert validation.recall == 1.0
        assert validation.f1_score == 1.0
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.validation_status == DeltaSpikeValidationStatus.PASSED
        assert validation.metadata["accuracy_threshold"] == 0.90
    
    def test_validate_delta_spike_detection_false_positive(self):
        """Test delta spike detection validation with false positive"""
        expected_spike = None  # No expected spike
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.MODERATE,
            volume_delta=500.0,
            price_change=25.0,
            confidence=0.85,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike
        )
        
        assert validation.is_correct is False
        assert validation.accuracy_score == 0.0
        assert validation.precision == 0.0
        assert validation.recall == 1.0  # No expected spike, so recall is 1.0
        assert validation.f1_score == 0.0
        assert validation.false_positive is True
        assert validation.false_negative is False
        assert validation.validation_status == DeltaSpikeValidationStatus.FAILED
    
    def test_validate_delta_spike_detection_false_negative(self):
        """Test delta spike detection validation with false negative"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.SELL_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=800.0,
            price_change=-40.0,
            confidence=0.90,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = None  # No detected spike
        
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike
        )
        
        assert validation.is_correct is False
        assert validation.accuracy_score == 0.0
        assert validation.precision == 1.0  # No detected spike, so precision is 1.0
        assert validation.recall == 0.0
        assert validation.f1_score == 0.0
        assert validation.false_positive is False
        assert validation.false_negative is True
        assert validation.validation_status == DeltaSpikeValidationStatus.FAILED
    
    def test_validate_delta_spike_detection_both_none(self):
        """Test delta spike detection validation with both None"""
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=None,
            detected_spike=None
        )
        
        assert validation.is_correct is True
        assert validation.accuracy_score == 1.0
        assert validation.precision == 1.0
        assert validation.recall == 1.0
        assert validation.f1_score == 1.0
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.validation_status == DeltaSpikeValidationStatus.PASSED
    
    def test_validate_delta_spike_detection_wrong_type(self):
        """Test delta spike detection validation with wrong spike type"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.SELL_SPIKE,  # Wrong type
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=-48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike
        )
        
        assert validation.is_correct is False
        assert validation.accuracy_score < 1.0  # Should be less than 1.0 due to wrong type
        assert validation.precision == 0.0
        assert validation.recall == 0.0
        assert validation.f1_score == 0.0
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.validation_status == DeltaSpikeValidationStatus.FAILED
    
    def test_calculate_strength_similarity(self):
        """Test strength similarity calculation"""
        # Same strength
        similarity = self.validator._calculate_strength_similarity(
            DeltaSpikeStrength.STRONG, DeltaSpikeStrength.STRONG
        )
        assert similarity == 1.0
        
        # Adjacent strengths
        similarity = self.validator._calculate_strength_similarity(
            DeltaSpikeStrength.MODERATE, DeltaSpikeStrength.STRONG
        )
        assert 0.0 < similarity < 1.0
        
        # Distant strengths
        similarity = self.validator._calculate_strength_similarity(
            DeltaSpikeStrength.WEAK, DeltaSpikeStrength.EXTREME
        )
        assert similarity < 0.5
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(10):
            expected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE if i % 2 == 0 else DeltaSpikeType.SELL_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG if i < 5 else DeltaSpikeStrength.MODERATE,
                volume_delta=1000.0 + i * 100,
                price_change=50.0 + i * 5,
                confidence=0.95 - i * 0.01,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            detected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=expected_spike.spike_type,  # Correct type
                spike_strength=expected_spike.spike_strength,  # Correct strength
                volume_delta=expected_spike.volume_delta * 0.95,  # Slightly different
                price_change=expected_spike.price_change * 0.96,  # Slightly different
                confidence=expected_spike.confidence * 0.98,  # Slightly different
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            self.validator.validate_delta_spike_detection(
                symbol="BTCUSDc",
                expected_spike=expected_spike,
                detected_spike=detected_spike
            )
        
        report = self.validator.generate_validation_report("BTCUSDc")
        
        assert report.symbol == "BTCUSDc"
        assert report.total_validations == 10
        assert report.correct_detections == 10
        assert report.false_positives == 0
        assert report.false_negatives == 0
        assert report.overall_accuracy == 1.0
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.f1_score == 1.0
        assert report.accuracy_level == DeltaSpikeAccuracyLevel.EXCELLENT
        assert report.validation_status == DeltaSpikeValidationStatus.PASSED
        assert len(report.detailed_validations) == 10
        assert len(report.recommendations) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report("UNKNOWN")
        
        assert report.symbol == "UNKNOWN"
        assert report.overall_accuracy == 0.0
        assert report.precision == 0.0
        assert report.recall == 0.0
        assert report.f1_score == 0.0
        assert report.accuracy_level == DeltaSpikeAccuracyLevel.POOR
        assert report.validation_status == DeltaSpikeValidationStatus.FAILED
        assert report.total_validations == 0
        assert report.correct_detections == 0
        assert report.false_positives == 0
        assert report.false_negatives == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Test with no data
        summary = self.validator.get_validation_summary()
        assert summary["total_validations"] == 0
        
        # Add some validations
        for i in range(5):
            expected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=1000.0,
                price_change=50.0,
                confidence=0.95,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            detected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=950.0,
                price_change=48.0,
                confidence=0.92,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            self.validator.validate_delta_spike_detection(
                symbol="BTCUSDc",
                expected_spike=expected_spike,
                detected_spike=detected_spike
            )
        
        summary = self.validator.get_validation_summary()
        
        assert summary["total_validations"] == 5
        assert summary["correct_detections"] == 5
        assert summary["false_positives"] == 0
        assert summary["false_negatives"] == 0
        assert summary["overall_accuracy"] == 1.0
        assert summary["average_precision"] == 1.0
        assert summary["average_recall"] == 1.0
        assert summary["average_f1_score"] == 1.0
        assert summary["accuracy_threshold"] == 0.90

class TestDeltaSpikeDetectionValidator:
    """Test delta spike detection validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DeltaSpikeDetectionValidator(accuracy_threshold=0.90)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.validator, DeltaSpikeValidator)
        assert self.validator.validator.accuracy_threshold == 0.90
        assert self.validator.start_time > 0
        assert len(self.validator.validation_reports) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_delta_spike_detection(self):
        """Test delta spike detection validation"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=expected_spike,
            detected_spike=detected_spike
        )
        
        assert isinstance(validation, DeltaSpikeValidation)
        assert validation.symbol == "BTCUSDc"
        assert validation.expected_spike == expected_spike
        assert validation.detected_spike == detected_spike
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            expected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=1000.0,
                price_change=50.0,
                confidence=0.95,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            detected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=950.0,
                price_change=48.0,
                confidence=0.92,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            self.validator.validate_delta_spike_detection(
                symbol="BTCUSDc",
                expected_spike=expected_spike,
                detected_spike=detected_spike
            )
        
        report = self.validator.generate_validation_report("BTCUSDc")
        
        assert isinstance(report, DeltaSpikeValidationReport)
        assert report.symbol == "BTCUSDc"
        assert report.total_validations == 3
        
        # Check that report was added to history
        assert len(self.validator.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            self.validator.validate_delta_spike_detection(
                symbol="BTCUSDc",
                expected_spike=None,
                detected_spike=None
            )
            self.validator.generate_validation_report("BTCUSDc")
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, DeltaSpikeValidationReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            self.validator.validate_delta_spike_detection(
                symbol="BTCUSDc",
                expected_spike=None,
                detected_spike=None
            )
        
        summary = self.validator.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        self.validator.validate_delta_spike_detection(
            symbol="BTCUSDc",
            expected_spike=None,
            detected_spike=None
        )
        self.validator.generate_validation_report("BTCUSDc")
        
        # Reset validations
        self.validator.reset_validations()
        
        assert len(self.validator.validator.validations) == 0
        assert len(self.validator.validation_reports) == 0

class TestGlobalFunctions:
    """Test global delta spike functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.delta_spike_validation
        infra.delta_spike_validation._delta_spike_validator = None
    
    def test_get_delta_spike_validator(self):
        """Test global validator access"""
        validator1 = get_delta_spike_validator()
        validator2 = get_delta_spike_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, DeltaSpikeDetectionValidator)
    
    def test_validate_delta_spike_detection_global(self):
        """Test global delta spike detection validation"""
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
        
        assert isinstance(validation, DeltaSpikeValidation)
        assert validation.symbol == "BTCUSDc"
        assert validation.expected_spike == expected_spike
        assert validation.detected_spike == detected_spike
    
    def test_generate_delta_spike_validation_report_global(self):
        """Test global delta spike validation report generation"""
        # Add some validations first
        for i in range(3):
            expected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=1000.0,
                price_change=50.0,
                confidence=0.95,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            detected_spike = DeltaSpike(
                timestamp=time.time() + i,
                start_time=time.time() + i - 60,
                end_time=time.time() + i,
                spike_type=DeltaSpikeType.BUY_SPIKE,
                spike_strength=DeltaSpikeStrength.STRONG,
                volume_delta=950.0,
                price_change=48.0,
                confidence=0.92,
                symbol="BTCUSDc",
                session_id="session_001"
            )
            
            validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
        
        report = generate_delta_spike_validation_report("BTCUSDc")
        
        assert isinstance(report, DeltaSpikeValidationReport)
        assert report.symbol == "BTCUSDc"
        assert report.total_validations == 3
    
    def test_get_delta_spike_validation_summary_global(self):
        """Test global delta spike validation summary"""
        # Add some validations
        for i in range(5):
            validate_delta_spike_detection("BTCUSDc", None, None)
        
        summary = get_delta_spike_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestDeltaSpikeValidationIntegration:
    """Integration tests for delta spike validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.delta_spike_validation
        infra.delta_spike_validation._delta_spike_validator = None
    
    def test_comprehensive_delta_spike_validation(self):
        """Test comprehensive delta spike validation workflow"""
        # Test multiple spike types and strengths
        spike_types = [DeltaSpikeType.BUY_SPIKE, DeltaSpikeType.SELL_SPIKE, DeltaSpikeType.NEUTRAL]
        spike_strengths = [DeltaSpikeStrength.WEAK, DeltaSpikeStrength.MODERATE, 
                          DeltaSpikeStrength.STRONG, DeltaSpikeStrength.EXTREME]
        
        for spike_type in spike_types:
            for strength in spike_strengths:
                expected_spike = DeltaSpike(
                    timestamp=time.time(),
                    start_time=time.time() - 60,
                    end_time=time.time(),
                    spike_type=spike_type,
                    spike_strength=strength,
                    volume_delta=1000.0,
                    price_change=50.0,
                    confidence=0.95,
                    symbol="BTCUSDc",
                    session_id="session_001"
                )
                
                detected_spike = DeltaSpike(
                    timestamp=time.time(),
                    start_time=time.time() - 60,
                    end_time=time.time(),
                    spike_type=spike_type,
                    spike_strength=strength,
                    volume_delta=950.0,
                    price_change=48.0,
                    confidence=0.92,
                    symbol="BTCUSDc",
                    session_id="session_001"
                )
                
                validation = validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
                
                assert isinstance(validation, DeltaSpikeValidation)
                assert validation.symbol == "BTCUSDc"
                assert validation.expected_spike == expected_spike
                assert validation.detected_spike == detected_spike
                assert validation.is_correct is True
                assert validation.validation_status == DeltaSpikeValidationStatus.PASSED
        
        # Generate validation report
        report = generate_delta_spike_validation_report("BTCUSDc")
        
        assert isinstance(report, DeltaSpikeValidationReport)
        assert report.symbol == "BTCUSDc"
        assert report.total_validations == len(spike_types) * len(spike_strengths)
        assert report.overall_accuracy == 1.0
        assert report.accuracy_level == DeltaSpikeAccuracyLevel.EXCELLENT
        assert report.validation_status == DeltaSpikeValidationStatus.PASSED
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) == len(spike_types) * len(spike_strengths)
    
    def test_accuracy_threshold_validation(self):
        """Test accuracy threshold validation"""
        # Test with high accuracy (should pass)
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
        
        assert validation.validation_status == DeltaSpikeValidationStatus.PASSED
        assert validation.accuracy_score > 0.90
        
        # Test with low accuracy (should fail)
        wrong_detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.SELL_SPIKE,  # Wrong type
            spike_strength=DeltaSpikeStrength.WEAK,  # Wrong strength
            volume_delta=500.0,
            price_change=-25.0,
            confidence=0.70,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = validate_delta_spike_detection("BTCUSDc", expected_spike, wrong_detected_spike)
        
        assert validation.validation_status == DeltaSpikeValidationStatus.FAILED
        assert validation.accuracy_score < 0.90
    
    def test_precision_recall_validation(self):
        """Test precision and recall validation"""
        # Test true positive
        expected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=1000.0,
            price_change=50.0,
            confidence=0.95,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        detected_spike = DeltaSpike(
            timestamp=time.time(),
            start_time=time.time() - 60,
            end_time=time.time(),
            spike_type=DeltaSpikeType.BUY_SPIKE,
            spike_strength=DeltaSpikeStrength.STRONG,
            volume_delta=950.0,
            price_change=48.0,
            confidence=0.92,
            symbol="BTCUSDc",
            session_id="session_001"
        )
        
        validation = validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
        
        assert validation.precision == 1.0
        assert validation.recall == 1.0
        assert validation.f1_score == 1.0
        assert validation.false_positive is False
        assert validation.false_negative is False
        
        # Test false positive
        validation = validate_delta_spike_detection("BTCUSDc", None, detected_spike)
        
        assert validation.precision == 0.0
        assert validation.recall == 1.0
        assert validation.f1_score == 0.0
        assert validation.false_positive is True
        assert validation.false_negative is False
        
        # Test false negative
        validation = validate_delta_spike_detection("BTCUSDc", expected_spike, None)
        
        assert validation.precision == 1.0
        assert validation.recall == 0.0
        assert validation.f1_score == 0.0
        assert validation.false_positive is False
        assert validation.false_negative is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
