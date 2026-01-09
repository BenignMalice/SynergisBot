# 🔔 Custom GPT Alert Update - Quick Reference

## Problem Solved

**Before**: When ChatGPT said "Would you like me to set an alert for BOS Bull on BTCUSD?", it couldn't actually do anything. It was just conversational.

**Now**: ChatGPT can **actually configure alerts** that the Telegram bot will monitor 24/7 and send you notifications when triggered!

---

## Step 1: Update `openai.yaml`

✅ **Already done!** The file has been updated with:
- Unified `BearerAuth` security scheme
- Three new alert management tools
- Complete examples

---

## Step 2: Update Custom GPT Configuration

### **A. Replace Schema:**

1. Go to your Custom GPT
2. Click **Configure** → **Actions** → **Edit Schema**
3. **Copy the entire contents** of `openai.yaml`
4. **Paste** into Custom GPT schema editor
5. Click **Save**

### **B. Update Authentication:**

**IMPORTANT**: Your authentication method has changed!

**Old**: `ApiKeyAuth` (header X-API-Key)
**New**: `BearerAuth` (Bearer token)

1. In Custom GPT Actions settings
2. Find **Authentication** section
3. Select **Bearer**
4. Paste your **phone token** (from `.env` file):
   ```
   Look for: PHONE_TOKEN=your_token_here
   ```
5. Save

---

## Step 3: (Optional) Add to ChatGPT Instructions

Add this section to your Custom GPT instructions:

```
### Alert System

You can now configure alerts for market conditions:

1. **Structure Alerts**: BOS Bull/Bear, CHOCH Bull/Bear
   - Use `moneybot.add_alert` with `alert_type: "structure"`
   - Example: "Alert me when BOS Bull triggers on BTCUSD M5"

2. **Price Alerts**: Price crosses levels
   - Use `moneybot.add_alert` with `alert_type: "price"`
   - Example: "Alert me when XAUUSD crosses 4100"

3. **Indicator Alerts**: RSI, MACD, ADX thresholds
   - Use `moneybot.add_alert` with `alert_type: "indicator"`
   - Example: "Alert me when RSI > 70 on EURUSD H1"

When user requests an alert:
1. Call `moneybot.add_alert` with appropriate parameters
2. Confirm alert is configured
3. Explain they'll receive Telegram notification when triggered

To list alerts: `moneybot.list_alerts`
To remove: `moneybot.remove_alert` with alert_id
```

---

## Step 4: Restart Services

```bash
# Terminal 1: Desktop Agent (Phone Control)
cd C:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py

# Terminal 2: Telegram Bot (Background Monitoring)
cd C:\mt5-gpt\TelegramMoneyBot.v7
python chatgpt_bot.py
```

**Wait for log messages:**
- Desktop Agent: `✅ Connected to hub`
- Telegram Bot: `✅ Custom Alert System initialized`

---

## Step 5: Test

### **Test 1: Add Price Alert**

**In Custom GPT, say**:
```
Alert me when XAUUSD crosses 4100
```

**Expected**:
- ChatGPT calls `moneybot.add_alert`
- You receive confirmation with alert ID
- Check `data/custom_alerts.json` - alert should be saved

### **Test 2: List Alerts**

**Say**:
```
Show my active alerts
```

**Expected**:
- ChatGPT calls `moneybot.list_alerts`
- You see your XAUUSD alert listed

### **Test 3: Wait for Trigger**

- When XAUUSD price crosses 4100...
- You'll receive a Telegram notification! 🔔

### **Test 4: Remove Alert**

**Say**:
```
Remove the XAUUSD alert
```

**Expected**:
- ChatGPT calls `moneybot.remove_alert`
- Alert is removed from system

---

## Common Issues

### **"Multiple security schemes" Error**
**Fix**: Make sure you updated `openai.yaml` to use only `BearerAuth` (already done)

### **"Tool not found" Error**
**Fix**: 
1. Restart `desktop_agent.py`
2. Check logs for `✅ Tool registered: moneybot.add_alert`

### **Alerts not triggering**
**Fix**:
1. Check `chatgpt_bot.py` is running
2. Look for `✅ Custom Alert System initialized` in logs
3. Check `data/custom_alerts.json` - is alert there?

### **"No connection" Error**
**Fix**:
1. Ensure ngrok is running
2. Check Custom GPT authentication uses correct token
3. Verify `desktop_agent.py` shows `✅ Connected to hub`

---

## File Locations

| File | Purpose |
|------|---------|
| `openai.yaml` | OpenAPI schema for Custom GPT |
| `desktop_agent.py` | Phone Control handler (runs on laptop) |
| `chatgpt_bot.py` | Telegram bot with background monitoring |
| `infra/custom_alerts.py` | Alert storage system |
| `infra/alert_monitor.py` | Alert checking logic |
| `data/custom_alerts.json` | Active alerts database |
| `data/logs/chatgpt_bot.log` | Bot logs |
| `desktop_agent.log` | Desktop agent logs |

---

## Quick Command Reference

### **Add Alert**
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

### **List Alerts**
```json
{
  "tool": "moneybot.list_alerts",
  "arguments": {}
}
```

### **Remove Alert**
```json
{
  "tool": "moneybot.remove_alert",
  "arguments": {
    "alert_id": "BTCUSD_structure_1729000000"
  }
}
```

---

## What Happens Behind the Scenes

1. **User asks ChatGPT** to set an alert
2. **ChatGPT calls** `moneybot.add_alert` via ngrok
3. **Desktop Agent** receives command, saves to `data/custom_alerts.json`
4. **Telegram Bot** (running 24/7) checks alerts every 60 seconds
5. **When condition met** → Telegram notification sent! 🔔

---

## Success Criteria

✅ Custom GPT schema updated
✅ Authentication changed to Bearer
✅ Both services running
✅ Custom Alert System initialized
✅ Test alert added successfully
✅ Alert visible in list
✅ (Eventually) Notification received when triggered

---

## Next: Tell the User!

Once everything is working, you can use alerts like:

```
"Set an alert when BOS Bull triggers on BTCUSD"
"Alert me when Gold crosses 4100"
"Notify me if EURUSD RSI goes above 70"
"Show my active alerts"
"Remove all BTCUSD alerts"
```

**The system now actually does what it says!** 🎉

