# Dynamic Lot Sizing Implementation Plan

## Overview
Implement dynamic lot sizing for auto-execution plans based on plan confidence/success probability. More conditions = higher confidence = larger lot size.

**Max Lot Sizes:**
- BTC/XAU: 0.03
- Forex: 0.05
- Base lot size: 0.01 (minimum)

---

## 1. Confidence Scoring System

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

### 1.2 Confidence Calculation Formula

```python
def calculate_plan_confidence(conditions: Dict[str, Any]) -> float:
    """
    Calculate confidence score (0-100) based on conditions.
    
    Returns:
        float: Confidence score from 0.0 to 1.0 (0-100%)
    """
    score = 0
    max_possible_score = 50  # Theoretical maximum
    
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
    if confluence:
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

### 1.3 Example Confidence Scores

**High Confidence (0.7-1.0):**
- Structure confirmation + CHOCH + Confluence >= 80 = ~0.75
- Order block + Rejection wick + Confluence >= 85 = ~0.80
- Liquidity sweep + CHOCH + Structure confirmation + Confluence >= 90 = ~0.95

**Medium Confidence (0.4-0.7):**
- Structure confirmation + Confluence >= 70 = ~0.50
- Rejection wick + VWAP deviation + Confluence >= 75 = ~0.55
- Equal highs/lows + Confluence >= 70 = ~0.45

**Low Confidence (0.0-0.4):**
- Price near only = ~0.10
- Price near + Low confluence (50-60) = ~0.20
- Basic conditions only = ~0.15

---

## 2. Lot Size Calculation

### 2.1 Lot Size Formula

```python
def calculate_dynamic_lot_size(
    symbol: str,
    confidence: float,
    base_lot_size: float = 0.01
) -> float:
    """
    Calculate lot size based on symbol type and confidence.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDc", "XAUUSDc", "EURUSDc")
        confidence: Confidence score (0.0 to 1.0)
        base_lot_size: Minimum lot size (default: 0.01)
    
    Returns:
        float: Calculated lot size
    """
    # Determine max lot size based on symbol type
    symbol_upper = symbol.upper()
    if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
        max_lot_size = 0.03
    else:
        # Forex pairs
        max_lot_size = 0.05
    
    # Calculate lot size: base + (confidence * (max - base))
    lot_size = base_lot_size + (confidence * (max_lot_size - base_lot_size))
    
    # Round to 2 decimal places
    lot_size = round(lot_size, 2)
    
    # Ensure it's within bounds
    lot_size = max(base_lot_size, min(lot_size, max_lot_size))
    
    return lot_size
```

### 2.2 Lot Size Examples

**BTC/XAU (Max: 0.03):**
- Confidence 0.0 → 0.01 (base)
- Confidence 0.5 → 0.02 (mid)
- Confidence 1.0 → 0.03 (max)

**Forex (Max: 0.05):**
- Confidence 0.0 → 0.01 (base)
- Confidence 0.5 → 0.03 (mid)
- Confidence 1.0 → 0.05 (max)

---

## 3. Code Implementation

### 3.1 New File: `infra/lot_size_calculator.py`

```python
"""
Dynamic Lot Size Calculator
Calculates lot size based on plan confidence and symbol type.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class LotSizeCalculator:
    """Calculate dynamic lot sizes based on plan confidence"""
    
    # Condition weights
    HIGH_VALUE_WEIGHT = 3
    MEDIUM_VALUE_WEIGHT = 2
    LOW_VALUE_WEIGHT = 1
    
    # High-value conditions
    HIGH_VALUE_CONDITIONS = [
        "structure_confirmation",
        "choch_bull", "choch_bear",
        "order_block", "breaker_block",
        "mss_bull", "mss_bear",
        "liquidity_sweep"
    ]
    
    # Medium-value conditions
    MEDIUM_VALUE_CONDITIONS = [
        "rejection_wick",
        "bos_bull", "bos_bear",
        "fvg_bull", "fvg_bear",
        "mitigation_block_bull", "mitigation_block_bear",
        "equal_highs", "equal_lows",
        "vwap_deviation",
        "volume_confirmation", "volume_spike"
    ]
    
    def calculate_confidence(self, conditions: Dict[str, Any]) -> float:
        """
        Calculate confidence score (0-1) based on conditions.
        
        Args:
            conditions: Plan conditions dictionary
        
        Returns:
            float: Confidence score from 0.0 to 1.0
        """
        if not conditions:
            return 0.0
        
        score = 0
        max_possible_score = 50  # Theoretical maximum
        
        # Count high-value conditions
        for condition in self.HIGH_VALUE_CONDITIONS:
            if conditions.get(condition) is True:
                score += self.HIGH_VALUE_WEIGHT
        
        # Count medium-value conditions
        for condition in self.MEDIUM_VALUE_CONDITIONS:
            if conditions.get(condition) is True:
                score += self.MEDIUM_VALUE_WEIGHT
        
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
        
        logger.debug(f"Plan confidence calculated: {confidence:.2f} (score: {score})")
        
        return confidence
    
    def calculate_lot_size(
        self,
        symbol: str,
        confidence: float,
        base_lot_size: float = 0.01
    ) -> float:
        """
        Calculate lot size based on symbol type and confidence.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc", "XAUUSDc", "EURUSDc")
            confidence: Confidence score (0.0 to 1.0)
            base_lot_size: Minimum lot size (default: 0.01)
        
        Returns:
            float: Calculated lot size
        """
        # Determine max lot size based on symbol type
        symbol_upper = symbol.upper()
        if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
            max_lot_size = 0.03
        else:
            # Forex pairs
            max_lot_size = 0.05
        
        # Calculate lot size: base + (confidence * (max - base))
        lot_size = base_lot_size + (confidence * (max_lot_size - base_lot_size))
        
        # Round to 2 decimal places
        lot_size = round(lot_size, 2)
        
        # Ensure it's within bounds
        lot_size = max(base_lot_size, min(lot_size, max_lot_size))
        
        logger.info(
            f"Calculated lot size for {symbol}: {lot_size} "
            f"(confidence: {confidence:.2f}, max: {max_lot_size})"
        )
        
        return lot_size
    
    def calculate_plan_lot_size(
        self,
        symbol: str,
        conditions: Dict[str, Any],
        base_lot_size: float = 0.01
    ) -> tuple[float, float]:
        """
        Calculate lot size for a plan based on conditions.
        
        Args:
            symbol: Trading symbol
            conditions: Plan conditions dictionary
            base_lot_size: Minimum lot size (default: 0.01)
        
        Returns:
            tuple: (lot_size, confidence) - Calculated lot size and confidence score
        """
        confidence = self.calculate_confidence(conditions)
        lot_size = self.calculate_lot_size(symbol, confidence, base_lot_size)
        
        return lot_size, confidence
```

### 3.2 Update `chatgpt_auto_execution_integration.py`

**Location**: In `create_trade_plan` method, after conditions validation

```python
# After line 102 (after conditions validation)

# ========== DYNAMIC LOT SIZING (Based on Confidence) ==========
try:
    from infra.lot_size_calculator import LotSizeCalculator
    
    # If volume is not explicitly provided or is default (0.01), calculate dynamically
    if volume is None or volume == 0.01:
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
        # Volume was explicitly provided, use it (user override)
        logger.info(f"Using explicit volume {volume} for plan {plan_id} (user override)")
except Exception as e:
    logger.warning(f"Dynamic lot sizing failed (non-critical): {e}, using default volume")
    # Fall back to default volume if calculation fails
    if volume is None or volume == 0:
        volume = 0.01
```

### 3.3 Update `auto_execution_system.py`

**Location**: In `_validate_plan_data` method, add lot size validation

```python
# After line 860 (volume validation)

# Validate lot size against symbol-specific maximums
symbol_upper = symbol.upper()
if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
    max_lot_size = 0.03
else:
    max_lot_size = 0.05

if volume > max_lot_size:
    return False, f"Lot size {volume} exceeds maximum for {symbol} (max: {max_lot_size})"
```

---

## 4. ChatGPT Integration

### 4.1 Update Tool Descriptions

**In `openai.yaml` and knowledge docs:**

Add to `create_auto_trade_plan` tool description:

```yaml
volume:
  type: number
  description: |
    Lot size for the trade. If not specified or set to 0.01, the system will 
    automatically calculate lot size based on plan confidence:
    - More conditions = Higher confidence = Larger lot size
    - Max lot sizes: BTC/XAU = 0.03, Forex = 0.05
    - Base lot size: 0.01 (minimum)
    - Confidence is calculated from: structure confirmation, CHOCH/BOS, 
      order blocks, confluence scores, rejection patterns, etc.
    - To override auto-calculation, explicitly set volume to desired value.
  default: 0.01
```

### 4.2 Update Knowledge Documents

**Add section to `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`:**

```markdown
## Dynamic Lot Sizing

The system automatically calculates lot size based on plan confidence when `volume` is not specified or set to 0.01.

### How It Works

1. **Confidence Calculation:**
   - System analyzes all conditions in the plan
   - High-value conditions (structure_confirmation, CHOCH, order_block, etc.) = 3 points each
   - Medium-value conditions (rejection_wick, BOS, FVG, etc.) = 2 points each
   - Confluence scores add bonus points (90+ = +10, 80+ = +8, etc.)
   - Confidence = (total_score / max_possible_score), normalized to 0-1

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

---

## 5. Testing Plan

### 5.1 Unit Tests

```python
# tests/test_lot_size_calculator.py

def test_confidence_calculation():
    calculator = LotSizeCalculator()
    
    # High confidence plan
    conditions = {
        "structure_confirmation": True,
        "choch_bull": True,
        "range_scalp_confluence": 85
    }
    confidence = calculator.calculate_confidence(conditions)
    assert confidence >= 0.6
    
    # Low confidence plan
    conditions = {
        "price_near": 88000,
        "tolerance": 100
    }
    confidence = calculator.calculate_confidence(conditions)
    assert confidence < 0.3

def test_lot_size_calculation():
    calculator = LotSizeCalculator()
    
    # BTC high confidence
    lot_size = calculator.calculate_lot_size("BTCUSDc", 0.8, 0.01)
    assert 0.02 <= lot_size <= 0.03
    
    # Forex high confidence
    lot_size = calculator.calculate_lot_size("EURUSDc", 0.8, 0.01)
    assert 0.03 <= lot_size <= 0.05
    
    # Low confidence
    lot_size = calculator.calculate_lot_size("BTCUSDc", 0.2, 0.01)
    assert lot_size < 0.015
```

### 5.2 Integration Tests

1. Create plan with many conditions → Verify high lot size
2. Create plan with few conditions → Verify low lot size
3. Create plan with explicit volume → Verify override works
4. Test with BTC/XAU symbols → Verify max 0.03
5. Test with Forex symbols → Verify max 0.05

---

## 6. Implementation Checklist

- [ ] Create `infra/lot_size_calculator.py`
- [ ] Update `chatgpt_auto_execution_integration.py` to use calculator
- [ ] Update `auto_execution_system.py` validation
- [ ] Update `openai.yaml` tool descriptions
- [ ] Update knowledge documents
- [ ] Add unit tests
- [ ] Test with real plans
- [ ] Document confidence calculation in plan notes

---

## 7. Rollout Plan

1. **Phase 1**: Implement calculator and integrate into plan creation
2. **Phase 2**: Update ChatGPT knowledge docs
3. **Phase 3**: Monitor and adjust weights if needed
4. **Phase 4**: Add confidence display to plan status responses

---

## Notes

- Confidence calculation is additive (more conditions = higher confidence)
- Confluence scores have significant impact on confidence
- Users can always override by explicitly setting volume
- System logs confidence and calculated lot size for transparency
