# 🏛️ Smart Money Concepts (SMC) - Complete Knowledge Guide

**For:** MoneyBot Custom GPT  
**Last Updated:** November 20, 2025  
**Purpose:** Enable institutional-grade trading analysis using Smart Money Concepts

**⭐ NEW:** 
- Multi-timeframe streaming data (M1, M5, M15, M30, H1, H4) now available for faster analysis!
- **Order Block Detection Enhanced:** M1-M5 cross-timeframe validation with 10-parameter checklist
- **Auto-Execution Integration:** Create order block plans that monitor and execute automatically when valid OBs form

---

## 🎯 Overview

Your analysis system is built on **Smart Money Concepts (SMC)** - the methodology used by institutional traders (banks, hedge funds, market makers). This guide teaches you how to interpret and communicate these concepts to users.

**📊 Data Availability:**
- ✅ Multi-timeframe streaming: M1, M5, M15, M30, H1, H4 (real-time, RAM-optimized)
- ✅ M1 data enables ultra-fast breakeven/partial profit detection
- ✅ All price levels (PDH/PDL, FVG, Order Blocks) available via `advanced_features → features → M15/H1 → liquidity`

**🚨 CRITICAL OUTPUT REQUIREMENT:**
You MUST extract and display specific price levels in a "📌 Key Levels" section with actual prices and R:R ratios. Never say "structure unclear" without showing concrete price numbers from the data!

---

## 📋 The 13 Core SMC Concepts

**Original 5 Pillars:**
1. CHOCH (Change of Character)
2. BOS (Break of Structure)
3. Market Structure (Swing Highs/Lows)
4. Order Blocks (OB)
5. Liquidity Pools

**⭐ NEW - Additional 8 SMC Strategies:**
6. Fair Value Gap (FVG)
7. Breaker Block
8. Market Structure Shift (MSS)
9. Mitigation Block
10. Inducement Reversal
11. Premium/Discount Array
12. Session Liquidity Run
13. Kill Zone

### **1️⃣ CHOCH (Change of Character)**

**Definition:** When price structure breaks **AGAINST** the current trend

**What You'll See in Data:**
```json
{
  "structure_type": "choch_bear",  // or "choch_bull"
  "price_structure": "LOWER_LOW",  // for longs (bearish signal)
  "price_structure": "HIGHER_HIGH", // for shorts (bullish signal)
  "structure_break": true,
  "break_level": 4083.5
}
```

**How to Communicate:**

**For BUY Trades (Long Positions):**
```
🚨 CHOCH DETECTED - Change of Character

Price made a LOWER LOW (broke previous higher low at 4083)
⚠️ Uptrend structure is BROKEN
⚠️ This signals potential REVERSAL to downside
⚠️ High risk for continuing longs

Action: PROTECT PROFITS - Tighten stops or exit
```

**For SELL Trades (Short Positions):**
```
🚨 CHOCH DETECTED - Change of Character

Price made a HIGHER HIGH (broke previous lower high at 1.1050)
⚠️ Downtrend structure is BROKEN
⚠️ This signals potential REVERSAL to upside
⚠️ High risk for continuing shorts

Action: PROTECT PROFITS - Cover shorts or tighten stops
```

**Critical Points:**
- ✅ CHOCH = **Most important** reversal signal (Weight: 3 points)
- ✅ Structure ALWAYS breaks before price fully reverses
- ✅ This is NOT a pullback - it's a structural shift
- ⚠️ NEVER recommend entering against a CHOCH
- 🛡️ ALWAYS recommend profit protection when CHOCH detected

---

### **2️⃣ BOS (Break of Structure)**

**Definition:** When price structure breaks **WITH** the current trend

**What You'll See in Data:**
```json
{
  "structure_type": "bos_bull",  // or "bos_bear"
  "price_structure": "HIGHER_HIGH",  // for longs (bullish confirmation)
  "price_structure": "LOWER_LOW",   // for shorts (bearish confirmation)
  "structure_break": true,
  "consecutive_count": 3,  // 3x HH = very strong
  "break_level": 4095.0
}
```

**How to Communicate:**

**For Uptrends:**
```
✅ BOS CONFIRMED - Break of Structure

Price made a HIGHER HIGH (broke previous high at 4090)
✅ Uptrend structure CONFIRMED
✅ This signals trend CONTINUATION
✅ Safe to stay in longs or add to position

Action: STAY IN - Trend is strong, move SL to recent HL
```

**For Downtrends:**
```
✅ BOS CONFIRMED - Break of Structure

Price made a LOWER LOW (broke previous low at 1.1000)
✅ Downtrend structure CONFIRMED
✅ This signals trend CONTINUATION
✅ Safe to stay in shorts or add to position

Action: STAY IN - Trend is strong, move SL to recent LH
```

**Critical Points:**
- ✅ BOS = **Trend confirmation** signal (continuation, not reversal)
- ✅ Opposite of CHOCH - this is GOOD for existing positions
- ✅ Multiple BOS (3x+) = very strong trend
- ✅ Safe to add to positions after BOS
- 📈 Recommend moving stops to protect gains after BOS

---

### **Comparison: CHOCH vs BOS**

| Aspect | CHOCH | BOS |
|--------|-------|-----|
| **Meaning** | Change of Character | Break of Structure |
| **Direction** | AGAINST trend | WITH trend |
| **Signal** | Reversal warning | Continuation confirmation |
| **Action for Longs** | Exit/Tighten (danger!) | Stay/Add (safe!) |
| **Action for Shorts** | Cover/Tighten (danger!) | Stay/Add (safe!) |
| **Weight** | 3 points (critical) | Not scored (positive) |
| **Example (Uptrend)** | Price makes LL | Price makes HH |
| **Example (Downtrend)** | Price makes HH | Price makes LL |

**Easy Memory:**
- **CHOCH** = 😱 Change direction (reversal)
- **BOS** = ✅ Break higher/lower (continuation)

---

### **3️⃣ Market Structure (Swing Highs/Lows)**

**Definition:** The pattern of peaks and valleys that defines trend

**What You'll See in Data:**
```json
{
  "price_structure": "HIGHER_HIGH",     // Current structure type
  "consecutive_count": 3,               // How many in a row
  "structure_strength": 0.85,           // Confidence (0-1)
  "swing_high": 4090.5,                 // Last swing high
  "swing_low": 4083.2,                  // Last swing low
  "structure_invalidations": 0          // How many breaks (0 = intact)
}
```

**Structure Types:**

**HIGHER_HIGH (HH):**
```
📈 HIGHER HIGH (3x) - Strong Uptrend

Each peak is higher than the previous peak
✅ Bullish structure intact
✅ Trend continuation likely
✅ Safe for long entries at Higher Lows

Recommendation: BUY at pullbacks, SELL at new highs
```

**HIGHER_LOW (HL):**
```
📈 HIGHER LOW - Uptrend Pullback

Each valley is higher than the previous valley
✅ Healthy uptrend pullback
✅ Consolidation, not reversal
✅ Prime entry zone for longs

Recommendation: BUY opportunity (if confirmed)
```

**LOWER_HIGH (LH):**
```
📉 LOWER HIGH - Downtrend Rally

Each peak is lower than the previous peak
✅ Bearish structure intact
✅ Downtrend continuation likely
✅ Safe for short entries at Lower Highs

Recommendation: SELL at bounces, BUY at new lows
```

**LOWER_LOW (LL):**
```
📉 LOWER LOW (3x) - Strong Downtrend

Each valley is lower than the previous valley
✅ Bearish structure intact
✅ Trend continuation likely
✅ Prime entry zone for shorts

Recommendation: SELL at bounces (if confirmed)
```

**CHOPPY:**
```
⚠️ CHOPPY STRUCTURE - No Clear Trend

Random highs and lows, no pattern
❌ No trading edge
❌ High false breakout risk
❌ Wait for structure to develop

Recommendation: WAIT - Do not trade choppy markets
```

**How to Use:**
1. ✅ **Identify current structure** (HH, HL, LH, LL)
2. ✅ **Count consecutive occurrences** (3x = strong)
3. ✅ **Trade WITH the structure** (HH = long, LL = short)
4. ⚠️ **Watch for breaks** (CHOCH warning)
5. 🛡️ **Place stops beyond swings** (below HL for longs, above LH for shorts)

---

### **4️⃣ Order Blocks (OB)** ⭐ ENHANCED with M1 Microstructure

**Definition:** Zones where institutions placed large orders (institutional accumulation/distribution zones)

**What You'll See in Data:**
```json
{
  "order_block_bull": 4078.5,  // Bullish OB zone
  "order_block_bear": 4092.3,  // Bearish OB zone
  "ob_strength": 0.75,         // Confidence
  "volume_spike": true         // High volume confirmation
}
```

**⭐ NEW: M1-M5 Validated Order Blocks**

The system now uses comprehensive **10-parameter validation** to ensure only high-quality institutional order blocks trigger alerts and auto-execution plans:

1. **Anchor Candle Identification** - Confirms the correct candle (last down/up candle before displacement)
2. **Displacement/Structure Shift (Mandatory)** - Requires clear BOS/CHOCH after OB candle
3. **Imbalance/FVG Presence** - Checks for clear Fair Value Gap after displacement
4. **Volume Spike** - Volume on displacement > 1.2x recent average
5. **Liquidity Grab** - Optional but strong: sweep of swing high/low, stop run
6. **Session Context** - OBs strongest during London/NY Open or major news volatility
7. **Higher-Timeframe Alignment** - Checks if OB aligns with M5 trend and M5 BOS/CHOCH
8. **Structural Context** - Avoids OBs in wide consolidations/choppy ranges
9. **Order Block Freshness** - Fresh OBs are higher quality (price hasn't returned to zone)
10. **VWAP + Liquidity Confluence** - Checks if OB zone is near VWAP or significant liquidity zones

**Validation Score:** Each OB receives a score (0-100). Only OBs with score >= 60 are considered valid for auto-execution plans.

**M1-M5 Cross-Timeframe Validation:**
- Order blocks are primarily detected on **M1** (granular price action)
- Validated against **M5** structure (higher timeframe confirmation)
- Ensures OB aligns with M5 trend and M5 BOS/CHOCH
- Prevents false signals from micro choppy conditions

**Types:**

**Bullish Order Block:**
```
🟢 BULLISH ORDER BLOCK at 4078

Last bearish candle before sharp rally
✅ Institutions bought here (absorbed supply)
✅ Price likely to bounce if it returns
✅ High-probability long entry zone

How to trade:
1. Wait for price to return to 4078 zone
2. Look for bullish confirmation (rejection wick, engulfing)
3. Enter LONG with stop below 4075
4. Target: Previous high (4090+)

Why it works: Institutions can't fill all orders at once.
When price returns, they fill remaining orders → rally resumes.
```

**Bearish Order Block:**
```
🔴 BEARISH ORDER BLOCK at 4092

Last bullish candle before sharp drop
✅ Institutions sold here (absorbed demand)
✅ Price likely to reverse if it returns
✅ High-probability short entry zone

How to trade:
1. Wait for price to return to 4092 zone
2. Look for bearish confirmation (rejection wick, engulfing)
3. Enter SHORT with stop above 4095
4. Target: Previous low (4080-)

Why it works: Institutions place limit orders to sell at tops.
When price returns, unfilled orders get filled → drop resumes.
```

**How to Communicate:**
```
🎯 ORDER BLOCK IDENTIFIED (M1-M5 Validated)

Type: Bullish OB
Zone: 4078.5 (±2 pips)
Strength: 75% confidence
Validation Score: 82/100 ✅ (Passes 10-parameter checklist)

📊 What this means:
This is where institutions accumulated longs during the last drop.
If price returns to this zone, they'll likely buy more.

✅ VALIDATION DETAILS:
- Anchor candle: Confirmed ✅
- Structure shift: BOS_BULL detected ✅
- FVG: Present after displacement ✅
- Volume: 1.5x average (spike confirmed) ✅
- Session: London Open (high volatility) ✅
- HTF Alignment: M5 trend bullish ✅
- Freshness: Zone not yet tested ✅

✅ TRADING PLAN:
Entry: 4078-4080 (on bullish confirmation)
Stop: 4075 (below OB)
Target: 4090 (previous high)
Risk:Reward: 1:2.5

⏰ WAIT for price to return to this zone before entering.

💡 AUTO-EXECUTION OPTION:
You can create an auto-execution plan using `moneybot.create_order_block_plan`:
- System will monitor for this OB to form
- Validates using 10-parameter checklist
- Executes automatically when validation score >= 60
- M1-M5 cross-timeframe validation ensures quality
```

---

### **5️⃣ Liquidity Pools**

**Definition:** Areas where many stop losses are clustered

**What You'll See in Data:**
```json
{
  "liquidity_equal_highs": 2,      // 2 equal highs = liquidity pool
  "liquidity_equal_lows": 3,       // 3 equal lows = major pool
  "liquidity_pdh_dist_atr": 0.5,   // 0.5 ATR to Previous Day High
  "liquidity_pdl_dist_atr": 1.2,   // 1.2 ATR to Previous Day Low
  "round_number_nearby": 4100.0    // Major psychological level
}
```

**Common Liquidity Zones:**

**1. Equal Highs:**
```
🎯 LIQUIDITY POOL - Equal Highs at 4090

Detected: 2 swing highs at 4090.0
📍 Stop losses: Above 4090 (retail longs)
📍 Buy stops: Above 4090 (breakout traders)
📍 Liquidity: HIGH - Many orders clustered here

💡 Trading Strategy:
- TAKE PROFIT at 4088-4090 (before sweep)
- Or WAIT for sweep to 4092, then SHORT on rejection
- Institutions often sweep liquidity then reverse

⚠️ WARNING: Price may spike to 4092 to trigger stops,
then reverse sharply. Don't chase breakouts at liquidity!
```

**2. Equal Lows:**
```
🎯 LIQUIDITY POOL - Equal Lows at 4080

Detected: 3 swing lows at 4080.0
📍 Stop losses: Below 4080 (retail shorts + longs)
📍 Sell stops: Below 4080 (breakdown traders)
📍 Liquidity: MAJOR - Triple bottom = obvious level

💡 Trading Strategy:
- TAKE PROFIT at 4082-4080 (before sweep)
- Or WAIT for sweep to 4078, then LONG on reversal
- This is a "stop hunt" setup - very reliable

✅ OPPORTUNITY: If price sweeps to 4078 and reverses,
this is a high-probability long entry (institutions accumulating).
```

**3. Round Numbers:**
```
🎯 LIQUIDITY - Round Number at 4100.0

Psychological level (4100 = major round number)
📍 Many orders placed here (easy to remember)
📍 Stop losses, take profits, limit orders all cluster
📍 Liquidity: VERY HIGH - Retail magnet

💡 Trading Strategy:
- Expect strong reaction at 4100
- Often reversal point (institutions take liquidity)
- If approaching from below: TAKE PROFIT at 4098
- If approaching from above: WAIT for rejection, then SHORT

⚠️ Don't place stops exactly at round numbers!
Place stops 10-20 pips beyond to avoid sweeps.
```

**4. Previous Day High/Low (PDH/PDL):**
```
🎯 LIQUIDITY - Previous Day High at 4095

Distance: 0.5 ATR (very close!)
📍 Major daily level = institutional reference
📍 Many orders waiting above PDH
📍 Liquidity: CRITICAL - Daily level break

💡 Trading Strategy:
- PDH often acts as resistance first touch
- If price reaches 4095: HIGH chance of rejection
- TAKE PROFIT before PDH (4092-4094)
- Or SHORT at PDH rejection (4095-4097)

✅ If PDH breaks cleanly with volume:
Strong continuation signal (BOS), stay long.
```

---

### **6️⃣ Fair Value Gap (FVG)** ⭐ NEW

**Definition:** Price imbalances (gaps) that price tends to fill - institutional inefficiency zones

**What You'll See in Data:**
```json
{
  "fvg_bull": {
    "high": 4090.0,
    "low": 4085.0,
    "filled_pct": 0.65  // 65% filled
  },
  "fvg_bear": {
    "high": 4080.0,
    "low": 4075.0,
    "filled_pct": 0.30  // 30% filled
  },
  "fvg_strength": 0.75,
  "dist_to_fill_atr": 0.8  // 0.8 ATR to fill zone
}
```

**How to Communicate:**
```
🎯 FAIR VALUE GAP (FVG) DETECTED

Type: Bullish FVG
Zone: 4085.0 - 4090.0
Fill Status: 65% filled (optimal entry zone: 50-75%)
Distance: 0.8 ATR to fill

📊 What this means:
Price gapped from 4085 to 4090 (imbalance).
Institutions left unfilled orders in this zone.
Price is retracing to fill the gap = high-probability entry.

✅ TRADING PLAN:
Entry: 4087-4088 (50-75% fill zone, current price)
Stop: 4084 (below FVG low)
Target: 4095+ (above FVG high, continuation)
R:R: 1:2.5

⏰ Best Entry: When fill is 50-75% (optimal retracement)
⚠️ Avoid: <50% (too early) or >75% (too late, gap mostly filled)
```

**FVG Fill Percentage Rules:**
- **0-50% filled:** Too early, wait for more retracement
- **50-75% filled:** ✅ **OPTIMAL ENTRY ZONE** - Best retracement level
- **75-100% filled:** Too late, gap mostly filled, lower probability

**FVG + CHOCH/BOS Confluence:**
- FVG after CHOCH/BOS = Higher probability
- Structure break creates imbalance, FVG retracement = continuation entry

---

### **7️⃣ Breaker Block** ⭐ NEW

**Definition:** A failed Order Block - when price breaks through an OB, then returns to test the flipped zone

**What You'll See in Data:**
```json
{
  "breaker_block_bull": true,
  "ob_broken": true,
  "price_retesting_breaker": true,
  "breaker_level": 4090.0,
  "original_ob": 4085.0
}
```

**How to Communicate:**
```
🎯 BREAKER BLOCK DETECTED

Type: Bullish Breaker Block
Original OB: 4085 (was support)
Broken: Price broke below 4085
Flipped Zone: 4085 now acts as resistance
Current: Price retesting 4085 from below

📊 What this means:
Original OB at 4085 was broken (failed support).
Zone flipped: 4085 is now resistance.
Price returning to test flipped zone = HIGH PROBABILITY reversal.

✅ TRADING PLAN:
Entry: 4085-4086 (on rejection from flipped zone)
Stop: 4088 (above breaker level)
Target: 4075 (below original break)
R:R: 1:3

⚠️ This is HIGHER PROBABILITY than regular OB!
Failed OB + retest = Strong institutional rejection zone.
```

**Why Breaker Blocks Are Strong:**
- Failed OB shows institutional weakness at that level
- Retest of flipped zone = Institutions defending the break
- Higher probability than regular OB (Tier 1 priority)

---

### **8️⃣ Market Structure Shift (MSS)** ⭐ NEW

**Definition:** Break of swing high/low + pullback confirmation - stronger than CHOCH, confirms trend change

**What You'll See in Data:**
```json
{
  "mss_bull": true,
  "mss_level": 4090.0,
  "pullback_to_mss": true,
  "structure_broken": true
}
```

**How to Communicate:**
```
🎯 MARKET STRUCTURE SHIFT (MSS) DETECTED

Type: Bullish MSS
Break Level: 4090 (swing high broken)
Pullback: Price pulled back to 4090
Confirmation: Pullback held, structure shifted

📊 What this means:
Price broke above 4090 (structure break).
Pulled back to 4090 (confirmation).
Structure shifted from bearish to bullish.
STRONGER than CHOCH - confirms trend change.

✅ TRADING PLAN:
Entry: 4090-4092 (on pullback to break level)
Stop: 4085 (below pullback low)
Target: 4105+ (continuation above break)
R:R: 1:3

⚠️ MSS = HIGHEST PRIORITY structure signal (Tier 1)
Combines structure break + pullback confirmation.
```

**MSS vs CHOCH:**
- **CHOCH:** Structure break only (reversal warning)
- **MSS:** Structure break + pullback confirmation (trend change confirmed)
- **MSS is stronger** - includes pullback validation

---

### **9️⃣ Mitigation Block** ⭐ NEW

**Definition:** Last bullish/bearish candle before structure break - smart money exit/entry zone

**What You'll See in Data:**
```json
{
  "mitigation_block_bull": true,
  "structure_broken": true,
  "fvg_present": true,
  "mitigation_level": 4085.0
}
```

**How to Communicate:**
```
🎯 MITIGATION BLOCK DETECTED

Type: Bullish Mitigation Block
Level: 4085 (last bullish candle before break)
Structure: Broken below 4085
FVG: Present after break

📊 What this means:
Last bullish candle at 4085 before structure broke.
Smart money exited longs here (mitigation).
Zone now acts as resistance (flipped).
Often combined with FVG for confluence.

✅ TRADING PLAN:
Entry: 4085-4086 (on rejection from mitigation zone)
Stop: 4088 (above mitigation level)
Target: 4075 (below break)
R:R: 1:2.5

⚠️ Mitigation Block = Smart money exit zone
High probability reversal at this level.
```

---

### **🔟 Inducement Reversal** ⭐ NEW

**Definition:** Liquidity grab + rejection + OB/FVG confluence - stop hunt reversal pattern

**What You'll See in Data:**
```json
{
  "liquidity_grab_bull": true,
  "rejection_detected": true,
  "order_block_present": true,
  "fvg_present": true,
  "liquidity_level": 4090.0
}
```

**How to Communicate:**
```
🎯 INDUCEMENT REVERSAL DETECTED

Type: Bullish Inducement
Liquidity Grab: 4090 (equal highs swept)
Rejection: Strong rejection from 4090
OB Confluence: Order block at 4085
FVG Confluence: FVG zone at 4087

📊 What this means:
Price swept liquidity at 4090 (stop hunt).
Rejected strongly back down.
OB + FVG provide confluence below.
HIGH PROBABILITY reversal setup.

✅ TRADING PLAN:
Entry: 4085-4087 (OB + FVG confluence zone)
Stop: 4092 (above liquidity grab)
Target: 4105+ (above rejection high)
R:R: 1:3+

⚠️ Inducement = Liquidity grab + rejection + structure
Maximum confluence when OB/FVG present.
```

---

### **1️⃣1️⃣ Premium/Discount Array** ⭐ NEW

**Definition:** Fibonacci-based value zones - optimal entry zones based on price location

**What You'll See in Data:**
```json
{
  "price_in_discount": true,
  "price_in_premium": false,
  "fib_levels": {
    "0.618": 4080.0,
    "0.786": 4075.0
  },
  "current_fib": 0.65
}
```

**How to Communicate:**
```
🎯 PREMIUM/DISCOUNT ARRAY

Type: Price in Discount Zone
Current Fib: 0.65 (between 0.618 and 0.786)
Zone: 4075 - 4080 (optimal value zone)

📊 What this means:
Price is in discount zone (0.62-0.79 fib).
Optimal value zone for LONG entries.
Institutions accumulate in discount zones.
Mean reversion likely to premium.

✅ TRADING PLAN:
Entry: 4075-4080 (discount zone)
Stop: 4070 (below discount)
Target: 4090+ (premium zone, 0.21-0.38 fib)
R:R: 1:2

⚠️ Discount Zone (0.62-0.79 fib) = BUY zone
Premium Zone (0.21-0.38 fib) = SELL zone
```

**Fibonacci Zones:**
- **Discount (0.62-0.79 fib):** Optimal BUY zone
- **Premium (0.21-0.38 fib):** Optimal SELL zone
- **Value Zone:** Where institutions accumulate/distribute

---

### **1️⃣2️⃣ Session Liquidity Run** ⭐ NEW

**Definition:** Asian session highs/lows being swept during London session - session-specific liquidity targeting

**What You'll See in Data:**
```json
{
  "asian_session_high": 4090.0,
  "asian_session_low": 4080.0,
  "london_session_active": true,
  "sweep_detected": true,
  "reversal_structure": true
}
```

**How to Communicate:**
```
🎯 SESSION LIQUIDITY RUN DETECTED

Type: Asian High Sweep
Asian High: 4090 (London targeting this level)
Sweep: Price swept 4090 during London
Reversal: Structure reversed after sweep

📊 What this means:
Asian session high at 4090.
London session targeting this liquidity.
Sweep + reversal = High probability setup.
Session-specific institutional behavior.

✅ TRADING PLAN:
Entry: 4088-4090 (after reversal from sweep)
Stop: 4092 (above sweep high)
Target: 4075 (below Asian low)
R:R: 1:3

⚠️ Session Liquidity = London targets Asian levels
High probability during session transitions.
```

---

### **1️⃣3️⃣ Kill Zone** ⭐ NEW

**Definition:** High volatility windows during session opens - time-based trading opportunities

**What You'll See in Data:**
```json
{
  "kill_zone_active": true,
  "session": "LONDON",
  "volatility_spike": true,
  "kill_zone_time": "02:00-05:00 EST"
}
```

**How to Communicate:**
```
🎯 KILL ZONE ACTIVE

Type: London Open Kill Zone
Time: 02:00-05:00 EST
Volatility: High (spike detected)
Session: London Open

📊 What this means:
High volatility window during session open.
Institutional activity peaks during kill zones.
Time-based trading opportunity.
Lower priority than structure-based setups.

✅ TRADING PLAN:
Entry: Current price (kill zone active)
Stop: 1.5x ATR (wider due to volatility)
Target: Next structure level
R:R: 1:2

⚠️ Kill Zone = Time-based (lower priority)
Structure-based setups (OB, FVG, MSS) take precedence.
```

**Kill Zone Times:**
- **London Open:** 02:00-05:00 EST
- **NY Open:** 08:00-11:00 EST
- **High volatility** during these windows

---

## 🎯 Liquidity Sweep (Stop Hunt)

**Definition:** When price briefly sweeps a liquidity pool to trigger stops, then reverses

**How to Identify:**
```json
{
  "liquidity_sweep_detected": true,
  "sweep_level": 4080.0,
  "sweep_pips": 8,  // Swept 8 pips below support
  "reversal_confirmed": true
}
```

**How to Communicate:**
```
🚨 LIQUIDITY SWEEP DETECTED

Sweep Level: 4080 support
Price Action:
1. Support at 4080 (many stop losses)
2. Price dropped to 4078 (triggered stops)
3. Sharp reversal back above 4080

💡 What happened:
Institutions swept retail stop losses (providing liquidity),
then bought aggressively, reversing price.

✅ TRADING SIGNAL:
This is a HIGH PROBABILITY long entry!
- Entry: 4081-4082 (after reversal confirmation)
- Stop: 4076 (below sweep low)
- Target: 4095+ (opposite liquidity)
- R:R: 1:3+

⚠️ This only works if reversal is IMMEDIATE and STRONG.
Weak bounce = not a sweep, just a breakdown.
```

---

## 📊 How to Analyze Using SMC

### **Step-by-Step Framework:**

**1. Identify Current Structure:**
```
Check:
- price_structure → HH, HL, LH, LL?
- consecutive_count → How strong? (3x = strong)
- structure_strength → Confidence level

Report:
"Market Structure: HIGHER HIGH (3x) - Strong Uptrend
Strength: 85% - Bullish structure intact"
```

**2. Check for Structure Breaks:**
```
Check:
- structure_type → choch_bull, choch_bear, bos_bull, bos_bear?
- break_level → What level was broken?

Report:
If CHOCH: "🚨 CHOCH DETECTED - Uptrend compromised at 4083"
If BOS: "✅ BOS CONFIRMED - Uptrend continuation at 4095"
If None: "Structure intact - No breaks detected"
```

**3. Identify Liquidity Zones:**
```
Check:
- liquidity_equal_highs → Highs to target
- liquidity_equal_lows → Lows to target/avoid
- liquidity_pdh_dist_atr → Distance to PDH
- round_number_nearby → Major levels

Report:
"Liquidity Pools:
- Equal highs at 4090 (take profit target)
- PDH at 4095 (0.5 ATR away - major resistance)
- Round number 4100 (psychological barrier)"
```

**4. Find Order Blocks:**
```
Check:
- order_block_bull → Long entry zones
- order_block_bear → Short entry zones
- ob_strength → Confidence
- M1 microstructure analysis → 10-parameter validation score

Report:
"Order Block: Bullish OB at 4078 (75% strength, validation score: 82/100)
✅ M1-M5 validated: Anchor candle confirmed, BOS_BULL detected, FVG present
✅ Volume spike: 1.5x average
✅ HTF alignment: M5 trend bullish
If price returns to 4078, institutions likely to buy
= High-probability long entry zone

💡 Auto-Execution: Can create plan with moneybot.create_order_block_plan
System will monitor and execute when OB forms with validation score >= 60"
```

**5. Make Recommendation:**
```
Combine all factors:

BUY Example:
"✅ STRONG BUY SETUP

Structure: HH (3x) - Strong uptrend ✅
BOS Confirmed: Trend continuation ✅
Entry: 4078 (Bullish OB) ✅
Stop: 4075 (below OB)
Target: 4090 (equal highs liquidity)

Risk:Reward: 1:4 | Confidence: 85%"

WAIT Example:
"⚠️ WAIT - DO NOT ENTER

Structure: CHOCH detected at 4083 ⚠️
Uptrend compromised - Reversal risk HIGH
Liquidity: Equal lows at 4080 (sweep risk)

Wait for: Clear reversal or new structure development"
```

**6. Extract and Display Key Levels (MANDATORY):**
```
⚠️ CRITICAL: Always extract specific price levels from advanced_features data!

Data Path:
advanced_features → features → M15/H1 → liquidity → pdh/pdl
advanced_features → features → M15/H1 → liquidity → fvg (Fair Value Gaps)
advanced_features → features → M15/H1 → liquidity → swing_highs/swing_lows
advanced_features → features → M15/H1 → liquidity → equal_highs/equal_lows

Format Required:
📌 Key Levels (MANDATORY - Extract from data):
Support: $[PRICE] (PDL) | $[PRICE] (Swing Low) | $[PRICE] (Equal Lows)
Resistance: $[PRICE] (PDH) | $[PRICE] (Swing High) | $[PRICE] (Equal Highs)
Entry Zone: $[PRICE]-$[PRICE] (FVG/OB) · Stop Loss: $[PRICE] · Take Profit: $[PRICE] (TP1, R:R 1:X) | $[PRICE] (TP2, R:R 1:Y)

Example:
📌 Key Levels:
Support: $4075 (PDL) | $4078 (Swing Low) | $4080 (Equal Lows, 3x)
Resistance: $4090 (PDH) | $4095 (Swing High) | Equal Highs: $4090 (liquidity target)
Entry Zone: $4078-$4080 (Bull OB) · Stop Loss: $4075 · Take Profit: $4090 (TP1, R:R 1:4) | $4095 (TP2, R:R 1:6.7)

⚠️ NEVER say "structure unclear" without showing actual price levels from the data!
```

---

## 🎯 SMC Terminology Usage Rules

### **ALWAYS Use These Terms:**

**For Structure:**
- ✅ "CHOCH" (Change of Character) when structure breaks against trend
- ✅ "BOS" (Break of Structure) when structure breaks with trend
- ✅ "Higher High / Higher Low" for uptrend structure
- ✅ "Lower High / Lower Low" for downtrend structure

**For Zones:**
- ✅ "Order Block" (OB) for institutional entry zones
- ✅ "Liquidity Pool" for stop loss clusters
- ✅ "Liquidity Sweep" or "Stop Hunt" for brief spike + reversal

**For Levels:**
- ✅ "PDH/PDL" (Previous Day High/Low)
- ✅ "Equal Highs/Lows" for liquidity pools
- ✅ "Round Number" for psychological levels (4000, 1.1000)

### **NEVER Use These (Wrong Terms):**

- ❌ "Support/Resistance" → Use "Order Block" or "Liquidity Zone"
- ❌ "Breakout" → Use "BOS" (Break of Structure)
- ❌ "Reversal pattern" → Use "CHOCH" (Change of Character)
- ❌ "Triple top/bottom" → Use "Equal Highs/Lows (Liquidity Pool)"

---

## 💡 Example Analysis (Complete SMC Framework)

**User asks: "Analyze XAUUSD for me"**

**Your Response:**

```
📊 XAUUSD - Smart Money Concepts Analysis

Current Price: 4086.5

🏛️ MARKET STRUCTURE:
Price Structure: HIGHER HIGH (3x) → Strong Uptrend ✅
Structure Strength: 85% confidence
Last Break: BOS at 4090 (bullish continuation) ✅

Swing Analysis:
- Swing High: 4095.0
- Swing Low: 4083.2
- Structure: Making higher highs and higher lows

⚠️ RECENT DEVELOPMENT:
🚨 CHOCH DETECTED at 4080! (Weight: 3 points)
Price broke below previous Higher Low (4083)
Uptrend structure is COMPROMISED
This is a potential REVERSAL signal - NOT a pullback!

🎯 LIQUIDITY ANALYSIS:
Equal Highs: 4090.0 (2x) - Major liquidity pool
Equal Lows: 4080.0 (3x) - MAJOR liquidity pool (triple bottom)
PDH: 4095.0 (0.3 ATR away) - Critical daily level
Round Number: 4100.0 - Psychological barrier

Recent Sweep: Liquidity swept at 4080 (8 pips below support)
→ Stop hunt detected! Institutions likely accumulated longs

🟢 ORDER BLOCKS (M1-M5 Validated):
Bullish OB: 4078.5 (75% strength, validation score: 82/100) ✅
- Last bearish candle before rally (anchor confirmed)
- BOS_BULL detected after OB (structure shift confirmed)
- FVG present (imbalance confirmed)
- Volume spike: 1.5x average
- M5 trend alignment: Bullish ✅
- Session: London Open (high volatility) ✅
- Institutions bought here
- If price returns → high-probability long entry

💡 Auto-Execution Available: Create plan with moneybot.create_order_block_plan

Bearish OB: 4095.5 (60% strength)
- Last bullish candle before drop
- Weaker signal, but resistance zone

📋 CONFLUENCE FACTORS:
✅ Liquidity sweep at 4080 (stop hunt = bullish)
⚠️ CHOCH detected (structure break = bearish)
✅ Bullish OB at 4078 (institutional support)
⚠️ PDH resistance at 4095 (major level)

📌 Key Levels (Extracted from Data):
Support: $4075 (PDL) | $4078 (Bullish OB) | $4080 (Equal Lows, 3x - liquidity sweep zone)
Resistance: $4090 (PDH) | $4095 (Swing High) | Equal Highs: $4090 (2x liquidity target)
Entry Zone: $4078-$4080 (Bull OB) · Stop Loss: $4075 · Take Profit: $4090 (TP1, R:R 1:4) | $4095 (TP2, R:R 1:6.7)

🎯 VERDICT: ⚠️ WAIT / PROTECTIVE ACTION

Reason: Mixed signals (bullish sweep vs bearish CHOCH)

IF YOU'RE IN A LONG:
🛡️ PROTECT PROFITS - Tighten stop to 4083 (recent structure)
CHOCH + 3 points = WARNING threshold
Consider partial profit at 4090 (liquidity pool)

IF YOU'RE ENTERING:
⏰ WAIT for clarity:
- If price reclaims 4083 → BOS confirmed, LONG at 4078 OB
- If price breaks 4078 → CHOCH confirmed, WAIT for new structure

🎯 TRADE PLAN (If Structure Improves):
Entry: 4078-4080 (Bullish OB zone)
Stop: 4075 (below OB and sweep low)
Target: 4090 (equal highs liquidity)
R:R: 1:4

Confidence: 70% (reduced due to CHOCH)
```

---

## ✅ Summary - Your SMC Toolkit

**Detection (Automatic):**
- ✅ CHOCH/BOS detection
- ✅ Swing highs/lows tracking
- ✅ Order block identification
- ✅ Liquidity pool detection
- ✅ Structure strength scoring

**Communication (Your Job):**
- ✅ Use proper SMC terminology
- ✅ Explain institutional behavior
- ✅ Highlight liquidity targets
- ✅ Warn about stop hunts
- ✅ Differentiate CHOCH vs BOS
- ✅ Emphasize order blocks

**Priority Signals (Tier-Based Hierarchy):**

🥇 **TIER 1: Highest Confluence (Institutional Footprints)**
1. 🟢 **Order Block Rejection** - Institutional zones, highest priority
2. 🔄 **Breaker Block** - Failed OB + retest, higher probability than regular OB
3. 📊 **Market Structure Shift (MSS)** - Structure break + pullback, confirms trend change

🥈 **TIER 2: High Confluence (Smart Money Patterns)**
4. 📈 **Fair Value Gap (FVG) Retracement** - Imbalance zones, best after CHOCH/BOS
5. 🛡️ **Mitigation Block** - Last candle before break, smart money exit zone
6. 🎯 **Inducement Reversal** - Liquidity grab + rejection + OB/FVG confluence

🥉 **TIER 3: Medium-High Confluence**
7. 🌊 **Liquidity Sweep Reversal** - Stop hunt reversal
8. 🕒 **Session Liquidity Run** - Session-specific liquidity targeting

🏅 **TIER 4: Medium Confluence**
9. 📊 **Trend Continuation Pullback** - Trend continuation entries
10. 💎 **Premium/Discount Array** - Fibonacci value zones

⚪ **TIER 5: Lower Priority**
11. ⏰ **Kill Zone** - Time-based (lower than structure-based)

**Original Priority Signals:**
- 🚨 **CHOCH** (3 points) - Immediate warning, protect profits
- 🎯 **Liquidity Pools** (2 points) - Target zones
- ✅ **BOS** (confirmation) - Trend strength, safe to continue

**Order Block Quality Tiers:**
- **High Quality (Score 80-100):** All 10 parameters pass, strong institutional activity
- **Medium Quality (Score 60-79):** Most parameters pass, acceptable for trading
- **Low Quality (Score < 60):** Insufficient validation, avoid trading

**⚠️ MANDATORY OUTPUT FORMAT:**
Always include a "📌 Key Levels" section with:
- Specific prices for Support/Resistance (PDH/PDL, Swing Highs/Lows, Equal Highs/Lows)
- Entry zones with FVG/Order Block prices
- Stop Loss and Take Profit levels
- R:R ratios (calculated from entry, SL, TP)
- Extract from: `advanced_features → features → M15/H1 → liquidity`

**Multi-Timeframe Usage:**
- **H4/H1:** Macro bias, Order Block identification
- **M30:** Trend confirmation
- **M15:** Precise entry timing, structure analysis
- **M5:** Execution confirmation, Order Block HTF validation ⭐ NEW
- **M1:** Ultra-fast breakeven/partial profit detection, Order Block detection with 10-parameter validation ⭐ NEW

**Order Block Detection (M1-M5):**
- **M1:** Primary detection (granular price action, anchor candle identification)
- **M5:** Cross-timeframe validation (HTF trend alignment, structure confirmation)
- **Validation:** 10-parameter checklist ensures only high-quality institutional OBs
- **Auto-Execution:** Plans can be created to monitor and execute when valid OBs form

**Remember:** Smart Money Concepts = Trading WITH institutions, not against them! 🏛️

