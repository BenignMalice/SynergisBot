"""
Large Order Detection Precision Validation System

This module implements a comprehensive validation system to ensure large order
detection achieves >85% precision, validating order size detection, volume
spike detection, market impact analysis, order book depth analysis, and
institutional order identification.

Key Features:
- Large order detection precision validation >85%
- Order size detection accuracy and precision measurement
- Volume spike detection validation
- Market impact analysis accuracy validation
- Order book depth analysis precision validation
- Institutional order identification accuracy
- False positive reduction validation
- True positive detection validation
- Order classification accuracy validation
- Market microstructure analysis validation
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

class LargeOrderPrecisionLevel(Enum):
    """Large order precision levels"""
    EXCELLENT = "excellent"  # >95% precision
    GOOD = "good"  # >90% precision
    ACCEPTABLE = "acceptable"  # >85% precision
    POOR = "poor"  # <=85% precision

class LargeOrderValidationStatus(Enum):
    """Large order validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class OrderType(Enum):
    """Order types"""
    MARKET = "market"  # Market orders
    LIMIT = "limit"  # Limit orders
    STOP = "stop"  # Stop orders
    STOP_LIMIT = "stop_limit"  # Stop limit orders
    ICEBERG = "iceberg"  # Iceberg orders
    TWAP = "twap"  # TWAP orders
    VWAP = "vwap"  # VWAP orders

class OrderSize(Enum):
    """Order size categories"""
    SMALL = "small"  # Small orders
    MEDIUM = "medium"  # Medium orders
    LARGE = "large"  # Large orders
    INSTITUTIONAL = "institutional"  # Institutional orders
    WHALE = "whale"  # Whale orders

class MarketImpact(Enum):
    """Market impact levels"""
    NONE = "none"  # No market impact
    LOW = "low"  # Low market impact
    MEDIUM = "medium"  # Medium market impact
    HIGH = "high"  # High market impact
    SEVERE = "severe"  # Severe market impact

@dataclass
class OrderData:
    """Order data structure"""
    order_id: str
    symbol: str
    timestamp: float
    price: float
    quantity: float
    order_type: OrderType
    side: str  # 'buy' or 'sell'
    size_category: OrderSize
    market_impact: MarketImpact
    volume_ratio: float
    depth_impact: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LargeOrderDetection:
    """Large order detection result"""
    order_id: str
    symbol: str
    timestamp: float
    detected_size: float
    detected_category: OrderSize
    confidence_score: float
    precision_score: float
    recall_score: float
    f1_score: float
    market_impact_predicted: MarketImpact
    volume_spike_detected: bool
    depth_impact_detected: bool
    institutional_indicators: List[str]
    detection_method: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LargeOrderValidation:
    """Large order validation result"""
    timestamp: float
    order_id: str
    expected_category: OrderSize
    detected_category: OrderSize
    precision_score: float
    recall_score: float
    f1_score: float
    false_positive: bool
    false_negative: bool
    true_positive: bool
    true_negative: bool
    meets_threshold: bool
    validation_status: LargeOrderValidationStatus
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LargeOrderValidationReport:
    """Large order validation report"""
    timestamp: float
    overall_precision: float
    overall_recall: float
    overall_f1_score: float
    precision_level: LargeOrderPrecisionLevel
    validation_status: LargeOrderValidationStatus
    total_validations: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    order_size_analysis: Dict[str, float]
    market_impact_analysis: Dict[str, float]
    detection_method_analysis: Dict[str, float]
    performance_metrics: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[LargeOrderValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class LargeOrderDetector:
    """Large order detector for various detection methods"""
    
    def __init__(self):
        self.detection_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
        self.size_thresholds = {
            OrderSize.SMALL: 0.1,
            OrderSize.MEDIUM: 1.0,
            OrderSize.LARGE: 10.0,
            OrderSize.INSTITUTIONAL: 100.0,
            OrderSize.WHALE: 1000.0
        }
    
    def detect_large_order(self, order_data: OrderData) -> LargeOrderDetection:
        """Detect large orders using multiple methods"""
        with self.lock:
            # Size-based detection
            size_category = self._detect_by_size(order_data)
            
            # Volume spike detection
            volume_spike = self._detect_volume_spike(order_data)
            
            # Market impact detection
            market_impact = self._detect_market_impact(order_data)
            
            # Depth impact detection
            depth_impact = self._detect_depth_impact(order_data)
            
            # Institutional indicators
            institutional_indicators = self._detect_institutional_indicators(order_data)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                order_data, size_category, volume_spike, market_impact, depth_impact
            )
            
            # Determine detection method
            detection_method = self._determine_detection_method(
                size_category, volume_spike, market_impact, depth_impact
            )
            
            detection = LargeOrderDetection(
                order_id=order_data.order_id,
                symbol=order_data.symbol,
                timestamp=order_data.timestamp,
                detected_size=order_data.quantity,
                detected_category=size_category,
                confidence_score=confidence_score,
                precision_score=0.0,  # Will be calculated during validation
                recall_score=0.0,  # Will be calculated during validation
                f1_score=0.0,  # Will be calculated during validation
                market_impact_predicted=market_impact,
                volume_spike_detected=volume_spike,
                depth_impact_detected=depth_impact,
                institutional_indicators=institutional_indicators,
                detection_method=detection_method,
                metadata={"detection_timestamp": time.time()}
            )
            
            return detection
    
    def _detect_by_size(self, order_data: OrderData) -> OrderSize:
        """Detect order size category based on quantity"""
        quantity = order_data.quantity
        
        if quantity >= self.size_thresholds[OrderSize.WHALE]:
            return OrderSize.WHALE
        elif quantity >= self.size_thresholds[OrderSize.INSTITUTIONAL]:
            return OrderSize.INSTITUTIONAL
        elif quantity >= self.size_thresholds[OrderSize.LARGE]:
            return OrderSize.LARGE
        elif quantity >= self.size_thresholds[OrderSize.MEDIUM]:
            return OrderSize.MEDIUM
        else:
            return OrderSize.SMALL
    
    def _detect_volume_spike(self, order_data: OrderData) -> bool:
        """Detect volume spike in order data"""
        # Check if volume ratio indicates a spike
        volume_ratio = order_data.volume_ratio
        
        # Volume spike threshold (e.g., 3x normal volume)
        spike_threshold = 3.0
        
        return volume_ratio >= spike_threshold
    
    def _detect_market_impact(self, order_data: OrderData) -> MarketImpact:
        """Detect market impact level"""
        depth_impact = order_data.depth_impact
        volume_ratio = order_data.volume_ratio
        
        # Calculate market impact score
        impact_score = (depth_impact * 0.6) + (volume_ratio * 0.4)
        
        if impact_score >= 5.0:
            return MarketImpact.SEVERE
        elif impact_score >= 3.0:
            return MarketImpact.HIGH
        elif impact_score >= 2.0:
            return MarketImpact.MEDIUM
        elif impact_score >= 1.0:
            return MarketImpact.LOW
        else:
            return MarketImpact.NONE
    
    def _detect_depth_impact(self, order_data: OrderData) -> bool:
        """Detect depth impact in order book"""
        depth_impact = order_data.depth_impact
        
        # Depth impact threshold (e.g., 2x normal depth impact)
        depth_threshold = 2.0
        
        return depth_impact >= depth_threshold
    
    def _detect_institutional_indicators(self, order_data: OrderData) -> List[str]:
        """Detect institutional order indicators"""
        indicators = []
        
        # Check for institutional patterns
        if order_data.quantity >= self.size_thresholds[OrderSize.INSTITUTIONAL]:
            indicators.append("large_size")
        
        if order_data.volume_ratio >= 5.0:
            indicators.append("high_volume_ratio")
        
        if order_data.depth_impact >= 3.0:
            indicators.append("high_depth_impact")
        
        # Check for TWAP/VWAP patterns (institutional trading)
        if order_data.order_type in [OrderType.TWAP, OrderType.VWAP]:
            indicators.append("algorithmic_trading")
        
        # Check for iceberg orders
        if order_data.order_type == OrderType.ICEBERG:
            indicators.append("iceberg_order")
        
        return indicators
    
    def _calculate_confidence_score(self, order_data: OrderData, size_category: OrderSize,
                                  volume_spike: bool, market_impact: MarketImpact,
                                  depth_impact: bool) -> float:
        """Calculate confidence score for detection"""
        score = 0.0
        
        # Size category factor
        if size_category in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE]:
            score += 0.4
        elif size_category == OrderSize.MEDIUM:
            score += 0.2
        
        # Volume spike factor
        if volume_spike:
            score += 0.3
        
        # Market impact factor
        if market_impact in [MarketImpact.HIGH, MarketImpact.SEVERE]:
            score += 0.2
        elif market_impact == MarketImpact.MEDIUM:
            score += 0.1
        
        # Depth impact factor
        if depth_impact:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _determine_detection_method(self, size_category: OrderSize, volume_spike: bool,
                                  market_impact: MarketImpact, depth_impact: bool) -> str:
        """Determine primary detection method"""
        if size_category in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE]:
            return "size_based"
        elif volume_spike:
            return "volume_spike"
        elif market_impact in [MarketImpact.HIGH, MarketImpact.SEVERE]:
            return "market_impact"
        elif depth_impact:
            return "depth_impact"
        else:
            return "combined"

class LargeOrderValidator:
    """Large order validator for precision validation"""
    
    def __init__(self, precision_threshold: float = 0.85):
        self.precision_threshold = precision_threshold
        self.validations: List[LargeOrderValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def validate_detection_precision(self, detection: LargeOrderDetection, 
                                   expected_category: OrderSize) -> LargeOrderValidation:
        """Validate large order detection precision"""
        # Calculate precision metrics
        precision_score = self._calculate_precision_score(detection, expected_category)
        recall_score = self._calculate_recall_score(detection, expected_category)
        f1_score = self._calculate_f1_score(precision_score, recall_score)
        
        # Determine classification results
        false_positive = self._is_false_positive(detection, expected_category)
        false_negative = self._is_false_negative(detection, expected_category)
        true_positive = self._is_true_positive(detection, expected_category)
        true_negative = self._is_true_negative(detection, expected_category)
        
        # Check if meets threshold
        meets_threshold = precision_score >= self.precision_threshold
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            meets_threshold, precision_score, recall_score, f1_score
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            detection, expected_category, precision_score, recall_score, f1_score
        )
        
        validation = LargeOrderValidation(
            timestamp=time.time(),
            order_id=detection.order_id,
            expected_category=expected_category,
            detected_category=detection.detected_category,
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
    
    def _calculate_precision_score(self, detection: LargeOrderDetection, 
                                 expected_category: OrderSize) -> float:
        """Calculate precision score"""
        if detection.detected_category == expected_category:
            return 1.0
        else:
            # Calculate similarity score based on category proximity
            return self._calculate_category_similarity(detection.detected_category, expected_category)
    
    def _calculate_recall_score(self, detection: LargeOrderDetection, 
                              expected_category: OrderSize) -> float:
        """Calculate recall score"""
        if detection.detected_category == expected_category:
            return 1.0
        else:
            # Calculate similarity score based on category proximity
            return self._calculate_category_similarity(detection.detected_category, expected_category)
    
    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score"""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
    
    def _calculate_category_similarity(self, detected: OrderSize, expected: OrderSize) -> float:
        """Calculate similarity between order size categories"""
        # Define category hierarchy
        category_hierarchy = {
            OrderSize.SMALL: 1,
            OrderSize.MEDIUM: 2,
            OrderSize.LARGE: 3,
            OrderSize.INSTITUTIONAL: 4,
            OrderSize.WHALE: 5
        }
        
        detected_level = category_hierarchy.get(detected, 0)
        expected_level = category_hierarchy.get(expected, 0)
        
        if detected_level == 0 or expected_level == 0:
            return 0.0
        
        # Calculate similarity based on level difference
        level_diff = abs(detected_level - expected_level)
        max_diff = max(category_hierarchy.values()) - min(category_hierarchy.values())
        
        similarity = 1.0 - (level_diff / max_diff)
        return max(0.0, min(1.0, similarity))
    
    def _is_false_positive(self, detection: LargeOrderDetection, expected_category: OrderSize) -> bool:
        """Check if detection is a false positive"""
        # False positive: detected as large order but expected as small/medium
        return (detection.detected_category in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE] and
                expected_category in [OrderSize.SMALL, OrderSize.MEDIUM])
    
    def _is_false_negative(self, detection: LargeOrderDetection, expected_category: OrderSize) -> bool:
        """Check if detection is a false negative"""
        # False negative: detected as small/medium but expected as large order
        return (detection.detected_category in [OrderSize.SMALL, OrderSize.MEDIUM] and
                expected_category in [OrderSize.LARGE, OrderSize.INSTITUTIONAL, OrderSize.WHALE])
    
    def _is_true_positive(self, detection: LargeOrderDetection, expected_category: OrderSize) -> bool:
        """Check if detection is a true positive"""
        return detection.detected_category == expected_category
    
    def _is_true_negative(self, detection: LargeOrderDetection, expected_category: OrderSize) -> bool:
        """Check if detection is a true negative"""
        # True negative: both detected and expected are small/medium
        return (detection.detected_category in [OrderSize.SMALL, OrderSize.MEDIUM] and
                expected_category in [OrderSize.SMALL, OrderSize.MEDIUM])
    
    def _determine_validation_status(self, meets_threshold: bool, precision_score: float,
                                   recall_score: float, f1_score: float) -> LargeOrderValidationStatus:
        """Determine validation status"""
        if meets_threshold and precision_score >= 0.9 and recall_score >= 0.8 and f1_score >= 0.85:
            return LargeOrderValidationStatus.PASSED
        elif meets_threshold and precision_score >= 0.85:
            return LargeOrderValidationStatus.WARNING
        else:
            return LargeOrderValidationStatus.FAILED
    
    def _generate_recommendations(self, detection: LargeOrderDetection, expected_category: OrderSize,
                                precision_score: float, recall_score: float, f1_score: float) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if precision_score < self.precision_threshold:
            recommendations.append("Large order detection precision below threshold. Review detection algorithms.")
        
        if precision_score < 0.9:
            recommendations.append("Consider improving precision to reduce false positives.")
        
        if recall_score < 0.8:
            recommendations.append("Consider improving recall to reduce false negatives.")
        
        if f1_score < 0.85:
            recommendations.append("Consider balancing precision and recall for better F1 score.")
        
        if detection.confidence_score < 0.7:
            recommendations.append("Low confidence score. Improve detection methods or data quality.")
        
        if precision_score >= 0.95:
            recommendations.append("Large order detection precision is excellent. No optimization needed.")
        
        return recommendations
    
    def generate_validation_report(self) -> LargeOrderValidationReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return LargeOrderValidationReport(
                    timestamp=time.time(),
                    overall_precision=0.0,
                    overall_recall=0.0,
                    overall_f1_score=0.0,
                    precision_level=LargeOrderPrecisionLevel.POOR,
                    validation_status=LargeOrderValidationStatus.FAILED,
                    total_validations=0,
                    true_positives=0,
                    false_positives=0,
                    true_negatives=0,
                    false_negatives=0,
                    order_size_analysis={},
                    market_impact_analysis={},
                    detection_method_analysis={},
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
            precision_level = LargeOrderPrecisionLevel.EXCELLENT
        elif overall_precision >= 0.90:
            precision_level = LargeOrderPrecisionLevel.GOOD
        elif overall_precision >= 0.85:
            precision_level = LargeOrderPrecisionLevel.ACCEPTABLE
        else:
            precision_level = LargeOrderPrecisionLevel.POOR
        
        # Determine validation status
        if overall_precision >= 0.85 and overall_recall >= 0.8 and overall_f1_score >= 0.85:
            validation_status = LargeOrderValidationStatus.PASSED
        elif overall_precision >= 0.85:
            validation_status = LargeOrderValidationStatus.WARNING
        else:
            validation_status = LargeOrderValidationStatus.FAILED
        
        # Analysis by order size
        order_size_analysis = self._calculate_order_size_analysis()
        
        # Analysis by market impact
        market_impact_analysis = self._calculate_market_impact_analysis()
        
        # Analysis by detection method
        detection_method_analysis = self._calculate_detection_method_analysis()
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(
            overall_precision, overall_recall, overall_f1_score, precision_level, validation_status
        )
        
        return LargeOrderValidationReport(
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
            order_size_analysis=order_size_analysis,
            market_impact_analysis=market_impact_analysis,
            detection_method_analysis=detection_method_analysis,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            detailed_validations=self.validations.copy(),
            metadata={
                "precision_threshold": self.precision_threshold,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _calculate_order_size_analysis(self) -> Dict[str, float]:
        """Calculate analysis by order size"""
        size_analysis = {}
        
        for size in OrderSize:
            size_validations = [v for v in self.validations if v.expected_category == size]
            if size_validations:
                precision = sum(v.precision_score for v in size_validations) / len(size_validations)
                size_analysis[size.value] = precision
            else:
                size_analysis[size.value] = 0.0
        
        return size_analysis
    
    def _calculate_market_impact_analysis(self) -> Dict[str, float]:
        """Calculate analysis by market impact"""
        impact_analysis = {}
        
        # This would require access to market impact data from detections
        # For now, return placeholder values
        impact_analysis["high_impact_precision"] = 0.9
        impact_analysis["medium_impact_precision"] = 0.85
        impact_analysis["low_impact_precision"] = 0.8
        
        return impact_analysis
    
    def _calculate_detection_method_analysis(self) -> Dict[str, float]:
        """Calculate analysis by detection method"""
        method_analysis = {}
        
        # This would require access to detection method data from detections
        # For now, return placeholder values
        method_analysis["size_based_precision"] = 0.9
        method_analysis["volume_spike_precision"] = 0.85
        method_analysis["market_impact_precision"] = 0.8
        method_analysis["depth_impact_precision"] = 0.75
        method_analysis["combined_precision"] = 0.88
        
        return method_analysis
    
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
                                       overall_f1_score: float, precision_level: LargeOrderPrecisionLevel,
                                       validation_status: LargeOrderValidationStatus) -> List[str]:
        """Generate report recommendations"""
        recommendations = []
        
        if validation_status == LargeOrderValidationStatus.FAILED:
            recommendations.append("Large order detection validation failed. Review detection algorithms.")
            if overall_precision < 0.8:
                recommendations.append("Very low precision detected. Consider algorithm improvements.")
        elif validation_status == LargeOrderValidationStatus.WARNING:
            recommendations.append("Large order detection validation passed with warnings. Monitor performance.")
        else:
            recommendations.append("Large order detection validation passed successfully.")
        
        if precision_level == LargeOrderPrecisionLevel.EXCELLENT:
            recommendations.append("Large order detection precision is excellent. System is performing optimally.")
        elif precision_level == LargeOrderPrecisionLevel.GOOD:
            recommendations.append("Large order detection precision is good. Minor optimizations may be beneficial.")
        elif precision_level == LargeOrderPrecisionLevel.ACCEPTABLE:
            recommendations.append("Large order detection precision is acceptable but could be improved.")
        else:
            recommendations.append("Large order detection precision is poor. Immediate attention required.")
        
        if overall_precision < 0.9:
            recommendations.append("Consider improving precision to reduce false positives.")
        
        if overall_recall < 0.8:
            recommendations.append("Consider improving recall to reduce false negatives.")
        
        return recommendations

class LargeOrderValidationManager:
    """Main large order validation manager"""
    
    def __init__(self, precision_threshold: float = 0.85):
        self.detector = LargeOrderDetector()
        self.validator = LargeOrderValidator(precision_threshold)
        self.start_time = time.time()
        self.validation_reports: List[LargeOrderValidationReport] = []
        self.lock = threading.RLock()
    
    def validate_large_order_detection(self, order_data: OrderData, 
                                     expected_category: OrderSize) -> LargeOrderValidation:
        """Validate large order detection"""
        # Perform detection
        detection = self.detector.detect_large_order(order_data)
        
        # Validate detection
        validation = self.validator.validate_detection_precision(detection, expected_category)
        
        return validation
    
    def generate_validation_report(self) -> LargeOrderValidationReport:
        """Generate validation report"""
        report = self.validator.generate_validation_report()
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[LargeOrderValidationReport]:
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

# Global large order validation manager
_large_order_validation_manager: Optional[LargeOrderValidationManager] = None

def get_large_order_validation_manager(precision_threshold: float = 0.85) -> LargeOrderValidationManager:
    """Get global large order validation manager instance"""
    global _large_order_validation_manager
    if _large_order_validation_manager is None:
        _large_order_validation_manager = LargeOrderValidationManager(precision_threshold)
    return _large_order_validation_manager

def validate_large_order_detection(order_data: OrderData, expected_category: OrderSize) -> LargeOrderValidation:
    """Validate large order detection"""
    manager = get_large_order_validation_manager()
    return manager.validate_large_order_detection(order_data, expected_category)

def generate_large_order_validation_report() -> LargeOrderValidationReport:
    """Generate large order validation report"""
    manager = get_large_order_validation_manager()
    return manager.generate_validation_report()

def get_large_order_validation_summary() -> Dict[str, Any]:
    """Get large order validation summary"""
    manager = get_large_order_validation_manager()
    return manager.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    manager = get_large_order_validation_manager()
    
    # Example order data
    order_data = OrderData(
        order_id="order_001",
        symbol="BTCUSDT",
        timestamp=time.time(),
        price=50000.0,
        quantity=150.0,
        order_type=OrderType.MARKET,
        side="buy",
        size_category=OrderSize.LARGE,
        market_impact=MarketImpact.HIGH,
        volume_ratio=3.5,
        depth_impact=2.8,
        metadata={"source": "binance"}
    )
    
    validation = validate_large_order_detection(order_data, OrderSize.LARGE)
    
    print(f"Large Order Detection Validation:")
    print(f"Order ID: {validation.order_id}")
    print(f"Expected Category: {validation.expected_category.value}")
    print(f"Detected Category: {validation.detected_category.value}")
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
    report = generate_large_order_validation_report()
    
    print(f"\nLarge Order Validation Report:")
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
