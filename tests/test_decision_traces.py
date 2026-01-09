"""
Comprehensive tests for decision traces system

Tests feature vector hashing, trace creation, compression, analysis,
error detection, and performance monitoring.
"""

import pytest
import time
import json
import threading
import pickle
import zlib
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.decision_traces import (
    DecisionTraceManager, FeatureHasher, TraceCompressor,
    TraceLevel, TraceType, TraceStatus, FeatureVector,
    DecisionTrace, TraceAnalysis,
    get_trace_manager, create_decision_trace, get_decision_trace,
    analyze_decision_trace, get_traces_by_symbol, get_traces_by_type,
    compress_old_traces, get_trace_statistics
)

class TestTraceLevel:
    """Test trace level enumeration"""
    
    def test_trace_levels(self):
        """Test all trace levels"""
        levels = [
            TraceLevel.DEBUG,
            TraceLevel.INFO,
            TraceLevel.WARNING,
            TraceLevel.ERROR,
            TraceLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, TraceLevel)
            assert level.value in ["debug", "info", "warning", "error", "critical"]

class TestTraceType:
    """Test trace type enumeration"""
    
    def test_trace_types(self):
        """Test all trace types"""
        types = [
            TraceType.TRADE_DECISION,
            TraceType.EXIT_DECISION,
            TraceType.FILTER_DECISION,
            TraceType.RISK_DECISION,
            TraceType.STRUCTURE_DECISION,
            TraceType.MOMENTUM_DECISION,
            TraceType.LIQUIDITY_DECISION
        ]
        
        for trace_type in types:
            assert isinstance(trace_type, TraceType)
            assert trace_type.value in [
                "trade_decision", "exit_decision", "filter_decision",
                "risk_decision", "structure_decision", "momentum_decision",
                "liquidity_decision"
            ]

class TestTraceStatus:
    """Test trace status enumeration"""
    
    def test_trace_statuses(self):
        """Test all trace statuses"""
        statuses = [
            TraceStatus.PENDING,
            TraceStatus.PROCESSING,
            TraceStatus.COMPLETED,
            TraceStatus.FAILED,
            TraceStatus.COMPRESSED
        ]
        
        for status in statuses:
            assert isinstance(status, TraceStatus)
            assert status.value in ["pending", "processing", "completed", "failed", "compressed"]

class TestFeatureVector:
    """Test feature vector data structure"""
    
    def test_feature_vector_creation(self):
        """Test feature vector creation"""
        features = {
            'price': 50000.0,
            'volume': 100.0,
            'atr': 500.0
        }
        
        vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features=features,
            metadata={"source": "mt5"},
            hash_value="abc123",
            size_bytes=1024
        )
        
        assert vector.timestamp > 0
        assert vector.symbol == "BTCUSDc"
        assert vector.features == features
        assert vector.metadata["source"] == "mt5"
        assert vector.hash_value == "abc123"
        assert vector.size_bytes == 1024
    
    def test_feature_vector_defaults(self):
        """Test feature vector defaults"""
        vector = FeatureVector(
            timestamp=time.time(),
            symbol="ETHUSDc",
            features={"price": 3000.0}
        )
        
        assert vector.metadata == {}
        assert vector.hash_value is None
        assert vector.size_bytes == 0

class TestDecisionTrace:
    """Test decision trace data structure"""
    
    def test_decision_trace_creation(self):
        """Test decision trace creation"""
        input_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={"price": 50000.0}
        )
        
        output_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={"decision": "buy"}
        )
        
        trace = DecisionTrace(
            trace_id="test_trace_1",
            timestamp=time.time(),
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_vector,
            output_features=output_vector,
            decision_result={"action": "buy", "confidence": 0.85},
            performance_metrics={"latency_ms": 50.0},
            error_info={"error": "test error"},
            processing_time_ms=100.0,
            status=TraceStatus.COMPLETED,
            compressed=True,
            compression_ratio=0.5
        )
        
        assert trace.trace_id == "test_trace_1"
        assert trace.symbol == "BTCUSDc"
        assert trace.trace_type == TraceType.TRADE_DECISION
        assert trace.level == TraceLevel.INFO
        assert trace.input_features == input_vector
        assert trace.output_features == output_vector
        assert trace.decision_result["action"] == "buy"
        assert trace.performance_metrics["latency_ms"] == 50.0
        assert trace.error_info["error"] == "test error"
        assert trace.processing_time_ms == 100.0
        assert trace.status == TraceStatus.COMPLETED
        assert trace.compressed is True
        assert trace.compression_ratio == 0.5
    
    def test_decision_trace_defaults(self):
        """Test decision trace defaults"""
        input_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={"price": 50000.0}
        )
        
        output_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={"decision": "buy"}
        )
        
        trace = DecisionTrace(
            trace_id="test_trace_2",
            timestamp=time.time(),
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_vector,
            output_features=output_vector,
            decision_result={"action": "buy"}
        )
        
        assert trace.performance_metrics == {}
        assert trace.error_info is None
        assert trace.processing_time_ms == 0.0
        assert trace.status == TraceStatus.PENDING
        assert trace.compressed is False
        assert trace.compression_ratio == 0.0

class TestFeatureHasher:
    """Test feature hasher"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.hasher = FeatureHasher()
    
    def test_hasher_initialization(self):
        """Test hasher initialization"""
        assert self.hasher.hash_algorithm == "sha256"
        assert len(self.hasher.hash_cache) == 0
        assert hasattr(self.hasher, 'lock')
    
    def test_hash_feature_vector(self):
        """Test feature vector hashing"""
        features = {
            'price': 50000.0,
            'volume': 100.0,
            'atr': 500.0
        }
        
        hash1 = self.hasher.hash_feature_vector(features)
        hash2 = self.hasher.hash_feature_vector(features)
        
        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
        assert isinstance(hash1, str)
    
    def test_hash_feature_vector_different(self):
        """Test hashing different feature vectors"""
        features1 = {'price': 50000.0, 'volume': 100.0}
        features2 = {'price': 50001.0, 'volume': 100.0}
        
        hash1 = self.hasher.hash_feature_vector(features1)
        hash2 = self.hasher.hash_feature_vector(features2)
        
        # Should be different
        assert hash1 != hash2
    
    def test_hash_caching(self):
        """Test hash caching"""
        features = {'price': 50000.0}
        
        # First call
        hash1 = self.hasher.hash_feature_vector(features)
        assert len(self.hasher.hash_cache) == 1
        
        # Second call should use cache
        hash2 = self.hasher.hash_feature_vector(features)
        assert hash1 == hash2
        assert len(self.hasher.hash_cache) == 1
    
    def test_compare_feature_vectors(self):
        """Test feature vector comparison"""
        vector1 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 50000.0, 'volume': 100.0}
        )
        
        vector2 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 50000.0, 'volume': 100.0}
        )
        
        # Identical vectors
        similarity = self.hasher.compare_feature_vectors(vector1, vector2)
        assert similarity == 1.0
        
        # Different vectors
        vector3 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 51000.0, 'volume': 100.0}
        )
        
        similarity = self.hasher.compare_feature_vectors(vector1, vector3)
        assert 0.0 <= similarity <= 1.0
    
    def test_compare_feature_vectors_numeric(self):
        """Test numeric feature comparison"""
        vector1 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 100.0}
        )
        
        vector2 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 200.0}
        )
        
        # Set hash values to be different
        vector1.hash_value = self.hasher.hash_feature_vector({'price': 100.0})
        vector2.hash_value = self.hasher.hash_feature_vector({'price': 200.0})
        
        similarity = self.hasher.compare_feature_vectors(vector1, vector2)
        # Should calculate similarity based on feature values
        assert 0.0 <= similarity <= 1.0
    
    def test_compare_feature_vectors_string(self):
        """Test string feature comparison"""
        vector1 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'status': 'active'}
        )
        
        vector2 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'status': 'active'}
        )
        
        # Set identical hash values
        vector1.hash_value = self.hasher.hash_feature_vector({'status': 'active'})
        vector2.hash_value = self.hasher.hash_feature_vector({'status': 'active'})
        
        similarity = self.hasher.compare_feature_vectors(vector1, vector2)
        assert similarity == 1.0  # Identical hash values
        
        # Different strings
        vector3 = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'status': 'inactive'}
        )
        
        # Set different hash values
        vector3.hash_value = self.hasher.hash_feature_vector({'status': 'inactive'})
        
        similarity = self.hasher.compare_feature_vectors(vector1, vector3)
        # Should calculate similarity based on feature values
        assert 0.0 <= similarity <= 1.0

class TestTraceCompressor:
    """Test trace compressor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.compressor = TraceCompressor()
    
    def test_compressor_initialization(self):
        """Test compressor initialization"""
        assert self.compressor.compression_level == 6
        assert self.compressor.compression_stats['total_compressed'] == 0
        assert self.compressor.compression_stats['total_original_size'] == 0
        assert self.compressor.compression_stats['total_compressed_size'] == 0
    
    def test_compress_trace(self):
        """Test trace compression"""
        # Create a test trace
        input_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 50000.0, 'volume': 100.0}
        )
        
        output_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'decision': 'buy'}
        )
        
        trace = DecisionTrace(
            trace_id="test_trace",
            timestamp=time.time(),
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_vector,
            output_features=output_vector,
            decision_result={'action': 'buy'}
        )
        
        # Compress trace
        compressed_data = self.compressor.compress_trace(trace)
        
        assert isinstance(compressed_data, bytes)
        assert len(compressed_data) > 0
        
        # Check statistics
        assert self.compressor.compression_stats['total_compressed'] == 1
        assert self.compressor.compression_stats['total_original_size'] > 0
        assert self.compressor.compression_stats['total_compressed_size'] > 0
    
    def test_decompress_trace(self):
        """Test trace decompression"""
        # Create and compress a trace
        input_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 50000.0}
        )
        
        output_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'decision': 'buy'}
        )
        
        original_trace = DecisionTrace(
            trace_id="test_trace",
            timestamp=time.time(),
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_vector,
            output_features=output_vector,
            decision_result={'action': 'buy'}
        )
        
        compressed_data = self.compressor.compress_trace(original_trace)
        
        # Decompress trace
        decompressed_trace = self.compressor.decompress_trace(compressed_data)
        
        assert isinstance(decompressed_trace, DecisionTrace)
        assert decompressed_trace.trace_id == original_trace.trace_id
        assert decompressed_trace.symbol == original_trace.symbol
        assert decompressed_trace.trace_type == original_trace.trace_type
        assert decompressed_trace.decision_result == original_trace.decision_result
    
    def test_compression_ratio(self):
        """Test compression ratio calculation"""
        # Create a trace with some data
        input_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'price': 50000.0, 'volume': 100.0, 'atr': 500.0}
        )
        
        output_vector = FeatureVector(
            timestamp=time.time(),
            symbol="BTCUSDc",
            features={'decision': 'buy', 'confidence': 0.85}
        )
        
        trace = DecisionTrace(
            trace_id="test_trace",
            timestamp=time.time(),
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_vector,
            output_features=output_vector,
            decision_result={'action': 'buy', 'confidence': 0.85}
        )
        
        # Compress trace
        self.compressor.compress_trace(trace)
        
        # Check compression ratio
        ratio = self.compressor.get_compression_ratio()
        assert 0.0 <= ratio <= 1.0

class TestDecisionTraceManager:
    """Test decision trace manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = DecisionTraceManager(max_traces=100, enable_compression=True)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.max_traces == 100
        assert self.manager.enable_compression is True
        assert len(self.manager.traces) == 0
        assert len(self.manager.compressed_traces) == 0
        assert isinstance(self.manager.feature_hasher, FeatureHasher)
        assert isinstance(self.manager.compressor, TraceCompressor)
        assert len(self.manager.analyses) == 0
        assert self.manager.stats['total_traces'] == 0
    
    def test_create_trace(self):
        """Test creating a trace"""
        input_features = {
            'price': 50000.0,
            'volume': 100.0,
            'atr': 500.0
        }
        
        output_features = {
            'decision': 'buy',
            'confidence': 0.85
        }
        
        decision_result = {
            'action': 'buy',
            'quantity': 0.01,
            'confidence': 0.85
        }
        
        trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features=input_features,
            output_features=output_features,
            decision_result=decision_result
        )
        
        assert isinstance(trace, DecisionTrace)
        assert trace.symbol == "BTCUSDc"
        assert trace.trace_type == TraceType.TRADE_DECISION
        assert trace.level == TraceLevel.INFO
        assert trace.input_features.features == input_features
        assert trace.output_features.features == output_features
        assert trace.decision_result == decision_result
        assert trace.status == TraceStatus.PENDING
        
        # Check that trace was stored
        assert trace.trace_id in self.manager.traces
        assert self.manager.stats['total_traces'] == 1
    
    def test_get_trace(self):
        """Test getting a trace"""
        # Create a trace
        trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        # Get the trace
        retrieved_trace = self.manager.get_trace(trace.trace_id)
        
        assert retrieved_trace is not None
        assert retrieved_trace.trace_id == trace.trace_id
        assert retrieved_trace.symbol == trace.symbol
    
    def test_get_trace_not_found(self):
        """Test getting non-existent trace"""
        trace = self.manager.get_trace("non_existent_id")
        assert trace is None
    
    def test_get_traces_by_symbol(self):
        """Test getting traces by symbol"""
        # Create traces for different symbols
        trace1 = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        trace2 = self.manager.create_trace(
            symbol="ETHUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 3000.0},
            output_features={'decision': 'sell'},
            decision_result={'action': 'sell'}
        )
        
        # Get traces for BTCUSDc
        btc_traces = self.manager.get_traces_by_symbol("BTCUSDc")
        assert len(btc_traces) == 1
        assert btc_traces[0].trace_id == trace1.trace_id
        
        # Get traces for ETHUSDc
        eth_traces = self.manager.get_traces_by_symbol("ETHUSDc")
        assert len(eth_traces) == 1
        assert eth_traces[0].trace_id == trace2.trace_id
    
    def test_get_traces_by_type(self):
        """Test getting traces by type"""
        # Create traces of different types
        trade_trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        exit_trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.EXIT_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 51000.0},
            output_features={'decision': 'exit'},
            decision_result={'action': 'exit'}
        )
        
        # Get trade decision traces
        trade_traces = self.manager.get_traces_by_type(TraceType.TRADE_DECISION)
        assert len(trade_traces) == 1
        assert trade_traces[0].trace_id == trade_trace.trace_id
        
        # Get exit decision traces
        exit_traces = self.manager.get_traces_by_type(TraceType.EXIT_DECISION)
        assert len(exit_traces) == 1
        assert exit_traces[0].trace_id == exit_trace.trace_id
    
    def test_analyze_trace(self):
        """Test trace analysis"""
        # Create a trace
        trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0, 'volume': 100.0, 'atr': 500.0},
            output_features={'decision': 'buy', 'confidence': 0.85},
            decision_result={'action': 'buy', 'confidence': 0.85}
        )
        
        # Analyze the trace
        analysis = self.manager.analyze_trace(trace.trace_id)
        
        assert analysis is not None
        assert analysis.trace_id == trace.trace_id
        assert analysis.analysis_timestamp > 0
        assert 'price' in analysis.feature_importance
        assert 0.0 <= analysis.decision_confidence <= 1.0
        assert 0.0 <= analysis.error_probability <= 1.0
        assert 0.0 <= analysis.performance_score <= 1.0
        assert isinstance(analysis.recommendations, list)
        assert isinstance(analysis.similar_traces, list)
        
        # Check that analysis was stored
        assert trace.trace_id in self.manager.analyses
    
    def test_analyze_trace_not_found(self):
        """Test analyzing non-existent trace"""
        analysis = self.manager.analyze_trace("non_existent_id")
        assert analysis is None
    
    def test_compress_old_traces(self):
        """Test compressing old traces"""
        # Create a trace
        trace = self.manager.create_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        # Set trace timestamp to old time
        trace.timestamp = time.time() - (25 * 3600)  # 25 hours ago
        
        # Compress old traces
        compressed_count = self.manager.compress_old_traces(age_hours=24)
        
        assert compressed_count == 1
        assert trace.trace_id in self.manager.compressed_traces
        assert trace.trace_id not in self.manager.traces
        assert trace.compressed is True
        assert self.manager.stats['compressed_traces'] == 1
    
    def test_get_statistics(self):
        """Test getting statistics"""
        # Create some traces
        for i in range(3):
            self.manager.create_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features={'price': 50000.0 + i},
                output_features={'decision': 'buy'},
                decision_result={'action': 'buy'}
            )
        
        stats = self.manager.get_statistics()
        
        assert stats['total_traces'] == 3
        assert stats['active_traces'] == 3
        assert stats['compressed_traces'] == 0
        assert stats['failed_traces'] == 0
        assert stats['total_size_bytes'] > 0
        assert stats['compressed_size_bytes'] == 0
        assert stats['compression_ratio'] == 0.0
        assert stats['analyses_count'] == 0
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_trace_created = Mock()
        on_trace_analyzed = Mock()
        on_error_detected = Mock()
        
        self.manager.set_callbacks(
            on_trace_created=on_trace_created,
            on_trace_analyzed=on_trace_analyzed,
            on_error_detected=on_error_detected
        )
        
        assert self.manager.on_trace_created == on_trace_created
        assert self.manager.on_trace_analyzed == on_trace_analyzed
        assert self.manager.on_error_detected == on_error_detected

class TestGlobalFunctions:
    """Test global decision trace functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.decision_traces
        infra.decision_traces._trace_manager = None
    
    def test_get_trace_manager(self):
        """Test global trace manager access"""
        manager1 = get_trace_manager()
        manager2 = get_trace_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, DecisionTraceManager)
    
    def test_create_decision_trace_global(self):
        """Test global decision trace creation"""
        trace = create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        assert isinstance(trace, DecisionTrace)
        assert trace.symbol == "BTCUSDc"
        assert trace.trace_type == TraceType.TRADE_DECISION
    
    def test_get_decision_trace_global(self):
        """Test global decision trace retrieval"""
        trace = create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        retrieved_trace = get_decision_trace(trace.trace_id)
        assert retrieved_trace is not None
        assert retrieved_trace.trace_id == trace.trace_id
        
        # Test non-existent trace
        non_existent = get_decision_trace("non_existent_id")
        assert non_existent is None
    
    def test_analyze_decision_trace_global(self):
        """Test global decision trace analysis"""
        trace = create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0, 'volume': 100.0},
            output_features={'decision': 'buy', 'confidence': 0.85},
            decision_result={'action': 'buy', 'confidence': 0.85}
        )
        
        analysis = analyze_decision_trace(trace.trace_id)
        assert analysis is not None
        assert analysis.trace_id == trace.trace_id
        assert 0.0 <= analysis.decision_confidence <= 1.0
    
    def test_get_traces_by_symbol_global(self):
        """Test global traces by symbol"""
        # Create traces for different symbols
        create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        create_decision_trace(
            symbol="ETHUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 3000.0},
            output_features={'decision': 'sell'},
            decision_result={'action': 'sell'}
        )
        
        # Get traces by symbol
        btc_traces = get_traces_by_symbol("BTCUSDc")
        eth_traces = get_traces_by_symbol("ETHUSDc")
        
        assert len(btc_traces) == 1
        assert len(eth_traces) == 1
        assert btc_traces[0].symbol == "BTCUSDc"
        assert eth_traces[0].symbol == "ETHUSDc"
    
    def test_get_traces_by_type_global(self):
        """Test global traces by type"""
        # Create traces of different types
        create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.EXIT_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 51000.0},
            output_features={'decision': 'exit'},
            decision_result={'action': 'exit'}
        )
        
        # Get traces by type
        trade_traces = get_traces_by_type(TraceType.TRADE_DECISION)
        exit_traces = get_traces_by_type(TraceType.EXIT_DECISION)
        
        assert len(trade_traces) == 1
        assert len(exit_traces) == 1
        assert trade_traces[0].trace_type == TraceType.TRADE_DECISION
        assert exit_traces[0].trace_type == TraceType.EXIT_DECISION
    
    def test_compress_old_traces_global(self):
        """Test global trace compression"""
        # Create a trace
        trace = create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},
            output_features={'decision': 'buy'},
            decision_result={'action': 'buy'}
        )
        
        # Set trace timestamp to old time
        manager = get_trace_manager()
        manager.traces[trace.trace_id].timestamp = time.time() - (25 * 3600)
        
        # Compress old traces
        compressed_count = compress_old_traces(age_hours=24)
        assert compressed_count == 1
    
    def test_get_trace_statistics_global(self):
        """Test global trace statistics"""
        # Create some traces
        for i in range(2):
            create_decision_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features={'price': 50000.0 + i},
                output_features={'decision': 'buy'},
                decision_result={'action': 'buy'}
            )
        
        stats = get_trace_statistics()
        assert stats['total_traces'] == 2
        assert stats['active_traces'] == 2

class TestDecisionTraceIntegration:
    """Integration tests for decision trace system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.decision_traces
        infra.decision_traces._trace_manager = None
    
    def test_comprehensive_trace_workflow(self):
        """Test comprehensive trace workflow"""
        # Create multiple traces
        traces = []
        for i in range(5):
            trace = create_decision_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features={
                    'price': 50000.0 + i * 100,
                    'volume': 100.0 + i * 10,
                    'atr': 500.0 + i * 50
                },
                output_features={
                    'decision': 'buy' if i % 2 == 0 else 'sell',
                    'confidence': 0.8 + i * 0.02
                },
                decision_result={
                    'action': 'buy' if i % 2 == 0 else 'sell',
                    'quantity': 0.01,
                    'confidence': 0.8 + i * 0.02
                }
            )
            traces.append(trace)
        
        # Analyze all traces
        analyses = []
        for trace in traces:
            analysis = analyze_decision_trace(trace.trace_id)
            if analysis:
                analyses.append(analysis)
        
        assert len(analyses) == 5
        
        # Check analysis quality
        for analysis in analyses:
            assert 0.0 <= analysis.decision_confidence <= 1.0
            assert 0.0 <= analysis.error_probability <= 1.0
            assert 0.0 <= analysis.performance_score <= 1.0
            assert isinstance(analysis.feature_importance, dict)
            assert isinstance(analysis.recommendations, list)
            assert isinstance(analysis.similar_traces, list)
        
        # Get statistics
        stats = get_trace_statistics()
        assert stats['total_traces'] == 5
        assert stats['active_traces'] == 5
        assert stats['analyses_count'] == 5
    
    def test_trace_compression_workflow(self):
        """Test trace compression workflow"""
        # Create traces
        traces = []
        for i in range(3):
            trace = create_decision_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features={'price': 50000.0 + i},
                output_features={'decision': 'buy'},
                decision_result={'action': 'buy'}
            )
            traces.append(trace)
        
        # Set some traces to old timestamps
        manager = get_trace_manager()
        for i, trace in enumerate(traces[:2]):
            manager.traces[trace.trace_id].timestamp = time.time() - (25 * 3600)
        
        # Compress old traces
        compressed_count = compress_old_traces(age_hours=24)
        assert compressed_count == 2
        
        # Check that traces were compressed
        stats = get_trace_statistics()
        assert stats['active_traces'] == 1  # Only one recent trace
        assert stats['compressed_traces'] == 2
        
        # Verify compressed traces can still be retrieved
        for trace in traces[:2]:
            retrieved_trace = get_decision_trace(trace.trace_id)
            assert retrieved_trace is not None
            assert retrieved_trace.trace_id == trace.trace_id
    
    def test_feature_vector_hashing_consistency(self):
        """Test feature vector hashing consistency"""
        features = {
            'price': 50000.0,
            'volume': 100.0,
            'atr': 500.0,
            'vwap': 49950.0
        }
        
        # Create multiple traces with same features
        traces = []
        for i in range(3):
            trace = create_decision_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features=features,
                output_features={'decision': 'buy'},
                decision_result={'action': 'buy'}
            )
            traces.append(trace)
        
        # Check that feature vectors have same hash
        hashes = [trace.input_features.hash_value for trace in traces]
        assert all(hash_val == hashes[0] for hash_val in hashes)
        
        # Check similarity
        manager = get_trace_manager()
        similarity = manager.feature_hasher.compare_feature_vectors(
            traces[0].input_features,
            traces[1].input_features
        )
        assert similarity == 1.0  # Identical features
    
    def test_trace_analysis_recommendations(self):
        """Test trace analysis recommendations"""
        # Create trace with low confidence
        trace = create_decision_trace(
            symbol="BTCUSDc",
            trace_type=TraceType.TRADE_DECISION,
            level=TraceLevel.INFO,
            input_features={'price': 50000.0},  # Minimal features
            output_features={'decision': 'buy', 'confidence': 0.5},  # Low confidence
            decision_result={'action': 'buy', 'confidence': 0.5}
        )
        
        # Analyze trace
        analysis = analyze_decision_trace(trace.trace_id)
        assert analysis is not None
        
        # Check that recommendations were generated
        assert len(analysis.recommendations) > 0
        
        # Check for specific recommendations
        recommendation_text = ' '.join(analysis.recommendations)
        assert 'confidence' in recommendation_text.lower() or 'features' in recommendation_text.lower()
    
    def test_trace_error_handling(self):
        """Test trace error handling"""
        # Test creating trace with invalid data
        try:
            trace = create_decision_trace(
                symbol="BTCUSDc",
                trace_type=TraceType.TRADE_DECISION,
                level=TraceLevel.INFO,
                input_features={},  # Empty features
                output_features={},  # Empty features
                decision_result={}  # Empty result
            )
            assert trace is not None  # Should still create trace
        except Exception as e:
            pytest.fail(f"Unexpected error creating trace: {e}")
        
        # Test analyzing non-existent trace
        analysis = analyze_decision_trace("non_existent_id")
        assert analysis is None
        
        # Test getting non-existent trace
        trace = get_decision_trace("non_existent_id")
        assert trace is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
