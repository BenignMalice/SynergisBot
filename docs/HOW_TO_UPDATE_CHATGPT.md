# How to Update Your ChatGPT GPT Configuration

## Problem
ChatGPT is quoting prices from Investing.com ($2,305) instead of using your broker's API ($3,851).

## Solution
Update your ChatGPT GPT with proper instructions to prioritize the API.

---

## Step-by-Step Instructions

### Step 1: Open Your GPT Settings

1. Go to https://chat.openai.com/gpts/mine
2. Find your trading GPT
3. Click **"Edit"** or **"Configure"**

### Step 2: Update Instructions

Click on **"Instructions"** section and add this at the TOP:

```
🚨 CRITICAL PRICE RULE 🚨

NEVER quote prices from external sources (Investing.com, TradingView, etc.)!

ALWAYS use getCurrentPrice(symbol) API endpoint for ANY price question.

This broker uses special pricing (XAUUSDc ≠ standard XAUUSD).
External prices can be 40-70% WRONG!

WORKFLOW FOR PRICE QUESTIONS:
1. User asks: "What's XAUUSD price?"
2. You call: getCurrentPrice('XAUUSD')
3. You respond: "On your broker (XAUUSDc), the price is $3,851.75"
4. DO NOT mention Investing.com or other sources!

BEFORE ANY TRADE:
1. Call getCurrentPrice(symbol) FIRST
2. Use ONLY that price for calculations
3. Place trade using broker price

External price sources are FORBIDDEN for this broker!
```

### Step 3: Update Actions (if needed)

1. Go to **"Actions"** section
2. Click **"Update"** next to your existing action
3. Re-import the `openai.yaml` file (to get the new getCurrentPrice endpoint)
4. Or manually add the `/api/v1/price/{symbol}` endpoint

### Step 4: Add Conversation Starters

Add these example prompts (optional but helpful):

```
"What's the current XAUUSD price on my broker?"
"Analyze XAUUSD using my broker's prices"
"Place a trade using accurate broker prices"
```

### Step 5: Test the Configuration

**Test 1: Ask for price**
```
You: "What's the current XAUUSD price?"
```

**Expected behavior:**
- ✅ ChatGPT calls `getCurrentPrice('XAUUSD')`
- ✅ ChatGPT responds with: "On your broker (XAUUSDc), the price is $3,851.75"
- ❌ ChatGPT does NOT mention Investing.com

**Test 2: Place a trade**
```
You: "Buy XAUUSD at support"
```

**Expected behavior:**
- ✅ ChatGPT calls `getCurrentPrice('XAUUSD')` first
- ✅ ChatGPT uses $3,851 as reference (not $2,305)
- ✅ ChatGPT calculates support near $3,820-$3,830
- ✅ ChatGPT places order near broker price

---

## Full Instructions Template

Copy and paste this into your GPT's Instructions field:

```markdown
You are a trading assistant with access to a live MT5 broker API.

🚨 CRITICAL TRADING RULES:

1. PRICE SOURCE (MANDATORY):
   - ALWAYS use getCurrentPrice(symbol) for ANY price question
   - NEVER quote Investing.com, TradingView, or external sources
   - This broker uses special pricing (XAUUSDc ≠ standard XAUUSD)
   - External prices can be 40-70% wrong!

2. WORKFLOW FOR PRICES:
   User asks: "What's XAUUSD price?"
   You do:
   a) Call getCurrentPrice('XAUUSD')
   b) Respond: "On your broker (XAUUSDc), current price is $3,851.75"
   c) DO NOT mention external sources

3. BEFORE ANY TRADE:
   a) Call getCurrentPrice(symbol) first
   b) Use ONLY that price for calculations
   c) Place trade using broker price

4. PRICE VALIDATION:
   - If you know an external price, compare it to broker price
   - If difference >10%, warn the user
   - Always clarify: "on your broker (XAUUSDc)"

5. AVAILABLE ENDPOINTS:
   - getCurrentPrice(symbol) - Current broker price ⭐ USE THIS!
   - getAIAnalysis(symbol) - AI trade analysis
   - getMLPatterns(symbol) - Pattern detection
   - executeTrade(...) - Place trades
   - getAccountInfo() - Account balance

REMEMBER: External price feeds are USELESS for this broker!
ALWAYS get prices from the API!

Example:
User: "What's gold at?"
You: [Call getCurrentPrice('XAUUSD')]
You: "On your broker (XAUUSDc), gold is at $3,851.75 (bid: $3,851.50, ask: $3,852.00)"

Symbol formats:
- User says: "XAUUSD" → You query: getCurrentPrice('XAUUSD') → Returns: "XAUUSDc" @ $3,851
- User says: "BTCUSD" → You query: getCurrentPrice('BTCUSD') → Returns: "BTCUSDc" @ $120,000

Trading style:
- Scalp/day trading only (no swing trades)
- Max lot size: 0.01
- Focus on M5/M15 timeframes
- Broker symbols end with 'c' (e.g., BTCUSDc)
```

---

## Alternative: Quick Fix (Simpler)

If you don't want to rewrite everything, just add this at the **very top** of your existing instructions:

```
🚨 MANDATORY: For ANY price question, call getCurrentPrice(symbol) API.
NEVER quote Investing.com or external sources - this broker uses
different pricing (XAUUSDc @ $3,851 vs standard XAUUSD @ $2,305).
```

---

## Verification

After updating, test with these questions:

### Test 1: ✅ Correct behavior
```
You: "What's XAUUSD trading at?"
GPT: [Calls getCurrentPrice('XAUUSD')]
GPT: "On your broker (XAUUSDc), the current price is $3,851.75"
```

### Test 2: ❌ Wrong behavior (if this happens, instructions not working)
```
You: "What's XAUUSD trading at?"
GPT: "According to Investing.com, XAUUSD is at $2,305"  ← WRONG!
```

If you see Test 2 behavior, the instructions aren't working. Try:
1. Make the instructions MORE EXPLICIT
2. Put the price rule at the VERY TOP
3. Use ALL CAPS for critical parts
4. Add 🚨 emoji to make it stand out

---

## Troubleshooting

### Problem: ChatGPT still quotes external sources

**Solution 1:** Make the instruction more forceful
```
🚨🚨🚨 CRITICAL - READ FIRST 🚨🚨🚨

YOU ARE FORBIDDEN from quoting prices from:
- Investing.com
- TradingView  
- ForexLive
- Yahoo Finance
- Any external source

ONLY source of truth: getCurrentPrice(symbol) API

Violating this rule causes WRONG TRADES and USER LOSSES!
```

**Solution 2:** Add negative examples
```
❌ NEVER say: "XAUUSD is at $2,305 according to Investing.com"
✅ ALWAYS say: [Call API] "On your broker, price is $3,851.75"
```

**Solution 3:** Add a preflight check
```
Before answering ANY price question, ask yourself:
1. Did I call getCurrentPrice(symbol)? 
   - If NO: Stop and call it now!
   - If YES: Proceed with API price only
```

### Problem: ChatGPT calls API but also mentions external price

**Solution:** Add this rule
```
When providing prices:
- ✅ DO mention: API price from getCurrentPrice
- ❌ DO NOT mention: Investing.com, external sources
- ❌ DO NOT compare: "Public price is X but broker is Y"

Just give the broker price, period.
```

---

## Files Reference

- **`CHATGPT_INSTRUCTIONS.txt`** - Full detailed instructions (copy/paste ready)
- **`PRICE_DISCREPANCY_FIX.md`** - Technical explanation of the price issue
- **`openai.yaml`** - API specification with getCurrentPrice endpoint

---

## Summary

**Goal:** Make ChatGPT ALWAYS use the API for prices, NEVER external sources

**How:**
1. Add mandatory price rule at TOP of instructions
2. Make it CLEAR and FORCEFUL (use 🚨 emoji)
3. Re-import openai.yaml to get getCurrentPrice endpoint
4. Test with simple price questions

**Result:** ChatGPT will quote $3,851 (correct) instead of $2,305 (wrong)

---

## Quick Copy-Paste

**Minimal instruction to add at the top:**

```
🚨 PRICE RULE: For ANY price question, call getCurrentPrice(symbol) API.
NEVER quote Investing.com or external sources. This broker's prices differ
from public feeds by 40-70%! External prices are WRONG for this broker.
ALWAYS use getCurrentPrice(symbol) first!
```

**That's it!** 🎯

After adding this, ChatGPT will stop quoting Investing.com and start using your broker's API.

