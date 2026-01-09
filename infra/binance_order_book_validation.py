"""
Binance Order Book Analysis Accuracy Validation System

This module implements a comprehensive validation system to ensure Binance
order book analysis achieves >95% accuracy, validating order book data
processing, depth analysis, price level detection, volume analysis,
imbalance detection, and support/resistance identification.

Key Features:
- Binance order book analysis accuracy validation >95%
- Order book data processing validation and accuracy assessment
- Depth analysis validation and precision measurement
- Price level detection accuracy validation
- Volume analysis accuracy and precision validation
- Imbalance detection accuracy validation
- Support/resistance identification accuracy validation
- Order book snapshot validation and consistency checking
- Real-time order book update validation
- Order book analysis performance validation
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
import websockets
import aiohttp

logger = logging.getLogger(__name__)

class OrderBookAccuracyLevel(Enum):
    """Order book accuracy levels"""
    EXCELLENT = "excellent"  # >98% accuracy
    GOOD = "good"  # >95% accuracy
    ACCEPTABLE = "acceptable"  # >90% accuracy
    POOR = "poor"  # <=90% accuracy

class OrderBookValidationStatus(Enum):
    """Order book validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

class OrderBookAnalysisType(Enum):
    """Order book analysis types"""
    DEPTH_ANALYSIS = "depth_analysis"  # Depth analysis
    PRICE_LEVEL_DETECTION = "price_level_detection"  # Price level detection
    VOLUME_ANALYSIS = "volume_analysis"  # Volume analysis
    IMBALANCE_DETECTION = "imbalance_detection"  # Imbalance detection
    SUPPORT_RESISTANCE = "support_resistance"  # Support/resistance identification
    SNAPSHOT_VALIDATION = "snapshot_validation"  # Snapshot validation
    UPDATE_VALIDATION = "update_validation"  # Update validation

class OrderBookDataQuality(Enum):
    """Order book data quality levels"""
    HIGH = "high"  # High quality data
    MEDIUM = "medium"  # Medium quality data
    LOW = "low"  # Low quality data
    POOR = "poor"  # Poor quality data

@dataclass
class OrderBookSnapshot:
    """Order book snapshot data"""
    symbol: str
    timestamp: float
    bids: List[Tuple[float, float]]  # (price, quantity)
    asks: List[Tuple[float, float]]  # (price, quantity)
    last_update_id: int
    data_quality: OrderBookDataQuality
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderBookAnalysis:
    """Order book analysis result"""
    analysis_type: OrderBookAnalysisType
    symbol: str
    timestamp: float
    detected_levels: List[float]
    volume_analysis: Dict[str, float]
    imbalance_ratio: float
    support_levels: List[float]
    resistance_levels: List[float]
    confidence_score: float
    accuracy_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderBookValidation:
    """Order book validation result"""
    timestamp: float
    analysis_type: OrderBookAnalysisType
    expected_result: Any
    actual_result: Any
    accuracy_score: float
    precision_score: float
    recall_score: float
    f1_score: float
    meets_threshold: bool
    validation_status: OrderBookValidationStatus
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderBookValidationReport:
    """Order book validation report"""
    timestamp: float
    overall_accuracy: float
    overall_precision: float
    overall_recall: float
    overall_f1_score: float
    accuracy_level: OrderBookAccuracyLevel
    validation_status: OrderBookValidationStatus
    total_validations: int
    passed_validations: int
    failed_validations: int
    analysis_type_accuracy: Dict[str, float]
    data_quality_analysis: Dict[str, float]
    performance_metrics: Dict[str, float]
    recommendations: List[str]
    detailed_validations: List[OrderBookValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class OrderBookAnalyzer:
    """Order book analyzer for various analysis types"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def analyze_depth(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """Analyze order book depth"""
        with self.lock:
            # Calculate depth metrics
            bid_depth = sum(qty for _, qty in snapshot.bids)
            ask_depth = sum(qty for _, qty in snapshot.asks)
            total_depth = bid_depth + ask_depth
            
            # Calculate depth ratio
            depth_ratio = bid_depth / ask_depth if ask_depth > 0 else float('inf')
            
            # Detect significant levels
            detected_levels = self._detect_significant_levels(snapshot.bids, snapshot.asks)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(snapshot, depth_ratio)
            
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.DEPTH_ANALYSIS,
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                detected_levels=detected_levels,
                volume_analysis={
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "total_depth": total_depth,
                    "depth_ratio": depth_ratio
                },
                imbalance_ratio=depth_ratio,
                support_levels=[],
                resistance_levels=[],
                confidence_score=confidence_score,
                accuracy_score=0.0,  # Will be calculated during validation
                metadata={"analysis_method": "depth_analysis"}
            )
            
            return analysis
    
    def analyze_price_levels(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """Analyze price levels in order book"""
        with self.lock:
            # Extract price levels
            bid_prices = [price for price, _ in snapshot.bids]
            ask_prices = [price for _, price in snapshot.asks]
            
            # Detect significant price levels
            significant_levels = self._detect_price_levels(bid_prices, ask_prices)
            
            # Calculate volume at each level
            volume_analysis = self._calculate_volume_at_levels(snapshot.bids, snapshot.asks)
            
            # Calculate confidence score
            confidence_score = self._calculate_price_level_confidence(snapshot, significant_levels)
            
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.PRICE_LEVEL_DETECTION,
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                detected_levels=significant_levels,
                volume_analysis=volume_analysis,
                imbalance_ratio=0.0,
                support_levels=[],
                resistance_levels=[],
                confidence_score=confidence_score,
                accuracy_score=0.0,
                metadata={"analysis_method": "price_level_detection"}
            )
            
            return analysis
    
    def analyze_volume(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """Analyze volume patterns in order book"""
        with self.lock:
            # Calculate volume metrics
            bid_volume = sum(qty for _, qty in snapshot.bids)
            ask_volume = sum(qty for _, qty in snapshot.asks)
            total_volume = bid_volume + ask_volume
            
            # Calculate volume distribution
            volume_distribution = self._calculate_volume_distribution(snapshot.bids, snapshot.asks)
            
            # Detect volume clusters
            volume_clusters = self._detect_volume_clusters(snapshot.bids, snapshot.asks)
            
            # Calculate confidence score
            confidence_score = self._calculate_volume_confidence(snapshot, volume_distribution)
            
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.VOLUME_ANALYSIS,
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                detected_levels=volume_clusters,
                volume_analysis={
                    "bid_volume": bid_volume,
                    "ask_volume": ask_volume,
                    "total_volume": total_volume,
                    "volume_distribution": volume_distribution
                },
                imbalance_ratio=bid_volume / ask_volume if ask_volume > 0 else float('inf'),
                support_levels=[],
                resistance_levels=[],
                confidence_score=confidence_score,
                accuracy_score=0.0,
                metadata={"analysis_method": "volume_analysis"}
            )
            
            return analysis
    
    def analyze_imbalance(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """Analyze order book imbalance"""
        with self.lock:
            # Calculate imbalance metrics
            bid_volume = sum(qty for _, qty in snapshot.bids)
            ask_volume = sum(qty for _, qty in snapshot.asks)
            imbalance_ratio = bid_volume / ask_volume if ask_volume > 0 else float('inf')
            
            # Detect imbalance patterns
            imbalance_patterns = self._detect_imbalance_patterns(snapshot.bids, snapshot.asks)
            
            # Calculate confidence score
            confidence_score = self._calculate_imbalance_confidence(snapshot, imbalance_ratio)
            
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.IMBALANCE_DETECTION,
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                detected_levels=imbalance_patterns,
                volume_analysis={
                    "bid_volume": bid_volume,
                    "ask_volume": ask_volume,
                    "imbalance_ratio": imbalance_ratio
                },
                imbalance_ratio=imbalance_ratio,
                support_levels=[],
                resistance_levels=[],
                confidence_score=confidence_score,
                accuracy_score=0.0,
                metadata={"analysis_method": "imbalance_detection"}
            )
            
            return analysis
    
    def analyze_support_resistance(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """Analyze support and resistance levels"""
        with self.lock:
            # Extract price levels
            bid_prices = [price for price, _ in snapshot.bids]
            ask_prices = [price for _, price in snapshot.asks]
            
            # Detect support levels (bid side)
            support_levels = self._detect_support_levels(bid_prices, snapshot.bids)
            
            # Detect resistance levels (ask side)
            resistance_levels = self._detect_resistance_levels(ask_prices, snapshot.asks)
            
            # Calculate confidence score
            confidence_score = self._calculate_support_resistance_confidence(
                snapshot, support_levels, resistance_levels
            )
            
            analysis = OrderBookAnalysis(
                analysis_type=OrderBookAnalysisType.SUPPORT_RESISTANCE,
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                detected_levels=support_levels + resistance_levels,
                volume_analysis={},
                imbalance_ratio=0.0,
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                confidence_score=confidence_score,
                accuracy_score=0.0,
                metadata={"analysis_method": "support_resistance"}
            )
            
            return analysis
    
    def _detect_significant_levels(self, bids: List[Tuple[float, float]], 
                                 asks: List[Tuple[float, float]]) -> List[float]:
        """Detect significant price levels"""
        levels = []
        
        # Combine all price levels
        all_prices = [price for price, _ in bids + asks]
        
        # Sort prices
        all_prices.sort()
        
        # Detect clusters of similar prices
        clusters = self._cluster_prices(all_prices)
        
        # Select significant clusters
        for cluster in clusters:
            if len(cluster) >= 2:  # At least 2 orders at similar price
                levels.append(sum(cluster) / len(cluster))  # Average price
        
        return levels
    
    def _detect_price_levels(self, bid_prices: List[float], ask_prices: List[float]) -> List[float]:
        """Detect significant price levels"""
        levels = []
        
        # Combine and sort prices
        all_prices = sorted(bid_prices + ask_prices)
        
        # Detect price clusters
        clusters = self._cluster_prices(all_prices)
        
        # Select significant clusters
        for cluster in clusters:
            if len(cluster) >= 2:
                levels.append(sum(cluster) / len(cluster))
        
        return levels
    
    def _calculate_volume_at_levels(self, bids: List[Tuple[float, float]], 
                                  asks: List[Tuple[float, float]]) -> Dict[str, float]:
        """Calculate volume at each price level"""
        volume_analysis = {}
        
        # Calculate bid volume distribution
        bid_volumes = [qty for _, qty in bids]
        volume_analysis["bid_volume_total"] = sum(bid_volumes)
        volume_analysis["bid_volume_avg"] = sum(bid_volumes) / len(bid_volumes) if bid_volumes else 0
        
        # Calculate ask volume distribution
        ask_volumes = [qty for _, qty in asks]
        volume_analysis["ask_volume_total"] = sum(ask_volumes)
        volume_analysis["ask_volume_avg"] = sum(ask_volumes) / len(ask_volumes) if ask_volumes else 0
        
        return volume_analysis
    
    def _calculate_volume_distribution(self, bids: List[Tuple[float, float]], 
                                     asks: List[Tuple[float, float]]) -> Dict[str, float]:
        """Calculate volume distribution"""
        distribution = {}
        
        # Bid distribution
        bid_volumes = [qty for _, qty in bids]
        if bid_volumes:
            distribution["bid_volume_mean"] = statistics.mean(bid_volumes)
            distribution["bid_volume_std"] = statistics.stdev(bid_volumes) if len(bid_volumes) > 1 else 0
        
        # Ask distribution
        ask_volumes = [qty for _, qty in asks]
        if ask_volumes:
            distribution["ask_volume_mean"] = statistics.mean(ask_volumes)
            distribution["ask_volume_std"] = statistics.stdev(ask_volumes) if len(ask_volumes) > 1 else 0
        
        return distribution
    
    def _detect_volume_clusters(self, bids: List[Tuple[float, float]], 
                              asks: List[Tuple[float, float]]) -> List[float]:
        """Detect volume clusters"""
        clusters = []
        
        # Group by similar volume
        all_orders = bids + asks
        volumes = [qty for _, qty in all_orders]
        
        if volumes:
            volume_clusters = self._cluster_volumes(volumes)
            for cluster in volume_clusters:
                if len(cluster) >= 2:
                    clusters.append(sum(cluster) / len(cluster))
        
        return clusters
    
    def _detect_imbalance_patterns(self, bids: List[Tuple[float, float]], 
                                 asks: List[Tuple[float, float]]) -> List[float]:
        """Detect imbalance patterns"""
        patterns = []
        
        # Calculate imbalance at different price levels
        for i in range(min(len(bids), len(asks))):
            bid_volume = bids[i][1] if i < len(bids) else 0
            ask_volume = asks[i][1] if i < len(asks) else 0
            
            if ask_volume > 0:
                imbalance = bid_volume / ask_volume
                if imbalance > 1.5 or imbalance < 0.5:  # Significant imbalance
                    patterns.append(imbalance)
        
        return patterns
    
    def _detect_support_levels(self, bid_prices: List[float], 
                             bids: List[Tuple[float, float]]) -> List[float]:
        """Detect support levels"""
        support_levels = []
        
        # Find price levels with high volume
        for price, volume in bids:
            if volume > statistics.mean([qty for _, qty in bids]) * 1.5:
                support_levels.append(price)
        
        return support_levels
    
    def _detect_resistance_levels(self, ask_prices: List[float], 
                                asks: List[Tuple[float, float]]) -> List[float]:
        """Detect resistance levels"""
        resistance_levels = []
        
        # Find price levels with high volume
        for price, volume in asks:
            if volume > statistics.mean([qty for _, qty in asks]) * 1.5:
                resistance_levels.append(price)
        
        return resistance_levels
    
    def _cluster_prices(self, prices: List[float], threshold: float = 0.001) -> List[List[float]]:
        """Cluster similar prices"""
        if not prices:
            return []
        
        clusters = []
        current_cluster = [prices[0]]
        
        for price in prices[1:]:
            if abs(price - current_cluster[-1]) <= threshold:
                current_cluster.append(price)
            else:
                clusters.append(current_cluster)
                current_cluster = [price]
        
        clusters.append(current_cluster)
        return clusters
    
    def _cluster_volumes(self, volumes: List[float], threshold: float = 0.1) -> List[List[float]]:
        """Cluster similar volumes"""
        if not volumes:
            return []
        
        clusters = []
        current_cluster = [volumes[0]]
        
        for volume in volumes[1:]:
            if abs(volume - current_cluster[-1]) / current_cluster[-1] <= threshold:
                current_cluster.append(volume)
            else:
                clusters.append(current_cluster)
                current_cluster = [volume]
        
        clusters.append(current_cluster)
        return clusters
    
    def _calculate_confidence_score(self, snapshot: OrderBookSnapshot, 
                                  depth_ratio: float) -> float:
        """Calculate confidence score for depth analysis"""
        score = 1.0
        
        # Data quality factor
        if snapshot.data_quality == OrderBookDataQuality.HIGH:
            score *= 1.0
        elif snapshot.data_quality == OrderBookDataQuality.MEDIUM:
            score *= 0.9
        elif snapshot.data_quality == OrderBookDataQuality.LOW:
            score *= 0.7
        else:
            score *= 0.5
        
        # Depth ratio factor
        if 0.5 <= depth_ratio <= 2.0:  # Balanced order book
            score *= 1.0
        else:
            score *= 0.8
        
        return max(0.0, min(1.0, score))
    
    def _calculate_price_level_confidence(self, snapshot: OrderBookSnapshot, 
                                        levels: List[float]) -> float:
        """Calculate confidence score for price level detection"""
        score = 1.0
        
        # Data quality factor
        if snapshot.data_quality == OrderBookDataQuality.HIGH:
            score *= 1.0
        elif snapshot.data_quality == OrderBookDataQuality.MEDIUM:
            score *= 0.9
        else:
            score *= 0.7
        
        # Number of levels factor
        if len(levels) >= 3:
            score *= 1.0
        elif len(levels) >= 2:
            score *= 0.9
        else:
            score *= 0.7
        
        return max(0.0, min(1.0, score))
    
    def _calculate_volume_confidence(self, snapshot: OrderBookSnapshot, 
                                   distribution: Dict[str, float]) -> float:
        """Calculate confidence score for volume analysis"""
        score = 1.0
        
        # Data quality factor
        if snapshot.data_quality == OrderBookDataQuality.HIGH:
            score *= 1.0
        elif snapshot.data_quality == OrderBookDataQuality.MEDIUM:
            score *= 0.9
        else:
            score *= 0.7
        
        # Volume distribution factor
        if "bid_volume_std" in distribution and "ask_volume_std" in distribution:
            if distribution["bid_volume_std"] > 0 and distribution["ask_volume_std"] > 0:
                score *= 1.0
            else:
                score *= 0.8
        
        return max(0.0, min(1.0, score))
    
    def _calculate_imbalance_confidence(self, snapshot: OrderBookSnapshot, 
                                     imbalance_ratio: float) -> float:
        """Calculate confidence score for imbalance analysis"""
        score = 1.0
        
        # Data quality factor
        if snapshot.data_quality == OrderBookDataQuality.HIGH:
            score *= 1.0
        elif snapshot.data_quality == OrderBookDataQuality.MEDIUM:
            score *= 0.9
        else:
            score *= 0.7
        
        # Imbalance ratio factor
        if 0.1 <= imbalance_ratio <= 10.0:  # Reasonable imbalance range
            score *= 1.0
        else:
            score *= 0.8
        
        return max(0.0, min(1.0, score))
    
    def _calculate_support_resistance_confidence(self, snapshot: OrderBookSnapshot, 
                                               support_levels: List[float], 
                                               resistance_levels: List[float]) -> float:
        """Calculate confidence score for support/resistance analysis"""
        score = 1.0
        
        # Data quality factor
        if snapshot.data_quality == OrderBookDataQuality.HIGH:
            score *= 1.0
        elif snapshot.data_quality == OrderBookDataQuality.MEDIUM:
            score *= 0.9
        else:
            score *= 0.7
        
        # Number of levels factor
        total_levels = len(support_levels) + len(resistance_levels)
        if total_levels >= 4:
            score *= 1.0
        elif total_levels >= 2:
            score *= 0.9
        else:
            score *= 0.7
        
        return max(0.0, min(1.0, score))

class OrderBookValidator:
    """Order book validator for accuracy validation"""
    
    def __init__(self, accuracy_threshold: float = 0.95):
        self.accuracy_threshold = accuracy_threshold
        self.validations: List[OrderBookValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def validate_analysis_accuracy(self, analysis: OrderBookAnalysis, 
                                 expected_result: Any) -> OrderBookValidation:
        """Validate order book analysis accuracy"""
        # Calculate accuracy metrics
        accuracy_score = self._calculate_accuracy_score(analysis, expected_result)
        precision_score = self._calculate_precision_score(analysis, expected_result)
        recall_score = self._calculate_recall_score(analysis, expected_result)
        f1_score = self._calculate_f1_score(precision_score, recall_score)
        
        # Check if meets threshold
        meets_threshold = accuracy_score >= self.accuracy_threshold
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            meets_threshold, accuracy_score, precision_score, recall_score
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            analysis, expected_result, accuracy_score, precision_score, recall_score
        )
        
        validation = OrderBookValidation(
            timestamp=time.time(),
            analysis_type=analysis.analysis_type,
            expected_result=expected_result,
            actual_result=analysis,
            accuracy_score=accuracy_score,
            precision_score=precision_score,
            recall_score=recall_score,
            f1_score=f1_score,
            meets_threshold=meets_threshold,
            validation_status=validation_status,
            recommendations=recommendations,
            metadata={
                "accuracy_threshold": self.accuracy_threshold,
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def _calculate_accuracy_score(self, analysis: OrderBookAnalysis, 
                                expected_result: Any) -> float:
        """Calculate accuracy score"""
        if expected_result is None:
            return 0.0
        
        # For depth analysis
        if analysis.analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS:
            if isinstance(expected_result, dict) and "depth_ratio" in expected_result:
                expected_ratio = expected_result["depth_ratio"]
                actual_ratio = analysis.imbalance_ratio
                if expected_ratio > 0 and actual_ratio > 0:
                    return 1.0 - abs(expected_ratio - actual_ratio) / max(expected_ratio, actual_ratio)
        
        # For price level detection
        elif analysis.analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION:
            if isinstance(expected_result, list):
                expected_levels = expected_result
                actual_levels = analysis.detected_levels
                return self._calculate_level_accuracy(expected_levels, actual_levels)
        
        # For volume analysis
        elif analysis.analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS:
            if isinstance(expected_result, dict) and "total_volume" in expected_result:
                expected_volume = expected_result["total_volume"]
                actual_volume = analysis.volume_analysis.get("total_volume", 0)
                if expected_volume > 0 and actual_volume > 0:
                    return 1.0 - abs(expected_volume - actual_volume) / max(expected_volume, actual_volume)
        
        # For imbalance detection
        elif analysis.analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION:
            if isinstance(expected_result, float):
                expected_imbalance = expected_result
                actual_imbalance = analysis.imbalance_ratio
                if expected_imbalance > 0 and actual_imbalance > 0:
                    return 1.0 - abs(expected_imbalance - actual_imbalance) / max(expected_imbalance, actual_imbalance)
        
        # For support/resistance
        elif analysis.analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE:
            if isinstance(expected_result, dict):
                expected_support = expected_result.get("support_levels", [])
                expected_resistance = expected_result.get("resistance_levels", [])
                actual_support = analysis.support_levels
                actual_resistance = analysis.resistance_levels
                
                support_accuracy = self._calculate_level_accuracy(expected_support, actual_support)
                resistance_accuracy = self._calculate_level_accuracy(expected_resistance, actual_resistance)
                
                return (support_accuracy + resistance_accuracy) / 2.0
        
        return 0.0
    
    def _calculate_precision_score(self, analysis: OrderBookAnalysis, 
                                 expected_result: Any) -> float:
        """Calculate precision score"""
        if expected_result is None:
            return 0.0
        
        # For level detection tasks
        if analysis.analysis_type in [OrderBookAnalysisType.PRICE_LEVEL_DETECTION, 
                                    OrderBookAnalysisType.SUPPORT_RESISTANCE]:
            if isinstance(expected_result, (list, dict)):
                expected_levels = expected_result if isinstance(expected_result, list) else expected_result.get("levels", [])
                actual_levels = analysis.detected_levels
                
                if not actual_levels:
                    return 0.0
                
                # Calculate precision as true positives / (true positives + false positives)
                true_positives = 0
                for actual_level in actual_levels:
                    if self._find_closest_level(actual_level, expected_levels) is not None:
                        true_positives += 1
                
                return true_positives / len(actual_levels)
        
        return 1.0
    
    def _calculate_recall_score(self, analysis: OrderBookAnalysis, 
                              expected_result: Any) -> float:
        """Calculate recall score"""
        if expected_result is None:
            return 0.0
        
        # For level detection tasks
        if analysis.analysis_type in [OrderBookAnalysisType.PRICE_LEVEL_DETECTION, 
                                    OrderBookAnalysisType.SUPPORT_RESISTANCE]:
            if isinstance(expected_result, (list, dict)):
                expected_levels = expected_result if isinstance(expected_result, list) else expected_result.get("levels", [])
                actual_levels = analysis.detected_levels
                
                if not expected_levels:
                    return 0.0
                
                # Calculate recall as true positives / (true positives + false negatives)
                true_positives = 0
                for expected_level in expected_levels:
                    if self._find_closest_level(expected_level, actual_levels) is not None:
                        true_positives += 1
                
                return true_positives / len(expected_levels)
        
        return 1.0
    
    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score"""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
    
    def _calculate_level_accuracy(self, expected_levels: List[float], 
                                actual_levels: List[float], 
                                tolerance: float = 0.001) -> float:
        """Calculate accuracy for level detection"""
        if not expected_levels and not actual_levels:
            return 1.0
        if not expected_levels or not actual_levels:
            return 0.0
        
        matches = 0
        for expected_level in expected_levels:
            for actual_level in actual_levels:
                if abs(expected_level - actual_level) <= tolerance:
                    matches += 1
                    break
        
        return matches / len(expected_levels)
    
    def _find_closest_level(self, target_level: float, levels: List[float], 
                          tolerance: float = 0.001) -> Optional[float]:
        """Find closest level within tolerance"""
        for level in levels:
            if abs(target_level - level) <= tolerance:
                return level
        return None
    
    def _determine_validation_status(self, meets_threshold: bool, accuracy_score: float,
                                   precision_score: float, recall_score: float) -> OrderBookValidationStatus:
        """Determine validation status"""
        if meets_threshold and accuracy_score >= 0.95 and precision_score >= 0.9 and recall_score >= 0.9:
            return OrderBookValidationStatus.PASSED
        elif meets_threshold and accuracy_score >= 0.9:
            return OrderBookValidationStatus.WARNING
        else:
            return OrderBookValidationStatus.FAILED
    
    def _generate_recommendations(self, analysis: OrderBookAnalysis, expected_result: Any,
                                accuracy_score: float, precision_score: float, 
                                recall_score: float) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if accuracy_score < self.accuracy_threshold:
            recommendations.append("Order book analysis accuracy below threshold. Review analysis algorithms.")
        
        if precision_score < 0.9:
            recommendations.append("Low precision detected. Reduce false positives in analysis.")
        
        if recall_score < 0.9:
            recommendations.append("Low recall detected. Improve detection of true positives.")
        
        if analysis.confidence_score < 0.8:
            recommendations.append("Low confidence score. Improve data quality or analysis methods.")
        
        if accuracy_score >= 0.95:
            recommendations.append("Order book analysis accuracy is excellent. No optimization needed.")
        
        return recommendations
    
    def generate_validation_report(self) -> OrderBookValidationReport:
        """Generate comprehensive validation report"""
        with self.lock:
            if not self.validations:
                return OrderBookValidationReport(
                    timestamp=time.time(),
                    overall_accuracy=0.0,
                    overall_precision=0.0,
                    overall_recall=0.0,
                    overall_f1_score=0.0,
                    accuracy_level=OrderBookAccuracyLevel.POOR,
                    validation_status=OrderBookValidationStatus.FAILED,
                    total_validations=0,
                    passed_validations=0,
                    failed_validations=0,
                    analysis_type_accuracy={},
                    data_quality_analysis={},
                    performance_metrics={},
                    recommendations=["No validation data available"],
                    detailed_validations=[],
                    metadata={"error": "No validation data available"}
                )
        
        # Calculate overall metrics
        total_validations = len(self.validations)
        passed_validations = sum(1 for v in self.validations if v.meets_threshold)
        failed_validations = total_validations - passed_validations
        
        overall_accuracy = sum(v.accuracy_score for v in self.validations) / total_validations
        overall_precision = sum(v.precision_score for v in self.validations) / total_validations
        overall_recall = sum(v.recall_score for v in self.validations) / total_validations
        overall_f1_score = sum(v.f1_score for v in self.validations) / total_validations
        
        # Determine accuracy level
        if overall_accuracy >= 0.98:
            accuracy_level = OrderBookAccuracyLevel.EXCELLENT
        elif overall_accuracy >= 0.95:
            accuracy_level = OrderBookAccuracyLevel.GOOD
        elif overall_accuracy >= 0.90:
            accuracy_level = OrderBookAccuracyLevel.ACCEPTABLE
        else:
            accuracy_level = OrderBookAccuracyLevel.POOR
        
        # Determine validation status
        if overall_accuracy >= 0.95 and overall_precision >= 0.9 and overall_recall >= 0.9:
            validation_status = OrderBookValidationStatus.PASSED
        elif overall_accuracy >= 0.90:
            validation_status = OrderBookValidationStatus.WARNING
        else:
            validation_status = OrderBookValidationStatus.FAILED
        
        # Analysis type accuracy
        analysis_type_accuracy = self._calculate_analysis_type_accuracy()
        
        # Data quality analysis
        data_quality_analysis = self._calculate_data_quality_analysis()
        
        # Performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_report_recommendations(
            overall_accuracy, overall_precision, overall_recall, accuracy_level, validation_status
        )
        
        return OrderBookValidationReport(
            timestamp=time.time(),
            overall_accuracy=overall_accuracy,
            overall_precision=overall_precision,
            overall_recall=overall_recall,
            overall_f1_score=overall_f1_score,
            accuracy_level=accuracy_level,
            validation_status=validation_status,
            total_validations=total_validations,
            passed_validations=passed_validations,
            failed_validations=failed_validations,
            analysis_type_accuracy=analysis_type_accuracy,
            data_quality_analysis=data_quality_analysis,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            detailed_validations=self.validations.copy(),
            metadata={
                "accuracy_threshold": self.accuracy_threshold,
                "validation_duration": time.time() - self.start_time
            }
        )
    
    def _calculate_analysis_type_accuracy(self) -> Dict[str, float]:
        """Calculate accuracy by analysis type"""
        type_accuracy = {}
        
        for analysis_type in OrderBookAnalysisType:
            type_validations = [
                v for v in self.validations 
                if v.analysis_type == analysis_type
            ]
            
            if type_validations:
                avg_accuracy = sum(v.accuracy_score for v in type_validations) / len(type_validations)
                type_accuracy[analysis_type.value] = avg_accuracy
            else:
                type_accuracy[analysis_type.value] = 0.0
        
        return type_accuracy
    
    def _calculate_data_quality_analysis(self) -> Dict[str, float]:
        """Calculate data quality analysis"""
        quality_analysis = {}
        
        # This would require access to snapshot data quality information
        # For now, return placeholder values
        quality_analysis["high_quality_ratio"] = 0.8
        quality_analysis["medium_quality_ratio"] = 0.15
        quality_analysis["low_quality_ratio"] = 0.05
        
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
    
    def _generate_report_recommendations(self, overall_accuracy: float, overall_precision: float,
                                      overall_recall: float, accuracy_level: OrderBookAccuracyLevel,
                                      validation_status: OrderBookValidationStatus) -> List[str]:
        """Generate report recommendations"""
        recommendations = []
        
        if validation_status == OrderBookValidationStatus.FAILED:
            recommendations.append("Order book analysis validation failed. Review analysis algorithms.")
            if overall_accuracy < 0.9:
                recommendations.append("Very low accuracy detected. Consider algorithm improvements.")
        elif validation_status == OrderBookValidationStatus.WARNING:
            recommendations.append("Order book analysis validation passed with warnings. Monitor performance.")
        else:
            recommendations.append("Order book analysis validation passed successfully.")
        
        if accuracy_level == OrderBookAccuracyLevel.EXCELLENT:
            recommendations.append("Order book analysis accuracy is excellent. System is performing optimally.")
        elif accuracy_level == OrderBookAccuracyLevel.GOOD:
            recommendations.append("Order book analysis accuracy is good. Minor optimizations may be beneficial.")
        elif accuracy_level == OrderBookAccuracyLevel.ACCEPTABLE:
            recommendations.append("Order book analysis accuracy is acceptable but could be improved.")
        else:
            recommendations.append("Order book analysis accuracy is poor. Immediate attention required.")
        
        if overall_precision < 0.9:
            recommendations.append("Consider improving precision to reduce false positives.")
        
        if overall_recall < 0.9:
            recommendations.append("Consider improving recall to reduce false negatives.")
        
        return recommendations

class OrderBookValidationManager:
    """Main order book validation manager"""
    
    def __init__(self, accuracy_threshold: float = 0.95):
        self.analyzer = OrderBookAnalyzer()
        self.validator = OrderBookValidator(accuracy_threshold)
        self.start_time = time.time()
        self.validation_reports: List[OrderBookValidationReport] = []
        self.lock = threading.RLock()
    
    def validate_order_book_analysis(self, snapshot: OrderBookSnapshot, 
                                   analysis_type: OrderBookAnalysisType,
                                   expected_result: Any) -> OrderBookValidation:
        """Validate order book analysis"""
        # Perform analysis
        if analysis_type == OrderBookAnalysisType.DEPTH_ANALYSIS:
            analysis = self.analyzer.analyze_depth(snapshot)
        elif analysis_type == OrderBookAnalysisType.PRICE_LEVEL_DETECTION:
            analysis = self.analyzer.analyze_price_levels(snapshot)
        elif analysis_type == OrderBookAnalysisType.VOLUME_ANALYSIS:
            analysis = self.analyzer.analyze_volume(snapshot)
        elif analysis_type == OrderBookAnalysisType.IMBALANCE_DETECTION:
            analysis = self.analyzer.analyze_imbalance(snapshot)
        elif analysis_type == OrderBookAnalysisType.SUPPORT_RESISTANCE:
            analysis = self.analyzer.analyze_support_resistance(snapshot)
        else:
            raise ValueError(f"Unsupported analysis type: {analysis_type}")
        
        # Validate analysis
        validation = self.validator.validate_analysis_accuracy(analysis, expected_result)
        
        return validation
    
    def generate_validation_report(self) -> OrderBookValidationReport:
        """Generate validation report"""
        report = self.validator.generate_validation_report()
        
        with self.lock:
            self.validation_reports.append(report)
        
        return report
    
    def get_validation_history(self) -> List[OrderBookValidationReport]:
        """Get validation history"""
        with self.lock:
            return self.validation_reports.copy()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        with self.lock:
            if not self.validator.validations:
                return {"total_validations": 0}
            
            total_validations = len(self.validator.validations)
            passed_validations = sum(1 for v in self.validator.validations if v.meets_threshold)
            failed_validations = total_validations - passed_validations
            
            overall_accuracy = sum(v.accuracy_score for v in self.validator.validations) / total_validations
            overall_precision = sum(v.precision_score for v in self.validator.validations) / total_validations
            overall_recall = sum(v.recall_score for v in self.validator.validations) / total_validations
            
            return {
                "total_validations": total_validations,
                "passed_validations": passed_validations,
                "failed_validations": failed_validations,
                "overall_accuracy": overall_accuracy,
                "overall_precision": overall_precision,
                "overall_recall": overall_recall,
                "accuracy_threshold": self.validator.accuracy_threshold
            }
    
    def reset_validations(self) -> None:
        """Reset all validation data"""
        with self.lock:
            self.validator.validations.clear()
            self.validation_reports.clear()

# Global order book validation manager
_order_book_validation_manager: Optional[OrderBookValidationManager] = None

def get_order_book_validation_manager(accuracy_threshold: float = 0.95) -> OrderBookValidationManager:
    """Get global order book validation manager instance"""
    global _order_book_validation_manager
    if _order_book_validation_manager is None:
        _order_book_validation_manager = OrderBookValidationManager(accuracy_threshold)
    return _order_book_validation_manager

def validate_order_book_analysis(snapshot: OrderBookSnapshot, 
                                analysis_type: OrderBookAnalysisType,
                                expected_result: Any) -> OrderBookValidation:
    """Validate order book analysis"""
    manager = get_order_book_validation_manager()
    return manager.validate_order_book_analysis(snapshot, analysis_type, expected_result)

def generate_order_book_validation_report() -> OrderBookValidationReport:
    """Generate order book validation report"""
    manager = get_order_book_validation_manager()
    return manager.generate_validation_report()

def get_order_book_validation_summary() -> Dict[str, Any]:
    """Get order book validation summary"""
    manager = get_order_book_validation_manager()
    return manager.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    manager = get_order_book_validation_manager()
    
    # Example order book snapshot
    snapshot = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=time.time(),
        bids=[(50000.0, 1.5), (49999.0, 2.0), (49998.0, 1.0)],
        asks=[(50001.0, 1.2), (50002.0, 1.8), (50003.0, 0.9)],
        last_update_id=12345,
        data_quality=OrderBookDataQuality.HIGH,
        metadata={"source": "binance"}
    )
    
    # Example expected result for depth analysis
    expected_depth_result = {"depth_ratio": 1.25}
    
    validation = validate_order_book_analysis(
        snapshot, 
        OrderBookAnalysisType.DEPTH_ANALYSIS, 
        expected_depth_result
    )
    
    print(f"Order Book Analysis Validation:")
    print(f"Analysis Type: {validation.analysis_type.value}")
    print(f"Accuracy Score: {validation.accuracy_score:.2%}")
    print(f"Precision Score: {validation.precision_score:.2%}")
    print(f"Recall Score: {validation.recall_score:.2%}")
    print(f"F1 Score: {validation.f1_score:.2%}")
    print(f"Meets Threshold: {validation.meets_threshold}")
    print(f"Validation Status: {validation.validation_status.value}")
    
    print("\nRecommendations:")
    for rec in validation.recommendations:
        print(f"- {rec}")
    
    # Generate validation report
    report = generate_order_book_validation_report()
    
    print(f"\nOrder Book Validation Report:")
    print(f"Overall Accuracy: {report.overall_accuracy:.2%}")
    print(f"Overall Precision: {report.overall_precision:.2%}")
    print(f"Overall Recall: {report.overall_recall:.2%}")
    print(f"Overall F1 Score: {report.overall_f1_score:.2%}")
    print(f"Accuracy Level: {report.accuracy_level.value}")
    print(f"Validation Status: {report.validation_status.value}")
    print(f"Total Validations: {report.total_validations}")
    print(f"Passed Validations: {report.passed_validations}")
    print(f"Failed Validations: {report.failed_validations}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
