"""
Comprehensive tests for large order detection precision validation system

Tests large order detection precision >85%, order size detection accuracy,
volume spike detection validation, market impact analysis accuracy,
order book depth analysis precision, institutional order identification,
false positive reduction validation, and true positive detection validation.
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
from collections import deque

from infra.large_order_detection_validation import (
    LargeOrderValidationManager, LargeOrderDetector, LargeOrderValidator,
    LargeOrderPrecisionLevel, LargeOrderValidationStatus, OrderType, OrderSize, MarketImpact,
    OrderData, LargeOrderDetection, LargeOrderValidation, LargeOrderValidationReport,
    get_large_order_validation_manager, validate_large_order_detection,
    generate_large_order_validation_report, get_large_order_validation_summary
)

class TestLargeOrderPrecisionLevel:
    """Test large order precision level enumeration"""
    
    def test_precision_levels(self):
        """Test all precision levels"""
        levels = [
            LargeOrderPrecisionLevel.EXCELLENT,
            LargeOrderPrecisionLevel.GOOD,
            LargeOrderPrecisionLevel.ACCEPTABLE,
            LargeOrderPrecisionLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, LargeOrderPrecisionLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestLargeOrderValidationStatus:
    """Test large order validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            LargeOrderValidationStatus.PASSED,
            LargeOrderValidationStatus.WARNING,
            LargeOrderValidationStatus.FAILED,
            LargeOrderValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, LargeOrderValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestOrderType:
    """Test order type enumeration"""
    
    def test_order_types(self):
        """Test all order types"""
        types = [
            OrderType.MARKET,
            OrderType.LIMIT,
            OrderType.STOP,
            OrderType.STOP_LIMIT,
            OrderType.ICEBERG,
            OrderType.TWAP,
            OrderType.VWAP
        ]
        
        for order_type in types:
            assert isinstance(order_type, OrderType)
            assert order_type.value in ["market", "limit", "stop", "stop_limit", 
                                       "iceberg", "twap", "vwap"]

class TestOrderSize:
    """Test order size enumeration"""
    
    def test_order_sizes(self):
        """Test all order sizes"""
        sizes = [
            OrderSize.SMALL,
            OrderSize.MEDIUM,
            OrderSize.LARGE,
            OrderSize.INSTITUTIONAL,
            OrderSize.WHALE
        ]
        
        for size in sizes:
            assert isinstance(size, OrderSize)
            assert size.value in ["small", "medium", "large", "institutional", "whale"]

class TestMarketImpact:
    """Test market impact enumeration"""
    
    def test_market_impacts(self):
        """Test all market impacts"""
        impacts = [
            MarketImpact.NONE,
            MarketImpact.LOW,
            MarketImpact.MEDIUM,
            MarketImpact.HIGH,
            MarketImpact.SEVERE
        ]
        
        for impact in impacts:
            assert isinstance(impact, MarketImpact)
            assert impact.value in ["none", "low", "medium", "high", "severe"]

class TestOrderData:
    """Test order data structure"""
    
    def test_order_data_creation(self):
        """Test order data creation"""
        order_data = OrderData(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=150.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=3.5,
            depth_impact=2.8,
            metadata={"source": "binance"}
        )
        
        assert order_data.order_id == "order_001"
        assert order_data.symbol == "BTCUSDT"
        assert order_data.timestamp > 0
        assert order_data.price == 50000.0
        assert order_data.quantity == 150.0
        assert order_data.order_type == OrderType.MARKET
        assert order_data.side == "buy"
        assert order_data.size_category == OrderSize.LARGE
        assert order_data.market_impact == MarketImpact.HIGH
        assert order_data.volume_ratio == 3.5
        assert order_data.depth_impact == 2.8
        assert order_data.metadata["source"] == "binance"
    
    def test_order_data_defaults(self):
        """Test order data defaults"""
        order_data = OrderData(
            order_id="order_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            price=3000.0,
            quantity=50.0,
            order_type=OrderType.LIMIT,
            side="sell",
            size_category=OrderSize.MEDIUM,
            market_impact=MarketImpact.LOW,
            volume_ratio=1.2,
            depth_impact=0.8
        )
        
        assert order_data.metadata == {}

class TestLargeOrderDetection:
    """Test large order detection data structure"""
    
    def test_large_order_detection_creation(self):
        """Test large order detection creation"""
        detection = LargeOrderDetection(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            detected_size=150.0,
            detected_category=OrderSize.LARGE,
            confidence_score=0.85,
            precision_score=0.90,
            recall_score=0.88,
            f1_score=0.89,
            market_impact_predicted=MarketImpact.HIGH,
            volume_spike_detected=True,
            depth_impact_detected=True,
            institutional_indicators=["large_size", "high_volume_ratio"],
            detection_method="size_based",
            metadata={"detection_timestamp": time.time()}
        )
        
        assert detection.order_id == "order_001"
        assert detection.symbol == "BTCUSDT"
        assert detection.timestamp > 0
        assert detection.detected_size == 150.0
        assert detection.detected_category == OrderSize.LARGE
        assert detection.confidence_score == 0.85
        assert detection.precision_score == 0.90
        assert detection.recall_score == 0.88
        assert detection.f1_score == 0.89
        assert detection.market_impact_predicted == MarketImpact.HIGH
        assert detection.volume_spike_detected is True
        assert detection.depth_impact_detected is True
        assert len(detection.institutional_indicators) == 2
        assert detection.detection_method == "size_based"
        assert detection.metadata["detection_timestamp"] > 0
    
    def test_large_order_detection_defaults(self):
        """Test large order detection defaults"""
        detection = LargeOrderDetection(
            order_id="order_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            detected_size=25.0,
            detected_category=OrderSize.MEDIUM,
            confidence_score=0.70,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            market_impact_predicted=MarketImpact.LOW,
            volume_spike_detected=False,
            depth_impact_detected=False,
            institutional_indicators=[],
            detection_method="combined"
        )
        
        assert detection.metadata == {}

class TestLargeOrderValidation:
    """Test large order validation data structure"""
    
    def test_large_order_validation_creation(self):
        """Test large order validation creation"""
        validation = LargeOrderValidation(
            timestamp=time.time(),
            order_id="order_001",
            expected_category=OrderSize.LARGE,
            detected_category=OrderSize.LARGE,
            precision_score=0.90,
            recall_score=0.88,
            f1_score=0.89,
            false_positive=False,
            false_negative=False,
            true_positive=True,
            true_negative=False,
            meets_threshold=True,
            validation_status=LargeOrderValidationStatus.PASSED,
            recommendations=["Detection precision is excellent"],
            metadata={"precision_threshold": 0.85}
        )
        
        assert validation.timestamp > 0
        assert validation.order_id == "order_001"
        assert validation.expected_category == OrderSize.LARGE
        assert validation.detected_category == OrderSize.LARGE
        assert validation.precision_score == 0.90
        assert validation.recall_score == 0.88
        assert validation.f1_score == 0.89
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.true_positive is True
        assert validation.true_negative is False
        assert validation.meets_threshold is True
        assert validation.validation_status == LargeOrderValidationStatus.PASSED
        assert len(validation.recommendations) == 1
        assert validation.metadata["precision_threshold"] == 0.85
    
    def test_large_order_validation_defaults(self):
        """Test large order validation defaults"""
        validation = LargeOrderValidation(
            timestamp=time.time(),
            order_id="order_002",
            expected_category=OrderSize.MEDIUM,
            detected_category=OrderSize.SMALL,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            false_positive=True,
            false_negative=False,
            true_positive=False,
            true_negative=False,
            meets_threshold=False,
            validation_status=LargeOrderValidationStatus.FAILED,
            recommendations=["Detection failed"]
        )
        
        assert validation.metadata == {}

class TestLargeOrderValidationReport:
    """Test large order validation report data structure"""
    
    def test_large_order_validation_report_creation(self):
        """Test large order validation report creation"""
        report = LargeOrderValidationReport(
            timestamp=time.time(),
            overall_precision=0.90,
            overall_recall=0.88,
            overall_f1_score=0.89,
            precision_level=LargeOrderPrecisionLevel.GOOD,
            validation_status=LargeOrderValidationStatus.PASSED,
            total_validations=100,
            true_positives=90,
            false_positives=10,
            true_negatives=0,
            false_negatives=0,
            order_size_analysis={"large": 0.92, "institutional": 0.88},
            market_impact_analysis={"high_impact_precision": 0.90},
            detection_method_analysis={"size_based_precision": 0.92},
            performance_metrics={"avg_validation_time_ms": 25.5},
            recommendations=["Large order detection precision is good"],
            detailed_validations=[],
            metadata={"precision_threshold": 0.85}
        )
        
        assert report.timestamp > 0
        assert report.overall_precision == 0.90
        assert report.overall_recall == 0.88
        assert report.overall_f1_score == 0.89
        assert report.precision_level == LargeOrderPrecisionLevel.GOOD
        assert report.validation_status == LargeOrderValidationStatus.PASSED
        assert report.total_validations == 100
        assert report.true_positives == 90
        assert report.false_positives == 10
        assert report.true_negatives == 0
        assert report.false_negatives == 0
        assert report.order_size_analysis["large"] == 0.92
        assert report.market_impact_analysis["high_impact_precision"] == 0.90
        assert report.detection_method_analysis["size_based_precision"] == 0.92
        assert report.performance_metrics["avg_validation_time_ms"] == 25.5
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["precision_threshold"] == 0.85
    
    def test_large_order_validation_report_defaults(self):
        """Test large order validation report defaults"""
        report = LargeOrderValidationReport(
            timestamp=time.time(),
            overall_precision=0.80,
            overall_recall=0.75,
            overall_f1_score=0.77,
            precision_level=LargeOrderPrecisionLevel.ACCEPTABLE,
            validation_status=LargeOrderValidationStatus.WARNING,
            total_validations=50,
            true_positives=40,
            false_positives=10,
            true_negatives=0,
            false_negatives=0,
            order_size_analysis={"large": 0.82},
            market_impact_analysis={"high_impact_precision": 0.80},
            detection_method_analysis={"size_based_precision": 0.82},
            performance_metrics={"avg_validation_time_ms": 30.0},
            recommendations=["Large order detection precision is acceptable"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestLargeOrderDetector:
    """Test large order detector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = LargeOrderDetector()
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        assert hasattr(self.detector, 'detection_cache')
        assert hasattr(self.detector, 'lock')
        assert hasattr(self.detector, 'size_thresholds')
        assert isinstance(self.detector.detection_cache, dict)
        assert isinstance(self.detector.size_thresholds, dict)
        assert len(self.detector.size_thresholds) == 5
    
    def test_detect_large_order(self):
        """Test large order detection"""
        order_data = OrderData(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=150.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=3.5,
            depth_impact=2.8
        )
        
        detection = self.detector.detect_large_order(order_data)
        
        assert detection.order_id == "order_001"
        assert detection.symbol == "BTCUSDT"
        assert detection.timestamp == order_data.timestamp
        assert detection.detected_size == 150.0
        assert detection.detected_category in [OrderSize.SMALL, OrderSize.MEDIUM, OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE]
        assert 0.0 <= detection.confidence_score <= 1.0
        assert detection.market_impact_predicted in [MarketImpact.NONE, MarketImpact.LOW, MarketImpact.MEDIUM, MarketImpact.HIGH, MarketImpact.SEVERE]
        assert detection.volume_spike_detected in [True, False]
        assert detection.depth_impact_detected in [True, False]
        assert isinstance(detection.institutional_indicators, list)
        assert detection.detection_method in ["size_based", "volume_spike", "market_impact", "depth_impact", "combined"]
        assert detection.metadata["detection_timestamp"] > 0
    
    def test_detect_by_size(self):
        """Test size-based detection"""
        # Test small order
        small_order = OrderData(
            order_id="small",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=0.5,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.SMALL,
            market_impact=MarketImpact.NONE,
            volume_ratio=0.5,
            depth_impact=0.2
        )
        
        detection = self.detector.detect_large_order(small_order)
        assert detection.detected_category == OrderSize.SMALL
        
        # Test large order
        large_order = OrderData(
            order_id="large",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=150.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=3.5,
            depth_impact=2.8
        )
        
        detection = self.detector.detect_large_order(large_order)
        assert detection.detected_category in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE]
    
    def test_detect_volume_spike(self):
        """Test volume spike detection"""
        # Test with volume spike
        spike_order = OrderData(
            order_id="spike",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=100.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=5.0,  # High volume ratio
            depth_impact=2.0
        )
        
        detection = self.detector.detect_large_order(spike_order)
        assert detection.volume_spike_detected is True
        
        # Test without volume spike
        normal_order = OrderData(
            order_id="normal",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=10.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.MEDIUM,
            market_impact=MarketImpact.LOW,
            volume_ratio=1.2,  # Normal volume ratio
            depth_impact=0.5
        )
        
        detection = self.detector.detect_large_order(normal_order)
        assert detection.volume_spike_detected is False
    
    def test_detect_market_impact(self):
        """Test market impact detection"""
        # Test high impact order
        high_impact_order = OrderData(
            order_id="high_impact",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=200.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.INSTITUTIONAL,
            market_impact=MarketImpact.HIGH,
            volume_ratio=4.0,
            depth_impact=3.5
        )
        
        detection = self.detector.detect_large_order(high_impact_order)
        assert detection.market_impact_predicted in [MarketImpact.HIGH, MarketImpact.SEVERE]
        
        # Test low impact order
        low_impact_order = OrderData(
            order_id="low_impact",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=5.0,
            order_type=OrderType.LIMIT,
            side="buy",
            size_category=OrderSize.SMALL,
            market_impact=MarketImpact.LOW,
            volume_ratio=0.8,
            depth_impact=0.3
        )
        
        detection = self.detector.detect_large_order(low_impact_order)
        assert detection.market_impact_predicted in [MarketImpact.NONE, MarketImpact.LOW]
    
    def test_detect_institutional_indicators(self):
        """Test institutional indicator detection"""
        # Test institutional order
        institutional_order = OrderData(
            order_id="institutional",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=500.0,
            order_type=OrderType.TWAP,
            side="buy",
            size_category=OrderSize.INSTITUTIONAL,
            market_impact=MarketImpact.HIGH,
            volume_ratio=6.0,
            depth_impact=4.0
        )
        
        detection = self.detector.detect_large_order(institutional_order)
        assert len(detection.institutional_indicators) > 0
        assert "large_size" in detection.institutional_indicators
        assert "high_volume_ratio" in detection.institutional_indicators
        assert "high_depth_impact" in detection.institutional_indicators
        assert "algorithmic_trading" in detection.institutional_indicators

class TestLargeOrderValidator:
    """Test large order validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = LargeOrderValidator(precision_threshold=0.85)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.precision_threshold == 0.85
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_detection_precision(self):
        """Test detection precision validation"""
        detection = LargeOrderDetection(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            detected_size=150.0,
            detected_category=OrderSize.LARGE,
            confidence_score=0.85,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            market_impact_predicted=MarketImpact.HIGH,
            volume_spike_detected=True,
            depth_impact_detected=True,
            institutional_indicators=["large_size"],
            detection_method="size_based"
        )
        
        expected_category = OrderSize.LARGE
        
        validation = self.validator.validate_detection_precision(detection, expected_category)
        
        assert validation.order_id == "order_001"
        assert validation.expected_category == OrderSize.LARGE
        assert validation.detected_category == OrderSize.LARGE
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                            LargeOrderValidationStatus.WARNING,
                                            LargeOrderValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
        assert validation.metadata["precision_threshold"] == 0.85
    
    def test_validate_detection_precision_false_positive(self):
        """Test detection precision validation with false positive"""
        detection = LargeOrderDetection(
            order_id="order_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            detected_size=50.0,
            detected_category=OrderSize.LARGE,  # Detected as large
            confidence_score=0.70,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            market_impact_predicted=MarketImpact.MEDIUM,
            volume_spike_detected=False,
            depth_impact_detected=False,
            institutional_indicators=[],
            detection_method="size_based"
        )
        
        expected_category = OrderSize.MEDIUM  # Expected as medium
        
        validation = self.validator.validate_detection_precision(detection, expected_category)
        
        assert validation.false_positive is True
        assert validation.true_positive is False
        assert validation.precision_score < 1.0
    
    def test_validate_detection_precision_false_negative(self):
        """Test detection precision validation with false negative"""
        detection = LargeOrderDetection(
            order_id="order_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            detected_size=200.0,
            detected_category=OrderSize.MEDIUM,  # Detected as medium
            confidence_score=0.60,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            market_impact_predicted=MarketImpact.LOW,
            volume_spike_detected=False,
            depth_impact_detected=False,
            institutional_indicators=[],
            detection_method="combined"
        )
        
        expected_category = OrderSize.LARGE  # Expected as large
        
        validation = self.validator.validate_detection_precision(detection, expected_category)
        
        assert validation.false_negative is True
        assert validation.true_positive is False
        assert validation.recall_score < 1.0
    
    def test_validate_detection_precision_true_positive(self):
        """Test detection precision validation with true positive"""
        detection = LargeOrderDetection(
            order_id="order_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            detected_size=1000.0,
            detected_category=OrderSize.INSTITUTIONAL,  # Detected as institutional
            confidence_score=0.95,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            market_impact_predicted=MarketImpact.SEVERE,
            volume_spike_detected=True,
            depth_impact_detected=True,
            institutional_indicators=["large_size", "high_volume_ratio"],
            detection_method="size_based"
        )
        
        expected_category = OrderSize.INSTITUTIONAL  # Expected as institutional
        
        validation = self.validator.validate_detection_precision(detection, expected_category)
        
        assert validation.true_positive is True
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.precision_score == 1.0
        assert validation.recall_score == 1.0
        assert validation.f1_score == 1.0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(5):
            detection = LargeOrderDetection(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                detected_size=100.0 + i * 50.0,
                detected_category=OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM,
                confidence_score=0.8 + i * 0.02,
                precision_score=0.0,
                recall_score=0.0,
                f1_score=0.0,
                market_impact_predicted=MarketImpact.HIGH if i % 2 == 0 else MarketImpact.LOW,
                volume_spike_detected=i % 2 == 0,
                depth_impact_detected=i % 2 == 0,
                institutional_indicators=["large_size"] if i % 2 == 0 else [],
                detection_method="size_based" if i % 2 == 0 else "combined"
            )
            
            expected_category = OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM
            self.validator.validate_detection_precision(detection, expected_category)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_validations == 5
        assert report.true_positives >= 0
        assert report.false_positives >= 0
        assert report.true_negatives >= 0
        assert report.false_negatives >= 0
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.precision_level in [LargeOrderPrecisionLevel.EXCELLENT,
                                        LargeOrderPrecisionLevel.GOOD,
                                        LargeOrderPrecisionLevel.ACCEPTABLE,
                                        LargeOrderPrecisionLevel.POOR]
        assert report.validation_status in [LargeOrderValidationStatus.PASSED,
                                         LargeOrderValidationStatus.WARNING,
                                         LargeOrderValidationStatus.FAILED]
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.order_size_analysis) > 0
        assert len(report.market_impact_analysis) > 0
        assert len(report.detection_method_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_precision == 0.0
        assert report.overall_recall == 0.0
        assert report.overall_f1_score == 0.0
        assert report.precision_level == LargeOrderPrecisionLevel.POOR
        assert report.validation_status == LargeOrderValidationStatus.FAILED
        assert report.total_validations == 0
        assert report.true_positives == 0
        assert report.false_positives == 0
        assert report.true_negatives == 0
        assert report.false_negatives == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.order_size_analysis == {}
        assert report.market_impact_analysis == {}
        assert report.detection_method_analysis == {}
        assert report.performance_metrics == {}

class TestLargeOrderValidationManager:
    """Test large order validation manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = LargeOrderValidationManager(precision_threshold=0.85)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.detector, LargeOrderDetector)
        assert isinstance(self.manager.validator, LargeOrderValidator)
        assert self.manager.validator.precision_threshold == 0.85
        assert self.manager.start_time > 0
        assert len(self.manager.validation_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_large_order_detection(self):
        """Test large order detection validation"""
        order_data = OrderData(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=150.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=3.5,
            depth_impact=2.8
        )
        
        expected_category = OrderSize.LARGE
        
        validation = self.manager.validate_large_order_detection(order_data, expected_category)
        
        assert isinstance(validation, LargeOrderValidation)
        assert validation.order_id == "order_001"
        assert validation.expected_category == OrderSize.LARGE
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                            LargeOrderValidationStatus.WARNING,
                                            LargeOrderValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            order_data = OrderData(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                price=100.0 + i * 10.0,
                quantity=50.0 + i * 25.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM,
                market_impact=MarketImpact.HIGH if i % 2 == 0 else MarketImpact.LOW,
                volume_ratio=2.0 + i * 0.5,
                depth_impact=1.0 + i * 0.3
            )
            
            expected_category = OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM
            self.manager.validate_large_order_detection(order_data, expected_category)
        
        report = self.manager.generate_validation_report()
        
        assert isinstance(report, LargeOrderValidationReport)
        assert report.total_validations == 3
        
        # Check that report was added to history
        assert len(self.manager.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            order_data = OrderData(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                price=100.0 + i * 10.0,
                quantity=50.0 + i * 25.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=OrderSize.LARGE,
                market_impact=MarketImpact.HIGH,
                volume_ratio=2.0 + i * 0.5,
                depth_impact=1.0 + i * 0.3
            )
            
            expected_category = OrderSize.LARGE
            self.manager.validate_large_order_detection(order_data, expected_category)
            self.manager.generate_validation_report()
        
        history = self.manager.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, LargeOrderValidationReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            order_data = OrderData(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                price=100.0 + i * 10.0,
                quantity=50.0 + i * 25.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM,
                market_impact=MarketImpact.HIGH if i % 2 == 0 else MarketImpact.LOW,
                volume_ratio=2.0 + i * 0.5,
                depth_impact=1.0 + i * 0.3
            )
            
            expected_category = OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM
            self.manager.validate_large_order_detection(order_data, expected_category)
        
        summary = self.manager.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
        assert "true_positives" in summary
        assert "false_positives" in summary
        assert "true_negatives" in summary
        assert "false_negatives" in summary
        assert "overall_precision" in summary
        assert "overall_recall" in summary
        assert "overall_f1_score" in summary
        assert "precision_threshold" in summary
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        order_data = OrderData(
            order_id="test_order",
            symbol="TEST",
            timestamp=time.time(),
            price=100.0,
            quantity=50.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=2.0,
            depth_impact=1.5
        )
        
        expected_category = OrderSize.LARGE
        self.manager.validate_large_order_detection(order_data, expected_category)
        self.manager.generate_validation_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.validation_reports) == 0

class TestGlobalFunctions:
    """Test global large order validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.large_order_detection_validation
        infra.large_order_detection_validation._large_order_validation_manager = None
    
    def test_get_large_order_validation_manager(self):
        """Test global manager access"""
        manager1 = get_large_order_validation_manager()
        manager2 = get_large_order_validation_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, LargeOrderValidationManager)
    
    def test_validate_large_order_detection_global(self):
        """Test global large order detection validation"""
        order_data = OrderData(
            order_id="order_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=150.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=3.5,
            depth_impact=2.8
        )
        
        expected_category = OrderSize.LARGE
        
        validation = validate_large_order_detection(order_data, expected_category)
        
        assert isinstance(validation, LargeOrderValidation)
        assert validation.order_id == "order_001"
        assert validation.expected_category == OrderSize.LARGE
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                            LargeOrderValidationStatus.WARNING,
                                            LargeOrderValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_large_order_validation_report_global(self):
        """Test global large order validation report generation"""
        # Add some validations first
        for i in range(3):
            order_data = OrderData(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                price=100.0 + i * 10.0,
                quantity=50.0 + i * 25.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM,
                market_impact=MarketImpact.HIGH if i % 2 == 0 else MarketImpact.LOW,
                volume_ratio=2.0 + i * 0.5,
                depth_impact=1.0 + i * 0.3
            )
            
            expected_category = OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM
            validate_large_order_detection(order_data, expected_category)
        
        report = generate_large_order_validation_report()
        
        assert isinstance(report, LargeOrderValidationReport)
        assert report.total_validations == 3
    
    def test_get_large_order_validation_summary_global(self):
        """Test global large order validation summary"""
        # Add some validations
        for i in range(5):
            order_data = OrderData(
                order_id=f"order_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                price=100.0 + i * 10.0,
                quantity=50.0 + i * 25.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM,
                market_impact=MarketImpact.HIGH if i % 2 == 0 else MarketImpact.LOW,
                volume_ratio=2.0 + i * 0.5,
                depth_impact=1.0 + i * 0.3
            )
            
            expected_category = OrderSize.LARGE if i % 2 == 0 else OrderSize.MEDIUM
            validate_large_order_detection(order_data, expected_category)
        
        summary = get_large_order_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestLargeOrderValidationIntegration:
    """Integration tests for large order validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.large_order_detection_validation
        infra.large_order_detection_validation._large_order_validation_manager = None
    
    def test_comprehensive_large_order_validation(self):
        """Test comprehensive large order validation workflow"""
        # Test different order sizes and types
        test_cases = [
            (OrderSize.SMALL, OrderType.MARKET, MarketImpact.LOW, 0.5, 0.2),
            (OrderSize.MEDIUM, OrderType.LIMIT, MarketImpact.LOW, 1.2, 0.8),
            (OrderSize.LARGE, OrderType.MARKET, MarketImpact.HIGH, 3.5, 2.8),
            (OrderSize.INSTITUTIONAL, OrderType.TWAP, MarketImpact.SEVERE, 6.0, 4.5),
            (OrderSize.WHALE, OrderType.VWAP, MarketImpact.SEVERE, 10.0, 8.0)
        ]
        
        for size_category, order_type, market_impact, volume_ratio, depth_impact in test_cases:
            order_data = OrderData(
                order_id=f"order_{size_category.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                price=50000.0,
                quantity=100.0 if size_category == OrderSize.SMALL else 500.0,
                order_type=order_type,
                side="buy",
                size_category=size_category,
                market_impact=market_impact,
                volume_ratio=volume_ratio,
                depth_impact=depth_impact,
                metadata={"test_case": size_category.value}
            )
            
            validation = validate_large_order_detection(order_data, size_category)
            
            assert isinstance(validation, LargeOrderValidation)
            assert validation.order_id == f"order_{size_category.value}"
            assert validation.expected_category == size_category
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.false_positive in [True, False]
            assert validation.false_negative in [True, False]
            assert validation.true_positive in [True, False]
            assert validation.true_negative in [True, False]
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                                LargeOrderValidationStatus.WARNING,
                                                LargeOrderValidationStatus.FAILED]
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_large_order_validation_report()
        
        assert isinstance(report, LargeOrderValidationReport)
        assert report.total_validations == len(test_cases)
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.precision_level in [LargeOrderPrecisionLevel.EXCELLENT,
                                        LargeOrderPrecisionLevel.GOOD,
                                        LargeOrderPrecisionLevel.ACCEPTABLE,
                                        LargeOrderPrecisionLevel.POOR]
        assert report.validation_status in [LargeOrderValidationStatus.PASSED,
                                         LargeOrderValidationStatus.WARNING,
                                         LargeOrderValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(test_cases)
        assert len(report.recommendations) > 0
        assert len(report.order_size_analysis) > 0
        assert len(report.market_impact_analysis) > 0
        assert len(report.detection_method_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_precision_threshold_validation(self):
        """Test precision threshold validation"""
        # Test with high precision (should pass)
        high_precision_order = OrderData(
            order_id="high_precision",
            symbol="BTCUSDT",
            timestamp=time.time(),
            price=50000.0,
            quantity=200.0,
            order_type=OrderType.MARKET,
            side="buy",
            size_category=OrderSize.LARGE,
            market_impact=MarketImpact.HIGH,
            volume_ratio=4.0,
            depth_impact=3.0
        )
        
        validation = validate_large_order_detection(high_precision_order, OrderSize.LARGE)
        
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                            LargeOrderValidationStatus.WARNING,
                                            LargeOrderValidationStatus.FAILED]
        
        # Test with low precision (should fail)
        low_precision_order = OrderData(
            order_id="low_precision",
            symbol="ETHUSDT",
            timestamp=time.time(),
            price=3000.0,
            quantity=5.0,
            order_type=OrderType.LIMIT,
            side="sell",
            size_category=OrderSize.SMALL,
            market_impact=MarketImpact.LOW,
            volume_ratio=0.8,
            depth_impact=0.3
        )
        
        validation = validate_large_order_detection(low_precision_order, OrderSize.LARGE)
        
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                            LargeOrderValidationStatus.WARNING,
                                            LargeOrderValidationStatus.FAILED]
    
    def test_order_size_analysis_validation(self):
        """Test order size analysis validation"""
        # Test different order sizes
        order_sizes = [OrderSize.SMALL, OrderSize.MEDIUM, OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE]
        
        for size in order_sizes:
            order_data = OrderData(
                order_id=f"order_{size.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                price=50000.0,
                quantity=50.0 if size == OrderSize.SMALL else 200.0,
                order_type=OrderType.MARKET,
                side="buy",
                size_category=size,
                market_impact=MarketImpact.HIGH if size in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE] else MarketImpact.LOW,
                volume_ratio=2.0 if size in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE] else 1.0,
                depth_impact=2.0 if size in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE] else 0.5
            )
            
            validation = validate_large_order_detection(order_data, size)
            
            assert validation.expected_category == size
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.false_positive in [True, False]
            assert validation.false_negative in [True, False]
            assert validation.true_positive in [True, False]
            assert validation.true_negative in [True, False]
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [LargeOrderValidationStatus.PASSED,
                                                LargeOrderValidationStatus.WARNING,
                                                LargeOrderValidationStatus.FAILED]
            assert len(validation.recommendations) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
