# 🚀 Phone Control - 3-Minute Quick Start

## ✅ Everything is Merged into Port 8000!

Phone control is now part of your main API. No separate command hub needed!

---

## 🎯 Start System (3 Commands)

### **1. Start Main API (if not running)**

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python app/main_api.py
```

**Copy these tokens from logs:**
```
🔐 Phone Control Tokens Generated:
   Phone Bearer Token: [COPY-THIS]    ← For Custom GPT
   Agent Secret: [COPY-THIS]          ← For desktop_agent.py
```

---

### **2. Update Desktop Agent**

Open `desktop_agent.py`, find line 43:

```python
AGENT_SECRET = "PASTE-AGENT-SECRET-HERE"
```

Paste the Agent Secret, save.

---

### **3. Start Desktop Agent**

```powershell
python desktop_agent.py
```

**Should see:**
```
✅ Connected to command hub
✅ Binance Service initialized
✅ Streaming 7 symbols
```

---

## 📱 Update Custom GPT (One Time)

### **Instructions:**
Copy `CUSTOM_GPT_INSTRUCTIONS.md` → Paste into Custom GPT Instructions

### **Knowledge:**
Upload:
- `ChatGPT_Knowledge_Binance_Integration.md`
- `ChatGPT_Knowledge_Document.md`
- `CUSTOM_GPT_INSTRUCTIONS_FULL.md`

### **Authentication:**
Paste **Phone Bearer Token** into Custom GPT → Actions → Authentication (Bearer)

---

## ✅ Test It!

From your phone ChatGPT:

```
"Analyse BTCUSD"
```

Should get full analysis with Binance enrichment!

---

## 📊 What's Running

| Component | Port | Status |
|-----------|------|--------|
| Main API | 8000 | Already running with ngrok |
| Desktop Agent | - | Just started |
| Binance | - | Auto-started with agent |
| ngrok | 8000 | Already running |

**Your existing ngrok URL works!**  
`https://verbally-faithful-monster.ngrok-free.app`

---

## 🔥 Common Issues

### "Connection refused"
→ Start main API first: `python app/main_api.py`

### "Authentication failed"
→ Update AGENT_SECRET in `desktop_agent.py` with correct token from logs

### "Agent offline" from phone
→ Check agent window, should say "✅ Connected to command hub"

---

**That's it! You're trading from your phone now!** 📱💰

---

**Reference:** See `PHONE_CONTROL_MERGED_SETUP.md` for complete details

