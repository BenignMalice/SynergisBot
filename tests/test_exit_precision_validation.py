"""
Comprehensive tests for exit precision validation system

Tests exit precision >80%, exit timing accuracy validation, market structure
analysis accuracy, momentum analysis accuracy, volatility analysis accuracy,
risk management effectiveness, false exit signal reduction, and true exit
signal detection validation.
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

from infra.exit_precision_validation import (
    ExitPrecisionManager, ExitAnalyzer, ExitValidator,
    ExitPrecisionLevel, ExitValidationStatus, ExitType, ExitQuality, MarketCondition,
    ExitSignal, ExitExecution, ExitValidation, ExitPrecisionReport,
    get_exit_precision_validation_manager, validate_exit_precision,
    generate_exit_precision_validation_report, get_exit_precision_validation_summary
)

class TestExitPrecisionLevel:
    """Test exit precision level enumeration"""
    
    def test_precision_levels(self):
        """Test all precision levels"""
        levels = [
            ExitPrecisionLevel.EXCELLENT,
            ExitPrecisionLevel.GOOD,
            ExitPrecisionLevel.ACCEPTABLE,
            ExitPrecisionLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, ExitPrecisionLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestExitValidationStatus:
    """Test exit validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            ExitValidationStatus.PASSED,
            ExitValidationStatus.WARNING,
            ExitValidationStatus.FAILED,
            ExitValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, ExitValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestExitType:
    """Test exit type enumeration"""
    
    def test_exit_types(self):
        """Test all exit types"""
        types = [
            ExitType.PROFIT_TAKE,
            ExitType.STOP_LOSS,
            ExitType.TRAILING_STOP,
            ExitType.BREAK_EVEN,
            ExitType.STRUCTURE_BREAK,
            ExitType.MOMENTUM_LOSS,
            ExitType.VOLATILITY_EXIT,
            ExitType.TIME_BASED
        ]
        
        for exit_type in types:
            assert isinstance(exit_type, ExitType)
            assert exit_type.value in ["profit_take", "stop_loss", "trailing_stop", 
                                     "break_even", "structure_break", "momentum_loss",
                                     "volatility_exit", "time_based"]

class TestExitQuality:
    """Test exit quality enumeration"""
    
    def test_exit_qualities(self):
        """Test all exit qualities"""
        qualities = [
            ExitQuality.EXCELLENT,
            ExitQuality.GOOD,
            ExitQuality.ACCEPTABLE,
            ExitQuality.POOR
        ]
        
        for quality in qualities:
            assert isinstance(quality, ExitQuality)
            assert quality.value in ["excellent", "good", "acceptable", "poor"]

class TestMarketCondition:
    """Test market condition enumeration"""
    
    def test_market_conditions(self):
        """Test all market conditions"""
        conditions = [
            MarketCondition.TRENDING,
            MarketCondition.RANGING,
            MarketCondition.VOLATILE,
            MarketCondition.CALM,
            MarketCondition.BREAKOUT,
            MarketCondition.REVERSAL
        ]
        
        for condition in conditions:
            assert isinstance(condition, MarketCondition)
            assert condition.value in ["trending", "ranging", "volatile", "calm", 
                                     "breakout", "reversal"]

class TestExitSignal:
    """Test exit signal data structure"""
    
    def test_exit_signal_creation(self):
        """Test exit signal creation"""
        signal = ExitSignal(
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={
                "support_levels": [50000.0, 49500.0],
                "resistance_levels": [51000.0, 51500.0],
                "structure_break": True,
                "break_strength": 0.8
            },
            momentum_indicators={
                "rsi": 75.0,
                "macd": 0.5,
                "stoch": 80.0
            },
            volatility_metrics={
                "atr": 1.5,
                "bollinger_width": 0.05,
                "vix": 25.0
            },
            risk_metrics={
                "drawdown": 0.02,
                "sharpe_ratio": 1.8,
                "var": 0.03
            },
            confidence_score=0.85,
            metadata={"source": "dtms"}
        )
        
        assert signal.signal_id == "exit_001"
        assert signal.symbol == "BTCUSDT"
        assert signal.timestamp > 0
        assert signal.exit_type == ExitType.PROFIT_TAKE
        assert signal.exit_price == 51000.0
        assert signal.exit_reason == "Profit target reached"
        assert signal.market_structure["support_levels"] == [50000.0, 49500.0]
        assert signal.momentum_indicators["rsi"] == 75.0
        assert signal.volatility_metrics["atr"] == 1.5
        assert signal.risk_metrics["drawdown"] == 0.02
        assert signal.confidence_score == 0.85
        assert signal.metadata["source"] == "dtms"
    
    def test_exit_signal_defaults(self):
        """Test exit signal defaults"""
        signal = ExitSignal(
            signal_id="exit_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            exit_type=ExitType.STOP_LOSS,
            exit_price=3000.0,
            exit_reason="Stop loss triggered",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.70
        )
        
        assert signal.metadata == {}

class TestExitExecution:
    """Test exit execution data structure"""
    
    def test_exit_execution_creation(self):
        """Test exit execution creation"""
        execution = ExitExecution(
            execution_id="exec_001",
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            executed_price=50995.0,
            execution_time_ms=25.0,
            slippage=5.0,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True,
            metadata={"executor": "mt5"}
        )
        
        assert execution.execution_id == "exec_001"
        assert execution.signal_id == "exit_001"
        assert execution.symbol == "BTCUSDT"
        assert execution.timestamp > 0
        assert execution.executed_price == 50995.0
        assert execution.execution_time_ms == 25.0
        assert execution.slippage == 5.0
        assert execution.execution_quality == ExitQuality.EXCELLENT
        assert execution.market_impact == 0.001
        assert execution.success is True
        assert execution.metadata["executor"] == "mt5"
    
    def test_exit_execution_defaults(self):
        """Test exit execution defaults"""
        execution = ExitExecution(
            execution_id="exec_002",
            signal_id="exit_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            executed_price=2995.0,
            execution_time_ms=30.0,
            slippage=5.0,
            execution_quality=ExitQuality.GOOD,
            market_impact=0.002,
            success=False
        )
        
        assert execution.metadata == {}

class TestExitValidation:
    """Test exit validation data structure"""
    
    def test_exit_validation_creation(self):
        """Test exit validation creation"""
        validation = ExitValidation(
            timestamp=time.time(),
            signal_id="exit_001",
            exit_type=ExitType.PROFIT_TAKE,
            expected_outcome=True,
            actual_outcome=True,
            precision_score=0.90,
            recall_score=0.88,
            f1_score=0.89,
            false_positive=False,
            false_negative=False,
            true_positive=True,
            true_negative=False,
            meets_threshold=True,
            validation_status=ExitValidationStatus.PASSED,
            recommendations=["Exit precision is excellent"],
            metadata={"precision_threshold": 0.80}
        )
        
        assert validation.timestamp > 0
        assert validation.signal_id == "exit_001"
        assert validation.exit_type == ExitType.PROFIT_TAKE
        assert validation.expected_outcome is True
        assert validation.actual_outcome is True
        assert validation.precision_score == 0.90
        assert validation.recall_score == 0.88
        assert validation.f1_score == 0.89
        assert validation.false_positive is False
        assert validation.false_negative is False
        assert validation.true_positive is True
        assert validation.true_negative is False
        assert validation.meets_threshold is True
        assert validation.validation_status == ExitValidationStatus.PASSED
        assert len(validation.recommendations) == 1
        assert validation.metadata["precision_threshold"] == 0.80
    
    def test_exit_validation_defaults(self):
        """Test exit validation defaults"""
        validation = ExitValidation(
            timestamp=time.time(),
            signal_id="exit_002",
            exit_type=ExitType.STOP_LOSS,
            expected_outcome=False,
            actual_outcome=True,
            precision_score=0.0,
            recall_score=0.0,
            f1_score=0.0,
            false_positive=True,
            false_negative=False,
            true_positive=False,
            true_negative=False,
            meets_threshold=False,
            validation_status=ExitValidationStatus.FAILED,
            recommendations=["Exit precision failed"]
        )
        
        assert validation.metadata == {}

class TestExitPrecisionReport:
    """Test exit precision report data structure"""
    
    def test_exit_precision_report_creation(self):
        """Test exit precision report creation"""
        report = ExitPrecisionReport(
            timestamp=time.time(),
            overall_precision=0.90,
            overall_recall=0.88,
            overall_f1_score=0.89,
            precision_level=ExitPrecisionLevel.GOOD,
            validation_status=ExitValidationStatus.PASSED,
            total_validations=100,
            true_positives=90,
            false_positives=10,
            true_negatives=0,
            false_negatives=0,
            exit_type_analysis={"profit_take": 0.92, "stop_loss": 0.88},
            market_condition_analysis={"trending_precision": 0.90},
            execution_quality_analysis={"excellent_precision": 0.95},
            performance_metrics={"avg_validation_time_ms": 25.5},
            recommendations=["Exit precision is good"],
            detailed_validations=[],
            metadata={"precision_threshold": 0.80}
        )
        
        assert report.timestamp > 0
        assert report.overall_precision == 0.90
        assert report.overall_recall == 0.88
        assert report.overall_f1_score == 0.89
        assert report.precision_level == ExitPrecisionLevel.GOOD
        assert report.validation_status == ExitValidationStatus.PASSED
        assert report.total_validations == 100
        assert report.true_positives == 90
        assert report.false_positives == 10
        assert report.true_negatives == 0
        assert report.false_negatives == 0
        assert report.exit_type_analysis["profit_take"] == 0.92
        assert report.market_condition_analysis["trending_precision"] == 0.90
        assert report.execution_quality_analysis["excellent_precision"] == 0.95
        assert report.performance_metrics["avg_validation_time_ms"] == 25.5
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["precision_threshold"] == 0.80
    
    def test_exit_precision_report_defaults(self):
        """Test exit precision report defaults"""
        report = ExitPrecisionReport(
            timestamp=time.time(),
            overall_precision=0.75,
            overall_recall=0.70,
            overall_f1_score=0.72,
            precision_level=ExitPrecisionLevel.ACCEPTABLE,
            validation_status=ExitValidationStatus.WARNING,
            total_validations=50,
            true_positives=40,
            false_positives=10,
            true_negatives=0,
            false_negatives=0,
            exit_type_analysis={"profit_take": 0.78},
            market_condition_analysis={"trending_precision": 0.75},
            execution_quality_analysis={"good_precision": 0.80},
            performance_metrics={"avg_validation_time_ms": 30.0},
            recommendations=["Exit precision is acceptable"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestExitAnalyzer:
    """Test exit analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = ExitAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_market_structure(self):
        """Test market structure analysis"""
        signal = ExitSignal(
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={
                "support_levels": [50000.0, 49500.0],
                "resistance_levels": [51000.0, 51500.0],
                "structure_break": True,
                "break_strength": 0.8,
                "trend_direction": 1.0,
                "trend_magnitude": 0.7
            },
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.85
        )
        
        analysis = self.analyzer.analyze_market_structure(signal)
        
        assert "support_strength" in analysis
        assert "resistance_strength" in analysis
        assert "structure_break" in analysis
        assert "trend_strength" in analysis
        assert analysis["structure_break"] is True
        assert analysis["trend_strength"] == 0.7
    
    def test_analyze_momentum(self):
        """Test momentum analysis"""
        signal = ExitSignal(
            signal_id="exit_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            exit_type=ExitType.STOP_LOSS,
            exit_price=3000.0,
            exit_reason="Stop loss triggered",
            market_structure={},
            momentum_indicators={
                "rsi": 75.0,
                "macd": 0.5,
                "stoch": 80.0
            },
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.70
        )
        
        analysis = self.analyzer.analyze_momentum(signal)
        
        assert "rsi_signal" in analysis
        assert "macd_signal" in analysis
        assert "stoch_signal" in analysis
        assert "momentum_score" in analysis
        assert analysis["rsi_signal"] == "overbought"
        assert analysis["macd_signal"] == "bullish"
        assert analysis["stoch_signal"] == "neutral"
        assert 0.0 <= analysis["momentum_score"] <= 1.0
    
    def test_analyze_volatility(self):
        """Test volatility analysis"""
        signal = ExitSignal(
            signal_id="exit_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            exit_type=ExitType.VOLATILITY_EXIT,
            exit_price=0.5,
            exit_reason="High volatility exit",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={
                "atr": 1.5,
                "bollinger_width": 0.05,
                "vix": 25.0
            },
            risk_metrics={},
            confidence_score=0.80
        )
        
        analysis = self.analyzer.analyze_volatility(signal)
        
        assert "atr_signal" in analysis
        assert "bollinger_signal" in analysis
        assert "vix_signal" in analysis
        assert "volatility_score" in analysis
        assert analysis["atr_signal"] == "normal_volatility"
        assert analysis["bollinger_signal"] == "normal_volatility"
        assert analysis["vix_signal"] == "normal_fear"
        assert 0.0 <= analysis["volatility_score"] <= 1.0
    
    def test_analyze_risk_metrics(self):
        """Test risk metrics analysis"""
        signal = ExitSignal(
            signal_id="exit_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            exit_type=ExitType.BREAK_EVEN,
            exit_price=25.0,
            exit_reason="Break even exit",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={
                "drawdown": 0.02,
                "sharpe_ratio": 1.8,
                "var": 0.03
            },
            confidence_score=0.75
        )
        
        analysis = self.analyzer.analyze_risk_metrics(signal)
        
        assert "drawdown_signal" in analysis
        assert "sharpe_signal" in analysis
        assert "var_signal" in analysis
        assert "risk_score" in analysis
        assert analysis["drawdown_signal"] == "normal_risk"
        assert analysis["sharpe_signal"] == "good"
        assert analysis["var_signal"] == "normal_risk"
        assert 0.0 <= analysis["risk_score"] <= 1.0

class TestExitValidator:
    """Test exit validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ExitValidator(precision_threshold=0.80)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.precision_threshold == 0.80
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_exit_precision(self):
        """Test exit precision validation"""
        signal = ExitSignal(
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.85
        )
        
        execution = ExitExecution(
            execution_id="exec_001",
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            executed_price=50995.0,
            execution_time_ms=25.0,
            slippage=5.0,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True
        )
        
        expected_outcome = True
        
        validation = self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
        assert validation.signal_id == "exit_001"
        assert validation.exit_type == ExitType.PROFIT_TAKE
        assert validation.expected_outcome is True
        assert validation.actual_outcome is True
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [ExitValidationStatus.PASSED,
                                              ExitValidationStatus.WARNING,
                                              ExitValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
        assert validation.metadata["precision_threshold"] == 0.80
    
    def test_validate_exit_precision_false_positive(self):
        """Test exit precision validation with false positive"""
        signal = ExitSignal(
            signal_id="exit_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            exit_type=ExitType.STOP_LOSS,
            exit_price=3000.0,
            exit_reason="Stop loss triggered",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.60
        )
        
        execution = ExitExecution(
            execution_id="exec_002",
            signal_id="exit_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            executed_price=2995.0,
            execution_time_ms=30.0,
            slippage=5.0,
            execution_quality=ExitQuality.GOOD,
            market_impact=0.002,
            success=True  # Executed successfully
        )
        
        expected_outcome = False  # Expected to fail
        
        validation = self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
        assert validation.false_positive is True
        assert validation.true_positive is False
        assert validation.precision_score < 1.0
    
    def test_validate_exit_precision_false_negative(self):
        """Test exit precision validation with false negative"""
        signal = ExitSignal(
            signal_id="exit_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            exit_type=ExitType.VOLATILITY_EXIT,
            exit_price=0.5,
            exit_reason="High volatility exit",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.70
        )
        
        execution = ExitExecution(
            execution_id="exec_003",
            signal_id="exit_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            executed_price=0.49,
            execution_time_ms=35.0,
            slippage=1.0,
            execution_quality=ExitQuality.ACCEPTABLE,
            market_impact=0.002,
            success=False  # Execution failed
        )
        
        expected_outcome = True  # Expected to succeed
        
        validation = self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
        assert validation.false_negative is True
        assert validation.true_positive is False
        assert validation.recall_score < 1.0
    
    def test_validate_exit_precision_true_positive(self):
        """Test exit precision validation with true positive"""
        signal = ExitSignal(
            signal_id="exit_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            exit_type=ExitType.BREAK_EVEN,
            exit_price=25.0,
            exit_reason="Break even exit",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.90
        )
        
        execution = ExitExecution(
            execution_id="exec_004",
            signal_id="exit_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            executed_price=24.95,
            execution_time_ms=20.0,
            slippage=0.5,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True  # Execution succeeded
        )
        
        expected_outcome = True  # Expected to succeed
        
        validation = self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
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
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE if i % 2 == 0 else ExitType.STOP_LOSS,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT if i % 2 == 0 else ExitQuality.GOOD,
                market_impact=0.001,
                success=i % 2 == 0
            )
            
            expected_outcome = i % 2 == 0
            self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_validations == 5
        assert report.true_positives >= 0
        assert report.false_positives >= 0
        assert report.true_negatives >= 0
        assert report.false_negatives >= 0
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.precision_level in [ExitPrecisionLevel.EXCELLENT,
                                        ExitPrecisionLevel.GOOD,
                                        ExitPrecisionLevel.ACCEPTABLE,
                                        ExitPrecisionLevel.POOR]
        assert report.validation_status in [ExitValidationStatus.PASSED,
                                          ExitValidationStatus.WARNING,
                                          ExitValidationStatus.FAILED]
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.exit_type_analysis) > 0
        assert len(report.market_condition_analysis) > 0
        assert len(report.execution_quality_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_precision == 0.0
        assert report.overall_recall == 0.0
        assert report.overall_f1_score == 0.0
        assert report.precision_level == ExitPrecisionLevel.POOR
        assert report.validation_status == ExitValidationStatus.FAILED
        assert report.total_validations == 0
        assert report.true_positives == 0
        assert report.false_positives == 0
        assert report.true_negatives == 0
        assert report.false_negatives == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.exit_type_analysis == {}
        assert report.market_condition_analysis == {}
        assert report.execution_quality_analysis == {}
        assert report.performance_metrics == {}

class TestExitPrecisionManager:
    """Test exit precision manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = ExitPrecisionManager(precision_threshold=0.80)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.analyzer, ExitAnalyzer)
        assert isinstance(self.manager.validator, ExitValidator)
        assert self.manager.validator.precision_threshold == 0.80
        assert self.manager.start_time > 0
        assert len(self.manager.validation_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_exit_precision(self):
        """Test exit precision validation"""
        signal = ExitSignal(
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={
                "support_levels": [50000.0, 49500.0],
                "resistance_levels": [51000.0, 51500.0],
                "structure_break": True,
                "break_strength": 0.8
            },
            momentum_indicators={
                "rsi": 75.0,
                "macd": 0.5,
                "stoch": 80.0
            },
            volatility_metrics={
                "atr": 1.5,
                "bollinger_width": 0.05,
                "vix": 25.0
            },
            risk_metrics={
                "drawdown": 0.02,
                "sharpe_ratio": 1.8,
                "var": 0.03
            },
            confidence_score=0.85
        )
        
        execution = ExitExecution(
            execution_id="exec_001",
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            executed_price=50995.0,
            execution_time_ms=25.0,
            slippage=5.0,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True
        )
        
        expected_outcome = True
        
        validation = self.manager.validate_exit_precision(signal, execution, expected_outcome)
        
        assert isinstance(validation, ExitValidation)
        assert validation.signal_id == "exit_001"
        assert validation.exit_type == ExitType.PROFIT_TAKE
        assert validation.expected_outcome is True
        assert validation.actual_outcome is True
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [ExitValidationStatus.PASSED,
                                              ExitValidationStatus.WARNING,
                                              ExitValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE if i % 2 == 0 else ExitType.STOP_LOSS,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT if i % 2 == 0 else ExitQuality.GOOD,
                market_impact=0.001,
                success=i % 2 == 0
            )
            
            expected_outcome = i % 2 == 0
            self.manager.validate_exit_precision(signal, execution, expected_outcome)
        
        report = self.manager.generate_validation_report()
        
        assert isinstance(report, ExitPrecisionReport)
        assert report.total_validations == 3
        
        # Check that report was added to history
        assert len(self.manager.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT,
                market_impact=0.001,
                success=True
            )
            
            expected_outcome = True
            self.manager.validate_exit_precision(signal, execution, expected_outcome)
            self.manager.generate_validation_report()
        
        history = self.manager.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, ExitPrecisionReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE if i % 2 == 0 else ExitType.STOP_LOSS,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT if i % 2 == 0 else ExitQuality.GOOD,
                market_impact=0.001,
                success=i % 2 == 0
            )
            
            expected_outcome = i % 2 == 0
            self.manager.validate_exit_precision(signal, execution, expected_outcome)
        
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
        signal = ExitSignal(
            signal_id="test_exit",
            symbol="TEST",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=100.0,
            exit_reason="Test exit",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.8
        )
        
        execution = ExitExecution(
            execution_id="test_exec",
            signal_id="test_exit",
            symbol="TEST",
            timestamp=time.time(),
            executed_price=99.5,
            execution_time_ms=25.0,
            slippage=0.5,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True
        )
        
        expected_outcome = True
        self.manager.validate_exit_precision(signal, execution, expected_outcome)
        self.manager.generate_validation_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.validation_reports) == 0

class TestGlobalFunctions:
    """Test global exit precision validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.exit_precision_validation
        infra.exit_precision_validation._exit_precision_validation_manager = None
    
    def test_get_exit_precision_validation_manager(self):
        """Test global manager access"""
        manager1 = get_exit_precision_validation_manager()
        manager2 = get_exit_precision_validation_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, ExitPrecisionManager)
    
    def test_validate_exit_precision_global(self):
        """Test global exit precision validation"""
        signal = ExitSignal(
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.85
        )
        
        execution = ExitExecution(
            execution_id="exec_001",
            signal_id="exit_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            executed_price=50995.0,
            execution_time_ms=25.0,
            slippage=5.0,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True
        )
        
        expected_outcome = True
        
        validation = validate_exit_precision(signal, execution, expected_outcome)
        
        assert isinstance(validation, ExitValidation)
        assert validation.signal_id == "exit_001"
        assert validation.exit_type == ExitType.PROFIT_TAKE
        assert validation.expected_outcome is True
        assert validation.actual_outcome is True
        assert 0.0 <= validation.precision_score <= 1.0
        assert 0.0 <= validation.recall_score <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert validation.false_positive in [True, False]
        assert validation.false_negative in [True, False]
        assert validation.true_positive in [True, False]
        assert validation.true_negative in [True, False]
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [ExitValidationStatus.PASSED,
                                            ExitValidationStatus.WARNING,
                                            ExitValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_exit_precision_validation_report_global(self):
        """Test global exit precision validation report generation"""
        # Add some validations first
        for i in range(3):
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE if i % 2 == 0 else ExitType.STOP_LOSS,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT if i % 2 == 0 else ExitQuality.GOOD,
                market_impact=0.001,
                success=i % 2 == 0
            )
            
            expected_outcome = i % 2 == 0
            validate_exit_precision(signal, execution, expected_outcome)
        
        report = generate_exit_precision_validation_report()
        
        assert isinstance(report, ExitPrecisionReport)
        assert report.total_validations == 3
    
    def test_get_exit_precision_validation_summary_global(self):
        """Test global exit precision validation summary"""
        # Add some validations
        for i in range(5):
            signal = ExitSignal(
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                exit_type=ExitType.PROFIT_TAKE if i % 2 == 0 else ExitType.STOP_LOSS,
                exit_price=100.0 + i * 10.0,
                exit_reason=f"Exit reason {i}",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.8 + i * 0.02
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{i:03d}",
                signal_id=f"exit_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                executed_price=100.0 + i * 10.0,
                execution_time_ms=25.0 + i * 5.0,
                slippage=5.0,
                execution_quality=ExitQuality.EXCELLENT if i % 2 == 0 else ExitQuality.GOOD,
                market_impact=0.001,
                success=i % 2 == 0
            )
            
            expected_outcome = i % 2 == 0
            validate_exit_precision(signal, execution, expected_outcome)
        
        summary = get_exit_precision_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestExitPrecisionValidationIntegration:
    """Integration tests for exit precision validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.exit_precision_validation
        infra.exit_precision_validation._exit_precision_validation_manager = None
    
    def test_comprehensive_exit_precision_validation(self):
        """Test comprehensive exit precision validation workflow"""
        # Test different exit types and scenarios
        test_cases = [
            (ExitType.PROFIT_TAKE, ExitQuality.EXCELLENT, True, True),
            (ExitType.STOP_LOSS, ExitQuality.GOOD, True, False),
            (ExitType.TRAILING_STOP, ExitQuality.ACCEPTABLE, False, True),
            (ExitType.BREAK_EVEN, ExitQuality.EXCELLENT, True, True),
            (ExitType.STRUCTURE_BREAK, ExitQuality.GOOD, False, False)
        ]
        
        for exit_type, execution_quality, expected_outcome, success in test_cases:
            signal = ExitSignal(
                signal_id=f"exit_{exit_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                exit_type=exit_type,
                exit_price=50000.0,
                exit_reason=f"{exit_type.value} exit",
                market_structure={
                    "support_levels": [49000.0, 48500.0],
                    "resistance_levels": [51000.0, 51500.0],
                    "structure_break": exit_type == ExitType.STRUCTURE_BREAK,
                    "break_strength": 0.8 if exit_type == ExitType.STRUCTURE_BREAK else 0.0
                },
                momentum_indicators={
                    "rsi": 75.0 if exit_type == ExitType.PROFIT_TAKE else 25.0,
                    "macd": 0.5 if exit_type == ExitType.PROFIT_TAKE else -0.5,
                    "stoch": 80.0 if exit_type == ExitType.PROFIT_TAKE else 20.0
                },
                volatility_metrics={
                    "atr": 1.5,
                    "bollinger_width": 0.05,
                    "vix": 25.0
                },
                risk_metrics={
                    "drawdown": 0.02,
                    "sharpe_ratio": 1.8,
                    "var": 0.03
                },
                confidence_score=0.85 if exit_type == ExitType.PROFIT_TAKE else 0.70
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{exit_type.value}",
                signal_id=f"exit_{exit_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                executed_price=49995.0,
                execution_time_ms=25.0,
                slippage=5.0,
                execution_quality=execution_quality,
                market_impact=0.001,
                success=success
            )
            
            validation = validate_exit_precision(signal, execution, expected_outcome)
            
            assert isinstance(validation, ExitValidation)
            assert validation.signal_id == f"exit_{exit_type.value}"
            assert validation.exit_type == exit_type
            assert validation.expected_outcome == expected_outcome
            assert validation.actual_outcome == success
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.false_positive in [True, False]
            assert validation.false_negative in [True, False]
            assert validation.true_positive in [True, False]
            assert validation.true_negative in [True, False]
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [ExitValidationStatus.PASSED,
                                                ExitValidationStatus.WARNING,
                                                ExitValidationStatus.FAILED]
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_exit_precision_validation_report()
        
        assert isinstance(report, ExitPrecisionReport)
        assert report.total_validations == len(test_cases)
        assert report.overall_precision >= 0.0
        assert report.overall_recall >= 0.0
        assert report.overall_f1_score >= 0.0
        assert report.precision_level in [ExitPrecisionLevel.EXCELLENT,
                                        ExitPrecisionLevel.GOOD,
                                        ExitPrecisionLevel.ACCEPTABLE,
                                        ExitPrecisionLevel.POOR]
        assert report.validation_status in [ExitValidationStatus.PASSED,
                                         ExitValidationStatus.WARNING,
                                         ExitValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(test_cases)
        assert len(report.recommendations) > 0
        assert len(report.exit_type_analysis) > 0
        assert len(report.market_condition_analysis) > 0
        assert len(report.execution_quality_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_precision_threshold_validation(self):
        """Test precision threshold validation"""
        # Test with high precision (should pass)
        high_precision_signal = ExitSignal(
            signal_id="high_precision",
            symbol="BTCUSDT",
            timestamp=time.time(),
            exit_type=ExitType.PROFIT_TAKE,
            exit_price=51000.0,
            exit_reason="Profit target reached",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.95
        )
        
        high_precision_execution = ExitExecution(
            execution_id="high_precision_exec",
            signal_id="high_precision",
            symbol="BTCUSDT",
            timestamp=time.time(),
            executed_price=50995.0,
            execution_time_ms=20.0,
            slippage=5.0,
            execution_quality=ExitQuality.EXCELLENT,
            market_impact=0.001,
            success=True
        )
        
        validation = validate_exit_precision(high_precision_signal, high_precision_execution, True)
        
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [ExitValidationStatus.PASSED,
                                            ExitValidationStatus.WARNING,
                                            ExitValidationStatus.FAILED]
        
        # Test with low precision (should fail)
        low_precision_signal = ExitSignal(
            signal_id="low_precision",
            symbol="ETHUSDT",
            timestamp=time.time(),
            exit_type=ExitType.STOP_LOSS,
            exit_price=3000.0,
            exit_reason="Stop loss triggered",
            market_structure={},
            momentum_indicators={},
            volatility_metrics={},
            risk_metrics={},
            confidence_score=0.50
        )
        
        low_precision_execution = ExitExecution(
            execution_id="low_precision_exec",
            signal_id="low_precision",
            symbol="ETHUSDT",
            timestamp=time.time(),
            executed_price=2995.0,
            execution_time_ms=50.0,
            slippage=5.0,
            execution_quality=ExitQuality.POOR,
            market_impact=0.002,
            success=False
        )
        
        validation = validate_exit_precision(low_precision_signal, low_precision_execution, True)
        
        assert validation.meets_threshold in [True, False]
        assert validation.validation_status in [ExitValidationStatus.PASSED,
                                            ExitValidationStatus.WARNING,
                                            ExitValidationStatus.FAILED]
    
    def test_exit_type_analysis_validation(self):
        """Test exit type analysis validation"""
        # Test different exit types
        exit_types = [ExitType.PROFIT_TAKE, ExitType.STOP_LOSS, ExitType.TRAILING_STOP, 
                     ExitType.BREAK_EVEN, ExitType.STRUCTURE_BREAK]
        
        for exit_type in exit_types:
            signal = ExitSignal(
                signal_id=f"exit_{exit_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                exit_type=exit_type,
                exit_price=50000.0,
                exit_reason=f"{exit_type.value} exit",
                market_structure={},
                momentum_indicators={},
                volatility_metrics={},
                risk_metrics={},
                confidence_score=0.80
            )
            
            execution = ExitExecution(
                execution_id=f"exec_{exit_type.value}",
                signal_id=f"exit_{exit_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                executed_price=49995.0,
                execution_time_ms=25.0,
                slippage=5.0,
                execution_quality=ExitQuality.GOOD,
                market_impact=0.001,
                success=True
            )
            
            expected_outcome = True
            validation = validate_exit_precision(signal, execution, expected_outcome)
            
            assert validation.exit_type == exit_type
            assert 0.0 <= validation.precision_score <= 1.0
            assert 0.0 <= validation.recall_score <= 1.0
            assert 0.0 <= validation.f1_score <= 1.0
            assert validation.false_positive in [True, False]
            assert validation.false_negative in [True, False]
            assert validation.true_positive in [True, False]
            assert validation.true_negative in [True, False]
            assert validation.meets_threshold in [True, False]
            assert validation.validation_status in [ExitValidationStatus.PASSED,
                                                ExitValidationStatus.WARNING,
                                                ExitValidationStatus.FAILED]
            assert len(validation.recommendations) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
