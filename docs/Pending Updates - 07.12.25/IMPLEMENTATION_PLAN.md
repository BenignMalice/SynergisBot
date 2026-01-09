# Implementation Plan - Knowledge Documents Alignment Fixes

**Date**: 2025-12-07  
**Based on**: `REVIEW_ALIGNMENT_ANALYSIS.md`  
**Status**: Planning Phase

---

## 📋 PRIORITY 1 FIXES (Critical - Fix Immediately)

### Fix 1: Add Strategy Type Mapping Section

**Target File**: `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Action**: Add a new section after "STRATEGY_FAMILIES" that maps strategy families to exact enum values.

**Content to Add**:
```markdown
## STRATEGY_FAMILY_TO_ENUM_MAPPING

When creating auto-execution plans, ChatGPT MUST use the exact `strategy_type` enum values from the codebase, not strategy family names.

### Mapping Table

| Strategy Family | StrategyType Enum Value | Use Case |
|----------------|------------------------|----------|
| trend_continuation | `trend_continuation_pullback` | Trend pullback to OB/FVG |
| mean_reversion | `mean_reversion_range_scalp` | Range-bound mean reversion |
| sweep_reversion | `liquidity_sweep_reversal` | Sweep → CHOCH reversals |
| breakout | `breakout_ib_volatility_trap` | Inside bar/volatility trap breakouts |
| volatility_trap | `breakout_ib_volatility_trap` | Compression → expansion |
| premium_discount | `premium_discount_array` | Premium/discount zone entries |
| smc_alignment | `order_block_rejection` | Order block-based setups |
| breaker_block | `breaker_block` | Failed OB retest |
| market_structure_shift | `market_structure_shift` | MSS continuation |
| fvg_retracement | `fvg_retracement` | FVG fill entries |
| mitigation_block | `mitigation_block` | Last candle before break |
| inducement_reversal | `inducement_reversal` | Liquidity grab reversals |
| session_liquidity_run | `session_liquidity_run` | Session liquidity sweeps |
| kill_zone | `kill_zone` | High volatility session windows |
| micro_scalp | `micro_scalp` | Ultra-short-term scalps |

### London Breakout Strategy

**Important**: "London Breakout" is a **workflow/analysis method**, not a strategy type enum value.

When creating plans for London Breakout setups:
- Use `strategy_type: "breakout_ib_volatility_trap"` in the plan
- Follow `LONDON_BREAKOUT_ANALYSIS_WORKFLOW_EMBEDDING.md` for validation
- The workflow determines if the setup is valid, but the enum value is `breakout_ib_volatility_trap`

### Rules

1. **NEVER** use strategy family names as `strategy_type` values
2. **ALWAYS** map to the exact enum value from the table above
3. If unsure which enum value to use, default to `breakout_ib_volatility_trap` for breakouts or `trend_continuation_pullback` for trends
4. London Breakout workflows → use `breakout_ib_volatility_trap` enum value
```

**Files to Update**:
- `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Add mapping section
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Add reference to mapping
- `SMC_MASTER_EMBEDDING.md` - Add enum value references in strategy selection

---

### Fix 2: Standardize Session Times

**Target Files**: All documents that reference session times

**Action**: Create a single source of truth and update all documents.

**Standard Session Times (from codebase analysis)**:
- **ASIAN**: 00:00-08:00 UTC
- **LONDON**: 08:00-13:00 UTC (core), 08:00-16:00 UTC (extended for some logic)
- **LONDON-NY OVERLAP**: 13:00-16:00 UTC
- **NEW YORK**: 16:00-21:00 UTC (or 13:00-21:00 UTC in some contexts)
- **LATE NY**: 21:00-00:00 UTC

**London Breakout Specific**:
- **London Breakout Window**: 07:00-10:00 UTC (special case for breakout strategy)
- **Primary Window**: 07:00-07:30 UTC
- **Secondary Window**: 07:30-08:15 UTC
- **Extended Window**: 08:15-10:00 UTC (if displacement clean)

**Content to Add to `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`**:
```markdown
# SESSION_WINDOWS (STANDARDIZED - UTC)

Session definitions (UTC-based, standard across all documents):

standard_sessions:
  asian: "00:00–08:00 UTC"
  london: "08:00–13:00 UTC" (core), "08:00–16:00 UTC" (extended)
  london_ny_overlap: "13:00–16:00 UTC"
  new_york: "16:00–21:00 UTC"
  late_ny: "21:00–00:00 UTC"

london_breakout_special_window:
  primary: "07:00–07:30 UTC"
  secondary: "07:30–08:15 UTC"
  extended: "08:15–10:00 UTC" (if displacement clean)
  invalid_before: "<07:00 UTC"
  invalid_after: ">10:00 UTC"
```

**Files to Update**:
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Update session_windows section
- `LONDON_BREAKOUT_ANALYSIS_WORKFLOW_EMBEDDING.md` - Verify times match
- `LONDON_BREAKOUT_STRATEGY_EMBEDDING.md` - Verify times match
- `GOLD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - Update London Open time
- `FOREX_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - Add session time references
- `SYMBOL_GUIDE_EMBEDDING.md` - Add session time references

---

### Fix 3: Clarify London Breakout Strategy Type

**Target Files**: All documents referencing London Breakout

**Action**: Add explicit clarification that London Breakout maps to `breakout_ib_volatility_trap`.

**Content to Add**:
```markdown
## LONDON_BREAKOUT_STRATEGY_TYPE_CLARIFICATION

**Critical**: "London Breakout" is a **workflow/analysis method**, not a `StrategyType` enum value.

When creating auto-execution plans for London Breakout setups:
- **Workflow**: Follow `LONDON_BREAKOUT_ANALYSIS_WORKFLOW_EMBEDDING.md` for validation
- **Strategy Type**: Use `strategy_type: "breakout_ib_volatility_trap"` in the plan
- **Reasoning**: London Breakout is a specific application of the Inside Bar Volatility Trap strategy

The workflow determines if the setup is valid (Asian range intact, London session, volatility expansion, etc.), but the enum value used in the plan is `breakout_ib_volatility_trap`.
```

**Files to Update**:
- `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Add clarification
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Add clarification
- `LONDON_BREAKOUT_ANALYSIS_WORKFLOW_EMBEDDING.md` - Add note about enum mapping
- `LONDON_BREAKOUT_STRATEGY_EMBEDDING.md` - Add note about enum mapping
- `GOLD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - Update references
- `FOREX_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - Update references

---

## 📋 PRIORITY 2 FIXES (Important - Fix Soon)

### Fix 4: Unify Regime Classification

**Target Files**: All documents with regime lists

**Action**: Create master regime list and update all documents to reference it.

**Master Regime List** (to be added to `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`):
```markdown
# MARKET_REGIME_CLASSIFICATION (MASTER LIST)

All documents MUST use these exact regime names:

valid_regimes:
  - trending
  - ranging
  - compression
  - expansion
  - reversal
  - chop

invalid_regimes_for_plans:
  - chop (unless micro-scalp approved)
  - volatility_shock
  - exhaustion

regime_variants:
  - ranging_expansion (variant of ranging + expansion)
  - compression_expansion (variant of compression + expansion)
  - trend_exhaustion (variant of trending + exhaustion)
  - liquidity_coil (variant of compression)

Note: Variants are combinations of base regimes. Use base regime name when creating plans.
```

**Files to Update**:
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Add master list
- `LONDON_BREAKOUT_ANALYSIS_WORKFLOW_EMBEDDING.md` - Update regime list
- `SMC_MASTER_EMBEDDING.md` - Update regime list
- `ChatGPT_Knowledge_Volatility_Regime_Trading_EMBEDDING.md` - Reference master list

---

### Fix 5: Add Explicit Tool References

**Target Files**: Documents that mention tool usage

**Action**: Add explicit tool name references.

**Content to Add**:
```markdown
## TOOL_REFERENCES (EXPLICIT)

ChatGPT MUST use these exact tool names:

price_fetching:
  - tool: `moneybot.getCurrentPrice` (or equivalent from openai.yaml)
  - when: Before ANY analysis, regime classification, or plan creation

analysis:
  - tool: `moneybot.analyse_symbol_full`
  - returns: `response.summary` (formatted analysis) and `response.data` (structured data)

auto_execution_plans:
  - tool: `moneybot.create_auto_trade_plan` (general plans)
  - tool: `moneybot.create_choch_plan` (CHOCH-specific)
  - tool: `moneybot.create_rejection_wick_plan` (rejection wick-specific)
  - tool: `moneybot.create_order_block_plan` (order block-specific)
  - tool: `moneybot.create_range_scalp_plan` (range scalping-specific)
  - tool: `moneybot.create_micro_scalp_plan` (micro-scalp-specific)
  - tool: `moneybot.create_bracket_trade_plan` (bracket trades)
```

**Files to Update**:
- `KNOWLEDGE_DOC_EMBEDDING.md` - Add tool references section
- `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Add tool references
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Add tool references

---

### Fix 6: Standardize Volatility Terminology

**Target Files**: All documents with volatility states

**Action**: Create standard volatility state names and update all documents.

**Standard Volatility States** (to be added to `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`):
```markdown
# VOLATILITY_STATES (STANDARDIZED)

All documents MUST use these exact volatility state names:

volatility_states:
  - low (or LOW_COMPRESSION)
  - stable (or STABLE_RANGING)
  - expanding (or EXPANDING_BREAKOUT)
  - high (or HIGH_EXTREME)
  - unstable
  - collapsing

mapping_rules:
  - LOW_COMPRESSION → low
  - STABLE_RANGING → stable
  - EXPANDING_BREAKOUT → expanding
  - HIGH_EXTREME → high
  - stable_or_expanding → stable (if stable) or expanding (if expanding)
  - expanding_or_stable → expanding (if expanding) or stable (if stable)
  - contracting → collapsing
```

**Files to Update**:
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Add standard states
- `ChatGPT_Knowledge_Volatility_Regime_Trading_EMBEDDING.md` - Update to use standard names
- `SMC_MASTER_EMBEDDING.md` - Update volatility references

---

## 📋 IMPLEMENTATION ORDER

### Phase 1: Critical Fixes (Do First)
1. ✅ Fix 1: Add Strategy Type Mapping
2. ✅ Fix 2: Standardize Session Times
3. ✅ Fix 3: Clarify London Breakout Strategy Type

### Phase 2: Important Fixes (Do Next)
4. ✅ Fix 4: Unify Regime Classification
5. ✅ Fix 5: Add Explicit Tool References
6. ✅ Fix 6: Standardize Volatility Terminology

### Phase 3: Verification
7. ✅ Re-run alignment check
8. ✅ Verify all enum values match codebase
9. ✅ Verify all session times are consistent
10. ✅ Verify all tool names match openai.yaml

---

## 📝 NOTES

- All fixes should maintain backward compatibility where possible
- Document changes should be minimal and focused
- Preserve all existing logic and rules
- Only add clarifications and mappings, don't remove content
- Test that ChatGPT can still understand and use the documents after changes

---

# END_OF_PLAN

