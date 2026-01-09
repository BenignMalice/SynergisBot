"""
Sustained Latency Validation System

This module implements a comprehensive validation system to ensure latency
<200ms sustained over time, including continuous monitoring, trend analysis,
performance degradation detection, and sustained performance validation.

Key Features:
- Sustained latency validation <200ms over time
- Continuous latency monitoring and analysis
- Performance trend analysis and degradation detection
- Sustained performance validation
- Latency stability assessment
- Performance regression detection
- Long-term performance tracking
- Automated alerting and recommendations
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

class LatencyTrend(Enum):
    """Latency trend types"""
    IMPROVING = "improving"  # Latency is decreasing over time
    STABLE = "stable"  # Latency is stable over time
    DEGRADING = "degrading"  # Latency is increasing over time
    VOLATILE = "volatile"  # Latency is highly variable
    UNKNOWN = "unknown"  # Insufficient data to determine trend

class SustainedPerformanceLevel(Enum):
    """Sustained performance levels"""
    EXCELLENT = "excellent"  # Consistently <50ms
    GOOD = "good"  # Consistently <100ms
    FAIR = "fair"  # Consistently <200ms
    POOR = "poor"  # Frequently >200ms
    CRITICAL = "critical"  # Consistently >200ms

class ValidationStatus(Enum):
    """Validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class LatencyStage(Enum):
    """Latency measurement stages"""
    TICK_INGESTION = "tick_ingestion"
    DATA_PROCESSING = "data_processing"
    FEATURE_CALCULATION = "feature_calculation"
    DECISION_MAKING = "decision_making"
    ORDER_EXECUTION = "order_execution"
    DATABASE_WRITE = "database_write"
    TOTAL_PIPELINE = "total_pipeline"

@dataclass
class LatencyMeasurement:
    """Latency measurement data structure"""
    timestamp: float
    stage: LatencyStage
    duration_ms: float
    symbol: str
    thread_id: int
    cpu_usage: float
    memory_usage: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LatencyWindow:
    """Latency measurement window"""
    start_time: float
    end_time: float
    measurements: List[LatencyMeasurement]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    min_ms: float
    mean_ms: float
    std_ms: float
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SustainedLatencyValidation:
    """Sustained latency validation result"""
    timestamp: float
    validation_period_hours: float
    total_measurements: int
    p95_latency_ms: float
    target_latency_ms: float
    meets_target: bool
    sustained_performance_level: SustainedPerformanceLevel
    latency_trend: LatencyTrend
    stability_score: float
    degradation_detected: bool
    validation_status: ValidationStatus
    issues_found: List[str]
    recommendations: List[str]
    detailed_analysis: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SustainedLatencyReport:
    """Sustained latency validation report"""
    timestamp: float
    overall_performance_score: float
    validation_period_hours: float
    total_measurements: int
    p95_latency_ms: float
    target_latency_ms: float
    meets_target: bool
    sustained_performance_level: SustainedPerformanceLevel
    latency_trend: LatencyTrend
    stability_score: float
    degradation_detected: bool
    validation_status: ValidationStatus
    stage_analysis: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    stability_analysis: Dict[str, Any]
    recommendations: List[str]
    detailed_validations: List[SustainedLatencyValidation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class LatencyWindowManager:
    """Manages latency measurement windows"""
    
    def __init__(self, window_size_minutes: int = 5, max_windows: int = 1440):  # 12 hours of 5-min windows
        self.window_size_minutes = window_size_minutes
        self.window_size_seconds = window_size_minutes * 60
        self.max_windows = max_windows
        self.windows: deque = deque(maxlen=max_windows)
        self.current_window: Optional[LatencyWindow] = None
        self.lock = threading.RLock()
    
    def add_measurement(self, measurement: LatencyMeasurement) -> None:
        """Add latency measurement to current window"""
        with self.lock:
            current_time = time.time()
            
            # Initialize current window if needed
            if self.current_window is None:
                self.current_window = LatencyWindow(
                    start_time=current_time,
                    end_time=current_time + self.window_size_seconds,
                    measurements=[],
                    p50_ms=0.0,
                    p95_ms=0.0,
                    p99_ms=0.0,
                    max_ms=0.0,
                    min_ms=0.0,
                    mean_ms=0.0,
                    std_ms=0.0,
                    count=0
                )
            
            # Check if measurement belongs to current window
            if measurement.timestamp >= self.current_window.start_time and measurement.timestamp < self.current_window.end_time:
                self.current_window.measurements.append(measurement)
            else:
                # Finalize current window and start new one
                if self.current_window.measurements:
                    self._finalize_window()
                
                self.current_window = LatencyWindow(
                    start_time=measurement.timestamp,
                    end_time=measurement.timestamp + self.window_size_seconds,
                    measurements=[measurement],
                    p50_ms=0.0,
                    p95_ms=0.0,
                    p99_ms=0.0,
                    max_ms=0.0,
                    min_ms=0.0,
                    mean_ms=0.0,
                    std_ms=0.0,
                    count=0
                )
    
    def _finalize_window(self) -> None:
        """Finalize current window and add to windows list"""
        if not self.current_window or not self.current_window.measurements:
            return
        
        measurements = self.current_window.measurements
        durations = [m.duration_ms for m in measurements]
        
        if durations:
            self.current_window.p50_ms = np.percentile(durations, 50)
            self.current_window.p95_ms = np.percentile(durations, 95)
            self.current_window.p99_ms = np.percentile(durations, 99)
            self.current_window.max_ms = max(durations)
            self.current_window.min_ms = min(durations)
            self.current_window.mean_ms = np.mean(durations)
            self.current_window.std_ms = np.std(durations)
            self.current_window.count = len(durations)
        
        self.windows.append(self.current_window)
        self.current_window = None
    
    def get_recent_windows(self, hours: float) -> List[LatencyWindow]:
        """Get recent windows within specified hours"""
        with self.lock:
            cutoff_time = time.time() - (hours * 3600)
            return [w for w in self.windows if w.end_time >= cutoff_time]
    
    def get_window_statistics(self, hours: float) -> Dict[str, Any]:
        """Get window statistics for specified period"""
        windows = self.get_recent_windows(hours)
        
        if not windows:
            return {
                "total_windows": 0,
                "total_measurements": 0,
                "avg_p95_ms": 0.0,
                "max_p95_ms": 0.0,
                "min_p95_ms": 0.0,
                "stability_score": 0.0
            }
        
        p95_values = [w.p95_ms for w in windows]
        
        return {
            "total_windows": len(windows),
            "total_measurements": sum(w.count for w in windows),
            "avg_p95_ms": np.mean(p95_values),
            "max_p95_ms": max(p95_values),
            "min_p95_ms": min(p95_values),
            "stability_score": self._calculate_stability_score(p95_values)
        }
    
    def _calculate_stability_score(self, values: List[float]) -> float:
        """Calculate stability score (0-1, higher is more stable)"""
        if len(values) < 2:
            return 1.0
        
        # Calculate coefficient of variation (lower is more stable)
        mean_val = np.mean(values)
        if mean_val == 0:
            return 1.0
        
        cv = np.std(values) / mean_val
        # Convert to stability score (0-1)
        return max(0.0, min(1.0, 1.0 - cv))

class TrendAnalyzer:
    """Analyzes latency trends over time"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def analyze_trend(self, windows: List[LatencyWindow], metric: str = "p95_ms") -> LatencyTrend:
        """Analyze latency trend from windows"""
        if len(windows) < 3:
            return LatencyTrend.UNKNOWN
        
        values = [getattr(w, metric) for w in windows]
        
        # Calculate volatility (coefficient of variation) first
        mean_val = np.mean(values)
        if mean_val == 0:
            cv = 0
        else:
            cv = np.std(values) / mean_val
        
        # If highly volatile, return volatile regardless of trend
        if cv > 0.3:  # High volatility threshold
            return LatencyTrend.VOLATILE
        
        # Calculate trend using linear regression
        x = np.arange(len(values))
        y = np.array(values)
        
        # Simple linear regression
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            return LatencyTrend.UNKNOWN
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Determine trend based on slope
        if slope < -0.05:  # Decreasing trend (more sensitive threshold)
            return LatencyTrend.IMPROVING
        elif slope > 0.05:  # Increasing trend (more sensitive threshold)
            return LatencyTrend.DEGRADING
        else:  # Stable trend
            return LatencyTrend.STABLE
    
    def detect_degradation(self, windows: List[LatencyWindow], threshold_increase: float = 0.2) -> bool:
        """Detect performance degradation"""
        if len(windows) < 6:  # Need at least 6 windows for reliable detection
            return False
        
        # Compare recent windows to earlier windows
        mid_point = len(windows) // 2
        recent_windows = windows[mid_point:]
        earlier_windows = windows[:mid_point]
        
        recent_p95 = np.mean([w.p95_ms for w in recent_windows])
        earlier_p95 = np.mean([w.p95_ms for w in earlier_windows])
        
        if earlier_p95 == 0:
            return recent_p95 > 0
        
        increase_ratio = (recent_p95 - earlier_p95) / earlier_p95
        return increase_ratio > threshold_increase

class SustainedLatencyValidator:
    """Sustained latency validator for comprehensive validation"""
    
    def __init__(self, target_latency_ms: float = 200.0, validation_period_hours: float = 24.0):
        self.target_latency_ms = target_latency_ms
        self.validation_period_hours = validation_period_hours
        self.window_manager = LatencyWindowManager()
        self.trend_analyzer = TrendAnalyzer()
        self.validations: List[SustainedLatencyValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def add_measurement(self, measurement: LatencyMeasurement) -> None:
        """Add latency measurement"""
        self.window_manager.add_measurement(measurement)
    
    def validate_sustained_latency(self) -> SustainedLatencyValidation:
        """Validate sustained latency performance"""
        # Get recent windows for validation period
        windows = self.window_manager.get_recent_windows(self.validation_period_hours)
        
        if not windows:
            return self._create_empty_validation()
        
        # Calculate overall statistics
        all_measurements = []
        for window in windows:
            all_measurements.extend(window.measurements)
        
        if not all_measurements:
            return self._create_empty_validation()
        
        durations = [m.duration_ms for m in all_measurements]
        p95_latency_ms = np.percentile(durations, 95)
        
        # Check if meets target
        meets_target = p95_latency_ms <= self.target_latency_ms
        
        # Determine sustained performance level
        sustained_performance_level = self._determine_performance_level(p95_latency_ms)
        
        # Analyze trend
        latency_trend = self.trend_analyzer.analyze_trend(windows)
        
        # Calculate stability score
        stability_score = self._calculate_stability_score(windows)
        
        # Detect degradation
        degradation_detected = self.trend_analyzer.detect_degradation(windows)
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            meets_target, sustained_performance_level, latency_trend, degradation_detected
        )
        
        # Generate issues and recommendations
        issues_found = self._identify_issues(
            p95_latency_ms, meets_target, latency_trend, degradation_detected, stability_score
        )
        recommendations = self._generate_recommendations(
            p95_latency_ms, meets_target, latency_trend, degradation_detected, stability_score
        )
        
        # Generate detailed analysis
        detailed_analysis = self._generate_detailed_analysis(windows, all_measurements)
        
        validation = SustainedLatencyValidation(
            timestamp=time.time(),
            validation_period_hours=self.validation_period_hours,
            total_measurements=len(all_measurements),
            p95_latency_ms=p95_latency_ms,
            target_latency_ms=self.target_latency_ms,
            meets_target=meets_target,
            sustained_performance_level=sustained_performance_level,
            latency_trend=latency_trend,
            stability_score=stability_score,
            degradation_detected=degradation_detected,
            validation_status=validation_status,
            issues_found=issues_found,
            recommendations=recommendations,
            detailed_analysis=detailed_analysis,
            metadata={
                "target_latency_ms": self.target_latency_ms,
                "validation_period_hours": self.validation_period_hours,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _create_empty_validation(self) -> SustainedLatencyValidation:
        """Create empty validation when no data available"""
        return SustainedLatencyValidation(
            timestamp=time.time(),
            validation_period_hours=self.validation_period_hours,
            total_measurements=0,
            p95_latency_ms=0.0,
            target_latency_ms=self.target_latency_ms,
            meets_target=False,
            sustained_performance_level=SustainedPerformanceLevel.CRITICAL,
            latency_trend=LatencyTrend.UNKNOWN,
            stability_score=0.0,
            degradation_detected=False,
            validation_status=ValidationStatus.FAILED,
            issues_found=["No latency data available"],
            recommendations=["Collect latency measurements"],
            detailed_analysis={},
            metadata={
                "target_latency_ms": self.target_latency_ms,
                "validation_period_hours": self.validation_period_hours,
                "validation_time": time.time()
            }
        )
    
    def _determine_performance_level(self, p95_latency_ms: float) -> SustainedPerformanceLevel:
        """Determine sustained performance level"""
        if p95_latency_ms <= 50:
            return SustainedPerformanceLevel.EXCELLENT
        elif p95_latency_ms <= 100:
            return SustainedPerformanceLevel.GOOD
        elif p95_latency_ms <= 200:
            return SustainedPerformanceLevel.FAIR
        elif p95_latency_ms <= 500:
            return SustainedPerformanceLevel.POOR
        else:
            return SustainedPerformanceLevel.CRITICAL
    
    def _calculate_stability_score(self, windows: List[LatencyWindow]) -> float:
        """Calculate stability score from windows"""
        if len(windows) < 2:
            return 1.0
        
        p95_values = [w.p95_ms for w in windows]
        return self.window_manager._calculate_stability_score(p95_values)
    
    def _determine_validation_status(self, meets_target: bool, performance_level: SustainedPerformanceLevel,
                                   trend: LatencyTrend, degradation_detected: bool) -> ValidationStatus:
        """Determine validation status"""
        if meets_target and performance_level in [SustainedPerformanceLevel.EXCELLENT, SustainedPerformanceLevel.GOOD]:
            return ValidationStatus.PASSED
        elif meets_target and not degradation_detected:
            return ValidationStatus.PASSED
        elif meets_target and degradation_detected:
            return ValidationStatus.WARNING
        else:
            return ValidationStatus.FAILED
    
    def _identify_issues(self, p95_latency_ms: float, meets_target: bool, trend: LatencyTrend,
                        degradation_detected: bool, stability_score: float) -> List[str]:
        """Identify performance issues"""
        issues = []
        
        if not meets_target:
            issues.append(f"P95 latency {p95_latency_ms:.1f}ms exceeds target {self.target_latency_ms}ms")
        
        if trend == LatencyTrend.DEGRADING:
            issues.append("Latency is degrading over time")
        
        if trend == LatencyTrend.VOLATILE:
            issues.append("Latency is highly volatile")
        
        if degradation_detected:
            issues.append("Performance degradation detected")
        
        if stability_score < 0.7:
            issues.append(f"Low stability score: {stability_score:.2f}")
        
        if p95_latency_ms > self.target_latency_ms * 2:
            issues.append("Latency significantly exceeds target")
        
        return issues
    
    def _generate_recommendations(self, p95_latency_ms: float, meets_target: bool, trend: LatencyTrend,
                                degradation_detected: bool, stability_score: float) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if not meets_target:
            recommendations.append("Optimize system performance to meet latency target")
            recommendations.append("Review and optimize critical path components")
        
        if trend == LatencyTrend.DEGRADING:
            recommendations.append("Investigate and fix performance degradation causes")
            recommendations.append("Monitor system resources and bottlenecks")
        
        if trend == LatencyTrend.VOLATILE:
            recommendations.append("Improve system stability and reduce variability")
            recommendations.append("Implement better resource management")
        
        if degradation_detected:
            recommendations.append("Conduct performance regression analysis")
            recommendations.append("Review recent system changes")
        
        if stability_score < 0.7:
            recommendations.append("Improve system stability and consistency")
            recommendations.append("Implement better load balancing")
        
        if p95_latency_ms > self.target_latency_ms * 1.5:
            recommendations.append("Critical performance optimization needed")
            recommendations.append("Consider system architecture review")
        
        if meets_target and stability_score > 0.8:
            recommendations.append("Excellent sustained performance! Continue current practices")
        
        return recommendations
    
    def _generate_detailed_analysis(self, windows: List[LatencyWindow], 
                                  measurements: List[LatencyMeasurement]) -> Dict[str, Any]:
        """Generate detailed analysis"""
        if not windows or not measurements:
            return {}
        
        # Stage analysis
        stage_measurements = defaultdict(list)
        for measurement in measurements:
            stage_measurements[measurement.stage.value].append(measurement.duration_ms)
        
        stage_analysis = {}
        for stage, durations in stage_measurements.items():
            stage_analysis[stage] = {
                "count": len(durations),
                "p50_ms": np.percentile(durations, 50),
                "p95_ms": np.percentile(durations, 95),
                "p99_ms": np.percentile(durations, 99),
                "max_ms": max(durations),
                "min_ms": min(durations),
                "mean_ms": np.mean(durations),
                "std_ms": np.std(durations)
            }
        
        # Trend analysis
        p95_values = [w.p95_ms for w in windows]
        trend_analysis = {
            "trend": self.trend_analyzer.analyze_trend(windows).value,
            "degradation_detected": self.trend_analyzer.detect_degradation(windows),
            "p95_trend": {
                "values": p95_values,
                "slope": self._calculate_trend_slope(p95_values),
                "volatility": np.std(p95_values) / np.mean(p95_values) if np.mean(p95_values) > 0 else 0
            }
        }
        
        # Stability analysis
        stability_analysis = {
            "stability_score": self._calculate_stability_score(windows),
            "window_count": len(windows),
            "measurement_count": len(measurements),
            "time_span_hours": (windows[-1].end_time - windows[0].start_time) / 3600 if len(windows) > 1 else 0
        }
        
        return {
            "stage_analysis": stage_analysis,
            "trend_analysis": trend_analysis,
            "stability_analysis": stability_analysis
        }
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate trend slope"""
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0
        
        return (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    
    def generate_validation_report(self) -> SustainedLatencyReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return SustainedLatencyReport(
                    timestamp=time.time(),
                    overall_performance_score=0.0,
                    validation_period_hours=self.validation_period_hours,
                    total_measurements=0,
                    p95_latency_ms=0.0,
                    target_latency_ms=self.target_latency_ms,
                    meets_target=False,
                    sustained_performance_level=SustainedPerformanceLevel.CRITICAL,
                    latency_trend=LatencyTrend.UNKNOWN,
                    stability_score=0.0,
                    degradation_detected=False,
                    validation_status=ValidationStatus.FAILED,
                    stage_analysis={},
                    trend_analysis={},
                    stability_analysis={},
                    recommendations=["No validation data available"],
                    detailed_validations=[],
                    metadata={"error": "No validation data available"}
                )
            
            # Get latest validation
            latest_validation = self.validations[-1]
            
            # Calculate overall performance score
            overall_score = self._calculate_overall_performance_score(latest_validation)
            
            return SustainedLatencyReport(
                timestamp=time.time(),
                overall_performance_score=overall_score,
                validation_period_hours=latest_validation.validation_period_hours,
                total_measurements=latest_validation.total_measurements,
                p95_latency_ms=latest_validation.p95_latency_ms,
                target_latency_ms=latest_validation.target_latency_ms,
                meets_target=latest_validation.meets_target,
                sustained_performance_level=latest_validation.sustained_performance_level,
                latency_trend=latest_validation.latency_trend,
                stability_score=latest_validation.stability_score,
                degradation_detected=latest_validation.degradation_detected,
                validation_status=latest_validation.validation_status,
                stage_analysis=latest_validation.detailed_analysis.get("stage_analysis", {}),
                trend_analysis=latest_validation.detailed_analysis.get("trend_analysis", {}),
                stability_analysis=latest_validation.detailed_analysis.get("stability_analysis", {}),
                recommendations=latest_validation.recommendations,
                detailed_validations=self.validations.copy(),
                metadata={
                    "target_latency_ms": self.target_latency_ms,
                    "validation_period_hours": self.validation_period_hours,
                    "validation_duration": time.time() - self.start_time
                }
            )
    
    def _calculate_overall_performance_score(self, validation: SustainedLatencyValidation) -> float:
        """Calculate overall performance score"""
        score = 0.0
        
        # Latency target score (40% weight)
        if validation.meets_target:
            score += 0.4
        else:
            score += 0.4 * max(0.0, 1.0 - (validation.p95_latency_ms - validation.target_latency_ms) / validation.target_latency_ms)
        
        # Performance level score (30% weight)
        level_scores = {
            SustainedPerformanceLevel.EXCELLENT: 1.0,
            SustainedPerformanceLevel.GOOD: 0.8,
            SustainedPerformanceLevel.FAIR: 0.6,
            SustainedPerformanceLevel.POOR: 0.3,
            SustainedPerformanceLevel.CRITICAL: 0.0
        }
        score += 0.3 * level_scores.get(validation.sustained_performance_level, 0.0)
        
        # Stability score (20% weight)
        score += 0.2 * validation.stability_score
        
        # Trend score (10% weight)
        trend_scores = {
            LatencyTrend.IMPROVING: 1.0,
            LatencyTrend.STABLE: 0.8,
            LatencyTrend.VOLATILE: 0.4,
            LatencyTrend.DEGRADING: 0.0,
            LatencyTrend.UNKNOWN: 0.5
        }
        score += 0.1 * trend_scores.get(validation.latency_trend, 0.0)
        
        return max(0.0, min(1.0, score))

# Global sustained latency validation manager
_sustained_latency_validator: Optional[SustainedLatencyValidator] = None

def get_sustained_latency_validator(target_latency_ms: float = 200.0, 
                                  validation_period_hours: float = 24.0) -> SustainedLatencyValidator:
    """Get global sustained latency validator instance"""
    global _sustained_latency_validator
    if _sustained_latency_validator is None:
        _sustained_latency_validator = SustainedLatencyValidator(target_latency_ms, validation_period_hours)
    return _sustained_latency_validator

def add_latency_measurement(measurement: LatencyMeasurement) -> None:
    """Add latency measurement"""
    validator = get_sustained_latency_validator()
    validator.add_measurement(measurement)

def validate_sustained_latency() -> SustainedLatencyValidation:
    """Validate sustained latency performance"""
    validator = get_sustained_latency_validator()
    return validator.validate_sustained_latency()

def generate_sustained_latency_report() -> SustainedLatencyReport:
    """Generate sustained latency validation report"""
    validator = get_sustained_latency_validator()
    return validator.generate_validation_report()

if __name__ == "__main__":
    # Example usage
    validator = get_sustained_latency_validator()
    
    # Example latency measurements
    for i in range(100):
        measurement = LatencyMeasurement(
            timestamp=time.time() - i * 60,  # 1 minute intervals
            stage=LatencyStage.TOTAL_PIPELINE,
            duration_ms=50.0 + np.random.normal(0, 10),  # Random latency around 50ms
            symbol="BTCUSDT",
            thread_id=1,
            cpu_usage=50.0 + np.random.normal(0, 5),
            memory_usage=60.0 + np.random.normal(0, 5),
            metadata={"test": True}
        )
        
        add_latency_measurement(measurement)
    
    validation = validate_sustained_latency()
    
    print(f"Sustained Latency Validation:")
    print(f"Validation Period: {validation.validation_period_hours:.1f} hours")
    print(f"Total Measurements: {validation.total_measurements}")
    print(f"P95 Latency: {validation.p95_latency_ms:.1f}ms")
    print(f"Target Latency: {validation.target_latency_ms:.1f}ms")
    print(f"Meets Target: {validation.meets_target}")
    print(f"Performance Level: {validation.sustained_performance_level.value}")
    print(f"Latency Trend: {validation.latency_trend.value}")
    print(f"Stability Score: {validation.stability_score:.2f}")
    print(f"Degradation Detected: {validation.degradation_detected}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    print("\nIssues Found:")
    for issue in validation.issues_found:
        print(f"- {issue}")
    
    print("\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate validation report
    report = generate_sustained_latency_report()
    
    print(f"\nSustained Latency Report:")
    print(f"Overall Performance Score: {report.overall_performance_score:.2f}")
    print(f"Stage Analysis: {len(report.stage_analysis)} stages")
    print(f"Trend Analysis: {len(report.trend_analysis)} metrics")
    print(f"Stability Analysis: {len(report.stability_analysis)} metrics")
    print(f"Recommendations: {len(report.recommendations)} items")
