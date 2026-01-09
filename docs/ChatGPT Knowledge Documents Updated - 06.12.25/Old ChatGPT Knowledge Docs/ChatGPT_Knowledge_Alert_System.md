# Custom Alert System - Quick Guide for ChatGPT

## 🚨 When User Asks for Alerts

**User says:** "Alert me when Bitcoin hits 115000" or "Set an alert for BOS Bull" or "set alert when xauusd reaches 4085"

**Your response:** Just call the tool IMMEDIATELY. Don't ask 5+ confirmation questions.

---

## ⚠️ CRITICAL: ALERTS vs TRADES

**ALERTS ARE NOT TRADES!**

When user says "set alert" or "alert me when", use **moneybot.add_alert** with:
- ✅ `alert_type`, `condition`, `description`, `parameters` (with `price_level`)
- ❌ **NEVER** use `direction`, `entry`, `stop_loss`, `take_profit`, `volume`, `ticket`, `action` for alerts!

**WRONG (Trade Parameters):**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "XAUUSD",
    "direction": "SELL",  // ❌ WRONG - this is for trades!
    "entry": 4085,        // ❌ WRONG - use parameters.price_level instead!
    "stop_loss": 4100,    // ❌ WRONG - alerts don't have SL/TP!
    "volume": 0           // ❌ WRONG - alerts don't have volume!
  }
}
```

**CORRECT (Alert Parameters):**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "XAUUSDc",
    "alert_type": "price",
    "condition": "crosses_above",
    "description": "XAUUSDc crosses above 4085",
    "parameters": {
      "price_level": 4085
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

---

## ✅ How to Create Alerts (One-Step Process)

### **Step 1: User Requests Alert**
User: "set alert when xauusd reaches 4085"

### **Step 2: Parse & Call Tool Immediately**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "XAUUSDc",
    "alert_type": "price",
    "condition": "crosses_above",
    "description": "XAUUSDc crosses above 4085",
    "parameters": {
      "price_level": 4085
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

### **Step 3: Confirm Success**
"✅ Alert created: You'll be notified when XAUUSDc reaches 4085"

**That's it!** No 10-message back-and-forth needed.

---

## 📋 Alert Types & Parameters

### **1. Price Alerts**

**Use when:** User wants to be notified at a specific price level

```json
{
  "alert_type": "price",
  "condition": "greater_than",  // or "less_than"
  "parameters": {
    "price_level": 115000
  }
}
```

**Examples:**
- "Alert me when BTCUSD hits 115000" → `symbol: "BTCUSDc", alert_type: "price", condition: "crosses_above", description: "BTCUSDc crosses above 115000", parameters: {price_level: 115000}`
- "set alert when xauusd reaches 4085" → `symbol: "XAUUSDc", alert_type: "price", condition: "crosses_above", description: "XAUUSDc crosses above 4085", parameters: {price_level: 4085}`
- "Alert me if XAUUSD drops below 2600" → `symbol: "XAUUSDc", alert_type: "price", condition: "crosses_below", description: "XAUUSDc drops below 2600", parameters: {price_level: 2600}`
- "Notify me when EURUSD reaches 1.0850" → `symbol: "EURUSDc", alert_type: "price", condition: "crosses_above", description: "EURUSDc crosses above 1.0850", parameters: {price_level: 1.0850}`

**⚠️ REMEMBER:** Always use broker symbol with 'c' suffix (XAUUSDc, BTCUSDc, EURUSDc) and NEVER use trade parameters!

---

### **2. Structure Alerts (CHOCH, BOS, Order Blocks)**

**Use when:** User wants to be notified of structural changes

**Available Patterns:**
- `bos_bull` - Bullish Break of Structure
- `bos_bear` - Bearish Break of Structure
- `choch_bull` - Bullish Change of Character
- `choch_bear` - Bearish Change of Character
- `ob_bull` - Bullish Order Block (M1-M5 validated) ⭐ NEW
- `ob_bear` - Bearish Order Block (M1-M5 validated) ⭐ NEW
- `order_block` - Order Block (auto-detect direction) ⭐ NEW

```json
{
  "alert_type": "structure",
  "condition": "detected",
  "parameters": {
    "pattern": "bos_bull",  // or "bos_bear", "choch_bull", "choch_bear", "ob_bull", "ob_bear", "order_block"
    "timeframe": "M15"  // or "M5", "M30", "H1", "H4" (for BOS/CHOCH only; Order Blocks use M1-M5 automatically)
  }
}
```

**Examples:**
- "Alert me when BOS Bull appears on M15" → `condition: "detected", pattern: "bos_bull", timeframe: "M15"`
- "Notify me if CHOCH detected on H1" → `condition: "detected", pattern: "choch_bull", timeframe: "H1"`
- "Tell me when trend breaks (bearish)" → `condition: "detected", pattern: "choch_bear", timeframe: "M15"`
- "Alert me when order block forms" → `condition: "detected", pattern: "order_block"` ⭐ NEW
- "Notify me of bullish order blocks" → `condition: "detected", pattern: "ob_bull"` ⭐ NEW

**⭐ Order Block Detection (NEW - November 2025):**

Order Block alerts use comprehensive 10-parameter validation:
1. **Correct Candle Identification** - Last down/up candle before displacement
2. **Displacement/Structure Shift** - BOS/CHOCH confirmation (mandatory)
3. **Imbalance/FVG Presence** - Fair Value Gap detection
4. **Volume Spike** - 1.2x+ average volume confirmation
5. **Liquidity Grab** - Sweep detection (optional but strong)
6. **Session Context** - London/NY/Overlap preferred
7. **Higher-Timeframe Alignment** - M5 trend alignment
8. **Structural Context** - Avoids choppy ranges
9. **Order Block Freshness** - Prevents duplicate alerts
10. **VWAP + Liquidity Confluence** - Zone validation

**Order Block Alert Requirements:**
- Minimum validation score: 60/100
- M1-M5 cross-timeframe validation
- Session-aware ATR filters
- Volume/imbalance confirmation
- VWAP + liquidity confluence checks

**Note:** Order Block alerts automatically use M1-M5 analysis and do not require a timeframe parameter.

---

### **3. Indicator Alerts (RSI, MACD, etc.)**

**Use when:** User wants indicator-based notifications

**⭐ NEW: Automatic Parameter Extraction**
If `parameters` is missing `indicator`, `timeframe`, or `value`, the system automatically extracts them from the `description` field. This makes alert creation much simpler!

```json
{
  "alert_type": "indicator",
  "condition": "greater_than",  // or "less_than", "crosses_above", "crosses_below"
  "description": "M15 RSI crosses above 60",  // System will extract: indicator="rsi", timeframe="M15", value=60
  "parameters": {
    "indicator": "rsi",  // Optional - auto-extracted if missing
    "timeframe": "M15",  // Optional - auto-extracted if missing
    "value": 60          // Optional - auto-extracted if missing
  }
}
```

**Examples:**
- "Alert me when RSI goes below 30 on M15" → 
  ```json
  {
    "alert_type": "indicator",
    "condition": "less_than",
    "description": "M15 RSI crosses below 30",
    "parameters": {"indicator": "rsi", "timeframe": "M15", "value": 30}
  }
  ```
- "Notify me when M15 RSI crosses above 60" → 
  ```json
  {
    "alert_type": "indicator",
    "condition": "greater_than",
    "description": "M15 RSI crosses above 60",
    // Parameters can be omitted - system extracts from description!
  }
  ```
- "Alert when H1 MACD crosses bullish" → 
  ```json
  {
    "alert_type": "indicator",
    "condition": "crosses_above",
    "description": "H1 MACD crosses above signal line"
  }
  ```

**⚠️ Note:** The system displays the condition in a user-friendly format (e.g., "RSI greater than 60 on M15" instead of just "greater_than") in the success message.

---

### **4. Volatility Alerts**

**Use when:** User wants to be notified of volatility changes

```json
{
  "alert_type": "volatility",
  "condition": "detected",
  "parameters": {
    "pattern": "expansion",  // or "contraction"
    "timeframe": "M15"
  }
}
```

---

## 🎯 Complete Examples (Copy These!)

### Example 1: Simple Price Alert
```
User: "Alert me when BTCUSD reaches 115000"

ChatGPT Action:
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "price",
    "condition": "greater_than",
    "description": "BTCUSD reached $115,000",
    "parameters": {"price_level": 115000},
    "expires_hours": 48,
    "one_time": true
  }
}

ChatGPT Response:
"✅ Alert created! You'll be notified when BTCUSD reaches $115,000.
The alert will expire in 48 hours and trigger only once."
```

### Example 2: Structure Alert
```
User: "Alert me when BOS Bull appears on M15"

ChatGPT Action:
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull detected on M15 timeframe",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}

ChatGPT Response:
"✅ Alert created! You'll be notified when a bullish Break of Structure (BOS) is detected on the M15 timeframe."
```

### Example 3: Indicator Alert with Automatic Extraction
```
User: "Alert me when M15 RSI crosses above 60"

ChatGPT Action:
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSDc",
    "alert_type": "indicator",
    "condition": "greater_than",
    "description": "M15 RSI crosses above 60 — potential momentum fade for BTCUSD short positions. Watch for signs of short squeeze or reduced downside pressure. Consider tightening stops or taking partial profit.",
    "parameters": {
      "indicator": "rsi",
      "timeframe": "M15",
      "value": 60
    },
    "expires_hours": 24,
    "one_time": true
  }
}

ChatGPT Response:
"✅ Alert Added
📊 Symbol: BTCUSDc
🔔 Alert: M15 RSI crosses above 60 — potential momentum fade...
📝 Type: indicator
⚙️ Condition: RSI greater than 60 on M15  ← User-friendly format!
🆔 Alert ID: BTCUSDc_indicator_1762000429

You'll receive a Discord notification when this condition is met.
🔔 This is a ONE-TIME alert - it will be automatically removed after triggering.
⏰ Expires in 24 hours"
```

**⭐ Note:** ChatGPT can include additional context in the `description` (e.g., reasoning, recommended actions), and the full description will be included in the Discord notification when the alert triggers.

### Example 4: Multiple Alerts
```
User: "Alert me when price hits 115000 OR when BOS Bull appears"

ChatGPT Action: Call moneybot.add_alert TWICE (one for each condition)

Alert 1:
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSDc",
    "alert_type": "price",
    "condition": "crosses_above",
    "description": "BTCUSDc crosses above 115000",
    "parameters": {"price_level": 115000},
    "expires_hours": 48,
    "one_time": true
  }
}

Alert 2:
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSDc",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull detected on M15",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}

ChatGPT Response:
"✅ Two alerts created:
1. Price alert: BTCUSDc ≥ $115,000
2. Structure alert: BOS Bull on M15

You'll be notified when either condition triggers."
```

---

## 🚫 What NOT to Do

### ❌ DON'T Ask Too Many Questions
**Bad:**
```
User: "Alert me when BTCUSD hits 115000"
ChatGPT: "What alert type? What condition? What description? Please confirm..."
```

**Good:**
```
User: "Alert me when BTCUSD hits 115000"
ChatGPT: *calls moneybot.add_alert immediately*
"✅ Alert created!"
```

### ❌ DON'T Require JSON from User
**Bad:**
```
ChatGPT: "Please provide the alert in this JSON format: {...}"
```

**Good:**
```
ChatGPT: *infers the structure from natural language and calls the tool*
```

### ❌ DON'T Ask Platform Type
**Bad:**
```
ChatGPT: "Which platform are you using? MT5, Binance, or TradingView?"
```

**Good:**
```
ChatGPT: *the system automatically uses MT5, no need to ask*
```

---

## 📊 Alert Conditions Reference

### Price Conditions:
- `greater_than` - Alert when price goes above level
- `less_than` - Alert when price goes below level
- `crosses` - Alert when price crosses level (either direction)

### Structure Conditions:
- `bos_bull` - Bullish Break of Structure
- `bos_bear` - Bearish Break of Structure
- `choch_bull` - Bullish Change of Character
- `choch_bear` - Bearish Change of Character

### Indicator Conditions:
- Use `condition: "detected"` with `parameters: {"pattern": "rsi_oversold", "timeframe": "M15", "threshold": 30}`
- Use `condition: "detected"` with `parameters: {"pattern": "rsi_overbought", "timeframe": "M15", "threshold": 70}`
- Use `condition: "detected"` with `parameters: {"pattern": "macd_cross_bull", "timeframe": "M15"}`
- Use `condition: "detected"` with `parameters: {"pattern": "macd_cross_bear", "timeframe": "M15"}`

### Volatility Conditions:
- Use `condition: "detected"` with `parameters: {"pattern": "expansion", "timeframe": "M15"}`
- Use `condition: "detected"` with `parameters: {"pattern": "contraction", "timeframe": "M15"}`

---

## ⏰ Default Settings

**If user doesn't specify:**
- `expires_hours`: 48 (alert expires after 48 hours)
- `one_time`: true (alert triggers only once, then deletes)
- `timeframe`: "M15" (for structure/indicator alerts)

**User can override:**
- "Set a recurring alert..." → `one_time: false`
- "Alert expires in 24 hours" → `expires_hours: 24`
- "Alert on H1 timeframe" → `parameters: {"timeframe": "H1"}`

---

## 🎯 Decision Tree

```
User requests alert
  ↓
Is it a price level? (e.g., "when BTC hits 115000")
  YES → alert_type: "price", condition: "greater_than"/"less_than"
  NO → Continue
  ↓
Is it a structure? (e.g., "when BOS appears")
  YES → alert_type: "structure", condition: "bos_bull"/"choch_bull"
  NO → Continue
  ↓
Is it an indicator? (e.g., "when RSI oversold")
  YES → alert_type: "indicator", condition: "rsi_oversold"
  NO → Continue
  ↓
Is it volatility? (e.g., "when volatility expands")
  YES → alert_type: "volatility", condition: "expansion"
  NO → Ask user to clarify
```

---

## ✅ Success Criteria

### Good Alert Creation (1-2 messages):
```
User: "Alert me when BTCUSD hits 115000"
ChatGPT: *calls tool* "✅ Alert created!"
```

### Bad Alert Creation (10+ messages):
```
User: "Alert me when BTCUSD hits 115000"
ChatGPT: "What type?"
User: "Price"
ChatGPT: "What condition?"
User: "Greater than"
ChatGPT: "Please confirm..."
User: "Yes"
ChatGPT: "What description?"
... (5 more messages)
ChatGPT: "Finally created!"
```

---

## 🔑 Key Principles

1. **Infer from Natural Language:** User says "alert me when X" → You determine alert_type, condition, and parameters
2. **Call Tool Immediately:** Don't ask for confirmations unless genuinely ambiguous
3. **One Alert = One Tool Call:** Don't overthink it
4. **Multiple Conditions = Multiple Alerts:** Call moneybot.add_alert twice for "X OR Y" scenarios
5. **Confirm Success:** After tool call, give a simple "✅ Alert created" message

---

## 📝 Quick Reference Card

| User Says | alert_type | condition | parameters |
|-----------|------------|-----------|------------|
| "Alert me when BTCUSD hits 115000" | price | crosses_above | {price_level: 115000} |
| "Alert when XAUUSD drops below 2600" | price | crosses_below | {price_level: 2600} |
| "Alert on BOS Bull M15" | structure | detected | {pattern: "bos_bull", timeframe: "M15"} |
| "Alert on CHOCH Bear" | structure | detected | {pattern: "choch_bear", timeframe: "M15"} |
| "Alert when order block forms" | structure | detected | {pattern: "order_block"} ⭐ NEW |
| "Alert on bullish order block" | structure | detected | {pattern: "ob_bull"} ⭐ NEW |
| "Alert on bearish order block" | structure | detected | {pattern: "ob_bear"} ⭐ NEW |
| "Alert when M15 RSI crosses above 60" | indicator | greater_than | {indicator: "rsi", timeframe: "M15", value: 60} ⭐ |
| "Alert when volatility expands" | volatility | detected | {pattern: "expansion", timeframe: "M15"} |

**⭐ Order Block Patterns (NEW):**
- `ob_bull` - Bullish Order Block (M1-M5 validated, 10-parameter checklist)
- `ob_bear` - Bearish Order Block (M1-M5 validated, 10-parameter checklist)
- `order_block` - Auto-detect direction (M1-M5 validated)

**⭐ For indicator alerts:** The system automatically extracts `indicator`, `timeframe`, and `value` from the `description` if parameters are missing. Example: `"M15 RSI crosses above 60"` → extracts all three automatically!

---

**Remember:** The system is designed to be SIMPLE. User asks → You call tool → Done. No 10-question interrogation needed!

