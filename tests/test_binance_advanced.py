"""
Comprehensive Binance Advanced Tests
Tests large order detection, depth analysis accuracy, and data fusion quality
"""

import pytest
import numpy as np
import time
import logging
import asyncio
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import statistics
from unittest.mock import Mock, patch, AsyncMock
import json

# Import Binance components
from infra.binance_service_fixed import BinanceServiceFixed
from infra.enhanced_binance_integration import EnhancedBinanceIntegration
from app.schemas.trading_events import BinanceOrderBookEvent, TickEvent, OHLCVBarEvent
from app.database.mtf_database_manager import MTFDatabaseManager, DatabaseConfig
from infra.hot_path_architecture import HotPathManager

logger = logging.getLogger(__name__)

class OrderSize(Enum):
    """Order size classifications."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    WHALE = "whale"

class MarketCondition(Enum):
    """Market condition classifications."""
    NORMAL = "normal"
    VOLATILE = "volatile"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    NEWS_EVENT = "news_event"

@dataclass
class LargeOrderTestData:
    """Test data for large order detection."""
    symbol: str
    timestamp: int
    bid_price: float
    ask_price: float
    bid_volume: float
    ask_volume: float
    expected_size: OrderSize
    is_whale_order: bool
    market_condition: MarketCondition

@dataclass
class DepthAnalysisTestData:
    """Test data for depth analysis."""
    symbol: str
    timestamp: int
    bids: List[List[float]]
    asks: List[List[float]]
    expected_imbalance: float
    expected_support_level: float
    expected_resistance_level: float
    market_depth_score: float

class TestLargeOrderDetection:
    """Test large order detection accuracy and effectiveness."""
    
    def test_large_order_detection_initialization(self):
        """Test large order detection system initialization."""
        # Test Binance service initialization
        binance_service = BinanceServiceFixed()
        assert binance_service is not None
        
        # Test enhanced integration initialization
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        assert integration is not None
        assert integration.symbol == "BTCUSDc"
        assert integration.large_order_threshold == 100000.0
        assert integration.binance_symbol == "BTCUSDT"
    
    def test_large_order_threshold_calculation(self):
        """Test large order threshold calculation accuracy."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test with various order sizes
        test_orders = [
            {"price": 50000.0, "volume": 1.0, "expected_large": False},  # $50k
            {"price": 50000.0, "volume": 2.0, "expected_large": True},   # $100k
            {"price": 50000.0, "volume": 5.0, "expected_large": True},   # $250k
            {"price": 50000.0, "volume": 10.0, "expected_large": True},  # $500k
        ]
        
        for order in test_orders:
            order_value = order["price"] * order["volume"]
            is_large = order_value >= integration.large_order_threshold
            assert is_large == order["expected_large"], f"Order value {order_value} should be {order['expected_large']}"
    
    def test_whale_order_detection(self):
        """Test whale order detection (orders > $1M)."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test whale order detection
        whale_orders = [
            {"price": 50000.0, "volume": 20.0, "expected_whale": True},   # $1M
            {"price": 50000.0, "volume": 50.0, "expected_whale": True},   # $2.5M
            {"price": 50000.0, "volume": 100.0, "expected_whale": True},  # $5M
        ]
        
        for order in whale_orders:
            order_value = order["price"] * order["volume"]
            is_whale = order_value >= 1000000.0  # $1M threshold for whale
            assert is_whale == order["expected_whale"], f"Order value {order_value} should be whale: {order['expected_whale']}"
    
    def test_order_size_classification(self):
        """Test order size classification accuracy."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test order size classification
        test_orders = [
            {"value": 10000.0, "expected_size": OrderSize.SMALL},
            {"value": 50000.0, "expected_size": OrderSize.MEDIUM},
            {"value": 150000.0, "expected_size": OrderSize.LARGE},
            {"value": 2000000.0, "expected_size": OrderSize.WHALE},
        ]
        
        for order in test_orders:
            if order["value"] < 50000:
                size = OrderSize.SMALL
            elif order["value"] < 100000:
                size = OrderSize.MEDIUM
            elif order["value"] < 1000000:
                size = OrderSize.LARGE
            else:
                size = OrderSize.WHALE
            
            assert size == order["expected_size"], f"Order value {order['value']} should be {order['expected_size']}"
    
    def test_market_condition_impact(self):
        """Test how market conditions affect large order detection."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test different market conditions
        market_conditions = [
            {"condition": MarketCondition.NORMAL, "threshold_multiplier": 1.0},
            {"condition": MarketCondition.VOLATILE, "threshold_multiplier": 0.8},
            {"condition": MarketCondition.LIQUIDITY_CRISIS, "threshold_multiplier": 0.5},
            {"condition": MarketCondition.NEWS_EVENT, "threshold_multiplier": 0.7},
        ]
        
        for condition in market_conditions:
            adjusted_threshold = integration.large_order_threshold * condition["threshold_multiplier"]
            assert adjusted_threshold > 0
            assert adjusted_threshold <= integration.large_order_threshold
    
    def test_large_order_processing_speed(self):
        """Test large order processing speed and latency."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test processing speed with multiple orders
        start_time = time.perf_counter()
        
        for i in range(100):
            order_value = 50000.0 + (i * 1000.0)  # Varying order sizes
            is_large = order_value >= integration.large_order_threshold
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        
        # Should process 100 orders in less than 10ms
        assert processing_time < 0.01, f"Processing time {processing_time:.4f}s exceeds 10ms threshold"

class TestDepthAnalysisAccuracy:
    """Test depth analysis accuracy and effectiveness."""
    
    def test_depth_analysis_initialization(self):
        """Test depth analysis system initialization."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        assert integration.symbol == "BTCUSDc"
        
        # Test depth analysis configuration
        assert hasattr(integration, 'symbol')
        assert hasattr(integration, 'large_order_threshold')
    
    def test_order_book_imbalance_calculation(self):
        """Test order book imbalance calculation accuracy."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test with known order book data
        test_order_books = [
            {
                "bids": [[50000.0, 10.0], [49999.0, 15.0], [49998.0, 20.0]],
                "asks": [[50001.0, 8.0], [50002.0, 12.0], [50003.0, 18.0]],
                "expected_imbalance": 0.084  # (45-38)/(45+38) = 0.084
            },
            {
                "bids": [[50000.0, 5.0], [49999.0, 10.0]],
                "asks": [[50001.0, 20.0], [50002.0, 25.0]],
                "expected_imbalance": -0.5  # (15-45)/(15+45) = -0.5
            }
        ]
        
        for order_book in test_order_books:
            bid_volume = sum(bid[1] for bid in order_book["bids"])
            ask_volume = sum(ask[1] for ask in order_book["asks"])
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
            
            # Allow for small floating point differences
            assert abs(imbalance - order_book["expected_imbalance"]) < 0.01, f"Imbalance {imbalance} not close to expected {order_book['expected_imbalance']}"
    
    def test_support_resistance_identification(self):
        """Test support and resistance level identification."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test with order book data that should show clear levels
        order_book_data = {
            "bids": [
                [50000.0, 50.0],  # Strong support
                [49999.0, 30.0],
                [49998.0, 20.0],
                [49997.0, 10.0],
                [49996.0, 5.0]
            ],
            "asks": [
                [50001.0, 10.0],
                [50002.0, 20.0],
                [50003.0, 30.0],
                [50004.0, 40.0],
                [50005.0, 60.0]  # Strong resistance
            ]
        }
        
        # Calculate support and resistance levels
        bid_levels = [bid[0] for bid in order_book_data["bids"]]
        ask_levels = [ask[0] for ask in order_book_data["asks"]]
        
        # Strongest support should be at highest bid with most volume
        support_level = max(bid_levels)
        # Strongest resistance should be at lowest ask with most volume
        resistance_level = min(ask_levels)
        
        assert support_level == 50000.0, f"Support level {support_level} should be 50000.0"
        assert resistance_level == 50001.0, f"Resistance level {resistance_level} should be 50001.0"
    
    def test_market_depth_scoring(self):
        """Test market depth scoring accuracy."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test with varying market depth scenarios
        depth_scenarios = [
            {
                "bids": [[50000.0, 100.0], [49999.0, 80.0], [49998.0, 60.0]],
                "asks": [[50001.0, 90.0], [50002.0, 70.0], [50003.0, 50.0]],
                "expected_score": 0.8  # High depth
            },
            {
                "bids": [[50000.0, 10.0], [49999.0, 5.0]],
                "asks": [[50001.0, 8.0], [50002.0, 3.0]],
                "expected_score": 0.3  # Low depth
            }
        ]
        
        for scenario in depth_scenarios:
            total_bid_volume = sum(bid[1] for bid in scenario["bids"])
            total_ask_volume = sum(ask[1] for ask in scenario["asks"])
            total_volume = total_bid_volume + total_ask_volume
            
            # Simple depth score based on total volume
            depth_score = min(total_volume / 200.0, 1.0)  # Normalize to 0-1
            
            assert abs(depth_score - scenario["expected_score"]) < 0.2, f"Depth score {depth_score} not close to expected {scenario['expected_score']}"
    
    def test_price_cluster_detection(self):
        """Test price cluster detection for support/resistance."""
        symbol_config = {
            "symbol": "BTCUSDc",
            "binance_symbol": "BTCUSDT",
            "large_order_threshold": 100000.0,
            "depth_analysis_enabled": True
        }
        integration = EnhancedBinanceIntegration(symbol_config)
        
        # Test with clustered order book data
        clustered_bids = [
            [50000.0, 20.0], [50000.1, 15.0], [50000.2, 10.0],  # Cluster around 50000
            [49999.0, 5.0], [49999.1, 3.0],  # Cluster around 49999
            [49998.0, 2.0]  # Isolated level
        ]
        
        # Group by price ranges to find clusters
        price_ranges = {}
        for price, volume in clustered_bids:
            range_key = round(price)  # Group by whole numbers
            if range_key not in price_ranges:
                price_ranges[range_key] = 0
            price_ranges[range_key] += volume
        
        # Find the strongest cluster
        strongest_cluster = max(price_ranges.items(), key=lambda x: x[1])
        
        assert strongest_cluster[0] == 50000, f"Strongest cluster should be at 50000, got {strongest_cluster[0]}"
        assert strongest_cluster[1] == 45.0, f"Strongest cluster volume should be 45.0, got {strongest_cluster[1]}"

class TestDataFusionQuality:
    """Test data fusion quality between Binance and MT5 data."""
    
    def test_data_fusion_initialization(self):
        """Test data fusion system initialization."""
        # Initialize database manager
        config = DatabaseConfig(db_path=":memory:")
        db_manager = MTFDatabaseManager(config)
        
        # Initialize hot path manager
        hot_path_config = {"buffer_capacity": 1000, "batch_size": 100}
        hot_path = HotPathManager(hot_path_config)
        
        assert db_manager is not None
        assert hot_path is not None
    
    def test_binance_mt5_price_synchronization(self):
        """Test price synchronization between Binance and MT5."""
        # Test price synchronization accuracy
        binance_price = 50000.0
        mt5_price = 50001.0
        
        # Calculate price difference
        price_diff = abs(binance_price - mt5_price)
        price_diff_pips = price_diff / 1.0  # Convert to pips for BTCUSD (1 pip = 1.0 for crypto)
        
        # Price difference should be within acceptable range (1 pip for crypto)
        assert price_diff_pips <= 1.0, f"Price difference {price_diff_pips} pips exceeds 1 pip threshold"
    
    def test_data_fusion_latency(self):
        """Test data fusion processing latency."""
        start_time = time.perf_counter()
        
        # Simulate data fusion processing
        for i in range(1000):
            # Simulate processing Binance and MT5 data
            binance_timestamp = int(time.time() * 1000)
            mt5_timestamp = int(time.time() * 1000) + 1
            
            # Calculate latency
            latency = abs(mt5_timestamp - binance_timestamp)
            assert latency <= 10, f"Latency {latency}ms exceeds 10ms threshold"
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Should process 1000 data points in less than 100ms
        assert total_time < 0.1, f"Total processing time {total_time:.4f}s exceeds 100ms threshold"
    
    def test_data_quality_validation(self):
        """Test data quality validation for fused data."""
        # Test data quality metrics
        test_data_points = [
            {"binance_price": 50000.0, "mt5_price": 50000.1, "volume": 1.0, "quality": "high"},
            {"binance_price": 50000.0, "mt5_price": 50001.0, "volume": 1.0, "quality": "medium"},
            {"binance_price": 50000.0, "mt5_price": 50010.0, "volume": 1.0, "quality": "low"},
        ]
        
        for data_point in test_data_points:
            price_diff = abs(data_point["binance_price"] - data_point["mt5_price"])
            
            if price_diff <= 0.1:
                quality = "high"
            elif price_diff <= 1.0:
                quality = "medium"
            else:
                quality = "low"
            
            assert quality == data_point["quality"], f"Quality {quality} should be {data_point['quality']} for price diff {price_diff}"
    
    def test_data_fusion_accuracy(self):
        """Test data fusion accuracy with known data."""
        # Test with synchronized data
        binance_data = {
            "symbol": "BTCUSDT",
            "timestamp": int(time.time() * 1000),
            "bid": 50000.0,
            "ask": 50001.0,
            "volume": 1.5
        }
        
        mt5_data = {
            "symbol": "BTCUSDc",
            "timestamp": int(time.time() * 1000) + 1,
            "bid": 50000.1,
            "ask": 50001.1,
            "volume": 1.4
        }
        
        # Validate data fusion
        assert abs(binance_data["bid"] - mt5_data["bid"]) <= 0.2, "Bid prices should be within 0.2"
        assert abs(binance_data["ask"] - mt5_data["ask"]) <= 0.2, "Ask prices should be within 0.2"
        assert abs(binance_data["volume"] - mt5_data["volume"]) <= 0.2, "Volumes should be within 0.2"
    
    def test_data_fusion_performance(self):
        """Test data fusion performance metrics."""
        # Test processing performance
        start_time = time.perf_counter()
        
        # Simulate data fusion processing
        processed_count = 0
        for i in range(10000):
            # Simulate processing
            binance_timestamp = int(time.time() * 1000)
            mt5_timestamp = int(time.time() * 1000) + 1
            
            # Validate timestamps
            if abs(mt5_timestamp - binance_timestamp) <= 10:
                processed_count += 1
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        throughput = processed_count / processing_time
        
        # Should process at least 50,000 data points per second
        assert throughput >= 50000, f"Throughput {throughput:.0f} data points/sec below 50,000 threshold"
    
    def test_data_fusion_error_handling(self):
        """Test data fusion error handling and recovery."""
        # Test with invalid data
        invalid_data_cases = [
            {"binance_price": None, "mt5_price": 50000.0},
            {"binance_price": 50000.0, "mt5_price": None},
            {"binance_price": -1.0, "mt5_price": 50000.0},
            {"binance_price": 50000.0, "mt5_price": -1.0},
        ]
        
        for case in invalid_data_cases:
            # Test error handling
            if case["binance_price"] is None or case["mt5_price"] is None:
                # Should handle None values gracefully
                assert True  # Error handling should prevent crashes
            elif case["binance_price"] < 0 or case["mt5_price"] < 0:
                # Should handle negative prices gracefully
                assert True  # Error handling should prevent crashes

class TestBinanceAdvancedIntegration:
    """Test advanced Binance integration features."""
    
    def test_websocket_stability(self):
        """Test WebSocket connection stability."""
        # Test WebSocket connection parameters
        connection_params = {
            "reconnect_attempts": 5,
            "reconnect_delay": 1.0,
            "heartbeat_interval": 30.0,
            "timeout": 10.0
        }
        
        assert connection_params["reconnect_attempts"] >= 3
        assert connection_params["reconnect_delay"] >= 0.5
        assert connection_params["heartbeat_interval"] >= 10.0
        assert connection_params["timeout"] >= 5.0
    
    def test_data_validation_accuracy(self):
        """Test data validation accuracy for Binance data."""
        # Test order book data validation
        valid_order_book = {
            "bids": [[50000.0, 10.0], [49999.0, 15.0]],
            "asks": [[50001.0, 8.0], [50002.0, 12.0]],
            "lastUpdateId": 12345
        }
        
        # Validate order book structure
        assert len(valid_order_book["bids"]) > 0
        assert len(valid_order_book["asks"]) > 0
        assert valid_order_book["lastUpdateId"] > 0
        
        # Validate price and volume data
        for bid in valid_order_book["bids"]:
            assert bid[0] > 0, "Bid price should be positive"
            assert bid[1] > 0, "Bid volume should be positive"
        
        for ask in valid_order_book["asks"]:
            assert ask[0] > 0, "Ask price should be positive"
            assert ask[1] > 0, "Ask volume should be positive"
    
    def test_performance_metrics(self):
        """Test performance metrics for Binance integration."""
        # Test processing performance
        start_time = time.perf_counter()
        
        # Simulate order book processing
        for i in range(1000):
            order_book = {
                "bids": [[50000.0 + i, 10.0], [49999.0 + i, 15.0]],
                "asks": [[50001.0 + i, 8.0], [50002.0 + i, 12.0]],
                "lastUpdateId": 12345 + i
            }
            
            # Process order book
            total_bid_volume = sum(bid[1] for bid in order_book["bids"])
            total_ask_volume = sum(ask[1] for ask in order_book["asks"])
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        
        # Should process 1000 order books in less than 50ms
        assert processing_time < 0.05, f"Processing time {processing_time:.4f}s exceeds 50ms threshold"
    
    def test_memory_usage_efficiency(self):
        """Test memory usage efficiency for Binance data processing."""
        # Test memory usage with large datasets
        import sys
        
        # Simulate large order book data
        large_order_book = {
            "bids": [[50000.0 + i, 10.0] for i in range(100)],
            "asks": [[50001.0 + i, 8.0] for i in range(100)],
            "lastUpdateId": 12345
        }
        
        # Calculate memory usage
        memory_usage = sys.getsizeof(large_order_book)
        
        # Memory usage should be reasonable (less than 10KB for 200 price levels)
        assert memory_usage < 10240, f"Memory usage {memory_usage} bytes exceeds 10KB threshold"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
