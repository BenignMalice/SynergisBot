# Micro-Scalp Regime Detection Explained

## How Micro-Scalp Regimes Map to the 4 Core Market Regimes

The micro-scalp system detects **3 specific regimes** that map to your 4 core market regimes:

| Micro-Scalp Regime | Maps To Core Regime | Description | Confidence Threshold |
|-------------------|---------------------|------------|---------------------|
| **VWAP Reversion** | **Ranging (Mean Reversion)** | Price deviated from VWAP, expecting mean reversion | **70%** |
| **Range Scalp** | **Ranging (Mean Reversion)** | Price in tight range, bouncing at edges | **55%** |
| **Balanced Zone** | **Compressing (Volatility Trap)** | Low volatility, equilibrium, compression before breakout | **65%** |
| **Edge Based** | **Volatile/Choppy** | Fallback when no clear regime detected | **60%** |

**Note:** The system doesn't explicitly detect "Trending" regime because micro-scalping focuses on mean reversion and compression setups, not trend following.

---

## Why Regime is UNKNOWN

The system returns **UNKNOWN** when **none of the 3 regimes meet their minimum confidence thresholds**:

```
VWAP Reversion: 0% (needs ≥70%)
Range Scalp: 0% (needs ≥55%)
Balanced Zone: 40% (needs ≥65%)
```

**Result:** All below thresholds → `UNKNOWN` → Falls back to `edge_based` strategy

---

## How Each Regime is Detected

### 1️⃣ VWAP Reversion (Threshold: 70%)

**What it detects:** Price has moved away from VWAP and is likely to revert

**Confidence Scoring:**
- **+40 points:** Price deviation ≥ 2.0 sigma from VWAP (or ≥0.5% for BTC, ≥0.2% for XAU)
- **+20 points:** Volume spike detected (1.3× average or Z-score > 1.5)
- **+20 points:** VWAP slope is flat (< 0.1× ATR normalized)
- **+20 points:** ATR(14) is stable (not dropping)

**Why it's 0% in your case:**
- Price is likely **too close to VWAP** (deviation < 2.0 sigma)
- OR no volume spike
- OR VWAP slope is too steep
- OR ATR is dropping

**Example conditions that would trigger:**
- BTC price at $94,000, VWAP at $93,500 → deviation = $500 → if VWAP std = $200, then 2.5 sigma ✅
- Volume spike (1.5× average) ✅
- VWAP slope flat ✅
- ATR stable ✅
- **Total: 100% confidence** → VWAP Reversion detected

---

### 2️⃣ Range Scalp (Threshold: 55%)

**What it detects:** Price is in a tight range and bouncing at edges

**Confidence Scoring:**
- **+30 points:** Price near range edge (within 0.5% of high or low)
- **+30 points:** Range has been respected ≥2 times (bounced off edges)
- **+20 points:** Bollinger Bands compressed (width < 2% of price)
- **+20 points:** M15 trend is NEUTRAL (not trending)

**Why it's 0% in your case:**
- **No range structure detected** (RangeBoundaryDetector found no range)
- OR price not near any range edge
- OR range too wide (width/ATR ratio ≥ 1.2)
- OR M15 is trending (not neutral)

**Example conditions that would trigger:**
- Range detected: High $94,200, Low $93,800 (width = $400)
- Current price at $94,150 (near high) ✅
- Range respected 3 times (bounced) ✅
- BB compressed ✅
- M15 trend neutral ✅
- **Total: 100% confidence** → Range Scalp detected

---

### 3️⃣ Balanced Zone (Threshold: 65%)

**What it detects:** Low volatility compression, equilibrium state, preparing for breakout

**Confidence Scoring:**
- **+30 points:** Bollinger Bands compressed (width < 2% of price)
- **+30 points:** Compression block detected (M1-M5 multi-timeframe compression)
- **+20 points:** ATR dropping (recent ATR < 80% of 14-period average)
- **+10 points:** Choppy liquidity detected (equal highs/lows pattern)
- **+10 points:** EMA(20) - VWAP distance < 0.1% (equilibrium)

**Why it's 40% in your case:**
- Likely has **BB compression (+30)** and **one other condition (+10)**
- But missing:
  - Compression block (M1-M5) ❌
  - OR ATR not dropping ❌
  - OR EMA-VWAP not in equilibrium ❌
- **Needs 65%** but only has **40%** → Not detected

**Example conditions that would trigger:**
- BB compressed (width = 1.5% of price) ✅
- Compression block on M1-M5 ✅
- ATR dropping (0.75× average) ✅
- EMA(20) = $94,000, VWAP = $94,005 (0.05% difference) ✅
- **Total: 100% confidence** → Balanced Zone detected

---

## Why Your Current Market Shows UNKNOWN

Based on your logs:
```
VWAP Reversion: 0% (threshold: 70%)
Range Scalp: 0% (threshold: 55%)
Balanced Zone: 40% (threshold: 65%)
```

**What this means:**
1. **VWAP Reversion (0%):** Price is **too close to VWAP** or missing volume/spike conditions
2. **Range Scalp (0%):** **No range structure detected** or price not near edges
3. **Balanced Zone (40%):** Has some compression but **missing key conditions** (compression block, ATR drop, or equilibrium)

**Current market state:** Likely in a **transitional/choppy state** that doesn't fit cleanly into any of the 3 micro-scalp regimes.

---

## How to See Why Each Regime Failed

The system now logs detailed reasons. Check your logs for messages like:

```
[BTCUSDc] ⚠️ Regime UNKNOWN - No regime met confidence thresholds: VWAP=0/70, Range=0/55, Balanced=40/65
[BTCUSDc]   VWAP Reversion: 0% (threshold: 70%)
[BTCUSDc]   Range Scalp: 0% (threshold: 55%)
[BTCUSDc]   Balanced Zone: 40% (threshold: 65%)
```

For more details, you can check the individual regime results in the snapshot:
- `regime_result['vwap_reversion_result']['reason']` - Why VWAP failed
- `regime_result['range_result']['reason']` - Why Range failed
- `regime_result['balanced_zone_result']` - What conditions Balanced Zone has

---

## When UNKNOWN is Expected

**UNKNOWN is normal and expected when:**
1. Market is in transition between regimes
2. Market is choppy/volatile (doesn't fit clean patterns)
3. Data is insufficient (not enough candles, missing indicators)
4. Market is trending strongly (micro-scalp doesn't detect trends)

**The system handles this gracefully:**
- Falls back to `edge_based` strategy
- Uses generic location filters and candle signals
- Still attempts to find micro-scalp setups, just without regime-specific optimizations

---

## Improving Regime Detection

If you want to see more regime detections, you could:

1. **Lower thresholds** (not recommended - increases false positives):
   ```json
   "strategy_confidence_thresholds": {
     "vwap_reversion": 60,  // was 70
     "range_scalp": 45,     // was 55
     "balanced_zone": 50    // was 65
   }
   ```

2. **Check why conditions are failing:**
   - VWAP: Is price close to VWAP? Check deviation
   - Range: Is a range structure being detected? Check RangeBoundaryDetector
   - Balanced: What's missing? Compression block? ATR drop? Equilibrium?

3. **Wait for market conditions to change:**
   - UNKNOWN is often correct - the market may genuinely be in a transitional state
   - The system will automatically detect regimes when conditions are met

---

## Summary

**Your current situation:**
- Market is in a **transitional/choppy state**
- None of the 3 micro-scalp regimes meet their thresholds
- System correctly identifies this as **UNKNOWN**
- Falls back to **edge_based** strategy (generic micro-scalp)

**This is working as designed.** The system is being conservative and only using regime-specific strategies when it's confident about the market state.

