# Phase III Advanced Plans - Capabilities Matrix

**Date**: 2026-01-07  
**Quick Reference**: Current vs. Required System Capabilities

---

## 📊 Capability Status Overview

| Plan Category | Current Support | Required Additions | Priority |
|--------------|----------------|-------------------|----------|
| 1. Cross-Market Correlation | 60% | Correlation condition checks, DXY/ETH tracking | High |
| 2. Order Flow Microstructure | 70% | Imbalance/spoof detection, rebuild speed | High |
| 3. Volatility Patterns | 50% | Fractal detection, IV collapse, recoil | Medium |
| 4. Institutional Signatures | 40% | Sequence tracking, cascade detection | Medium |
| 5. Multi-Timeframe Confluence | 30% | Multi-TF checks, M1 pullback | High |
| 6. Adaptive Scenarios | 40% | Conditional modifications, post-news | Medium |
| 7. Predictive Momentum | 30% | Momentum decay, time-based exits | Low |

---

## ✅ Currently Supported Conditions

### Order Flow (Already Working)
- ✅ `absorption_zone_detected`
- ✅ `delta_positive` / `delta_negative`
- ✅ `cvd_rising` / `cvd_falling`
- ✅ `cvd_div_bull` / `cvd_div_bear`
- ✅ `delta_divergence_bull` / `delta_divergence_bear`

### Structure (Already Working)
- ✅ `choch_bull` / `choch_bear`
- ✅ `bos_bull` / `bos_bear`
- ✅ `fvg_bull` / `fvg_bear`
- ✅ `fvg_filled_pct`
- ✅ `mss_bull` / `mss_bear`
- ✅ `breaker_block`
- ✅ `order_block`
- ✅ `mitigation_block_bull` / `mitigation_block_bear`

### Volatility (Already Working)
- ✅ `bb_squeeze` / `bb_expansion`
- ✅ `inside_bar`
- ✅ `volatility_state`
- ✅ `atr_5m_threshold`
- ✅ `vix_threshold`

### Session (Already Working)
- ✅ `session` (ASIA, LONDON, NY, WEEKEND)
- ✅ `require_active_session`
- ✅ News blackout checking

---

## ❌ Missing Conditions (Need Implementation)

### 1. Cross-Market Correlation
```python
# NEW CONDITIONS NEEDED
"dxy_change_pct": 0.3  # DXY percentage change
"dxy_stall_detected": true  # DXY momentum stall
"btc_hold_above_support": true  # BTC support hold
"ethbtc_ratio_deviation": 1.5  # ETH/BTC ratio deviation (σ)
"ethbtc_divergence_direction": "bullish" | "bearish"
"nasdaq_15min_bullish": true  # NASDAQ 15-min trend
"nasdaq_correlation_confirmed": true  # Correlation alignment
```

### 2. Order Flow Microstructure
```python
# NEW CONDITIONS NEEDED
"imbalance_detected": true  # Order book imbalance
"imbalance_direction": "buy" | "sell"
"spoof_detected": true  # Spoofing activity
"bid_rebuild_speed": 0.5  # Bid rebuild rate
"ask_decay_speed": 0.3  # Ask decay rate
"liquidity_rebuild_confirmed": true  # Rebuild > decay
"momentum_flip_confirmed": true  # Momentum reversal
```

### 3. Volatility Patterns
```python
# NEW CONDITIONS NEEDED
"consecutive_inside_bars": 3  # Number of consecutive inside bars
"volatility_fractal_expansion": true  # Fractal pattern
"iv_collapse_detected": true  # Implied volatility collapse
"volatility_recoil_confirmed": true  # Recoil pattern
"rmag_atr_ratio": 5.0  # RMAG > +5 ATR
"bb_width_rising": true  # BB width increasing
"impulse_continuation_confirmed": true  # Pattern confirmed
```

### 4. Institutional Signatures
```python
# NEW CONDITIONS NEEDED
"overlapping_obs_count": 3  # Overlapping order blocks
"mitigation_cascade_confirmed": true  # Cascade pattern
"liquidity_vacuum_refill": true  # FVG + imbalance combo
"breaker_retest_count": 2  # Number of retests
"breaker_retest_chain_confirmed": true  # Chain pattern
```

### 5. Multi-Timeframe Confluence
```python
# NEW CONDITIONS NEEDED
"choch_bull_m5": true  # CHOCH on M5
"choch_bull_m15": true  # CHOCH on M15
"mtf_choch_sync": true  # Multi-TF alignment
"bos_bear_m15": true  # BOS on M15
"m1_pullback_confirmed": true  # M1 pullback
"fvg_bull_m30": true  # FVG on M30
"htf_fvg_align": true  # HTF alignment
```

### 6. Adaptive Scenarios
```python
# NEW FEATURES NEEDED
"weekend_auto_tighten": true  # Weekend SL tightening
"btc_open_interest_drop": true  # OI drops
"sl_tighten_multiplier": 0.8  # SL multiplier
"news_absorption_filter": true  # Pause strategies
"news_blackout_window": 15  # Minutes pre/post
"post_news_reclaim": true  # Post-news logic
"pre_news_level": 92000  # Pre-news price
"price_reclaim_confirmed": true  # Reclaim confirmed
```

### 7. Predictive Momentum
```python
# NEW CONDITIONS NEEDED
"momentum_decay_trap": true  # Enable decay detection
"rsi_divergence_detected": true  # RSI divergence
"macd_divergence_detected": true  # MACD divergence
"tick_rate_declining": true  # Tick rate decline
"momentum_decay_confirmed": true  # Decay confirmed
"time_decay_scalper": true  # Time-based exit
"min_unrealized_gain_rr": 0.4  # Min R:R for exit
"max_hold_time_minutes": 15  # Max hold time
"adaptive_trailing_breaker": true  # Trailing mode
"trailing_activation_rr": 1.5  # Activation R:R
```

---

## 🔄 Implementation Priority

### **Priority 1: High Value, Low Complexity**
1. **Multi-Timeframe Confluence** (Category 5)
   - High impact on win rate
   - Moderate implementation complexity
   - Uses existing structure detection

2. **Order Flow Microstructure** (Category 2)
   - High precision improvement
   - Builds on existing order flow service
   - Moderate complexity

### **Priority 2: High Value, High Complexity**
3. **Cross-Market Correlation** (Category 1)
   - High value for BTC trading
   - Requires external data sources
   - Moderate complexity

4. **Adaptive Scenarios** (Category 6)
   - High risk management value
   - Requires plan modification system
   - High complexity

### **Priority 3: Medium Value**
5. **Volatility Patterns** (Category 3)
   - Medium precision improvement
   - Moderate complexity
   - Builds on existing volatility detection

6. **Institutional Signatures** (Category 4)
   - Medium value
   - Requires pattern tracking
   - Moderate complexity

### **Priority 4: Lower Priority**
7. **Predictive Momentum** (Category 7)
   - Lower immediate value
   - High complexity
   - Can be added later

---

## 🚀 Quick Start Implementation

### Phase 1: Foundation (2 weeks)
- Multi-timeframe condition checking
- Order flow imbalance detection
- Basic correlation condition checks

### Phase 2: Enhancement (2 weeks)
- Volatility pattern recognition
- Institutional signature detection
- Adaptive scenario handling

### Phase 3: Advanced (2 weeks)
- Full correlation tracking
- Predictive momentum models
- Complete testing & documentation

---

## 📝 Notes

- **Existing Infrastructure**: Most foundation exists (order flow, structure detection, volatility)
- **Data Requirements**: Some plans need external data (ETH price, NASDAQ, BTC OI)
- **Performance**: Multi-timeframe checks may need optimization
- **Testing**: Comprehensive testing required for pattern detection accuracy

---

**Last Updated**: 2026-01-07  
**Status**: Planning Complete - Ready for Implementation


