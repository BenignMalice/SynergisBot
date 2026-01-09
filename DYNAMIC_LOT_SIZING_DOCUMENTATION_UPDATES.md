# Dynamic Lot Sizing - Documentation Updates Required

## Summary
This document lists all required updates to `openai.yaml` and ChatGPT knowledge documents for dynamic lot sizing feature.

---

## 1. openai.yaml Updates

### 1.1 Main Tool Description (`createAutoTradePlan`)

**File**: `openai.yaml`  
**Location**: Around line 2173 (in the main tool description)

**Action**: Add dynamic lot sizing explanation to the tool description

**Add this text** to the description (after the existing content):
```
🎯 **DYNAMIC LOT SIZING:** The `volume` parameter supports automatic lot size calculation based on plan confidence. If `volume` is not specified or set to 0.01, the system automatically calculates lot size based on the number and quality of conditions:
- More conditions = Higher confidence = Larger lot size
- Max lot sizes: BTC/XAU = 0.03, Forex = 0.05
- Base lot size: 0.01 (minimum)
- Confidence is calculated from: structure_confirmation, CHOCH/BOS, order blocks, confluence scores, rejection patterns, etc.
- To override auto-calculation, explicitly set volume to desired value (> 0.01)
- Calculated confidence and lot size are logged in plan notes for transparency
```

### 1.2 Example Arguments - All Plan Creation Tools

**File**: `openai.yaml`  
**Location**: Multiple locations (see below)

**Action**: Update `volume` parameter in example arguments for all plan creation tools

#### Tool 1: `createAutoTradePlan`
- **Location**: Line ~2182
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

#### Tool 2: `createCHOCHPlan`
- **Location**: Line ~2206
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

#### Tool 3: `createRejectionWickPlan`
- **Location**: Line ~2222
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

#### Tool 4: `createOrderBlockPlan`
- **Location**: Line ~2234
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

#### Tool 5: `createRangeScalpPlan`
- **Location**: Line ~2250
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

#### Tool 6: `createMicroScalpPlan`
- **Location**: Line ~2265
- **Current**: `volume: 0.01`
- **Update to**: `volume: 0.01  # Optional: Auto-calculated based on confidence if not specified`

### 1.3 Volume Parameter Description (if exists separately)

**File**: `openai.yaml`  
**Location**: Check if there's a separate volume parameter description section

**Action**: If volume parameter is documented separately, update description to:
```
volume (optional): Position size in lots. If not specified or set to 0.01, system automatically calculates based on plan confidence (more conditions = higher confidence = larger lot size). Max lot sizes: BTC/XAU = 0.03, Forex = 0.05. Base lot size: 0.01 (minimum). To override auto-calculation, explicitly set volume to desired value (> 0.01). Calculated confidence and lot size are logged in plan notes.
```

---

## 2. ChatGPT Knowledge Documents Updates

### 2.1 File: `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**Location**: After tool parameters section (around line 1007, after the plan creation tools section)

**Action**: Add new section "Dynamic Lot Sizing"

**Add this complete section:**
```markdown
## Dynamic Lot Sizing

The system automatically calculates lot size based on plan confidence when `volume` is not specified or set to 0.01.

### How It Works

1. **Confidence Calculation:**
   - System analyzes all conditions in the plan
   - High-value conditions (structure_confirmation, CHOCH, order_block, etc.) = 3 points each
   - Medium-value conditions (rejection_wick, BOS, FVG, etc.) = 2 points each
   - Confluence scores add bonus points (90+ = +10, 80+ = +8, etc.)
   - Confidence = (total_score / 40), normalized to 0-1

2. **Lot Size Calculation:**
   - BTC/XAU: `lot_size = 0.01 + (confidence * 0.02)` → Max: 0.03
   - Forex: `lot_size = 0.01 + (confidence * 0.04)` → Max: 0.05
   - Base lot size: 0.01 (minimum)

3. **Examples:**
   - High confidence (0.8): BTC → 0.026, Forex → 0.042
   - Medium confidence (0.5): BTC → 0.02, Forex → 0.03
   - Low confidence (0.2): BTC → 0.014, Forex → 0.018

### When to Use Auto vs Manual

**Use Auto (default):**
- Let system calculate based on conditions
- Ensures risk scales with plan quality
- Recommended for most plans
- System logs confidence and calculated lot size in plan notes

**Use Manual (explicit volume):**
- When you want specific lot size regardless of confidence
- For testing or specific risk requirements
- Example: `"volume": 0.02` (overrides auto-calculation)

### Best Practices

1. **Add More Conditions for Higher Confidence:**
   - Include structure_confirmation, CHOCH/BOS, confluence scores
   - Multiple confirmation signals increase confidence
   - Higher confluence scores (80+) significantly boost confidence

2. **Don't Override Unless Necessary:**
   - Let the system calculate automatically
   - Only override if you have specific risk requirements

3. **Review Calculated Lot Sizes:**
   - Check plan notes for confidence percentage and calculated lot size
   - Adjust conditions if lot size is too low/high for your risk tolerance
```

### 2.2 File: `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Location**: In the tool usage section (around line 240, where volume parameter is mentioned)

**Action**: Update volume parameter description

**Find this line:**
```markdown
- `volume` (optional): Position size (default: 0.01)
```

**Replace with:**
```markdown
- `volume` (optional): Position size. If not specified or set to 0.01, system automatically calculates based on plan confidence (more conditions = higher confidence = larger lot size). Max: BTC/XAU = 0.03, Forex = 0.05. To override, explicitly set volume to desired value.
```

---

## 3. Additional Files to Check

### 3.1 Check for Other Volume References

**Files to search:**
- `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`
- `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`
- Any other knowledge documents that mention volume parameter

**Action**: Update any volume parameter descriptions to mention dynamic lot sizing

---

## 4. Implementation Priority

1. **High Priority** (Required for feature to work):
   - ✅ Code implementation (already in plan)
   - ✅ openai.yaml tool description update
   - ✅ Knowledge doc section addition

2. **Medium Priority** (Improves user understanding):
   - ✅ Example argument updates in openai.yaml
   - ✅ Instructions file update

3. **Low Priority** (Nice to have):
   - ✅ Other knowledge doc files (if they exist)

---

## 5. Verification Checklist

After updates, verify:
- [ ] openai.yaml tool description includes dynamic lot sizing explanation
- [ ] All plan creation tool examples show volume as optional with auto-calculation note
- [ ] Knowledge doc has dedicated "Dynamic Lot Sizing" section
- [ ] Instructions file mentions dynamic lot sizing in volume parameter
- [ ] All volume parameter descriptions are consistent
- [ ] Max lot sizes are correct (0.03 for BTC/XAU, 0.05 for Forex)

---

## Notes

- The feature is backward compatible - existing plans with explicit volume will continue to work
- Auto-calculation only triggers when volume is None, 0, or 0.01
- Users can always override by setting volume > 0.01
- Confidence and calculated lot size are logged in plan notes for transparency
