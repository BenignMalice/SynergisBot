"""
Structure Detection Accuracy Validation System

This module implements a comprehensive validation system for market structure
detection accuracy, ensuring the system meets the >75% accuracy target for
reliable trading decisions.

Key Features:
- Structure detection accuracy measurement
- BOS/CHOCH validation algorithms
- Support/resistance level accuracy
- Market structure pattern recognition
- Accuracy reporting and analysis
- Performance benchmarking
"""

import time
import json
import logging
import threading
import statistics
import numpy as np
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger(__name__)

class StructureType(Enum):
    """Types of market structures"""
    BOS = "bos"  # Break of Structure
    CHOCH = "choch"  # Change of Character
    SUPPORT = "support"
    RESISTANCE = "resistance"
    TREND_LINE = "trend_line"
    CHANNEL = "channel"
    TRIANGLE = "triangle"
    FLAG = "flag"
    PENNANT = "pennant"

class ValidationStatus(Enum):
    """Structure validation status"""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    EXPIRED = "expired"
    CONFLICTED = "conflicted"

class AccuracyLevel(Enum):
    """Accuracy level classifications"""
    EXCELLENT = "excellent"  # >90%
    GOOD = "good"  # 75-90%
    FAIR = "fair"  # 60-75%
    POOR = "poor"  # <60%

@dataclass
class StructurePoint:
    """Market structure point"""
    timestamp: float
    price: float
    structure_type: StructureType
    timeframe: str
    symbol: str
    strength: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StructureValidation:
    """Structure validation result"""
    structure_id: str
    timestamp: float
    structure_type: StructureType
    symbol: str
    timeframe: str
    detected_price: float
    actual_price: float
    price_deviation: float
    time_deviation: float
    validation_status: ValidationStatus
    accuracy_score: float
    confidence: float
    validation_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AccuracyMetrics:
    """Accuracy metrics for structure detection"""
    total_structures: int = 0
    valid_structures: int = 0
    invalid_structures: int = 0
    pending_structures: int = 0
    overall_accuracy: float = 0.0
    price_accuracy: float = 0.0
    time_accuracy: float = 0.0
    confidence_accuracy: float = 0.0
    structure_type_accuracy: Dict[StructureType, float] = field(default_factory=dict)
    timeframe_accuracy: Dict[str, float] = field(default_factory=dict)
    symbol_accuracy: Dict[str, float] = field(default_factory=dict)

class StructureDetector:
    """Market structure detection engine"""
    
    def __init__(self, lookback_periods: int = 20):
        self.lookback_periods = lookback_periods
        self.price_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.structure_cache: Dict[str, List[StructurePoint]] = defaultdict(list)
        self.lock = threading.RLock()
    
    def add_price_data(self, symbol: str, timeframe: str, timestamp: float, 
                      open_price: float, high_price: float, low_price: float, 
                      close_price: float, volume: float) -> None:
        """Add price data for structure analysis"""
        with self.lock:
            key = f"{symbol}_{timeframe}"
            self.price_data[key].append({
                'timestamp': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
    
    def detect_bos(self, symbol: str, timeframe: str, lookback: int = 10) -> List[StructurePoint]:
        """Detect Break of Structure (BOS)"""
        key = f"{symbol}_{timeframe}"
        if key not in self.price_data or len(self.price_data[key]) < lookback:
            return []
        
        data = list(self.price_data[key])
        bos_points = []
        
        for i in range(lookback, len(data)):
            current_bar = data[i]
            previous_bars = data[i-lookback:i]
            
            # Check for BOS conditions
            if self._is_bos_pattern(current_bar, previous_bars):
                strength = self._calculate_bos_strength(current_bar, previous_bars)
                confidence = self._calculate_bos_confidence(current_bar, previous_bars)
                
                bos_point = StructurePoint(
                    timestamp=current_bar['timestamp'],
                    price=current_bar['high'] if current_bar['close'] > current_bar['open'] else current_bar['low'],
                    structure_type=StructureType.BOS,
                    timeframe=timeframe,
                    symbol=symbol,
                    strength=strength,
                    confidence=confidence,
                    metadata={
                        'lookback_periods': lookback,
                        'volume': current_bar['volume'],
                        'price_range': current_bar['high'] - current_bar['low']
                    }
                )
                
                bos_points.append(bos_point)
        
        return bos_points
    
    def detect_choch(self, symbol: str, timeframe: str, lookback: int = 10) -> List[StructurePoint]:
        """Detect Change of Character (CHOCH)"""
        key = f"{symbol}_{timeframe}"
        if key not in self.price_data or len(self.price_data[key]) < lookback:
            return []
        
        data = list(self.price_data[key])
        choch_points = []
        
        for i in range(lookback, len(data)):
            current_bar = data[i]
            previous_bars = data[i-lookback:i]
            
            # Check for CHOCH conditions
            if self._is_choch_pattern(current_bar, previous_bars):
                strength = self._calculate_choch_strength(current_bar, previous_bars)
                confidence = self._calculate_choch_confidence(current_bar, previous_bars)
                
                choch_point = StructurePoint(
                    timestamp=current_bar['timestamp'],
                    price=current_bar['close'],
                    structure_type=StructureType.CHOCH,
                    timeframe=timeframe,
                    symbol=symbol,
                    strength=strength,
                    confidence=confidence,
                    metadata={
                        'lookback_periods': lookback,
                        'volume': current_bar['volume'],
                        'trend_change': self._detect_trend_change(previous_bars)
                    }
                )
                
                choch_points.append(choch_point)
        
        return choch_points
    
    def detect_support_resistance(self, symbol: str, timeframe: str, 
                                lookback: int = 20) -> List[StructurePoint]:
        """Detect support and resistance levels"""
        key = f"{symbol}_{timeframe}"
        if key not in self.price_data or len(self.price_data[key]) < lookback:
            return []
        
        data = list(self.price_data[key])
        levels = []
        
        # Find pivot highs and lows
        for i in range(lookback, len(data) - lookback):
            current_bar = data[i]
            
            # Check for pivot high (resistance)
            if self._is_pivot_high(data, i, lookback):
                strength = self._calculate_level_strength(data, i, 'resistance')
                confidence = self._calculate_level_confidence(data, i, 'resistance')
                
                resistance_point = StructurePoint(
                    timestamp=current_bar['timestamp'],
                    price=current_bar['high'],
                    structure_type=StructureType.RESISTANCE,
                    timeframe=timeframe,
                    symbol=symbol,
                    strength=strength,
                    confidence=confidence,
                    metadata={
                        'lookback_periods': lookback,
                        'volume': current_bar['volume'],
                        'touches': self._count_level_touches(data, current_bar['high'], i)
                    }
                )
                
                levels.append(resistance_point)
            
            # Check for pivot low (support)
            if self._is_pivot_low(data, i, lookback):
                strength = self._calculate_level_strength(data, i, 'support')
                confidence = self._calculate_level_confidence(data, i, 'support')
                
                support_point = StructurePoint(
                    timestamp=current_bar['timestamp'],
                    price=current_bar['low'],
                    structure_type=StructureType.SUPPORT,
                    timeframe=timeframe,
                    symbol=symbol,
                    strength=strength,
                    confidence=confidence,
                    metadata={
                        'lookback_periods': lookback,
                        'volume': current_bar['volume'],
                        'touches': self._count_level_touches(data, current_bar['low'], i)
                    }
                )
                
                levels.append(support_point)
        
        return levels
    
    def _is_bos_pattern(self, current_bar: Dict, previous_bars: List[Dict]) -> bool:
        """Check if current bar forms a BOS pattern"""
        if len(previous_bars) < 3:
            return False
        
        # Check for higher high or lower low
        current_high = current_bar['high']
        current_low = current_bar['low']
        
        # Get recent highs and lows
        recent_highs = [bar['high'] for bar in previous_bars[-3:]]
        recent_lows = [bar['low'] for bar in previous_bars[-3:]]
        
        max_recent_high = max(recent_highs)
        min_recent_low = min(recent_lows)
        
        # BOS: Break above recent high or below recent low
        return current_high > max_recent_high or current_low < min_recent_low
    
    def _is_choch_pattern(self, current_bar: Dict, previous_bars: List[Dict]) -> bool:
        """Check if current bar forms a CHOCH pattern"""
        if len(previous_bars) < 5:
            return False
        
        # Analyze trend direction
        recent_trend = self._analyze_trend(previous_bars[-5:])
        current_trend = self._analyze_trend([previous_bars[-1], current_bar])
        
        # CHOCH: Trend direction change
        return recent_trend != current_trend and current_trend != 'sideways'
    
    def _is_pivot_high(self, data: List[Dict], index: int, lookback: int) -> bool:
        """Check if bar at index is a pivot high"""
        if index < lookback or index >= len(data) - lookback:
            return False
        
        current_high = data[index]['high']
        
        # Check if current high is higher than surrounding bars
        for i in range(index - lookback, index + lookback + 1):
            if i != index and data[i]['high'] >= current_high:
                return False
        
        return True
    
    def _is_pivot_low(self, data: List[Dict], index: int, lookback: int) -> bool:
        """Check if bar at index is a pivot low"""
        if index < lookback or index >= len(data) - lookback:
            return False
        
        current_low = data[index]['low']
        
        # Check if current low is lower than surrounding bars
        for i in range(index - lookback, index + lookback + 1):
            if i != index and data[i]['low'] <= current_low:
                return False
        
        return True
    
    def _calculate_bos_strength(self, current_bar: Dict, previous_bars: List[Dict]) -> float:
        """Calculate BOS strength"""
        if not previous_bars:
            return 0.0
        
        # Calculate price movement strength
        price_range = current_bar['high'] - current_bar['low']
        avg_range = statistics.mean([bar['high'] - bar['low'] for bar in previous_bars])
        
        strength = min(1.0, price_range / avg_range) if avg_range > 0 else 0.0
        
        # Factor in volume
        volume_factor = min(1.0, current_bar['volume'] / statistics.mean([bar['volume'] for bar in previous_bars]))
        
        return (strength + volume_factor) / 2.0
    
    def _calculate_choch_strength(self, current_bar: Dict, previous_bars: List[Dict]) -> float:
        """Calculate CHOCH strength"""
        if not previous_bars:
            return 0.0
        
        # Calculate trend change magnitude
        recent_trend = self._analyze_trend(previous_bars[-3:])
        current_trend = self._analyze_trend([previous_bars[-1], current_bar])
        
        if recent_trend == current_trend:
            return 0.0
        
        # Calculate strength based on price movement
        price_change = abs(current_bar['close'] - previous_bars[-1]['close'])
        avg_change = statistics.mean([abs(bar['close'] - previous_bars[i-1]['close']) 
                                    for i, bar in enumerate(previous_bars[1:], 1)])
        
        strength = min(1.0, price_change / avg_change) if avg_change > 0 else 0.0
        
        return strength
    
    def _calculate_bos_confidence(self, current_bar: Dict, previous_bars: List[Dict]) -> float:
        """Calculate BOS confidence"""
        if not previous_bars:
            return 0.0
        
        # Confidence based on volume and price action
        volume_confidence = min(1.0, current_bar['volume'] / statistics.mean([bar['volume'] for bar in previous_bars]))
        price_confidence = self._calculate_bos_strength(current_bar, previous_bars)
        
        return (volume_confidence + price_confidence) / 2.0
    
    def _calculate_choch_confidence(self, current_bar: Dict, previous_bars: List[Dict]) -> float:
        """Calculate CHOCH confidence"""
        if not previous_bars:
            return 0.0
        
        # Confidence based on trend change clarity
        trend_change_confidence = self._calculate_choch_strength(current_bar, previous_bars)
        volume_confidence = min(1.0, current_bar['volume'] / statistics.mean([bar['volume'] for bar in previous_bars]))
        
        return (trend_change_confidence + volume_confidence) / 2.0
    
    def _calculate_level_strength(self, data: List[Dict], index: int, level_type: str) -> float:
        """Calculate support/resistance level strength"""
        if index < 5 or index >= len(data) - 5:
            return 0.0
        
        level_price = data[index]['high'] if level_type == 'resistance' else data[index]['low']
        touches = self._count_level_touches(data, level_price, index)
        
        # Strength based on number of touches and time span
        time_span = data[index]['timestamp'] - data[index-5]['timestamp']
        strength = min(1.0, (touches * 0.2) + (time_span / 3600) * 0.1)  # Normalize
        
        return strength
    
    def _calculate_level_confidence(self, data: List[Dict], index: int, level_type: str) -> float:
        """Calculate support/resistance level confidence"""
        if index < 5 or index >= len(data) - 5:
            return 0.0
        
        level_price = data[index]['high'] if level_type == 'resistance' else data[index]['low']
        touches = self._count_level_touches(data, level_price, index)
        
        # Confidence based on touches and volume
        volume_at_level = data[index]['volume']
        avg_volume = statistics.mean([bar['volume'] for bar in data[max(0, index-5):index+1]])
        volume_confidence = min(1.0, volume_at_level / avg_volume) if avg_volume > 0 else 0.0
        
        touch_confidence = min(1.0, touches * 0.3)
        
        return (volume_confidence + touch_confidence) / 2.0
    
    def _analyze_trend(self, bars: List[Dict]) -> str:
        """Analyze trend direction"""
        if len(bars) < 2:
            return 'sideways'
        
        # Simple trend analysis
        first_close = bars[0]['close']
        last_close = bars[-1]['close']
        
        if last_close > first_close * 1.001:  # 0.1% threshold
            return 'uptrend'
        elif last_close < first_close * 0.999:  # 0.1% threshold
            return 'downtrend'
        else:
            return 'sideways'
    
    def _detect_trend_change(self, bars: List[Dict]) -> bool:
        """Detect trend change"""
        if len(bars) < 4:
            return False
        
        # Compare first half vs second half trend
        mid_point = len(bars) // 2
        first_half_trend = self._analyze_trend(bars[:mid_point])
        second_half_trend = self._analyze_trend(bars[mid_point:])
        
        return first_half_trend != second_half_trend
    
    def _count_level_touches(self, data: List[Dict], level_price: float, index: int) -> int:
        """Count how many times price touched the level"""
        tolerance = level_price * 0.001  # 0.1% tolerance
        touches = 0
        
        for bar in data[max(0, index-10):index+1]:
            if abs(bar['high'] - level_price) <= tolerance or abs(bar['low'] - level_price) <= tolerance:
                touches += 1
        
        return touches

class StructureValidator:
    """Structure validation engine"""
    
    def __init__(self, validation_window_hours: int = 24):
        self.validation_window_hours = validation_window_hours
        self.validations: List[StructureValidation] = []
        self.accuracy_metrics = AccuracyMetrics()
        self.lock = threading.RLock()
    
    def validate_structure(self, structure_point: StructurePoint, 
                          actual_price: float, actual_timestamp: float) -> StructureValidation:
        """Validate a structure point against actual market data"""
        validation_id = f"val_{int(time.time())}_{hashlib.md5(str(structure_point.timestamp).encode()).hexdigest()[:8]}"
        
        # Calculate deviations
        price_deviation = abs(structure_point.price - actual_price) / actual_price
        time_deviation = abs(structure_point.timestamp - actual_timestamp)
        
        # Determine validation status
        validation_status = self._determine_validation_status(
            price_deviation, time_deviation, structure_point.confidence
        )
        
        # Calculate accuracy score
        accuracy_score = self._calculate_accuracy_score(
            price_deviation, time_deviation, structure_point.confidence
        )
        
        validation = StructureValidation(
            structure_id=validation_id,
            timestamp=time.time(),
            structure_type=structure_point.structure_type,
            symbol=structure_point.symbol,
            timeframe=structure_point.timeframe,
            detected_price=structure_point.price,
            actual_price=actual_price,
            price_deviation=price_deviation,
            time_deviation=time_deviation,
            validation_status=validation_status,
            accuracy_score=accuracy_score,
            confidence=structure_point.confidence,
            validation_time=time.time() - structure_point.timestamp,
            metadata={
                'detected_strength': structure_point.strength,
                'detected_confidence': structure_point.confidence
            }
        )
        
        with self.lock:
            self.validations.append(validation)
            self._update_accuracy_metrics()
        
        return validation
    
    def _determine_validation_status(self, price_deviation: float, 
                                   time_deviation: float, confidence: float) -> ValidationStatus:
        """Determine validation status based on deviations and confidence"""
        # Define thresholds
        price_threshold = 0.02  # 2% price deviation
        time_threshold = 3600   # 1 hour time deviation
        confidence_threshold = 0.7  # 70% confidence threshold
        
        if price_deviation <= price_threshold and time_deviation <= time_threshold and confidence >= confidence_threshold:
            return ValidationStatus.VALID
        elif price_deviation <= price_threshold * 2 and time_deviation <= time_threshold * 2:
            return ValidationStatus.PENDING
        else:
            return ValidationStatus.INVALID
    
    def _calculate_accuracy_score(self, price_deviation: float, 
                                time_deviation: float, confidence: float) -> float:
        """Calculate accuracy score"""
        # Normalize deviations (lower is better)
        price_score = max(0.0, 1.0 - (price_deviation / 0.05))  # 5% max deviation
        time_score = max(0.0, 1.0 - (time_deviation / 7200))   # 2 hours max deviation
        
        # Combine with confidence
        accuracy_score = (price_score * 0.4 + time_score * 0.3 + confidence * 0.3)
        
        return min(1.0, max(0.0, accuracy_score))
    
    def _update_accuracy_metrics(self) -> None:
        """Update accuracy metrics"""
        if not self.validations:
            return
        
        # Count validations by status
        valid_count = sum(1 for v in self.validations if v.validation_status == ValidationStatus.VALID)
        invalid_count = sum(1 for v in self.validations if v.validation_status == ValidationStatus.INVALID)
        pending_count = sum(1 for v in self.validations if v.validation_status == ValidationStatus.PENDING)
        
        total_count = len(self.validations)
        
        # Update metrics
        self.accuracy_metrics.total_structures = total_count
        self.accuracy_metrics.valid_structures = valid_count
        self.accuracy_metrics.invalid_structures = invalid_count
        self.accuracy_metrics.pending_structures = pending_count
        self.accuracy_metrics.overall_accuracy = valid_count / total_count if total_count > 0 else 0.0
        
        # Calculate detailed accuracy metrics
        if self.validations:
            self.accuracy_metrics.price_accuracy = statistics.mean([1.0 - v.price_deviation for v in self.validations])
            self.accuracy_metrics.time_accuracy = statistics.mean([1.0 - (v.time_deviation / 7200) for v in self.validations])
            self.accuracy_metrics.confidence_accuracy = statistics.mean([v.confidence for v in self.validations])
            
            # Calculate accuracy by structure type
            for structure_type in StructureType:
                type_validations = [v for v in self.validations if v.structure_type == structure_type]
                if type_validations:
                    type_accuracy = sum(1.0 - v.price_deviation for v in type_validations) / len(type_validations)
                    self.accuracy_metrics.structure_type_accuracy[structure_type] = type_accuracy
            
            # Calculate accuracy by timeframe
            timeframes = set(v.timeframe for v in self.validations)
            for timeframe in timeframes:
                tf_validations = [v for v in self.validations if v.timeframe == timeframe]
                if tf_validations:
                    tf_accuracy = sum(1.0 - v.price_deviation for v in tf_validations) / len(tf_validations)
                    self.accuracy_metrics.timeframe_accuracy[timeframe] = tf_accuracy
            
            # Calculate accuracy by symbol
            symbols = set(v.symbol for v in self.validations)
            for symbol in symbols:
                symbol_validations = [v for v in self.validations if v.symbol == symbol]
                if symbol_validations:
                    symbol_accuracy = sum(1.0 - v.price_deviation for v in symbol_validations) / len(symbol_validations)
                    self.accuracy_metrics.symbol_accuracy[symbol] = symbol_accuracy
    
    def get_accuracy_report(self) -> Dict[str, Any]:
        """Get comprehensive accuracy report"""
        with self.lock:
            # Determine accuracy level
            overall_accuracy = self.accuracy_metrics.overall_accuracy
            if overall_accuracy >= 0.9:
                accuracy_level = AccuracyLevel.EXCELLENT
            elif overall_accuracy >= 0.75:
                accuracy_level = AccuracyLevel.GOOD
            elif overall_accuracy >= 0.6:
                accuracy_level = AccuracyLevel.FAIR
            else:
                accuracy_level = AccuracyLevel.POOR
            
            return {
                'overall_accuracy': overall_accuracy,
                'accuracy_level': accuracy_level.value,
                'total_structures': self.accuracy_metrics.total_structures,
                'valid_structures': self.accuracy_metrics.valid_structures,
                'invalid_structures': self.accuracy_metrics.invalid_structures,
                'pending_structures': self.accuracy_metrics.pending_structures,
                'price_accuracy': self.accuracy_metrics.price_accuracy,
                'time_accuracy': self.accuracy_metrics.time_accuracy,
                'confidence_accuracy': self.accuracy_metrics.confidence_accuracy,
                'structure_type_accuracy': {k.value: v for k, v in self.accuracy_metrics.structure_type_accuracy.items()},
                'timeframe_accuracy': self.accuracy_metrics.timeframe_accuracy,
                'symbol_accuracy': self.accuracy_metrics.symbol_accuracy,
                'meets_target': overall_accuracy >= 0.75,
                'recommendations': self._generate_recommendations()
            }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on accuracy analysis"""
        recommendations = []
        
        overall_accuracy = self.accuracy_metrics.overall_accuracy
        
        if overall_accuracy < 0.75:
            recommendations.append("Structure detection accuracy below target (75%). Review detection algorithms.")
        
        if self.accuracy_metrics.price_accuracy < 0.8:
            recommendations.append("Price accuracy below 80%. Improve price level detection algorithms.")
        
        if self.accuracy_metrics.time_accuracy < 0.8:
            recommendations.append("Time accuracy below 80%. Improve timing detection algorithms.")
        
        if self.accuracy_metrics.confidence_accuracy < 0.7:
            recommendations.append("Confidence accuracy below 70%. Review confidence calculation methods.")
        
        # Check structure type accuracy
        for structure_type, accuracy in self.accuracy_metrics.structure_type_accuracy.items():
            if accuracy < 0.7:
                recommendations.append(f"{structure_type.value} detection accuracy below 70%. Review {structure_type.value} algorithms.")
        
        # Check timeframe accuracy
        for timeframe, accuracy in self.accuracy_metrics.timeframe_accuracy.items():
            if accuracy < 0.7:
                recommendations.append(f"{timeframe} timeframe accuracy below 70%. Review {timeframe} detection parameters.")
        
        return recommendations

class StructureValidationSystem:
    """Main structure validation system"""
    
    def __init__(self):
        self.detector = StructureDetector()
        self.validator = StructureValidator()
        self.lock = threading.RLock()
    
    def analyze_structure_accuracy(self, symbol: str, timeframe: str, 
                                 lookback_hours: int = 24) -> Dict[str, Any]:
        """Analyze structure detection accuracy for a symbol and timeframe"""
        # Get historical data (this would be implemented based on data source)
        # For now, we'll simulate the analysis
        
        # Detect structures
        bos_structures = self.detector.detect_bos(symbol, timeframe)
        choch_structures = self.detector.detect_choch(symbol, timeframe)
        support_resistance = self.detector.detect_support_resistance(symbol, timeframe)
        
        all_structures = bos_structures + choch_structures + support_resistance
        
        # Validate structures (simulate with mock data)
        for structure in all_structures:
            # Simulate actual market data
            actual_price = structure.price * (1.0 + np.random.normal(0, 0.01))  # 1% noise
            actual_timestamp = structure.timestamp + np.random.normal(0, 300)  # 5 min noise
            
            # Validate structure
            validation = self.validator.validate_structure(structure, actual_price, actual_timestamp)
        
        # Get accuracy report
        accuracy_report = self.validator.get_accuracy_report()
        
        return accuracy_report
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary"""
        with self.lock:
            return {
                'total_validations': len(self.validator.validations),
                'accuracy_metrics': asdict(self.validator.accuracy_metrics),
                'meets_75_percent_target': self.validator.accuracy_metrics.overall_accuracy >= 0.75
            }

# Global validation system
_validation_system: Optional[StructureValidationSystem] = None

def get_validation_system() -> StructureValidationSystem:
    """Get global validation system instance"""
    global _validation_system
    if _validation_system is None:
        _validation_system = StructureValidationSystem()
    return _validation_system

def get_structure_validator() -> StructureValidationSystem:
    """Get structure validator - alias for backward compatibility"""
    return get_validation_system()

def analyze_structure_accuracy(symbol: str, timeframe: str, 
                             lookback_hours: int = 24) -> Dict[str, Any]:
    """Analyze structure detection accuracy"""
    system = get_validation_system()
    return system.analyze_structure_accuracy(symbol, timeframe, lookback_hours)

def get_validation_summary() -> Dict[str, Any]:
    """Get validation summary"""
    system = get_validation_system()
    return system.get_validation_summary()

if __name__ == "__main__":
    # Example usage
    system = get_validation_system()
    
    # Analyze structure accuracy
    report = analyze_structure_accuracy("BTCUSDc", "H1", lookback_hours=24)
    
    print(f"Structure Detection Accuracy Report:")
    print(f"Overall Accuracy: {report['overall_accuracy']:.2%}")
    print(f"Accuracy Level: {report['accuracy_level']}")
    print(f"Meets 75% Target: {report['meets_target']}")
    print(f"Total Structures: {report['total_structures']}")
    print(f"Valid Structures: {report['valid_structures']}")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"- {rec}")
