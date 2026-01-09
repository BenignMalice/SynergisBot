# Range Scalping Plan - Key Changes Summary

## 🔄 Changes from Original Plan

### 1. Position Sizing - No Partial Profits

**Original Plan:**
- Risk-based lot sizing with partial profit taking at 0.6R

**Updated Plan:**
- **Fixed 0.01 lots for ALL range scalps**
- **No partial profits** (single position exit only)
- Early exit if conditions deteriorate

**Rationale:**
- 0.01 lot size is too small to split
- Better to exit full position early when risk increases
- Simpler risk management

---

### 2. Dynamic R:R Adjustment - Early Exit Focus

**Original Plan:**
- Partial close at 0.6R
- Move SL to breakeven after 0.3R
- Trail to 2R on strong divergence

**Updated Plan:**
- **Quick move to +0.5R** → Move SL to breakeven (risk off)
- **Stagnant after 1h** → Exit early (energy loss)
- **Strong divergence** → Exit at current profit (preserve gain)
- **Opposite order flow** → Exit at ~0.6R if profitable, exit if losing
- **Range invalidation** → Exit immediately

**No More:**
- ❌ Partial profit taking
- ❌ Trailing to 2R (let it run)
- ❌ Complex position management

**Instead:**
- ✅ Full position exit when conditions deteriorate
- ✅ Breakeven protection after quick move
- ✅ Early exit on stagnation or divergence

---

### 3. Risk Mitigation Framework - Added

**New Components:**

#### A. 3-Confluence Rule (Simplified Entry)
- **Structure**: Range clearly defined (3-touch rule)
- **Location**: Price at edge (VWAP ± 0.75ATR or PDH/PDL)
- **Confirmation**: ONE signal only (RSI OR rejection wick OR tape pressure)

**Why:** Prevents over-optimization, keeps entries simple

#### B. False Range Detection
- Volume increasing inside range → Red flag
- Candle bodies getting larger → Red flag
- VWAP starting to angle → Red flag
- CVD divergence (hidden accumulation) → Red flag

**If 2+ of 4 true** → DO NOT trade (wait for BOS/retest instead)

#### C. Range Invalidation Detection
- Close 2 full candles outside range → STOP
- VWAP slope > 20° → STOP
- BB width expands > 50% from average → STOP
- M15 BOS confirmed → STOP

**If 2+ conditions trigger** → Range invalidated, exit all trades

#### D. Session Filters
- **BLOCKED**: London-NY Overlap (12:00-15:00 UTC)
- **BLOCKED**: First 30 min of London/NY sessions
- **ALLOWED**: Asian, London Mid, Post-NY, NY Late

#### E. Trade Activity Filters
**Required (ALL must be true):**
- Volume > 50% of 1h average
- Price touches ±0.5ATR from VWAP
- Time elapsed since last scalp > 15 min
- No major red news inside 1 hour

**If any false** → Skip trade (dead market)

#### F. Adaptive Anchor Refresh
- If ATR (H1) changes >40% from previous day → Recalc PDH/PDL
- If new session high/low exceeds PDH/PDL by >0.25% and holds 15 min → Replace anchor

**Why:** Prevents using outdated levels during volatility shifts

#### G. Nested Range Alignment
- **Hierarchy**: H1 → M15 → M5
- **Rule**: M15 defines active range, M5 must align for entry
- **Conflict**: If M15 and M5 conflict → Do nothing

---

### 4. Early Exit Manager - New Component

**File:** `infra/range_scalping_exit_manager.py`

**Early Exit Triggers:**
1. **Range Invalidation** → Exit immediately (critical)
2. **Quick Move to +0.5R** → Move SL to breakeven (risk off)
3. **Stagnant After 1h** → Exit early (energy loss)
4. **Strong Divergence** → Exit at current profit (preserve gain)
5. **Opposite Order Flow** → Exit at ~0.6R if profitable

**No More:**
- Complex partial profit management
- Multi-tier exit strategies
- Position scaling

**Instead:**
- Simple full position exit
- Breakeven protection
- Risk-first mentality

---

### 5. Configuration Changes

**New Config Files:**
- `config/range_scalping_risk_filters.py` → Risk mitigation logic
- `config/range_scalping_exit_config.json` → Early exit rules
- Updated `config/range_scalping_config.json` → Risk filter settings

**Removed from Config:**
- Partial profit taking rules
- Position scaling multipliers
- Complex R:R trailing logic

**Added to Config:**
- 3-Confluence Rule settings
- False range detection thresholds
- Range invalidation conditions
- Session filter rules
- Trade activity criteria
- Early exit trigger settings

---

### 6. Integration Changes

**Updated Components:**
- `IntelligentExitManager` → Add range-specific early exit rules
- `DynamicStopManager` → Add breakeven SL move logic
- `config/lot_sizing.py` → Add `get_lot_size_for_range_scalp()` (fixed 0.01)
- Trade execution handlers → Accept `trade_type="range_scalp"` flag

**New Components:**
- `RangeScalpingRiskFilters` → Pre-trade risk checks
- `RangeScalpingExitManager` → Early exit logic
- Range monitoring during open trades

---

## 📊 Implementation Impact

### Simplified Execution Flow

**Before (Original Plan):**
1. Enter trade with risk-based lot size
2. Move to breakeven at 0.3R
3. Partial close at 0.6R
4. Trail to 2R on divergence
5. Manage multiple position sizes

**After (Updated Plan):**
1. Enter trade with fixed 0.01 lots
2. Monitor range validity continuously
3. Move to breakeven at 0.5R (if quick move)
4. Exit early if conditions deteriorate
5. Simple full position exit

**Result:** Much simpler, less moving parts, easier to test

---

### Risk Management Philosophy Shift

**Before:**
- "Manage the trade" (complex exits, partial profits)
- Optimize for maximum profit
- Multi-tier position management

**After:**
- "Prevent bad trades" (risk filters, early exits)
- Optimize for capital preservation
- Single position, simple exits

**Result:** Better risk control, fewer losing trades, less drawdown

---

## ✅ Key Takeaways

1. **No Partial Profits**: Fixed 0.01 lots = simple full position exits
2. **Early Exit Focus**: Exit when conditions deteriorate, not maximize profit
3. **Risk-First Approach**: Prevent bad trades rather than manage them
4. **Simplified Rules**: 3-Confluence Rule vs. complex multi-indicator setups
5. **Automated Filters**: Pre-trade risk checks prevent edge cases

---

**See:** `docs/RANGE_SCALPING_MASTER_PLAN_V2.md` for full implementation plan.

