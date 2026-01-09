# 📱 TelegramMoneyBot Phone Control - Quickstart Guide

**Goal**: Control your desktop trading agent from your phone in 15 minutes.

---

## ✅ Prerequisites Checklist

Before you start, make sure you have:

- [ ] Python 3.9+ installed
- [ ] TelegramMoneyBot.v7 cloned and working
- [ ] MT5 installed and logged in
- [ ] ngrok installed and authenticated
- [ ] OpenAI Custom GPT access (ChatGPT Plus or Enterprise)

---

## 🚀 5-Step Setup

### **Step 1: Start the Command Hub** (2 min)

```bash
cd C:\mt5-gpt\TelegramMoneyBot.v7
python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8001
```

**Look for these lines in the output:**
```
🔐 Phone Bearer Token: PHONE_abc123xyz...
🔐 Agent Secret: AGENT_def456uvw...
```

**Copy both tokens!** You'll need them in the next steps.

---

### **Step 2: Expose the Hub via ngrok** (1 min)

Open a **new terminal** and run:

```bash
ngrok http 8001
```

**Copy the HTTPS URL** from the output:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8001
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
            Copy this!
```

---

### **Step 3: Configure & Start the Desktop Agent** (2 min)

Open `desktop_agent.py` in your editor.

**Find line 39** and replace the placeholder:
```python
AGENT_SECRET = "REPLACE_WITH_YOUR_AGENT_SECRET"
```

**Paste the Agent Secret** from Step 1:
```python
AGENT_SECRET = "AGENT_def456uvw..."  # Your actual secret
```

**Save the file** and run:
```bash
python desktop_agent.py
```

**Look for:**
```
✅ Successfully connected to Command Hub.
📡 Heartbeat active. Listening for commands...
```

---

### **Step 4: Configure Your Phone's Custom GPT** (5 min)

1. **Open ChatGPT on your phone** and go to:
   - https://chatgpt.com/gpts/editor

2. **Create a New GPT**:
   - Name: "MoneyBot Control"
   - Description: "Trade control for my desktop MoneyBot"

3. **Instructions**:
   - Click "Configure" tab
   - Paste the contents of `PHONE_CONTROL_CUSTOM_GPT_INSTRUCTIONS.md`

4. **Actions**:
   - Click "Actions" → "Import from URL or file"
   - Upload `openai_phone.yaml`
   
5. **Edit the imported action**:
   - Find the `servers` section
   - Replace `YOUR_NGROK_URL_HERE` with your ngrok URL from Step 2:
     ```yaml
     servers:
       - url: https://abc123.ngrok-free.app  # Your actual ngrok URL
     ```

6. **Authentication**:
   - In the Actions panel, click "Authentication"
   - Select "Bearer Token"
   - Paste the **Phone Bearer Token** from Step 1

7. **Save** your GPT.

---

### **Step 5: Test from Your Phone!** (5 min)

Open your new "MoneyBot Control" GPT on your phone and try:

#### **Test 1: Connectivity**
```
ping
```

**Expected:**
```
🏓 Pong! Hello from desktop agent!
Status: healthy
Timestamp: [current time]
```

#### **Test 2: Analysis**
```
Analyse BTCUSD
```

**Expected:**
```
📊 BTCUSD Analysis - [STRATEGY]

Direction: BUY/SELL MARKET
Entry: [price]
Stop Loss: [price]
Take Profit: [price]
Risk:Reward: 1:[ratio]
Confidence: [%]

Regime: [regime type]
Current: [current price]

💡 [Reasoning]

Reply "Execute" to place this trade.
```

#### **Test 3: Monitoring**
```
Show my trades
```

**Expected:**
```
📊 Monitoring Status - [N] Position(s)

[List of positions with P/L and V8 status]

━━━━━━━━━━━━━━━━━━━━
Total P/L: $[amount]
Monitored: [N]/[N] positions
Advanced-Enhanced Exits: ACTIVE
```

#### **Test 4: Execution** ⚠️ (CAUTION: Real trade!)

Only do this if you want to place a real trade:

```
Execute
```

**Expected:**
```
✅ Trade Executed Successfully!

Ticket: [ticket number]
[DIRECTION] [SYMBOL] @ [entry price]
SL: [price] | TP: [price]
Volume: 0.01 lots

🤖 Advanced-Enhanced Intelligent Exits: ACTIVE
   Breakeven: [%]
   Partial: [%]

📊 Your trade is now on autopilot!
```

---

## 🔧 Troubleshooting

### **"Desktop agent is offline"**

**Check:**
1. Is `desktop_agent.py` running? (Step 3)
2. Is `hub/command_hub.py` running? (Step 1)
3. Is ngrok running and showing the same URL? (Step 2)
4. Did you paste the correct `AGENT_SECRET` in `desktop_agent.py`?

**Fix:**
- Restart all three services in order: Hub → ngrok → Agent
- Check for error messages in each terminal

---

### **"Invalid Bearer Token"**

**Check:**
1. Did you copy the **Phone Bearer Token** from the hub's startup logs?
2. Did you paste it into your Custom GPT's Authentication settings?
3. Are there any extra spaces or line breaks?

**Fix:**
- Copy the token again from the hub terminal
- Delete the old token in Custom GPT settings
- Paste the new token and save

---

### **"Analysis failed: Failed to fetch market data"**

**Check:**
1. Is MT5 running and logged in?
2. Is the symbol available on your broker? (Try `XAUUSDc` if `XAUUSD` fails)
3. Is your internet connection stable?

**Fix:**
- Restart MT5
- Check `desktop_agent.py` terminal for detailed error messages
- Try a different symbol (e.g., "EURUSD")

---

### **ngrok URL keeps changing**

**Problem**: Free ngrok URLs change every time you restart ngrok.

**Solutions**:
1. **Get a static domain** (ngrok paid plan)
2. **Update the URL** in `openai_phone.yaml` each time ngrok restarts
3. **Use Tailscale** (more advanced, but permanent URLs)

---

## 🎯 What to Test

### **Recommended Test Sequence:**

1. ✅ **Ping** (verify connectivity)
2. ✅ **Analyse BTCUSD** (verify decision engine)
3. ✅ **Analyse XAUUSD** (verify multi-symbol support)
4. ✅ **Show my trades** (verify monitoring, even if empty)
5. ⚠️ **Execute** (only if you want a real trade!)

### **Advanced Tests:**

- "Detailed analysis of BTCUSD" (should include Advanced insights)
- "Analyse EURUSD" (test forex pairs)
- "Analyse XAGUSD" (test silver)
- Try HOLD signals (low-confidence or no setup markets)

---

## 📊 What Happens Behind the Scenes

When you send a message from your phone:

```
Your Phone (Custom GPT)
    ↓ HTTPS (Bearer token)
ngrok → Command Hub (localhost:8001)
    ↓ WebSocket (Agent secret)
Desktop Agent (desktop_agent.py)
    ↓ Function call
MoneyBot Stack (MT5, decision_engine, Advanced features, etc.)
    ↓ Result
Desktop Agent
    ↓ WebSocket
Command Hub
    ↓ HTTPS
Your Phone (formatted summary)
```

**Round-trip time**: 3-10 seconds depending on the task.

---

## 🔒 Security Notes

- **Bearer tokens** authenticate your phone to the hub
- **Agent secrets** authenticate your agent to the hub
- **ngrok HTTPS** encrypts all traffic
- **No secrets in code** (except `desktop_agent.py` for now)

**For production**:
- Move secrets to environment variables
- Use ngrok's static domains
- Set up IP whitelisting
- Rotate tokens regularly

---

## 🚀 You're Ready!

You can now:
- 📊 **Analyse** any symbol from your phone
- 💰 **Execute** trades with Advanced intelligent exits
- 📈 **Monitor** all positions in real-time
- 🤖 **Trust** the autopilot to manage your exits

**All from anywhere in the world!** 🌍

---

## 📚 Further Reading

- `PHONE_CONTROL_SETUP.md` - Detailed setup guide
- `PHONE_CONTROL_SPRINT1_COMPLETE.md` - Architecture overview
- `PHONE_CONTROL_SPRINT2_COMPLETE.md` - Integration details
- `PHONE_CONTROL_CUSTOM_GPT_INSTRUCTIONS.md` - How the GPT works

---

**Need help?** Check the troubleshooting section or review the logs in each terminal.

**Ready for more?** See `PHONE_CONTROL_SPRINT2_COMPLETE.md` for Sprint 3 roadmap (trade modification, advanced tools, reporting).

