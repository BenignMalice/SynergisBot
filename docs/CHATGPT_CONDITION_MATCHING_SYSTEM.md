# How ChatGPT Knows When to Use Conditions for Auto-Execution Plans

## Overview

ChatGPT uses a **pattern-matching system** that maps keywords in the reasoning/strategy to specific required conditions. This ensures that auto-execution plans monitor for the correct market conditions, not just price levels.

## The Pattern Matching System

### Location of Rules

The rules are defined in **two locations** (for redundancy):

1. **`openai.yaml`** (lines 492-506 and 652-658)
2. **`AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`** (lines 6-31)

Both files contain identical mapping rules so ChatGPT always has the guidance available.

### How It Works

**Step 1: ChatGPT analyzes the strategy/reasoning text**

When ChatGPT creates a trade plan, it:
1. Reads the market analysis
2. Identifies the strategy type (e.g., "Order Block", "CHOCH", "Breakout")
3. Writes the reasoning/notes field

**Step 2: Pattern matching rules kick in**

The instructions contain explicit rules like:
```
If reasoning mentions "Order Block" or "OB" 
→ Include {"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}
```

**Step 3: ChatGPT includes matching conditions**

Based on the keywords detected, ChatGPT adds the appropriate conditions to the plan.

## Complete Pattern Matching Rules

### 1. Order Block Strategies

**Keywords:** "Order Block", "OB"

**Required conditions:**
```json
{
  "order_block": true,
  "order_block_type": "auto",
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to detect institutional order blocks, not just wait for price

---

### 2. CHOCH/BOS Strategies

**Keywords:** "CHOCH", "BOS", "Change of Character", "Break of Structure"

**Required conditions:**
```json
{
  "choch_bull": true,  // or "choch_bear": true
  "timeframe": "M5",   // or "M15"
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to detect market structure shifts, not just price levels

---

### 3. Breakout Strategies

**Keywords:** "Breakout", "Inside Bar", "Volatility Trap"

**Required conditions:**
```json
{
  "price_above": entry_price,  // or "price_below"
  "price_near": entry_price,
  "tolerance": X
}
```

**Critical rule:** ALWAYS include both `price_above`/`price_below` AND `price_near` + `tolerance`

**Why:** Ensures breakout happens at the specific level, not just any level

---

### 4. Rejection Wick Strategies

**Keywords:** "Rejection Wick", "Pin Bar"

**Required conditions:**
```json
{
  "rejection_wick": true,
  "timeframe": "M5",
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to detect authentic rejection wicks, not just price touches

---

### 5. Liquidity Sweep Strategies

**Keywords:** "Liquidity Sweep", "Stop Hunt"

**Required conditions:**
```json
{
  "liquidity_sweep": true,
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to detect liquidity grabs, not just price levels

---

### 6. VWAP Deviation Strategies

**Keywords:** "VWAP Deviation", "VWAP Bounce", "VWAP Fade"

**Required conditions:**
```json
{
  "vwap_deviation": true,
  "vwap_deviation_direction": "below",  // or "above"
  "vwap_deviation_threshold": 2.0,
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to calculate VWAP distance, not just check price

---

### 7. EMA Slope Strategies

**Keywords:** "EMA Slope", "Trend Alignment"

**Required conditions:**
```json
{
  "ema_slope": true,
  "ema_slope_direction": "bullish",  // or "bearish"
  "price_near": entry_price,
  "tolerance": X
}
```

**Why:** System needs to check EMA slope angle, not just price vs EMA

---

## Critical Rules ChatGPT Must Follow

### Rule 1: Always Include `price_near` + `tolerance`

**Every plan MUST have:**
```json
{
  "price_near": entry_price,
  "tolerance": appropriate_value
}
```

**Why:** Without this, the plan might execute at the wrong price level

**Example of what goes wrong:**
```json
// ❌ WRONG - Missing price_near
{
  "choch_bull": true,
  "timeframe": "M5"
}
// Result: Will execute at ANY price when CHOCH is detected

// ✅ CORRECT
{
  "choch_bull": true,
  "timeframe": "M5",
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Result: Only executes when CHOCH is detected AND price is near 86000
```

---

### Rule 2: Match Conditions to Strategy Type

**The conditions MUST match what's described in reasoning:**

**Example 1: Order Block Strategy**
```
Reasoning: "Price rejecting from bullish order block at 86000"

✅ CORRECT conditions:
{
  "order_block": true,
  "order_block_type": "auto",
  "price_near": 86000.0,
  "tolerance": 100.0
}

❌ WRONG conditions:
{
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Missing order_block detection!
```

**Example 2: CHOCH Strategy**
```
Reasoning: "Waiting for M5 CHOCH Bull confirmation at 4140"

✅ CORRECT conditions:
{
  "choch_bull": true,
  "timeframe": "M5",
  "price_near": 4140.0,
  "tolerance": 3.0
}

❌ WRONG conditions:
{
  "price_above": 4140.0,
  "price_near": 4140.0,
  "tolerance": 3.0
}
// Wrong condition type - looking for breakout instead of CHOCH!
```

---

### Rule 3: Breakout Plans Need Both Directional AND Proximity Conditions

**For breakout strategies:**
```json
{
  "price_above": entry_price,  // Directional condition
  "price_near": entry_price,   // Proximity condition
  "tolerance": X               // Tolerance for proximity
}
```

**Why both are needed:**
- `price_above`: Ensures price breaks ABOVE the level
- `price_near`: Ensures execution happens NEAR the breakout level (not far away)
- `tolerance`: Defines acceptable distance from entry

**What goes wrong without both:**
```json
// ❌ WRONG - Only directional
{
  "price_above": 86000.0
}
// Result: Will execute at ANY price above 86000 (could be 87000, 88000, etc.)

// ✅ CORRECT
{
  "price_above": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Result: Only executes when price breaks above 86000 AND is within 100 points of 86000
```

---

### Rule 4: Never Mix Contradictory Conditions

**❌ NEVER include both:**
```json
{
  "price_above": 86000.0,
  "price_below": 86000.0  // Contradictory!
}
```

**✅ Use one or the other:**
```json
// For BUY breakout
{
  "price_above": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0
}

// For SELL breakdown
{
  "price_below": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0
}
```

---

## Optional Enhancement Conditions

### When to Add (vs When NOT to Add)

**These conditions are OPTIONAL and should only be added when market conditions specifically warrant them:**

#### `m1_choch_bos_combo: true`
- **Add when:** M1 structure is clear and extra precision is critical for CHOCH plans
- **Don't add when:** Market is choppy or you want higher execution probability
- **Effect:** Requires M1 CHOCH+BOS combo confirmation (very strict)

#### `min_volatility: 0.5`
- **Add when:** Market is in a dead zone and you want to wait for volatility expansion
- **Don't add when:** Volatility is already normal or expanding
- **Effect:** Blocks execution if ATR ratio is below 0.5

#### `bb_width_threshold: 2.5`
- **Add when:** Specifically waiting for volatility expansion (Bollinger squeeze breakout)
- **Don't add when:** Normal breakout or trend continuation
- **Effect:** Blocks execution if Bollinger Band width is below 2.5

#### `volatility_state: "EXPANDING"` or `"CONTRACTING"`
- **Add when:**
  - `EXPANDING`: For breakout trades IF you want extra confirmation (optional)
  - `CONTRACTING`: For mean reversion/range scalp trades (rare)
- **Don't add when:** Default behavior - let price action trigger
- **Effect:** Blocks execution if volatility state doesn't match

**⚠️ CRITICAL for Breakouts:**
- DO NOT use `volatility_state: CONTRACTING` for breakout strategies
- Breakouts execute during EXPANSION, not CONTRACTION
- Default: OMIT volatility_state for breakout plans

---

## How ChatGPT Determines Tolerance Values

**Tolerance varies by symbol:**

### Forex (e.g., EURUSD, GBPUSD)
- **Default:** 0.0003 (3 pips) for M5
- **Tighter:** 0.0001-0.0002 for M1 micro scalps
- **Wider:** 0.0005 for H1

### Crypto (e.g., BTCUSDc)
- **Default:** 100.0 for M5 (±100 USD)
- **Tighter:** 20.0 for M1 micro scalps
- **Wider:** 200.0 for H1

### Metals (e.g., XAUUSDc)
- **Default:** 3.0 for M5 (±$3)
- **Tighter:** 1.0 for M1 micro scalps
- **Wider:** 5.0 for H1

**Rule of thumb:** Tolerance should be ~0.3-0.5% of price or 1-2x average spread

---

## Strategy Type Parameter (for Universal Manager)

### When to Include `strategy_type`

ChatGPT is instructed to **ALWAYS include** `strategy_type` when creating plans.

**Why:** Enables Universal Dynamic SL/TP Manager for advanced stop loss and take profit management.

**Available strategy types:**
1. `breakout_ib_volatility_trap` - For range breakouts, inside bar setups
2. `trend_continuation_pullback` - For trend-following trades
3. `liquidity_sweep_reversal` - For reversal trades after stop hunts
4. `order_block_rejection` - For institutional OB trades
5. `mean_reversion_range_scalp` - For range trading, scalping

**Selection criteria:**
- **NOT based on preference** - must match actual market conditions
- **Order Block > Liquidity Sweep > Trend Continuation > Range Scalp > Breakout** (priority order)
- **Breakout is LAST choice** - only when volatility compression is confirmed

---

## Examples of Complete Plans

### Example 1: Order Block Strategy
```json
{
  "symbol": "XAUUSDc",
  "direction": "BUY",
  "entry_price": 4140.0,
  "stop_loss": 4135.0,
  "take_profit": 4155.0,
  "conditions": {
    "order_block": true,
    "order_block_type": "auto",
    "price_near": 4140.0,
    "tolerance": 3.0
  },
  "strategy_type": "order_block_rejection",
  "reasoning": "Bullish order block at 4140 with institutional support"
}
```

### Example 2: CHOCH Strategy
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry_price": 86000.0,
  "stop_loss": 85800.0,
  "take_profit": 86500.0,
  "conditions": {
    "choch_bull": true,
    "timeframe": "M5",
    "price_near": 86000.0,
    "tolerance": 100.0
  },
  "strategy_type": "trend_continuation_pullback",
  "reasoning": "M5 CHOCH Bull confirming trend continuation at 86000"
}
```

### Example 3: Breakout Strategy (Simple)
```json
{
  "symbol": "EURUSDc",
  "direction": "BUY",
  "entry_price": 1.1500,
  "stop_loss": 1.1480,
  "take_profit": 1.1540,
  "conditions": {
    "price_above": 1.1500,
    "price_near": 1.1500,
    "tolerance": 0.0003
  },
  "strategy_type": "breakout_ib_volatility_trap",
  "reasoning": "Range breakout above 1.1500 resistance"
}
```

### Example 4: Liquidity Sweep Strategy
```json
{
  "symbol": "XAUUSDc",
  "direction": "SELL",
  "entry_price": 4128.0,
  "stop_loss": 4133.0,
  "take_profit": 4110.0,
  "conditions": {
    "liquidity_sweep": true,
    "choch_bear": true,
    "timeframe": "M5",
    "price_near": 4128.0,
    "tolerance": 3.0
  },
  "strategy_type": "liquidity_sweep_reversal",
  "reasoning": "Liquidity sweep + CHOCH Bear at 4128 for reversal"
}
```

---

## Validation System

### Backend Validation (`chatgpt_auto_execution_integration.py`)

The system has **automatic condition validation** that checks:

1. **Missing required companion conditions:**
   - If `order_block: true` → Auto-adds `order_block_type: "auto"`
   - If `ema_slope_direction` exists → Auto-adds `ema_slope: true`
   - If structure conditions exist → Auto-adds `timeframe: "M5"` if missing

2. **Invalid values:**
   - `volatility_state` must be "EXPANDING", "CONTRACTING", or "STABLE"
   - Auto-corrects common typos (e.g., "EXPAND" → "EXPANDING")

3. **Required fields:**
   - Ensures `price_near` and `tolerance` are present when needed

**Location:** `chatgpt_auto_execution_integration.py`, `_validate_and_fix_conditions()` method (lines 150-236)

---

## Common Mistakes and Fixes

### Mistake 1: Missing Core Condition

**❌ WRONG:**
```json
{
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Reasoning says "Order Block at 86000" but no order_block condition!
```

**✅ CORRECT:**
```json
{
  "order_block": true,
  "order_block_type": "auto",
  "price_near": 86000.0,
  "tolerance": 100.0
}
```

### Mistake 2: Breakout Without `price_near`

**❌ WRONG:**
```json
{
  "price_above": 86000.0
}
// Will execute at ANY price above 86000!
```

**✅ CORRECT:**
```json
{
  "price_above": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Only executes near the breakout level
```

### Mistake 3: Wrong `volatility_state` for Breakout

**❌ WRONG:**
```json
{
  "price_above": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0,
  "volatility_state": "CONTRACTING"  // Backwards!
}
// Reasoning: "Inside Bar breakout at 86000"
```

**✅ CORRECT:**
```json
{
  "price_above": 86000.0,
  "price_near": 86000.0,
  "tolerance": 100.0
}
// Omit volatility_state (recommended)
```

---

## Summary

**How ChatGPT knows when to use conditions:**

1. **Keyword detection** in reasoning/strategy text
2. **Pattern matching rules** map keywords to required conditions
3. **Mandatory `price_near` + `tolerance`** for all plans
4. **Strategy-specific conditions** ensure correct market validation
5. **Optional enhancements** only when market conditions warrant
6. **Backend validation** catches missing/invalid conditions

**Result:** Plans monitor for the correct market conditions and execute at the right price levels, not just any price.

