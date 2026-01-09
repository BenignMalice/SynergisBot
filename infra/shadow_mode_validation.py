"""
Shadow Mode Validation System

This module implements a comprehensive validation system to ensure the shadow mode
system is ready for production use and can effectively compare DTMS exits with
Intelligent Exits.

Key Features:
- Shadow mode readiness validation
- DTMS vs Intelligent Exits comparison
- Performance metrics validation
- Decision trace validation
- Shadow mode lifecycle management
- A/B testing framework validation
- Statistical significance testing
- Rollback mechanism validation
"""

import time
import json
import logging
import threading
import statistics
import numpy as np
import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import sys
import scipy.stats

logger = logging.getLogger(__name__)

class ShadowModeReadiness(Enum):
    """Shadow mode readiness levels"""
    READY = "ready"  # Ready for production
    PREPARING = "preparing"  # In preparation phase
    TESTING = "testing"  # In testing phase
    NOT_READY = "not_ready"  # Not ready for production

class ComparisonResult(Enum):
    """Comparison result types"""
    DTMS_BETTER = "dtms_better"  # DTMS performs better
    INTELLIGENT_BETTER = "intelligent_better"  # Intelligent Exits perform better
    EQUIVALENT = "equivalent"  # Performance is equivalent
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data for comparison

class ValidationStatus(Enum):
    """Validation status levels"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

@dataclass
class ShadowModeMetrics:
    """Shadow mode performance metrics"""
    timestamp: float
    dtms_trades: int
    intelligent_trades: int
    dtms_win_rate: float
    intelligent_win_rate: float
    dtms_avg_rr: float
    intelligent_avg_rr: float
    dtms_max_drawdown: float
    intelligent_max_drawdown: float
    dtms_latency_ms: float
    intelligent_latency_ms: float
    confidence_delta: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComparisonReport:
    """Shadow mode comparison report"""
    comparison_result: ComparisonResult
    statistical_significance: float
    confidence_level: float
    sample_size: int
    dtms_metrics: Dict[str, Any]
    intelligent_metrics: Dict[str, Any]
    performance_delta: Dict[str, float]
    recommendations: List[str]
    validation_status: ValidationStatus

@dataclass
class ShadowModeValidation:
    """Shadow mode validation result"""
    timestamp: float
    readiness_level: ShadowModeReadiness
    validation_status: ValidationStatus
    readiness_score: float
    comparison_report: Optional[ComparisonReport]
    recommendations: List[str]
    validation_details: Dict[str, Any]

class ShadowModeReadinessValidator:
    """Shadow mode readiness validator"""
    
    def __init__(self):
        self.metrics: List[ShadowModeMetrics] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
        self.min_sample_size = 100  # Minimum trades for statistical significance
        self.min_confidence_level = 0.95  # Minimum confidence level
        self.min_performance_delta = 0.05  # Minimum performance delta (5%)
    
    def validate_readiness(self) -> ShadowModeValidation:
        """Validate shadow mode readiness"""
        with self.lock:
            # Check if we have enough data
            if len(self.metrics) < self.min_sample_size:
                return ShadowModeValidation(
                    timestamp=time.time(),
                    readiness_level=ShadowModeReadiness.NOT_READY,
                    validation_status=ValidationStatus.FAILED,
                    readiness_score=0.0,
                    comparison_report=None,
                    recommendations=["Insufficient data for shadow mode validation. Need at least 100 trades."],
                    validation_details={"sample_size": len(self.metrics), "required": self.min_sample_size}
                )
            
            # Calculate readiness score
            readiness_score = self._calculate_readiness_score()
            
            # Determine readiness level
            if readiness_score >= 0.9:
                readiness_level = ShadowModeReadiness.READY
                validation_status = ValidationStatus.PASSED
            elif readiness_score >= 0.7:
                readiness_level = ShadowModeReadiness.PREPARING
                validation_status = ValidationStatus.WARNING
            elif readiness_score >= 0.5:
                readiness_level = ShadowModeReadiness.TESTING
                validation_status = ValidationStatus.WARNING
            else:
                readiness_level = ShadowModeReadiness.NOT_READY
                validation_status = ValidationStatus.FAILED
            
            # Generate comparison report if ready
            comparison_report = None
            if readiness_level == ShadowModeReadiness.READY:
                comparison_report = self._generate_comparison_report()
            
            # Generate recommendations
            recommendations = self._generate_recommendations(readiness_score, comparison_report)
            
            # Validation details
            validation_details = {
                "sample_size": len(self.metrics),
                "readiness_score": readiness_score,
                "dtms_trades": sum(m.dtms_trades for m in self.metrics),
                "intelligent_trades": sum(m.intelligent_trades for m in self.metrics),
                "avg_dtms_win_rate": statistics.mean([m.dtms_win_rate for m in self.metrics]),
                "avg_intelligent_win_rate": statistics.mean([m.intelligent_win_rate for m in self.metrics])
            }
            
            return ShadowModeValidation(
                timestamp=time.time(),
                readiness_level=readiness_level,
                validation_status=validation_status,
                readiness_score=readiness_score,
                comparison_report=comparison_report,
                recommendations=recommendations,
                validation_details=validation_details
            )
    
    def _calculate_readiness_score(self) -> float:
        """Calculate shadow mode readiness score (0-1)"""
        if not self.metrics:
            return 0.0
        
        # Calculate various readiness factors
        sample_size_score = min(1.0, len(self.metrics) / self.min_sample_size)
        
        # Data quality score
        data_quality_score = self._calculate_data_quality_score()
        
        # Performance stability score
        stability_score = self._calculate_stability_score()
        
        # Comparison readiness score
        comparison_score = self._calculate_comparison_readiness_score()
        
        # Weighted average
        readiness_score = (
            sample_size_score * 0.3 +
            data_quality_score * 0.3 +
            stability_score * 0.2 +
            comparison_score * 0.2
        )
        
        return readiness_score
    
    def _calculate_data_quality_score(self) -> float:
        """Calculate data quality score (0-1)"""
        if not self.metrics:
            return 0.0
        
        # Check for missing or invalid data
        valid_metrics = 0
        for metric in self.metrics:
            if (metric.dtms_trades > 0 and metric.intelligent_trades > 0 and
                0 <= metric.dtms_win_rate <= 1 and 0 <= metric.intelligent_win_rate <= 1):
                valid_metrics += 1
        
        return valid_metrics / len(self.metrics)
    
    def _calculate_stability_score(self) -> float:
        """Calculate performance stability score (0-1)"""
        if len(self.metrics) < 2:
            return 0.0
        
        # Calculate coefficient of variation for win rates
        dtms_win_rates = [m.dtms_win_rate for m in self.metrics]
        intelligent_win_rates = [m.intelligent_win_rate for m in self.metrics]
        
        dtms_cv = statistics.stdev(dtms_win_rates) / statistics.mean(dtms_win_rates) if statistics.mean(dtms_win_rates) > 0 else 1.0
        intelligent_cv = statistics.stdev(intelligent_win_rates) / statistics.mean(intelligent_win_rates) if statistics.mean(intelligent_win_rates) > 0 else 1.0
        
        # Lower CV is better (more stable)
        avg_cv = (dtms_cv + intelligent_cv) / 2
        stability_score = max(0.0, 1.0 - avg_cv)
        
        return stability_score
    
    def _calculate_comparison_readiness_score(self) -> float:
        """Calculate comparison readiness score (0-1)"""
        if not self.metrics:
            return 0.0
        
        # Check if we have sufficient data for both systems
        total_dtms_trades = sum(m.dtms_trades for m in self.metrics)
        total_intelligent_trades = sum(m.intelligent_trades for m in self.metrics)
        
        if total_dtms_trades < 50 or total_intelligent_trades < 50:
            return 0.0
        
        # Check if performance differences are meaningful
        dtms_avg_win_rate = statistics.mean([m.dtms_win_rate for m in self.metrics])
        intelligent_avg_win_rate = statistics.mean([m.intelligent_win_rate for m in self.metrics])
        
        win_rate_delta = abs(dtms_avg_win_rate - intelligent_avg_win_rate)
        
        # Higher delta means more meaningful comparison
        comparison_score = min(1.0, win_rate_delta / 0.1)  # 10% delta = 1.0 score
        
        return comparison_score
    
    def _generate_comparison_report(self) -> ComparisonReport:
        """Generate detailed comparison report"""
        if not self.metrics:
            return None
        
        # Calculate metrics for both systems
        dtms_metrics = self._calculate_system_metrics("dtms")
        intelligent_metrics = self._calculate_system_metrics("intelligent")
        
        # Calculate performance deltas
        performance_delta = {
            "win_rate_delta": dtms_metrics["win_rate"] - intelligent_metrics["win_rate"],
            "avg_rr_delta": dtms_metrics["avg_rr"] - intelligent_metrics["avg_rr"],
            "max_drawdown_delta": dtms_metrics["max_drawdown"] - intelligent_metrics["max_drawdown"],
            "latency_delta": dtms_metrics["latency_ms"] - intelligent_metrics["latency_ms"]
        }
        
        # Statistical significance test
        statistical_significance = self._calculate_statistical_significance()
        
        # Determine comparison result
        comparison_result = self._determine_comparison_result(performance_delta, statistical_significance)
        
        # Generate recommendations
        recommendations = self._generate_comparison_recommendations(comparison_result, performance_delta)
        
        return ComparisonReport(
            comparison_result=comparison_result,
            statistical_significance=statistical_significance,
            confidence_level=self.min_confidence_level,
            sample_size=len(self.metrics),
            dtms_metrics=dtms_metrics,
            intelligent_metrics=intelligent_metrics,
            performance_delta=performance_delta,
            recommendations=recommendations,
            validation_status=ValidationStatus.PASSED
        )
    
    def _calculate_system_metrics(self, system: str) -> Dict[str, Any]:
        """Calculate metrics for a specific system"""
        if system == "dtms":
            win_rates = [m.dtms_win_rate for m in self.metrics]
            avg_rrs = [m.dtms_avg_rr for m in self.metrics]
            max_drawdowns = [m.dtms_max_drawdown for m in self.metrics]
            latencies = [m.dtms_latency_ms for m in self.metrics]
            total_trades = sum(m.dtms_trades for m in self.metrics)
        else:
            win_rates = [m.intelligent_win_rate for m in self.metrics]
            avg_rrs = [m.intelligent_avg_rr for m in self.metrics]
            max_drawdowns = [m.intelligent_max_drawdown for m in self.metrics]
            latencies = [m.intelligent_latency_ms for m in self.metrics]
            total_trades = sum(m.intelligent_trades for m in self.metrics)
        
        return {
            "win_rate": statistics.mean(win_rates),
            "avg_rr": statistics.mean(avg_rrs),
            "max_drawdown": statistics.mean(max_drawdowns),
            "latency_ms": statistics.mean(latencies),
            "total_trades": total_trades,
            "win_rate_std": statistics.stdev(win_rates) if len(win_rates) > 1 else 0.0,
            "avg_rr_std": statistics.stdev(avg_rrs) if len(avg_rrs) > 1 else 0.0
        }
    
    def _calculate_statistical_significance(self) -> float:
        """Calculate statistical significance of performance differences"""
        if len(self.metrics) < 2:
            return 0.0
        
        # Perform t-test on win rates
        dtms_win_rates = [m.dtms_win_rate for m in self.metrics]
        intelligent_win_rates = [m.intelligent_win_rate for m in self.metrics]
        
        try:
            t_stat, p_value = scipy.stats.ttest_ind(dtms_win_rates, intelligent_win_rates)
            return 1.0 - p_value  # Convert p-value to significance (higher is better)
        except:
            return 0.0
    
    def _determine_comparison_result(self, performance_delta: Dict[str, float], 
                                   statistical_significance: float) -> ComparisonResult:
        """Determine comparison result based on performance delta and significance"""
        if statistical_significance < self.min_confidence_level:
            return ComparisonResult.INSUFFICIENT_DATA
        
        # Check if DTMS is significantly better
        if (performance_delta["win_rate_delta"] > self.min_performance_delta and
            performance_delta["avg_rr_delta"] > 0 and
            performance_delta["max_drawdown_delta"] < 0):
            return ComparisonResult.DTMS_BETTER
        
        # Check if Intelligent Exits are significantly better
        if (performance_delta["win_rate_delta"] < -self.min_performance_delta and
            performance_delta["avg_rr_delta"] < 0 and
            performance_delta["max_drawdown_delta"] > 0):
            return ComparisonResult.INTELLIGENT_BETTER
        
        # Otherwise, they are equivalent
        return ComparisonResult.EQUIVALENT
    
    def _generate_recommendations(self, readiness_score: float, 
                                comparison_report: Optional[ComparisonReport]) -> List[str]:
        """Generate recommendations based on readiness score and comparison"""
        recommendations = []
        
        if readiness_score < 0.5:
            recommendations.append("Shadow mode is not ready. Need more data and better performance stability.")
        elif readiness_score < 0.7:
            recommendations.append("Shadow mode is in testing phase. Continue collecting data and monitoring performance.")
        elif readiness_score < 0.9:
            recommendations.append("Shadow mode is preparing for production. Final validation needed.")
        else:
            recommendations.append("Shadow mode is ready for production deployment.")
        
        if comparison_report:
            if comparison_report.comparison_result == ComparisonResult.DTMS_BETTER:
                recommendations.append("DTMS shows superior performance. Consider full deployment.")
            elif comparison_report.comparison_result == ComparisonResult.INTELLIGENT_BETTER:
                recommendations.append("Intelligent Exits show superior performance. Consider keeping current system.")
            elif comparison_report.comparison_result == ComparisonResult.EQUIVALENT:
                recommendations.append("Both systems show equivalent performance. Consider gradual transition.")
            else:
                recommendations.append("Insufficient data for meaningful comparison. Continue shadow mode.")
        
        return recommendations
    
    def _generate_comparison_recommendations(self, comparison_result: ComparisonResult,
                                           performance_delta: Dict[str, float]) -> List[str]:
        """Generate specific comparison recommendations"""
        recommendations = []
        
        if comparison_result == ComparisonResult.DTMS_BETTER:
            recommendations.append(f"DTMS shows {performance_delta['win_rate_delta']:.2%} better win rate.")
            recommendations.append(f"DTMS shows {performance_delta['avg_rr_delta']:.2f} better average R:R.")
            recommendations.append("Recommend proceeding with DTMS deployment.")
        elif comparison_result == ComparisonResult.INTELLIGENT_BETTER:
            recommendations.append(f"Intelligent Exits show {abs(performance_delta['win_rate_delta']):.2%} better win rate.")
            recommendations.append(f"Intelligent Exits show {abs(performance_delta['avg_rr_delta']):.2f} better average R:R.")
            recommendations.append("Recommend keeping current Intelligent Exits system.")
        elif comparison_result == ComparisonResult.EQUIVALENT:
            recommendations.append("Both systems show equivalent performance.")
            recommendations.append("Consider gradual transition to DTMS for consistency.")
        else:
            recommendations.append("Insufficient data for meaningful comparison.")
            recommendations.append("Continue shadow mode for more data collection.")
        
        return recommendations
    
    def add_metrics(self, metrics: ShadowModeMetrics) -> None:
        """Add shadow mode metrics"""
        with self.lock:
            self.metrics.append(metrics)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        with self.lock:
            if not self.metrics:
                return {"total_metrics": 0}
            
            return {
                "total_metrics": len(self.metrics),
                "total_dtms_trades": sum(m.dtms_trades for m in self.metrics),
                "total_intelligent_trades": sum(m.intelligent_trades for m in self.metrics),
                "avg_dtms_win_rate": statistics.mean([m.dtms_win_rate for m in self.metrics]),
                "avg_intelligent_win_rate": statistics.mean([m.intelligent_win_rate for m in self.metrics]),
                "avg_confidence_delta": statistics.mean([m.confidence_delta for m in self.metrics])
            }

class ShadowModeValidator:
    """Main shadow mode validator"""
    
    def __init__(self):
        self.readiness_validator = ShadowModeReadinessValidator()
        self.start_time = time.time()
        self.validation_results: List[ShadowModeValidation] = []
        self.lock = threading.RLock()
    
    def validate_shadow_mode(self) -> ShadowModeValidation:
        """Validate shadow mode readiness"""
        # Get readiness validation
        validation = self.readiness_validator.validate_readiness()
        
        # Store validation result
        with self.lock:
            self.validation_results.append(validation)
        
        return validation
    
    def add_metrics(self, metrics: ShadowModeMetrics) -> None:
        """Add shadow mode metrics"""
        self.readiness_validator.add_metrics(metrics)
    
    def get_validation_history(self) -> List[ShadowModeValidation]:
        """Get validation history"""
        with self.lock:
            return self.validation_results.copy()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return self.readiness_validator.get_metrics_summary()
    
    def reset_metrics(self) -> None:
        """Reset all metrics"""
        with self.lock:
            self.readiness_validator.metrics.clear()
            self.validation_results.clear()

# Global shadow mode validator
_shadow_mode_validator: Optional[ShadowModeValidator] = None

def get_shadow_mode_validator() -> ShadowModeValidator:
    """Get global shadow mode validator instance"""
    global _shadow_mode_validator
    if _shadow_mode_validator is None:
        _shadow_mode_validator = ShadowModeValidator()
    return _shadow_mode_validator

def validate_shadow_mode() -> ShadowModeValidation:
    """Validate shadow mode readiness"""
    validator = get_shadow_mode_validator()
    return validator.validate_shadow_mode()

def add_shadow_mode_metrics(metrics: ShadowModeMetrics) -> None:
    """Add shadow mode metrics"""
    validator = get_shadow_mode_validator()
    validator.add_metrics(metrics)

def get_shadow_mode_metrics_summary() -> Dict[str, Any]:
    """Get shadow mode metrics summary"""
    validator = get_shadow_mode_validator()
    return validator.get_metrics_summary()

if __name__ == "__main__":
    # Example usage
    validator = get_shadow_mode_validator()
    
    # Add some sample metrics
    for i in range(150):  # More than minimum sample size
        metrics = ShadowModeMetrics(
            timestamp=time.time() + i,
            dtms_trades=10 + i,
            intelligent_trades=8 + i,
            dtms_win_rate=0.75 + (i % 10) * 0.01,
            intelligent_win_rate=0.70 + (i % 10) * 0.01,
            dtms_avg_rr=2.5 + (i % 5) * 0.1,
            intelligent_avg_rr=2.3 + (i % 5) * 0.1,
            dtms_max_drawdown=0.05 + (i % 3) * 0.01,
            intelligent_max_drawdown=0.06 + (i % 3) * 0.01,
            dtms_latency_ms=50.0 + (i % 10) * 2.0,
            intelligent_latency_ms=60.0 + (i % 10) * 2.0,
            confidence_delta=0.05 + (i % 5) * 0.01
        )
        validator.add_metrics(metrics)
    
    # Validate shadow mode
    result = validate_shadow_mode()
    
    print(f"Shadow Mode Validation:")
    print(f"Readiness Level: {result.readiness_level.value}")
    print(f"Validation Status: {result.validation_status.value}")
    print(f"Readiness Score: {result.readiness_score:.2f}")
    print(f"Sample Size: {result.validation_details['sample_size']}")
    print(f"DTMS Trades: {result.validation_details['dtms_trades']}")
    print(f"Intelligent Trades: {result.validation_details['intelligent_trades']}")
    print(f"Avg DTMS Win Rate: {result.validation_details['avg_dtms_win_rate']:.2%}")
    print(f"Avg Intelligent Win Rate: {result.validation_details['avg_intelligent_win_rate']:.2%}")
    
    if result.comparison_report:
        print(f"\nComparison Result: {result.comparison_report.comparison_result.value}")
        print(f"Statistical Significance: {result.comparison_report.statistical_significance:.2f}")
        print(f"Win Rate Delta: {result.comparison_report.performance_delta['win_rate_delta']:.2%}")
        print(f"Avg R:R Delta: {result.comparison_report.performance_delta['avg_rr_delta']:.2f}")
    
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"- {rec}")
