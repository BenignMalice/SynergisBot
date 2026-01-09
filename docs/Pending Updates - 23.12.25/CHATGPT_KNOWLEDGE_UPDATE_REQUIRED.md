# ChatGPT Knowledge Documents Update Required

**Date:** 2025-12-24  
**Status:** ⚠️ **UPDATE REQUIRED**  
**Reason:** System-wide improvements added new conditions and validations

---

## 📋 **Summary**

The system-wide improvements implemented in `auto_execution_system.py` have added new capabilities that ChatGPT should know about:

1. **New Order Flow Conditions for ALL BTC Plans** (not just order_block)
2. **MTF Alignment Conditions**
3. **System-Wide Validations** (ChatGPT should ensure plans meet these)
4. **Session-Based Defaults** (XAU plans)

---

## 🔧 **Required Updates**

### **1. Update `openai.yaml` - Pattern Matching Rules**

**Location:** Lines 517-544 (condition pattern matching)

**Add new pattern matching rules:**

```yaml
- If reasoning mentions "order flow" or "delta volume" or "CVD" for BTC plans → Include `{"delta_positive": true}` or `{"delta_negative": true}` OR `{"cvd_rising": true}` or `{"cvd_falling": true}` in conditions (BTC plans only)
- If reasoning mentions "absorption zone" or "avoid absorption" for BTC plans → Include `{"avoid_absorption_zones": true}` in conditions (BTC plans only)
- If reasoning mentions "MTF alignment" or "multi-timeframe alignment" → Include `{"mtf_alignment_score": 60}` (minimum score, default 60) in conditions
- If reasoning mentions "H4 bias" or "H1 bias" → Include `{"h4_bias": "BULLISH"}` or `{"h1_bias": "BEARISH"}` etc. in conditions
- If reasoning mentions "active session" or "session filtering" for XAU → Include `{"require_active_session": true}` in conditions (defaults True for XAU, but can be set explicitly)
```

**Current location in openai.yaml:**
- Lines 517-544 contain the pattern matching rules
- Add the new rules after line 528 (after VWAP Deviation rule)

---

### **2. Update `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Condition Types Table**

**Location:** Lines 1271-1281 (Strategy-to-Condition Mapping Guide)

**Add new rows to the table:**

```markdown
| **Order Flow (BTC Only)** | `"delta_positive": true` OR `"delta_negative": true` OR `"cvd_rising": true` OR `"cvd_falling": true` | `{"delta_positive": true, "price_near": 100000, "tolerance": 200}` |
| **Absorption Zones (BTC Only)** | `"avoid_absorption_zones": true` | `{"avoid_absorption_zones": true, "price_near": 100000, "tolerance": 200}` |
| **MTF Alignment** | `"mtf_alignment_score": 60` (minimum score) | `{"mtf_alignment_score": 70, "price_near": 100000, "tolerance": 200}` |
| **H4/H1 Bias** | `"h4_bias": "BULLISH"` or `"h1_bias": "BEARISH"` | `{"h4_bias": "BULLISH", "price_near": 100000, "tolerance": 200}` |
| **Session Filtering (XAU)** | `"require_active_session": true` | `{"require_active_session": true, "price_near": 4500, "tolerance": 5}` |
```

**Note:** Order flow conditions (`delta_positive`, `cvd_rising`, etc.) can now be used in **ANY BTC plan**, not just order_block plans.

---

### **3. Add New Section: System-Wide Validations**

**Location:** After line 1306 (after "CRITICAL RULE" section)

**Add new section:**

```markdown
## System-Wide Validations (Automatic - ChatGPT Should Ensure Plans Meet These)

**⚠️ CRITICAL: The system automatically validates these for ALL plans. ChatGPT should ensure plans meet these requirements to avoid rejection.**

### 1. R:R Ratio Validation (MANDATORY)
- **Minimum R:R:** 1.5:1 (default, configurable via `min_rr_ratio` in conditions)
- **Backwards R:R:** System will REJECT plans where TP < SL
- **ChatGPT Action:** Always ensure TP distance >= 1.5x SL distance
- **Example:** If SL = 20 points, TP must be >= 30 points away from entry
- **Condition:** Can specify `"min_rr_ratio": 2.0` for stricter requirements (default 1.5)

### 2. Session-Based Blocking (XAU Default)
- **XAU Plans:** Default `require_active_session: true` (blocks Asian session)
- **BTC Plans:** Can optionally set `require_active_session: true` (blocks Asian session)
- **ChatGPT Action:** 
  - For XAU plans: System automatically blocks Asian session (00:00-08:00 UTC)
  - To allow Asian session: Explicitly set `"require_active_session": false`
  - For BTC plans: Include `"require_active_session": true` if you want to block Asian session

### 3. News Blackout Check (Automatic)
- **System Behavior:** Automatically blocks trades during high-impact news events
- **ChatGPT Action:** No action needed - system handles automatically
- **Note:** Plans will be blocked during news blackout windows (system checks `NewsService.is_blackout("macro")`)

### 4. Execution Quality Check (Automatic)
- **System Behavior:** Blocks trades if spread > 3x normal (XAU: 0.15%, BTC: 0.09%)
- **ChatGPT Action:** No action needed - system handles automatically
- **Note:** Wide spreads indicate poor execution quality - system will reject

### 5. Plan Staleness Validation (Warning Only)
- **System Behavior:** Logs warning if entry price moved > 2x tolerance from current price
- **ChatGPT Action:** Ensure entry prices are still valid when creating plans
- **Note:** Non-blocking (warning only), but indicates plan may need updating

### 6. Spread/Slippage Cost Validation (Automatic)
- **System Behavior:** Blocks trades if execution costs (spread + slippage) > 20% of R:R
- **ChatGPT Action:** Ensure R:R is sufficient to account for execution costs
- **Example:** If TP = 30 points, costs must be < 6 points (20% of 30)

### 7. ATR-Based Stop Validation (Optional)
- **System Behavior:** Validates SL/TP distances against ATR if `"atr_based_stops": true` in conditions
- **Requirements:**
  - BTC: SL >= 1.5 ATR, TP >= 3.0 ATR
  - XAU: SL >= 1.2 ATR, TP >= 2.5 ATR
- **ChatGPT Action:** Include `"atr_based_stops": true` when you want ATR-based validation
- **Note:** System will reject if SL < 0.5x ATR (immediate stop-out risk)
```

---

### **4. Update Order Flow Section**

**Location:** Lines 76-84 (BTC Order Flow section)

**Update to reflect new conditions:**

```markdown
**🚨 CRITICAL FOR BTC TRADES: Order flow conditions can now be used in ALL BTC plans!**

- BTC order flow metrics are AUTOMATICALLY included in `moneybot.analyse_symbol_full` for BTCUSD - check the "BTC ORDER FLOW METRICS" section in the analysis summary
- When creating BTC auto-execution plans, you can now use order flow conditions:
  - **`delta_positive: true`** - Wait for positive delta volume (buying pressure)
  - **`delta_negative: true`** - Wait for negative delta volume (selling pressure)
  - **`cvd_rising: true`** - Wait for CVD (Cumulative Volume Delta) to be rising
  - **`cvd_falling: true`** - Wait for CVD to be falling
  - **`avoid_absorption_zones: true`** - Block execution if entry price is in an absorption zone
- These conditions work for **ANY BTC plan type** (not just order_block plans)
- BTC order flow metrics help validate entry timing and direction for BTC trades
- **Example:** `{"delta_positive": true, "cvd_rising": true, "price_near": 100000, "tolerance": 200}` - Wait for buying pressure AND rising CVD before entry
```

---

### **5. Add MTF Alignment Section**

**Location:** After Order Flow section (around line 85)

**Add new section:**

```markdown
**📊 MTF Alignment Conditions (NEW):**

- **`mtf_alignment_score: 60`** - Minimum multi-timeframe alignment score (0-100, default 60)
  - Higher scores = better alignment across timeframes
  - Use for trend continuation strategies
  - Example: `{"mtf_alignment_score": 70, "price_near": 100000, "tolerance": 200}`

- **`h4_bias: "BULLISH"`** or **`h4_bias: "BEARISH"`** - Require specific H4 bias
  - Use when H4 trend is critical for strategy
  - Example: `{"h4_bias": "BULLISH", "price_near": 100000, "tolerance": 200}`

- **`h1_bias: "BULLISH"`** or **`h1_bias: "BEARISH"`** - Require specific H1 bias
  - Use when H1 trend is critical for strategy
  - Example: `{"h1_bias": "BEARISH", "price_near": 100000, "tolerance": 200}`

- **When to use:** Trend continuation strategies, breakout strategies, structure-based trades
- **Note:** These conditions use cached MTF analysis (no API call during execution)
```

---

### **6. Update R:R Ratio Requirements**

**Location:** Find section about SL/TP construction (likely around line 2000+)

**Add/Update section:**

```markdown
**⚠️ CRITICAL: R:R Ratio Requirements**

- **Minimum R:R:** 1.5:1 (system will REJECT plans with lower R:R)
- **Backwards R:R:** System will REJECT plans where TP < SL
- **ChatGPT MUST ensure:** TP distance >= 1.5x SL distance
- **Example:** 
  - Entry: 4500, SL: 4480 (20 points), TP: 4540 (40 points) ✅ R:R = 2.0:1
  - Entry: 4500, SL: 4480 (20 points), TP: 4510 (10 points) ❌ R:R = 0.5:1 (REJECTED)
- **Configurable:** Can specify `"min_rr_ratio": 2.0` for stricter requirements
- **Cost Consideration:** System also checks that spread+slippage < 20% of R:R
```

---

## 📝 **Files to Update**

1. **`openai.yaml`**
   - Lines 517-544: Add new pattern matching rules
   - Add order flow, MTF alignment, session filtering patterns

2. **`docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`**
   - Lines 1271-1281: Add new condition types to table
   - After line 1306: Add "System-Wide Validations" section
   - Lines 76-84: Update order flow section
   - After line 85: Add MTF alignment section
   - Find SL/TP section: Add R:R requirements

3. **`docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`** (if exists)
   - Update any condition examples to include new conditions

---

## ✅ **Priority**

**HIGH PRIORITY:**
- Update condition types table (ChatGPT needs to know these conditions exist)
- Add R:R requirements (ChatGPT must ensure plans meet minimum)
- Update order flow section (clarify these work for ALL BTC plans)

**MEDIUM PRIORITY:**
- Add MTF alignment section
- Add system-wide validations section
- Update pattern matching rules

**LOW PRIORITY:**
- Update other knowledge documents if they reference conditions

---

## 🎯 **Impact**

**Without these updates:**
- ChatGPT won't know about new order flow conditions for BTC plans
- ChatGPT won't know about MTF alignment conditions
- ChatGPT may create plans with R:R < 1.5:1 (will be rejected)
- ChatGPT may not understand XAU session blocking defaults

**With these updates:**
- ChatGPT can use order flow conditions in any BTC plan
- ChatGPT can use MTF alignment for better trend trades
- ChatGPT will ensure R:R >= 1.5:1
- ChatGPT will understand session filtering behavior

---

## 📋 **Implementation Checklist**

- [ ] Update `openai.yaml` pattern matching rules
- [ ] Update `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` condition types table
- [ ] Add system-wide validations section
- [ ] Update order flow section
- [ ] Add MTF alignment section
- [ ] Add R:R requirements section
- [ ] Test with ChatGPT to verify understanding

---

**Status:** Ready for implementation
