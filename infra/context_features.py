"""
Context Features System

This module implements a context features system that ensures Binance order book data
is used only for context and never blocks trading decisions. It provides relative
context information without hard gating trading operations.

Key Features:
- Context-only data processing (never blocks decisions)
- Relative context information (trends, momentum, sentiment)
- Non-blocking data integration
- Context feature scoring and weighting
- Real-time context updates
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime, timedelta
import threading
from collections import deque
import numpy as np
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """Types of context features"""
    ORDER_BOOK_DEPTH = "order_book_depth"
    ORDER_BOOK_IMBALANCE = "order_book_imbalance"
    LARGE_ORDER_DETECTION = "large_order_detection"
    SUPPORT_RESISTANCE = "support_resistance"
    VOLUME_PROFILE = "volume_profile"
    MARKET_SENTIMENT = "market_sentiment"
    MOMENTUM_INDICATOR = "momentum_indicator"
    VOLATILITY_CONTEXT = "volatility_context"

class ContextWeight(Enum):
    """Weight levels for context features"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ContextStatus(Enum):
    """Status of context features"""
    ACTIVE = "active"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ERROR = "error"

@dataclass
class ContextFeature:
    """Individual context feature"""
    feature_type: ContextType
    symbol: str
    value: float
    weight: ContextWeight
    confidence: float  # 0.0 to 1.0
    timestamp: float
    status: ContextStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ContextScore:
    """Context score for a symbol"""
    symbol: str
    total_score: float
    weighted_score: float
    feature_count: int
    last_update: float
    features: List[ContextFeature] = field(default_factory=list)

@dataclass
class ContextConfig:
    """Configuration for context features"""
    max_features_per_symbol: int = 100
    feature_timeout_ms: int = 5000
    update_interval_ms: int = 1000
    stale_threshold_ms: int = 10000
    confidence_threshold: float = 0.5
    weight_multipliers: Dict[ContextWeight, float] = field(default_factory=lambda: {
        ContextWeight.LOW: 0.1,
        ContextWeight.MEDIUM: 0.3,
        ContextWeight.HIGH: 0.6,
        ContextWeight.CRITICAL: 1.0
    })
    enable_non_blocking: bool = True
    enable_context_scoring: bool = True

class ContextFeatureProcessor:
    """Processes and manages context features"""
    
    def __init__(self, config: ContextConfig):
        self.config = config
        self.features: Dict[str, List[ContextFeature]] = {}
        self.context_scores: Dict[str, ContextScore] = {}
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Callbacks
        self.on_feature_updated: Optional[Callable[[ContextFeature], None]] = None
        self.on_context_changed: Optional[Callable[[ContextScore], None]] = None
        self.on_stale_feature: Optional[Callable[[ContextFeature], None]] = None
    
    def set_callbacks(self,
                      on_feature_updated: Optional[Callable[[ContextFeature], None]] = None,
                      on_context_changed: Optional[Callable[[ContextScore], None]] = None,
                      on_stale_feature: Optional[Callable[[ContextFeature], None]] = None) -> None:
        """Set callback functions for context events"""
        self.on_feature_updated = on_feature_updated
        self.on_context_changed = on_context_changed
        self.on_stale_feature = on_stale_feature
    
    def add_feature(self, feature: ContextFeature) -> None:
        """Add a context feature (non-blocking)"""
        with self.lock:
            symbol = feature.symbol
            
            # Initialize symbol if not exists
            if symbol not in self.features:
                self.features[symbol] = []
                self.context_scores[symbol] = ContextScore(
                    symbol=symbol,
                    total_score=0.0,
                    weighted_score=0.0,
                    feature_count=0,
                    last_update=time.time()
                )
            
            # Add feature
            self.features[symbol].append(feature)
            
            # Maintain max features per symbol
            if len(self.features[symbol]) > self.config.max_features_per_symbol:
                self.features[symbol] = self.features[symbol][-self.config.max_features_per_symbol:]
            
            # Update context score
            self._update_context_score(symbol)
            
            # Call feature updated callback
            if self.on_feature_updated:
                try:
                    self.on_feature_updated(feature)
                except Exception as e:
                    logger.error(f"Error in on_feature_updated callback: {e}")
    
    def _update_context_score(self, symbol: str) -> None:
        """Update context score for a symbol"""
        if symbol not in self.features:
            return
        
        features = self.features[symbol]
        current_time = time.time()
        
        # Filter active features
        active_features = [
            f for f in features 
            if f.status == ContextStatus.ACTIVE and 
            (current_time - f.timestamp) < (self.config.stale_threshold_ms / 1000.0)
        ]
        
        if not active_features:
            return
        
        # Calculate scores
        total_score = sum(f.value for f in active_features)
        weighted_score = sum(
            f.value * self.config.weight_multipliers[f.weight] 
            for f in active_features
        )
        
        # Update context score
        self.context_scores[symbol] = ContextScore(
            symbol=symbol,
            total_score=total_score,
            weighted_score=weighted_score,
            feature_count=len(active_features),
            last_update=current_time,
            features=active_features
        )
        
        # Call context changed callback
        if self.on_context_changed:
            try:
                self.on_context_changed(self.context_scores[symbol])
            except Exception as e:
                logger.error(f"Error in on_context_changed callback: {e}")
    
    def get_context_score(self, symbol: str) -> Optional[ContextScore]:
        """Get context score for a symbol"""
        with self.lock:
            return self.context_scores.get(symbol)
    
    def get_features(self, symbol: str, feature_type: Optional[ContextType] = None) -> List[ContextFeature]:
        """Get features for a symbol, optionally filtered by type"""
        with self.lock:
            if symbol not in self.features:
                return []
            
            features = self.features[symbol]
            
            if feature_type:
                features = [f for f in features if f.feature_type == feature_type]
            
            return features
    
    def get_all_context_scores(self) -> Dict[str, ContextScore]:
        """Get all context scores"""
        with self.lock:
            return dict(self.context_scores)
    
    def cleanup_stale_features(self) -> int:
        """Clean up stale features and return count of removed features"""
        with self.lock:
            current_time = time.time()
            stale_threshold = self.config.stale_threshold_ms / 1000.0
            removed_count = 0
            
            for symbol in list(self.features.keys()):
                features = self.features[symbol]
                stale_features = []
                active_features = []
                
                for feature in features:
                    if (current_time - feature.timestamp) > stale_threshold:
                        feature.status = ContextStatus.STALE
                        stale_features.append(feature)
                        
                        # Call stale feature callback
                        if self.on_stale_feature:
                            try:
                                self.on_stale_feature(feature)
                            except Exception as e:
                                logger.error(f"Error in on_stale_feature callback: {e}")
                    else:
                        active_features.append(feature)
                
                self.features[symbol] = active_features
                removed_count += len(stale_features)
                
                # Update context score if features changed
                if stale_features:
                    self._update_context_score(symbol)
            
            return removed_count
    
    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get feature statistics"""
        with self.lock:
            total_features = sum(len(features) for features in self.features.values())
            total_symbols = len(self.features)
            
            feature_types = {}
            status_counts = {}
            
            for symbol, features in self.features.items():
                for feature in features:
                    # Count by type
                    feature_type = feature.feature_type.value
                    feature_types[feature_type] = feature_types.get(feature_type, 0) + 1
                    
                    # Count by status
                    status = feature.status.value
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_features': total_features,
                'total_symbols': total_symbols,
                'feature_types': feature_types,
                'status_counts': status_counts,
                'avg_features_per_symbol': total_features / max(1, total_symbols)
            }

class OrderBookContextProcessor:
    """Processes order book data for context features"""
    
    def __init__(self, context_processor: ContextFeatureProcessor):
        self.context_processor = context_processor
        self.lock = threading.RLock()
    
    def process_order_book_depth(self, symbol: str, bids: List[Tuple[float, float]], 
                                asks: List[Tuple[float, float]], timestamp: float) -> None:
        """Process order book depth for context features"""
        try:
            # Calculate order book imbalance
            imbalance = self._calculate_order_book_imbalance(bids, asks)
            
            # Create imbalance feature
            feature = ContextFeature(
                feature_type=ContextType.ORDER_BOOK_IMBALANCE,
                symbol=symbol,
                value=imbalance,
                weight=ContextWeight.MEDIUM,
                confidence=0.8,
                timestamp=timestamp,
                status=ContextStatus.ACTIVE,
                metadata={
                    'bid_count': len(bids),
                    'ask_count': len(asks),
                    'total_volume': sum(vol for _, vol in bids + asks)
                }
            )
            
            self.context_processor.add_feature(feature)
            
            # Calculate depth feature
            depth_score = self._calculate_depth_score(bids, asks)
            
            depth_feature = ContextFeature(
                feature_type=ContextType.ORDER_BOOK_DEPTH,
                symbol=symbol,
                value=depth_score,
                weight=ContextWeight.LOW,
                confidence=0.7,
                timestamp=timestamp,
                status=ContextStatus.ACTIVE,
                metadata={
                    'bid_depth': len(bids),
                    'ask_depth': len(asks)
                }
            )
            
            self.context_processor.add_feature(depth_feature)
            
        except Exception as e:
            logger.error(f"Error processing order book depth for {symbol}: {e}")
    
    def _calculate_order_book_imbalance(self, bids: List[Tuple[float, float]], 
                                       asks: List[Tuple[float, float]]) -> float:
        """Calculate order book imbalance"""
        if not bids or not asks:
            return 0.0
        
        bid_volume = sum(vol for _, vol in bids)
        ask_volume = sum(vol for _, vol in asks)
        
        if bid_volume + ask_volume == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / (bid_volume + ask_volume)
    
    def _calculate_depth_score(self, bids: List[Tuple[float, float]], 
                             asks: List[Tuple[float, float]]) -> float:
        """Calculate order book depth score"""
        if not bids or not asks:
            return 0.0
        
        # Calculate depth as average of bid and ask levels
        bid_levels = len(bids)
        ask_levels = len(asks)
        
        return (bid_levels + ask_levels) / 2.0

class LargeOrderContextProcessor:
    """Processes large order detection for context features"""
    
    def __init__(self, context_processor: ContextFeatureProcessor):
        self.context_processor = context_processor
        self.lock = threading.RLock()
    
    def process_large_order(self, symbol: str, order_size: float, order_type: str,
                          price: float, timestamp: float) -> None:
        """Process large order detection for context features"""
        try:
            # Calculate large order impact score
            impact_score = self._calculate_impact_score(order_size, order_type, price)
            
            # Create large order feature
            feature = ContextFeature(
                feature_type=ContextType.LARGE_ORDER_DETECTION,
                symbol=symbol,
                value=impact_score,
                weight=ContextWeight.HIGH,
                confidence=0.9,
                timestamp=timestamp,
                status=ContextStatus.ACTIVE,
                metadata={
                    'order_size': order_size,
                    'order_type': order_type,
                    'price': price,
                    'impact_score': impact_score
                }
            )
            
            self.context_processor.add_feature(feature)
            
        except Exception as e:
            logger.error(f"Error processing large order for {symbol}: {e}")
    
    def _calculate_impact_score(self, order_size: float, order_type: str, price: float) -> float:
        """Calculate large order impact score"""
        # Base impact on order size relative to price
        size_impact = order_size / max(price, 1.0)
        
        # Adjust based on order type
        type_multiplier = 1.0
        if order_type.lower() in ['market', 'immediate']:
            type_multiplier = 1.5
        elif order_type.lower() in ['limit', 'resting']:
            type_multiplier = 0.8
        
        return size_impact * type_multiplier

class SupportResistanceContextProcessor:
    """Processes support/resistance levels for context features"""
    
    def __init__(self, context_processor: ContextFeatureProcessor):
        self.context_processor = context_processor
        self.lock = threading.RLock()
    
    def process_support_resistance(self, symbol: str, levels: List[Dict[str, Any]], 
                                 timestamp: float) -> None:
        """Process support/resistance levels for context features"""
        try:
            for level in levels:
                level_type = level.get('type', 'unknown')
                strength = level.get('strength', 0.0)
                price = level.get('price', 0.0)
                
                # Create support/resistance feature
                feature = ContextFeature(
                    feature_type=ContextType.SUPPORT_RESISTANCE,
                    symbol=symbol,
                    value=strength,
                    weight=ContextWeight.MEDIUM,
                    confidence=0.7,
                    timestamp=timestamp,
                    status=ContextStatus.ACTIVE,
                    metadata={
                        'level_type': level_type,
                        'price': price,
                        'strength': strength
                    }
                )
                
                self.context_processor.add_feature(feature)
                
        except Exception as e:
            logger.error(f"Error processing support/resistance for {symbol}: {e}")

class ContextFeatureManager:
    """Main context feature manager"""
    
    def __init__(self, config: ContextConfig):
        self.config = config
        self.processor = ContextFeatureProcessor(config)
        self.order_book_processor = OrderBookContextProcessor(self.processor)
        self.large_order_processor = LargeOrderContextProcessor(self.processor)
        self.support_resistance_processor = SupportResistanceContextProcessor(self.processor)
        self.lock = threading.RLock()
        
        # Start cleanup task
        self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.config.update_interval_ms / 1000.0)
                    removed_count = self.processor.cleanup_stale_features()
                    if removed_count > 0:
                        logger.debug(f"Cleaned up {removed_count} stale features")
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def process_order_book_data(self, symbol: str, order_book_data: Dict[str, Any]) -> None:
        """Process order book data for context features (non-blocking)"""
        try:
            bids = order_book_data.get('bids', [])
            asks = order_book_data.get('asks', [])
            timestamp = order_book_data.get('timestamp', time.time())
            
            # Process in background to avoid blocking
            self.processor.executor.submit(
                self.order_book_processor.process_order_book_depth,
                symbol, bids, asks, timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing order book data for {symbol}: {e}")
    
    def process_large_order(self, symbol: str, order_data: Dict[str, Any]) -> None:
        """Process large order data for context features (non-blocking)"""
        try:
            order_size = order_data.get('size', 0.0)
            order_type = order_data.get('type', 'unknown')
            price = order_data.get('price', 0.0)
            timestamp = order_data.get('timestamp', time.time())
            
            # Process in background to avoid blocking
            self.processor.executor.submit(
                self.large_order_processor.process_large_order,
                symbol, order_size, order_type, price, timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing large order for {symbol}: {e}")
    
    def process_support_resistance(self, symbol: str, levels_data: List[Dict[str, Any]]) -> None:
        """Process support/resistance data for context features (non-blocking)"""
        try:
            timestamp = time.time()
            
            # Process in background to avoid blocking
            self.processor.executor.submit(
                self.support_resistance_processor.process_support_resistance,
                symbol, levels_data, timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing support/resistance for {symbol}: {e}")
    
    def get_context_for_symbol(self, symbol: str) -> Optional[ContextScore]:
        """Get context score for a symbol (non-blocking)"""
        return self.processor.get_context_score(symbol)
    
    def get_all_context_scores(self) -> Dict[str, ContextScore]:
        """Get all context scores (non-blocking)"""
        return self.processor.get_all_context_scores()
    
    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get feature statistics (non-blocking)"""
        return self.processor.get_feature_statistics()
    
    def set_callbacks(self,
                      on_feature_updated: Optional[Callable[[ContextFeature], None]] = None,
                      on_context_changed: Optional[Callable[[ContextScore], None]] = None,
                      on_stale_feature: Optional[Callable[[ContextFeature], None]] = None) -> None:
        """Set callback functions for context events"""
        self.processor.set_callbacks(
            on_feature_updated=on_feature_updated,
            on_context_changed=on_context_changed,
            on_stale_feature=on_stale_feature
        )

# Global context feature manager
_context_manager: Optional[ContextFeatureManager] = None

def get_context_manager(config: Optional[ContextConfig] = None) -> ContextFeatureManager:
    """Get global context feature manager instance"""
    global _context_manager
    if _context_manager is None:
        if config is None:
            config = ContextConfig()
        _context_manager = ContextFeatureManager(config)
    return _context_manager

def process_order_book_context(symbol: str, order_book_data: Dict[str, Any]) -> None:
    """Process order book data for context features"""
    manager = get_context_manager()
    manager.process_order_book_data(symbol, order_book_data)

def process_large_order_context(symbol: str, order_data: Dict[str, Any]) -> None:
    """Process large order data for context features"""
    manager = get_context_manager()
    manager.process_large_order(symbol, order_data)

def get_context_score(symbol: str) -> Optional[ContextScore]:
    """Get context score for a symbol"""
    manager = get_context_manager()
    return manager.get_context_for_symbol(symbol)

def get_all_context_scores() -> Dict[str, ContextScore]:
    """Get all context scores"""
    manager = get_context_manager()
    return manager.get_all_context_scores()

if __name__ == "__main__":
    # Example usage
    config = ContextConfig(
        max_features_per_symbol=50,
        feature_timeout_ms=5000,
        update_interval_ms=1000,
        enable_non_blocking=True
    )
    
    manager = ContextFeatureManager(config)
    
    # Process some order book data
    order_book_data = {
        'bids': [(100.0, 1.5), (99.9, 2.0), (99.8, 1.0)],
        'asks': [(100.1, 1.2), (100.2, 1.8), (100.3, 0.9)],
        'timestamp': time.time()
    }
    
    manager.process_order_book_data("BTCUSDc", order_book_data)
    
    # Wait a bit for processing
    time.sleep(0.1)
    
    # Get context score
    context_score = manager.get_context_for_symbol("BTCUSDc")
    if context_score:
        print(f"Context score for BTCUSDc: {context_score.total_score}")
        print(f"Weighted score: {context_score.weighted_score}")
        print(f"Feature count: {context_score.feature_count}")
    
    # Get statistics
    stats = manager.get_feature_statistics()
    print(f"Feature statistics: {stats}")
