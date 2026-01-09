"""
Fair Value Gap (FVG) detection.
Detects imbalance zones where price moved inefficiently.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def detect_fvg(
    bars: pd.DataFrame,
    atr: float,
    min_width_mult: float = 0.1,
    lookback: int = 10
) -> Dict[str, Any]:
    """
    Detect Fair Value Gaps (imbalance zones).
    
    Bearish FVG: high(n-1) < low(n+1), width ≥ min_width_mult×ATR
    Bullish FVG: low(n-1) > high(n+1), width ≥ min_width_mult×ATR
    
    Args:
        bars: DataFrame with OHLC columns
        atr: Average True Range for normalization
        min_width_mult: Minimum gap width as multiple of ATR
        lookback: Number of recent bars to check
    
    Returns:
        {
            "fvg_bull": bool,
            "fvg_bear": bool,
            "fvg_zone": (float, float),  # (upper, lower)
            "width_atr": float,
            "bars_ago": int
        }
    """
    try:
        if len(bars) < 3 or atr <= 0:
            return _empty_fvg()
        
        # Check recent bars for FVG
        recent_bars = bars.iloc[-(lookback + 2):] if len(bars) >= lookback + 2 else bars
        
        min_width = min_width_mult * atr
        
        # Search for most recent FVG
        for i in range(len(recent_bars) - 2, 0, -1):
            if i < 1 or i >= len(recent_bars) - 1:
                continue
            
            bar_before = recent_bars.iloc[i - 1]
            bar_current = recent_bars.iloc[i]
            bar_after = recent_bars.iloc[i + 1]
            
            # Bullish FVG: gap up (low of bar_before > high of bar_after)
            if bar_before["low"] > bar_after["high"]:
                gap_width = bar_before["low"] - bar_after["high"]
                
                if gap_width >= min_width:
                    bars_ago = len(recent_bars) - i - 1
                    
                    return {
                        "fvg_bull": True,
                        "fvg_bear": False,
                        "fvg_zone": (bar_before["low"], bar_after["high"]),
                        "width_atr": gap_width / atr,
                        "bars_ago": bars_ago
                    }
            
            # Bearish FVG: gap down (high of bar_before < low of bar_after)
            if bar_before["high"] < bar_after["low"]:
                gap_width = bar_after["low"] - bar_before["high"]
                
                if gap_width >= min_width:
                    bars_ago = len(recent_bars) - i - 1
                    
                    return {
                        "fvg_bull": False,
                        "fvg_bear": True,
                        "fvg_zone": (bar_after["low"], bar_before["high"]),
                        "width_atr": gap_width / atr,
                        "bars_ago": bars_ago
                    }
        
        return _empty_fvg()
        
    except Exception as e:
        logger.debug(f"FVG detection failed: {e}")
        return _empty_fvg()


def _empty_fvg() -> Dict[str, Any]:
    """Return empty FVG result."""
    return {
        "fvg_bull": False,
        "fvg_bear": False,
        "fvg_zone": (0.0, 0.0),
        "width_atr": 0.0,
        "bars_ago": -1
    }

