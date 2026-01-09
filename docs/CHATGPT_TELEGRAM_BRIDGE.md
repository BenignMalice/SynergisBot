# 🤖 ChatGPT Telegram Bridge

## Overview

Control ChatGPT directly from Telegram! Send messages, get analysis, and execute trades without leaving Telegram.

---

## 🚀 Features

### What You Can Do

1. **Chat with ChatGPT** - Natural conversation in Telegram
2. **Market Analysis** - Ask ChatGPT to analyze any symbol
3. **Trade Recommendations** - Get entry, SL, TP levels
4. **Execute Trades** - ChatGPT can place trades on MT5
5. **Check Account** - View balance, equity, positions
6. **OCO Bracket Trades** - ChatGPT can place bracket trades with automatic OCO

### How It Works

```
You (Telegram) → Bot → OpenAI API → ChatGPT Response → Bot → You (Telegram)
```

ChatGPT has access to your MT5 via the API endpoints:
- `/api/v1/price/{symbol}` - Live prices
- `/api/v1/account` - Account info
- `/mt5/execute` - Execute trades
- `/mt5/execute_bracket` - OCO bracket trades
- `/ai/analysis/{symbol}` - Technical analysis

---

## 📝 Setup

### Step 1: Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-...`)

### Step 2: Configure in Telegram

Send this command to your bot:
```
/setgptkey sk-your-api-key-here
```

✅ Your key is stored in memory only (not saved to disk for security)

### Step 3: Start Chatting

```
/chatgpt
```

---

## 💬 Commands

### `/chatgpt`
Start a ChatGPT conversation

**Example:**
```
User: /chatgpt
Bot: 🤖 ChatGPT Trading Assistant

     I can help you with:
     • Market analysis
     • Trade recommendations
     • Placing trades on MT5
     ...
```

### `/endgpt`
End the current ChatGPT conversation

### `/setgptkey <key>`
Set your OpenAI API key

---

## 🎯 Usage Examples

### Example 1: Market Analysis

```
You: Analyze XAUUSD and tell me if it's a good time to buy

ChatGPT: Let me check the current market data for XAUUSD...

[ChatGPT calls /api/v1/price/XAUUSD and /ai/analysis/XAUUSD]

Based on the data:
- Current price: $3,860.25
- RSI: 50 (neutral)
- Market regime: RANGE
- EMA20 > EMA50 (slightly bullish)

It's a neutral setup. I'd wait for RSI to drop below 40 
or look for a breakout above $3,870 resistance.
```

### Example 2: Get Trade Recommendation

```
You: Give me a buy setup for XAUUSD with entry, SL, and TP

ChatGPT: Here's a BUY setup for XAUUSD:

📈 BUY LIMIT @ $3,850
🛡️ Stop Loss: $3,842 (8 pips risk)
🎯 Take Profit: $3,870 (20 pips reward)
💰 R:R Ratio: 2.5:1

This is based on:
- Support level at $3,850
- RSI trending down (potential oversold bounce)
- Range-bound market favors mean reversion

Would you like me to place this trade?
```

### Example 3: Execute Trade

```
You: Yes, place that trade

ChatGPT: Executing BUY LIMIT order for XAUUSD...

[ChatGPT calls /mt5/execute with the parameters]

✅ Trade executed successfully!
- Order ID: #116380123
- Entry: $3,850
- SL: $3,842
- TP: $3,870
- Lot: 0.01

I'll monitor this for you. Good luck! 🍀
```

### Example 4: OCO Bracket Trade

```
You: Place a bracket trade on XAUUSD at 3850 and 3870

ChatGPT: Setting up OCO bracket trade...

[ChatGPT calls /mt5/execute_bracket]

✅ Bracket trade created with OCO monitoring!

BUY LIMIT @ $3,850
- SL: $3,842 | TP: $3,870
- Order: #116380150

SELL LIMIT @ $3,870
- SL: $3,878 | TP: $3,850
- Order: #116380151

OCO Group: OCO_XAUUSDc_1759480000_116380150

When one order fills, the other will be automatically 
cancelled within 3 seconds. 🎯
```

### Example 5: Check Account

```
You: What's my account balance?

ChatGPT: [ChatGPT calls /api/v1/account]

Your MT5 Account:
- Balance: $726.87 USC
- Equity: $726.87
- Free Margin: $726.87
- Profit: $0.00
- No open positions

You're all set to trade! 💰
```

---

## 🎨 Quick Action Buttons

When you start `/chatgpt`, you get these buttons:

| Button | Action |
|--------|--------|
| 📊 Analyze Market | Quick market analysis |
| 💰 Check Balance | View account info |
| 📈 Get Recommendation | Ask for trade setup |
| 🎯 Place Trade | Execute a trade |
| ❌ End Chat | Close conversation |

---

## 🔒 Security & Privacy

### What's Stored

**In Memory (Bot Runtime):**
- OpenAI API key (set with `/setgptkey`)
- Conversation history (last 10 messages per user)
- Session state

**Not Stored:**
- API key is NOT saved to disk
- Conversations are cleared when bot restarts
- No permanent logs of your chats

### What ChatGPT Can Access

**Via API (when you authorize):**
- ✅ Market prices (`/api/v1/price/{symbol}`)
- ✅ Your account balance (`/api/v1/account`)
- ✅ Technical indicators (`/ai/analysis/{symbol}`)
- ✅ Trade execution (`/mt5/execute`, `/mt5/execute_bracket`)
- ✅ OCO status (`/oco/status`)

**Cannot Access:**
- ❌ Your Telegram messages (outside the /chatgpt session)
- ❌ Other users' data
- ❌ Bot configuration or internal data

---

## ⚙️ Configuration

### API Model

**Default:** `gpt-4o-mini`
- Fast responses (1-3 seconds)
- Cost-effective ($0.15 per 1M tokens)
- Good for trading decisions

**Alternative:** `gpt-4o`
- More detailed analysis
- Slower (3-5 seconds)
- Higher cost ($2.50 per 1M tokens)

*Model can be changed in `handlers/chatgpt_bridge.py`, line 95*

### Conversation History

**Default:** Last 10 messages kept in memory

This prevents token limit issues and keeps responses fast.

---

## 💡 Pro Tips

### 1. Be Specific
```
❌ "What about gold?"
✅ "Analyze XAUUSD and give me a BUY setup with SL and TP"
```

### 2. Confirm Before Executing
```
❌ "Place a trade"
✅ "Give me a recommendation first, then I'll tell you to execute"
```

### 3. Use Symbols Correctly
```
✅ XAUUSD (will be normalized to XAUUSDc)
✅ BTCUSD (will be normalized to BTCUSDc)
```

### 4. Ask for OCO When Range-Trading
```
"Place a bracket trade on XAUUSD with BUY @ 3850 and SELL @ 3870"
→ ChatGPT will use /mt5/execute_bracket automatically
```

---

## 🐛 Troubleshooting

### "OpenAI API key not configured"
**Solution:** Run `/setgptkey sk-your-key-here`

### "No active ChatGPT session"
**Solution:** Start a new session with `/chatgpt`

### ChatGPT taking too long
**Possible causes:**
- API server slow/offline
- ngrok tunnel down
- OpenAI API rate limits

**Check:**
1. `/health` - Is API server running?
2. Check ngrok terminal - Is it active?
3. OpenAI dashboard - Any rate limit issues?

### "ChatGPT API error: 429"
**Solution:** You've hit OpenAI rate limits. Wait a few minutes.

### "ChatGPT API error: 401"
**Solution:** Invalid API key. Get a new one and run `/setgptkey`

---

## 📊 Cost Estimate

**Using gpt-4o-mini:**
- ~500 tokens per message exchange
- $0.15 per 1M tokens
- **Cost per chat:** ~$0.000075 (negligible)
- **100 chats:** ~$0.0075 (less than 1 cent)

**Very affordable for personal use!**

---

## 🎯 Advanced Features

### Multi-Timeframe Analysis
```
"Analyze XAUUSD on M5, M15, and H1 timeframes"
```

### Risk Management
```
"Check my portfolio risk and active positions"
```

### Trade History
```
"Show me my last 5 trades and their performance"
```

---

## 🔄 How to Restart

If bot restarts:
1. Conversations are cleared
2. API key is lost (you'll need to run `/setgptkey` again)
3. OCO monitoring continues (stored in database)

---

## ✅ Summary

**You can now:**
- 🤖 Chat with ChatGPT in Telegram
- 📊 Get market analysis
- 💰 Execute trades via ChatGPT
- 🎯 Place OCO bracket trades
- 📈 Check account status

**All without leaving Telegram!** 🚀

---

## 📚 Related Documentation

- `OCO_API_IMPLEMENTATION.md` - OCO bracket trades
- `CHATGPT_API_SETUP.md` - API integration details
- `openai.yaml` - Full API specification

---

**Start chatting: `/chatgpt`** 💬

