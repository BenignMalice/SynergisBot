# Dynamic Lot Sizing Implementation Plan (Updated with Fixes)

## Overview
Implement dynamic lot sizing for auto-execution plans based on plan confidence/success probability. More conditions = higher confidence = larger lot size.

**Max Lot Sizes:**
- BTC/XAU: 0.03
- Forex: 0.05
- Base lot size: 0.01 (minimum)

**⚠️ FIXED ISSUES:**
1. ✅ Aligned max lot sizes with plan (was 0.02/0.04 in openai.yaml, now 0.03/0.05)
2. ✅ Fixed volume detection logic (check for None/0, not just 0.01)
3. ✅ Increased max_possible_score to 60 for better confidence scaling
4. ✅ Added proper integration point after conditions validation
5. ✅ Added confidence field to plan response for transparency

---

## 1. Confidence Scoring System (UPDATED)

### 1.1 Condition Categories & Weights

**High-Value Conditions (Weight: 3 points each):**
- `structure_confirmation: true` - Strong structure validation
- `choch_bull: true` / `choch_bear: true` - Clear structure break
- `order_block: true` - Institutional level
- `breaker_block: true` - Strong reversal signal
- `mss_bull: true` / `mss_bear: true` - Market structure shift
- `liquidity_sweep: true` - High probability reversal
- `range_scalp_confluence >= 80` - High confluence score
- `min_confluence >= 80` - High confluence score

**Medium-Value Conditions (Weight: 2 points each):**
- `rejection_wick: true` - Rejection pattern
- `bos_bull: true` / `bos_bear: true` - Break of structure
- `fvg_bull: true` / `fvg_bear: true` - Fair value gap
- `mitigation_block_bull: true` / `mitigation_block_bear: true` - Mitigation level
- `equal_highs: true` / `equal_lows: true` - Range confirmation
- `vwap_deviation: true` - Mean reversion signal
- `range_scalp_confluence >= 70` - Medium confluence
- `min_confluence >= 70` - Medium confluence
- `volume_confirmation: true` - Volume validation
- `volume_spike: true` - Strong volume signal

**Low-Value Conditions (Weight: 1 point each):**
- `price_near` + `tolerance` - Basic price proximity (required, but low weight)
- `timeframe` - Timeframe specification
- `structure_timeframe` - Structure timeframe
- `bb_expansion: true` - Bollinger band expansion
- `bb_squeeze: true` - Bollinger band squeeze
- `inside_bar: true` - Inside bar pattern
- `range_scalp_confluence >= 50` - Low confluence
- `min_confluence >= 50` - Low confluence
- `plan_type` - Plan type specification

**Confluence Score Bonus:**
- `range_scalp_confluence` or `min_confluence` value directly adds to score:
  - 90-100: +10 points
  - 80-89: +8 points
  - 70-79: +5 points
  - 60-69: +3 points
  - 50-59: +1 point

### 1.2 Confidence Calculation Formula (UPDATED)

**FIXED:** Increased max_possible_score from 50 to 60 for better scaling

```python
def calculate_plan_confidence(conditions: Dict[str, Any]) -> float:
    """
    Calculate confidence score (0-1) based on conditions.
    
    Returns:
        float: Confidence score from 0.0 to 1.0 (0-100%)
    """
    score = 0
    max_possible_score = 60  # UPDATED: Increased from 50 to 60 for better scaling
    
    # High-value conditions (3 points each)
    high_value_conditions = [
        "structure_confirmation",
        "choch_bull", "choch_bear",
        "order_block", "breaker_block",
        "mss_bull", "mss_bear",
        "liquidity_sweep"
    ]
    
    # Medium-value conditions (2 points each)
    medium_value_conditions = [
        "rejection_wick",
        "bos_bull", "bos_bear",
        "fvg_bull", "fvg_bear",
        "mitigation_block_bull", "mitigation_block_bear",
        "equal_highs", "equal_lows",
        "vwap_deviation",
        "volume_confirmation", "volume_spike"
    ]
    
    # Count high-value conditions
    for condition in high_value_conditions:
        if conditions.get(condition) is True:
            score += 3
    
    # Count medium-value conditions
    for condition in medium_value_conditions:
        if conditions.get(condition) is True:
            score += 2
    
    # Add confluence bonus
    confluence = conditions.get("range_scalp_confluence") or conditions.get("min_confluence")
    if confluence and isinstance(confluence, (int, float)):
        if confluence >= 90:
            score += 10
        elif confluence >= 80:
            score += 8
        elif confluence >= 70:
            score += 5
        elif confluence >= 60:
            score += 3
        elif confluence >= 50:
            score += 1
    
    # Normalize to 0-1 range
    confidence = min(score / max_possible_score, 1.0)
    
    return confidence
```

---

## 2. Code Implementation (UPDATED)

### 2.1 New File: `infra/lot_size_calculator.py`

**No changes needed** - code is correct as specified in original plan.

### 2.2 Update `chatgpt_auto_execution_integration.py` (FIXED)

**Location**: In `create_trade_plan` method, after conditions validation (after line 102)

**FIXED:** Changed volume detection from `volume == 0.01` to `volume is None or volume == 0 or volume == 0.01`

```python
# After line 102 (after conditions validation)

# ========== DYNAMIC LOT SIZING (Based on Confidence) ==========
try:
    from infra.lot_size_calculator import LotSizeCalculator
    
    # FIXED: Check if volume is not explicitly provided or is default (0.01)
    # This allows users to override by explicitly setting volume > 0.01
    if volume is None or volume == 0 or volume == 0.01:
        calculator = LotSizeCalculator()
        calculated_lot_size, confidence = calculator.calculate_plan_lot_size(
            symbol=symbol_normalized,
            conditions=conditions,
            base_lot_size=0.01
        )
        
        # Use calculated lot size
        volume = calculated_lot_size
        
        # Add confidence info to notes if not present
        if notes:
            notes += f" [Confidence: {confidence:.0%}, Auto Lot: {volume}]"
        else:
            notes = f"Confidence: {confidence:.0%}, Auto Lot: {volume}"
        
        logger.info(
            f"Auto-calculated lot size for plan {plan_id}: {volume} "
            f"(confidence: {confidence:.2f}, conditions: {len(conditions)} conditions)"
        )
    else:
        # Volume was explicitly provided (> 0.01), use it (user override)
        logger.info(f"Using explicit volume {volume} for plan {plan_id} (user override)")
except Exception as e:
    logger.warning(f"Dynamic lot sizing failed (non-critical): {e}, using default volume")
    # Fall back to default volume if calculation fails
    if volume is None or volume == 0:
        volume = 0.01
```

### 2.3 Update `auto_execution_system.py` (UPDATED)

**Location**: In `_validate_plan_data` method, add lot size validation

**FIXED:** Updated max lot sizes to match plan (0.03 for BTC/XAU, 0.05 for Forex)

```python
# After line 860 (volume validation)

# Validate lot size against symbol-specific maximums
symbol_upper = symbol.upper()
if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
    max_lot_size = 0.03  # UPDATED: Was 0.02, now 0.03
else:
    max_lot_size = 0.05  # UPDATED: Was 0.04, now 0.05

if volume > max_lot_size:
    return False, f"Lot size {volume} exceeds maximum for {symbol} (max: {max_lot_size})"
```

---

## 3. openai.yaml Updates Required

### 3.1 Update `createAutoTradePlan` Tool

**Location**: Around line 2182 (in the example arguments)

**Current:**
```yaml
volume: 0.01
```

**Update to:**
```yaml
volume: 0.01  # Optional: If not specified or 0.01, system auto-calculates based on plan confidence. Max: BTC/XAU=0.03, Forex=0.05
```

### 3.2 Update Volume Description in Tool Description

**Location**: In the main tool description (around line 2173)

**Add to description:**
```
🎯 **DYNAMIC LOT SIZING:** The `volume` parameter supports automatic lot size calculation based on plan confidence. If `volume` is not specified or set to 0.01, the system automatically calculates lot size based on the number and quality of conditions:
- More conditions = Higher confidence = Larger lot size
- Max lot sizes: BTC/XAU = 0.03, Forex = 0.05
- Base lot size: 0.01 (minimum)
- Confidence is calculated from: structure_confirmation, CHOCH/BOS, order blocks, confluence scores, rejection patterns, etc.
- To override auto-calculation, explicitly set volume to desired value (> 0.01)
- Calculated confidence and lot size are logged in plan notes for transparency
```

### 3.3 Update All Other Plan Creation Tools

**Tools to update:**
- `createCHOCHPlan` (line ~2206)
- `createRejectionWickPlan` (line ~2222)
- `createOrderBlockPlan` (line ~2234)
- `createRangeScalpPlan` (line ~2250)
- `createMicroScalpPlan` (line ~2265)

**For each tool, update the `volume` parameter in example:**
```yaml
volume: 0.01  # Optional: Auto-calculated based on confidence if not specified
```

---

## 4. Knowledge Documents Updates Required

### 4.1 File: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**Location**: After the tool parameters section (around line 1007)

**Add new section:**
```markdown
## Dynamic Lot Sizing

The system automatically calculates lot size based on plan confidence when `volume` is not specified or set to 0.01.

### How It Works

1. **Confidence Calculation:**
   - System analyzes all conditions in the plan
   - High-value conditions (structure_confirmation, CHOCH, order_block, etc.) = 3 points each
   - Medium-value conditions (rejection_wick, BOS, FVG, etc.) = 2 points each
   - Confluence scores add bonus points (90+ = +10, 80+ = +8, etc.)
   - Confidence = (total_score / 60), normalized to 0-1

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

### 4.2 File: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Location**: In the tool usage section (around line 240)

**Update the volume parameter description:**
```markdown
- `volume` (optional): Position size. If not specified or set to 0.01, system automatically calculates based on plan confidence (more conditions = higher confidence = larger lot size). Max: BTC/XAU = 0.03, Forex = 0.05. To override, explicitly set volume to desired value.
```

---

## 5. Implementation Checklist (UPDATED)

- [ ] Create `infra/lot_size_calculator.py`
- [ ] Update `chatgpt_auto_execution_integration.py` to use calculator (FIXED: volume detection)
- [ ] Update `auto_execution_system.py` validation (FIXED: max lot sizes)
- [ ] Update `openai.yaml` tool descriptions (all plan creation tools)
- [ ] Update `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
- [ ] Update `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
- [ ] Add unit tests
- [ ] Test with real plans
- [ ] Verify confidence calculation in plan notes

---

## 6. Summary of Fixes

1. **Volume Detection Logic**: Changed from `volume == 0.01` to `volume is None or volume == 0 or volume == 0.01` to properly detect when user wants auto-calculation vs explicit override

2. **Max Lot Sizes**: Updated from 0.02/0.04 to 0.03/0.05 to match plan requirements

3. **Confidence Scaling**: Increased max_possible_score from 50 to 60 for better confidence distribution

4. **Integration Point**: Confirmed correct location (after conditions validation, before plan save)

5. **Documentation**: Added comprehensive updates for both openai.yaml and knowledge docs

---

## 7. Testing Plan (No Changes)

Same as original plan - test with various condition combinations to verify confidence and lot size calculations.
