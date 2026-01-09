"""
Advanced Spread Filter System

Implements rolling median spread filtering with outlier clipping and news window exclusion.
Critical for filtering out high-spread periods that could lead to poor execution.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

class SpreadFilterSignal(Enum):
    """Spread filter signal types."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    EXTREME = "extreme"
    NEWS_WINDOW = "news_window"
    OUTLIER = "outlier"

class NewsEventType(Enum):
    """News event types that affect spreads."""
    NFP = "nfp"  # Non-Farm Payrolls
    FOMC = "fomc"  # Federal Open Market Committee
    ECB = "ecb"  # European Central Bank
    BOE = "boe"  # Bank of England
    RBA = "rba"  # Reserve Bank of Australia
    BOC = "boc"  # Bank of Canada
    RBNZ = "rbnz"  # Reserve Bank of New Zealand
    CPI = "cpi"  # Consumer Price Index
    GDP = "gdp"  # Gross Domestic Product
    RETAIL_SALES = "retail_sales"
    UNEMPLOYMENT = "unemployment"
    INTEREST_RATE = "interest_rate"
    OTHER = "other"

@dataclass
class NewsEvent:
    """News event data structure."""
    event_type: NewsEventType
    timestamp_ms: int
    impact_level: str  # "low", "medium", "high"
    currency: str  # e.g., "USD", "EUR", "GBP"
    description: str
    exclusion_window_minutes: int = 30  # Minutes to exclude around the event

@dataclass
class SpreadData:
    """Spread data point."""
    timestamp_ms: int
    bid: float
    ask: float
    spread: float
    spread_pips: float
    source: str  # "mt5" or "binance"
    is_valid: bool = True

@dataclass
class SpreadFilterConfig:
    """Configuration for spread filter."""
    symbol: str
    window_size: int = 20  # Rolling median window size
    outlier_threshold: float = 2.5  # Standard deviations for outlier detection
    normal_spread_threshold: float = 1.5  # Normal spread threshold in pips
    elevated_spread_threshold: float = 3.0  # Elevated spread threshold in pips
    high_spread_threshold: float = 5.0  # High spread threshold in pips
    extreme_spread_threshold: float = 10.0  # Extreme spread threshold in pips
    news_exclusion_enabled: bool = True
    outlier_clipping_enabled: bool = True
    min_data_points: int = 10  # Minimum data points for analysis
    pip_value: float = 0.0001  # Default pip value for major pairs
    crypto_pip_multiplier: float = 1.0  # Multiplier for crypto pairs

class AdvancedSpreadFilter:
    """
    Advanced spread filter with rolling median, outlier clipping, and news exclusion.
    """
    
    def __init__(self, symbol: str, config: Optional[SpreadFilterConfig] = None):
        self.symbol = symbol
        self.config = config or SpreadFilterConfig(symbol=symbol)
        
        # Spread data storage
        self.spread_buffer = deque(maxlen=self.config.window_size * 2)
        self.rolling_median = deque(maxlen=self.config.window_size)
        self.spread_history = []
        
        # News events
        self.news_events: List[NewsEvent] = []
        self.active_news_windows: List[Tuple[int, int]] = []  # (start_ms, end_ms)
        
        # Statistics
        self.total_spreads_processed = 0
        self.filtered_spreads = 0
        self.outlier_spreads = 0
        self.news_window_spreads = 0
        self.current_median_spread = 0.0
        self.current_std_spread = 0.0
        
        # Performance tracking
        self.last_update_time_ms = 0
        self.update_count = 0
        
        logger.info(f"AdvancedSpreadFilter initialized for {symbol}")

    def add_news_event(self, news_event: NewsEvent):
        """Add a news event for exclusion window calculation."""
        self.news_events.append(news_event)
        
        # Calculate exclusion window
        start_ms = news_event.timestamp_ms - (news_event.exclusion_window_minutes * 60 * 1000)
        end_ms = news_event.timestamp_ms + (news_event.exclusion_window_minutes * 60 * 1000)
        
        self.active_news_windows.append((start_ms, end_ms))
        
        # Sort by start time
        self.active_news_windows.sort(key=lambda x: x[0])
        
        logger.info(f"Added news event: {news_event.event_type.value} at {news_event.timestamp_ms}")

    def update_spread(self, spread_data: SpreadData) -> Optional[SpreadFilterSignal]:
        """
        Update spread filter with new spread data.
        Returns filter signal or None if data is invalid.
        """
        if not spread_data.is_valid or spread_data.spread <= 0:
            return None
        
        current_time_ms = spread_data.timestamp_ms
        self.last_update_time_ms = current_time_ms
        self.update_count += 1
        
        # Add to spread buffer
        self.spread_buffer.append(spread_data)
        self.total_spreads_processed += 1
        
        # Check if we have enough data for analysis
        if len(self.spread_buffer) < self.config.min_data_points:
            return SpreadFilterSignal.NORMAL
        
        # Calculate rolling median
        self._update_rolling_median()
        
        # Check for news window exclusion
        if self._is_in_news_window(current_time_ms):
            self.news_window_spreads += 1
            return SpreadFilterSignal.NEWS_WINDOW
        
        # Check for outliers
        if self._is_outlier(spread_data.spread_pips):
            self.outlier_spreads += 1
            if self.config.outlier_clipping_enabled:
                return SpreadFilterSignal.OUTLIER
        
        # Classify spread level
        signal = self._classify_spread(spread_data.spread_pips)
        
        if signal != SpreadFilterSignal.NORMAL:
            self.filtered_spreads += 1
        
        return signal

    def _update_rolling_median(self):
        """Update rolling median calculation."""
        if len(self.spread_buffer) < self.config.min_data_points:
            return
        
        # Get recent spreads for median calculation
        recent_spreads = [data.spread_pips for data in list(self.spread_buffer)[-self.config.window_size:]]
        
        # Calculate median
        median_spread = np.median(recent_spreads)
        self.rolling_median.append(median_spread)
        
        # Update current statistics
        self.current_median_spread = median_spread
        self.current_std_spread = np.std(recent_spreads) if len(recent_spreads) > 1 else 0.0

    def _is_in_news_window(self, timestamp_ms: int) -> bool:
        """Check if timestamp is within a news exclusion window."""
        if not self.config.news_exclusion_enabled:
            return False
        
        # Clean up expired news windows
        current_time = timestamp_ms
        self.active_news_windows = [
            (start, end) for start, end in self.active_news_windows
            if end > current_time
        ]
        
        # Check if timestamp falls within any active window
        for start_ms, end_ms in self.active_news_windows:
            if start_ms <= timestamp_ms <= end_ms:
                return True
        
        return False

    def _is_outlier(self, spread_pips: float) -> bool:
        """Check if spread is an outlier using statistical methods."""
        if len(self.rolling_median) < self.config.min_data_points:
            return False
        
        # Calculate z-score
        if self.current_std_spread == 0:
            return False
        
        z_score = abs(spread_pips - self.current_median_spread) / self.current_std_spread
        
        return z_score > self.config.outlier_threshold

    def _classify_spread(self, spread_pips: float) -> SpreadFilterSignal:
        """Classify spread into signal categories."""
        if spread_pips <= self.config.normal_spread_threshold:
            return SpreadFilterSignal.NORMAL
        elif spread_pips <= self.config.elevated_spread_threshold:
            return SpreadFilterSignal.ELEVATED
        elif spread_pips <= self.config.high_spread_threshold:
            return SpreadFilterSignal.HIGH
        elif spread_pips <= self.config.extreme_spread_threshold:
            return SpreadFilterSignal.EXTREME
        else:
            return SpreadFilterSignal.EXTREME

    def get_current_median_spread(self) -> float:
        """Get current rolling median spread."""
        return self.current_median_spread

    def get_current_std_spread(self) -> float:
        """Get current spread standard deviation."""
        return self.current_std_spread

    def get_spread_statistics(self) -> Dict:
        """Get comprehensive spread filter statistics."""
        return {
            "symbol": self.symbol,
            "config": {
                "window_size": self.config.window_size,
                "outlier_threshold": self.config.outlier_threshold,
                "normal_threshold": self.config.normal_spread_threshold,
                "elevated_threshold": self.config.elevated_spread_threshold,
                "high_threshold": self.config.high_spread_threshold,
                "extreme_threshold": self.config.extreme_spread_threshold
            },
            "data_counts": {
                "total_spreads_processed": self.total_spreads_processed,
                "filtered_spreads": self.filtered_spreads,
                "outlier_spreads": self.outlier_spreads,
                "news_window_spreads": self.news_window_spreads,
                "spread_buffer_size": len(self.spread_buffer),
                "rolling_median_size": len(self.rolling_median)
            },
            "current_state": {
                "median_spread": self.current_median_spread,
                "std_spread": self.current_std_spread,
                "last_update_time_ms": self.last_update_time_ms,
                "update_count": self.update_count
            },
            "performance": {
                "filter_rate": self.filtered_spreads / max(self.total_spreads_processed, 1),
                "outlier_rate": self.outlier_spreads / max(self.total_spreads_processed, 1),
                "news_exclusion_rate": self.news_window_spreads / max(self.total_spreads_processed, 1)
            }
        }

    def get_recent_spreads(self, count: int = 10) -> List[SpreadData]:
        """Get recent spread data."""
        return list(self.spread_buffer)[-count:]

    def get_spread_distribution(self) -> Dict[str, int]:
        """Get distribution of spread signals."""
        if not self.spread_history:
            return {}
        
        distribution = {}
        for signal in self.spread_history:
            signal_name = signal.value if hasattr(signal, 'value') else str(signal)
            distribution[signal_name] = distribution.get(signal_name, 0) + 1
        
        return distribution

    def is_spread_normal(self) -> bool:
        """Check if current spread is within normal range."""
        if not self.spread_buffer:
            return True
        
        latest_spread = self.spread_buffer[-1]
        return latest_spread.spread_pips <= self.config.normal_spread_threshold

    def is_spread_elevated(self) -> bool:
        """Check if current spread is elevated."""
        if not self.spread_buffer:
            return False
        
        latest_spread = self.spread_buffer[-1]
        return (self.config.normal_spread_threshold < latest_spread.spread_pips <= 
                self.config.elevated_spread_threshold)

    def is_spread_high(self) -> bool:
        """Check if current spread is high."""
        if not self.spread_buffer:
            return False
        
        latest_spread = self.spread_buffer[-1]
        return (self.config.elevated_spread_threshold < latest_spread.spread_pips <= 
                self.config.high_spread_threshold)

    def is_spread_extreme(self) -> bool:
        """Check if current spread is extreme."""
        if not self.spread_buffer:
            return False
        
        latest_spread = self.spread_buffer[-1]
        return latest_spread.spread_pips > self.config.high_spread_threshold

    def get_spread_quality_score(self) -> float:
        """Get spread quality score (0-1, higher is better)."""
        if not self.spread_buffer:
            return 1.0
        
        latest_spread = self.spread_buffer[-1]
        spread_pips = latest_spread.spread_pips
        
        # Calculate quality score based on spread level
        if spread_pips <= self.config.normal_spread_threshold:
            return 1.0
        elif spread_pips <= self.config.elevated_spread_threshold:
            return 0.8
        elif spread_pips <= self.config.high_spread_threshold:
            return 0.6
        elif spread_pips <= self.config.extreme_spread_threshold:
            return 0.4
        else:
            return 0.2

    def should_avoid_trading(self) -> bool:
        """Determine if trading should be avoided due to spread conditions."""
        if not self.spread_buffer:
            return False
        
        latest_spread = self.spread_buffer[-1]
        
        # Avoid trading if spread is extreme or in news window
        if self._is_in_news_window(latest_spread.timestamp_ms):
            return True
        
        if latest_spread.spread_pips > self.config.extreme_spread_threshold:
            return True
        
        return False

    def get_optimal_trading_window(self) -> Optional[Tuple[int, int]]:
        """Get optimal trading window based on spread analysis."""
        if len(self.spread_buffer) < self.config.min_data_points:
            return None
        
        # Find periods with normal spreads
        normal_periods = []
        for i, spread_data in enumerate(self.spread_buffer):
            if spread_data.spread_pips <= self.config.normal_spread_threshold:
                normal_periods.append((spread_data.timestamp_ms, i))
        
        if not normal_periods:
            return None
        
        # Return the most recent normal period
        latest_normal = normal_periods[-1]
        return (latest_normal[0], latest_normal[0] + 300000)  # 5-minute window

    def validate_spread_data(self, spread_data: SpreadData) -> bool:
        """Validate spread data for consistency and quality."""
        if not spread_data.is_valid:
            return False
        
        if spread_data.spread <= 0:
            return False
        
        if spread_data.bid <= 0 or spread_data.ask <= 0:
            return False
        
        if spread_data.ask <= spread_data.bid:
            return False
        
        # Check for reasonable spread range (not too wide or too narrow)
        if spread_data.spread_pips < 0.1 or spread_data.spread_pips > 100.0:
            return False
        
        return True

    def reset_filter(self):
        """Reset the spread filter to initial state."""
        self.spread_buffer.clear()
        self.rolling_median.clear()
        self.spread_history.clear()
        self.total_spreads_processed = 0
        self.filtered_spreads = 0
        self.outlier_spreads = 0
        self.news_window_spreads = 0
        self.current_median_spread = 0.0
        self.current_std_spread = 0.0
        self.last_update_time_ms = 0
        self.update_count = 0
        
        logger.info(f"Spread filter reset for {self.symbol}")

    def get_filter_status(self) -> Dict:
        """Get current filter status and health."""
        return {
            "symbol": self.symbol,
            "is_healthy": len(self.spread_buffer) >= self.config.min_data_points,
            "data_quality": {
                "buffer_size": len(self.spread_buffer),
                "median_size": len(self.rolling_median),
                "last_update_age_ms": int(time.time() * 1000) - self.last_update_time_ms
            },
            "spread_conditions": {
                "is_normal": self.is_spread_normal(),
                "is_elevated": self.is_spread_elevated(),
                "is_high": self.is_spread_high(),
                "is_extreme": self.is_spread_extreme(),
                "quality_score": self.get_spread_quality_score()
            },
            "trading_recommendation": {
                "should_avoid": self.should_avoid_trading(),
                "optimal_window": self.get_optimal_trading_window()
            }
        }
