# 📋 ChatGPT Instructions Update - Pending Order Analysis

## Overview

Your ChatGPT instructions file (`chatgpt_instructions.txt`) has been updated to include the new pending order analysis and modification capabilities.

---

## ✅ What Was Added

### **New Section: PENDING ORDER ANALYSIS & MODIFICATION**

This comprehensive section teaches ChatGPT how to:
1. Recognize when users want to analyze pending orders
2. Fetch and review all pending orders
3. Analyze each order against current market conditions
4. Modify orders when adjustments are needed
5. Explain the reasoning behind modifications

---

## 📝 Key Components Added

### **1. Trigger Phrases**
ChatGPT now recognizes these user requests:
- "Analyze my pending orders"
- "Review my limit orders"
- "Check if my pending orders are still good"
- "Re-evaluate my orders"
- "Update my bracket for current conditions"

### **2. Analysis Workflow**
5-step process:
1. Call `getPendingOrders()` to see all orders
2. Call `getCurrentPrice(symbol)` for each symbol
3. Analyze validity (entry, volatility, structure, R:R)
4. Call `modifyPendingOrder()` if adjustments needed
5. Explain WHY each change was made

### **3. Order Type Validation**
ChatGPT now validates:
- ✅ BUY LIMIT: Entry BELOW current price
- ✅ SELL LIMIT: Entry ABOVE current price
- ✅ BUY STOP: Entry ABOVE current price
- ✅ SELL STOP: Entry BELOW current price

### **4. What ChatGPT Checks**

#### **Entry Price Validity**
- Is entry still near support/resistance?
- Has price moved significantly away?
- Is entry at a key EMA level?

#### **Volatility Appropriateness**
- Compare SL distance to current ATR
- Has volatility increased? → Widen stops
- Has volatility decreased? → Tighten stops

**ATR Guidelines:**
- XAUUSDc (Gold): 2.0-3.0 ATR normal ($2-$3)
- BTCUSDc (Bitcoin): 100-200 ATR normal ($100-$200)
- Forex: 20-40 pips normal

#### **Market Structure Changes**
- Trend reversals (bullish → bearish)
- Breakouts from consolidation
- EMA crossovers

#### **Risk:Reward Ratio**
- Minimum 1.5:1 maintained
- TP extension opportunities
- SL tightening opportunities

### **5. Example Analysis**
Complete example showing:
- How to fetch orders
- How to analyze each one
- How to modify when needed
- How to explain changes to user

### **6. Common Scenarios**
4 typical situations with solutions:
1. **Market Moved Away** → Move entry closer
2. **Volatility Increased** → Widen stops
3. **Trend Reversed** → Cancel order
4. **Bracket Adjustment** → Keep favored side

### **7. Precision Rules**
Correct decimal precision for each instrument:
- XAUUSDc: 3 decimals (3938.500)
- BTCUSDc: 2 decimals (123456.78)
- Forex: 3 decimals (87.381)

### **8. Best Practices**
7 guidelines for optimal order management:
1. Review daily or after major moves
2. Check before news events
3. Widen stops during high volatility
4. Tighten stops during low volatility
5. Align orders with current trend
6. Maintain minimum 1.5:1 R:R
7. Use ATR for stop distances

### **9. Communication Format**
Structured format for presenting analysis:
```
📋 Pending Order Analysis

You have [N] pending orders:

🔍 [SYMBOL] [ORDER_TYPE] #[TICKET]
Current: [price] | Entry: [entry_price]
[✅ VALID / ❌ ISSUE]: [Analysis]
[✅ RECOMMENDATION / ⚠️ WARNING]: [Action]

[If modifying:]
🔧 Modifying order...
✅ Modified: [Changes made]
Reason: [Explanation]

📊 Summary:
• [N] orders modified
• [N] orders unchanged
• All orders aligned with current conditions
```

---

## 🔄 How to Update Your ChatGPT GPT

### **Option 1: Copy New Section**
1. Open your ChatGPT GPT configuration
2. Find the instructions section
3. Scroll to the end (after the price rules)
4. Copy the new "PENDING ORDER ANALYSIS & MODIFICATION" section
5. Paste it at the end
6. Save

### **Option 2: Replace Entire File**
1. Open `chatgpt_instructions.txt`
2. Copy all contents
3. Open your ChatGPT GPT configuration
4. Replace all instructions with the new content
5. Save

---

## 📊 Example Usage After Update

**User**: "Analyze my pending orders"

**ChatGPT** (with new instructions):
```
📋 Fetching pending orders...

You have 4 pending orders:

🔍 NZDJPY SELL STOP #117491393
Current: 87.381 | Entry: 87.300
❌ ISSUE: Entry too close to current price (only 81 points)
✅ RECOMMENDATION: Move entry to 87.250 for better placement

🔧 Modifying order...
✅ Modified SELL STOP #117491393:
• Entry: 87.300 → 87.250 (moved down 50 points)
• SL: 87.500 → 87.450 (tightened to maintain 2:1 R:R)
• TP: 87.000 (unchanged)

Reason: Market moved up, adjusting entry to better support level
and tightening SL to maintain risk:reward ratio.

🔍 NZDJPY BUY STOP #117491392
Current: 87.381 | Entry: 87.600
✅ VALID: Good placement above resistance
✅ SL distance appropriate (200 points = 0.82 ATR)
No changes needed.

🔍 AUDUSD BUY LIMIT #117482947
Current: 0.65948 | Entry: 0.65900
✅ VALID: Good entry near support (EMA20: 0.65920)
⚠️ WARNING: SL a bit tight (150 points = 0.81 ATR)
✅ RECOMMENDATION: Widen SL to 0.65700

🔧 Modifying order...
✅ Modified: SL 0.65750 → 0.65700

🔍 EURUSD SELL LIMIT #117482911
Current: 1.16634 | Entry: 1.16900
✅ VALID: Good entry at resistance
✅ SL/TP distances appropriate
No changes needed.

📊 Summary:
• 2 orders modified for better placement
• 2 orders remain unchanged (already optimal)
• All orders now aligned with current volatility
```

---

## 🎯 Benefits

With these updated instructions, ChatGPT will:
- ✅ Automatically recognize pending order analysis requests
- ✅ Follow a systematic analysis workflow
- ✅ Check all critical factors (entry, volatility, structure, R:R)
- ✅ Make intelligent modification decisions
- ✅ Explain reasoning clearly to the user
- ✅ Use correct precision for each instrument
- ✅ Apply best practices for order management
- ✅ Present analysis in a clear, structured format

---

## 📁 Files Updated

1. ✅ `chatgpt_instructions.txt` - Main instructions file
2. ✅ `handlers/chatgpt_bridge.py` - System prompt includes pending order guidance
3. ✅ `openai.yaml` - API documentation includes new endpoints
4. ✅ `docs/PENDING_ORDER_ANALYSIS.md` - User-facing documentation

---

## ✅ Status

- ✅ Instructions file updated
- ✅ New section added (150+ lines)
- ✅ Examples included
- ✅ Best practices documented
- ✅ Communication format defined
- ✅ Ready to copy to ChatGPT GPT

**Next Step**: Copy the updated instructions to your ChatGPT GPT configuration!
