# ChatGPT API Setup Guide

This guide explains how to set up the FastAPI server so ChatGPT (or other services) can place trades directly to your MT5 account.

---

## 🎯 What This Does

- Exposes your bot as an HTTP API that ChatGPT can call
- Allows ChatGPT to execute trades on your MT5 account
- Uses ngrok to create a secure public URL
- Provides real-time account information and trade execution

---

## 📋 Prerequisites

1. **Install required packages:**
```bash
pip install fastapi uvicorn pydantic
```

2. **Ensure your MT5 is running and logged in**

3. **Have your ngrok account set up** (already configured in `ngrok.yml`)

---

## 🚀 Quick Start

### Option 1: Start Everything at Once (Recommended)

1. **Double-click `start_with_ngrok.bat`**
   - This will start both the API server and ngrok tunnel
   - Two command windows will open

2. **Wait for both to initialize** (about 5-10 seconds)

3. **Your API is now available at:**
   - **Public URL:** https://verbally-faithful-monster.ngrok-free.app
   - **Local URL:** http://localhost:8000
   - **API Docs:** http://localhost:8000/docs

### Option 2: Manual Start

1. **Start the API server:**
```bash
python -m uvicorn app.main_api:app --reload --host 0.0.0.0 --port 8000
```

2. **In a separate terminal, start ngrok:**
```bash
ngrok http --url=verbally-faithful-monster.ngrok-free.app 8000
```

---

## 🔧 Configure ChatGPT

### Method 1: Using ChatGPT Actions (GPTs)

1. Go to https://chat.openai.com/gpts/editor
2. Create a new GPT or edit an existing one
3. Go to "Configure" → "Actions"
4. Click "Create new action"
5. Import the schema from `openapi_spec.json` file
6. Or paste this URL in the Schema field:
```
https://verbally-faithful-monster.ngrok-free.app/openapi.json
```

### Method 2: Using Custom Instructions

Add this to your ChatGPT custom instructions or system prompt:

```
You have access to a trading API at https://verbally-faithful-monster.ngrok-free.app

Available endpoints:
- POST /api/v1/trade/execute - Execute a trade
- GET /api/v1/account - Get account info
- GET /api/v1/symbols - List available symbols
- GET /health - Check system health

When executing trades:
1. Always check the current price first
2. Set stop loss below entry for BUY (above for SELL)
3. Set take profit above entry for BUY (below for SELL)
4. Use 0.01 lot size (maximum allowed)
5. Symbols must end with 'c' (BTCUSDc, XAUUSDc, etc.)

Example trade execution:
{
  "symbol": "BTCUSDc",
  "action": "BUY",
  "entry": 60000.0,
  "stop_loss": 59500.0,
  "take_profit": 61000.0,
  "lot_size": 0.01,
  "comment": "GPT recommendation"
}
```

---

## 📡 API Endpoints

### 1. Execute Trade
```http
POST /api/v1/trade/execute
Content-Type: application/json

{
  "symbol": "BTCUSDc",
  "action": "BUY",
  "entry": 60000.0,      // Optional - market price if not specified
  "stop_loss": 59500.0,
  "take_profit": 61000.0,
  "lot_size": 0.01,
  "comment": "GPT trade"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Trade executed: BUY BTCUSDc",
  "ticket": 123456,
  "position": 123456,
  "entry_price": 60000.0
}
```

### 2. Get Account Information
```http
GET /api/v1/account
```

**Response:**
```json
{
  "login": 12345678,
  "balance": 10000.0,
  "equity": 10050.0,
  "profit": 50.0,
  "margin": 200.0,
  "free_margin": 9800.0,
  "currency": "USD"
}
```

### 3. List Available Symbols
```http
GET /api/v1/symbols
```

**Response:**
```json
{
  "symbols": [
    {
      "symbol": "BTCUSDc",
      "description": "Bitcoin vs US Dollar",
      "bid": 60000.0,
      "ask": 60005.0,
      "digits": 2
    }
  ]
}
```

### 4. Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "mt5_connected": true,
  "account": 12345678,
  "balance": 10000.0
}
```

---

## 🧪 Testing the API

### 1. Test with Browser
Open in your browser:
```
http://localhost:8000/docs
```

This opens the interactive Swagger UI where you can test all endpoints.

### 2. Test with curl
```bash
# Health check
curl http://localhost:8000/health

# Get account info
curl http://localhost:8000/api/v1/account

# Execute a trade
curl -X POST http://localhost:8000/api/v1/trade/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDc",
    "action": "BUY",
    "stop_loss": 59500.0,
    "take_profit": 61000.0,
    "lot_size": 0.01
  }'
```

### 3. Test with ChatGPT
Once configured, you can ask ChatGPT:

```
"Check my MT5 account balance"
"Execute a BUY trade on BTCUSDc with stop loss at 59500 and take profit at 61000"
"What symbols are available for trading?"
```

---

## 🛡️ Security Notes

1. **ngrok URL Security:**
   - Your ngrok URL is semi-permanent but can be changed in `ngrok.yml`
   - Only share with trusted services
   - ngrok free tier has some rate limits

2. **API Security (Production):**
   - Consider adding authentication (API keys, OAuth)
   - Implement rate limiting
   - Add IP whitelisting if needed
   - Use HTTPS only (ngrok provides this automatically)

3. **Risk Management:**
   - The API enforces max lot size of 0.01 (configurable in code)
   - All trades must have SL and TP
   - Invalid price levels are rejected
   - Circuit breaker from main bot still applies

---

## 🐛 Troubleshooting

### Error: "MT5 service not initialized"
**Solution:** Make sure MT5 is running and logged in before starting the API server.

### Error: "Connection refused"
**Solution:** Check that the API server is running on port 8000:
```bash
netstat -ano | findstr :8000
```

### Error: "Tool call was not successful"
**Possible causes:**
1. ngrok tunnel is not running
2. API server is not running
3. MT5 is not connected
4. Invalid symbol or trade parameters

**Solution:**
- Check both API server and ngrok are running
- Visit http://localhost:8000/health to verify status
- Check the API server logs in the command window

### ngrok URL changed
**Solution:** Update the `openapi_spec.json` file and re-import to ChatGPT:
1. Get your new ngrok URL from the ngrok terminal
2. Update the "servers" section in `openapi_spec.json`
3. Re-import the schema in ChatGPT Actions

---

## 📊 Monitoring

### View API Logs
The API server logs all requests and trade executions to the console. Watch for:
- `[INFO] Executing trade: BUY BTCUSDc @ MARKET`
- `[INFO] Trade executed successfully: ticket=123456`
- `[ERROR] Trade execution failed: ...`

### View MT5 Logs
All trades are also logged to:
- `data/journal.sqlite` (trade journal)
- MT5 terminal (trade history)

---

## 🔄 Stopping the Server

1. Close both command windows (API server and ngrok)
2. Or press `Ctrl+C` in each terminal

---

## 💡 Advanced Usage

### Custom ngrok URL
To use your own custom ngrok domain:
1. Upgrade to ngrok paid plan
2. Update `ngrok.yml`:
```yaml
tunnels:
  fastapi:
    proto: http
    addr: 8000
    domain: your-custom-domain.ngrok.app
```

### Add Authentication
Edit `app/main_api.py` to add API key authentication:
```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "your-secret-key":
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.post("/api/v1/trade/execute", dependencies=[Depends(verify_api_key)])
async def execute_trade(trade: TradeRequest):
    # ... existing code ...
```

### Run as Windows Service
Use `nssm` (Non-Sucking Service Manager) to run the API as a Windows service:
```bash
nssm install TelegramBotAPI "C:\path\to\python.exe" "-m uvicorn app.main_api:app --host 0.0.0.0 --port 8000"
nssm start TelegramBotAPI
```

---

## 📞 Support

If you encounter issues:
1. Check the API logs in the command window
2. Visit http://localhost:8000/docs to test endpoints manually
3. Check MT5 connection with `/health` endpoint
4. Review the error messages in the API response

---

## 🎉 You're All Set!

Your bot can now accept trade requests from ChatGPT or any HTTP client. The API provides a secure, reliable way to execute trades programmatically while maintaining all the safety features of your existing bot.

Happy trading! 🚀

