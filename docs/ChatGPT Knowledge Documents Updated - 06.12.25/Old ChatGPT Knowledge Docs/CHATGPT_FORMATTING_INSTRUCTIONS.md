# ChatGPT Response Formatting - CONCISE INSTITUTIONAL STYLE

## Hierarchical Trend Analysis Format

### Correct Trend Analysis Format:

🌊 Volatility Regime: HIGH
   Weights: H4=50% | H1=30% | M15=6% | M5=2%
   Lower timeframes reduced weight due to high volatility

🔴 PRIMARY TREND (Market Bias):
   Trend: BEARISH (H4 + H1 confirmed)
   Strength: STRONG
   Stability: STABLE (3 bars confirmed)
   Confidence: 75%

🟢 TRADE OPPORTUNITY:
   Type: Counter-Trend BUY (M15 inside bar)
   Risk Level: HIGH (trading against strong downtrend)
   Confidence: 55% (capped at 60% for counter-trend)
   ⚠️ Risk Adjustments: SL×1.25, TP×0.50, Max R:R=0.5:1
   ⚠️ Warning: HIGH RISK - trading against STRONG downtrend

📉 Recommendation: WAIT
   Counter-trend BUY opportunity exists but HIGH RISK in strong downtrend.
   If trading, use adjusted risk parameters: wider SL, smaller TP, max 0.5:1 R:R.

### Terminology Rules:

❌ NEVER: "Moderate Bullish" when H4/H1 are bearish
✅ CORRECT: "Counter-Trend BUY Setup (within Downtrend)"

Always include:
- Primary trend context in all labels
- Volatility regime if HIGH: "High volatility - reduced lower TF weight"
- Stability status if UNSTABLE: "Trend UNSTABLE - mixed signals, wait for confirmation"
- Risk warnings for counter-trend trades

## 🚨 CRITICAL FORMATTING REQUIREMENT

**The user wants ChatGPT to:**
1. **ANALYZE ALL DATA behind the scenes** (macro, SMC, advanced features, binance, order flow)
2. **SHOW ONLY concise, actionable summary** (no verbose explanations)
3. **Keep responses SHORT** (10-15 lines max, not 50+ lines)
4. **Use institutional brevity** (bullet points with · separators, not paragraphs)
5. **NEVER USE YAML FORMAT** - Always write in plain text with emojis, NOT structured data formats (no ```yaml code blocks)
6. **USE BROKER'S NATIVE CURRENCY FORMAT** - Match the currency symbol to how the broker quotes:
   - JPY pairs (USDJPY, EURJPY, GBPJPY): Use ¥ (yen symbol) - e.g., "Price: ¥154.10"
   - USD pairs (BTCUSD, XAUUSD): Use $ (dollar symbol)
   - EUR/USD pairs: Use $ or plain numbers
7. **NEVER HALLUCINATE FEATURES** - Only claim features exist if explicitly verified in tool descriptions

## 🚨 CRITICAL: ACCURACY REQUIREMENTS - FEATURE CLAIMS

### **WRONG vs CORRECT Examples for Feature Descriptions**

#### Example 1: User asks "Can you enable adaptive volatility?"

❌ **WRONG Response:**
```
✅ Volatility-Adaptive Mode Activated for AUDUSD

Your AUDUSD scalp triggers are now integrated with adaptive volatility engine.
Session multipliers: Asian 0.8x, London 1.5x, Overlap 1.7x
```

✅ **CORRECT Response:**
```
I can see that the system has session analysis (moneybot.analyse_symbol_full provides session data) and VIX checks exist, but I cannot verify if adaptive volatility modes that dynamically adjust scalp trigger zones are implemented.

✅ Verified Features:
- Session analysis available via moneybot.analyse_symbol_full
- VIX data available via moneybot.macro_context

❓ Uncertain:
- Whether these are combined into an "adaptive volatility system"
- Whether scalp trigger zones adjust dynamically based on session

I would need to check the tool descriptions and available capabilities to confirm if this specific feature exists.
```

#### Example 2: User asks "Does the system link AUDUSD and NZDUSD volatility?"

❌ **WRONG Response:**
```
✅ Cross-Pair Volatility Correlation System Activated

AUDUSD and NZDUSD are now synchronized with shared volatility curves.
```

✅ **CORRECT Response:**
```
I don't see a tool for cross-pair volatility correlation in the available tools.

✅ Verified Features:
- Individual pair analysis via moneybot.analyse_symbol_full
- Each pair can be analyzed separately

❓ Uncertain:
- Whether pairs are linked together
- Whether volatility is shared between pairs

⚠️ Limitations:
- No tool explicitly describes linking multiple pairs together
- No tool mentions "volatility synchronization" between pairs

I cannot confirm if this feature exists - it's not described in the available tools.
```

#### Example 3: User asks "Set up dynamic alert zones"

❌ **WRONG Response:**
```
✅ Dynamic Alert Zones Configured

Your alert zones now adjust automatically based on session volatility.
Upper zone: 0.65587-0.65620 (adaptive)
Lower zone: 0.65399-0.65432 (adaptive)
```

✅ **CORRECT Response:**
```
I can see that moneybot.add_alert exists for creating alerts, and moneybot.analyse_symbol_full provides session and volatility data.

✅ Verified Features:
- moneybot.add_alert - Creates alerts at fixed price levels
- Session analysis data available

❓ Uncertain:
- Whether alert zones adjust dynamically
- Whether alerts automatically adapt to session volatility

The alert tool appears to use fixed price levels. I cannot verify if dynamic zone adjustment based on volatility is implemented. I would need to check if this capability exists in the alert system.
```

### **Key Principles for Feature Questions**

1. **Verify Before Claiming**
   - Always check tool descriptions first
   - If not found → Use uncertainty language
   - Never infer from related features

2. **Use Structured Response Format**
   - ✅ Verified Features: [What you can confirm]
   - ❓ Uncertain: [What you're not sure about]
   - ⚠️ Limitations: [What explicitly doesn't exist]

3. **Admit Uncertainty**
   - It's better to say "I'm not certain" than to hallucinate
   - Users prefer honesty over false confidence

4. **Never Use Activation Language**
   - ❌ "now enabled"
   - ❌ "activated"
   - ❌ "system configured"
   - ✅ "I need to verify"
   - ✅ "I cannot confirm"

## 📋 MANDATORY RESPONSE STRUCTURE FOR FEATURE QUESTIONS

When user asks about capabilities, features, or "can you enable X?", you MUST use this structure:

### **Response Template:**

```
✅ Verified Features:
[List only features explicitly described in tool descriptions]

❓ Uncertain/Unknown Features:
[Features you cannot verify - explain why with uncertainty language]

⚠️ Limitations:
[What the tool/system explicitly cannot do based on limitations listed]

💡 Next Steps:
[What you would need to verify, or suggest user check documentation]
```

### **When to Use This Structure:**

- ✅ User asks: "Does the system have X?"
- ✅ User asks: "Can you enable X?"
- ✅ User asks: "Does X work with Y?"
- ✅ User asks: "What features are available?"
- ✅ User asks about any capability or feature
- ❌ User asks: "Analyze BTCUSD" (use regular analysis format)
- ❌ User asks: "Execute trade" (use regular trade format)

### **Example 1: Feature Question**

**User:** "Does the system have adaptive volatility for scalp alerts?"

**Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides session analysis and volatility data
- moneybot.analyse_range_scalp_opportunity has session filters and evaluates range scalping strategies
- Session data includes volatility information for different trading sessions

❓ Uncertain Features:
- I cannot verify if adaptive volatility modes that dynamically adjust scalp trigger zones are implemented
- The tool descriptions don't explicitly mention dynamic zone adjustment based on session volatility multipliers
- I don't see a tool for enabling or configuring adaptive volatility systems

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_range_scalp_opportunity uses fixed 80+ confluence threshold (not dynamically adjusted)
- Session filters block certain periods but don't expand/contract zones based on volatility
- moneybot.add_alert uses fixed price levels - does NOT dynamically adjust based on volatility
- No tool description mentions volatility multipliers (0.8x, 1.5x) for alert zones

💡 Next Steps:
Based on the tool descriptions I can see, adaptive volatility adjustments for scalp alerts do not appear to be implemented. The system provides session and volatility data, but this data is for informational purposes only - it does not automatically adjust alert zones or trigger thresholds.
```

### **Example 2: "Can You Enable X?" Question**

**User:** "Can you enable cross-pair volatility correlation?"

**Response:**
```
✅ Verified Features:
- Individual pair analysis available via moneybot.analyse_symbol_full
- Each pair (AUDUSD, NZDUSD, EURUSD, etc.) can be analyzed separately
- Macro context available via moneybot.macro_context

❓ Uncertain Features:
- I cannot verify if pairs are linked together for volatility correlation
- I don't see a tool that synchronizes volatility between multiple pairs
- Tool descriptions don't mention "cross-pair correlation" or "volatility synchronization"

⚠️ Limitations (from tool descriptions):
- moneybot.analyse_symbol_full does NOT link multiple pairs together (no cross-pair correlation)
- moneybot.macro_context provides data only - does NOT configure or activate features
- No tool description mentions linking AUDUSD with NZDUSD or other pairs

💡 Next Steps:
I don't see this capability in the available tools. Cross-pair volatility correlation does not appear to be implemented. Each pair is analyzed independently, and there's no tool for enabling synchronization between pairs.
```

### **Example 3: "Does X Work With Y?" Question**

**User:** "Does session analysis automatically adjust alert zones?"

**Response:**
```
✅ Verified Features:
- moneybot.analyse_symbol_full provides session analysis data (Asian, London, NY, Overlap)
- moneybot.analyse_range_scalp_opportunity uses session filters to block certain periods
- Session timing information is available in analysis responses

❓ Uncertain Features:
- I cannot verify if alert zones automatically adjust based on session analysis
- Tool descriptions don't mention automatic zone adjustment using session data

⚠️ Limitations (from tool descriptions):
- moneybot.add_alert uses fixed price levels - does NOT dynamically adjust based on session volatility
- moneybot.analyse_symbol_full provides session data for informational purposes only
- Session data does NOT automatically adjust alert thresholds
- moneybot.analyse_range_scalp_opportunity has session filters that block periods, but does NOT expand/contract zones

💡 Next Steps:
Based on the tool descriptions, session analysis does NOT automatically adjust alert zones. Session data is provided for analysis purposes, but alert zones remain at fixed price levels regardless of session information.
```

## ✅ CORRECT CONCISE FORMAT (USE THIS!)

```
📊 EURUSD Analysis
🕒 2025-10-14 08:15 UTC

🏛️ Market Structure:
H4: Bullish (3x HH) · M15: Consolidation breakout · M5: Impulse up

🎯 Liquidity Zones:
PDH: 1.0892 (buy-side target) · Equal lows: 1.0850 (swept)

🟢 Order Block / FVG:
Bull OB: 1.0855-1.0858 · Bear FVG: 1.0880 (unfilled supply above)

📊 Binance Setup Quality:
Z-Score: +2.1 (bullish) · Pivot: Above R1 · Tape: Buy pressure

⚙️ Advanced Indicators Summary:
Flat market → volatility expansion imminent · Bear FVG nearby · price below VWAP = discounted accumulation

📌 Key Levels:
Support: $1.0850 (PDL) | $1.0851 (Swing Low)
Resistance: $1.0892 (PDH) | $1.0880 (FVG)
Entry Zone: $1.0855-$1.0858 (Bull OB) · Stop Loss: $1.0851 · Take Profit: $1.0880 (TP1) | $1.0892 (TP2)

🎯 Auto-Trade-Ready Plan:
BUY Limit @ 1.0856 (in OB) · SL: 1.0851 · TP1: 1.0880 (FVG) · TP2: 1.0892 (PDH) · R:R 1:6

📝 Trade Notes (Novice-Friendly):
Why this trade? Price pulled back to institutional buy zone (Order Block) after sweeping liquidity. We're buying the dip in an uptrend, targeting unfilled supply gaps above. Risk is small (5 pips), reward is large (30+ pips).

📉 VERDICT: BUY at 1.0856, targeting 1.0892
```

**Key characteristics:**
- **Total length:** 15 lines (not 50+)
- **Bullet separators:** Use · not full sentences
- **No verbose explanations:** "Flat market → volatility expansion" not paragraphs
- **"Advanced Indicators Summary" section:** Summarizes 11 Advanced features
- **Trade Notes added:** Short novice-friendly "why" section
- **All data analyzed:** Macro, SMC, Advanced, Binance, Order Flow checked internally

## ❌ WRONG VERBOSE FORMAT (DON'T USE!)

```
📊 Multi-Timeframe Analysis — EURUSD
🕒 Timestamp: 2025-10-14 08:15 UTC

🔹 H4 (4-Hour) – Macro Bias
Bias: 🟢 BULLISH (85%)
Reason: Price has made three consecutive higher highs, confirming a strong uptrend. The EMA20 is above EMA50 which is above EMA200, showing excellent trend structure. RSI is at 62 which indicates bullish momentum without being overbought. ADX is at 28 showing good trend strength.
EMA Stack: 20=1.0870 | 50=1.0845 | 200=1.0820
RSI: 62 (Bullish momentum)
ADX: 28 → Strong trend
📈 Overall uptrend confirmed, safe to look for long entries

🔹 H1 (1-Hour) – Trend Confirmation
[... another 10 lines of verbose explanation ...]

🔹 M30 (30-Minute) – Entry Refinement
[... another 10 lines ...]

[... continues for 50+ lines total ...]
```

**Why this is WRONG:**
- ❌ Too long (50+ lines when user wants 10-15)
- ❌ Too verbose ("Price has made three consecutive higher highs, confirming a strong uptrend...")
- ❌ Too slow to read (takes 2+ minutes)
- ❌ Repeating obvious information

## 📋 MANDATORY SECTIONS (In Order)

### 1. Header (2 lines)
```
📊 [SYMBOL] Analysis
🕒 [TIMESTAMP]
```

### 2. Market Structure (1-2 lines)
**Show:** H4/H1/M30/M15/M5 status in ONE line with · separators
**Format:** `H4: [status] · M15: [status] · M5: [status]`
**Examples:**
- `H4: Bullish (3x HH) · M15: Consolidation · M5: Impulse up`
- `H4: Bearish (2x LL) · M15: CHOCH detected · M5: Rejection`

### 3. Liquidity Zones (1 line) ⭐ UPDATED (Tier 2.1)
**Show:** Key liquidity levels with ATR distance and urgency indicators
**Format:** `PDH: [price] · PDL: [price] · Stop cluster above: [price] ([count] stops, [X] ATR away) → [SWEEP TARGET/Near/Distant]`
**Tier 2.1 Enhancement:** Include ATR distance for liquidity clusters
- **SWEEP TARGET:** <1 ATR away (high priority, likely stop hunt target)
- **Near:** 1-2 ATR away (moderate priority)
- **Distant:** >3 ATR away (low priority, far from current price)
**Examples:**
- `PDH: 4115 · Stop cluster above: 110500 (15 stops, 1.2 ATR) → SWEEP TARGET`
- `PDL: 3985 · Equal lows: 4000 (swept) · Stop cluster below: 39900 (12 stops, 2.5 ATR) → Near`

### 4. Order Blocks / FVG (1 line)
**Show:** Nearest OB or FVG
**Format:** `Bull OB: [range] · Bear FVG: [range]`
**Example:** `Bull OB: 4072-4074 · Bear FVG: 4110 (unfilled)`

### 5. Binance Setup Quality (1 line)
**Show:** Key metrics ONLY
**Format:** `Z-Score: [value] · Pivot: [status] · Tape: [pressure]`
**Example:** `Z-Score: +2.1 (bullish) · Above R1 · Buy pressure`

### 6. Advanced Indicators Summary (1-2 lines) ⭐ CRITICAL
**Show:** Ultra-condensed institutional insight from Advanced features
**Format:** Emoji + Short phrases with → arrows
**Examples:**
- `⚙️ Advanced Indicators Summary: Flat market → volatility expansion imminent · Bear FVG nearby · price below VWAP = discounted accumulation`
- `⚙️ Advanced Indicators Summary: RMAG stretched (-5.5σ) → mean reversion likely · Fake momentum (RSI 68 + ADX 18) → fade risk`
- `⚙️ Advanced Indicators Summary: Quality uptrend (EMA slope +0.18) · MTF aligned 3/3 · expansion + strong trend = ride it`

**KEY:** This section summarizes the 11 Advanced technical features (RMAG, EMA Slope, Bollinger-ADX, etc.)

**📊 Volume Context (Tier 2.2 - NEW):** 
- **If volume is expanding >1.3x or contracting <0.7x**, mention it in Advanced Indicators Summary or Trade Notes
- **Examples:**
  - `Volume expanding 1.5x → breakout confirmation` (in Advanced Indicators Summary)
  - `Volume contracting → false breakout risk` (in Trade Notes when relevant)
  - `Volume: Expanding (1.4x avg) · Delta: +BUY pressure` (when shown in Market Context)

**🕯️ Candle Patterns (Tier 1.1 - NEW):**
- **Pattern confirmation status** is automatically tracked and should be displayed when patterns are present
- **Format:** `[Timeframe]: [Pattern Name] → [Bias] → [Status] (Strength: [score])`
- **Status values:** `CONFIRMED` (pattern validated), `INVALIDATED` (pattern failed), or no status (pending)
- **Examples:**
  - `M5: Morning Star → Bullish → CONFIRMED (Strength: 0.85)` (in Candle Patterns section)
  - `M15: Bear Engulfing → Bearish → INVALIDATED` (show but note invalidation)
  - `H1: Bull Engulfing → Bullish (Strength: 0.90)` (pending, no status yet)
- **Pattern strength** (0.0-1.0) contributes 5% weight to bias confidence - higher strength patterns boost confidence
- **Display in:** New "🕯️ CANDLE PATTERNS" section (Tier 1) or within Advanced Indicators Summary (concise format)

### 6b. Market Context (Tier 2 - NEW) ⭐ OPTIONAL SECTION
**Show:** Volume delta, Liquidity map snapshot, Session context, News guardrail
**Format:** Multi-line section with subsections (in full analysis format)
**When to include:** In full analysis format (not required for concise 10-15 line format, but data is available)
**Example:**
```
📊 MARKET CONTEXT
📈 Volume & Delta: Expanding (1.5x avg) · Buy delta: +12% (order flow)
🗺️ Liquidity Map:
  Above: $110,500 (15 stops, 1.2 ATR) → SWEEP TARGET
  Below: $109,900 (12 stops, 0.8 ATR) → SWEEP TARGET
🕒 Session: NY · 45min remaining · High vol expected
📰 News: Next high-impact event in 2h 15min (CPI release)
```
**Concise format:** May be omitted or condensed into Advanced Indicators Summary
**Session warnings:** Display actionable warnings when <15min remaining: "⚠️ Session ending in 15min → close scalps"

### 7. Key Levels (1-2 lines) ⭐ MANDATORY - NEW
**Show:** Specific actionable price levels extracted from advanced_features data
**Format:** Support/Resistance/Entry/Exit levels with labels
**Example:** 
- `📌 Key Levels: Support: $109,800 (PDL) | $109,200 (Swing Low) · Resistance: $110,850 (PDH) | $111,250 (Swing High) · Entry Zone: $110,200-$110,350 (FVG) · Stop Loss: $109,950 · Take Profit: $110,750 (TP1) | $111,200 (TP2)`

**⚠️ CRITICAL DATA EXTRACTION:**
- Extract PDH/PDL prices from: `advanced_features → features → M15/H1 → liquidity → pdh/pdl`
- Extract FVG zones from: `advanced_features → features → M15 → fvg` (show if `dist_to_fill_atr < 1.5`)
- Extract swing highs/lows from liquidity object
- Calculate R:R ratios from entry, SL, and TP levels
- **NEVER say "structure unclear" without showing actual price levels from the data!**

### 8. Auto-Trade-Ready Plan (1-2 lines) ⭐ CRITICAL
**Show:** Exact entry/SL/TP in ONE line
**Format:** `[Order type] @ [entry] · SL: [price] · TP1: [price] · TP2: [price] · R:R [ratio]`

**🚨 IMPORTANT:** ALWAYS provide a pending order trade plan, even when verdict is "WAIT"
- **If verdict is BUY/SELL NOW:** Use "Market NOW" order
- **If verdict is WAIT:** Use PENDING order (Buy Limit/Sell Limit/Buy Stop/Sell Stop)
- **Key principle:** User should place pending order NOW - system waits for price, not user

**Examples:**
- `BUY Market NOW @ 4145 · SL: 4140 · TP1: 4165 · TP2: 4175 · R:R 1:6` (Execute immediately)
- `BUY Limit @ 4125 (pullback to OB) · SL: 4120 · TP1: 4155 · TP2: 4175 · R:R 1:6` (WAIT verdict)
- `SELL Limit @ 4155 (rally to Bear OB) · SL: 4160 · TP: 4120 · R:R 1:7` (WAIT verdict)
- `BUY Stop @ 4156 (breakout above resistance) · SL: 4150 · TP: 4180 · R:R 1:4` (WAIT for breakout)

### 8b. Pending Trade Detailed Format (NEW!) ⭐ CRITICAL
**🚨 NEVER USE "WAIT" - ALWAYS USE DETAILED FORMAT:**
**❌ WRONG:** "📉 VERDICT: ⏰ WAIT — Place pending BUY Limit @ 111,300"
**✅ CORRECT:** Use detailed format below with strategy name

```
[Strategy Name] (Recommended)

🟡 BUY Limit @ 1.0970 (retest of breakout/OB)
🛡️ SL: 1.0940 (below Asian low - 5 pips) - Risk: $12.00
🎯 TP1: 1.1010 (1.5R) - $16.00
🎯 TP2: 1.1040 (2.5R) - $28.00
📊 R:R ≈ 1 : 2.3
📦 Lot Size: 0.04 lots
```

**Format Requirements:**
- **Title:** Dynamic strategy name + "(Recommended)" (e.g., "Scalp Entry", "Buy the Dip", "Breakout Momentum", "Mean Reversion", "Conservative Pullback", etc.)
- **Entry:** Order type + price + reason
- **SL:** Price + reason + dollar risk amount
- **TP1/TP2:** Price + R multiple + dollar profit amount
- **R:R:** Risk to reward ratio with 📊 emoji
- **Lot Size:** Position size with 📦 emoji

### 9. Trade Notes (5-6 lines) ⭐ NEW REQUIREMENT
**Purpose:** Explain reasoning for NOVICE traders
**Format:** "Why this trade? [Simple explanation in 1-2 sentences]"
**Examples:**
- `Why this trade? Price pulled back to institutional buy zone (Order Block) after sweeping liquidity. We're buying the dip in an uptrend, targeting unfilled supply gaps above. Risk is small (5 pips), reward is large (30+ pips).`
- `Why this trade? Bitcoin extremely oversold (-5.5σ below average). Statistically 99.99% probability of bounce. We're buying fear at discount prices, targeting mean reversion to 113k.`
- `Why this trade? Gold has both DXY and US10Y falling (double tailwind). Price at proven Order Block with clean structure. Low-risk entry for swing to liquidity pool above.`

**🎓 OPTIONAL: Detailed SMC Reasoning**
If user asks "why that entry?", "explain reasoning", "why those levels?", or similar questions, provide detailed SMC breakdown:

**Format:**
```
🧭 Entry @ [Price] — [Why This Level]

Market Context: [1-2 sentence setup]
This level represents [SMC concept]
✅ So, [Price] = [institutional logic]

🛡️ Stop Loss @ [Price] — [Protection Logic]

[Why this specific SL placement]
[Risk management reasoning]
✅ So, [Price] = [invalidation logic]

💰 Take Profit @ [Price] — [Target Logic]

[Why this specific TP]
[Liquidity/structure reasoning]
✅ So, [Price] = [liquidity sweep target]

⚙️ Supporting Confluences
[List key advanced features that support the setup]
```

**Example:**
```
🧭 Entry @ 113,200 — Breakout Confirmation Zone

Market Context: BTCUSD was consolidating in 111.8k–113.2k range (tight volatility squeeze).
113,200 = Buy-side liquidity cluster + range high → institutions place stop orders above this.
A break above signals BOS (Break of Structure) — confirming trend continuation.
✅ So, 113,200 = breakout trigger, ensuring entry only after momentum proves strength.

🛡️ Stop Loss @ 112,600 — Structural Protection

Stop set 600 pts below entry, just below last Higher Low (HL) and mid-range re-entry zone.
Protects against false breakout retrace. Below range mid (≈112,700) where liquidity refills.
600 pts = ~0.5% risk buffer, aligned with volatility (ATR ≈ 550 pts).
✅ So, 112,600 = invalidation zone — if price falls here, breakout has failed.

💰 Take Profit @ 114,800 — Liquidity Pool Target

Above equal highs at 114,700–114,800, visible on M15/H1 charts.
Next buy-side liquidity pool where stop orders from shorts cluster.
Perfect alignment with 1:2.6 risk/reward.
✅ So, 114,800 = first liquidity sweep target where institutions take profits.

⚙️ Supporting Confluences
RMAG: +1.6σ (moderate stretch, ready for breakout)
VWAP Zone: outer boundary → price ready for expansion
Volume: rising near 113k → accumulation breakout pattern confirmed
```

**IMPORTANT:** Only provide this detailed breakdown when user explicitly asks for it. Default analysis should be concise 10-15 lines.

### 10. Verdict (1 line)
**Format:** `📉 VERDICT: [ACTION] at [price], targeting [price]`

**Verdict Types:**
- **BUY NOW / SELL NOW:** Execute market order immediately
  - Example: `📉 VERDICT: BUY NOW at 4145, targeting 4175`
- **Pending Trade Recommended:** Use detailed pending trade format (see section 7b)
  - Example: `📉 VERDICT: Pending Trade Recommended — Conservative Pullback Entry (see detailed plan above)`
- **AVOID:** No trade plan provided, explain why setup is invalid
  - Example: `📉 VERDICT: ❌ AVOID — CHOCH detected, uptrend broken. Wait for new structure.`

**🚨 CRITICAL:** Even with WAIT verdict, ALWAYS provide pending order plan in section 7

## 🎯 INTERNAL ANALYSIS CHECKLIST

**You MUST analyze all these layers BEFORE writing response:**
1. ✅ Macro context (DXY, US10Y, VIX for Gold/USD pairs)
2. ✅ Multi-timeframe structure (H4/H1/M30/M15/M5)
3. ✅ Advanced features (RMAG, EMA slope, Bollinger-ADX, etc.)
4. ✅ Technical indicators (EMA, RSI, MACD, Stoch, BB, ATR)
5. ✅ Binance enrichment (Z-Score, Pivots, Liquidity, Tape, Patterns)
6. ✅ Order flow (Whales, Imbalance, Pressure)
7. ✅ Market Context ⭐ NEW (Tier 2) - Volume trends, Liquidity clusters with ATR, Session timing with warnings, News guardrail
8. ✅ Pattern Tracking ⭐ NEW (Tier 1) - Pattern confirmation status (CONFIRMED/INVALIDATED), pattern strength weighting
9. ✅ SMC (CHOCH, BOS, Order Blocks, Liquidity)

**But ONLY show:**
- Market Structure summary (1 line)
- Liquidity Zones with ATR distance (1 line) ⭐ Tier 2.1
- Order Blocks/FVG (1 line)
- Candle Patterns with confirmation status (1 line) ⭐ Tier 1.1 (if patterns present)
- Binance Quality (1 line)
- Advanced Indicators Summary (1-2 lines)
- Market Context (1-2 lines) ⭐ Tier 2 (Volume delta, Session warnings, Liquidity map, News guardrail)
- Key Levels (1-2 lines) ⭐ NEW
- Trade Plan (1-2 lines)
- Trade Notes (2-3 lines)
- Verdict (1 line)

**Total: 11-17 lines maximum**

## 🚨 CRITICAL WARNING EXCEPTIONS

**If CRITICAL condition detected, ADD warning section:**

### RMAG Stretched (>2σ or <-2σ)
```
⚠️ CRITICAL: Price -5.5σ below EMA200 (extreme oversold)
Statistically 99.99% probability of mean reversion. DO NOT CHASE SHORTS.
```

### CHOCH Detected
```
🚨 CHOCH DETECTED: Structure broken at 4083 (LL made)
Exit longs immediately or tighten SL. Uptrend invalidated.
```

### News Blackout
```
🚫 NEWS BLACKOUT: NFP in 15 minutes
DO NOT TRADE. Wait for event to pass.
```

**These warnings are ADDITIONS, not replacements. Keep the concise format, just add 1-2 line warning at top.**

## 📊 SPECIAL CASES

### Multiple Symbols Comparison
**Format:** Table with ONE row per symbol
```
| Symbol | Structure | Advanced | Verdict | R:R |
|--------|-----------|----------|---------|-----|
| EURUSD | Bullish (3x HH) | Quality trend · MTF 3/3 | BUY @ 1.0856 | 1:6 |
| GBPUSD | Bearish (2x LL) | CHOCH detected | WAIT | - |
| XAUUSD | Consolidation | Squeeze → breakout pending | WAIT | - |
```

### Pending Order Analysis
**Format:** ONE line per order
```
🔍 Order #117491393 (SELL STOP USDJPY @ 87.250)
Status: ✅ VALID · Entry at resistance · SL 2.1 ATR · R:R 1:2.5
Action: Keep as-is
```

### Position Review
**Format:** 2-3 lines per position
```
🎫 Ticket 120828675 (BUY XAUUSD @ 3950)
Current: 3955 (+$5) · CHOCH detected at 3952 ⚠️
Action: Exit NOW or tighten SL to 3953 · Uptrend broken
```

## 📊 Range Scalping Analysis Format (NEW!)

### When to Use
- User asks: "Can I scalp [symbol] right now?"
- User asks: "Is this a ranging market?"
- User asks: "What range scalping opportunities are available?"
- Tool: `moneybot.analyse_range_scalp_opportunity` is called

### Required Format (10-15 lines max)

```
📊 [SYMBOL] Range Scalp Analysis

🕒 Session: [Asian/London/NY]

🏛️ Range Structure:
Type: [Session/Daily/Dynamic] Range · Expansion: [Stable/Expanding/Contracting]
High: [price] · Low: [price] · Midpoint: [price]
Width: ~[X]× ATR ([volatility description])

⚙️ Risk / Confluence:
Confluence Score: [X]/100 [✅/❌] (Need ≥80 for valid trade)
Range Valid: [✅/❌] · Session Allows: [✅/❌]

📋 Top Strategy:
[Strategy Name] - [BUY/SELL]
Entry: [price] · SL: [price] · TP: [price]
R:R: 1:[X] · Confidence: [X]%

⚠️ Exit Triggers:
• [Trigger 1] = [action]
• [Trigger 2] = [action]

📉 VERDICT: [BUY/SELL/WAIT] [reason/entry price, target]
```

### Example: Valid Range Scalp

```
📊 BTCUSD Range Scalp Analysis

🕒 Session: Asian

🏛️ Range Structure:
Type: Dynamic Range · Expansion: Stable
High: 110,743.17 · Low: 109,713.16 · Midpoint: 110,272.10
Width: ~1.51× ATR (moderate volatility)

⚙️ Risk / Confluence:
Confluence Score: 85/100 ✅ (Passed threshold)
Range Valid: ✅ · Session Allows: ✅

📋 Top Strategy:
VWAP Mean Reversion - BUY
Entry: 109,850 · SL: 109,700 · TP: 110,150
R:R: 1:2.0 · Confidence: 85%

⚠️ Exit Triggers:
• 2+ candles break range = exit immediately
• +0.5R profit = move SL to breakeven

📉 VERDICT: BUY range scalp at 109,850, targeting 110,150
```

### Example: No Valid Setup

```
📊 BTCUSD Range Scalp Analysis

🕒 Session: London-NY Overlap

🏛️ Range Structure:
Type: Dynamic Range · Expansion: Stable
High: 110,743.17 · Low: 109,713.16 · Midpoint: 110,272.10
Width: ~1.51× ATR (moderate volatility)

⚙️ Risk / Confluence:
Confluence Score: 35/100 ❌ (Need ≥80 for valid trade)
Range Valid: ✅ · Session Allows: ❌ (Overlap period - blocked)

⚠️ Warnings:
❌ 3-confluence score too low: 35/100 (required: 80+)
❌ Session filter blocked: London-NY overlap (12:00-15:00 UTC)

📉 VERDICT: WAIT — Low confluence (35/100) + Overlap period blocked
```

### Formatting Rules

**Range Structure:**
- Show type, expansion state, high/low/midpoint in ONE line
- Width in ATR multiples (e.g., "~1.5× ATR")
- Volatility description: "low", "moderate", "high"

**Risk/Confluence:**
- Show score with ✅/❌ indicator
- Show which checks passed/failed
- Use · separators for multiple statuses

**Top Strategy:**
- Only show if confluence ≥80 AND range valid AND session allows
- Format: `[Strategy Name] - [Direction]`
- Entry/SL/TP on ONE line
- R:R and confidence on same line

**Exit Triggers:**
- List 2-3 most important triggers
- Use bullet points (•)
- Brief action description

**Warnings:**
- Only show if conditions NOT met
- Use ❌ prefix
- Be specific (e.g., "35/100" not just "too low")

**Verdict:**
- BUY/SELL if valid setup found
- WAIT if conditions not met
- Include brief reason

### Integration Notes
- Range scalping uses fixed 0.01 lots (never risk-based)
- Separate exit manager (`RangeScalpingExitManager`) handles exits
- Standard `IntelligentExitManager` skips range scalps
- Monitoring runs every 5 minutes for active trades

---

## 💡 CONCISENESS TECHNIQUES

### Use · Separators, Not Sentences
❌ WRONG: "The H4 timeframe shows a bullish bias at 85% confidence. The M15 timeframe is currently in consolidation."
✅ CORRECT: `H4: Bullish (85%) · M15: Consolidation`

### Use → Arrows, Not "Which Means"
❌ WRONG: "DXY is falling which means this is bullish for Gold"
✅ CORRECT: `DXY↓ → Bullish for Gold`

### Use Abbreviations
❌ WRONG: "Previous Day High"
✅ CORRECT: "PDH"

❌ WRONG: "Order Block"
✅ CORRECT: "OB"

❌ WRONG: "Fair Value Gap"
✅ CORRECT: "FVG"

### Combine Related Info
❌ WRONG (3 lines):
```
EMA20: 1.0870
EMA50: 1.0845
EMA200: 1.0820
```
✅ CORRECT (1 line):
```
EMA: 20/50/200 aligned bullish
```

### Skip Obvious Information
❌ WRONG: "RSI is at 62 which indicates bullish momentum without being overbought"
✅ CORRECT: `RSI: 62 (bullish)`

### Use Emojis for Status
❌ WRONG: "The trend is bullish"
✅ CORRECT: "🟢 Bullish"

### Bias Confidence Display (Tier 2.4 - NEW)
**For CONCISE format (10-15 lines):**
- **Use emoji-only:** `🟢 BIAS: Buy` or `🔴 BIAS: Sell` or `🟡 BIAS: Wait`
- **Score optional:** Only include numeric score (e.g., `78/100`) if space allows
- **Examples:**
  - `🟢 BIAS: Buy` (preferred for concise)
  - `🟢 BIAS: Buy (78/100)` (if space permits)

**For FULL analysis format:**
- **Keep both:** `🟢 BIAS CONFIDENCE: 78/100`
- **Emoji thresholds:**
  - 🟢 = 75-100 (Strong buy/confidence)
  - 🟡 = 60-74 (Wait/Neutral/Moderate)
  - 🔴 = 0-59 (Sell/Avoid/Low confidence)

## 📝 EXAMPLE TRANSFORMATIONS

### Example 1: Gold Analysis
**OLD VERBOSE FORMAT (50+ lines):**
```
📊 Multi-Timeframe Analysis — XAUUSD
🕒 Timestamp: 2025-10-14 08:15 UTC

🔹 H4 (4-Hour) – Macro Bias
Bias: 🟢 BULLISH (85%)
Reason: The four-hour timeframe shows a strong bullish structure with three consecutive higher highs. The EMA20 is positioned above the EMA50, which is above the EMA200, indicating excellent trend alignment...
[continues for 50+ lines]
```

**NEW CONCISE FORMAT (12 lines):**
```
📊 XAUUSD Analysis
🕒 2025-10-14 08:15 UTC

🏛️ Market Structure:
H4: Bullish (3x HH) · M15: Pullback to OB · M5: Bullish reversal candle

🎯 Liquidity Zones:
PDH: 4115 (target) · Equal lows: 4065 (swept)

🟢 Order Block / FVG:
Bull OB: 4072-4074 (entry zone) · Bear FVG: 4110 (resistance)

📊 Binance Setup Quality:
Z-Score: +1.8 (bullish) · Above pivot · Strong buy tape

⚙️ Advanced Indicators Summary:
DXY↓ + US10Y↓ = double tailwind · Quality uptrend (EMA +0.16) · MTF aligned 3/3

🎯 Auto-Trade-Ready Plan:
BUY Limit @ 4073 (OB) · SL: 4068 · TP1: 4095 · TP2: 4115 (PDH) · R:R 1:8

📝 Trade Notes:
Why this trade? Both DXY and US10Y falling (macro tailwind for Gold). Price pulled back to institutional buy zone after liquidity sweep. We're buying the dip with structure intact, targeting previous high. Professional 5-pip risk for 40+ pip reward.

📉 VERDICT: BUY at 4073, targeting 4115
```

**NOVICE-FRIENDLY FORMAT (Standard Behavior - 12-15 lines):**
```
📊 Gold (XAUUSD) Analysis
🕒 2025-10-14 08:15 UTC | Current Price: $4,073

📈 Market Trend:
Uptrend (price making higher highs) · Price pulled back to buy zone

📍 Key Price Levels:
Support (floor): $4,065 (price bounced here before)
Resistance (ceiling): $4,115 (target price)
Entry Zone: $4,072-$4,074 (institutional buy area)

💹 Market Conditions:
Strong momentum · Dollar weakening (good for Gold) · Buy pressure building

🎯 Trade Plan:
Entry: $4,073 (buy when price reaches this zone)
Stop Loss: $4,068 (protects you if price falls - limits loss to $5)
Take Profit 1: $4,095 (first profit target - risk $5 to make $22)
Take Profit 2: $4,115 (second profit target - risk $5 to make $42)
Risk:Reward: 1:8 (risk $5 to potentially make $40)

📝 Why This Trade?
Gold is in an uptrend and pulled back to a proven buy zone where big institutions (banks, hedge funds) typically buy. The US Dollar is weakening, which usually makes Gold go up. We're buying the dip at a good price, with a tight stop loss to protect us, targeting the previous high. This is a high-probability setup where we risk $5 to potentially make $40.

✅ RECOMMENDATION: BUY at $4,073, targeting $4,115
```

### Example 2: Bitcoin with RMAG Warning
**NEW CONCISE FORMAT WITH CRITICAL WARNING (14 lines):**
```
⚠️ CRITICAL: Price -5.5σ below EMA200 (extreme oversold)
99.99% statistical probability of mean reversion. DO NOT CHASE SHORTS.

📊 BTCUSD Analysis
🕒 2025-10-14 10:45 UTC

🏛️ Market Structure:
H4: Downtrend (2x LL) · M15: Capitulation wicks · M5: First green candle

🎯 Liquidity Zones:
Equal lows: 109.5k (swept) · PDH: 115k (target)

🟢 Order Block / FVG:
Bull OB: 110.8-111.2k · Current price: 110.5k (in OB)

📊 Binance Setup Quality:
Z-Score: -3.2 (extreme fear) · Below all pivots · Selling exhaustion

⚙️ Advanced Indicators Summary:
RMAG -5.5σ (0.00006% occurrence) · VIX 21 (fear) + S&P -0.8% · BTC.D 49% (weak)

🎯 Auto-Trade-Ready Plan:
BUY Market @ 110.5k · SL: 109.5k · TP1: 113k · TP2: 115k · R:R 1:4.5

📝 Trade Notes:
Why this trade? Bitcoin extremely oversold (only happens 0.00006% of time). Price at proven Order Block after liquidity sweep. We're buying panic at statistical extreme, targeting mathematical mean reversion. Contrarian high-probability setup.

📉 VERDICT: BUY NOW at 110.5k, targeting 113-115k (mean reversion play)
```

**NOVICE-FRIENDLY FORMAT WITH WARNING (Standard Behavior - 14-16 lines):**
```
⚠️ CRITICAL WARNING: Bitcoin Extremely Oversold
Bitcoin is at an extremely rare oversold level (only happens 0.00006% of the time). This means price is likely to bounce back up. DO NOT sell/short Bitcoin right now.

📊 Bitcoin (BTCUSD) Analysis
🕒 2025-10-14 10:45 UTC | Current Price: $110,500

📈 Market Trend:
Downtrend (price falling) · BUT price at extreme oversold level (very rare)

📍 Key Price Levels:
Support (floor): $109,500 (price bounced here before - strong support)
Resistance (ceiling): $115,000 (target price if bounce happens)
Entry Zone: $110,500-$111,200 (institutional buy area - we're in it now)

💹 Market Conditions:
Extreme oversold (very rare) · Market fear high · Selling exhausted · Buy pressure building

🎯 Trade Plan:
Entry: $110,500 (buy now - we're at the buy zone)
Stop Loss: $109,500 (protects you if price falls further - limits loss to $1,000)
Take Profit 1: $113,000 (first profit target - risk $1,000 to make $2,500)
Take Profit 2: $115,000 (second profit target - risk $1,000 to make $4,500)
Risk:Reward: 1:4.5 (risk $1,000 to potentially make $4,500)

📝 Why This Trade?
Bitcoin is at an extremely rare oversold level (this only happens 0.00006% of the time). When prices get this oversold, they almost always bounce back up. We're buying at a proven buy zone where big institutions typically buy. This is a contrarian trade - we're buying when everyone else is panicking and selling. The risk is controlled with a stop loss, and the potential reward is 4.5x what we risk.

✅ RECOMMENDATION: BUY NOW at $110,500, targeting $113,000-$115,000 (mean reversion play)
```

### Example 3: WAIT Verdict with Pending Order
**NEW CONCISE FORMAT WITH PENDING ORDER (12 lines):**
```
📊 XAUUSD Analysis
🕒 2025-10-14 14:30 UTC

🏛️ Market Structure:
H4: Bullish (3x HH) · M15: Rally extended · M5: Overbought wicks

🎯 Liquidity Zones:
PDH: 4175 (near resistance) · Bull OB: 4120-4130 (discount zone below)

🟢 Order Block / FVG:
Bull OB: 4120-4130 (institutional buy zone) · Current price: 4155 (premium)

📊 Binance Setup Quality:
Z-Score: +2.8 (overbought) · Above all pivots · Tape cooling off

⚙️ Advanced Indicators Summary:
RMAG 3.1 → overbought zone · VWAP outer → premium area · Momentum ↑ (3.8 ratio) · ADX low = weak trend continuation

🎯 Auto-Trade-Ready Plan:
BUY Limit @ 4125 (pullback to OB) · SL: 4118 · TP1: 4155 · TP2: 4175 · R:R 1:5

📝 Trade Notes:
Why this trade? Gold macro bias bullish (DXY↓ + US10Y↓), but price overextended after rally. Smart Money prefers re-entry at discount OB levels for best R:R. Place pending order NOW - system executes when price pulls back to institutional buy zone.

Scalp Entry (Recommended)

🟡 BUY Limit @ 4125 (pullback to OB)
🛡️ SL: 4118 (below Asian low - 7 pips) - Risk: $14.00
🎯 TP1: 4155 (1.5R) - $21.00
🎯 TP2: 4175 (2.5R) - $35.00
📊 R:R ≈ 1 : 2.5
📦 Lot Size: 0.02 lots

📉 VERDICT: Pending Trade Recommended — Conservative Pullback Entry (see detailed plan above)
```

**Key differences from "BUY NOW" verdict:**
- ✅ Uses "BUY Limit" (pending order) instead of "Market NOW"
- ✅ Entry price is BELOW current price (waiting for pullback)
- ✅ Verdict explains WHY waiting and WHERE to enter
- ✅ Trade Notes emphasize "place pending order NOW - system executes when..."
- ✅ User doesn't need to watch charts - system handles execution

## 🎯 IMPLEMENTATION INSTRUCTIONS FOR CHATGPT

**🚨 CRITICAL: NOVICE-FRIENDLY OUTPUT (STANDARD BEHAVIOR)**

**The user wants:**
1. ✅ **Full analysis still performed** - Analyze ALL data layers (macro, SMC, advanced, binance, order flow)
2. ✅ **Novice-friendly output** - Format reports so beginners can understand them
3. ✅ **Explain technical terms** - Don't assume users know trading jargon
4. ✅ **Simple language** - Use plain English, explain what things mean

### **NOVICE-FRIENDLY FORMATTING RULES:**

1. **When user requests analysis:**
   - Call `moneybot.analyse_symbol_full(symbol)` to get ALL data layers
   - OR call individual APIs (macro, MTF, advanced, binance, order flow)
   - Analyze EVERYTHING internally (behind the scenes)
   - **Output format: Simple, clear, explained**

2. **Process all data layers (internal analysis only - not shown to user):**
   - Check macro (DXY/US10Y/VIX for Gold, DXY for USD pairs)
   - Check multi-timeframe structure (H4/H1/M30/M15/M5)
   - Check advanced features (RMAG, EMA slope, volatility state, etc.)
   - Check technical indicators (EMA, RSI, MACD, ADX, etc.)
   - Check Binance enrichment (Z-Score, Pivots, Tape, Liquidity)
   - Check order flow (Whales, Imbalance, Pressure)
   - Check SMC (CHOCH, BOS, Order Blocks, Liquidity)

3. **Determine critical conditions (internal analysis):**
   - RMAG >2σ or <-2σ? → Add critical warning (explain what this means)
   - CHOCH detected? → Add CHOCH warning (explain what this means)
   - News blackout? → Add news warning
   - Fake momentum? → Mention in Market Conditions Summary

4. **Write NOVICE-FRIENDLY response (10-15 lines):**
   - **Market Trend** (1 line) - Use simple terms: "Uptrend", "Downtrend", "Sideways"
   - **Key Price Levels** (1-2 lines) - Explain what they are: "Support (floor price)", "Resistance (ceiling price)"
   - **Entry Setup** (1 line) - Explain: "Buy zone", "Sell zone", "Wait for pullback"
   - **Market Conditions** (1-2 lines) - Simple summary: "Strong momentum", "Overbought", "Oversold"
   - **Trade Plan** (2-3 lines) - Clear entry, stop loss, take profit with explanations
   - **Why This Trade?** (2-3 lines) - Plain English explanation for beginners
   - **Recommendation** (1 line) - Simple: "BUY", "SELL", or "WAIT"

5. **NOVICE-FRIENDLY LANGUAGE RULES:**
   - ✅ **DO use:** "Uptrend" instead of "Bullish structure with 3x HH"
   - ✅ **DO use:** "Price floor" instead of "PDL (Previous Day Low)"
   - ✅ **DO use:** "Price ceiling" instead of "PDH (Previous Day High)"
   - ✅ **DO use:** "Buy zone" instead of "Bull Order Block"
   - ✅ **DO use:** "Sell zone" instead of "Bear Order Block"
   - ✅ **DO use:** "Price gap" instead of "FVG (Fair Value Gap)"
   - ✅ **DO use:** "Strong momentum" instead of "EMA slope +0.16"
   - ✅ **DO use:** "Very oversold" instead of "RMAG -5.5σ"
   - ✅ **DO use:** "Institutional buy area" instead of "Order Block"
   - ✅ **DO explain:** What "Stop Loss" means (protects you from big losses)
   - ✅ **DO explain:** What "Take Profit" means (where you exit for profit)
   - ✅ **DO explain:** What "Risk:Reward" means (how much you risk vs how much you can make)

6. **DO NOT use (unless you explain what they mean):**
   - ❌ Technical jargon without explanation (PDH, PDL, FVG, OB, CHOCH, BOS)
   - ❌ Greek letters (σ, σ) without explanation
   - ❌ Abbreviations without explanation (EMA, RSI, MACD, ADX, ATR)
   - ❌ Complex terminology (RMAG, Z-Score, CVD, Delta)
   - ❌ Timeframe codes without explanation (H4, M15, M5)

7. **Always include:**
   - ✅ **Simple trend description** - "Uptrend", "Downtrend", "Sideways"
   - ✅ **Key price levels with explanations** - "Support at $4200 (price floor)", "Resistance at $4250 (price ceiling)"
   - ✅ **Entry explanation** - "Buy when price pulls back to $4200 (institutional buy zone)"
   - ✅ **Stop Loss explanation** - "Stop Loss at $4190 (protects you if price falls)"
   - ✅ **Take Profit explanation** - "Take Profit at $4250 (where you exit for profit)"
   - ✅ **Risk:Reward explanation** - "Risk:Reward 1:5 (risk $10 to make $50)"
   - ✅ **Why This Trade? section** - Plain English explanation (2-3 sentences)
   - ✅ **Simple recommendation** - "BUY", "SELL", or "WAIT" with clear reasoning

## 📚 REFERENCE - USER'S EXACT REQUIREMENTS

From user message:
> "the chatgpt analysis I am receiving now is too long and takes to long to be shown with everything being shown in it. i still want all data to be assessed and analysed and combined into a trade though."

> "this more the style I want to see with the addition of an explanation of reasoning for trade so that a novice trader can understand it. Once again i want chatgpt to analyse all available data before making a recommendation even though it is not showing it in its reply"

**Translation:**
1. Analyze ALL data (macro, SMC, advanced, binance, order flow) ✅
2. Show ONLY concise summary (10-15 lines, not 50+) ✅
3. Add novice-friendly reasoning section ✅
4. Use "Advanced Indicators Summary" section name ✅
5. Use institutional brevity (bullets, arrows, abbreviations) ✅

**NEW REQUIREMENT (December 2025):**
> "for chatgpt analysis i want it to still do full symbol analysis but i want output report to be suitable for a novice as standard behaviour from now on"

**Translation:**
1. ✅ **Still analyze ALL data** - Full comprehensive analysis behind the scenes
2. ✅ **Novice-friendly output** - Use simple language, explain technical terms
3. ✅ **Standard behavior** - This is now the default format for all analyses
4. ✅ **Explain what things mean** - Don't assume users know trading jargon
5. ✅ **Plain English** - Use "uptrend" not "bullish structure with 3x HH"

---

**Status:** ✅ Concise formatting instructions complete + Novice-friendly format added
**Last Updated:** 2025-12-05
**Purpose:** Reduce ChatGPT response length from 50+ lines to 10-15 lines while maintaining comprehensive analysis quality
