# SMC-Integrated Exit Management Requirements

## Current Status

Your Advanced Exit Management system (`intelligent_exit_manager.py`) is **EXCELLENT** but is **MISSING SMC integration** (BOS/CHOCH signals).

### ✅ What Works Now:
1. **Breakeven at 0.2R (20%)** - Line 43, 209
2. **Trailing starts AFTER breakeven** - Lines 49, 82, 875-879
3. **ATR-based trailing (1.5x ATR)** - Lines 1315-1454
4. **Binance momentum checks** - Lines 754-814
5. **Whale order detection** - Lines 816-874
6. **Liquidity void warnings** - Lines 876-941

### ❌ What's MISSING:
**NO BOS/CHOCH structure detection!**

Your system currently uses:
- Profit percentage triggers (20%/50%)
- ATR calculations
- VIX adjustments
- Binance momentum
- Whale orders
- But **NOT SMC structure signals**

## Your SMC Exit Rules (User Requirements)

From your instructions:

> "After a BOS confirmation, it's safe to start trailing — trend is continuing and institutional structure supports holding."

> "If a CHOCH forms (structure break against your direction), that's your cue to tighten stops or partially exit."

> "The Advanced Exits system (ATR+VIX hybrid) normally triggers trailing once ≈20% of the planned profit (0.2R) is achieved — this protects equity while still allowing room for expansion."

> "Never start trailing too early (e.g., immediately at breakeven) — doing so can choke your trade's breathing space and cause premature stop-outs."

> **Ideal sequence:**
> 1. Trade enters profit → hold until BOS confirms trend.
> 2. Move SL to breakeven once ~0.2R–0.5R achieved.
> 3. Start ATR-based trailing after partial profits taken or volatility expansion confirmed.

> **Summary:**
> - Start trailing stops only after BOS confirmation and partial target achieved.
> - If a CHOCH appears instead → tighten or close.
> - Trailing with structure = professional management.

## Required Changes

### 1. Add SMC Structure Detection Helper

Add a new method to fetch BOS/CHOCH signals:

```python
def _get_smc_structure(self, rule: ExitRule) -> Optional[Dict[str, Any]]:
    """
    Get current SMC structure (BOS/CHOCH) for the symbol.

    Returns:
        {
            "bos_bull": bool,
            "bos_bear": bool,
            "choch_bull": bool,
            "choch_bear": bool,
            "bars_since_bos": int,
            "structure_type": "bos_bull" | "bos_bear" | "choch_bull" | "choch_bear" | "none"
        }
    """
    try:
        from infra.feature_structure import StructureFeatures
        from domain.market_structure import detect_bos_choch
        import MetaTrader5 as mt5

        # Get M15 bars for structure detection
        bars = mt5.copy_rates_from_pos(rule.symbol, mt5.TIMEFRAME_M15, 0, 100)
        if bars is None or len(bars) < 20:
            return None

        import pandas as pd
        df = pd.DataFrame(bars)

        # Get structure features
        struct_features = StructureFeatures()
        features = struct_features.compute(df, rule.symbol, "M15")

        # Get swing points
        swing_highs = features.get("swing_highs", [])
        swing_lows = features.get("swing_lows", [])

        # Combine and sort swings by index
        all_swings = []
        for sh in swing_highs:
            all_swings.append({"price": sh["price"], "kind": "HH", "idx": sh["index"]})
        for sl in swing_lows:
            all_swings.append({"price": sl["price"], "kind": "LL", "idx": sl["index"]})

        all_swings.sort(key=lambda s: s["idx"])

        # Calculate ATR for threshold
        import numpy as np
        high_low = df['high'].values[1:] - df['low'].values[1:]
        high_close = np.abs(df['high'].values[1:] - df['close'].values[:-1])
        low_close = np.abs(df['low'].values[1:] - df['close'].values[:-1])
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0

        # Detect BOS/CHOCH
        current_close = df['close'].iloc[-1]
        structure = detect_bos_choch(
            swings=all_swings,
            current_close=current_close,
            atr=atr,
            bos_threshold=0.2,
            sustained_bars=1
        )

        # Determine structure type
        if structure.get("bos_bull"):
            structure["structure_type"] = "bos_bull"
        elif structure.get("bos_bear"):
            structure["structure_type"] = "bos_bear"
        elif structure.get("choch_bull"):
            structure["structure_type"] = "choch_bull"
        elif structure.get("choch_bear"):
            structure["structure_type"] = "choch_bear"
        else:
            structure["structure_type"] = "none"

        return structure

    except Exception as e:
        logger.debug(f"SMC structure detection failed for {rule.symbol}: {e}")
        return None
```

### 2. Add BOS Check to Trailing Logic

Modify `_check_position_exits` to check for BOS before enabling trailing:

**Current code (line 875-879):**
```python
# Enable trailing after breakeven if enabled
if rule.trailing_enabled:
    rule.trailing_active = True
    rule.last_trailing_sl = action.get("new_sl")
    logger.info(f"✅ Trailing stops ACTIVATED for ticket {rule.ticket}")
```

**NEW code (with BOS check):**
```python
# Enable trailing after breakeven if enabled AND BOS confirmed
if rule.trailing_enabled:
    # Check for BOS confirmation before enabling trailing
    structure = self._get_smc_structure(rule)

    if structure:
        # Check if BOS aligns with our position direction
        bos_confirmed = False

        if rule.direction == "buy" and structure.get("bos_bull"):
            bos_confirmed = True
            logger.info(f"✅ BOS BULL confirmed for {rule.symbol} - safe to trail!")
        elif rule.direction == "sell" and structure.get("bos_bear"):
            bos_confirmed = True
            logger.info(f"✅ BOS BEAR confirmed for {rule.symbol} - safe to trail!")

        if bos_confirmed:
            rule.trailing_active = True
            rule.last_trailing_sl = action.get("new_sl")
            logger.info(f"✅ Trailing stops ACTIVATED for ticket {rule.ticket} (BOS confirmed + breakeven hit)")
        else:
            logger.info(f"⏳ Breakeven hit but waiting for BOS confirmation before trailing (ticket {rule.ticket})")
            rule.trailing_active = False  # Don't trail yet
    else:
        # Fallback: If structure detection fails, use old behavior (activate after breakeven)
        rule.trailing_active = True
        rule.last_trailing_sl = action.get("new_sl")
        logger.warning(f"⚠️ SMC structure unavailable - activating trailing after breakeven (ticket {rule.ticket})")
```

### 3. Add CHOCH Detection for Immediate Action

Add a new check in `_check_position_exits` (after line 920):

```python
# 4a. NEW: SMC CHOCH detection (BEFORE trailing check)
structure = self._get_smc_structure(rule)
if structure:
    # Check for CHOCH against our position direction
    choch_detected = False

    if rule.direction == "buy" and structure.get("choch_bear"):
        choch_detected = True
        logger.warning(f"🚨 CHOCH BEAR detected for {rule.symbol} (ticket {rule.ticket}) - structure broken!")
    elif rule.direction == "sell" and structure.get("choch_bull"):
        choch_detected = True
        logger.warning(f"🚨 CHOCH BULL detected for {rule.symbol} (ticket {rule.ticket}) - structure broken!")

    if choch_detected:
        # CHOCH = Tighten stop immediately to current price - small buffer
        # This protects profits while giving a small breathing room
        symbol_info = mt5.symbol_info(rule.symbol)
        atr = self._get_atr(rule.symbol, mt5.TIMEFRAME_M15)

        # Tighten to current price minus 0.5 ATR (very tight)
        if rule.direction == "buy":
            tight_sl = current_price - (atr * 0.5)
        else:
            tight_sl = current_price + (atr * 0.5)

        # Only tighten if it's better than current SL
        if rule.direction == "buy" and tight_sl > current_sl:
            action = self._tighten_stop_choch(rule, position, tight_sl, current_price)
            if action:
                actions.append(action)
                rule.actions_taken.append({
                    "action": "choch_tighten",
                    "timestamp": datetime.now().isoformat(),
                    "structure": structure["structure_type"],
                    "new_sl": tight_sl
                })
        elif rule.direction == "sell" and tight_sl < current_sl:
            action = self._tighten_stop_choch(rule, position, tight_sl, current_price)
            if action:
                actions.append(action)
                rule.actions_taken.append({
                    "action": "choch_tighten",
                    "timestamp": datetime.now().isoformat(),
                    "structure": structure["structure_type"],
                    "new_sl": tight_sl
                })
```

### 4. Add CHOCH Stop Tightening Method

```python
def _tighten_stop_choch(
    self,
    rule: ExitRule,
    position,
    tight_sl: float,
    current_price: float
) -> Optional[Dict[str, Any]]:
    """
    Tighten stop immediately when CHOCH detected (structure break).

    This is different from trailing - it's an emergency tighten
    to protect profits when structure breaks against you.
    """
    try:
        current_sl = position.sl if position.sl else rule.initial_sl

        # Modify position
        success = self._modify_position_sl(rule.ticket, tight_sl, position.tp)

        if success:
            logger.warning(
                f"🚨 CHOCH TIGHTEN: Stop tightened for {rule.symbol} (ticket {rule.ticket}): "
                f"{current_sl:.5f} → {tight_sl:.5f} | "
                f"Structure BROKEN - protecting profits!"
            )

            # Log to database
            if self.db_logger:
                try:
                    self.db_logger.log_action(
                        ticket=rule.ticket,
                        symbol=rule.symbol,
                        action_type="choch_tighten",
                        old_sl=current_sl,
                        new_sl=tight_sl,
                        details={
                            "current_price": current_price,
                            "direction": rule.direction,
                            "reason": "CHOCH detected - structure break"
                        },
                        success=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to log CHOCH tighten to database: {e}")

            return {
                "action": "choch_tighten",
                "ticket": rule.ticket,
                "symbol": rule.symbol,
                "old_sl": current_sl,
                "new_sl": tight_sl,
                "reason": "CHOCH detected",
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"Failed to tighten stop for CHOCH for ticket {rule.ticket}")
            return None

    except Exception as e:
        logger.error(f"Error tightening stop for CHOCH for ticket {rule.ticket}: {e}", exc_info=True)
        return None
```

### 5. Add Helper for ATR Calculation

```python
def _get_atr(self, symbol: str, timeframe) -> float:
    """Get ATR for symbol and timeframe"""
    try:
        import MetaTrader5 as mt5
        bars = mt5.copy_rates_from_pos(symbol, timeframe, 0, 50)

        if bars is None or len(bars) < 14:
            return 0.0

        import numpy as np
        high_low = bars['high'][1:] - bars['low'][1:]
        high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
        low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0

        return float(atr)

    except Exception as e:
        logger.debug(f"ATR calculation failed: {e}")
        return 0.0
```

## Summary of Changes

### File: `infra/intelligent_exit_manager.py`

1. **Add method:** `_get_smc_structure()` - Detects BOS/CHOCH
2. **Add method:** `_get_atr()` - Helper for ATR calculation
3. **Add method:** `_tighten_stop_choch()` - Emergency stop tightening
4. **Modify:** `_check_position_exits()` line 875-879 - Add BOS check before enabling trailing
5. **Add to:** `_check_position_exits()` after line 920 - Add CHOCH detection check

### New Behavior:

#### OLD (Current):
1. Trade hits 0.2R profit → Move SL to breakeven
2. Trailing IMMEDIATELY active after breakeven
3. NO structure checks

#### NEW (SMC-Integrated):
1. Trade hits 0.2R profit → Move SL to breakeven
2. **Check for BOS confirmation:**
   - **If BOS confirmed** → Activate trailing (trend continuing, safe to trail)
   - **If NO BOS yet** → Wait, don't trail (protect breathing room)
3. **Continuously check for CHOCH:**
   - **If CHOCH detected** → Tighten stop immediately to current price - 0.5 ATR
   - **Protection:** Structure broken, get out before reversal accelerates

## Benefits

1. ✅ **Professional SMC integration** - Trailing based on structure, not just profit %
2. ✅ **Prevents premature trailing** - Waits for BOS confirmation
3. ✅ **CHOCH protection** - Immediate tightening when structure breaks
4. ✅ **Respects trend continuation** - Only trails after BOS confirms trend
5. ✅ **Institutional edge** - Aligns with Smart Money behavior

## Implementation Priority

**HIGH PRIORITY** - This is a critical enhancement that aligns your exit system with professional SMC methodology.

Current system is good but mechanical. Adding SMC structure checks makes it **intelligent AND adaptive** to market structure.

---

**Next Steps:**
1. Review this document
2. Implement the 5 changes to `intelligent_exit_manager.py`
3. Test with paper trading
4. Deploy to live system

**Status:** ⏳ Pending implementation
**Complexity:** Medium (3-4 hours)
**Impact:** HIGH - Professional SMC-based exit management
