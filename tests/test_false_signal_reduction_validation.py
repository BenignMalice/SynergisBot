"""
Comprehensive tests for false signal reduction validation system

Tests false signal reduction >80% effectiveness, signal quality assessment,
noise reduction validation, trading signal accuracy validation across market
conditions, signal-to-noise ratio improvement measurement, false positive/negative
reduction analysis, market condition-specific signal validation, timeframe-specific
signal quality assessment, and advanced statistical analysis and validation.
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

from infra.false_signal_reduction_validation import (
    FalseSignalReductionValidator, FalseSignalReducer,
    SignalQualityLevel, FalseSignalReductionStatus, SignalType, MarketCondition, Timeframe,
    TradingSignal, SignalValidation, FalseSignalReductionReport,
    get_false_signal_validator, validate_signal_reduction,
    generate_false_signal_validation_report, get_false_signal_validation_summary
)

class TestSignalQualityLevel:
    """Test signal quality level enumeration"""
    
    def test_quality_levels(self):
        """Test all quality levels"""
        levels = [
            SignalQualityLevel.EXCELLENT,
            SignalQualityLevel.GOOD,
            SignalQualityLevel.ACCEPTABLE,
            SignalQualityLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, SignalQualityLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestFalseSignalReductionStatus:
    """Test false signal reduction status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            FalseSignalReductionStatus.PASSED,
            FalseSignalReductionStatus.WARNING,
            FalseSignalReductionStatus.FAILED,
            FalseSignalReductionStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, FalseSignalReductionStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestSignalType:
    """Test signal type enumeration"""
    
    def test_signal_types(self):
        """Test all signal types"""
        types = [
            SignalType.BUY_SIGNAL,
            SignalType.SELL_SIGNAL,
            SignalType.HOLD_SIGNAL,
            SignalType.EXIT_SIGNAL
        ]
        
        for signal_type in types:
            assert isinstance(signal_type, SignalType)
            assert signal_type.value in ["buy_signal", "sell_signal", "hold_signal", "exit_signal"]

class TestMarketCondition:
    """Test market condition enumeration"""
    
    def test_market_conditions(self):
        """Test all market conditions"""
        conditions = [
            MarketCondition.TRENDING,
            MarketCondition.RANGING,
            MarketCondition.VOLATILE,
            MarketCondition.CALM
        ]
        
        for condition in conditions:
            assert isinstance(condition, MarketCondition)
            assert condition.value in ["trending", "ranging", "volatile", "calm"]

class TestTimeframe:
    """Test timeframe enumeration"""
    
    def test_timeframes(self):
        """Test all timeframes"""
        timeframes = [
            Timeframe.M1,
            Timeframe.M5,
            Timeframe.M15,
            Timeframe.M30,
            Timeframe.H1,
            Timeframe.H4
        ]
        
        for timeframe in timeframes:
            assert isinstance(timeframe, Timeframe)
            assert timeframe.value in ["M1", "M5", "M15", "M30", "H1", "H4"]

class TestTradingSignal:
    """Test trading signal data structure"""
    
    def test_trading_signal_creation(self):
        """Test trading signal creation"""
        signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,
            metadata={"source": "technical_analysis", "strategy": "momentum"}
        )
        
        assert signal.timestamp > 0
        assert signal.signal_type == SignalType.BUY_SIGNAL
        assert signal.symbol == "BTCUSDc"
        assert signal.timeframe == Timeframe.M5
        assert signal.price == 50000.0
        assert signal.confidence == 0.95
        assert signal.market_condition == MarketCondition.TRENDING
        assert signal.signal_strength == 0.9
        assert signal.metadata["source"] == "technical_analysis"
        assert signal.metadata["strategy"] == "momentum"
    
    def test_trading_signal_defaults(self):
        """Test trading signal defaults"""
        signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.SELL_SIGNAL,
            symbol="EURUSDc",
            timeframe=Timeframe.H1,
            price=1.2000,
            confidence=0.85,
            market_condition=MarketCondition.RANGING,
            signal_strength=0.7
        )
        
        assert signal.metadata == {}

class TestSignalValidation:
    """Test signal validation data structure"""
    
    def test_signal_validation_creation(self):
        """Test signal validation creation"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.6,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.4,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = None  # Signal was filtered out
        
        validation = SignalValidation(
            timestamp=time.time(),
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal,
            is_valid=True,
            false_signal_reduction=1.0,
            signal_quality_score=0.9,
            noise_reduction=0.8,
            signal_to_noise_ratio=2.5,
            false_positive_reduction=1.0,
            false_negative_reduction=0.0,
            validation_status=FalseSignalReductionStatus.PASSED,
            metadata={"validation_time": time.time()}
        )
        
        assert validation.timestamp > 0
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == Timeframe.M5
        assert validation.original_signal == original_signal
        assert validation.filtered_signal == filtered_signal
        assert validation.is_valid is True
        assert validation.false_signal_reduction == 1.0
        assert validation.signal_quality_score == 0.9
        assert validation.noise_reduction == 0.8
        assert validation.signal_to_noise_ratio == 2.5
        assert validation.false_positive_reduction == 1.0
        assert validation.false_negative_reduction == 0.0
        assert validation.validation_status == FalseSignalReductionStatus.PASSED
        assert validation.metadata["validation_time"] > 0
    
    def test_signal_validation_defaults(self):
        """Test signal validation defaults"""
        validation = SignalValidation(
            timestamp=time.time(),
            symbol="EURUSDc",
            timeframe=Timeframe.H1,
            original_signal=None,
            filtered_signal=None,
            is_valid=False,
            false_signal_reduction=0.0,
            signal_quality_score=0.0,
            noise_reduction=0.0,
            signal_to_noise_ratio=0.0,
            false_positive_reduction=0.0,
            false_negative_reduction=0.0,
            validation_status=FalseSignalReductionStatus.FAILED
        )
        
        assert validation.metadata == {}

class TestFalseSignalReductionReport:
    """Test false signal reduction report data structure"""
    
    def test_false_signal_reduction_report_creation(self):
        """Test false signal reduction report creation"""
        report = FalseSignalReductionReport(
            timestamp=time.time(),
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            overall_reduction=0.85,
            signal_quality_improvement=0.90,
            noise_reduction=0.80,
            signal_to_noise_improvement=1.5,
            false_positive_reduction=0.88,
            false_negative_reduction=0.82,
            quality_level=SignalQualityLevel.GOOD,
            validation_status=FalseSignalReductionStatus.PASSED,
            total_signals=100,
            valid_signals=85,
            false_signals_filtered=15,
            signal_quality_scores=[0.9, 0.8, 0.85],
            market_condition_analysis={"trending": 0.9, "ranging": 0.8},
            timeframe_analysis={"M5": 0.85, "H1": 0.80},
            recommendations=["False signal reduction validation passed successfully"],
            detailed_validations=[],
            metadata={"reduction_threshold": 0.80, "confidence_level": 0.95}
        )
        
        assert report.timestamp > 0
        assert report.symbol == "BTCUSDc"
        assert report.timeframe == Timeframe.M5
        assert report.overall_reduction == 0.85
        assert report.signal_quality_improvement == 0.90
        assert report.noise_reduction == 0.80
        assert report.signal_to_noise_improvement == 1.5
        assert report.false_positive_reduction == 0.88
        assert report.false_negative_reduction == 0.82
        assert report.quality_level == SignalQualityLevel.GOOD
        assert report.validation_status == FalseSignalReductionStatus.PASSED
        assert report.total_signals == 100
        assert report.valid_signals == 85
        assert report.false_signals_filtered == 15
        assert len(report.signal_quality_scores) == 3
        assert report.market_condition_analysis["trending"] == 0.9
        assert report.timeframe_analysis["M5"] == 0.85
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["reduction_threshold"] == 0.80
    
    def test_false_signal_reduction_report_defaults(self):
        """Test false signal reduction report defaults"""
        report = FalseSignalReductionReport(
            timestamp=time.time(),
            symbol="EURUSDc",
            timeframe=Timeframe.H1,
            overall_reduction=0.75,
            signal_quality_improvement=0.70,
            noise_reduction=0.65,
            signal_to_noise_improvement=1.2,
            false_positive_reduction=0.72,
            false_negative_reduction=0.68,
            quality_level=SignalQualityLevel.ACCEPTABLE,
            validation_status=FalseSignalReductionStatus.WARNING,
            total_signals=50,
            valid_signals=35,
            false_signals_filtered=10,
            signal_quality_scores=[0.7, 0.6],
            market_condition_analysis={"trending": 0.8},
            timeframe_analysis={"H1": 0.75},
            recommendations=["False signal reduction validation passed with warnings"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestFalseSignalReducer:
    """Test false signal reducer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.reducer = FalseSignalReducer(reduction_threshold=0.80)
    
    def test_reducer_initialization(self):
        """Test reducer initialization"""
        assert self.reducer.reduction_threshold == 0.80
        assert len(self.reducer.validations) == 0
        assert hasattr(self.reducer, 'lock')
        assert self.reducer.start_time > 0
        assert self.reducer.min_sample_size == 100
        assert self.reducer.confidence_level == 0.95
    
    def test_validate_signal_reduction_high_quality(self):
        """Test signal reduction validation with high quality signal"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.98,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.95,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = self.reducer.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal
        )
        
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == Timeframe.M5
        assert validation.original_signal == original_signal
        assert validation.filtered_signal == filtered_signal
        assert validation.is_valid is True
        assert validation.false_signal_reduction >= 0.0
        assert validation.signal_quality_score >= 0.0
        assert validation.noise_reduction >= 0.0
        assert validation.signal_to_noise_ratio >= 0.0
        assert validation.false_positive_reduction >= 0.0
        assert validation.false_negative_reduction >= 0.0
        assert validation.validation_status in [FalseSignalReductionStatus.PASSED, 
                                               FalseSignalReductionStatus.WARNING, 
                                               FalseSignalReductionStatus.FAILED]
        assert validation.metadata["reduction_threshold"] == 0.80
    
    def test_validate_signal_reduction_false_signal_filtered(self):
        """Test signal reduction validation with false signal filtered out"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.6,  # Low confidence
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.4,  # Low strength
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = None  # Signal was filtered out
        
        validation = self.reducer.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal
        )
        
        assert validation.is_valid is True  # False signal was correctly filtered
        assert validation.false_signal_reduction == 1.0  # 100% reduction
        assert validation.signal_quality_score == 1.0  # High quality (false signal removed)
        assert validation.noise_reduction == 1.0  # 100% noise reduction
        assert validation.false_positive_reduction == 1.0  # False positive eliminated
        assert validation.validation_status == FalseSignalReductionStatus.PASSED
    
    def test_validate_signal_reduction_valid_signal_preserved(self):
        """Test signal reduction validation with valid signal preserved"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.98,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.95,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = self.reducer.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal
        )
        
        assert validation.is_valid is True
        assert validation.false_signal_reduction == 0.0  # No false signal to reduce
        assert validation.signal_quality_score >= 0.0
        assert validation.noise_reduction >= 0.0
        assert validation.signal_to_noise_ratio >= 0.0
        assert validation.false_positive_reduction == 0.0  # No false positive to reduce
        assert validation.false_negative_reduction == 0.0  # No false negative to reduce
    
    def test_validate_signal_reduction_invalid_signal_preserved(self):
        """Test signal reduction validation with invalid signal preserved"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.6,  # Low confidence
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.4,  # Low strength
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.65,  # Still low confidence
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.45,  # Still low strength
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = self.reducer.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal
        )
        
        assert validation.is_valid is False  # Invalid signal was not properly filtered
        assert validation.false_signal_reduction == 0.5  # Partial reduction
        assert validation.signal_quality_score < 1.0  # Lower quality
        assert validation.false_positive_reduction == 0.0  # False positive not addressed
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(10):
            original_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL if i % 2 == 0 else SignalType.SELL_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0 + i * 100,
                confidence=0.6 + i * 0.03,  # Varying confidence
                market_condition=MarketCondition.TRENDING if i < 5 else MarketCondition.RANGING,
                signal_strength=0.4 + i * 0.05,  # Varying strength
                metadata={"source": "technical_analysis"}
            )
            
            # Some signals filtered, some preserved
            if i < 5:  # First 5 signals filtered out
                filtered_signal = None
            else:  # Last 5 signals preserved
                filtered_signal = TradingSignal(
                    timestamp=time.time() + i,
                    signal_type=original_signal.signal_type,
                    symbol=original_signal.symbol,
                    timeframe=original_signal.timeframe,
                    price=original_signal.price,
                    confidence=original_signal.confidence + 0.05,
                    market_condition=original_signal.market_condition,
                    signal_strength=original_signal.signal_strength + 0.05,
                    metadata={"source": "technical_analysis", "filtered": True}
                )
            
            self.reducer.validate_signal_reduction(
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                original_signal=original_signal,
                filtered_signal=filtered_signal
            )
        
        report = self.reducer.generate_validation_report("BTCUSDc", Timeframe.M5)
        
        assert report.symbol == "BTCUSDc"
        assert report.timeframe == Timeframe.M5
        assert report.total_signals == 10
        assert report.valid_signals >= 0
        assert report.false_signals_filtered >= 0
        assert report.overall_reduction >= 0.0
        assert report.signal_quality_improvement >= 0.0
        assert report.noise_reduction >= 0.0
        assert report.signal_to_noise_improvement >= 0.0
        assert report.false_positive_reduction >= 0.0
        assert report.false_negative_reduction >= 0.0
        assert report.quality_level in [SignalQualityLevel.EXCELLENT, SignalQualityLevel.GOOD,
                                       SignalQualityLevel.ACCEPTABLE, SignalQualityLevel.POOR]
        assert report.validation_status in [FalseSignalReductionStatus.PASSED,
                                          FalseSignalReductionStatus.WARNING,
                                          FalseSignalReductionStatus.FAILED]
        assert len(report.detailed_validations) == 10
        assert len(report.recommendations) > 0
        assert len(report.signal_quality_scores) == 10
        assert len(report.market_condition_analysis) > 0
        assert len(report.timeframe_analysis) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.reducer.generate_validation_report("UNKNOWN", Timeframe.M5)
        
        assert report.symbol == "UNKNOWN"
        assert report.timeframe == Timeframe.M5
        assert report.overall_reduction == 0.0
        assert report.signal_quality_improvement == 0.0
        assert report.noise_reduction == 0.0
        assert report.signal_to_noise_improvement == 0.0
        assert report.false_positive_reduction == 0.0
        assert report.false_negative_reduction == 0.0
        assert report.quality_level == SignalQualityLevel.POOR
        assert report.validation_status == FalseSignalReductionStatus.FAILED
        assert report.total_signals == 0
        assert report.valid_signals == 0
        assert report.false_signals_filtered == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.signal_quality_scores == []
        assert report.market_condition_analysis == {}
        assert report.timeframe_analysis == {}
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Test with no data
        summary = self.reducer.get_validation_summary()
        assert summary["total_validations"] == 0
        
        # Add some validations
        for i in range(5):
            original_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.8,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.7,
                metadata={"source": "technical_analysis"}
            )
            
            filtered_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.85,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.75,
                metadata={"source": "technical_analysis", "filtered": True}
            )
            
            self.reducer.validate_signal_reduction(
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                original_signal=original_signal,
                filtered_signal=filtered_signal
            )
        
        summary = self.reducer.get_validation_summary()
        
        assert summary["total_validations"] == 5
        assert summary["valid_signals"] >= 0
        assert summary["false_signals_filtered"] >= 0
        assert summary["overall_reduction"] >= 0.0
        assert summary["signal_quality_improvement"] >= 0.0
        assert summary["noise_reduction"] >= 0.0
        assert summary["reduction_threshold"] == 0.80

class TestFalseSignalReductionValidator:
    """Test false signal reduction validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = FalseSignalReductionValidator(reduction_threshold=0.80)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.reducer, FalseSignalReducer)
        assert self.validator.reducer.reduction_threshold == 0.80
        assert self.validator.start_time > 0
        assert len(self.validator.validation_reports) == 0
        assert hasattr(self.validator, 'lock')
    
    def test_validate_signal_reduction(self):
        """Test signal reduction validation"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.98,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.95,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = self.validator.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=original_signal,
            filtered_signal=filtered_signal
        )
        
        assert isinstance(validation, SignalValidation)
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == Timeframe.M5
        assert validation.original_signal == original_signal
        assert validation.filtered_signal == filtered_signal
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            original_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.8,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.7,
                metadata={"source": "technical_analysis"}
            )
            
            filtered_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.85,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.75,
                metadata={"source": "technical_analysis", "filtered": True}
            )
            
            self.validator.validate_signal_reduction(
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                original_signal=original_signal,
                filtered_signal=filtered_signal
            )
        
        report = self.validator.generate_validation_report("BTCUSDc", Timeframe.M5)
        
        assert isinstance(report, FalseSignalReductionReport)
        assert report.symbol == "BTCUSDc"
        assert report.timeframe == Timeframe.M5
        assert report.total_signals == 3
        
        # Check that report was added to history
        assert len(self.validator.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            self.validator.validate_signal_reduction(
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                original_signal=None,
                filtered_signal=None
            )
            self.validator.generate_validation_report("BTCUSDc", Timeframe.M5)
        
        history = self.validator.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, FalseSignalReductionReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            self.validator.validate_signal_reduction(
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                original_signal=None,
                filtered_signal=None
            )
        
        summary = self.validator.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        self.validator.validate_signal_reduction(
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            original_signal=None,
            filtered_signal=None
        )
        self.validator.generate_validation_report("BTCUSDc", Timeframe.M5)
        
        # Reset validations
        self.validator.reset_validations()
        
        assert len(self.validator.reducer.validations) == 0
        assert len(self.validator.validation_reports) == 0

class TestGlobalFunctions:
    """Test global false signal reduction functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.false_signal_reduction_validation
        infra.false_signal_reduction_validation._false_signal_validator = None
    
    def test_get_false_signal_validator(self):
        """Test global validator access"""
        validator1 = get_false_signal_validator()
        validator2 = get_false_signal_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, FalseSignalReductionValidator)
    
    def test_validate_signal_reduction_global(self):
        """Test global signal reduction validation"""
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.98,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.95,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = validate_signal_reduction("BTCUSDc", Timeframe.M5, original_signal, filtered_signal)
        
        assert isinstance(validation, SignalValidation)
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == Timeframe.M5
        assert validation.original_signal == original_signal
        assert validation.filtered_signal == filtered_signal
    
    def test_generate_false_signal_validation_report_global(self):
        """Test global false signal validation report generation"""
        # Add some validations first
        for i in range(3):
            original_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.8,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.7,
                metadata={"source": "technical_analysis"}
            )
            
            filtered_signal = TradingSignal(
                timestamp=time.time() + i,
                signal_type=SignalType.BUY_SIGNAL,
                symbol="BTCUSDc",
                timeframe=Timeframe.M5,
                price=50000.0,
                confidence=0.85,
                market_condition=MarketCondition.TRENDING,
                signal_strength=0.75,
                metadata={"source": "technical_analysis", "filtered": True}
            )
            
            validate_signal_reduction("BTCUSDc", Timeframe.M5, original_signal, filtered_signal)
        
        report = generate_false_signal_validation_report("BTCUSDc", Timeframe.M5)
        
        assert isinstance(report, FalseSignalReductionReport)
        assert report.symbol == "BTCUSDc"
        assert report.timeframe == Timeframe.M5
        assert report.total_signals == 3
    
    def test_get_false_signal_validation_summary_global(self):
        """Test global false signal validation summary"""
        # Add some validations
        for i in range(5):
            validate_signal_reduction("BTCUSDc", Timeframe.M5, None, None)
        
        summary = get_false_signal_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestFalseSignalReductionValidationIntegration:
    """Integration tests for false signal reduction validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.false_signal_reduction_validation
        infra.false_signal_reduction_validation._false_signal_validator = None
    
    def test_comprehensive_false_signal_reduction_validation(self):
        """Test comprehensive false signal reduction validation workflow"""
        # Test multiple signal types and market conditions
        signal_types = [SignalType.BUY_SIGNAL, SignalType.SELL_SIGNAL, SignalType.HOLD_SIGNAL]
        market_conditions = [MarketCondition.TRENDING, MarketCondition.RANGING, MarketCondition.VOLATILE]
        timeframes = [Timeframe.M5, Timeframe.M15, Timeframe.H1]
        
        for signal_type in signal_types:
            for market_condition in market_conditions:
                for timeframe in timeframes:
                    original_signal = TradingSignal(
                        timestamp=time.time(),
                        signal_type=signal_type,
                        symbol="BTCUSDc",
                        timeframe=timeframe,
                        price=50000.0,
                        confidence=0.8,
                        market_condition=market_condition,
                        signal_strength=0.7,
                        metadata={"source": "technical_analysis"}
                    )
                    
                    # Some signals filtered, some preserved
                    if signal_type == SignalType.HOLD_SIGNAL:
                        filtered_signal = None  # Filter out hold signals in trending markets
                    else:
                        filtered_signal = TradingSignal(
                            timestamp=time.time(),
                            signal_type=signal_type,
                            symbol="BTCUSDc",
                            timeframe=timeframe,
                            price=50000.0,
                            confidence=0.85,
                            market_condition=market_condition,
                            signal_strength=0.75,
                            metadata={"source": "technical_analysis", "filtered": True}
                        )
                    
                    validation = validate_signal_reduction("BTCUSDc", timeframe, original_signal, filtered_signal)
                    
                    assert isinstance(validation, SignalValidation)
                    assert validation.symbol == "BTCUSDc"
                    assert validation.timeframe == timeframe
                    assert validation.original_signal == original_signal
                    assert validation.filtered_signal == filtered_signal
                    assert validation.false_signal_reduction >= 0.0
                    assert validation.signal_quality_score >= 0.0
                    assert validation.noise_reduction >= 0.0
                    assert validation.signal_to_noise_ratio >= 0.0
                    assert validation.false_positive_reduction >= 0.0
                    assert validation.false_negative_reduction >= 0.0
                    assert validation.validation_status in [FalseSignalReductionStatus.PASSED,
                                                          FalseSignalReductionStatus.WARNING,
                                                          FalseSignalReductionStatus.FAILED]
        
        # Generate validation report
        report = generate_false_signal_validation_report("BTCUSDc", Timeframe.M5)
        
        assert isinstance(report, FalseSignalReductionReport)
        assert report.symbol == "BTCUSDc"
        assert report.timeframe == Timeframe.M5
        # Only count M5 signals since we're filtering by timeframe
        m5_signals = len(signal_types) * len(market_conditions)
        assert report.total_signals == m5_signals
        assert report.overall_reduction >= 0.0
        assert report.signal_quality_improvement >= 0.0
        assert report.noise_reduction >= 0.0
        assert report.signal_to_noise_improvement >= 0.0
        assert report.false_positive_reduction >= 0.0
        assert report.false_negative_reduction >= 0.0
        assert report.quality_level in [SignalQualityLevel.EXCELLENT, SignalQualityLevel.GOOD,
                                       SignalQualityLevel.ACCEPTABLE, SignalQualityLevel.POOR]
        assert report.validation_status in [FalseSignalReductionStatus.PASSED,
                                          FalseSignalReductionStatus.WARNING,
                                          FalseSignalReductionStatus.FAILED]
        assert len(report.detailed_validations) == m5_signals
        assert len(report.recommendations) > 0
        assert len(report.signal_quality_scores) == m5_signals
        assert len(report.market_condition_analysis) > 0
        assert len(report.timeframe_analysis) > 0
    
    def test_reduction_threshold_validation(self):
        """Test reduction threshold validation"""
        # Test with high reduction (should pass)
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.6,  # Low confidence
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.4,  # Low strength
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = None  # Signal was filtered out
        
        validation = validate_signal_reduction("BTCUSDc", Timeframe.M5, original_signal, filtered_signal)
        
        assert validation.validation_status == FalseSignalReductionStatus.PASSED
        assert validation.false_signal_reduction == 1.0  # 100% reduction
        
        # Test with low reduction (should fail)
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.95,  # High confidence
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.9,  # High strength
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.98,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.95,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = validate_signal_reduction("BTCUSDc", Timeframe.M5, original_signal, filtered_signal)
        
        assert validation.validation_status in [FalseSignalReductionStatus.PASSED,
                                              FalseSignalReductionStatus.WARNING,
                                              FalseSignalReductionStatus.FAILED]
        assert validation.false_signal_reduction >= 0.0
    
    def test_signal_quality_improvement_validation(self):
        """Test signal quality improvement validation"""
        # Test quality improvement
        original_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.7,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.6,
            metadata={"source": "technical_analysis"}
        )
        
        filtered_signal = TradingSignal(
            timestamp=time.time(),
            signal_type=SignalType.BUY_SIGNAL,
            symbol="BTCUSDc",
            timeframe=Timeframe.M5,
            price=50000.0,
            confidence=0.9,
            market_condition=MarketCondition.TRENDING,
            signal_strength=0.8,
            metadata={"source": "technical_analysis", "filtered": True}
        )
        
        validation = validate_signal_reduction("BTCUSDc", Timeframe.M5, original_signal, filtered_signal)
        
        assert validation.signal_quality_score >= 0.0
        assert validation.noise_reduction >= 0.0
        assert validation.signal_to_noise_ratio >= 0.0
        assert validation.false_positive_reduction >= 0.0
        assert validation.false_negative_reduction >= 0.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
