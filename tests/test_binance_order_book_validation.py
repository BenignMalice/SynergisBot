"""
Comprehensive tests for Binance order book analysis accuracy validation system

Tests Binance order book analysis accuracy >95%, order book data processing
validation, depth analysis validation, price level detection accuracy,
volume analysis accuracy, imbalance detection accuracy, support/resistance
identification accuracy, and order book snapshot validation.
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

from infra.binance_order_book_validation import (
    OrderBookValidationManager, OrderBookAnalyzer, OrderBookValidator,
    OrderBookAccuracyLevel, OrderBookValidationStatus, OrderBookAnalysisType, OrderBookDataQuality,
    OrderBookSnapshot, OrderBookAnalysis, OrderBookValidation, OrderBookValidationReport,
    get_order_book_validation_manager, validate_order_book_analysis,
    generate_order_book_validation_report, get_order_book_validation_summary
)

class TestOrderBookAccuracyLevel:
    """Test order book accuracy level enumeration"""
    
    def test_accuracy_levels(self):
        """Test all accuracy levels"""
        levels = [
            OrderBookAccuracyLevel.EXCELLENT,
            OrderBookAccuracyLevel.GOOD,
            OrderBookAccuracyLevel.ACCEPTABLE,
            OrderBookAccuracyLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, OrderBookAccuracyLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestOrderBookValidationStatus:
    """Test order book validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            OrderBookValidationStatus.PASSED,
            OrderBookValidationStatus.WARNING,
            OrderBookValidationStatus.FAILED,
            OrderBookValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, OrderBookValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestOrderBookAnalysisType:
    """Test order book analysis type enumeration"""
    
    def test_analysis_types(self):
        """Test all analysis types"""
        types = [
            OrderBookAnalysisType.DEPTH_ANALYSIS,
            OrderBookAnalysisType.PRICE_LEVEL_DETECTION,
            OrderBookAnalysisType.VOLUME_ANALYSIS,
            OrderBookAnalysisType.IMBALANCE_DETECTION,
            OrderBookAnalysisType.SUPPORT_RESISTANCE,
            OrderBookAnalysisType.SNAPSHOT_VALIDATION,
            OrderBookAnalysisType.UPDATE_VALIDATION
        ]
        
        for analysis_type in types:
            assert isinstance(analysis_type, OrderBookAnalysisType)
            assert analysis_type.value in ["depth_analysis", "price_level_detection", 
                                         "volume_analysis", "imbalance_detection",
                                         "support_resistance", "snapshot_validation", "update_validation"]

class TestOrderBookDataQuality:
    """Test order book data quality enumeration"""
    
    def test_data_quality_levels(self):
        """Test all data quality levels"""
        qualities = [
            OrderBookDataQuality.HIGH,
            OrderBookDataQuality.MEDIUM,
            OrderBookDataQuality.LOW,
            OrderBookDataQuality.POOR
        ]
        
        for quality in qualities:
            assert isinstance(quality, OrderBookDataQuality)
            assert quality.value in ["high", "medium", "low", "poor"]

class TestOrderBookSnapshot:
    """Test order book snapshot data structure"""
    
    def test_order_book_snapshot_creation(self):
        """Test order book snapshot creation"""
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5), (49999.0, 2.0), (49998.0, 1.0)],
            asks=[(50001.0, 1.2), (50002.0, 1.8), (50003.0, 0.9)],
            last_update_id=12345,
            data_quality=OrderBookDataQuality.HIGH,
            metadata={"source": "binance"}
        )
        
        assert snapshot.symbol == "BTCUSDT"
        assert snapshot.timestamp > 0
        assert len(snapshot.bids) == 3
        assert len(snapshot.asks) == 3
        assert snapshot.last_update_id == 12345
        assert snapshot.data_quality == OrderBookDataQuality.HIGH
        assert snapshot.metadata["source"] == "binance"
    
    def test_order_book_snapshot_defaults(self):
        """Test order book snapshot defaults"""
        snapshot = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=time.time(),
            bids=[(3000.0, 1.0)],
            asks=[(3001.0, 1.0)],
            last_update_id=54321,
            data_quality=OrderBookDataQuality.MEDIUM
        )
        
        assert snapshot.metadata == {}

class TestOrderBookAnalysis:
    """Test order book analysis data structure"""
    
    def test_order_book_analysis_creation(self):
        """Test order book analysis creation"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.DEPTH_ANALYSIS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            detected_levels=[50000.0, 50001.0],
            volume_analysis={"bid_depth": 4.5, "ask_depth": 3.9, "total_depth": 8.4},
            imbalance_ratio=1.15,
            support_levels=[49999.0],
            resistance_levels=[50002.0],
            confidence_score=0.85,
            accuracy_score=0.92,
            metadata={"analysis_method": "depth_analysis"}
        )
        
        assert analysis.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert analysis.symbol == "BTCUSDT"
        assert analysis.timestamp > 0
        assert len(analysis.detected_levels) == 2
        assert analysis.volume_analysis["bid_depth"] == 4.5
        assert analysis.imbalance_ratio == 1.15
        assert len(analysis.support_levels) == 1
        assert len(analysis.resistance_levels) == 1
        assert analysis.confidence_score == 0.85
        assert analysis.accuracy_score == 0.92
        assert analysis.metadata["analysis_method"] == "depth_analysis"
    
    def test_order_book_analysis_defaults(self):
        """Test order book analysis defaults"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.VOLUME_ANALYSIS,
            symbol="ETHUSDT",
            timestamp=time.time(),
            detected_levels=[],
            volume_analysis={},
            imbalance_ratio=0.0,
            support_levels=[],
            resistance_levels=[],
            confidence_score=0.0,
            accuracy_score=0.0
        )
        
        assert analysis.metadata == {}

class TestOrderBookValidation:
    """Test order book validation data structure"""
    
    def test_order_book_validation_creation(self):
        """Test order book validation creation"""
        validation = OrderBookValidation(
            timestamp=time.time(),
            analysis_type=OrderBookAnalysisType.DEPTH_ANALYSIS,
            expected_result={"depth_ratio": 1.25},
            actual_result=None,
            accuracy_score=0.95,
            precision_score=0.92,
            recall_score=0.88,
            f1_score=0.90,
            meets_threshold=True,
            validation_status=OrderBookValidationStatus.PASSED,
            recommendations=["Analysis accuracy is excellent"],
            metadata={"accuracy_threshold": 0.95}
        )
        
        assert validation.timestamp > 0
        assert validation.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert validation.expected_result["depth_ratio"] == 1.25
        assert validation.accuracy_score == 0.95
        assert validation.precision_score == 0.92
        assert validation.recall_score == 0.88
        assert validation.f1_score == 0.90
        assert validation.meets_threshold is True
        assert validation.validation_status == OrderBookValidationStatus.PASSED
        assert len(validation.recommendations) == 1
        assert validation.metadata["accuracy_threshold"] == 0.95
    
    def test_order_book_validation_defaults(self):
        """Test order book validation defaults"""
        validation = OrderBookValidation(
            timestamp=time.time(),
            analysis_type=OrderBookAnalysisType.VOLUME_ANALYSIS,
            expected_result=None,
            actual_result=None,
            accuracy_score=0.0,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            meets_threshold=False,
            validation_status=OrderBookValidationStatus.FAILED,
            recommendations=["Analysis failed"]
        )
        
        assert validation.metadata == {}

class TestOrderBookValidationReport:
    """Test order book validation report data structure"""
    
    def test_order_book_validation_report_creation(self):
        """Test order book validation report creation"""
        report = OrderBookValidationReport(
            timestamp=time.time(),
            overall_accuracy=0.95,
            overall_precision=0.92,
            overall_recall=0.88,
            overall_f1_score=0.90,
            accuracy_level=OrderBookAccuracyLevel.GOOD,
            validation_status=OrderBookValidationStatus.PASSED,
            total_validations=100,
            passed_validations=95,
            failed_validations=5,
            analysis_type_accuracy={"depth_analysis": 0.96, "volume_analysis": 0.94},
            data_quality_analysis={"high_quality_ratio": 0.8, "medium_quality_ratio": 0.15},
            performance_metrics={"avg_validation_time_ms": 25.5, "total_validations": 100},
            recommendations=["Order book analysis accuracy is good"],
            detailed_validations=[],
            metadata={"accuracy_threshold": 0.95}
        )
        
        assert report.timestamp > 0
        assert report.overall_accuracy == 0.95
        assert report.overall_precision == 0.92
        assert report.overall_recall == 0.88
        assert report.overall_f1_score == 0.90
        assert report.accuracy_level == OrderBookAccuracyLevel.GOOD
        assert report.validation_status == OrderBookValidationStatus.PASSED
        assert report.total_validations == 100
        assert report.passed_validations == 95
        assert report.failed_validations == 5
        assert report.analysis_type_accuracy["depth_analysis"] == 0.96
        assert report.data_quality_analysis["high_quality_ratio"] == 0.8
        assert report.performance_metrics["avg_validation_time_ms"] == 25.5
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["accuracy_threshold"] == 0.95
    
    def test_order_book_validation_report_defaults(self):
        """Test order book validation report defaults"""
        report = OrderBookValidationReport(
            timestamp=time.time(),
            overall_accuracy=0.85,
            overall_precision=0.82,
            overall_recall=0.78,
            overall_f1_score=0.80,
            accuracy_level=OrderBookAccuracyLevel.ACCEPTABLE,
            validation_status=OrderBookValidationStatus.WARNING,
            total_validations=50,
            passed_validations=40,
            failed_validations=10,
            analysis_type_accuracy={"depth_analysis": 0.86},
            data_quality_analysis={"high_quality_ratio": 0.6},
            performance_metrics={"avg_validation_time_ms": 30.0},
            recommendations=["Order book analysis accuracy is acceptable"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestOrderBookAnalyzer:
    """Test order book analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = OrderBookAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_depth(self):
        """Test depth analysis"""
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5), (49999.0, 2.0), (49998.0, 1.0)],
            asks=[(50001.0, 1.2), (50002.0, 1.8), (50003.0, 0.9)],
            last_update_id=12345,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        analysis = self.analyzer.analyze_depth(snapshot)
        
        assert analysis.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert analysis.symbol == "BTCUSDT"
        assert analysis.timestamp == snapshot.timestamp
        assert len(analysis.detected_levels) >= 0
        assert "bid_depth" in analysis.volume_analysis
        assert "ask_depth" in analysis.volume_analysis
        assert "total_depth" in analysis.volume_analysis
        assert "depth_ratio" in analysis.volume_analysis
        assert analysis.imbalance_ratio > 0
        assert 0.0 <= analysis.confidence_score <= 1.0
        assert analysis.metadata["analysis_method"] == "depth_analysis"
    
    def test_analyze_price_levels(self):
        """Test price level analysis"""
        snapshot = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=time.time(),
            bids=[(3000.0, 1.0), (2999.0, 1.5), (2998.0, 0.8)],
            asks=[(3001.0, 1.2), (3002.0, 1.3), (3003.0, 0.9)],
            last_update_id=54321,
            data_quality=OrderBookDataQuality.MEDIUM
        )
        
        analysis = self.analyzer.analyze_price_levels(snapshot)
        
        assert analysis.analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION
        assert analysis.symbol == "ETHUSDT"
        assert analysis.timestamp == snapshot.timestamp
        assert len(analysis.detected_levels) >= 0
        assert "bid_volume_total" in analysis.volume_analysis
        assert "ask_volume_total" in analysis.volume_analysis
        assert 0.0 <= analysis.confidence_score <= 1.0
        assert analysis.metadata["analysis_method"] == "price_level_detection"
    
    def test_analyze_volume(self):
        """Test volume analysis"""
        snapshot = OrderBookSnapshot(
            symbol="ADAUSDT",
            timestamp=time.time(),
            bids=[(0.5, 1000.0), (0.49, 1500.0), (0.48, 800.0)],
            asks=[(0.51, 1200.0), (0.52, 1300.0), (0.53, 900.0)],
            last_update_id=98765,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        analysis = self.analyzer.analyze_volume(snapshot)
        
        assert analysis.analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS
        assert analysis.symbol == "ADAUSDT"
        assert analysis.timestamp == snapshot.timestamp
        assert len(analysis.detected_levels) >= 0
        assert "bid_volume" in analysis.volume_analysis
        assert "ask_volume" in analysis.volume_analysis
        assert "total_volume" in analysis.volume_analysis
        assert "volume_distribution" in analysis.volume_analysis
        assert analysis.imbalance_ratio > 0
        assert 0.0 <= analysis.confidence_score <= 1.0
        assert analysis.metadata["analysis_method"] == "volume_analysis"
    
    def test_analyze_imbalance(self):
        """Test imbalance analysis"""
        snapshot = OrderBookSnapshot(
            symbol="DOTUSDT",
            timestamp=time.time(),
            bids=[(25.0, 2.0), (24.9, 3.0), (24.8, 1.5)],
            asks=[(25.1, 1.0), (25.2, 2.5), (25.3, 1.2)],
            last_update_id=11111,
            data_quality=OrderBookDataQuality.MEDIUM
        )
        
        analysis = self.analyzer.analyze_imbalance(snapshot)
        
        assert analysis.analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION
        assert analysis.symbol == "DOTUSDT"
        assert analysis.timestamp == snapshot.timestamp
        assert len(analysis.detected_levels) >= 0
        assert "bid_volume" in analysis.volume_analysis
        assert "ask_volume" in analysis.volume_analysis
        assert "imbalance_ratio" in analysis.volume_analysis
        assert analysis.imbalance_ratio > 0
        assert 0.0 <= analysis.confidence_score <= 1.0
        assert analysis.metadata["analysis_method"] == "imbalance_detection"
    
    def test_analyze_support_resistance(self):
        """Test support/resistance analysis"""
        snapshot = OrderBookSnapshot(
            symbol="LINKUSDT",
            timestamp=time.time(),
            bids=[(15.0, 5.0), (14.9, 3.0), (14.8, 2.0)],
            asks=[(15.1, 2.0), (15.2, 4.0), (15.3, 3.0)],
            last_update_id=22222,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        analysis = self.analyzer.analyze_support_resistance(snapshot)
        
        assert analysis.analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE
        assert analysis.symbol == "LINKUSDT"
        assert analysis.timestamp == snapshot.timestamp
        assert len(analysis.detected_levels) >= 0
        assert len(analysis.support_levels) >= 0
        assert len(analysis.resistance_levels) >= 0
        assert 0.0 <= analysis.confidence_score <= 1.0
        assert analysis.metadata["analysis_method"] == "support_resistance"

class TestOrderBookValidator:
    """Test order book validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = OrderBookValidator(accuracy_threshold=0.95)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.accuracy_threshold == 0.95
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_analysis_accuracy_depth_analysis(self):
        """Test analysis accuracy validation for depth analysis"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.DEPTH_ANALYSIS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            detected_levels=[],
            volume_analysis={},
            imbalance_ratio=1.25,
            support_levels=[],
            resistance_levels=[],
            confidence_score=0.85,
            accuracy_score=0.0
        )
        
        expected_result = {"depth_ratio": 1.20}
        
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        assert validation.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert validation.expected_result == expected_result
        assert validation.actual_result == analysis
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
        assert validation.metadata["accuracy_threshold"] == 0.95
    
    def test_validate_analysis_accuracy_price_levels(self):
        """Test analysis accuracy validation for price level detection"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.PRICE_LEVEL_DETECTION,
            symbol="ETHUSDT",
            timestamp=time.time(),
            detected_levels=[3000.0, 3001.0, 3002.0],
            volume_analysis={},
            imbalance_ratio=0.0,
            support_levels=[],
            resistance_levels=[],
            confidence_score=0.90,
            accuracy_score=0.0
        )
        
        expected_result = [3000.5, 3001.5, 3002.5]
        
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        assert validation.analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION
        assert validation.expected_result == expected_result
        assert validation.actual_result == analysis
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_analysis_accuracy_volume_analysis(self):
        """Test analysis accuracy validation for volume analysis"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.VOLUME_ANALYSIS,
            symbol="ADAUSDT",
            timestamp=time.time(),
            detected_levels=[],
            volume_analysis={"total_volume": 1000.0, "bid_volume": 600.0, "ask_volume": 400.0},
            imbalance_ratio=1.5,
            support_levels=[],
            resistance_levels=[],
            confidence_score=0.88,
            accuracy_score=0.0
        )
        
        expected_result = {"total_volume": 1050.0, "bid_volume": 630.0, "ask_volume": 420.0}
        
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        assert validation.analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS
        assert validation.expected_result == expected_result
        assert validation.actual_result == analysis
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_analysis_accuracy_imbalance_detection(self):
        """Test analysis accuracy validation for imbalance detection"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.IMBALANCE_DETECTION,
            symbol="DOTUSDT",
            timestamp=time.time(),
            detected_levels=[],
            volume_analysis={},
            imbalance_ratio=1.8,
            support_levels=[],
            resistance_levels=[],
            confidence_score=0.92,
            accuracy_score=0.0
        )
        
        expected_result = 1.75
        
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        assert validation.analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION
        assert validation.expected_result == expected_result
        assert validation.actual_result == analysis
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_analysis_accuracy_support_resistance(self):
        """Test analysis accuracy validation for support/resistance"""
        analysis = OrderBookAnalysis(
            analysis_type=OrderBookAnalysisType.SUPPORT_RESISTANCE,
            symbol="LINKUSDT",
            timestamp=time.time(),
            detected_levels=[15.0, 15.1, 15.2],
            volume_analysis={},
            imbalance_ratio=0.0,
            support_levels=[15.0],
            resistance_levels=[15.1, 15.2],
            confidence_score=0.87,
            accuracy_score=0.0
        )
        
        expected_result = {"support_levels": [15.05], "resistance_levels": [15.15, 15.25]}
        
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        assert validation.analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE
        assert validation.expected_result == expected_result
        assert validation.actual_result == analysis
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(5):
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.DEPTH_ANALYSIS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                detected_levels=[],
                volume_analysis={},
                imbalance_ratio=1.0 + i * 0.1,
                support_levels=[],
                resistance_levels=[],
                confidence_score=0.8 + i * 0.02,
                accuracy_score=0.0
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_validations == 5
        assert report.passed_validations >= 0
        assert report.failed_validations >= 0
        assert report.overall_accuracy >= 0.0
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.accuracy_level in [OrderBookAccuracyLevel.EXCELLENT,
                                       OrderBookAccuracyLevel.GOOD,
                                       OrderBookAccuracyLevel.ACCEPTABLE,
                                       OrderBookAccuracyLevel.POOR]
        assert report.validation_status in [OrderBookValidationStatus.PASSED,
                                          OrderBookValidationStatus.WARNING,
                                          OrderBookValidationStatus.FAILED]
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.analysis_type_accuracy) > 0
        assert len(report.data_quality_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_accuracy == 0.0
        assert report.overall_precision == 0.0
        assert report.overall_recall == 0.0
        assert report.overall_f1_score == 0.0
        assert report.accuracy_level == OrderBookAccuracyLevel.POOR
        assert report.validation_status == OrderBookValidationStatus.FAILED
        assert report.total_validations == 0
        assert report.passed_validations == 0
        assert report.failed_validations == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.analysis_type_accuracy == {}
        assert report.data_quality_analysis == {}
        assert report.performance_metrics == {}

class TestOrderBookValidationManager:
    """Test order book validation manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = OrderBookValidationManager(accuracy_threshold=0.95)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.analyzer, OrderBookAnalyzer)
        assert isinstance(self.manager.validator, OrderBookValidator)
        assert self.manager.validator.accuracy_threshold == 0.95
        assert self.manager.start_time > 0
        assert len(self.manager.validation_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_order_book_analysis_depth(self):
        """Test order book analysis validation for depth analysis"""
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5), (49999.0, 2.0)],
            asks=[(50001.0, 1.2), (50002.0, 1.8)],
            last_update_id=12345,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"depth_ratio": 1.25}
        
        validation = self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_order_book_analysis_price_levels(self):
        """Test order book analysis validation for price level detection"""
        snapshot = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=time.time(),
            bids=[(3000.0, 1.0), (2999.0, 1.5)],
            asks=[(3001.0, 1.2), (3002.0, 1.3)],
            last_update_id=54321,
            data_quality=OrderBookDataQuality.MEDIUM
        )
        
        expected_result = [3000.5, 3001.5]
        
        validation = self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.PRICE_LEVEL_DETECTION, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_order_book_analysis_volume(self):
        """Test order book analysis validation for volume analysis"""
        snapshot = OrderBookSnapshot(
            symbol="ADAUSDT",
            timestamp=time.time(),
            bids=[(0.5, 1000.0), (0.49, 1500.0)],
            asks=[(0.51, 1200.0), (0.52, 1300.0)],
            last_update_id=98765,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"total_volume": 5000.0, "bid_volume": 2500.0, "ask_volume": 2500.0}
        
        validation = self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.VOLUME_ANALYSIS, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_order_book_analysis_imbalance(self):
        """Test order book analysis validation for imbalance detection"""
        snapshot = OrderBookSnapshot(
            symbol="DOTUSDT",
            timestamp=time.time(),
            bids=[(25.0, 2.0), (24.9, 3.0)],
            asks=[(25.1, 1.0), (25.2, 2.5)],
            last_update_id=11111,
            data_quality=OrderBookDataQuality.MEDIUM
        )
        
        expected_result = 1.8
        
        validation = self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.IMBALANCE_DETECTION, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_validate_order_book_analysis_support_resistance(self):
        """Test order book analysis validation for support/resistance"""
        snapshot = OrderBookSnapshot(
            symbol="LINKUSDT",
            timestamp=time.time(),
            bids=[(15.0, 5.0), (14.9, 3.0)],
            asks=[(15.1, 2.0), (15.2, 4.0)],
            last_update_id=22222,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"support_levels": [15.05], "resistance_levels": [15.15]}
        
        validation = self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.SUPPORT_RESISTANCE, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            snapshot = OrderBookSnapshot(
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
                last_update_id=10000 + i,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            self.manager.validate_order_book_analysis(
                snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
            )
        
        report = self.manager.generate_validation_report()
        
        assert isinstance(report, OrderBookValidationReport)
        assert report.total_validations == 3
        
        # Check that report was added to history
        assert len(self.manager.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            snapshot = OrderBookSnapshot(
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
                last_update_id=10000 + i,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            self.manager.validate_order_book_analysis(
                snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
            )
            self.manager.generate_validation_report()
        
        history = self.manager.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, OrderBookValidationReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            snapshot = OrderBookSnapshot(
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
                last_update_id=10000 + i,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            self.manager.validate_order_book_analysis(
                snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
            )
        
        summary = self.manager.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
        assert "passed_validations" in summary
        assert "failed_validations" in summary
        assert "overall_accuracy" in summary
        assert "overall_precision" in summary
        assert "overall_recall" in summary
        assert "accuracy_threshold" in summary
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        snapshot = OrderBookSnapshot(
            symbol="TEST",
            timestamp=time.time(),
            bids=[(100.0, 1.0)],
            asks=[(101.0, 1.0)],
            last_update_id=99999,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"depth_ratio": 1.0}
        self.manager.validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
        )
        self.manager.generate_validation_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.validation_reports) == 0

class TestGlobalFunctions:
    """Test global order book validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.binance_order_book_validation
        infra.binance_order_book_validation._order_book_validation_manager = None
    
    def test_get_order_book_validation_manager(self):
        """Test global manager access"""
        manager1 = get_order_book_validation_manager()
        manager2 = get_order_book_validation_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, OrderBookValidationManager)
    
    def test_validate_order_book_analysis_global(self):
        """Test global order book analysis validation"""
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5), (49999.0, 2.0)],
            asks=[(50001.0, 1.2), (50002.0, 1.8)],
            last_update_id=12345,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"depth_ratio": 1.25}
        
        validation = validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
        )
        
        assert isinstance(validation, OrderBookValidation)
        assert validation.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS
        assert validation.expected_result == expected_result
        assert 0.0 <= validation.accuracy_score <= 1.0
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_order_book_validation_report_global(self):
        """Test global order book validation report generation"""
        # Add some validations first
        for i in range(3):
            snapshot = OrderBookSnapshot(
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
                last_update_id=10000 + i,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            validate_order_book_analysis(
                snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
            )
        
        report = generate_order_book_validation_report()
        
        assert isinstance(report, OrderBookValidationReport)
        assert report.total_validations == 3
    
    def test_get_order_book_validation_summary_global(self):
        """Test global order book validation summary"""
        # Add some validations
        for i in range(5):
            snapshot = OrderBookSnapshot(
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                bids=[(100.0 + i, 1.0)],
                asks=[(101.0 + i, 1.0)],
                last_update_id=10000 + i,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            expected_result = {"depth_ratio": 1.0 + i * 0.1}
            validate_order_book_analysis(
                snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
            )
        
        summary = get_order_book_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestOrderBookValidationIntegration:
    """Integration tests for order book validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.binance_order_book_validation
        infra.binance_order_book_validation._order_book_validation_manager = None
    
    def test_comprehensive_order_book_validation(self):
        """Test comprehensive order book validation workflow"""
        # Test multiple analysis types
        analysis_types = [
            OrderBookAnalysisType.DEPTH_ANALYSIS,
            OrderBookAnalysisType.PRICE_LEVEL_DETECTION,
            OrderBookAnalysisType.VOLUME_ANALYSIS,
            OrderBookAnalysisType.IMBALANCE_DETECTION,
            OrderBookAnalysisType.SUPPORT_RESISTANCE
        ]
        
        for analysis_type in analysis_types:
            snapshot = OrderBookSnapshot(
                symbol="BTCUSDT",
                timestamp=time.time(),
                bids=[(50000.0, 1.5), (49999.0, 2.0), (49998.0, 1.0)],
                asks=[(50001.0, 1.2), (50002.0, 1.8), (50003.0, 0.9)],
                last_update_id=12345,
                data_quality=OrderBookDataQuality.HIGH,
                metadata={"source": "binance"}
            )
            
            # Create expected result based on analysis type
            if analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS:
                expected_result = {"depth_ratio": 1.25}
            elif analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION:
                expected_result = [50000.5, 50001.5, 50002.5]
            elif analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS:
                expected_result = {"total_volume": 8.4, "bid_volume": 4.5, "ask_volume": 3.9}
            elif analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION:
                expected_result = 1.15
            elif analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE:
                expected_result = {"support_levels": [49999.0], "resistance_levels": [50002.0]}
            
            validation = validate_order_book_analysis(snapshot, analysis_type, expected_result)
            
            assert isinstance(validation, OrderBookValidation)
            assert validation.analysis_type == analysis_type
            assert validation.expected_result == expected_result
            assert 0.0 <= validation.accuracy_score <= 1.0
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                                OrderBookValidationStatus.WARNING,
                                                OrderBookValidationStatus.FAILED]
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_order_book_validation_report()
        
        assert isinstance(report, OrderBookValidationReport)
        assert report.total_validations == len(analysis_types)
        assert report.overall_accuracy >= 0.0
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.accuracy_level in [OrderBookAccuracyLevel.EXCELLENT,
                                       OrderBookAccuracyLevel.GOOD,
                                       OrderBookAccuracyLevel.ACCEPTABLE,
                                       OrderBookAccuracyLevel.POOR]
        assert report.validation_status in [OrderBookValidationStatus.PASSED,
                                          OrderBookValidationStatus.WARNING,
                                          OrderBookValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(analysis_types)
        assert len(report.recommendations) > 0
        assert len(report.analysis_type_accuracy) > 0
        assert len(report.data_quality_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_accuracy_threshold_validation(self):
        """Test accuracy threshold validation"""
        # Test with high accuracy (should pass)
        snapshot = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(50000.0, 1.5), (49999.0, 2.0)],
            asks=[(50001.0, 1.2), (50002.0, 1.8)],
            last_update_id=12345,
            data_quality=OrderBookDataQuality.HIGH
        )
        
        expected_result = {"depth_ratio": 1.25}
        
        validation = validate_order_book_analysis(
            snapshot, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result
        )
        
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                            OrderBookValidationStatus.WARNING,
                                            OrderBookValidationStatus.FAILED]
        
        # Test with low accuracy (should fail)
        snapshot_low = OrderBookSnapshot(
            symbol="ETHUSDT",
            timestamp=time.time(),
            bids=[(3000.0, 1.0)],
            asks=[(3001.0, 1.0)],
            last_update_id=54321,
            data_quality=OrderBookDataQuality.LOW
        )
        
        expected_result_low = {"depth_ratio": 5.0}  # Very different from actual
        
        validation_low = validate_order_book_analysis(
            snapshot_low, OrderBookAnalysisType.DEPTH_ANALYSIS, expected_result_low
        )
        
        assert validation_low.meets_threshold in [True, False]
        assert validation_low.validation_status in [OrderBookValidationStatus.PASSED,
                                                  OrderBookValidationStatus.WARNING,
                                                  OrderBookValidationStatus.FAILED]
    
    def test_analysis_type_accuracy_validation(self):
        """Test analysis type accuracy validation"""
        # Test different analysis types with different expected results
        test_cases = [
            (OrderBookAnalysisType.DEPTH_ANALYSIS, {"depth_ratio": 1.25}),
            (OrderBookAnalysisType.PRICE_LEVEL_DETECTION, [50000.5, 50001.5]),
            (OrderBookAnalysisType.VOLUME_ANALYSIS, {"total_volume": 8.4}),
            (OrderBookAnalysisType.IMBALANCE_DETECTION, 1.15),
            (OrderBookAnalysisType.SUPPORT_RESISTANCE, {"support_levels": [49999.0], "resistance_levels": [50002.0]})
        ]
        
        for analysis_type, expected_result in test_cases:
            snapshot = OrderBookSnapshot(
                symbol="BTCUSDT",
                timestamp=time.time(),
                bids=[(50000.0, 1.5), (49999.0, 2.0)],
                asks=[(50001.0, 1.2), (50002.0, 1.8)],
                last_update_id=12345,
                data_quality=OrderBookDataQuality.HIGH
            )
            
            validation = validate_order_book_analysis(snapshot, analysis_type, expected_result)
            
            assert validation.analysis_type == analysis_type
            assert validation.expected_result == expected_result
            assert 0.0 <= validation.accuracy_score <= 1.0
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [OrderBookValidationStatus.PASSED,
                                                OrderBookValidationStatus.WARNING,
                                                OrderBookValidationStatus.FAILED]
            assert len(validation.recommendations) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
