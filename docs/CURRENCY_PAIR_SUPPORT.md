# Currency Pair Support & Feature Coverage

## ✅ Full Feature Support

The integration works for **ALL currency pairs**, with different levels of sophistication depending on the pair type.

---

## 🎯 Pair-Specific Macro Bias Rules

### **Optimized Pairs (7 Active Symbols)**

These pairs have **custom macro bias calculations** with pair-specific factors:

| Pair | Macro Factors | Real Yield | NASDAQ Correlation | Special Features |
|------|--------------|------------|-------------------|------------------|
| **XAUUSD** | DXY, US10Y, Real Yield, VIX | ✅ Yes | ❌ N/A | Real yield calculation (1.72% current - bearish) |
| **BTCUSD** | NASDAQ, VIX, DXY | ❌ N/A | ✅ Yes (0.70 correlation) | Risk-on/risk-off sentiment |
| **EURUSD** | DXY (primary) | ❌ N/A | ❌ N/A | USD strength mirror |
| **GBPUSD** | DXY (primary) | ❌ N/A | ❌ N/A | USD strength mirror |
| **USDJPY** | US-JP yield spread, DXY | ❌ N/A | ❌ N/A | Yield differential tracking |
| **GBPJPY** | VIX, US10Y (risk sentiment) | ❌ N/A | ❌ N/A | Carry trade risk sentiment |
| **EURJPY** | VIX, US10Y (risk sentiment) | ❌ N/A | ❌ N/A | Carry trade risk sentiment |

### **How It Works:**

1. **Gold (XAUUSD):**
   - Uses **real yield** (US10Y nominal - breakeven inflation) for accurate macro bias
   - Real yield > 1.5% = bearish headwind
   - Real yield < 0.5% = bullish tailwind
   - **Current:** 1.72% (elevated) → Bearish macro bias

2. **Bitcoin (BTCUSD):**
   - Uses **NASDAQ correlation** (risk-on proxy)
   - Strong correlation (0.70) amplifies NASDAQ signals
   - VIX (risk sentiment) also factored

3. **USD Pairs (EURUSD, GBPUSD):**
   - **DXY mirror** (primary driver)
   - DXY up = bearish for EUR/GBP
   - DXY down = bullish for EUR/GBP

4. **Yen Pairs (USDJPY, GBPJPY, EURJPY):**
   - **Yield differentials** (USDJPY)
   - **Risk sentiment** via VIX (cross pairs)
   - Fed expectations tracked

---

## 🔄 Generic Fallback (All Other Pairs)

For **any pair not in the optimized list**, the system uses:

```python
_calculate_generic_bias(symbol)
```

**Features:**
- ✅ DXY-based bias (works for all USD pairs)
- ✅ Volatility forecasting (EXPANDING/CONTRACTING/STABLE)
- ✅ Liquidity analysis (equal highs/lows, sweeps, HVN/LVN)
- ✅ Order flow (if Binance available)
- ⚠️ Generic macro bias (DXY trend only, no pair-specific factors)

**Example:**
- `AUDUSD` → Uses DXY trend (moderate sophistication)
- `USDCAD` → Uses DXY trend (moderate sophistication)
- `NZDUSD` → Uses DXY trend (moderate sophistication)

---

## ✅ Universal Features (Work for ALL Pairs)

These features work identically for **every currency pair**:

1. **Volatility Forecasting**
   - ✅ ATR momentum calculation
   - ✅ BB width percentile
   - ✅ Volatility signal (EXPANDING/CONTRACTING/STABLE)
   - ✅ Range probability

2. **Liquidity Analysis**
   - ✅ Equal highs/lows detection
   - ✅ Liquidity sweeps
   - ✅ HVN/LVN (volume profile proxy)
   - ✅ Stop cluster warnings

3. **Order Flow** (conditional on Binance)
   - ✅ Whale activity detection
   - ✅ Order book imbalance
   - ✅ Liquidity void detection
   - ⚠️ Only for pairs with Binance data (BTC, major FX)

4. **Technical Analysis**
   - ✅ All indicators (RSI, MACD, ADX, EMAs, etc.)
   - ✅ SMC structure (CHOCH, BOS)
   - ✅ Advanced features (RMAG, VWAP, FVG)

---

## 📊 Current Coverage Status

### **7 Active Symbols:**
- ✅ **BTCUSD** - Full features + NASDAQ correlation
- ✅ **XAUUSD** - Full features + Real yield
- ✅ **EURUSD** - Full features + DXY bias
- ✅ **GBPUSD** - Full features + DXY bias
- ✅ **USDJPY** - Full features + Yield spread
- ✅ **GBPJPY** - Full features + Risk sentiment
- ✅ **EURJPY** - Full features + Risk sentiment

### **Other Pairs:**
- ✅ **Any FX pair** - DXY-based generic bias + all technical features
- ✅ **Any crypto** - DXY-based generic bias + all technical features (no NASDAQ correlation unless added)

---

## 🚀 Adding New Pairs

### **To Add Pair-Specific Rules:**

Edit `infra/macro_bias_calculator.py`:

```python
def calculate_bias(self, symbol: str) -> Dict[str, Any]:
    symbol_normalized = symbol.upper().replace('C', '')
    
    if symbol_normalized == 'XAUUSD':
        return self._calculate_gold_bias()
    # ... existing pairs ...
    elif symbol_normalized == 'AUDUSD':  # NEW PAIR
        return self._calculate_audusd_bias()
    else:
        return self._calculate_generic_bias(symbol_normalized)

def _calculate_audusd_bias(self) -> Dict[str, Any]:
    """Custom bias for AUDUSD (commodity currency)"""
    # Use DXY + commodity sentiment
    # ...
```

### **Generic Bias is Sufficient For:**
- Most USD pairs (EUR, GBP, AUD, NZD, CAD, CHF)
- Most major crosses (once USD pairs are covered)
- Exotic pairs (won't have specific rules but will still work)

---

## 💡 Recommendations

1. **For Optimized Pairs (7 active):**
   - ✅ Full macro context available
   - ✅ Most accurate bias scores
   - ✅ Pair-specific factors considered

2. **For Other Pairs:**
   - ✅ Still get DXY-based bias (useful)
   - ✅ All technical features work
   - ✅ Volatility forecasting works
   - ⚠️ Missing pair-specific macro factors (can be added later)

3. **Adding New Pairs to Optimized List:**
   - Identify key macro drivers for the pair
   - Add custom calculation method
   - Test with real data

---

## 📈 Example: Generic Pair Analysis

**Input:** `AUDUSD` (not in optimized list)

**Output:**
- ✅ Macro Bias: `-0.50` (DXY strengthening)
- ✅ Volatility Signal: `EXPANDING`
- ✅ Liquidity: Equal highs detected
- ✅ Order Flow: Neutral (if Binance unavailable)
- ⚠️ No pair-specific factors (AUD commodity correlation, RBA rate, etc.)

**Still Useful:** ✅ Yes - DXY bias is a strong proxy for most USD pairs.

---

## ✅ Conclusion

**Yes, it works for all currency pairs!**

- **7 optimized pairs:** Full sophisticated macro bias with pair-specific factors
- **All other pairs:** Generic DXY-based bias + all technical features
- **Universal features:** Volatility, liquidity, order flow work for all pairs
- **Extensible:** Easy to add pair-specific rules for new pairs

The system gracefully handles any symbol and provides the best analysis available, with fallbacks to generic methods when pair-specific rules don't exist.

