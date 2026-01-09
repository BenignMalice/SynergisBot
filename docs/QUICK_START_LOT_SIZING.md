# 🚀 Quick Start - Dynamic Lot Sizing

## ✅ What Changed

Your bot now **automatically calculates lot sizes** based on risk!

### **New Lot Sizes:**
- **BTCUSD/XAUUSD:** Max 0.02 lots (was 0.01)
- **Forex pairs:** Max 0.04 lots (was 0.01)

### **How It Works:**
When you execute a trade **without specifying volume**, the system calculates it based on:
- Your account equity
- Stop loss distance
- Symbol-specific risk % (0.75-1.25%)

---

## 🎯 Usage

### **Before (Manual):**
```
execute btcusd buy at 65000, sl 64800, tp 65400, volume 0.01
```

### **Now (Automatic):**
```
execute btcusd buy at 65000, sl 64800, tp 65400
```

**System automatically calculates and uses optimal lot size!**

---

## 📊 Configuration

| Symbol | Max Lot | Risk % |
|--------|---------|--------|
| BTCUSD | 0.02 | 0.75% |
| XAUUSD | 0.02 | 1.0% |
| EURUSD | 0.04 | 1.25% |
| GBPUSD | 0.04 | 1.25% |
| USDJPY | 0.04 | 1.25% |
| GBPJPY | 0.04 | 1.0% |
| EURJPY | 0.04 | 1.0% |

---

## 🔧 Activation

**Restart desktop agent:**
```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

---

## 🧪 Test It

**On your phone ChatGPT:**
```
check lot sizing configuration
```

**Then execute a trade:**
```
analyse btcusd
execute
```

**Look for:**
```
📊 Calculated lot size: 0.02 (Risk-based, Equity=$10,000.00)
💰 Executing BUY BTCUSDc @ 0.02 lots
```

---

## 💡 Tips

1. **Still want manual control?** Just specify `volume`:
   ```
   execute btcusd buy at 65000, sl 64800, tp 65400, volume 0.01
   ```

2. **Want different risk %?** Specify `risk_pct`:
   ```
   execute eurusd buy at 1.1000, sl 1.0980, tp 1.1040, risk_pct 2.0
   ```

3. **Check configuration anytime:**
   ```
   check lot sizing for btcusd
   ```

---

**Full details:** See `LOT_SIZING_COMPLETE.md` 📄

