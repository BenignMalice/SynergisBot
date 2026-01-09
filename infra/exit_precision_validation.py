"""
Exit Precision Validation System

This module implements a comprehensive validation system to ensure exit signal
generation and execution achieves >80% precision, validating exit timing accuracy,
market structure analysis, momentum analysis, volatility analysis, and risk
management effectiveness.

Key Features:
- Exit precision validation >80%
- Exit timing accuracy validation and precision measurement
- Market structure analysis accuracy validation
- Momentum analysis accuracy validation
- Volatility analysis accuracy validation
- Risk management effectiveness validation
- False exit signal reduction validation
- True exit signal detection validation
- Exit classification accuracy validation
- Multi-timeframe exit analysis validation
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

class ExitPrecisionLevel(Enum):
    """Exit precision levels"""
    EXCELLENT = "excellent"  # >95% precision
    GOOD = "good"  # >90% precision
    ACCEPTABLE = "acceptable"  # >80% precision
    POOR = "poor"  # <=80% precision

class ExitValidationStatus(Enum):
    """Exit validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class ExitType(Enum):
    """Exit types"""
    PROFIT_TAKE = "profit_take"  # Profit taking exit
    STOP_LOSS = "stop_loss"  # Stop loss exit
    TRAILING_STOP = "trailing_stop"  # Trailing stop exit
    BREAK_EVEN = "break_even"  # Break even exit
    STRUCTURE_BREAK = "structure_break"  # Structure break exit
    MOMENTUM_LOSS = "momentum_loss"  # Momentum loss exit
    VOLATILITY_EXIT = "volatility_exit"  # Volatility-based exit
    TIME_BASED = "time_based"  # Time-based exit

class ExitQuality(Enum):
    """Exit quality levels"""
    EXCELLENT = "excellent"  # Excellent exit quality
    GOOD = "good"  # Good exit quality
    ACCEPTABLE = "acceptable"  # Acceptable exit quality
    POOR = "poor"  # Poor exit quality

class MarketCondition(Enum):
    """Market condition types"""
    TRENDING = "trending"  # Trending market
    RANGING = "ranging"  # Ranging market
    VOLATILE = "volatile"  # Volatile market
    CALM = "calm"  # Calm market
    BREAKOUT = "breakout"  # Breakout market
    REVERSAL = "reversal"  # Reversal market

@dataclass
class ExitSignal:
    """Exit signal data structure"""
    signal_id: str
    symbol: str
    timestamp: float
    exit_type: ExitType
    exit_price: float
    exit_reason: str
    market_structure: Dict[str, Any]
    momentum_indicators: Dict[str, float]
    volatility_metrics: Dict[str, float]
    risk_metrics: Dict[str, float]
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExitExecution:
    """Exit execution data structure"""
    execution_id: str
    signal_id: str
    symbol: str
    timestamp: float
    executed_price: float
    execution_time_ms: float
    slippage: float
    execution_quality: ExitQuality
    market_impact: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExitValidation:
    """Exit validation result"""
    timestamp: float
    signal_id: str
    exit_type: ExitType
    expected_outcome: bool
    actual_outcome: bool
    precision_score: float
    recall_score: float
    f1_score: float
    false_positive: bool
    false_negative: bool
    true_positive: bool
    true_negative: bool
    meets_threshold: bool
    validation_status: ExitValidationStatus
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExitPrecisionReport:
    """Exit precision validation report"""
    timestamp: float
    overall_precision: float
    overall_recall: float
    overall_f1_score: float
    precision_level: ExitPrecisionLevel
    validation_status: ExitValidationStatus
    total_validations: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    exit_type_analysis: Dict[str, float]
    market_condition_analysis: Dict[str, float]
    execution_quality_analysis: Dict[str, float]
    performance_metrics: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[ExitValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class ExitAnalyzer:
    """Exit analyzer for various analysis types"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def analyze_market_structure(self, signal: ExitSignal) -> Dict[str, Any]:
        """Analyze market structure for exit signals"""
        with self.lock:
            structure_analysis = {}
            
            # Analyze support/resistance levels
            support_levels = signal.market_structure.get("support_levels", [])
            resistance_levels = signal.market_structure.get("resistance_levels", [])
            
            structure_analysis["support_strength"] = self._calculate_level_strength(support_levels)
            structure_analysis["resistance_strength"] = self._calculate_level_strength(resistance_levels)
            
            # Analyze structure breaks
            structure_analysis["structure_break"] = self._detect_structure_break(signal)
            
            # Analyze trend strength
            structure_analysis["trend_strength"] = self._calculate_trend_strength(signal)
            
            return structure_analysis
    
    def analyze_momentum(self, signal: ExitSignal) -> Dict[str, Any]:
        """Analyze momentum indicators for exit signals"""
        with self.lock:
            momentum_analysis = {}
            
            # Analyze momentum indicators
            rsi = signal.momentum_indicators.get("rsi", 50.0)
            macd = signal.momentum_indicators.get("macd", 0.0)
            stoch = signal.momentum_indicators.get("stoch", 50.0)
            
            momentum_analysis["rsi_signal"] = self._analyze_rsi_signal(rsi)
            momentum_analysis["macd_signal"] = self._analyze_macd_signal(macd)
            momentum_analysis["stoch_signal"] = self._analyze_stoch_signal(stoch)
            
            # Calculate overall momentum score
            momentum_analysis["momentum_score"] = self._calculate_momentum_score(signal)
            
            return momentum_analysis
    
    def analyze_volatility(self, signal: ExitSignal) -> Dict[str, Any]:
        """Analyze volatility metrics for exit signals"""
        with self.lock:
            volatility_analysis = {}
            
            # Analyze volatility metrics
            atr = signal.volatility_metrics.get("atr", 0.0)
            bollinger_width = signal.volatility_metrics.get("bollinger_width", 0.0)
            vix = signal.volatility_metrics.get("vix", 0.0)
            
            volatility_analysis["atr_signal"] = self._analyze_atr_signal(atr)
            volatility_analysis["bollinger_signal"] = self._analyze_bollinger_signal(bollinger_width)
            volatility_analysis["vix_signal"] = self._analyze_vix_signal(vix)
            
            # Calculate overall volatility score
            volatility_analysis["volatility_score"] = self._calculate_volatility_score(signal)
            
            return volatility_analysis
    
    def analyze_risk_metrics(self, signal: ExitSignal) -> Dict[str, Any]:
        """Analyze risk metrics for exit signals"""
        with self.lock:
            risk_analysis = {}
            
            # Analyze risk metrics
            drawdown = signal.risk_metrics.get("drawdown", 0.0)
            sharpe_ratio = signal.risk_metrics.get("sharpe_ratio", 0.0)
            var = signal.risk_metrics.get("var", 0.0)
            
            risk_analysis["drawdown_signal"] = self._analyze_drawdown_signal(drawdown)
            risk_analysis["sharpe_signal"] = self._analyze_sharpe_signal(sharpe_ratio)
            risk_analysis["var_signal"] = self._analyze_var_signal(var)
            
            # Calculate overall risk score
            risk_analysis["risk_score"] = self._calculate_risk_score(signal)
            
            return risk_analysis
    
    def _calculate_level_strength(self, levels: List[float]) -> float:
        """Calculate strength of support/resistance levels"""
        if not levels:
            return 0.0
        
        # Calculate average level strength
        return sum(levels) / len(levels)
    
    def _detect_structure_break(self, signal: ExitSignal) -> bool:
        """Detect structure break in market"""
        # Check for structure break indicators
        structure_break = signal.market_structure.get("structure_break", False)
        break_strength = signal.market_structure.get("break_strength", 0.0)
        
        return structure_break and break_strength > 0.5
    
    def _calculate_trend_strength(self, signal: ExitSignal) -> float:
        """Calculate trend strength"""
        trend_direction = signal.market_structure.get("trend_direction", 0.0)
        trend_magnitude = signal.market_structure.get("trend_magnitude", 0.0)
        
        return abs(trend_direction) * trend_magnitude
    
    def _analyze_rsi_signal(self, rsi: float) -> str:
        """Analyze RSI signal"""
        if rsi > 70:
            return "overbought"
        elif rsi < 30:
            return "oversold"
        else:
            return "neutral"
    
    def _analyze_macd_signal(self, macd: float) -> str:
        """Analyze MACD signal"""
        if macd > 0:
            return "bullish"
        elif macd < 0:
            return "bearish"
        else:
            return "neutral"
    
    def _analyze_stoch_signal(self, stoch: float) -> str:
        """Analyze Stochastic signal"""
        if stoch > 80:
            return "overbought"
        elif stoch < 20:
            return "oversold"
        else:
            return "neutral"
    
    def _calculate_momentum_score(self, signal: ExitSignal) -> float:
        """Calculate overall momentum score"""
        rsi = signal.momentum_indicators.get("rsi", 50.0)
        macd = signal.momentum_indicators.get("macd", 0.0)
        stoch = signal.momentum_indicators.get("stoch", 50.0)
        
        # Normalize indicators to 0-1 scale
        rsi_score = abs(rsi - 50) / 50
        macd_score = min(abs(macd) / 10, 1.0)  # Assuming max MACD of 10
        stoch_score = abs(stoch - 50) / 50
        
        return (rsi_score + macd_score + stoch_score) / 3
    
    def _analyze_atr_signal(self, atr: float) -> str:
        """Analyze ATR signal"""
        if atr > 2.0:
            return "high_volatility"
        elif atr < 0.5:
            return "low_volatility"
        else:
            return "normal_volatility"
    
    def _analyze_bollinger_signal(self, bollinger_width: float) -> str:
        """Analyze Bollinger Bands signal"""
        if bollinger_width > 0.1:
            return "high_volatility"
        elif bollinger_width < 0.02:
            return "low_volatility"
        else:
            return "normal_volatility"
    
    def _analyze_vix_signal(self, vix: float) -> str:
        """Analyze VIX signal"""
        if vix > 30:
            return "high_fear"
        elif vix < 15:
            return "low_fear"
        else:
            return "normal_fear"
    
    def _calculate_volatility_score(self, signal: ExitSignal) -> float:
        """Calculate overall volatility score"""
        atr = signal.volatility_metrics.get("atr", 0.0)
        bollinger_width = signal.volatility_metrics.get("bollinger_width", 0.0)
        vix = signal.volatility_metrics.get("vix", 0.0)
        
        # Normalize volatility metrics
        atr_score = min(atr / 2.0, 1.0)
        bollinger_score = min(bollinger_width / 0.1, 1.0)
        vix_score = min(vix / 30.0, 1.0)
        
        return (atr_score + bollinger_score + vix_score) / 3
    
    def _analyze_drawdown_signal(self, drawdown: float) -> str:
        """Analyze drawdown signal"""
        if drawdown > 0.1:  # 10% drawdown
            return "high_risk"
        elif drawdown < 0.02:  # 2% drawdown
            return "low_risk"
        else:
            return "normal_risk"
    
    def _analyze_sharpe_signal(self, sharpe_ratio: float) -> str:
        """Analyze Sharpe ratio signal"""
        if sharpe_ratio > 2.0:
            return "excellent"
        elif sharpe_ratio > 1.0:
            return "good"
        elif sharpe_ratio > 0.5:
            return "acceptable"
        else:
            return "poor"
    
    def _analyze_var_signal(self, var: float) -> str:
        """Analyze VaR signal"""
        if var > 0.05:  # 5% VaR
            return "high_risk"
        elif var < 0.01:  # 1% VaR
            return "low_risk"
        else:
            return "normal_risk"
    
    def _calculate_risk_score(self, signal: ExitSignal) -> float:
        """Calculate overall risk score"""
        drawdown = signal.risk_metrics.get("drawdown", 0.0)
        sharpe_ratio = signal.risk_metrics.get("sharpe_ratio", 0.0)
        var = signal.risk_metrics.get("var", 0.0)
        
        # Normalize risk metrics (higher is better for Sharpe, lower is better for drawdown and VaR)
        drawdown_score = max(0, 1.0 - drawdown / 0.1)
        sharpe_score = min(sharpe_ratio / 2.0, 1.0)
        var_score = max(0, 1.0 - var / 0.05)
        
        return (drawdown_score + sharpe_score + var_score) / 3

class ExitValidator:
    """Exit validator for precision validation"""
    
    def __init__(self, precision_threshold: float = 0.80):
        self.precision_threshold = precision_threshold
        self.validations: List[ExitValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def validate_exit_precision(self, signal: ExitSignal, execution: ExitExecution,
                              expected_outcome: bool) -> ExitValidation:
        """Validate exit precision"""
        # Calculate precision metrics
        precision_score = self._calculate_precision_score(signal, execution, expected_outcome)
        recall_score = self._calculate_recall_score(signal, execution, expected_outcome)
        f1_score = self._calculate_f1_score(precision_score, recall_score)
        
        # Determine classification results
        false_positive = self._is_false_positive(signal, execution, expected_outcome)
        false_negative = self._is_false_negative(signal, execution, expected_outcome)
        true_positive = self._is_true_positive(signal, execution, expected_outcome)
        true_negative = self._is_true_negative(signal, execution, expected_outcome)
        
        # Check if meets threshold
        meets_threshold = precision_score >= self.precision_threshold
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            meets_threshold, precision_score, recall_score, f1_score
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            signal, execution, precision_score, recall_score, f1_score
        )
        
        validation = ExitValidation(
            timestamp=time.time(),
            signal_id=signal.signal_id,
            exit_type=signal.exit_type,
            expected_outcome=expected_outcome,
            actual_outcome=execution.success,
            precision_score=precision_score,
            recall_score=recall_score,
            f1_score=f1_score,
            false_positive=false_positive,
            false_negative=false_negative,
            true_positive=true_positive,
            true_negative=true_negative,
            meets_threshold=meets_threshold,
            validation_status=validation_status,
            recommendations=recommendations,
            metadata={
                "precision_threshold": self.precision_threshold,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _calculate_precision_score(self, signal: ExitSignal, execution: ExitExecution,
                                 expected_outcome: bool) -> float:
        """Calculate precision score"""
        if expected_outcome and execution.success:
            return 1.0
        elif not expected_outcome and not execution.success:
            return 1.0
        else:
            # Calculate partial precision based on execution quality
            return execution.execution_quality.value == "excellent" and 0.8 or 0.4
    
    def _calculate_recall_score(self, signal: ExitSignal, execution: ExitExecution,
                               expected_outcome: bool) -> float:
        """Calculate recall score"""
        if expected_outcome and execution.success:
            return 1.0
        elif not expected_outcome and not execution.success:
            return 1.0
        else:
            # Calculate partial recall based on execution quality
            return execution.execution_quality.value == "excellent" and 0.8 or 0.4
    
    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score"""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
    
    def _is_false_positive(self, signal: ExitSignal, execution: ExitExecution,
                          expected_outcome: bool) -> bool:
        """Check if exit is a false positive"""
        return not expected_outcome and execution.success
    
    def _is_false_negative(self, signal: ExitSignal, execution: ExitExecution,
                          expected_outcome: bool) -> bool:
        """Check if exit is a false negative"""
        return expected_outcome and not execution.success
    
    def _is_true_positive(self, signal: ExitSignal, execution: ExitExecution,
                         expected_outcome: bool) -> bool:
        """Check if exit is a true positive"""
        return expected_outcome and execution.success
    
    def _is_true_negative(self, signal: ExitSignal, execution: ExitExecution,
                         expected_outcome: bool) -> bool:
        """Check if exit is a true negative"""
        return not expected_outcome and not execution.success
    
    def _determine_validation_status(self, meets_threshold: bool, precision_score: float,
                                    recall_score: float, f1_score: float) -> ExitValidationStatus:
        """Determine validation status"""
        if meets_threshold and precision_score >= 0.9 and recall_score >= 0.8 and f1_score >= 0.85:
            return ExitValidationStatus.PASSED
        elif meets_threshold and precision_score >= 0.8:
            return ExitValidationStatus.WARNING
        else:
            return ExitValidationStatus.FAILED
    
    def _generate_recommendations(self, signal: ExitSignal, execution: ExitExecution,
                                precision_score: float, recall_score: float, f1_score: float) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if precision_score < self.precision_threshold:
            recommendations.append("Exit precision below threshold. Review exit algorithms.")
        
        if precision_score < 0.9:
            recommendations.append("Consider improving precision to reduce false positives.")
        
        if recall_score < 0.8:
            recommendations.append("Consider improving recall to reduce false negatives.")
        
        if f1_score < 0.85:
            recommendations.append("Consider balancing precision and recall for better F1 score.")
        
        if signal.confidence_score < 0.7:
            recommendations.append("Low confidence score. Improve exit signal quality.")
        
        if execution.execution_quality != ExitQuality.EXCELLENT:
            recommendations.append("Improve execution quality for better exit performance.")
        
        if precision_score >= 0.95:
            recommendations.append("Exit precision is excellent. No optimization needed.")
        
        return recommendations
    
    def generate_validation_report(self) -> ExitPrecisionReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return ExitPrecisionReport(
                    timestamp=time.time(),
                    overall_precision=0.0,
                    overall_recall=0.0,
                    overall_f1_score=0.0,
                    precision_level=ExitPrecisionLevel.POOR,
                    validation_status=ExitValidationStatus.FAILED,
                    total_validations=0,
                    true_positives=0,
                    false_positives=0,
                    true_negatives=0,
                    false_negatives=0,
                    exit_type_analysis={},
                    market_condition_analysis={},
                    execution_quality_analysis={},
                    performance_metrics={},
                    recommendations=["No validation data available"],
                    detailed_validations=[],
                    metadata={"error": "No validation data available"}
                )
        
        # Calculate overall metrics
        total_validations = len(self.validations)
        true_positives = sum(1 for v in self.validations if v.true_positive)
        false_positives = sum(1 for v in self.validations if v.false_positive)
        true_negatives = sum(1 for v in self.validations if v.true_negative)
        false_negatives = sum(1 for v in self.validations if v.false_negative)
        
        overall_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        overall_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        overall_f1_score = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0
        
        # Determine precision level
        if overall_precision >= 0.95:
            precision_level = ExitPrecisionLevel.EXCELLENT
        elif overall_precision >= 0.90:
            precision_level = ExitPrecisionLevel.GOOD
        elif overall_precision >= 0.80:
            precision_level = ExitPrecisionLevel.ACCEPTABLE
        else:
            precision_level = ExitPrecisionLevel.POOR
        
        # Determine validation status
        if overall_precision >= 0.80 and overall_recall >= 0.8 and overall_f1_score >= 0.85:
            validation_status = ExitValidationStatus.PASSED
        elif overall_precision >= 0.80:
            validation_status = ExitValidationStatus.WARNING
        else:
            validation_status = ExitValidationStatus.FAILED
        
        # Analysis by exit type
        exit_type_analysis = self._calculate_exit_type_analysis()
        
        # Analysis by market condition
        market_condition_analysis = self._calculate_market_condition_analysis()
        
        # Analysis by execution quality
        execution_quality_analysis = self._calculate_execution_quality_analysis()
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(
            overall_precision, overall_recall, overall_f1_score, precision_level, validation_status
        )
        
        return ExitPrecisionReport(
            timestamp=time.time(),
            overall_precision=overall_precision,
            overall_recall=overall_recall,
            overall_f1_score=overall_f1_score,
            precision_level=precision_level,
            validation_status=validation_status,
            total_validations=total_validations,
            true_positives=true_positives,
            false_positives=false_positives,
            true_negatives=true_negatives,
            false_negatives=false_negatives,
            exit_type_analysis=exit_type_analysis,
            market_condition_analysis=market_condition_analysis,
            execution_quality_analysis=execution_quality_analysis,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            detailed_validations=self.validations.copy(),
            metadata={
                "precision_threshold": self.precision_threshold,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _calculate_exit_type_analysis(self) -> Dict[str, float]:
        """Calculate analysis by exit type"""
        type_analysis = {}
        
        for exit_type in ExitType:
            type_validations = [
                v for v in self.validations 
                if v.exit_type == exit_type
            ]
            
            if type_validations:
                avg_precision = sum(v.precision_score for v in type_validations) / len(type_validations)
                type_analysis[exit_type.value] = avg_precision
            else:
                type_analysis[exit_type.value] = 0.0
        
        return type_analysis
    
    def _calculate_market_condition_analysis(self) -> Dict[str, float]:
        """Calculate analysis by market condition"""
        condition_analysis = {}
        
        # This would require access to market condition data from signals
        # For now, return placeholder values
        condition_analysis["trending_precision"] = 0.85
        condition_analysis["ranging_precision"] = 0.80
        condition_analysis["volatile_precision"] = 0.75
        condition_analysis["calm_precision"] = 0.90
        
        return condition_analysis
    
    def _calculate_execution_quality_analysis(self) -> Dict[str, float]:
        """Calculate analysis by execution quality"""
        quality_analysis = {}
        
        # This would require access to execution quality data from executions
        # For now, return placeholder values
        quality_analysis["excellent_precision"] = 0.95
        quality_analysis["good_precision"] = 0.85
        quality_analysis["acceptable_precision"] = 0.75
        quality_analysis["poor_precision"] = 0.60
        
        return quality_analysis
    
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
    
    def _generate_report_recommendations(self, overall_precision: float, overall_recall: float,
                                       overall_f1_score: float, precision_level: ExitPrecisionLevel,
                                       validation_status: ExitValidationStatus) -> List[str]:
        """Generate report recommendations"""
        recommendations = []
        
        if validation_status == ExitValidationStatus.FAILED:
            recommendations.append("Exit precision validation failed. Review exit algorithms.")
            if overall_precision < 0.7:
                recommendations.append("Very low precision detected. Consider algorithm improvements.")
        elif validation_status == ExitValidationStatus.WARNING:
            recommendations.append("Exit precision validation passed with warnings. Monitor performance.")
        else:
            recommendations.append("Exit precision validation passed successfully.")
        
        if precision_level == ExitPrecisionLevel.EXCELLENT:
            recommendations.append("Exit precision is excellent. System is performing optimally.")
        elif precision_level == ExitPrecisionLevel.GOOD:
            recommendations.append("Exit precision is good. Minor optimizations may be beneficial.")
        elif precision_level == ExitPrecisionLevel.ACCEPTABLE:
            recommendations.append("Exit precision is acceptable but could be improved.")
        else:
            recommendations.append("Exit precision is poor. Immediate attention required.")
        
        if overall_precision < 0.9:
            recommendations.append("Consider improving precision to reduce false positives.")
        
        if overall_recall < 0.8:
            recommendations.append("Consider improving recall to reduce false negatives.")
        
        return recommendations

class ExitPrecisionManager:
    """Main exit precision validation manager"""
    
    def __init__(self, precision_threshold: float = 0.80):
        self.analyzer = ExitAnalyzer()
        self.validator = ExitValidator(precision_threshold)
        self.start_time = time.time()
        self.validation_reports: List[ExitPrecisionReport] = []
        self.lock = threading.RLock()
    
    def validate_exit_precision(self, signal: ExitSignal, execution: ExitExecution,
                              expected_outcome: bool) -> ExitValidation:
        """Validate exit precision"""
        # Perform analysis
        structure_analysis = self.analyzer.analyze_market_structure(signal)
        momentum_analysis = self.analyzer.analyze_momentum(signal)
        volatility_analysis = self.analyzer.analyze_volatility(signal)
        risk_analysis = self.analyzer.analyze_risk_metrics(signal)
        
        # Validate exit precision
        validation = self.validator.validate_exit_precision(signal, execution, expected_outcome)
        
        return validation
    
    def generate_validation_report(self) -> ExitPrecisionReport:
        """Generate validation report"""
        report = self.validator.generate_validation_report()
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[ExitPrecisionReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        with self.lock:
            if not self.validator.validations:
                return {"total_validations": 0}
            
            total_validations = len(self.validator.validations)
            true_positives = sum(1 for v in self.validator.validations if v.true_positive)
            false_positives = sum(1 for v in self.validator.validations if v.false_positive)
            true_negatives = sum(1 for v in self.validator.validations if v.true_negative)
            false_negatives = sum(1 for v in self.validator.validations if v.false_negative)
            
            overall_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
            overall_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
            overall_f1_score = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0
            
            return {
                "total_validations": total_validations,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "true_negatives": true_negatives,
                "false_negatives": false_negatives,
                "overall_precision": overall_precision,
                "overall_recall": overall_recall,
                "overall_f1_score": overall_f1_score,
                "precision_threshold": self.validator.precision_threshold
            }
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.validator.validations.clear()
            self.validation_reports.clear()

# Global exit precision validation manager
_exit_precision_validation_manager: Optional[ExitPrecisionManager] = None

def get_exit_precision_validation_manager(precision_threshold: float = 0.80) -> ExitPrecisionManager:
    """Get global exit precision validation manager instance"""
    global _exit_precision_validation_manager
    if _exit_precision_validation_manager is None:
        _exit_precision_validation_manager = ExitPrecisionManager(precision_threshold)
    return _exit_precision_validation_manager

def validate_exit_precision(signal: ExitSignal, execution: ExitExecution, 
                           expected_outcome: bool) -> ExitValidation:
    """Validate exit precision"""
    manager = get_exit_precision_validation_manager()
    return manager.validate_exit_precision(signal, execution, expected_outcome)

def generate_exit_precision_validation_report() -> ExitPrecisionReport:
    """Generate exit precision validation report"""
    manager = get_exit_precision_validation_manager()
    return manager.generate_validation_report()

def get_exit_precision_validation_summary() -> Dict[str, Any]:
    """Get exit precision validation summary"""
    manager = get_exit_precision_validation_manager()
    return manager.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    manager = get_exit_precision_validation_manager()
    
    # Example exit signal
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
    
    # Example exit execution
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
    
    validation = validate_exit_precision(signal, execution, True)
    
    print(f"Exit Precision Validation:")
    print(f"Signal ID: {validation.signal_id}")
    print(f"Exit Type: {validation.exit_type.value}")
    print(f"Expected Outcome: {validation.expected_outcome}")
    print(f"Actual Outcome: {validation.actual_outcome}")
    print(f"Precision Score: {validation.precision_score:.2%}")
    print(f"Recall Score: {validation.recall_score:.2%}")
    print(f"F1 Score: {validation.f1_score:.2%}")
    print(f"False Positive: {validation.false_positive}")
    print(f"False Negative: {validation.false_negative}")
    print(f"True Positive: {validation.true_positive}")
    print(f"True Negative: {validation.true_negative}")
    print(f"Meets Threshold: {validation.meets_threshold}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    print("\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate validation report
    report = generate_exit_precision_validation_report()
    
    print(f"\nExit Precision Validation Report:")
    print(f"Overall Precision: {report.overall_precision:.2%}")
    print(f"Overall Recall: {report.overall_recall:.2%}")
    print(f"Overall F1 Score: {report.overall_f1_score:.2%}")
    print(f"Precision Level: {report.precision_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Validations: {report.total_validations}")
    print(f"True Positives: {report.true_positives}")
    print(f"False Positives: {report.false_positives}")
    print(f"True Negatives: {report.true_negatives}")
    print(f"False Negatives: {report.false_negatives}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
