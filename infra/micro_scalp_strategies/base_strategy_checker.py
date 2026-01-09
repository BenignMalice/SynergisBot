"""
Base Strategy Checker

Base class for strategy-specific condition checkers with shared helper methods.
All strategy checkers inherit from this class to access helper methods.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import statistics

from infra.micro_scalp_conditions import MicroScalpConditionsChecker, ConditionCheckResult

logger = logging.getLogger(__name__)


class BaseStrategyChecker(MicroScalpConditionsChecker, ABC):
    """
    Base class for strategy-specific condition checkers.
    
    CRITICAL: This class includes helper methods that are also used by MicroScalpRegimeDetector.
    These methods are made available here so strategy checkers can access them via inheritance.
    """
    
    def __init__(self, config: Dict[str, Any], 
                 volatility_filter, 
                 vwap_filter, 
                 sweep_detector, 
                 ob_detector, 
                 spread_tracker,
                 m1_analyzer=None, 
                 session_manager=None, 
                 news_service=None,
                 strategy_name: str = None):
        super().__init__(config, volatility_filter, vwap_filter,
                        sweep_detector, ob_detector, spread_tracker,
                        m1_analyzer, session_manager)
        self.news_service = news_service  # For news checks in Layer 1
        self.strategy_name = strategy_name  # For confluence weight lookup
        self._current_snapshot = None  # Temporary snapshot storage for helper method access
    
    def validate(self, snapshot: Dict[str, Any]) -> ConditionCheckResult:
        """
        Base implementation that calls strategy-specific overrides.
        
        Subclasses should NOT override this method, but should override:
        - _check_location_filter() - Strategy-specific location requirements
        - _check_candle_signals() - Strategy-specific signal detection
        - _calculate_confluence_score() - Strategy-specific confluence weighting
        
        This ensures consistent 4-layer validation structure while allowing
        strategy-specific logic in individual layers.
        """
        # Store snapshot temporarily for helper method access (e.g., range_structure)
        self._current_snapshot = snapshot
        
        try:
            # Extract parameters from snapshot (base class methods require individual params)
            symbol = snapshot.get('symbol', '')
            candles = snapshot.get('candles', [])
            current_price = snapshot.get('current_price', 0.0)
            vwap = snapshot.get('vwap', 0.0)
            atr1 = snapshot.get('atr1')
            btc_order_flow = snapshot.get('btc_order_flow')
            
            reasons = []
            details = {}
            
            # Layer 1: Pre-Trade Filters (use base class)
            pre_trade_result = self._check_pre_trade_filters(
                symbol, candles, snapshot.get('spread_data'), current_price
            )
            pre_trade_passed = pre_trade_result.passed
            details['pre_trade'] = {
                'passed': pre_trade_passed,
                'atr1': pre_trade_result.atr1_value,
                'm1_range_avg': pre_trade_result.m1_range_avg,
                'reasons': pre_trade_result.reasons
            }
            
            if not pre_trade_passed:
                reasons.extend(pre_trade_result.reasons)
                return ConditionCheckResult(
                    passed=False,
                    pre_trade_passed=False,
                    location_passed=False,
                    primary_triggers=0,
                    secondary_confluence=0,
                    confluence_score=0.0,
                    is_aplus_setup=False,
                    reasons=reasons,
                    details=details
                )
            
            # Layer 2: Location Filter (strategy-specific override)
            location_result = self._check_location_filter(symbol, candles, current_price, vwap, atr1)
            location_passed = location_result.get('passed', False)
            details['location'] = location_result
            
            if not location_passed:
                reasons.append("Not at edge location (strategy-specific check failed)")
                return ConditionCheckResult(
                    passed=False,
                    pre_trade_passed=True,
                    location_passed=False,
                    primary_triggers=0,
                    secondary_confluence=0,
                    confluence_score=0.0,
                    is_aplus_setup=False,
                    reasons=reasons,
                    details=details
                )
            
            # Layer 3: Candle Signals (strategy-specific override)
            signal_result = self._check_candle_signals(
                symbol, candles, current_price, vwap, atr1, btc_order_flow
            )
            primary_count = signal_result.get('primary_count', 0)
            secondary_count = signal_result.get('secondary_count', 0)
            primary_triggers = signal_result.get('primary_triggers', [])
            secondary_confluence = signal_result.get('secondary_confluence', [])
            details['signals'] = signal_result
            
            if primary_count < 1 or secondary_count < 1:
                failure_msg = f"Insufficient signals: {primary_count} primary, {secondary_count} secondary (need ≥1 each)"
                if primary_count > 0:
                    failure_msg += f" - Primary: {', '.join(primary_triggers)}"
                if secondary_count > 0:
                    failure_msg += f" - Secondary: {', '.join(secondary_confluence)}"
                reasons.append(failure_msg)
                return ConditionCheckResult(
                    passed=False,
                    pre_trade_passed=True,
                    location_passed=True,
                    primary_triggers=primary_count,
                    secondary_confluence=secondary_count,
                    confluence_score=0.0,
                    is_aplus_setup=False,
                    reasons=reasons,
                    details=details
                )
            
            # Layer 4: Confluence Score (strategy-specific override)
            confluence_score = self._calculate_confluence_score(
                symbol, candles, current_price, vwap, atr1, location_result, signal_result
            )
            details['confluence'] = {
                'score': confluence_score,
                'min_for_trade': self._get_min_score(symbol),
                'min_for_aplus': self._get_min_score_aplus(symbol)
            }
            
            min_score = self._get_min_score(symbol)
            min_score_aplus = self._get_min_score_aplus(symbol)
            
            if confluence_score < min_score:
                reasons.append(f"Confluence score {confluence_score:.1f} < minimum {min_score}")
                return ConditionCheckResult(
                    passed=False,
                    pre_trade_passed=True,
                    location_passed=True,
                    primary_triggers=primary_count,
                    secondary_confluence=secondary_count,
                    confluence_score=confluence_score,
                    is_aplus_setup=False,
                    reasons=reasons,
                    details=details
                )
            
            # All layers passed
            is_aplus = confluence_score >= min_score_aplus
            
            result = ConditionCheckResult(
                passed=True,
                pre_trade_passed=True,
                location_passed=True,
                primary_triggers=primary_count,
                secondary_confluence=secondary_count,
                confluence_score=confluence_score,
                is_aplus_setup=is_aplus,
                reasons=reasons,
                details=details
            )
            
            return result
        finally:
            # Always clear snapshot reference
            self._current_snapshot = None
    
    @abstractmethod
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """Generate strategy-specific trade idea"""
        pass
    
    # ============================================================================
    # HELPER METHODS - Shared with MicroScalpRegimeDetector
    # ============================================================================
    
    def _calculate_vwap_std(self, candles: List[Dict], vwap: float) -> float:
        """Calculate VWAP standard deviation (shared helper method)"""
        if len(candles) < 10 or vwap == 0:
            return 0.0
        
        try:
            # Calculate typical prices
            typical_prices = []
            volumes = []
            
            for candle in candles[-20:]:  # Use last 20 candles
                high = candle.get('high', 0)
                low = candle.get('low', 0)
                close = candle.get('close', 0)
                volume = candle.get('volume', 0)
                
                if volume > 0:
                    typical_price = (high + low + close) / 3
                    typical_prices.append(typical_price)
                    volumes.append(volume)
            
            if not typical_prices:
                return 0.0
            
            # Calculate weighted standard deviation
            total_volume = sum(volumes)
            if total_volume == 0:
                return 0.0
            
            # Weighted mean
            weighted_mean = sum(tp * vol for tp, vol in zip(typical_prices, volumes)) / total_volume
            
            # Weighted variance
            weighted_variance = sum(vol * (tp - weighted_mean) ** 2 for tp, vol in zip(typical_prices, volumes)) / total_volume
            
            # Standard deviation
            std = weighted_variance ** 0.5
            
            return std
        except Exception as e:
            logger.debug(f"Error calculating VWAP std: {e}")
            return 0.0
    
    def _calculate_vwap_slope(self, candles: List[Dict[str, Any]], vwap: float) -> float:
        """Calculate VWAP slope over last N candles (shared helper method)"""
        if len(candles) < 5 or vwap == 0:
            return 0.0
        
        # Calculate VWAP for last 5 candles and previous 5 candles
        recent_candles = candles[-5:]
        previous_candles = candles[-10:-5] if len(candles) >= 10 else candles[:5]
        
        # Calculate VWAP for each period
        recent_vwap = self._calculate_vwap_from_candles(recent_candles)
        previous_vwap = self._calculate_vwap_from_candles(previous_candles)
        
        if previous_vwap == 0:
            return 0.0
        
        # Slope = (recent_vwap - previous_vwap) / previous_vwap
        # Normalized by price to get percentage change
        slope = (recent_vwap - previous_vwap) / previous_vwap
        
        return slope
    
    def _calculate_vwap_from_candles(self, candles: List[Dict[str, Any]]) -> float:
        """Calculate VWAP from candle list (helper for slope calculation)"""
        if not candles:
            return 0.0
        
        total_pv = 0.0
        total_volume = 0.0
        
        for candle in candles:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)
            
            if volume <= 0:
                continue
            
            typical_price = (high + low + close) / 3
            total_pv += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return 0.0
        
        return total_pv / total_volume
    
    def _check_volume_spike(self, candles: List[Dict]) -> bool:
        """Check volume spike using configurable normalization method (shared helper)"""
        volume_normalization = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_normalization', 'multiplier')
        
        if volume_normalization == 'z_score':
            return self._check_volume_spike_zscore(candles)
        else:
            return self._check_volume_spike_multiplier(candles)
    
    def _check_volume_spike_multiplier(self, candles: List[Dict]) -> bool:
        """Check if volume ≥ multiplier × 10-bar average"""
        if len(candles) < 11:
            return False
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-11:-1]]
        avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
        
        if avg_volume == 0:
            return False
        
        volume_multiplier = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_spike_multiplier', 1.3)
        return last_volume >= avg_volume * volume_multiplier
    
    def _check_volume_spike_zscore(self, candles: List[Dict]) -> bool:
        """Check volume spike using Z-score normalization (exchange-agnostic)"""
        if len(candles) < 31:
            # Fallback to multiplier if not enough data
            return self._check_volume_spike_multiplier(candles)
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-31:-1]]
        
        if not recent_volumes or all(v == 0 for v in recent_volumes):
            return False
        
        mean_volume = statistics.mean(recent_volumes)
        std_volume = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
        
        if std_volume == 0:
            # Fallback to multiplier
            return self._check_volume_spike_multiplier(candles)
        
        z_score = (last_volume - mean_volume) / std_volume
        z_score_threshold = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_z_score_threshold', 1.5)
        
        return z_score >= z_score_threshold
    
    def _check_bb_compression(self, candles: List[Dict]) -> bool:
        """
        Check if Bollinger Band width is contracting (shared helper method).
        
        RECOMMENDED: BB width < 0.02 (2% of price) → Balanced Zone
        
        Returns True if:
        - Recent BB width < 2% of price (absolute threshold)
        - OR Recent BB width < threshold × average (relative compression fallback)
        """
        if len(candles) < 20:
            return False
        
        try:
            import pandas as pd
            import numpy as np
            
            # Convert to DataFrame
            df = self._candles_to_df(candles)
            if df is None or len(df) < 20:
                return False
            
            # Calculate Bollinger Bands
            period = 20
            std_dev = 2.0
            
            close = df['close']
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            bb_upper = sma + (std * std_dev)
            bb_lower = sma - (std * std_dev)
            bb_width_pct = (bb_upper - bb_lower) / sma  # As decimal (0.02 = 2%)
            
            if len(bb_width_pct) < 5:
                return False
            
            # RECOMMENDED: Check absolute threshold first (BB width < 0.02 = 2%)
            recent_width_pct = bb_width_pct.iloc[-1]  # Most recent BB width
            if recent_width_pct < 0.02:  # 2% of price
                return True
            
            # Fallback: Check relative compression (recent < average)
            if len(bb_width_pct) >= 10:
                recent_avg = bb_width_pct.iloc[-5:].mean()
                avg_width = bb_width_pct.iloc[-20:].mean()
                
                if avg_width > 0:
                    compression_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('bb_compression_threshold', 0.9)
                    compression_ratio = recent_avg / avg_width
                    return compression_ratio < compression_threshold
            
            return False
        except Exception as e:
            logger.debug(f"Error checking BB compression: {e}")
            return False
    
    def _check_compression_block(self, candles: List[Dict], atr1: Optional[float] = None) -> bool:
        """Check for inside bars / tight structure (shared helper method)"""
        if len(candles) < 3:
            return False
        
        # Validate candle structure
        if not all(isinstance(c, dict) and 'high' in c and 'low' in c for c in candles):
            logger.warning("Invalid candle structure in compression check")
            return False
        
        # Check for inside bars (last 3 candles)
        inside_count = 0
        for i in range(max(1, len(candles) - 2), len(candles)):
            current = candles[i]
            previous = candles[i-1]
            
            current_high = current.get('high', 0)
            current_low = current.get('low', 0)
            previous_high = previous.get('high', 0)
            previous_low = previous.get('low', 0)
            
            # Inside bar: current high/low within previous high/low
            if current_high < previous_high and current_low > previous_low:
                inside_count += 1
        
        # Also check for tight range (small candle bodies)
        if len(candles) >= 5 and atr1:
            recent_candles = candles[-5:]
            avg_range = sum(c.get('high', 0) - c.get('low', 0) for c in recent_candles) / len(recent_candles)
            
            if atr1 > 0:
                # If average range is less than 0.5× ATR, consider it compressed
                if avg_range < atr1 * 0.5:
                    return True
        
        # Return True if at least 2 inside bars in last 3 candles
        return inside_count >= 2
    
    def _count_range_respects(self, candles: List[Dict], range_high: float, range_low: float) -> int:
        """Count how many times price bounced at range edges (shared helper method)"""
        if len(candles) < 10 or range_high <= range_low:
            return 0
        
        tolerance = (range_high - range_low) * 0.01  # 1% of range width
        respects = 0
        
        for i in range(1, len(candles)):
            prev_candle = candles[i-1]
            curr_candle = candles[i]
            
            prev_high = prev_candle.get('high', 0)
            prev_low = prev_candle.get('low', 0)
            curr_high = curr_candle.get('high', 0)
            curr_low = curr_candle.get('low', 0)
            
            # Check bounce at range high
            if abs(prev_high - range_high) <= tolerance:
                # Price touched high, then reversed down
                if curr_low < prev_low:
                    respects += 1
            
            # Check bounce at range low
            if abs(prev_low - range_low) <= tolerance:
                # Price touched low, then reversed up
                if curr_high > prev_high:
                    respects += 1
        
        return respects
    
    def _check_m15_trend(self, symbol: str, snapshot: Dict[str, Any]) -> str:
        """Check M15 trend - should be NEUTRAL for range detection (shared helper method)"""
        m15_candles = snapshot.get('m15_candles', [])
        
        if not m15_candles or len(m15_candles) < 20:
            return 'UNKNOWN'  # Cannot determine
        
        try:
            # Calculate simple trend from M15 candles
            recent_closes = [c.get('close', 0) for c in m15_candles[-20:]]
            
            if len(recent_closes) < 20 or any(c == 0 for c in recent_closes):
                return 'UNKNOWN'
            
            # Check if price is trending or ranging
            first_half = recent_closes[:10]
            second_half = recent_closes[10:]
            
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            
            if first_avg == 0 or second_avg == 0:
                return 'UNKNOWN'
            
            # Calculate trend strength
            trend_pct = abs(second_avg - first_avg) / first_avg if first_avg > 0 else 0
            
            # If trend is weak (< 0.2%), consider it neutral
            if trend_pct < 0.002:  # 0.2%
                return 'NEUTRAL'
            elif second_avg > first_avg:
                return 'BULLISH'
            else:
                return 'BEARISH'
        except Exception as e:
            logger.debug(f"Error checking M15 trend: {e}")
            return 'UNKNOWN'
    
    def _check_choppy_liquidity(self, candles: List[Dict]) -> bool:
        """Check for wicks but no displacement (choppy liquidity) (shared helper method)"""
        if len(candles) < 10:
            return False
        
        # Check last 5 candles for wicks without strong displacement
        wick_count = 0
        displacement_count = 0
        
        for candle in candles[-5:]:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            open_price = candle.get('open', 0)
            close = candle.get('close', 0)
            
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            total_range = high - low
            
            if total_range > 0:
                # Significant wick (wick > body)
                wick_ratio = (upper_wick + lower_wick) / total_range
                if wick_ratio > 0.5:  # More than 50% wick
                    wick_count += 1
                
                # Check for displacement (strong move)
                body_ratio = body / total_range
                if body_ratio > 0.7:  # Strong body (>70% of range)
                    displacement_count += 1
        
        # Choppy: wicks present but no strong displacement
        return wick_count >= 3 and displacement_count < 2
    
    def _candles_to_df(self, candles: List[Dict[str, Any]]) -> Optional[Any]:
        """Convert candle list to DataFrame with datetime index (shared helper method)"""
        if not candles:
            return None
        
        try:
            import pandas as pd
            
            # Extract data
            times = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for candle in candles:
                # Handle different time formats
                time_val = candle.get('time')
                if isinstance(time_val, (int, float)):
                    # Unix timestamp
                    times.append(pd.Timestamp.fromtimestamp(time_val, tz='UTC'))
                elif isinstance(time_val, str):
                    times.append(pd.Timestamp(time_val))
                elif hasattr(time_val, 'timestamp'):
                    times.append(pd.Timestamp.fromtimestamp(time_val.timestamp(), tz='UTC'))
                else:
                    times.append(pd.Timestamp.now(tz='UTC'))
                
                opens.append(candle.get('open', 0))
                highs.append(candle.get('high', 0))
                lows.append(candle.get('low', 0))
                closes.append(candle.get('close', 0))
                volumes.append(candle.get('volume', 0))
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=times)
            
            return df
        except Exception as e:
            logger.error(f"Error converting candles to DataFrame: {e}")
            return None
    
    def _detect_entry_type_from_candles(self, candles: List[Dict[str, Any]]) -> str:
        """
        Detect entry type (fade or breakout) from candle structure.
        
        Returns:
            'fade' if price is within compression block (inside bars)
            'breakout' if price has broken out of compression block
        """
        if len(candles) < 3:
            return 'fade'  # Default to fade if insufficient data
        
        # Get compression block boundaries (last 3 candles)
        compression_high = max(c.get('high', 0) for c in candles[-3:])
        compression_low = min(c.get('low', 0) for c in candles[-3:])
        last_close = candles[-1].get('close', 0)
        
        # Check if price has broken out
        if last_close > compression_high or last_close < compression_low:
            return 'breakout'
        else:
            return 'fade'

