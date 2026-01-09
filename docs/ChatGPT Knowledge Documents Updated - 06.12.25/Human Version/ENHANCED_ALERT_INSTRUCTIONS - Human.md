# Enhanced Alert Instructions for ChatGPT

## 🚨 **ALERT HANDLING - ENHANCED LOGIC**

When user asks for alerts, use this enhanced logic to parse intent and map to correct parameters:

### **Step 1: Parse User Intent**
Extract from user request:
- **Symbol**: Look for BTC, XAU, Gold, EUR, GBP, etc. → Map to broker symbols with 'c' suffix
- **Price Level**: Extract numeric values (handle commas: 4,248 → 4248)
- **Condition**: "crosses above", "hits", "reaches" → "crosses_above"
- **Volatility**: "volatility high", "VIX > 20" → Add volatility conditions
- **Purpose**: "first partials", "entry", "exit" → Add purpose parameter

### **Step 2: Map to Correct Parameters**
```json
{
  "symbol": "XAUUSDc",  // Always use 'c' suffix for broker symbols
  "alert_type": "price",
  "condition": "crosses_above",
  "description": "XAUUSDc crosses above 4248.0 - high volatility (VIX > 20) - for first partials",
  "parameters": {
    "price_level": 4248.0,
    "volatility_condition": "high",  // If volatility mentioned
    "vix_threshold": 20.0,           // If VIX > 20 mentioned
    "purpose": "first_partials"      // If purpose mentioned
  },
  "expires_hours": 24,
  "one_time": true
}
```

### **Step 3: Call moneybot.add_alert**
Use the parsed parameters to call the tool immediately.

## 📋 **Examples**

### **Example 1: Complex Alert Request**
**User:** "set alert for monitor near 4,248 for first partials; volatility high (VIX > 20)"

**Parsed Parameters:**
```json
{
  "symbol": "XAUUSDc",
  "alert_type": "price", 
  "condition": "crosses_above",
  "description": "XAUUSDc crosses above 4248.0 - high volatility (VIX > 20) - for first partials",
  "parameters": {
    "price_level": 4248.0,
    "volatility_condition": "high",
    "vix_threshold": 20.0,
    "purpose": "first_partials"
  },
  "expires_hours": 24,
  "one_time": true
}
```

### **Example 2: Simple Price Alert**
**User:** "alert me when bitcoin hits 115000"

**Parsed Parameters:**
```json
{
  "symbol": "BTCUSDc",
  "alert_type": "price",
  "condition": "crosses_above", 
  "description": "BTCUSDc crosses above 115000.0",
  "parameters": {
    "price_level": 115000.0
  },
  "expires_hours": 24,
  "one_time": true
}
```

### **Example 3: Drop Below Alert**
**User:** "notify me if gold drops below 2600"

**Parsed Parameters:**
```json
{
  "symbol": "XAUUSDc",
  "alert_type": "price",
  "condition": "crosses_below",
  "description": "XAUUSDc crosses below 2600.0", 
  "parameters": {
    "price_level": 2600.0
  },
  "expires_hours": 24,
  "one_time": true
}
```

## ⭐ **NEW: Automatic Parameter Extraction**

The alert system now automatically extracts missing parameters from the `description` field for indicator alerts:

**If `parameters` is missing `indicator`, `timeframe`, or `value`:**
- The system uses regex to extract them from the `description`
- Example: `"M15 RSI crosses above 60"` → automatically extracts `indicator="rsi"`, `timeframe="M15"`, `value=60`

**This means ChatGPT can:**
1. **Rely on description parsing** - If the description is clear, parameters can be omitted
2. **Include additional context** - Add reasoning, recommended actions, or notes to the description - they'll be included in Discord notifications
3. **Use user-friendly condition display** - The success message shows "RSI greater than 60 on M15" instead of just "greater_than"

**Example:**
```json
{
  "symbol": "BTCUSDc",
  "alert_type": "indicator",
  "condition": "greater_than",
  "description": "M15 RSI crosses above 60 — potential momentum fade. Watch for short squeeze or reduced downside pressure. Consider tightening stops or taking partial profit.",
  // Parameters can be omitted - system extracts indicator/timeframe/value automatically!
  "expires_hours": 24,
  "one_time": true
}
```

**Discord Notification:** When the alert triggers, users receive the **full description text** (including any reasoning, recommendations, or notes you added).

---

## 🔧 **Symbol Mapping**
- BTC/Bitcoin → BTCUSDc
- XAU/Gold → XAUUSDc  
- ETH/Ethereum → ETHUSDc
- EUR/Euro → EURUSDc
- GBP/Pound → GBPUSDc
- JPY/Yen → USDJPYc

## 🎯 **Key Rules**
1. **Always use 'c' suffix** for broker symbols
2. **Handle comma-separated numbers** (4,248 → 4248)
3. **Detect volatility conditions** (VIX > 20, high volatility)
4. **Extract purpose** (first partials, entry, exit)
5. **Call tool immediately** - don't ask for confirmation
6. **Use proper parameters** - not trade parameters
7. **⭐ Include rich descriptions** - Any text in `description` will be included in Discord notifications (e.g., reasoning, recommendations, notes)
8. **⭐ Automatic extraction** - For indicator alerts, you can rely on description parsing if parameters are clear

## ✅ **Success Criteria**
- Alert created successfully with correct parameters
- User receives confirmation with alert details (including user-friendly condition display)
- Alert monitors the specified conditions
- Volatility and purpose conditions are included when mentioned
- **⭐ Full description text** (including reasoning, recommendations, notes) is included in Discord notifications when alert triggers
- **⭐ Automatic parameter extraction** works correctly for indicator alerts when description is clear
