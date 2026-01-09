# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Choose Your System

**Option A: ChatGPT System** (Recommended for beginners)
- Simple, lightweight
- ChatGPT + Telegram + MT5 API
- Manual trading with AI advice

**Option B: Full Bot**
- Complex, feature-rich
- Everything Option A has + auto-trading
- Advanced features

### Step 2: Start the System

**Option A:**
```bash
start_chatgpt_system.bat
```

**Option B:**
```bash
start_with_ngrok.bat
# Or
python trade_bot.py
```

### Step 3: Open Telegram

```
/start
/chatgpt
```

That's it! Start chatting with your AI trading assistant.

---

## 📖 Full Documentation

- **ChatGPT System:** See `CHATGPT_SYSTEM.md`
- **Full Bot:** See `README.md` or `Starting Synergis.txt`
- **Comparison:** See `SYSTEM_COMPARISON.md`
- **API Integration:** See `openai.yaml`

---

## 🆘 Need Help?

### "Bot doesn't respond"
- Check console for errors
- Verify `.env` has `TELEGRAM_TOKEN`
- Restart the system

### "OpenAI API key not configured"
- Add to `.env`: `OPENAI_API_KEY=sk-...`
- Or use: `/setgptkey sk-...`

### "Services not initialized"
- Check MT5 is running
- Check API server is running
- Visit `http://localhost:8000/docs`

---

## 📝 Example Session

```
You: /chatgpt

Bot: 🤖 ChatGPT Session Started!

     [📊 Market Analysis] [💰 Check Balance]
     [🎯 Trade Recommendation] [📈 Suggest Trade]
     [❌ End Chat]

You: Give me a trade for XAUUSD

Bot: 📊 Fetching current market data...

     Based on current analysis for XAUUSD:
     - Current Price: $3,863.82
     - Market Regime: RANGE
     - Recommendation: HOLD
     
     The market is range-bound. I recommend
     waiting for a breakout signal before
     entering a position.

You: What about BTCUSD?

Bot: 📊 Fetching current market data...

     For BTCUSD:
     - Current Price: $119,800.77
     - Market Regime: TRENDING
     - Recommendation: BUY
     
     Entry: $119,750
     SL: $119,250
     TP: $121,000
     
     Would you like me to execute this trade?

You: Yes

Bot: ✅ Trade executed successfully!
```

---

## 🎯 What's Next?

1. ✅ **Test the bot** - Ask questions, explore features
2. ✅ **Read the docs** - Understand what's possible
3. ✅ **Customize** - Edit handlers, add features
4. ✅ **Go live** - Start real trading (carefully!)

---

**Happy Trading! 🤖📈**

