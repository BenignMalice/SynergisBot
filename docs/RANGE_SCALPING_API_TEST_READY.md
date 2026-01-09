# Range Scalping System - API Test Ready

## ✅ **STATUS: System Ready for API Testing**

**All 4 phases complete:**
- ✅ Phase 1: Core Infrastructure
- ✅ Phase 2: Early Exit System  
- ✅ Phase 3: Strategy Implementation
- ✅ Phase 4: Integration

**Tool Code:** Ready in `desktop_agent_range_scalp_tool.py`

---

## 🧪 **TEST FILES CREATED**

### 1. `test_range_scalp_dispatch.py` ⭐ **USE THIS**
- Tests via `/dispatch` endpoint (same as ChatGPT uses)
- Uses built-in `urllib` (no external dependencies)
- **Requires:** API server running + desktop agent connected

### 2. `test_range_scalp_api.py`
- Tests via desktop_agent registry directly
- Requires desktop_agent imports

### 3. `test_range_scalping_system.py`
- Structure validation tests
- Good for checking code integrity

---

## 📋 **HOW TO TEST**

### **Option 1: Via /dispatch API (Recommended)**

```bash
python test_range_scalp_dispatch.py BTCUSD
```

**Prerequisites:**
1. ✅ API server running (`app/main_api.py` on port 8000)
2. ✅ Desktop agent connected (`desktop_agent.py`)
3. ✅ Tool registered in `desktop_agent.py` (add code from `desktop_agent_range_scalp_tool.py`)

**Note:** You may need to update the bearer token in the test file:
```python
phone_token = "YOUR_ACTUAL_TOKEN_HERE"  # Get from API server logs
```

### **Option 2: Via ChatGPT/Custom GPT**

Once tool is registered in `desktop_agent.py`:
1. Start desktop agent
2. Ask ChatGPT: "Analyse range scalping opportunity for BTCUSD"
3. ChatGPT will call `moneybot.analyse_range_scalp_opportunity`

---

## ⚠️ **IMPORTANT: Register Tool First**

**Before testing, add the tool to `desktop_agent.py`:**

1. Open `desktop_agent_range_scalp_tool.py`
2. Copy all contents
3. Paste into `desktop_agent.py` at **line 6119** (between `tool_analyse_symbol_full` and `tool_execute_trade`)
4. Restart `desktop_agent.py`

**Or see:** `ADD_TOOL_TO_DESKTOP_AGENT.md` for detailed instructions

---

## 🔍 **EXPECTED API RESPONSE**

```json
{
  "command_id": "...",
  "status": "success",
  "summary": "Range scalping analysis for BTCUSD",
  "data": {
    "range_detected": true,
    "range_structure": {
      "range_type": "session",
      "range_high": 110500.00,
      "range_low": 109500.00,
      "range_mid": 110000.00
    },
    "risk_checks": {
      "confluence_score": 85,
      "3_confluence_passed": true,
      "risk_passed": true
    },
    "top_strategy": {
      "name": "vwap_reversion",
      "direction": "BUY",
      "entry_price": 109750.00,
      "stop_loss": 109650.00,
      "take_profit": 109850.00,
      "r_r_ratio": 1.20,
      "confidence": 75
    }
  },
  "execution_time": 2.34
}
```

---

## 🐛 **TROUBLESHOOTING**

### "Tool not found"
- Tool not registered in `desktop_agent.py`
- Restart desktop agent after adding tool

### "Desktop agent offline"
- `desktop_agent.py` not running
- Check WebSocket connection to API server

### "403 Forbidden"
- Wrong bearer token
- Get correct token from API server logs
- Update `phone_token` in test file

### "No range detected"
- Market may be trending (ADX > 25)
- Insufficient data
- Check MT5 connection

---

## ✅ **VERIFICATION CHECKLIST**

Before testing, verify:
- [ ] Tool code added to `desktop_agent.py` line 6119
- [ ] Desktop agent restarted
- [ ] API server running (`app/main_api.py`)
- [ ] Desktop agent connected (check logs for "✅ Authenticated")
- [ ] MT5 connection active
- [ ] Correct bearer token in test file

---

## 📊 **NEXT STEPS**

After successful test:
1. Update knowledge documents
2. Test with ChatGPT integration
3. Monitor live trades (if enabled in config)

---

**Status:** ✅ **READY FOR API TESTING** (after tool registration)

