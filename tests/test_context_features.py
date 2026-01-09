"""
Comprehensive tests for context features system

Tests context feature processing, scoring, non-blocking operations,
order book analysis, large order detection, and support/resistance processing.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from infra.context_features import (
    ContextFeatureManager, ContextFeatureProcessor, OrderBookContextProcessor,
    LargeOrderContextProcessor, SupportResistanceContextProcessor,
    ContextFeature, ContextScore, ContextConfig, ContextType, ContextWeight,
    ContextStatus, get_context_manager, process_order_book_context,
    process_large_order_context, get_context_score, get_all_context_scores
)

class TestContextType:
    """Test context type enumeration"""
    
    def test_context_types(self):
        """Test all context types"""
        context_types = [
            ContextType.ORDER_BOOK_DEPTH,
            ContextType.ORDER_BOOK_IMBALANCE,
            ContextType.LARGE_ORDER_DETECTION,
            ContextType.SUPPORT_RESISTANCE,
            ContextType.VOLUME_PROFILE,
            ContextType.MARKET_SENTIMENT,
            ContextType.MOMENTUM_INDICATOR,
            ContextType.VOLATILITY_CONTEXT
        ]
        
        for context_type in context_types:
            assert isinstance(context_type, ContextType)
            assert context_type.value in [
                "order_book_depth", "order_book_imbalance", "large_order_detection",
                "support_resistance", "volume_profile", "market_sentiment",
                "momentum_indicator", "volatility_context"
            ]

class TestContextWeight:
    """Test context weight enumeration"""
    
    def test_context_weights(self):
        """Test all context weights"""
        weights = [
            ContextWeight.LOW,
            ContextWeight.MEDIUM,
            ContextWeight.HIGH,
            ContextWeight.CRITICAL
        ]
        
        for weight in weights:
            assert isinstance(weight, ContextWeight)
            assert weight.value in ["low", "medium", "high", "critical"]

class TestContextStatus:
    """Test context status enumeration"""
    
    def test_context_statuses(self):
        """Test all context statuses"""
        statuses = [
            ContextStatus.ACTIVE,
            ContextStatus.STALE,
            ContextStatus.UNAVAILABLE,
            ContextStatus.ERROR
        ]
        
        for status in statuses:
            assert isinstance(status, ContextStatus)
            assert status.value in ["active", "stale", "unavailable", "error"]

class TestContextConfig:
    """Test context configuration"""
    
    def test_context_config_creation(self):
        """Test context configuration creation"""
        config = ContextConfig(
            max_features_per_symbol=100,
            feature_timeout_ms=5000,
            update_interval_ms=1000,
            stale_threshold_ms=10000,
            confidence_threshold=0.5,
            enable_non_blocking=True,
            enable_context_scoring=True
        )
        
        assert config.max_features_per_symbol == 100
        assert config.feature_timeout_ms == 5000
        assert config.update_interval_ms == 1000
        assert config.stale_threshold_ms == 10000
        assert config.confidence_threshold == 0.5
        assert config.enable_non_blocking is True
        assert config.enable_context_scoring is True
        assert len(config.weight_multipliers) == 4
    
    def test_context_config_defaults(self):
        """Test context configuration defaults"""
        config = ContextConfig()
        
        assert config.max_features_per_symbol == 100
        assert config.feature_timeout_ms == 5000
        assert config.update_interval_ms == 1000
        assert config.stale_threshold_ms == 10000
        assert config.confidence_threshold == 0.5
        assert config.enable_non_blocking is True
        assert config.enable_context_scoring is True
        assert config.weight_multipliers[ContextWeight.LOW] == 0.1
        assert config.weight_multipliers[ContextWeight.MEDIUM] == 0.3
        assert config.weight_multipliers[ContextWeight.HIGH] == 0.6
        assert config.weight_multipliers[ContextWeight.CRITICAL] == 1.0

class TestContextFeature:
    """Test context feature data structure"""
    
    def test_context_feature_creation(self):
        """Test context feature creation"""
        feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_IMBALANCE,
            symbol="BTCUSDc",
            value=0.5,
            weight=ContextWeight.MEDIUM,
            confidence=0.8,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE,
            metadata={'test': 'value'}
        )
        
        assert feature.feature_type == ContextType.ORDER_BOOK_IMBALANCE
        assert feature.symbol == "BTCUSDc"
        assert feature.value == 0.5
        assert feature.weight == ContextWeight.MEDIUM
        assert feature.confidence == 0.8
        assert feature.timestamp > 0
        assert feature.status == ContextStatus.ACTIVE
        assert feature.metadata['test'] == 'value'
    
    def test_context_feature_defaults(self):
        """Test context feature defaults"""
        feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_DEPTH,
            symbol="ETHUSDc",
            value=1.0,
            weight=ContextWeight.LOW,
            confidence=0.7,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE
        )
        
        assert feature.metadata == {}

class TestContextScore:
    """Test context score data structure"""
    
    def test_context_score_creation(self):
        """Test context score creation"""
        features = [
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol="BTCUSDc",
                value=0.5,
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            )
        ]
        
        score = ContextScore(
            symbol="BTCUSDc",
            total_score=0.5,
            weighted_score=0.15,
            feature_count=1,
            last_update=time.time(),
            features=features
        )
        
        assert score.symbol == "BTCUSDc"
        assert score.total_score == 0.5
        assert score.weighted_score == 0.15
        assert score.feature_count == 1
        assert score.last_update > 0
        assert len(score.features) == 1

class TestContextFeatureProcessor:
    """Test context feature processor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ContextConfig(max_features_per_symbol=10)
        self.processor = ContextFeatureProcessor(self.config)
    
    def test_processor_initialization(self):
        """Test processor initialization"""
        assert self.processor.config == self.config
        assert len(self.processor.features) == 0
        assert len(self.processor.context_scores) == 0
        assert hasattr(self.processor.executor, 'submit')  # Check if it's a thread pool executor
    
    def test_add_feature(self):
        """Test adding a context feature"""
        feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_IMBALANCE,
            symbol="BTCUSDc",
            value=0.5,
            weight=ContextWeight.MEDIUM,
            confidence=0.8,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE
        )
        
        self.processor.add_feature(feature)
        
        assert "BTCUSDc" in self.processor.features
        assert len(self.processor.features["BTCUSDc"]) == 1
        assert "BTCUSDc" in self.processor.context_scores
        assert self.processor.context_scores["BTCUSDc"].feature_count == 1
    
    def test_add_multiple_features(self):
        """Test adding multiple features for same symbol"""
        features = [
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol="BTCUSDc",
                value=0.5,
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            ),
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_DEPTH,
                symbol="BTCUSDc",
                value=1.0,
                weight=ContextWeight.LOW,
                confidence=0.7,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            )
        ]
        
        for feature in features:
            self.processor.add_feature(feature)
        
        assert len(self.processor.features["BTCUSDc"]) == 2
        assert self.processor.context_scores["BTCUSDc"].feature_count == 2
        assert self.processor.context_scores["BTCUSDc"].total_score == 1.5
    
    def test_max_features_per_symbol(self):
        """Test max features per symbol limit"""
        # Add more features than the limit
        for i in range(15):  # More than max_features_per_symbol (10)
            feature = ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol="BTCUSDc",
                value=float(i),
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            )
            self.processor.add_feature(feature)
        
        # Should only keep the last 10 features
        assert len(self.processor.features["BTCUSDc"]) == 10
    
    def test_get_context_score(self):
        """Test getting context score"""
        feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_IMBALANCE,
            symbol="BTCUSDc",
            value=0.5,
            weight=ContextWeight.MEDIUM,
            confidence=0.8,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE
        )
        
        self.processor.add_feature(feature)
        
        score = self.processor.get_context_score("BTCUSDc")
        assert score is not None
        assert score.symbol == "BTCUSDc"
        assert score.total_score == 0.5
        assert score.feature_count == 1
        
        # Test non-existent symbol
        score = self.processor.get_context_score("NONEXISTENT")
        assert score is None
    
    def test_get_features(self):
        """Test getting features"""
        features = [
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol="BTCUSDc",
                value=0.5,
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            ),
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_DEPTH,
                symbol="BTCUSDc",
                value=1.0,
                weight=ContextWeight.LOW,
                confidence=0.7,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            )
        ]
        
        for feature in features:
            self.processor.add_feature(feature)
        
        # Get all features
        all_features = self.processor.get_features("BTCUSDc")
        assert len(all_features) == 2
        
        # Get features by type
        imbalance_features = self.processor.get_features("BTCUSDc", ContextType.ORDER_BOOK_IMBALANCE)
        assert len(imbalance_features) == 1
        assert imbalance_features[0].feature_type == ContextType.ORDER_BOOK_IMBALANCE
        
        # Test non-existent symbol
        features = self.processor.get_features("NONEXISTENT")
        assert len(features) == 0
    
    def test_cleanup_stale_features(self):
        """Test cleanup of stale features"""
        # Add a stale feature
        stale_feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_IMBALANCE,
            symbol="BTCUSDc",
            value=0.5,
            weight=ContextWeight.MEDIUM,
            confidence=0.8,
            timestamp=time.time() - 20,  # 20 seconds ago (stale)
            status=ContextStatus.ACTIVE
        )
        
        # Add a fresh feature
        fresh_feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_DEPTH,
            symbol="BTCUSDc",
            value=1.0,
            weight=ContextWeight.LOW,
            confidence=0.7,
            timestamp=time.time(),  # Now
            status=ContextStatus.ACTIVE
        )
        
        self.processor.add_feature(stale_feature)
        self.processor.add_feature(fresh_feature)
        
        # Cleanup stale features
        removed_count = self.processor.cleanup_stale_features()
        
        assert removed_count == 1
        assert len(self.processor.features["BTCUSDc"]) == 1
        assert self.processor.features["BTCUSDc"][0].value == 1.0  # Fresh feature
    
    def test_get_feature_statistics(self):
        """Test getting feature statistics"""
        # Add some features
        features = [
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol="BTCUSDc",
                value=0.5,
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            ),
            ContextFeature(
                feature_type=ContextType.ORDER_BOOK_DEPTH,
                symbol="ETHUSDc",
                value=1.0,
                weight=ContextWeight.LOW,
                confidence=0.7,
                timestamp=time.time(),
                status=ContextStatus.ACTIVE
            )
        ]
        
        for feature in features:
            self.processor.add_feature(feature)
        
        stats = self.processor.get_feature_statistics()
        
        assert stats['total_features'] == 2
        assert stats['total_symbols'] == 2
        assert 'order_book_imbalance' in stats['feature_types']
        assert 'order_book_depth' in stats['feature_types']
        assert stats['avg_features_per_symbol'] == 1.0
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_feature_updated = Mock()
        on_context_changed = Mock()
        on_stale_feature = Mock()
        
        self.processor.set_callbacks(
            on_feature_updated=on_feature_updated,
            on_context_changed=on_context_changed,
            on_stale_feature=on_stale_feature
        )
        
        assert self.processor.on_feature_updated == on_feature_updated
        assert self.processor.on_context_changed == on_context_changed
        assert self.processor.on_stale_feature == on_stale_feature

class TestOrderBookContextProcessor:
    """Test order book context processor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ContextConfig()
        self.context_processor = ContextFeatureProcessor(self.config)
        self.order_book_processor = OrderBookContextProcessor(self.context_processor)
    
    def test_process_order_book_depth(self):
        """Test processing order book depth"""
        bids = [(100.0, 1.5), (99.9, 2.0), (99.8, 1.0)]
        asks = [(100.1, 1.2), (100.2, 1.8), (100.3, 0.9)]
        timestamp = time.time()
        
        self.order_book_processor.process_order_book_depth("BTCUSDc", bids, asks, timestamp)
        
        # Check that features were added
        features = self.context_processor.get_features("BTCUSDc")
        assert len(features) == 2  # Imbalance and depth features
        
        # Check imbalance feature
        imbalance_features = [f for f in features if f.feature_type == ContextType.ORDER_BOOK_IMBALANCE]
        assert len(imbalance_features) == 1
        assert imbalance_features[0].symbol == "BTCUSDc"
        assert imbalance_features[0].weight == ContextWeight.MEDIUM
        
        # Check depth feature
        depth_features = [f for f in features if f.feature_type == ContextType.ORDER_BOOK_DEPTH]
        assert len(depth_features) == 1
        assert depth_features[0].symbol == "BTCUSDc"
        assert depth_features[0].weight == ContextWeight.LOW
    
    def test_calculate_order_book_imbalance(self):
        """Test order book imbalance calculation"""
        bids = [(100.0, 2.0), (99.9, 1.0)]  # Total: 3.0
        asks = [(100.1, 1.0), (100.2, 1.0)]  # Total: 2.0
        
        imbalance = self.order_book_processor._calculate_order_book_imbalance(bids, asks)
        expected = (3.0 - 2.0) / (3.0 + 2.0)  # 0.2
        assert abs(imbalance - expected) < 0.001
    
    def test_calculate_depth_score(self):
        """Test depth score calculation"""
        bids = [(100.0, 1.0), (99.9, 1.0), (99.8, 1.0)]  # 3 levels
        asks = [(100.1, 1.0), (100.2, 1.0)]  # 2 levels
        
        depth_score = self.order_book_processor._calculate_depth_score(bids, asks)
        expected = (3 + 2) / 2.0  # 2.5
        assert depth_score == expected
    
    def test_empty_order_book(self):
        """Test handling empty order book"""
        self.order_book_processor.process_order_book_depth("BTCUSDc", [], [], time.time())
        
        # Should not crash and should add features with zero values
        features = self.context_processor.get_features("BTCUSDc")
        assert len(features) == 2  # Imbalance and depth features with zero values
        assert all(f.value == 0.0 for f in features)

class TestLargeOrderContextProcessor:
    """Test large order context processor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ContextConfig()
        self.context_processor = ContextFeatureProcessor(self.config)
        self.large_order_processor = LargeOrderContextProcessor(self.context_processor)
    
    def test_process_large_order(self):
        """Test processing large order"""
        self.large_order_processor.process_large_order(
            "BTCUSDc", 1000.0, "market", 50000.0, time.time()
        )
        
        # Check that feature was added
        features = self.context_processor.get_features("BTCUSDc")
        assert len(features) == 1
        
        feature = features[0]
        assert feature.feature_type == ContextType.LARGE_ORDER_DETECTION
        assert feature.symbol == "BTCUSDc"
        assert feature.weight == ContextWeight.HIGH
        assert feature.confidence == 0.9
        assert feature.metadata['order_size'] == 1000.0
        assert feature.metadata['order_type'] == "market"
        assert feature.metadata['price'] == 50000.0
    
    def test_calculate_impact_score(self):
        """Test impact score calculation"""
        # Test market order
        market_impact = self.large_order_processor._calculate_impact_score(
            1000.0, "market", 50000.0
        )
        expected_market = (1000.0 / 50000.0) * 1.5  # size/price * market multiplier
        assert abs(market_impact - expected_market) < 0.001
        
        # Test limit order
        limit_impact = self.large_order_processor._calculate_impact_score(
            1000.0, "limit", 50000.0
        )
        expected_limit = (1000.0 / 50000.0) * 0.8  # size/price * limit multiplier
        assert abs(limit_impact - expected_limit) < 0.001

class TestSupportResistanceContextProcessor:
    """Test support/resistance context processor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ContextConfig()
        self.context_processor = ContextFeatureProcessor(self.config)
        self.support_resistance_processor = SupportResistanceContextProcessor(self.context_processor)
    
    def test_process_support_resistance(self):
        """Test processing support/resistance levels"""
        levels = [
            {'type': 'support', 'strength': 0.8, 'price': 100.0},
            {'type': 'resistance', 'strength': 0.6, 'price': 105.0}
        ]
        
        self.support_resistance_processor.process_support_resistance(
            "BTCUSDc", levels, time.time()
        )
        
        # Check that features were added
        features = self.context_processor.get_features("BTCUSDc")
        assert len(features) == 2
        
        for feature in features:
            assert feature.feature_type == ContextType.SUPPORT_RESISTANCE
            assert feature.symbol == "BTCUSDc"
            assert feature.weight == ContextWeight.MEDIUM
            assert feature.confidence == 0.7
            assert 'level_type' in feature.metadata
            assert 'price' in feature.metadata
            assert 'strength' in feature.metadata

class TestContextFeatureManager:
    """Test context feature manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ContextConfig(update_interval_ms=100)  # Fast updates for testing
        self.manager = ContextFeatureManager(self.config)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.config == self.config
        assert isinstance(self.manager.processor, ContextFeatureProcessor)
        assert isinstance(self.manager.order_book_processor, OrderBookContextProcessor)
        assert isinstance(self.manager.large_order_processor, LargeOrderContextProcessor)
        assert isinstance(self.manager.support_resistance_processor, SupportResistanceContextProcessor)
    
    def test_process_order_book_data(self):
        """Test processing order book data"""
        order_book_data = {
            'bids': [(100.0, 1.5), (99.9, 2.0)],
            'asks': [(100.1, 1.2), (100.2, 1.8)],
            'timestamp': time.time()
        }
        
        self.manager.process_order_book_data("BTCUSDc", order_book_data)
        
        # Wait a bit for background processing
        time.sleep(0.1)
        
        # Check that features were added
        features = self.manager.processor.get_features("BTCUSDc")
        assert len(features) >= 2  # At least imbalance and depth features
    
    def test_process_large_order(self):
        """Test processing large order data"""
        order_data = {
            'size': 1000.0,
            'type': 'market',
            'price': 50000.0,
            'timestamp': time.time()
        }
        
        self.manager.process_large_order("BTCUSDc", order_data)
        
        # Wait a bit for background processing
        time.sleep(0.1)
        
        # Check that feature was added
        features = self.manager.processor.get_features("BTCUSDc")
        large_order_features = [f for f in features if f.feature_type == ContextType.LARGE_ORDER_DETECTION]
        assert len(large_order_features) == 1
    
    def test_process_support_resistance(self):
        """Test processing support/resistance data"""
        levels_data = [
            {'type': 'support', 'strength': 0.8, 'price': 100.0},
            {'type': 'resistance', 'strength': 0.6, 'price': 105.0}
        ]
        
        self.manager.process_support_resistance("BTCUSDc", levels_data)
        
        # Wait a bit for background processing
        time.sleep(0.1)
        
        # Check that features were added
        features = self.manager.processor.get_features("BTCUSDc")
        support_resistance_features = [f for f in features if f.feature_type == ContextType.SUPPORT_RESISTANCE]
        assert len(support_resistance_features) == 2
    
    def test_get_context_for_symbol(self):
        """Test getting context for a symbol"""
        # Add some features first
        order_book_data = {
            'bids': [(100.0, 1.5)],
            'asks': [(100.1, 1.2)],
            'timestamp': time.time()
        }
        self.manager.process_order_book_data("BTCUSDc", order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        context_score = self.manager.get_context_for_symbol("BTCUSDc")
        assert context_score is not None
        assert context_score.symbol == "BTCUSDc"
        assert context_score.feature_count > 0
    
    def test_get_all_context_scores(self):
        """Test getting all context scores"""
        # Add features for multiple symbols
        symbols = ["BTCUSDc", "ETHUSDc"]
        for symbol in symbols:
            order_book_data = {
                'bids': [(100.0, 1.5)],
                'asks': [(100.1, 1.2)],
                'timestamp': time.time()
            }
            self.manager.process_order_book_data(symbol, order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        all_scores = self.manager.get_all_context_scores()
        assert len(all_scores) >= 2
        assert "BTCUSDc" in all_scores
        assert "ETHUSDc" in all_scores
    
    def test_get_feature_statistics(self):
        """Test getting feature statistics"""
        # Add some features
        order_book_data = {
            'bids': [(100.0, 1.5)],
            'asks': [(100.1, 1.2)],
            'timestamp': time.time()
        }
        self.manager.process_order_book_data("BTCUSDc", order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        stats = self.manager.get_feature_statistics()
        assert 'total_features' in stats
        assert 'total_symbols' in stats
        assert 'feature_types' in stats
        assert 'status_counts' in stats
        assert 'avg_features_per_symbol' in stats
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_feature_updated = Mock()
        on_context_changed = Mock()
        on_stale_feature = Mock()
        
        self.manager.set_callbacks(
            on_feature_updated=on_feature_updated,
            on_context_changed=on_context_changed,
            on_stale_feature=on_stale_feature
        )
        
        assert self.manager.processor.on_feature_updated == on_feature_updated
        assert self.manager.processor.on_context_changed == on_context_changed
        assert self.manager.processor.on_stale_feature == on_stale_feature

class TestGlobalFunctions:
    """Test global context functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.context_features
        infra.context_features._context_manager = None
    
    def test_get_context_manager(self):
        """Test global context manager access"""
        manager1 = get_context_manager()
        manager2 = get_context_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, ContextFeatureManager)
    
    def test_process_order_book_context(self):
        """Test global order book context processing"""
        order_book_data = {
            'bids': [(100.0, 1.5)],
            'asks': [(100.1, 1.2)],
            'timestamp': time.time()
        }
        
        process_order_book_context("BTCUSDc", order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check that features were added
        manager = get_context_manager()
        features = manager.processor.get_features("BTCUSDc")
        assert len(features) >= 2  # At least imbalance and depth features
    
    def test_process_large_order_context(self):
        """Test global large order context processing"""
        order_data = {
            'size': 1000.0,
            'type': 'market',
            'price': 50000.0,
            'timestamp': time.time()
        }
        
        process_large_order_context("BTCUSDc", order_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        # Check that feature was added
        manager = get_context_manager()
        features = manager.processor.get_features("BTCUSDc")
        large_order_features = [f for f in features if f.feature_type == ContextType.LARGE_ORDER_DETECTION]
        assert len(large_order_features) == 1
    
    def test_get_context_score(self):
        """Test global context score retrieval"""
        # Add some features first
        order_book_data = {
            'bids': [(100.0, 1.5)],
            'asks': [(100.1, 1.2)],
            'timestamp': time.time()
        }
        process_order_book_context("BTCUSDc", order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        context_score = get_context_score("BTCUSDc")
        assert context_score is not None
        assert context_score.symbol == "BTCUSDc"
    
    def test_get_all_context_scores(self):
        """Test global all context scores retrieval"""
        # Add features for multiple symbols
        symbols = ["BTCUSDc", "ETHUSDc"]
        for symbol in symbols:
            order_book_data = {
                'bids': [(100.0, 1.5)],
                'asks': [(100.1, 1.2)],
                'timestamp': time.time()
            }
            process_order_book_context(symbol, order_book_data)
        
        # Wait for processing
        time.sleep(0.1)
        
        all_scores = get_all_context_scores()
        assert len(all_scores) >= 2
        assert "BTCUSDc" in all_scores
        assert "ETHUSDc" in all_scores

class TestContextIntegration:
    """Integration tests for context features system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.context_features
        infra.context_features._context_manager = None
    
    def test_comprehensive_context_processing(self):
        """Test comprehensive context processing"""
        # Process order book data
        order_book_data = {
            'bids': [(100.0, 1.5), (99.9, 2.0)],
            'asks': [(100.1, 1.2), (100.2, 1.8)],
            'timestamp': time.time()
        }
        process_order_book_context("BTCUSDc", order_book_data)
        
        # Process large order
        order_data = {
            'size': 1000.0,
            'type': 'market',
            'price': 50000.0,
            'timestamp': time.time()
        }
        process_large_order_context("BTCUSDc", order_data)
        
        # Process support/resistance
        levels_data = [
            {'type': 'support', 'strength': 0.8, 'price': 100.0},
            {'type': 'resistance', 'strength': 0.6, 'price': 105.0}
        ]
        manager = get_context_manager()
        manager.process_support_resistance("BTCUSDc", levels_data)
        
        # Wait for all processing
        time.sleep(0.2)
        
        # Check context score
        context_score = get_context_score("BTCUSDc")
        assert context_score is not None
        assert context_score.feature_count >= 4  # At least 4 features
        
        # Check feature types
        features = manager.processor.get_features("BTCUSDc")
        feature_types = {f.feature_type for f in features}
        assert ContextType.ORDER_BOOK_IMBALANCE in feature_types
        assert ContextType.ORDER_BOOK_DEPTH in feature_types
        assert ContextType.LARGE_ORDER_DETECTION in feature_types
        assert ContextType.SUPPORT_RESISTANCE in feature_types
    
    def test_non_blocking_operations(self):
        """Test that operations are non-blocking"""
        start_time = time.time()
        
        # Process multiple operations
        for i in range(10):
            order_book_data = {
                'bids': [(100.0 + i, 1.5)],
                'asks': [(100.1 + i, 1.2)],
                'timestamp': time.time()
            }
            process_order_book_context(f"SYMBOL{i}", order_book_data)
        
        end_time = time.time()
        
        # Should complete quickly (non-blocking)
        assert (end_time - start_time) < 0.1  # Less than 100ms
    
    def test_context_scoring_accuracy(self):
        """Test context scoring accuracy"""
        # Add features with known weights
        manager = get_context_manager()
        
        # Add low weight feature
        low_feature = ContextFeature(
            feature_type=ContextType.ORDER_BOOK_DEPTH,
            symbol="TEST",
            value=1.0,
            weight=ContextWeight.LOW,
            confidence=0.8,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE
        )
        manager.processor.add_feature(low_feature)
        
        # Add high weight feature
        high_feature = ContextFeature(
            feature_type=ContextType.LARGE_ORDER_DETECTION,
            symbol="TEST",
            value=2.0,
            weight=ContextWeight.HIGH,
            confidence=0.9,
            timestamp=time.time(),
            status=ContextStatus.ACTIVE
        )
        manager.processor.add_feature(high_feature)
        
        # Check scoring
        context_score = manager.get_context_for_symbol("TEST")
        assert context_score is not None
        assert context_score.total_score == 3.0  # 1.0 + 2.0
        assert context_score.feature_count == 2
        
        # Weighted score should be: 1.0 * 0.1 + 2.0 * 0.6 = 1.3
        expected_weighted = 1.0 * 0.1 + 2.0 * 0.6
        assert abs(context_score.weighted_score - expected_weighted) < 0.001

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
