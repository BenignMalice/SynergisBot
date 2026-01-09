"""
Spread Tracker for Micro-Scalp Strategy

Tracks real-time spread, calculates rolling average and volatility (stdev)
to prevent low-volume false triggers and catch Asian-session expansions.
"""

from __future__ import annotations

import logging
import statistics
from collections import deque
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SpreadData:
    """Spread data for a symbol"""
    current_spread: float
    average_spread: float
    spread_volatility: float  # Standard deviation
    spread_ratio: float  # current / average
    sample_count: int


class SpreadTracker:
    """
    Tracks spread history and calculates rolling statistics.
    
    Features:
    - Rolling average spread (last 100 M1 candles)
    - Spread volatility (stdev) calculation
    - Asian-session expansion detection
    - Low-volume false trigger prevention
    """
    
    def __init__(self, window_size: int = 100):
        """
        Initialize Spread Tracker.
        
        Args:
            window_size: Number of spread samples to keep (default: 100)
        """
        self.window_size = window_size
        self.spread_history: Dict[str, deque] = {}  # {symbol: deque of spreads}
        self.timestamps: Dict[str, deque] = {}  # {symbol: deque of timestamps}
    
    def update_spread(self, symbol: str, bid: float, ask: float, timestamp: Optional[float] = None) -> float:
        """
        Update spread history for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc", "BTCUSDc")
            bid: Current bid price
            ask: Current ask price
            timestamp: Optional timestamp (default: current time)
        
        Returns:
            Current spread value
        """
        spread = ask - bid
        
        if spread <= 0:
            logger.warning(f"Invalid spread for {symbol}: {spread} (bid={bid}, ask={ask})")
            return 0.0
        
        # Initialize deques if needed
        if symbol not in self.spread_history:
            self.spread_history[symbol] = deque(maxlen=self.window_size)
            self.timestamps[symbol] = deque(maxlen=self.window_size)
        
        # Add to history
        self.spread_history[symbol].append(spread)
        if timestamp is not None:
            self.timestamps[symbol].append(timestamp)
        
        return spread
    
    def get_average_spread(self, symbol: str, window: Optional[int] = None) -> float:
        """
        Get average spread for a symbol.
        
        Args:
            symbol: Trading symbol
            window: Optional window size (default: use all available data)
        
        Returns:
            Average spread, or 0.0 if no data
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) == 0:
            return 0.0
        
        spreads = list(self.spread_history[symbol])
        
        if window is not None:
            spreads = spreads[-window:]
        
        if len(spreads) == 0:
            return 0.0
        
        return statistics.mean(spreads)
    
    def get_spread_volatility(self, symbol: str, window: Optional[int] = None) -> float:
        """
        Get spread volatility (standard deviation) for a symbol.
        
        Args:
            symbol: Trading symbol
            window: Optional window size (default: use all available data)
        
        Returns:
            Spread volatility (stdev), or 0.0 if insufficient data
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) < 2:
            return 0.0
        
        spreads = list(self.spread_history[symbol])
        
        if window is not None:
            spreads = spreads[-window:]
        
        if len(spreads) < 2:
            return 0.0
        
        try:
            return statistics.stdev(spreads)
        except statistics.StatisticsError:
            return 0.0
    
    def get_spread_ratio(self, symbol: str, current_spread: Optional[float] = None) -> float:
        """
        Get current spread ratio (current / average).
        
        Args:
            symbol: Trading symbol
            current_spread: Optional current spread (if None, uses latest)
        
        Returns:
            Spread ratio, or 0.0 if no data
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) == 0:
            return 0.0
        
        if current_spread is None:
            current_spread = self.spread_history[symbol][-1]
        
        avg_spread = self.get_average_spread(symbol)
        
        if avg_spread == 0:
            return 0.0
        
        return current_spread / avg_spread
    
    def is_spread_acceptable(self, symbol: str, max_ratio: float = 1.5, 
                            current_spread: Optional[float] = None) -> bool:
        """
        Check if current spread is acceptable for micro-scalp execution.
        
        Args:
            symbol: Trading symbol
            max_ratio: Maximum spread ratio (default: 1.5)
            current_spread: Optional current spread (if None, uses latest)
        
        Returns:
            True if spread is acceptable, False otherwise
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) == 0:
            # No data yet, allow trade (will be validated later)
            return True
        
        ratio = self.get_spread_ratio(symbol, current_spread)
        
        if ratio == 0:
            return True  # No average yet, allow trade
        
        return ratio <= max_ratio
    
    def get_spread_data(self, symbol: str, current_spread: Optional[float] = None) -> SpreadData:
        """
        Get comprehensive spread data for a symbol.
        
        Args:
            symbol: Trading symbol
            current_spread: Optional current spread (if None, uses latest)
        
        Returns:
            SpreadData object with all metrics
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) == 0:
            return SpreadData(
                current_spread=current_spread or 0.0,
                average_spread=0.0,
                spread_volatility=0.0,
                spread_ratio=0.0,
                sample_count=0
            )
        
        if current_spread is None:
            current_spread = self.spread_history[symbol][-1]
        
        avg_spread = self.get_average_spread(symbol)
        volatility = self.get_spread_volatility(symbol)
        ratio = self.get_spread_ratio(symbol, current_spread)
        sample_count = len(self.spread_history[symbol])
        
        return SpreadData(
            current_spread=current_spread,
            average_spread=avg_spread,
            spread_volatility=volatility,
            spread_ratio=ratio,
            sample_count=sample_count
        )
    
    def detect_asian_session_expansion(self, symbol: str, threshold_multiplier: float = 2.0) -> bool:
        """
        Detect if spread has expanded significantly (e.g., during Asian session).
        
        Args:
            symbol: Trading symbol
            threshold_multiplier: Threshold multiplier for expansion (default: 2.0)
        
        Returns:
            True if spread expansion detected, False otherwise
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) < 10:
            return False
        
        avg_spread = self.get_average_spread(symbol)
        current_spread = self.spread_history[symbol][-1]
        
        if avg_spread == 0:
            return False
        
        ratio = current_spread / avg_spread
        return ratio >= threshold_multiplier
    
    def clear_history(self, symbol: Optional[str] = None):
        """
        Clear spread history for a symbol or all symbols.
        
        Args:
            symbol: Optional symbol to clear (if None, clears all)
        """
        if symbol is not None:
            if symbol in self.spread_history:
                del self.spread_history[symbol]
            if symbol in self.timestamps:
                del self.timestamps[symbol]
        else:
            self.spread_history.clear()
            self.timestamps.clear()
    
    def get_sample_count(self, symbol: str) -> int:
        """
        Get number of spread samples for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Number of samples
        """
        if symbol not in self.spread_history:
            return 0
        return len(self.spread_history[symbol])
    
    def get_median_spread(self, symbol: str, window: Optional[int] = None) -> float:
        """
        Get median spread for a symbol.
        
        Args:
            symbol: Trading symbol
            window: Optional window size (default: use all available data)
        
        Returns:
            Median spread, or 0.0 if no data
        """
        if symbol not in self.spread_history or len(self.spread_history[symbol]) == 0:
            return 0.0
        
        spreads = list(self.spread_history[symbol])
        
        if window is not None:
            spreads = spreads[-window:]
        
        if len(spreads) == 0:
            return 0.0
        
        try:
            return statistics.median(spreads)
        except statistics.StatisticsError:
            return 0.0

