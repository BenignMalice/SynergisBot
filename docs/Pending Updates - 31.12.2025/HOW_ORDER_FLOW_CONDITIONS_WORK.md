# How Order Flow Conditions Work - Automatic vs Manual

**Date:** 2025-12-30  
**Question:** Will order flow conditions work automatically or do I need to specify them to ChatGPT?

---

## ✅ **Two Ways It Works**

### **1. Automatic Pattern Matching** (Semi-Automatic)

**How It Works:**
- ChatGPT analyzes BTCUSD and sees order flow signals in the analysis
- When ChatGPT writes the plan's `reasoning/notes` field, it may mention order flow terms
- **Pattern matching rules automatically detect keywords** and add conditions

**Keywords That Auto-Trigger:**
- "CVD divergence" → Adds `cvd_div_bear: true` or `cvd_div_bull: true`
- "delta divergence" → Adds `delta_divergence_bull: true` or `delta_divergence_bear: true`
- "absorption zone" → Adds `avoid_absorption_zones: true` or `absorption_zone_detected: true`
- "order flow" or "CVD" → Adds `delta_positive`, `cvd_rising`, etc.

**Example:**
```
User: "Create a SELL plan for BTCUSD if CVD divergence bearish is detected"

ChatGPT reasoning: "SELL plan waiting for bearish CVD divergence signal..."

→ Pattern matching detects "CVD divergence bearish"
→ Automatically adds: {"cvd_div_bear": true, "price_near": 88000, "tolerance": 200}
```

**Limitation:**
- Only works if ChatGPT mentions the keywords in reasoning/notes
- ChatGPT might not always mention order flow terms even if signals are present
- Pattern matching is keyword-based, not signal-based

---

### **2. Explicit Instructions** (More Reliable)

**How It Works:**
- You explicitly tell ChatGPT to use order flow conditions
- ChatGPT will check order flow metrics and add appropriate conditions
- More reliable than pattern matching

**Example Requests:**
```
✅ "Create a BUY plan for BTCUSD with order flow confirmation"
✅ "Create a SELL plan if CVD divergence bearish is detected"
✅ "Create a plan at absorption zone with buying pressure"
✅ "Create a plan with delta divergence bullish condition"
```

**What ChatGPT Will Do:**
1. Check `moneybot.btc_order_flow_metrics` (or use data from `analyse_symbol_full`)
2. See the order flow signals
3. Add appropriate conditions based on your request

---

## 🎯 **Best Practice: Hybrid Approach**

### **Recommended Workflow:**

1. **Ask ChatGPT to analyze BTCUSD:**
   ```
   "Analyze BTCUSD for a trade setup"
   ```

2. **ChatGPT will automatically:**
   - Call `moneybot.analyse_symbol_full` (includes BTC order flow metrics)
   - See order flow signals in the analysis
   - Mention them in the analysis output

3. **Then explicitly request order flow conditions:**
   ```
   "Create a BUY plan with order flow confirmation"
   OR
   "Create a SELL plan if CVD divergence is detected"
   ```

4. **ChatGPT will:**
   - Use the order flow data it already has
   - Add appropriate conditions based on your request
   - Pattern matching will also trigger if keywords are mentioned

---

## 📊 **What's Automatic vs Manual**

### **✅ Fully Automatic:**
- **Order flow data collection**: BTC order flow metrics are automatically included in `analyse_symbol_full` for BTCUSD
- **Condition monitoring**: Once conditions are in the plan, the system automatically monitors them every 5 seconds
- **Pattern matching**: If ChatGPT mentions keywords, conditions are automatically added

### **⚠️ Semi-Automatic (Requires ChatGPT Recognition):**
- **Condition addition**: ChatGPT needs to recognize order flow signals as actionable
- **Keyword detection**: Pattern matching only works if ChatGPT mentions the keywords

### **🔧 Manual (You Need to Request):**
- **Explicit condition requests**: If you want specific conditions, explicitly ask for them
- **Strategy selection**: You may need to guide ChatGPT on which conditions to use

---

## 💡 **Examples of What to Say**

### **For Basic Order Flow:**
```
✅ "Create a BUY plan with buying pressure confirmation"
✅ "Create a SELL plan with selling pressure confirmation"
✅ "Create a plan with CVD rising condition"
```

### **For Divergence Detection:**
```
✅ "Create a SELL plan if CVD divergence bearish is detected"
✅ "Create a BUY plan if delta divergence bullish is detected"
✅ "Create a plan waiting for CVD divergence signal"
```

### **For Absorption Zones:**
```
✅ "Create a BUY plan at absorption zone with buying pressure"
✅ "Create a plan avoiding absorption zones"
✅ "Create a plan at absorption zone detected level"
```

### **Combined Conditions:**
```
✅ "Create a BUY plan with order flow confirmation: delta positive, CVD rising, and absorption zone detected"
✅ "Create a SELL plan if CVD divergence bearish and avoid absorption zones"
```

---

## 🎯 **Summary**

**Will it work automatically?**
- **Partially**: Pattern matching will auto-trigger if ChatGPT mentions keywords
- **But**: ChatGPT might not always mention order flow terms even when signals are present
- **Best**: Explicitly request order flow conditions for more reliable results

**What you should do:**
1. ✅ Let ChatGPT analyze BTCUSD (it will see order flow data automatically)
2. ✅ Explicitly request order flow conditions when creating plans
3. ✅ Use specific terms like "CVD divergence", "delta divergence", "absorption zone"
4. ✅ Pattern matching will also help if ChatGPT mentions these terms

**The system will automatically:**
- ✅ Monitor all order flow conditions once they're in the plan
- ✅ Check conditions every 5 seconds for order flow plans
- ✅ Execute when all conditions are met

**You need to:**
- 🔧 Explicitly request order flow conditions (more reliable)
- 🔧 Or rely on ChatGPT to mention keywords (less reliable)

---

## 📝 **Recommendation**

**For best results:**
1. Ask ChatGPT to analyze BTCUSD first
2. Review the order flow signals in the analysis
3. Explicitly request order flow conditions when creating plans:
   - "Create a BUY plan with order flow confirmation"
   - "Create a SELL plan if CVD divergence bearish is detected"
   - "Create a plan at absorption zone with buying pressure"

This ensures ChatGPT uses the order flow conditions reliably!
