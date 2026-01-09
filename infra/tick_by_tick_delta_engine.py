"""
Tick-by-Tick Delta Engine (Phase 1.1)

Real-time delta calculation from Binance aggTrades.
Processes each aggTrade to calculate delta and CVD incrementally.

Note: Binance aggTrades are aggregated trades, not individual ticks.
Each aggTrade represents multiple trades combined, but provides
buy/sell side information sufficient for delta calculation.
"""

import logging
import time
from typing import Dict, Optional, List, Deque
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DeltaMetrics:
    """Delta metrics for a single aggTrade"""
    delta: float
    cvd: float
    timestamp: float
    buy_volume: float
    sell_volume: float
    cumulative_buy_volume: float
    cumulative_sell_volume: float


class TickByTickDeltaEngine:
    """
    Real-time delta calculation engine.
    
    Processes Binance aggTrades to calculate:
    - Delta per trade (buy_volume - sell_volume)
    - Cumulative Volume Delta (CVD)
    - Delta history for divergence detection
    """
    
    def __init__(self, symbol: str = "BTCUSDT", max_history: int = 200):
        """
        Initialize tick-by-tick delta engine.
        
        Args:
            symbol: Trading symbol (default: BTCUSDT)
            max_history: Maximum number of delta/CVD values to store
        """
        self.symbol = symbol
        self.max_history = max_history
        
        # Real-time buffers (bounded deques for memory efficiency)
        self.tick_buffer: Deque[Dict] = deque(maxlen=1000)  # Last 1000 aggTrades
        self.delta_history: Deque[float] = deque(maxlen=max_history)  # Last N delta values
        self.cvd_history: Deque[float] = deque(maxlen=max_history * 2)  # Last 2N CVD values
        
        # Current state
        self.current_delta = 0.0
        self.current_cvd = 0.0
        self.cumulative_buy_volume = 0.0
        self.cumulative_sell_volume = 0.0
        self.last_tick_time = 0.0
        self.tick_count = 0
        
        logger.debug(f"TickByTickDeltaEngine initialized for {symbol}")
    
    def process_aggtrade(self, trade_data: Dict) -> Optional[DeltaMetrics]:
        """
        Process Binance aggTrade and calculate delta.
        
        Args:
            trade_data: Dict with 'side' ("BUY"/"SELL"), 'quantity', 'timestamp', 'price'
        
        Returns:
            DeltaMetrics or None if insufficient data
        """
        try:
            # Extract from trade data (Binance aggTrade format)
            side = trade_data.get("side")  # "BUY" or "SELL"
            quantity = trade_data.get("quantity", 0.0)
            timestamp = trade_data.get("timestamp", time.time())
            price = trade_data.get("price", 0.0)
            
            if quantity <= 0:
                return None
            
            # Calculate buy/sell volume
            if side == "BUY":
                buy_volume = quantity
                sell_volume = 0.0
            elif side == "SELL":
                buy_volume = 0.0
                sell_volume = quantity
            else:
                logger.warning(f"Unknown side '{side}' in trade data")
                return None
            
            # Calculate delta for this trade
            delta = buy_volume - sell_volume
            
            # Update cumulative volumes
            self.cumulative_buy_volume += buy_volume
            self.cumulative_sell_volume += sell_volume
            
            # Update CVD (cumulative sum of deltas)
            self.current_cvd += delta
            self.cvd_history.append(self.current_cvd)
            
            # Store delta
            self.current_delta = delta
            self.delta_history.append(delta)
            
            # Store trade
            self.tick_buffer.append({
                "delta": delta,
                "cvd": self.current_cvd,
                "timestamp": timestamp,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "price": price,
                "quantity": quantity
            })
            
            self.last_tick_time = timestamp
            self.tick_count += 1
            
            return DeltaMetrics(
                delta=delta,
                cvd=self.current_cvd,
                timestamp=timestamp,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                cumulative_buy_volume=self.cumulative_buy_volume,
                cumulative_sell_volume=self.cumulative_sell_volume
            )
            
        except Exception as e:
            logger.error(f"Error processing aggTrade for {self.symbol}: {e}")
            return None
    
    def get_current_delta(self) -> float:
        """Get current delta value"""
        return self.current_delta
    
    def get_cvd_value(self) -> float:
        """Get current CVD value"""
        return self.current_cvd
    
    def get_cvd_trend(self, period: int = 10) -> Dict[str, any]:
        """
        Get CVD trend (rising/falling/flat) based on recent slope.
        
        Args:
            period: Number of recent CVD values to analyze (default: 10)
        
        Returns:
            Dict with 'trend' ('rising'/'falling'/'flat') and 'slope' (float)
        """
        if len(self.cvd_history) < period:
            return {'trend': 'flat', 'slope': 0.0}
        
        # Get last N CVD values
        recent_cvd = list(self.cvd_history)[-period:]
        
        # Calculate slope (simple linear regression)
        if len(recent_cvd) < 2:
            return {'trend': 'flat', 'slope': 0.0}
        
        # Simple slope calculation: (last - first) / period
        slope = (recent_cvd[-1] - recent_cvd[0]) / period
        
        # Determine trend
        if slope > 0.01:  # Threshold to avoid noise
            trend = 'rising'
        elif slope < -0.01:
            trend = 'falling'
        else:
            trend = 'flat'
        
        return {
            'trend': trend,
            'slope': slope,
            'cvd_start': recent_cvd[0],
            'cvd_end': recent_cvd[-1],
            'period': period
        }
    
    def get_delta_history(self, count: int = 20) -> List[float]:
        """
        Get recent delta history.
        
        Args:
            count: Number of recent delta values to return
        
        Returns:
            List of delta values (most recent last)
        """
        if len(self.delta_history) == 0:
            return []
        
        return list(self.delta_history)[-count:]
    
    def get_cvd_history(self, count: int = 20) -> List[float]:
        """
        Get recent CVD history.
        
        Args:
            count: Number of recent CVD values to return
        
        Returns:
            List of CVD values (most recent last)
        """
        if len(self.cvd_history) == 0:
            return []
        
        return list(self.cvd_history)[-count:]
    
    def get_statistics(self) -> Dict[str, any]:
        """Get engine statistics"""
        return {
            'symbol': self.symbol,
            'tick_count': self.tick_count,
            'current_delta': self.current_delta,
            'current_cvd': self.current_cvd,
            'cumulative_buy_volume': self.cumulative_buy_volume,
            'cumulative_sell_volume': self.cumulative_sell_volume,
            'delta_history_size': len(self.delta_history),
            'cvd_history_size': len(self.cvd_history),
            'last_tick_time': self.last_tick_time,
            'cvd_trend': self.get_cvd_trend()
        }
    
    def reset(self):
        """Reset engine state (useful for testing or reinitialization)"""
        self.tick_buffer.clear()
        self.delta_history.clear()
        self.cvd_history.clear()
        self.current_delta = 0.0
        self.current_cvd = 0.0
        self.cumulative_buy_volume = 0.0
        self.cumulative_sell_volume = 0.0
        self.last_tick_time = 0.0
        self.tick_count = 0
        logger.debug(f"TickByTickDeltaEngine reset for {self.symbol}")
