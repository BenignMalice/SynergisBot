"""
False Signal Reduction Validation System

This module implements a comprehensive validation system to ensure false signal
reduction achieves >80% effectiveness, validating signal quality, noise reduction,
and trading signal accuracy across different market conditions and timeframes.

Key Features:
- False signal reduction validation >80% effectiveness
- Signal quality assessment and noise reduction validation
- Trading signal accuracy validation across market conditions
- Signal-to-noise ratio improvement measurement
- False positive/negative reduction analysis
- Market condition-specific signal validation
- Timeframe-specific signal quality assessment
- Advanced statistical analysis and validation
"""

import time
import math
import statistics
import numpy as np
import threading
import sqlite3
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import sys
import logging

logger = logging.getLogger(__name__)

class SignalQualityLevel(Enum):
    """Signal quality levels"""
    EXCELLENT = "excellent"  # >95% quality
    GOOD = "good"  # >90% quality
    ACCEPTABLE = "acceptable"  # >80% quality
    POOR = "poor"  # <=80% quality

class FalseSignalReductionStatus(Enum):
    """False signal reduction status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class SignalType(Enum):
    """Signal types"""
    BUY_SIGNAL = "buy_signal"  # Buy trading signal
    SELL_SIGNAL = "sell_signal"  # Sell trading signal
    HOLD_SIGNAL = "hold_signal"  # Hold/no action signal
    EXIT_SIGNAL = "exit_signal"  # Exit position signal

class MarketCondition(Enum):
    """Market conditions"""
    TRENDING = "trending"  # Trending market
    RANGING = "ranging"  # Ranging/sideways market
    VOLATILE = "volatile"  # High volatility market
    CALM = "calm"  # Low volatility market

class Timeframe(Enum):
    """Timeframes"""
    M1 = "M1"  # 1 minute
    M5 = "M5"  # 5 minutes
    M15 = "M15"  # 15 minutes
    M30 = "M30"  # 30 minutes
    H1 = "H1"  # 1 hour
    H4 = "H4"  # 4 hours

@dataclass
class TradingSignal:
    """Trading signal data"""
    timestamp: float
    signal_type: SignalType
    symbol: str
    timeframe: Timeframe
    price: float
    confidence: float
    market_condition: MarketCondition
    signal_strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SignalValidation:
    """Signal validation result"""
    timestamp: float
    symbol: str
    timeframe: Timeframe
    original_signal: TradingSignal
    filtered_signal: Optional[TradingSignal]
    is_valid: bool
    false_signal_reduction: float
    signal_quality_score: float
    noise_reduction: float
    signal_to_noise_ratio: float
    false_positive_reduction: float
    false_negative_reduction: float
    validation_status: FalseSignalReductionStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FalseSignalReductionReport:
    """False signal reduction validation report"""
    timestamp: float
    symbol: str
    timeframe: Timeframe
    overall_reduction: float
    signal_quality_improvement: float
    noise_reduction: float
    signal_to_noise_improvement: float
    false_positive_reduction: float
    false_negative_reduction: float
    quality_level: SignalQualityLevel
    validation_status: FalseSignalReductionStatus
    total_signals: int
    valid_signals: int
    false_signals_filtered: int
    signal_quality_scores: List[float]
    market_condition_analysis: Dict[str, float]
    timeframe_analysis: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[SignalValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class FalseSignalReducer:
    """False signal reducer"""
    
    def __init__(self, reduction_threshold: float = 0.80):
        self.reduction_threshold = reduction_threshold
        self.validations: List[SignalValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
        self.min_sample_size = 100  # Minimum samples for statistical significance
        self.confidence_level = 0.95  # 95% confidence level
    
    def validate_signal_reduction(self, symbol: str, timeframe: Timeframe,
                                original_signal: TradingSignal,
                                filtered_signal: Optional[TradingSignal]) -> SignalValidation:
        """Validate false signal reduction effectiveness"""
        # Calculate false signal reduction
        false_signal_reduction = self._calculate_false_signal_reduction(
            original_signal, filtered_signal
        )
        
        # Calculate signal quality score
        signal_quality_score = self._calculate_signal_quality_score(
            original_signal, filtered_signal
        )
        
        # Calculate noise reduction
        noise_reduction = self._calculate_noise_reduction(
            original_signal, filtered_signal
        )
        
        # Calculate signal-to-noise ratio
        signal_to_noise_ratio = self._calculate_signal_to_noise_ratio(
            original_signal, filtered_signal
        )
        
        # Calculate false positive/negative reduction
        false_positive_reduction = self._calculate_false_positive_reduction(
            original_signal, filtered_signal
        )
        false_negative_reduction = self._calculate_false_negative_reduction(
            original_signal, filtered_signal
        )
        
        # Determine if signal is valid
        is_valid = self._is_signal_valid(original_signal, filtered_signal)
        
        # Determine validation status
        validation_status = self._determine_validation_status(false_signal_reduction)
        
        validation = SignalValidation(
            timestamp=time.time(),
            symbol=symbol,
            timeframe=timeframe,
            original_signal=original_signal,
            filtered_signal=filtered_signal,
            is_valid=is_valid,
            false_signal_reduction=false_signal_reduction,
            signal_quality_score=signal_quality_score,
            noise_reduction=noise_reduction,
            signal_to_noise_ratio=signal_to_noise_ratio,
            false_positive_reduction=false_positive_reduction,
            false_negative_reduction=false_negative_reduction,
            validation_status=validation_status,
            metadata={
                "reduction_threshold": self.reduction_threshold,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _calculate_false_signal_reduction(self, original_signal: TradingSignal,
                                        filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate false signal reduction percentage"""
        if filtered_signal is None:
            # Signal was filtered out - check if it was a false signal
            if self._is_false_signal(original_signal):
                return 1.0  # 100% reduction of false signal
            else:
                return 0.0  # 0% reduction (valid signal was filtered)
        
        # Signal was not filtered - check improvement
        if self._is_false_signal(original_signal) and not self._is_false_signal(filtered_signal):
            return 1.0  # 100% reduction of false signal
        elif not self._is_false_signal(original_signal) and not self._is_false_signal(filtered_signal):
            return 0.0  # No false signal to reduce
        else:
            # Both are false signals or both are valid
            return 0.5  # Partial reduction
    
    def _calculate_signal_quality_score(self, original_signal: TradingSignal,
                                       filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate signal quality score"""
        if filtered_signal is None:
            # Signal was filtered out
            if self._is_false_signal(original_signal):
                return 1.0  # High quality (false signal removed)
            else:
                return 0.0  # Low quality (valid signal removed)
        
        # Compare signal quality
        original_quality = self._assess_signal_quality(original_signal)
        filtered_quality = self._assess_signal_quality(filtered_signal)
        
        return max(0.0, min(1.0, filtered_quality - original_quality + 0.5))
    
    def _calculate_noise_reduction(self, original_signal: TradingSignal,
                                 filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate noise reduction percentage"""
        if filtered_signal is None:
            # Signal was filtered out
            return 1.0 if self._is_noisy_signal(original_signal) else 0.0
        
        # Compare noise levels
        original_noise = self._assess_signal_noise(original_signal)
        filtered_noise = self._assess_signal_noise(filtered_signal)
        
        if original_noise == 0:
            return 0.0  # No noise to reduce
        
        return max(0.0, min(1.0, (original_noise - filtered_noise) / original_noise))
    
    def _calculate_signal_to_noise_ratio(self, original_signal: TradingSignal,
                                       filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate signal-to-noise ratio improvement"""
        if filtered_signal is None:
            return 0.0  # No signal to measure
        
        original_snr = self._calculate_snr(original_signal)
        filtered_snr = self._calculate_snr(filtered_signal)
        
        if original_snr == 0:
            return 0.0
        
        return max(0.0, (filtered_snr - original_snr) / original_snr)
    
    def _calculate_false_positive_reduction(self, original_signal: TradingSignal,
                                          filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate false positive reduction"""
        if self._is_false_positive(original_signal):
            if filtered_signal is None:
                return 1.0  # False positive eliminated
            elif not self._is_false_positive(filtered_signal):
                return 1.0  # False positive corrected
            else:
                return 0.0  # False positive not addressed
        else:
            return 0.0  # No false positive to reduce
    
    def _calculate_false_negative_reduction(self, original_signal: TradingSignal,
                                          filtered_signal: Optional[TradingSignal]) -> float:
        """Calculate false negative reduction"""
        if self._is_false_negative(original_signal):
            if filtered_signal is not None and not self._is_false_negative(filtered_signal):
                return 1.0  # False negative corrected
            else:
                return 0.0  # False negative not addressed
        else:
            return 0.0  # No false negative to reduce
    
    def _is_signal_valid(self, original_signal: TradingSignal,
                        filtered_signal: Optional[TradingSignal]) -> bool:
        """Determine if signal validation is valid"""
        if filtered_signal is None:
            # Signal was filtered out
            return self._is_false_signal(original_signal)
        
        # Signal was not filtered - check if it's valid
        return not self._is_false_signal(filtered_signal)
    
    def _is_false_signal(self, signal: TradingSignal) -> bool:
        """Determine if signal is false"""
        if signal is None:
            return False  # None signals are not considered false signals
        
        # Check confidence threshold
        if signal.confidence < 0.7:
            return True
        
        # Check signal strength
        if signal.signal_strength < 0.5:
            return True
        
        # Check market condition appropriateness
        if not self._is_signal_appropriate_for_market(signal):
            return True
        
        return False
    
    def _is_noisy_signal(self, signal: TradingSignal) -> bool:
        """Determine if signal is noisy"""
        if signal is None:
            return False  # None signals are not considered noisy
        
        # Check for high noise indicators
        if signal.confidence < 0.8:
            return True
        
        if signal.signal_strength < 0.7:
            return True
        
        return False
    
    def _is_false_positive(self, signal: TradingSignal) -> bool:
        """Determine if signal is a false positive"""
        if signal is None:
            return False  # None signals are not false positives
        
        return (signal.signal_type in [SignalType.BUY_SIGNAL, SignalType.SELL_SIGNAL] and
                self._is_false_signal(signal))
    
    def _is_false_negative(self, signal: TradingSignal) -> bool:
        """Determine if signal is a false negative"""
        if signal is None:
            return False  # None signals are not false negatives
        
        return (signal.signal_type == SignalType.HOLD_SIGNAL and
                not self._is_false_signal(signal))
    
    def _assess_signal_quality(self, signal: TradingSignal) -> float:
        """Assess signal quality score"""
        if signal is None:
            return 0.0  # None signals have no quality
        
        quality_score = 0.0
        
        # Confidence factor
        quality_score += signal.confidence * 0.4
        
        # Signal strength factor
        quality_score += signal.signal_strength * 0.3
        
        # Market condition appropriateness
        if self._is_signal_appropriate_for_market(signal):
            quality_score += 0.3
        
        return max(0.0, min(1.0, quality_score))
    
    def _assess_signal_noise(self, signal: TradingSignal) -> float:
        """Assess signal noise level"""
        if signal is None:
            return 0.0  # None signals have no noise
        
        noise_level = 0.0
        
        # Low confidence indicates noise
        noise_level += (1.0 - signal.confidence) * 0.5
        
        # Low signal strength indicates noise
        noise_level += (1.0 - signal.signal_strength) * 0.3
        
        # Market condition mismatch indicates noise
        if not self._is_signal_appropriate_for_market(signal):
            noise_level += 0.2
        
        return max(0.0, min(1.0, noise_level))
    
    def _calculate_snr(self, signal: TradingSignal) -> float:
        """Calculate signal-to-noise ratio"""
        if signal is None:
            return 0.0  # None signals have no SNR
        
        signal_power = signal.confidence * signal.signal_strength
        noise_power = self._assess_signal_noise(signal)
        
        if noise_power == 0:
            return float('inf') if signal_power > 0 else 0.0
        
        return signal_power / noise_power
    
    def _is_signal_appropriate_for_market(self, signal: TradingSignal) -> bool:
        """Determine if signal is appropriate for market condition"""
        if signal is None:
            return False  # None signals are not appropriate for any market
        
        if signal.market_condition == MarketCondition.TRENDING:
            return signal.signal_type in [SignalType.BUY_SIGNAL, SignalType.SELL_SIGNAL]
        elif signal.market_condition == MarketCondition.RANGING:
            return signal.signal_type == SignalType.HOLD_SIGNAL
        elif signal.market_condition == MarketCondition.VOLATILE:
            return signal.signal_type in [SignalType.BUY_SIGNAL, SignalType.SELL_SIGNAL, SignalType.EXIT_SIGNAL]
        else:  # CALM
            return signal.signal_type == SignalType.HOLD_SIGNAL
    
    def _determine_validation_status(self, reduction: float) -> FalseSignalReductionStatus:
        """Determine validation status based on reduction percentage"""
        if reduction >= self.reduction_threshold:
            return FalseSignalReductionStatus.PASSED
        elif reduction >= self.reduction_threshold * 0.8:
            return FalseSignalReductionStatus.WARNING
        else:
            return FalseSignalReductionStatus.FAILED
    
    def generate_validation_report(self, symbol: str, timeframe: Timeframe) -> FalseSignalReductionReport:
        """Generate comprehensive false signal reduction validation report"""
        with self.lock:
            # Filter validations for symbol and timeframe
            relevant_validations = [
                v for v in self.validations 
                if v.symbol == symbol and v.timeframe == timeframe
            ]
        
        if not relevant_validations:
            return FalseSignalReductionReport(
                timestamp=time.time(),
                symbol=symbol,
                timeframe=timeframe,
                overall_reduction=0.0,
                signal_quality_improvement=0.0,
                noise_reduction=0.0,
                signal_to_noise_improvement=0.0,
                false_positive_reduction=0.0,
                false_negative_reduction=0.0,
                quality_level=SignalQualityLevel.POOR,
                validation_status=FalseSignalReductionStatus.FAILED,
                total_signals=0,
                valid_signals=0,
                false_signals_filtered=0,
                signal_quality_scores=[],
                market_condition_analysis={},
                timeframe_analysis={},
                recommendations=["No validation data available"],
                detailed_validations=[],
                metadata={"error": "No validation data available"}
            )
        
        # Calculate overall metrics
        total_signals = len(relevant_validations)
        valid_signals = sum(1 for v in relevant_validations if v.is_valid)
        false_signals_filtered = sum(1 for v in relevant_validations 
                                   if v.filtered_signal is None and v.original_signal is not None)
        
        # Calculate average metrics
        overall_reduction = sum(v.false_signal_reduction for v in relevant_validations) / total_signals
        signal_quality_improvement = sum(v.signal_quality_score for v in relevant_validations) / total_signals
        noise_reduction = sum(v.noise_reduction for v in relevant_validations) / total_signals
        signal_to_noise_improvement = sum(v.signal_to_noise_ratio for v in relevant_validations) / total_signals
        false_positive_reduction = sum(v.false_positive_reduction for v in relevant_validations) / total_signals
        false_negative_reduction = sum(v.false_negative_reduction for v in relevant_validations) / total_signals
        
        # Determine quality level
        if overall_reduction >= 0.95:
            quality_level = SignalQualityLevel.EXCELLENT
        elif overall_reduction >= 0.90:
            quality_level = SignalQualityLevel.GOOD
        elif overall_reduction >= 0.80:
            quality_level = SignalQualityLevel.ACCEPTABLE
        else:
            quality_level = SignalQualityLevel.POOR
        
        # Determine validation status
        if overall_reduction >= self.reduction_threshold:
            validation_status = FalseSignalReductionStatus.PASSED
        elif overall_reduction >= self.reduction_threshold * 0.8:
            validation_status = FalseSignalReductionStatus.WARNING
        else:
            validation_status = FalseSignalReductionStatus.FAILED
        
        # Calculate signal quality scores
        signal_quality_scores = [v.signal_quality_score for v in relevant_validations]
        
        # Market condition analysis
        market_condition_analysis = self._analyze_market_conditions(relevant_validations)
        
        # Timeframe analysis
        timeframe_analysis = self._analyze_timeframes(relevant_validations)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            overall_reduction, signal_quality_improvement, noise_reduction,
            quality_level, validation_status
        )
        
        return FalseSignalReductionReport(
            timestamp=time.time(),
            symbol=symbol,
            timeframe=timeframe,
            overall_reduction=overall_reduction,
            signal_quality_improvement=signal_quality_improvement,
            noise_reduction=noise_reduction,
            signal_to_noise_improvement=signal_to_noise_improvement,
            false_positive_reduction=false_positive_reduction,
            false_negative_reduction=false_negative_reduction,
            quality_level=quality_level,
            validation_status=validation_status,
            total_signals=total_signals,
            valid_signals=valid_signals,
            false_signals_filtered=false_signals_filtered,
            signal_quality_scores=signal_quality_scores,
            market_condition_analysis=market_condition_analysis,
            timeframe_analysis=timeframe_analysis,
            recommendations=recommendations,
            detailed_validations=relevant_validations,
            metadata={
                "reduction_threshold": self.reduction_threshold,
                "confidence_level": self.confidence_level,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _analyze_market_conditions(self, validations: List[SignalValidation]) -> Dict[str, float]:
        """Analyze signal reduction by market condition"""
        condition_analysis = {}
        
        for condition in MarketCondition:
            condition_validations = [
                v for v in validations 
                if v.original_signal and v.original_signal.market_condition == condition
            ]
            
            if condition_validations:
                avg_reduction = sum(v.false_signal_reduction for v in condition_validations) / len(condition_validations)
                condition_analysis[condition.value] = avg_reduction
            else:
                condition_analysis[condition.value] = 0.0
        
        return condition_analysis
    
    def _analyze_timeframes(self, validations: List[SignalValidation]) -> Dict[str, float]:
        """Analyze signal reduction by timeframe"""
        timeframe_analysis = {}
        
        for timeframe in Timeframe:
            tf_validations = [
                v for v in validations 
                if v.timeframe == timeframe
            ]
            
            if tf_validations:
                avg_reduction = sum(v.false_signal_reduction for v in tf_validations) / len(tf_validations)
                timeframe_analysis[timeframe.value] = avg_reduction
            else:
                timeframe_analysis[timeframe.value] = 0.0
        
        return timeframe_analysis
    
    def _generate_recommendations(self, overall_reduction: float, signal_quality_improvement: float,
                               noise_reduction: float, quality_level: SignalQualityLevel,
                               validation_status: FalseSignalReductionStatus) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if validation_status == FalseSignalReductionStatus.FAILED:
            recommendations.append("False signal reduction validation failed. Review filtering algorithm.")
            if overall_reduction < 0.5:
                recommendations.append("Very low reduction detected. Consider complete algorithm redesign.")
        elif validation_status == FalseSignalReductionStatus.WARNING:
            recommendations.append("False signal reduction validation passed with warnings. Monitor performance.")
            if overall_reduction < 0.85:
                recommendations.append("Consider optimizing filtering algorithm for better reduction.")
        else:
            recommendations.append("False signal reduction validation passed successfully.")
        
        if quality_level == SignalQualityLevel.EXCELLENT:
            recommendations.append("False signal reduction quality is excellent. System is performing optimally.")
        elif quality_level == SignalQualityLevel.GOOD:
            recommendations.append("False signal reduction quality is good. Minor optimizations may be beneficial.")
        elif quality_level == SignalQualityLevel.ACCEPTABLE:
            recommendations.append("False signal reduction quality is acceptable but could be improved.")
        else:
            recommendations.append("False signal reduction quality is poor. Immediate attention required.")
        
        if signal_quality_improvement < 0.8:
            recommendations.append("Low signal quality improvement detected. Consider enhancing signal processing.")
        
        if noise_reduction < 0.8:
            recommendations.append("Low noise reduction detected. Consider improving noise filtering.")
        
        return recommendations
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary statistics"""
        with self.lock:
            if not self.validations:
                return {"total_validations": 0}
            
            total_validations = len(self.validations)
            valid_signals = sum(1 for v in self.validations if v.is_valid)
            false_signals_filtered = sum(1 for v in self.validations 
                                       if v.filtered_signal is None and v.original_signal is not None)
            
            overall_reduction = sum(v.false_signal_reduction for v in self.validations) / total_validations
            signal_quality_improvement = sum(v.signal_quality_score for v in self.validations) / total_validations
            noise_reduction = sum(v.noise_reduction for v in self.validations) / total_validations
            
            return {
                "total_validations": total_validations,
                "valid_signals": valid_signals,
                "false_signals_filtered": false_signals_filtered,
                "overall_reduction": overall_reduction,
                "signal_quality_improvement": signal_quality_improvement,
                "noise_reduction": noise_reduction,
                "reduction_threshold": self.reduction_threshold
            }

class FalseSignalReductionValidator:
    """Main false signal reduction validator"""
    
    def __init__(self, reduction_threshold: float = 0.80):
        self.reducer = FalseSignalReducer(reduction_threshold)
        self.start_time = time.time()
        self.validation_reports: List[FalseSignalReductionReport] = []
        self.lock = threading.RLock()
    
    def validate_signal_reduction(self, symbol: str, timeframe: Timeframe,
                                 original_signal: TradingSignal,
                                 filtered_signal: Optional[TradingSignal]) -> SignalValidation:
        """Validate false signal reduction effectiveness"""
        return self.reducer.validate_signal_reduction(
            symbol, timeframe, original_signal, filtered_signal
        )
    
    def generate_validation_report(self, symbol: str, timeframe: Timeframe) -> FalseSignalReductionReport:
        """Generate validation report"""
        report = self.reducer.generate_validation_report(symbol, timeframe)
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[FalseSignalReductionReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        return self.reducer.get_validation_summary()
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.reducer.validations.clear()
            self.validation_reports.clear()

# Global false signal reduction validator
_false_signal_validator: Optional[FalseSignalReductionValidator] = None

def get_false_signal_validator(reduction_threshold: float = 0.80) -> FalseSignalReductionValidator:
    """Get global false signal reduction validator instance"""
    global _false_signal_validator
    if _false_signal_validator is None:
        _false_signal_validator = FalseSignalReductionValidator(reduction_threshold)
    return _false_signal_validator

def validate_signal_reduction(symbol: str, timeframe: Timeframe,
                            original_signal: TradingSignal,
                            filtered_signal: Optional[TradingSignal]) -> SignalValidation:
    """Validate false signal reduction effectiveness"""
    validator = get_false_signal_validator()
    return validator.validate_signal_reduction(symbol, timeframe, original_signal, filtered_signal)

def generate_false_signal_validation_report(symbol: str, timeframe: Timeframe) -> FalseSignalReductionReport:
    """Generate false signal reduction validation report"""
    validator = get_false_signal_validator()
    return validator.generate_validation_report(symbol, timeframe)

def get_false_signal_validation_summary() -> Dict[str, Any]:
    """Get false signal reduction validation summary"""
    validator = get_false_signal_validator()
    return validator.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    validator = get_false_signal_validator()
    
    # Example signal validation
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
    
    print(f"False Signal Reduction Validation:")
    print(f"Symbol: {validation.symbol}")
    print(f"Timeframe: {validation.timeframe.value}")
    print(f"Is Valid: {validation.is_valid}")
    print(f"False Signal Reduction: {validation.false_signal_reduction:.2%}")
    print(f"Signal Quality Score: {validation.signal_quality_score:.2%}")
    print(f"Noise Reduction: {validation.noise_reduction:.2%}")
    print(f"Signal-to-Noise Ratio: {validation.signal_to_noise_ratio:.2f}")
    print(f"False Positive Reduction: {validation.false_positive_reduction:.2%}")
    print(f"False Negative Reduction: {validation.false_negative_reduction:.2%}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    # Generate validation report
    report = generate_false_signal_validation_report("BTCUSDc", Timeframe.M5)
    
    print(f"\nFalse Signal Reduction Validation Report:")
    print(f"Overall Reduction: {report.overall_reduction:.2%}")
    print(f"Signal Quality Improvement: {report.signal_quality_improvement:.2%}")
    print(f"Noise Reduction: {report.noise_reduction:.2%}")
    print(f"Signal-to-Noise Improvement: {report.signal_to_noise_improvement:.2%}")
    print(f"False Positive Reduction: {report.false_positive_reduction:.2%}")
    print(f"False Negative Reduction: {report.false_negative_reduction:.2%}")
    print(f"Quality Level: {report.quality_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Signals: {report.total_signals}")
    print(f"Valid Signals: {report.valid_signals}")
    print(f"False Signals Filtered: {report.false_signals_filtered}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
