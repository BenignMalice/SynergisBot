"""
BTC Order Flow Metrics Calculator

Calculates advanced order flow metrics from Binance WebSocket data:
- Delta Volume
- CVD (Cumulative Volume Delta)
- CVD Divergence
- CVD Slope
- Absorption Zones
- Buy/Sell Pressure Balance

All calculations use in-memory data only (no database writes).
Resource efficient - uses existing Binance streaming data.
"""

import logging
import time
import numpy as np
from typing import Dict, Optional, List, Tuple
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Phase 1.1: Import tick engine (lazy import to avoid circular dependencies)
try:
    from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
    TICK_ENGINE_AVAILABLE = True
except ImportError:
    TICK_ENGINE_AVAILABLE = False
    logger.debug("TickByTickDeltaEngine not available (will use fallback)")

# Phase 1.3: Import delta divergence detector
try:
    from infra.delta_divergence_detector import DeltaDivergenceDetector
    DELTA_DIVERGENCE_DETECTOR_AVAILABLE = True
except ImportError:
    DELTA_DIVERGENCE_DETECTOR_AVAILABLE = False
    logger.debug("DeltaDivergenceDetector not available (will use fallback)")


@dataclass
class OrderFlowMetrics:
    """Order flow metrics for a symbol"""
    symbol: str
    timestamp: float
    
    # Delta Volume
    delta_volume: float
    buy_volume: float
    sell_volume: float
    
    # CVD
    cvd: float
    cvd_slope: float
    
    # CVD Divergence
    cvd_divergence_strength: float
    cvd_divergence_type: Optional[str]  # "bearish", "bullish", None
    
    # Absorption Zones
    absorption_zones: List[Dict]
    
    # Buy/Sell Pressure
    buy_sell_pressure: float
    dominant_side: str
    
    # Metadata
    window_seconds: int
    bar_count: int


class BTCOrderFlowMetrics:
    """
    Calculate comprehensive order flow metrics for BTCUSD.
    
    Uses existing Binance WebSocket data:
    - OrderFlowService for buy/sell pressure
    - WhaleDetector for trade history
    - OrderBookAnalyzer for depth data
    
    All calculations are in-memory only (no database writes).
    """
    
    def __init__(
        self,
        order_flow_service=None,
        mt5_service=None,  # NEW: MT5 service for price bar alignment (Phase 1.2)
        cvd_window_seconds: int = 300,  # 5 minutes for CVD calculation
        cvd_slope_period: int = 10,  # Bars for slope calculation
        absorption_threshold_volume: float = 100000,  # $100k minimum for absorption
        absorption_threshold_imbalance: float = 1.5  # 1.5x imbalance ratio
    ):
        """
        Initialize BTC order flow metrics calculator.
        
        Args:
            order_flow_service: OrderFlowService instance (from infra.order_flow_service)
            mt5_service: Optional MT5Service instance for price bar alignment (Phase 1.2)
            cvd_window_seconds: Time window for CVD calculation (default: 5 minutes)
            cvd_slope_period: Number of bars for CVD slope calculation (default: 10)
            absorption_threshold_volume: Minimum volume for absorption zone (default: $100k)
            absorption_threshold_imbalance: Minimum order book imbalance for absorption (default: 1.5x)
        """
        self.order_flow_service = order_flow_service
        self.mt5_service = mt5_service  # NEW: Store MT5 service for price bar alignment
        
        # CVD calculation parameters
        self.cvd_window_seconds = cvd_window_seconds
        self.cvd_slope_period = cvd_slope_period
        
        # Absorption zone parameters
        self.absorption_threshold_volume = absorption_threshold_volume
        self.absorption_threshold_imbalance = absorption_threshold_imbalance
        
        # In-memory storage for bar-level data
        self.bar_data = {}  # symbol -> deque of bar data
        self.cvd_history = {}  # symbol -> deque of CVD values
        
        # Bar aggregation settings
        self.bar_interval_seconds = 60  # 1-minute bars for aggregation
        
        # Phase 1.1: Tick-by-tick delta engines (one per symbol)
        self.tick_engines: Dict[str, 'TickByTickDeltaEngine'] = {}  # symbol -> engine
        
        # Phase 4.1: Metrics caching for performance optimization
        self._metrics_cache: Dict[str, tuple] = {}  # cache_key -> (metrics, timestamp)
        self._cache_ttl = 5  # 5 seconds cache TTL
        
        # Phase 4.1: Performance monitoring (optional)
        self.performance_monitor = None
        try:
            from infra.order_flow_performance_monitor import OrderFlowPerformanceMonitor
            self.performance_monitor = OrderFlowPerformanceMonitor()
        except Exception as e:
            logger.debug(f"Performance monitor not available: {e}")
        
        logger.info("📊 BTCOrderFlowMetrics initialized")
        logger.info(f"   CVD window: {cvd_window_seconds}s")
        logger.info(f"   CVD slope period: {cvd_slope_period} bars")
        logger.info(f"   Absorption threshold: ${absorption_threshold_volume:,.0f}")
        if TICK_ENGINE_AVAILABLE:
            logger.info("   Phase 1.1: Tick-by-tick delta engine available")
    
    def initialize_tick_engine(self, symbol: str) -> bool:
        """
        Initialize tick-by-tick delta engine for a symbol.
        
        Phase 1.1: Creates and connects tick engine to order flow service.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
        
        Returns:
            True if initialized successfully, False otherwise
        """
        if not TICK_ENGINE_AVAILABLE:
            logger.debug(f"Tick engine not available for {symbol}")
            return False
        
        if symbol in self.tick_engines:
            logger.debug(f"Tick engine already initialized for {symbol}")
            return True
        
        try:
            # Create tick engine
            tick_engine = TickByTickDeltaEngine(symbol=symbol, max_history=200)
            self.tick_engines[symbol] = tick_engine
            
            # Connect to order flow service if available
            if self.order_flow_service and hasattr(self.order_flow_service, 'trades_stream'):
                # Note: The order flow service processes trades via analyzer
                # We'll need to hook into the trade processing pipeline
                # For now, tick engine will be populated via process_aggtrade() calls
                logger.debug(f"Tick engine created for {symbol} (will be populated via trade callbacks)")
            else:
                logger.debug(f"Tick engine created for {symbol} (order flow service not available for auto-connection)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing tick engine for {symbol}: {e}")
            return False
    
    def process_aggtrade(self, symbol: str, trade_data: Dict) -> Optional[Dict]:
        """
        Process a Binance aggTrade and update tick engine.
        
        Phase 1.1: This method should be called from order flow service
        when new aggTrades are received.
        
        Args:
            symbol: Trading symbol
            trade_data: Dict with 'side', 'quantity', 'timestamp', 'price'
        
        Returns:
            DeltaMetrics dict or None
        """
        if not TICK_ENGINE_AVAILABLE:
            return None
        
        # Initialize tick engine if not already done
        if symbol not in self.tick_engines:
            self.initialize_tick_engine(symbol)
        
        tick_engine = self.tick_engines.get(symbol)
        if not tick_engine:
            return None
        
        # Process trade
        metrics = tick_engine.process_aggtrade(trade_data)
        if metrics:
            return {
                'delta': metrics.delta,
                'cvd': metrics.cvd,
                'timestamp': metrics.timestamp,
                'buy_volume': metrics.buy_volume,
                'sell_volume': metrics.sell_volume
            }
        
        return None
    
    def get_metrics(
        self,
        symbol: str = "BTCUSDT",
        window_seconds: int = 30
    ) -> Optional[OrderFlowMetrics]:
        """
        Get comprehensive order flow metrics for a symbol.
        
        Args:
            symbol: Trading symbol (default: BTCUSDT)
            window_seconds: Time window for pressure calculation (default: 30s)
        
        Returns:
            OrderFlowMetrics object or None if data unavailable
        """
        # Verify order flow service is available and running
        if not self.order_flow_service:
            logger.debug(f"Order flow service not available for {symbol} (service is None)")
            logger.debug("   Reason: OrderFlowService was not provided during initialization")
            logger.debug("   Solution: Ensure Binance service is running and order flow service is initialized in chatgpt_bot.py or desktop_agent.py")
            logger.debug("   Note: This is expected if order flow service is not running - system will continue without order flow data")
            return None
        
        if not hasattr(self.order_flow_service, 'running'):
            logger.debug(f"Order flow service not available for {symbol} (missing 'running' attribute)")
            logger.debug("   Reason: OrderFlowService instance is invalid or corrupted")
            return None
        
        if not self.order_flow_service.running:
            logger.debug(f"Order flow service not available for {symbol} (service not running)")
            logger.debug(f"   Service status: running={self.order_flow_service.running}")
            logger.debug(f"   Service symbols: {getattr(self.order_flow_service, 'symbols', 'unknown')}")
            logger.debug("   Reason: Order flow service exists but streams are not active")
            logger.debug("   Solution: Check if Binance service is running and order flow service was started successfully")
            logger.debug("   Note: This is expected if order flow service is not running - system will continue without order flow data")
            return None
        
        try:
            # 1. Get buy/sell pressure (already implemented)
            pressure_data = self.order_flow_service.get_buy_sell_pressure(symbol, window_seconds)
            if not pressure_data:
                # Check if symbol exists in trade history
                whale_detector = self.order_flow_service.analyzer.whale_detector
                if symbol not in whale_detector.trade_history:
                    logger.warning(f"Symbol {symbol} not found in trade_history. Available symbols: {list(whale_detector.trade_history.keys())}")
                    return None
                
                # Check if there are any trades at all
                trade_count = len(whale_detector.trade_history[symbol])
                if trade_count == 0:
                    logger.warning(f"No trades collected yet for {symbol} (trade_history empty)")
                    return None
                
                # Check if trades are too old
                if trade_count > 0:
                    latest_trade = max(whale_detector.trade_history[symbol], key=lambda t: t["timestamp"])
                    age_seconds = time.time() - latest_trade["timestamp"]
                    logger.warning(f"Trades exist for {symbol} but none in {window_seconds}s window. Latest trade age: {age_seconds:.1f}s, Trade count: {trade_count}")
                
                return None
            
            buy_volume = pressure_data.get("buy_volume", 0)
            sell_volume = pressure_data.get("sell_volume", 0)
            delta_volume = buy_volume - sell_volume
            pressure_ratio = pressure_data.get("pressure", 1.0)
            dominant_side = pressure_data.get("dominant_side", "NEUTRAL")
            
            # 2. Calculate CVD from aggregated bars
            # Phase 1.1: Try to use tick engine if available (more accurate)
            tick_engine = self.tick_engines.get(symbol)
            if tick_engine and hasattr(tick_engine, 'get_cvd_value'):
                cvd = tick_engine.get_cvd_value()
                cvd_trend_data = tick_engine.get_cvd_trend(self.cvd_slope_period)
                cvd_slope = cvd_trend_data.get('slope', 0.0)
                bar_count = len(tick_engine.cvd_history) if hasattr(tick_engine, 'cvd_history') else 0
            else:
                # Fallback to bar-based calculation
                cvd_data = self._calculate_cvd(symbol)
                cvd = cvd_data.get("cvd", 0.0) if cvd_data else 0.0
                cvd_slope = cvd_data.get("slope", 0.0) if cvd_data else 0.0
                bar_count = cvd_data.get("bar_count", 0) if cvd_data else 0
            
            # 3. Calculate CVD divergence
            divergence_data = self._calculate_cvd_divergence(symbol)
            divergence_strength = divergence_data.get("strength", 0.0) if divergence_data else 0.0
            divergence_type = divergence_data.get("type") if divergence_data else None
            
            # Phase 1.3: Calculate delta divergence (price vs delta trend)
            delta_divergence = self._calculate_delta_divergence(symbol, delta_volume)
            
            # 4. Detect absorption zones
            absorption_zones = self._detect_absorption_zones(symbol)
            
            return OrderFlowMetrics(
                symbol=symbol,
                timestamp=time.time(),
                delta_volume=delta_volume,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                cvd=cvd,
                cvd_slope=cvd_slope,
                cvd_divergence_strength=divergence_strength,
                cvd_divergence_type=divergence_type,
                absorption_zones=absorption_zones,
                buy_sell_pressure=pressure_ratio,
                dominant_side=dominant_side,
                window_seconds=window_seconds,
                bar_count=bar_count
            )
            
            # Phase 4.1: Update cache and record performance
            if metrics:
                self._metrics_cache[cache_key] = (metrics, current_time)
                # Clean up old cache entries (keep last 10)
                if len(self._metrics_cache) > 10:
                    oldest_key = min(self._metrics_cache.keys(), 
                                    key=lambda k: self._metrics_cache[k][1])
                    del self._metrics_cache[oldest_key]
            
            # Record performance metrics
            latency_ms = (time.perf_counter() - start_time) * 1000
            if self.performance_monitor:
                self.performance_monitor.record_metrics_call(cached=False, latency_ms=latency_ms)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating order flow metrics for {symbol}: {e}", exc_info=True)
            return None
    
    def _calculate_cvd(self, symbol: str) -> Optional[Dict]:
        """
        Calculate CVD (Cumulative Volume Delta) from aggregated bars.
        
        Aggregates Binance trades into 1-minute bars, then calculates:
        - Delta volume per bar (buy_volume - sell_volume)
        - Cumulative sum (CVD)
        - CVD slope (rate of change)
        
        Returns:
            {"cvd": float, "slope": float, "bar_count": int} or None
        """
        if not self.order_flow_service:
            return None
        
        try:
            # Get trade history from whale detector
            whale_detector = self.order_flow_service.analyzer.whale_detector
            if symbol not in whale_detector.trade_history:
                return None
            
            # Get trades within CVD window
            cutoff_time = time.time() - self.cvd_window_seconds
            recent_trades = [
                trade for trade in whale_detector.trade_history[symbol]
                if trade["timestamp"] >= cutoff_time
            ]
            
            if not recent_trades:
                return None
            
            # Aggregate trades into 1-minute bars
            bars = self._aggregate_trades_to_bars(recent_trades)
            
            if not bars:
                return None
            
            # Calculate delta volume per bar
            bar_deltas = []
            for bar in bars:
                delta = bar["buy_volume"] - bar["sell_volume"]
                bar_deltas.append(delta)
            
            # Calculate CVD (cumulative sum)
            cvd_values = np.cumsum(bar_deltas)
            current_cvd = float(cvd_values[-1]) if len(cvd_values) > 0 else 0.0
            
            # Calculate CVD slope (rate of change over last N bars)
            slope = 0.0
            if len(cvd_values) >= self.cvd_slope_period:
                # Linear regression for smoother slope
                x = np.arange(len(cvd_values[-self.cvd_slope_period:]))
                y = cvd_values[-self.cvd_slope_period:]
                slope = float(np.polyfit(x, y, 1)[0])  # Linear fit, get slope
            elif len(cvd_values) >= 2:
                # Simple difference if not enough data
                slope = float(cvd_values[-1] - cvd_values[0]) / len(cvd_values)
            
            # Store CVD history for divergence calculation
            if symbol not in self.cvd_history:
                self.cvd_history[symbol] = deque(maxlen=100)  # Keep last 100 CVD values
            self.cvd_history[symbol].append(current_cvd)
            
            return {
                "cvd": current_cvd,
                "slope": slope,
                "bar_count": len(bars),
                "bar_deltas": bar_deltas,
                "cvd_values": cvd_values.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error calculating CVD for {symbol}: {e}", exc_info=True)
            return None
    
    def _aggregate_trades_to_bars(self, trades: List[Dict]) -> List[Dict]:
        """
        Aggregate trades into 1-minute bars.
        
        Args:
            trades: List of trade dictionaries with timestamp, side, quantity, price
        
        Returns:
            List of bar dictionaries with buy_volume, sell_volume, etc.
        """
        if not trades:
            return []
        
        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda t: t["timestamp"])
        
        # Group trades into 1-minute bars
        bars = []
        current_bar = None
        bar_start_time = None
        
        for trade in sorted_trades:
            trade_time = trade["timestamp"]
            
            # Determine which bar this trade belongs to
            bar_timestamp = int(trade_time // self.bar_interval_seconds) * self.bar_interval_seconds
            
            # Start new bar if needed
            if current_bar is None or bar_timestamp != bar_start_time:
                if current_bar is not None:
                    bars.append(current_bar)
                
                current_bar = {
                    "timestamp": bar_timestamp,
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "buy_value": 0.0,
                    "sell_value": 0.0,
                    "trade_count": 0,
                    "high": trade.get("price", 0),
                    "low": trade.get("price", 0),
                    "open": trade.get("price", 0),
                    "close": trade.get("price", 0)
                }
                bar_start_time = bar_timestamp
            
            # Add trade to current bar
            price = trade.get("price", 0)
            quantity = trade.get("quantity", 0)
            usd_value = trade.get("usd_value", 0)
            side = trade.get("side", "BUY")
            
            if side == "BUY":
                current_bar["buy_volume"] += quantity
                current_bar["buy_value"] += usd_value
            else:
                current_bar["sell_volume"] += quantity
                current_bar["sell_value"] += usd_value
            
            current_bar["trade_count"] += 1
            current_bar["high"] = max(current_bar["high"], price)
            current_bar["low"] = min(current_bar["low"], price)
            current_bar["close"] = price
        
        # Add final bar
        if current_bar is not None:
            bars.append(current_bar)
        
        return bars
    
    def _calculate_cvd_divergence(self, symbol: str) -> Optional[Dict]:
        """
        Calculate CVD divergence strength with price bar alignment.
        
        Phase 1.2: Enhanced with MT5 price bars for accurate divergence detection.
        
        Divergence occurs when:
        - Bearish: Price makes higher highs, CVD makes lower highs
        - Bullish: Price makes lower lows, CVD makes higher lows
        
        Returns:
            {"strength": float (0-1), "type": "bearish"/"bullish"/None} or None
        """
        try:
            # Phase 1.2: Try to use tick engine CVD history first (more accurate)
            tick_engine = self.tick_engines.get(symbol)
            if tick_engine and hasattr(tick_engine, 'get_cvd_history'):
                cvd_values = tick_engine.get_cvd_history(50)  # Get last 50 CVD values
                if len(cvd_values) >= 20:
                    # Use tick engine CVD with price bars
                    return self._calculate_cvd_divergence_with_price_bars(symbol, cvd_values)
            
            # Fallback: Use bar-based CVD history
            if symbol not in self.cvd_history or len(self.cvd_history[symbol]) < 10:
                return self._calculate_cvd_divergence_simplified(symbol)
            
            cvd_values = list(self.cvd_history[symbol])[-20:]
            if len(cvd_values) < 10:
                return self._calculate_cvd_divergence_simplified(symbol)
            
            # Try enhanced calculation with price bars
            return self._calculate_cvd_divergence_with_price_bars(symbol, cvd_values)
            
        except Exception as e:
            logger.error(f"Error calculating CVD divergence for {symbol}: {e}", exc_info=True)
            return self._calculate_cvd_divergence_simplified(symbol)
    
    def _calculate_cvd_divergence_with_price_bars(self, symbol: str, cvd_values: List[float]) -> Optional[Dict]:
        """
        Calculate CVD divergence using price bars aligned with CVD values.
        
        Phase 1.2: Uses MT5 M1 bars for price data, aligned with CVD history.
        
        Args:
            symbol: Trading symbol
            cvd_values: List of CVD values (aligned with price bars)
        
        Returns:
            Dict with 'type' ('bearish'/'bullish'/'None') and 'strength' (0.0-1.0)
        """
        try:
            # Get price bars from MT5 (returns DataFrame)
            if not self.mt5_service:
                return self._calculate_cvd_divergence_simplified(symbol)
            
            # Convert symbol format (BTCUSDT -> BTCUSDc)
            mt5_symbol = symbol.replace("USDT", "USDc")
            
            # Get M1 bars (need enough for divergence detection)
            m1_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
            if m1_bars_df is None or len(m1_bars_df) < 20:
                logger.debug(f"Insufficient M1 bars for {symbol}, using simplified divergence")
                return self._calculate_cvd_divergence_simplified(symbol)
            
            # Align CVD values with price bars (simplified 1:1 alignment)
            # Both are 1-minute intervals, so assume alignment
            if len(cvd_values) < len(m1_bars_df):
                # Not enough CVD values, use simplified
                return self._calculate_cvd_divergence_simplified(symbol)
            
            # Get aligned CVD values (last N matching price bars)
            aligned_cvd = cvd_values[-len(m1_bars_df):]
            
            # Detect divergence using price and CVD bars
            return self._detect_divergence_from_bars(m1_bars_df, aligned_cvd)
            
        except Exception as e:
            logger.debug(f"Error in enhanced CVD divergence for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
    
    def _detect_divergence_from_bars(self, price_bars_df, cvd_bars: List[float]) -> Dict:
        """
        Detect divergence from aligned price and CVD bars.
        
        Phase 1.2: Works with pandas DataFrame for price bars.
        
        Args:
            price_bars_df: pandas DataFrame with price bars
            cvd_bars: List of CVD values (aligned with price_bars_df)
        
        Returns:
            Dict with 'type' ('bearish'/'bullish'/'None') and 'strength' (0.0-1.0)
        """
        if len(price_bars_df) < 20 or len(cvd_bars) < 20:
            return {"type": None, "strength": 0.0}
        
        try:
            # Get last 20 bars for analysis
            recent_bars = price_bars_df.tail(20)
            price_highs_array = recent_bars['high'].values
            price_lows_array = recent_bars['low'].values
            price_closes_array = recent_bars['close'].values
            
            # Get corresponding CVD values
            aligned_cvd = cvd_bars[-20:]
            
            # Find swing highs/lows in price
            price_highs = []
            price_lows = []
            
            for i in range(1, len(price_highs_array) - 1):
                # Check for swing high
                if (price_highs_array[i] > price_highs_array[i-1] and 
                    price_highs_array[i] > price_highs_array[i+1]):
                    price_highs.append((i, float(price_highs_array[i])))
                # Check for swing low
                if (price_lows_array[i] < price_lows_array[i-1] and 
                    price_lows_array[i] < price_lows_array[i+1]):
                    price_lows.append((i, float(price_lows_array[i])))
            
            # Find corresponding CVD highs/lows
            cvd_highs = []
            cvd_lows = []
            
            for i in range(1, len(aligned_cvd) - 1):
                if aligned_cvd[i] > aligned_cvd[i-1] and aligned_cvd[i] > aligned_cvd[i+1]:
                    cvd_highs.append((i, float(aligned_cvd[i])))
                if aligned_cvd[i] < aligned_cvd[i-1] and aligned_cvd[i] < aligned_cvd[i+1]:
                    cvd_lows.append((i, float(aligned_cvd[i])))
            
            # Detect bearish divergence: Price makes higher high, CVD makes lower high
            if len(price_highs) >= 2 and len(cvd_highs) >= 2:
                price_trend = price_highs[-1][1] > price_highs[-2][1]
                cvd_trend = cvd_highs[-1][1] < cvd_highs[-2][1]
                
                if price_trend and cvd_trend:
                    strength = self._calculate_divergence_strength(price_highs, cvd_highs)
                    return {"type": "bearish", "strength": strength}
            
            # Detect bullish divergence: Price makes lower low, CVD makes higher low
            if len(price_lows) >= 2 and len(cvd_lows) >= 2:
                price_trend = price_lows[-1][1] < price_lows[-2][1]
                cvd_trend = cvd_lows[-1][1] > cvd_lows[-2][1]
                
                if price_trend and cvd_trend:
                    strength = self._calculate_divergence_strength(price_lows, cvd_lows)
                    return {"type": "bullish", "strength": strength}
            
            return {"type": None, "strength": 0.0}
            
        except Exception as e:
            logger.debug(f"Error detecting divergence from bars: {e}")
            return {"type": None, "strength": 0.0}
    
    def _calculate_divergence_strength(self, price_points: List, cvd_points: List) -> float:
        """
        Calculate divergence strength (0.0-1.0).
        
        Args:
            price_points: List of (index, price_value) tuples
            cvd_points: List of (index, cvd_value) tuples
        
        Returns:
            Strength value between 0.0 and 1.0
        """
        if len(price_points) < 2 or len(cvd_points) < 2:
            return 0.0
        
        try:
            # Calculate how opposite the trends are
            price_change = abs(price_points[-1][1] - price_points[-2][1])
            cvd_change = abs(cvd_points[-1][1] - cvd_points[-2][1])
            
            # Normalize to 0-1
            if price_change == 0:
                return 0.0
            
            # Strength based on relative change
            # Higher strength when both price and CVD have significant opposite movements
            strength = min(1.0, (price_change + cvd_change) / (price_change * 2))
            return strength
            
        except Exception as e:
            logger.debug(f"Error calculating divergence strength: {e}")
            return 0.0
    
    def _calculate_cvd_divergence_simplified(self, symbol: str) -> Optional[Dict]:
        """
        Simplified CVD divergence (fallback when price bars unavailable).
        
        Uses order book data instead of price bars.
        """
        if symbol not in self.cvd_history or len(self.cvd_history[symbol]) < 10:
            return None
        
        try:
            # Get recent CVD values
            cvd_values = list(self.cvd_history[symbol])[-20:]
            
            if len(cvd_values) < 10:
                return None
            
            # Simple divergence detection: compare recent CVD trend
            recent_cvd = cvd_values[-10:]
            cvd_trend = recent_cvd[-1] - recent_cvd[0]
            
            # For simplified version, return minimal divergence
            # (Full implementation requires price bars)
            return {
                "strength": 0.0,  # Placeholder
                "type": None
            }
            
        except Exception as e:
            logger.debug(f"Error in simplified CVD divergence for {symbol}: {e}")
            return None
    
    def _detect_absorption_zones(self, symbol: str) -> List[Dict]:
        """
        Detect absorption zones (price levels where large orders are absorbed).
        
        Absorption zones are identified by:
        - High volume at a price level
        - Low price movement (price doesn't move much despite volume)
        - Order book imbalance (large orders on one side)
        
        Returns:
            List of absorption zone dictionaries
        """
        zones = []
        
        if not self.order_flow_service:
            return zones
        
        try:
            # Get order book data
            signal = self.order_flow_service.get_order_flow_signal(symbol)
            if not signal or not signal.get("order_book"):
                return zones
            
            order_book = signal["order_book"]
            imbalance = order_book.get("imbalance", 1.0)
            imbalance_pct = order_book.get("imbalance_pct", 0.0)
            
            # Get recent trade volume
            pressure_data = self.order_flow_service.get_buy_sell_pressure(symbol, window=60)
            if not pressure_data:
                return zones
            
            total_volume = pressure_data.get("buy_volume", 0) + pressure_data.get("sell_volume", 0)
            net_volume = pressure_data.get("net_volume", 0)
            
            # Phase 3.2: Enhanced absorption zone detection with price movement tracking
            # High volume + high imbalance + low price movement = absorption
            if total_volume >= self.absorption_threshold_volume:
                if abs(imbalance - 1.0) >= (self.absorption_threshold_imbalance - 1.0):
                    # Get price movement (for absorption confirmation)
                    price_movement = self._get_price_movement(symbol, window=60)
                    price_stall = self._check_price_stall(symbol, price_movement)
                    
                    # Potential absorption zone detected
                    best_prices = self.order_flow_service.analyzer.depth_analyzer.get_best_bid_ask(symbol)
                    if best_prices:
                        mid_price = (best_prices["bid"] + best_prices["ask"]) / 2
                        
                        # Calculate absorption strength (Phase 3.2: includes price stall)
                        volume_score = min(1.0, total_volume / (self.absorption_threshold_volume * 2))
                        imbalance_score = min(1.0, abs(imbalance_pct) / 50.0)  # 50% imbalance = max score
                        price_stall_score = 1.0 if price_stall else 0.5  # Boost if price stalled
                        strength = (volume_score + imbalance_score + price_stall_score) / 3.0
                        
                        if strength >= 0.5:  # Minimum threshold
                            zones.append({
                                "price_level": mid_price,
                                "strength": strength,
                                "volume_absorbed": total_volume,
                                "net_volume": net_volume,
                                "imbalance_ratio": imbalance,
                                "imbalance_pct": imbalance_pct,
                                "price_movement": price_movement if price_movement else None,
                                "price_stall": price_stall,
                                "side": "BUY" if net_volume > 0 else "SELL",
                                "timestamp": time.time()
                            })
            
            return zones
            
        except Exception as e:
            logger.error(f"Error detecting absorption zones for {symbol}: {e}", exc_info=True)
            return zones
    
    def _calculate_delta_divergence(self, symbol: str, current_delta: float) -> Optional[Dict]:
        """
        Calculate delta divergence (price trend vs delta trend).
        
        Phase 1.3: Uses DeltaDivergenceDetector for accurate detection.
        
        Args:
            symbol: Trading symbol
            current_delta: Current delta value (for reference)
        
        Returns:
            Dict with 'type' ('bullish'/'bearish'), 'strength' (0.0-1.0), or None
        """
        if not DELTA_DIVERGENCE_DETECTOR_AVAILABLE:
            return None
        
        try:
            # Get price bars from MT5
            if not self.mt5_service:
                return None
            
            mt5_symbol = symbol.replace("USDT", "USDc")
            price_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
            if price_bars_df is None or len(price_bars_df) < 20:
                return None
            
            # Get delta history from tick engine if available
            tick_engine = self.tick_engines.get(symbol)
            if tick_engine and hasattr(tick_engine, 'get_delta_history'):
                delta_history = tick_engine.get_delta_history(50)
            else:
                # Fallback: Calculate from recent pressure data
                # This is less accurate but works as fallback
                delta_history = []
                # Try to get recent deltas from order flow service
                if self.order_flow_service:
                    # Get pressure data for multiple windows to build history
                    for window in [30, 60, 90, 120, 150]:
                        pressure = self.order_flow_service.get_buy_sell_pressure(symbol, window)
                        if pressure:
                            delta = pressure.get("buy_volume", 0) - pressure.get("sell_volume", 0)
                            delta_history.append(delta)
                
                if len(delta_history) < 20:
                    return None
            
            # Use delta divergence detector
            detector = DeltaDivergenceDetector(min_bars=20, trend_period=10)
            return detector.detect_delta_divergence(price_bars_df, delta_history)
            
        except Exception as e:
            logger.debug(f"Error calculating delta divergence for {symbol}: {e}")
            return None
    
    def _get_price_movement(self, symbol: str, window: int) -> Optional[float]:
        """
        Get price movement over window (for absorption detection).
        
        Phase 3.2: Calculates price movement using MT5 price bars.
        
        Args:
            symbol: Trading symbol
            window: Time window in seconds
        
        Returns:
            Price movement (absolute change) or None if unavailable
        """
        try:
            # Get price bars from MT5
            if not self.mt5_service:
                return None
            
            mt5_symbol = symbol.replace("USDT", "USDc")
            # Get M1 bars covering the window (window/60 bars, minimum 10)
            bars_needed = max(10, int(window / 60) + 1)
            m1_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", bars_needed)
            
            if m1_bars_df is None or len(m1_bars_df) < 2:
                return None
            
            # Calculate price movement (high - low over window)
            price_high = float(m1_bars_df['high'].max())
            price_low = float(m1_bars_df['low'].min())
            price_movement = price_high - price_low
            
            return price_movement
            
        except Exception as e:
            logger.debug(f"Error getting price movement for {symbol}: {e}")
            return None
    
    def _check_price_stall(self, symbol: str, price_movement: Optional[float]) -> bool:
        """
        Check if price has stalled (low movement relative to ATR).
        
        Phase 3.2: Determines if price movement is low enough to indicate absorption.
        
        Args:
            symbol: Trading symbol
            price_movement: Absolute price movement (from _get_price_movement)
        
        Returns:
            True if price has stalled (low movement), False otherwise
        """
        if price_movement is None:
            # If we can't get price movement, assume not stalled (conservative)
            return False
        
        try:
            # Get ATR for normalization
            atr = self._get_atr(symbol)
            
            if atr and atr > 0:
                # Price movement < 10% of ATR = stalled
                movement_pct = (price_movement / atr) * 100
                return movement_pct < 10.0
            else:
                # Fallback: Use fixed threshold (0.1% of current price)
                # Get current price
                if self.order_flow_service:
                    best_prices = self.order_flow_service.analyzer.depth_analyzer.get_best_bid_ask(symbol)
                    if best_prices:
                        current_price = (best_prices["bid"] + best_prices["ask"]) / 2
                        if current_price > 0:
                            movement_pct = (price_movement / current_price) * 100
                            return movement_pct < 0.1  # < 0.1% movement = stalled
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking price stall for {symbol}: {e}")
            return False
    
    def _get_atr(self, symbol: str) -> Optional[float]:
        """
        Get ATR (Average True Range) for symbol.
        
        Phase 3.2: Gets ATR from MT5 for price movement normalization.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            ATR value or None if unavailable
        """
        try:
            if not self.mt5_service:
                return None
            
            mt5_symbol = symbol.replace("USDT", "USDc")
            
            # Get M1 bars for ATR calculation (need at least 14 bars for ATR)
            m1_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", 20)
            if m1_bars_df is None or len(m1_bars_df) < 14:
                return None
            
            # Calculate ATR (simplified: use high-low range average)
            # True ATR would use True Range (max of high-low, high-prev_close, prev_close-low)
            # For simplicity, use average of high-low ranges
            high_low_ranges = m1_bars_df['high'].values - m1_bars_df['low'].values
            atr = float(np.mean(high_low_ranges[-14:]))  # Last 14 bars
            
            return atr
            
        except Exception as e:
            logger.debug(f"Error getting ATR for {symbol}: {e}")
            return None
    
    def get_metrics_summary(self, symbol: str = "BTCUSDT") -> Optional[str]:
        """
        Get human-readable summary of order flow metrics.
        
        Args:
            symbol: Trading symbol (default: BTCUSDT)
        
        Returns:
            Formatted string summary or None
        """
        metrics = self.get_metrics(symbol)
        if not metrics:
            return None
        
        lines = []
        lines.append(f"📊 Order Flow Metrics: {symbol}")
        lines.append("=" * 60)
        
        # Delta Volume
        lines.append(f"\n💰 Delta Volume:")
        lines.append(f"   Buy: {metrics.buy_volume:,.2f}")
        lines.append(f"   Sell: {metrics.sell_volume:,.2f}")
        lines.append(f"   Net: {metrics.delta_volume:+,.2f} ({metrics.dominant_side})")
        
        # CVD
        lines.append(f"\n📈 CVD (Cumulative Volume Delta):")
        lines.append(f"   Current: {metrics.cvd:+,.2f}")
        lines.append(f"   Slope: {metrics.cvd_slope:+,.2f} per bar")
        lines.append(f"   Bars: {metrics.bar_count}")
        
        # CVD Divergence
        if metrics.cvd_divergence_strength > 0:
            lines.append(f"\n⚠️ CVD Divergence:")
            lines.append(f"   Type: {metrics.cvd_divergence_type or 'None'}")
            lines.append(f"   Strength: {metrics.cvd_divergence_strength:.2%}")
        else:
            lines.append(f"\n✅ CVD Divergence: None detected")
        
        # Absorption Zones
        if metrics.absorption_zones:
            lines.append(f"\n🎯 Absorption Zones: {len(metrics.absorption_zones)}")
            for zone in metrics.absorption_zones[:3]:  # Show top 3
                lines.append(f"   ${zone['price_level']:,.2f} - {zone['side']} "
                           f"(Strength: {zone['strength']:.2%}, "
                           f"Volume: ${zone['volume_absorbed']:,.0f})")
        else:
            lines.append(f"\n✅ Absorption Zones: None detected")
        
        # Buy/Sell Pressure
        lines.append(f"\n⚖️ Buy/Sell Pressure:")
        lines.append(f"   Ratio: {metrics.buy_sell_pressure:.2f}x")
        lines.append(f"   Dominant: {metrics.dominant_side}")
        
        return "\n".join(lines)


def get_btc_order_flow_metrics(order_flow_service=None, mt5_service=None) -> Optional[BTCOrderFlowMetrics]:
    """
    Factory function to create BTCOrderFlowMetrics instance.
    
    Args:
        order_flow_service: OrderFlowService instance (optional, will create if None)
        mt5_service: Optional MT5Service instance (Phase 1.2)
    
    Returns:
        BTCOrderFlowMetrics instance or None if OrderFlowService unavailable
    """
    try:
        if order_flow_service is None:
            from infra.order_flow_service import OrderFlowService
            order_flow_service = OrderFlowService()
        
        return BTCOrderFlowMetrics(order_flow_service=order_flow_service, mt5_service=mt5_service)
    except Exception as e:
        logger.error(f"Failed to create BTCOrderFlowMetrics: {e}", exc_info=True)
        return None

