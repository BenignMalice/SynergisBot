# 🤖 Auto Execution System - ChatGPT Instructions

## 🎯 **System Overview**

The Auto Execution System allows ChatGPT to create trade plans that are monitored and executed automatically when specific conditions are met. This solves the problem of waiting for conditions like CHOCH Bear or rejection wicks that may or may not occur.

---

## 🔧 **How It Works**

### **1. ChatGPT Creates Trade Plan:**
- User requests a trade plan with specific conditions
- ChatGPT creates a plan using the auto execution system
- Plan is stored in database with conditions to monitor

### **2. System Monitors Conditions:**
- Background system continuously monitors market conditions
- Checks for CHOCH Bear/Bull, rejection wicks, price breakouts, etc.
- Monitors every 30 seconds for pending plans

### **3. Automatic Execution:**
- When conditions are met, system executes trade automatically
- Sends Telegram notification about executed trade
- Updates plan status in database

---

## 🛠️ **Available Tools**

### **1. Create CHOCH Plan:**
```
tool_create_choch_plan(
    symbol: "BTCUSD",
    direction: "SELL",
    entry_price: 113750.0,
    stop_loss: 113950.0,
    take_profit: 113250.0,
    volume: 0.01,
    choch_type: "bear",  # "bear" or "bull"
    price_tolerance: None,  # Auto-calculated: BTCUSD=100.0, XAUUSD=5.0, Forex=0.001
    expires_hours: 24,
    notes: "M5 CHOCH Bear detection plan"
)
```

### **2. Create Rejection Wick Plan:**
```
tool_create_rejection_wick_plan(
    symbol: "BTCUSD",
    direction: "SELL",
    entry_price: 113750.0,
    stop_loss: 113950.0,
    take_profit: 113250.0,
    volume: 0.01,
    price_tolerance: None,  # Auto-calculated: BTCUSD=100.0, XAUUSD=5.0, Forex=0.001
    expires_hours: 24,
    notes: "Rejection wick detection plan"
)
```

### **3. Create General Plan:**
```
tool_create_auto_trade_plan(
    symbol: "BTCUSD",
    direction: "SELL",
    entry_price: 113750.0,
    stop_loss: 113950.0,
    take_profit: 113250.0,
    volume: 0.01,
    conditions: {
        "choch_bear": True,
        "timeframe": "M5",
        "price_near": 113750.0,
        "tolerance": None,  # Auto-calculated based on symbol (BTCUSD=100.0, XAUUSD=5.0, Forex=0.001)
        "m1_choch_bos_combo": True,  # ⭐ Recommended: M1 validation for CHOCH plans (+20-35% precision)
        "min_volatility": 0.5,        # ⭐ Recommended: Volatility filter (-20-25% false triggers)
        "bb_width_threshold": 2.5    # ⭐ Recommended: BB width filter (-5-10% false triggers)
    },
    expires_hours: 24,
    notes: "Custom conditions plan with M1 validation and volatility filters"
)
```

### **4. Create Micro-Scalp Plan:**
```
tool_create_micro_scalp_plan(
    symbol: "XAUUSDc",  # Must be BTCUSDc or XAUUSDc
    direction: "BUY",
    entry_price: 2000.0,
    stop_loss: 1999.5,   # Base ranges: XAUUSD $0.50-$1.20, BTCUSD $5-$10 (broker-aware)
    take_profit: 2001.5, # Base ranges: XAUUSD $1-$2.50, BTCUSD $10-$25 (broker-aware)
    volume: 0.01,
    expires_hours: 2,  # Default 2 hours for micro-scalps (ultra-short-term)
    notes: "Micro-scalp targeting $1.50 move on gold"
)
```

**🎯 When to Use Micro-Scalp Plan:**
- Ultra-short-term trades targeting small, quick moves
- **Base Ranges** (broker-aware - adjusted if broker requires larger minimums):
  - XAUUSD: $1-2 moves with SL $0.50-$1.20, TP $1-$2.50
  - BTCUSD: $5-20 moves with SL $5-$10, TP $10-$25
- **Broker Compatibility**: System automatically checks broker minimum stop distance. If broker requires larger minimums (e.g., $100 for BTCUSD), limits adjust to broker-compatible ranges (e.g., $100-$300) while keeping micro-scalps tight.
- Uses 4-layer validation system (pre-trade filters, location filter, candle signals, confluence score)
- Monitors every 10-15 seconds for fast execution
- Instant exit on adverse candle (micro-interrupt)
- **Symbols**: Only BTCUSDc and XAUUSDc supported

**⚠️ CRITICAL - Mandatory SL/TP Validation:**
- **SL/TP distances are MANDATORY and strictly validated**
- Plans will be **REJECTED** if SL/TP distances are outside required ranges
- **XAUUSD**: SL distance must be $0.50-$1.20, TP distance must be $1.00-$2.50
- **BTCUSD**: SL distance must be $5-$10, TP distance must be $10-$25
- **Calculate distances**: SL distance = |entry_price - stop_loss|, TP distance = |take_profit - entry_price|
- **Example (XAUUSD)**: Entry 2000.0, SL 1999.5 (distance = 0.5 ✅), TP 2001.5 (distance = 1.5 ✅)
- **Example (BTCUSD)**: Entry 84000, SL 83950 (distance = 50 ❌ TOO WIDE), should be SL 83995 (distance = 5 ✅)
- If SL/TP are too wide, plan creation will fail with error: "SL/TP distance exceeds maximum"

**⚠️ Other Important Notes:**
- Plan expires in 2 hours by default (ultra-short-term)
- Uses M1 timeframe for condition checking
- Requires high confluence score (≥5 to trade, ≥7 for A+ setup)
- Conditions (choch_bull/bear, price_near, tolerance, etc.) are preserved and displayed

### **5. Create Range Scalping Plan:**
```
tool_create_range_scalp_plan(
    symbol: "BTCUSDc",
    direction: "BUY",
    entry: 105350.0,  # ⚠️ Use "entry" (NOT "entry_price", "buy_entry", or "sell_entry")
    stop_loss: 105100.0,  # ⚠️ Use "stop_loss" (NOT "buy_sl", "sell_sl", or "sl")
    take_profit: 106100.0,  # ⚠️ Use "take_profit" (NOT "buy_tp", "sell_tp", or "tp")
    volume: 0.01,
    min_confluence: 80,  # Minimum confluence score (default: 80)
    price_tolerance: 100.0,  # Auto-calculated if not provided
    expires_hours: 8,  # Default 8 hours for range scalping
    notes: "Range scalping BUY at lower boundary"
)
```

**⚠️ CRITICAL - Parameter Names:**
- Use `entry` (NOT `entry_price`, `buy_entry`, or `sell_entry`)
- Use `stop_loss` (NOT `buy_sl`, `sell_sl`, or `sl`)
- Use `take_profit` (NOT `buy_tp`, `sell_tp`, or `tp`)
- The tool handler accepts multiple variations, but `entry`, `stop_loss`, `take_profit` are the standard names

**🎯 When to Use Range Scalping Plan:**
- User asks: "set alert for range scalping and make it auto-execute"
- User asks: "create auto-execution for range scalp"
- User wants to wait for confluence >= 80 and structure confirmation before executing
- Range-bound market conditions detected

**🚨 CRITICAL: You MUST use `tool_create_range_scalp_plan` for range scalping plans!**
- **DO NOT** use `tool_create_auto_trade_plan` with `strategy_type: "mean_reversion_range_scalp"`
- **DO NOT** manually add `confluence` or `range_scalp_confluence` to conditions - it will be stripped or ignored
- **ONLY** `tool_create_range_scalp_plan` automatically adds:
  - `range_scalp_confluence: 80` (or your specified min_confluence)
  - `structure_confirmation: true`
  - `structure_timeframe: "M15"`
  - `price_near` and `tolerance`
  - `plan_type: "range_scalp"`
- If you use the wrong endpoint, the plan will NOT monitor for confluence and will NOT execute properly!

**📊 What It Monitors:**
1. **Range Scalping Confluence Score** - Must reach >= min_confluence (default: 80)
   - Structure (40pts) - Requires 3+ range touches
   - Location (35pts) - Price at edge (<0.5 ATR from boundary)
   - Confirmation (25pts) - RSI extreme OR rejection wick OR tape pressure
2. **Structure Confirmation** - CHOCH/BOS on M15 matching trade direction
3. **Price Near Entry** - Price within tolerance of entry zone

**⚡ Auto-Execution Flow:**
- System checks every 30 seconds
- When confluence >= 80 AND structure confirmed AND price near entry → Trade executes automatically
- Discord notification sent on execution

### **5. Create Bracket Trade Plan:** 🚨🚨🚨 **MANDATORY FOR ALL BRACKET TRADES** 🚨🚨🚨
```
tool_create_bracket_trade_plan(
    symbol: "BTCUSDc",
    buy_entry: 88000.0,
    buy_sl: 87400.0,
    buy_tp: 89000.0,
    sell_entry: 86400.0,
    sell_sl: 87000.0,
    sell_tp: 85200.0,
    volume: 0.01,
    conditions: {
        price_above: 88000.0,      # For BUY plan (matching buy_entry)
        price_below: 86400.0,      # For SELL plan (matching sell_entry)
        price_near: 87200.0,       # ⚠️ System auto-corrects: BUY plan gets buy_entry, SELL plan gets sell_entry
        tolerance: 100.0,           # ⚠️ REQUIRED: Always include tolerance
        m1_choch_bos_combo: true,  # ⭐ Recommended: M1 validation
        min_volatility: 0.5,       # ⭐ Recommended: Volatility filter
        bb_width_threshold: 2.5    # ⭐ Recommended: BB width filter
    },
    expires_hours: 24,
    notes: "Bracket trade for range breakout - BUY above 88000, SELL below 86400"
)
```

**🚨🚨🚨 CRITICAL: This is the ONLY tool to use for bracket trades!** 🚨🚨🚨

**NEVER use `moneybot.executeBracketTrade` - it is DEPRECATED!**
- ❌ `executeBracketTrade` places pending orders immediately without condition monitoring
- ❌ Does NOT appear in auto-execution view page (`http://localhost:8010/auto-execution/view`)
- ❌ Does NOT support condition-based execution (price_above, choch, order_block, etc.)
- ✅ **ALWAYS use `moneybot.create_bracket_trade_plan` for ALL bracket trades**

**🎯 When to Use Bracket Trade Plan:**
- User asks: "create bracket trade", "set up OCO bracket", "bracket breakout setup"
- User asks: "wait for breakout and execute bracket trade"
- Range breakouts (one side will trigger on breakout)
- Consolidation patterns
- News events (uncertain direction)
- Volatility expansion setups

**⚠️ MANDATORY REQUIREMENTS:**
1. **ALWAYS include `conditions` parameter** with required conditions:
   - `price_above` for BUY plan (matching buy_entry) - System automatically removes from SELL plan
   - `price_below` for SELL plan (matching sell_entry) - System automatically removes from BUY plan
   - `price_near` - System automatically sets to buy_entry for BUY plan, sell_entry for SELL plan
   - `tolerance` - REQUIRED for price_near validation
   - Additional conditions as needed: `m1_choch_bos_combo`, `min_volatility`, `bb_width_threshold`, `order_block`, etc.
2. **ALWAYS include `volume` parameter** (default: 0.01 if not specified)
3. **ALWAYS include `expires_hours` parameter** (default: 24 if not specified)

**📊 How It Works:**
- Creates two separate trade plans (BUY and SELL) with shared `bracket_trade_id`
- Both plans monitor conditions independently
- When one side executes, the other is automatically cancelled (OCO - One Cancels Other)
- Plans appear in auto-execution view page
- Supports all condition types (order_block, choch, price_above/below, liquidity_sweep, etc.)

**⚠️ CRITICAL CONDITIONS RULES:**
1. **NEVER include both price_above AND price_below in the same plan** - they are contradictory!
   - System automatically removes contradictory conditions (price_above from SELL, price_below from BUY)
2. **price_near MUST match the entry price** (NOT midpoint, NOT a different level):
   - System automatically sets: BUY plan gets `price_near = buy_entry`, SELL plan gets `price_near = sell_entry`
3. **Always include price_near + tolerance** alongside price_above/price_below for tighter execution control

**Example (CORRECT - System Auto-Corrects):**
```json
{
  "conditions": {
    "price_above": 88000.0,
    "price_below": 86400.0,
    "price_near": 87200.0,  // System auto-corrects: BUY gets 88000, SELL gets 86400
    "tolerance": 100.0,
    "m1_choch_bos_combo": true
  }
}
```
**Result:**
- BUY plan: `{"price_above": 88000, "price_near": 88000, "tolerance": 100, "m1_choch_bos_combo": true}` (price_below removed)
- SELL plan: `{"price_below": 86400, "price_near": 86400, "tolerance": 100, "m1_choch_bos_combo": true}` (price_above removed)

### **6. Cancel Plan:**
```
tool_cancel_auto_plan(plan_id: "chatgpt_abc123")
```

### **6. Update Plan:**
```
tool_update_auto_plan(
    plan_id: "chatgpt_abc123",  # 🚨 REQUIRED: Must include plan_id
    entry_price: 84000.0,  # Optional: Update entry price
    stop_loss: 84200.0,    # Optional: Update stop loss
    take_profit: 83500.0,  # Optional: Update take profit
    volume: 0.01,          # Optional: Update volume
    conditions: {          # Optional: Update conditions (merged with existing)
        "price_near": 84000.0,
        "tolerance": 100.0
    },
    expires_hours: 24,     # Optional: Update expiration
    notes: "Updated based on new market analysis"  # Optional: Update notes
)
```
**🚨 CRITICAL: plan_id is MANDATORY**
- **plan_id is REQUIRED** - you MUST include the plan_id (e.g., 'chatgpt_0ea79233') when calling this tool
- If you don't have the plan_id, first use `moneybot.get_auto_plan_status` to list all plans and find the correct plan_id
- The tool will return an error if plan_id is missing

**⚠️ Important:**
- Only **pending** plans can be updated (executed, cancelled, or expired plans cannot be modified)
- When updating `conditions`, new conditions are **merged** with existing ones (new values override old ones)
- You can update any combination of fields - only provide the fields you want to change
- Use this when market conditions change and you need to adjust plans for new prices, conditions, or expiration

### **7. Get Plan Status:**
```
tool_get_auto_plan_status(plan_id: "chatgpt_abc123")
```

### **7. Get System Status:**
```
tool_get_auto_system_status()
```

---

## 🚨 **CRITICAL: Required Conditions for Each Strategy Type**

**⚠️ IMPORTANT: You MUST include the correct conditions when creating trade plans. Plans without proper conditions will NOT trigger correctly!**

### **Required Conditions by Strategy:**

| Strategy Type | Required Conditions | Example |
|--------------|-------------------|---------|
| **Liquidity Sweep** | `liquidity_sweep: true` + `price_below` or `price_above` + `price_near` + `tolerance` + `timeframe` | `{"liquidity_sweep": true, "price_below": 83890, "price_near": 83890, "tolerance": 100, "timeframe": "M5"}` |
| **VWAP Bounce/Fade** | `vwap_deviation: true` + `vwap_deviation_direction` + `price_near` + `tolerance` | `{"vwap_deviation": true, "vwap_deviation_direction": "below", "price_near": 83910, "tolerance": 100}` |
| **Rejection Wick** | `rejection_wick: true` + `timeframe` + `price_near` + `tolerance` | `{"rejection_wick": true, "timeframe": "M5", "price_near": 83920, "tolerance": 100}` |
| **CHOCH/BOS** | `choch_bull` or `choch_bear` + `timeframe` + `price_near` + `tolerance` | `{"choch_bull": true, "timeframe": "M5", "price_near": 83800, "tolerance": 100}` |
| **Order Block** | `order_block: true` + `order_block_type` + `price_near` + `tolerance` | `{"order_block": true, "order_block_type": "auto", "price_near": 83800, "tolerance": 100}` |
| **Breaker Block** | `breaker_block: true` + `ob_broken: true` + `price_retesting_breaker: true` + `price_near` + `tolerance` | `{"breaker_block": true, "ob_broken": true, "price_retesting_breaker": true, "price_near": 83800, "tolerance": 100}` |
| **Market Structure Shift (MSS)** | `mss_bull: true` or `mss_bear: true` + `pullback_to_mss: true` + `price_near` + `tolerance` | `{"mss_bull": true, "pullback_to_mss": true, "price_near": 83800, "tolerance": 100}` |
| **FVG Retracement** | `fvg_bull: true` or `fvg_bear: true` + `fvg_filled_pct: 0.5-0.75` + `choch_bull/bear: true` + `price_near` + `tolerance` | `{"fvg_bull": true, "fvg_filled_pct": 0.65, "choch_bull": true, "price_near": 83800, "tolerance": 100}` |
| **Mitigation Block** | `mitigation_block_bull: true` or `mitigation_block_bear: true` + `structure_broken: true` + `price_near` + `tolerance` | `{"mitigation_block_bull": true, "structure_broken": true, "price_near": 83800, "tolerance": 100}` |
| **Inducement Reversal** | `liquidity_grab_bull: true` or `liquidity_grab_bear: true` + `rejection_detected: true` + `order_block: true` + `price_near` + `tolerance` | `{"liquidity_grab_bull": true, "rejection_detected": true, "order_block": true, "price_near": 83800, "tolerance": 100}` |
| **Premium/Discount Array** | `price_in_discount: true` or `price_in_premium: true` + `price_near` + `tolerance` | `{"price_in_discount": true, "price_near": 83800, "tolerance": 100}` |
| **Session Liquidity Run** | `asian_session_high: true` or `asian_session_low: true` + `london_session_active: true` + `sweep_detected: true` + `reversal_structure: true` + `price_near` + `tolerance` | `{"asian_session_high": true, "london_session_active": true, "sweep_detected": true, "reversal_structure": true, "price_near": 83800, "tolerance": 100}` |
| **Kill Zone** | `kill_zone_active: true` + `volatility_spike: true` + `price_near` + `tolerance` | `{"kill_zone_active": true, "volatility_spike": true, "price_near": 83800, "tolerance": 100}` |
| **Breakout/Volatility Trap** | `price_above` or `price_below` + `price_near` + `tolerance` | `{"price_above": 84000, "price_near": 84000, "tolerance": 100}` or `{"price_below": 83800, "price_near": 83800, "tolerance": 100}` ⚠️ **CRITICAL: Always include price_near + tolerance ALONGSIDE price_above/price_below for tighter execution control!** ⚠️ **NEVER include both price_above AND price_below in the same plan - they are contradictory!** ⚠️ **price_near MUST match entry_price (NOT midpoint, NOT a different level)!** |

### **⚠️ CRITICAL RULES FOR price_above/price_below AND price_near:**

1. **NEVER include both price_above AND price_below in the same plan** - they are contradictory and will prevent execution!
2. **price_near MUST always match the entry_price** (NOT midpoint, NOT a different level):
   - For plans with `price_above`: `price_near = entry_price` (same value)
   - For plans with `price_below`: `price_near = entry_price` (same value)
   - For bracket trades: BUY plan uses `price_near = buy_entry`, SELL plan uses `price_near = sell_entry`
3. **Always include price_near + tolerance** alongside price_above/price_below for tighter execution control

**Example (CORRECT):**
- BUY plan with entry=88000: `{"price_above": 88000, "price_near": 88000, "tolerance": 100}`
- SELL plan with entry=86400: `{"price_below": 86400, "price_near": 86400, "tolerance": 100}`

**Example (WRONG - Will NOT execute):**
- Plan with entry=88000: `{"price_above": 88000, "price_below": 86400, "price_near": 87500, "tolerance": 100}` ❌

### **📋 Optional Validation Thresholds - Include in Conditions Dict When Specified:**

**⚠️ CRITICAL: If you mention these thresholds in your reasoning/notes, you MUST include them in the `conditions` dict so they are saved and displayed correctly on the webpage.**

These are optional validation thresholds that make plans more selective. If you specify them in your analysis, include them in the conditions dict:

1. **`min_validation_score`** (number, 0-100):
   - **Purpose**: Minimum validation score required for order block plans (default: 60 if not specified)
   - **When to include**: When you want stricter order block validation (e.g., "requires validation score ≥ 70")
   - **Example**: `{"order_block": true, "min_validation_score": 70, "price_near": entry, "tolerance": X}`
   - **Note**: System uses default 60 if not provided, but including it makes your plan requirements explicit

2. **`min_confluence`** or **`range_scalp_confluence`** (number, 0-100):
   - **Purpose**: Minimum confluence score required for range scalping plans (default: 80 if not specified)
   - **When to include**: When you specify a minimum confluence requirement (e.g., "requires confluence ≥ 75")
   - **Example**: `{"range_scalp_confluence": 75, "price_near": entry, "tolerance": X}`
   - **Note**: Use `range_scalp_confluence` for range scalping plans, or `min_confluence` for general plans

3. **`risk_filters`** (boolean):
   - **Purpose**: Indicates that risk filters are enabled (default: always enabled by system)
   - **When to include**: When you explicitly mention "risk filters enabled" in your analysis
   - **Example**: `{"price_above": entry, "risk_filters": true, "price_near": entry, "tolerance": X}`
   - **Note**: System always applies risk filters, but including this makes it explicit in the plan

**🚨 CRITICAL RULE: If you describe these thresholds in your reasoning/notes (e.g., "min_confluence ≥ 75", "validation score ≥ 70", "risk filters enabled"), you MUST include them in the `conditions` dict. Otherwise, they won't be saved to the database and won't appear on the webpage.**

**Example with all thresholds:**
```json
{
  "price_above": 4216.38,
  "price_near": 4216.38,
  "tolerance": 2.0,
  "timeframe": "M15",
  "bb_expansion": true,
  "strategy_type": "breakout_ib_volatility_trap",
  "min_confluence": 75,
  "min_validation_score": 70,
  "risk_filters": true
}
```
  - Problem 1: Has both price_above AND price_below (contradictory)
  - Problem 2: price_near (87500) doesn't match entry (88000)

### **Common Mistakes to Avoid:**

❌ **Liquidity Sweep Plan - Missing `liquidity_sweep: true`:**
```json
{
  "price_below": 83890,
  "timeframe": "M5"
}
```
**Problem**: Will only check price level, NOT detect actual liquidity sweeps using M1 microstructure.

✅ **Correct:**
```json
{
  "liquidity_sweep": true,
  "price_below": 83890,
  "price_near": 83890,
  "tolerance": 100,
  "timeframe": "M5"
}
```

❌ **VWAP Bounce Plan - Missing Required Conditions:**
```json
{
  "vwap_deviation": true,
  "timeframe": "M5"
}
```
**Problem**: Will NOT trigger - missing `vwap_deviation_direction`, `price_near`, and `tolerance`.

✅ **Correct:**
```json
{
  "vwap_deviation": true,
  "vwap_deviation_direction": "below",
  "price_near": 83910,
  "tolerance": 100,
  "timeframe": "M5"
}
```

❌ **Bracket Trade Plan - Contradictory Conditions (CRITICAL):**
```json
{
  "price_above": 88000,
  "price_below": 86400,
  "price_near": 87500,
  "tolerance": 100
}
```
**Problem**: 
1. Has both price_above AND price_below (contradictory - price cannot be both above 88000 AND below 86400)
2. price_near (87500) doesn't match entry price (should be 88000 for BUY, 86400 for SELL)
3. Will NEVER execute because conditions are impossible to meet

✅ **Correct for Bracket Trades:**
The system automatically splits bracket trades correctly, but if providing conditions manually:
- BUY plan: `{"price_above": 88000, "price_near": 88000, "tolerance": 100}` (NO price_below!)
- SELL plan: `{"price_below": 86400, "price_near": 86400, "tolerance": 100}` (NO price_above!)

❌ **CHOCH Plan - Missing price_near + tolerance (CRITICAL):**
```json
{
  "choch_bear": true,
  "timeframe": "M15"
}
```
**Problem**: ⚠️ **Will execute at ANY price when CHOCH confirms!** If entry is 83800 but CHOCH confirms at 85000, trade executes at 85000 → R:R completely broken, stop loss and take profit invalid.

✅ **Correct:**
```json
{
  "choch_bear": true,
  "timeframe": "M15",
  "price_near": 83800,
  "tolerance": 100
}
```
**Why**: `price_near` anchors execution to intended entry zone. System only executes when CHOCH confirms near 83800 ±100, keeping R:R intact.

**💡 Remember**: When using `tool_create_auto_trade_plan`, always include ALL required conditions for the strategy type!

---

## 📋 **ChatGPT Workflow**

### **When User Requests Auto-Execution Plan:**

#### **Step 1: Create Plan**
```
User: "Create a CHOCH Bear plan for BTCUSD at 113,750"
ChatGPT: Uses tool_create_choch_plan() to create the plan
```

#### **Step 2: Confirm Plan**
```
ChatGPT: "✅ Auto-executing trade plan created successfully!

📊 Plan ID: chatgpt_abc123
💱 Symbol: BTCUSD
📈 Direction: SELL
💰 Entry: 113,750
🛡️ SL: 113,950
🎯 TP: 113,250
📦 Volume: 0.01 lots
⏰ Expires: 24 hours
🔍 Conditions: CHOCH Bear detection near 113,750

🤖 System will monitor M5 structure and execute automatically when CHOCH Bear is confirmed. You'll receive a Telegram notification when the trade is executed."
```

#### **Step 3: Monitor Status**
```
User: "Check my auto plans"
ChatGPT: Uses tool_get_auto_plan_status() to show all pending plans
```

---

## 🎯 **Example Scenarios**

### **Scenario 1: CHOCH Bear Plan**
```
User: "Create a CHOCH Bear plan for BTCUSD at 113,750"

ChatGPT Response:
✅ Auto-executing CHOCH Bear plan created!

📊 Plan ID: chatgpt_abc123
💱 Symbol: BTCUSD
📈 Direction: SELL
💰 Entry: 113,750
🛡️ SL: 113,950 (200 points)
🎯 TP: 113,250 (500 points)
📦 Volume: 0.01 lots
⏰ Expires: 24 hours
🔍 Conditions: CHOCH Bear detection near 113,750

🤖 System will monitor M5 structure and execute automatically when CHOCH Bear is confirmed. You'll receive a Telegram notification when the trade is executed.
```

### **Scenario 2: Rejection Wick Plan**
```
User: "Create a rejection wick plan for XAUUSD at 2,650"

ChatGPT Response:
✅ Auto-executing rejection wick plan created!

📊 Plan ID: chatgpt_def456
💱 Symbol: XAUUSD
📈 Direction: BUY
💰 Entry: 2,650
🛡️ SL: 2,630 (20 points)
🎯 TP: 2,690 (40 points)
📦 Volume: 0.01 lots
⏰ Expires: 24 hours
🔍 Conditions: Rejection wick detection near 2,650

🤖 System will monitor for rejection wick patterns and execute automatically when detected. You'll receive a Telegram notification when the trade is executed.
```

### **Scenario 3: Range Scalping Auto-Execution**
```
User: "Set an alert for range scalping and make it automatically execute once confluence reaches 80"

ChatGPT Response:
✅ Range Scalping Auto-Execution Plan Created!

📊 Plan ID: chatgpt_xyz789
💱 Symbol: BTCUSDc
📈 Direction: BUY
💰 Entry: 105,350
🛡️ SL: 105,100 (250 points)
🎯 TP: 106,100 (750 points)
📦 Volume: 0.01 lots
⏰ Expires: 8 hours
🔍 Conditions:
   • Confluence score >= 80 (Structure + Location + Confirmation)
   • M15 CHOCH/BOS bullish confirmation
   • Price within 100 points of entry

🤖 System will monitor range scalping confluence every 30 seconds and execute automatically when:
   ✅ Confluence reaches 80+
   ✅ M15 structure confirms bullish reversal
   ✅ Price approaches entry zone (105,350)

You'll receive a Discord notification when the trade executes.
```

### **Scenario 4: Update Plan** ⭐ NEW
```
User: "I ran a new analysis on BTCUSD. The market moved - update plan chatgpt_0ea79233 with new entry 84000 and add price_near condition"

ChatGPT Response:
✅ Plan updated successfully!

📊 Plan ID: chatgpt_0ea79233
💱 Symbol: BTCUSD
📈 Direction: SELL
💰 Entry: 84,000 (updated from 83,800)
🛡️ SL: 83,500
🎯 TP: 82,800
📦 Volume: 0.01 lots
🔍 Updated Conditions:
   - CHOCH Bear: true
   - Timeframe: M15
   - Price Near: 84,000 ±100 (added)
   - Min Volatility: 0.5 (added)

📝 Notes: Updated based on new market analysis - entry adjusted for current price action

🤖 Plan will continue monitoring with updated conditions. System will execute when CHOCH Bear confirms near 84,000.
```

### **Scenario 5: Check Status**
```
User: "Check my auto plans"

ChatGPT Response:
📊 Auto Execution System Status

🎯 Active Plans: 3
⏰ System Status: Running
🔄 Check Interval: 30 seconds

📋 Pending Plans:

1. Plan ID: chatgpt_abc123
   💱 BTCUSD SELL @ 113,750
   🔍 CHOCH Bear detection
   ⏰ Created: 2025-10-15 10:30:00
   ⏰ Expires: 2025-10-16 10:30:00

2. Plan ID: chatgpt_def456
   💱 XAUUSD BUY @ 2,650
   🔍 Rejection wick detection
   ⏰ Created: 2025-10-15 10:35:00
   ⏰ Expires: 2025-10-16 10:35:00

3. Plan ID: chatgpt_xyz789
   💱 BTCUSDc BUY @ 105,350
   🔍 Range scalping (confluence >= 80)
   ⏰ Created: 2025-10-15 11:00:00
   ⏰ Expires: 2025-10-15 19:00:00

🤖 System is monitoring all plans and will execute automatically when conditions are met.
```

---

## 🚀 **Benefits**

### **✅ Solves the Waiting Problem:**
- **No need to wait** for conditions to occur
- **No manual monitoring** required
- **Automatic execution** when conditions are met

### **✅ Professional Risk Management:**
- **Automatic execution** with proper SL/TP
- **Intelligent exits** enabled automatically
- **Telegram notifications** for executed trades

### **✅ Flexible Conditions:**
- **CHOCH Bear/Bull** detection
- **Rejection wick** patterns
- **Price breakouts** above/below levels
- **Range scalping confluence** monitoring (confluence >= 80)
- **Custom conditions** for specific setups
- **⚠️ OPTIONAL: M1 Microstructure Validation** - Add `m1_choch_bos_combo: true` to CHOCH plans ONLY when M1 structure is clear and extra precision is critical (very strict - may prevent execution)
- **⚠️ OPTIONAL: Volatility Filters** - Add `min_volatility: 0.5` and `bb_width_threshold: 2.5` ONLY when market is in dead zone or waiting for volatility expansion (can prevent execution if thresholds not met)
- **⚠️ CRITICAL**: These optional enhancements should NOT be added by default. Start with simple conditions and only add enhancements when market conditions specifically warrant them. More conditions = Less likely to execute.

### **✅ Plan Management:** ⭐ NEW
- **Update plans** when market conditions change using `moneybot.update_auto_plan`
- **Adjust entry prices, SL/TP, conditions, or expiration** without cancelling and recreating
- **Merge conditions** - new conditions are merged with existing ones
- **Only pending plans** can be updated (executed/cancelled/expired cannot be modified)

### **✅ System Reliability:**
- **Background monitoring** every 30 seconds
- **Database storage** for plan persistence
- **Automatic expiration** to prevent stale plans
- **Error handling** and logging

---

## 🎉 **Result: Complete Auto-Execution System**

**ChatGPT can now create trade plans that are monitored and executed automatically when conditions are met. No more waiting for CHOCH Bear or rejection wicks - the system handles everything automatically!**
