"""
Binance Context Integration for Multi-Timeframe Trading
Context features only - never blocks trading decisions
"""

import asyncio
import websockets
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class OrderBookSnapshot:
    """Order book snapshot for context analysis"""
    symbol: str
    timestamp_utc: int
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]
    spread: float
    mid_price: float
    volume_imbalance: float
    large_orders: List[Dict[str, Any]]

@dataclass
class MarketMicrostructure:
    """Market microstructure analysis"""
    symbol: str
    timestamp_utc: int
    bid_ask_spread: float
    volume_imbalance: float
    order_flow_imbalance: float
    large_order_ratio: float
    support_resistance_levels: List[float]
    liquidity_zones: List[Dict[str, Any]]

class BinanceContextAnalyzer:
    """Binance context analyzer for market microstructure"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        self.symbol = symbol
        self.config = config
        self.order_book_cache = deque(maxlen=1000)
        self.microstructure_cache = deque(maxlen=100)
        
        # Analysis parameters
        self.large_order_threshold = config.get('large_order_threshold', 0.1)  # 10% of average
        self.support_resistance_lookback = config.get('support_resistance_lookback', 50)
        self.volume_imbalance_threshold = config.get('volume_imbalance_threshold', 0.3)
        
    def analyze_order_book(self, snapshot: OrderBookSnapshot) -> MarketMicrostructure:
        """Analyze order book for market microstructure"""
        try:
            # Calculate basic metrics
            spread = snapshot.spread
            mid_price = snapshot.mid_price
            
            # Calculate volume imbalance
            bid_volume = sum(bid[1] for bid in snapshot.bids[:5])  # Top 5 levels
            ask_volume = sum(ask[1] for ask in snapshot.asks[:5])
            volume_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
            
            # Calculate order flow imbalance
            order_flow_imbalance = self._calculate_order_flow_imbalance(snapshot)
            
            # Detect large orders
            large_orders = self._detect_large_orders(snapshot)
            large_order_ratio = len(large_orders) / max(len(snapshot.bids) + len(snapshot.asks), 1)
            
            # Identify support/resistance levels
            support_resistance = self._identify_support_resistance(snapshot)
            
            # Identify liquidity zones
            liquidity_zones = self._identify_liquidity_zones(snapshot)
            
            return MarketMicrostructure(
                symbol=self.symbol,
                timestamp_utc=snapshot.timestamp_utc,
                bid_ask_spread=spread,
                volume_imbalance=volume_imbalance,
                order_flow_imbalance=order_flow_imbalance,
                large_order_ratio=large_order_ratio,
                support_resistance_levels=support_resistance,
                liquidity_zones=liquidity_zones
            )
            
        except Exception as e:
            logger.error(f"Error analyzing order book for {self.symbol}: {e}")
            return self._create_empty_microstructure(snapshot.timestamp_utc)
            
    def _calculate_order_flow_imbalance(self, snapshot: OrderBookSnapshot) -> float:
        """Calculate order flow imbalance"""
        try:
            # Simple order flow calculation based on bid/ask pressure
            bid_pressure = sum(bid[1] for bid in snapshot.bids[:3])  # Top 3 levels
            ask_pressure = sum(ask[1] for ask in snapshot.asks[:3])
            
            if bid_pressure + ask_pressure == 0:
                return 0
                
            return (bid_pressure - ask_pressure) / (bid_pressure + ask_pressure)
            
        except Exception as e:
            logger.error(f"Error calculating order flow imbalance: {e}")
            return 0.0
            
    def _detect_large_orders(self, snapshot: OrderBookSnapshot) -> List[Dict[str, Any]]:
        """Detect large orders in order book"""
        try:
            large_orders = []
            
            # Calculate average order size
            all_orders = snapshot.bids + snapshot.asks
            if not all_orders:
                return large_orders
                
            avg_size = np.mean([order[1] for order in all_orders])
            threshold = avg_size * self.large_order_threshold
            
            # Find large orders
            for i, (price, quantity) in enumerate(snapshot.bids):
                if quantity > threshold:
                    large_orders.append({
                        'side': 'bid',
                        'price': price,
                        'quantity': quantity,
                        'level': i,
                        'size_ratio': quantity / avg_size
                    })
                    
            for i, (price, quantity) in enumerate(snapshot.asks):
                if quantity > threshold:
                    large_orders.append({
                        'side': 'ask',
                        'price': price,
                        'quantity': quantity,
                        'level': i,
                        'size_ratio': quantity / avg_size
                    })
                    
            return large_orders
            
        except Exception as e:
            logger.error(f"Error detecting large orders: {e}")
            return []
            
    def _identify_support_resistance(self, snapshot: OrderBookSnapshot) -> List[float]:
        """Identify support and resistance levels"""
        try:
            levels = []
            
            # Get price levels from order book
            bid_prices = [bid[0] for bid in snapshot.bids]
            ask_prices = [ask[0] for ask in snapshot.asks]
            
            # Find significant price levels (simplified)
            all_prices = bid_prices + ask_prices
            if len(all_prices) < 5:
                return levels
                
            # Calculate price clusters
            price_clusters = self._cluster_prices(all_prices)
            
            # Select significant clusters as S/R levels
            for cluster in price_clusters:
                if len(cluster) >= 3:  # At least 3 orders at similar price
                    levels.append(np.mean(cluster))
                    
            return sorted(levels)
            
        except Exception as e:
            logger.error(f"Error identifying support/resistance: {e}")
            return []
            
    def _cluster_prices(self, prices: List[float], tolerance: float = 0.001) -> List[List[float]]:
        """Cluster prices within tolerance"""
        if not prices:
            return []
            
        sorted_prices = sorted(prices)
        clusters = []
        current_cluster = [sorted_prices[0]]
        
        for price in sorted_prices[1:]:
            if abs(price - current_cluster[-1]) <= tolerance:
                current_cluster.append(price)
            else:
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [price]
                
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
            
        return clusters
        
    def _identify_liquidity_zones(self, snapshot: OrderBookSnapshot) -> List[Dict[str, Any]]:
        """Identify liquidity zones in order book"""
        try:
            zones = []
            
            # Analyze bid side liquidity
            bid_liquidity = self._analyze_side_liquidity(snapshot.bids, 'bid')
            if bid_liquidity:
                zones.append(bid_liquidity)
                
            # Analyze ask side liquidity
            ask_liquidity = self._analyze_side_liquidity(snapshot.asks, 'ask')
            if ask_liquidity:
                zones.append(ask_liquidity)
                
            return zones
            
        except Exception as e:
            logger.error(f"Error identifying liquidity zones: {e}")
            return []
            
    def _analyze_side_liquidity(self, orders: List[List[float]], side: str) -> Optional[Dict[str, Any]]:
        """Analyze liquidity on one side of order book"""
        try:
            if len(orders) < 3:
                return None
                
            # Calculate total liquidity in top 5 levels
            top_5_volume = sum(order[1] for order in orders[:5])
            total_volume = sum(order[1] for order in orders)
            
            if total_volume == 0:
                return None
                
            # Calculate liquidity concentration
            concentration = top_5_volume / total_volume
            
            # Calculate average spread between levels
            if len(orders) > 1:
                spreads = [orders[i][0] - orders[i+1][0] for i in range(len(orders)-1)]
                avg_spread = np.mean(spreads) if spreads else 0
            else:
                avg_spread = 0
                
            return {
                'side': side,
                'total_volume': total_volume,
                'concentration': concentration,
                'avg_spread': avg_spread,
                'levels_count': len(orders)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing side liquidity: {e}")
            return None
            
    def _create_empty_microstructure(self, timestamp_utc: int) -> MarketMicrostructure:
        """Create empty microstructure when analysis fails"""
        return MarketMicrostructure(
            symbol=self.symbol,
            timestamp_utc=timestamp_utc,
            bid_ask_spread=0.0,
            volume_imbalance=0.0,
            order_flow_imbalance=0.0,
            large_order_ratio=0.0,
            support_resistance_levels=[],
            liquidity_zones=[]
        )

class BinanceWebSocketClient:
    """Binance WebSocket client for order book data"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        self.symbol = symbol
        self.config = config
        self.websocket = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.get('max_reconnect_attempts', 10)
        self.reconnect_delay = config.get('reconnect_delay', 1.0)
        
        # Binance symbol mapping
        self.binance_symbol = self._map_to_binance_symbol(symbol)
        
        # Callbacks
        self.on_order_book_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
    def _map_to_binance_symbol(self, symbol: str) -> str:
        """Map broker symbol to Binance symbol"""
        mapping = {
            'BTCUSDc': 'BTCUSDT',
            'XAUUSDc': 'XAUUSDT',  # Gold futures
            'ETHUSDc': 'ETHUSDT'
        }
        return mapping.get(symbol, symbol)
        
    async def start(self):
        """Start WebSocket connection"""
        try:
            self.running = True
            await self._connect()
            
        except Exception as e:
            logger.error(f"Error starting Binance WebSocket for {self.symbol}: {e}")
            if self.on_error:
                self.on_error(e)
                
    async def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            
    async def _connect(self):
        """Connect to Binance WebSocket"""
        try:
            # Binance depth stream URL
            url = f"wss://stream.binance.com:9443/ws/{self.binance_symbol.lower()}@depth"
            
            self.websocket = await websockets.connect(url)
            logger.info(f"Connected to Binance WebSocket for {self.symbol}")
            
            # Reset reconnect attempts on successful connection
            self.reconnect_attempts = 0
            
            # Start listening for messages
            await self._listen()
            
        except Exception as e:
            logger.error(f"Error connecting to Binance WebSocket: {e}")
            await self._handle_reconnect()
            
    async def _listen(self):
        """Listen for WebSocket messages"""
        try:
            async for message in self.websocket:
                if not self.running:
                    break
                    
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Binance WebSocket connection closed for {self.symbol}")
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            await self._handle_reconnect()
            
    async def _process_message(self, data: Dict[str, Any]):
        """Process incoming WebSocket message"""
        try:
            # Extract order book data
            if 'bids' in data and 'asks' in data:
                snapshot = OrderBookSnapshot(
                    symbol=self.symbol,
                    timestamp_utc=int(time.time() * 1000),  # Convert to milliseconds
                    bids=[[float(bid[0]), float(bid[1])] for bid in data['bids']],
                    asks=[[float(ask[0]), float(ask[1])] for ask in data['asks']],
                    spread=0.0,  # Will be calculated
                    mid_price=0.0,  # Will be calculated
                    volume_imbalance=0.0,  # Will be calculated
                    large_orders=[]  # Will be calculated
                )
                
                # Calculate derived metrics
                if snapshot.bids and snapshot.asks:
                    best_bid = snapshot.bids[0][0]
                    best_ask = snapshot.asks[0][0]
                    snapshot.spread = best_ask - best_bid
                    snapshot.mid_price = (best_bid + best_ask) / 2
                    
                # Notify callback
                if self.on_order_book_update:
                    self.on_order_book_update(snapshot)
                    
        except Exception as e:
            logger.error(f"Error processing order book message: {e}")
            
    async def _handle_reconnect(self):
        """Handle WebSocket reconnection"""
        if not self.running:
            return
            
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for {self.symbol}")
            return
            
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** self.reconnect_attempts)  # Exponential backoff
        
        logger.info(f"Reconnecting to Binance WebSocket for {self.symbol} in {delay}s (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
        
        try:
            await self._connect()
        except Exception as e:
            logger.error(f"Error during reconnection: {e}")

class BinanceContextManager:
    """Manager for Binance context integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.analyzers: Dict[str, BinanceContextAnalyzer] = {}
        self.websocket_clients: Dict[str, BinanceWebSocketClient] = {}
        self.running = False
        
    def add_symbol(self, symbol: str, symbol_config: Dict[str, Any]):
        """Add symbol for Binance context analysis"""
        try:
            # Create analyzer
            analyzer = BinanceContextAnalyzer(symbol, symbol_config)
            self.analyzers[symbol] = analyzer
            
            # Create WebSocket client
            client = BinanceWebSocketClient(symbol, symbol_config)
            client.on_order_book_update = self._on_order_book_update
            client.on_error = self._on_error
            self.websocket_clients[symbol] = client
            
            logger.info(f"Added {symbol} to Binance context analysis")
            
        except Exception as e:
            logger.error(f"Error adding symbol {symbol}: {e}")
            
    async def start(self):
        """Start all Binance context services"""
        try:
            self.running = True
            
            # Start WebSocket clients
            tasks = []
            for symbol, client in self.websocket_clients.items():
                task = asyncio.create_task(client.start())
                tasks.append(task)
                
            # Wait for all clients to start
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info("Started all Binance context services")
            
        except Exception as e:
            logger.error(f"Error starting Binance context services: {e}")
            
    async def stop(self):
        """Stop all Binance context services"""
        try:
            self.running = False
            
            # Stop WebSocket clients
            for client in self.websocket_clients.values():
                await client.stop()
                
            logger.info("Stopped all Binance context services")
            
        except Exception as e:
            logger.error(f"Error stopping Binance context services: {e}")
            
    async def _on_order_book_update(self, snapshot: OrderBookSnapshot):
        """Handle order book update"""
        try:
            symbol = snapshot.symbol
            if symbol in self.analyzers:
                analyzer = self.analyzers[symbol]
                microstructure = analyzer.analyze_order_book(snapshot)
                
                # Store for context (non-blocking)
                analyzer.microstructure_cache.append(microstructure)
                
                # Log context features (for debugging)
                logger.debug(f"Binance context for {symbol}: "
                           f"spread={microstructure.bid_ask_spread:.4f}, "
                           f"imbalance={microstructure.volume_imbalance:.2f}, "
                           f"large_orders={microstructure.large_order_ratio:.2f}")
                
        except Exception as e:
            logger.error(f"Error handling order book update: {e}")
            
    async def _on_error(self, error: Exception):
        """Handle WebSocket error"""
        logger.error(f"Binance WebSocket error: {error}")
        
    def get_context_features(self, symbol: str) -> Optional[MarketMicrostructure]:
        """Get latest context features for symbol"""
        try:
            if symbol in self.analyzers:
                analyzer = self.analyzers[symbol]
                if analyzer.microstructure_cache:
                    return analyzer.microstructure_cache[-1]
            return None
            
        except Exception as e:
            logger.error(f"Error getting context features for {symbol}: {e}")
            return None


# Example usage and testing
if __name__ == "__main__":
    # Test Binance context integration
    config = {
        'large_order_threshold': 0.1,
        'support_resistance_lookback': 50,
        'volume_imbalance_threshold': 0.3,
        'max_reconnect_attempts': 5,
        'reconnect_delay': 1.0
    }
    
    manager = BinanceContextManager(config)
    
    # Add test symbol
    manager.add_symbol("BTCUSDc", config)
    
    # Test with sample order book data
    snapshot = OrderBookSnapshot(
        symbol="BTCUSDc",
        timestamp_utc=int(time.time() * 1000),
        bids=[[50000.0, 1.5], [49999.0, 2.0], [49998.0, 1.0]],
        asks=[[50001.0, 1.2], [50002.0, 1.8], [50003.0, 0.9]],
        spread=1.0,
        mid_price=50000.5,
        volume_imbalance=0.0,
        large_orders=[]
    )
    
    # Test analyzer
    analyzer = manager.analyzers["BTCUSDc"]
    microstructure = analyzer.analyze_order_book(snapshot)
    
    print(f"Market microstructure analysis:")
    print(f"  Spread: {microstructure.bid_ask_spread:.4f}")
    print(f"  Volume imbalance: {microstructure.volume_imbalance:.2f}")
    print(f"  Order flow imbalance: {microstructure.order_flow_imbalance:.2f}")
    print(f"  Large order ratio: {microstructure.large_order_ratio:.2f}")
    print(f"  Support/Resistance levels: {microstructure.support_resistance_levels}")
    print(f"  Liquidity zones: {len(microstructure.liquidity_zones)}")
