# ✅ Dynamic Lot Sizing - COMPLETE

## 🎯 What Was Implemented

Your trading bot now has **intelligent, risk-based lot sizing** that automatically calculates the optimal position size for each trade based on:

- ✅ Symbol category (CRYPTO, METAL, FOREX)
- ✅ Account equity
- ✅ Stop loss distance
- ✅ Symbol-specific risk parameters
- ✅ Maximum lot caps per symbol

---

## 📊 Lot Sizing Configuration

### **CRYPTO (Higher Volatility → Lower Risk %)**
| Symbol | Max Lot | Default Risk % |
|--------|---------|----------------|
| BTCUSDc | 0.02 | 0.75% |

### **METALS (Medium Volatility → Medium Risk %)**
| Symbol | Max Lot | Default Risk % |
|--------|---------|----------------|
| XAUUSDc | 0.02 | 1.0% |

### **FOREX (Lower Volatility → Higher Risk %)**
| Symbol | Max Lot | Default Risk % |
|--------|---------|----------------|
| EURUSDc | 0.04 | 1.25% |
| GBPUSDc | 0.04 | 1.25% |
| USDJPYc | 0.04 | 1.25% |
| GBPJPYc | 0.04 | 1.0% (more volatile) |
| EURJPYc | 0.04 | 1.0% (more volatile) |

---

## 🔧 How It Works

### **Formula:**
```
lot_size = (equity × risk_pct / 100) / (stop_distance_in_ticks × tick_value)
```

### **Example: BTCUSD Trade**

**Scenario:**
- Account Equity: $10,000
- Entry: 65,000
- Stop Loss: 64,800
- Stop Distance: 200 points
- Risk %: 0.75% (default for BTC)

**Calculation:**
```
Risk Amount = $10,000 × 0.75% = $75
Stop Distance = 200 points
Tick Value = $1 per point (for BTC)

Lot Size = $75 / (200 × $1) = 0.375 lots

Capped to Max: 0.02 lots (BTC maximum)
Final Lot Size: 0.02 lots
```

---

## 🚀 Usage

### **Option 1: Automatic (Recommended)**

**Just don't specify volume when executing:**

```
execute btcusd buy at 65000, sl 64800, tp 65400
```

**System automatically:**
1. Gets your account equity
2. Calculates stop distance
3. Applies symbol-specific risk %
4. Caps at symbol maximum
5. Executes with calculated lot size

**You'll see:**
```
📊 Calculated lot size: 0.02 (Risk-based, Equity=$10,000.00)
💰 Executing BUY BTCUSDc @ 0.02 lots
```

---

### **Option 2: Manual Override**

**Specify volume if you want:**

```
execute btcusd buy at 65000, sl 64800, tp 65400, volume 0.01
```

**System uses your specified volume** (still capped by broker limits).

---

### **Option 3: Custom Risk %**

**Override the default risk percentage:**

```
execute eurusd buy at 1.1000, sl 1.0980, tp 1.1040, risk_pct 2.0
```

**System calculates lot size using 2.0% risk instead of default 1.25%.**

---

## 📱 New Tool: Check Lot Sizing

**Via Phone ChatGPT:**

```
check lot sizing for btcusd
```

**Response:**
```
📊 Lot Sizing for BTCUSDc

Category: CRYPTO
Max Lot Size: 0.02
Default Risk %: 0.75%
Min Lot Size: 0.01

💡 When you execute a trade without specifying volume,
the system will calculate the optimal lot size based on:
  • Your account equity
  • Stop loss distance
  • Symbol risk percentage (0.75%)
  • Maximum lot cap (0.02 lots)
```

---

**Or check all symbols:**

```
show lot sizing configuration
```

**Response:**
```
📊 Lot Sizing Configuration

💰 CRYPTO:
  BTCUSDc: Max 0.02 lots, Risk 0.75%

🥇 METALS:
  XAUUSDc: Max 0.02 lots, Risk 1.0%

💱 FOREX:
  EURUSDc: Max 0.04 lots, Risk 1.25%
  GBPUSDc: Max 0.04 lots, Risk 1.25%
  USDJPYc: Max 0.04 lots, Risk 1.25%
  GBPJPYc: Max 0.04 lots, Risk 1.0%
  EURJPYc: Max 0.04 lots, Risk 1.0%

💡 Automatic Lot Sizing:
When you execute trades without specifying volume, the system
calculates the optimal lot size based on your equity, stop
distance, and symbol-specific risk parameters.
```

---

## 📁 Files Created/Modified

### **✅ New Files:**
1. **`config/lot_sizing.py`** - Complete lot sizing module
   - Symbol-specific configuration
   - Risk-based calculation functions
   - Helper utilities

### **✅ Modified Files:**
1. **`desktop_agent.py`**
   - Added `get_lot_size` import
   - Updated `tool_execute_trade` for automatic lot sizing
   - Added `tool_lot_sizing_info` for checking configuration

---

## 🎯 Benefits

### **1. Risk Management**
- ✅ Consistent risk per trade across all symbols
- ✅ Accounts for symbol volatility (crypto vs forex)
- ✅ Prevents over-leveraging

### **2. Simplicity**
- ✅ No need to calculate lot sizes manually
- ✅ Just specify entry/SL/TP
- ✅ System handles the rest

### **3. Flexibility**
- ✅ Can still manually override if needed
- ✅ Can adjust risk % per trade
- ✅ Respects broker minimums and maximums

### **4. Safety**
- ✅ Hard caps per symbol prevent mistakes
- ✅ Minimum lot size enforced
- ✅ Validates calculations before execution

---

## 🧪 Testing

### **Test 1: BTCUSD (Crypto)**

**Command:**
```
execute btcusd buy at 65000, sl 64800, tp 65400
```

**Expected:**
- Calculates lot size based on 0.75% risk
- Caps at 0.02 lots maximum
- Logs: "📊 Calculated lot size: 0.02 (Risk-based)"

---

### **Test 2: EURUSD (Forex)**

**Command:**
```
execute eurusd buy at 1.1000, sl 1.0980, tp 1.1040
```

**Expected:**
- Calculates lot size based on 1.25% risk
- Caps at 0.04 lots maximum
- Logs: "📊 Calculated lot size: 0.04 (Risk-based)"

---

### **Test 3: Manual Override**

**Command:**
```
execute xauusd buy at 3950, sl 3940, tp 3970, volume 0.01
```

**Expected:**
- Uses specified 0.01 lots
- Logs: "📊 Using provided lot size: 0.01"

---

## 🔧 Customization

### **To Change Maximum Lot Sizes:**

Edit `config/lot_sizing.py`:

```python
MAX_LOT_SIZES: Dict[str, float] = {
    "BTCUSDc": 0.03,  # Change from 0.02 to 0.03
    "XAUUSDc": 0.03,  # Change from 0.02 to 0.03
    "EURUSDc": 0.05,  # Change from 0.04 to 0.05
    # ...
}
```

---

### **To Change Default Risk %:**

Edit `config/lot_sizing.py`:

```python
DEFAULT_RISK_PCT: Dict[str, float] = {
    "BTCUSDc": 1.0,   # Change from 0.75% to 1.0%
    "XAUUSDc": 1.5,   # Change from 1.0% to 1.5%
    "EURUSDc": 1.5,   # Change from 1.25% to 1.5%
    # ...
}
```

---

### **To Add New Symbols:**

Edit `config/lot_sizing.py`:

```python
MAX_LOT_SIZES: Dict[str, float] = {
    # ... existing symbols ...
    
    # Add new symbol
    "ETHUSDc": 0.02,
    "ETHUSD": 0.02,
}

DEFAULT_RISK_PCT: Dict[str, float] = {
    # ... existing symbols ...
    
    # Add new symbol
    "ETHUSDc": 0.75,
    "ETHUSD": 0.75,
}
```

**Then restart `desktop_agent.py`.**

---

## ⚠️ Important Notes

### **1. Restart Required**

After making changes to `config/lot_sizing.py`, **restart `desktop_agent.py`**:

```powershell
# Stop desktop_agent.py (Ctrl+C)
# Then restart:
cd C:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

---

### **2. Broker Limits**

The system respects:
- ✅ Minimum lot size (0.01)
- ✅ Maximum lot size (per symbol config)
- ✅ Broker-specific lot step sizes

---

### **3. Account Currency**

The system automatically handles:
- ✅ USD accounts
- ✅ Cent accounts (USC, EUC, etc.)
- ✅ Different base currencies

---

## 📊 Real-World Example

### **Your Current Setup:**

**Account:** $10,000 equity

**Trade 1: BTCUSD**
- Entry: 65,000
- SL: 64,800 (200 points)
- Risk: 0.75% = $75
- **Lot Size: 0.02** (capped at max)

**Trade 2: XAUUSD**
- Entry: 3,950
- SL: 3,940 (10 points)
- Risk: 1.0% = $100
- **Lot Size: 0.02** (capped at max)

**Trade 3: EURUSD**
- Entry: 1.1000
- SL: 1.0980 (20 pips)
- Risk: 1.25% = $125
- **Lot Size: 0.04** (capped at max)

**Total Risk:** $75 + $100 + $125 = $300 (3% of equity)

---

## ✅ Status

- ✅ Lot sizing module created (`config/lot_sizing.py`)
- ✅ Desktop agent updated (`desktop_agent.py`)
- ✅ Automatic calculation integrated
- ✅ Manual override supported
- ✅ New tool added (`moneybot.lot_sizing_info`)
- ✅ Symbol-specific configuration complete
- ✅ Risk-based formula implemented
- ✅ Maximum caps enforced
- ⏳ **Restart `desktop_agent.py` to activate**

---

## 🚀 Next Steps

1. **Restart Desktop Agent:**
   ```powershell
   cd C:\mt5-gpt\TelegramMoneyBot.v7
   python desktop_agent.py
   ```

2. **Test on Phone ChatGPT:**
   ```
   check lot sizing configuration
   ```

3. **Execute a Test Trade:**
   ```
   analyse btcusd
   execute (let it calculate lot size automatically)
   ```

4. **Verify in Logs:**
   - Look for "📊 Calculated lot size: X.XX (Risk-based)"
   - Confirm it matches your expectations

---

**Your bot now intelligently sizes positions based on risk! 🎯✅**

