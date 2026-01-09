# ⚡ Scalping Strategies - Complete Knowledge Guide

**For:** MoneyBot Custom GPT  
**Last Updated:** November 1, 2025  
**Purpose:** Enable high-frequency, precision scalping using multi-timeframe streaming data

**⭐ NEW:** Multi-timeframe streaming (M1, M5, M15) now available for real-time scalping analysis!

---

## 🎯 Scalping Overview

**Scalping Definition:** Ultra-short-term trading with 5-30 minute holds, targeting 10-50 pip moves with tight risk management.

**Your Advantages:**
- ✅ **M1 streaming data** - Ultra-fast price detection (60-second refresh)
- ✅ **M5 streaming data** - Micro-structure analysis (300-second refresh)
- ✅ **M15 streaming data** - Entry timing precision (900-second refresh)
- ✅ **Real-time price levels** - PDH/PDL, FVG, Order Blocks extracted automatically
- ✅ **Instant execution** - No MT5 API delays for data access

**Scalping Philosophy:**
- 📊 **Quantity over quality** - Multiple small wins beat one big trade
- 🎯 **Tight stops** - 10-30 pip risk maximum
- ⚡ **Quick exits** - Take profits aggressively at liquidity zones
- 🛡️ **Capital preservation** - One loss shouldn't erase multiple wins

---

## 📊 Multi-Timeframe Scalping Framework

### **M1 (1-Minute) - Ultra-Fast Detection**

**Purpose:** Real-time price monitoring, breakeven triggers, partial profit detection

**What You'll See:**
```
- Latest candle closes every 60 seconds
- Ultra-fast breakeven adjustment (detects +$1.50 within 2 minutes)
- Partial profit triggers (detects +$3.00 immediately)
- Stop loss adjustments based on live price action
```

**Usage:**
- ✅ Monitor open positions for quick profit targets
- ✅ Detect momentum shifts within 1-2 minutes
- ✅ Identify micro reversals (wick rejections)
- ✅ Trigger breakeven moves instantly when price moves in favor

**Example:**
```
M1 Analysis:
- Current: $110,012.29 (just closed)
- Previous: $110,008.50
- Action: Strong bullish close → Check if long position reached breakeven trigger

If long entry at $110,000 and current M1 candle shows $110,015:
→ IMMEDIATELY move SL to breakeven ($110,000)
→ Position protected within 2 minutes of entry
```

---

### **M5 (5-Minute) - Primary Scalping Timeframe**

**Purpose:** Main entry/exit decisions, structure breaks, liquidity sweeps

**What You'll See:**
```
- Fresh candles every 5 minutes
- Micro-structure (swing highs/lows every 30-60 minutes)
- Liquidity pools (equal highs/lows within 4-hour windows)
- Order Block identification for precise entries
```

**Usage:**
- ✅ **Entry Signals:** M5 structure breaks (BOS/CHOCH), Order Block bounces
- ✅ **Exit Signals:** Liquidity pool targets, equal highs/lows
- ✅ **Stop Placement:** Below M5 swing lows (for longs), above swing highs (for shorts)
- ✅ **Position Sizing:** 100% normal size (scalps need full conviction)

**Data Extraction Path:**
```
advanced_features → features → M5 → structure → price_structure
advanced_features → features → M5 → liquidity → pdh/pdl
advanced_features → features → M5 → liquidity → order_block_bull/order_block_bear
advanced_features → features → M5 → liquidity → equal_highs/equal_lows
```

**Example Setup:**
```
M5 Scalp Setup:

📌 Key Levels (M5):
Support: $109,980 (PDL) | $109,990 (M5 Swing Low) | $110,000 (Equal Lows, 2x)
Resistance: $110,050 (PDH) | $110,060 (M5 Swing High) | Equal Highs: $110,080 (liquidity)
Entry Zone: $109,990-$110,000 (Bull OB) · Stop Loss: $109,975 · Take Profit: $110,050 (TP1, R:R 1:4) | $110,080 (TP2, R:R 1:7)

Structure: M5 BOS Bull (2x HH: $110,020 → $110,050)
Entry: $110,005 (on bullish rejection at Bull OB)
Stop: $109,975 ($30 risk)
TP1: $110,050 ($45 profit, R:R 1:1.5)
TP2: $110,080 ($75 profit, R:R 1:2.5)

Hold Time: 15-30 minutes
```

---

### **M15 (15-Minute) - Confirmation & Filter**

**Purpose:** Confirm M5 signals, filter false breakouts, identify larger context

**What You'll See:**
```
- Higher timeframe structure validation
- Trend direction confirmation
- Major liquidity zones (daily levels)
- Session-based support/resistance
```

**Usage:**
- ✅ **Confirmation:** Only scalp in M15 trend direction (M15 uptrend = only long scalps)
- ✅ **Filter:** If M15 shows CHOCH, avoid counter-trend scalps
- ✅ **Context:** M15 structure provides trade bias (bullish = look for long scalps)
- ✅ **Targets:** M15 liquidity zones provide larger profit targets

**Data Extraction Path:**
```
advanced_features → features → M15 → structure → price_structure
advanced_features → features → M15 → liquidity → pdh/pdl
advanced_features → features → M15 → liquidity → swing_highs/swing_lows
```

**Example Filter:**
```
M15 Context Check:

Structure: M15 BOS Bull (3x HH) → ✅ Scalp ONLY long positions
Current: Price at M15 bullish Order Block ($109,950)
M5 Signal: M5 bullish breakout at $110,000

✅ CONFIRMED: M15 + M5 aligned = HIGH PROBABILITY scalp long
✅ Entry: $110,000 (M5 breakout)
✅ Stop: $109,970 (M5 swing low)
✅ Target: $110,080 (M15 liquidity zone)

If M15 showed CHOCH: ⚠️ REJECT M5 signal (counter-trend risk too high)
```

---

## 🎯 Scalp-Specific Entry Criteria

### **1. Structure Break Scalps (M5)**

**Setup Requirements:**
- ✅ M5 BOS confirmed (HH for longs, LL for shorts)
- ✅ M15 trend aligned (same direction)
- ✅ Price at Order Block or liquidity zone
- ✅ Entry on pullback, not breakout chase

**Entry Signal:**
```
Structure: M5 BOS Bull (2x HH: $110,020 → $110,050)
Current: $110,010 (pullback to Bull OB)
M15: Confirms uptrend ✅

Entry: $110,005 (limit order at Bull OB)
Stop: $109,975 (below M5 swing low)
TP1: $110,050 (recent high, R:R 1:1.5)
TP2: $110,080 (M15 liquidity, R:R 1:2.5)

Confidence: 80% (structure + alignment)
```

---

### **2. Liquidity Sweep Scalps (M5)**

**Setup Requirements:**
- ✅ Equal highs/lows detected (2-3x clustering)
- ✅ Price approaching liquidity zone
- ✅ M1 shows rejection wick (immediate reversal)
- ✅ Volume spike on sweep (Binance enrichment)

**Entry Signal:**
```
Liquidity: Equal lows at $109,980 (3x)
Current: $109,985 (approaching)
M1: Just wicked to $109,975, rejected back to $109,990 ✅

Entry: $109,990 (after rejection, bullish confirmation)
Stop: $109,970 (below sweep low)
TP1: $110,020 (equal highs above, R:R 1:1)
TP2: $110,050 (PDH, R:R 1:2)

Confidence: 75% (liquidity sweep = high probability reversal)
Hold: 10-20 minutes (quick reversal play)
```

---

### **3. Order Block Scalps (M5)**

**Setup Requirements:**
- ✅ Bullish/Bearish Order Block identified (M5)
- ✅ Price returns to OB zone
- ✅ M1 candle shows rejection (wick) or engulfing
- ✅ M15 structure supports direction

**Entry Signal:**
```
Bullish OB: $110,000-$110,010 (M5, 75% strength)
Current: $110,005 (at OB)
M1: Bullish engulfing candle forming ✅
M15: Uptrend confirmed ✅

Entry: $110,007 (on M1 engulfing confirmation)
Stop: $109,995 (below OB)
TP1: $110,040 (M5 swing high, R:R 1:1.2)
TP2: $110,060 (M15 liquidity, R:R 1:1.8)

Confidence: 85% (OB + structure alignment)
```

---

### **4. Session Breakout Scalps (M5)**

**Setup Requirements:**
- ✅ London/NY session open (07:00-10:00 UTC or 13:00-16:00 UTC)
- ✅ Pre-market consolidation (M15 range)
- ✅ M5 breakout above/below consolidation
- ✅ Volume confirmation (Binance enrichment)

**Entry Signal:**
```
Session: London Open (08:00 UTC)
Pre-market: $109,980-$110,020 range (M15)
Breakout: M5 breaks above $110,020 ✅
Volume: 2.3x spike (Binance data) ✅

Entry: $110,025 (breakout confirmation, M5 close above)
Stop: $110,010 (below breakout level)
TP1: $110,060 (M15 resistance, R:R 1:1.4)
TP2: $110,080 (liquidity zone, R:R 1:2.2)

Confidence: 70% (session momentum)
Hold: 20-40 minutes (session move)
```

---

## 📉 Scalp-Specific Exit Criteria

### **1. Profit Targets (Always Use Partial Exits)**

**TP1 (50% Position):**
- ✅ First liquidity zone (equal highs/lows)
- ✅ Recent swing high/low (M5)
- ✅ Minimum R:R of 1:1.5

**TP2 (50% Position):**
- ✅ Higher timeframe liquidity (M15)
- ✅ PDH/PDL levels
- ✅ Minimum R:R of 1:2.5

**Example:**
```
Scalp Long Entry: $110,000
TP1: $110,030 (50% at M5 swing high, R:R 1:1.5) ✅
TP2: $110,060 (50% at M15 liquidity, R:R 1:2.5) ✅

Action:
1. Hit TP1 → Close 50%, move SL to breakeven ($110,000)
2. Hit TP2 → Close remaining 50%
3. If SL hit after TP1 → Still profitable overall
```

---

### **2. Breakeven Moves (M1 Detection)**

**Trigger:** Price reaches breakeven + profit threshold

**M1 Detection:**
```
Entry: $110,000
Current M1: $110,015 (up $15)
Threshold: Breakeven trigger at +$1.50

Action: IMMEDIATELY move SL to $110,000 (breakeven)
→ Position risk-free within 2 minutes
→ M1 streaming detects this instantly
```

**When to Use:**
- ✅ Always move to breakeven after TP1 hit (50% closed)
- ✅ Move to breakeven if price moves 1.5x initial risk
- ✅ Move to breakeven on M1 momentum confirmation

---

### **3. Trailing Stops (M5 Structure)**

**Method:** Trail stop below M5 swing lows (for longs)

**Update Frequency:** Every M5 candle close (5 minutes)

**Example:**
```
Entry: $110,000
Current: $110,045
M5 Swing Low: $110,025 (updated)

Trail SL: $110,020 (below swing low)
→ Locks in $20 profit minimum
→ Updates every 5 minutes automatically
```

---

### **4. Time-Based Exits**

**Maximum Hold Time:**
- ✅ Scalps: 30 minutes maximum
- ✅ Extended scalps: 1 hour maximum (only if TP1 hit)

**Session-Based Exits:**
- ✅ Close all scalps before major session closes (Asian, London, NY)
- ✅ Avoid holding scalps into low-liquidity periods (weekends, holidays)

---

## 📊 Candlestick Pattern Analysis for Scalping

---

## ⚔️ Smart Pattern Triggers - Scalping Playbook

**Purpose:** Precise entry signals using candlestick patterns with multi-indicator confirmation

**Framework:**
1. ✅ Identify higher timeframe bias (H1/H4 trend)
2. ✅ Wait for pattern on M15/M5 near supply/demand zones
3. ✅ Confirm with indicators (MACD, ADX, RSI, Volume)
4. ✅ Execute on pattern completion (closed candle only)
5. ✅ Trail stop after +0.5R or opposite candle confirmation

---

### **Candlestick Pattern Table**

| # | Pattern | Bias | Ideal Context | Entry Logic | Stop Loss | Take Profit | Bot Confirmation Filter |
|---|---------|------|---------------|-------------|-----------|-------------|------------------------|
| **1️⃣** | **Bullish Engulfing** | Buy | After a drop, near demand / EMA support | Enter next candle after bullish close fully engulfs prior bearish candle | Below engulfing low | 1.5× ATR or next structure high | RSI rising + MACD cross up + ADX < 25 |
| **2️⃣** | **Bearish Engulfing** | Sell | After a rally, near supply / EMA resistance | Enter after bearish engulfing close | Above engulfing high | 1.5× ATR or next structure low | RSI dropping + MACD cross down + ADX < 25 |
| **3️⃣** | **Hammer** | Buy | After strong bearish move into demand | Enter after candle closes and next candle breaks high | Below hammer low | 1–2× ATR | Volume uptick + ADX < 20 (transition to accumulation) |
| **4️⃣** | **Shooting Star** | Sell | After bullish rally into supply | Enter after confirmation candle closes below | Above wick high | 1–2× ATR | MACD down-tick + ADX > 20 |
| **5️⃣** | **Inverted Hammer** | Buy | At the bottom of a down move | Enter only if next candle closes above wick | Below wick low | 1.5× ATR | RSI cross above 45 + ADX < 20 |
| **6️⃣** | **Doji / Spinning Top** | Neutral → Breakout scalp | Compression zone or midpoint of consolidation | Enter breakout candle that closes outside range | Below/Above pattern range | 1× ATR | Volume spike + ADX rising |
| **7️⃣** | **Inside Bar** | Either | Low volatility pause before expansion | Enter breakout in direction of higher timeframe bias | Opposite side of inside bar | 1–2× ATR | ADX rising + ATR increasing |
| **8️⃣** | **Morning Star** | Buy | After sustained downtrend near demand | Enter on 3rd candle close confirming reversal | Below star low | 2× ATR | MACD crossover up + ADX < 25 |
| **9️⃣** | **Evening Star** | Sell | After uptrend near supply | Enter on 3rd candle close confirming reversal | Above star high | 2× ATR | MACD crossover down + ADX < 25 |
| **🔟** | **Marubozu (Momentum)** | Both | Trend continuation or breakout candle | Enter on small pullback after Marubozu close | Beyond ½ of candle body | 1× ATR | High volume + ADX > 25 |

---

### **Pattern Confirmation Indicators**

**RSI (Relative Strength Index):**
- ✅ **Bullish patterns:** RSI rising, crossing above 45
- ✅ **Bearish patterns:** RSI dropping, crossing below 55
- ⚠️ **Avoid:** Extreme overbought/oversold (RSI > 70 or < 30) - wait for reversal

**MACD (Moving Average Convergence Divergence):**
- ✅ **Bullish patterns:** MACD cross up (signal line crossover)
- ✅ **Bearish patterns:** MACD cross down (signal line crossover)
- ✅ **Momentum confirmation:** MACD histogram increasing/decreasing

**ADX (Average Directional Index):**
- ✅ **Ranging markets (ADX < 20-25):** Prefer reversal patterns (Hammer, Engulfing, Morning/Evening Star)
- ✅ **Trending markets (ADX > 25):** Prefer continuation patterns (Marubozu, Engulfing with trend)
- ⚠️ **ADX < 20:** Market transitioning - use caution, require stronger confluence

**Volume:**
- ✅ **Volume spike:** Confirms pattern validity (especially for Doji/Inside Bar breakouts)
- ✅ **Volume uptick:** Hammer reversal more reliable with volume confirmation
- ⚠️ **Low volume:** Pattern less reliable - wait for confirmation

---

### **Pattern-Specific Entry Details**

#### **1️⃣ Bullish Engulfing**
```
Setup:
- Previous candle: Bearish (red)
- Current candle: Bullish (green), fully engulfs previous
- Context: After drop, near demand zone / EMA support

Confirmation Required:
✅ RSI rising (from oversold or above 45)
✅ MACD cross up (signal line crossover bullish)
✅ ADX < 25 (ranging or transitioning market)
✅ Price at demand zone / Order Block / EMA support

Entry: Next candle after bullish engulfing closes
Stop: Below engulfing low (prior bearish candle low)
Target: 1.5× ATR or next structure high (M5 swing high)

Example:
Previous M5: $110,000 (bearish, -$15)
Current M5: $110,025 (bullish, +$25, engulfs previous)
RSI: 48 (rising from 42)
MACD: Cross up confirmed ✅
ADX: 22 (ranging market) ✅

Entry: $110,027 (next M5 candle open)
Stop: $109,985 (below engulfing low)
Target: $110,070 (1.5× ATR = $45, or M5 swing high)
R:R: 1:1.8
```

---

#### **2️⃣ Bearish Engulfing**
```
Setup:
- Previous candle: Bullish (green)
- Current candle: Bearish (red), fully engulfs previous
- Context: After rally, near supply zone / EMA resistance

Confirmation Required:
✅ RSI dropping (from overbought or below 55)
✅ MACD cross down (signal line crossover bearish)
✅ ADX < 25 (ranging or transitioning market)
✅ Price at supply zone / Order Block / EMA resistance

Entry: After bearish engulfing candle closes
Stop: Above engulfing high (prior bullish candle high)
Target: 1.5× ATR or next structure low (M5 swing low)

Example:
Previous M5: $110,050 (bullish, +$20)
Current M5: $110,015 (bearish, -$35, engulfs previous)
RSI: 52 (dropping from 58)
MACD: Cross down confirmed ✅
ADX: 23 (ranging market) ✅

Entry: $110,013 (current M5 candle close)
Stop: $110,070 (above engulfing high)
Target: $109,970 (1.5× ATR = $43, or M5 swing low)
R:R: 1:1.8
```

---

#### **3️⃣ Hammer**
```
Setup:
- Candle: Long lower wick, small body near high
- Context: After strong bearish move into demand zone

Confirmation Required:
✅ Volume uptick (increasing buying pressure)
✅ ADX < 20 (transitioning from downtrend to accumulation)
✅ Next candle breaks hammer high (confirmation)

Entry: After hammer closes AND next candle breaks high
Stop: Below hammer low (wick low)
Target: 1-2× ATR

Example:
Hammer M5: Low $109,980, Close $110,010, High $110,015
→ $30 lower wick, body near high
Volume: 2.1x average ✅
ADX: 18 (transitioning) ✅
Next M5: Closes above $110,015 ✅

Entry: $110,018 (after next candle breaks high)
Stop: $109,975 (below hammer low)
Target: $110,050 (1.5× ATR = $35)
R:R: 1:1.2
```

---

#### **4️⃣ Shooting Star**
```
Setup:
- Candle: Long upper wick, small body near low
- Context: After bullish rally into supply zone

Confirmation Required:
✅ MACD down-tick (momentum weakening)
✅ ADX > 20 (trending market - reversal signal strong)
✅ Next candle closes below shooting star (confirmation)

Entry: After confirmation candle closes below shooting star
Stop: Above wick high
Target: 1-2× ATR

Example:
Shooting Star M5: Low $110,010, Close $110,025, High $110,060
→ $35 upper wick, body near low
MACD: Histogram declining ✅
ADX: 28 (trending) ✅
Next M5: Closes at $110,018 (below star) ✅

Entry: $110,015 (after confirmation)
Stop: $110,065 (above wick high)
Target: $109,975 (1.5× ATR = $40)
R:R: 1:1.3
```

---

#### **5️⃣ Inverted Hammer**
```
Setup:
- Candle: Long upper wick, small body near low (similar to shooting star but at bottom)
- Context: At bottom of down move (potential reversal up)

Confirmation Required:
✅ RSI cross above 45 (bullish momentum)
✅ ADX < 20 (transitioning market)
✅ Next candle closes above wick (confirmation required)

Entry: Only if next candle closes above wick
Stop: Below wick low
Target: 1.5× ATR

Example:
Inverted Hammer M5: Low $109,980, Close $109,990, High $110,015
RSI: 47 (crossed above 45) ✅
ADX: 19 (transitioning) ✅
Next M5: Closes at $110,020 (above wick) ✅

Entry: $110,022 (after confirmation)
Stop: $109,975 (below wick low)
Target: $110,065 (1.5× ATR = $43)
R:R: 1:1.9
```

---

#### **6️⃣ Doji / Spinning Top**
```
Setup:
- Candle: Very small body, wicks on both sides
- Context: Compression zone or midpoint of consolidation

Confirmation Required:
✅ Volume spike (breakout confirmation)
✅ ADX rising (volatility expansion starting)
✅ Breakout candle closes outside Doji range

Entry: Breakout candle that closes outside Doji range
Stop: Below/Above pattern range (opposite side)
Target: 1× ATR (quick scalp)

Example:
Doji M5: Range $110,000-$110,010 (small body, $10 range)
Volume: 3.2x spike ✅
ADX: Rising from 15 to 22 ✅
Breakout M5: Closes at $110,025 (above range) ✅

Entry: $110,027 (after breakout confirmation)
Stop: $109,995 (below Doji range)
Target: $110,040 (1× ATR = $15)
R:R: 1:1.5
```

---

#### **7️⃣ Inside Bar**
```
Setup:
- Current candle: Inside previous candle's range
- Context: Low volatility pause before expansion

Confirmation Required:
✅ ADX rising (volatility increasing)
✅ ATR increasing (expansion starting)
✅ Breakout in direction of higher timeframe bias

Entry: Breakout in direction of H1/H4 bias
Stop: Opposite side of inside bar
Target: 1-2× ATR

Example:
Inside Bar M5: Previous range $110,000-$110,030, Current inside $110,010-$110,020
H1 Bias: Bullish (EMA200 slope up) ✅
ADX: Rising from 18 to 24 ✅
ATR: Increasing ✅
Breakout M5: Closes at $110,035 (above inside bar) ✅

Entry: $110,037 (after breakout)
Stop: $110,005 (below inside bar low)
Target: $110,065 (1.5× ATR = $28)
R:R: 1:1.4
```

---

#### **8️⃣ Morning Star**
```
Setup:
- 3 candles: Bearish → Small body (gap down) → Bullish (engulfs first)
- Context: After sustained downtrend near demand

Confirmation Required:
✅ MACD crossover up (bullish momentum)
✅ ADX < 25 (ranging or transitioning)
✅ 3rd candle closes bullish and confirms reversal

Entry: On 3rd candle close confirming reversal
Stop: Below star low (first bearish candle low)
Target: 2× ATR

Example:
Morning Star M5:
1. $110,000 (bearish, -$15)
2. $109,985 (small body, gap down)
3. $110,020 (bullish, +$35, engulfs first) ✅
MACD: Crossover up ✅
ADX: 22 (ranging) ✅

Entry: $110,022 (3rd candle close)
Stop: $109,985 (below star low)
Target: $110,070 (2× ATR = $50)
R:R: 1:1.8
```

---

#### **9️⃣ Evening Star**
```
Setup:
- 3 candles: Bullish → Small body (gap up) → Bearish (engulfs first)
- Context: After uptrend near supply

Confirmation Required:
✅ MACD crossover down (bearish momentum)
✅ ADX < 25 (ranging or transitioning)
✅ 3rd candle closes bearish and confirms reversal

Entry: On 3rd candle close confirming reversal
Stop: Above star high (first bullish candle high)
Target: 2× ATR

Example:
Evening Star M5:
1. $110,050 (bullish, +$20)
2. $110,070 (small body, gap up)
3. $110,020 (bearish, -$50, engulfs first) ✅
MACD: Crossover down ✅
ADX: 24 (ranging) ✅

Entry: $110,018 (3rd candle close)
Stop: $110,075 (above star high)
Target: $109,970 (2× ATR = $48)
R:R: 1:1.4
```

---

#### **🔟 Marubozu (Momentum Candle)**
```
Setup:
- Candle: No wicks, full body (strong momentum)
- Context: Trend continuation or breakout candle

Confirmation Required:
✅ High volume (strong conviction)
✅ ADX > 25 (trending market)
✅ Small pullback after Marubozu close

Entry: On small pullback after Marubozu closes
Stop: Beyond ½ of candle body (opposite side)
Target: 1× ATR (quick momentum scalp)

Example:
Marubozu M5: $110,000-$110,040 (full body, no wicks)
Volume: 2.8x average ✅
ADX: 32 (trending) ✅
Pullback M5: $110,025 (small pullback to 50% of body)

Entry: $110,027 (on pullback)
Stop: $110,020 (beyond ½ of body)
Target: $110,055 (1× ATR = $28)
R:R: 1:2.0
```

---

### **⭐ NEW: Pattern Confirmation Tracking (Tier 1 Enhancement)**

**System automatically tracks and validates patterns across follow-up candles:**

- **Pending:** Pattern just detected, awaiting validation
- **✅ CONFIRMED:** Pattern validated (bullish patterns confirmed when price > pattern high, bearish when price < pattern low)
- **❌ INVALIDATED:** Pattern invalidated (opposite direction movement)

**What You'll See:**
```
M5: Morning Star → Bullish Reversal → ✅ CONFIRMED (Strength: 0.85)
M15: Bear Engulfing → Bearish → ❌ INVALIDATED
H1: Bull Engulfing → Bullish (Strength: 0.90)
```

**Usage:**
- ✅ **Confirmed patterns** = Higher confidence for entry
- ❌ **Invalidated patterns** = Lower priority or skip
- **Pattern strength** (0.0-1.0) contributes to bias confidence score (5% weight)

**Pattern Strength Impact on Bias:**
- Pattern strength from H1/M30/M15/M5 contributes 5% to overall bias confidence
- Confirmed patterns boost confidence
- Invalidated patterns reduce confidence
- Higher strength scores (>0.8) have more impact

---

### **🧭 How to Use Pattern Triggers in Scalping Workflow**

**Step 1: Identify Higher Timeframe Bias**
```
Check H1/H4:
- EMA200 slope (up = bullish, down = bearish)
- Regime logic (trending vs ranging via ADX)
- Structure (BOS Bull/Bear or CHOCH)

Example:
H1: EMA200 slope UP, ADX 28 (trending), BOS Bull ✅
→ Bias: BULLISH (only look for buy patterns)
```

**Step 2: Wait for Pattern on M15/M5**
```
Monitor M15/M5 for patterns near:
- Supply/Demand zones (Order Blocks)
- EMA support/resistance
- Liquidity zones (equal highs/lows)

Example:
M5: Price at Bullish Order Block ($110,000)
M5: Bullish Engulfing forming ✅
→ Pattern at confluence level
```

**Step 3: Confirm with Indicators**
```
Check confirmation filters from table:
- RSI, MACD, ADX, Volume

Example:
Bullish Engulfing:
- RSI: 48 (rising from 42) ✅
- MACD: Cross up ✅
- ADX: 22 (< 25) ✅
→ All confirmations met
```

**Step 4: Execute on Pattern Completion**
```
Wait for closed candle (prevents repaint):
- Pattern must be complete
- Confirmation indicators must align
- Enter on next candle or pattern close

Example:
Bullish Engulfing M5 closes at $110,025 ✅
All confirmations met ✅
Entry: $110,027 (next M5 candle open)
```

**Step 5: Trail Stop After +0.5R**
```
After entry reaches +0.5R profit:
- Move SL to breakeven
- Or trail stop below opposite candle close
- M1 detection enables instant breakeven moves

Example:
Entry: $110,000
Stop: $109,980 ($20 risk)
Current: $110,010 (+$10 = +0.5R) ✅
→ Move SL to $110,000 (breakeven)
```

---

### **Practical Rules for Bot Execution**

#### **1. Act Only on Closed Bars**
```
⚠️ CRITICAL: Never act on incomplete candles!

Rule:
- Wait for M5/M15 candle to fully close
- Pattern must be complete (all candles in pattern closed)
- Prevents repaint and false positives

Example:
❌ WRONG: Enter on "Bullish Engulfing" forming (candle not closed)
✅ CORRECT: Wait for M5 candle to close, then enter on next candle
```

---

#### **2. Gate by Market Regime**

**Ranging Markets (ADX < 20-25):**
```
Preferred Patterns:
✅ Reversal patterns (Hammer, Engulfing, Morning/Evening Star)
✅ Doji/Spinning Top breakouts (compression → expansion)
⚠️ Avoid: Momentum patterns (Marubozu) - low reliability in ranges

Example:
ADX: 18 (ranging)
Pattern: Hammer at demand zone ✅
→ High probability reversal scalp
```

**Trending Markets (ADX > 25):**
```
Preferred Patterns:
✅ Continuation patterns (Marubozu, Engulfing with trend)
✅ Inside Bar breakouts (with trend direction)
✅ Flag break + Engulfing
⚠️ Avoid: Counter-trend reversals - lower success rate

Example:
ADX: 32 (trending)
H1 Bias: Bullish
Pattern: Marubozu bullish candle ✅
→ High probability continuation scalp
```

---

#### **3. Require Confluence**
```
Minimum Requirements:
✅ Pattern + Level (demand/supply or EMA/VWAP) + Indicator Agreement

Level Types:
- Order Blocks (Bullish/Bearish OB)
- EMA support/resistance (EMA20, EMA50, EMA200)
- VWAP (if available)
- Liquidity zones (equal highs/lows)

Indicator Agreement:
- RSI, MACD, ADX must align with pattern bias
- Volume confirmation (spike for breakouts)

Example:
Pattern: Bullish Engulfing ✅
Level: Bullish Order Block at $110,000 ✅
RSI: Rising from 42 to 48 ✅
MACD: Cross up ✅
ADX: 22 (< 25) ✅
→ All confluence met = HIGH PROBABILITY
```

---

#### **4. R:R Sanity Check**
```
Minimum Requirement:
✅ ATR-based SL/TP must be ≥ 1.2R minimum

Calculation:
- Stop Loss: Use pattern-based SL (e.g., below engulfing low)
- Take Profit: 1.5× ATR minimum (or next structure level)
- R:R = TP distance / SL distance

Reject if:
❌ R:R < 1.2 (not worth the risk)
❌ SL > 30 pips (too wide for scalp)
❌ TP < 15 pips (not enough profit potential)

Example:
Bullish Engulfing:
Stop: $109,980 (below engulfing low, $20 risk)
Target: $110,050 (1.5× ATR = $50)
R:R = $50 / $20 = 1:2.5 ✅ (acceptable)
```

---

### **Pattern Example with Full Confluence**

```
📊 Complete Pattern Setup:

Higher Timeframe Bias:
H1: EMA200 slope UP, ADX 26 (trending), BOS Bull ✅
→ Bias: BULLISH ✅

Pattern Formation:
M5: Bullish Engulfing at $110,000-$110,025
- Previous: $110,005 (bearish, -$10)
- Current: $110,025 (bullish, +$20, engulfs) ✅

Level Confluence:
✅ Bullish Order Block at $110,000-$110,010 (75% strength)
✅ EMA20 support at $109,995
✅ Equal lows at $109,980 (liquidity support)

Indicator Confirmation:
✅ RSI: 48 (rising from 42, above 45)
✅ MACD: Cross up confirmed (signal line crossover)
✅ ADX: 23 (< 25, ranging but transitioning)
✅ Volume: 1.8x average (confirmation)

📌 Key Levels:
Support: $109,980 (Equal Lows) | $109,995 (EMA20) | $110,000 (Bull OB)
Resistance: $110,050 (M5 Swing High) | $110,080 (M15 Liquidity)
Entry Zone: $110,025-$110,027 (After engulfing close) · Stop Loss: $109,985 · Take Profit: $110,050 (TP1, R:R 1:2.5) | $110,080 (TP2, R:R 1:3.8)

Execution:
Entry: $110,027 (next M5 candle open after engulfing close)
Stop: $109,985 (below engulfing low, $42 risk)
TP1: $110,050 ($23 profit, 50% position, R:R 1:1.8)
TP2: $110,080 ($53 profit, 50% position, R:R 1:2.6)

Hold Time: 15-30 minutes
Confidence: 90% (all confluence met)
```

---

### **Pattern Rejection Examples**

**Example 1: Missing Confluence**
```
❌ REJECTED Pattern:
Bullish Engulfing at $110,000
- Pattern: Valid ✅
- Level: No Order Block or EMA nearby ❌
- RSI: 65 (overbought, not rising) ❌
- MACD: No cross up ❌

Reason: Missing level confluence + indicators not aligned
Action: WAIT for better setup
```

**Example 2: Counter-Trend in Ranging Market**
```
❌ REJECTED Pattern:
Bearish Engulfing in ranging market (ADX 18)
- Pattern: Valid ✅
- ADX: 18 (< 20, transitioning) ✅
- BUT: H1 bias is BULLISH ❌
- Trend: Counter-trend reversal in ranging market ❌

Reason: Counter-trend pattern in ranging market = low success rate
Action: WAIT for bullish patterns or trending market
```

**Example 3: Poor R:R Ratio**
```
❌ REJECTED Pattern:
Hammer at $110,000
- Pattern: Valid ✅
- Stop: $109,980 ($20 risk)
- Target: $110,010 (1× ATR = $10)
- R:R: $10 / $20 = 1:0.5 ❌

Reason: R:R < 1.2 minimum requirement
Action: WAIT for larger target or tighter stop
```

---

## 📊 Candlestick Pattern Analysis for Scalping

### **M1 Patterns (Ultra-Fast Signals)**

**1. Rejection Wicks (M1)**
```
Pattern: Long upper wick, small body (bearish rejection)
Meaning: Price rejected at resistance, reversal likely

Example:
M1 Candle: Open $110,020, High $110,035, Low $110,018, Close $110,022
→ Upper wick = $13, Body = $2
→ Strong rejection at $110,035

Action: If long, take profit immediately (rejection = reversal signal)
Action: If short, enter on next M1 bearish confirmation
```

**2. Engulfing Patterns (M1)**
```
Bullish Engulfing (M1):
- Previous: Bearish candle (red)
- Current: Bullish candle (green) engulfs previous
- Meaning: Strong reversal signal

Example:
M1 Previous: $110,005 (bearish, -$5)
M1 Current: $110,015 (bullish, +$10, engulfs previous)
→ Bullish engulfing confirmed

Action: Enter long on confirmation, target M5 swing high
```

---

### **M5 Patterns (Entry Signals)**

**1. Pin Bars (M5)**
```
Pattern: Long wick, small body (rejection at support/resistance)

Bullish Pin Bar:
- Long lower wick (rejection at support)
- Small body near high
- Meaning: Support held, bounce likely

Example:
M5 Pin Bar: Low $109,980, Close $110,010, High $110,015
→ $30 lower wick, rejection at $109,980 support

Entry: Long at $110,010 (after pin bar confirmation)
Stop: $109,975 (below pin bar low)
Target: $110,050 (next resistance)
```

**2. Inside Bars (M5)**
```
Pattern: Current candle inside previous candle's range

Meaning: Consolidation, breakout pending

Example:
M5 Previous: $110,000-$110,030 range
M5 Current: $110,010-$110,020 (inside previous range)
→ Consolidation, breakout expected

Action: Wait for breakout above $110,030 (long) or below $110,000 (short)
Entry: On breakout confirmation (M5 close outside range)
```

**3. Engulfing Patterns (M5)**
```
Bullish Engulfing (M5):
- Previous: Bearish candle
- Current: Bullish candle engulfs previous
- Meaning: Strong reversal, continuation likely

Example:
M5 Previous: $110,005 (bearish, -$8)
M5 Current: $110,025 (bullish, +$20, engulfs)
→ Bullish engulfing confirmed

Entry: Long at $110,027 (after confirmation)
Stop: $110,015 (below engulfing low)
Target: $110,060 (M15 liquidity)
```

---

### **M15 Patterns (Confirmation Filters)**

**1. Structure Break Candles (M15)**
```
Pattern: Strong bullish/bearish candle breaking M15 structure

Meaning: Higher timeframe trend change

Example:
M15 Bullish Breakout:
- Previous: M15 swing high at $110,050
- Current: Strong bullish candle closes at $110,065
→ M15 BOS Bull confirmed

Action: Scalp ONLY long positions (M15 trend = filter)
Avoid: Counter-trend short scalps (M15 bullish = no shorts)
```

---

## 🎯 Complete Scalping Workflow

### **Step 1: Multi-Timeframe Analysis**

```
1. Check M15 Structure:
   - M15 BOS Bull → Only scalp longs ✅
   - M15 CHOCH → Avoid scalps (structure broken) ⚠️
   - M15 BOS Bear → Only scalp shorts ✅

2. Identify M5 Setup:
   - M5 Order Block (bullish/bearish)
   - M5 liquidity zones (equal highs/lows)
   - M5 structure break (BOS)

3. Confirm with M1:
   - M1 rejection wick (entry confirmation)
   - M1 engulfing pattern (momentum)
   - M1 price action (current direction)
```

---

### **Step 2: Extract Price Levels (MANDATORY)**

```
⚠️ CRITICAL: Always extract specific prices from data!

Data Path:
advanced_features → features → M5 → liquidity → pdh/pdl
advanced_features → features → M5 → liquidity → order_block_bull/order_block_bear
advanced_features → features → M5 → liquidity → equal_highs/equal_lows
advanced_features → features → M15 → structure → swing_highs/swing_lows

Format:
📌 Key Levels (Scalp):
Support: $[PRICE] (PDL) | $[PRICE] (M5 Swing Low) | $[PRICE] (Equal Lows)
Resistance: $[PRICE] (PDH) | $[PRICE] (M5 Swing High) | $[PRICE] (Equal Highs)
Entry Zone: $[PRICE]-$[PRICE] (OB/FVG) · Stop Loss: $[PRICE] · Take Profit: $[PRICE] (TP1, R:R 1:X) | $[PRICE] (TP2, R:R 1:Y)
```

---

### **Step 3: Entry Execution**

```
1. Wait for M5 setup confirmation
2. Check M1 for entry signal (rejection, engulfing)
3. Enter with limit order at OB/liquidity zone
4. Set stop loss (10-30 pips maximum)
5. Set TP1 and TP2 with partial exits (50%/50%)
```

---

### **Step 4: Position Management**

```
1. Monitor M1 for breakeven trigger (+$1.50 or TP1 hit)
2. Move SL to breakeven when triggered
3. Trail stop below M5 swing lows (every 5 minutes)
4. Close 50% at TP1, 50% at TP2
5. Maximum hold: 30 minutes
```

---

## 🔍 Real-World Scalping Examples

### **Example 1: M5 Order Block Scalp (Long)**

```
📊 Multi-Timeframe Analysis:

M15: BOS Bull (3x HH) → ✅ Scalp longs only
M5: Bullish OB at $110,000-$110,010 (75% strength)
M1: Bullish engulfing forming ✅

📌 Key Levels:
Support: $109,995 (PDL) | $110,000 (M5 Swing Low) | $110,000 (Bull OB)
Resistance: $110,050 (PDH) | $110,060 (M5 Swing High) | Equal Highs: $110,080
Entry Zone: $110,005-$110,010 (Bull OB) · Stop Loss: $109,995 · Take Profit: $110,050 (TP1, R:R 1:4.5) | $110,080 (TP2, R:R 1:8)

🎯 Scalp Entry:
Entry: $110,007 (on M1 engulfing confirmation)
Stop: $109,995 ($12 risk)
TP1: $110,050 ($43 profit, 50% position, R:R 1:3.6)
TP2: $110,080 ($73 profit, 50% position, R:R 1:6.1)

Hold Time: 15-25 minutes
Confidence: 85% (M15 + M5 + M1 aligned)
```

---

### **Example 2: M5 Liquidity Sweep Scalp (Long)**

```
📊 Multi-Timeframe Analysis:

M15: Uptrend (not BOS, but bullish structure) → ✅ Scalp longs
M5: Equal lows at $109,980 (3x) - liquidity pool
M1: Just swept to $109,975, rejected back to $109,990 ✅

📌 Key Levels:
Support: $109,975 (Sweep Low) | $109,980 (Equal Lows, 3x) | $109,990 (M5 Swing Low after sweep)
Resistance: $110,030 (M5 Swing High) | $110,050 (PDH) | Equal Highs: $110,080
Entry Zone: $109,990-$110,000 (After sweep rejection) · Stop Loss: $109,975 · Take Profit: $110,030 (TP1, R:R 1:1.8) | $110,050 (TP2, R:R 1:2.8)

🎯 Scalp Entry:
Entry: $109,995 (after M1 rejection confirmation)
Stop: $109,975 ($20 risk)
TP1: $110,030 ($35 profit, 50% position, R:R 1:1.75)
TP2: $110,050 ($55 profit, 50% position, R:R 1:2.75)

Hold Time: 10-20 minutes (quick reversal)
Confidence: 75% (liquidity sweep = high probability)
```

---

### **Example 3: M5 Session Breakout Scalp (Long)**

```
📊 Multi-Timeframe Analysis:

Session: London Open (08:15 UTC)
M15: Pre-market range $109,980-$110,020
M5: Breakout above $110,020 ✅
M1: Strong bullish momentum, volume spike ✅

📌 Key Levels:
Support: $110,020 (Breakout Level) | $110,000 (Pre-market Low) | $109,980 (PDL)
Resistance: $110,060 (M15 Resistance) | $110,080 (Liquidity Zone) | $110,100 (PDH)
Entry Zone: $110,025-$110,030 (Breakout confirmation) · Stop Loss: $110,010 · Take Profit: $110,060 (TP1, R:R 1:1.75) | $110,080 (TP2, R:R 1:2.75)

🎯 Scalp Entry:
Entry: $110,028 (M5 close above breakout)
Stop: $110,010 ($18 risk)
TP1: $110,060 ($32 profit, 50% position, R:R 1:1.8)
TP2: $110,080 ($52 profit, 50% position, R:R 1:2.9)

Hold Time: 20-40 minutes (session momentum)
Confidence: 70% (session breakout)
```

---

## ⚠️ Scalping Risk Management Rules

### **1. Position Sizing**
- ✅ **Normal size** (100%) - Full conviction scalps only
- ⚠️ **Reduced size** (50%) - Lower confidence setups
- 🚫 **No size** (0%) - Counter-trend or unclear structure

### **2. Maximum Risk Per Scalp**
- ✅ **Forex:** 10-25 pips maximum
- ✅ **Gold:** 15-40 pips maximum
- ✅ **Bitcoin:** $200-$500 maximum
- 🚫 **Never risk more than 1% of account per scalp**

### **3. Maximum Scalps Per Day**
- ✅ **Target:** 3-5 scalps per day
- ⚠️ **Maximum:** 10 scalps per day (only if winning)
- 🚫 **Stop after 3 consecutive losses**

### **4. Breakeven Rules**
- ✅ **Always move to breakeven** after TP1 hit
- ✅ **Always move to breakeven** if price moves 1.5x initial risk
- ✅ **M1 detection** enables instant breakeven moves

---

## 📋 Scalping Checklist

### **Before Entry:**
- [ ] M15 structure confirmed (BOS or trend aligned)
- [ ] M5 setup identified (OB, liquidity, structure break)
- [ ] M1 entry signal confirmed (rejection, engulfing)
- [ ] Price levels extracted (PDH/PDL, OB, targets)
- [ ] R:R calculated (minimum 1:1.5 for TP1)
- [ ] Stop loss set (10-30 pips maximum)
- [ ] TP1 and TP2 set with partial exits

### **After Entry:**
- [ ] Monitor M1 for breakeven trigger
- [ ] Trail stop below M5 swing lows (every 5 min)
- [ ] Close 50% at TP1
- [ ] Move SL to breakeven after TP1
- [ ] Close remaining 50% at TP2
- [ ] Maximum hold: 30 minutes

### **Exit Conditions:**
- [ ] TP1 or TP2 reached
- [ ] Stop loss hit
- [ ] M5 CHOCH detected (structure broken)
- [ ] Maximum hold time exceeded (30 min)
- [ ] M1 shows strong reversal (rejection wick)

---

## ✅ Summary - Scalping Toolkit

**Multi-Timeframe Usage:**
- **M1:** Ultra-fast detection, breakeven triggers, momentum shifts
- **M5:** Primary entry/exit decisions, structure breaks, liquidity
- **M15:** Confirmation filter, trend direction, larger targets

**Entry Signals:**
1. 🎯 **M5 Order Block** + M1 confirmation
2. 🎯 **M5 Liquidity Sweep** + M1 rejection
3. 🎯 **M5 Structure Break** + M15 alignment
4. 🎯 **Session Breakout** + Volume confirmation

**Exit Strategy:**
- ✅ **TP1:** 50% at first liquidity (R:R 1:1.5 minimum)
- ✅ **TP2:** 50% at M15 target (R:R 1:2.5 minimum)
- ✅ **Breakeven:** M1 trigger after +$1.50 or TP1
- ✅ **Trail Stop:** M5 swing lows (every 5 min)

**Risk Management:**
- ✅ Maximum 10-30 pip risk per scalp
- ✅ Always partial exits (50%/50%)
- ✅ Maximum 30-minute hold
- ✅ Maximum 10 scalps per day
- ✅ Stop after 3 consecutive losses

**Remember:** Scalping = Quick wins, tight stops, aggressive profit taking! ⚡📈

**Last Updated:** November 1, 2025  
**Data Source:** Multi-Timeframe Streamer (M1, M5, M15, M30, H1, H4)

