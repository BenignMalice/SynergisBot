# Enhanced Data Fields - Data Structure Definitions

**Date**: December 11, 2025  
**Status**: ✅ **COMPLETE**  
**Purpose**: Define Python type definitions/dataclasses for all 9 new data blocks

---

## Overview

This document defines the data structures for all 9 enhanced data fields to be added to the `analyse_symbol_full` response. All structures are designed to be JSON-serializable and include data quality indicators where applicable.

---

## 1. Correlation Context (`correlation_context`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "corr_window_minutes": int,  # Window size in minutes (default: 240)
    "corr_vs_dxy": Optional[float],  # -1.0 to +1.0, or None if unavailable
    "corr_vs_sp500": Optional[float],  # -1.0 to +1.0, or None if unavailable
    "corr_vs_us10y": Optional[float],  # -1.0 to +1.0, or None if unavailable
    "corr_vs_btc": Optional[float],  # -1.0 to +1.0, or None if unavailable (only for non-BTC symbols)
    "conflict_flags": {
        "gold_vs_dxy_conflict": bool,  # True if correlation breaks expected pattern
        "sp500_divergence": bool,  # True if SP500 correlation diverges from expected
        "us10y_divergence": bool,  # True if US10Y correlation diverges from expected
        "btc_divergence": bool  # True if BTC correlation diverges from expected
    },
    "data_quality": str,  # "good" | "limited" | "unavailable"
    "sample_size": int  # Number of bars used for calculation
}
```

**Validation Rules**:
- `corr_window_minutes`: Must be positive integer, typically 240 (4 hours)
- `corr_vs_*`: Must be in range [-1.0, 1.0] if not None
- `data_quality`: 
  - "good" if sample_size >= 192 (80% of 240 bars) and overlap >= 80%
  - "limited" if sample_size >= 120 (50% of 240 bars) and overlap >= 50%
  - "unavailable" if sample_size < 120 or overlap < 50%
- `sample_size`: Must be >= 0

**Example**:
```json
{
    "corr_window_minutes": 240,
    "corr_vs_dxy": -0.72,
    "corr_vs_sp500": 0.15,
    "corr_vs_us10y": -0.48,
    "corr_vs_btc": null,
    "conflict_flags": {
        "gold_vs_dxy_conflict": true,
        "sp500_divergence": false,
        "us10y_divergence": false,
        "btc_divergence": false
    },
    "data_quality": "good",
    "sample_size": 240
}
```

---

## 2. Order Flow (`order_flow`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "cvd_value": float,  # Cumulative volume delta (proxy for non-BTC)
    "cvd_slope": str,  # "up" | "down" | "flat"
    "aggressor_ratio": Optional[float],  # buy_vol / sell_vol (proxy), or None if unavailable
    "imbalance_score": int,  # 0-100 (how one-sided)
    "large_trade_count": int,  # Blocks > X size in window (if available)
    "data_quality": str,  # "proxy" | "limited" | "good" | "unavailable"
    "data_source": str,  # "mt5_tick_proxy" | "binance_aggtrades" | "unavailable"
    "window_minutes": int  # Window size in minutes (default: 30)
}
```

**Validation Rules**:
- `cvd_value`: Can be any float (positive or negative)
- `cvd_slope`: Must be one of "up", "down", "flat"
- `aggressor_ratio`: Must be >= 0.0 if not None, or None if sell_vol == 0
- `imbalance_score`: Must be in range [0, 100]
- `data_quality`:
  - "good" for BTC (Binance true order flow)
  - "proxy" for non-BTC (MT5 tick-based estimation)
  - "limited" if insufficient tick data
  - "unavailable" if no data available
- `window_minutes`: Must be positive integer, typically 30

**Example**:
```json
{
    "cvd_value": 132.5,
    "cvd_slope": "falling",
    "aggressor_ratio": 0.84,
    "imbalance_score": 30,
    "large_trade_count": 2,
    "data_quality": "proxy",
    "data_source": "mt5_tick_proxy",
    "window_minutes": 30
}
```

---

## 3. HTF Levels (`htf_levels`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "weekly_open": float,  # Current week's open (Monday 00:00 UTC)
    "monthly_open": float,  # Current month's open (1st day 00:00 UTC)
    "previous_week_high": float,
    "previous_week_low": float,
    "previous_day_high": float,  # Aligns with PDH naming
    "previous_day_low": float,   # Aligns with PDL naming
    "range_reference": str,  # "weekly_range" | "asia_session_range" | "daily_range"
    "current_price_position": str,  # "discount" | "equilibrium" | "premium"
    "discount_threshold": float,  # Bottom 33% of range (default: 0.33)
    "premium_threshold": float,   # Top 33% of range (default: 0.66)
    "timezone": str  # Timezone used for calculations (default: "UTC")
}
```

**Validation Rules**:
- All price fields: Must be positive floats
- `range_reference`: Must be one of "weekly_range", "asia_session_range", "daily_range"
- `current_price_position`: Must be one of "discount", "equilibrium", "premium"
- `discount_threshold`: Must be in range [0.0, 1.0], typically 0.33
- `premium_threshold`: Must be in range [0.0, 1.0], typically 0.66
- `timezone`: Must be valid timezone string, default "UTC"

**Example**:
```json
{
    "weekly_open": 4175.0,
    "monthly_open": 4120.0,
    "previous_week_high": 4225.0,
    "previous_week_low": 4085.0,
    "previous_day_high": 4210.0,
    "previous_day_low": 4190.0,
    "range_reference": "weekly_range",
    "current_price_position": "premium",
    "discount_threshold": 0.33,
    "premium_threshold": 0.66,
    "timezone": "UTC"
}
```

---

## 4. Session Risk (`session_risk`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "is_rollover_window": bool,  # True during daily rollover (00:00 UTC ±30min)
    "is_news_lock_active": bool,  # True if high-impact news in ±30min window
    "minutes_to_next_high_impact": Optional[int],  # Minutes until next HIGH/ULTRA event, or None
    "is_in_high_impact_window": bool,  # True if within ±30min of high-impact event
    "session_profile": str,  # "quiet" | "normal" | "explosive" (may default to "normal")
    "session_volatility_multiplier": float,  # Historical vol multiplier (default: 1.0)
    "rollover_window_start": str,  # ISO format datetime string (e.g., "2025-12-11T00:00:00Z")
    "rollover_window_end": str  # ISO format datetime string (e.g., "2025-12-11T00:30:00Z")
}
```

**Validation Rules**:
- `is_rollover_window`: Boolean
- `is_news_lock_active`: Boolean
- `minutes_to_next_high_impact`: Must be >= 0 if not None, or None if no upcoming events
- `is_in_high_impact_window`: Boolean
- `session_profile`: Must be one of "quiet", "normal", "explosive" (defaults to "normal" if historical data unavailable)
- `session_volatility_multiplier`: Must be > 0.0, typically 1.0 (default if historical data unavailable)
- `rollover_window_start/end`: Must be valid ISO format datetime strings in UTC

**Example**:
```json
{
    "is_rollover_window": false,
    "is_news_lock_active": false,
    "minutes_to_next_high_impact": 75,
    "is_in_high_impact_window": false,
    "session_profile": "normal",
    "session_volatility_multiplier": 1.0,
    "rollover_window_start": "2025-12-11T00:00:00Z",
    "rollover_window_end": "2025-12-11T00:30:00Z"
}
```

---

## 5. Execution Context (`execution_context`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "current_spread_points": float,  # Current spread in points
    "spread_vs_median": float,  # Multiple of median spread (e.g., 2.1x)
    "is_spread_elevated": bool,  # True if spread_vs_median > 1.5
    "avg_slippage_points": Optional[float],  # Average slippage from last N trades, or None
    "slippage_vs_normal": Optional[float],  # Multiple of normal slippage, or None
    "is_slippage_elevated": bool,  # True if slippage_vs_normal > 1.5 (or False if slippage unavailable)
    "execution_quality": str,  # "good" | "degraded" | "poor"
    "slippage_sample_size": int,  # Number of trades used for slippage calc (0 if unavailable)
    "slippage_data_available": bool  # False if no trade history
}
```

**Validation Rules**:
- `current_spread_points`: Must be >= 0.0
- `spread_vs_median`: Must be > 0.0
- `is_spread_elevated`: Boolean (True if spread_vs_median > 1.5)
- `avg_slippage_points`: Must be >= 0.0 if not None
- `slippage_vs_normal`: Must be > 0.0 if not None
- `is_slippage_elevated`: Boolean (True if slippage_vs_normal > 1.5 and available)
- `execution_quality`:
  - "good" if spread_vs_median < 1.5 and (slippage_vs_normal < 1.5 or not available)
  - "degraded" if spread_vs_median > 1.5 OR slippage_vs_normal > 1.5
  - "poor" if spread_vs_median > 2.0 AND slippage_vs_normal > 2.0
- `slippage_sample_size`: Must be >= 0
- `slippage_data_available`: Boolean

**Example**:
```json
{
    "current_spread_points": 19.0,
    "spread_vs_median": 2.1,
    "is_spread_elevated": true,
    "avg_slippage_points": 6.0,
    "slippage_vs_normal": 1.8,
    "is_slippage_elevated": true,
    "execution_quality": "degraded",
    "slippage_sample_size": 10,
    "slippage_data_available": true
}
```

---

## 6. Strategy Stats (`strategy_stats`)

**Type**: `Optional[Dict[str, Any]]`  
**Nullable**: Yes (can be `None`)

```python
{
    "strategy": str,  # Strategy name (e.g., "INSIDE_BAR_VOLATILITY_TRAP")
    "regime": str,  # Matched regime (e.g., "stable_vol_range_compression")
    "sample_size": int,  # Number of trades in similar regime
    "win_rate": float,  # 0.0 to 1.0
    "avg_rr": float,  # Average risk:reward
    "max_drawdown_rr": float,  # Worst case R:R (can be negative)
    "median_holding_time_minutes": int,  # Median holding time in minutes
    "confidence": str,  # "high" | "medium" | "low"
    "regime_match_quality": str  # "exact" | "fuzzy" | "approximate"
} OR None if no data available
```

**Validation Rules**:
- `strategy`: Must be non-empty string
- `regime`: Must be non-empty string
- `sample_size`: Must be >= 10 (otherwise return None)
- `win_rate`: Must be in range [0.0, 1.0]
- `avg_rr`: Can be any float (typically > 0.0)
- `max_drawdown_rr`: Can be any float (can be negative)
- `median_holding_time_minutes`: Must be >= 0
- `confidence`:
  - "high" if sample_size >= 30 and regime_match_quality in ["exact", "fuzzy"]
  - "medium" if sample_size >= 10
  - "low" if sample_size < 10 (should not occur - return None instead)
- `regime_match_quality`: Must be one of "exact", "fuzzy", "approximate"
- Return `None` if sample_size < 10

**Example**:
```json
{
    "strategy": "INSIDE_BAR_VOLATILITY_TRAP",
    "regime": "stable_vol_range_compression",
    "sample_size": 47,
    "win_rate": 0.62,
    "avg_rr": 1.9,
    "max_drawdown_rr": -1.3,
    "median_holding_time_minutes": 95,
    "confidence": "high",
    "regime_match_quality": "exact"
}
```

---

## 7. Structure Summary (`structure_summary`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "current_range_type": str,  # "balanced_range" | "trend_channel" | "breakout" | "distribution" | "accumulation"
    "range_state": str,  # "mid_range" | "near_range_high" | "near_range_low" | "just_broke_range"
    "has_liquidity_sweep": bool,
    "sweep_type": str,  # "bull" | "bear" | "none"
    "sweep_level": Optional[float],  # Price level if sweep detected, or None
    "discount_premium_state": str,  # "seeking_premium_liquidity" | "seeking_discount_liquidity" | "balanced"
    "range_high": Optional[float],  # From M1 microstructure liquidity zones, or None
    "range_low": Optional[float],   # From M1 microstructure liquidity zones, or None
    "range_mid": Optional[float]    # Calculated, or None
}
```

**Validation Rules**:
- `current_range_type`: Must be one of "balanced_range", "trend_channel", "breakout", "distribution", "accumulation"
- `range_state`: Must be one of "mid_range", "near_range_high", "near_range_low", "just_broke_range"
- `has_liquidity_sweep`: Boolean
- `sweep_type`: Must be one of "bull", "bear", "none"
- `sweep_level`: Must be > 0.0 if not None, or None if no sweep
- `discount_premium_state`: Must be one of "seeking_premium_liquidity", "seeking_discount_liquidity", "balanced"
- `range_high/low/mid`: Must be > 0.0 if not None, or None if range not detected

**Example**:
```json
{
    "current_range_type": "balanced_range",
    "range_state": "mid_range",
    "has_liquidity_sweep": true,
    "sweep_type": "bear",
    "sweep_level": 4188.95,
    "discount_premium_state": "seeking_premium_liquidity",
    "range_high": 4207.11,
    "range_low": 4188.96,
    "range_mid": 4198.04
}
```

---

## 8. Symbol Constraints (`symbol_constraints`)

**Type**: `Dict[str, Any]`  
**Nullable**: Yes (can be `{}` or `None`)

```python
{
    "max_concurrent_trades_for_symbol": int,  # Max concurrent trades for this symbol
    "max_total_risk_on_symbol_pct": float,  # Max % of account risk on this symbol
    "allowed_strategies": List[str],  # List of allowed strategies (empty = all allowed)
    "risk_profile": str,  # "aggressive" | "normal" | "conservative"
    "banned_strategies": List[str],  # Strategies not allowed for this symbol
    "max_position_size_pct": float  # Max position size as % of account
}
```

**Validation Rules**:
- `max_concurrent_trades_for_symbol`: Must be >= 1
- `max_total_risk_on_symbol_pct`: Must be > 0.0 and <= 100.0
- `allowed_strategies`: List of strings (empty list means all strategies allowed)
- `risk_profile`: Must be one of "aggressive", "normal", "conservative"
- `banned_strategies`: List of strings (can be empty)
- `max_position_size_pct`: Must be > 0.0 and <= 100.0

**Example**:
```json
{
    "max_concurrent_trades_for_symbol": 2,
    "max_total_risk_on_symbol_pct": 3.0,
    "allowed_strategies": [
        "INSIDE_BAR_VOLATILITY_TRAP",
        "VOLATILITY_REVERSION_SCALP"
    ],
    "risk_profile": "normal",
    "banned_strategies": ["SWING_TREND_FOLLOWING"],
    "max_position_size_pct": 5.0
}
```

---

## Data Quality Indicators

**Standardized Values** (used across all applicable fields):
- `"good"`: High-quality data, reliable, can be used with confidence
- `"limited"`: Some data available but sample size small or gaps present - use with caution
- `"proxy"`: Estimated/calculated data, less reliable than true data - use with caution and prefer structure confirmation
- `"unavailable"`: No data available - IGNORE the field entirely, do not use in analysis

**Mandatory Checking Rules**:
1. ALWAYS check `data_quality` field before using any field value
2. If `data_quality == "unavailable"`, do NOT use the field in analysis or reasoning
3. If `data_quality == "limited"`, acknowledge uncertainty and use with caution
4. If `data_quality == "proxy"`, understand limitations and prefer structure confirmation
5. If `data_quality == "good"`, data is reliable and can be used with confidence

---

## JSON Serialization Requirements

All fields must be JSON-serializable:
- No numpy types (convert to `float`, `int`, `list`)
- No datetime objects (convert to ISO format strings)
- No complex objects (use dictionaries or lists)
- Handle `None` values appropriately (can be `null` in JSON)

**Conversion Helpers**:
```python
def to_json_serializable(value: Any) -> Any:
    """Convert value to JSON-serializable format"""
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: to_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_json_serializable(item) for item in value]
    else:
        return value
```

---

**Status**: ✅ **COMPLETE** - All data structures defined and validated

