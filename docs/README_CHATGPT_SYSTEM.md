# 🤖 ChatGPT Trading System

A lightweight Telegram bot that provides AI-powered trading assistance using ChatGPT and MT5 integration.

---

## 🎯 Overview

This is a **standalone system** that combines:
- 🤖 **ChatGPT** - AI trading assistant
- 💬 **Telegram** - User interface
- 📊 **MT5 API** - Real-time market data and trading

Unlike the full `trade_bot.py`, this system focuses on **manual trading with AI recommendations**.

---

## ⚡ Quick Start

### 1. Configure `.env`
```bash
TELEGRAM_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key  # Optional
```

### 2. Start System
```bash
start_chatgpt_system.bat
```

### 3. Open Telegram
```
/chatgpt
```

That's it! 🎉

---

## 💬 Example Usage

```
You: Give me a trade recommendation for XAUUSD

Bot: 📊 Fetching current market data...

     Based on current market analysis for XAUUSD:
     
     💰 Current Price: $3,863.82
     📊 Market Regime: RANGE
     📈 RSI: 50.0
     
     Recommendation: HOLD
     
     The market is currently range-bound with no
     clear trend. I recommend waiting for a breakout
     before entering a position.
     
     Key levels to watch:
     • Resistance: $3,880
     • Support: $3,850
```

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/chatgpt` | Start AI conversation |
| `/endgpt` | End conversation |
| `/setgptkey <key>` | Set OpenAI API key |
| `/help` | Show help |

---

## 🎯 Quick Actions

When you start `/chatgpt`, you get buttons for:
- 📊 **Market Analysis** - Analyze XAUUSD
- 💰 **Check Balance** - Get account info
- 🎯 **Trade Recommendation** - Get trade setup
- 📈 **Suggest Trade** - Find good symbols
- ❌ **End Chat** - Exit conversation

---

## 🚀 What It Can Do

✅ **Real-time Analysis**
- Fetch live MT5 prices
- Calculate technical indicators
- Detect market regimes

✅ **AI Recommendations**
- Trade setups with entry/SL/TP
- Market insights
- Risk analysis

✅ **Natural Conversations**
- Ask in plain English
- Context-aware responses
- Follow-up questions

✅ **Trade Execution**
- Execute trades via API
- OCO bracket orders
- Account monitoring

---

## 🔧 System Components

### Running Processes
1. **ngrok** - Tunnel (background)
2. **FastAPI** - API server (port 8000)
3. **chatgpt_bot.py** - Telegram bot

### Key Files
- `chatgpt_bot.py` - Main bot
- `handlers/chatgpt_bridge.py` - ChatGPT logic
- `app/main_api.py` - API server
- `start_chatgpt_system.bat` - Startup script

---

## 📖 Documentation

- **Quick Start:** `QUICK_START.md`
- **Full Guide:** `CHATGPT_SYSTEM.md`
- **Comparison:** `SYSTEM_COMPARISON.md`
- **Architecture:** `ARCHITECTURE.md`
- **Summary:** `CHATGPT_SYSTEM_COMPLETE.md`

---

## 🆚 vs Full Bot

| Feature | This System | Full Bot |
|---------|------------|----------|
| ChatGPT | ✅ | ✅ |
| Manual Trading | ✅ | ✅ |
| Auto-Trading | ❌ | ✅ |
| Signal Scanning | ❌ | ✅ |
| Position Monitoring | ❌ | ✅ |
| Trade Journal | ❌ | ✅ |
| **Complexity** | Simple | Complex |
| **Best For** | Manual + AI | Automated |

---

## 🛠️ Troubleshooting

### Bot Not Responding
```bash
# Check .env has TELEGRAM_TOKEN
# Restart system
stop_chatgpt_system.bat
start_chatgpt_system.bat
```

### No Market Data
```bash
# Check MT5 is running
# Check API: http://localhost:8000/health
# Check API console for errors
```

### Generic Responses
```bash
# Set OpenAI key:
/setgptkey sk-your-key-here
# Or add to .env
```

---

## 🔐 Security

⚠️ **Keep Secret:**
- `TELEGRAM_TOKEN`
- `OPENAI_API_KEY`
- `.env` file

⚠️ **Local Only:**
- API runs on `localhost:8000`
- Use ngrok for external access
- Add authentication for production

---

## 📊 API Endpoints

The bot uses these MT5 API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/api/v1/price/{symbol}` | Get current price |
| `/ai/analysis/{symbol}` | ChatGPT analysis |
| `/api/v1/account` | Account balance |
| `/mt5/execute` | Execute trade |
| `/health` | Health check |

Test API: `http://localhost:8000/docs`

---

## 💡 Tips

### Get Better Responses
- Be specific: "Give me entry, SL, TP for XAUUSD"
- Ask follow-ups: "Why HOLD?"
- Request details: "Show me the indicators"

### Use Quick Actions
- Click buttons instead of typing
- Faster and more consistent
- Pre-defined prompts

### Check Real Data
- Look for "📊 Fetching current market data..."
- Verify prices are current
- Check API logs if suspicious

---

## 🎓 Example Sessions

### Session 1: Market Analysis
```
/chatgpt
→ Click "📊 Market Analysis"
→ Get comprehensive XAUUSD breakdown
/endgpt
```

### Session 2: Trade Recommendation
```
/chatgpt
"Give me a trade setup for BTCUSD with risk:reward 1:3"
→ Get entry, SL, TP with reasoning
"Execute this trade"
→ Trade executed via API
/endgpt
```

### Session 3: Account Check
```
/chatgpt
→ Click "💰 Check Balance"
→ Get balance, equity, margin
"Can I afford 0.1 lots on XAUUSD?"
→ Risk calculation
/endgpt
```

---

## 🚀 Next Steps

1. ✅ **Test it** - Start the system and chat
2. ✅ **Read docs** - Understand capabilities
3. ✅ **Experiment** - Try different queries
4. ✅ **Customize** - Edit handlers if needed
5. ✅ **Trade** - Use for real trading decisions

---

## 📞 Support

### Check Logs
- **Bot:** `chatgpt_bot.py` console
- **API:** `uvicorn` console
- **ngrok:** `http://localhost:4040`

### Test API
```bash
# Health check
http://localhost:8000/health

# API docs
http://localhost:8000/docs

# Test endpoint
curl http://localhost:8000/api/v1/price/XAUUSD
```

---

## 🎉 Ready to Use!

Start your AI trading assistant now:

```bash
start_chatgpt_system.bat
```

Open Telegram and begin chatting! 🤖

---

**Built with:**
- Python 3.11+
- python-telegram-bot
- OpenAI GPT-4o-mini
- FastAPI
- MetaTrader 5

**License:** MIT
**Author:** Your Name
**Version:** 1.0.0

---

**Happy Trading! 📈💰**

