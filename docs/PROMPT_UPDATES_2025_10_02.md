# ChatGPT Prompt Updates - October 2, 2025

## Summary
Updated all ChatGPT prompts to reflect current trading preferences, constraints, and recent system enhancements.

## Changes Applied

### 1. **Main Analysis Prompt** (`infra/openai_service.py`)

#### Added Trading Style & Constraints Section:
```
TRADING STYLE & CONSTRAINTS:
- ONLY scalp or day trading setups - NO swing trades (close within the same session)
- Maximum position size: 0.01 lots (strictly enforced)
- Focus on lower timeframes: M5 and M15 for precise entries
- Broker symbols end with 'c' (e.g., XAUUSDc, BTCUSDc, EURUSDc)
```

#### Added Order Type Selection Guidance:
```
ORDER TYPE SELECTION:
- MARKET: Use when entry is very close to current price (within spread + 0.1%) or immediate execution needed
- PENDING (LIMIT): Use for range fades - entry into pullbacks, away from current price
- PENDING (STOP): Use for breakout continuation - entry beyond current price
- Suggest appropriate entry based on setup quality and current price distance
```

#### Added Bracket/OCO Criteria:
```
BRACKET/OCO CRITERIA (Use Sparingly):
- ONLY recommend OCO brackets for breakout situations:
  * Price at key support/resistance zones
  * Consolidation ranges (low ATR, tight Bollinger Bands)
  * High-impact news events (NFP, CPI, FOMC)
  * Volatility squeezes (Bollinger Band pinches, triangle patterns)
- For normal setups: propose single directional entry
- OCO requires clear breakout potential in BOTH directions
```

### 2. **Prompt Templates** (`infra/prompt_templates.py`)

Updated all three strategy templates (v2) with consistent trading constraints:

#### Trend Pullback Template v2:
- Added scalp/intraday specialization
- Added 0.01 lot maximum constraint
- Added M5/M15 focus for entries

#### Range Fade Template v2:
- Added scalp/intraday specialization
- Added 0.01 lot maximum constraint
- Added M5/M15 focus for entries

#### Breakout Template v2:
- Added scalp/intraday specialization
- Added 0.01 lot maximum constraint
- Added M5/M15 focus for entries
- Added explicit OCO bracket criteria (only for key zones)

## Rationale

### User Preferences (From Memory):
1. **Only scalp/day trading** - No swing trade recommendations [[memory:8487018]]
2. **Maximum 0.01 lots** - Risk management constraint [[memory:8360291]]
3. **Broker symbol convention** - Symbols end with 'c' [[memory:8360289]]
4. **OCO bracket criteria** - Only for breakout situations at key zones [[memory:8574396]]
5. **Lower timeframe focus** - M5/M15 for scalp trades [[memory:8361312]]

### Recent System Enhancements:
1. **Order Type Selection** - User can now choose Market/Pending/OCO via buttons
2. **Pending Order Fix** - Correctly handles pending order callbacks
3. **Prompt Router** - Regime-aware analysis with strategy-specific templates
4. **Enhanced Feature Builder** - Cross-timeframe analysis, pattern detection, structure

## Benefits

### 1. **Consistency**
- All prompts now reflect the same trading style and constraints
- LLM will consistently recommend scalp/day trades only
- Maximum lot size enforced at prompt level

### 2. **Better Order Type Recommendations**
- Clear guidance on when to use Market vs Pending orders
- Proper distance-based logic for order type selection
- Explicit criteria for OCO brackets

### 3. **Improved Trade Quality**
- Focus on lower timeframes aligns with scalp trading style
- OCO brackets only suggested for appropriate setups
- No more swing trade recommendations

### 4. **User Experience**
- Recommendations match user's trading style preferences
- Order type suggestions align with available buttons
- Clearer rationale for suggested entry types

## Testing Recommendations

1. **Test Scalp Trade Recognition**:
   - Request trades on M5/M15 timeframes
   - Verify no swing trades are recommended
   - Check that TP targets are within-session

2. **Test Order Type Logic**:
   - Verify Market orders suggested when price is close to entry
   - Verify Pending orders suggested when entry is away from price
   - Check that order type rationale is clear

3. **Test OCO Bracket Criteria**:
   - Request trade during consolidation → should suggest OCO
   - Request normal pullback trade → should NOT suggest OCO
   - Verify OCO only appears at key breakout zones

4. **Test Lot Size Enforcement**:
   - Verify all recommendations use 0.01 lots maximum
   - Check that risk calculations respect lot size limit

## Files Modified

- `infra/openai_service.py` - Main analysis prompt (lines 381-439)
- `infra/prompt_templates.py` - All v2 templates (trend_pullback, range_fade, breakout)

## Next Steps

1. Monitor trade recommendations for consistency with new prompts
2. Gather feedback on order type suggestions
3. Fine-tune OCO bracket criteria based on usage patterns
4. Consider adding prompt version tracking for A/B testing

## Notes

- Prompt Router (v2 templates) are currently active by default
- Original fallback prompt also updated for consistency
- Changes are backward compatible with existing code
- No database migrations required

