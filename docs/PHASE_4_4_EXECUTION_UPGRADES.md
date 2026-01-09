# Phase 4.4 - Execution Upgrades

## 🎯 Objectives

Improve trade execution quality and exit management through:
1. **OCO Brackets** - Bidirectional breakout entries
2. **Adaptive TP** - Dynamic targets based on momentum
3. **Momentum-Aware Trailing** - Intelligent stop management
4. **Structure-Aware SL** - Anchoring to swings, FVG, and liquidity zones

---

## 📐 Component Breakdown

### 1. OCO (One-Cancels-Other) Brackets

**Purpose**: Place both buy stop and sell stop around consolidation; whichever fills cancels the other.

**When to Use**:
- Breakout strategy in volatile/range regimes
- Consolidation/range detected (bb_width < 0.03, ADX < 25)
- London/NY sessions (sufficient liquidity)
- Not during news blackout

**Logic**:
```python
# Detect consolidation
if is_breakout_strategy and is_consolidation:
    range_high = max(last_20_highs)
    range_low = min(last_20_lows)
    
    # Place brackets
    buy_stop = range_high + (0.2 × ATR)  # Above resistance
    sell_stop = range_low - (0.2 × ATR)  # Below support
    
    # SL/TP for each side
    buy_sl = buy_stop - (0.8 × ATR)
    buy_tp = buy_stop + (2.0 × (buy_stop - buy_sl))
    
    sell_sl = sell_stop + (0.8 × ATR)
    sell_tp = sell_stop - (2.0 × (sell_sl - sell_stop))
    
    # Expiry: 60-90 minutes or session end
    expiry = min(90_minutes, session_end)
```

**Validation**:
- Range width ≥ 0.5 × ATR (avoid tiny ranges)
- Bracket distance ≥ 0.2 × ATR (avoid whipsaw)
- Spread < 20% ATR (good fill quality)
- No pending orders already active

**Output**:
```json
{
  "order_type": "oco_bracket",
  "buy_stop": 100.5,
  "buy_sl": 99.7,
  "buy_tp": 102.1,
  "sell_stop": 99.5,
  "sell_sl": 100.3,
  "sell_tp": 97.9,
  "expiry_minutes": 90
}
```

---

### 2. Adaptive TP (Take Profit)

**Purpose**: Extend TP when momentum expands; scale out early when momentum fades.

**Momentum Indicators**:
- MACD histogram slope (last 3 bars)
- Range expansion: current_range / median_range(20)
- Volume z-score
- ATR expansion: ATR(5) / ATR(14)

**Logic**:
```python
def calculate_adaptive_tp(entry, sl, base_rr, momentum_state):
    base_tp = entry + (base_rr × (entry - sl))
    
    # Momentum extension
    if momentum_state == "strong":
        # MACD hist slope > 0.2, range > 1.2× median, volume_z > 1.0
        extension_factor = 1.5  # Extend TP by 50%
        adaptive_tp = entry + (base_rr × extension_factor × (entry - sl))
        
    elif momentum_state == "fading":
        # MACD hist slope < -0.1, range < 0.8× median, volume_z < 0
        extension_factor = 0.7  # Reduce TP by 30%
        adaptive_tp = entry + (base_rr × extension_factor × (entry - sl))
        
    else:  # "normal"
        adaptive_tp = base_tp
    
    # Clamp to reasonable range
    min_tp = entry + (1.2 × (entry - sl))  # Min 1.2R
    max_tp = entry + (4.0 × (entry - sl))  # Max 4.0R
    
    return clamp(adaptive_tp, min_tp, max_tp)
```

**Momentum State Detection**:
```python
def detect_momentum_state(macd_hist, range_ratio, volume_z, atr_ratio):
    score = 0
    
    # MACD histogram slope (3-bar)
    if macd_hist_slope > 0.2:
        score += 1
    elif macd_hist_slope < -0.1:
        score -= 1
    
    # Range expansion
    if range_ratio > 1.2:
        score += 1
    elif range_ratio < 0.8:
        score -= 1
    
    # Volume
    if volume_z > 1.0:
        score += 1
    elif volume_z < 0:
        score -= 1
    
    # ATR expansion
    if atr_ratio > 1.15:
        score += 1
    
    if score >= 2:
        return "strong"
    elif score <= -2:
        return "fading"
    else:
        return "normal"
```

---

### 3. Momentum-Aware Trailing Stops

**Purpose**: Trail stops to lock in profit when momentum continues; tighten when momentum fades.

**Logic**:
```python
def calculate_trailing_stop(position, momentum_state, structure):
    entry = position.entry
    current_price = position.current_price
    sl = position.sl
    unrealized_r = (current_price - entry) / (entry - sl)  # In R multiples
    
    # Only trail after 1R in profit
    if unrealized_r < 1.0:
        return sl  # Keep original SL
    
    # Momentum-based trailing
    if momentum_state == "strong":
        # Wide trail: SuperTrend or Keltner upper band
        trailing_sl = structure.supertrend_band  # e.g., current - (2.0 × ATR)
        
    elif momentum_state == "fading":
        # Tight trail: Move to breakeven + 0.5R
        trailing_sl = entry + (0.5 × (entry - sl))
        
    else:  # "normal"
        # Standard trail: EMA20 or current - (1.5 × ATR)
        trailing_sl = max(structure.ema20, current_price - (1.5 × structure.atr))
    
    # Never trail backwards
    return max(trailing_sl, sl)
```

**Structure Anchors** (from Phase 4.1):
- **Swings**: Last swing low (for long) + 0.1 × ATR buffer
- **FVG edges**: If price is above FVG, trail to FVG upper edge
- **Equal lows**: If equal lows swept, trail to sweep level + buffer

---

### 4. Structure-Aware SL Anchoring

**Purpose**: Place SL beyond structure to avoid premature stop-outs.

**Anchor Priority** (Phase 4.1 integration):
1. **Swing high/low** (most recent within 20 bars)
2. **Fair Value Gap (FVG)** edge
3. **Equal highs/lows** cluster
4. **Sweep level** (if liquidity grab detected)

**Logic**:
```python
def calculate_structure_sl(entry, direction, structure, atr):
    buffer = 0.1 × atr  # 10% ATR buffer beyond structure
    
    if direction == "long":
        # Find nearest structure below entry
        anchors = []
        
        # Swing low
        if structure.last_swing_low and structure.last_swing_low < entry:
            anchors.append(structure.last_swing_low)
        
        # FVG lower edge
        if structure.fvg_bull and structure.fvg_zone_lower < entry:
            anchors.append(structure.fvg_zone_lower)
        
        # Equal lows
        if structure.eq_low_cluster and structure.eq_low_price < entry:
            anchors.append(structure.eq_low_price)
        
        # Sweep level
        if structure.sweep_bear and structure.sweep_price < entry:
            anchors.append(structure.sweep_price)
        
        # Use nearest anchor
        if anchors:
            structure_level = max(anchors)  # Nearest below entry
            sl = structure_level - buffer
        else:
            # Fallback: 0.5 × ATR below entry
            sl = entry - (0.5 × atr)
        
        return sl
    
    else:  # "short"
        # Mirror logic for shorts
        anchors = []
        
        if structure.last_swing_high and structure.last_swing_high > entry:
            anchors.append(structure.last_swing_high)
        
        if structure.fvg_bear and structure.fvg_zone_upper > entry:
            anchors.append(structure.fvg_zone_upper)
        
        if structure.eq_high_cluster and structure.eq_high_price > entry:
            anchors.append(structure.eq_high_price)
        
        if structure.sweep_bull and structure.sweep_price > entry:
            anchors.append(structure.sweep_price)
        
        if anchors:
            structure_level = min(anchors)  # Nearest above entry
            sl = structure_level + buffer
        else:
            sl = entry + (0.5 × atr)
        
        return sl
```

**Validation**:
- SL distance ≥ 0.4 × ATR (minimum from validator)
- SL distance ≤ 1.5 × ATR (avoid too wide)
- RR after structure SL ≥ strategy min_rr

---

## 🔧 Implementation Plan

### Phase 4.4.1 - OCO Brackets
**Files**:
- `infra/execution_manager.py` (NEW) - OCO logic
- `domain/consolidation.py` (NEW) - Range detection
- `handlers/trading.py` (ENHANCE) - OCO order placement

**Tests**:
- Consolidation detection
- Bracket calculation
- Expiry logic

### Phase 4.4.2 - Adaptive TP
**Files**:
- `infra/momentum_detector.py` (NEW) - Momentum state detection
- `infra/execution_manager.py` (ENHANCE) - Adaptive TP logic

**Tests**:
- Momentum state detection
- TP extension/reduction
- Clamping logic

### Phase 4.4.3 - Trailing Stops
**Files**:
- `infra/position_manager.py` (ENHANCE) - Trailing logic
- `infra/execution_manager.py` (ENHANCE) - Trail calculation

**Tests**:
- Trail trigger (after 1R)
- Momentum-based trailing
- Structure anchoring

### Phase 4.4.4 - Structure SL
**Files**:
- `infra/execution_manager.py` (ENHANCE) - SL anchoring
- Integration with Phase 4.1 structure features

**Tests**:
- Structure anchor detection
- SL calculation
- Buffer application

---

## 📊 Output Schema

### Enhanced Trade Specification
```json
{
  "strategy": "breakout",
  "order_type": "oco_bracket | buy_stop | sell_stop | buy_limit | sell_limit",
  
  // Standard fields
  "entry": 100.0,
  "sl": 98.5,
  "tp": 103.0,
  "rr": 2.0,
  
  // OCO bracket (if applicable)
  "oco_bracket": {
    "buy_stop": 100.5,
    "buy_sl": 99.7,
    "buy_tp": 102.1,
    "sell_stop": 99.5,
    "sell_sl": 100.3,
    "sell_tp": 97.9,
    "expiry_minutes": 90
  },
  
  // Adaptive TP
  "adaptive_tp": {
    "base_tp": 103.0,
    "momentum_state": "strong",
    "adaptive_tp": 104.5,
    "extension_factor": 1.5
  },
  
  // Structure SL
  "structure_sl": {
    "anchor_type": "swing_low | fvg_edge | eq_lows | sweep_level",
    "anchor_price": 98.3,
    "buffer_atr": 0.1,
    "final_sl": 98.2
  },
  
  // Trailing stop config
  "trailing_config": {
    "enabled": true,
    "trigger_r": 1.0,
    "trail_method": "momentum_aware | ema20 | supertrend",
    "tighten_on_fade": true
  }
}
```

---

## ✅ Success Metrics

1. **OCO Brackets**:
   - Capture breakouts in both directions
   - Reduce missed breakout opportunities by 30%

2. **Adaptive TP**:
   - Increase avg R per winner by 15%
   - Reduce premature TP hits in strong momentum

3. **Trailing Stops**:
   - Lock in 80%+ of runners above 2R
   - Reduce giveback from 1.5R → 0.3R on fades

4. **Structure SL**:
   - Reduce stop-outs by 20%
   - Increase win rate by 5-8%

---

## 🚀 Rollout Strategy

1. **Build & Test** (Phase 4.4.1-4.4.4)
2. **Simulation Mode** - Test with paper trades
3. **Gradual Rollout**:
   - Enable structure SL first (lowest risk)
   - Add adaptive TP
   - Add trailing stops
   - Enable OCO brackets last (requires most validation)
4. **Monitor & Tune** - Track metrics weekly

---

## 🔄 Integration Points

- **Phase 4.1 Features**: Use BOS, FVG, sweeps, equal highs/lows for SL anchoring
- **Phase 4.2 Sessions**: OCO brackets only in London/NY; tighten trailing in Asia
- **Validator**: Ensure structure SL still meets min distance requirements
- **Router**: Add execution hints to DecisionOutcome

---

**Ready to implement Phase 4.4.1 - OCO Brackets?**

