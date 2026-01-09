"""
Rolling Volume Footprint - Cumulative volume profile over time window.

Tracks volume accumulation at each price level over a rolling time period,
providing insight into where liquidity accumulates and potential support/resistance zones.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def calculate_rolling_volume_footprint(
    df: pd.DataFrame,
    window_bars: int = 100,
    price_precision: int = 4,
    min_volume_threshold: float = 0.01
) -> Dict[str, Any]:
    """
    Calculate rolling volume footprint over a time window.
    
    The volume footprint shows cumulative volume traded at each price level,
    helping identify:
    - High volume nodes (HVN) - support/resistance zones
    - Low volume nodes (LVN) - vacuum zones (quick moves)
    - Volume profile shape - distribution of liquidity
    
    Args:
        df: DataFrame with columns: ['time', 'open', 'high', 'low', 'close', 'volume']
        window_bars: Number of bars to include in rolling window (default: 100)
        price_precision: Decimal places for price binning (default: 4)
        min_volume_threshold: Minimum volume ratio to include in footprint (default: 0.01 = 1%)
    
    Returns:
        {
            "footprint_active": bool,
            "window_bars": int,
            "total_volume": float,
            "price_levels": List[Dict],  # [{"price": float, "volume": float, "volume_pct": float}]
            "hvn_zones": List[Dict],  # High volume nodes (top 20% by volume)
            "lvn_zones": List[Dict],  # Low volume nodes (bottom 20% by volume)
            "poc": float,  # Point of Control (price with highest volume)
            "value_area_high": float,  # 70% value area upper bound
            "value_area_low": float,  # 70% value area lower bound
            "current_price_volume_rank": int,  # Rank of current price in volume distribution (1-100)
            "current_price_volume_pct": float,  # Volume % at current price level
        }
    """
    try:
        if len(df) < window_bars:
            return _empty_footprint(window_bars)
        
        # Get rolling window data
        recent = df.iloc[-window_bars:].copy()
        
        if recent['volume'].sum() == 0:
            return _empty_footprint(window_bars)
        
        total_volume = recent['volume'].sum()
        
        # Create price bins with specified precision
        price_min = recent['low'].min()
        price_max = recent['high'].max()
        price_range = price_max - price_min
        
        if price_range == 0:
            return _empty_footprint(window_bars)
        
        # Create price levels (bins) - use round() for precision
        price_levels_dict = defaultdict(float)
        
        # Distribute volume across price levels for each bar
        # Using tick-by-price calculation (approximate)
        for idx, row in recent.iterrows():
            bar_volume = float(row['volume'])
            if bar_volume == 0:
                continue
            
            # Price range of the bar
            bar_low = row['low']
            bar_high = row['high']
            
            # Round to price precision
            bar_low_rounded = round(bar_low, price_precision)
            bar_high_rounded = round(bar_high, price_precision)
            
            # Create price levels within the bar's range
            # Use smaller step for better resolution
            step = 10 ** (-price_precision)  # e.g., 0.0001 for 4 decimal places
            
            if bar_high_rounded == bar_low_rounded:
                # Single price level
                price_level = bar_low_rounded
                price_levels_dict[price_level] += bar_volume
            else:
                # Distribute volume across price levels in the bar
                # Simple distribution: equal volume to each price level touched
                num_levels_in_bar = int((bar_high_rounded - bar_low_rounded) / step) + 1
                volume_per_level = bar_volume / num_levels_in_bar if num_levels_in_bar > 0 else bar_volume
                
                current_price = bar_low_rounded
                while current_price <= bar_high_rounded:
                    price_level = round(current_price, price_precision)
                    price_levels_dict[price_level] += volume_per_level
                    current_price += step
        
        # Convert to sorted list
        price_levels = []
        for price, volume in sorted(price_levels_dict.items()):
            volume_pct = (volume / total_volume) * 100 if total_volume > 0 else 0
            price_levels.append({
                "price": float(price),
                "volume": float(volume),
                "volume_pct": round(volume_pct, 2)
            })
        
        if not price_levels:
            return _empty_footprint(window_bars)
        
        # Find POC (Point of Control) - price with highest volume
        poc_entry = max(price_levels, key=lambda x: x['volume'])
        poc = poc_entry['price']
        
        # Calculate value area (70% of volume)
        # Sort by volume descending
        sorted_by_volume = sorted(price_levels, key=lambda x: x['volume'], reverse=True)
        cumulative_volume = 0
        value_area_levels = []
        target_volume = total_volume * 0.70  # 70% value area
        
        for level in sorted_by_volume:
            cumulative_volume += level['volume']
            value_area_levels.append(level)
            if cumulative_volume >= target_volume:
                break
        
        if value_area_levels:
            value_area_high = max(level['price'] for level in value_area_levels)
            value_area_low = min(level['price'] for level in value_area_levels)
        else:
            value_area_high = price_max
            value_area_low = price_min
        
        # Identify HVN zones (top 20% by volume)
        volume_threshold_high = total_volume * (min_volume_threshold * 20)  # Top 20%
        hvn_zones = [
            level for level in price_levels
            if level['volume'] >= volume_threshold_high
        ]
        hvn_zones = sorted(hvn_zones, key=lambda x: x['volume'], reverse=True)[:10]  # Top 10
        
        # Identify LVN zones (bottom 20% by volume, excluding zero)
        volume_threshold_low = total_volume * min_volume_threshold  # Bottom threshold
        non_zero_levels = [level for level in price_levels if level['volume'] > 0]
        if non_zero_levels:
            sorted_lvn = sorted(non_zero_levels, key=lambda x: x['volume'])
            lvn_zones = [
                level for level in sorted_lvn[:len(non_zero_levels) // 5]  # Bottom 20%
                if level['volume'] <= volume_threshold_low
            ][:10]  # Top 10 lowest
        else:
            lvn_zones = []
        
        # Get current price volume rank
        current_price = float(recent.iloc[-1]['close'])
        current_price_rounded = round(current_price, price_precision)
        
        # Find volume at current price
        current_volume = 0
        for level in price_levels:
            if abs(level['price'] - current_price_rounded) < step:
                current_volume = level['volume']
                break
        
        # Calculate rank (percentile)
        volumes_sorted = sorted([level['volume'] for level in price_levels], reverse=True)
        if volumes_sorted:
            current_rank = 1
            for vol in volumes_sorted:
                if current_volume >= vol:
                    break
                current_rank += 1
            total_levels = len(volumes_sorted)
            current_volume_rank = int((current_rank / total_levels) * 100) if total_levels > 0 else 50
        else:
            current_volume_rank = 50
        
        current_volume_pct = (current_volume / total_volume) * 100 if total_volume > 0 else 0
        
        return {
            "footprint_active": True,
            "window_bars": window_bars,
            "total_volume": float(total_volume),
            "price_levels": price_levels,  # Can be large, consider limiting
            "hvn_zones": hvn_zones[:5],  # Top 5 HVNs
            "lvn_zones": lvn_zones[:5],  # Top 5 LVNs
            "poc": poc,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "current_price_volume_rank": current_volume_rank,
            "current_price_volume_pct": round(current_volume_pct, 2),
            "price_min": float(price_min),
            "price_max": float(price_max),
        }
        
    except Exception as e:
        logger.error(f"Error calculating rolling volume footprint: {e}", exc_info=True)
        return _empty_footprint(window_bars)


def _empty_footprint(window_bars: int) -> Dict[str, Any]:
    """Return empty footprint structure"""
    return {
        "footprint_active": False,
        "window_bars": window_bars,
        "total_volume": 0.0,
        "price_levels": [],
        "hvn_zones": [],
        "lvn_zones": [],
        "poc": 0.0,
        "value_area_high": 0.0,
        "value_area_low": 0.0,
        "current_price_volume_rank": 50,
        "current_price_volume_pct": 0.0,
    }

