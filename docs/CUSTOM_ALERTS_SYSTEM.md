# 🔔 Custom Alerts System - Complete Guide

## Overview

The Custom Alerts System allows ChatGPT to configure alerts for specific market conditions that will be monitored 24/7 by the Discord bot and trigger Discord notifications when conditions are met.

## ✅ What's Been Fixed

### 1. **OpenAPI Security Scheme**
- **Problem**: Custom GPT only supports one security scheme, but we had two (`ApiKeyAuth` and `PhoneTokenAuth`)
- **Fix**: Unified to single `BearerAuth` scheme for all endpoints
- **Location**: `openai.yaml`

### 2. **New Alert Management Tools**
Three new tools added to `desktop_agent.py` for Custom GPT:
- `moneybot.add_alert` - Configure new alerts
- `moneybot.list_alerts` - View active alerts
- `moneybot.remove_alert` - Remove alerts

### 3. **Background Alert Monitoring**
- New `AlertMonitor` class checks alerts every 60 seconds
- Integrated into `chatgpt_bot.py` background tasks
- Sends Discord notifications when alerts trigger

---

## 🎯 Supported Alert Types

### 1. **Structure Alerts** (`alert_type: "structure"`)
Detect Smart Money Concepts patterns:
- **BOS Bull** - Bullish Break of Structure
- **BOS Bear** - Bearish Break of Structure
- **CHOCH Bull** - Bullish Change of Character
- **CHOCH Bear** - Bearish Change of Character

**Example:**
```json
{
  "symbol": "BTCUSD",
  "alert_type": "structure",
  "condition": "detected",
  "description": "BOS Bull on BTCUSD M5",
  "parameters": {
    "pattern": "bos_bull",
    "timeframe": "M5"
  }
}
```

### 2. **Price Alerts** (`alert_type: "price"`)
Monitor price levels:
- `crosses_above` - Price crosses above a level
- `crosses_below` - Price crosses below a level
- `greater_than` - Price is above a level
- `less_than` - Price is below a level

**Example:**
```json
{
  "symbol": "XAUUSD",
  "alert_type": "price",
  "condition": "crosses_above",
  "description": "XAUUSD crosses above 4100",
  "parameters": {
    "price_level": 4100
  }
}
```

### 3. **Indicator Alerts** (`alert_type: "indicator"`)
Monitor technical indicators:
- Supported: RSI, MACD, ADX, ATR, EMA20, EMA50, etc.
- Conditions: `greater_than`, `less_than`, `equals`

**Example:**
```json
{
  "symbol": "BTCUSD",
  "alert_type": "indicator",
  "condition": "greater_than",
  "description": "BTCUSD RSI > 70 on H1",
  "parameters": {
    "indicator": "rsi",
    "value": 70,
    "timeframe": "H1"
  }
}
```

### 4. **Order Flow Alerts** (`alert_type: "order_flow"`)
Detect institutional activity:
- Whale orders
- Liquidity voids
- Order book imbalance

*(Implementation requires Binance integration)*

### 5. **Volatility Alerts** (`alert_type: "volatility"`)
Monitor volatility metrics:
- ATR thresholds
- ADX changes
- VIX levels

**Example:**
```json
{
  "symbol": "XAUUSD",
  "alert_type": "volatility",
  "condition": "greater_than",
  "description": "XAUUSD volatility spike",
  "parameters": {
    "metric": "atr",
    "threshold": 15.0,
    "timeframe": "M15"
  }
}
```

---

## 📱 How It Works

### **From Custom GPT's Perspective:**

1. **User asks ChatGPT**: "Set an alert when BOS Bull triggers on BTCUSD"

2. **ChatGPT calls**:
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull on BTCUSD M5",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M5"
    }
  }
}
```

3. **System responds**:
```
✅ Alert Added

📊 Symbol: BTCUSD
🔔 Alert: BOS Bull on BTCUSD M5
📝 Type: structure
⚙️ Condition: detected
🆔 Alert ID: BTCUSD_structure_1729000000

You'll receive a Discord notification when this condition is met.
```

4. **Background monitoring**:
   - `chatgpt_bot.py` checks alerts every 60 seconds
   - When BOS Bull is detected, Discord notification is sent:
   
```
🏗️ Alert Triggered!

🎯 **BOS Bull on BTCUSD M5**
📊 Symbol: BTCUSD
⏰ Triggered: #1

🏗️ Pattern: BOS Bull
⏱️ Timeframe: M5
💵 Current Price: $60,250.00
```

### **From Discord Bot's Perspective:**

The bot runs a background task (`check_custom_alerts`) every 60 seconds:

1. Fetch all active alerts from `data/custom_alerts.json`
2. For each alert:
   - Get current MT5 data
   - Check if condition is met
   - If triggered, send notification
   - Mark alert as triggered with timestamp

---

## 🛠️ Technical Implementation

### **Files Created/Modified:**

#### **New Files:**
1. `infra/custom_alerts.py` - Alert data models and storage
2. `infra/alert_monitor.py` - Alert checking logic
3. `CUSTOM_ALERTS_SYSTEM.md` - This documentation

#### **Modified Files:**
1. `desktop_agent.py`:
   - Added `CustomAlertManager` import
   - Added 3 new tools: `add_alert`, `list_alerts`, `remove_alert`
   
2. `openai.yaml`:
   - Unified security to single `BearerAuth` scheme
   - Added new alert tools to enum
   - Added examples for alert management

3. `chatgpt_bot.py`:
   - Added `CustomAlertManager` and `AlertMonitor` imports
   - Added `check_custom_alerts()` background task
   - Initialized alert monitor in main()
   - Added scheduler job for alert monitoring

### **Storage:**
Alerts are stored in `data/custom_alerts.json`:
```json
{
  "BTCUSD_structure_1729000000": {
    "alert_id": "BTCUSD_structure_1729000000",
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull on BTCUSD M5",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M5"
    },
    "created_at": "2025-10-14T10:30:00",
    "expires_at": null,
    "enabled": true,
    "triggered_count": 0,
    "last_triggered": null
  }
}
```

---

## 🎬 Usage Examples

### **Example 1: BOS Bull Alert**
**User**: "Let me know when BOS Bull triggers on BTCUSD"

**ChatGPT**: Calls `moneybot.add_alert` with structure parameters

**Result**: Discord notification sent when pattern detected

---

### **Example 2: Price Cross Alert**
**User**: "Alert me when Gold crosses 4100"

**ChatGPT**: 
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "XAUUSD",
    "alert_type": "price",
    "condition": "crosses_above",
    "description": "XAUUSD crosses above 4100",
    "parameters": {"price_level": 4100}
  }
}
```

---

### **Example 3: RSI Overbought Alert**
**User**: "Notify me when EURUSD RSI goes above 70"

**ChatGPT**:
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "EURUSD",
    "alert_type": "indicator",
    "condition": "greater_than",
    "description": "EURUSD RSI > 70",
    "parameters": {
      "indicator": "rsi",
      "value": 70,
      "timeframe": "H1"
    }
  }
}
```

---

### **Example 4: List All Alerts**
**User**: "Show my active alerts"

**ChatGPT**: Calls `moneybot.list_alerts`

**Response**:
```
🔔 Active Alerts (3)

✅ BTCUSD: BOS Bull on BTCUSD M5
   ID: BTCUSD_structure_1729000000
   Triggers: 0

✅ XAUUSD: XAUUSD crosses above 4100
   ID: XAUUSD_price_1729000100
   Triggers: 2

✅ EURUSD: EURUSD RSI > 70
   ID: EURUSD_indicator_1729000200
   Triggers: 1
```

---

### **Example 5: Remove Alert**
**User**: "Remove the BTCUSD BOS alert"

**ChatGPT**: 
```json
{
  "tool": "moneybot.remove_alert",
  "arguments": {
    "alert_id": "BTCUSD_structure_1729000000"
  }
}
```

---

## ⚙️ Configuration

### **Alert Expiry:**
Alerts can have an optional expiry:
```json
{
  "expires_hours": 24
}
```
Expired alerts are automatically cleaned up.

### **Alert Monitoring Frequency:**
Default: Every 60 seconds
*(Can be adjusted in `chatgpt_bot.py` scheduler)*

### **Supported Symbols:**
Any symbol in your MT5 (with 'c' suffix internally):
- BTCUSD → BTCUSDc
- XAUUSD → XAUUSDc
- EURUSD → EURUSDc
- etc.

---

## 🔧 Deployment Steps

### **1. Update Custom GPT:**
1. Open Custom GPT configuration
2. Go to Actions → Edit Schema
3. Replace `openai.yaml` content
4. Ensure authentication uses **Bearer Token** (phone token)
5. Save and test

### **2. Restart Services:**
```bash
# Restart desktop agent
python desktop_agent.py

# Restart Discord bot
python chatgpt_bot.py
```

### **3. Verify:**
1. Ask ChatGPT: "Add an alert for XAUUSD when it crosses 4100"
2. Check `data/custom_alerts.json` - alert should be saved
3. Wait for condition to trigger
4. Verify Discord notification received

---

## 🐛 Troubleshooting

### **Alert not triggering:**
- Check `data/custom_alerts.json` - is alert enabled?
- Check bot logs: `data/logs/chatgpt_bot.log`
- Verify symbol format (e.g., "BTCUSD" not "BTCUSDc")
- Check if MT5 data is available for that symbol

### **"Multiple security schemes" error:**
- Update `openai.yaml` with unified `BearerAuth`
- Remove old `ApiKeyAuth` and `PhoneTokenAuth` references
- Update Custom GPT to use Bearer authentication

### **Alert tool not found:**
- Verify `openai.yaml` includes alert tools in enum
- Check desktop agent logs - tools should be registered
- Restart desktop agent

---

## 🎯 Next Steps

1. ✅ **Test the system**:
   - Add a simple price alert
   - Wait for trigger
   - Verify notification

2. ✅ **ChatGPT instructions**:
   - Update ChatGPT instructions to mention alert capability
   - Add example prompts

3. ✅ **User documentation**:
   - Inform user about new feature
   - Provide usage examples

---

## 📊 Summary

**What changed:**
- ✅ Fixed OpenAPI security (unified to BearerAuth)
- ✅ Added 3 alert management tools
- ✅ Created alert storage system
- ✅ Implemented background monitoring
- ✅ Integrated Discord notifications

**What you can now do:**
When ChatGPT asks "Would you like me to set an alert for [condition]?", saying YES will:
1. Configure a custom alert via `moneybot.add_alert`
2. Store it in `data/custom_alerts.json`
3. Monitor it 24/7 via `chatgpt_bot.py`
4. Send Discord notification when triggered

**No more manual monitoring required!** 🎉

