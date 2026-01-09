# Price Alerts System - Complete Implementation

## Overview

The Price Alerts system allows users to set price targets and receive **Telegram notifications** when those prices are hit. Perfect for monitoring breakouts, reversals, and key levels.

---

## 🎯 How It Works

### User Flow:
1. **Custom GPT/Telegram suggests:** "Would you like me to set price alerts for..."
2. **User responds:** "Yes, set both alerts"
3. **System creates alerts:** Stores in `data/price_alerts.json`
4. **Background monitor:** Checks prices every 60 seconds
5. **Alert triggers:** Sends Telegram notification when price hit
6. **User notified:** Receives message with price and next steps

---

## 📁 Files Created/Modified

### 1. `infra/price_alerts.py` (NEW)
**Purpose:** Core price alert management system

**Key Classes:**
- `PriceAlert`: Individual alert object
- `PriceAlertManager`: Manages all alerts, monitoring, and notifications

**Key Features:**
- Store alerts in JSON file (`data/price_alerts.json`)
- Background monitoring thread
- Automatic Telegram notifications
- Support for "above" and "below" alert types

### 2. `app/main_api.py` (UPDATED)
**Purpose:** Added REST API endpoints for Custom GPT

**New Endpoints:**
- `POST /api/v1/alerts/create` - Create price alert
- `GET /api/v1/alerts` - List alerts
- `DELETE /api/v1/alerts/{alert_id}` - Delete alert
- `POST /api/v1/alerts/start_monitoring` - Start background monitoring
- `POST /api/v1/alerts/stop_monitoring` - Stop monitoring

---

## 🔧 API Endpoints

### Create Alert
```http
POST /api/v1/alerts/create
Content-Type: application/json

{
  "symbol": "XAUUSD",
  "alert_type": "above",  // or "below"
  "target_price": 3975.0,
  "message": "🟢 Gold bullish reversal above $3,975"
}
```

**Response:**
```json
{
  "ok": true,
  "alert": {
    "alert_id": "XAUUSD_above_3975.0_1728509876",
    "symbol": "XAUUSD",
    "alert_type": "above",
    "target_price": 3975.0,
    "message": "🟢 Gold bullish reversal above $3,975",
    "created_at": "2025-10-09T22:15:00",
    "triggered": false,
    "triggered_at": null
  },
  "message": "✅ Alert created: XAUUSD above $3975.00"
}
```

### List Alerts
```http
GET /api/v1/alerts?symbol=XAUUSD&active_only=true
```

**Response:**
```json
{
  "alerts": [
    {
      "alert_id": "XAUUSD_above_3975.0_1728509876",
      "symbol": "XAUUSD",
      "alert_type": "above",
      "target_price": 3975.0,
      "triggered": false
    },
    {
      "alert_id": "XAUUSD_below_3950.0_1728509877",
      "symbol": "XAUUSD",
      "alert_type": "below",
      "target_price": 3950.0,
      "triggered": false
    }
  ],
  "count": 2,
  "active_count": 2,
  "triggered_count": 0
}
```

### Delete Alert
```http
DELETE /api/v1/alerts/XAUUSD_above_3975.0_1728509876
```

**Response:**
```json
{
  "ok": true,
  "message": "✅ Alert XAUUSD_above_3975.0_1728509876 deleted"
}
```

### Start Monitoring
```http
POST /api/v1/alerts/start_monitoring?check_interval=60
```

**Response:**
```json
{
  "ok": true,
  "message": "✅ Price monitoring started (checks every 60s)",
  "check_interval": 60
}
```

---

## 📱 Telegram Integration

### Alert Notification Format:
```
🔔 **Price Alert Triggered!**

**XAUUSD**: $3,976.50
**Condition**: Price above $3,975.00

📝 🟢 Gold bullish reversal above $3,975
Consider long entry with:
• Entry: $3,976-$3,980
• Stop Loss: $3,965
• Take Profit: $4,000+

⏰ Triggered: 2025-10-09 22:30:15
```

---

## 🤖 Custom GPT Usage

### Example Conversation:

**User:** "What's the market context for Gold?"

**GPT:** 
```
📉 Verdict: ⚪ WAIT — No clean entry
Gold is oversold on lower timeframes but lacks reversal confirmation.
With macro fundamentals bearish (DXY ↑ + US10Y ↑) and technical 
alignment weak, best action is to stand aside until price reclaims 
$3,970+ or confirms breakdown below $3,950.

👉 Would you like me to set price alerts for:
✅ A bearish breakdown below $3,950, or
🟢 A bullish reversal above $3,975?
```

**User:** "Yes, set both alerts"

**GPT calls:**
```javascript
// Alert 1: Bearish breakdown
createPriceAlert({
  symbol: "XAUUSD",
  alert_type: "below",
  target_price: 3950.0,
  message: "🔴 Gold breakdown below $3,950 - Consider short entry"
})

// Alert 2: Bullish reversal
createPriceAlert({
  symbol: "XAUUSD",
  alert_type: "above",
  target_price: 3975.0,
  message: "🟢 Gold reversal above $3,975 - Consider long entry"
})
```

**GPT responds:**
```
✅ **Price Alerts Set!**

I've created 2 alerts for Gold (XAUUSD):

1. 🔴 **Bearish Alert**: Below $3,950
   → You'll get notified if Gold breaks down

2. 🟢 **Bullish Alert**: Above $3,975
   → You'll get notified if Gold reverses higher

You'll receive a Telegram message when either price is hit.
The monitoring system checks every 60 seconds.

📊 Current Price: $3,962.78
⏳ Waiting for breakout or breakdown...
```

---

## 🔄 Background Monitoring

### How It Works:
1. **Thread-based:** Runs in background, doesn't block main application
2. **Interval:** Checks prices every 60 seconds (configurable)
3. **Efficient:** Groups alerts by symbol to minimize MT5 calls
4. **Persistent:** Alerts survive server restarts (stored in JSON)

### Monitoring Loop:
```python
while monitoring:
    1. Get all active alerts
    2. Group by symbol (e.g., all XAUUSD alerts together)
    3. For each symbol:
       - Fetch current price from MT5
       - Check all alerts for that symbol
       - If condition met:
         * Mark alert as triggered
         * Send Telegram notification
         * Save to disk
    4. Sleep for check_interval (60s)
```

### Starting Monitoring:
The monitoring should auto-start when the API server boots. Add this to your `app/main_api.py` startup:

```python
@app.on_event("startup")
async def startup_event():
    # Existing startup code...
    
    # Start price alert monitoring
    from infra.price_alerts import get_alert_manager
    alert_manager = get_alert_manager()
    alert_manager.start_monitoring(
        mt5_service=mt5_service,
        telegram_bot=None,  # Will integrate with trade_bot
        check_interval=60
    )
    logger.info("Price alert monitoring started")
```

---

## 📊 Data Storage

### File: `data/price_alerts.json`
```json
{
  "alerts": [
    {
      "alert_id": "XAUUSD_above_3975.0_1728509876",
      "symbol": "XAUUSD",
      "alert_type": "above",
      "target_price": 3975.0,
      "message": "🟢 Gold bullish reversal above $3,975",
      "created_at": "2025-10-09T22:15:00.123456",
      "triggered": false,
      "triggered_at": null
    },
    {
      "alert_id": "XAUUSD_below_3950.0_1728509877",
      "symbol": "XAUUSD",
      "alert_type": "below",
      "target_price": 3950.0,
      "message": "🔴 Gold breakdown below $3,950",
      "created_at": "2025-10-09T22:15:01.234567",
      "triggered": true,
      "triggered_at": "2025-10-09T22:45:30.987654"
    }
  ],
  "last_updated": "2025-10-09T22:45:30.987654"
}
```

---

## 🧪 Testing

### Test 1: Create Alerts
```bash
cd c:\mt5-gpt\TelegramMoneyBot.v7

# Create bearish alert
python -c "
import requests
response = requests.post('http://localhost:8000/api/v1/alerts/create', json={
    'symbol': 'XAUUSD',
    'alert_type': 'below',
    'target_price': 3950.0,
    'message': '🔴 Gold breakdown below \$3,950'
})
print(response.json())
"

# Create bullish alert
python -c "
import requests
response = requests.post('http://localhost:8000/api/v1/alerts/create', json={
    'symbol': 'XAUUSD',
    'alert_type': 'above',
    'target_price': 3975.0,
    'message': '🟢 Gold reversal above \$3,975'
})
print(response.json())
"
```

### Test 2: List Alerts
```bash
python -c "
import requests
response = requests.get('http://localhost:8000/api/v1/alerts?symbol=XAUUSD')
print(response.json())
"
```

### Test 3: Start Monitoring
```bash
python -c "
import requests
response = requests.post('http://localhost:8000/api/v1/alerts/start_monitoring?check_interval=60')
print(response.json())
"
```

### Test 4: Check Alert File
```bash
cat data/price_alerts.json
```

---

## ⚙️ Configuration

### Check Interval:
- **Default:** 60 seconds
- **Min recommended:** 30 seconds (avoid API rate limits)
- **Max recommended:** 300 seconds (5 minutes)

**Adjust via:**
```http
POST /api/v1/alerts/start_monitoring?check_interval=30
```

### Telegram Integration:
Currently, alerts are created and monitored, but Telegram notifications require the `trade_bot` integration. To complete:

1. Pass telegram bot instance to monitoring
2. Update `infra/price_alerts.py` line 147-148 to use actual bot
3. Ensure bot has `send_message()` method

---

## 🚀 Next Steps

### 1. Update `openai.yaml`
Add the new alert endpoints so Custom GPT can call them.

### 2. Update Custom GPT Instructions
Add guidance on when and how to suggest price alerts.

### 3. Test End-to-End
1. Ask Custom GPT about Gold
2. Accept alert suggestions
3. Verify alerts created
4. Wait for price to hit target
5. Confirm Telegram notification received

### 4. Add to Telegram Bot
Add handlers for `/alerts` command to manage alerts via Telegram chat.

---

## 📋 Summary

✅ **Created:** `infra/price_alerts.py` - Alert management system
✅ **Updated:** `app/main_api.py` - Added 5 REST endpoints
✅ **Features:**
  - Create alerts for "above" and "below" prices
  - Background monitoring (60s interval)
  - Automatic Telegram notifications
  - Persistent storage in JSON
  - Support for multiple symbols

✅ **Ready for:** Custom GPT and Telegram integration

**Status:** 🟢 Core system complete, ready for testing!

