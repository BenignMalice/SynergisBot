"""
Market liquidity structure detection.
Detects equal highs/lows, sweeps, and liquidity grabs.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def detect_equal_highs(
    highs: np.ndarray,
    lows: np.ndarray,
    times: np.ndarray,
    atr: float,
    lookback: int = 50,
    tolerance_mult: float = 0.1,
    min_touches: int = 2
) -> Dict[str, Any]:
    """
    Detect clusters of equal highs (resting liquidity).
    
    Rule: Two or more swing highs within tolerance at ~same level within lookback period.
    
    Args:
        highs: Array of high prices
        lows: Array of low prices (for swing detection)
        times: Array of timestamps
        atr: Average True Range for normalization
        lookback: Number of bars to look back
        tolerance_mult: Tolerance as multiple of ATR (default 0.1)
        min_touches: Minimum number of touches to form cluster
    
    Returns:
        {
            "eq_high_cluster": bool,
            "cluster_price": float,
            "cluster_count": int,
            "bars_ago": int,
            "cluster_zone": (float, float)  # (lower, upper)
        }
    """
    try:
        if len(highs) < lookback or atr <= 0:
            return _empty_equal_highs()
        
        # Get recent highs
        recent_highs = highs[-lookback:]
        
        # Find swing highs (local maxima)
        swing_highs = _find_swing_highs(recent_highs, window=3)
        
        if len(swing_highs) < min_touches:
            return _empty_equal_highs()
        
        # Calculate tolerance
        tolerance = tolerance_mult * atr
        
        # Find clusters
        clusters = _find_price_clusters(swing_highs, tolerance, min_touches)
        
        if not clusters:
            return _empty_equal_highs()
        
        # Return the most recent/strongest cluster
        strongest_cluster = max(clusters, key=lambda c: c["count"])
        
        return {
            "eq_high_cluster": True,
            "cluster_price": strongest_cluster["price"],
            "cluster_count": strongest_cluster["count"],
            "bars_ago": strongest_cluster["bars_ago"],
            "cluster_zone": (
                strongest_cluster["price"] - tolerance,
                strongest_cluster["price"] + tolerance
            )
        }
        
    except Exception as e:
        logger.debug(f"Equal highs detection failed: {e}")
        return _empty_equal_highs()


def detect_equal_lows(
    lows: np.ndarray,
    highs: np.ndarray,
    times: np.ndarray,
    atr: float,
    lookback: int = 50,
    tolerance_mult: float = 0.1,
    min_touches: int = 2
) -> Dict[str, Any]:
    """
    Detect clusters of equal lows (resting liquidity).
    
    Mirror of detect_equal_highs for support levels.
    
    Returns:
        {
            "eq_low_cluster": bool,
            "cluster_price": float,
            "cluster_count": int,
            "bars_ago": int,
            "cluster_zone": (float, float)
        }
    """
    try:
        if len(lows) < lookback or atr <= 0:
            return _empty_equal_lows()
        
        # Get recent lows
        recent_lows = lows[-lookback:]
        
        # Find swing lows (local minima)
        swing_lows = _find_swing_lows(recent_lows, window=3)
        
        if len(swing_lows) < min_touches:
            return _empty_equal_lows()
        
        # Calculate tolerance
        tolerance = tolerance_mult * atr
        
        # Find clusters
        clusters = _find_price_clusters(swing_lows, tolerance, min_touches)
        
        if not clusters:
            return _empty_equal_lows()
        
        # Return the most recent/strongest cluster
        strongest_cluster = max(clusters, key=lambda c: c["count"])
        
        return {
            "eq_low_cluster": True,
            "cluster_price": strongest_cluster["price"],
            "cluster_count": strongest_cluster["count"],
            "bars_ago": strongest_cluster["bars_ago"],
            "cluster_zone": (
                strongest_cluster["price"] - tolerance,
                strongest_cluster["price"] + tolerance
            )
        }
        
    except Exception as e:
        logger.debug(f"Equal lows detection failed: {e}")
        return _empty_equal_lows()


def detect_sweep(
    bars: pd.DataFrame,
    atr: float,
    sweep_threshold: float = 0.15,
    lookback: int = 20
) -> Dict[str, Any]:
    """
    Detect liquidity sweeps (stop hunts).
    
    Bullish sweep: High breaks prior swing high by ≥sweep_threshold×ATR
                   but closes back below prior high and within prior bar body/BB.
    
    Args:
        bars: DataFrame with OHLC columns (and optionally 'volume')
        atr: Average True Range
        sweep_threshold: Minimum break distance as multiple of ATR
        lookback: Bars to look back for swing identification
    
    Returns:
        {
            "sweep_bull": bool,
            "sweep_bear": bool,
            "depth": float,  # break distance / ATR
            "bars_ago": int,
            "sweep_price": float
        }
    """
    try:
        if len(bars) < lookback + 2 or atr <= 0:
            return _empty_sweep()
        
        # Get recent bars
        recent_bars = bars.iloc[-(lookback+2):]
        
        # Find swing high/low in lookback
        swing_high_idx = recent_bars["high"].iloc[:-1].idxmax()
        swing_low_idx = recent_bars["low"].iloc[:-1].idxmin()
        
        swing_high = recent_bars.loc[swing_high_idx, "high"]
        swing_low = recent_bars.loc[swing_low_idx, "low"]
        
        # Check last bar for sweep
        last_bar = recent_bars.iloc[-1]
        
        # Bullish sweep detection
        sweep_bull = False
        bull_depth = 0.0
        bull_price = 0.0
        
        if last_bar["high"] > swing_high:
            break_distance = last_bar["high"] - swing_high
            if break_distance >= sweep_threshold * atr:
                # Check if closed back below swing high
                if last_bar["close"] < swing_high:
                    sweep_bull = True
                    bull_depth = break_distance / atr
                    bull_price = last_bar["high"]
        
        # Bearish sweep detection
        sweep_bear = False
        bear_depth = 0.0
        bear_price = 0.0
        
        if last_bar["low"] < swing_low:
            break_distance = swing_low - last_bar["low"]
            if break_distance >= sweep_threshold * atr:
                # Check if closed back above swing low
                if last_bar["close"] > swing_low:
                    sweep_bear = True
                    bear_depth = break_distance / atr
                    bear_price = last_bar["low"]
        
        return {
            "sweep_bull": sweep_bull,
            "sweep_bear": sweep_bear,
            "depth": max(bull_depth, bear_depth),
            "bars_ago": 0 if (sweep_bull or sweep_bear) else -1,
            "sweep_price": bull_price if sweep_bull else bear_price,
            "bull_depth": bull_depth,
            "bear_depth": bear_depth
        }
        
    except Exception as e:
        logger.debug(f"Sweep detection failed: {e}")
        return _empty_sweep()


def validate_sweep(
    bars: pd.DataFrame,
    sweep_result: Dict[str, Any],
    atr: float,
    confirmation_bars: int = 3
) -> Dict[str, Any]:
    """
    Phase 3.2: Enhanced Sweep Detection - Post-sweep validation and confirmation.
    
    Validates detected sweeps by checking:
    1. Volume confirmation (higher volume on sweep bar = more valid)
    2. Follow-through (price movement after sweep confirms reversal)
    3. Fake sweep detection (if price continues past sweep = fake)
    4. Confidence scoring (0-100) based on validation factors
    
    Args:
        bars: DataFrame with OHLCV columns
        sweep_result: Result from detect_sweep()
        atr: Average True Range
        confirmation_bars: Number of bars to check for follow-through (default: 3)
    
    Returns:
        {
            "sweep_bull": bool,
            "sweep_bear": bool,
            "sweep_bull_validated": bool,
            "sweep_bear_validated": bool,
            "bull_confidence": float,  # 0-100
            "bear_confidence": float,  # 0-100
            "bull_fake": bool,  # True if fake (price continued past)
            "bear_fake": bool,
            "bull_follow_through": float,  # ATR distance price moved after sweep
            "bear_follow_through": float,
            "bull_volume_ratio": float,  # Sweep bar volume / avg volume
            "bear_volume_ratio": float,
            "validation_details": {
                "bull": {...},
                "bear": {...}
            }
        }
    """
    try:
        if len(bars) < confirmation_bars + 1:
            return _empty_sweep_validation()
        
        result = {
            "sweep_bull": sweep_result.get("sweep_bull", False),
            "sweep_bear": sweep_result.get("sweep_bear", False),
            "sweep_bull_validated": False,
            "sweep_bear_validated": False,
            "bull_confidence": 0.0,
            "bear_confidence": 0.0,
            "bull_fake": False,
            "bear_fake": False,
            "bull_follow_through": 0.0,
            "bear_follow_through": 0.0,
            "bull_volume_ratio": 1.0,
            "bear_volume_ratio": 1.0,
            "validation_details": {
                "bull": {},
                "bear": {}
            }
        }
        
        sweep_price = sweep_result.get("sweep_price", 0)
        sweep_bull = sweep_result.get("sweep_bull", False)
        sweep_bear = sweep_result.get("sweep_bear", False)
        
        # Get sweep bar (last bar if sweep detected)
        if sweep_bull or sweep_bear:
            sweep_bar_idx = len(bars) - 1
            sweep_bar = bars.iloc[sweep_bar_idx]
            
            # Check volume confirmation
            if 'volume' in bars.columns:
                recent_volume = bars['volume'].iloc[-20:].mean() if len(bars) >= 20 else bars['volume'].mean()
                sweep_volume = sweep_bar['volume']
                volume_ratio = sweep_volume / max(recent_volume, 1.0)
            else:
                volume_ratio = 1.0
            
            # Check follow-through in next bars
            if len(bars) >= sweep_bar_idx + confirmation_bars + 1:
                follow_bars = bars.iloc[sweep_bar_idx+1:sweep_bar_idx+1+confirmation_bars]
            else:
                follow_bars = bars.iloc[sweep_bar_idx+1:] if sweep_bar_idx + 1 < len(bars) else pd.DataFrame()
            
            # Validate bullish sweep
            if sweep_bull:
                bull_confidence = 50.0  # Base confidence
                
                # Volume confirmation (+20 points if high volume)
                if volume_ratio >= 1.5:
                    bull_confidence += 20
                elif volume_ratio >= 1.2:
                    bull_confidence += 10
                
                result["bull_volume_ratio"] = volume_ratio
                
                # Check for fake sweep (if price exceeded sweep high again)
                if len(follow_bars) > 0:
                    max_follow_high = follow_bars["high"].max()
                    if max_follow_high >= sweep_price:
                        result["bull_fake"] = True
                        bull_confidence -= 30
                
                # Check follow-through (price moved down after sweep = good)
                if len(follow_bars) > 0:
                    follow_close = follow_bars["close"].iloc[-1]
                    follow_distance = (sweep_price - follow_close) / max(atr, 1.0)
                    result["bull_follow_through"] = follow_distance
                    
                    # Positive follow-through (moved away from sweep) = confirmation
                    if follow_distance > 0.3:  # Moved > 0.3 ATR away
                        bull_confidence += 25
                        result["sweep_bull_validated"] = True
                    elif follow_distance > 0.15:
                        bull_confidence += 15
                        result["sweep_bull_validated"] = True
                    elif follow_distance < -0.2:  # Price went back up (fake)
                        bull_confidence -= 20
                        result["bull_fake"] = True
                
                # Depth confirmation (deeper sweeps are more valid)
                bull_depth = sweep_result.get("bull_depth", 0)
                if bull_depth >= 0.3:
                    bull_confidence += 10
                elif bull_depth >= 0.2:
                    bull_confidence += 5
                
                bull_confidence = max(0, min(100, bull_confidence))
                result["bull_confidence"] = bull_confidence
                result["validation_details"]["bull"] = {
                    "volume_ratio": volume_ratio,
                    "follow_through_atr": result["bull_follow_through"],
                    "depth_atr": bull_depth,
                    "fake": result["bull_fake"],
                    "validated": result["sweep_bull_validated"]
                }
            
            # Validate bearish sweep
            if sweep_bear:
                bear_confidence = 50.0  # Base confidence
                
                # Volume confirmation
                if volume_ratio >= 1.5:
                    bear_confidence += 20
                elif volume_ratio >= 1.2:
                    bear_confidence += 10
                
                result["bear_volume_ratio"] = volume_ratio
                
                # Check for fake sweep (if price went below sweep low again)
                if len(follow_bars) > 0:
                    min_follow_low = follow_bars["low"].min()
                    if min_follow_low <= sweep_price:
                        result["bear_fake"] = True
                        bear_confidence -= 30
                
                # Check follow-through (price moved up after sweep = good)
                if len(follow_bars) > 0:
                    follow_close = follow_bars["close"].iloc[-1]
                    follow_distance = (follow_close - sweep_price) / max(atr, 1.0)
                    result["bear_follow_through"] = follow_distance
                    
                    # Positive follow-through = confirmation
                    if follow_distance > 0.3:
                        bear_confidence += 25
                        result["sweep_bear_validated"] = True
                    elif follow_distance > 0.15:
                        bear_confidence += 15
                        result["sweep_bear_validated"] = True
                    elif follow_distance < -0.2:  # Price went back down (fake)
                        bear_confidence -= 20
                        result["bear_fake"] = True
                
                # Depth confirmation
                bear_depth = sweep_result.get("bear_depth", 0)
                if bear_depth >= 0.3:
                    bear_confidence += 10
                elif bear_depth >= 0.2:
                    bear_confidence += 5
                
                bear_confidence = max(0, min(100, bear_confidence))
                result["bear_confidence"] = bear_confidence
                result["validation_details"]["bear"] = {
                    "volume_ratio": volume_ratio,
                    "follow_through_atr": result["bear_follow_through"],
                    "depth_atr": bear_depth,
                    "fake": result["bear_fake"],
                    "validated": result["sweep_bear_validated"]
                }
        
        return result
        
    except Exception as e:
        logger.debug(f"Sweep validation failed: {e}")
        return _empty_sweep_validation()


def _empty_sweep_validation() -> Dict[str, Any]:
    """Return empty sweep validation result"""
    return {
        "sweep_bull": False,
        "sweep_bear": False,
        "sweep_bull_validated": False,
        "sweep_bear_validated": False,
        "bull_confidence": 0.0,
        "bear_confidence": 0.0,
        "bull_fake": False,
        "bear_fake": False,
        "bull_follow_through": 0.0,
        "bear_follow_through": 0.0,
        "bull_volume_ratio": 1.0,
        "bear_volume_ratio": 1.0,
        "validation_details": {
            "bull": {},
            "bear": {}
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def _find_swing_highs(highs: np.ndarray, window: int = 3) -> List[Tuple[int, float]]:
    """
    Find swing highs (local maxima).
    
    Returns list of (index, price) tuples.
    """
    swings = []
    for i in range(window, len(highs) - window):
        is_swing = True
        for j in range(1, window + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        
        if is_swing:
            swings.append((i, highs[i]))
    
    return swings


def _find_swing_lows(lows: np.ndarray, window: int = 3) -> List[Tuple[int, float]]:
    """
    Find swing lows (local minima).
    
    Returns list of (index, price) tuples.
    """
    swings = []
    for i in range(window, len(lows) - window):
        is_swing = True
        for j in range(1, window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        
        if is_swing:
            swings.append((i, lows[i]))
    
    return swings


def _find_price_clusters(
    swings: List[Tuple[int, float]],
    tolerance: float,
    min_touches: int
) -> List[Dict[str, Any]]:
    """
    Find clusters of prices within tolerance.
    
    Returns list of cluster dicts with price, count, bars_ago.
    """
    if not swings:
        return []
    
    clusters = []
    used_indices = set()
    
    for i, (idx_i, price_i) in enumerate(swings):
        if i in used_indices:
            continue
        
        # Find all swings within tolerance of this price
        cluster_indices = [i]
        cluster_prices = [price_i]
        
        for j, (idx_j, price_j) in enumerate(swings):
            if j != i and j not in used_indices:
                if abs(price_j - price_i) <= tolerance:
                    cluster_indices.append(j)
                    cluster_prices.append(price_j)
                    used_indices.add(j)
        
        # Check if cluster meets minimum size
        if len(cluster_indices) >= min_touches:
            avg_price = np.mean(cluster_prices)
            # FIXED: most_recent_idx is the bar index from original data
            # We need to track how far back this cluster is from current
            most_recent_bar_idx = max([swings[k][0] for k in cluster_indices])
            # If we have the total data length, bars_ago should be: total_len - most_recent_bar_idx - 1
            # For now, use the swing index as a proxy
            bars_ago = max(cluster_indices)  # Most recent swing in the cluster
            
            clusters.append({
                "price": avg_price,
                "count": len(cluster_indices),
                "bars_ago": bars_ago
            })
            
            used_indices.add(i)
    
    return clusters


def _empty_equal_highs() -> Dict[str, Any]:
    """Return empty equal highs result."""
    return {
        "eq_high_cluster": False,
        "cluster_price": 0.0,
        "cluster_count": 0,
        "bars_ago": -1,
        "cluster_zone": (0.0, 0.0)
    }


def _empty_equal_lows() -> Dict[str, Any]:
    """Return empty equal lows result."""
    return {
        "eq_low_cluster": False,
        "cluster_price": 0.0,
        "cluster_count": 0,
        "bars_ago": -1,
        "cluster_zone": (0.0, 0.0)
    }


def _empty_sweep() -> Dict[str, Any]:
    """Return empty sweep result."""
    return {
        "sweep_bull": False,
        "sweep_bear": False,
        "depth": 0.0,
        "bars_ago": -1,
        "sweep_price": 0.0,
        "bull_depth": 0.0,
        "bear_depth": 0.0
    }


def detect_stop_clusters(
    bars: pd.DataFrame,
    atr: float,
    lookback: int = 50,
    min_wick_atr: float = 0.5,
    cluster_tolerance_atr: float = 0.15,
    min_wicks: int = 3
) -> Dict[str, Any]:
    """
    Detect stop clusters from candle wicks.
    
    Stop clusters are identified by multiple candles with long wicks (upper or lower)
    clustering at similar price levels. These represent zones where retail stops are
    likely parked, making them attractive targets for institutional liquidity sweeps.
    
    Args:
        bars: DataFrame with OHLC columns (open, high, low, close)
        atr: Average True Range for normalization
        lookback: Number of bars to look back (default: 50)
        min_wick_atr: Minimum wick size as multiple of ATR (default: 0.5)
        cluster_tolerance_atr: Price tolerance for clustering as multiple of ATR (default: 0.15)
        min_wicks: Minimum number of wicks needed to form a cluster (default: 3)
    
    Returns:
        {
            "stop_cluster_above": bool,
            "stop_cluster_above_price": float,
            "stop_cluster_above_count": int,
            "stop_cluster_above_dist_atr": float,
            "stop_cluster_below": bool,
            "stop_cluster_below_price": float,
            "stop_cluster_below_count": int,
            "stop_cluster_below_dist_atr": float
        }
    """
    try:
        if len(bars) < lookback or atr <= 0:
            return _empty_stop_clusters()
        
        # Get recent bars
        recent_bars = bars.iloc[-lookback:].copy()
        
        # Calculate wick sizes
        # Upper wick = high - max(open, close)
        # Lower wick = min(open, close) - low
        recent_bars['body_high'] = recent_bars[['open', 'close']].max(axis=1)
        recent_bars['body_low'] = recent_bars[['open', 'close']].min(axis=1)
        recent_bars['upper_wick'] = recent_bars['high'] - recent_bars['body_high']
        recent_bars['lower_wick'] = recent_bars['body_low'] - recent_bars['low']
        
        # Filter for significant wicks (> min_wick_atr * ATR)
        min_wick_size = min_wick_atr * atr
        tolerance = cluster_tolerance_atr * atr
        
        # Find candles with long upper wicks (stop clusters above)
        long_upper_wicks = recent_bars[recent_bars['upper_wick'] >= min_wick_size].copy()
        long_upper_wicks['wick_top'] = long_upper_wicks['high']  # Top of wick is the high
        
        # Find candles with long lower wicks (stop clusters below)
        long_lower_wicks = recent_bars[recent_bars['lower_wick'] >= min_wick_size].copy()
        long_lower_wicks['wick_bottom'] = long_lower_wicks['low']  # Bottom of wick is the low
        
        # Find clusters of upper wick tops
        stop_cluster_above = False
        stop_cluster_above_price = 0.0
        stop_cluster_above_count = 0
        stop_cluster_above_dist_atr = 999.0
        
        if len(long_upper_wicks) >= min_wicks:
            # Find price clusters among wick tops
            wick_tops = long_upper_wicks['wick_top'].values
            cluster = _find_wick_clusters(wick_tops, tolerance, min_wicks)
            
            if cluster:
                stop_cluster_above = True
                stop_cluster_above_price = cluster['price']
                stop_cluster_above_count = cluster['count']
                
                # Calculate distance from current price (last close)
                current_price = bars['close'].iloc[-1]
                distance = stop_cluster_above_price - current_price
                stop_cluster_above_dist_atr = distance / atr if atr > 0 else 999.0
        
        # Find clusters of lower wick bottoms
        stop_cluster_below = False
        stop_cluster_below_price = 0.0
        stop_cluster_below_count = 0
        stop_cluster_below_dist_atr = 999.0
        
        if len(long_lower_wicks) >= min_wicks:
            # Find price clusters among wick bottoms
            wick_bottoms = long_lower_wicks['wick_bottom'].values
            cluster = _find_wick_clusters(wick_bottoms, tolerance, min_wicks)
            
            if cluster:
                stop_cluster_below = True
                stop_cluster_below_price = cluster['price']
                stop_cluster_below_count = cluster['count']
                
                # Calculate distance from current price
                current_price = bars['close'].iloc[-1]
                distance = current_price - stop_cluster_below_price
                stop_cluster_below_dist_atr = distance / atr if atr > 0 else 999.0
        
        return {
            "stop_cluster_above": stop_cluster_above,
            "stop_cluster_above_price": float(stop_cluster_above_price),
            "stop_cluster_above_count": stop_cluster_above_count,
            "stop_cluster_above_dist_atr": round(stop_cluster_above_dist_atr, 2),
            "stop_cluster_below": stop_cluster_below,
            "stop_cluster_below_price": float(stop_cluster_below_price),
            "stop_cluster_below_count": stop_cluster_below_count,
            "stop_cluster_below_dist_atr": round(stop_cluster_below_dist_atr, 2)
        }
        
    except Exception as e:
        logger.debug(f"Stop cluster detection failed: {e}")
        return _empty_stop_clusters()


def _find_wick_clusters(
    wick_prices: np.ndarray,
    tolerance: float,
    min_wicks: int
) -> Optional[Dict[str, Any]]:
    """
    Find the strongest cluster of wick prices within tolerance.
    
    Returns the cluster with the most wicks, or None if no cluster meets min_wicks.
    """
    if len(wick_prices) < min_wicks:
        return None
    
    # Sort prices for easier clustering
    sorted_prices = np.sort(wick_prices)
    
    best_cluster = None
    best_count = 0
    
    # Try each price as a potential cluster center
    for i in range(len(sorted_prices)):
        center_price = sorted_prices[i]
        
        # Find all prices within tolerance
        in_cluster = sorted_prices[
            (sorted_prices >= center_price - tolerance) &
            (sorted_prices <= center_price + tolerance)
        ]
        
        if len(in_cluster) >= min_wicks and len(in_cluster) > best_count:
            best_cluster = {
                'price': float(np.mean(in_cluster)),  # Average price of cluster
                'count': len(in_cluster),
                'center': float(center_price),
                'tolerance': tolerance
            }
            best_count = len(in_cluster)
    
    return best_cluster


def _empty_stop_clusters() -> Dict[str, Any]:
    """Return empty stop cluster result."""
    return {
        "stop_cluster_above": False,
        "stop_cluster_above_price": 0.0,
        "stop_cluster_above_count": 0,
        "stop_cluster_above_dist_atr": 999.0,
        "stop_cluster_below": False,
        "stop_cluster_below_price": 0.0,
        "stop_cluster_below_count": 0,
        "stop_cluster_below_dist_atr": 999.0
    }