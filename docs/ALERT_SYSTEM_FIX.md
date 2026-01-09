# ALERT SYSTEM FIX

## 🚨 **Issue Identified**

The alert command is failing because the system is sending **trade-related parameters** instead of **alert parameters** to the `moneybot.add_alert` tool.

### ❌ **What's Being Sent (Incorrect)**
```json
{
  "symbol": "XAUUSD",
  "direction": "BUY", 
  "entry": 4248,
  "stop_loss": 0,
  "take_profit": 0,
  "volume": 0,
  "ticket": 126604845,
  "action": "enable"
}
```

### ✅ **What Should Be Sent (Correct)**
```json
{
  "symbol": "XAUUSD",
  "alert_type": "price",
  "condition": "crosses_above", 
  "description": "XAUUSD crosses above 4248 for first partials - high volatility (VIX > 20)",
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

## 🔧 **Required Parameters for moneybot.add_alert**

The `moneybot.add_alert` tool requires these specific parameters:

### **Required Parameters:**
- `symbol` - Trading symbol (e.g., "XAUUSD")
- `alert_type` - Type of alert ("price", "structure", "indicator", "order_flow", "volatility")
- `condition` - Condition type ("detected", "crosses_above", "crosses_below", "greater_than", "less_than")
- `description` - Human-readable description

### **Optional Parameters:**
- `parameters` - Dict of alert-specific parameters
- `expires_hours` - Optional expiry in hours
- `one_time` - Auto-remove after first trigger (default: True)

## 🎯 **Correct Alert Command for XAUUSD**

```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "XAUUSD",
    "alert_type": "price",
    "condition": "crosses_above",
    "description": "XAUUSD crosses above 4248 for first partials - high volatility (VIX > 20)",
    "parameters": {
      "price_level": 4248.0,
      "volatility_condition": "high",
      "vix_threshold": 20.0,
      "purpose": "first_partials"
    },
    "expires_hours": 24,
    "one_time": true
  }
}
```

## 📋 **Alert Types Available**

### 1. **Price Alerts**
- `alert_type`: "price"
- `condition`: "crosses_above", "crosses_below", "greater_than", "less_than"
- `parameters`: `{"price_level": 4248.0}`

### 2. **Structure Alerts (CHOCH, BOS)**
- `alert_type`: "structure"
- `condition`: "detected"
- `parameters`: `{"pattern": "bos_bull", "timeframe": "M15"}`

### 3. **Indicator Alerts**
- `alert_type`: "indicator"
- `condition`: "greater_than", "less_than"
- `parameters`: `{"indicator": "rsi", "value": 70, "timeframe": "H1"}`

### 4. **Volatility Alerts**
- `alert_type`: "volatility"
- `condition`: "greater_than", "less_than"
- `parameters`: `{"vix_threshold": 20.0}`

## 🚀 **Solution**

The system needs to be updated to:

1. **Parse user intent correctly** - When user asks for "alert for monitor near 4,248", it should create a price alert, not a trade command
2. **Map to correct parameters** - Convert user request to proper alert parameters
3. **Handle volatility conditions** - Include VIX > 20 condition in the alert logic

## ✅ **Expected Result**

With the correct parameters, the alert should be created successfully and will:

- Monitor XAUUSD price crossing above 4,248
- Only trigger when VIX > 20 (high volatility)
- Alert for first partials opportunity
- Expire in 24 hours
- Be a one-time alert (removed after triggering)

The user will receive a Telegram notification when XAUUSD crosses above 4,248 during high volatility conditions.
