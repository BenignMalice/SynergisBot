# Bitcoin (BTCUSD) Analysis - Quick Reference Card

## ₿ Custom GPT Bitcoin Analysis Protocol

### Quick Start (RECOMMENDED)

**For comprehensive analysis, use ONE call:**
```
moneybot.analyse_symbol_full(symbol: "BTCUSD")
  Returns unified analysis combining:
  ✅ Macro context (VIX, S&P500, DXY, BTC.D, Fear & Greed)
  ✅ Smart Money Concepts (CHOCH, BOS, M1/M5/M15/M30/H1/H4 structure)
  ✅ Advanced features (RMAG, Bollinger ADX, VWAP, FVG)
  ✅ Technical indicators (EMA, RSI, MACD, Stoch, BB, ATR)
  ✅ Binance enrichment (Z-Score, Pivots, Liquidity, Tape, Patterns)
  ✅ Order flow analysis (Whales, Imbalance, Pressure)
  ✅ **BTC Order Flow Metrics** ⭐ NEW - Advanced order flow metrics (Delta Volume, CVD, CVD Slope, CVD Divergence, Absorption Zones, Buy/Sell Pressure) - **AUTOMATICALLY INCLUDED** in `moneybot.analyse_symbol_full` for BTCUSD! Check the "BTC ORDER FLOW METRICS" section in the analysis summary. Also available via `moneybot.btc_order_flow_metrics` for standalone requests. 🚨 **CRITICAL FOR BTC TRADES**: Always check BTC order flow metrics when analyzing BTCUSD, making recommendations, or creating auto-execution plans for BTC. Order flow signals help validate entry timing and direction.
  ✅ **Enhanced Data Fields** ⭐ NEW (December 2025) - Correlation context (DXY, SP500, US10Y, BTC), HTF levels (weekly/monthly opens, premium/discount zones), Session risk (rollover, news lock), Execution context (spread/slippage quality), Strategy stats (historical performance), Structure summary (range type, liquidity sweeps), Symbol constraints (max trades, banned strategies) - **AUTOMATICALLY INCLUDED** in `moneybot.analyse_symbol_full`! Check the "📊 ENHANCED DATA FIELDS ⭐ NEW" section in the analysis summary.
  ✅ Multi-timeframe streaming data (M1, M5, M15, M30, H1, H4) ⭐ NEW
  ✅ Technical analysis with entry/SL/TP
  ✅ Layered recommendations (scalp/intraday/swing)
  ✅ Unified verdict with confluence logic
  
  Response time: <6 seconds
  
  🚨 CRITICAL: Display the 'summary' field VERBATIM - never paraphrase or say "unavailable"
  🚨 CRITICAL: Extract and display specific price levels (PDH/PDL, FVG, entry zones, R:R) from advanced_features data!
```

### Alternative: Individual Tools (for deep-dive)

**If user wants granular analysis:**
```
moneybot.macro_context(symbol: "BTCUSD") → Just macro layer
  Returns:
  - VIX (Risk sentiment)
  - S&P 500 (Equity correlation +0.70)
  - DXY (USD strength, inverse -0.60)
  - BTC Dominance (>50% strong, <45% weak)
  - Crypto Fear & Greed Index (0-100 sentiment)
  - Bitcoin-specific verdict (BULLISH/BEARISH for Crypto)
  
moneybot.getMultiTimeframeAnalysis(symbol: "BTCUSD") → Just SMC layer

moneybot.btc_order_flow_metrics(symbol: "BTCUSDT") ⭐ NEW - Advanced Order Flow Metrics
  Returns:
  - Delta Volume (buy/sell imbalance, net delta, dominant side)
  - CVD (Cumulative Volume Delta with slope per bar)
  - CVD Divergence (price vs CVD divergence detection)
  - Absorption Zones (price levels with high order absorption, imbalance ratios)
  - Buy/Sell Pressure (ratio and dominant side)
  ⚠️ Use when user asks for "order flow", "CVD", "delta volume", "absorption zones", or "buy/sell pressure" for BTC
  ⚠️ Requires OrderFlowService to be running (initialized in chatgpt_bot.py)
  ⚠️ Only works for BTCUSD (Binance data)
```

**Bitcoin-specific analysis layers (ALL AVAILABLE VIA macro_context):**
1. **Risk Sentiment Layer** (VIX, S&P 500) → Crypto market sentiment ✅
2. **Crypto Fundamentals** (BTC Dominance, Fear & Greed Index) → Market strength ✅
3. **SMC Layer** (CHOCH, BOS, Order Blocks, Liquidity) → Entry/exit precision ✅
4. **Volatility Layer** (ATR, Bollinger) → Position sizing ✅

---

## 📊 Layer 1: Bitcoin-Specific Market Drivers

### 1. Risk Sentiment (Most Important for Bitcoin)

**VIX (Volatility Index):**
```
VIX <15: Risk-on → ✅ Bullish for Bitcoin
- Investors seek higher returns
- Money flows to risk assets (crypto)
- Bitcoin tends to rally

VIX 15-20: Normal → ⚪ Neutral for Bitcoin
- Balanced risk/reward environment
- Bitcoin follows technical patterns

VIX >20: Risk-off → 🔴 Bearish for Bitcoin
- Flight to safety (USD, Gold)
- Money exits risk assets
- Bitcoin often drops 5-15%
```

**Stock Market Correlation - ✅ LIVE via macro_context:**

**Data Source:** Yahoo Finance (FREE, ^GSPC ticker)

```
S&P 500 Rising → ✅ Bullish for Bitcoin
- Risk-on sentiment
- Correlation: +0.70 (STRONG)
- Example: S&P +1.56% → Bitcoin likely to rally

S&P 500 Falling → 🔴 Bearish for Bitcoin
- Risk-off sentiment
- Bitcoin follows equities down
- Example: S&P -2.0% → Bitcoin may drop 3-5%
```

---

### 2. US Dollar (DXY) - Inverse Correlation

```
DXY Rising → 🔴 Bearish for Bitcoin
- Stronger USD = weaker Bitcoin
- Inverse correlation: -0.60
- Bitcoin priced in USD weakens

DXY Falling → ✅ Bullish for Bitcoin
- Weaker USD = stronger Bitcoin
- Money flows to alternative assets
- Bitcoin rallies
```

---

### 3. Bitcoin Dominance (BTC.D) - ✅ LIVE via macro_context

**Data Source:** CoinGecko API (FREE, no API key required)

```
BTC.D Rising (>50%) → ✅ STRONG (Money flowing to Bitcoin)
- Money flowing FROM altcoins TO Bitcoin
- "Safe haven" in crypto
- Bullish for BTC, bearish for alts
- Example: 57.3% = Strong Bitcoin outperformance

BTC.D Falling (<45%) → ⚠️ WEAK (Alt season)
- Money flowing FROM Bitcoin TO altcoins
- "Alt season" starting
- Risk: Bitcoin may consolidate
- Example: 43.2% = Money rotating to altcoins

BTC.D Neutral (45-50%) → ⚪ NEUTRAL
- Balanced crypto market
- Follow technical signals
```

---

### 4. Crypto Fear & Greed Index - ✅ LIVE via macro_context

**Data Source:** Alternative.me API (FREE, no API key required)

```
Extreme Fear (0-25) → ✅ BUY OPPORTUNITY
- Panic selling, oversold
- Historically best entry zone
- Example: 15/100 = "Blood in the streets"
- Bitcoin often bottoms at <25

Fear (25-45) → ⚪ CAUTIOUS
- Negative sentiment, but not capitulation
- Wait for technical confirmation
- Example: 38/100 = Fear
- Can go lower before bouncing

Neutral (45-55) → ⚪ BALANCED
- Market indecision
- Follow technical patterns

Greed (55-75) → ⚠️ CAUTION
- Euphoria building
- Consider taking profits
- Example: 68/100 = Greed
- Tops forming

Extreme Greed (75-100) → 🔴 SELL SIGNAL
- Overheated, overbought
- Historically best exit zone
- Example: 85/100 = "Everyone buying"
- Bitcoin often tops at >75
```

**How to Use:**
```
Fear <25 + Bullish OB = STRONG BUY (contrarian entry)
Greed >75 + Bearish CHOCH = STRONG SELL (exit signal)
Fear 38 + VIX >20 = WAIT (more downside possible)
Greed 68 + BTC.D >50% = HOLD (still has room)
```

---

## 🎯 Layer 2: Bitcoin SMC (Critical for Entries/Exits)

### CHOCH (Change of Character) - CRITICAL! 🚨

**Bitcoin CHOCH = Major Reversal Signal**

**Bullish CHOCH (Exit Longs):**
```
Price makes LOWER LOW → Uptrend structure BROKEN
🚨 Bitcoin can drop $2,000-$5,000 after CHOCH

Example:
BTC at $67,500 → Makes LL at $66,800 (previous HL was $67,200)
→ EXIT longs immediately
→ Expect drop to $64,000-$65,000

Why it matters:
- Bitcoin reversals are VIOLENT (10-20% drops)
- CHOCH gives 2-6 hour warning before major drop
- Institutional money exits on CHOCH
```

**Bearish CHOCH (Exit Shorts):**
```
Price makes HIGHER HIGH → Downtrend structure BROKEN
🚨 Bitcoin can rally $3,000-$6,000 after bearish CHOCH

Example:
BTC at $63,000 → Makes HH at $64,200 (previous LH was $63,800)
→ EXIT shorts immediately
→ Expect rally to $66,500-$68,000

Why it matters:
- Bitcoin short squeezes are BRUTAL (15-25% rallies)
- FOMO kicks in fast
- Liquidations fuel the rally
```

---

### BOS (Break of Structure) - Trend Confirmation ✅

**Bullish BOS (Ride the Trend):**
```
3x consecutive HH = Very strong uptrend
Bitcoin can run $5,000-$15,000 after strong BOS

Example:
HH at $64k → $66k → $68k (3x consecutive)
→ STAY IN longs
→ Trail SL below each higher low
→ Target: $72k-$75k (next major resistance)

Bitcoin trend characteristics:
- Trends last 2-8 weeks
- Pullbacks are 5-10% (healthy)
- Don't exit on minor dips
```

**Bearish BOS (Short with Caution):**
```
3x consecutive LL = Confirmed downtrend
Bitcoin can drop $8,000-$20,000 in bear trends

Example:
LL at $68k → $65k → $62k (3x consecutive)
→ STAY IN shorts (if already positioned)
→ Trail SL above each lower high
→ Target: $58k-$55k (next major support)

⚠️ Warning:
- Bitcoin shorts are RISKY (sudden rallies)
- Use wider stops (10-15%)
- Take profits aggressively
```

---

### Order Blocks - Precise Entry Zones 🎯

**Bullish Order Block (Accumulation Zone):**
```
Last green 4H candle before price drops
= Institutional buy zone

Bitcoin Example:
- Current price: $66,200 (above OB)
- Bullish OB: $64,800-$65,200 (last green before drop)
- Entry: Wait for pullback to $64,800-$65,200
- SL: $64,200 (below OB, $600-1,000 risk)
- TP1: $67,500 (recent high)
- TP2: $69,800 (liquidity pool above)
- R:R: 1:4 to 1:8

Why Order Blocks work for Bitcoin:
- Institutional algorithms respect these zones
- High volume accumulation visible
- 70%+ success rate on H4 OBs
```

**Bearish Order Block (Distribution Zone):**
```
Last red 4H candle before price rises
= Institutional sell zone

Bitcoin Example:
- Current price: $66,500 (below OB)
- Bearish OB: $68,200-$68,800 (last red before rally)
- Entry: Wait for rally to $68,200-$68,800
- SL: $69,200 (above OB, $600-1,000 risk)
- TP1: $66,000 (recent low)
- TP2: $63,500 (liquidity pool below)
- R:R: 1:3 to 1:5

⚠️ Note:
- Bitcoin can wick through OBs (use limits)
- Don't chase if price gaps through
```

---

### Liquidity Pools - Bitcoin's Magnet Levels 💰

**Equal Highs (Bullish Target):**
```
3+ swing highs within $200 = Buy-side liquidity
Bitcoin WILL sweep these levels

Example:
Equal highs at $69,800, $69,750, $69,820
→ Target: $69,800 (price magnetically drawn here)
→ Place TP at $69,600 (before sweep)
→ Or trail SL after sweep occurs

Why Bitcoin loves liquidity:
- Leveraged longs/shorts cluster here
- Liquidations create buying/selling pressure
- Predictable price targets
```

**Equal Lows (Stop Hunt Zone):**
```
3+ swing lows within $200 = Sell-side liquidity
Bitcoin often sweeps then reverses HARD

Example:
Equal lows at $64,500, $64,480, $64,520
→ Expect sweep to $64,300 (hunt stops)
→ If LONG: Place SL at $64,000 (below hunt zone)
→ If SHORT: Take profit at $64,500, expect reversal

Bitcoin liquidity sweep characteristics:
- Wicks $300-$800 below/above equal lows/highs
- Reversal happens within 15-60 minutes
- Perfect entry for counter-trend scalps
```

---

## 🎯 Bitcoin-Specific Trading Strategies

### Strategy 1: Risk-On Trend Following

```
Setup Requirements:
✅ VIX <15 (Risk-on)
✅ S&P 500 rising (Equities bullish)
✅ BOS Bull confirmed (3x HH)
✅ Price at Bullish Order Block

Entry:
- Wait for pullback to OB
- Enter at $64,800-$65,200
- SL: $64,200
- TP1: $67,500 | TP2: $69,800

Confidence: 90%
Hold Time: 2-7 days (trend following)
Position Size: 100% (normal size)

Why it works:
- Macro + Technical aligned
- Bitcoin trends hard in risk-on environments
- Institutional buying at OBs
```

---

### Strategy 2: CHOCH Reversal Trade

```
Setup Requirements:
✅ CHOCH detected (LL made in uptrend)
✅ Price approaching Bearish Order Block
⚠️ VIX rising (Risk-off starting)

Entry:
- Wait for rally to Bearish OB ($68,200-$68,800)
- SHORT from OB rejection
- SL: $69,200
- TP1: $66,000 | TP2: $63,500

Confidence: 85%
Hold Time: 1-4 days (reversal trade)
Position Size: 50-75% (higher risk)

Why it works:
- Structure broken = trend over
- Institutions distribute at OBs
- Risk-off accelerates downside
```

---

### Strategy 3: Liquidity Sweep Scalp

```
Setup Requirements:
✅ Equal lows identified ($64,500 level)
✅ Price approaching from above
✅ H1 oversold (RSI <30)

Entry:
- Wait for sweep to $64,300 (below equal lows)
- BUY on reversal candle
- SL: $64,000 (tight)
- TP: $65,800 (1,500 pips)

Confidence: 75%
Hold Time: 4-12 hours (scalp)
Position Size: 50% (quick trade)

Why it works:
- Liquidity sweeps are predictable
- Bitcoin reverses aggressively after hunts
- Short-term mean reversion
```

---

## 📊 Bitcoin Volatility Management

### ATR-Based Position Sizing

```
Normal Volatility (ATR $800-$1,200):
- Position Size: 100%
- Stop Loss: 1.5x ATR ($1,200-$1,800)
- Target: 2.5-3x ATR ($2,000-$3,600)

High Volatility (ATR $1,500-$2,500):
- Position Size: 50-75%
- Stop Loss: 2x ATR ($3,000-$5,000)
- Target: 3-4x ATR ($4,500-$10,000)

Extreme Volatility (ATR >$2,500):
- Position Size: 25-50%
- Stop Loss: 2.5x ATR ($6,000+)
- Consider waiting for consolidation
```

---

### Session-Specific Behavior

```
Asian Session (00:00-08:00 UTC):
- Lower volatility ($200-$500 ranges)
- Range-bound trading
- Good for: Scalping Order Blocks

London Session (08:00-16:00 UTC):
- Medium volatility ($500-$1,200 moves)
- Liquidity sweeps common
- Good for: Breakouts, CHOCH detection

NY Session (13:00-22:00 UTC):
- Highest volatility ($800-$2,000 moves)
- Trend continuation or reversals
- Good for: BOS confirmation, trend trades

Weekend (Sat-Sun):
- Low liquidity (gaps possible)
- Avoid new positions
- Monitor existing trades only
```

---

## 🔍 Real-World Bitcoin Examples

### Example 1: Perfect Long Setup (Risk-On Rally)

```
📊 Market Context (LIVE from macro_context):
VIX: 21.8 (Risk-off) ⚠️
S&P 500: +1.56% (Equities rising) ✅
DXY: 99.15 (Falling) ✅
BTC.D: 57.3% (STRONG - Bitcoin outperforming) ✅
Crypto F&G: 38/100 (Fear) ⚠️

Sentiment: 🟢 BULLISH (3 of 5 signals bullish, mixed risk)

🏛️ Bitcoin SMC:
Structure: BOS Bull (3x HH: $64k→$66k→$68k)
Current Price: $66,200 (pullback in progress)
Bullish OB: $64,800-$65,200 (H4 accumulation zone)
Liquidity Pool: Equal Highs at $69,800

📊 Technical Confluence: 92/100
- BOS confirmed
- At Bullish OB
- Risk-on macro
- Advanced features: Quality uptrend

📌 Key Levels:
Support: $64,200 (PDL) | $64,800 (Swing Low)
Resistance: $69,800 (PDH) | Equal Highs: $69,800 (liquidity target)
Entry Zone: $64,800-$65,200 (Bull OB) · Stop Loss: $64,200 · Take Profit: $67,500 (TP1, R:R 1:4.5) | $69,800 (TP2, R:R 1:8.3)

📉 VERDICT: STRONG BUY at Order Block

🎯 Trade Plan:
Entry: $64,800-$65,200 (pending limit order)
Stop Loss: $64,200 ($600-1,000 risk)
TP1: $67,500 (recent high) - 25% position
TP2: $69,800 (liquidity sweep) - 50% position
TP3: Trail remaining 25%
R:R: 1:4 to 1:8

Hold Time: 3-7 days
Position Size: 100% (normal)
Confidence: 90%

Why high confidence:
- All macro signals bullish
- Clean BOS structure
- At proven accumulation zone
- Clear liquidity target
```

---

### Example 2: CHOCH Reversal (Risk-Off Starting)

```
📊 Market Context:
VIX: 18.5 → 21.2 (Rising +14%, Risk-off) ⚠️
S&P 500: -0.8% (Equities falling) 🔴
DXY: 99.8 (Rising +0.5%) 🔴
BTC.D: 49% (Weakening) ⚠️

Sentiment: 🔴🔴 BEARISH (Risk-off accelerating)

🏛️ Bitcoin SMC:
🚨 CHOCH DETECTED at $66,800 (Lower Low made)
Previous Structure: Uptrend (HL at $67,200)
Current Price: $66,500 (breakdown in progress)
Bearish OB: $68,200-$68,800 (distribution zone above)

📉 VERDICT: PROTECT PROFITS / PREPARE SHORT

Current Action:
- If in longs: EXIT IMMEDIATELY or SL to breakeven
- Expect drop to $64,000-$63,000 (-5% to -7%)

Next Trade Setup:
Wait for rally to Bearish OB ($68,200-$68,800)
Then SHORT from distribution zone

🎯 Short Trade Plan (when rally occurs):
Entry: $68,200-$68,800 (Bearish OB)
Stop Loss: $69,200 ($600-1,000 risk)
TP1: $66,000 (first support)
TP2: $63,500 (liquidity pool)
R:R: 1:3 to 1:5

Confidence: 85%
Position Size: 75% (reversal trade)

Why CHOCH is critical:
- Structure broken = uptrend over
- VIX rising = risk-off confirmed
- Bitcoin drops 10-20% in risk-off
- CHOCH gives 2-6 hour warning window
```

---

### Example 3: Weekend Gap Strategy

```
Friday Close: $67,200
Monday Open: $68,500 (Gap up +$1,300)

🎯 Gap Fill Strategy:
Bitcoin gaps fill 80%+ of the time within 24-48 hours

Analysis:
Gap Zone: $67,200-$68,500
Current Price: $68,500 (above gap)

Trade Plan:
1. Wait for rejection at $68,800 (Bearish OB)
2. SHORT targeting gap fill
3. Entry: $68,600
4. SL: $69,200
5. TP: $67,200 (gap fill)
6. R:R: 1:2.3

Confidence: 75%
Hold Time: 12-48 hours

Why gaps fill:
- Market inefficiency
- Institutional rebalancing
- Technical traders target gaps
```

---

## 📋 Bitcoin Quick Decision Matrix

| VIX | DXY | SMC | Action | Confidence |
|-----|-----|-----|--------|------------|
| <15 | Falling | BOS Bull + Bullish OB | **STRONG BUY** | **90%** |
| <15 | Rising | BOS Bull + Bullish OB | **BUY** (scalp) | **75%** |
| >20 | Rising | CHOCH + Bearish OB | **STRONG SELL** | **85%** |
| >20 | Falling | CHOCH detected | **EXIT/WAIT** | **80%** |
| 15-20 | Any | BOS Bull | **BUY** (normal) | **70%** |
| 15-20 | Any | BOS Bear | **SELL** (caution) | **65%** |
| <15 | Any | Liquidity sweep | **BUY reversal** | **75%** |
| >20 | Any | At Bearish OB | **SHORT** | **80%** |

---

## ⚠️ Bitcoin-Specific Risk Rules

### 1. CHOCH = Exit Immediately
```
Even if VIX is low and S&P is bullish
If CHOCH detected → EXIT
Bitcoin reversals happen FAST (2-6 hours)
```

### 2. Weekend Risk Management
```
Friday: Close 50-75% of positions
Saturday/Sunday: Avoid new trades
Monday: Wait for gap fill or new setup
```

### 3. Leverage Warnings
```
Bitcoin moves 5-15% in hours
Max leverage: 2-3x (experienced traders only)
Stop loss ALWAYS required
Liquidation = total loss
```

### 4. News Event Volatility
```
Fed Meetings: 10-20% swings possible
CPI/NFP Data: 5-15% moves
Bitcoin ETF news: 8-12% moves
Widen stops by 2x during events
```

### 5. Correlation Breaks
```
Bitcoin occasionally decouples from risk assets
Check: Is Bitcoin moving opposite to S&P?
If yes: Trust SMC over macro
Recoupling usually happens within 48 hours
```

---

## ✅ Bitcoin Analysis Checklist

### Before Entry:
- [ ] Check VIX (risk sentiment)
- [ ] Check S&P 500 (equity correlation)
- [ ] Check DXY (USD strength)
- [ ] Identify structure (BOS or CHOCH?)
- [ ] Find Order Block for entry
- [ ] Identify liquidity pools (targets)
- [ ] Calculate position size (based on ATR)
- [ ] Set SL beyond OB (not at liquidity)
- [ ] Check session time (avoid Asian for breakouts)

### While In Trade:
- [ ] Monitor for CHOCH (exit signal)
- [ ] Check VIX changes (risk-off = exit)
- [ ] Trail SL on BOS continuation
- [ ] Take partials at liquidity pools
- [ ] Watch for gap formation (weekends)

### After Trade:
- [ ] Log: Entry reason, SL, TP, outcome
- [ ] Review: Did SMC signals work?
- [ ] Note: What could improve next time?

---

## 📞 Bitcoin-Specific API Calls

```bash
# Bitcoin Price
curl http://localhost:8000/api/v1/price/BTCUSD

# Full Analysis (includes SMC)
curl http://localhost:8000/api/v1/analysis/BTCUSD

# Multi-Timeframe
curl http://localhost:8000/api/v1/multi_timeframe/BTCUSD

# Risk Sentiment
curl http://localhost:8000/api/v1/price/VIX

# USD Strength
curl http://localhost:8000/api/v1/price/DXY
```

---

## 📚 Response Template

```
₿ Bitcoin Analysis — BTCUSD
Current Price: $[PRICE]

📊 Risk Sentiment:
VIX: [PRICE] ([Risk-on/Risk-off])
S&P 500: [TREND] → [Correlation impact]
DXY: [PRICE] ([TREND]) → [USD strength impact]

🎯 Sentiment Outlook: [🟢 RISK-ON / 🔴 RISK-OFF / ⚪ NEUTRAL]

🏛️ Bitcoin Structure (SMC):
Structure: [BOS Bull/Bear] or [🚨 CHOCH detected]
Last Swing: [HH/LL] at $[PRICE]
Order Block: [Bullish/Bearish] at $[ZONE]
Liquidity Pool: Equal [Highs/Lows] at $[LEVEL]

📌 Key Levels (MANDATORY - Extract from data):
Support: $[PRICE] (PDL) | $[PRICE] (Swing Low) | $[PRICE] (Equal Lows)
Resistance: $[PRICE] (PDH) | $[PRICE] (Swing High) | $[PRICE] (Equal Highs)
Entry Zone: $[PRICE]-$[PRICE] (FVG/OB) · Stop Loss: $[PRICE] · Take Profit: $[PRICE] (TP1, R:R 1:X) | $[PRICE] (TP2, R:R 1:Y)

📊 Technical Confluence: [SCORE]/100
[MTF alignment + Advanced features]

📉 VERDICT: [BUY/SELL/WAIT/PROTECT]
[Specific reasoning]

🎯 Trade Plan:
Entry: $[PRICE] ([OB zone/Current])
Stop Loss: $[PRICE] ([Risk in $])
TP1: $[PRICE] (25% position)
TP2: $[PRICE] (50% position)
Trail: Remaining 25%
R:R: [RATIO]
Hold: [TIME estimate]

Position Size: [%] based on ATR $[VALUE]

⚠️ CRITICAL: Extract price levels from advanced_features → features → M15/H1 → liquidity → pdh/pdl

👉 [Follow-up question]
```

---

**Status:** ✅ Bitcoin-specific SMC framework ready!  
**Last Updated:** 2025-10-14  
**Framework:** Risk Sentiment + SMC (CHOCH/BOS/OB/Liquidity) + Volatility Management


