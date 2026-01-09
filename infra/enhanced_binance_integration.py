"""
Enhanced Binance Integration
Large order detection, support/resistance identification, and market microstructure analysis
"""

import asyncio
import websockets
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
from collections import deque
import aiohttp
import time

logger = logging.getLogger(__name__)

class EnhancedBinanceIntegration:
    """Enhanced Binance integration with advanced market analysis"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'BTCUSDc')
        self.binance_symbol = symbol_config.get('binance_symbol', 'BTCUSDT')
        
        # Configuration
        self.large_order_threshold = symbol_config.get('large_order_threshold', 100000)  # $100k
        self.support_resistance_levels = symbol_config.get('support_resistance_levels', 5)
        self.order_book_depth = symbol_config.get('order_book_depth', 20)
        self.update_frequency = symbol_config.get('update_frequency', 1000)  # ms
        
        # WebSocket connection
        self.websocket = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1.0
        
        # Market data storage
        self.order_book = {'bids': [], 'asks': []}
        self.trade_history = deque(maxlen=1000)
        self.price_levels = deque(maxlen=10000)
        self.large_orders = deque(maxlen=100)
        
        # Analysis results
        self.support_levels = []
        self.resistance_levels = []
        self.large_order_alerts = []
        self.market_microstructure = {}
        
        # Performance tracking
        self.last_update_time = 0
        self.update_count = 0
        self.error_count = 0
        
    async def connect(self):
        """Connect to Binance WebSocket"""
        try:
            url = f"wss://stream.binance.com:9443/ws/{self.binance_symbol.lower()}@depth20@100ms"
            self.websocket = await websockets.connect(url)
            self.connected = True
            self.reconnect_attempts = 0
            logger.info(f"Connected to Binance WebSocket for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error connecting to Binance WebSocket: {e}")
            self.connected = False
            await self._handle_reconnect()
    
    async def disconnect(self):
        """Disconnect from Binance WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info(f"Disconnected from Binance WebSocket for {self.symbol}")
    
    async def _handle_reconnect(self):
        """Handle reconnection logic"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached for {self.symbol}")
            return
        
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** self.reconnect_attempts), 60)
        logger.info(f"Reconnecting to Binance in {delay} seconds (attempt {self.reconnect_attempts})")
        
        await asyncio.sleep(delay)
        await self.connect()
    
    async def start_streaming(self):
        """Start streaming market data"""
        if not self.connected:
            await self.connect()
        
        try:
            async for message in self.websocket:
                await self._process_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Binance WebSocket connection closed for {self.symbol}")
            self.connected = False
            await self._handle_reconnect()
            
        except Exception as e:
            logger.error(f"Error in Binance streaming: {e}")
            self.error_count += 1
            await self._handle_reconnect()
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            if 'bids' in data and 'asks' in data:
                await self._update_order_book(data)
            elif 'p' in data and 'q' in data:
                await self._process_trade(data)
            
            self.update_count += 1
            self.last_update_time = time.time()
            
        except Exception as e:
            logger.error(f"Error processing Binance message: {e}")
            self.error_count += 1
    
    async def _update_order_book(self, data: Dict[str, Any]):
        """Update order book data"""
        try:
            self.order_book['bids'] = [[float(bid[0]), float(bid[1])] for bid in data['bids']]
            self.order_book['asks'] = [[float(ask[0]), float(ask[1])] for ask in data['asks']]
            
            # Analyze order book for large orders
            await self._analyze_large_orders()
            
            # Update support/resistance levels
            await self._update_support_resistance()
            
        except Exception as e:
            logger.error(f"Error updating order book: {e}")
    
    async def _process_trade(self, data: Dict[str, Any]):
        """Process trade data"""
        try:
            trade = {
                'price': float(data['p']),
                'quantity': float(data['q']),
                'timestamp': int(data['T']),
                'is_buyer_maker': data['m']
            }
            
            self.trade_history.append(trade)
            self.price_levels.append(trade['price'])
            
            # Analyze trade for large orders
            if trade['quantity'] * trade['price'] > self.large_order_threshold:
                await self._detect_large_order(trade)
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def _analyze_large_orders(self):
        """Analyze order book for large orders"""
        try:
            large_bids = []
            large_asks = []
            
            # Analyze bids for large orders
            for bid in self.order_book['bids']:
                if bid[0] * bid[1] > self.large_order_threshold:
                    large_bids.append(bid)
            
            # Analyze asks for large orders
            for ask in self.order_book['asks']:
                if ask[0] * ask[1] > self.large_order_threshold:
                    large_asks.append(ask)
            
            # Store large orders
            if large_bids or large_asks:
                large_order_data = {
                    'timestamp': int(time.time() * 1000),
                    'large_bids': large_bids,
                    'large_asks': large_asks,
                    'total_bid_value': sum(bid[0] * bid[1] for bid in large_bids),
                    'total_ask_value': sum(ask[0] * ask[1] for ask in large_asks)
                }
                self.large_orders.append(large_order_data)
                
        except Exception as e:
            logger.error(f"Error analyzing large orders: {e}")
    
    async def _detect_large_order(self, trade: Dict[str, Any]):
        """Detect large order from trade data"""
        try:
            order_value = trade['price'] * trade['quantity']
            
            large_order = {
                'timestamp': trade['timestamp'],
                'price': trade['price'],
                'quantity': trade['quantity'],
                'value': order_value,
                'is_buyer_maker': trade['is_buyer_maker'],
                'type': 'buy' if not trade['is_buyer_maker'] else 'sell'
            }
            
            self.large_orders.append(large_order)
            
            # Create alert
            alert = {
                'symbol': self.symbol,
                'type': 'large_order',
                'timestamp': trade['timestamp'],
                'data': large_order,
                'severity': 'high' if order_value > self.large_order_threshold * 5 else 'medium'
            }
            
            self.large_order_alerts.append(alert)
            logger.info(f"Large order detected: {order_value:,.2f} {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error detecting large order: {e}")
    
    async def _update_support_resistance(self):
        """Update support and resistance levels"""
        try:
            if len(self.price_levels) < 100:
                return
            
            prices = np.array(self.price_levels)
            
            # Calculate support levels (price clusters)
            support_levels = self._find_price_clusters(prices, 'support')
            resistance_levels = self._find_price_clusters(prices, 'resistance')
            
            self.support_levels = support_levels
            self.resistance_levels = resistance_levels
            
        except Exception as e:
            logger.error(f"Error updating support/resistance: {e}")
    
    def _find_price_clusters(self, prices: np.ndarray, level_type: str) -> List[Dict[str, Any]]:
        """Find price clusters for support/resistance levels"""
        try:
            # Sort prices
            sorted_prices = np.sort(prices)
            
            # Find clusters using density
            clusters = []
            cluster_threshold = np.std(sorted_prices) * 0.1  # 10% of standard deviation
            
            current_cluster = [sorted_prices[0]]
            
            for i in range(1, len(sorted_prices)):
                if sorted_prices[i] - sorted_prices[i-1] <= cluster_threshold:
                    current_cluster.append(sorted_prices[i])
                else:
                    if len(current_cluster) >= 5:  # Minimum cluster size
                        clusters.append({
                            'price': np.mean(current_cluster),
                            'strength': len(current_cluster),
                            'type': level_type,
                            'range': [min(current_cluster), max(current_cluster)]
                        })
                    current_cluster = [sorted_prices[i]]
            
            # Add final cluster
            if len(current_cluster) >= 5:
                clusters.append({
                    'price': np.mean(current_cluster),
                    'strength': len(current_cluster),
                    'type': level_type,
                    'range': [min(current_cluster), max(current_cluster)]
                })
            
            # Sort by strength and return top levels
            clusters.sort(key=lambda x: x['strength'], reverse=True)
            return clusters[:self.support_resistance_levels]
            
        except Exception as e:
            logger.error(f"Error finding price clusters: {e}")
            return []
    
    async def get_market_analysis(self) -> Dict[str, Any]:
        """Get comprehensive market analysis"""
        try:
            current_time = int(time.time() * 1000)
            
            # Calculate market microstructure
            microstructure = await self._calculate_microstructure()
            
            # Get recent large orders
            recent_large_orders = [
                order for order in self.large_orders 
                if current_time - order.get('timestamp', 0) < 300000  # Last 5 minutes
            ]
            
            # Get recent alerts
            recent_alerts = [
                alert for alert in self.large_order_alerts
                if current_time - alert.get('timestamp', 0) < 300000  # Last 5 minutes
            ]
            
            return {
                'symbol': self.symbol,
                'timestamp': current_time,
                'order_book': self.order_book,
                'support_levels': self.support_levels,
                'resistance_levels': self.resistance_levels,
                'large_orders': recent_large_orders,
                'alerts': recent_alerts,
                'microstructure': microstructure,
                'performance': {
                    'update_count': self.update_count,
                    'error_count': self.error_count,
                    'last_update': self.last_update_time,
                    'connected': self.connected
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting market analysis: {e}")
            return {}
    
    async def _calculate_microstructure(self) -> Dict[str, Any]:
        """Calculate market microstructure metrics"""
        try:
            if not self.order_book['bids'] or not self.order_book['asks']:
                return {}
            
            # Calculate spread
            best_bid = self.order_book['bids'][0][0]
            best_ask = self.order_book['asks'][0][0]
            spread = best_ask - best_bid
            spread_percentage = (spread / best_bid) * 100
            
            # Calculate order book imbalance
            total_bid_volume = sum(bid[1] for bid in self.order_book['bids'])
            total_ask_volume = sum(ask[1] for ask in self.order_book['asks'])
            imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
            
            # Calculate price impact
            price_impact = self._calculate_price_impact()
            
            return {
                'spread': spread,
                'spread_percentage': spread_percentage,
                'imbalance': imbalance,
                'price_impact': price_impact,
                'bid_volume': total_bid_volume,
                'ask_volume': total_ask_volume
            }
            
        except Exception as e:
            logger.error(f"Error calculating microstructure: {e}")
            return {}
    
    def _calculate_price_impact(self) -> float:
        """Calculate price impact of large orders"""
        try:
            if not self.order_book['bids'] or not self.order_book['asks']:
                return 0.0
            
            # Calculate impact of consuming top 5 levels
            bid_impact = sum(bid[0] * bid[1] for bid in self.order_book['bids'][:5])
            ask_impact = sum(ask[0] * ask[1] for ask in self.order_book['asks'][:5])
            
            return (bid_impact + ask_impact) / 2
            
        except Exception as e:
            logger.error(f"Error calculating price impact: {e}")
            return 0.0
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'connected': self.connected,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'last_update_time': self.last_update_time,
            'reconnect_attempts': self.reconnect_attempts,
            'data_points': len(self.price_levels),
            'large_orders_count': len(self.large_orders),
            'alerts_count': len(self.large_order_alerts)
        }

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_enhanced_binance():
        # Test configuration
        config = {
            'symbol': 'BTCUSDc',
            'binance_symbol': 'BTCUSDT',
            'large_order_threshold': 50000,  # $50k
            'support_resistance_levels': 3,
            'order_book_depth': 20
        }
        
        # Create integration
        binance = EnhancedBinanceIntegration(config)
        
        print("Testing Enhanced Binance Integration:")
        
        # Connect
        await binance.connect()
        
        if binance.connected:
            print("Connected to Binance WebSocket")
            
            # Start streaming for a short time
            streaming_task = asyncio.create_task(binance.start_streaming())
            
            # Wait for some data
            await asyncio.sleep(5)
            
            # Get market analysis
            analysis = await binance.get_market_analysis()
            print(f"Market Analysis: {analysis}")
            
            # Get performance stats
            stats = binance.get_performance_stats()
            print(f"Performance Stats: {stats}")
            
            # Cancel streaming
            streaming_task.cancel()
            
            # Disconnect
            await binance.disconnect()
            print("Disconnected from Binance WebSocket")
        else:
            print("Failed to connect to Binance WebSocket")
    
    # Run test
    asyncio.run(test_enhanced_binance())
