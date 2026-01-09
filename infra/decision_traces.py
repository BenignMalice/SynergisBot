"""
Decision Traces System

This module implements a comprehensive decision traces system that captures
full feature vectors with hashes for error analysis, providing detailed
debugging and analysis capabilities for trading decisions.

Key Features:
- Full feature vector capture and hashing
- Decision trace storage and retrieval
- Error analysis and debugging support
- Performance impact monitoring
- Trace compression and optimization
- Integration with shadow mode and observability
"""

import time
import json
import logging
import threading
import hashlib
import pickle
import zlib
from typing import Dict, List, Optional, Any, Callable, Tuple, Union, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import uuid
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class TraceLevel(Enum):
    """Trace logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class TraceType(Enum):
    """Types of decision traces"""
    TRADE_DECISION = "trade_decision"
    EXIT_DECISION = "exit_decision"
    FILTER_DECISION = "filter_decision"
    RISK_DECISION = "risk_decision"
    STRUCTURE_DECISION = "structure_decision"
    MOMENTUM_DECISION = "momentum_decision"
    LIQUIDITY_DECISION = "liquidity_decision"

class TraceStatus(Enum):
    """Trace processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPRESSED = "compressed"

@dataclass
class FeatureVector:
    """Feature vector for decision analysis"""
    timestamp: float
    symbol: str
    features: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash_value: Optional[str] = None
    size_bytes: int = 0

@dataclass
class DecisionTrace:
    """Complete decision trace"""
    trace_id: str
    timestamp: float
    symbol: str
    trace_type: TraceType
    level: TraceLevel
    input_features: FeatureVector
    output_features: FeatureVector
    decision_result: Dict[str, Any]
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    error_info: Optional[Dict[str, Any]] = None
    processing_time_ms: float = 0.0
    status: TraceStatus = TraceStatus.PENDING
    compressed: bool = False
    compression_ratio: float = 0.0

@dataclass
class TraceAnalysis:
    """Analysis of decision traces"""
    trace_id: str
    analysis_timestamp: float
    feature_importance: Dict[str, float]
    decision_confidence: float
    error_probability: float
    performance_score: float
    recommendations: List[str] = field(default_factory=list)
    similar_traces: List[str] = field(default_factory=list)

class FeatureHasher:
    """Handles feature vector hashing and comparison"""
    
    def __init__(self, hash_algorithm: str = "sha256"):
        self.hash_algorithm = hash_algorithm
        self.hash_cache: Dict[str, str] = {}
        self.lock = threading.RLock()
    
    def hash_feature_vector(self, features: Dict[str, Any]) -> str:
        """Generate hash for feature vector"""
        # Create a deterministic string representation
        feature_str = self._serialize_features(features)
        
        # Check cache first
        with self.lock:
            if feature_str in self.hash_cache:
                return self.hash_cache[feature_str]
        
        # Generate hash
        hash_obj = hashlib.new(self.hash_algorithm)
        hash_obj.update(feature_str.encode('utf-8'))
        hash_value = hash_obj.hexdigest()
        
        # Cache the result
        with self.lock:
            self.hash_cache[feature_str] = hash_value
        
        return hash_value
    
    def _serialize_features(self, features: Dict[str, Any]) -> str:
        """Serialize features to deterministic string"""
        # Sort keys for deterministic output
        sorted_items = sorted(features.items())
        
        # Convert to JSON string with sorted keys
        return json.dumps(sorted_items, sort_keys=True, separators=(',', ':'))
    
    def compare_feature_vectors(self, vec1: FeatureVector, vec2: FeatureVector) -> float:
        """Compare two feature vectors and return similarity score"""
        if vec1.hash_value == vec2.hash_value:
            return 1.0  # Identical
        
        # Calculate similarity based on common features
        common_features = set(vec1.features.keys()) & set(vec2.features.keys())
        if not common_features:
            return 0.0
        
        # Calculate weighted similarity
        total_weight = 0.0
        similarity_sum = 0.0
        
        for feature in common_features:
            weight = self._get_feature_weight(feature)
            similarity = self._compare_feature_values(
                vec1.features[feature], 
                vec2.features[feature]
            )
            
            total_weight += weight
            similarity_sum += weight * similarity
        
        return similarity_sum / total_weight if total_weight > 0 else 0.0
    
    def _get_feature_weight(self, feature_name: str) -> float:
        """Get weight for feature based on importance"""
        # Define feature importance weights
        weights = {
            'price': 1.0,
            'volume': 0.8,
            'atr': 0.9,
            'vwap': 0.9,
            'delta': 0.7,
            'spread': 0.6,
            'momentum': 0.8,
            'structure': 0.9,
            'liquidity': 0.7
        }
        return weights.get(feature_name, 0.5)
    
    def _compare_feature_values(self, val1: Any, val2: Any) -> float:
        """Compare two feature values and return similarity"""
        if val1 == val2:
            return 1.0
        
        # Handle numeric values
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if val1 == 0 and val2 == 0:
                return 1.0
            if val1 == 0 or val2 == 0:
                return 0.0
            
            # Calculate relative similarity
            ratio = min(val1, val2) / max(val1, val2)
            return ratio
        
        # Handle string values
        if isinstance(val1, str) and isinstance(val2, str):
            if val1 == val2:
                return 1.0
            # Simple string similarity (can be enhanced)
            return 0.5 if val1.lower() == val2.lower() else 0.0
        
        # Handle list/array values
        if isinstance(val1, (list, tuple)) and isinstance(val2, (list, tuple)):
            if len(val1) != len(val2):
                return 0.0
            
            similarities = []
            for v1, v2 in zip(val1, val2):
                similarities.append(self._compare_feature_values(v1, v2))
            
            return sum(similarities) / len(similarities) if similarities else 0.0
        
        # Default similarity
        return 0.0

class TraceCompressor:
    """Handles trace compression and optimization"""
    
    def __init__(self, compression_level: int = 6):
        self.compression_level = compression_level
        self.compression_stats = {
            'total_compressed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0
        }
        self.lock = threading.RLock()
    
    def compress_trace(self, trace: DecisionTrace) -> bytes:
        """Compress decision trace"""
        try:
            # Serialize trace to bytes
            trace_data = pickle.dumps(trace)
            original_size = len(trace_data)
            
            # Compress using zlib
            compressed_data = zlib.compress(trace_data, self.compression_level)
            compressed_size = len(compressed_data)
            
            # Update statistics
            with self.lock:
                self.compression_stats['total_compressed'] += 1
                self.compression_stats['total_original_size'] += original_size
                self.compression_stats['total_compressed_size'] += compressed_size
            
            return compressed_data
            
        except Exception as e:
            logger.error(f"Error compressing trace: {e}")
            return pickle.dumps(trace)
    
    def decompress_trace(self, compressed_data: bytes) -> DecisionTrace:
        """Decompress decision trace"""
        try:
            # Decompress using zlib
            decompressed_data = zlib.decompress(compressed_data)
            
            # Deserialize trace
            trace = pickle.loads(decompressed_data)
            return trace
            
        except Exception as e:
            logger.error(f"Error decompressing trace: {e}")
            # Try to load as uncompressed data
            return pickle.loads(compressed_data)
    
    def get_compression_ratio(self) -> float:
        """Get overall compression ratio"""
        with self.lock:
            if self.compression_stats['total_original_size'] == 0:
                return 0.0
            
            return (1.0 - self.compression_stats['total_compressed_size'] / 
                   self.compression_stats['total_original_size'])

class DecisionTraceManager:
    """Manages decision traces and analysis"""
    
    def __init__(self, max_traces: int = 10000, enable_compression: bool = True):
        self.max_traces = max_traces
        self.enable_compression = enable_compression
        self.traces: Dict[str, DecisionTrace] = {}
        self.compressed_traces: Dict[str, bytes] = {}
        self.feature_hasher = FeatureHasher()
        self.compressor = TraceCompressor()
        self.analyses: Dict[str, TraceAnalysis] = {}
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'total_traces': 0,
            'compressed_traces': 0,
            'failed_traces': 0,
            'total_size_bytes': 0,
            'compressed_size_bytes': 0
        }
        
        # Callbacks
        self.on_trace_created: Optional[Callable[[DecisionTrace], None]] = None
        self.on_trace_analyzed: Optional[Callable[[TraceAnalysis], None]] = None
        self.on_error_detected: Optional[Callable[[DecisionTrace], None]] = None
    
    def set_callbacks(self,
                      on_trace_created: Optional[Callable[[DecisionTrace], None]] = None,
                      on_trace_analyzed: Optional[Callable[[TraceAnalysis], None]] = None,
                      on_error_detected: Optional[Callable[[DecisionTrace], None]] = None) -> None:
        """Set callback functions for trace events"""
        self.on_trace_created = on_trace_created
        self.on_trace_analyzed = on_trace_analyzed
        self.on_error_detected = on_error_detected
    
    def create_trace(self, 
                     symbol: str,
                     trace_type: TraceType,
                     level: TraceLevel,
                     input_features: Dict[str, Any],
                     output_features: Dict[str, Any],
                     decision_result: Dict[str, Any],
                     metadata: Optional[Dict[str, Any]] = None) -> DecisionTrace:
        """Create a new decision trace"""
        trace_id = str(uuid.uuid4())
        timestamp = time.time()
        
        # Create feature vectors
        input_vector = FeatureVector(
            timestamp=timestamp,
            symbol=symbol,
            features=input_features,
            metadata=metadata or {}
        )
        
        output_vector = FeatureVector(
            timestamp=timestamp,
            symbol=symbol,
            features=output_features,
            metadata=metadata or {}
        )
        
        # Generate hashes
        input_vector.hash_value = self.feature_hasher.hash_feature_vector(input_features)
        output_vector.hash_value = self.feature_hasher.hash_feature_vector(output_features)
        
        # Calculate sizes
        input_vector.size_bytes = len(pickle.dumps(input_vector))
        output_vector.size_bytes = len(pickle.dumps(output_vector))
        
        # Create trace
        trace = DecisionTrace(
            trace_id=trace_id,
            timestamp=timestamp,
            symbol=symbol,
            trace_type=trace_type,
            level=level,
            input_features=input_vector,
            output_features=output_vector,
            decision_result=decision_result,
            status=TraceStatus.PENDING
        )
        
        # Store trace
        with self.lock:
            self.traces[trace_id] = trace
            self.stats['total_traces'] += 1
            self.stats['total_size_bytes'] += input_vector.size_bytes + output_vector.size_bytes
            
            # Maintain max traces limit
            if len(self.traces) > self.max_traces:
                self._remove_oldest_traces()
        
        # Call trace created callback
        if self.on_trace_created:
            try:
                self.on_trace_created(trace)
            except Exception as e:
                logger.error(f"Error in on_trace_created callback: {e}")
        
        return trace
    
    def _remove_oldest_traces(self) -> None:
        """Remove oldest traces to maintain limit"""
        # Sort traces by timestamp
        sorted_traces = sorted(
            self.traces.items(),
            key=lambda x: x[1].timestamp
        )
        
        # Remove oldest 10% of traces
        remove_count = max(1, len(sorted_traces) // 10)
        
        for trace_id, trace in sorted_traces[:remove_count]:
            del self.traces[trace_id]
            if trace_id in self.compressed_traces:
                del self.compressed_traces[trace_id]
    
    def get_trace(self, trace_id: str) -> Optional[DecisionTrace]:
        """Get trace by ID"""
        with self.lock:
            if trace_id in self.traces:
                return self.traces[trace_id]
            elif trace_id in self.compressed_traces:
                # Decompress and return
                return self.compressor.decompress_trace(self.compressed_traces[trace_id])
            return None
    
    def get_traces_by_symbol(self, symbol: str, limit: Optional[int] = None) -> List[DecisionTrace]:
        """Get traces for a specific symbol"""
        with self.lock:
            symbol_traces = [
                trace for trace in self.traces.values()
                if trace.symbol == symbol
            ]
            
            # Sort by timestamp (newest first)
            symbol_traces.sort(key=lambda x: x.timestamp, reverse=True)
            
            if limit:
                return symbol_traces[:limit]
            return symbol_traces
    
    def get_traces_by_type(self, trace_type: TraceType, limit: Optional[int] = None) -> List[DecisionTrace]:
        """Get traces by type"""
        with self.lock:
            type_traces = [
                trace for trace in self.traces.values()
                if trace.trace_type == trace_type
            ]
            
            # Sort by timestamp (newest first)
            type_traces.sort(key=lambda x: x.timestamp, reverse=True)
            
            if limit:
                return type_traces[:limit]
            return type_traces
    
    def analyze_trace(self, trace_id: str) -> Optional[TraceAnalysis]:
        """Analyze a decision trace"""
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        
        try:
            # Calculate feature importance
            feature_importance = self._calculate_feature_importance(trace)
            
            # Calculate decision confidence
            decision_confidence = self._calculate_decision_confidence(trace)
            
            # Calculate error probability
            error_probability = self._calculate_error_probability(trace)
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(trace)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(trace, feature_importance)
            
            # Find similar traces
            similar_traces = self._find_similar_traces(trace)
            
            # Create analysis
            analysis = TraceAnalysis(
                trace_id=trace_id,
                analysis_timestamp=time.time(),
                feature_importance=feature_importance,
                decision_confidence=decision_confidence,
                error_probability=error_probability,
                performance_score=performance_score,
                recommendations=recommendations,
                similar_traces=similar_traces
            )
            
            # Store analysis
            with self.lock:
                self.analyses[trace_id] = analysis
            
            # Call analysis callback
            if self.on_trace_analyzed:
                try:
                    self.on_trace_analyzed(analysis)
                except Exception as e:
                    logger.error(f"Error in on_trace_analyzed callback: {e}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing trace {trace_id}: {e}")
            return None
    
    def _calculate_feature_importance(self, trace: DecisionTrace) -> Dict[str, float]:
        """Calculate feature importance for trace"""
        importance = {}
        
        # Analyze input features
        for feature_name, feature_value in trace.input_features.features.items():
            # Simple importance calculation based on feature type and value
            if isinstance(feature_value, (int, float)):
                # Numeric features: importance based on magnitude and variance
                importance[feature_name] = abs(feature_value) / 1000.0  # Normalize
            elif isinstance(feature_value, str):
                # String features: importance based on length and content
                importance[feature_name] = len(feature_value) / 100.0
            else:
                # Default importance
                importance[feature_name] = 0.5
        
        # Normalize importance scores
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}
        
        return importance
    
    def _calculate_decision_confidence(self, trace: DecisionTrace) -> float:
        """Calculate decision confidence for trace"""
        # Extract confidence from decision result
        confidence = trace.decision_result.get('confidence', 0.5)
        
        # Adjust based on feature quality
        feature_quality = len(trace.input_features.features) / 20.0  # Normalize
        feature_quality = min(1.0, feature_quality)
        
        # Combine confidence and feature quality
        final_confidence = (confidence + feature_quality) / 2.0
        return min(1.0, max(0.0, final_confidence))
    
    def _calculate_error_probability(self, trace: DecisionTrace) -> float:
        """Calculate error probability for trace"""
        # Check for error indicators
        error_indicators = 0
        total_indicators = 0
        
        # Check decision result for errors
        if 'error' in trace.decision_result:
            error_indicators += 1
        total_indicators += 1
        
        # Check for missing features
        if len(trace.input_features.features) < 5:
            error_indicators += 1
        total_indicators += 1
        
        # Check for extreme values
        for feature_name, feature_value in trace.input_features.features.items():
            if isinstance(feature_value, (int, float)):
                if abs(feature_value) > 10000:  # Extreme value
                    error_indicators += 1
                total_indicators += 1
        
        return error_indicators / total_indicators if total_indicators > 0 else 0.0
    
    def _calculate_performance_score(self, trace: DecisionTrace) -> float:
        """Calculate performance score for trace"""
        # Extract performance metrics
        metrics = trace.performance_metrics
        
        # Calculate score based on available metrics
        score = 0.0
        metric_count = 0
        
        if 'latency_ms' in metrics:
            latency = metrics['latency_ms']
            # Lower latency is better (inverse relationship)
            latency_score = max(0.0, 1.0 - (latency / 1000.0))  # Normalize to 1 second
            score += latency_score
            metric_count += 1
        
        if 'accuracy' in metrics:
            accuracy = metrics['accuracy']
            score += accuracy
            metric_count += 1
        
        if 'profit_factor' in metrics:
            profit_factor = metrics['profit_factor']
            # Higher profit factor is better
            pf_score = min(1.0, profit_factor / 2.0)  # Normalize to 2.0
            score += pf_score
            metric_count += 1
        
        return score / metric_count if metric_count > 0 else 0.5
    
    def _generate_recommendations(self, trace: DecisionTrace, feature_importance: Dict[str, float]) -> List[str]:
        """Generate recommendations for trace"""
        recommendations = []
        
        # Check for low confidence
        if trace.decision_result.get('confidence', 1.0) < 0.7:
            recommendations.append("Consider additional market analysis for higher confidence")
        
        # Check for missing important features
        important_features = ['price', 'volume', 'atr', 'vwap']
        missing_features = [f for f in important_features if f not in trace.input_features.features]
        if missing_features:
            recommendations.append(f"Add missing features: {', '.join(missing_features)}")
        
        # Check for extreme values
        for feature_name, feature_value in trace.input_features.features.items():
            if isinstance(feature_value, (int, float)) and abs(feature_value) > 1000:
                recommendations.append(f"Review extreme value in {feature_name}: {feature_value}")
        
        # Check error probability
        error_prob = self._calculate_error_probability(trace)
        if error_prob > 0.3:
            recommendations.append("High error probability detected - review decision logic")
        
        return recommendations
    
    def _find_similar_traces(self, trace: DecisionTrace, limit: int = 5) -> List[str]:
        """Find similar traces"""
        similar_traces = []
        
        with self.lock:
            for other_trace_id, other_trace in self.traces.items():
                if other_trace_id == trace.trace_id:
                    continue
                
                # Calculate similarity
                similarity = self.feature_hasher.compare_feature_vectors(
                    trace.input_features,
                    other_trace.input_features
                )
                
                if similarity > 0.7:  # High similarity threshold
                    similar_traces.append((other_trace_id, similarity))
        
        # Sort by similarity and return top matches
        similar_traces.sort(key=lambda x: x[1], reverse=True)
        return [trace_id for trace_id, _ in similar_traces[:limit]]
    
    def compress_old_traces(self, age_hours: int = 24) -> int:
        """Compress traces older than specified age"""
        if not self.enable_compression:
            return 0
        
        cutoff_time = time.time() - (age_hours * 3600)
        compressed_count = 0
        
        with self.lock:
            traces_to_compress = [
                (trace_id, trace) for trace_id, trace in self.traces.items()
                if trace.timestamp < cutoff_time and not trace.compressed
            ]
            
            for trace_id, trace in traces_to_compress:
                try:
                    # Compress trace
                    compressed_data = self.compressor.compress_trace(trace)
                    
                    # Store compressed version
                    self.compressed_traces[trace_id] = compressed_data
                    
                    # Update trace status
                    trace.compressed = True
                    trace.compression_ratio = self.compressor.get_compression_ratio()
                    
                    # Remove from main traces (keep in compressed)
                    del self.traces[trace_id]
                    
                    compressed_count += 1
                    self.stats['compressed_traces'] += 1
                    
                except Exception as e:
                    logger.error(f"Error compressing trace {trace_id}: {e}")
                    self.stats['failed_traces'] += 1
        
        return compressed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trace statistics"""
        with self.lock:
            return {
                'total_traces': self.stats['total_traces'],
                'active_traces': len(self.traces),
                'compressed_traces': len(self.compressed_traces),
                'failed_traces': self.stats['failed_traces'],
                'total_size_bytes': self.stats['total_size_bytes'],
                'compressed_size_bytes': self.stats['compressed_size_bytes'],
                'compression_ratio': self.compressor.get_compression_ratio(),
                'analyses_count': len(self.analyses)
            }

# Global trace manager
_trace_manager: Optional[DecisionTraceManager] = None

def get_trace_manager() -> DecisionTraceManager:
    """Get global trace manager instance"""
    global _trace_manager
    if _trace_manager is None:
        _trace_manager = DecisionTraceManager()
    return _trace_manager

def create_decision_trace(symbol: str,
                         trace_type: TraceType,
                         level: TraceLevel,
                         input_features: Dict[str, Any],
                         output_features: Dict[str, Any],
                         decision_result: Dict[str, Any],
                         metadata: Optional[Dict[str, Any]] = None) -> DecisionTrace:
    """Create a new decision trace"""
    manager = get_trace_manager()
    return manager.create_trace(
        symbol, trace_type, level, input_features, 
        output_features, decision_result, metadata
    )

def get_decision_trace(trace_id: str) -> Optional[DecisionTrace]:
    """Get decision trace by ID"""
    manager = get_trace_manager()
    return manager.get_trace(trace_id)

def analyze_decision_trace(trace_id: str) -> Optional[TraceAnalysis]:
    """Analyze a decision trace"""
    manager = get_trace_manager()
    return manager.analyze_trace(trace_id)

def get_traces_by_symbol(symbol: str, limit: Optional[int] = None) -> List[DecisionTrace]:
    """Get traces for a specific symbol"""
    manager = get_trace_manager()
    return manager.get_traces_by_symbol(symbol, limit)

def get_traces_by_type(trace_type: TraceType, limit: Optional[int] = None) -> List[DecisionTrace]:
    """Get traces by type"""
    manager = get_trace_manager()
    return manager.get_traces_by_type(trace_type, limit)

def compress_old_traces(age_hours: int = 24) -> int:
    """Compress old traces"""
    manager = get_trace_manager()
    return manager.compress_old_traces(age_hours)

def get_trace_statistics() -> Dict[str, Any]:
    """Get trace statistics"""
    manager = get_trace_manager()
    return manager.get_statistics()

if __name__ == "__main__":
    # Example usage
    manager = get_trace_manager()
    
    # Create a decision trace
    input_features = {
        'price': 50000.0,
        'volume': 100.0,
        'atr': 500.0,
        'vwap': 49950.0,
        'momentum': 0.75
    }
    
    output_features = {
        'decision': 'buy',
        'confidence': 0.85,
        'risk_score': 0.3
    }
    
    decision_result = {
        'action': 'buy',
        'quantity': 0.01,
        'stop_loss': 49500.0,
        'take_profit': 51000.0,
        'confidence': 0.85
    }
    
    trace = create_decision_trace(
        symbol="BTCUSDc",
        trace_type=TraceType.TRADE_DECISION,
        level=TraceLevel.INFO,
        input_features=input_features,
        output_features=output_features,
        decision_result=decision_result
    )
    
    print(f"Created trace: {trace.trace_id}")
    
    # Analyze the trace
    analysis = analyze_decision_trace(trace.trace_id)
    if analysis:
        print(f"Analysis confidence: {analysis.decision_confidence}")
        print(f"Error probability: {analysis.error_probability}")
        print(f"Recommendations: {analysis.recommendations}")
    
    # Get statistics
    stats = get_trace_statistics()
    print(f"Trace statistics: {json.dumps(stats, indent=2)}")
