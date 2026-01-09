# 📊 Symbol Mapping Reference

## ✅ Verification Status: ALL TESTS PASSED

Your Binance ↔ MT5 symbol mapping is fully synchronized and tested.

---

## 🔄 Symbol Mapping Table

| # | Binance Symbol | MT5 Symbol | Phone Input Options |
|---|----------------|------------|---------------------|
| 1 | `btcusdt` | `BTCUSDc` | BTCUSD, BTCUSDc, btcusdt |
| 2 | `xauusd` | `XAUUSDc` | XAUUSD, XAUUSDc, xauusd |
| 3 | `eurusd` | `EURUSDc` | EURUSD, EURUSDc, eurusd |
| 4 | `gbpusd` | `GBPUSDc` | GBPUSD, GBPUSDc, gbpusd |
| 5 | `usdjpy` | `USDJPYc` | USDJPY, USDJPYc, usdjpy |
| 6 | `gbpjpy` | `GBPJPYc` | GBPJPY, GBPJPYc, gbpjpy |
| 7 | `eurjpy` | `EURJPYc` | EURJPY, EURJPYc, eurjpy |

---

## 🎯 How It Works

### Automatic Conversion System

```
┌──────────────────────────────────────────────────────────┐
│  YOU (Phone)                                             │
│  Says: "Analyse BTCUSD"                                  │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  DESKTOP AGENT                                           │
│  • Receives: "BTCUSD"                                    │
│  • Converts to MT5: "BTCUSDc" → MT5 analysis            │
│  • Converts to Binance: "btcusdt" → Feed validation     │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  PARALLEL OPERATIONS                                     │
│                                                          │
│  MT5 Path:              Binance Path:                   │
│  BTCUSDc → get_quote()  btcusdt → check feed health    │
│  BTCUSDc → indicators   btcusdt → get offset           │
│  BTCUSDc → execute      btcusdt → validate safety      │
└──────────────────────────────────────────────────────────┘
```

---

## 🧪 Tested Scenarios

### ✅ Test Results

**Test 1: Binance → MT5 Conversion**
```
btcusdt → BTCUSDc ✅
eurusd → EURUSDc ✅
gbpjpy → GBPJPYc ✅
(All 7 symbols passed)
```

**Test 2: MT5 → Binance Conversion**
```
BTCUSDc → btcusdt ✅
EURUSDc → eurusd ✅
GBPJPYc → gbpjpy ✅
(All 7 symbols passed)
```

**Test 3: Round-Trip Conversion**
```
btcusdt → BTCUSDc → btcusdt ✅
eurusd → EURUSDc → eurusd ✅
(No data loss in conversion)
```

**Test 4: User Input Variations**
```
BTCUSD → BTCUSDc ✅ (uppercase)
btcusdc → BTCUSDc ✅ (already has 'c')
BTCUSDc → BTCUSDc ✅ (correct format)
GBPJPY → GBPJPYc ✅ (forex)
xauusd → XAUUSDc ✅ (lowercase)
```

---

## 💡 Conversion Rules

### Binance → MT5

1. **Input:** Any case (BTCUSD, btcusd, BTCUSDc)
2. **Normalize:** Convert to uppercase
3. **Remove USDT:** If crypto (BTCUSDT → BTCUSD)
4. **Remove existing 'c':** If present (normalize)
5. **Add 'c' suffix:** Result: BTCUSDc
6. **Output:** MT5-compatible symbol

### MT5 → Binance

1. **Input:** MT5 format (BTCUSDc, EURUSDc)
2. **Normalize:** Convert to uppercase
3. **Remove 'c' suffix:** BTCUSDc → BTCUSD
4. **Add USDT for crypto:** BTCUSD → BTCUSDT (if BTC/ETH)
5. **Lowercase:** BTCUSDT → btcusdt
6. **Output:** Binance-compatible symbol

---

## 🔍 Examples by Symbol Type

### Crypto (Bitcoin)

```python
# From phone
"Analyse BTCUSD"  # ← You say this

# Desktop agent automatically:
# 1. MT5 analysis uses: "BTCUSDc"
# 2. Binance feed uses: "btcusdt"
# 3. Offset synced between both

# Result: Seamless integration ✅
```

### Commodity (Gold)

```python
# From phone
"Analyse XAUUSD"  # ← You say this

# Desktop agent automatically:
# 1. MT5 analysis uses: "XAUUSDc"
# 2. Binance feed uses: "xauusd"
# 3. No USDT conversion needed

# Result: Direct mapping ✅
```

### Forex (Pound/Yen)

```python
# From phone
"Analyse GBPJPY"  # ← You say this

# Desktop agent automatically:
# 1. MT5 analysis uses: "GBPJPYc"
# 2. Binance feed uses: "gbpjpy"
# 3. Cross pair, no USD conversion

# Result: Perfect sync ✅
```

---

## 🚦 What Happens Behind the Scenes

### When You Say: "Analyse BTCUSD"

1. **Phone GPT** → sends `tool: "moneybot.analyse_symbol"`, `arguments: {"symbol": "BTCUSD"}`

2. **Command Hub** → routes to desktop agent

3. **Desktop Agent** → receives "BTCUSD"
   ```python
   # Internal conversions:
   mt5_symbol = "BTCUSDc"    # For MT5 operations
   binance_symbol = "btcusdt"  # For Binance feed
   ```

4. **MT5 Analysis**
   ```python
   mt5_service.get_quote("BTCUSDc")       # Get current price
   indicator_bridge.get_multi("BTCUSDc")  # Get indicators
   decision_engine.decide_trade("BTCUSDc") # Generate signal
   ```

5. **Binance Validation**
   ```python
   binance_service.get_latest_price("btcusdt")    # Get Binance price
   binance_service.get_feed_health("btcusdt")     # Check feed quality
   sync_manager.get_current_offset("btcusdt")     # Get price offset
   ```

6. **Pre-Execution Validation**
   ```python
   # If you then say "Execute"
   signal_prefilter.adjust_and_validate(
       symbol="BTCUSDc",           # MT5 format
       signal=recommendation,       # Original signal
       mt5_quote=current_quote      # Current MT5 prices
   )
   # Automatically adjusts signal based on Binance offset
   ```

7. **MT5 Execution**
   ```python
   mt5.order_send({
       "symbol": "BTCUSDc",           # Correct MT5 symbol
       "entry": adjusted_entry,        # Adjusted for offset
       "sl": adjusted_sl,             # Adjusted for offset
       "tp": adjusted_tp              # Adjusted for offset
   })
   ```

---

## ⚙️ Configuration

### Current Configuration (desktop_agent.py)

```python
symbols_to_stream = [
    "btcusdt",   # → BTCUSDc on MT5
    "xauusd",    # → XAUUSDc on MT5
    "eurusd",    # → EURUSDc on MT5
    "gbpusd",    # → GBPUSDc on MT5
    "usdjpy",    # → USDJPYc on MT5
    "gbpjpy",    # → GBPJPYc on MT5
    "eurjpy"     # → EURJPYc on MT5
]
```

### Conversion Logic (infra/binance_service.py)

```python
def _convert_to_mt5_symbol(self, binance_symbol: str) -> str:
    """
    Smart conversion handles all input formats:
    - BTCUSD → BTCUSDc
    - btcusdt → BTCUSDc
    - BTCUSDc → BTCUSDc (already correct)
    """
    symbol = binance_symbol.upper()
    
    if symbol.endswith("USDT"):
        symbol = symbol.replace("USDT", "USD")
    
    if symbol.endswith("C"):
        symbol = symbol[:-1]  # Normalize
    
    if not symbol.endswith("c"):
        symbol += "c"
    
    return symbol
```

---

## ✅ Verification

### Run Test Anytime

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python test_symbol_mapping.py
```

**Expected output:**
```
✅ ALL TESTS PASSED!
✓ Binance symbols will correctly map to MT5 symbols ending in 'c'
✓ MT5 symbols will correctly map back to Binance symbols
✓ User inputs (from phone) will be handled correctly
✓ All 7 configured symbols are properly mapped
```

---

## 🎓 Best Practices

### From Your Phone

**✅ DO:**
- Use simple names: "BTCUSD", "EURUSD", "GBPJPY"
- System handles conversion automatically
- Works with or without 'c' suffix

**❌ DON'T:**
- Don't worry about exact format
- Don't add 'c' manually (but okay if you do)
- Don't use Binance format (btcusdt) - system converts anyway

### Examples

```
✅ "Analyse BTCUSD"     → Works perfectly
✅ "Analyse BTCUSDc"    → Works perfectly  
✅ "Analyse btcusd"     → Works perfectly
✅ "Analyse GBPJPY"     → Works perfectly
✅ "Check feed EURUSD"  → Works perfectly
```

---

## 🔧 Troubleshooting

### Issue: "Symbol not found"

**Cause:** Symbol not in Binance streaming list  
**Solution:** Add to `desktop_agent.py` symbols list

### Issue: "No MT5 quote available"

**Cause:** MT5 symbol doesn't end in 'c'  
**Solution:** Automatic conversion handles this now ✅

### Issue: "Offset not available"

**Cause:** Need both Binance and MT5 data  
**Solution:** Wait 15-30 seconds after startup

---

## 📊 Summary

✅ **7 symbols** fully mapped and tested  
✅ **Bidirectional conversion** (Binance ↔ MT5)  
✅ **Case insensitive** user input  
✅ **Handles all formats** automatically  
✅ **Zero data loss** in round-trip conversion  
✅ **Production ready** and verified

**Your system seamlessly bridges Binance (for real-time data) and MT5 (for execution) without any manual symbol management required!** 🚀

---

**Need to add a new symbol?**

1. Add Binance format to `desktop_agent.py`
2. Run `test_symbol_mapping.py` to verify
3. Restart desktop agent
4. Done! ✅

