# 🎉 Phone Control System Ready (ngrok)

Your TelegramMoneyBot Phone Control System is ready to use!

## ✅ What's Done

1. ✅ **Command Hub** running on port 8001
2. ✅ **ngrok** exposing hub at `https://verbally-faithful-monster.ngrok-free.app`
3. ✅ **openai.yaml** updated with `/dispatch` endpoint
4. ✅ **Desktop Agent** ready to start (`desktop_agent.py`)
5. ✅ **Tokens** generated and documented

## 🚀 Quick Start (3 Steps)

### Step 1: Update Custom GPT (2 minutes)
1. Go to ChatGPT → Your MoneyBot GPT → **Configure** → **Actions**
2. Click **Import from URL** or **Refresh**
3. Paste the entire contents of `openai.yaml`
4. Verify authentication token is: `G1XjstAJMTutKcTr1K9Myai0-pVdCBOl1hSqj2sZves`
5. Save

### Step 2: Start Desktop Agent (30 seconds)
Open a **new** PowerShell window:
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

Wait for:
```
✅ Connected to Command Hub!
🎧 Listening for commands from phone...
```

### Step 3: Test from Phone (1 minute)
Open ChatGPT app on your phone, select your MoneyBot GPT:

**Test 1:** Say **"ping my desktop"**
- Expected: "🏓 Pong from Desktop"

**Test 2:** Say **"analyse BTCUSD"**
- Expected: Full market analysis with Advanced features

**Test 3:** Say **"what positions are open?"**
- Expected: List of open positions and P/L

---

## 📋 System URLs

| Component | URL |
|-----------|-----|
| ngrok Public URL | `https://verbally-faithful-monster.ngrok-free.app` |
| Command Hub (local) | `http://localhost:8001` |
| Health Check | `https://verbally-faithful-monster.ngrok-free.app/health` |

## 🔐 Authentication

**Phone Bearer Token** (for Custom GPT Actions):
```
G1XjstAJMTutKcTr1K9Myai0-pVdCBOl1hSqj2sZves
```

**Agent Secret** (already in `desktop_agent.py`):
```
F9PojuC4P7xsN2s0594aa9w7SSZX292bXBLhXo-JVsI
```

## 🧰 What You Can Do from Your Phone

1. **Ping** - Test connection: "ping my desktop"
2. **Analyse** - Market analysis: "analyse XAUUSD"
3. **Execute** - Place trades: "buy BTCUSD, SL 59000, TP 62000"
4. **Monitor** - Check positions: "show my open positions"
5. **Modify** - Adjust SL/TP: "move SL on position 123456 to 3945"
6. **Close** - Close positions: "close 50% of position 123456"
7. **Exits** - Toggle intelligent exits: "enable Advanced exits for 123456"
8. **Macro** - DXY/VIX/US10Y: "macro context for Gold"

## 📦 Files You Need

| File | Purpose |
|------|---------|
| `openai.yaml` | Import this into your Custom GPT Actions |
| `desktop_agent.py` | Run this on your desktop PC |
| `hub/command_hub.py` | Already running (don't restart) |
| `PHONE_CONTROL_CUSTOM_GPT_INSTRUCTIONS.md` | Instructions for your Custom GPT |

## 🔄 Daily Workflow

### Morning Setup (1 minute)
1. Start ngrok: Already running ✅
2. Start Command Hub: Already running ✅
3. Start Desktop Agent:
   ```powershell
   python desktop_agent.py
   ```

### Trading from Phone
- Open ChatGPT app
- Select MoneyBot GPT
- Start talking: "analyse BTCUSD", "show positions", etc.

### End of Day
- Stop Desktop Agent: Ctrl+C
- Leave ngrok and Command Hub running

## ⚠️ Important Notes

### ngrok Free Limitations
- ✅ 1 tunnel at a time
- ⚠️ URL changes on restart (but you haven't restarted yet!)
- ⚠️ 40 connections/minute limit

### When ngrok URL Changes
If you restart ngrok, the URL will change. You'll need to:
1. Get new URL from ngrok terminal
2. Update `openai.yaml` server URL
3. Re-import in Custom GPT Actions

### Keeping ngrok Alive
- Leave the ngrok terminal window open
- Don't close it or your phone won't be able to connect

## 🧪 Troubleshooting

### "Desktop agent not connected"
```powershell
# Restart the desktop agent
cd c:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

### "Timeout"
- Check desktop agent terminal for errors
- Verify Command Hub is running on port 8001
- Check ngrok is still active

### "Unauthorized"
- Verify Custom GPT has Bearer token: `G1XjstAJMTutKcTr1K9Myai0-pVdCBOl1hSqj2sZves`
- Re-import `openai.yaml` if needed

### Command Hub Not Responding
If you accidentally closed it:
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8001
```

## 🎯 Next Steps

1. **Right Now**: Start desktop agent and test "ping"
2. **Today**: Test all 8 phone tools
3. **This Week**: Use phone control for real trading
4. **Later**: Consider Cloudflare Tunnel for permanent URL (optional)

---

**You're ready!** 🚀

Open PowerShell, run `python desktop_agent.py`, then test from your phone!

