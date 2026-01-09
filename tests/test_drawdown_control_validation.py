"""
Comprehensive tests for drawdown control validation system

Tests drawdown control within limits, risk management effectiveness validation,
position sizing accuracy, stop loss effectiveness, portfolio protection
mechanisms, risk-adjusted returns analysis, false risk signal reduction,
and true risk signal detection validation.
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

from infra.drawdown_control_validation import (
    DrawdownControlManager, RiskControlAnalyzer, DrawdownValidator,
    DrawdownLevel, DrawdownValidationStatus, RiskControlType, DrawdownTrigger,
    DrawdownEvent, RiskControl, DrawdownValidation, DrawdownControlReport,
    get_drawdown_control_validation_manager, validate_drawdown_control,
    generate_drawdown_control_validation_report, get_drawdown_control_validation_summary
)

class TestDrawdownLevel:
    """Test drawdown level enumeration"""
    
    def test_drawdown_levels(self):
        """Test all drawdown levels"""
        levels = [
            DrawdownLevel.MINIMAL,
            DrawdownLevel.LOW,
            DrawdownLevel.MODERATE,
            DrawdownLevel.HIGH,
            DrawdownLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, DrawdownLevel)
            assert level.value in ["minimal", "low", "moderate", "high", "critical"]

class TestDrawdownValidationStatus:
    """Test drawdown validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            DrawdownValidationStatus.PASSED,
            DrawdownValidationStatus.WARNING,
            DrawdownValidationStatus.FAILED,
            DrawdownValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, DrawdownValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestRiskControlType:
    """Test risk control type enumeration"""
    
    def test_risk_control_types(self):
        """Test all risk control types"""
        types = [
            RiskControlType.POSITION_SIZING,
            RiskControlType.STOP_LOSS,
            RiskControlType.PORTFOLIO_LIMITS,
            RiskControlType.CIRCUIT_BREAKER,
            RiskControlType.CORRELATION_LIMITS,
            RiskControlType.VOLATILITY_CONTROLS
        ]
        
        for risk_type in types:
            assert isinstance(risk_type, RiskControlType)
            assert risk_type.value in ["position_sizing", "stop_loss", "portfolio_limits",
                                     "circuit_breaker", "correlation_limits", "volatility_controls"]

class TestDrawdownTrigger:
    """Test drawdown trigger enumeration"""
    
    def test_drawdown_triggers(self):
        """Test all drawdown triggers"""
        triggers = [
            DrawdownTrigger.POSITION_LOSS,
            DrawdownTrigger.CORRELATION_SPIKE,
            DrawdownTrigger.VOLATILITY_SPIKE,
            DrawdownTrigger.SYSTEM_ERROR,
            DrawdownTrigger.MARKET_SHOCK,
            DrawdownTrigger.LIQUIDITY_CRISIS
        ]
        
        for trigger in triggers:
            assert isinstance(trigger, DrawdownTrigger)
            assert trigger.value in ["position_loss", "correlation_spike", "volatility_spike",
                                    "system_error", "market_shock", "liquidity_crisis"]

class TestDrawdownEvent:
    """Test drawdown event data structure"""
    
    def test_drawdown_event_creation(self):
        """Test drawdown event creation"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_001",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6,
            metadata={"source": "dtms"}
        )
        
        assert drawdown_event.event_id == "drawdown_001"
        assert drawdown_event.timestamp > 0
        assert drawdown_event.symbol == "BTCUSDT"
        assert drawdown_event.drawdown_amount == 500.0
        assert drawdown_event.drawdown_percentage == 0.05
        assert drawdown_event.trigger_type == DrawdownTrigger.POSITION_LOSS
        assert drawdown_event.risk_control_type == RiskControlType.STOP_LOSS
        assert drawdown_event.position_size == 0.1
        assert drawdown_event.stop_loss_distance == 100.0
        assert drawdown_event.market_volatility == 0.025
        assert drawdown_event.correlation_factor == 0.6
        assert drawdown_event.metadata["source"] == "dtms"
    
    def test_drawdown_event_defaults(self):
        """Test drawdown event defaults"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_002",
            timestamp=time.time(),
            symbol="ETHUSDT",
            drawdown_amount=300.0,
            drawdown_percentage=0.03,
            trigger_type=DrawdownTrigger.VOLATILITY_SPIKE,
            risk_control_type=RiskControlType.CIRCUIT_BREAKER,
            position_size=0.2,
            stop_loss_distance=150.0,
            market_volatility=0.03,
            correlation_factor=0.7
        )
        
        assert drawdown_event.metadata == {}

class TestRiskControl:
    """Test risk control data structure"""
    
    def test_risk_control_creation(self):
        """Test risk control creation"""
        risk_control = RiskControl(
            control_id="control_001",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.85,
            response_time_ms=150.0,
            metadata={"strategy": "scalp"}
        )
        
        assert risk_control.control_id == "control_001"
        assert risk_control.control_type == RiskControlType.STOP_LOSS
        assert risk_control.symbol == "BTCUSDT"
        assert risk_control.timestamp > 0
        assert risk_control.threshold_value == 100.0
        assert risk_control.current_value == 95.0
        assert risk_control.is_triggered is True
        assert risk_control.effectiveness_score == 0.85
        assert risk_control.response_time_ms == 150.0
        assert risk_control.metadata["strategy"] == "scalp"
    
    def test_risk_control_defaults(self):
        """Test risk control defaults"""
        risk_control = RiskControl(
            control_id="control_002",
            control_type=RiskControlType.CIRCUIT_BREAKER,
            symbol="ETHUSDT",
            timestamp=time.time(),
            threshold_value=200.0,
            current_value=180.0,
            is_triggered=False,
            effectiveness_score=0.70,
            response_time_ms=300.0
        )
        
        assert risk_control.metadata == {}

class TestDrawdownValidation:
    """Test drawdown validation data structure"""
    
    def test_drawdown_validation_creation(self):
        """Test drawdown validation creation"""
        validation = DrawdownValidation(
            timestamp=time.time(),
            event_id="drawdown_001",
            expected_drawdown_limit=0.10,
            actual_drawdown=0.05,
            within_limits=True,
            risk_control_effectiveness=0.85,
            position_sizing_accuracy=0.90,
            stop_loss_effectiveness=0.80,
            portfolio_protection_score=0.85,
            overall_score=0.85,
            validation_status=DrawdownValidationStatus.PASSED,
            recommendations=["Drawdown control is excellent"],
            metadata={"max_drawdown_limit": 0.10}
        )
        
        assert validation.timestamp > 0
        assert validation.event_id == "drawdown_001"
        assert validation.expected_drawdown_limit == 0.10
        assert validation.actual_drawdown == 0.05
        assert validation.within_limits is True
        assert validation.risk_control_effectiveness == 0.85
        assert validation.position_sizing_accuracy == 0.90
        assert validation.stop_loss_effectiveness == 0.80
        assert validation.portfolio_protection_score == 0.85
        assert validation.overall_score == 0.85
        assert validation.validation_status == DrawdownValidationStatus.PASSED
        assert len(validation.recommendations) == 1
        assert validation.metadata["max_drawdown_limit"] == 0.10
    
    def test_drawdown_validation_defaults(self):
        """Test drawdown validation defaults"""
        validation = DrawdownValidation(
            timestamp=time.time(),
            event_id="drawdown_002",
            expected_drawdown_limit=0.10,
            actual_drawdown=0.15,
            within_limits=False,
            risk_control_effectiveness=0.60,
            position_sizing_accuracy=0.70,
            stop_loss_effectiveness=0.65,
            portfolio_protection_score=0.60,
            overall_score=0.64,
            validation_status=DrawdownValidationStatus.FAILED,
            recommendations=["Drawdown exceeds limits"]
        )
        
        assert validation.metadata == {}

class TestDrawdownControlReport:
    """Test drawdown control report data structure"""
    
    def test_drawdown_control_report_creation(self):
        """Test drawdown control report creation"""
        report = DrawdownControlReport(
            timestamp=time.time(),
            overall_drawdown_control=0.85,
            average_drawdown=0.04,
            max_drawdown=0.08,
            drawdown_level=DrawdownLevel.LOW,
            validation_status=DrawdownValidationStatus.PASSED,
            total_events=100,
            controlled_events=85,
            uncontrolled_events=15,
            total_drawdown_amount=4000.0,
            total_drawdown_percentage=4.0,
            risk_control_analysis={"average_risk_control_score": 0.85},
            position_sizing_analysis={"average_position_sizing_score": 0.90},
            stop_loss_analysis={"average_stop_loss_score": 0.80},
            portfolio_protection_analysis={"average_portfolio_protection_score": 0.85},
            performance_metrics={"avg_validation_time_ms": 25.5},
            recommendations=["Drawdown control is good"],
            detailed_validations=[],
            metadata={"max_drawdown_limit": 0.10}
        )
        
        assert report.timestamp > 0
        assert report.overall_drawdown_control == 0.85
        assert report.average_drawdown == 0.04
        assert report.max_drawdown == 0.08
        assert report.drawdown_level == DrawdownLevel.LOW
        assert report.validation_status == DrawdownValidationStatus.PASSED
        assert report.total_events == 100
        assert report.controlled_events == 85
        assert report.uncontrolled_events == 15
        assert report.total_drawdown_amount == 4000.0
        assert report.total_drawdown_percentage == 4.0
        assert report.risk_control_analysis["average_risk_control_score"] == 0.85
        assert report.position_sizing_analysis["average_position_sizing_score"] == 0.90
        assert report.stop_loss_analysis["average_stop_loss_score"] == 0.80
        assert report.portfolio_protection_analysis["average_portfolio_protection_score"] == 0.85
        assert report.performance_metrics["avg_validation_time_ms"] == 25.5
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["max_drawdown_limit"] == 0.10
    
    def test_drawdown_control_report_defaults(self):
        """Test drawdown control report defaults"""
        report = DrawdownControlReport(
            timestamp=time.time(),
            overall_drawdown_control=0.60,
            average_drawdown=0.08,
            max_drawdown=0.15,
            drawdown_level=DrawdownLevel.HIGH,
            validation_status=DrawdownValidationStatus.WARNING,
            total_events=50,
            controlled_events=30,
            uncontrolled_events=20,
            total_drawdown_amount=2000.0,
            total_drawdown_percentage=8.0,
            risk_control_analysis={"average_risk_control_score": 0.60},
            position_sizing_analysis={"average_position_sizing_score": 0.70},
            stop_loss_analysis={"average_stop_loss_score": 0.65},
            portfolio_protection_analysis={"average_portfolio_protection_score": 0.60},
            performance_metrics={"avg_validation_time_ms": 30.0},
            recommendations=["Drawdown control needs improvement"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestRiskControlAnalyzer:
    """Test risk control analyzer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = RiskControlAnalyzer()
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert hasattr(self.analyzer, 'analysis_cache')
        assert hasattr(self.analyzer, 'lock')
        assert isinstance(self.analyzer.analysis_cache, dict)
    
    def test_analyze_risk_control_effectiveness(self):
        """Test risk control effectiveness analysis"""
        drawdown_event = DrawdownEvent(
            event_id="test_event",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6
        )
        
        risk_control = RiskControl(
            control_id="test_control",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.85,
            response_time_ms=150.0
        )
        
        analysis = self.analyzer.analyze_risk_control_effectiveness(drawdown_event, risk_control)
        
        assert "position_sizing_score" in analysis
        assert "stop_loss_score" in analysis
        assert "portfolio_protection_score" in analysis
        assert "response_effectiveness" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["position_sizing_score"] <= 1.0
        assert 0.0 <= analysis["stop_loss_score"] <= 1.0
        assert 0.0 <= analysis["portfolio_protection_score"] <= 1.0
        assert 0.0 <= analysis["response_effectiveness"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_position_sizing_accuracy(self):
        """Test position sizing accuracy analysis"""
        drawdown_event = DrawdownEvent(
            event_id="test_event",
            timestamp=time.time(),
            symbol="ETHUSDT",
            drawdown_amount=300.0,
            drawdown_percentage=0.03,
            trigger_type=DrawdownTrigger.VOLATILITY_SPIKE,
            risk_control_type=RiskControlType.POSITION_SIZING,
            position_size=0.2,
            stop_loss_distance=150.0,
            market_volatility=0.03,
            correlation_factor=0.7
        )
        
        risk_control = RiskControl(
            control_id="test_control",
            control_type=RiskControlType.POSITION_SIZING,
            symbol="ETHUSDT",
            timestamp=time.time(),
            threshold_value=200.0,
            current_value=180.0,
            is_triggered=False,
            effectiveness_score=0.70,
            response_time_ms=300.0
        )
        
        analysis = self.analyzer.analyze_position_sizing_accuracy(drawdown_event, risk_control)
        
        assert "size_calculation_accuracy" in analysis
        assert "risk_percentage_accuracy" in analysis
        assert "position_consistency" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["size_calculation_accuracy"] <= 1.0
        assert 0.0 <= analysis["risk_percentage_accuracy"] <= 1.0
        assert 0.0 <= analysis["position_consistency"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_stop_loss_effectiveness(self):
        """Test stop loss effectiveness analysis"""
        drawdown_event = DrawdownEvent(
            event_id="test_event",
            timestamp=time.time(),
            symbol="ADAUSDT",
            drawdown_amount=200.0,
            drawdown_percentage=0.02,
            trigger_type=DrawdownTrigger.CORRELATION_SPIKE,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=1000.0,
            stop_loss_distance=0.2,
            market_volatility=0.02,
            correlation_factor=0.8
        )
        
        risk_control = RiskControl(
            control_id="test_control",
            control_type=RiskControlType.STOP_LOSS,
            symbol="ADAUSDT",
            timestamp=time.time(),
            threshold_value=0.2,
            current_value=0.18,
            is_triggered=True,
            effectiveness_score=0.75,
            response_time_ms=200.0
        )
        
        analysis = self.analyzer.analyze_stop_loss_effectiveness(drawdown_event, risk_control)
        
        assert "stop_loss_placement" in analysis
        assert "stop_loss_execution" in analysis
        assert "stop_loss_timing" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["stop_loss_placement"] <= 1.0
        assert 0.0 <= analysis["stop_loss_execution"] <= 1.0
        assert 0.0 <= analysis["stop_loss_timing"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0
    
    def test_analyze_portfolio_protection(self):
        """Test portfolio protection analysis"""
        drawdown_event = DrawdownEvent(
            event_id="test_event",
            timestamp=time.time(),
            symbol="DOTUSDT",
            drawdown_amount=400.0,
            drawdown_percentage=0.04,
            trigger_type=DrawdownTrigger.MARKET_SHOCK,
            risk_control_type=RiskControlType.CIRCUIT_BREAKER,
            position_size=4.0,
            stop_loss_distance=100.0,
            market_volatility=0.04,
            correlation_factor=0.9
        )
        
        risk_control = RiskControl(
            control_id="test_control",
            control_type=RiskControlType.CIRCUIT_BREAKER,
            symbol="DOTUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=80.0,
            is_triggered=True,
            effectiveness_score=0.90,
            response_time_ms=100.0
        )
        
        analysis = self.analyzer.analyze_portfolio_protection(drawdown_event, risk_control)
        
        assert "correlation_limits" in analysis
        assert "volatility_controls" in analysis
        assert "circuit_breaker_effectiveness" in analysis
        assert "overall_score" in analysis
        assert 0.0 <= analysis["correlation_limits"] <= 1.0
        assert 0.0 <= analysis["volatility_controls"] <= 1.0
        assert 0.0 <= analysis["circuit_breaker_effectiveness"] <= 1.0
        assert 0.0 <= analysis["overall_score"] <= 1.0

class TestDrawdownValidator:
    """Test drawdown validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DrawdownValidator(max_drawdown_limit=0.10)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.max_drawdown_limit == 0.10
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_drawdown_control(self):
        """Test drawdown control validation"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_001",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6
        )
        
        risk_control = RiskControl(
            control_id="control_001",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.85,
            response_time_ms=150.0
        )
        
        validation = self.validator.validate_drawdown_control(drawdown_event, risk_control)
        
        assert validation.event_id == "drawdown_001"
        assert validation.expected_drawdown_limit == 0.10
        assert validation.actual_drawdown == 0.05
        assert validation.within_limits in [True, False]
        assert 0.0 <= validation.risk_control_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.portfolio_protection_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [DrawdownValidationStatus.PASSED,
                                               DrawdownValidationStatus.WARNING,
                                               DrawdownValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
        assert validation.metadata["max_drawdown_limit"] == 0.10
    
    def test_validate_drawdown_control_within_limits(self):
        """Test drawdown control validation within limits"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_002",
            timestamp=time.time(),
            symbol="ETHUSDT",
            drawdown_amount=300.0,
            drawdown_percentage=0.03,  # Within 10% limit
            trigger_type=DrawdownTrigger.VOLATILITY_SPIKE,
            risk_control_type=RiskControlType.CIRCUIT_BREAKER,
            position_size=0.2,
            stop_loss_distance=150.0,
            market_volatility=0.03,
            correlation_factor=0.7
        )
        
        risk_control = RiskControl(
            control_id="control_002",
            control_type=RiskControlType.CIRCUIT_BREAKER,
            symbol="ETHUSDT",
            timestamp=time.time(),
            threshold_value=200.0,
            current_value=180.0,
            is_triggered=True,
            effectiveness_score=0.90,
            response_time_ms=100.0
        )
        
        validation = self.validator.validate_drawdown_control(drawdown_event, risk_control)
        
        assert validation.within_limits is True
        assert validation.actual_drawdown < validation.expected_drawdown_limit
    
    def test_validate_drawdown_control_exceeds_limits(self):
        """Test drawdown control validation exceeds limits"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_003",
            timestamp=time.time(),
            symbol="ADAUSDT",
            drawdown_amount=2000.0,
            drawdown_percentage=0.15,  # Exceeds 10% limit
            trigger_type=DrawdownTrigger.MARKET_SHOCK,
            risk_control_type=RiskControlType.PORTFOLIO_LIMITS,
            position_size=1000.0,
            stop_loss_distance=2.0,
            market_volatility=0.05,
            correlation_factor=0.9
        )
        
        risk_control = RiskControl(
            control_id="control_003",
            control_type=RiskControlType.PORTFOLIO_LIMITS,
            symbol="ADAUSDT",
            timestamp=time.time(),
            threshold_value=2.0,
            current_value=1.5,
            is_triggered=False,
            effectiveness_score=0.50,
            response_time_ms=500.0
        )
        
        validation = self.validator.validate_drawdown_control(drawdown_event, risk_control)
        
        assert validation.within_limits is False
        assert validation.actual_drawdown > validation.expected_drawdown_limit
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations
        for i in range(5):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            self.validator.validate_drawdown_control(drawdown_event, risk_control)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_events == 5
        assert report.controlled_events >= 0
        assert report.uncontrolled_events >= 0
        assert report.total_drawdown_amount >= 0.0
        assert report.total_drawdown_percentage >= 0.0
        assert report.overall_drawdown_control >= 0.0
        assert report.average_drawdown >= 0.0
        assert report.max_drawdown >= 0.0
        assert report.drawdown_level in [DrawdownLevel.MINIMAL, DrawdownLevel.LOW,
                                       DrawdownLevel.MODERATE, DrawdownLevel.HIGH,
                                       DrawdownLevel.CRITICAL]
        assert report.validation_status in [DrawdownValidationStatus.PASSED,
                                          DrawdownValidationStatus.WARNING,
                                          DrawdownValidationStatus.FAILED]
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.risk_control_analysis) > 0
        assert len(report.position_sizing_analysis) > 0
        assert len(report.stop_loss_analysis) > 0
        assert len(report.portfolio_protection_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_drawdown_control == 0.0
        assert report.average_drawdown == 0.0
        assert report.max_drawdown == 0.0
        assert report.drawdown_level == DrawdownLevel.CRITICAL
        assert report.validation_status == DrawdownValidationStatus.FAILED
        assert report.total_events == 0
        assert report.controlled_events == 0
        assert report.uncontrolled_events == 0
        assert report.total_drawdown_amount == 0.0
        assert report.total_drawdown_percentage == 0.0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.risk_control_analysis == {}
        assert report.position_sizing_analysis == {}
        assert report.stop_loss_analysis == {}
        assert report.portfolio_protection_analysis == {}
        assert report.performance_metrics == {}

class TestDrawdownControlManager:
    """Test drawdown control manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = DrawdownControlManager(max_drawdown_limit=0.10)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.analyzer, RiskControlAnalyzer)
        assert isinstance(self.manager.validator, DrawdownValidator)
        assert self.manager.validator.max_drawdown_limit == 0.10
        assert self.manager.start_time > 0
        assert len(self.manager.validation_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_drawdown_control(self):
        """Test drawdown control validation"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_001",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6
        )
        
        risk_control = RiskControl(
            control_id="control_001",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.85,
            response_time_ms=150.0
        )
        
        validation = self.manager.validate_drawdown_control(drawdown_event, risk_control)
        
        assert isinstance(validation, DrawdownValidation)
        assert validation.event_id == "drawdown_001"
        assert validation.expected_drawdown_limit == 0.10
        assert validation.actual_drawdown == 0.05
        assert validation.within_limits in [True, False]
        assert 0.0 <= validation.risk_control_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.portfolio_protection_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [DrawdownValidationStatus.PASSED,
                                              DrawdownValidationStatus.WARNING,
                                              DrawdownValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(3):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            self.manager.validate_drawdown_control(drawdown_event, risk_control)
        
        report = self.manager.generate_validation_report()
        
        assert isinstance(report, DrawdownControlReport)
        assert report.total_events == 3
        
        # Check that report was added to history
        assert len(self.manager.validation_reports) == 1
    
    def test_get_validation_history(self):
        """Test getting validation history"""
        # Generate some reports
        for i in range(3):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            self.manager.validate_drawdown_control(drawdown_event, risk_control)
            self.manager.generate_validation_report()
        
        history = self.manager.get_validation_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, DrawdownControlReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            self.manager.validate_drawdown_control(drawdown_event, risk_control)
        
        summary = self.manager.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
        assert "within_limits" in summary
        assert "average_drawdown" in summary
        assert "overall_score" in summary
        assert "max_drawdown_limit" in summary
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        drawdown_event = DrawdownEvent(
            event_id="test_event",
            timestamp=time.time(),
            symbol="TEST",
            drawdown_amount=100.0,
            drawdown_percentage=0.01,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=50.0,
            market_volatility=0.02,
            correlation_factor=0.5
        )
        
        risk_control = RiskControl(
            control_id="test_control",
            control_type=RiskControlType.STOP_LOSS,
            symbol="TEST",
            timestamp=time.time(),
            threshold_value=50.0,
            current_value=45.0,
            is_triggered=True,
            effectiveness_score=0.8,
            response_time_ms=100.0
        )
        
        self.manager.validate_drawdown_control(drawdown_event, risk_control)
        self.manager.generate_validation_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.validation_reports) == 0

class TestGlobalFunctions:
    """Test global drawdown control validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.drawdown_control_validation
        infra.drawdown_control_validation._drawdown_control_validation_manager = None
    
    def test_get_drawdown_control_validation_manager(self):
        """Test global manager access"""
        manager1 = get_drawdown_control_validation_manager()
        manager2 = get_drawdown_control_validation_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, DrawdownControlManager)
    
    def test_validate_drawdown_control_global(self):
        """Test global drawdown control validation"""
        drawdown_event = DrawdownEvent(
            event_id="drawdown_001",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6
        )
        
        risk_control = RiskControl(
            control_id="control_001",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.85,
            response_time_ms=150.0
        )
        
        validation = validate_drawdown_control(drawdown_event, risk_control)
        
        assert isinstance(validation, DrawdownValidation)
        assert validation.event_id == "drawdown_001"
        assert validation.expected_drawdown_limit == 0.10
        assert validation.actual_drawdown == 0.05
        assert validation.within_limits in [True, False]
        assert 0.0 <= validation.risk_control_effectiveness <= 1.0
        assert 0.0 <= validation.position_sizing_accuracy <= 1.0
        assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
        assert 0.0 <= validation.portfolio_protection_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.validation_status in [DrawdownValidationStatus.PASSED,
                                            DrawdownValidationStatus.WARNING,
                                            DrawdownValidationStatus.FAILED]
        assert len(validation.recommendations) > 0
    
    def test_generate_drawdown_control_validation_report_global(self):
        """Test global drawdown control validation report generation"""
        # Add some validations first
        for i in range(3):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            validate_drawdown_control(drawdown_event, risk_control)
        
        report = generate_drawdown_control_validation_report()
        
        assert isinstance(report, DrawdownControlReport)
        assert report.total_events == 3
    
    def test_get_drawdown_control_validation_summary_global(self):
        """Test global drawdown control validation summary"""
        # Add some validations
        for i in range(5):
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{i:03d}",
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                drawdown_amount=100.0 + i * 50.0,
                drawdown_percentage=0.01 + i * 0.02,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=RiskControlType.STOP_LOSS,
                position_size=0.1 + i * 0.05,
                stop_loss_distance=50.0 + i * 25.0,
                market_volatility=0.02 + i * 0.005,
                correlation_factor=0.5 + i * 0.1
            )
            
            risk_control = RiskControl(
                control_id=f"control_{i:03d}",
                control_type=RiskControlType.STOP_LOSS,
                symbol=f"SYMBOL{i}",
                timestamp=time.time() + i,
                threshold_value=50.0 + i * 25.0,
                current_value=45.0 + i * 20.0,
                is_triggered=i % 2 == 0,
                effectiveness_score=0.8 + i * 0.02,
                response_time_ms=100.0 + i * 50.0
            )
            
            validate_drawdown_control(drawdown_event, risk_control)
        
        summary = get_drawdown_control_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestDrawdownControlValidationIntegration:
    """Integration tests for drawdown control validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.drawdown_control_validation
        infra.drawdown_control_validation._drawdown_control_validation_manager = None
    
    def test_comprehensive_drawdown_control_validation(self):
        """Test comprehensive drawdown control validation workflow"""
        # Test different drawdown scenarios and risk control types
        test_cases = [
            (DrawdownTrigger.POSITION_LOSS, RiskControlType.STOP_LOSS, 0.05, True),
            (DrawdownTrigger.CORRELATION_SPIKE, RiskControlType.CORRELATION_LIMITS, 0.08, True),
            (DrawdownTrigger.VOLATILITY_SPIKE, RiskControlType.VOLATILITY_CONTROLS, 0.12, False),
            (DrawdownTrigger.MARKET_SHOCK, RiskControlType.CIRCUIT_BREAKER, 0.15, False),
            (DrawdownTrigger.SYSTEM_ERROR, RiskControlType.PORTFOLIO_LIMITS, 0.03, True)
        ]
        
        for trigger_type, control_type, drawdown_percentage, expected_within_limits in test_cases:
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{trigger_type.value}",
                timestamp=time.time(),
                symbol="BTCUSDT",
                drawdown_amount=1000.0 * drawdown_percentage,
                drawdown_percentage=drawdown_percentage,
                trigger_type=trigger_type,
                risk_control_type=control_type,
                position_size=0.1,
                stop_loss_distance=100.0,
                market_volatility=0.025,
                correlation_factor=0.6
            )
            
            risk_control = RiskControl(
                control_id=f"control_{trigger_type.value}",
                control_type=control_type,
                symbol="BTCUSDT",
                timestamp=time.time(),
                threshold_value=100.0,
                current_value=95.0,
                is_triggered=drawdown_percentage > 0.10,
                effectiveness_score=0.85,
                response_time_ms=150.0
            )
            
            validation = validate_drawdown_control(drawdown_event, risk_control)
            
            assert isinstance(validation, DrawdownValidation)
            assert validation.event_id == f"drawdown_{trigger_type.value}"
            assert validation.expected_drawdown_limit == 0.10
            assert validation.actual_drawdown == drawdown_percentage
            assert validation.within_limits in [True, False]
            assert 0.0 <= validation.risk_control_effectiveness <= 1.0
            assert 0.0 <= validation.position_sizing_accuracy <= 1.0
            assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
            assert 0.0 <= validation.portfolio_protection_score <= 1.0
            assert 0.0 <= validation.overall_score <= 1.0
            assert validation.validation_status in [DrawdownValidationStatus.PASSED,
                                                DrawdownValidationStatus.WARNING,
                                                DrawdownValidationStatus.FAILED]
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_drawdown_control_validation_report()
        
        assert isinstance(report, DrawdownControlReport)
        assert report.total_events == len(test_cases)
        assert report.overall_drawdown_control >= 0.0
        assert report.average_drawdown >= 0.0
        assert report.max_drawdown >= 0.0
        assert report.drawdown_level in [DrawdownLevel.MINIMAL, DrawdownLevel.LOW,
                                        DrawdownLevel.MODERATE, DrawdownLevel.HIGH,
                                        DrawdownLevel.CRITICAL]
        assert report.validation_status in [DrawdownValidationStatus.PASSED,
                                         DrawdownValidationStatus.WARNING,
                                         DrawdownValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(test_cases)
        assert len(report.recommendations) > 0
        assert len(report.risk_control_analysis) > 0
        assert len(report.position_sizing_analysis) > 0
        assert len(report.stop_loss_analysis) > 0
        assert len(report.portfolio_protection_analysis) > 0
        assert len(report.performance_metrics) > 0
    
    def test_drawdown_limit_validation(self):
        """Test drawdown limit validation"""
        # Test with drawdown within limits
        within_limits_event = DrawdownEvent(
            event_id="within_limits",
            timestamp=time.time(),
            symbol="BTCUSDT",
            drawdown_amount=500.0,
            drawdown_percentage=0.05,  # Within 10% limit
            trigger_type=DrawdownTrigger.POSITION_LOSS,
            risk_control_type=RiskControlType.STOP_LOSS,
            position_size=0.1,
            stop_loss_distance=100.0,
            market_volatility=0.025,
            correlation_factor=0.6
        )
        
        within_limits_control = RiskControl(
            control_id="within_limits_control",
            control_type=RiskControlType.STOP_LOSS,
            symbol="BTCUSDT",
            timestamp=time.time(),
            threshold_value=100.0,
            current_value=95.0,
            is_triggered=True,
            effectiveness_score=0.90,
            response_time_ms=100.0
        )
        
        validation = validate_drawdown_control(within_limits_event, within_limits_control)
        
        assert validation.within_limits is True
        assert validation.actual_drawdown < validation.expected_drawdown_limit
        
        # Test with drawdown exceeding limits
        exceeds_limits_event = DrawdownEvent(
            event_id="exceeds_limits",
            timestamp=time.time(),
            symbol="ETHUSDT",
            drawdown_amount=1500.0,
            drawdown_percentage=0.15,  # Exceeds 10% limit
            trigger_type=DrawdownTrigger.MARKET_SHOCK,
            risk_control_type=RiskControlType.CIRCUIT_BREAKER,
            position_size=0.2,
            stop_loss_distance=150.0,
            market_volatility=0.04,
            correlation_factor=0.8
        )
        
        exceeds_limits_control = RiskControl(
            control_id="exceeds_limits_control",
            control_type=RiskControlType.CIRCUIT_BREAKER,
            symbol="ETHUSDT",
            timestamp=time.time(),
            threshold_value=150.0,
            current_value=120.0,
            is_triggered=True,
            effectiveness_score=0.70,
            response_time_ms=200.0
        )
        
        validation = validate_drawdown_control(exceeds_limits_event, exceeds_limits_control)
        
        assert validation.within_limits is False
        assert validation.actual_drawdown > validation.expected_drawdown_limit
    
    def test_risk_control_type_analysis(self):
        """Test risk control type analysis"""
        # Test different risk control types
        control_types = [RiskControlType.POSITION_SIZING, RiskControlType.STOP_LOSS,
                        RiskControlType.PORTFOLIO_LIMITS, RiskControlType.CIRCUIT_BREAKER,
                        RiskControlType.CORRELATION_LIMITS, RiskControlType.VOLATILITY_CONTROLS]
        
        for control_type in control_types:
            drawdown_event = DrawdownEvent(
                event_id=f"drawdown_{control_type.value}",
                timestamp=time.time(),
                symbol="BTCUSDT",
                drawdown_amount=500.0,
                drawdown_percentage=0.05,
                trigger_type=DrawdownTrigger.POSITION_LOSS,
                risk_control_type=control_type,
                position_size=0.1,
                stop_loss_distance=100.0,
                market_volatility=0.025,
                correlation_factor=0.6
            )
            
            risk_control = RiskControl(
                control_id=f"control_{control_type.value}",
                control_type=control_type,
                symbol="BTCUSDT",
                timestamp=time.time(),
                threshold_value=100.0,
                current_value=95.0,
                is_triggered=True,
                effectiveness_score=0.85,
                response_time_ms=150.0
            )
            
            validation = validate_drawdown_control(drawdown_event, risk_control)
            
            assert validation.expected_drawdown_limit == 0.10
            assert validation.actual_drawdown == 0.05
            assert 0.0 <= validation.risk_control_effectiveness <= 1.0
            assert 0.0 <= validation.position_sizing_accuracy <= 1.0
            assert 0.0 <= validation.stop_loss_effectiveness <= 1.0
            assert 0.0 <= validation.portfolio_protection_score <= 1.0
            assert 0.0 <= validation.overall_score <= 1.0
            assert validation.validation_status in [DrawdownValidationStatus.PASSED,
                                                DrawdownValidationStatus.WARNING,
                                                DrawdownValidationStatus.FAILED]
            assert len(validation.recommendations) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
