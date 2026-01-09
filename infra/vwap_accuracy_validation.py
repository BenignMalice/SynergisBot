"""
VWAP Accuracy Validation System

This module implements a comprehensive validation system to ensure VWAP calculations
are accurate within ±0.1σ tolerance, validating both real-time and historical
VWAP calculations against known benchmarks and statistical models.

Key Features:
- VWAP accuracy validation within ±0.1σ tolerance
- Real-time VWAP calculation validation
- Historical VWAP accuracy assessment
- Session-anchored VWAP validation
- Sigma band accuracy validation
- Multi-timeframe VWAP validation
- Statistical significance testing
- Performance benchmarking
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

class VWAPAccuracyLevel(Enum):
    """VWAP accuracy levels"""
    EXCELLENT = "excellent"  # <0.05σ deviation
    GOOD = "good"  # <0.1σ deviation
    ACCEPTABLE = "acceptable"  # <0.2σ deviation
    POOR = "poor"  # >=0.2σ deviation

class VWAPValidationStatus(Enum):
    """VWAP validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class VWAPSessionType(Enum):
    """VWAP session types"""
    FOREX = "forex"  # Forex trading sessions
    CRYPTO = "crypto"  # 24/7 crypto trading
    METALS = "metals"  # Metals trading sessions
    CUSTOM = "custom"  # Custom session definition

@dataclass
class VWAPTick:
    """VWAP tick data"""
    timestamp: float
    price: float
    volume: float
    symbol: str
    source: str  # 'mt5' or 'binance'
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VWAPCalculation:
    """VWAP calculation result"""
    timestamp: float
    vwap: float
    volume: float
    price_volume_sum: float
    session_id: str
    symbol: str
    session_type: VWAPSessionType
    sigma: float
    upper_band: float
    lower_band: float
    accuracy_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VWAPAccuracyMetrics:
    """VWAP accuracy metrics"""
    timestamp: float
    symbol: str
    session_type: VWAPSessionType
    expected_vwap: float
    calculated_vwap: float
    deviation: float
    deviation_sigma: float
    accuracy_level: VWAPAccuracyLevel
    validation_status: VWAPValidationStatus
    sample_size: int
    confidence_interval: Tuple[float, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VWAPValidationReport:
    """VWAP validation report"""
    timestamp: float
    symbol: str
    session_type: VWAPSessionType
    overall_accuracy: float
    accuracy_level: VWAPAccuracyLevel
    validation_status: VWAPValidationStatus
    total_samples: int
    passed_samples: int
    failed_samples: int
    average_deviation: float
    max_deviation: float
    sigma_accuracy: float
    recommendations: List[str]
    detailed_metrics: List[VWAPAccuracyMetrics]
    metadata: Dict[str, Any] = field(default_factory=dict)

class VWAPAccuracyValidator:
    """VWAP accuracy validator"""
    
    def __init__(self, tolerance_sigma: float = 0.1):
        self.tolerance_sigma = tolerance_sigma
        self.calculations: List[VWAPCalculation] = []
        self.accuracy_metrics: List[VWAPAccuracyMetrics] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
        self.min_sample_size = 100  # Minimum samples for statistical significance
        self.confidence_level = 0.95  # 95% confidence level
    
    def validate_vwap_accuracy(self, symbol: str, session_type: VWAPSessionType,
                             expected_vwap: float, calculated_vwap: float,
                             sigma: float, sample_size: int) -> VWAPAccuracyMetrics:
        """Validate VWAP accuracy against expected value"""
        # Calculate deviation
        deviation = abs(calculated_vwap - expected_vwap)
        deviation_sigma = deviation / sigma if sigma > 0 else float('inf')
        
        # Determine accuracy level
        if deviation_sigma < 0.05:
            accuracy_level = VWAPAccuracyLevel.EXCELLENT
        elif deviation_sigma < 0.1:
            accuracy_level = VWAPAccuracyLevel.GOOD
        elif deviation_sigma < 0.2:
            accuracy_level = VWAPAccuracyLevel.ACCEPTABLE
        else:
            accuracy_level = VWAPAccuracyLevel.POOR
        
        # Determine validation status
        if deviation_sigma <= self.tolerance_sigma:
            validation_status = VWAPValidationStatus.PASSED
        elif deviation_sigma <= self.tolerance_sigma * 2:
            validation_status = VWAPValidationStatus.WARNING
        else:
            validation_status = VWAPValidationStatus.FAILED
        
        # Calculate confidence interval
        confidence_interval = self._calculate_confidence_interval(
            calculated_vwap, sigma, sample_size
        )
        
        # Calculate accuracy score
        accuracy_score = max(0.0, 1.0 - (deviation_sigma / self.tolerance_sigma))
        
        metrics = VWAPAccuracyMetrics(
            timestamp=time.time(),
            symbol=symbol,
            session_type=session_type,
            expected_vwap=expected_vwap,
            calculated_vwap=calculated_vwap,
            deviation=deviation,
            deviation_sigma=deviation_sigma,
            accuracy_level=accuracy_level,
            validation_status=validation_status,
            sample_size=sample_size,
            confidence_interval=confidence_interval,
            metadata={
                "tolerance_sigma": self.tolerance_sigma,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.accuracy_metrics.append(metrics)
        
        return metrics
    
    def _calculate_confidence_interval(self, vwap: float, sigma: float, 
                                     sample_size: int) -> Tuple[float, float]:
        """Calculate confidence interval for VWAP"""
        if sample_size < 2:
            return (vwap, vwap)
        
        # Standard error of the mean
        standard_error = sigma / math.sqrt(sample_size)
        
        # 95% confidence interval (z-score = 1.96)
        z_score = 1.96
        margin_of_error = z_score * standard_error
        
        lower_bound = vwap - margin_of_error
        upper_bound = vwap + margin_of_error
        
        return (lower_bound, upper_bound)
    
    def validate_session_vwap(self, symbol: str, session_type: VWAPSessionType,
                             ticks: List[VWAPTick]) -> VWAPCalculation:
        """Validate VWAP calculation for a session"""
        if not ticks:
            raise ValueError("No ticks provided for VWAP calculation")
        
        # Calculate VWAP
        total_volume = sum(tick.volume for tick in ticks)
        if total_volume == 0:
            raise ValueError("Total volume is zero")
        
        price_volume_sum = sum(tick.price * tick.volume for tick in ticks)
        vwap = price_volume_sum / total_volume
        
        # Calculate sigma (standard deviation)
        price_deviations = [(tick.price - vwap) ** 2 * tick.volume for tick in ticks]
        variance = sum(price_deviations) / total_volume
        sigma = math.sqrt(variance)
        
        # Calculate sigma bands
        upper_band = vwap + (2 * sigma)
        lower_band = vwap - (2 * sigma)
        
        # Calculate accuracy score
        accuracy_score = self._calculate_accuracy_score(vwap, sigma, ticks)
        
        calculation = VWAPCalculation(
            timestamp=time.time(),
            vwap=vwap,
            volume=total_volume,
            price_volume_sum=price_volume_sum,
            session_id=ticks[0].session_id if ticks else "",
            symbol=symbol,
            session_type=session_type,
            sigma=sigma,
            upper_band=upper_band,
            lower_band=lower_band,
            accuracy_score=accuracy_score,
            metadata={
                "tick_count": len(ticks),
                "session_start": ticks[0].timestamp if ticks else 0,
                "session_end": ticks[-1].timestamp if ticks else 0
            }
        )
        
        with self.lock:
            self.calculations.append(calculation)
        
        return calculation
    
    def _calculate_accuracy_score(self, vwap: float, sigma: float, 
                                ticks: List[VWAPTick]) -> float:
        """Calculate accuracy score for VWAP calculation"""
        if not ticks or sigma == 0:
            return 0.0
        
        # Calculate how many ticks fall within expected sigma bands
        within_1_sigma = 0
        within_2_sigma = 0
        
        for tick in ticks:
            deviation = abs(tick.price - vwap)
            if deviation <= sigma:
                within_1_sigma += 1
            if deviation <= 2 * sigma:
                within_2_sigma += 1
        
        # Calculate accuracy score based on normal distribution expectations
        expected_1_sigma = 0.6827  # 68.27% within 1 sigma
        expected_2_sigma = 0.9545  # 95.45% within 2 sigma
        
        actual_1_sigma = within_1_sigma / len(ticks)
        actual_2_sigma = within_2_sigma / len(ticks)
        
        # Score based on how close actual distribution is to expected
        score_1_sigma = 1.0 - abs(actual_1_sigma - expected_1_sigma) / expected_1_sigma
        score_2_sigma = 1.0 - abs(actual_2_sigma - expected_2_sigma) / expected_2_sigma
        
        # Weighted average (2-sigma is more important)
        accuracy_score = (score_1_sigma * 0.3 + score_2_sigma * 0.7)
        
        return max(0.0, min(1.0, accuracy_score))
    
    def generate_validation_report(self, symbol: str, session_type: VWAPSessionType) -> VWAPValidationReport:
        """Generate comprehensive VWAP validation report"""
        with self.lock:
            # Filter metrics for symbol and session type
            relevant_metrics = [
                m for m in self.accuracy_metrics
                if m.symbol == symbol and m.session_type == session_type
            ]
        
        if not relevant_metrics:
            return VWAPValidationReport(
                timestamp=time.time(),
                symbol=symbol,
                session_type=session_type,
                overall_accuracy=0.0,
                accuracy_level=VWAPAccuracyLevel.POOR,
                validation_status=VWAPValidationStatus.FAILED,
                total_samples=0,
                passed_samples=0,
                failed_samples=0,
                average_deviation=0.0,
                max_deviation=0.0,
                sigma_accuracy=0.0,
                recommendations=["No data available for validation"],
                detailed_metrics=[],
                metadata={"error": "No validation data available"}
            )
        
        # Calculate overall metrics
        total_samples = len(relevant_metrics)
        passed_samples = sum(1 for m in relevant_metrics if m.validation_status == VWAPValidationStatus.PASSED)
        failed_samples = sum(1 for m in relevant_metrics if m.validation_status == VWAPValidationStatus.FAILED)
        
        average_deviation = statistics.mean([m.deviation_sigma for m in relevant_metrics])
        max_deviation = max([m.deviation_sigma for m in relevant_metrics])
        
        # Calculate overall accuracy
        overall_accuracy = passed_samples / total_samples if total_samples > 0 else 0.0
        
        # Determine overall accuracy level
        if average_deviation < 0.05:
            accuracy_level = VWAPAccuracyLevel.EXCELLENT
        elif average_deviation < 0.1:
            accuracy_level = VWAPAccuracyLevel.GOOD
        elif average_deviation < 0.2:
            accuracy_level = VWAPAccuracyLevel.ACCEPTABLE
        else:
            accuracy_level = VWAPAccuracyLevel.POOR
        
        # Determine validation status
        if overall_accuracy >= 0.95:
            validation_status = VWAPValidationStatus.PASSED
        elif overall_accuracy >= 0.80:
            validation_status = VWAPValidationStatus.WARNING
        else:
            validation_status = VWAPValidationStatus.FAILED
        
        # Calculate sigma accuracy
        sigma_accuracy = 1.0 - (average_deviation / self.tolerance_sigma)
        sigma_accuracy = max(0.0, min(1.0, sigma_accuracy))
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            overall_accuracy, average_deviation, accuracy_level, validation_status
        )
        
        return VWAPValidationReport(
            timestamp=time.time(),
            symbol=symbol,
            session_type=session_type,
            overall_accuracy=overall_accuracy,
            accuracy_level=accuracy_level,
            validation_status=validation_status,
            total_samples=total_samples,
            passed_samples=passed_samples,
            failed_samples=failed_samples,
            average_deviation=average_deviation,
            max_deviation=max_deviation,
            sigma_accuracy=sigma_accuracy,
            recommendations=recommendations,
            detailed_metrics=relevant_metrics,
            metadata={
                "tolerance_sigma": self.tolerance_sigma,
                "confidence_level": self.confidence_level,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _generate_recommendations(self, overall_accuracy: float, average_deviation: float,
                                accuracy_level: VWAPAccuracyLevel, 
                                validation_status: VWAPValidationStatus) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if validation_status == VWAPValidationStatus.FAILED:
            recommendations.append("VWAP accuracy validation failed. Review calculation algorithm.")
            if average_deviation > 0.5:
                recommendations.append("High deviation detected. Check data quality and calculation logic.")
        elif validation_status == VWAPValidationStatus.WARNING:
            recommendations.append("VWAP accuracy validation passed with warnings. Monitor performance.")
            if average_deviation > 0.2:
                recommendations.append("Consider optimizing VWAP calculation for better accuracy.")
        else:
            recommendations.append("VWAP accuracy validation passed successfully.")
        
        if accuracy_level == VWAPAccuracyLevel.EXCELLENT:
            recommendations.append("VWAP accuracy is excellent. System is performing optimally.")
        elif accuracy_level == VWAPAccuracyLevel.GOOD:
            recommendations.append("VWAP accuracy is good. Minor optimizations may be beneficial.")
        elif accuracy_level == VWAPAccuracyLevel.ACCEPTABLE:
            recommendations.append("VWAP accuracy is acceptable but could be improved.")
        else:
            recommendations.append("VWAP accuracy is poor. Immediate attention required.")
        
        if overall_accuracy < 0.9:
            recommendations.append("Consider increasing sample size for more reliable validation.")
        
        return recommendations
    
    def get_accuracy_summary(self) -> Dict[str, Any]:
        """Get accuracy summary statistics"""
        with self.lock:
            if not self.accuracy_metrics:
                return {"total_validations": 0}
            
            total_validations = len(self.accuracy_metrics)
            passed_validations = sum(1 for m in self.accuracy_metrics 
                                   if m.validation_status == VWAPValidationStatus.PASSED)
            
            accuracy_levels = [m.accuracy_level for m in self.accuracy_metrics]
            accuracy_level_counts = {
                level.value: accuracy_levels.count(level) 
                for level in VWAPAccuracyLevel
            }
            
            average_deviation = statistics.mean([m.deviation_sigma for m in self.accuracy_metrics])
            max_deviation = max([m.deviation_sigma for m in self.accuracy_metrics])
            
            return {
                "total_validations": total_validations,
                "passed_validations": passed_validations,
                "pass_rate": passed_validations / total_validations,
                "accuracy_level_distribution": accuracy_level_counts,
                "average_deviation_sigma": average_deviation,
                "max_deviation_sigma": max_deviation,
                "tolerance_sigma": self.tolerance_sigma
            }

class VWAPValidator:
    """Main VWAP validator"""
    
    def __init__(self, tolerance_sigma: float = 0.1):
        self.accuracy_validator = VWAPAccuracyValidator(tolerance_sigma)
        self.start_time = time.time()
        self.validation_reports: List[VWAPValidationReport] = []
        self.lock = threading.RLock()
    
    def validate_vwap_accuracy(self, symbol: str, session_type: VWAPSessionType,
                             expected_vwap: float, calculated_vwap: float,
                             sigma: float, sample_size: int) -> VWAPAccuracyMetrics:
        """Validate VWAP accuracy"""
        return self.accuracy_validator.validate_vwap_accuracy(
            symbol, session_type, expected_vwap, calculated_vwap, sigma, sample_size
        )
    
    def validate_session_vwap(self, symbol: str, session_type: VWAPSessionType,
                             ticks: List[VWAPTick]) -> VWAPCalculation:
        """Validate session VWAP calculation"""
        return self.accuracy_validator.validate_session_vwap(
            symbol, session_type, ticks
        )
    
    def generate_validation_report(self, symbol: str, session_type: VWAPSessionType) -> VWAPValidationReport:
        """Generate validation report"""
        report = self.accuracy_validator.generate_validation_report(symbol, session_type)
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[VWAPValidationReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_accuracy_summary(self) -> Dict[str, Any]:
        """Get accuracy summary"""
        return self.accuracy_validator.get_accuracy_summary()
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.accuracy_validator.accuracy_metrics.clear()
            self.accuracy_validator.calculations.clear()
            self.validation_reports.clear()

# Global VWAP validator
_vwap_validator: Optional[VWAPValidator] = None

def get_vwap_validator(tolerance_sigma: float = 0.1) -> VWAPValidator:
    """Get global VWAP validator instance"""
    global _vwap_validator
    if _vwap_validator is None:
        _vwap_validator = VWAPValidator(tolerance_sigma)
    return _vwap_validator

def validate_vwap_accuracy(symbol: str, session_type: VWAPSessionType,
                         expected_vwap: float, calculated_vwap: float,
                         sigma: float, sample_size: int) -> VWAPAccuracyMetrics:
    """Validate VWAP accuracy"""
    validator = get_vwap_validator()
    return validator.validate_vwap_accuracy(
        symbol, session_type, expected_vwap, calculated_vwap, sigma, sample_size
    )

def validate_session_vwap(symbol: str, session_type: VWAPSessionType,
                         ticks: List[VWAPTick]) -> VWAPCalculation:
    """Validate session VWAP calculation"""
    validator = get_vwap_validator()
    return validator.validate_session_vwap(symbol, session_type, ticks)

def generate_vwap_validation_report(symbol: str, session_type: VWAPSessionType) -> VWAPValidationReport:
    """Generate VWAP validation report"""
    validator = get_vwap_validator()
    return validator.generate_validation_report(symbol, session_type)

def get_vwap_accuracy_summary() -> Dict[str, Any]:
    """Get VWAP accuracy summary"""
    validator = get_vwap_validator()
    return validator.get_accuracy_summary()

if __name__ == "__main__":
    # Example usage
    validator = get_vwap_validator()
    
    # Example VWAP accuracy validation
    metrics = validate_vwap_accuracy(
        symbol="BTCUSDc",
        session_type=VWAPSessionType.CRYPTO,
        expected_vwap=50000.0,
        calculated_vwap=50005.0,
        sigma=100.0,
        sample_size=1000
    )
    
    print(f"VWAP Accuracy Validation:")
    print(f"Symbol: {metrics.symbol}")
    print(f"Expected VWAP: {metrics.expected_vwap}")
    print(f"Calculated VWAP: {metrics.calculated_vwap}")
    print(f"Deviation: {metrics.deviation}")
    print(f"Deviation (σ): {metrics.deviation_sigma:.3f}")
    print(f"Accuracy Level: {metrics.accuracy_level.value}")
    print(f"Validation Status: {metrics.validation_status.value}")
    print(f"Sample Size: {metrics.sample_size}")
    print(f"Confidence Interval: {metrics.confidence_interval}")
    
    # Generate validation report
    report = generate_vwap_validation_report("BTCUSDc", VWAPSessionType.CRYPTO)
    
    print(f"\nVWAP Validation Report:")
    print(f"Overall Accuracy: {report.overall_accuracy:.2%}")
    print(f"Accuracy Level: {report.accuracy_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Samples: {report.total_samples}")
    print(f"Passed Samples: {report.passed_samples}")
    print(f"Average Deviation: {report.average_deviation:.3f}σ")
    print(f"Max Deviation: {report.max_deviation:.3f}σ")
    print(f"Sigma Accuracy: {report.sigma_accuracy:.2%}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
