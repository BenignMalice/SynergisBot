# Order Flow and Absorption Framework

## PURPOSE

Define deterministic logic for interpreting Order Flow, CVD, Delta, Imbalance, and Absorption Zones across all tradable symbols.

This framework allows ChatGPT to integrate microstructural liquidity signals into directional bias, confluence scoring, and plan validation.

It converts raw order flow data into structured reasoning:
- Confirms or invalidates structure-based bias
- Detects trapped buyers/sellers
- Identifies absorption-driven reversals
- Adjusts trade confidence dynamically

**⚠️ CRITICAL: Data Quality Awareness**

Order flow data quality varies significantly by symbol:
- **BTCUSD**: High-quality data from Binance (`data_quality: "good"`)
- **Non-BTC Symbols**: Proxy data from MT5 tick analysis (`data_quality: "proxy"`)

**Always check `data_quality` field before interpretation. Proxy data requires reduced confidence.**

---

## SYSTEM HIERARCHY

This file must always defer to:
- `KNOWLEDGE_DOC_EMBEDDING` (OS Layer)
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED`
- `BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING`
- `VOLATILITY_REGIME_STRATEGIES_EMBEDDING`
- `UPDATED_GPT_INSTRUCTIONS_FIXED`

If any conflict occurs → higher document wins.

---

## DATA REQUIREMENTS & FIELD MAPPING

### Primary Data Source: `moneybot.analyse_symbol_full`

**Location**: `response.data.order_flow`

**Available Fields** (All Symbols):

| Field | Type | Description | Interpretation |
|-------|------|-------------|----------------|
| `cvd_value` | float | Cumulative volume delta | Net directional participation |
| `cvd_slope` | string | "up" \| "down" \| "flat" | Momentum direction |
| `aggressor_ratio` | float | buy_vol / sell_vol | Proxy for delta volume |
| `imbalance_score` | int | 0-100 | How one-sided the flow is |
| `large_trade_count` | int | Count of large trades | Institutional activity |
| `data_quality` | string | "good" \| "proxy" \| "limited" \| "unavailable" | **CRITICAL: Always check this** |
| `data_source` | string | Source identifier | "binance_aggtrades" or "mt5_tick_proxy" |
| `window_minutes` | int | Time window used | Default: 30 minutes |

### Enhanced Data Source: `moneybot.btc_order_flow_metrics` (BTC Only)

**Location**: `response.data.btc_order_flow_metrics`

**Available Fields** (BTCUSD Only):

| Field | Type | Description | Interpretation |
|-------|------|-------------|----------------|
| `delta_volume` | dict | `{buy_volume, sell_volume, net_delta, dominant_side}` | True buy/sell split |
| `cvd` | dict | `{current, slope, bar_count}` | CVD with numeric slope |
| `cvd_divergence` | dict | `{strength: 0.0-1.0, type: "bearish"\|"bullish"\|null}` | Price vs CVD mismatch |
| `absorption_zones` | array | `[{price_level, strength, volume_absorbed, side, ...}]` | Institutional trap zones |
| `buy_sell_pressure` | dict | `{ratio, dominant_side}` | Pressure balance |

**⚠️ IMPORTANT**: This tool is BTC-only. For non-BTC symbols, use `order_flow` from `analyse_symbol_full`.

---

## FIELD MAPPING: Requested → Actual

ChatGPT may request fields that don't exist directly. Use this mapping:

| Requested Field | Actual Field(s) | Notes |
|----------------|-----------------|-------|
| `delta_volume` | `aggressor_ratio` (non-BTC) or `delta_volume.net_delta` (BTC) | For non-BTC, use `aggressor_ratio > 1.0` = buy pressure |
| `cvd_divergence` | Calculate from `cvd_slope` + price direction (non-BTC) or `cvd_divergence` (BTC) | See divergence calculation below |
| `absorption_zones` | Not available (non-BTC) or `absorption_zones` array (BTC) | For non-BTC, infer from CVD slope + price behavior |
| `order_book_imbalance` | `imbalance_score` (0-100) | Convert: `imbalance_score / 100` = percentage |
| `aggressive_taker_imbalance` | `aggressor_ratio` | Similar concept, different calculation |

---

## DATA QUALITY RULES (CRITICAL)

### Quality Levels

1. **"good"** (BTC only):
   - True order flow from Binance
   - Full confidence in interpretation
   - All fields reliable

2. **"proxy"** (Non-BTC symbols):
   - Estimated from MT5 tick data
   - **Reduce confidence by 50%**
   - Use as supporting evidence, not primary signal
   - CVD and slope are approximations

3. **"limited"**:
   - Insufficient data (< 50% of requested bars)
   - **Reduce confidence by 70%**
   - Use with extreme caution

4. **"unavailable"**:
   - No data available
   - **Do not use for analysis**
   - State explicitly: "Order flow data unavailable"

### Quality-Based Confidence Adjustment

```python
base_confidence = confluence_score

if data_quality == "good":
    order_flow_confidence_multiplier = 1.0  # Full confidence
elif data_quality == "proxy":
    order_flow_confidence_multiplier = 0.5  # 50% reduction
elif data_quality == "limited":
    order_flow_confidence_multiplier = 0.3  # 70% reduction
else:  # unavailable
    order_flow_confidence_multiplier = 0.0  # Ignore
```

---

## INTERPRETATION LOGIC

### 1️⃣ CVD & Slope Relationship

**Available Data**: `cvd_value`, `cvd_slope` (all symbols)

| Condition | Interpretation | Confidence Impact |
|-----------|----------------|-------------------|
| `cvd_slope == "up"` and price rising | Genuine buy-side aggression | +10 confluence |
| `cvd_slope == "up"` and price falling | Hidden strength (absorption) | +5 confluence, reversal bias |
| `cvd_slope == "down"` and price falling | Genuine sell-side aggression | +10 confluence |
| `cvd_slope == "down"` and price rising | Hidden weakness (exhaustion) | -10 confluence, reversal bias |
| `cvd_slope == "flat"` | Neutral participation | 0 (no adjustment) |

**Rule**: CVD slope determines internal conviction. Falling CVD while price rises = divergence (hidden weakness).

### 2️⃣ Aggressor Ratio Interpretation (Delta Proxy)

**Available Data**: `aggressor_ratio` (all symbols)

| Condition | Interpretation | Notes |
|-----------|----------------|-------|
| `aggressor_ratio > 1.5` | Strong buy pressure | Similar to positive delta |
| `aggressor_ratio < 0.67` | Strong sell pressure | Similar to negative delta |
| `0.67 < aggressor_ratio < 1.5` | Balanced flow | Neutral |

**For BTC**: Use `delta_volume.net_delta` instead (more accurate).

**Rule**: Aggressor ratio > 1.0 = buy pressure, < 1.0 = sell pressure.

### 3️⃣ Imbalance Score Interpretation

**Available Data**: `imbalance_score` (0-100, all symbols)

| Score Range | Interpretation | Confidence Impact |
|-------------|----------------|-------------------|
| 0-20 | Balanced flow | 0 (neutral) |
| 21-40 | Moderate imbalance | +5 confluence if aligned with structure |
| 41-60 | Strong imbalance | +10 confluence if aligned |
| 61-80 | Very strong imbalance | +15 confluence if aligned |
| 81-100 | Extreme imbalance | +20 confluence if aligned, but watch for exhaustion |

**Rule**: High imbalance (> 60) + opposite CVD slope = exhaustion signal.

### 4️⃣ CVD Divergence Detection

**For BTC**: Use `cvd_divergence.strength` and `cvd_divergence.type` directly.

**For Non-BTC**: Calculate manually:

```python
# Divergence detection logic
if cvd_slope == "up" and price_direction == "down":
    divergence_type = "bullish_divergence"  # Smart money buying
    divergence_strength = 0.5  # Moderate (proxy data)
elif cvd_slope == "down" and price_direction == "up":
    divergence_type = "bearish_divergence"  # Buyer exhaustion
    divergence_strength = 0.5  # Moderate (proxy data)
else:
    divergence_type = None
    divergence_strength = 0.0
```

**Divergence Strength Interpretation**:

| Strength | Confidence Adjustment | Action |
|----------|----------------------|--------|
| 0.0-0.2 | Ignore (noise) | No adjustment |
| 0.3-0.6 | -10 confluence | Moderate warning |
| 0.7-1.0 | -20 confluence | Strong reversal signal |

### 5️⃣ Absorption Zone Detection

**For BTC**: Use `absorption_zones` array directly.

**For Non-BTC**: Infer from available data:

```python
# Absorption inference (non-BTC)
absorption_detected = False
absorption_side = None

if cvd_slope == "up" and price_change < 0.1 * atr:
    # Buy pressure but price not moving = absorption
    absorption_detected = True
    absorption_side = "buy_side"  # Buyers being absorbed
elif cvd_slope == "down" and price_change > -0.1 * atr:
    # Sell pressure but price not moving = absorption
    absorption_detected = True
    absorption_side = "sell_side"  # Sellers being absorbed
```

**Absorption Impact**:
- Detected absorption: -10 confluence
- Absorption + divergence: -20 confluence (strong reversal signal)

---

## CONFLUENCE INTEGRATION RULES

### Alignment Scoring

| Condition | Confluence Adjustment | Notes |
|-----------|----------------------|-------|
| CVD slope + structure aligned | +10 points | Both pointing same direction |
| Aggressor ratio + structure aligned | +5 points | Supporting evidence |
| Imbalance score > 40 + structure aligned | +5 to +20 points | Based on score strength |
| CVD divergence detected | -10 to -20 points | Based on strength |
| Absorption detected | -10 points | Reversal warning |
| Divergence + Absorption combo | -20 points | Strong reversal signal |
| Imbalance contradicts structure | -10 points | Flow vs structure conflict |

### Data Quality Multiplier

**Apply multiplier AFTER all adjustments**:

```python
final_confluence = base_confluence + order_flow_adjustments
if data_quality == "proxy":
    final_confluence = base_confluence + (order_flow_adjustments * 0.5)
elif data_quality == "limited":
    final_confluence = base_confluence + (order_flow_adjustments * 0.3)
```

### Minimum Alignment Requirement

**Never use order flow alone** - require at least 2 metrics to align:

- CVD slope + Aggressor ratio
- CVD slope + Imbalance score
- Aggressor ratio + Imbalance score

If only 1 metric available → reduce confidence by 50%.

---

## STRUCTURE OVERRIDE POLICY

### When Order Flow Can Override Structure

1. **Strong Flow Contradiction**:
   - CVD divergence strength > 0.7
   - AND absorption detected
   - → Downgrade structure confidence by 30%

2. **Flow Confirmation**:
   - CVD slope + aggressor ratio + imbalance all align with structure
   - → Upgrade structure confidence by 20%

3. **Absorption > Structure**:
   - Absorption detected near key OB/FVG
   - → Invalidate continuation plans
   - → Switch to reversal bias

### Override Rules

- **Order flow NEVER completely overrides strong structure** (BOS/CHOCH with >80% confidence)
- **Order flow CAN override weak structure** (< 60% confidence)
- **Absorption zones invalidate continuation plans** regardless of structure strength

---

## STRATEGY INTEGRATION

### Strategy-Specific Order Flow Requirements

| Strategy Type | Order Flow Requirement | Data Quality Needed |
|---------------|------------------------|---------------------|
| Trend Continuation | Sustained CVD slope alignment + aggressor ratio > 1.2 | "good" or "proxy" |
| Reversal / CHOCH | Divergence + absorption confirmation | "good" preferred |
| Range Scalp | Neutral flow (imbalance < 30) + alternating imbalances | "proxy" acceptable |
| Breakout | Expanding imbalance (> 60) + aggressive flow dominance | "good" preferred |
| Micro-Scalp | M1 absorption + quick flow flip | "good" only (BTC) |

### BTC vs Non-BTC Strategy Selection

**BTC (High-Quality Data)**:
- Can use all strategies with full confidence
- Absorption zones available for precise entries
- CVD divergence available for reversal timing

**Non-BTC (Proxy Data)**:
- Prefer trend continuation and range scalp (less dependent on precise flow)
- Avoid micro-scalp (requires high-quality data)
- Use order flow as supporting evidence, not primary signal

---

## SESSION BEHAVIOUR OVERLAY

### Session-Specific Flow Patterns

| Session | Typical Flow Pattern | Interpretation |
|---------|----------------------|----------------|
| Asian | Low aggression, light liquidity | False CVD divergence common (ignore) |
| London Open | Volatility spike → traps | Absorption + reversal frequent |
| London | Sustained momentum | CVD + aggressor alignment matters |
| NY Open | Secondary expansion | Strongest aggressive flow |
| NY Late | Fade of dominant flow | Absorption zones strengthen |

**Rule**: During Asian session, reduce order flow confidence by 30% (low liquidity = unreliable proxy).

---

## OUTPUT REQUIREMENT (MANDATORY DISPLAY)

Each analysis that includes order flow data MUST explicitly state:

```
Order Flow Bias: [Buy / Sell / Neutral]
Data Quality: [good / proxy / limited / unavailable]
CVD: [value] (Slope: [up/down/flat])
Aggressor Ratio: [X.XX] (Buy/Sell pressure)
Imbalance Score: [0-100] ([direction])
[If BTC] CVD Divergence: [type, strength]
[If BTC] Absorption Zones: [count] detected
→ Interpretation: [summary sentence]
```

**Example Output**:

```
Order Flow Bias: Buy
Data Quality: proxy (reduced confidence)
CVD: +132.5 (Slope: up)
Aggressor Ratio: 1.25 (Buy pressure)
Imbalance Score: 45 (Buy-side)
→ Interpretation: Buy-side flow supports structure, but proxy data quality requires caution. CVD rising with price confirms bullish bias.
```

---

## SAFETY & VALIDATION

### Critical Rules

1. **Never infer order flow values** - use tool data only
2. **Always check `data_quality`** before interpretation
3. **Require minimum 2 metrics** to align for confidence
4. **Apply data quality multiplier** to all adjustments
5. **State data quality explicitly** in output

### Missing Field Handling

If a field is missing:
- Display all available fields
- Mark missing fields explicitly: "⚠️ FIELD MISSING: [field_name]"
- Reduce confidence accordingly
- Do not assume values

### Proxy Data Limitations

For non-BTC symbols with `data_quality: "proxy"`:
- Use as supporting evidence only
- Never use as primary signal
- Reduce all confidence adjustments by 50%
- Prefer structure and volatility signals over order flow

---

## BTC-SPECIFIC ENHANCEMENTS

### Using `moneybot.btc_order_flow_metrics` Tool

**When to Use**: For BTCUSD analysis, call this tool for enhanced data.

**Additional Fields Available**:
- `delta_volume.buy_volume` / `delta_volume.sell_volume` - True volume split
- `cvd_divergence.strength` - Calculated divergence (0.0-1.0)
- `cvd_divergence.type` - "bearish" | "bullish" | null
- `absorption_zones[]` - Array of price levels with absorption data

**Enhanced Interpretation**:

1. **True Delta Volume**:
   - Use `delta_volume.net_delta` instead of `aggressor_ratio`
   - More accurate than proxy calculation

2. **CVD Divergence**:
   - Use `cvd_divergence.strength` directly (no calculation needed)
   - Strength > 0.7 = strong reversal signal

3. **Absorption Zones**:
   - Each zone has: `price_level`, `strength`, `volume_absorbed`, `side`
   - Use `price_level` for precise entry/exit zones
   - Strength > 0.7 = high-probability reversal zone

---

## SUMMARY

This framework upgrades the Professional Reasoning Layer (PRL) by introducing order flow logic as a fifth analytical dimension.

### ✅ Enables:
- Micro-precision reversals (BTC)
- Early identification of traps (BTC)
- Dynamic confidence adjustment (all symbols)
- Institutional-style liquidity interpretation (BTC)
- Proxy-based flow confirmation (non-BTC)

### ⚠️ Limitations:
- Non-BTC symbols use proxy data (reduced confidence)
- Some fields not available for non-BTC (divergence, absorption zones)
- Requires data quality awareness
- Minimum 2 metrics alignment required

### 🎯 Best Use Cases:
- **BTC**: Full order flow analysis with all features
- **Non-BTC**: Supporting evidence for structure-based decisions
- **All Symbols**: Confidence adjustment and validation

**Tag**: ORDER_FLOW_LOGIC_V1.0  
**Version**: December 2025  
**Data Quality Awareness**: CRITICAL

