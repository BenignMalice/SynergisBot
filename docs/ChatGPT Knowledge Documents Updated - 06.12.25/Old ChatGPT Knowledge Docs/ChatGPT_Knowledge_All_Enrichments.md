# 📊 Complete Enrichment System - Knowledge Document

**For:** MoneyBot Custom GPT  
**Last Updated:** November 1, 2025  
**Total Fields:** 37 (Institutional-Grade) + Advanced Pattern Detection (NEW!)

---

## 🎯 Overview

Your analysis includes **37 enrichment fields** from multiple data sources:
- **Binance** - Real-time 1-second streaming data (7 symbols)
- **MT5** - Broker execution + technical indicators
- **Advanced Indicators** - 11 advanced institutional indicators + **Candlestick Pattern Detection** ⭐ NEW
- **Order Flow** - Whale detection, book imbalance, tape reading
- **Yahoo Finance** - Macro context (DXY, VIX, US10Y)

---

## 📋 The 37 Enrichment Fields

### **🔹 Baseline (13 fields)**
Always included in every analysis:

1. **Price** - Current Binance price
2. **Price Trend (10s)** - RISING/FALLING/FLAT
3. **Price Change %** - Last 10 ticks
4. **Volume** - Current tick volume
5. **Volume Surge** - Detected/Not detected
6. **Momentum (10s)** - ±% movement
7. **Momentum Acceleration** - Speed of momentum change
8. **Divergence vs MT5** - Price difference
9. **Divergence %** - Percentage offset
10. **Last Candle Color** - Green/Red
11. **Last Candle Size** - Body size
12. **Wicks** - Upper/lower wick sizes
13. **Data Age** - Seconds since last tick

---

### **🔥 Top 5 - Phase 1 (5 fields)**

#### **14-18. Price Structure**
- **Structure Type:** HIGHER HIGH, HIGHER LOW, LOWER HIGH, LOWER LOW, EQUAL, CHOPPY
- **Consecutive Count:** How many in a row (3x = strong)
- **Strength:** Based on consistency

**What it means:**
- **HIGHER HIGH (3x)** = Strong uptrend, continuation likely
- **LOWER LOW (3x)** = Strong downtrend, continuation likely
- **CHOPPY** = No clear structure, avoid trading

**How to use:**
- ✅ Trade WITH structure (HH for longs, LL for shorts)
- ❌ Avoid CHOPPY or EQUAL (no clear direction)

---

#### **19-23. Volatility State**
- **State:** EXPANDING, CONTRACTING, STABLE
- **Change %:** Rate of expansion/contraction
- **Squeeze Duration:** How long contracting (seconds)

**What it means:**
- **EXPANDING** = Breakout in progress, momentum building
- **CONTRACTING** = Coiling, breakout imminent
- **Squeeze (20s+)** = High-probability breakout setup

**How to use:**
- ✅ Enter ON expansion or AFTER squeeze resolves
- ⏳ Wait during contraction (breakout pending)

---

#### **24-27. Momentum Consistency**
- **Score:** 0-100 (100 = all ticks same direction)
- **Quality:** EXCELLENT (90%+), GOOD (75-90%), FAIR (50-75%), POOR (<50%)
- **Consecutive Moves:** How many ticks in same direction

**What it means:**
- **EXCELLENT (92%)** = Clean, strong move, high confidence
- **CHOPPY (<50%)** = Indecisive, avoid trading

**How to use:**
- ✅ Trade only when 75%+ (GOOD or EXCELLENT)
- ❌ Skip if FAIR or POOR

---

#### **28-29. Spread Trend**
- **Trend:** NARROWING, WIDENING, STABLE
- **Choppiness:** 0-100 (0 = smooth, 100 = choppy)

**What it means:**
- **NARROWING** = Good liquidity, tight spreads
- **WIDENING** = Poor liquidity, execution risk
- **High Choppiness (>70)** = Erratic price action

**How to use:**
- ✅ Trade when NARROWING or STABLE
- ⚠️ Caution if WIDENING

---

#### **30-32. Micro Timeframe Alignment**
- **3s/10s/30s Direction:** BULLISH/BEARISH/NEUTRAL for each
- **Alignment Score:** 0-100
- **Strength:** STRONG (100%), MODERATE (67%), WEAK (<67%)

**What it means:**
- **STRONG (100%)** = All 3 timeframes agree, high-probability entry
- **WEAK** = Timeframes disagree, wait for alignment

**How to use:**
- ✅ Enter when 67%+ (MODERATE or STRONG)
- ⏳ Wait if WEAK or MISALIGNED

---

### **🚀 Phase 2A (6 fields)**

#### **33-36. Key Level Detection**
- **Price:** Exact level ($112,150)
- **Type:** Support or Resistance
- **Touch Count:** 2, 3, 4+ touches
- **Strength:** Weak (2 touches) or Strong (3+ touches)
- **Last Touch Ago:** Seconds since last hit

**What it means:**
- **4 touches = STRONG level** - High confidence for breakout/rejection
- **Fresh (<5s)** = Immediate reaction zone
- **Resistance broken** = Bullish, becomes support
- **Support broken** = Bearish, becomes resistance

**How to use:**
- ✅ **Breakout:** 3+ touches then break = execute
- ✅ **Rejection:** 3+ touches then reject = fade
- ❌ Avoid trading AT the level (wait for break/reject)

---

#### **37-38. Momentum Divergence**
- **Type:** BULLISH, BEARISH, NONE
- **Strength:** 0-100%

**What it means:**
- **BEARISH Divergence** = Price up, volume down = Exhaustion, reversal likely
- **BULLISH Divergence** = Price down, volume up = Accumulation, bounce likely
- **65%+ strength** = High-probability reversal

**How to use:**
- ⚠️ **BEARISH divergence on longs** = EXIT or don't enter
- ✅ **BULLISH divergence on oversold** = Enter long
- 🔄 **Mean reversion** signal (fade the move)

---

#### **39-41. Real-Time ATR**
- **Binance ATR:** Calculated from 1s ticks
- **MT5 ATR:** From MT5 indicator
- **Divergence %:** Difference between them
- **State:** HIGHER, LOWER, ALIGNED

**What it means:**
- **HIGHER (+12%)** = Broker feed lagging, volatility increasing
- **ALIGNED** = Feeds in sync
- **LOWER** = Volatility decreasing

**How to use:**
- ✅ **Use Binance ATR** for stop placement (more current)
- ⚠️ **Large divergence** = Feed desync, verify before trading

---

#### **42-44. Bollinger Bands**
- **Position:** OUTSIDE_UPPER, UPPER_BAND, MIDDLE, LOWER_BAND, OUTSIDE_LOWER
- **Width %:** Band width as % of price
- **Squeeze:** True/False (width <0.3%)

**What it means:**
- **OUTSIDE UPPER** = Overbought, mean reversion opportunity
- **OUTSIDE LOWER** = Oversold, bounce opportunity
- **SQUEEZE (<0.3%)** = Coiling, breakout imminent (80% probability)

**How to use:**
- 🔄 **Mean reversion:** Fade OUTSIDE moves
- 🔥 **Breakout:** Enter when squeeze RESOLVES
- ⏳ **During squeeze:** Wait for direction

---

#### **45-47. Move Speed**
- **Speed:** PARABOLIC, FAST, NORMAL, SLOW
- **Percentile:** 0-100 (95th+ = unusual)
- **Warning:** True/False

**What it means:**
- **PARABOLIC (96th percentile)** = Exhaustion, don't chase!
- **FAST (78th percentile)** = Strong momentum, valid
- **SLOW** = Weak move, wait for acceleration

**How to use:**
- ⚠️ **PARABOLIC + Warning** = DON'T ENTER (exhaustion imminent)
- ✅ **FAST without warning** = Valid momentum trade
- ❌ **SLOW** = Skip, weak setup

---

#### **48-50. Momentum-Volume Alignment**
- **Score:** 0-100 (% of momentum with volume)
- **Quality:** STRONG (75%+), MODERATE (50-75%), WEAK (<50%)
- **Confirmation:** True/False

**What it means:**
- **STRONG (88%)** = Volume backing the move, high confidence
- **WEAK (35%)** = No volume, fake move, reversal likely

**How to use:**
- ✅ **75%+ confirmation** = Valid move, trade it
- ⚠️ **<50%** = Weak move, fade or skip

---

### **💎 Phase 2B (7 fields)**

#### **51-53. Tick Frequency**
- **Ticks/sec:** Actual tick rate (1.0 = normal)
- **Activity Level:** VERY_HIGH, HIGH, NORMAL, LOW
- **Percentile:** 0-100

**What it means:**
- **VERY_HIGH (3.3/s)** = Active market, good liquidity
- **LOW (0.6/s)** = Inactive, poor liquidity, avoid trading

**How to use:**
- ✅ Trade during HIGH or VERY_HIGH activity
- ❌ **SKIP during LOW activity** (poor execution)

---

#### **54-56. Price Z-Score**
- **Z-Score:** Standard deviations from mean (±σ)
- **Extremity:** EXTREME_HIGH, HIGH, NORMAL, LOW, EXTREME_LOW
- **Signal:** OVERBOUGHT, OVERSOLD, NEUTRAL

**What it means:**
- **Z-Score >2.5** = EXTREME OVERBOUGHT, mean reversion likely (80% historical)
- **Z-Score <-2.5** = EXTREME OVERSOLD, bounce likely
- **Normal (-1.5 to +1.5)** = Neutral, no mean reversion signal

**How to use:**
- 🔄 **>2.5σ** = FADE (short overbought moves)
- 🔄 **<-2.5σ** = BUY (oversold bounces)
- ✅ Combine with other signals (Above R2, bearish pattern)

---

#### **57-59. Pivot Points**
- **Pivot (P), R1, R2, S1, S2:** Standard intraday levels
- **Position:** ABOVE_R2, ABOVE_R1, ABOVE_PIVOT, BELOW_PIVOT, BELOW_S1, BELOW_S2

**What it means:**
- **R1, R2** = Natural resistance (profit targets for longs)
- **S1, S2** = Natural support (profit targets for shorts)
- **ABOVE R2 / BELOW S2** = Overextended

**How to use:**
- 🎯 **Profit targets:** R1/R2 for longs, S1/S2 for shorts
- ⚠️ **Above R2/Below S2** = Mean reversion setup
- ✅ **Pivot = key intraday level** (watch for reactions)

---

#### **60-62. Tape Reading**
- **Aggressor:** BUYERS, SELLERS, BALANCED
- **Strength:** 0-100%
- **Dominance:** STRONG, MODERATE, WEAK

**What it means:**
- **BUYERS DOMINATING (85%)** = Institutional buying, continuation likely
- **SELLERS DOMINATING** = Institutional selling, weakness
- **BALANCED** = No clear direction, choppy

**How to use:**
- ✅ **STRONG dominance** = Trade WITH the aggressor
- ⏳ **BALANCED** = Wait for dominance
- 🔄 **Dominance SHIFT** = Potential reversal

---

#### **63-65. Liquidity Score**
- **Score:** 0-100
- **Quality:** EXCELLENT (85+), GOOD (70-85), FAIR (50-70), POOR (<50)
- **Execution Confidence:** HIGH, MEDIUM, LOW

**What it means:**
- **EXCELLENT (92)** = Tight spreads, good fills, safe to trade
- **POOR (38)** = Wide spreads, slippage risk, avoid

**How to use:**
- ✅ **85+ score** = Trade confidently
- ⚠️ **<50 score = SKIP** (execution risk too high)
- 📏 Adjust position size based on liquidity

---

#### **66-68. Time-of-Day Context**
- **Hour:** UTC hour (0-23)
- **Session:** ASIAN, LONDON, NY, OFF_HOURS
- **Volatility vs Typical:** HIGHER, NORMAL, LOWER

**What it means:**
- **NY (13:00-21:00 UTC)** = Highest volatility, best for breakouts
- **LONDON (08:00-16:00 UTC)** = Normal volatility, good trading
- **ASIAN (00:00-08:00 UTC)** = Lower volatility, range-bound
- **OFF_HOURS (21:00-00:00 UTC)** = Lowest activity, avoid trading

**How to use:**
- ✅ **NY/LONDON** = Best times to trade
- ⚠️ **OFF_HOURS = AVOID** (low liquidity)
- 📊 Adjust strategy: NY = breakouts, ASIAN = ranges

---

#### **69-71. Candle Patterns (Binance - Basic)**
- **Pattern:** DOJI, HAMMER, SHOOTING_STAR, ENGULFING_BULL, ENGULFING_BEAR, NONE
- **Confidence:** 0-100%
- **Direction:** BULLISH, BEARISH, NEUTRAL

**What it means:**
- **HAMMER (75%)** = Bullish reversal (long lower wick)
- **SHOOTING_STAR (75%)** = Bearish reversal (long upper wick)
- **DOJI (80%)** = Indecision, potential reversal
- **ENGULFING (85%)** = Strong reversal signal

**How to use:**
- ✅ **75%+ confidence** = Valid pattern, trade it
- 🔄 **Reversal patterns** = Fade previous move
- ⏳ **DOJI** = Wait for next candle confirmation

**⚠️ NOTE:** Basic Binance patterns are limited. For comprehensive pattern detection, use `moneybot.getAdvancedFeatures` to access:
- **Single-bar patterns:** Marubozu (bull/bear), Doji, Hammer, Shooting Star, Pin Bar (bull/bear)
- **Multi-bar patterns:** Bull/Bear Engulfing, Inside Bar, Outside Bar, Breakout Bar, Morning Star, Evening Star, Three White Soldiers, Three Black Crows
- **Pattern strength score & wick metrics:** For confirmation and confluence

**Data Path:** `advanced_features → features → M5/M15/H1 → candlestick_flags`, `pattern_flags`, `wick_metrics`, `pattern_strength`

---

### **📊 Advanced Pattern Detection (NEW - via getAdvancedFeatures)**

**Access via:** `moneybot.getAdvancedFeatures(symbol)` → `features → {timeframe} → pattern_data`

**Available Timeframes:** M5, M15, M30, H1, H4

#### **Single-Bar Patterns (candlestick_flags)**
- **marubozu_bull/bear:** Strong momentum candle with minimal wicks (body >80% of range)
- **doji:** Small body (<10% of range), large wicks (indecision/reversal)
- **hammer:** Long lower wick, small body near high (bullish reversal)
- **shooting_star:** Long upper wick, small body near low (bearish reversal)
- **pin_bar_bull/bear:** Long wick on one side (rejection at support/resistance)

#### **Multi-Bar Patterns (pattern_flags)**
- **bull_engulfing/bear_engulfing:** Current candle fully engulfs previous (strong reversal)
- **inside_bar:** Current candle inside previous range (consolidation, breakout pending)
- **outside_bar:** Current candle engulfs previous range (volatility expansion)
- **breakout_bar:** Range expansion candle (1.5x recent range)
- **morning_star:** 3-bar bullish reversal (bearish → small body → bullish)
- **evening_star:** 3-bar bearish reversal (bullish → small body → bearish)
- **three_white_soldiers:** 3 consecutive strong bullish candles (continuation)
- **three_black_crows:** 3 consecutive strong bearish candles (continuation)

#### **Pattern Analysis (wick_metrics)**
- **upper_wick_pct / lower_wick_pct:** Wick size as percentage of total range
- **body_pct:** Body size as percentage of total range
- **wick_asymmetry:** -1 to 1 (negative = lower wick dominant, positive = upper wick)
- **upper_wick_atr / lower_wick_atr:** Wick sizes in ATR units (for stop placement)

#### **Pattern Strength (pattern_strength)**
- **Score:** 0.0-1.0 (higher = stronger pattern)
- **Factors:** Body size, volume confirmation, trend alignment, volatility

**How to Use:**
- ✅ **Pattern + Level (OB/liquidity) + Indicators (RSI/MACD/ADX)** = High probability
- ✅ **Pattern strength >0.7** = Strong signal
- ✅ **Multi-timeframe confirmation** = M5 pattern + M15 alignment = Very high confidence
- ⚠️ **Pattern alone** = Lower confidence, require confluence
- 📊 **Use with:** Smart Pattern Triggers playbook for scalping strategies

**See:** `ChatGPT_Knowledge_Scalping_Strategies.md` for complete pattern-based trading strategies

---

### **🐋 Order Flow (6 fields)**

#### **72-77. Order Flow Analysis**
- **Signal:** BULLISH, BEARISH, NEUTRAL
- **Confidence:** 0-100%
- **Book Imbalance:** Bid/ask ratio
- **Whale Count:** Large orders detected
- **Pressure Side:** BUY, SELL, NEUTRAL
- **Liquidity Voids:** Count of thin zones

**What it means:**
- **Whale orders** = Institutional activity
- **Book imbalance >2.0** = Heavy bid or ask side
- **Liquidity voids** = Dangerous zones (rapid price movement)

**How to use:**
- ✅ **Whales + strong signal** = High conviction
- ⚠️ **Liquidity voids** = Avoid stops in these zones
- 📊 Pressure side confirms direction

---

## 🎯 **Decision Matrix**

### **STRONG SETUP (8+ Confirmations)**
```
✅ Structure: HIGHER HIGH (3x)
✅ Volatility: EXPANDING
✅ Momentum: EXCELLENT (90%+)
✅ Micro Alignment: STRONG (100%)
✅ Key Level: Broken (4 touches)
✅ Volume: STRONG (85%+)
✅ Activity: VERY_HIGH
✅ Liquidity: EXCELLENT (90+)
✅ Tape: BUYERS DOMINATING (80%+)
✅ Session: NY/LONDON
✅ No warnings

→ EXECUTE WITH CONFIDENCE
```

### **SKIP/WAIT (3+ Warnings)**
```
⚠️ PARABOLIC Move (96th percentile)
⚠️ BEARISH Divergence (65%+)
⚠️ Z-Score >2.5 (extreme overbought)
⚠️ Above R2 (overextended)
⚠️ Shooting Star pattern (75%+)
⚠️ LOW Activity (<0.8 ticks/s)
⚠️ POOR Liquidity (<50/100)
⚠️ OFF_HOURS Session

→ SKIP OR FADE (mean reversion)
```

### **MEAN REVERSION SETUP**
```
✅ Z-Score >2.5 (EXTREME OVERBOUGHT)
✅ Above R2 (overextended)
✅ BEARISH Divergence (60%+)
✅ Shooting Star (75%+)
✅ Weak Volume (<50%)

→ SHORT/FADE (high probability)
```

---

## 💡 **Usage Guidelines**

### **Always Display:**
1. Structure (if not CHOPPY)
2. Volatility State (if EXPANDING/CONTRACTING)
3. Momentum Quality (if EXCELLENT/CHOPPY)
4. Key Level (if 3+ touches)
5. Divergence (if detected)
6. PARABOLIC warning (if present)
7. Z-Score (if extreme ±2.5σ)
8. Liquidity (if POOR or EXCELLENT)
9. Session context
10. Warnings (any present)

### **Count Confirmations:**
- **8+ confirmations** = STRONG setup
- **5-7 confirmations** = MODERATE setup
- **<5 confirmations** = WEAK setup, wait

### **Count Warnings:**
- **3+ warnings** = SKIP or fade
- **1-2 warnings** = Caution, reduce size
- **0 warnings** = Green light

---

## 📊 **How Data Flows to You**

```
Binance WebSocket (1s ticks)
    ↓
37 Enrichments Calculated
    ↓
MT5 Data + Advanced Indicators + Pattern Detection ⭐ NEW
    ↓
Decision Engine
    ↓
ChatGPT Receives:
  - Full enrichment summary
  - Recommendation with confirmations
  - Warnings and cautions
  - Confidence score
  - Pattern detection (via getAdvancedFeatures)
```

**All 37 fields are AUTOMATICALLY included in every `moneybot.analyse_symbol` call.**

**Pattern Detection** is available via `moneybot.getAdvancedFeatures(symbol)`:
- Returns patterns for M5, M15, M30, H1, H4 timeframes
- Includes single-bar patterns, multi-bar patterns, wick metrics, pattern strength
- Use with Smart Pattern Triggers playbook for scalping strategies

You don't need to request enrichments separately - they're enriching the MT5 data before it reaches the decision engine!

---

**Last Updated:** November 1, 2025  
**Total Fields:** 37 + Advanced Pattern Detection | **Status:** Production Ready ✅  
**New:** Comprehensive candlestick pattern detection (17 patterns) via `getAdvancedFeatures`

