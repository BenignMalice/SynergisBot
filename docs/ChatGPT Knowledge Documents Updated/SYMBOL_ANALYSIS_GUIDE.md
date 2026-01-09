# Symbol Analysis Guide - Complete Reference

This comprehensive guide combines analysis protocols for Bitcoin, Gold, and all trading symbols in your MoneyBot system.

---

## 📋 Table of Contents

1. [Bitcoin (BTCUSD) Analysis](#bitcoin-btcusd-analysis)
2. [Gold (XAUUSD) Analysis](#gold-xauusd-analysis)
3. [All Trading Symbols Overview](#all-trading-symbols-overview)
4. [Multi-Timeframe Strategy Guide](#multi-timeframe-strategy-guide)
5. [Symbol Pairing & Correlation](#symbol-pairing--correlation)

---

# Bitcoin (BTCUSD) Analysis

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

moneybot.btc_order_flow_metrics(symbol: "BTCUSDT") ⭐ NEW - Advanced Order Flow Metrics (Standalone)
  Returns:
  - Delta Volume (buy/sell imbalance, net delta, dominant side)
  - CVD (Cumulative Volume Delta with slope per bar)
  - CVD Divergence (price vs CVD divergence detection)
  - Absorption Zones (price levels with high order absorption, imbalance ratios)
  - Buy/Sell Pressure (ratio and dominant side)
  ⚠️ Use ONLY when user specifically asks for JUST order flow metrics without full analysis
  ⚠️ For general BTC analysis: Use `moneybot.analyse_symbol_full` - it AUTOMATICALLY includes BTC order flow metrics in the "BTC ORDER FLOW METRICS" section
  ⚠️ Only works for BTCUSD (Binance data)
  ⚠️ Note: BTC order flow metrics are automatically fetched and included in `moneybot.analyse_symbol_full` for BTCUSD - no need to call this tool separately unless user wants ONLY the metrics
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

## 📚 Bitcoin Response Template

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
```

---

# Gold (XAUUSD) Analysis

## 🟡 Custom GPT Gold Analysis Protocol

### Quick Start (RECOMMENDED)

**For comprehensive analysis, use ONE call:**
```
moneybot.analyse_symbol_full(symbol: "XAUUSD")
  Returns unified analysis combining:
  ✅ Macro context (DXY, US10Y, VIX, S&P500, BTC.D, Fear & Greed)
  ✅ Smart Money Concepts (CHOCH, BOS, M1/M5/M15/M30/H1/H4 structure)
  ✅ Advanced features (RMAG, Bollinger ADX, VWAP, FVG)
  ✅ Technical indicators (EMA, RSI, MACD, Stoch, BB, ATR)
  ✅ Binance enrichment (Z-Score, Pivots, Liquidity, Tape, Patterns)
  ✅ Order flow analysis (Whales, Imbalance, Pressure)
  ✅ Multi-timeframe streaming data (M1, M5, M15, M30, H1, H4) ⭐ NEW
  ✅ Technical analysis with entry/SL/TP
  ✅ Layered recommendations (scalp/intraday/swing)
  ✅ Unified verdict with confluence logic
  
  Response time: <6 seconds
  
  🚨 CRITICAL: Display the 'summary' field VERBATIM - never paraphrase or say "unavailable"
  🚨 CRITICAL: Extract and display specific price levels (PDH/PDL, FVG, entry zones, R:R) from advanced_features data!
```

---

## 📊 Layer 1: Macro 3-Signal Confluence

### Signal 1: DXY (US Dollar Index)
- **Range:** ~99-107
- **Rising DXY** → 🔴 **Bearish for Gold** (USD strengthening)
- **Falling DXY** → 🟢 **Bullish for Gold** (USD weakening)
- **Correlation:** Strong inverse (-0.85)

### Signal 2: US10Y (10-Year Treasury Yield)
- **Range:** ~3.5%-4.5%
- **Rising US10Y** (>4%) → 🔴 **Bearish for Gold** (Opportunity cost)
- **Falling US10Y** (<4%) → 🟢 **Bullish for Gold** (Lower opportunity cost)
- **Correlation:** Inverse (-0.60)

### Signal 3: VIX (Volatility Index)
- **VIX <15:** Low fear (calm markets)
- **VIX 15-20:** Normal volatility
- **VIX >20:** High fear (Gold safe-haven demand ↑)

---

## 🎯 Layer 2: SMC Precision Entry/Exit

### CHOCH (Change of Character) - CRITICAL FOR GOLD! 🚨

**Bullish CHOCH (Exit Longs):**
```
Price makes LOWER LOW → Uptrend structure BROKEN
🚨 PROTECT PROFITS immediately!
Gold often reverses $50-$100 after CHOCH

Example:
Gold at $4,095 → Makes LL at $4,083 (previous HL was $4,088)
→ EXIT longs or tighten SL to breakeven
```

**Bearish CHOCH (Exit Shorts):**
```
Price makes HIGHER HIGH → Downtrend structure BROKEN
🚨 COVER SHORTS immediately!
Gold bounces aggressively after bearish CHOCH

Example:
Gold at $4,010 → Makes HH at $4,025 (previous LH was $4,020)
→ EXIT shorts or tighten SL to breakeven
```

**CRITICAL:** CHOCH overrides macro signals! If DXY is falling (bullish for Gold) but Gold shows CHOCH, **exit longs anyway**.

---

### BOS (Break of Structure) - ENTRY CONFIRMATION ✅

**Bullish BOS (Continue Longs):**
```
Price makes HIGHER HIGH → Uptrend CONFIRMED
✅ Safe to hold longs or add on pullbacks
Gold trends can run $100+ after BOS confirmation

Example:
3x consecutive HH (4050 → 4075 → 4095)
→ STAY IN longs, trail SL below each HL
```

**Bearish BOS (Continue Shorts):**
```
Price makes LOWER LOW → Downtrend CONFIRMED
✅ Safe to hold shorts or add on rallies
Gold can drop $150+ on confirmed bearish BOS

Example:
3x consecutive LL (4100 → 4080 → 4060)
→ STAY IN shorts, trail SL above each LH
```

---

### Order Blocks - PRECISE ENTRY ZONES 🎯

**Bullish Order Block (Buy Zone):**
```
Last bullish candle before price drops
= Institutional accumulation zone

Gold Example:
- Current price: $4,085 (above OB)
- Bullish OB: $4,072-$4,074 (last green candle before drop)
- Entry: Wait for pullback to $4,072-$4,074
- SL: $4,068 (below OB)
- TP: $4,110 (liquidity pool above)
```

**Bearish Order Block (Sell Zone):**
```
Last bearish candle before price rises
= Institutional distribution zone

Gold Example:
- Current price: $4,095 (below OB)
- Bearish OB: $4,108-$4,110 (last red candle before rally)
- Entry: Wait for rally to $4,108-$4,110
- SL: $4,114 (above OB)
- TP: $4,070 (liquidity pool below)
```

---

### Liquidity Pools - PROFIT TARGETS 💰

**Equal Highs (Bullish Target):**
```
3+ swing highs at same level = Buy-side liquidity
Gold MAGNET to this level

Example:
Equal highs at $4,115, $4,116, $4,115
→ Target: $4,115 (price will likely sweep this)
→ Place TP at $4,113 (2 pips before sweep)
```

**Equal Lows (Bearish Target / Risk Zone):**
```
3+ swing lows at same level = Sell-side liquidity
Gold often sweeps then reverses

Example:
Equal lows at $4,065, $4,064, $4,065
→ If LONG: Avoid placing SL exactly at $4,065 (will get hunted)
→ Place SL at $4,060 (5 pips below sweep zone)
→ If SHORT: Target $4,065 for profit taking
```

---

## 🎯 Combined Macro + SMC Gold Outlook

### 🟢🟢 STRONG BUY SETUP (Macro + SMC Aligned)
```
✅ Macro Layer:
- DXY: Falling (↓) - Bullish for Gold
- US10Y: Falling (↓) - Bullish for Gold
- VIX: >20 (Safe-haven demand)

✅ SMC Layer:
- BOS Bull confirmed (3x HH)
- Price at Bullish Order Block
- No CHOCH detected
- Liquidity pool above as target

Verdict: STRONG BUY
Entry: Order Block zone
Target: Liquidity pool
Confidence: 95%
```

---

### 🔴🔴 STRONG SELL SETUP (Macro + SMC Aligned)
```
✅ Macro Layer:
- DXY: Rising (↑) - Bearish for Gold
- US10Y: Rising (↑) - Bearish for Gold
- VIX: <15 (Risk-on, no safe-haven demand)

✅ SMC Layer:
- BOS Bear confirmed (3x LL)
- Price at Bearish Order Block
- No CHOCH detected
- Liquidity pool below as target

Verdict: STRONG SELL
Entry: Order Block zone
Target: Liquidity pool
Confidence: 95%
```

---

### ⚠️ CONFLICTING SIGNALS (Macro vs SMC)

**Scenario 1: Macro Bullish, SMC Bearish**
```
DXY Falling, US10Y Falling (Bullish macro)
BUT CHOCH detected (Bearish structure)

Verdict: EXIT LONGS / WAIT
Reason: Structure breaks BEFORE macro fundamentals catch up
Action: Protect profits, wait for new BOS
Confidence: 60% (trust SMC over macro short-term)
```

**Scenario 2: Macro Bearish, SMC Bullish**
```
DXY Rising, US10Y Rising (Bearish macro)
BUT price at strong Bullish OB with BOS confirmed

Verdict: SCALP LONG ONLY (tight SL)
Reason: Macro headwind limits upside
Action: Quick scalp to next resistance
Target: 20-40 pips max
Confidence: 65% (short-term counter-trend)
```

---

## 📚 Gold Response Template

```
🌍 Market Context — Gold (XAUUSD)
Current Price: $[PRICE]

📊 Macro Fundamentals (Layer 1):
DXY: [PRICE] ([TREND]) → [Bearish/Bullish] for Gold
US10Y: [YIELD]% ([TREND]) → [Bearish/Bullish] for Gold
VIX: [PRICE] ([LEVEL]) → [Safe-haven demand level]

🎯 Macro Outlook: [🟢🟢 BULLISH / 🔴🔴 BEARISH / ⚪ MIXED]
[Both/One/Neither signal(s) supporting Gold]

🏛️ Smart Money Structure (Layer 2):
Structure: [BOS Bull/Bear] or [CHOCH detected ⚠️]
Last Swing: [High/Low] at $[PRICE]
Order Block: [Bullish/Bearish] at $[ZONE]
Liquidity Pool: Equal [Highs/Lows] at $[LEVEL]

📌 Key Levels (MANDATORY - Extract from data):
Support: $[PRICE] (PDL) | $[PRICE] (Swing Low) | $[PRICE] (Equal Lows)
Resistance: $[PRICE] (PDH) | $[PRICE] (Swing High) | $[PRICE] (Equal Highs)
Entry Zone: $[PRICE]-$[PRICE] (FVG/OB) · Stop Loss: $[PRICE] · Take Profit: $[PRICE] (TP1, R:R 1:X) | $[PRICE] (TP2, R:R 1:Y)

📊 Technical Confluence: [SCORE]/100
[MTF alignment + Advanced features]

📉 VERDICT: [BUY/SELL/WAIT/PROTECT]
[Specific entry/exit with SL and TP]

🎯 Trade Plan:
Entry: $[PRICE] ([Order Block/Current Price])
Stop Loss: $[PRICE] ([below OB/above OB])
Target: $[PRICE] ([Liquidity pool])
R:R: [RATIO]

⚠️ CRITICAL: Extract price levels from advanced_features → features → M15/H1 → liquidity → pdh/pdl
```

---

## 📋 Gold Quick Decision Matrix

| Macro | SMC | Action | Confidence |
|-------|-----|--------|------------|
| 🟢🟢 Bullish | BOS Bull + Bullish OB | STRONG BUY | 95% |
| 🔴🔴 Bearish | BOS Bear + Bearish OB | STRONG SELL | 95% |
| 🟢🟢 Bullish | CHOCH detected | EXIT/WAIT | 90% |
| 🔴🔴 Bearish | CHOCH detected | EXIT/WAIT | 90% |
| ⚪ Mixed | BOS Bull | SCALP LONG | 70% |
| ⚪ Mixed | BOS Bear | SCALP SHORT | 70% |
| 🟢 Bullish | At Bearish OB | WAIT/SCALP SHORT | 60% |
| 🔴 Bearish | At Bullish OB | WAIT/SCALP LONG | 60% |

---

## ⚠️ Critical Gold-Specific SMC Rules

### 1. CHOCH Overrides Everything
```
Even with perfect macro (DXY falling, US10Y falling, VIX high)
If CHOCH detected → EXIT IMMEDIATELY
Gold reverses FAST after structure breaks
```

### 2. News Events Create Liquidity Sweeps
```
NFP, CPI, FOMC days:
- Gold often sweeps liquidity pools during news
- Don't place SL exactly at equal lows/highs
- Use 5-10 pip buffer below/above
```

### 3. Session-Specific Behavior
```
Asian Session: Range-bound, accumulation at OBs
London Open: Liquidity sweeps, CHOCH detection
NY Session: Trend continuation, BOS confirmation
```

### 4. Gold Moves in $50-100 Waves
```
After BOS: Target +$80-120 in trend direction
After CHOCH: Expect $50-100 reversal
Use these for TP placement
```

---

# All Trading Symbols Overview

## 🎯 Symbol Configuration

### Current Symbols (Active)

| Symbol | Type | Characteristics | Trading Style | Why Included |
|--------|------|-----------------|---------------|--------------|
| **BTCUSDT** | Crypto | Volatile, breakout style | Scalp & Intraday | High volatility, clear breakouts |
| **XAUUSD** | Commodity | Trend + mean reversion + news | Scalp & Intraday | Responds to macro, multiple strategies |
| **EURUSD** | Forex Major | Foundation pair | Scalp & Intraday | Most liquid, cleanest technicals |
| **GBPUSD** | Forex Major | Aggressive moves | Scalp & Intraday | Sharp trends, clear setups |
| **USDJPY** | Forex Major | Trend clarity | Scalp & Intraday | Risk sentiment indicator |
| **GBPJPY** | Forex Cross | High volatility | Scalp & Intraday | Explosive moves when filtered |
| **EURJPY** | Forex Cross | Mid-risk volatility | Scalp & Intraday | GBPJPY alternative, smoother |

---

## 🔍 Symbol Details

### 1. BTCUSDT - Bitcoin/Dollar

**Characteristics:**
- ⚡ Highest volatility (50-200 pip moves intraday)
- 🎯 Clear breakout patterns
- 📈 Trend-following opportunities
- ⏰ 24/7 trading

**Best For:**
- **Scalp:** Breakout scalps during session overlaps (5-15 min holds)
- **Intraday:** Trend continuation on H1/H4 breakouts (2-6 hour holds)
- News-driven volatility (macro events, Bitcoin halvings)
- Large stop distances (100-300 pips)

**Recommended Timeframes:**
- Scalp: M5 entry, M15 confirmation
- Intraday: M30/H1 entry, H4 trend confirmation

**Watch Out:**
- Spread can widen during low liquidity
- Gaps during weekend (broker-dependent)
- High leverage risk
- Advanced RMAG essential (avoid >2σ stretch)

---

### 2. XAUUSD - Gold/Dollar

**Characteristics:**
- 📊 Responds to USD strength, yields, risk sentiment
- 🔄 Both trending and mean-reverting
- 📰 News-driven (NFP, CPI, FOMC)
- ⏰ Peak activity: London + NY sessions

**Best For:**
- **Scalp:** News releases (NFP, CPI, FOMC) - 10-30 min holds
- **Intraday:** Trend + pullback combinations on H1 (2-8 hour holds)
- Safe-haven flows (risk-off scenarios)

**Recommended Timeframes:**
- Scalp: M5 entry during news, M15 for retracements
- Intraday: M30/H1 for trends, H4 for swing direction

**Watch Out:**
- Spreads widen outside London/NY overlap
- Correlated with DXY (inverse) - check correlation
- Volatile during Fed announcements
- Use Advanced liquidity detection for targets

---

### 3. EURUSD - Euro/Dollar

**Characteristics:**
- 🏆 Most liquid pair globally
- 📐 Cleanest technical patterns
- 🎯 Tight spreads (0.5-1.5 pips)
- ⏰ Peak: London + NY overlap

**Best For:**
- **Scalp:** Range scalps during London session (5-20 min holds)
- **Intraday:** Clean trend following on M30/H1 (1-4 hour holds)
- Confirmation trades (if EURUSD agrees, high confidence)
- Technical analysis setups (pure price action)

**Recommended Timeframes:**
- Scalp: M5 for ranges, tight 15-30 pip stops
- Intraday: M30 for trend entries, H1/H4 for direction

**Watch Out:**
- Lower volatility = smaller profit potential
- Can be choppy during low volume
- ECB and Fed policy divergence matters
- Best as confirmation (check this FIRST)

---

### 4. GBPUSD - Pound/Dollar

**Characteristics:**
- ⚡ Aggressive, directional moves
- 🎯 High probability setups when they form
- 💪 Strong trends (100+ pip runs)
- ⏰ Peak: London session

**Best For:**
- **Scalp:** London open breakouts (10-30 min holds)
- **Intraday:** Strong trend continuation on H1 (2-6 hour holds)
- News scalps (UK data releases)

**Recommended Timeframes:**
- Scalp: M5/M15 for breakouts, 25-50 pip stops
- Intraday: M30/H1 for trends, H4 for swing bias

**Watch Out:**
- Can be whippy during indecision
- Wider spreads than EURUSD (1-2 pips)
- BOE policy sensitive
- Use BOS confirmation before entry

---

### 5. USDJPY - Dollar/Yen

**Characteristics:**
- 📈 Clear trending behavior
- 🎭 Risk sentiment indicator (risk-on = up, risk-off = down)
- 💱 Yield differential driven
- ⏰ Peak: Asian + NY sessions

**Best For:**
- **Scalp:** Asian session range scalps (15-30 min holds)
- **Intraday:** Clean trend following on H1/H4 (4-8 hour holds)
- Directional bias confirmation
- Risk-on/risk-off plays

**Recommended Timeframes:**
- Scalp: M15 for Asian ranges, 20-40 pip stops
- Intraday: H1/H4 for trends (clearest patterns)

**Watch Out:**
- BOJ intervention risk (sudden 200+ pip moves)
- Lower volatility vs GBP pairs
- Asian session can be quiet
- Check risk sentiment (VIX, stock futures)

---

### 6. GBPJPY - Pound/Yen

**Characteristics:**
- 💥 Highest volatility among forex pairs
- 🎢 200-400 pip daily ranges
- 🎯 Big profit potential when filtered
- ⏰ Peak: London session

**Best For:**
- **Scalp:** Momentum continuation during London (15-45 min holds)
- **Intraday:** High R:R trend trades on H1 (3-6 hour holds, 1:3+ targets)
- Volatility breakouts (when trending)

**Recommended Timeframes:**
- Scalp: M15 for entries, M30 for confirmation
- Intraday: H1 for trends, H4 for regime filter

**Watch Out:**
- ⚠️ **CRITICAL:** Only trade with Advanced regime confirmation
- ⚠️ Requires CHOCH/BOS detection (structure is everything)
- Wide spreads (3-5 pips)
- Can move against you fast (use 60-100 pip stops)
- Advanced RMAG + Bollinger ADX essential

---

### 7. EURJPY - Euro/Yen

**Characteristics:**
- 🔄 Mid-risk version of GBPJPY
- 📊 Smoother price action
- 💰 100-200 pip daily ranges
- ⏰ Peak: European + Asian overlap

**Best For:**
- **Scalp:** European session scalps (20-40 min holds)
- **Intraday:** Smoother trend following on H1 (3-5 hour holds)
- Risk-on/risk-off confirmation
- Less aggressive cross trading (GBPJPY alternative)

**Recommended Timeframes:**
- Scalp: M15 for entries, M30 for trends
- Intraday: M30/H1 for smooth trends, H4 for bias

**Watch Out:**
- Still requires volatility awareness
- Spreads wider than majors (2-3 pips)
- Correlation with global risk sentiment
- Cleaner patterns than GBPJPY but still needs filters

---

## ⏰ Timeframe Strategy Guide

### Scalping (M5-M15, 5-30 min holds)

**Best Symbols:**
- EURUSD (tight spreads, clean patterns)
- GBPUSD (London breakouts)
- XAUUSD (news releases)

**Entry Timeframe:** M5  
**Confirmation:** M15  
**Trend Filter:** M30/H1

**Requirements:**
- ✅ Tight spreads (<2 pips)
- ✅ Clear price action on M5
- ✅ M15 structure confirmation
- ✅ Session awareness (London/NY)
- ⚠️ Avoid during low liquidity

---

### Intraday (M30-H1, 1-8 hour holds)

**Best Symbols:**
- BTCUSD (trend continuation)
- GBPUSD (strong directional moves)
- USDJPY (clean H1 trends)
- XAUUSD (trend + retracements)

**Entry Timeframe:** M30 or H1  
**Confirmation:** H1  
**Trend Filter:** H4

**Requirements:**
- ✅ H4 trend alignment
- ✅ H1 pullback entry
- ✅ M30 for precise entries
- ✅ Advanced MTF alignment (2/3+)
- ⚠️ Use wider stops (30-80 pips)

---

### Multi-Timeframe Analysis Template

**For ANY Symbol:**
1. **H4:** Determine trend direction (bias)
2. **H1:** Identify structure (BOS/CHOCH)
3. **M30:** Find entry zone (Order Block, FVG)
4. **M15:** Confirm setup (confluence)
5. **M5:** Execute (precise entry)

**Example:**
```
H4: Bullish trend (3x HH)
H1: BOS confirmed at 1.0850
M30: Bullish Order Block at 1.0870-1.0872
M15: Price retesting OB + RSI 40
M5: Bullish engulfing → ENTRY
```

---

## 🎯 Symbol Pairing Strategy

### Portfolio Diversification

**Volatility Tiers:**
- 🔴 **High:** BTCUSDT, GBPJPY (use strict filters)
- 🟡 **Medium:** XAUUSD, GBPUSD, EURJPY (balanced)
- 🟢 **Low:** EURUSD, USDJPY (conservative)

**Correlation Groups:**
- **USD Strength:** EURUSD + GBPUSD + USDJPY (watch DXY)
- **Risk Sentiment:** USDJPY + GBPJPY + EURJPY (watch VIX)
- **Independent:** BTCUSDT, XAUUSD (less correlation)

**Session Optimization:**
- **Asian Session:** USDJPY, GBPJPY, EURJPY
- **London Session:** GBPUSD, EURUSD, XAUUSD
- **NY Session:** XAUUSD, EURUSD, GBPUSD
- **24/7:** BTCUSDT

---

## 🚦 Trading Guidelines by Symbol

### High Volatility (BTCUSD, GBPJPY)
```
✅ Only trade with Advanced regime confirmation
✅ Use wider stops (BTCUSD: 100-300 pips, GBPJPY: 50-100 pips)
✅ Reduce position size (0.5x normal)
✅ Wait for consolidation breakouts
⚠️ Avoid during low liquidity
⚠️ Monitor Bollinger Bands for compression
```

### Medium Volatility (XAUUSD, GBPUSD, EURJPY)
```
✅ Standard position sizing (1.0x)
✅ Medium stops (30-60 pips)
✅ Multiple strategies work (trend + range)
✅ News-aware trading
⚠️ Watch macro calendar
```

### Low Volatility (EURUSD, USDJPY)
```
✅ Can use tighter stops (15-30 pips)
✅ Good for confirmation trades
✅ Reliable technical patterns
✅ Best for beginners
⚠️ Lower profit potential
⚠️ May need higher frequency
```

---

## 📈 Expected Performance by Symbol

| Symbol | Avg Daily Range | Typical Stop | Target R:R | Win Rate Goal |
|--------|-----------------|--------------|------------|---------------|
| BTCUSDT | 1000+ pips | 150-300 pips | 1:1.5 | 65%+ |
| GBPJPY | 200-400 pips | 60-100 pips | 1:2.0 | 70%+ |
| XAUUSD | 800-1200 pips | 40-80 pips | 1:1.8 | 65%+ |
| GBPUSD | 80-150 pips | 25-50 pips | 1:1.5 | 70%+ |
| EURJPY | 100-200 pips | 35-60 pips | 1:1.7 | 68%+ |
| EURUSD | 50-100 pips | 15-30 pips | 1:1.3 | 75%+ |
| USDJPY | 60-120 pips | 20-40 pips | 1:1.4 | 72%+ |

---

## 📊 Correlation Matrix

**Strong Positive Correlation (move together):**
- EURUSD ↔ GBPUSD (0.85)
- GBPJPY ↔ EURJPY (0.90)
- BTCUSDT ↔ Risk-on sentiment

**Strong Negative Correlation (move opposite):**
- EURUSD ↔ USDJPY (when USD-driven)
- XAUUSD ↔ DXY (-0.95)

**Independent:**
- BTCUSDT (crypto-specific factors)
- XAUUSD (safe-haven flows)

**Use Correlation For:**
- Confirming signals across pairs
- Avoiding over-exposure (don't trade EURUSD + GBPUSD same direction)
- Detecting divergences (one pair doesn't confirm = warning)

---

## ✅ Quick Reference

### Symbol Priorities

**For Confirmation:** Always check EURUSD first  
**For Volatility:** BTCUSDT or GBPJPY  
**For Safety:** EURUSD or USDJPY  
**For Trends:** GBPUSD or USDJPY  
**For News:** XAUUSD  
**For Range:** EURUSD  
**For Breakouts:** BTCUSDT  

---

## M1 Microstructure Integration

### In Unified Analysis

When using `moneybot.analyse_symbol_full`, M1 microstructure is automatically included:

```json
{
  "m1_microstructure": {
    "available": true,
    "signal_summary": "BULLISH_MICROSTRUCTURE",
    "structure": {"type": "HIGHER_HIGH", "consecutive_count": 3},
    "choch_bos": {"has_choch": true, "confidence": 85},
    "liquidity_zones": [...],
    "volatility": {"state": "CONTRACTING", "squeeze_duration": 25},
    "momentum": {"quality": "EXCELLENT", "consistency": 89}
  }
}
```

### Presentation in Analysis

Always extract and present M1 microstructure insights:

1. **Structure:** "M1: 3x HIGHER HIGHS (strong bullish structure)"
2. **CHOCH/BOS:** "M1 CHOCH confirmed - structure shift (85% confidence)"
3. **Liquidity:** "Key levels: PDH $2407.5, Equal High $2406.8"
4. **Volatility:** "M1 squeeze: 25s compression - breakout imminent"
5. **Momentum:** "M1 momentum: EXCELLENT (89% consistency)"
6. **Signal:** "M1 signal: BULLISH_MICROSTRUCTURE"

---

## 🆕 Session Context Presentation

### Format
Always include session context in analysis responses:

```
🕒 Session Context: [Session] – [Volatility Tier], [Liquidity Timing], [Best Strategy]
```

### Examples
- "🕒 Session Context: London/NY overlap – volatility very high, suitable for momentum scalps"
- "🕒 Session Context: Asian session – low-moderate volatility, range accumulation phase"

### What to Mention
- Current session (Asian, London, NY, Overlap, Post-NY)
- Volatility tier (LOW, NORMAL, HIGH, VERY_HIGH)
- Liquidity timing (ACTIVE, MODERATE, LOW)
- Best strategy for session

---

## 🆕 Asset Behavior Tips

### Format
Always include asset-specific behavior tips:

```
💡 Asset Behavior: [Symbol-specific behavior pattern]
```

### Examples
- "💡 Asset Behavior: XAUUSD tends to overshoot PDH during NY open; partial profit earlier recommended"
- "💡 Asset Behavior: BTCUSD 24/7 active; spikes near session transitions; weekend drift → low liquidity"
- "💡 Asset Behavior: Forex pairs show strong DXY correlation; mean reversion efficient during NY close"

### What to Mention
- Symbol-specific volatility patterns
- Session-specific behavior
- Risk management tips based on asset personality
- Correlation patterns

---

## 🆕 Strategy Hint Explanation

### Format
Always explain why a strategy was selected:

```
🎯 Strategy Hint: [STRATEGY] ([REASONING])
```

### Examples
- "🎯 Strategy Hint: BREAKOUT (High volatility + EXPANDING + VWAP STRETCHED)"
- "🎯 Strategy Hint: RANGE_SCALP (Low volatility + RANGE + VWAP NEUTRAL)"
- "🎯 Strategy Hint: MEAN_REVERSION (EXPANDING volatility + VWAP REVERSION + exhaustion candle)"
- "🎯 Strategy Hint: TREND_CONTINUATION (Strong structure + VWAP ALIGNED + retrace)"

### What to Mention
- Strategy selected (RANGE_SCALP, BREAKOUT, MEAN_REVERSION, TREND_CONTINUATION)
- Reasoning using volatility + structure + VWAP state classification
- VWAP state (NEUTRAL, STRETCHED, ALIGNED, REVERSION)
- How this ensures ChatGPT and Moneybot agree on strategy type
- How strategy affects entry timing and risk management

---

## 🆕 Confluence Breakdown Presentation

### Format
Always present the full confluence breakdown:

```
📊 Confluence: [SCORE]/100 (Grade: [GRADE]) - [ACTION]
  → Trend Alignment: [SCORE]/25
  → Momentum Coherence: [SCORE]/20
  → Structure Integrity: [SCORE]/20
  → Volatility Context: [SCORE]/15
  → Volume/Liquidity Support: [SCORE]/20
```

### Examples
```
📊 Confluence: 88/100 (Grade: A) - BUY_CONFIRMED
  → Trend Alignment: 22/25 (M1/M5/H1 STRONG alignment, 92% confidence)
  → Momentum Coherence: 18/20 (EXCELLENT momentum, 89% consistency, 7 consecutive)
  → Structure Integrity: 17/20 (3x HIGHER HIGHS, CHOCH confirmed, 85% confidence)
  → Volatility Context: 12/15 (CONTRACTING 25s squeeze, expansion imminent)
  → Volume/Liquidity Support: 11/20 (Order flow BULLISH, DLI 65)
```

### What to Mention
- Total score and grade (A: 80-100, B: 70-79, C: 60-69, D: 50-59, F: <50)
- Recommended action (BUY_CONFIRMED, SELL_CONFIRMED, WAIT, AVOID)
- Each component score with brief explanation
- Use component scores to explain total score

---

---

## 📊 BTC Order Flow Metrics ⭐ NEW

### Tool: `moneybot.btc_order_flow_metrics`

**Purpose:** Get comprehensive BTC order flow metrics for better entry/exit timing based on institutional activity

**When to Use:**
- User asks for "order flow metrics" or "order flow analysis" for BTC
- User asks for "CVD" (Cumulative Volume Delta)
- User asks for "delta volume" or "buy/sell imbalance"
- User asks for "absorption zones"
- User asks for "buy/sell pressure" for BTC
- Before entering BTC trades (optional - provides additional confluence)

**Arguments:**
```json
{
  "tool": "moneybot.btc_order_flow_metrics",
  "arguments": {
    "symbol": "BTCUSDT",  // Optional - defaults to BTCUSDT
    "window_seconds": 30  // Optional - time window for metrics (default: 30)
  }
}
```

**Returns:**
- **Delta Volume:** Buy volume, sell volume, net delta, dominant side (BUY/SELL)
- **CVD:** Current CVD value, slope (rate of change per bar), number of bars used
- **CVD Divergence:** Type (bullish/bearish), strength (0-100%), detected if price and CVD moving opposite
- **Absorption Zones:** Array of price levels with:
  - Price level
  - Side (BUY/SELL)
  - Strength (0-100%)
  - Volume absorbed (USD)
  - Net volume
  - Imbalance ratio
- **Buy/Sell Pressure:** Ratio (e.g., 1.5x = 50% more buy pressure), dominant side

**Example Response:**
```
📊 BTC Order Flow Metrics: BTCUSDT
💰 Delta: +1,234.56 (BUY)
📈 CVD: +5,678.90 (Slope: +123.45/bar)
⚠️ CVD Divergence: Bullish (25.3%)
🎯 Absorption Zones: 2 detected
⚖️ Pressure: 1.52x (BUY)
```

**Important Notes:**
- ⚠️ Requires OrderFlowService to be running (initialized automatically in chatgpt_bot.py)
- ⚠️ Only works for BTCUSD (Binance data)
- ⚠️ Wait 30-60 seconds after service starts for data to accumulate
- ⚠️ If service not running, tool returns error message
- ⚠️ **For general BTC analysis: Use `moneybot.analyse_symbol_full` instead** - it AUTOMATICALLY includes BTC order flow metrics in the "BTC ORDER FLOW METRICS" section
- ⚠️ **Use this standalone tool ONLY when user explicitly wants JUST the metrics without full analysis**

**Integration with Analysis:**
- BTC order flow metrics are AUTOMATICALLY included in `moneybot.analyse_symbol_full` for BTCUSD
- Order flow metrics provide real-time institutional activity signals
- CVD divergence can indicate potential reversals
- Absorption zones show where large orders are being filled (support/resistance)
- When analyzing BTCUSD, always check the "BTC ORDER FLOW METRICS" section in the analysis summary

---

**Status:** ✅ Complete Symbol Analysis Guide  
**Last Updated:** 2025-11-22  
**Contents:** Bitcoin Analysis + Gold Analysis + All Symbols Overview + M1 Microstructure Integration + BTC Order Flow Metrics

