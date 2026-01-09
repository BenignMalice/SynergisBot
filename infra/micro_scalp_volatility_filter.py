"""
Micro-Scalp Volatility Filter

Filters micro-scalp trades based on volatility conditions:
- ATR(1) threshold validation
- M1 range size validation
- Spread volatility adjustment
- Session-adaptive thresholds (future enhancement)
"""

from __future__ import annotations

import logging
import statistics
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VolatilityFilterResult:
    """Volatility filter check result"""
    passed: bool
    atr1_value: float
    atr1_passed: bool
    m1_range_avg: float
    m1_range_passed: bool
    spread_passed: bool
    reasons: List[str]  # Reasons for pass/fail


class MicroScalpVolatilityFilter:
    """
    Volatility filter for micro-scalp strategy.
    
    Validates:
    - ATR(1) >= threshold (symbol-specific)
    - Average M1 range >= threshold (symbol-specific)
    - Spread within limits
    - Volatility state (expanding/contracting)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Micro-Scalp Volatility Filter.
        
        Args:
            config: Configuration dict with symbol-specific thresholds
        """
        self.config = config
        self.session_manager = None  # Optional: for session-adaptive thresholds
    
    def calculate_atr1(self, candles: List[Dict[str, Any]]) -> float:
        """
        Calculate ATR(1) from M1 candles.
        
        ATR(1) uses period=1, which means it's just the True Range of the last candle.
        For micro-scalps, we use a small period (e.g., 3-5) to get recent volatility.
        
        Args:
            candles: List of M1 candle dicts
        
        Returns:
            ATR(1) value (using period=3 for stability)
        """
        if len(candles) < 2:
            return 0.0
        
        # Calculate True Range for recent candles
        true_ranges = []
        period = min(3, len(candles) - 1)  # Use last 3 candles for ATR(1)
        
        for i in range(max(1, len(candles) - period), len(candles)):
            high = candles[i].get('high', 0)
            low = candles[i].get('low', 0)
            prev_close = candles[i-1].get('close', 0) if i > 0 else candles[i].get('open', 0)
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if not true_ranges:
            return 0.0
        
        return statistics.mean(true_ranges)
    
    def calculate_atr14(self, candles: List[Dict[str, Any]]) -> float:
        """
        Calculate ATR(14) from M1 candles.
        
        ATR(14) uses period=14, which is the standard ATR calculation.
        Uses Wilder's smoothing method (exponential moving average of True Range).
        
        Args:
            candles: List of M1 candle dicts (need at least 15 candles for ATR14)
        
        Returns:
            ATR(14) value or 0.0 if insufficient data
        """
        if len(candles) < 15:
            return 0.0
        
        # Calculate True Range for all candles
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].get('high', 0)
            low = candles[i].get('low', 0)
            prev_close = candles[i-1].get('close', 0)
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < 14:
            return 0.0
        
        # Use Wilder's smoothing: ATR = (Previous ATR * 13 + Current TR) / 14
        # For first ATR, use simple average of first 14 TR values
        atr = statistics.mean(true_ranges[:14])
        
        # Apply Wilder's smoothing for remaining values
        for tr in true_ranges[14:]:
            atr = (atr * 13 + tr) / 14
        
        return atr
    
    def calculate_avg_m1_range(self, candles: List[Dict[str, Any]], window: int = 10) -> float:
        """
        Calculate average M1 range over recent candles.
        
        Args:
            candles: List of M1 candle dicts
            window: Number of candles to average (default: 10)
        
        Returns:
            Average M1 range
        """
        if len(candles) == 0:
            return 0.0
        
        recent_candles = candles[-window:] if len(candles) >= window else candles
        
        ranges = []
        for candle in recent_candles:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            if high > 0 and low > 0:
                ranges.append(high - low)
        
        if not ranges:
            return 0.0
        
        return statistics.mean(ranges)
    
    def check_volatility_filters(self, symbol: str, candles: List[Dict[str, Any]],
                                current_spread: float, spread_data: Optional[Dict[str, Any]] = None) -> VolatilityFilterResult:
        """
        Check all volatility filters for a symbol.
        
        Args:
            symbol: Trading symbol
            candles: List of M1 candles
            current_spread: Current spread value
            spread_data: Optional spread data from SpreadTracker
        
        Returns:
            VolatilityFilterResult
        """
        # Get symbol-specific rules
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        
        if rules_key not in self.config:
            return VolatilityFilterResult(
                passed=False,
                atr1_value=0.0,
                atr1_passed=False,
                m1_range_avg=0.0,
                m1_range_passed=False,
                spread_passed=False,
                reasons=["Symbol not configured"]
            )
        
        rules = self.config[rules_key]
        pre_trade_filters = rules.get('pre_trade_filters', {})
        volatility_filters = pre_trade_filters.get('volatility', {})
        spread_filters = pre_trade_filters.get('spread', {})
        
        # Calculate ATR(1)
        atr1_value = self.calculate_atr1(candles)
        atr1_min = volatility_filters.get('atr1_min', 0.0)
        atr1_passed = atr1_value >= atr1_min
        
        # Calculate average M1 range
        m1_range_avg = self.calculate_avg_m1_range(candles)
        m1_range_min = volatility_filters.get('m1_range_avg_min', 0.0)
        m1_range_passed = m1_range_avg >= m1_range_min
        
        # Check spread
        max_spread = spread_filters.get('max_spread', float('inf'))
        spread_passed = current_spread <= max_spread
        
        # Determine if all filters passed
        passed = atr1_passed and m1_range_passed and spread_passed
        
        # Build reasons
        reasons = []
        if not atr1_passed:
            reasons.append(f"ATR(1) {atr1_value:.4f} < threshold {atr1_min:.4f}")
        if not m1_range_passed:
            reasons.append(f"Avg M1 range {m1_range_avg:.4f} < threshold {m1_range_min:.4f}")
        if not spread_passed:
            reasons.append(f"Spread {current_spread:.4f} > max {max_spread:.4f}")
        if passed:
            reasons.append("All volatility filters passed")
        
        return VolatilityFilterResult(
            passed=passed,
            atr1_value=atr1_value,
            atr1_passed=atr1_passed,
            m1_range_avg=m1_range_avg,
            m1_range_passed=m1_range_passed,
            spread_passed=spread_passed,
            reasons=reasons
        )
    
    def get_dynamic_atr_threshold(self, symbol: str, atr1_value: float) -> float:
        """
        Get dynamic ATR threshold based on 30-min rolling ATR (future enhancement).
        
        Args:
            symbol: Trading symbol
            atr1_value: Current ATR(1) value
        
        Returns:
            Dynamic threshold (currently returns base threshold)
        """
        # TODO: Implement 30-min rolling ATR calculation
        # For now, return base threshold
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        
        if rules_key not in self.config:
            return 0.0
        
        rules = self.config[rules_key]
        pre_trade_filters = rules.get('pre_trade_filters', {})
        volatility_filters = pre_trade_filters.get('volatility', {})
        
        base_threshold = volatility_filters.get('atr1_min', 0.0)
        
        # Future: Calculate 30-min rolling ATR and adapt threshold
        # rolling_atr = self._calculate_rolling_atr(symbol, window_minutes=30)
        # if rolling_atr > base_threshold * 1.5:
        #     return base_threshold * 1.2
        # elif rolling_atr < base_threshold * 0.7:
        #     return base_threshold * 0.9
        
        return base_threshold
    
    def check_session_filter(self, symbol: str) -> bool:
        """
        Check if current session allows micro-scalps.
        
        Blocks Post-NY session (21-23 UTC) for low volatility.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if session allows micro-scalps, False otherwise
        """
        risk_mitigation = self.config.get('risk_mitigation', {})
        if not risk_mitigation.get('session_filter_enabled', False):
            return True  # Session filter disabled
        
        if not risk_mitigation.get('block_post_ny_session', False):
            return True  # Post-NY blocking disabled
        
        try:
            from datetime import datetime, timezone
            utc_now = datetime.now(timezone.utc)
            utc_hour = utc_now.hour
            
            post_ny_hours = risk_mitigation.get('post_ny_session_hours', [21, 23])
            if len(post_ny_hours) == 2:
                start_hour, end_hour = post_ny_hours
                if start_hour <= utc_hour < end_hour:
                    return False  # Block micro-scalps during Post-NY session
        
        except Exception as e:
            logger.warning(f"Error checking session filter: {e}")
            return True  # Allow on error
        
        return True
    
    def is_volatility_expanding(self, candles: List[Dict[str, Any]], window: int = 5) -> bool:
        """
        Check if volatility is expanding (for micro-scalp confirmation).
        
        Args:
            candles: List of M1 candles
            window: Number of candles to compare (default: 5)
        
        Returns:
            True if volatility is expanding
        """
        if len(candles) < window * 2:
            return False
        
        # Calculate recent ATR(1) values
        recent_atr = self.calculate_atr1(candles[-window:])
        previous_atr = self.calculate_atr1(candles[-(window * 2):-window])
        
        if previous_atr == 0:
            return False
        
        # Volatility expanding if recent ATR > previous ATR
        return recent_atr > previous_atr * 1.1  # 10% increase

