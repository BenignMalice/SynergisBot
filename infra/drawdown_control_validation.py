"""
Drawdown Control Validation System

This module implements a comprehensive validation system to ensure drawdown
control within acceptable limits, validating risk management effectiveness,
position sizing accuracy, stop loss effectiveness, and overall portfolio
protection mechanisms.

Key Features:
- Drawdown control validation within limits
- Risk management effectiveness validation and precision measurement
- Position sizing accuracy validation
- Stop loss effectiveness validation
- Portfolio protection mechanism validation
- Risk-adjusted returns analysis validation
- False risk signal reduction validation
- True risk signal detection validation
- Risk classification accuracy validation
- Multi-timeframe risk analysis validation
"""

import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class DrawdownLevel(Enum):
    """Drawdown severity levels"""
    MINIMAL = "minimal"  # <2% drawdown
    LOW = "low"  # 2-5% drawdown
    MODERATE = "moderate"  # 5-10% drawdown
    HIGH = "high"  # 10-15% drawdown
    CRITICAL = "critical"  # >15% drawdown

class DrawdownValidationStatus(Enum):
    """Drawdown validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class RiskControlType(Enum):
    """Risk control types"""
    POSITION_SIZING = "position_sizing"  # Position sizing controls
    STOP_LOSS = "stop_loss"  # Stop loss controls
    PORTFOLIO_LIMITS = "portfolio_limits"  # Portfolio-level limits
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker controls
    CORRELATION_LIMITS = "correlation_limits"  # Correlation limits
    VOLATILITY_CONTROLS = "volatility_controls"  # Volatility-based controls

class DrawdownTrigger(Enum):
    """Drawdown trigger types"""
    POSITION_LOSS = "position_loss"  # Individual position loss
    CORRELATION_SPIKE = "correlation_spike"  # High correlation losses
    VOLATILITY_SPIKE = "volatility_spike"  # Volatility-driven losses
    SYSTEM_ERROR = "system_error"  # System-related losses
    MARKET_SHOCK = "market_shock"  # Market shock losses
    LIQUIDITY_CRISIS = "liquidity_crisis"  # Liquidity-driven losses

@dataclass
class DrawdownEvent:
    """Drawdown event data structure"""
    event_id: str
    timestamp: float
    symbol: str
    drawdown_amount: float
    drawdown_percentage: float
    trigger_type: DrawdownTrigger
    risk_control_type: RiskControlType
    position_size: float
    stop_loss_distance: float
    market_volatility: float
    correlation_factor: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskControl:
    """Risk control data structure"""
    control_id: str
    control_type: RiskControlType
    symbol: str
    timestamp: float
    threshold_value: float
    current_value: float
    is_triggered: bool
    effectiveness_score: float
    response_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DrawdownValidation:
    """Drawdown validation result"""
    timestamp: float
    event_id: str
    expected_drawdown_limit: float
    actual_drawdown: float
    within_limits: bool
    risk_control_effectiveness: float
    position_sizing_accuracy: float
    stop_loss_effectiveness: float
    portfolio_protection_score: float
    overall_score: float
    validation_status: DrawdownValidationStatus
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DrawdownControlReport:
    """Drawdown control validation report"""
    timestamp: float
    overall_drawdown_control: float
    average_drawdown: float
    max_drawdown: float
    drawdown_level: DrawdownLevel
    validation_status: DrawdownValidationStatus
    total_events: int
    controlled_events: int
    uncontrolled_events: int
    total_drawdown_amount: float
    total_drawdown_percentage: float
    risk_control_analysis: Dict[str, float]
    position_sizing_analysis: Dict[str, float]
    stop_loss_analysis: Dict[str, float]
    portfolio_protection_analysis: Dict[str, float]
    performance_metrics: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[DrawdownValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class RiskControlAnalyzer:
    """Risk control analyzer for various risk management aspects"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def analyze_risk_control_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> Dict[str, Any]:
        """Analyze risk control effectiveness"""
        with self.lock:
            analysis = {}
            
            # Analyze position sizing effectiveness
            analysis["position_sizing_score"] = self._analyze_position_sizing_effectiveness(drawdown_event, risk_control)
            
            # Analyze stop loss effectiveness
            analysis["stop_loss_score"] = self._analyze_stop_loss_effectiveness(drawdown_event, risk_control)
            
            # Analyze portfolio protection
            analysis["portfolio_protection_score"] = self._analyze_portfolio_protection(drawdown_event, risk_control)
            
            # Analyze risk control response
            analysis["response_effectiveness"] = self._analyze_response_effectiveness(drawdown_event, risk_control)
            
            # Calculate overall risk control score
            analysis["overall_score"] = self._calculate_overall_risk_control_score(analysis)
            
            return analysis
    
    def analyze_position_sizing_accuracy(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> Dict[str, Any]:
        """Analyze position sizing accuracy"""
        with self.lock:
            analysis = {}
            
            # Analyze position size calculation
            analysis["size_calculation_accuracy"] = self._analyze_position_size_calculation(drawdown_event, risk_control)
            
            # Analyze risk percentage
            analysis["risk_percentage_accuracy"] = self._analyze_risk_percentage_accuracy(drawdown_event, risk_control)
            
            # Analyze position consistency
            analysis["position_consistency"] = self._analyze_position_consistency(drawdown_event, risk_control)
            
            # Calculate overall position sizing score
            analysis["overall_score"] = self._calculate_overall_position_sizing_score(analysis)
            
            return analysis
    
    def analyze_stop_loss_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> Dict[str, Any]:
        """Analyze stop loss effectiveness"""
        with self.lock:
            analysis = {}
            
            # Analyze stop loss placement
            analysis["stop_loss_placement"] = self._analyze_stop_loss_placement(drawdown_event, risk_control)
            
            # Analyze stop loss execution
            analysis["stop_loss_execution"] = self._analyze_stop_loss_execution(drawdown_event, risk_control)
            
            # Analyze stop loss timing
            analysis["stop_loss_timing"] = self._analyze_stop_loss_timing(drawdown_event, risk_control)
            
            # Calculate overall stop loss score
            analysis["overall_score"] = self._calculate_overall_stop_loss_score(analysis)
            
            return analysis
    
    def analyze_portfolio_protection(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> Dict[str, Any]:
        """Analyze portfolio protection mechanisms"""
        with self.lock:
            analysis = {}
            
            # Analyze correlation limits
            analysis["correlation_limits"] = self._analyze_correlation_limits(drawdown_event, risk_control)
            
            # Analyze volatility controls
            analysis["volatility_controls"] = self._analyze_volatility_controls(drawdown_event, risk_control)
            
            # Analyze circuit breaker effectiveness
            analysis["circuit_breaker_effectiveness"] = self._analyze_circuit_breaker_effectiveness(drawdown_event, risk_control)
            
            # Calculate overall portfolio protection score
            analysis["overall_score"] = self._calculate_overall_portfolio_protection_score(analysis)
            
            return analysis
    
    def _analyze_position_sizing_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze position sizing effectiveness"""
        # Calculate position sizing effectiveness based on drawdown vs position size
        expected_drawdown = drawdown_event.position_size * drawdown_event.stop_loss_distance
        actual_drawdown = drawdown_event.drawdown_amount
        
        if expected_drawdown > 0:
            effectiveness = max(0.0, 1.0 - abs(actual_drawdown - expected_drawdown) / expected_drawdown)
            return min(1.0, effectiveness)
        else:
            return 0.0
    
    def _analyze_stop_loss_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze stop loss effectiveness"""
        # Calculate stop loss effectiveness based on actual vs expected drawdown
        expected_drawdown = drawdown_event.position_size * drawdown_event.stop_loss_distance
        actual_drawdown = drawdown_event.drawdown_amount
        
        if expected_drawdown > 0:
            effectiveness = max(0.0, 1.0 - abs(actual_drawdown - expected_drawdown) / expected_drawdown)
            return min(1.0, effectiveness)
        else:
            return 0.0
    
    def _analyze_portfolio_protection(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze portfolio protection effectiveness"""
        # Calculate portfolio protection based on correlation and volatility factors
        correlation_factor = drawdown_event.correlation_factor
        volatility_factor = drawdown_event.market_volatility
        
        # Higher correlation and volatility should trigger better protection
        protection_score = 0.0
        
        if correlation_factor > 0.7:  # High correlation
            protection_score += 0.3
        
        if volatility_factor > 0.02:  # High volatility
            protection_score += 0.3
        
        if risk_control.is_triggered:
            protection_score += 0.4
        
        return min(1.0, protection_score)
    
    def _analyze_response_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze risk control response effectiveness"""
        # Calculate response effectiveness based on response time and trigger status
        response_time = risk_control.response_time_ms
        
        # Faster response is better (under 100ms is excellent)
        if response_time < 100:
            response_score = 1.0
        elif response_time < 500:
            response_score = 0.8
        elif response_time < 1000:
            response_score = 0.6
        else:
            response_score = 0.4
        
        # Trigger effectiveness
        trigger_score = 1.0 if risk_control.is_triggered else 0.5
        
        return (response_score + trigger_score) / 2.0
    
    def _calculate_overall_risk_control_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall risk control score"""
        scores = [
            analysis.get("position_sizing_score", 0.0),
            analysis.get("stop_loss_score", 0.0),
            analysis.get("portfolio_protection_score", 0.0),
            analysis.get("response_effectiveness", 0.0)
        ]
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _analyze_position_size_calculation(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze position size calculation accuracy"""
        # Calculate position size calculation accuracy
        optimal_size = risk_control.threshold_value / drawdown_event.stop_loss_distance
        actual_size = drawdown_event.position_size
        
        if optimal_size > 0:
            accuracy = min(actual_size / optimal_size, optimal_size / actual_size)
            return max(0.0, min(1.0, accuracy))
        else:
            return 0.0
    
    def _analyze_risk_percentage_accuracy(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze risk percentage accuracy"""
        # Calculate risk percentage accuracy
        risk_percentage = (drawdown_event.drawdown_amount / drawdown_event.position_size) * 100
        
        # Optimal risk percentage is typically 1-2%
        if 0.5 <= risk_percentage <= 3.0:
            return 1.0
        elif 0.25 <= risk_percentage <= 5.0:
            return 0.8
        else:
            return 0.5
    
    def _analyze_position_consistency(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze position consistency"""
        # Calculate position consistency score
        # This would typically compare with historical position sizes
        return 0.8  # Placeholder for consistency analysis
    
    def _calculate_overall_position_sizing_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall position sizing score"""
        scores = [
            analysis.get("size_calculation_accuracy", 0.0),
            analysis.get("risk_percentage_accuracy", 0.0),
            analysis.get("position_consistency", 0.0)
        ]
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _analyze_stop_loss_placement(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze stop loss placement"""
        # Calculate stop loss placement effectiveness
        stop_loss_distance = drawdown_event.stop_loss_distance
        actual_drawdown = drawdown_event.drawdown_amount
        
        if stop_loss_distance > 0:
            placement_score = max(0.0, 1.0 - abs(actual_drawdown - stop_loss_distance) / stop_loss_distance)
            return min(1.0, placement_score)
        else:
            return 0.0
    
    def _analyze_stop_loss_execution(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze stop loss execution"""
        # Calculate stop loss execution effectiveness
        expected_drawdown = drawdown_event.position_size * drawdown_event.stop_loss_distance
        actual_drawdown = drawdown_event.drawdown_amount
        
        if expected_drawdown > 0:
            execution_score = max(0.0, 1.0 - abs(actual_drawdown - expected_drawdown) / expected_drawdown)
            return min(1.0, execution_score)
        else:
            return 0.0
    
    def _analyze_stop_loss_timing(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze stop loss timing"""
        # Calculate stop loss timing effectiveness
        response_time = risk_control.response_time_ms
        
        # Faster response is better
        if response_time < 100:
            return 1.0
        elif response_time < 500:
            return 0.8
        elif response_time < 1000:
            return 0.6
        else:
            return 0.4
    
    def _calculate_overall_stop_loss_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall stop loss score"""
        scores = [
            analysis.get("stop_loss_placement", 0.0),
            analysis.get("stop_loss_execution", 0.0),
            analysis.get("stop_loss_timing", 0.0)
        ]
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _analyze_correlation_limits(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze correlation limits effectiveness"""
        # Calculate correlation limits effectiveness
        correlation_factor = drawdown_event.correlation_factor
        
        # Higher correlation should trigger better limits
        if correlation_factor > 0.8:
            return 1.0
        elif correlation_factor > 0.6:
            return 0.8
        elif correlation_factor > 0.4:
            return 0.6
        else:
            return 0.4
    
    def _analyze_volatility_controls(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze volatility controls effectiveness"""
        # Calculate volatility controls effectiveness
        volatility_factor = drawdown_event.market_volatility
        
        # Higher volatility should trigger better controls
        if volatility_factor > 0.03:
            return 1.0
        elif volatility_factor > 0.02:
            return 0.8
        elif volatility_factor > 0.01:
            return 0.6
        else:
            return 0.4
    
    def _analyze_circuit_breaker_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Analyze circuit breaker effectiveness"""
        # Calculate circuit breaker effectiveness
        if risk_control.control_type == RiskControlType.CIRCUIT_BREAKER:
            if risk_control.is_triggered:
                return 1.0
            else:
                return 0.5
        else:
            return 0.0
    
    def _calculate_overall_portfolio_protection_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall portfolio protection score"""
        scores = [
            analysis.get("correlation_limits", 0.0),
            analysis.get("volatility_controls", 0.0),
            analysis.get("circuit_breaker_effectiveness", 0.0)
        ]
        
        return sum(scores) / len(scores) if scores else 0.0

class DrawdownValidator:
    """Drawdown validator for control validation"""
    
    def __init__(self, max_drawdown_limit: float = 0.10):
        self.max_drawdown_limit = max_drawdown_limit
        self.validations: List[DrawdownValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def validate_drawdown_control(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> DrawdownValidation:
        """Validate drawdown control"""
        # Check if within limits
        within_limits = drawdown_event.drawdown_percentage <= self.max_drawdown_limit
        
        # Calculate various scores
        risk_control_effectiveness = self._calculate_risk_control_effectiveness(drawdown_event, risk_control)
        position_sizing_accuracy = self._calculate_position_sizing_accuracy(drawdown_event, risk_control)
        stop_loss_effectiveness = self._calculate_stop_loss_effectiveness(drawdown_event, risk_control)
        portfolio_protection_score = self._calculate_portfolio_protection_score(drawdown_event, risk_control)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(
            risk_control_effectiveness, position_sizing_accuracy, 
            stop_loss_effectiveness, portfolio_protection_score
        )
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            within_limits, overall_score, drawdown_event.drawdown_percentage
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            drawdown_event, risk_control, within_limits, overall_score
        )
        
        validation = DrawdownValidation(
            timestamp=time.time(),
            event_id=drawdown_event.event_id,
            expected_drawdown_limit=self.max_drawdown_limit,
            actual_drawdown=drawdown_event.drawdown_percentage,
            within_limits=within_limits,
            risk_control_effectiveness=risk_control_effectiveness,
            position_sizing_accuracy=position_sizing_accuracy,
            stop_loss_effectiveness=stop_loss_effectiveness,
            portfolio_protection_score=portfolio_protection_score,
            overall_score=overall_score,
            validation_status=validation_status,
            recommendations=recommendations,
            metadata={
                "max_drawdown_limit": self.max_drawdown_limit,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _calculate_risk_control_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Calculate risk control effectiveness"""
        # Calculate based on risk control effectiveness
        control_score = 0.0
        
        # Risk control trigger effectiveness
        if risk_control.is_triggered:
            control_score += 0.4
        
        # Response time effectiveness
        response_time = risk_control.response_time_ms
        if response_time < 100:
            control_score += 0.3
        elif response_time < 500:
            control_score += 0.2
        else:
            control_score += 0.1
        
        # Control type effectiveness
        if risk_control.control_type == RiskControlType.CIRCUIT_BREAKER:
            control_score += 0.3
        elif risk_control.control_type == RiskControlType.STOP_LOSS:
            control_score += 0.2
        else:
            control_score += 0.1
        
        return max(0.0, min(1.0, control_score))
    
    def _calculate_position_sizing_accuracy(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Calculate position sizing accuracy"""
        # Calculate based on position sizing accuracy
        sizing_score = 0.0
        
        # Position size calculation accuracy
        optimal_size = risk_control.threshold_value / drawdown_event.stop_loss_distance
        if optimal_size > 0:
            size_accuracy = min(drawdown_event.position_size / optimal_size, optimal_size / drawdown_event.position_size)
            sizing_score += size_accuracy * 0.5
        
        # Risk percentage accuracy
        risk_percentage = (drawdown_event.drawdown_amount / drawdown_event.position_size) * 100
        if 0.5 <= risk_percentage <= 3.0:
            sizing_score += 0.5
        elif 0.25 <= risk_percentage <= 5.0:
            sizing_score += 0.3
        else:
            sizing_score += 0.1
        
        return max(0.0, min(1.0, sizing_score))
    
    def _calculate_stop_loss_effectiveness(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Calculate stop loss effectiveness"""
        # Calculate based on stop loss effectiveness
        stop_loss_score = 0.0
        
        # Stop loss placement
        expected_drawdown = drawdown_event.position_size * drawdown_event.stop_loss_distance
        actual_drawdown = drawdown_event.drawdown_amount
        if expected_drawdown > 0:
            placement_accuracy = max(0.0, 1.0 - abs(actual_drawdown - expected_drawdown) / expected_drawdown)
            stop_loss_score += placement_accuracy * 0.5
        
        # Stop loss execution
        if risk_control.control_type == RiskControlType.STOP_LOSS and risk_control.is_triggered:
            stop_loss_score += 0.5
        
        return max(0.0, min(1.0, stop_loss_score))
    
    def _calculate_portfolio_protection_score(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> float:
        """Calculate portfolio protection score"""
        # Calculate based on portfolio protection mechanisms
        protection_score = 0.0
        
        # Correlation factor protection
        correlation_factor = drawdown_event.correlation_factor
        if correlation_factor > 0.7:
            protection_score += 0.3
        
        # Volatility factor protection
        volatility_factor = drawdown_event.market_volatility
        if volatility_factor > 0.02:
            protection_score += 0.3
        
        # Circuit breaker protection
        if risk_control.control_type == RiskControlType.CIRCUIT_BREAKER and risk_control.is_triggered:
            protection_score += 0.4
        
        return max(0.0, min(1.0, protection_score))
    
    def _calculate_overall_score(self, risk_control_effectiveness: float, position_sizing_accuracy: float,
                               stop_loss_effectiveness: float, portfolio_protection_score: float) -> float:
        """Calculate overall score"""
        scores = [risk_control_effectiveness, position_sizing_accuracy, stop_loss_effectiveness, portfolio_protection_score]
        return sum(scores) / len(scores)
    
    def _determine_validation_status(self, within_limits: bool, overall_score: float, 
                                   drawdown_percentage: float) -> DrawdownValidationStatus:
        """Determine validation status"""
        if within_limits and overall_score >= 0.8 and drawdown_percentage <= 0.05:
            return DrawdownValidationStatus.PASSED
        elif within_limits and overall_score >= 0.6:
            return DrawdownValidationStatus.WARNING
        else:
            return DrawdownValidationStatus.FAILED
    
    def _generate_recommendations(self, drawdown_event: DrawdownEvent, risk_control: RiskControl,
                                within_limits: bool, overall_score: float) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if not within_limits:
            recommendations.append("Drawdown exceeds limits. Implement stricter risk controls.")
        
        if drawdown_event.drawdown_percentage > 0.15:
            recommendations.append("Critical drawdown level. Consider emergency stop procedures.")
        
        if overall_score < 0.8:
            recommendations.append("Overall score below target. Review risk management practices.")
        
        if drawdown_event.correlation_factor > 0.8:
            recommendations.append("High correlation detected. Implement correlation limits.")
        
        if drawdown_event.market_volatility > 0.03:
            recommendations.append("High volatility detected. Implement volatility controls.")
        
        if not risk_control.is_triggered:
            recommendations.append("Risk control not triggered. Review control thresholds.")
        
        if risk_control.response_time_ms > 1000:
            recommendations.append("Slow risk control response. Optimize control mechanisms.")
        
        if within_limits and overall_score >= 0.9:
            recommendations.append("Drawdown control is excellent. Continue current strategies.")
        
        return recommendations
    
    def generate_validation_report(self) -> DrawdownControlReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return DrawdownControlReport(
                    timestamp=time.time(),
                    overall_drawdown_control=0.0,
                    average_drawdown=0.0,
                    max_drawdown=0.0,
                    drawdown_level=DrawdownLevel.CRITICAL,
                    validation_status=DrawdownValidationStatus.FAILED,
                    total_events=0,
                    controlled_events=0,
                    uncontrolled_events=0,
                    total_drawdown_amount=0.0,
                    total_drawdown_percentage=0.0,
                    risk_control_analysis={},
                    position_sizing_analysis={},
                    stop_loss_analysis={},
                    portfolio_protection_analysis={},
                    performance_metrics={},
                    recommendations=["No validation data available"],
                    detailed_validations=[],
                    metadata={"error": "No validation data available"}
                )
        
        # Calculate overall metrics
        total_events = len(self.validations)
        controlled_events = sum(1 for v in self.validations if v.within_limits)
        uncontrolled_events = total_events - controlled_events
        
        total_drawdown_amount = sum(v.actual_drawdown for v in self.validations)
        total_drawdown_percentage = sum(v.actual_drawdown for v in self.validations)
        average_drawdown = total_drawdown_percentage / total_events if total_events > 0 else 0.0
        max_drawdown = max(v.actual_drawdown for v in self.validations) if self.validations else 0.0
        
        overall_drawdown_control = controlled_events / total_events if total_events > 0 else 0.0
        
        # Determine drawdown level
        if max_drawdown < 0.02:
            drawdown_level = DrawdownLevel.MINIMAL
        elif max_drawdown < 0.05:
            drawdown_level = DrawdownLevel.LOW
        elif max_drawdown < 0.10:
            drawdown_level = DrawdownLevel.MODERATE
        elif max_drawdown < 0.15:
            drawdown_level = DrawdownLevel.HIGH
        else:
            drawdown_level = DrawdownLevel.CRITICAL
        
        # Determine validation status
        if overall_drawdown_control >= 0.9 and max_drawdown <= 0.05:
            validation_status = DrawdownValidationStatus.PASSED
        elif overall_drawdown_control >= 0.7:
            validation_status = DrawdownValidationStatus.WARNING
        else:
            validation_status = DrawdownValidationStatus.FAILED
        
        # Analysis by risk control type
        risk_control_analysis = self._calculate_risk_control_analysis()
        position_sizing_analysis = self._calculate_position_sizing_analysis()
        stop_loss_analysis = self._calculate_stop_loss_analysis()
        portfolio_protection_analysis = self._calculate_portfolio_protection_analysis()
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(
            overall_drawdown_control, drawdown_level, validation_status, max_drawdown
        )
        
        return DrawdownControlReport(
            timestamp=time.time(),
            overall_drawdown_control=overall_drawdown_control,
            average_drawdown=average_drawdown,
            max_drawdown=max_drawdown,
            drawdown_level=drawdown_level,
            validation_status=validation_status,
            total_events=total_events,
            controlled_events=controlled_events,
            uncontrolled_events=uncontrolled_events,
            total_drawdown_amount=total_drawdown_amount,
            total_drawdown_percentage=total_drawdown_percentage,
            risk_control_analysis=risk_control_analysis,
            position_sizing_analysis=position_sizing_analysis,
            stop_loss_analysis=stop_loss_analysis,
            portfolio_protection_analysis=portfolio_protection_analysis,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            detailed_validations=self.validations.copy(),
            metadata={
                "max_drawdown_limit": self.max_drawdown_limit,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _calculate_risk_control_analysis(self) -> Dict[str, float]:
        """Calculate risk control analysis"""
        analysis = {}
        
        if self.validations:
            risk_scores = [v.risk_control_effectiveness for v in self.validations]
            analysis["average_risk_control_score"] = sum(risk_scores) / len(risk_scores)
            analysis["max_risk_control_score"] = max(risk_scores)
            analysis["min_risk_control_score"] = min(risk_scores)
        else:
            analysis["average_risk_control_score"] = 0.0
            analysis["max_risk_control_score"] = 0.0
            analysis["min_risk_control_score"] = 0.0
        
        return analysis
    
    def _calculate_position_sizing_analysis(self) -> Dict[str, float]:
        """Calculate position sizing analysis"""
        analysis = {}
        
        if self.validations:
            sizing_scores = [v.position_sizing_accuracy for v in self.validations]
            analysis["average_position_sizing_score"] = sum(sizing_scores) / len(sizing_scores)
            analysis["max_position_sizing_score"] = max(sizing_scores)
            analysis["min_position_sizing_score"] = min(sizing_scores)
        else:
            analysis["average_position_sizing_score"] = 0.0
            analysis["max_position_sizing_score"] = 0.0
            analysis["min_position_sizing_score"] = 0.0
        
        return analysis
    
    def _calculate_stop_loss_analysis(self) -> Dict[str, float]:
        """Calculate stop loss analysis"""
        analysis = {}
        
        if self.validations:
            stop_loss_scores = [v.stop_loss_effectiveness for v in self.validations]
            analysis["average_stop_loss_score"] = sum(stop_loss_scores) / len(stop_loss_scores)
            analysis["max_stop_loss_score"] = max(stop_loss_scores)
            analysis["min_stop_loss_score"] = min(stop_loss_scores)
        else:
            analysis["average_stop_loss_score"] = 0.0
            analysis["max_stop_loss_score"] = 0.0
            analysis["min_stop_loss_score"] = 0.0
        
        return analysis
    
    def _calculate_portfolio_protection_analysis(self) -> Dict[str, float]:
        """Calculate portfolio protection analysis"""
        analysis = {}
        
        if self.validations:
            protection_scores = [v.portfolio_protection_score for v in self.validations]
            analysis["average_portfolio_protection_score"] = sum(protection_scores) / len(protection_scores)
            analysis["max_portfolio_protection_score"] = max(protection_scores)
            analysis["min_portfolio_protection_score"] = min(protection_scores)
        else:
            analysis["average_portfolio_protection_score"] = 0.0
            analysis["max_portfolio_protection_score"] = 0.0
            analysis["min_portfolio_protection_score"] = 0.0
        
        return analysis
    
    def _calculate_performance_metrics(self) -> Dict[str, float]:
        """Calculate performance metrics"""
        metrics = {}
        
        if self.validations:
            validation_times = [v.timestamp for v in self.validations]
            metrics["avg_validation_time_ms"] = (max(validation_times) - min(validation_times)) / len(validation_times) * 1000
            metrics["total_validations"] = len(self.validations)
            
            # Calculate validation rate per second, avoiding division by zero
            duration = time.time() - self.start_time
            if duration > 0:
                metrics["validation_rate_per_second"] = len(self.validations) / duration
            else:
                metrics["validation_rate_per_second"] = 0.0
        
        return metrics
    
    def _generate_report_recommendations(self, overall_drawdown_control: float, drawdown_level: DrawdownLevel,
                                       validation_status: DrawdownValidationStatus, max_drawdown: float) -> List[str]:
        """Generate report recommendations"""
        recommendations = []
        
        if validation_status == DrawdownValidationStatus.FAILED:
            recommendations.append("Drawdown control validation failed. Review risk management strategies.")
            if max_drawdown > 0.15:
                recommendations.append("Critical drawdown level. Implement emergency stop procedures.")
        elif validation_status == DrawdownValidationStatus.WARNING:
            recommendations.append("Drawdown control validation passed with warnings. Monitor performance.")
        else:
            recommendations.append("Drawdown control validation passed successfully.")
        
        if drawdown_level == DrawdownLevel.CRITICAL:
            recommendations.append("Critical drawdown level detected. Immediate attention required.")
        elif drawdown_level == DrawdownLevel.HIGH:
            recommendations.append("High drawdown level detected. Consider stricter risk controls.")
        elif drawdown_level == DrawdownLevel.MODERATE:
            recommendations.append("Moderate drawdown level. Monitor risk management effectiveness.")
        elif drawdown_level == DrawdownLevel.LOW:
            recommendations.append("Low drawdown level. Good risk management practices.")
        else:
            recommendations.append("Minimal drawdown level. Excellent risk management.")
        
        if overall_drawdown_control < 0.8:
            recommendations.append("Consider improving drawdown control mechanisms.")
        
        if max_drawdown > 0.10:
            recommendations.append("Consider implementing stricter drawdown limits.")
        
        return recommendations

class DrawdownControlManager:
    """Main drawdown control validation manager"""
    
    def __init__(self, max_drawdown_limit: float = 0.10):
        self.analyzer = RiskControlAnalyzer()
        self.validator = DrawdownValidator(max_drawdown_limit)
        self.start_time = time.time()
        self.validation_reports: List[DrawdownControlReport] = []
        self.lock = threading.RLock()
    
    def validate_drawdown_control(self, drawdown_event: DrawdownEvent, risk_control: RiskControl) -> DrawdownValidation:
        """Validate drawdown control"""
        # Perform analysis
        risk_analysis = self.analyzer.analyze_risk_control_effectiveness(drawdown_event, risk_control)
        position_analysis = self.analyzer.analyze_position_sizing_accuracy(drawdown_event, risk_control)
        stop_loss_analysis = self.analyzer.analyze_stop_loss_effectiveness(drawdown_event, risk_control)
        portfolio_analysis = self.analyzer.analyze_portfolio_protection(drawdown_event, risk_control)
        
        # Validate drawdown control
        validation = self.validator.validate_drawdown_control(drawdown_event, risk_control)
        
        return validation
    
    def generate_validation_report(self) -> DrawdownControlReport:
        """Generate validation report"""
        report = self.validator.generate_validation_report()
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[DrawdownControlReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        with self.lock:
            if not self.validator.validations:
                return {"total_validations": 0}
            
            total_validations = len(self.validator.validations)
            within_limits = sum(1 for v in self.validator.validations if v.within_limits)
            average_drawdown = sum(v.actual_drawdown for v in self.validator.validations) / total_validations if total_validations > 0 else 0.0
            overall_score = sum(v.overall_score for v in self.validator.validations) / total_validations if total_validations > 0 else 0.0
            
            return {
                "total_validations": total_validations,
                "within_limits": within_limits,
                "average_drawdown": average_drawdown,
                "overall_score": overall_score,
                "max_drawdown_limit": self.validator.max_drawdown_limit
            }
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.validator.validations.clear()
            self.validation_reports.clear()

# Global drawdown control validation manager
_drawdown_control_validation_manager: Optional[DrawdownControlManager] = None

def get_drawdown_control_validation_manager(max_drawdown_limit: float = 0.10) -> DrawdownControlManager:
    """Get global drawdown control validation manager instance"""
    global _drawdown_control_validation_manager
    if _drawdown_control_validation_manager is None:
        _drawdown_control_validation_manager = DrawdownControlManager(max_drawdown_limit)
    return _drawdown_control_validation_manager

def validate_drawdown_control(drawdown_event: DrawdownEvent, risk_control: RiskControl) -> DrawdownValidation:
    """Validate drawdown control"""
    manager = get_drawdown_control_validation_manager()
    return manager.validate_drawdown_control(drawdown_event, risk_control)

def generate_drawdown_control_validation_report() -> DrawdownControlReport:
    """Generate drawdown control validation report"""
    manager = get_drawdown_control_validation_manager()
    return manager.generate_validation_report()

def get_drawdown_control_validation_summary() -> Dict[str, Any]:
    """Get drawdown control validation summary"""
    manager = get_drawdown_control_validation_manager()
    return manager.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    manager = get_drawdown_control_validation_manager()
    
    # Example drawdown event
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
    
    # Example risk control
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
    
    validation = validate_drawdown_control(drawdown_event, risk_control)
    
    print(f"Drawdown Control Validation:")
    print(f"Event ID: {validation.event_id}")
    print(f"Expected Drawdown Limit: {validation.expected_drawdown_limit:.1%}")
    print(f"Actual Drawdown: {validation.actual_drawdown:.1%}")
    print(f"Within Limits: {validation.within_limits}")
    print(f"Risk Control Effectiveness: {validation.risk_control_effectiveness:.2f}")
    print(f"Position Sizing Accuracy: {validation.position_sizing_accuracy:.2f}")
    print(f"Stop Loss Effectiveness: {validation.stop_loss_effectiveness:.2f}")
    print(f"Portfolio Protection Score: {validation.portfolio_protection_score:.2f}")
    print(f"Overall Score: {validation.overall_score:.2f}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    print("\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate validation report
    report = generate_drawdown_control_validation_report()
    
    print(f"\nDrawdown Control Validation Report:")
    print(f"Overall Drawdown Control: {report.overall_drawdown_control:.2%}")
    print(f"Average Drawdown: {report.average_drawdown:.1%}")
    print(f"Max Drawdown: {report.max_drawdown:.1%}")
    print(f"Drawdown Level: {report.drawdown_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Events: {report.total_events}")
    print(f"Controlled Events: {report.controlled_events}")
    print(f"Uncontrolled Events: {report.uncontrolled_events}")
    print(f"Total Drawdown Amount: {report.total_drawdown_amount:.2f}")
    print(f"Total Drawdown Percentage: {report.total_drawdown_percentage:.1%}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
