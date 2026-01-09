# 📰 News Trading Strategy - Quick Reference

## 🎯 Strategy Overview

**Type:** Event-Driven Volatility Trading  
**Best Pairs:** XAUUSD (★★★★★), GBPUSD (★★★★), EURUSD (★★★★), BTCUSD (★★★)  
**Timeframe:** M5 entry, M15 confirmation  
**Holding Period:** 5-30 minutes (news scalp)  
**Win Rate Target:** 60-65%  
**Average R:R:** 1:3.0 to 1:4.0  
**Risk Level:** HIGH (requires discipline and tight stops)

---

## 📚 Strategy Logic

### Why News Trading Works:
1. **Predictable Volatility** - News events create explosive moves (50-200 pips in minutes)
2. **Directional Clarity** - Strong fundamentals override technical resistance
3. **High Volume** - Real institutional money flow (not retail noise)
4. **Time-Specific** - Exact time known weeks in advance (preparation possible)
5. **Momentum Continuation** - Initial spike often extends 100-300 pips further

### Market Psychology:
```
Pre-News (30 min before):
→ Market consolidates, tight range
→ Traders close positions (fear of unknown)
→ Volume dies down, spreads tighten

News Release (8:30 AM EST):
→ Data released (NFP, CPI, etc.)
→ Algos parse data instantly
→ Spike occurs (50-100 pips in 1-2 minutes)
→ Retail stops triggered

Post-News (5-15 min after):
→ Initial spike exhausted
→ Profit-taking pullback (20-40% retracement)
→ Smart money enters → TRUE MOVE BEGINS
→ Trend continues for next 1-4 hours
```

**Our Edge:** Trade the **post-spike pullback**, NOT the initial explosion!

---

## 📅 High-Impact News Calendar

### **⚠️ ULTRA-HIGH IMPACT (Trade These):**

#### **🇺🇸 U.S. Events (XAUUSD, EURUSD, GBPUSD, BTCUSD)**

| Event | Day | Time (EST) | Avg Move | Best Pair | Notes |
|-------|-----|-----------|----------|-----------|-------|
| **Non-Farm Payrolls (NFP)** | 1st Fri | 8:30 AM | 100-300 pips | XAUUSD, EURUSD | KING of news events |
| **CPI (Inflation)** | ~13th | 8:30 AM | 80-200 pips | XAUUSD, BTCUSD | Fed policy impact |
| **Core CPI** | ~13th | 8:30 AM | 100-250 pips | XAUUSD | Excludes food/energy |
| **FOMC Rate Decision** | 8x/year | 2:00 PM | 150-400 pips | XAUUSD, EURUSD | Federal Reserve meeting |
| **Fed Chair Speech (Powell)** | Varies | Varies | 100-300 pips | XAUUSD, BTCUSD | Policy guidance |
| **Initial Jobless Claims** | Thu | 8:30 AM | 30-80 pips | XAUUSD | Weekly employment |
| **Retail Sales** | ~15th | 8:30 AM | 50-150 pips | EURUSD, GBPUSD | Consumer spending |
| **GDP (Quarterly)** | Last day | 8:30 AM | 60-120 pips | EURUSD | Economic growth |

#### **🇬🇧 U.K. Events (GBPUSD, EURGBP)**

| Event | Day | Time (EST) | Avg Move | Best Pair | Notes |
|-------|-----|-----------|----------|-----------|-------|
| **BOE Rate Decision** | 8x/year | 7:00 AM | 100-200 pips | GBPUSD | Bank of England |
| **CPI (U.K.)** | ~15th | 7:00 AM | 60-150 pips | GBPUSD | Inflation data |
| **Employment Data** | ~12th | 7:00 AM | 40-100 pips | GBPUSD | Jobs report |

#### **🇪🇺 Eurozone Events (EURUSD)**

| Event | Day | Time (EST) | Avg Move | Best Pair | Notes |
|-------|-----|-----------|----------|-----------|-------|
| **ECB Rate Decision** | 8x/year | 8:15 AM | 80-180 pips | EURUSD | European Central Bank |
| **Eurozone CPI** | Last day | 5:00 AM | 50-120 pips | EURUSD | Inflation |

#### **₿ Crypto Events (BTCUSD)**

| Event | Day | Time | Avg Move | Notes |
|-------|-----|------|----------|-------|
| **Bitcoin Halving** | Every 4 yrs | Varies | 10-30% | Planned scarcity event |
| **ETF Approval/News** | Unscheduled | Market hrs | 5-20% | SEC regulatory decisions |
| **Fed Policy (Crypto impact)** | Same as FOMC | 2:00 PM | 5-15% | Risk-on/risk-off |

---

## ⏰ Pre-News Preparation (30-60 min before)

### Step 1: Check News Calendar

**ChatGPT Command:**
```
"What high-impact news events are coming up in the next 4 hours?"
```

**System Tool:**
```
moneybot.news_status(hours_ahead: 4)
  → Returns: Upcoming events, impact level, blackout status
```

**What to Look For:**
- ✅ "Ultra" or "High" impact events
- ✅ Events affecting your symbol (NFP = XAUUSD, GBPUSD)
- ✅ Time = Next 30-60 minutes
- ❌ Skip if low/medium impact

---

### Step 2: Identify Pre-News Range

**ChatGPT Command:**
```
"Show me XAUUSD consolidation range for NFP news trade"
```

**What to Look For:**

✅ **Tight Consolidation (Last 1-2 hours):**
- XAUUSD: Range < 50 pips
- GBPUSD: Range < 20 pips
- EURUSD: Range < 15 pips
- BTCUSD: Range < 200 pips

✅ **Clear Boundaries:**
- Multiple touches at high/low
- Equal highs/lows (liquidity building)
- M5/M15 choppy structure

✅ **Low Volume:**
- Volume < 0.8x average
- Spreads normal (not widening)

❌ **Avoid If:**
- Already trending (news leaked?)
- Wide range (>2x ATR)
- Spread widening (broker issues)
- Volume spiking before event

**Example:**
```
NFP Friday 8:30 AM EST
Pre-News Range (6:30-8:25 AM):
  XAUUSD: 4050-4075 (25 pips - TIGHT ✅)
  Structure: Choppy M15
  Volume: 0.6x average (quiet ✅)
  DXY: Consolidating at 104.5
```

---

### Step 3: Check Macro Context

**ChatGPT Command:**
```
"What's the macro bias for XAUUSD?"
"Is DXY trending or ranging?"
```

**Directional Bias:**

**Bullish XAUUSD (BUY after news):**
- DXY falling or weak
- Risk-off sentiment (VIX > 20)
- Yields falling (US10Y down)
- Weak U.S. data expected (consensus)

**Bearish XAUUSD (SELL after news):**
- DXY rising or strong
- Risk-on sentiment (VIX < 15)
- Yields rising (US10Y up)
- Strong U.S. data expected

**Neutral:**
- No clear macro bias
- Trade BOTH directions (spike + retracement)

---

### Step 4: Set Alerts (Optional)

**ChatGPT Command:**
```
"Alert me 10 minutes before NFP at 8:30 AM EST"
"Alert when XAUUSD breaks above 4080 or below 4050"
```

**Recommended Alerts:**
- ⏰ Time-based: "10 min before event"
- 📊 Price-based: "Break above/below pre-news range"
- 📰 News-based: "When NFP data released"

---

## 🚀 Entry Strategy (RECOMMENDED: Post-Spike Pullback)

### **Phase 1: Wait for Initial Spike (8:30:00 - 8:32:00 AM)**

**DO NOT ENTER during initial spike!**

**Why:**
- Spreads widen (5-15 pips XAUUSD)
- Slippage massive (10-50 pips)
- Direction can reverse instantly
- Algos front-run retail

**What to Do:**
- ✅ **WATCH** the spike direction
- ✅ **MEASURE** spike magnitude (50+ pips = good)
- ✅ **IDENTIFY** spike high/low
- ❌ **DO NOT** chase the spike

**Example:**
```
8:30:00 AM: NFP released (250k jobs, beat expectations → USD strong)
8:30:15 AM: XAUUSD spikes DOWN from 4065 to 4015 (-50 pips in 15 seconds)
8:31:00 AM: XAUUSD hits low at 4008 (-57 pips total)
8:31:30 AM: Price starts to reverse → PREPARE FOR ENTRY
```

---

### **Phase 2: Wait for Pullback (8:32:00 - 8:35:00 AM)**

**Entry Setup:**

#### **A. Spike + Pullback Entry (Conservative)**

**Conditions:**
1. ✅ **Initial spike** > 40 pips (XAUUSD) or > 20 pips (GBPUSD)
2. ✅ **Pullback** 30-50% of spike (Fibonacci 0.382-0.50)
3. ✅ **Volume confirmation** (>1.5x average on pullback candle)
4. ✅ **BOS detected** on M5 (trend continuation)
5. ✅ **Rejection candle** (pin bar, engulfing at pullback level)

**Entry:**
- Type: Market order (when conditions met)
- Entry: Pullback zone (38-50% Fib retracement)
- Direction: Same as initial spike

**Example (Bearish XAUUSD after NFP):**
```
8:30:15 AM: Spike DOWN 4065 → 4008 (-57 pips)
8:32:00 AM: Pullback UP to 4030 (38% retrace, 22 pips)
8:32:30 AM: Bearish engulfing at 4030
           BOS Bear detected on M5
           Volume: 1.8x average
           
🔴 SELL XAUUSD @ 4028 (market order)
🛡️ SL: 4045 (above pullback + 15 pips buffer)
🎯 TP1: 3990 (below spike low, 1.5R = 38 pips)
🎯 TP2: 3970 (extended target, 2.5R = 58 pips)
📊 R:R: 1:2.4
```

**ChatGPT Command:**
```
"Execute SELL XAUUSD, entry market, SL 4045, TP 3990, volume 0"
```

---

#### **B. Range Breakout Entry (Aggressive)**

**Conditions:**
1. ✅ **Spike breaks** pre-news range (high or low)
2. ✅ **M5 candle closes** beyond range (confirmation)
3. ✅ **Volume spike** > 2.0x average
4. ✅ **No immediate reversal** (next candle continues)

**Entry:**
- Type: Market order (immediately after breakout close)
- Entry: At market price (within 5 pips of breakout)
- Direction: Breakout direction

**Example (Bullish GBPUSD after BOE):**
```
7:00:00 AM: BOE rate decision (hawkish)
Pre-News Range: 1.3040-1.3060 (20 pips)
7:00:30 AM: Spike UP to 1.3085 (breaks range high by 25 pips)
7:01:00 AM: M5 candle closes at 1.3082 (confirmation)
           Volume: 2.5x average
           
🟢 BUY GBPUSD @ 1.3083 (market order)
🛡️ SL: 1.3055 (below range low - 5 pips)
🎯 TP1: 1.3125 (1.5R = 42 pips)
🎯 TP2: 1.3155 (2.5R = 72 pips)
📊 R:R: 1:2.6
```

---

#### **C. Fade the Overextension (Contrarian - Advanced)**

**Conditions:**
1. ✅ **Spike > 100 pips** (XAUUSD) = likely overextended
2. ✅ **RMAG > +3.0σ** or **< -3.0σ** (extreme stretch)
3. ✅ **RSI > 85** or **< 15** (extreme overbought/oversold)
4. ✅ **Rejection wick** on M5 (exhaustion)
5. ✅ **Volume declining** (no follow-through)

**Entry:**
- Type: Limit order (at extreme level)
- Entry: Spike high/low (counter-trend)
- Direction: OPPOSITE to spike

**Example (Fade BTCUSD Spike):**
```
2:00:00 PM: FOMC hawkish (rate hike)
2:00:30 PM: BTCUSD spikes DOWN 64500 → 62800 (-1700 pts = -2.6%)
2:02:00 PM: RMAG: -3.5σ (extreme oversold)
           RSI: 12 (extreme)
           Wick rejection at 62800
           Volume declining
           
🟢 BUY Limit BTCUSD @ 62850 (contrarian)
🛡️ SL: 62200 (below wick - 650 pts)
🎯 TP1: 63500 (mean reversion, 1:1 R:R)
🎯 TP2: 64000 (full retracement, 1:1.8 R:R)
⚠️ Risk: HIGH - only for experienced traders
```

---

## 🛡️ Risk Management (CRITICAL FOR NEWS TRADING)

### Position Sizing:

**Conservative (Recommended for beginners):**
```
volume: 0  (auto-calculated)
→ System reduces to 0.5x normal size for news trades
→ XAUUSD: 0.01 lots (vs 0.02 normal)
→ Risk: 0.5% per trade (vs 1% normal)
```

**Standard (Experienced traders):**
```
volume: 0  (auto-calculated)
→ System uses 0.75x normal size
→ Risk: 0.75% per trade
```

**Aggressive (Experts only):**
```
volume: 0  (auto-calculated, but manually override if confident)
→ 1.0x normal size
→ Risk: 1% per trade
```

**NEVER exceed 1% risk on news trades!**

---

### Stop Loss Guidelines:

**Post-Spike Pullback Entry:**
- **Tight:** Above/below pullback high/low + 15 pips (XAUUSD)
- **Standard:** Above/below pullback + 20-30 pips
- **Wide:** Above/below spike extreme + 10 pips

**Range Breakout Entry:**
- **Tight:** Below/above pre-news range opposite extreme
- **Standard:** Below/above range + 10 pips buffer

**Fade Entry (Contrarian):**
- **Tight:** Beyond spike extreme + 20-30 pips
- **Wide:** 1.5x ATR beyond spike extreme

**Examples:**
```
XAUUSD Post-Spike Pullback:
  Spike: 4065 → 4008 (-57 pips)
  Pullback: 4030
  SL: 4045 (above pullback + 15 pips)
  Risk: 17 pips

GBPUSD Range Breakout:
  Range: 1.3040-1.3060
  Entry: 1.3083 (breakout)
  SL: 1.3055 (below range - 5 pips)
  Risk: 28 pips
```

---

### Take Profit Strategy:

**TP1 (50% of position) - ALWAYS SET THIS:**
- **Conservative:** 1.5R (1.5x stop distance)
- **Standard:** 2.0R
- **Locks in profit** early (news can reverse quickly)

**TP2 (Remaining 50%) - OPTIONAL:**
- **Conservative:** 2.5R or pre-news opposite extreme
- **Aggressive:** 3.0R or next major liquidity level
- **Extended targets:** PDH/PDL, psychological levels

**Trailing Stop (Recommended):**
- Activate after +1.0R profit
- Trail by 0.5R increments
- Lock in 1.5R minimum when TP2 near

**Example:**
```
XAUUSD SELL @ 4028
SL: 4045 (17 pips risk)

TP1: 3998 (1.8R = 30 pips) → Close 50%
TP2: 3975 (3.1R = 53 pips) → Close 50%

Trailing:
  Price hits 4010 (+1.0R) → Trail SL to 4040 (lock in +12 pips)
  Price hits 4000 (+1.6R) → Trail SL to 4028 (breakeven + 20)
  Price hits 3990 (TP1) → Close 50%, trail SL to 4015 (lock +13 pips on remaining)
```

---

### Time-Based Exit:

**News trades have limited lifespan!**

**Exit Rules:**
- ⏰ **15 minutes:** If not at +0.5R, consider closing
- ⏰ **30 minutes:** If not at +1.0R, close 50% or all
- ⏰ **1 hour:** Close remaining 50% (news impact fading)
- ⏰ **2 hours:** News effect gone, close all positions

**Why:**
- News volatility = temporary (30 min - 2 hours)
- Market returns to technical patterns
- New trend may emerge (opposite direction)

---

## ❌ Invalidation & Exit Rules

### Exit Immediately If:

**1. Opposite Spike Detected**
```
Example:
Initial spike: DOWN 50 pips (bearish)
You entered: SELL @ 4028
Sudden spike: UP 40 pips (opposite direction!)
→ EXIT immediately at market price
→ News data revised or misinterpreted
```

**2. Spread Spikes (Broker Issues)**
```
Normal spread: 2-3 pips ✅
Sudden spike: 10-20 pips ❌
→ Liquidity crisis
→ Exit if possible, or wait for spread to normalize
```

**3. CHOCH Detected (Structure Reversal)**
```
You entered: SELL after bearish spike
CHOCH Bull detected: M5 structure breaks bullish
→ Trend invalidated
→ Exit at market
```

**4. Volume Dies (No Follow-Through)**
```
Entry: Volume 2.0x average ✅
10 min later: Volume 0.5x average ❌
→ No institutional participation
→ Spike was retail-driven (will reverse)
→ Exit at breakeven or small profit
```

**5. Time-Based Stop (1 hour elapsed)**
```
Entry time: 8:32 AM
Current time: 9:32 AM (1 hour later)
Position: Still open, only +0.5R profit
→ News effect fading
→ Close position (don't hold overnight)
```

---

### Reduce Position (Partial Exit) If:

**1. TP1 Hit**
```
Always close 50% at TP1
→ Locks in profit
→ Reduces emotional pressure
→ Lets remaining 50% run
```

**2. Divergence Detected**
```
Price making LLs but RSI making HLs (bullish divergence in your SELL)
→ Momentum weakening
→ Close 50%, move SL to breakeven
```

**3. Session Transition (London Close, NY Open)**
```
NFP trade entered at 8:32 AM
London close: 12:00 PM (3.5 hours later)
→ Session shift = reversal risk
→ Close 50% or all
```

---

## 📊 Example Trades (Historical)

### Example 1: NFP Friday - XAUUSD SELL ✅ WIN

**Date:** Dec 6, 2024 (hypothetical)  
**Pair:** XAUUSD  
**Event:** Non-Farm Payrolls (NFP) at 8:30 AM EST

**Pre-News (8:00-8:25 AM):**
```
Pre-News Range: 4050-4075 (25 pips - TIGHT ✅)
Structure: Choppy M15, no clear direction
BB Squeeze: TRUE ✅
Volume: 0.6x average (quiet)
DXY: 104.5 (stable)
Consensus: +175k jobs expected
```

**News Release (8:30:00 AM):**
```
NFP Data: +285k jobs (BEAT expectations by 110k!)
→ USD strength confirmed
→ Bearish for XAUUSD
```

**Initial Spike (8:30:00 - 8:31:30 AM):**
```
8:30:05 AM: Price drops 4065 → 4045 (-20 pips)
8:30:30 AM: Accelerates 4045 → 4020 (-25 pips more)
8:31:00 AM: Spike low at 4008 (-57 pips total)
8:31:30 AM: Starts to reverse upward
```

**Pullback & Entry (8:32:00 - 8:33:00 AM):**
```
8:32:00 AM: Pullback to 4028 (35% Fib retrace, 20 pips)
8:32:30 AM: Bearish engulfing at 4030
           BOS Bear confirmed on M5
           Volume: 2.1x average
           RSI: 58 (neutral, room to fall)
           RMAG: +0.8σ (healthy)
```

**Trade Execution:**
```
🔴 SELL XAUUSD @ 4028 (market order)
🛡️ SL: 4045 (above pullback + 15 pips) = 17 pips risk
🎯 TP1: 3998 (below spike low, 1.8R = 30 pips)
🎯 TP2: 3970 (extended target, 3.4R = 58 pips)
📊 Confidence: 78%
```

**Trade Management:**
```
8:40 AM: Price hits 4010 (+1.1R, +18 pips)
→ System trails SL to 4040 (lock in +12 pips)

8:55 AM: Price hits 3998 (TP1 hit ✅)
→ System closes 50% (+30 pips locked)
→ SL trails to 4018 on remaining 50%

9:15 AM: Price hits 3975 (near TP2)
→ Price stalls at 3975 (psychological level)
→ System closes remaining 50% at 3978 (+50 pips)
```

**Result:**
```
✅ WINNER
Profit: +40 pips average (30 + 50 / 2)
R:R Realized: 1:2.4
Risk: 0.5% (half position)
Profit: +1.2% (2.4R × 0.5%)
Duration: 43 minutes
```

---

### Example 2: FOMC Rate Decision - BTCUSD BUY ✅ WIN

**Date:** Dec 18, 2024 (hypothetical)  
**Pair:** BTCUSD  
**Event:** FOMC Rate Decision at 2:00 PM EST

**Pre-News (1:00-1:55 PM):**
```
Pre-News Range: 64200-64500 (300 pts - TIGHT ✅)
Structure: Consolidating M15
Volume: 0.7x average
S&P 500: Flat (waiting for Fed)
Consensus: 25 bps rate cut expected
```

**News Release (2:00:00 PM):**
```
FOMC: 25 bps rate cut (AS EXPECTED)
Powell Speech: "Data-dependent, cautiously dovish"
→ Risk-on sentiment
→ Bullish for BTCUSD
```

**Initial Spike (2:00:00 - 2:02:00 PM):**
```
2:00:10 PM: Price spikes UP 64300 → 64800 (+500 pts)
2:01:00 PM: Accelerates 64800 → 65200 (+400 more)
2:01:30 PM: Spike high at 65400 (+1100 pts total = +1.7%)
2:02:00 PM: Starts to pullback
```

**Pullback & Entry (2:03:00 - 2:04:00 PM):**
```
2:03:00 PM: Pullback to 65000 (36% Fib, 400 pts)
2:03:30 PM: Bullish engulfing at 65000
           BOS Bull confirmed on M5
           Volume: 1.9x average
           S&P 500: +0.8% (risk-on confirmed)
```

**Trade Execution:**
```
🟢 BUY BTCUSD @ 65020 (market order)
🛡️ SL: 64500 (below pullback - 50 pts) = 520 pts risk
🎯 TP1: 65800 (1.5R = 780 pts)
🎯 TP2: 66300 (2.5R = 1280 pts)
📊 Confidence: 82%
```

**Trade Management:**
```
2:15 PM: Price hits 65800 (TP1 hit ✅)
→ System closes 50% (+780 pts locked)

2:35 PM: Price hits 66100 (near TP2)
→ Volume declining, RSI 72 (overbought)
→ Manually close remaining 50% at 66100 (+1080 pts)
```

**Result:**
```
✅ WINNER
Profit: +930 pts average (780 + 1080 / 2)
R:R Realized: 1:1.8
Risk: 0.75%
Profit: +1.35% (1.8R × 0.75%)
Duration: 32 minutes
```

---

### Example 3: CPI Release - EURUSD FAKE SPIKE ❌ SMALL LOSS (Managed)

**Date:** Dec 13, 2024 (hypothetical)  
**Pair:** EURUSD  
**Event:** U.S. CPI at 8:30 AM EST

**Pre-News (8:00-8:25 AM):**
```
Pre-News Range: 1.0480-1.0505 (25 pips - TIGHT ✅)
Structure: Choppy M15
DXY: 104.2 (consolidating)
Consensus: CPI +0.3% MoM expected
```

**News Release (8:30:00 AM):**
```
CPI Data: +0.3% MoM (IN LINE with expectations)
→ No surprise = no clear direction
→ Initial spike ambiguous
```

**Initial Spike (8:30:00 - 8:31:00 AM):**
```
8:30:05 AM: Price spikes UP 1.0490 → 1.0510 (+20 pips)
8:30:30 AM: Reverses DOWN 1.0510 → 1.0485 (-25 pips)
8:31:00 AM: Spikes UP again 1.0485 → 1.0505 (+20 pips)
⚠️ WHIPSAW action (conflicting interpretation)
```

**Entry Attempt (8:32:00 AM) - MISTAKE:**
```
8:32:00 AM: Pullback to 1.0498 (looks like bullish entry)
8:32:30 AM: Bullish pin bar at 1.0498
           ❌ Volume: 0.9x average (WEAK!)
           ❌ BOS: Not confirmed (structure unclear)
           ❌ DXY: Not moving (no follow-through)
```

**Trade Execution (Should Have SKIPPED):**
```
🟢 BUY EURUSD @ 1.0500 (market order)
🛡️ SL: 1.0480 (20 pips risk)
🎯 TP1: 1.0540 (1.5R)
⚠️ Confidence: 55% (TOO LOW - should have skipped!)
```

**Trade Management:**
```
8:35 AM: Price stalls at 1.0505 (+5 pips, +0.25R)
         No volume, no follow-through
         
8:38 AM: Price drops back to 1.0495 (-5 pips)
         News effect fading
         
8:40 AM: MANUALLY EXIT at 1.0495 (-5 pips loss)
         Reason: "No conviction, weak volume"
```

**Result:**
```
❌ SMALL LOSS (but managed well)
Loss: -5 pips (vs -20 pips if hit SL)
Risk: 0.25% (vs 0.5% if full loss)
Lesson: SKIP trades when news "meets expectations" (no surprise = weak move)
```

---

## 🤖 ChatGPT Commands Reference

### Pre-News Check (30-60 min before):

**Check Calendar:**
```
"What high-impact news events are coming up in the next 4 hours?"
"When is NFP this week?"
"Show me upcoming FOMC dates"
```

**Check Pre-News Range:**
```
"Show me XAUUSD consolidation range for NFP news trade"
"Is GBPUSD in a tight range before BOE decision?"
```

**Check Macro:**
```
"What's the macro bias for XAUUSD before NFP?"
"Is DXY trending up or down?"
"What's the risk sentiment (VIX)?"
```

---

### Post-News Entry (2-5 min after release):

**Analyze Spike:**
```
"Analyze XAUUSD post-NFP spike - is pullback entry valid?"
"Check if BOS detected on GBPUSD M5 after BOE decision"
"Show me BTCUSD RMAG and RSI after FOMC - is it overextended?"
```

**Full Analysis:**
```
"moneybot.analyse_symbol_full for XAUUSD"
```
→ Returns all layers (macro, SMC, advanced, binance, order flow)

---

### Alert Setup (1 day before):

**Time-Based:**
```
"Alert me 30 minutes before NFP on Friday at 8:30 AM EST"
"Remind me at 1:45 PM EST for FOMC decision at 2:00 PM"
```

**Price-Based:**
```
"Alert when XAUUSD breaks above 4080 or below 4050 (pre-news range)"
```

---

### Trade Execution:

**Market Order (Post-Spike Pullback):**
```
"Execute SELL XAUUSD, entry market, SL 4045, TP 3998, volume 0"
```

**Limit Order (Pre-Spike Breakout):**
```
"Place BUY Limit GBPUSD @ 1.3065, SL 1.3045, TP 1.3100"
```

---

### Trade Management:

**Check Status:**
```
"Is XAUUSD news trade still valid? Check for CHOCH or reversal"
"How long has my GBPUSD position been open? (time-based exit)"
```

**Modify Position:**
```
"Move SL to breakeven on XAUUSD ticket #123456"
"Close 50% of EURUSD position now"
```

**Close Trade:**
```
"Close XAUUSD ticket #123456 immediately"
```

---

## 📈 Performance Expectations

### Target Metrics (Monthly):

**Win Rate:** 60-65%  
**Average R:R:** 1:3.0  
**Trades Per Month:** 8-12 (2-3x per week)  
**Profit Factor:** 2.5-3.5+  
**Max Drawdown:** <3% (with 0.5% risk per trade)

### Best Pairs (by win rate):

1. **XAUUSD:** 65% win rate
   - Most reactive to U.S. news
   - Largest moves (100-300 pips)
   - Best for NFP, CPI, FOMC

2. **GBPUSD:** 62% win rate
   - Strong BOE reactions
   - Clean breakouts
   - Good liquidity

3. **EURUSD:** 60% win rate
   - ECB decisions
   - Lower volatility
   - Tighter spreads

4. **BTCUSD:** 58% win rate
   - Fed policy impact
   - High R:R (1:4.0+)
   - Higher risk (larger stops)

---

## ⚠️ Common Mistakes to Avoid

### 1. Chasing the Initial Spike ❌
**Mistake:**
- Entering during 8:30:00-8:31:00 AM spike
- FOMO (fear of missing out)
- Massive slippage and spread widening

**Fix:**
- ALWAYS wait for pullback (30-50% retrace)
- Or skip the trade entirely

---

### 2. Ignoring Volume ❌
**Mistake:**
- Entering on low volume pullback
- Volume < 1.2x average = fake pullback

**Fix:**
- Require 1.5x+ volume spike on entry candle
- Check Binance enrichment for volume confirmation

---

### 3. Trading "Meet Expectations" News ❌
**Mistake:**
- Trading when actual = expected (no surprise)
- Market already priced in

**Fix:**
- Only trade when: Actual BEATS or MISSES expectations by >20%
- Example: NFP expected 175k, actual 285k (+63% beat) = TRADE ✅
- Example: CPI expected 0.3%, actual 0.3% (0% surprise) = SKIP ❌

---

### 4. No Stop Loss ❌
**Mistake:**
- "I'll exit manually if it goes against me"
- News can move 100+ pips against you in seconds

**Fix:**
- ALWAYS use stop loss (system requirement)
- Place beyond spike extreme or pullback + buffer

---

### 5. Overtrading News ❌
**Mistake:**
- Trading every single news event (low/medium impact)
- Burning out, taking poor setups

**Fix:**
- ONLY trade ULTRA-HIGH impact (NFP, CPI, FOMC, BOE)
- Skip medium/low impact events
- Quality > Quantity (2-3x per week max)

---

### 6. Holding Too Long ❌
**Mistake:**
- Holding news position for 2+ hours
- News effect fades, technicals take over

**Fix:**
- Time-based exit: Close within 30-60 minutes
- Or at least close 50% and trail remaining

---

### 7. Not Reducing Position Size ❌
**Mistake:**
- Trading full 1% risk on news (same as regular trades)
- News = higher risk, requires smaller size

**Fix:**
- Use 0.5x or 0.75x normal position size
- Risk: 0.5-0.75% per trade (vs 1% normal)

---

## 📚 Additional News Resources Needed

### **🔥 CRITICAL: Add These Data Sources**

See companion document: `NEWS_DATA_SOURCES_NEEDED.md`

**Top Priority:**
1. ✅ Forex Factory XML (Already have)
2. 🔥 **Investing.com API** (Real-time calendar + actual vs expected)
3. 🔥 **TradingEconomics API** (Historical data + forecasts)
4. 🔥 **Twitter/X Real-Time Feed** (Breaking news, Fed speeches)
5. ⭐ **ForexLive** (Instant news interpretation)

---

## 🎓 Knowledge Documents to Study

**Must Read:**
1. **`ChatGPT_Knowledge_Smart_Money_Concepts.md`**
   - BOS/CHOCH detection (critical for post-spike entry)

2. **`SYMBOL_GUIDE.md`**
   - Pair characteristics (XAUUSD vs GBPUSD volatility)

3. **`ChatGPT_Knowledge_Alert_System.md`**
   - Setting up time-based and price-based alerts

**Advanced:**
4. **`ChatGPT_Knowledge_All_Enrichments.md`**
   - Volume analysis, RMAG stretch detection

5. **`GOLD_ANALYSIS_QUICK_REFERENCE.md`**
   - XAUUSD-specific macro factors (DXY, yields)

6. **`LONDON_BREAKOUT_STRATEGY.md`**
   - Similar entry logic (breakout + pullback)

---

## 🔄 Weekly Routine

### **Monday:**
- Review news calendar for the week
- Identify ULTRA-HIGH impact events (NFP, CPI, FOMC)
- Mark calendar for preparation times

### **News Day (e.g., Friday NFP):**
- **7:00 AM:** Wake up, review pre-market
- **8:00 AM:** Check pre-news range (XAUUSD, EURUSD)
- **8:15 AM:** Set alerts, check macro bias
- **8:25 AM:** Final prep, position terminal
- **8:30 AM:** WATCH spike (don't enter yet)
- **8:32 AM:** Analyze pullback, enter if conditions met
- **8:45 AM:** Manage trade (TP1, trailing)
- **9:30 AM:** Close remaining position (1 hour rule)

### **Post-Trade:**
- Journal result (win/loss, lessons)
- Review: What worked? What didn't?
- Prepare for next event

---

## ✅ Final Checklist (Before Every News Trade)

**Pre-News (30-60 min before):**
- [ ] ULTRA-HIGH impact event identified (NFP, CPI, FOMC)
- [ ] Pre-news range identified (tight, <50 pips XAUUSD)
- [ ] Macro bias checked (DXY, VIX, yields)
- [ ] Alerts set (time + price breakout)
- [ ] Position size reduced (0.5x or 0.75x normal)

**Post-News (2-5 min after release):**
- [ ] Initial spike > 40 pips (XAUUSD) or > 20 pips (GBPUSD)
- [ ] Pullback 30-50% of spike (Fib 0.382-0.50)
- [ ] Volume spike > 1.5x average on entry candle
- [ ] BOS detected on M5 (trend continuation)
- [ ] Rejection candle at pullback level (pin bar, engulfing)
- [ ] No CHOCH detected (invalidation)
- [ ] Spread normal (<3 pips XAUUSD, <2 pips GBPUSD)

**Risk Management:**
- [ ] Stop loss beyond pullback + buffer (15-30 pips)
- [ ] TP1 at 1.5-2.0R (lock profit)
- [ ] TP2 at 2.5-3.0R or next liquidity level
- [ ] Time-based exit: Close within 30-60 minutes

**If Any Condition Fails:**
- [ ] SKIP THE TRADE → Wait for next event

---

## 📞 Support

**Questions?**
Ask ChatGPT:
- "Explain news trading strategy"
- "What's the difference between spike entry and pullback entry?"
- "How do I check upcoming news events?"

**Need Help?**
Reference these docs:
- `CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md` - Core rules
- `ChatGPT_Knowledge_Smart_Money_Concepts.md` - SMC framework
- `NEWS_DATA_SOURCES_NEEDED.md` - Additional news APIs

---

**🎯 Remember: Patience is Power**

**Wait for the pullback. The best news trades are made 2-5 minutes AFTER the release, not during the chaos.**

**Trade only ULTRA-HIGH impact events. Quality > Quantity.**

**Good luck, and may your news trades be profitable! 📰💰**

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-14  
**Status:** Active Strategy ✅  
**Next Steps:** Implement additional news data sources (see NEWS_DATA_SOURCES_NEEDED.md)

