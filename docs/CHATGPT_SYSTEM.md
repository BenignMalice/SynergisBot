# ChatGPT Trading System

A standalone system that combines **Telegram Bot + ChatGPT + MT5 API** without the full `trade_bot.py` functionality.

---

## 🎯 What This Is

This is a **lightweight alternative** to the full trading bot that focuses on:
- ✅ ChatGPT conversations via Telegram
- ✅ Real-time MT5 data integration
- ✅ AI-powered trade recommendations
- ✅ Trade execution via API
- ✅ NO signal scanning, NO auto-trading

---

## 📦 Components

### 1. **chatgpt_bot.py**
- Telegram bot that handles ChatGPT conversations
- Connects to MT5 API for data and trading
- Lightweight, fast, focused on AI interactions

### 2. **app/main_api.py**
- FastAPI server exposing MT5 functionality
- Endpoints for price data, account info, trade execution
- AI analysis endpoints (ChatGPT, ML patterns, exit strategies)

### 3. **ngrok**
- Tunnels API to public internet
- Allows ChatGPT Actions to call your API

---

## 🚀 Quick Start

### 1. Configure Environment

Create/update `.env` file:
```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_BOT_CHAT_ID=your_chat_id

# OpenAI (optional - can set via /setgptkey)
OPENAI_API_KEY=your_openai_key

# MT5 (if needed by API)
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_server
```

### 2. Start System

**Windows:**
```bash
start_chatgpt_system.bat
```

**Manual Start:**
```bash
# Terminal 1: Start ngrok
ngrok http 8000 --config=ngrok.yml

# Terminal 2: Start API
python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Start ChatGPT bot
python chatgpt_bot.py
```

### 3. Use the Bot

Open Telegram and:
```
/start          → Welcome message
/chatgpt        → Start AI conversation
/setgptkey KEY  → Set OpenAI API key
/help           → Show help
```

---

## 💬 ChatGPT Commands

Once you start `/chatgpt`, you can:

### Quick Action Buttons:
- **📊 Market Analysis** - Analyze current XAUUSD market
- **💰 Check Balance** - Get MT5 account info
- **🎯 Trade Recommendation** - Get AI trade setup
- **📈 Suggest Trade** - Ask for good symbols
- **❌ End Chat** - Exit conversation

### Natural Language:
```
"Analyze XAUUSD for me"
"Give me a trade recommendation for BTCUSD"
"What's my account balance?"
"Should I buy or sell gold right now?"
"Give me entry, SL, and TP for XAUUSD"
```

---

## 🔌 API Endpoints Available

The ChatGPT bot can access:

### Market Data
- `GET /api/v1/price/{symbol}` - Current price
- `GET /market/analysis/{symbol}` - Market analysis

### AI Analysis
- `GET /ai/analysis/{symbol}` - ChatGPT-powered analysis
- `GET /ml/patterns/{symbol}` - ML pattern detection
- `GET /ai/exits/{symbol}` - Exit strategy recommendations

### Account & Trading
- `GET /api/v1/account` - Account balance/equity
- `POST /mt5/execute` - Execute market orders
- `POST /mt5/execute_bracket` - Execute OCO bracket orders

### Risk & Monitoring
- `GET /risk/metrics` - Current risk metrics
- `GET /health` - System health check

---

## 🆚 vs. Full trade_bot.py

| Feature | ChatGPT System | Full trade_bot.py |
|---------|---------------|------------------|
| ChatGPT Integration | ✅ | ✅ |
| MT5 Trading | ✅ | ✅ |
| AI Analysis | ✅ | ✅ |
| Signal Scanning | ❌ | ✅ |
| Auto-Trading | ❌ | ✅ |
| Chart Buttons | ❌ | ✅ |
| Position Monitoring | ❌ | ✅ |
| Circuit Breaker | ❌ | ✅ |
| Journal System | ❌ | ✅ |
| Menu System | ❌ | ✅ |

**Use this when:**
- You want **manual trading with AI assistance**
- You only need **ChatGPT recommendations**
- You want a **lighter, faster bot**
- You don't need signal scanning or auto-trading

**Use trade_bot.py when:**
- You want **full automated trading**
- You need **signal scanning and analysis**
- You want **complete trade management**
- You need all the advanced features

---

## 🛠️ Troubleshooting

### Bot doesn't respond
1. Check `chatgpt_bot.py` is running
2. Check `.env` has correct `TELEGRAM_TOKEN`
3. Check console for errors

### "OpenAI API key not configured"
1. Add to `.env`: `OPENAI_API_KEY=sk-...`
2. Or use: `/setgptkey sk-...` in Telegram

### "Services not initialized" from API
1. Check `app/main_api.py` is running
2. Check MT5 is running and logged in
3. Check API logs for errors

### ChatGPT gives generic numbers
1. Check API is accessible: `http://localhost:8000/health`
2. Check MT5 connection in API logs
3. Try restarting the system

---

## 📊 Example Workflow

1. **Start system:**
   ```bash
   start_chatgpt_system.bat
   ```

2. **Open Telegram:**
   ```
   /chatgpt
   ```

3. **Ask ChatGPT:**
   ```
   Give me a trade recommendation for XAUUSD with entry, SL, and TP
   ```

4. **ChatGPT responds:**
   ```
   📊 Fetching current market data...
   
   Based on current analysis:
   - Current Price: $3,863.82
   - Market Regime: RANGE
   - Recommendation: HOLD
   
   The market is range-bound. Wait for breakout...
   ```

5. **Continue conversation:**
   ```
   What about BTCUSD?
   ```

6. **End when done:**
   ```
   /endgpt
   ```

---

## 🔐 Security Notes

- ⚠️ Never share your `.env` file
- ⚠️ Keep your `TELEGRAM_TOKEN` secret
- ⚠️ Keep your `OPENAI_API_KEY` private
- ⚠️ Use ngrok auth token for production

---

## 📝 Logs

**ChatGPT Bot logs:**
- Shown in `chatgpt_bot.py` console window
- Shows Telegram messages and ChatGPT responses

**API logs:**
- Shown in `uvicorn` console window
- Shows MT5 connections and API calls

**ngrok logs:**
- Visit: `http://localhost:4040`
- Shows all incoming API requests

---

## 🚀 Next Steps

1. **Test the bot** - Ask it questions, see how it responds
2. **Monitor logs** - Watch API calls and responses
3. **Customize prompts** - Edit `handlers/chatgpt_bridge.py`
4. **Add more endpoints** - Extend `app/main_api.py`
5. **Connect to ChatGPT Actions** - Use `openai.yaml`

---

## 📞 Support

If you encounter issues:
1. Check console logs for errors
2. Verify MT5 is running and connected
3. Test API endpoints manually: `http://localhost:8000/docs`
4. Check ngrok dashboard: `http://localhost:4040`

---

**Enjoy your AI-powered trading assistant! 🤖📈**

