# BTCUSD Zero Indicators - Complete Debugging Guide

## 🔍 **Current Situation**

You're getting recommendations with:
- ✅ Price data works (Bid: $122185.44, Ask: $122203.44)
- ❌ RSI: 50.0 (neutral default)
- ❌ ADX: 0.0 (no data)
- ❌ ATR: 0.00 (no data)
- ❌ EMA20/50/200: $0.00 (no data)
- ❌ Market Regime: UNKNOWN

## 📊 **Data Flow**

```
User: "get btcusdc trade recommendation"
   ↓
ChatGPT Bridge (handlers/chatgpt_bridge.py)
   ↓
execute_get_market_data("btcusdc")
   ↓
Converts to: "BTCUSDC"
   ↓
API Request: GET /api/v1/multi_timeframe/BTCUSDC
   ↓
API (app/main_api.py)
   ↓
normalize_symbol("BTCUSDC")
   - Removes 'C' → "BTCUSD"
   - Adds 'c' → "BTCUSDc" ✅
   ↓
IndicatorBridge.get_multi("BTCUSDc")
   ↓
MT5: copy_rates_from_pos("BTCUSDc", M5, 0, 500)
   ↓
Result: ??? (This is where it might be failing)
```

## 🎯 **Diagnostic Steps**

### Step 1: Check if API Server is Running

The ChatGPT bot needs the API server to be running separately!

```bash
# Check if API is running
curl http://localhost:8000/health

# If not running, start it:
python app/main_api.py
```

**Expected Output:**
```json
{"status": "ok", "timestamp": "2025-10-09T..."}
```

### Step 2: Test API Directly

Run the test script:

```bash
python test_api_btc.py
```

**What to Look For:**
- ✅ All status codes should be 200
- ✅ RSI should be a real number (not 50.0)
- ✅ ADX should be > 0
- ✅ EMA20 should be a real price
- ✅ ATR should be > 0

**If you see zeros:** The API is running but IndicatorBridge can't get data

**If API isn't running:** That's your problem!

### Step 3: Check MT5 Connection

```python
import MetaTrader5 as mt5

# Initialize MT5
if not mt5.initialize():
    print("❌ MT5 not initialized")
else:
    print("✅ MT5 connected")
    
    # Check symbol
    symbol = "BTCUSDc"
    info = mt5.symbol_info(symbol)
    
    if info is None:
        print(f"❌ Symbol {symbol} not found")
    else:
        print(f"✅ Symbol found: {info.description}")
        print(f"   Visible: {info.visible}")
        
        # Try to get data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 10)
        if rates is None:
            print(f"❌ No data for {symbol}")
        else:
            print(f"✅ Got {len(rates)} bars of data")
```

## 🚨 **Most Likely Causes**

### Cause 1: API Server Not Running ⭐ **MOST COMMON**

**Symptoms:**
- Price data works (direct MT5 connection)
- Indicators all 0.00 (need API)

**Solution:**
```bash
# Terminal 1: Start API server
python app/main_api.py

# Terminal 2: Start Telegram bot
python chatgpt_bot.py
```

**Why:** The Telegram bot uses the API server for indicator calculations. If the API isn't running, it can't get indicator data.

### Cause 2: IndicatorBridge Can't Get Data

**Symptoms:**
- API is running
- Still getting 0.00 values

**Check API Logs:**
```
[2025-10-09 ...] [WARNING] infra.indicator_bridge: No rates data for BTCUSDc M5
```

**Solution:**
- Ensure BTCUSDc has historical data in MT5
- Check if symbol is enabled in Market Watch
- Try: `python check_symbol.py BTC` to verify

### Cause 3: Symbol Name Mismatch in normalize_symbol()

**Symptoms:**
- API logs show wrong symbol name

**Check:**
Look at API logs when you request data:
```
[INFO] app.main_api: Multi-timeframe analysis for BTCUSDc
```

Should be "BTCUSDc" not "BTCUSD" or "BTCUSDcc"

## 🔧 **Quick Fix Checklist**

✅ **Step 1:** Is MT5 running and connected?
```bash
# Check MT5 terminal is open
```

✅ **Step 2:** Is API server running?
```bash
curl http://localhost:8000/health
# If not, start it: python app/main_api.py
```

✅ **Step 3:** Does BTCUSDc have data?
```bash
python check_symbol.py BTC
# Should show: Data: ✅ HAS DATA
```

✅ **Step 4:** Test API directly
```bash
python test_api_btc.py
# Should show real indicator values
```

✅ **Step 5:** Try Telegram again
```
Analyze BTCUSDc for me
```

## 📝 **Expected API Response**

When working correctly, `/api/v1/multi_timeframe/BTCUSDC` should return:

```json
{
  "symbol": "BTCUSDc",
  "timeframes": {
    "H4": {
      "bias": "BULLISH",
      "confidence": 75,
      "rsi": 65.5,
      "adx": 42.3,
      "ema20": 120500.00,
      "atr": 1250.00
    },
    "M5": {
      "execution": "BUY",
      "rsi": 58.2,
      "adx": 38.5
    }
  },
  "recommendation": {
    "action": "BUY",
    "confidence": 78,
    "alignment_score": 85
  }
}
```

## 🎯 **Most Likely Solution**

Based on your symptoms (price works but indicators are 0), the issue is **99% likely**:

### **🚨 API Server Not Running**

**Test:**
```bash
curl http://localhost:8000/health
```

**If you get "connection refused":**
```bash
# Start the API server
python app/main_api.py

# Keep it running in a separate terminal
```

**Then test again:**
```
In Telegram: "Analyze BTCUSDc for me"
```

## 📊 **Architecture Reminder**

Your system has **TWO separate processes**:

1. **API Server** (`app/main_api.py`)
   - Handles indicator calculations
   - Runs on port 8000
   - Must be running for indicators to work

2. **Telegram Bot** (`chatgpt_bot.py`)
   - Handles user messages
   - Calls API for analysis
   - Can get prices directly from MT5

**Both must be running!**

## 🔍 **Verification Script**

I've created `test_api_btc.py` that will:
- Test all symbol variations
- Check API responses
- Show indicator values
- Identify the problem

Run it and share the output!

## 💡 **Quick Commands**

```bash
# 1. Check if API is running
curl http://localhost:8000/health

# 2. If not running, start it (Terminal 1)
python app/main_api.py

# 3. Test API data (Terminal 2)
python test_api_btc.py

# 4. If API works, test Telegram bot
# In Telegram: "Analyze BTCUSDc for me"
```

## 📞 **Next Steps**

1. Run `python test_api_btc.py`
2. Share the output
3. I'll tell you exactly what's wrong

---

**Most likely:** You need to start the API server with `python app/main_api.py` 🚀
