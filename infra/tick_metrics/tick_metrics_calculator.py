"""
Tick Metrics Calculator

Computes all derived microstructure metrics from raw MT5 tick data.
Uses MT5 tick flag constants (TICK_FLAG_BUY, TICK_FLAG_SELL) for delta/CVD calculations.
"""
import logging
import math
import MetaTrader5 as mt5
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)


class TickMetricsCalculator:
    """Calculates microstructure metrics from raw tick data."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize calculator with optional configuration.
        
        Args:
            config: Optional config dict with thresholds
        """
        self.config = config or {}
        self.thresholds = self.config.get("thresholds", {})
        
        # Default thresholds
        self.absorption_volume_multiplier = self.thresholds.get("absorption_volume_multiplier", 2.0)
        self.absorption_price_tolerance_pct = self.thresholds.get("absorption_price_tolerance_pct", 0.05)
        self.void_spread_multiplier = self.thresholds.get("liquidity_void_spread_multiplier", 2.0)
        self.cvd_slope_threshold = self.thresholds.get("cvd_slope_threshold", 0.1)
    
    def calculate_all_metrics(
        self,
        ticks: List[Dict[str, Any]],
        timeframe: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Master function: Calculate all metrics from tick data.
        
        Args:
            ticks: List of tick dictionaries
            timeframe: Optional timeframe label (M5, M15, H1) for organization
        
        Returns:
            Dictionary with all calculated metrics
        """
        if not ticks or len(ticks) == 0:
            return self._empty_metrics()
        
        # Core metrics
        delta_cvd = self._calculate_delta_cvd(ticks)
        spread_stats = self._calculate_spread_stats(ticks)
        volatility = self._calculate_realized_volatility(ticks)
        absorption = self._detect_absorption_zones(ticks)
        liquidity_voids = self._detect_liquidity_voids(ticks)
        activity = self._calculate_tick_activity(ticks)
        
        # Build result
        result = {
            "realized_volatility": volatility.get("realized_vol", 0.0),
            "volatility_ratio": volatility.get("vol_ratio", 1.0),
            "delta_volume": delta_cvd.get("delta_volume", 0.0),
            "cvd": delta_cvd.get("cvd", 0.0),
            "cvd_slope": delta_cvd.get("cvd_slope", "flat"),
            "dominant_side": delta_cvd.get("dominant_side", "NEUTRAL"),
            "spread": spread_stats,
            "absorption": absorption,
            "liquidity_voids": liquidity_voids,
            "tick_rate": activity.get("tick_rate", 0.0),
            "tick_count": len(ticks),
            "max_gap_ms": activity.get("max_gap_ms", 0),
            "trade_tick_ratio": delta_cvd.get("trade_tick_ratio", 0.0)
        }
        
        return result
    
    def _calculate_delta_cvd(self, ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate delta volume and CVD from tick data.
        
        IMPORTANT: Only ticks with TICK_FLAG_BUY or TICK_FLAG_SELL contribute to delta.
        Quote-only ticks (BID/ASK changes without trades) are correctly excluded.
        Low trade_count relative to total ticks indicates less reliable delta signal.
        
        Args:
            ticks: List of tick dictionaries
        
        Returns:
            Dictionary with delta_volume, cvd, cvd_slope, dominant_side, trade_tick_ratio
        """
        buy_volume = 0.0
        sell_volume = 0.0
        trade_tick_count = 0
        total_tick_count = len(ticks)
        
        cvd_series = []  # For slope calculation
        cumulative_delta = 0.0
        
        for tick in ticks:
            flags = tick.get('flags', 0)
            
            # Prefer volume_real (fractional precision) over volume (integer)
            volume = tick.get('volume_real') or tick.get('volume', 0)
            
            # Only count ticks with BUY or SELL flags (trade ticks)
            if flags & mt5.TICK_FLAG_BUY:
                buy_volume += volume
                cumulative_delta += volume
                trade_tick_count += 1
            elif flags & mt5.TICK_FLAG_SELL:
                sell_volume += volume
                cumulative_delta -= volume
                trade_tick_count += 1
            
            # Track CVD series for slope calculation (sample every 100 ticks to avoid memory)
            if len(cvd_series) == 0 or len(ticks) - len(cvd_series) * 100 >= 100:
                cvd_series.append(cumulative_delta)
        
        delta_volume = buy_volume - sell_volume
        
        # Calculate dominant side
        if abs(delta_volume) < 1e-10:
            dominant_side = "NEUTRAL"
        elif delta_volume > 0:
            dominant_side = "BUY"
        else:
            dominant_side = "SELL"
        
        # Calculate CVD slope
        cvd_slope = self._calculate_cvd_slope(cvd_series, self.cvd_slope_threshold)
        
        # Calculate trade tick ratio (data quality metric)
        trade_tick_ratio = trade_tick_count / total_tick_count if total_tick_count > 0 else 0.0
        
        return {
            "delta_volume": delta_volume,
            "cvd": cumulative_delta,
            "cvd_slope": cvd_slope,
            "dominant_side": dominant_side,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "trade_tick_ratio": trade_tick_ratio
        }
    
    def _calculate_cvd_slope(
        self,
        cvd_values: List[float],
        threshold: float = 0.1
    ) -> str:
        """
        Calculate CVD slope direction using percentage change.
        
        Args:
            cvd_values: List of cumulative delta values (chronological)
            threshold: Change percentage to consider non-flat (default 10%)
        
        Returns:
            "up", "down", or "flat"
        """
        if len(cvd_values) < 2:
            return "flat"
        
        # Use first and last values for overall direction
        first_val = cvd_values[0]
        last_val = cvd_values[-1]
        
        # Handle division by zero
        if abs(first_val) < 1e-10:
            if last_val > 0:
                return "up"
            elif last_val < 0:
                return "down"
            return "flat"
        
        # Calculate percentage change
        pct_change = (last_val - first_val) / abs(first_val)
        
        if pct_change > threshold:
            return "up"
        elif pct_change < -threshold:
            return "down"
        return "flat"
    
    def _calculate_spread_stats(self, ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate spread statistics, handling missing bid/ask values.
        
        Args:
            ticks: List of tick dictionaries
        
        Returns:
            Dictionary with mean, std, max, widening_events
        """
        spreads = []
        
        for tick in ticks:
            bid = tick.get('bid', 0)
            ask = tick.get('ask', 0)
            
            # Only include valid spreads (both bid and ask present and positive)
            if bid > 0 and ask > 0 and ask > bid:
                spreads.append(ask - bid)
        
        if not spreads:
            return {"mean": 0, "std": 0, "max": 0, "widening_events": 0}
        
        mean_spread = sum(spreads) / len(spreads)
        
        # Calculate standard deviation
        if len(spreads) > 1:
            variance = sum((s - mean_spread) ** 2 for s in spreads) / (len(spreads) - 1)
            std_spread = math.sqrt(variance)
        else:
            std_spread = 0.0
        
        max_spread = max(spreads)
        
        # Count widening events (spread > 2x mean)
        widening_threshold = mean_spread * self.void_spread_multiplier
        widening_events = sum(1 for s in spreads if s > widening_threshold)
        
        return {
            "mean": mean_spread,
            "std": std_spread,
            "max": max_spread,
            "widening_events": widening_events
        }
    
    def _calculate_realized_volatility(
        self,
        ticks: List[Dict[str, Any]],
        window_minutes: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Calculate realized volatility from log returns.
        
        Args:
            ticks: List of tick dictionaries
            window_minutes: Optional window size (if None, uses all ticks)
        
        Returns:
            Dictionary with realized_vol and vol_ratio
        """
        if len(ticks) < 2:
            return {"realized_vol": 0.0, "vol_ratio": 1.0}
        
        # Extract prices (use 'last' if available, fallback to 'bid')
        prices = []
        for tick in ticks:
            price = tick.get('last') or tick.get('bid', 0)
            if price > 0:
                prices.append(price)
        
        if len(prices) < 2:
            return {"realized_vol": 0.0, "vol_ratio": 1.0}
        
        # Calculate log returns
        log_returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                log_return = math.log(prices[i] / prices[i-1])
                log_returns.append(log_return)
        
        if len(log_returns) < 2:
            return {"realized_vol": 0.0, "vol_ratio": 1.0}
        
        # Calculate standard deviation of log returns
        mean_return = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
        realized_vol = math.sqrt(variance)
        
        # Volatility ratio (vs baseline) - will be calculated by generator using previous_day
        return {
            "realized_vol": realized_vol,
            "vol_ratio": 1.0  # Default, will be updated by generator
        }
    
    def _detect_absorption_zones(
        self,
        ticks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect absorption zones where high volume meets price stall.
        
        Algorithm:
        1. Group ticks into 1-minute bins
        2. For each bin, check: volume > multiplier x mean AND price_change < tolerance%
        3. If both conditions met, record as absorption zone
        
        Args:
            ticks: List of tick dictionaries
        
        Returns:
            Dictionary with count, zones (list of prices), avg_strength
        """
        if len(ticks) < 60:  # Need at least 1 minute of data
            return {'count': 0, 'zones': [], 'avg_strength': 0.0}
        
        # Calculate mean volume per second
        total_volume = sum(tick.get('volume_real') or tick.get('volume', 0) for tick in ticks)
        if total_volume == 0:
            return {'count': 0, 'zones': [], 'avg_strength': 0.0}
        
        time_span_ms = ticks[-1].get('time_msc', 0) - ticks[0].get('time_msc', 0)
        if time_span_ms <= 0:
            return {'count': 0, 'zones': [], 'avg_strength': 0.0}
        
        mean_vol_per_sec = total_volume / (time_span_ms / 1000.0)
        
        # Group into 1-minute bins
        bins = {}
        for tick in ticks:
            time_msc = tick.get('time_msc', 0)
            minute = time_msc // 60000  # Convert to minutes
            
            if minute not in bins:
                bins[minute] = []
            bins[minute].append(tick)
        
        zones = []
        for minute, group in bins.items():
            if len(group) < 2:
                continue
            
            # Calculate volume and price stats for this bin
            vol_sum = sum(tick.get('volume_real') or tick.get('volume', 0) for tick in group)
            prices = [tick.get('last') or tick.get('bid', 0) for tick in group if tick.get('last') or tick.get('bid', 0) > 0]
            
            if len(prices) < 2:
                continue
            
            price_min = min(prices)
            price_max = max(prices)
            avg_price = sum(prices) / len(prices)
            
            if avg_price <= 0:
                continue
            
            price_range = price_max - price_min
            price_change_pct = (price_range / avg_price) * 100
            
            # Check conditions: high volume AND price stall
            vol_threshold = mean_vol_per_sec * 60 * self.absorption_volume_multiplier
            
            if vol_sum > vol_threshold and price_change_pct < self.absorption_price_tolerance_pct:
                strength = min(1.0, vol_sum / vol_threshold)
                zones.append({
                    'price': round(avg_price, 2),
                    'strength': strength
                })
        
        # Sort by strength and take top 10
        zones.sort(key=lambda x: x['strength'], reverse=True)
        top_zones = zones[:10]
        
        return {
            'count': len(zones),
            'zones': [z['price'] for z in top_zones],
            'avg_strength': sum(z['strength'] for z in zones) / len(zones) if zones else 0.0
        }
    
    def _detect_liquidity_voids(self, ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect liquidity voids (spread jumps > threshold x mean).
        
        Args:
            ticks: List of tick dictionaries
        
        Returns:
            Dictionary with count and avg_void_size
        """
        spreads = []
        for tick in ticks:
            bid = tick.get('bid', 0)
            ask = tick.get('ask', 0)
            if bid > 0 and ask > bid:
                spreads.append(ask - bid)
        
        if not spreads:
            return {'count': 0, 'avg_void_size': 0.0}
        
        mean_spread = sum(spreads) / len(spreads)
        void_threshold = mean_spread * self.void_spread_multiplier
        
        voids = [s for s in spreads if s > void_threshold]
        
        return {
            'count': len(voids),
            'avg_void_size': sum(voids) / len(voids) if voids else 0.0
        }
    
    def _calculate_tick_activity(self, ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate tick frequency and gap metrics.
        
        Args:
            ticks: List of tick dictionaries
        
        Returns:
            Dictionary with tick_rate (ticks per second) and max_gap_ms
        """
        if len(ticks) < 2:
            return {'tick_rate': 0.0, 'max_gap_ms': 0}
        
        # Calculate time span
        first_time = ticks[0].get('time_msc', 0)
        last_time = ticks[-1].get('time_msc', 0)
        time_span_ms = last_time - first_time
        
        if time_span_ms <= 0:
            return {'tick_rate': 0.0, 'max_gap_ms': 0}
        
        tick_rate = len(ticks) / (time_span_ms / 1000.0)
        
        # Calculate max gap between consecutive ticks
        max_gap = 0
        for i in range(1, len(ticks)):
            gap = ticks[i].get('time_msc', 0) - ticks[i-1].get('time_msc', 0)
            if gap > max_gap:
                max_gap = gap
        
        return {
            'tick_rate': tick_rate,
            'max_gap_ms': max_gap
        }
    
    def _aggregate_by_timeframe(
        self,
        ticks: List[Dict[str, Any]],
        tf_minutes: int
    ) -> List[List[Dict[str, Any]]]:
        """
        Group ticks into timeframe bins (e.g., M5 = 5-minute bins).
        
        Args:
            ticks: List of tick dictionaries
            tf_minutes: Timeframe in minutes (5, 15, 60)
        
        Returns:
            List of tick lists, one per bin
        """
        if not ticks:
            return []
        
        bins = {}
        for tick in ticks:
            time_msc = tick.get('time_msc', 0)
            # Convert to minutes and bin
            minute = (time_msc // 60000) // tf_minutes
            
            if minute not in bins:
                bins[minute] = []
            bins[minute].append(tick)
        
        # Return bins in chronological order
        sorted_bins = sorted(bins.items())
        return [bins[bin_id] for bin_id, _ in sorted_bins]
    
    def _calculate_volatility_ratio(
        self,
        current_volatility: float,
        previous_day_volatility: Optional[float],
        default_baseline: float = 1.0
    ) -> float:
        """
        Calculate volatility ratio (current vs previous day baseline).
        
        Baseline Priority:
        1. Primary: Previous day's realized volatility from cache
        2. Fallback: Return default_baseline (neutral - treat as "normal" volatility)
        
        Args:
            current_volatility: Realized volatility for current timeframe
            previous_day_volatility: Previous day's realized volatility (may be None)
            default_baseline: Ratio to return if no baseline available
        
        Returns:
            Ratio (>1.2 = expanding, <0.8 = contracting, ~1.0 = stable)
        """
        if not previous_day_volatility or previous_day_volatility < 1e-10:
            return default_baseline  # No baseline, assume neutral
        
        return current_volatility / previous_day_volatility
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "realized_volatility": 0.0,
            "volatility_ratio": 1.0,
            "delta_volume": 0.0,
            "cvd": 0.0,
            "cvd_slope": "flat",
            "dominant_side": "NEUTRAL",
            "spread": {"mean": 0, "std": 0, "max": 0, "widening_events": 0},
            "absorption": {"count": 0, "zones": [], "avg_strength": 0.0},
            "liquidity_voids": {"count": 0, "avg_void_size": 0.0},
            "tick_rate": 0.0,
            "tick_count": 0,
            "max_gap_ms": 0,
            "trade_tick_ratio": 0.0
        }

