## 🚀 TelegramMoneyBot Phone Control System - Setup Guide

Control your desktop trading bot from your phone via Custom GPT!

---

## 📋 **What You're Building:**

```
📱 Phone (Custom GPT) 
    ↓ HTTPS
☁️  ngrok (exposes localhost to internet)
    ↓
💻 Command Hub (localhost:8001)
    ↓ WebSocket
🤖 Desktop Agent (connects to hub)
    ↓
📊 Your MoneyBot Stack (MT5, analysis, trading)
```

**Round-trip**: Phone → Hub → Agent → MoneyBot → Agent → Hub → Phone (3-30 seconds)

---

## ⚡ **Quick Start (5 Minutes)**

### **Step 1: Start the Command Hub**

Open a terminal in `C:\mt5-gpt\TelegramMoneyBot.v7`:

```bash
python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8001
```

**Look for these lines in the output:**
```
🔐 Phone Bearer Token: eyJhbGc...
🔐 Agent Secret: dGhpc2l...
```

**IMPORTANT**: Copy both tokens! You'll need them in Steps 3 and 4.

---

### **Step 2: Expose Hub via ngrok**

Open a **second terminal**:

```bash
ngrok http 8001
```

**Copy the HTTPS URL** (looks like `https://abc123.ngrok-free.app`)

---

### **Step 3: Configure Desktop Agent**

Edit `desktop_agent.py`, replace line 31:

```python
AGENT_SECRET = "PASTE_AGENT_SECRET_FROM_STEP_1"
```

Start the agent in a **third terminal**:

```bash
python desktop_agent.py
```

**You should see:**
```
✅ Authenticated with hub - ready to receive commands
```

---

### **Step 4: Configure Phone Custom GPT**

1. Go to https://chatgpt.com/gpts/editor
2. Create a new GPT named "MoneyBot Phone Control"
3. In **Configure** → **Actions**:
   - Click "Create new action"
   - Paste contents of `openai_phone.yaml`
   - Replace `YOUR_NGROK_URL_HERE` with your ngrok URL from Step 2
4. In **Authentication**:
   - Choose "Bearer token"
   - Paste the **Phone Bearer Token** from Step 1
5. Click "Save"

---

### **Step 5: Test It!**

In your phone Custom GPT, send:

```
ping test
```

You should get:
```
🏓 Pong! Hello from desktop agent!
```

**SUCCESS!** Your phone is now connected to your desktop trading bot! 🎉

---

## 📱 **Phone Custom GPT Instructions**

Add these instructions to your Custom GPT:

```
You are MoneyBot Phone Control - a trading assistant that controls a desktop trading bot.

CORE CAPABILITIES:
- Analyse trading symbols (BTCUSD, XAUUSD, EURUSD, etc.)
- Execute trades with intelligent exits
- Monitor open positions
- Report account status

COMMAND FLOW:
1. User asks for analysis → call dispatchCommand with tool "moneybot.analyse_symbol"
2. Show the summary clearly
3. If user says "execute" → call dispatchCommand with tool "moneybot.execute_trade" using the data from step 1
4. Confirm ticket number and monitoring status

SAFETY RULES:
- NEVER execute trades without explicit "execute" command
- Always show the full plan before executing
- If agent is offline, tell user clearly

RESPONSE FORMAT:
- Keep summaries short (2-3 screens max)
- Use emojis for clarity (📊 analysis, 💰 execution, 📈 monitoring)
- Always show: direction, entry, SL, TP, confidence
- After execution, confirm: ticket, monitoring enabled

EXAMPLE CONVERSATION:
User: "Analyse BTCUSD"
You: [Call dispatchCommand with analyse_symbol]
     Show: Direction, Entry, SL, TP, Confidence, R:R
     
User: "Execute"
You: [Call dispatchCommand with execute_trade using previous data]
     Show: Ticket, Entry confirmed, Monitoring enabled

User: "Show status"
You: [Call dispatchCommand with monitor_status]
     Show: Open positions, P/L, monitoring status
```

---

## 🔧 **Available Tools**

### **1. ping**
Test connectivity.

**Arguments:**
- `message` (optional): Custom message

**Example:**
```json
{
  "tool": "ping",
  "arguments": {
    "message": "Hello from phone!"
  }
}
```

---

### **2. moneybot.analyse_symbol**
Analyse a trading symbol.

**Arguments:**
- `symbol` (required): Trading symbol (BTCUSD, XAUUSD, etc.)
- `detail_level` (optional): "standard" | "detailed"

**Example:**
```json
{
  "tool": "moneybot.analyse_symbol",
  "arguments": {
    "symbol": "BTCUSD",
    "detail_level": "standard"
  }
}
```

**Returns:**
- Summary with direction, entry, SL, TP, confidence
- Structured data for execution

---

### **3. moneybot.execute_trade**
Execute a trade on MT5.

**Arguments:**
- `symbol` (required): Trading symbol
- `direction` (required): "BUY" | "SELL"
- `entry` (required): Entry price
- `stop_loss` (required): Stop loss price
- `take_profit` (required): Take profit price
- `volume` (optional): Position size (default 0.01)
- `order_type` (optional): "market" | "limit" | "stop" (default "market")

**Example:**
```json
{
  "tool": "moneybot.execute_trade",
  "arguments": {
    "symbol": "BTCUSD",
    "direction": "BUY",
    "entry": 65430.00,
    "stop_loss": 65100.00,
    "take_profit": 65950.00,
    "volume": 0.01
  }
}
```

**Returns:**
- Ticket number
- Trade confirmation
- Monitoring status

---

### **4. moneybot.monitor_status**
Check status of all monitored positions.

**Arguments:** (none)

**Example:**
```json
{
  "tool": "moneybot.monitor_status",
  "arguments": {}
}
```

**Returns:**
- Summary of open trades
- P/L for each position
- Intelligent exit status

---

## 🔐 **Security Notes**

1. **Keep tokens secret!** Never share them publicly.
2. **Rotate tokens** if compromised:
   - Stop hub
   - Edit `hub/command_hub.py` lines 41-42
   - Restart hub
   - Update agent and phone GPT with new tokens

3. **Use HTTPS** (ngrok provides this automatically)

4. **Restrict ngrok** (optional):
   - Add IP whitelist in ngrok dashboard
   - Or use Tailscale instead of ngrok

---

## 🐛 **Troubleshooting**

### **"Desktop agent offline"**
- Check if `desktop_agent.py` is running
- Check if AGENT_SECRET matches hub logs
- Check if MT5 is running

### **"Authentication failed"**
- Check if Phone Bearer Token matches hub logs
- Verify token is in Custom GPT Authentication settings

### **"Command timed out"**
- Normal for first analysis (loading indicators)
- Increase timeout in phone request (up to 120s)
- Check agent logs for errors

### **"Invalid JSON received"**
- Check ngrok URL is correct in `openai_phone.yaml`
- Verify ngrok is running

---

## 📊 **What's Next? (Sprint 2)**

Once basic connectivity works, we'll add:

1. ✅ Real decision_engine integration (replace mock analysis)
2. ✅ Real MT5 order execution
3. ✅ Advanced features in analysis
4. ✅ Intelligent exits auto-enablement
5. ✅ Trade history and audit logs
6. ✅ Multi-symbol batch analysis

---

## 🎯 **Testing Checklist**

- [ ] Hub starts without errors
- [ ] ngrok exposes hub successfully
- [ ] Agent connects and authenticates
- [ ] Phone GPT can call `/health`
- [ ] Phone GPT can execute `ping` tool
- [ ] Phone GPT receives pong response
- [ ] Analysis tool returns mock data
- [ ] Execute tool returns mock ticket
- [ ] Monitor tool shows open positions

---

## 💡 **Tips**

1. **Keep all three terminals open**: hub, ngrok, agent
2. **Use `--reload` for development**:
   ```bash
   uvicorn hub.command_hub:app --reload --host 0.0.0.0 --port 8001
   ```
3. **Check logs** for debugging (agent and hub both log verbosely)
4. **Test with `ping` first** before trying trading commands

---

**Status**: ✅ Sprint 1 Complete - Core infrastructure ready!

**Next**: Sprint 2 - Real analysis and execution integration

