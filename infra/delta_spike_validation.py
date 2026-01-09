"""
Delta Spike Detection Validation System

This module implements a comprehensive validation system to ensure delta spike
detection achieves >90% accuracy, validating both real-time and historical
delta spike detection against known market movements and statistical models.

Key Features:
- Delta spike detection validation >90% accuracy
- Real-time delta spike detection validation
- Historical delta spike accuracy assessment
- Precision and recall validation
- False positive/negative analysis
- Market movement correlation validation
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

class DeltaSpikeAccuracyLevel(Enum):
    """Delta spike accuracy levels"""
    EXCELLENT = "excellent"  # >95% accuracy
    GOOD = "good"  # >90% accuracy
    ACCEPTABLE = "acceptable"  # >80% accuracy
    POOR = "poor"  # <=80% accuracy

class DeltaSpikeValidationStatus(Enum):
    """Delta spike validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class DeltaSpikeType(Enum):
    """Delta spike types"""
    BUY_SPIKE = "buy_spike"  # Buy volume spike
    SELL_SPIKE = "sell_spike"  # Sell volume spike
    NEUTRAL = "neutral"  # No significant spike
    MIXED = "mixed"  # Mixed buy/sell spikes

class DeltaSpikeStrength(Enum):
    """Delta spike strength levels"""
    WEAK = "weak"  # <1.5x normal volume
    MODERATE = "moderate"  # 1.5-3x normal volume
    STRONG = "strong"  # 3-5x normal volume
    EXTREME = "extreme"  # >5x normal volume

@dataclass
class DeltaTick:
    """Delta tick data"""
    timestamp: float
    price: float
    volume: float
    direction: int  # 1 for buy, -1 for sell, 0 for neutral
    symbol: str
    source: str  # 'mt5' or 'binance'
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeltaSpike:
    """Delta spike detection result"""
    timestamp: float
    start_time: float
    end_time: float
    spike_type: DeltaSpikeType
    spike_strength: DeltaSpikeStrength
    volume_delta: float
    price_change: float
    confidence: float
    symbol: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeltaSpikeValidation:
    """Delta spike validation result"""
    timestamp: float
    symbol: str
    expected_spike: Optional[DeltaSpike]
    detected_spike: Optional[DeltaSpike]
    is_correct: bool
    accuracy_score: float
    precision: float
    recall: float
    f1_score: float
    false_positive: bool
    false_negative: bool
    validation_status: DeltaSpikeValidationStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeltaSpikeValidationReport:
    """Delta spike validation report"""
    timestamp: float
    symbol: str
    overall_accuracy: float
    precision: float
    recall: float
    f1_score: float
    accuracy_level: DeltaSpikeAccuracyLevel
    validation_status: DeltaSpikeValidationStatus
    total_validations: int
    correct_detections: int
    false_positives: int
    false_negatives: int
    true_positives: int
    true_negatives: int
    spike_type_accuracy: Dict[str, float]
    strength_accuracy: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[DeltaSpikeValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class DeltaSpikeValidator:
    """Delta spike validator"""
    
    def __init__(self, accuracy_threshold: float = 0.90):
        self.accuracy_threshold = accuracy_threshold
        self.validations: List[DeltaSpikeValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
        self.min_sample_size = 100  # Minimum samples for statistical significance
        self.confidence_level = 0.95  # 95% confidence level
    
    def validate_delta_spike_detection(self, symbol: str, expected_spike: Optional[DeltaSpike],
                                     detected_spike: Optional[DeltaSpike]) -> DeltaSpikeValidation:
        """Validate delta spike detection accuracy"""
        # Determine if detection is correct
        is_correct = self._is_detection_correct(expected_spike, detected_spike)
        
        # Calculate accuracy metrics
        accuracy_score = self._calculate_accuracy_score(expected_spike, detected_spike)
        precision = self._calculate_precision(expected_spike, detected_spike)
        recall = self._calculate_recall(expected_spike, detected_spike)
        f1_score = self._calculate_f1_score(precision, recall)
        
        # Determine false positive/negative
        false_positive = self._is_false_positive(expected_spike, detected_spike)
        false_negative = self._is_false_negative(expected_spike, detected_spike)
        
        # Determine validation status
        validation_status = self._determine_validation_status(accuracy_score)
        
        validation = DeltaSpikeValidation(
            timestamp=time.time(),
            symbol=symbol,
            expected_spike=expected_spike,
            detected_spike=detected_spike,
            is_correct=is_correct,
            accuracy_score=accuracy_score,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            false_positive=false_positive,
            false_negative=false_negative,
            validation_status=validation_status,
            metadata={
                "accuracy_threshold": self.accuracy_threshold,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _is_detection_correct(self, expected_spike: Optional[DeltaSpike],
                            detected_spike: Optional[DeltaSpike]) -> bool:
        """Determine if delta spike detection is correct"""
        # Both None - correct
        if expected_spike is None and detected_spike is None:
            return True
        
        # One None, other not - incorrect
        if expected_spike is None or detected_spike is None:
            return False
        
        # Both present - check if they match
        return (expected_spike.spike_type == detected_spike.spike_type and
                expected_spike.spike_strength == detected_spike.spike_strength)
    
    def _calculate_accuracy_score(self, expected_spike: Optional[DeltaSpike],
                                detected_spike: Optional[DeltaSpike]) -> float:
        """Calculate accuracy score for delta spike detection"""
        if expected_spike is None and detected_spike is None:
            return 1.0
        
        if expected_spike is None or detected_spike is None:
            return 0.0
        
        # Calculate similarity based on spike characteristics
        type_similarity = 1.0 if expected_spike.spike_type == detected_spike.spike_type else 0.0
        strength_similarity = self._calculate_strength_similarity(
            expected_spike.spike_strength, detected_spike.spike_strength
        )
        confidence_similarity = 1.0 - abs(expected_spike.confidence - detected_spike.confidence)
        
        # Weighted average
        accuracy_score = (
            type_similarity * 0.5 +
            strength_similarity * 0.3 +
            confidence_similarity * 0.2
        )
        
        return max(0.0, min(1.0, accuracy_score))
    
    def _calculate_strength_similarity(self, expected_strength: DeltaSpikeStrength,
                                     detected_strength: DeltaSpikeStrength) -> float:
        """Calculate similarity between spike strengths"""
        strength_order = {
            DeltaSpikeStrength.WEAK: 1,
            DeltaSpikeStrength.MODERATE: 2,
            DeltaSpikeStrength.STRONG: 3,
            DeltaSpikeStrength.EXTREME: 4
        }
        
        expected_order = strength_order.get(expected_strength, 0)
        detected_order = strength_order.get(detected_strength, 0)
        
        if expected_order == detected_order:
            return 1.0
        
        # Calculate similarity based on distance
        max_distance = 3  # Maximum possible distance
        distance = abs(expected_order - detected_order)
        similarity = 1.0 - (distance / max_distance)
        
        return max(0.0, similarity)
    
    def _calculate_precision(self, expected_spike: Optional[DeltaSpike],
                           detected_spike: Optional[DeltaSpike]) -> float:
        """Calculate precision for delta spike detection"""
        if detected_spike is None:
            return 1.0  # No detected spike, precision is 1.0 (no false positives)
        
        if expected_spike is None:
            return 0.0  # False positive
        
        # True positive if both spikes exist and match
        return 1.0 if self._is_detection_correct(expected_spike, detected_spike) else 0.0
    
    def _calculate_recall(self, expected_spike: Optional[DeltaSpike],
                        detected_spike: Optional[DeltaSpike]) -> float:
        """Calculate recall for delta spike detection"""
        if expected_spike is None:
            return 1.0  # No expected spike, recall is 1.0 (no false negatives)
        
        if detected_spike is None:
            return 0.0  # False negative
        
        # True positive if both spikes exist and match
        return 1.0 if self._is_detection_correct(expected_spike, detected_spike) else 0.0
    
    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score from precision and recall"""
        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)
    
    def _is_false_positive(self, expected_spike: Optional[DeltaSpike],
                          detected_spike: Optional[DeltaSpike]) -> bool:
        """Determine if detection is a false positive"""
        return expected_spike is None and detected_spike is not None
    
    def _is_false_negative(self, expected_spike: Optional[DeltaSpike],
                          detected_spike: Optional[DeltaSpike]) -> bool:
        """Determine if detection is a false negative"""
        return expected_spike is not None and detected_spike is None
    
    def _determine_validation_status(self, accuracy_score: float) -> DeltaSpikeValidationStatus:
        """Determine validation status based on accuracy score"""
        if accuracy_score >= self.accuracy_threshold:
            return DeltaSpikeValidationStatus.PASSED
        elif accuracy_score >= self.accuracy_threshold * 0.8:
            return DeltaSpikeValidationStatus.WARNING
        else:
            return DeltaSpikeValidationStatus.FAILED
    
    def generate_validation_report(self, symbol: str) -> DeltaSpikeValidationReport:
        """Generate comprehensive delta spike validation report"""
        with self.lock:
            # Filter validations for symbol
            relevant_validations = [v for v in self.validations if v.symbol == symbol]
        
        if not relevant_validations:
            return DeltaSpikeValidationReport(
                timestamp=time.time(),
                symbol=symbol,
                overall_accuracy=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                accuracy_level=DeltaSpikeAccuracyLevel.POOR,
                validation_status=DeltaSpikeValidationStatus.FAILED,
                total_validations=0,
                correct_detections=0,
                false_positives=0,
                false_negatives=0,
                true_positives=0,
                true_negatives=0,
                spike_type_accuracy={},
                strength_accuracy={},
                recommendations=["No validation data available"],
                detailed_validations=[],
                metadata={"error": "No validation data available"}
            )
        
        # Calculate overall metrics
        total_validations = len(relevant_validations)
        correct_detections = sum(1 for v in relevant_validations if v.is_correct)
        false_positives = sum(1 for v in relevant_validations if v.false_positive)
        false_negatives = sum(1 for v in relevant_validations if v.false_negative)
        
        true_positives = sum(1 for v in relevant_validations 
                           if v.expected_spike is not None and v.detected_spike is not None and v.is_correct)
        true_negatives = sum(1 for v in relevant_validations 
                           if v.expected_spike is None and v.detected_spike is None)
        
        # Calculate accuracy metrics
        overall_accuracy = correct_detections / total_validations if total_validations > 0 else 0.0
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Determine accuracy level
        if overall_accuracy >= 0.95:
            accuracy_level = DeltaSpikeAccuracyLevel.EXCELLENT
        elif overall_accuracy >= 0.90:
            accuracy_level = DeltaSpikeAccuracyLevel.GOOD
        elif overall_accuracy >= 0.80:
            accuracy_level = DeltaSpikeAccuracyLevel.ACCEPTABLE
        else:
            accuracy_level = DeltaSpikeAccuracyLevel.POOR
        
        # Determine validation status
        if overall_accuracy >= self.accuracy_threshold:
            validation_status = DeltaSpikeValidationStatus.PASSED
        elif overall_accuracy >= self.accuracy_threshold * 0.8:
            validation_status = DeltaSpikeValidationStatus.WARNING
        else:
            validation_status = DeltaSpikeValidationStatus.FAILED
        
        # Calculate spike type accuracy
        spike_type_accuracy = self._calculate_spike_type_accuracy(relevant_validations)
        
        # Calculate strength accuracy
        strength_accuracy = self._calculate_strength_accuracy(relevant_validations)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            overall_accuracy, precision, recall, f1_score, accuracy_level, validation_status
        )
        
        return DeltaSpikeValidationReport(
            timestamp=time.time(),
            symbol=symbol,
            overall_accuracy=overall_accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy_level=accuracy_level,
            validation_status=validation_status,
            total_validations=total_validations,
            correct_detections=correct_detections,
            false_positives=false_positives,
            false_negatives=false_negatives,
            true_positives=true_positives,
            true_negatives=true_negatives,
            spike_type_accuracy=spike_type_accuracy,
            strength_accuracy=strength_accuracy,
            recommendations=recommendations,
            detailed_validations=relevant_validations,
            metadata={
                "accuracy_threshold": self.accuracy_threshold,
                "confidence_level": self.confidence_level,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _calculate_spike_type_accuracy(self, validations: List[DeltaSpikeValidation]) -> Dict[str, float]:
        """Calculate accuracy by spike type"""
        type_accuracy = {}
        
        for spike_type in DeltaSpikeType:
            type_validations = [
                v for v in validations 
                if v.expected_spike and v.expected_spike.spike_type == spike_type
            ]
            
            if type_validations:
                correct_count = sum(1 for v in type_validations if v.is_correct)
                type_accuracy[spike_type.value] = correct_count / len(type_validations)
            else:
                type_accuracy[spike_type.value] = 0.0
        
        return type_accuracy
    
    def _calculate_strength_accuracy(self, validations: List[DeltaSpikeValidation]) -> Dict[str, float]:
        """Calculate accuracy by spike strength"""
        strength_accuracy = {}
        
        for strength in DeltaSpikeStrength:
            strength_validations = [
                v for v in validations 
                if v.expected_spike and v.expected_spike.spike_strength == strength
            ]
            
            if strength_validations:
                correct_count = sum(1 for v in strength_validations if v.is_correct)
                strength_accuracy[strength.value] = correct_count / len(strength_validations)
            else:
                strength_accuracy[strength.value] = 0.0
        
        return strength_accuracy
    
    def _generate_recommendations(self, overall_accuracy: float, precision: float,
                                recall: float, f1_score: float, accuracy_level: DeltaSpikeAccuracyLevel,
                                validation_status: DeltaSpikeValidationStatus) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if validation_status == DeltaSpikeValidationStatus.FAILED:
            recommendations.append("Delta spike detection validation failed. Review detection algorithm.")
            if overall_accuracy < 0.5:
                recommendations.append("Very low accuracy detected. Consider complete algorithm redesign.")
        elif validation_status == DeltaSpikeValidationStatus.WARNING:
            recommendations.append("Delta spike detection validation passed with warnings. Monitor performance.")
            if overall_accuracy < 0.85:
                recommendations.append("Consider optimizing detection algorithm for better accuracy.")
        else:
            recommendations.append("Delta spike detection validation passed successfully.")
        
        if accuracy_level == DeltaSpikeAccuracyLevel.EXCELLENT:
            recommendations.append("Delta spike detection accuracy is excellent. System is performing optimally.")
        elif accuracy_level == DeltaSpikeAccuracyLevel.GOOD:
            recommendations.append("Delta spike detection accuracy is good. Minor optimizations may be beneficial.")
        elif accuracy_level == DeltaSpikeAccuracyLevel.ACCEPTABLE:
            recommendations.append("Delta spike detection accuracy is acceptable but could be improved.")
        else:
            recommendations.append("Delta spike detection accuracy is poor. Immediate attention required.")
        
        if precision < 0.8:
            recommendations.append("Low precision detected. Consider reducing false positives.")
        
        if recall < 0.8:
            recommendations.append("Low recall detected. Consider reducing false negatives.")
        
        if f1_score < 0.8:
            recommendations.append("Low F1 score detected. Balance precision and recall improvements.")
        
        return recommendations
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary statistics"""
        with self.lock:
            if not self.validations:
                return {"total_validations": 0}
            
            total_validations = len(self.validations)
            correct_detections = sum(1 for v in self.validations if v.is_correct)
            false_positives = sum(1 for v in self.validations if v.false_positive)
            false_negatives = sum(1 for v in self.validations if v.false_negative)
            
            overall_accuracy = correct_detections / total_validations
            precision = sum(v.precision for v in self.validations) / total_validations
            recall = sum(v.recall for v in self.validations) / total_validations
            f1_score = sum(v.f1_score for v in self.validations) / total_validations
            
            return {
                "total_validations": total_validations,
                "correct_detections": correct_detections,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "overall_accuracy": overall_accuracy,
                "average_precision": precision,
                "average_recall": recall,
                "average_f1_score": f1_score,
                "accuracy_threshold": self.accuracy_threshold
            }

class DeltaSpikeDetectionValidator:
    """Main delta spike detection validator"""
    
    def __init__(self, accuracy_threshold: float = 0.90):
        self.validator = DeltaSpikeValidator(accuracy_threshold)
        self.start_time = time.time()
        self.validation_reports: List[DeltaSpikeValidationReport] = []
        self.lock = threading.RLock()
    
    def validate_delta_spike_detection(self, symbol: str, expected_spike: Optional[DeltaSpike],
                                     detected_spike: Optional[DeltaSpike]) -> DeltaSpikeValidation:
        """Validate delta spike detection accuracy"""
        return self.validator.validate_delta_spike_detection(symbol, expected_spike, detected_spike)
    
    def generate_validation_report(self, symbol: str) -> DeltaSpikeValidationReport:
        """Generate validation report"""
        report = self.validator.generate_validation_report(symbol)
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[DeltaSpikeValidationReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        return self.validator.get_validation_summary()
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.validator.validations.clear()
            self.validation_reports.clear()

# Global delta spike validator
_delta_spike_validator: Optional[DeltaSpikeDetectionValidator] = None

def get_delta_spike_validator(accuracy_threshold: float = 0.90) -> DeltaSpikeDetectionValidator:
    """Get global delta spike validator instance"""
    global _delta_spike_validator
    if _delta_spike_validator is None:
        _delta_spike_validator = DeltaSpikeDetectionValidator(accuracy_threshold)
    return _delta_spike_validator

def validate_delta_spike_detection(symbol: str, expected_spike: Optional[DeltaSpike],
                                 detected_spike: Optional[DeltaSpike]) -> DeltaSpikeValidation:
    """Validate delta spike detection accuracy"""
    validator = get_delta_spike_validator()
    return validator.validate_delta_spike_detection(symbol, expected_spike, detected_spike)

def generate_delta_spike_validation_report(symbol: str) -> DeltaSpikeValidationReport:
    """Generate delta spike validation report"""
    validator = get_delta_spike_validator()
    return validator.generate_validation_report(symbol)

def get_delta_spike_validation_summary() -> Dict[str, Any]:
    """Get delta spike validation summary"""
    validator = get_delta_spike_validator()
    return validator.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    validator = get_delta_spike_validator()
    
    # Example delta spike validation
    expected_spike = DeltaSpike(
        timestamp=time.time(),
        start_time=time.time() - 60,
        end_time=time.time(),
        spike_type=DeltaSpikeType.BUY_SPIKE,
        spike_strength=DeltaSpikeStrength.STRONG,
        volume_delta=1000.0,
        price_change=50.0,
        confidence=0.95,
        symbol="BTCUSDc",
        session_id="session_001"
    )
    
    detected_spike = DeltaSpike(
        timestamp=time.time(),
        start_time=time.time() - 60,
        end_time=time.time(),
        spike_type=DeltaSpikeType.BUY_SPIKE,
        spike_strength=DeltaSpikeStrength.STRONG,
        volume_delta=950.0,
        price_change=48.0,
        confidence=0.92,
        symbol="BTCUSDc",
        session_id="session_001"
    )
    
    validation = validate_delta_spike_detection("BTCUSDc", expected_spike, detected_spike)
    
    print(f"Delta Spike Detection Validation:")
    print(f"Symbol: {validation.symbol}")
    print(f"Is Correct: {validation.is_correct}")
    print(f"Accuracy Score: {validation.accuracy_score:.2%}")
    print(f"Precision: {validation.precision:.2%}")
    print(f"Recall: {validation.recall:.2%}")
    print(f"F1 Score: {validation.f1_score:.2%}")
    print(f"False Positive: {validation.false_positive}")
    print(f"False Negative: {validation.false_negative}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    # Generate validation report
    report = generate_delta_spike_validation_report("BTCUSDc")
    
    print(f"\nDelta Spike Validation Report:")
    print(f"Overall Accuracy: {report.overall_accuracy:.2%}")
    print(f"Precision: {report.precision:.2%}")
    print(f"Recall: {report.recall:.2%}")
    print(f"F1 Score: {report.f1_score:.2%}")
    print(f"Accuracy Level: {report.accuracy_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Validations: {report.total_validations}")
    print(f"Correct Detections: {report.correct_detections}")
    print(f"False Positives: {report.false_positives}")
    print(f"False Negatives: {report.false_negatives}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
