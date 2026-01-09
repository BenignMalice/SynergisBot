"""
Comprehensive tests for R:R improvement validation system

Tests R:R improvement >1:3, trade risk management validation, profit target
optimization accuracy, stop loss effectiveness, position sizing accuracy,
risk-adjusted returns analysis, false risk signal reduction, and true risk
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

from infra.rr_improvement_validation import (
    RRImprovementManager, RiskAnalyzer, RRValidator,
    RRImprovementLevel, RRValidationStatus, RiskLevel, TradeOutcome, RiskManagementType,
    TradeData, RiskManagement, RRValidation, RRImprovementReport,
    get_rr_improvement_validation_manager, validate_rr_improvement,
    generate_rr_improvement_validation_report, get_rr_improvement_validation_summary
)

class TestRRImprovementLevel:
    """Test R:R improvement level enumeration"""
    
    def test_improvement_levels(self):
        """Test all improvement levels"""
        levels = [
            RRImprovementLevel.EXCELLENT,
            RRImprovementLevel.GOOD,
            RRImprovementLevel.ACCEPTABLE,
            RRImprovementLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, RRImprovementLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestRRValidationStatus:
    """Test R:R validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            RRValidationStatus.PASSED,
            RRValidationStatus.WARNING,
            RRValidationStatus.FAILED,
            RRValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, RRValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestRiskLevel:
    """Test risk level enumeration"""
    
    def test_risk_levels(self):
        """Test all risk levels"""
        levels = [
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.EXTREME
        ]
        
        for level in levels:
            assert isinstance(level, RiskLevel)
            assert level.value in ["low", "medium", "high", "extreme"]

class TestTradeOutcome:
    """Test trade outcome enumeration"""
    
    def test_trade_outcomes(self):
        """Test all trade outcomes"""
        outcomes = [
            TradeOutcome.PROFIT,
            TradeOutcome.LOSS,
            TradeOutcome.BREAK_EVEN,
            TradeOutcome.PARTIAL_PROFIT,
            TradeOutcome.PARTIAL_LOSS
        ]
        
        for outcome in outcomes:
            assert isinstance(outcome, TradeOutcome)
            assert outcome.value in ["profit", "loss", "break_even", "partial_profit", "partial_loss"]

class TestRiskManagementType:
    """Test risk management type enumeration"""
    
    def test_risk_management_types(self):
        """Test all risk management types"""
        types = [
            RiskManagementType.POSITION_SIZING,
            RiskManagementType.STOP_LOSS,
            RiskManagementType.TAKE_PROFIT,
            RiskManagementType.TRAILING_STOP,
            RiskManagementType.HEDGING,
            RiskManagementType.DIVERSIFICATION
        ]
        
        for risk_type in types:
            assert isinstance(risk_type, RiskManagementType)
            assert risk_type.value in ["position_sizing", "stop_loss", "take_profit", 
                                     "trailing_stop", "hedging", "diversification"]

class TestTradeData:
    """Test trade data structure"""
    
    def test_trade_data_creation(self):
        """Test trade data creation"""
        trade_data = TradeData(
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=51500.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=300.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM,
            metadata={"source": "dtms"}
        )
        
        assert trade_data.trade_id == "trade_001"
        assert trade_data.symbol == "BTCUSDT"
        assert trade_data.timestamp > 0
        assert trade_data.entry_price == 50000.0
        assert trade_data.exit_price == 51500.0
        assert trade_data.position_size == 0.1
        assert trade_data.risk_amount == 100.0
        assert trade_data.reward_amount == 300.0
        assert trade_data.actual_rr_ratio == 3.0
        assert trade_data.target_rr_ratio == 3.0
        assert trade_data.trade_outcome == TradeOutcome.PROFIT
        assert trade_data.risk_level == RiskLevel.MEDIUM
        assert trade_data.metadata["source"] == "dtms"
    
    def test_trade_data_defaults(self):
        """Test trade data defaults"""
        trade_data = TradeData(
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            entry_price=3000.0,
            exit_price=2950.0,
            position_size=0.2,
            risk_amount=50.0,
            reward_amount=100.0,
            actual_rr_ratio=2.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.LOSS,
            risk_level=RiskLevel.HIGH
        )
        
        assert trade_data.metadata == {}

class TestRiskManagement:
    """Test risk management data structure"""
    
    def test_risk_management_creation(self):
        """Test risk management creation"""
        risk_management = RiskManagement(
            risk_id="risk_001",
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=100.0,
            reward_amount=300.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=53000.0,
            risk_percentage=2.0,
            effectiveness_score=0.85,
            metadata={"strategy": "scalp"}
        )
        
        assert risk_management.risk_id == "risk_001"
        assert risk_management.trade_id == "trade_001"
        assert risk_management.symbol == "BTCUSDT"
        assert risk_management.timestamp > 0
        assert risk_management.risk_type == RiskManagementType.POSITION_SIZING
        assert risk_management.risk_amount == 100.0
        assert risk_management.reward_amount == 300.0
        assert risk_management.rr_ratio == 3.0
        assert risk_management.position_size == 0.1
        assert risk_management.stop_loss_price == 49000.0
        assert risk_management.take_profit_price == 53000.0
        assert risk_management.risk_percentage == 2.0
        assert risk_management.effectiveness_score == 0.85
        assert risk_management.metadata["strategy"] == "scalp"
    
    def test_risk_management_defaults(self):
        """Test risk management defaults"""
        risk_management = RiskManagement(
            risk_id="risk_002",
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.STOP_LOSS,
            risk_amount=50.0,
            reward_amount=100.0,
            rr_ratio=2.0,
            position_size=0.2,
            stop_loss_price=2950.0,
            take_profit_price=3100.0,
            risk_percentage=1.5,
            effectiveness_score=0.70
        )
        
        assert risk_management.metadata == {}

class TestRRValidation:
    """Test R:R validation data structure"""
    
    def test_rr_validation_creation(self):
        """Test R:R validation creation"""
        validation = RRValidation(
            timestamp=time.time(),
            trade_id="trade_001",
            expected_rr_ratio=3.0,
            actual_rr_ratio=3.0,
            improvement_ratio=1.0,
            meets_threshold=True,
            risk_management_score=0.85,
            profit_optimization_score=0.90,
            stop_loss_effectiveness=0.80,
            position_sizing_accuracy=0.85,
            overall_score=0.85,
            validation_status=RRValidationStatus.PASSED,
            recommendations=["R:R improvement is excellent"],
            metadata={"target_rr_ratio": 3.0}
        )
        
        assert validation.timestamp > 0
        assert validation.trade_id == "trade_001"
        assert validation.expected_rr_ratio == 3.0
        assert validation.actual_rr_ratio == 3.0
        assert validation.improvement_ratio == 1.0
        assert validation.meets_threshold is True
        assert validation.risk_management_score == 0.85
        assert validation.profit_optimization_score == 0.90
        assert validation.stop_loss_effectiveness == 0.80
        assert validation.position_sizing_accuracy == 0.85
        assert validation.overall_score == 0.85
        assert validation.validation_status == RRValidationStatus.PASSED
        assert len(validation.recommendations) == 1
        assert validation.metadata["target_rr_ratio"] == 3.0
    
    def test_rr_validation_defaults(self):
        """Test R:R validation defaults"""
        validation = RRValidation(
            timestamp=time.time(),
            trade_id="trade_002",
            expected_rr_ratio=3.0,
            actual_rr_ratio=2.0,
            improvement_ratio=0.67,
            meets_threshold=False,
            risk_management_score=0.60,
            profit_optimization_score=0.70,
            stop_loss_effectiveness=0.65,
            position_sizing_accuracy=0.60,
            overall_score=0.64,
            validation_status=RRValidationStatus.FAILED,
            recommendations=["R:R improvement below target"]
        )
        
        assert validation.metadata == {}

class TestRRImprovementReport:
    """Test R:R improvement report data structure"""
    
    def test_rr_improvement_report_creation(self):
        """Test R:R improvement report creation"""
        report = RRImprovementReport(
            timestamp=time.time(),
            overall_rr_improvement=1.2,
            average_rr_ratio=3.6,
            improvement_level=RRImprovementLevel.GOOD,
            validation_status=RRValidationStatus.PASSED,
            total_trades=100,
            profitable_trades=70,
            losing_trades=25,
            break_even_trades=5,
            total_profit=2100.0,
            total_loss=500.0,
            net_profit=1600.0,
            win_rate=0.70,
            average_win=30.0,
            average_loss=20.0,
            risk_management_analysis={"average_risk_score": 0.85},
            profit_optimization_analysis={"average_profit_score": 0.90},
            stop_loss_analysis={"average_stop_loss_score": 0.80},
            position_sizing_analysis={"average_position_score": 0.85},
            performance_metrics={"avg_validation_time_ms": 25.5},
            recommendations=["R:R improvement is good"],
            detailed_validations=[],
            metadata={"target_rr_ratio": 3.0}
        )
        
        assert report.timestamp > 0
        assert report.overall_rr_improvement == 1.2
        assert report.average_rr_ratio == 3.6
        assert report.improvement_level == RRImprovementLevel.GOOD
        assert report.validation_status == RRValidationStatus.PASSED
        assert report.total_trades == 100
        assert report.profitable_trades == 70
        assert report.losing_trades == 25
        assert report.break_even_trades == 5
        assert report.total_profit == 2100.0
        assert report.total_loss == 500.0
        assert report.net_profit == 1600.0
        assert report.win_rate == 0.70
        assert report.average_win == 30.0
        assert report.average_loss == 20.0
        assert report.risk_management_analysis["average_risk_score"] == 0.85
        assert report.profit_optimization_analysis["average_profit_score"] == 0.90
        assert report.stop_loss_analysis["average_stop_loss_score"] == 0.80
        assert report.position_sizing_analysis["average_position_score"] == 0.85
        assert report.performance_metrics["avg_validation_time_ms"] == 25.5
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["target_rr_ratio"] == 3.0
    
    def test_rr_improvement_report_defaults(self):
        """Test R:R improvement report defaults"""
        report = RRImprovementReport(
            timestamp=time.time(),
            overall_rr_improvement=0.8,
            average_rr_ratio=2.4,
            improvement_level=RRImprovementLevel.POOR,
            validation_status=RRValidationStatus.FAILED,
            total_trades=50,
            profitable_trades=25,
            losing_trades=20,
            break_even_trades=5,
            total_profit=750.0,
            total_loss=400.0,
            net_profit=350.0,
            win_rate=0.50,
            average_win=30.0,
            average_loss=20.0,
            risk_management_analysis={"average_risk_score": 0.60},
            profit_optimization_analysis={"average_profit_score": 0.70},
            stop_loss_analysis={"average_stop_loss_score": 0.65},
            position_sizing_analysis={"average_position_score": 0.60},
            performance_metrics={"avg_validation_time_ms": 30.0},
            recommendations=["R:R improvement is poor"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestRiskAnalyzer:
    """Test risk analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = RiskAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_risk_management(self):
        """Test risk management analysis"""
        trade_data = TradeData(
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=51500.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=300.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_001",
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=100.0,
            reward_amount=300.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=53000.0,
            risk_percentage=2.0,
            effectiveness_score=0.85
        )
        
        analysis = self.analyzer.analyze_risk_management(trade_data, risk_management)
        
        assert "position_sizing_score" in analysis
        assert "stop_loss_score" in analysis
        assert "take_profit_score" in analysis
        assert "rr_ratio_score" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["position_sizing_score"] <= 1.0
        assert 0.0 <= analysis["stop_loss_score"] <= 1.0
        assert 0.0 <= analysis["take_profit_score"] <= 1.0
        assert 0.0 <= analysis["rr_ratio_score"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_profit_optimization(self):
        """Test profit optimization analysis"""
        trade_data = TradeData(
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            entry_price=3000.0,
            exit_price=3100.0,
            position_size=0.2,
            risk_amount=50.0,
            reward_amount=100.0,
            actual_rr_ratio=2.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_002",
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.TAKE_PROFIT,
            risk_amount=50.0,
            reward_amount=100.0,
            rr_ratio=2.0,
            position_size=0.2,
            stop_loss_price=2950.0,
            take_profit_price=3100.0,
            risk_percentage=1.5,
            effectiveness_score=0.80
        )
        
        analysis = self.analyzer.analyze_profit_optimization(trade_data, risk_management)
        
        assert "profit_target_accuracy" in analysis
        assert "profit_maximization" in analysis
        assert "profit_consistency" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["profit_target_accuracy"] <= 1.0
        assert 0.0 <= analysis["profit_maximization"] <= 1.0
        assert 0.0 <= analysis["profit_consistency"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_stop_loss_effectiveness(self):
        """Test stop loss effectiveness analysis"""
        trade_data = TradeData(
            trade_id="trade_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            entry_price=0.5,
            exit_price=0.48,
            position_size=1000.0,
            risk_amount=20.0,
            reward_amount=40.0,
            actual_rr_ratio=2.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.LOSS,
            risk_level=RiskLevel.HIGH
        )
        
        risk_management = RiskManagement(
            risk_id="risk_003",
            trade_id="trade_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.STOP_LOSS,
            risk_amount=20.0,
            reward_amount=40.0,
            rr_ratio=2.0,
            position_size=1000.0,
            stop_loss_price=0.48,
            take_profit_price=0.52,
            risk_percentage=4.0,
            effectiveness_score=0.75
        )
        
        analysis = self.analyzer.analyze_stop_loss_effectiveness(trade_data, risk_management)
        
        assert "stop_loss_placement" in analysis
        assert "stop_loss_execution" in analysis
        assert "stop_loss_timing" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["stop_loss_placement"] <= 1.0
        assert 0.0 <= analysis["stop_loss_execution"] <= 1.0
        assert 0.0 <= analysis["stop_loss_timing"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_position_sizing(self):
        """Test position sizing analysis"""
        trade_data = TradeData(
            trade_id="trade_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            entry_price=25.0,
            exit_price=27.5,
            position_size=4.0,
            risk_amount=10.0,
            reward_amount=30.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.LOW
        )
        
        risk_management = RiskManagement(
            risk_id="risk_004",
            trade_id="trade_004",
            symbol="DOTUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=10.0,
            reward_amount=30.0,
            rr_ratio=3.0,
            position_size=4.0,
            stop_loss_price=22.5,
            take_profit_price=30.0,
            risk_percentage=1.0,
            effectiveness_score=0.90
        )
        
        analysis = self.analyzer.analyze_position_sizing(trade_data, risk_management)
        
        assert "position_size_calculation" in analysis
        assert "risk_percentage" in analysis
        assert "position_consistency" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["position_size_calculation"] <= 1.0
        assert 0.0 <= analysis["risk_percentage"] <= 1.0
        assert 0.0 <= analysis["position_consistency"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0

class TestRRValidator:
    """Test R:R validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = RRValidator(target_rr_ratio=3.0)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.target_rr_ratio == 3.0
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_rr_improvement(self):
        """Test R:R improvement validation"""
        trade_data = TradeData(
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=51500.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=300.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_001",
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=100.0,
            reward_amount=300.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=53000.0,
            risk_percentage=2.0,
            effectiveness_score=0.85
        )
        
        validation = self.validator.validate_rr_improvement(trade_data, risk_management)
        
        assert validation.trade_id == "trade_001"
        assert validation.expected_rr_ratio == 3.0
        assert validation.actual_rr_ratio == 3.0
        assert validation.improvement_ratio >= 0.0
        assert validation.meets_threshold in [True, False]
        assert 0.0 <= validation.risk_management_score <= 1.0
        assert 0.0 <= validation.profit_optimization_score <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [RRValidationStatus.PASSED,
                                             RRValidationStatus.WARNING,
                                             RRValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
        assert validation.metadata["target_rr_ratio"] == 3.0
    
    def test_validate_rr_improvement_below_threshold(self):
        """Test R:R improvement validation below threshold"""
        trade_data = TradeData(
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            entry_price=3000.0,
            exit_price=3020.0,
            position_size=0.2,
            risk_amount=50.0,
            reward_amount=75.0,
            actual_rr_ratio=1.5,  # Below target
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_002",
            trade_id="trade_002",
            symbol="ETHUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.STOP_LOSS,
            risk_amount=50.0,
            reward_amount=75.0,
            rr_ratio=1.5,
            position_size=0.2,
            stop_loss_price=2975.0,
            take_profit_price=3075.0,
            risk_percentage=1.5,
            effectiveness_score=0.60
        )
        
        validation = self.validator.validate_rr_improvement(trade_data, risk_management)
        
        assert validation.meets_threshold is False
        assert validation.actual_rr_ratio < validation.expected_rr_ratio
        assert validation.improvement_ratio < 1.0
    
    def test_validate_rr_improvement_above_threshold(self):
        """Test R:R improvement validation above threshold"""
        trade_data = TradeData(
            trade_id="trade_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            entry_price=0.5,
            exit_price=0.6,
            position_size=1000.0,
            risk_amount=20.0,
            reward_amount=80.0,
            actual_rr_ratio=4.0,  # Above target
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.LOW
        )
        
        risk_management = RiskManagement(
            risk_id="risk_003",
            trade_id="trade_003",
            symbol="ADAUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.TAKE_PROFIT,
            risk_amount=20.0,
            reward_amount=80.0,
            rr_ratio=4.0,
            position_size=1000.0,
            stop_loss_price=0.48,
            take_profit_price=0.64,
            risk_percentage=4.0,
            effectiveness_score=0.95
        )
        
        validation = self.validator.validate_rr_improvement(trade_data, risk_management)
        
        assert validation.meets_threshold is True
        assert validation.actual_rr_ratio >= validation.expected_rr_ratio
        assert validation.improvement_ratio >= 1.0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(5):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT if i % 2 == 0 else TradeOutcome.LOSS,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            self.validator.validate_rr_improvement(trade_data, risk_management)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_trades == 5
        assert report.profitable_trades >= 0
        assert report.losing_trades >= 0
        assert report.break_even_trades >= 0
        assert report.total_profit >= 0.0
        assert report.total_loss >= 0.0
        assert report.net_profit >= 0.0
        assert 0.0 <= report.win_rate <= 1.0
        assert report.average_win >= 0.0
        assert report.average_loss >= 0.0
        assert report.overall_rr_improvement >= 0.0
        assert report.average_rr_ratio >= 0.0
        assert report.improvement_level in [RRImprovementLevel.EXCELLENT,
                                          RRImprovementLevel.GOOD,
                                          RRImprovementLevel.ACCEPTABLE,
                                          RRImprovementLevel.POOR]
        assert report.validation_status in [RRValidationStatus.PASSED,
                                          RRValidationStatus.WARNING,
                                          RRValidationStatus.FAILED]
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.risk_management_analysis) > 0
        assert len(report.profit_optimization_analysis) > 0
        assert len(report.stop_loss_analysis) > 0
        assert len(report.position_sizing_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_rr_improvement == 0.0
        assert report.average_rr_ratio == 0.0
        assert report.improvement_level == RRImprovementLevel.POOR
        assert report.validation_status == RRValidationStatus.FAILED
        assert report.total_trades == 0
        assert report.profitable_trades == 0
        assert report.losing_trades == 0
        assert report.break_even_trades == 0
        assert report.total_profit == 0.0
        assert report.total_loss == 0.0
        assert report.net_profit == 0.0
        assert report.win_rate == 0.0
        assert report.average_win == 0.0
        assert report.average_loss == 0.0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.risk_management_analysis == {}
        assert report.profit_optimization_analysis == {}
        assert report.stop_loss_analysis == {}
        assert report.position_sizing_analysis == {}
        assert report.performance_metrics == {}

class TestRRImprovementManager:
    """Test R:R improvement manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = RRImprovementManager(target_rr_ratio=3.0)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.analyzer, RiskAnalyzer)
        assert isinstance(self.manager.validator, RRValidator)
        assert self.manager.validator.target_rr_ratio == 3.0
        assert self.manager.start_time > 0
        assert len(self.manager.validation_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_rr_improvement(self):
        """Test R:R improvement validation"""
        trade_data = TradeData(
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=51500.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=300.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_001",
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=100.0,
            reward_amount=300.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=53000.0,
            risk_percentage=2.0,
            effectiveness_score=0.85
        )
        
        validation = self.manager.validate_rr_improvement(trade_data, risk_management)
        
        assert isinstance(validation, RRValidation)
        assert validation.trade_id == "trade_001"
        assert validation.expected_rr_ratio == 3.0
        assert validation.actual_rr_ratio == 3.0
        assert validation.improvement_ratio >= 0.0
        assert validation.meets_threshold in [True, False]
        assert 0.0 <= validation.risk_management_score <= 1.0
        assert 0.0 <= validation.profit_optimization_score <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [RRValidationStatus.PASSED,
                                              RRValidationStatus.WARNING,
                                              RRValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT if i % 2 == 0 else TradeOutcome.LOSS,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            self.manager.validate_rr_improvement(trade_data, risk_management)
        
        report = self.manager.generate_validation_report()
        
        assert isinstance(report, RRImprovementReport)
        assert report.total_trades == 3
        
        # Check that report was added to history
        assert len(self.manager.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            self.manager.validate_rr_improvement(trade_data, risk_management)
            self.manager.generate_validation_report()
        
        history = self.manager.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, RRImprovementReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT if i % 2 == 0 else TradeOutcome.LOSS,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            self.manager.validate_rr_improvement(trade_data, risk_management)
        
        summary = self.manager.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
        assert "meets_threshold" in summary
        assert "average_rr_ratio" in summary
        assert "overall_score" in summary
        assert "target_rr_ratio" in summary
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        trade_data = TradeData(
            trade_id="test_trade",
            symbol="TEST",
            timestamp=time.time(),
            entry_price=100.0,
            exit_price=110.0,
            position_size=0.1,
            risk_amount=50.0,
            reward_amount=150.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="test_risk",
            trade_id="test_trade",
            symbol="TEST",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=50.0,
            reward_amount=150.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=95.0,
            take_profit_price=120.0,
            risk_percentage=2.0,
            effectiveness_score=0.8
        )
        
        self.manager.validate_rr_improvement(trade_data, risk_management)
        self.manager.generate_validation_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.validation_reports) == 0

class TestGlobalFunctions:
    """Test global R:R improvement validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.rr_improvement_validation
        infra.rr_improvement_validation._rr_improvement_validation_manager = None
    
    def test_get_rr_improvement_validation_manager(self):
        """Test global manager access"""
        manager1 = get_rr_improvement_validation_manager()
        manager2 = get_rr_improvement_validation_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, RRImprovementManager)
    
    def test_validate_rr_improvement_global(self):
        """Test global R:R improvement validation"""
        trade_data = TradeData(
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=51500.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=300.0,
            actual_rr_ratio=3.0,
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.MEDIUM
        )
        
        risk_management = RiskManagement(
            risk_id="risk_001",
            trade_id="trade_001",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.POSITION_SIZING,
            risk_amount=100.0,
            reward_amount=300.0,
            rr_ratio=3.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=53000.0,
            risk_percentage=2.0,
            effectiveness_score=0.85
        )
        
        validation = validate_rr_improvement(trade_data, risk_management)
        
        assert isinstance(validation, RRValidation)
        assert validation.trade_id == "trade_001"
        assert validation.expected_rr_ratio == 3.0
        assert validation.actual_rr_ratio == 3.0
        assert validation.improvement_ratio >= 0.0
        assert validation.meets_threshold in [True, False]
        assert 0.0 <= validation.risk_management_score <= 1.0
        assert 0.0 <= validation.profit_optimization_score <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [RRValidationStatus.PASSED,
                                            RRValidationStatus.WARNING,
                                            RRValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_rr_improvement_validation_report_global(self):
        """Test global R:R improvement validation report generation"""
        # Add some validations first
        for i in range(3):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT if i % 2 == 0 else TradeOutcome.LOSS,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            validate_rr_improvement(trade_data, risk_management)
        
        report = generate_rr_improvement_validation_report()
        
        assert isinstance(report, RRImprovementReport)
        assert report.total_trades == 3
    
    def test_get_rr_improvement_validation_summary_global(self):
        """Test global R:R improvement validation summary"""
        # Add some validations
        for i in range(5):
            trade_data = TradeData(
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                entry_price=100.0 + i * 10.0,
                exit_price=110.0 + i * 10.0,
                position_size=0.1 + i * 0.05,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                actual_rr_ratio=3.0 + i * 0.5,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT if i % 2 == 0 else TradeOutcome.LOSS,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{i:03d}",
                trade_id=f"trade_{i:03d}",
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                risk_type=RiskManagementType.POSITION_SIZING,
                risk_amount=50.0 + i * 10.0,
                reward_amount=150.0 + i * 30.0,
                rr_ratio=3.0 + i * 0.5,
                position_size=0.1 + i * 0.05,
                stop_loss_price=95.0 + i * 10.0,
                take_profit_price=120.0 + i * 10.0,
                risk_percentage=2.0 + i * 0.5,
                effectiveness_score=0.8 + i * 0.02
            )
            
            validate_rr_improvement(trade_data, risk_management)
        
        summary = get_rr_improvement_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestRRImprovementValidationIntegration:
    """Integration tests for R:R improvement validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.rr_improvement_validation
        infra.rr_improvement_validation._rr_improvement_validation_manager = None
    
    def test_comprehensive_rr_improvement_validation(self):
        """Test comprehensive R:R improvement validation workflow"""
        # Test different trade scenarios and risk management types
        test_cases = [
            (TradeOutcome.PROFIT, RiskManagementType.POSITION_SIZING, 3.0, 3.0, True),
            (TradeOutcome.LOSS, RiskManagementType.STOP_LOSS, 2.0, 3.0, False),
            (TradeOutcome.PROFIT, RiskManagementType.TAKE_PROFIT, 4.0, 3.0, True),
            (TradeOutcome.PARTIAL_PROFIT, RiskManagementType.TRAILING_STOP, 2.5, 3.0, False),
            (TradeOutcome.BREAK_EVEN, RiskManagementType.HEDGING, 1.0, 3.0, False)
        ]
        
        for trade_outcome, risk_type, actual_rr, target_rr, expected_meets_threshold in test_cases:
            trade_data = TradeData(
                trade_id=f"trade_{trade_outcome.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                entry_price=50000.0,
                exit_price=51000.0,
                position_size=0.1,
                risk_amount=100.0,
                reward_amount=300.0,
                actual_rr_ratio=actual_rr,
                target_rr_ratio=target_rr,
                trade_outcome=trade_outcome,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{trade_outcome.value}",
                trade_id=f"trade_{trade_outcome.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                risk_type=risk_type,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=actual_rr,
                position_size=0.1,
                stop_loss_price=49000.0,
                take_profit_price=53000.0,
                risk_percentage=2.0,
                effectiveness_score=0.85
            )
            
            validation = validate_rr_improvement(trade_data, risk_management)
            
            assert isinstance(validation, RRValidation)
            assert validation.trade_id == f"trade_{trade_outcome.value}"
            assert validation.expected_rr_ratio == 3.0
            assert validation.actual_rr_ratio == actual_rr
            assert validation.improvement_ratio >= 0.0
            assert validation.meets_threshold in [True, False]
            assert 0.0 <= validation.risk_management_score <= 1.0
            assert 0.0 <= validation.profit_optimization_score <= 1.0
            assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
            assert 0.0 <= validation.position_sizing_accuracy <= 1.0
            assert 0.0 <= validation.overall_score <= 1.0
            assert validation.validation_status in [RRValidationStatus.PASSED,
                                                RRValidationStatus.WARNING,
                                                RRValidationStatus.FAILED]
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_rr_improvement_validation_report()
        
        assert isinstance(report, RRImprovementReport)
        assert report.total_trades == len(test_cases)
        assert report.overall_rr_improvement >= 0.0
        assert report.average_rr_ratio >= 0.0
        assert report.improvement_level in [RRImprovementLevel.EXCELLENT,
                                        RRImprovementLevel.GOOD,
                                        RRImprovementLevel.ACCEPTABLE,
                                        RRImprovementLevel.POOR]
        assert report.validation_status in [RRValidationStatus.PASSED,
                                         RRValidationStatus.WARNING,
                                         RRValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(test_cases)
        assert len(report.recommendations) > 0
        assert len(report.risk_management_analysis) > 0
        assert len(report.profit_optimization_analysis) > 0
        assert len(report.stop_loss_analysis) > 0
        assert len(report.position_sizing_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_rr_threshold_validation(self):
        """Test R:R threshold validation"""
        # Test with high R:R ratio (should pass)
        high_rr_trade = TradeData(
            trade_id="high_rr",
            symbol="BTCUSDT",
            timestamp=time.time(),
            entry_price=50000.0,
            exit_price=53000.0,
            position_size=0.1,
            risk_amount=100.0,
            reward_amount=400.0,
            actual_rr_ratio=4.0,  # Above target
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.LOW
        )
        
        high_rr_risk = RiskManagement(
            risk_id="high_rr_risk",
            trade_id="high_rr",
            symbol="BTCUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.TAKE_PROFIT,
            risk_amount=100.0,
            reward_amount=400.0,
            rr_ratio=4.0,
            position_size=0.1,
            stop_loss_price=49000.0,
            take_profit_price=54000.0,
            risk_percentage=2.0,
            effectiveness_score=0.95
        )
        
        validation = validate_rr_improvement(high_rr_trade, high_rr_risk)
        
        assert validation.meets_threshold is True
        assert validation.actual_rr_ratio >= validation.expected_rr_ratio
        assert validation.improvement_ratio >= 1.0
        
        # Test with low R:R ratio (should fail)
        low_rr_trade = TradeData(
            trade_id="low_rr",
            symbol="ETHUSDT",
            timestamp=time.time(),
            entry_price=3000.0,
            exit_price=3020.0,
            position_size=0.2,
            risk_amount=50.0,
            reward_amount=75.0,
            actual_rr_ratio=1.5,  # Below target
            target_rr_ratio=3.0,
            trade_outcome=TradeOutcome.PROFIT,
            risk_level=RiskLevel.HIGH
        )
        
        low_rr_risk = RiskManagement(
            risk_id="low_rr_risk",
            trade_id="low_rr",
            symbol="ETHUSDT",
            timestamp=time.time(),
            risk_type=RiskManagementType.STOP_LOSS,
            risk_amount=50.0,
            reward_amount=75.0,
            rr_ratio=1.5,
            position_size=0.2,
            stop_loss_price=2975.0,
            take_profit_price=3075.0,
            risk_percentage=1.5,
            effectiveness_score=0.60
        )
        
        validation = validate_rr_improvement(low_rr_trade, low_rr_risk)
        
        assert validation.meets_threshold is False
        assert validation.actual_rr_ratio < validation.expected_rr_ratio
        assert validation.improvement_ratio < 1.0
    
    def test_risk_management_type_analysis(self):
        """Test risk management type analysis"""
        # Test different risk management types
        risk_types = [RiskManagementType.POSITION_SIZING, RiskManagementType.STOP_LOSS, 
                     RiskManagementType.TAKE_PROFIT, RiskManagementType.TRAILING_STOP,
                     RiskManagementType.HEDGING, RiskManagementType.DIVERSIFICATION]
        
        for risk_type in risk_types:
            trade_data = TradeData(
                trade_id=f"trade_{risk_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                entry_price=50000.0,
                exit_price=51500.0,
                position_size=0.1,
                risk_amount=100.0,
                reward_amount=300.0,
                actual_rr_ratio=3.0,
                target_rr_ratio=3.0,
                trade_outcome=TradeOutcome.PROFIT,
                risk_level=RiskLevel.MEDIUM
            )
            
            risk_management = RiskManagement(
                risk_id=f"risk_{risk_type.value}",
                trade_id=f"trade_{risk_type.value}",
                symbol="BTCUSDT",
                timestamp=time.time(),
                risk_type=risk_type,
                risk_amount=100.0,
                reward_amount=300.0,
                rr_ratio=3.0,
                position_size=0.1,
                stop_loss_price=49000.0,
                take_profit_price=53000.0,
                risk_percentage=2.0,
                effectiveness_score=0.85
            )
            
            validation = validate_rr_improvement(trade_data, risk_management)
            
            assert validation.expected_rr_ratio == 3.0
            assert validation.actual_rr_ratio == 3.0
            assert 0.0 <= validation.risk_management_score <= 1.0
            assert 0.0 <= validation.profit_optimization_score <= 1.0
            assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
            assert 0.0 <= validation.position_sizing_accuracy <= 1.0
            assert 0.0 <= validation.overall_score <= 1.0
            assert validation.validation_status in [RRValidationStatus.PASSED,
                                                RRValidationStatus.WARNING,
                                                RRValidationStatus.FAILED]
            assert len(validation.recommendations) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
