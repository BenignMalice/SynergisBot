"""
Go/No-Go Criteria System

This module implements a comprehensive go/no-go criteria system that monitors
drawdown stability, queue backpressure incidence, and p95 latency to determine
production readiness and system health.

Key Features:
- Drawdown stability monitoring and analysis
- Queue backpressure incidence tracking
- P95 latency monitoring and alerting
- Production readiness assessment
- Risk-based decision making
- Automated go/no-go recommendations
"""

import time
import json
import logging
import threading
import statistics
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import numpy as np
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class CriteriaStatus(Enum):
    """Go/No-Go criteria status"""
    GO = "go"
    NO_GO = "no_go"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class CriteriaType(Enum):
    """Types of go/no-go criteria"""
    DRAWDOWN_STABILITY = "drawdown_stability"
    QUEUE_BACKPRESSURE = "queue_backpressure"
    LATENCY_P95 = "latency_p95"
    SYSTEM_HEALTH = "system_health"
    DATA_QUALITY = "data_quality"
    PERFORMANCE = "performance"

class SeverityLevel(Enum):
    """Severity levels for criteria violations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class CriteriaThreshold:
    """Threshold configuration for criteria"""
    name: str
    criteria_type: CriteriaType
    warning_threshold: float
    critical_threshold: float
    measurement_window: int  # seconds
    min_samples: int
    enabled: bool = True

@dataclass
class CriteriaMeasurement:
    """Individual measurement for criteria"""
    timestamp: float
    value: float
    criteria_type: CriteriaType
    severity: SeverityLevel
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CriteriaAssessment:
    """Assessment of go/no-go criteria"""
    timestamp: float
    overall_status: CriteriaStatus
    criteria_results: Dict[CriteriaType, CriteriaStatus]
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    confidence_score: float
    next_assessment_time: float

@dataclass
class DrawdownMetrics:
    """Drawdown stability metrics"""
    current_drawdown: float
    max_drawdown: float
    drawdown_duration: float
    recovery_time: float
    drawdown_frequency: float
    volatility: float
    sharpe_ratio: float

@dataclass
class QueueMetrics:
    """Queue backpressure metrics"""
    queue_depth: int
    processing_rate: float
    backpressure_incidence: float
    queue_utilization: float
    overflow_count: int
    avg_wait_time: float
    max_wait_time: float

@dataclass
class LatencyMetrics:
    """Latency performance metrics"""
    p50_latency: float
    p95_latency: float
    p99_latency: float
    max_latency: float
    avg_latency: float
    latency_variance: float
    timeout_rate: float

class DrawdownAnalyzer:
    """Analyzes drawdown stability"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.returns: deque = deque(maxlen=window_size)
        self.drawdowns: deque = deque(maxlen=window_size)
        self.peak_values: deque = deque(maxlen=window_size)
        self.lock = threading.RLock()
    
    def add_return(self, return_value: float, timestamp: float) -> None:
        """Add a return value for analysis"""
        with self.lock:
            self.returns.append((timestamp, return_value))
            
            # Update peak values
            if not self.peak_values:
                self.peak_values.append(return_value)
            else:
                self.peak_values.append(max(self.peak_values[-1], return_value))
            
            # Calculate current drawdown
            if self.peak_values:
                current_drawdown = (self.peak_values[-1] - return_value) / self.peak_values[-1]
                self.drawdowns.append((timestamp, current_drawdown))
    
    def get_drawdown_metrics(self) -> DrawdownMetrics:
        """Get current drawdown metrics"""
        with self.lock:
            if len(self.returns) < 2:
                return DrawdownMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            
            # Calculate current drawdown
            current_drawdown = 0.0
            if self.drawdowns:
                current_drawdown = self.drawdowns[-1][1]
            
            # Calculate max drawdown
            max_drawdown = max(dd[1] for dd in self.drawdowns) if self.drawdowns else 0.0
            
            # Calculate drawdown duration
            drawdown_duration = self._calculate_drawdown_duration()
            
            # Calculate recovery time
            recovery_time = self._calculate_recovery_time()
            
            # Calculate drawdown frequency
            drawdown_frequency = self._calculate_drawdown_frequency()
            
            # Calculate volatility
            returns_list = [r[1] for r in self.returns]
            volatility = statistics.stdev(returns_list) if len(returns_list) > 1 else 0.0
            
            # Calculate Sharpe ratio
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            return DrawdownMetrics(
                current_drawdown=current_drawdown,
                max_drawdown=max_drawdown,
                drawdown_duration=drawdown_duration,
                recovery_time=recovery_time,
                drawdown_frequency=drawdown_frequency,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio
            )
    
    def _calculate_drawdown_duration(self) -> float:
        """Calculate current drawdown duration"""
        if not self.drawdowns:
            return 0.0
        
        current_time = time.time()
        drawdown_start = None
        
        # Find when current drawdown started
        for i in range(len(self.drawdowns) - 1, -1, -1):
            if self.drawdowns[i][1] > 0:  # In drawdown
                if drawdown_start is None:
                    drawdown_start = self.drawdowns[i][0]
            else:
                break
        
        if drawdown_start:
            return current_time - drawdown_start
        
        return 0.0
    
    def _calculate_recovery_time(self) -> float:
        """Calculate average recovery time from drawdowns"""
        if len(self.drawdowns) < 2:
            return 0.0
        
        recovery_times = []
        in_drawdown = False
        drawdown_start = None
        
        for timestamp, drawdown in self.drawdowns:
            if drawdown > 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = timestamp
            elif drawdown == 0 and in_drawdown:
                in_drawdown = False
                if drawdown_start:
                    recovery_times.append(timestamp - drawdown_start)
        
        return statistics.mean(recovery_times) if recovery_times else 0.0
    
    def _calculate_drawdown_frequency(self) -> float:
        """Calculate drawdown frequency per day"""
        if len(self.drawdowns) < 2:
            return 0.0
        
        # Count drawdown periods
        drawdown_periods = 0
        in_drawdown = False
        
        for _, drawdown in self.drawdowns:
            if drawdown > 0 and not in_drawdown:
                in_drawdown = True
                drawdown_periods += 1
            elif drawdown == 0:
                in_drawdown = False
        
        # Calculate frequency per day
        time_span = (self.drawdowns[-1][0] - self.drawdowns[0][0]) / (24 * 3600)  # days
        return drawdown_periods / time_span if time_span > 0 else 0.0
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio"""
        if len(self.returns) < 2:
            return 0.0
        
        returns_list = [r[1] for r in self.returns]
        mean_return = statistics.mean(returns_list)
        std_return = statistics.stdev(returns_list)
        
        return mean_return / std_return if std_return > 0 else 0.0

class QueueAnalyzer:
    """Analyzes queue backpressure"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.queue_depths: deque = deque(maxlen=window_size)
        self.processing_times: deque = deque(maxlen=window_size)
        self.overflow_events: deque = deque(maxlen=window_size)
        self.lock = threading.RLock()
    
    def add_queue_measurement(self, depth: int, processing_time: float, 
                             timestamp: float, overflow: bool = False) -> None:
        """Add queue measurement"""
        with self.lock:
            self.queue_depths.append((timestamp, depth))
            self.processing_times.append((timestamp, processing_time))
            
            if overflow:
                self.overflow_events.append((timestamp, True))
    
    def get_queue_metrics(self) -> QueueMetrics:
        """Get current queue metrics"""
        with self.lock:
            if not self.queue_depths:
                return QueueMetrics(0, 0.0, 0.0, 0.0, 0, 0.0, 0.0)
            
            # Current queue depth
            current_depth = self.queue_depths[-1][1] if self.queue_depths else 0
            
            # Calculate processing rate
            processing_rate = self._calculate_processing_rate()
            
            # Calculate backpressure incidence
            backpressure_incidence = self._calculate_backpressure_incidence()
            
            # Calculate queue utilization
            queue_utilization = self._calculate_queue_utilization()
            
            # Count overflow events
            overflow_count = len(self.overflow_events)
            
            # Calculate wait times
            avg_wait_time = statistics.mean([pt[1] for pt in self.processing_times]) if self.processing_times else 0.0
            max_wait_time = max([pt[1] for pt in self.processing_times]) if self.processing_times else 0.0
            
            return QueueMetrics(
                queue_depth=current_depth,
                processing_rate=processing_rate,
                backpressure_incidence=backpressure_incidence,
                queue_utilization=queue_utilization,
                overflow_count=overflow_count,
                avg_wait_time=avg_wait_time,
                max_wait_time=max_wait_time
            )
    
    def _calculate_processing_rate(self) -> float:
        """Calculate items processed per second"""
        if len(self.processing_times) < 2:
            return 0.0
        
        time_span = self.processing_times[-1][0] - self.processing_times[0][0]
        return len(self.processing_times) / time_span if time_span > 0 else 0.0
    
    def _calculate_backpressure_incidence(self) -> float:
        """Calculate percentage of time under backpressure"""
        if not self.queue_depths:
            return 0.0
        
        # Define backpressure threshold (e.g., 80% of max capacity)
        max_capacity = 1000  # Assume max queue capacity
        backpressure_threshold = max_capacity * 0.8
        
        backpressure_count = sum(1 for _, depth in self.queue_depths if depth > backpressure_threshold)
        return backpressure_count / len(self.queue_depths)
    
    def _calculate_queue_utilization(self) -> float:
        """Calculate average queue utilization"""
        if not self.queue_depths:
            return 0.0
        
        max_capacity = 1000  # Assume max queue capacity
        utilizations = [depth / max_capacity for _, depth in self.queue_depths]
        return statistics.mean(utilizations)

class LatencyAnalyzer:
    """Analyzes latency performance"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.latencies: deque = deque(maxlen=window_size)
        self.timeouts: deque = deque(maxlen=window_size)
        self.lock = threading.RLock()
    
    def add_latency_measurement(self, latency: float, timestamp: float, 
                               timeout: bool = False) -> None:
        """Add latency measurement"""
        with self.lock:
            self.latencies.append((timestamp, latency))
            
            if timeout:
                self.timeouts.append((timestamp, True))
    
    def get_latency_metrics(self) -> LatencyMetrics:
        """Get current latency metrics"""
        with self.lock:
            if not self.latencies:
                return LatencyMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            
            latency_values = [lat[1] for lat in self.latencies]
            
            # Calculate percentiles
            p50_latency = np.percentile(latency_values, 50)
            p95_latency = np.percentile(latency_values, 95)
            p99_latency = np.percentile(latency_values, 99)
            
            # Calculate other metrics
            max_latency = max(latency_values)
            avg_latency = statistics.mean(latency_values)
            latency_variance = statistics.variance(latency_values) if len(latency_values) > 1 else 0.0
            
            # Calculate timeout rate
            timeout_rate = len(self.timeouts) / len(self.latencies) if self.latencies else 0.0
            
            return LatencyMetrics(
                p50_latency=p50_latency,
                p95_latency=p95_latency,
                p99_latency=p99_latency,
                max_latency=max_latency,
                avg_latency=avg_latency,
                latency_variance=latency_variance,
                timeout_rate=timeout_rate
            )

class GoNoGoCriteria:
    """Main go/no-go criteria system"""
    
    def __init__(self):
        self.thresholds: Dict[CriteriaType, CriteriaThreshold] = {}
        self.measurements: Dict[CriteriaType, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.assessments: List[CriteriaAssessment] = []
        self.lock = threading.RLock()
        
        # Analyzers
        self.drawdown_analyzer = DrawdownAnalyzer()
        self.queue_analyzer = QueueAnalyzer()
        self.latency_analyzer = LatencyAnalyzer()
        
        # Callbacks
        self.on_criteria_violation: Optional[Callable[[CriteriaType, SeverityLevel], None]] = None
        self.on_assessment_completed: Optional[Callable[[CriteriaAssessment], None]] = None
        self.on_status_change: Optional[Callable[[CriteriaStatus], None]] = None
        
        # Initialize default thresholds
        self._initialize_default_thresholds()
    
    def _initialize_default_thresholds(self) -> None:
        """Initialize default criteria thresholds"""
        self.thresholds = {
            CriteriaType.DRAWDOWN_STABILITY: CriteriaThreshold(
                name="Drawdown Stability",
                criteria_type=CriteriaType.DRAWDOWN_STABILITY,
                warning_threshold=0.05,  # 5% drawdown
                critical_threshold=0.10,  # 10% drawdown
                measurement_window=3600,  # 1 hour
                min_samples=10
            ),
            CriteriaType.QUEUE_BACKPRESSURE: CriteriaThreshold(
                name="Queue Backpressure",
                criteria_type=CriteriaType.QUEUE_BACKPRESSURE,
                warning_threshold=0.20,  # 20% backpressure
                critical_threshold=0.50,  # 50% backpressure
                measurement_window=300,  # 5 minutes
                min_samples=5
            ),
            CriteriaType.LATENCY_P95: CriteriaThreshold(
                name="P95 Latency",
                criteria_type=CriteriaType.LATENCY_P95,
                warning_threshold=200.0,  # 200ms
                critical_threshold=500.0,  # 500ms
                measurement_window=300,  # 5 minutes
                min_samples=10
            )
        }
    
    def set_callbacks(self,
                      on_criteria_violation: Optional[Callable[[CriteriaType, SeverityLevel], None]] = None,
                      on_assessment_completed: Optional[Callable[[CriteriaAssessment], None]] = None,
                      on_status_change: Optional[Callable[[CriteriaStatus], None]] = None) -> None:
        """Set callback functions for criteria events"""
        self.on_criteria_violation = on_criteria_violation
        self.on_assessment_completed = on_assessment_completed
        self.on_status_change = on_status_change
    
    def add_measurement(self, criteria_type: CriteriaType, value: float, 
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a measurement for criteria assessment"""
        timestamp = time.time()
        
        with self.lock:
            measurement = CriteriaMeasurement(
                timestamp=timestamp,
                value=value,
                criteria_type=criteria_type,
                severity=self._assess_severity(criteria_type, value),
                metadata=metadata or {}
            )
            
            self.measurements[criteria_type].append(measurement)
            
            # Check for violations
            if measurement.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
                if self.on_criteria_violation:
                    try:
                        self.on_criteria_violation(criteria_type, measurement.severity)
                    except Exception as e:
                        logger.error(f"Error in on_criteria_violation callback: {e}")
    
    def _assess_severity(self, criteria_type: CriteriaType, value: float) -> SeverityLevel:
        """Assess severity of a measurement"""
        if criteria_type not in self.thresholds:
            return SeverityLevel.LOW
        
        threshold = self.thresholds[criteria_type]
        
        if value >= threshold.critical_threshold:
            return SeverityLevel.CRITICAL
        elif value >= threshold.warning_threshold:
            return SeverityLevel.HIGH
        elif value >= threshold.warning_threshold * 0.5:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def assess_criteria(self) -> CriteriaAssessment:
        """Perform comprehensive criteria assessment"""
        timestamp = time.time()
        
        with self.lock:
            criteria_results = {}
            violations = []
            recommendations = []
            
            # Assess each criteria type
            for criteria_type in CriteriaType:
                if criteria_type not in self.thresholds:
                    criteria_results[criteria_type] = CriteriaStatus.UNKNOWN
                    continue
                
                status = self._assess_criteria_type(criteria_type)
                criteria_results[criteria_type] = status
                
                # Collect violations
                if status in [CriteriaStatus.NO_GO, CriteriaStatus.CRITICAL]:
                    violations.append({
                        'criteria_type': criteria_type.value,
                        'status': status.value,
                        'threshold': self.thresholds[criteria_type].critical_threshold,
                        'timestamp': timestamp
                    })
                
                # Generate recommendations
                if status == CriteriaStatus.NO_GO:
                    recommendations.extend(self._generate_recommendations(criteria_type))
            
            # Determine overall status
            overall_status = self._determine_overall_status(criteria_results)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(criteria_results)
            
            # Create assessment
            assessment = CriteriaAssessment(
                timestamp=timestamp,
                overall_status=overall_status,
                criteria_results=criteria_results,
                violations=violations,
                recommendations=recommendations,
                confidence_score=confidence_score,
                next_assessment_time=timestamp + 300  # Next assessment in 5 minutes
            )
            
            # Store assessment
            self.assessments.append(assessment)
            
            # Keep only recent assessments
            if len(self.assessments) > 100:
                self.assessments = self.assessments[-100:]
            
            # Call assessment callback
            if self.on_assessment_completed:
                try:
                    self.on_assessment_completed(assessment)
                except Exception as e:
                    logger.error(f"Error in on_assessment_completed callback: {e}")
            
            return assessment
    
    def _assess_criteria_type(self, criteria_type: CriteriaType) -> CriteriaStatus:
        """Assess a specific criteria type"""
        if criteria_type not in self.thresholds:
            return CriteriaStatus.UNKNOWN
        
        threshold = self.thresholds[criteria_type]
        measurements = self.measurements[criteria_type]
        
        if len(measurements) < threshold.min_samples:
            return CriteriaStatus.UNKNOWN
        
        # Get recent measurements within window
        cutoff_time = time.time() - threshold.measurement_window
        recent_measurements = [
            m for m in measurements 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_measurements:
            return CriteriaStatus.UNKNOWN
        
        # Calculate average value
        avg_value = statistics.mean([m.value for m in recent_measurements])
        
        # Determine status
        if avg_value >= threshold.critical_threshold:
            return CriteriaStatus.CRITICAL
        elif avg_value >= threshold.warning_threshold:
            return CriteriaStatus.NO_GO
        elif avg_value >= threshold.warning_threshold * 0.7:
            return CriteriaStatus.WARNING
        else:
            return CriteriaStatus.GO
    
    def _determine_overall_status(self, criteria_results: Dict[CriteriaType, CriteriaStatus]) -> CriteriaStatus:
        """Determine overall go/no-go status"""
        if CriteriaStatus.CRITICAL in criteria_results.values():
            return CriteriaStatus.CRITICAL
        elif CriteriaStatus.NO_GO in criteria_results.values():
            return CriteriaStatus.NO_GO
        elif CriteriaStatus.WARNING in criteria_results.values():
            return CriteriaStatus.WARNING
        elif CriteriaStatus.UNKNOWN in criteria_results.values():
            return CriteriaStatus.UNKNOWN
        else:
            return CriteriaStatus.GO
    
    def _calculate_confidence_score(self, criteria_results: Dict[CriteriaType, CriteriaStatus]) -> float:
        """Calculate confidence score for assessment"""
        total_criteria = len(criteria_results)
        if total_criteria == 0:
            return 0.0
        
        # Weight different statuses
        status_weights = {
            CriteriaStatus.GO: 1.0,
            CriteriaStatus.WARNING: 0.7,
            CriteriaStatus.NO_GO: 0.3,
            CriteriaStatus.CRITICAL: 0.0,
            CriteriaStatus.UNKNOWN: 0.5
        }
        
        weighted_sum = sum(status_weights.get(status, 0.5) for status in criteria_results.values())
        return weighted_sum / total_criteria
    
    def _generate_recommendations(self, criteria_type: CriteriaType) -> List[str]:
        """Generate recommendations for criteria violations"""
        recommendations = []
        
        if criteria_type == CriteriaType.DRAWDOWN_STABILITY:
            recommendations.extend([
                "Review risk management parameters",
                "Consider reducing position sizes",
                "Implement additional stop-loss mechanisms",
                "Analyze market conditions for increased volatility"
            ])
        elif criteria_type == CriteriaType.QUEUE_BACKPRESSURE:
            recommendations.extend([
                "Increase queue processing capacity",
                "Implement queue prioritization",
                "Add more processing threads",
                "Consider queue partitioning"
            ])
        elif criteria_type == CriteriaType.LATENCY_P95:
            recommendations.extend([
                "Optimize critical code paths",
                "Review database query performance",
                "Consider caching strategies",
                "Implement connection pooling"
            ])
        
        return recommendations
    
    def get_latest_assessment(self) -> Optional[CriteriaAssessment]:
        """Get the latest criteria assessment"""
        with self.lock:
            return self.assessments[-1] if self.assessments else None
    
    def get_assessment_history(self, limit: Optional[int] = None) -> List[CriteriaAssessment]:
        """Get assessment history"""
        with self.lock:
            if limit:
                return self.assessments[-limit:]
            return list(self.assessments)
    
    def get_criteria_statistics(self) -> Dict[str, Any]:
        """Get criteria statistics"""
        with self.lock:
            stats = {
                'total_assessments': len(self.assessments),
                'criteria_types': len(self.thresholds),
                'measurements_count': {ct.value: len(measurements) for ct, measurements in self.measurements.items()},
                'latest_status': self.assessments[-1].overall_status.value if self.assessments else 'unknown',
                'confidence_score': self.assessments[-1].confidence_score if self.assessments else 0.0
            }
            
            # Add analyzer statistics
            stats['drawdown_metrics'] = asdict(self.drawdown_analyzer.get_drawdown_metrics())
            stats['queue_metrics'] = asdict(self.queue_analyzer.get_queue_metrics())
            stats['latency_metrics'] = asdict(self.latency_analyzer.get_latency_metrics())
            
            return stats
    
    def assess_system_status(self) -> Dict[str, Any]:
        """Assess system status - alias for backward compatibility"""
        assessment = self.assess_criteria()
        return {
            'status': assessment.overall_status.value,
            'confidence': assessment.confidence_score,
            'violations': len(assessment.violations),
            'recommendations': len(assessment.recommendations),
            'timestamp': assessment.timestamp
        }

# Global criteria system
_criteria_system: Optional[GoNoGoCriteria] = None

def get_criteria_system() -> GoNoGoCriteria:
    """Get global criteria system instance"""
    global _criteria_system
    if _criteria_system is None:
        _criteria_system = GoNoGoCriteria()
    return _criteria_system

def get_go_nogo_criteria() -> GoNoGoCriteria:
    """Alias for get_criteria_system for backward compatibility"""
    return get_criteria_system()

def add_measurement(criteria_type: CriteriaType, value: float, 
                   metadata: Optional[Dict[str, Any]] = None) -> None:
    """Add a measurement to the criteria system"""
    system = get_criteria_system()
    system.add_measurement(criteria_type, value, metadata)

def assess_criteria() -> CriteriaAssessment:
    """Perform criteria assessment"""
    system = get_criteria_system()
    return system.assess_criteria()

def get_latest_assessment() -> Optional[CriteriaAssessment]:
    """Get latest criteria assessment"""
    system = get_criteria_system()
    return system.get_latest_assessment()

def get_criteria_statistics() -> Dict[str, Any]:
    """Get criteria statistics"""
    system = get_criteria_system()
    return system.get_criteria_statistics()

if __name__ == "__main__":
    # Example usage
    system = get_criteria_system()
    
    # Add some measurements
    add_measurement(CriteriaType.DRAWDOWN_STABILITY, 0.03)  # 3% drawdown
    add_measurement(CriteriaType.QUEUE_BACKPRESSURE, 0.15)  # 15% backpressure
    add_measurement(CriteriaType.LATENCY_P95, 150.0)  # 150ms p95 latency
    
    # Perform assessment
    assessment = assess_criteria()
    print(f"Overall status: {assessment.overall_status.value}")
    print(f"Confidence score: {assessment.confidence_score}")
    print(f"Violations: {len(assessment.violations)}")
    print(f"Recommendations: {assessment.recommendations}")
    
    # Get statistics
    stats = get_criteria_statistics()
    print(f"Statistics: {json.dumps(stats, indent=2)}")
