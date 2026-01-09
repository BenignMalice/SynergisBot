# Range Scalping System - Live Test Instructions

## ✅ **IMPLEMENTATION STATUS**

**All 4 Phases Complete:**
- ✅ Phase 1: Core Infrastructure (RangeBoundaryDetector, RiskFilters, Configs)
- ✅ Phase 2: Early Exit System (ExitManager, Monitor, ErrorHandler)
- ✅ Phase 3: Strategy Implementation (5 strategies + Scorer)
- ✅ Phase 4: Integration (openai.yaml, analysis function, lot sizing)

**Tool Registration:** ✅ **ADDED** to `desktop_agent.py` (line ~6119)

---

## 🧪 **TESTING WITH LIVE CONNECTION**

### Option 1: Via Desktop Agent (Recommended)

**Step 1:** Start desktop agent
```bash
cd C:\Coding\MoneyBot
python desktop_agent.py
```

**Step 2:** In ChatGPT or via API, call:
```json
{
  "tool": "moneybot.analyse_range_scalp_opportunity",
  "arguments": {
    "symbol": "BTCUSD",
    "check_risk_filters": true
  }
}
```

**Expected Response:**
```json
{
  "summary": "Range scalping analysis for BTCUSD",
  "data": {
    "range_detected": true,
    "range_structure": {...},
    "risk_checks": {...},
    "top_strategy": {...},
    "warnings": []
  }
}
```

### Option 2: Direct Python Test

**File:** `test_range_scalping_integration.py`

**Usage:**
```bash
# Terminal 1: Start desktop agent
python desktop_agent.py

# Terminal 2: Run test
python test_range_scalping_integration.py BTCUSD
```

---

## 📋 **VERIFICATION CHECKLIST**

### Phase 1: Core Infrastructure ✅
- [ ] Config loads without errors
- [ ] RangeBoundaryDetector detects ranges
- [ ] RiskFilters calculate effective ATR
- [ ] RangeStructure serialization works

### Phase 2: Early Exit System ✅
- [ ] ErrorHandler initializes
- [ ] ExitManager loads state correctly
- [ ] Thread locks present

### Phase 3: Strategies ✅
- [ ] All 5 strategies initialize
- [ ] SL/TP calculations work
- [ ] Scorer ranks strategies

### Phase 4: Integration ✅
- [ ] Tool registered in desktop_agent
- [ ] openai.yaml updated
- [ ] Lot sizing returns 0.01
- [ ] Analysis function completes

---

## 🔍 **TROUBLESHOOTING**

### If tool not found:
1. Check `desktop_agent.py` line ~6119 has tool registration
2. Restart desktop_agent.py
3. Check registry: `registry.tools.keys()`

### If analysis fails:
1. Check MT5 connection
2. Verify symbol exists (e.g., "BTCUSDc")
3. Check logs for specific error

### If no range detected:
- Market may be trending (ADX > 25)
- Insufficient data (need M5/M15/H1 candles)
- Check logs for range detection errors

---

## 📊 **EXPECTED OUTPUT**

**Successful Analysis:**
```
✅ Range Detected
   Type: session
   High: 110500.00
   Low: 109500.00
   Mid: 110000.00

🔍 3-Confluence Score: 85/100
   Confluence Passed: ✅
   False Range: ✅ None
   Range Valid: ✅
   Session Allows: ✅

🎯 Top Strategy:
   Name: vwap_reversion
   Direction: BUY
   Entry: 109750.00
   SL: 109650.00
   TP: 109850.00
   R:R: 1.20
   Confidence: 75/100
```

---

## ⚠️ **IMPORTANT NOTES**

1. **Config Enabled:** Make sure `config/range_scalping_config.json` has `"enabled": true`
2. **MT5 Connection:** Requires active MT5 connection
3. **Dependencies:** Requires pandas, MetaTrader5, numpy
4. **Session Timing:** May block trades during London-NY overlap (12:00-15:00 UTC)

---

## 🎯 **NEXT STEPS AFTER TESTING**

1. Update knowledge documents (if tests pass)
2. Update formatting instructions
3. Test with ChatGPT integration
4. Monitor actual trades (if enabled)

