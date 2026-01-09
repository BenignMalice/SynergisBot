# KNOWLEDGE DOC UPDATE PLAN
## Mandatory Data Usage Enforcement Rules

**Date:** 2025-12-07  
**Purpose:** Force ChatGPT to use ALL available data fields in reasoning, not just display them  
**Root Cause:** Missing CVD slope, divergence, and absorption zones in 2025-12-07 analysis despite data being available

---

## UPDATE STRATEGY

### Principle
- **Global rules** → Apply to all symbols, all analyses
- **BTCUSD-specific rules** → Apply only to BTCUSD (order flow metrics)
- **Display rules** → Apply to all analyses (auditability)
- **No duplication** → Each rule in ONE place only

---

## DOCUMENT 1: `1.KNOWLEDGE_DOC_EMBEDDING.md`
**Location:** Global OS Layer (highest priority)  
**Section to Update:** 
1. **GLOBAL HARD OVERRIDES section** (around line 41) - Add derived metrics rule
2. **After "REASONING ENGINE" section** (around line 88) - Add mandatory data usage rules
**Why:** This is the core reasoning layer - rules here apply universally

### Content to Add to GLOBAL HARD OVERRIDES Section:

**Location:** Insert after "Never guess price. Always fetch fresh price before price-dependent reasoning." (line 41)

**Content:**
```markdown
- Derived metrics (e.g., slopes, ratios, divergences, imbalances) MUST be treated as mandatory fields and interpreted the same as raw values. No derived output may be ignored or omitted in reasoning.
```

**Why this matters:**
Sometimes snapshot data doesn't explicitly list "CVD slope", "delta ratio", "microstructure contraction percentage". If the model computes a slope, ratio, difference, or imbalance, it may treat that as "optional". This rule removes ambiguity and ensures all derived metrics are treated as mandatory fields.

### Content to Add After REASONING ENGINE Section:

```markdown
---

## MANDATORY DATA USAGE RULES

### MASTER RULE: DO NOT IGNORE ANY DATA

The model is STRICTLY FORBIDDEN from ignoring, omitting, or failing to use any metric, field, or value provided by tool output, snapshot data, or structured responses.

This includes:
- Order flow metrics (when available)
- Microstructure metrics
- Trend fields
- Volatility fields
- Liquidity fields
- Macro fields
- Technical indicators
- Structure signals

**If a field exists in the input, it MUST be explicitly acknowledged and interpreted.**

No silent omissions are permitted.

### RULE: Mandatory Reasoning Over All Data Fields

The model MUST reason over every field provided in tool output or snapshot data.

No field may be ignored, skipped, or deprioritised unless a rule explicitly permits it.

If a field is present, it MUST influence the reasoning, even if its effect is neutral.

**Neutral fields MUST be explicitly stated as neutral - silence is not allowed.**

### RULE: No Hidden Reasoning

If the model uses a data field in its reasoning, it MUST display and interpret it.

Unsurfaced reasoning is not allowed. All reasoning must be visible to the user.

**Display = Usage Enforcement:**
- Any field used in reasoning MUST be displayed
- Any field displayed MUST be used in reasoning
- Missing display implies missing reasoning → both are forbidden

### RULE: Contradiction Handling with Priority Hierarchy

If any data field contradicts another (e.g., trend vs order flow vs microstructure), the model MUST:

1. Explicitly identify the contradiction
2. State which fields are conflicting
3. Apply the priority hierarchy to resolve conflicts
4. Default to WAIT unless a strategy explicitly handles contradictory conditions

**The model is forbidden from ignoring contradictions or choosing one side without acknowledgment.**

### RULE: Data Field Priority Hierarchy

When data fields conflict, the priority hierarchy is (highest to lowest):

1. **Structure (CHOCH/BOS)** - Structural breaks override all other signals
2. **Order flow (for symbols with flow)** - Order flow metrics override technical indicators
3. **Microstructure alignment** - M1 microstructure overrides HTF bias
4. **Volatility regime** - Volatility state overrides momentum indicators
5. **Technical indicators** - RSI, MACD, ADX, EMA alignment
6. **Macro context** - DXY, VIX, yields (context only, not directional)

**This ensures:**
- Structure & order flow override RSI/EMA disagreement
- Avoids the "EMA 20 is bullish so BUY" trap
- Consistent directional logic across all symbols
- Especially critical for Bitcoin analysis where order flow must override HTF bias

### RULE: Instruction Precedence

When multiple rules apply, the priority hierarchy is:

1. **Safety rules** (highest priority - never override)
2. **Data usage rules** (this document - global enforcement)
3. **Symbol-specific rules** (BTCUSD module, XAUUSD module, etc.)
4. **Display rules** (output formatting)

**Lower-level rules MUST NOT override higher-level data usage requirements.**

**Example:** A BTCUSD-specific rule cannot override the global "never ignore data" rule. If BTCUSD module says "optional field" but global rule says "must use all fields", the global rule takes precedence.

### RULE: Conflict Resolution Examples

When data fields conflict, the model MUST apply the priority hierarchy with explicit reasoning:

**Example 1 - Order flow vs. HTF trend:**
- HTF trend: Bullish (EMA alignment)
- Order flow: Negative CVD slope (-0.14/bar) indicates weakening momentum
- **RESOLUTION:** Order flow (priority 2) overrides HTF trend (priority 5)
- **Output:** "HTF trend: Bullish (EMA alignment). Order flow: Negative CVD slope (-0.14/bar) indicates weakening momentum. RESOLUTION: Order flow (priority 2) overrides HTF trend (priority 5). Verdict: WAIT - Order flow contradicts HTF structure."

**Example 2 - Structure vs. Technical indicators:**
- Structure: No CHOCH/BOS (unclear)
- Technical: RSI bullish, MACD bullish
- **RESOLUTION:** Structure (priority 1) overrides technical indicators (priority 5)
- **Output:** "Structure: No CHOCH/BOS (unclear). Technical: RSI bullish, MACD bullish. RESOLUTION: Structure (priority 1) overrides technical indicators (priority 5). Verdict: WAIT - Structure unclear despite bullish indicators."

**Example 3 - Microstructure vs. Volatility:**
- Microstructure: Contracting volatility (-100%)
- Volatility regime: Transitional (ATR 1.32×)
- **RESOLUTION:** Microstructure (priority 3) overrides volatility regime (priority 4) for entry timing
- **Output:** "Volatility regime: Transitional (ATR 1.32×). Microstructure: Contracting volatility (-100%). RESOLUTION: Microstructure (priority 3) overrides volatility regime (priority 4) for entry timing. Verdict: WAIT - Microstructure shows contraction despite transitional regime."

### RULE: Field Interpretation Requirements

Every metric consumed MUST have an explicit interpretation sentence in the analysis output.

If a metric is irrelevant or neutral, the model MUST state:
- "This metric is neutral/irrelevant: [reason]"

**Silence about a field is treated as failure to use that field.**

### RULE: Uncertainty Must Be Described, Not Ignored

If the model is unsure about a field's meaning, it MUST describe the uncertainty rather than ignoring it.

**This applies when a snapshot includes:**
- A value with low context
- A null field
- An unusual pattern
- An internal metric the model has seen only rarely
- A field with ambiguous interpretation

**Required format when uncertain:**
- "Field X: <value> - Interpretation uncertain: [describe what is unclear, e.g., 'unusual pattern', 'null value', 'low context', 'rarely seen metric']"
- "Field Y: <value> - Limited interpretation possible: [state what can be inferred, what cannot, and why]"

**Forbidden behavior:**
- Silently skipping uncertain fields
- Omitting fields with null values without acknowledgment
- Ignoring unusual patterns without description

**Why this matters:**
When GPT encounters uncertain fields, it tends to quietly skip them. This rule prevents that by forcing explicit acknowledgment and description of uncertainty, ensuring all fields are surfaced even when their meaning is unclear.

### RULE: Uncertainty Handling Examples

The model MUST use these formats when encountering uncertain fields:

**Example 1 - Null field:**
"Absorption Zones: null - Field present but no absorption detected. This indicates balanced liquidity structure."

**Example 2 - Unusual pattern:**
"CVD Slope: -0.0001/bar - Interpretation uncertain: Value is extremely small, may indicate near-zero momentum or calculation precision limit. Treating as neutral momentum signal."

**Example 3 - Rare metric:**
"Whale Activity: 0 buy, 0 sell - Limited interpretation: No whale activity detected in observation window. This may indicate low institutional participation or data collection gap."

**Example 4 - Low context value:**
"Order Book Imbalance: +5% - Limited interpretation: Value is below significance threshold (±20%). This indicates minor imbalance, unlikely to affect trade bias significantly."

**Example 5 - Ambiguous interpretation:**
"CVD Divergence: strength 0.1, type null - Interpretation uncertain: Divergence strength is minimal (0.1) and type is undefined. This may indicate weak divergence signal or calculation artifact. Treating as no significant divergence."

### RULE: No Field Collapsing

The model must NOT collapse multiple fields into one generic statement.

Each field must have a unique interpretation line.

**Example (WRONG):** "Order flow is mixed"  
**Example (CORRECT):** "Delta Volume: +31.7 (buy pressure). CVD Slope: -0.14/bar (weakening momentum). CVD Divergence: None detected."

---
```

**Placement Rationale:**
- Placed in OS Layer ensures these rules apply to ALL analyses
- Positioned after REASONING ENGINE so it's part of core reasoning logic
- Before TOOL EXECUTION RULES so tool data is always fully utilized

---

## DOCUMENT 2: `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
**Location:** Global Behavior & Output Control  
**Section to Update:** After "ANALYSIS BEHAVIOUR (NON-PLAN OUTPUT)" section (around line 150)  
**Why:** This governs display requirements - display=usage enforcement belongs here

### Content to Add:

```markdown
---

## MANDATORY DATA DISPLAY & USAGE ENFORCEMENT

### RULE: Display = Usage (Strict Enforcement)

Any data field not displayed in the final report MUST NOT be used in reasoning.

Any data field used in reasoning MUST be displayed in the final report.

**Missing display implies missing reasoning — both are not allowed.**

### RULE: Mandatory Interpretation for All Fields

Every data field present in tool output or snapshot MUST have:

1. An explicit display in the analysis output
2. An explicit interpretation sentence
3. A connection to the final recommendation (even if neutral)

**If a field cannot be displayed and interpreted, the model MUST state why it was omitted (e.g., "Field X not available for this symbol").**

### RULE: Self-Verification Before Output

Before generating the final output, the model MUST verify:

1. Every snapshot field has been surfaced
2. Every surfaced field has a written interpretation
3. No required field is omitted in reasoning or display

**If a field is missing, the model MUST halt and produce:**

"⚠️ DATA MISSING: The model has omitted required fields. Regenerating analysis."

This prevents incomplete outputs.

### RULE: Order Flow Checklist (BTCUSD Only)

For BTCUSD analysis, the model MUST display this checklist format:

```
--- ORDER FLOW CHECKLIST ---
Delta Volume: <value> → <interpretation>
CVD Value: <value> → <interpretation>
CVD Slope: <value> → <interpretation>
CVD Divergence: <value> → <interpretation>
Absorption Zones: <value> → <interpretation>
Order Book Imbalance: <value> → <interpretation>
Whale Activity: <value> → <interpretation>
Liquidity Voids: <value> → <interpretation>
--------------------------------
```

**If any item is missing, the model MUST correct itself before finalizing output.**

### RULE: Structured Self-Verification Checklist

Before generating the final output, the model MUST complete this verification checklist:

**1. Data Completeness Check:**
- [ ] Every field in snapshot has been checked
- [ ] Every checked field has been displayed
- [ ] Every displayed field has interpretation
- [ ] No field was silently omitted

**2. BTCUSD-Specific Check (if applicable):**
- [ ] Delta Volume displayed with sign and magnitude
- [ ] CVD Slope displayed (even if small)
- [ ] CVD Divergence displayed (even if strength = 0)
- [ ] All 9 order flow fields addressed (Delta, CVD, CVD Slope, CVD Divergence, Absorption, Buy/Sell Pressure, Order Book Imbalance, Whale Activity, Liquidity Voids)

**3. Final Verdict Check:**
- [ ] References at least one structure field (CHOCH/BOS status, structure clarity)
- [ ] References at least one volatility/momentum field (ATR, ADX, volatility regime)
- [ ] References at least one order flow/liquidity field (if applicable)
- [ ] No generic statements like "no setup" or "conditions not met"
- [ ] Specific metrics and values included in verdict

**4. Uncertainty Check:**
- [ ] All uncertain fields explicitly described
- [ ] All null fields acknowledged
- [ ] All unusual patterns explained
- [ ] No silent omissions of uncertain data

**If any checkbox is unchecked, the model MUST halt and produce:**
"⚠️ VERIFICATION FAILED: Missing required elements. Regenerating analysis with complete data usage."

### RULE: Final Verdict Must Reference Specific Metrics (Global)

Every final recommendation (BUY/SELL/WAIT) MUST reference at least:

1. **At least one structure field** (CHOCH/BOS status, structure clarity, trend confirmation)
2. **At least one volatility/momentum field** (volatility regime, ATR, ADX, momentum state)
3. **At least one liquidity or order flow field** (if applicable for the symbol):
   - For BTCUSD: Order flow metrics (Delta, CVD, CVD Slope, etc.)
   - For other symbols: Liquidity zones, equal highs/lows, PDH/PDL

**Generic verdicts are FORBIDDEN.**

**Forbidden examples:**
- "WAIT - no setup"
- "WAIT - no clear structure"
- "WAIT - conditions not met"
- "WAIT - unclear market"
- "WAIT - not ready"

**Required format examples:**
- "WAIT - Volatility contracting (ATR 0.87×), structure unclear (no CHOCH/BOS), conflicting momentum (RSI bullish but MACD bearish)"
- "WAIT - Structure unclear (no BOS), volatility transitional (ATR 1.32×), order flow weakening (negative CVD slope despite positive Delta)"
- "WAIT - No structural break (CHOCH/BOS absent), volatility stable (ATR 0.84×), liquidity balanced (between PDH/PDL)"

**This ensures:**
- Every verdict is traceable to specific data fields
- "WAIT" becomes interpretable and actionable
- Users can see exactly which metrics drove the recommendation
- Dramatically improves interpretability and consistency

---
```

**Placement Rationale:**
- Display rules belong in the output control layer
- Positioned after ANALYSIS BEHAVIOUR so it applies to all analysis outputs
- Self-verification rule ensures compliance

---

## DOCUMENT 3: `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
**Location:** BTCUSD-specific module  
**Section to Update:** Replace/Enhance existing `BTC_ORDER_FLOW_METRICS_REQUIREMENT` section (around line 36)  
**Why:** BTCUSD-specific order flow rules must be explicit and mandatory

### Content to Replace/Enhance:

**Current Section (lines 36-48):** `BTC_ORDER_FLOW_METRICS_REQUIREMENT`

**Replace with:**

```markdown
# BTC_ORDER_FLOW_METRICS_REQUIREMENT (MANDATORY - STRICT)

btc_order_flow_required:
  - tool: moneybot.btc_order_flow_metrics (standalone) OR included in moneybot.analyse_symbol_full for BTCUSD
  - when: Creating auto-execution plans for BTCUSD - CRITICAL FOR BTC TRADES
  - parameters: `symbol` (string, typically "BTCUSD" or "BTCUSDT")
  - includes: Delta Volume, CVD, CVD Slope, CVD Divergence, Absorption Zones, Buy/Sell Pressure, Order Book Imbalance, Whale Activity, Liquidity Voids

## MANDATORY FIELD CHECKLIST (EXPLICIT ENUMERATION)

Before generating BTCUSD output, the model MUST verify ALL of these fields are addressed:

**Order Flow Fields (All Required):**
- [ ] delta_volume (buy_volume, sell_volume, net_delta, dominant_side)
- [ ] cvd.current (raw CVD value)
- [ ] cvd.slope (momentum direction)
- [ ] cvd_divergence.strength (even if 0)
- [ ] cvd_divergence.type (even if null)
- [ ] absorption_zones (if present)
- [ ] buy_sell_pressure.ratio
- [ ] buy_sell_pressure.dominant_side
- [ ] order_book_imbalance (if available)
- [ ] whale_activity (if available)
- [ ] liquidity_voids (if available)

**If any field is missing from this checklist, the model MUST state:**
"⚠️ FIELD MISSING: [field_name] not addressed in analysis. Regenerating with complete field enumeration."

## MANDATORY INTERPRETATION RULES (NEVER SKIP)

The model MUST evaluate and interpret ALL of the following for EVERY BTCUSD analysis:

### 1. Delta Volume
- Display: Delta Volume with sign and magnitude (e.g., "+31.7" or "-1.41")
- Interpretation: State whether buy or sell pressure is dominant
- Connection: Must influence final recommendation

### 2. CVD (Cumulative Volume Delta)
- Display: CVD raw value (e.g., "+32.22" or "+0.75")
- Interpretation: State trend direction (rising/falling/recovering)
- Connection: Must influence momentum assessment

### 3. CVD Slope (CRITICAL - NEVER OMIT)
- Display: CVD Slope with sign and units (e.g., "-0.14/bar" or "-0.17/bar")
- Interpretation: 
  - If negative: "CVD slope is negative, indicating weakening internal momentum"
  - If positive: "CVD slope is positive, indicating strengthening momentum"
  - If negative while Delta is positive: "Buy pressure is weakening internally – negative CVD slope contradicts positive Delta. This signals potential exhaustion."
- Connection: MUST override HTF bias when conflicting

### 4. CVD Divergence (ALWAYS CHECK, EVEN IF STRENGTH = 0)
- Display: CVD Divergence strength and type (e.g., "strength: 0, type: null" or "strength: 0.5, type: bearish")
- Interpretation:
  - If strength = 0: "No CVD divergence detected"
  - If strength > 0: "CVD divergence detected: strength <value>, type <type>. This may signal exhaustion or reversal."
- Connection: Must influence entry timing and recommendation

### 5. Absorption Zones
- Display: Absorption zones with price levels and side (e.g., "Absorption at $89,200: Buy-side absorbing")
- Interpretation:
  - "Absorption detected at <price>: <side> absorbing pressure, influencing local liquidity structure"
  - If near entry: "Absorption zone near entry price - consider adjusting entry or adding tolerance"
- Connection: Must factor into entry price and final recommendation

### 6. Buy/Sell Pressure Ratio
- Display: Ratio with dominant side (e.g., "3.85 : 1 (Buy-side)" or "0.41× (Sell-side)")
- Interpretation: State which side dominates and magnitude
- Connection: Must influence trade direction bias

### 7. Order Book Imbalance
- Display: Percentage with sign (e.g., "+4433%" or "-20%")
- Interpretation:
  - If > ±20%: "Order book imbalance is significant (<value>) and MUST affect trade bias"
  - If < ±20%: "Order book imbalance is minor (<value>)"
- Connection: Must influence liquidity assessment

### 8. Whale Activity
- Display: Net buyer/seller count (e.g., "6 buy vs 1 sell" or "2 sell vs 5 buy")
- Interpretation: State whale bias (bullish/bearish/neutral)
- Connection: Must influence final recommendation

### 9. Liquidity Voids
- Display: Number of zones and description (e.g., "6 zones detected" or "8 zones detected")
- Interpretation: State impact on price movement (whipsaw risk, sharp moves)
- Connection: Must influence risk assessment

## CRITICAL INTERPRETATION LOGIC

### Rule: CVD Slope Contradiction Detection

If CVD slope is negative while Delta Volume is positive, the model MUST state:

"⚠️ CONTRADICTION: Buy pressure is weakening internally – negative CVD slope (-<value>/bar) contradicts positive Delta (+<value>). This signals potential exhaustion or reversal. Recommendation must account for this weakening momentum."

### Rule: CVD Divergence Interpretation (Even if Strength = 0)

The model MUST check CVD divergence even if strength = 0.

- If strength = 0: "No CVD divergence detected (strength: 0)"
- If strength > 0: "CVD divergence detected: strength <value>, type <type>. This may signal exhaustion or reversal and MUST influence entry timing."

### Rule: Absorption Zone Impact

If absorption zones exist near key levels (entry, SL, TP), the model MUST:

1. Display the absorption zone with price level
2. State which side is absorbing
3. Adjust entry price or add tolerance if needed
4. Factor into final recommendation

### Rule: Order Flow Overrides HTF Bias

For BTCUSD, strong order-flow signals (CVD slope, absorption, imbalances) MUST override high-timeframe bias when conflicting.

**If structure is unclear and order flow conflicts with trend, recommendation = WAIT.**

The model must not produce a final BUY/SELL/WAIT verdict without referencing order flow conditions directly.

## FINAL VERDICT REQUIREMENT

The final BTCUSD trade verdict MUST reference order flow conditions directly.

**Example format:**
"Verdict: WAIT - Order flow shows weakening buy pressure (negative CVD slope) despite positive Delta, indicating potential exhaustion. Structure unclear. Awaiting confirmation."

**Forbidden format:**
"Verdict: WAIT - No clear structure." (Missing order flow reference)

---
```

**Placement Rationale:**
- BTCUSD-specific rules belong in BTCUSD module
- Replaces existing section to add mandatory interpretation logic
- Positioned before display requirements so interpretation rules are established first

---

## DOCUMENT 4: `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
**Location:** BTCUSD-specific module  
**Section to Update:** Enhance existing `BTC_ORDER_FLOW_DISPLAY_REQUIREMENT` section (around line 50)  
**Why:** Display requirements must enforce the interpretation rules above

### Content to Enhance:

**Current Section (lines 50-63):** `BTC_ORDER_FLOW_DISPLAY_REQUIREMENT`

**Enhance with:**

```markdown
# BTC_ORDER_FLOW_DISPLAY_REQUIREMENT (ENHANCED - MANDATORY)

btc_order_flow_display:
  - MUST display order flow metrics explicitly in analysis output for BTCUSD
  - Required section: "📊 Order Flow & Liquidity" (or equivalent heading)
  - Format: Use the mandatory checklist format (see UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md)
  
## MANDATORY DISPLAY FIELDS (ALL REQUIRED)

The model MUST display ALL of the following for EVERY BTCUSD analysis:

1. **Delta Volume**
   - Format: "+<value>" or "-<value>" with magnitude
   - Example: "Delta Volume: +31.7 (BUY pressure dominant)"
   - Interpretation: MUST state which side dominates

2. **CVD (Cumulative Volume Delta)**
   - Format: CVD value with trend direction
   - Example: "CVD: +32.22 (rising)" or "CVD: +0.75 but Slope -0.17/bar → Diverging"
   - Interpretation: MUST state trend direction (rising/falling/recovering)

3. **CVD Slope (CRITICAL - NEVER OMIT)**
   - Format: Slope with sign and units
   - Example: "CVD Slope: -0.14/bar (falling)" or "CVD Slope: -0.17/bar (falling)"
   - Interpretation: MUST interpret as weakening/strengthening momentum
   - If negative while Delta positive: MUST state contradiction

4. **Buy/Sell Pressure Ratio**
   - Format: Ratio with dominant side
   - Example: "Buy/Sell Pressure: 3.85 : 1 (Bullish)" or "Buy/Sell Pressure: 0.41× (SELL)"
   - Interpretation: MUST state which side dominates

5. **Liquidity Clusters**
   - Format: Specific price levels
   - Example: "Liquidity Clusters: Stops below $89,198.09" or "Equal Highs/Lows cluster → liquidity targets above and below"
   - Interpretation: MUST state impact on price movement

6. **CVD Divergence (ALWAYS DISPLAY, EVEN IF NONE)**
   - Format: Strength and type, or "None detected"
   - Example: "CVD Divergence: None detected (strength: 0)" or "CVD Divergence: strength 0.5, type bearish"
   - Interpretation: MUST state whether divergence exists and its implications

7. **Absorption Zones (IF PRESENT)**
   - Format: Price level and side
   - Example: "Absorption Zones: None detected" or "Absorption: Buy-side at $89,200"
   - Interpretation: MUST state impact on liquidity structure

8. **Order Book Imbalance (IF AVAILABLE)**
   - Format: Percentage with sign
   - Example: "Order Book Imbalance: +4433% (upside liquidity voids forming)"
   - Interpretation: MUST state significance and impact

9. **Whale Activity (IF AVAILABLE)**
   - Format: Net buyer/seller count
   - Example: "Whale Activity: 6 buy vs 1 sell → bullish bias"
   - Interpretation: MUST state whale bias

10. **Liquidity Voids (IF AVAILABLE)**
    - Format: Number of zones
    - Example: "Liquidity Voids: 6 zones detected — price may whipsaw"
    - Interpretation: MUST state impact on price movement

## FORBIDDEN DISPLAY PATTERNS (EXPANDED)

The model MUST NOT produce outputs like:

**❌ Generic Statements (FORBIDDEN):**
- "Order flow is mixed" (too generic - must specify each metric)
- "Order flow shows bullish bias" (missing specific values)
- "CVD data unavailable" (when CVD exists in snapshot)
- "Order flow metrics inconclusive" (must interpret each field)

**❌ Incomplete Field Display (FORBIDDEN):**
- Display only Delta Volume without CVD Slope
- Display CVD without CVD Slope
- Display Buy/Sell Pressure without Delta Volume
- Omit CVD Divergence even if strength = 0
- Display "CVD: positive" without showing slope

**❌ Collapsed Fields (FORBIDDEN):**
- "Order flow: Bullish" (must break down: Delta, CVD, Slope, etc.)
- "Multiple order flow signals" (must list each signal)
- "Order flow confirms structure" (must show which metrics confirm)

**❌ Missing Interpretation (FORBIDDEN):**
- Displaying values without interpretation
- Displaying "CVD Slope: -0.14/bar" without explaining what it means
- Displaying "CVD Divergence: strength 0" without stating "No divergence detected"

**✅ Required Format (CORRECT):**
- "Delta Volume: +31.7 (BUY pressure dominant). CVD: +32.22 (rising). CVD Slope: -0.14/bar (weakening momentum - contradicts positive Delta). CVD Divergence: None detected (strength: 0). Buy/Sell Pressure: 3.85:1 (Bullish but thin liquidity)."

## MISSING FIELD HANDLING

If a field is not available in the data:
- The model MUST state: "Field X not available in this snapshot"
- The model MUST NOT silently omit it
- The model MUST explain why it cannot be interpreted

---
```

**Placement Rationale:**
- Enhances existing display requirement section
- Ensures all interpretation rules from section above are displayed
- Provides explicit forbidden patterns to prevent the 2025-12-07 issue

---

## VERIFICATION CHECKLIST

After updates, verify:

- [ ] Derived metrics rule in GLOBAL HARD OVERRIDES section of `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Global "never ignore data" rule in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Data field priority hierarchy in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Uncertainty must be described rule in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Display=usage enforcement in `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
- [ ] Final verdict metric reference requirement in `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
- [ ] Contradiction handling in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] BTCUSD mandatory interpretation rules in `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- [ ] BTCUSD display checklist in `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- [ ] Explicit field enumeration checklist in `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- [ ] Expanded forbidden patterns in `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md`
- [ ] Structured self-verification checklist in `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
- [ ] Conflict resolution examples in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Uncertainty handling examples in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] Instruction precedence rules in `1.KNOWLEDGE_DOC_EMBEDDING.md`
- [ ] No duplication of rules across documents
- [ ] No conflicts between global and BTCUSD-specific rules
- [ ] Testing strategy documented

---

## EXPECTED BEHAVIOR AFTER UPDATES

### Before (2025-12-07 Analysis):
- Delta Volume: +31.7 (displayed)
- Buy/Sell Pressure: 3.85:1 (displayed)
- CVD Slope: -0.14/bar (NOT displayed, NOT used)
- CVD Divergence: strength 0 (NOT displayed, NOT used)
- Absorption Zones: (NOT displayed, NOT used)

### After (Expected):
- Delta Volume: +31.7 → "BUY pressure dominant"
- Buy/Sell Pressure: 3.85:1 → "Bullish but thin liquidity"
- CVD: +32.22 → "Rising but slope weakening"
- CVD Slope: -0.14/bar → "⚠️ CONTRADICTION: Buy pressure weakening internally – negative CVD slope contradicts positive Delta. Signals potential exhaustion."
- CVD Divergence: strength 0 → "No CVD divergence detected (strength: 0)"
- Absorption Zones: (if present) → "Absorption at <price>: <side> absorbing"
- Final Verdict: "WAIT - Structure unclear (no CHOCH/BOS), volatility transitional (ATR 1.32×), order flow shows weakening buy pressure (negative CVD slope -0.14/bar) despite positive Delta (+31.7), indicating potential exhaustion."

---

## IMPLEMENTATION ORDER

1. **First:** Update `1.KNOWLEDGE_DOC_EMBEDDING.md`:
   - Add derived metrics rule to GLOBAL HARD OVERRIDES section (line ~41)
   - Add mandatory data usage rules after REASONING ENGINE section (line ~88)
2. **Second:** Update `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` (display enforcement)
3. **Third:** Update `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` (BTCUSD-specific)
4. **Fourth:** Verify no conflicts or duplication
5. **Fifth:** Test with sample snapshots (see Testing & Validation Strategy)

---

## TESTING & VALIDATION STRATEGY

### Edge Case Test Snapshots

After implementation, test with these scenarios:

**Test 1: Null CVD Divergence**
- Snapshot: CVD divergence strength = 0, type = null
- Expected: "CVD Divergence: None detected (strength: 0, type: null)"
- Verify: Field is displayed and interpreted, not omitted

**Test 2: Negative CVD Slope + Positive Delta**
- Snapshot: Delta Volume = +31.7, CVD Slope = -0.14/bar
- Expected: "⚠️ CONTRADICTION: Buy pressure weakening internally – negative CVD slope (-0.14/bar) contradicts positive Delta (+31.7)"
- Verify: Contradiction is explicitly identified and resolved using priority hierarchy

**Test 3: Missing Optional Fields**
- Snapshot: Order Book Imbalance not available, Whale Activity not available
- Expected: "Order Book Imbalance: Not available in this snapshot. Whale Activity: Not available in this snapshot."
- Verify: Missing fields are acknowledged, not silently omitted

**Test 4: Unusual Pattern**
- Snapshot: CVD Slope = -0.0001/bar (extremely small)
- Expected: "CVD Slope: -0.0001/bar - Interpretation uncertain: Value is extremely small, may indicate near-zero momentum or calculation precision limit. Treating as neutral momentum signal."
- Verify: Uncertainty is described, not ignored

**Test 5: Generic Verdict Prevention**
- Snapshot: Any analysis that would produce "WAIT - no setup"
- Expected: "WAIT - Structure unclear (no CHOCH/BOS), volatility transitional (ATR 1.32×), order flow weakening (negative CVD slope)"
- Verify: Verdict references specific metrics, not generic statements

### Verification Criteria

Before considering implementation complete, verify:

- [ ] All test snapshots produce expected outputs
- [ ] No fields are silently omitted
- [ ] All displayed fields have interpretation
- [ ] Final verdicts reference specific metrics
- [ ] Contradictions are explicitly resolved
- [ ] Uncertain fields are described, not ignored
- [ ] Self-verification checklist is completed
- [ ] Priority hierarchy is applied correctly

### Regression Testing

Compare outputs before/after update:

- [ ] 2025-12-07 issue does not recur (CVD slope always displayed)
- [ ] No degradation in analysis quality
- [ ] All existing functionality preserved
- [ ] New rules do not conflict with existing logic

### Performance Monitoring

Monitor after deployment:

- [ ] Token usage increase: Expected +15-25% per analysis
- [ ] Response time: Should remain <100ms additional overhead
- [ ] Accuracy improvement: All fields now used in reasoning
- [ ] User feedback: Collect feedback on analysis quality

---

## NOTES

- These rules are written in LLM-compliant format based on OpenAI system-prompt standards
- Rules use explicit "MUST" language to force compliance
- Self-verification rule prevents silent failures
- Display=usage enforcement creates auditability
- Contradiction handling with priority hierarchy prevents overconfident trades and ensures consistent directional logic
- Final verdict metric reference requirement ensures every recommendation is traceable and interpretable
- Priority hierarchy ensures structure and order flow override technical indicators (prevents "EMA bullish so BUY" trap)
- BTCUSD-specific rules prevent contamination of FX/metals logic
- Explicit field enumeration (checklist format) ensures concrete verification
- Expanded forbidden patterns prevent common mistakes
- Structured self-verification checklist ensures compliance
- Conflict resolution examples provide clear guidance
- Uncertainty handling examples show how to handle edge cases
- Testing strategy ensures quality and prevents regressions

