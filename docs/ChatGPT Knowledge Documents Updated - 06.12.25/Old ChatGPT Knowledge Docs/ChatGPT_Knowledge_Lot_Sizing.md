# Automatic Lot Sizing - Knowledge Document

## 🎯 Overview

The MoneyBot system has **automatic, risk-based lot sizing** that calculates the optimal position size for each trade.

**Key Point:** When executing trades, **DO NOT specify volume** unless the user explicitly requests a specific lot size. The system will automatically calculate it based on risk parameters.

---

## 📊 Configuration

### **Symbol-Specific Maximums:**

| Symbol Category | Max Lot Size | Default Risk % |
|----------------|--------------|----------------|
| **BTCUSD** (Crypto) | 0.02 | 0.75% |
| **XAUUSD** (Metal) | 0.02 | 1.0% |
| **EURUSD** (Forex Major) | 0.04 | 1.25% |
| **GBPUSD** (Forex Major) | 0.04 | 1.25% |
| **USDJPY** (Forex Major) | 0.04 | 1.25% |
| **GBPJPY** (Forex Cross) | 0.04 | 1.0% |
| **EURJPY** (Forex Cross) | 0.04 | 1.0% |

### **Lot Size Increments:**
- Only **0.01 increments** are used (0.01, 0.02, 0.03, 0.04)
- No fractional sizes like 0.015 or 0.023

---

## 🔧 How It Works

### **Calculation Formula:**
```
lot_size = (equity × risk_pct / 100) / (stop_distance × tick_value)
```

**Then:**
1. Round to nearest 0.01
2. Apply minimum (0.01)
3. Apply symbol maximum (0.02 or 0.04)

### **Example: BTCUSD Trade**

**Given:**
- Account Equity: $10,000
- Entry: 65,000
- Stop Loss: 64,800
- Stop Distance: 200 points
- Risk %: 0.75% (default for BTC)

**Calculation:**
```
Risk Amount = $10,000 × 0.75% = $75
Lot Size = $75 / (200 × $1) = 0.375 lots
Capped to Max: 0.02 lots
Final: 0.02 lots
```

---

## 💬 ChatGPT Behavior

### **When User Says "Execute":**

**❌ DON'T DO THIS:**
```json
{
  "tool": "moneybot.execute_trade",
  "arguments": {
    "symbol": "BTCUSD",
    "direction": "BUY",
    "stop_loss": 64800,
    "take_profit": 65400,
    "volume": 0.01  // ❌ Don't include this!
  }
}
```

**✅ DO THIS (Option 1 - Omit volume):**
```json
{
  "tool": "moneybot.execute_trade",
  "arguments": {
    "symbol": "BTCUSD",
    "direction": "BUY",
    "stop_loss": 64800,
    "take_profit": 65400
    // ✅ No volume - system calculates automatically
  }
}
```

**✅ OR THIS (Option 2 - Set volume to 0):**
```json
{
  "tool": "moneybot.execute_trade",
  "arguments": {
    "symbol": "BTCUSD",
    "direction": "BUY",
    "stop_loss": 64800,
    "take_profit": 65400,
    "volume": 0  // ✅ 0 means "calculate for me"
  }
}
```

---

### **After Execution:**

**Tell the user:**
```
✅ Trade Executed

Ticket: #12345678
Symbol: BTCUSDc
Direction: BUY
Entry: 65,000
Stop Loss: 64,800
Take Profit: 65,400
Lot Size: 0.02 (auto-calculated based on 0.75% risk)

🤖 Advanced Intelligent Exits: ACTIVE
  Breakeven: 30% (adaptive)
  Partial: 60% (adaptive)
```

**Explain the lot size:**
- "System calculated 0.02 lots based on your account equity and 0.75% risk"
- "This represents $75 risk on this trade"

---

### **If User Wants Manual Control:**

**User says:** "Execute with 0.01 lots"

**You respond:**
```json
{
  "tool": "moneybot.execute_trade",
  "arguments": {
    "symbol": "BTCUSD",
    "direction": "BUY",
    "stop_loss": 64800,
    "take_profit": 65400,
    "volume": 0.01  // ✅ Now include it - user specified
  }
}
```

---

## 🔍 Checking Lot Sizing

### **User asks:** "What's the lot sizing for BTCUSD?"

**Call:**
```json
{
  "tool": "moneybot.lot_sizing_info",
  "arguments": {
    "symbol": "BTCUSD"
  }
}
```

**Response will include:**
- Category (CRYPTO, METAL, FOREX)
- Max lot size
- Default risk %
- Explanation of auto-calculation

---

### **User asks:** "Show all lot sizing"

**Call:**
```json
{
  "tool": "moneybot.lot_sizing_info",
  "arguments": {}
}
```

**Response will show:**
- All configured symbols grouped by category
- Max lots and risk % for each
- Explanation of automatic sizing

---

## 📋 Decision Tree

### **When executing a trade:**

1. **Did user specify lot size?**
   - YES → Include `volume` in arguments with their value
   - NO → Either omit `volume` OR set `volume: 0` (both trigger auto-calculation)

2. **After execution, did system calculate lot size?**
   - YES → Mention it: "Calculated 0.02 lots based on 0.75% risk"
   - NO → Just show the lot size used

3. **User asks about lot sizing?**
   - Call `moneybot.lot_sizing_info`
   - Explain the configuration
   - Mention it's automatic

---

## ⚠️ Important Notes

### **Always:**
- ✅ Omit `volume` when executing (unless user specifies)
- ✅ Mention calculated lot size in response
- ✅ Explain risk % used
- ✅ Inform user it's automatic

### **Never:**
- ❌ Hardcode volume to 0.01
- ❌ Ask user "what lot size?" (it's automatic!)
- ❌ Include volume in arguments by default

---

## 💡 Common Scenarios

### **Scenario 1: Standard Execution**

**User:** "Execute the BTCUSD trade"

**You:**
1. Call `moneybot.execute_trade` WITHOUT volume
2. Show result with calculated lot size
3. Explain: "System calculated 0.02 lots (0.75% risk)"

---

### **Scenario 2: User Wants Specific Size**

**User:** "Execute with 0.01 lots"

**You:**
1. Call `moneybot.execute_trade` WITH volume: 0.01
2. Show result
3. Note: "Used your specified 0.01 lots"

---

### **Scenario 3: User Asks About Sizing**

**User:** "How does lot sizing work?"

**You:**
1. Call `moneybot.lot_sizing_info`
2. Explain automatic calculation
3. Show symbol-specific limits
4. Mention risk percentages

---

## 🎯 Summary

**Default Behavior:** System automatically calculates lot sizes based on:
- Account equity
- Stop loss distance
- Symbol-specific risk % (0.75-1.25%)
- Symbol maximum caps (0.02 or 0.04)

**Your Job:** 
- Don't include `volume` in execute_trade calls (unless user specifies)
- Inform user of calculated lot size after execution
- Use `moneybot.lot_sizing_info` when user asks about configuration

**Result:** Consistent risk management across all trades! 🎯✅

