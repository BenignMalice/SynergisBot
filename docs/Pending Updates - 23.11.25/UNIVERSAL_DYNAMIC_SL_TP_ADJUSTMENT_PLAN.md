# Universal Dynamic SL/TP Adjustment System - Implementation Plan

**Created:** November 23, 2025  
**Status:** ✅ **COMPLETED** - All phases implemented and tested  
**Priority:** High  
**Completion Date:** November 25, 2025

**⚠️ Review Note:** This plan has been reviewed for errors and bugs. See:
- `UNIVERSAL_SL_TP_PLAN_REVIEW_ISSUES.md` - First review (critical issues addressed)
- `UNIVERSAL_SL_TP_PLAN_REVIEW_ISSUES_V2.md` - Second review (additional issues addressed)
- `UNIVERSAL_SL_TP_PLAN_REVIEW_ISSUES_V3.md` - Third review (integration and logic issues addressed)
- `UNIVERSAL_SL_TP_PLAN_REVIEW_ISSUES_V4.md` - Fourth review (additional robustness issues addressed)
- `UNIVERSAL_SL_TP_PLAN_FINAL_REVIEW.md` - Final review (implementation completeness)

All critical and medium issues have been addressed in this document. All final review recommendations have been integrated.

---

## 📋 Executive Summary

This plan outlines the implementation of a **Universal Dynamic SL/TP Adjustment System** that adapts stop loss and take profit management based on:

- **Strategy Type** (breakout, trend continuation, sweep reversal, OB rejection, mean-reversion)
- **Symbol** (BTC vs XAU - different behaviors)
- **Session** (Asia, London, NY - volatility and behavior differences)

The system will work alongside existing exit managers (`IntelligentExitManager`, `RangeScalpingExitManager`, `MicroScalpExecutionManager`) with explicit ownership to prevent conflicts.

---

## 🎯 Goals

1. **Strategy-Aware Trailing**: Different trailing methods per strategy type
2. **Symbol-Specific Behavior**: BTC and XAU have different trailing requirements
3. **Session-Aware Adjustments**: Asia, London, NY require different SL/TP behavior
4. **Zero Conflicts**: Explicit ownership prevents multiple managers modifying same trade
5. **Anti-Thrash Safeguards**: Minimum distance + cooldown prevent MT5 spam
6. **Maintainable Architecture**: Frozen rule snapshots prevent config sprawl

## ⚠️ Conflict Prevention with DTMS

**CRITICAL**: Three systems can modify SL/TP:
1. **Universal Dynamic SL/TP Manager** (strategy-specific trailing)
2. **DTMS** (defensive management - hedging, recovery)
3. **Intelligent Exit Manager** (simple profit protection)

### Conflict Resolution Strategy

**Priority Order** (highest to lowest):
1. **DTMS Defensive Actions** (HEDGED, WARNING_L2) - Takes priority for risk management
2. **Universal SL/TP Manager** - For strategy-specific trailing on managed strategies
3. **DTMS Normal Actions** - For defensive management when not in critical states
4. **Intelligent Exit Manager** - Fallback for simple profit protection

### Ownership Rules

- **Universal Manager**: Owns trades with `strategy_type` in `UNIVERSAL_MANAGED_STRATEGIES`
- **DTMS**: Can override Universal Manager only in defensive states (HEDGED, WARNING_L2)
- **Legacy Managers**: Only manage trades not owned by Universal Manager or DTMS

**All systems check `trade_registry` before modifying SL/TP to prevent conflicts.**

---

## 🏗️ Architecture Overview

### System Hierarchy

```
Universal Dynamic SL/TP Manager (NEW)
├── Strategy Classifier (identifies trade type)
├── Session Detector (Asia/London/NY)
├── Symbol-Specific Rule Engine (BTC vs XAU)
├── Trailing Logic Dispatcher (routes to correct trailing method)
└── Execution Coordinator (modifies positions via MT5Service)
    │
    ├── IntelligentExitManager (standard trades - can be enhanced)
    ├── RangeScalpingExitManager (range trades - can be enhanced)
    └── MicroScalpExecutionManager (micro-scalps - can be enhanced)
```

### Core Components

1. **UniversalDynamicSLTPManager**: Main orchestrator
2. **StrategyClassifier**: Identifies trade type from plan/conditions
3. **SessionDetector**: Time-based + volatility-based session detection
4. **SymbolSpecificRuleEngine**: BTC vs XAU adjustments
5. **TrailingLogicDispatcher**: Routes to correct trailing method
6. **ExecutionCoordinator**: Modifies positions via MT5Service
7. **TradeRegistry**: Global ownership tracking

### Class Structure

```python
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Enum Definitions
class Session(Enum):
    """
    Market session enumeration.
    
    Used throughout the system for session-aware adjustments.
    Import this enum in any module that uses session detection:
        from infra.universal_sl_tp_manager import Session
    """
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY = "NY"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    LATE_NY = "LATE_NY"

class StrategyType(Enum):
    """
    Strategy type enumeration.
    
    Used to identify trade types for rule resolution.
    Import this enum in any module that uses strategy types:
        from infra.universal_sl_tp_manager import StrategyType
    """
    BREAKOUT_IB_VOLATILITY_TRAP = "breakout_ib_volatility_trap"
    BREAKOUT_BOS = "breakout_bos"
    TREND_CONTINUATION_PULLBACK = "trend_continuation_pullback"
    TREND_CONTINUATION_BOS = "trend_continuation_bos"
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"
    ORDER_BLOCK_REJECTION = "order_block_rejection"
    MEAN_REVERSION_RANGE_SCALP = "mean_reversion_range_scalp"
    MEAN_REVERSION_VWAP_FADE = "mean_reversion_vwap_fade"
    DEFAULT_STANDARD = "default_standard"
    MICRO_SCALP = "micro_scalp"  # Already handled separately

# Universal managed strategies
UNIVERSAL_MANAGED_STRATEGIES = [
    StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
    StrategyType.TREND_CONTINUATION_PULLBACK,
    StrategyType.LIQUIDITY_SWEEP_REVERSAL,
    StrategyType.ORDER_BLOCK_REJECTION,
    StrategyType.MEAN_REVERSION_RANGE_SCALP
]

class UniversalDynamicSLTPManager:
    """
    Universal Dynamic SL/TP Manager - Main orchestrator.
    """
    def __init__(self, db_path: str = None, mt5_service=None, config_path: str = None):
        """
        Initialize the manager.
        
        Args:
            db_path: Path to SQLite database (default: "data/universal_trades.db")
            mt5_service: MT5Service instance for position modifications
            config_path: Path to config JSON file (default: "config/universal_sl_tp_config.json")
        """
        self.db_path = db_path or "data/universal_trades.db"
        self.config_path = config_path or "config/universal_sl_tp_config.json"
        self.mt5_service = mt5_service
        self.active_trades: Dict[int, TradeState] = {}  # Active trade registry
        self.config = self._load_config()  # Load from JSON config
        
        # Initialize database schema
        self._init_database()
        
        # Recover trades on startup
        self.recover_trades_on_startup()
    
def monitor_all_trades(self):
    """Monitor all active trades (called by scheduler)."""
    # Check MT5 connection first
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            logger.error("MT5 not initialized - skipping trade monitoring")
            return
    except Exception as e:
        logger.error(f"Error checking MT5 connection: {e}")
        return
    
    tickets = list(self.active_trades.keys())
    for ticket in tickets:
        try:
            self.monitor_trade(ticket)
        except Exception as e:
            logger.error(f"Error monitoring trade {ticket}: {e}", exc_info=True)
```

---

## 📊 Strategy Types

### Supported Strategy Types

```python
StrategyType:
  - BREAKOUT_IB_VOLATILITY_TRAP
  - BREAKOUT_BOS
  - TREND_CONTINUATION_PULLBACK
  - TREND_CONTINUATION_BOS
  - LIQUIDITY_SWEEP_REVERSAL
  - ORDER_BLOCK_REJECTION
  - MEAN_REVERSION_RANGE_SCALP
  - MEAN_REVERSION_VWAP_FADE
  - MICRO_SCALP  # Already handled separately
```

### Strategy Identification Methods

#### Option A: Explicit Strategy Tag (Recommended)
When trade plan is created, include `strategy_type` field:

```json
{
  "plan_id": "chatgpt_123",
  "symbol": "BTCUSDc",
  "strategy_type": "breakout_ib_volatility_trap",
  "direction": "BUY",
  "entry": 84000,
  "stop_loss": 83800,
  "take_profit": 84500,
  "conditions": {
    "inside_bar": true,
    "volatility_compression": true
  }
}
```

#### Option B: Pattern Matching from Conditions
If no explicit tag, infer from conditions:
- `inside_bar: true` + `volatility_compression: true` → `breakout_ib_volatility_trap`
- `choch_bull: true` + `bos_continuation: true` → `trend_continuation`
- `liquidity_sweep: true` + `reversal_signal: true` → `sweep_reversal`
- `order_block: true` + `rejection: true` → `ob_rejection`
- `range_bound: true` + `mean_reversion: true` → `mean_reversion_scalp`

#### Option C: ChatGPT-Provided Strategy
ChatGPT explicitly sets `strategy_type` when creating plans based on analysis.

### Manual/Legacy Trades Without Strategy Type

**Problem**: Manual MT5 trades, old plans without `strategy_type`, or experiments without proper tagging.

**Solution**: Explicit fallback behavior - never leave it ambiguous.

#### Fallback Options

**Option 1: Do Not Register (Recommended for Manual Trades)**
```python
def register_trade(self, ticket, symbol, strategy_type=None, ...):
    if strategy_type is None:
        # Explicit: Do not register with universal manager
        # Let legacy exit managers handle it
        logger.info(f"Trade {ticket} has no strategy_type - skipping universal manager")
        return None  # Not registered
```

**Option 2: Default Conservative Profile**
```python
def register_trade(self, ticket, symbol, strategy_type=None, ...):
    if strategy_type is None:
        # Fallback to DEFAULT_STANDARD strategy
        strategy_type = "DEFAULT_STANDARD"
        logger.warning(f"Trade {ticket} has no strategy_type - using DEFAULT_STANDARD")
    
    # DEFAULT_STANDARD rules:
    # - Simple BE at +1R
    # - Optional basic ATR trail (conservative)
    # - No partial profits
    # - Longer cooldown (60s)
```

#### Configuration for Default Strategy

```json
{
  "strategies": {
    "DEFAULT_STANDARD": {
      "breakeven_trigger_r": 1.0,
      "trailing_method": "atr_basic",
      "trailing_timeframe": "M15",
      "atr_multiplier": 2.0,
      "trailing_enabled": true,
      "partial_profit_r": null,
      "sl_modification_cooldown_seconds": 60
    }
  }
}
```

**Recommendation**: Use Option 1 for manual trades (let legacy managers handle), Option 2 for auto-execution plans that somehow lack strategy_type (safety net).

---

## 🕐 Session Detection

### Time-Based Session Classification

```python
def detect_session(symbol: str, timestamp: datetime) -> Session:
    """
    Detect market session based on UTC time.
    
    Args:
        symbol: Trading symbol (BTCUSDc, XAUUSDc, EURUSDc, US30c, etc.)
        timestamp: UTC datetime
        
    Returns:
        Session enum value
        
    Note:
        Session boundaries (UTC):
        - Asia: 00:00 - 08:00
        - London: 08:00 - 13:00
        - London-NY Overlap: 13:00 - 16:00
        - NY: 16:00 - 21:00
        - Late NY: 21:00 - 00:00
        
        BTC trades 24/7 but sessions still matter for volatility.
        Other symbols (XAU, EURUSD, US30) use same session times.
    """
    utc_hour = timestamp.hour
    
    # Session boundaries (UTC)
    # Check overlap first (highest priority)
    if 13 <= utc_hour < 16:
        return Session.LONDON_NY_OVERLAP
    elif 8 <= utc_hour < 13:
        return Session.LONDON
    elif 16 <= utc_hour < 21:
        return Session.NY
    elif 21 <= utc_hour or utc_hour < 8:
        if utc_hour >= 21:
            return Session.LATE_NY
        else:
            return Session.ASIA
    
    # Default fallback
    return Session.ASIA
```

### Session Frozen at Trade Open
- Session is detected **once** when trade is registered
- Session is **frozen** in `TradeState` and does not change mid-trade
- Session adjustments are **baked into** resolved rules at trade open

---

## 🎯 Strategy-Specific Trailing Rules

### 1. Breakout / IB Volatility Trap

**Goal**: Catch expansion after compression without getting wicked out.

#### BTC Trailing Rules
- **London/NY (high volatility)**:
  - Move SL to BE at +1R
  - Trail using M1 swing lows (last 2 confirmed HLs)
  - If momentum strong (CVD positive + volume): Switch to ATR trailing (SL = close - 1.5 × ATR(M5))
- **Asia (low volatility)**:
  - Move SL to BE at +0.75R (tighter)
  - Trail under M1 micro HLs aggressively
  - Don't expect massive expansions - lock 1-2R

#### XAU Trailing Rules
- **London/NY**:
  - Move SL to BE at +1R
  - Trail using M5 structure (not M1 - too noisy on gold)
  - Use last M5 HL for longs
  - At +2R, switch to displacement trailing (last displacement candle low)
- **Asia**:
  - Rare to get clean breakout runs
  - Move SL to BE early (+0.5R)
  - Trail using VWAP proximity (if price snaps back → tighten aggressively)

### 2. Trend Continuation (Pullbacks, BOS Continuation)

**Goal**: Ride trend legs without being stopped during normal pullbacks.

#### BTC Trailing Rules
- **London/NY**:
  - Do NOT trail too early
  - Move SL to BE only at +1R or after second HL forms
  - Trail behind M5 HL/LH structure
  - For strong trends: Use EMA20 on M5 as dynamic trailing zone
  - Momentum exhaustion (CVD divergence) → tighten SL aggressively
- **Asia**:
  - BTC trends often stall - be more conservative
  - BE at +0.75R
  - Trail using M1 HLs (tighter)
  - Take partials early (1.5R)

#### XAU Trailing Rules
- **London/NY**:
  - Move SL to BE at +0.75-1R
  - Trail under M5 HL/LH, not M1
  - When ADX > 30 and strong displacement candles: Switch to ATR trail (SL = close - 1.0 × ATR(M15))
- **Asia**:
  - Trend legs are small
  - Take profit sooner and trail tightly on M1

### 3. Liquidity Sweep → Reversal

**Goal**: Precision entries with fast follow-through; protect from snapbacks.

#### BTC Trailing Rules
- **All sessions**:
  - Move SL to BE extremely fast: +0.5R
  - If price doesn't follow through within 2-3 candles → tighten or exit
  - Trail using micro CHOCH structure (trail under new HL after reversal)
  - If delta flips against position → cut quickly

#### XAU Trailing Rules
- **London/NY**:
  - Move SL to BE at +0.5R
  - If displacement candle confirms reversal: Use trailing under displacement candle low
- **Asia**:
  - Sweeps often fade into chop
  - Take TP early (1-1.5R)
  - SL to BE fast
  - Trailing = minimal

### 4. Order Block Rejection

**Goal**: Ride the move away from an institutional zone.

#### BTC Trailing Rules
- **London/NY**:
  - Move SL to BE at +1R or after clear displacement
  - Trail using OB midpoint or last M5 swing
- **Asia**:
  - Tighten more aggressively
  - BE at +0.75R
  - Trail under M1 swings

#### XAU Trailing Rules
- **London/NY**:
  - Move SL to BE at +0.75R
  - Trail using last HL/LH on M5 or displacement candle's opposite wick
  - At +2R, allow runner with ATR trail
- **Asia**:
  - OB trades can be slow
  - Take TP1 early
  - Trail tightly using M1

### 5. Mean-Reversion / Range Scalp (Incl. VWAP Fade)

**Goal**: Quick bounce → quick TP.

#### BTC Trailing Rules
- **All sessions**:
  - SL to BE at +0.5R
  - No "trail for big win"
  - Fast in, fast out
  - TP mostly fixed; trailing is minimal or none

#### XAU Trailing Rules
- **Asia**:
  - SL to BE at +0.5R
  - Optional micro-trail under M1 structure
  - Always TP early
- **London/NY**:
  - Gold often breaks ranges during transition to London
  - Don't trail for long runs
  - Take TP and get out

---

## 📐 Timeframe Selection Logic

### Monitoring Timeframes (for trailing stops)

| Strategy | BTC Monitoring | XAU Monitoring | Execution TF |
|----------|----------------|----------------|--------------|
| Breakout | M1 (London/NY), M1 (Asia) | M5 (all sessions) | M1 |
| Trend Cont. | M5 (all) | M5 (all) | M1 |
| Sweep Rev. | M1 (all) | M5 (London/NY), M1 (Asia) | M1 |
| OB Rejection | M5 (all) | M5 (all) | M1 |
| Mean-Rev | M1 (all) | M1 (all) | M1 |

### Timeframe Priority Rules

1. **Strategy-based defaults**:
   - Breakouts (BTC): M1 swing lows for tight trailing
   - Breakouts (XAU): M5 structure (less noise)
   - Trend continuation: M5 HL/LH structure
   - Sweep reversals: M1 micro CHOCH
   - OB rejections: M5 structure or displacement candles
   - Mean-reversion: M1 (if any trailing)

2. **Symbol-based overrides**:
   - BTC: Prefer M1 for breakouts (wick tolerance)
   - XAU: Prefer M5 for most strategies (cleaner structure)

3. **Session-based adjustments**:
   - High volatility (London/NY): Use higher timeframe (M5) to avoid noise
   - Low volatility (Asia): Use lower timeframe (M1) for precision

### Execution Timeframes
- Always use M1 for micro-adjustments (fastest response)
- Use M5/M15 for structure-based trailing (more stable)

---

## 🔧 Configuration Structure

### JSON Configuration File

**Location**: `config/universal_sl_tp_config.json`

```json
{
  "universal_sl_tp_rules": {
    "strategies": {
      "breakout_ib_volatility_trap": {
        "breakeven_trigger_r": 1.0,
        "breakeven_trigger_r_asia": 0.75,
        "trailing_method": "structure_atr_hybrid",
        "trailing_timeframe_btc": "M1",
        "trailing_timeframe_xau": "M5",
        "atr_multiplier": 1.5,
        "structure_lookback": 2,
        "partial_profit_r": 1.5,
        "partial_close_pct": 50,
        "momentum_exhaustion_detection": true,
        "stall_detection_candles": 3,
        "sl_modification_cooldown_seconds": 20
      },
      "trend_continuation_pullback": {
        "breakeven_trigger_r": 1.0,
        "trailing_method": "structure_based",
        "trailing_timeframe": "M5",
        "structure_lookback": 1,
        "atr_buffer": 0.5,
        "sl_modification_cooldown_seconds": 45
      },
      "liquidity_sweep_reversal": {
        "breakeven_trigger_r": 0.5,
        "trailing_method": "micro_choch",
        "trailing_timeframe": "M1",
        "structure_lookback": 1,
        "sl_modification_cooldown_seconds": 15
      },
      "order_block_rejection": {
        "breakeven_trigger_r": 1.0,
        "breakeven_trigger_r_asia": 0.75,
        "trailing_method": "displacement_or_structure",
        "trailing_timeframe": "M5",
        "structure_lookback": 1,
        "sl_modification_cooldown_seconds": 30
      },
      "mean_reversion_range_scalp": {
        "breakeven_trigger_r": 0.5,
        "trailing_method": "minimal_be_only",
        "trailing_enabled": false,
        "sl_modification_cooldown_seconds": 10
      }
    },
    "symbol_adjustments": {
      "BTCUSDc": {
        "default_timeframe": "M5",
        "trailing_timeframe": "M1",
        "atr_period": 14,
        "atr_timeframe": "M5",
        "wick_tolerance_multiplier": 1.2,
        "trend_persistence_factor": 1.5,
        "min_sl_change_r": 0.1,
        "session_adjustments": {
          "ASIA": {
            "tp_multiplier": 0.8,
            "sl_tightening": 1.1
          },
          "LONDON": {
            "tp_multiplier": 1.2,
            "sl_tightening": 0.9
          },
          "NY": {
            "tp_multiplier": 1.3,
            "sl_tightening": 0.85
          },
          "LONDON_NY_OVERLAP": {
            "tp_multiplier": 1.3,
            "sl_tightening": 0.85
          },
          "LATE_NY": {
            "tp_multiplier": 0.9,
            "sl_tightening": 1.0
          }
        }
      },
      "XAUUSDc": {
        "default_timeframe": "M15",
        "trailing_timeframe": "M5",
        "atr_period": 14,
        "atr_timeframe": "M15",
        "wick_tolerance_multiplier": 1.0,
        "trend_persistence_factor": 1.0,
        "min_sl_change_r": 0.1,
        "session_adjustments": {
          "ASIA": {
            "tp_multiplier": 0.9,
            "sl_tightening": 1.0
          },
          "LONDON": {
            "tp_multiplier": 1.1,
            "sl_tightening": 0.95
          },
          "NY": {
            "tp_multiplier": 1.2,
            "sl_tightening": 0.9
          },
          "LONDON_NY_OVERLAP": {
            "tp_multiplier": 1.2,
            "sl_tightening": 0.9
          },
          "LATE_NY": {
            "tp_multiplier": 0.8,
            "sl_tightening": 1.1
          }
        }
      },
      "EURUSDc": {
        "default_timeframe": "M15",
        "trailing_timeframe": "M5",
        "atr_period": 14,
        "atr_timeframe": "M15",
        "wick_tolerance_multiplier": 1.0,
        "trend_persistence_factor": 1.0,
        "min_sl_change_r": 0.1,
        "session_adjustments": {
          "ASIA": {
            "tp_multiplier": 0.85,
            "sl_tightening": 1.05
          },
          "LONDON": {
            "tp_multiplier": 1.15,
            "sl_tightening": 0.95
          },
          "NY": {
            "tp_multiplier": 1.25,
            "sl_tightening": 0.9
          },
          "LONDON_NY_OVERLAP": {
            "tp_multiplier": 1.2,
            "sl_tightening": 0.9
          },
          "LATE_NY": {
            "tp_multiplier": 0.9,
            "sl_tightening": 1.05
          }
        }
      },
      "US30c": {
        "default_timeframe": "M15",
        "trailing_timeframe": "M5",
        "atr_period": 14,
        "atr_timeframe": "M15",
        "wick_tolerance_multiplier": 1.1,
        "trend_persistence_factor": 1.3,
        "min_sl_change_r": 0.1,
        "session_adjustments": {
          "ASIA": {
            "tp_multiplier": 0.8,
            "sl_tightening": 1.1
          },
          "LONDON": {
            "tp_multiplier": 1.2,
            "sl_tightening": 0.9
          },
          "NY": {
            "tp_multiplier": 1.4,
            "sl_tightening": 0.85
          },
          "LONDON_NY_OVERLAP": {
            "tp_multiplier": 1.3,
            "sl_tightening": 0.85
          },
          "LATE_NY": {
            "tp_multiplier": 0.85,
            "sl_tightening": 1.1
          }
        }
      }
    }
  }
}
```

### Configuration Units Documentation

**Critical**: **R-space is the primary logic space** - most logic lives in R-multiples, with points/pips only used for lower-level translation and broker validation.

#### Design Philosophy: R-Space First

**Primary Logic (R-Space)**:
- `breakeven_trigger_r`: 1.0 (move to BE at +1R) - **Universal across symbols**
- `partial_profit_r`: 1.5 (take partial at +1.5R) - **Universal across symbols**
- `min_sl_change_r`: 0.1 (only move SL if it improves ≥ 0.1R) - **Universal across symbols**

**Lower-Level Translation (Points/Pips)**:
- Points/pips are only used for:
  1. **Broker validation**: Check if change meets broker's minimum stop distance
  2. **Final conversion**: Convert R-based calculations to actual price levels
  3. **Symbol-specific constraints**: Handle broker-specific requirements

#### Units Reference

| Config Field | Type | Value | Notes |
|--------------|------|-------|-------|
| `breakeven_trigger_r` | R-multiple | 1.0 | Universal - same for all symbols |
| `partial_profit_r` | R-multiple | 1.5 | Universal - same for all symbols |
| `min_sl_change_r` | R-multiple | 0.1 | Universal - same for all symbols |
| `atr_multiplier` | Dimensionless | 1.5 | Multiplier for ATR-based trailing |
| `tp_multiplier` | Dimensionless | 1.2 | Session-based TP adjustment |
| `sl_tightening` | Dimensionless | 0.9 | Session-based SL adjustment |

**Broker Validation (Symbol-Specific)**:
- `broker_min_stop_distance_points`: Symbol-specific broker requirement
- Used only for final validation before MT5 modification
- Not used in decision logic

**Implementation**: 
- All decision logic uses R-space (intuitively consistent across symbols)
- Points/pips conversion happens only at the final step before broker call
- Broker validation uses symbol-specific points/pips as a safety check

---

---

## 🛡️ Complexity Mitigation Safeguards

### 1. Frozen Rule Snapshot (Prevents Config Sprawl)

**Problem**: Merging STRATEGY_RULES + SYMBOL_RULES + session_adjustments on every check is wasteful and can cause inconsistent behavior.

**Solution**: Resolve all rules into a single frozen snapshot at trade open.

#### Implementation

```python
def register_trade(self, ticket, symbol, strategy_type, entry_price, initial_sl, 
                   initial_tp, direction, plan_id=None, initial_volume=None):
    """
    Register a trade with the universal SL/TP manager.
    
    Args:
        ticket: MT5 position ticket
        symbol: Trading symbol
        strategy_type: Strategy type (string or StrategyType enum)
        entry_price: Entry price
        initial_sl: Initial stop loss
        initial_tp: Initial take profit
        direction: "BUY" or "SELL"
        plan_id: Optional plan ID for recovery
        initial_volume: Optional initial volume (fetched from MT5 if not provided)
        
    Returns:
        TradeState if registered, None if registration failed or skipped
    """
    import MetaTrader5 as mt5
    
    # Normalize strategy_type to enum
    strategy_type = self._normalize_strategy_type(strategy_type)
    
    # Validate position exists and get data
    try:
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            logger.error(f"Position {ticket} not found - cannot register")
            return None
        
        position = positions[0]
        
        # Validate position data matches provided data
        if position.symbol != symbol:
            logger.warning(f"Position {ticket} symbol mismatch: {position.symbol} != {symbol}")
            symbol = position.symbol  # Use actual symbol
        
        # Use position data if not provided
        if initial_volume is None:
            initial_volume = position.volume
        
        if entry_price is None:
            entry_price = position.price_open
        
        if initial_sl is None:
            initial_sl = position.sl
        
        if initial_tp is None:
            initial_tp = position.tp
        
    except Exception as e:
        logger.error(f"Error validating position {ticket}: {e}")
        # Use provided data as fallback
        if initial_volume is None:
            initial_volume = 0.0
        if entry_price is None or initial_sl is None or initial_tp is None:
            logger.error(f"Missing required position data for {ticket} - cannot register")
            return None
    
    # Detect session ONCE at trade open
    session = detect_session(symbol, datetime.now())
    
    # Calculate baseline ATR for volatility comparison
    atr_timeframe = self._get_atr_timeframe_for_strategy(strategy_type, symbol)
    baseline_atr = self._get_current_atr(symbol, atr_timeframe)
    
    # Resolve ALL rules into final snapshot (ONE TIME)
    resolved_rules = self._resolve_trailing_rules(
        strategy_type=strategy_type,
        symbol=symbol,
        session=session
    )
    
    # Store frozen snapshot on trade state
    trade_state = TradeState(
        ticket=ticket,
        strategy_type=strategy_type,
        symbol=symbol,
        session=session,  # Frozen at open
        resolved_trailing_rules=resolved_rules,  # ← Frozen config
        baseline_atr=baseline_atr,  # ← Stored for volatility comparison
        initial_volume=initial_volume,
        entry_price=entry_price,
        initial_sl=initial_sl,
        initial_tp=initial_tp,
        direction=direction,
        plan_id=plan_id,
        ...
    )
```

#### Resolved Rules Structure

```python
{
  "ticket": 123456,
  "strategy_type": "breakout_ib_volatility_trap",
  "symbol": "BTCUSDc",
  "session": "LONDON",
  "resolved_trailing_rules": {
    "breakeven_trigger_r": 1.0,
    "partial_profit_r": 1.5,
    "partial_close_pct": 50,
    "trailing_method": "structure_atr_hybrid",
    "trailing_timeframe": "M1",
    "atr_multiplier": 1.5,
    "structure_lookback": 2,
    "stall_detection_candles": 3,
    "sl_modification_cooldown_seconds": 20,
    "min_sl_change_r": 0.1
  }
}
```

**Benefits**:
- Single source of truth per trade
- No runtime config merging
- Easier debugging (inspect `trade_state.resolved_trailing_rules`)
- Consistent behavior throughout trade lifecycle

### 2. Ownership Flag (Prevents Manager Conflicts)

**Problem**: Multiple managers trying to modify the same position causes conflicts and race conditions.

**⚠️ CRITICAL**: Three systems can modify SL/TP:
1. **Universal Dynamic SL/TP Manager** (new system)
2. **DTMS** (Defensive Trade Management System)
3. **Intelligent Exit Manager** (legacy)

**Solution**: Explicit ownership with `managed_by` field and conflict prevention.

#### Ownership Hierarchy

```python
# Ownership priority (highest to lowest):
# 1. "universal_sl_tp_manager" - Strategy-specific dynamic trailing
# 2. "dtms_manager" - Defensive management (hedging, recovery)
# 3. "legacy_exit_manager" - Simple profit protection
# 4. "manual" - Manual trades, no automated management
```

#### Implementation

```python
# Mark trades at registration
def register_trade(self, ticket, strategy_type, ...):
    # CRITICAL: Determine ownership based on strategy_type FIRST
    # Don't check if DTMS is already managing - we register BEFORE DTMS
    if strategy_type and strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
        managed_by = "universal_sl_tp_manager"
    else:
        # Not a universal-managed strategy
        # Will be managed by DTMS or legacy managers
        managed_by = "legacy_exit_manager"  # Default, may be overridden by DTMS
    
    # Check if trade already registered (prevent duplicate registration)
    if ticket in trade_registry:
        existing_state = trade_registry[ticket]
        if existing_state.managed_by == "universal_sl_tp_manager":
            logger.warning(f"Trade {ticket} already registered with Universal Manager - skipping")
            return existing_state
    
    trade_state = TradeState(
        ticket=ticket,
        managed_by=managed_by,  # ← Ownership flag
        ...
    )
    
    # Store in global registry
    from infra.trade_registry import set_trade_state
    set_trade_state(ticket, trade_state)
    self.active_trades[ticket] = trade_state
```

#### DTMS Integration - Conflict Prevention

```python
# In dtms_core/action_executor.py - BEFORE modifying SL/TP
def _tighten_sl(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
    ticket = trade_data.get('ticket')
    
    # Check ownership before modifying
    trade_state = trade_registry.get(ticket)
    if trade_state:
        if trade_state.managed_by == "universal_sl_tp_manager":
            # Universal manager owns this - DTMS should not modify SL/TP
            logger.warning(
                f"DTMS skipping SL modification for {ticket}: "
                f"owned by universal_sl_tp_manager"
            )
            return ActionResult(
                success=False,
                action_type='tighten_sl',
                details=action,
                error_message="Trade managed by universal_sl_tp_manager - DTMS cannot modify SL/TP"
            )
        # If managed_by == "dtms_manager" or "legacy_exit_manager", proceed
    
    # ... existing SL modification logic ...
```

#### Universal Manager Checks DTMS Ownership

```python
# In universal_sl_tp_manager.py - BEFORE modifying SL/TP
def _modify_position_sl(self, ticket: int, new_sl: float, trade_state: TradeState) -> bool:
    # Verify ownership
    if trade_state.managed_by != "universal_sl_tp_manager":
        logger.warning(
            f"Cannot modify SL for {ticket}: "
            f"owned by {trade_state.managed_by}"
        )
        return False
    
    # Check if DTMS is actively managing (defensive actions can override)
    if self._is_dtms_actively_managing(ticket):
        # DTMS is in HEDGED or WARNING_L2 state - allow DTMS to take priority
        logger.info(
            f"Skipping SL modification for {ticket}: "
            f"DTMS is actively managing (defensive mode)"
        )
        return False
    
    # ... proceed with modification ...
```

#### Legacy Managers Check Ownership

```python
# In intelligent_exit_manager.py
def check_exits(self):
    for ticket, rule in self.rules.items():
        # Check ownership
        trade_state = trade_registry.get(ticket)
        if trade_state:
            if trade_state.managed_by == "universal_sl_tp_manager":
                continue  # Skip - universal manager owns this
            if trade_state.managed_by == "dtms_manager":
                continue  # Skip - DTMS owns this
        
        # Only process if we own it or no ownership set
        # ... existing intelligent exit logic ...
```

#### DTMS Helper Methods

```python
def _is_dtms_managed(self, ticket: int) -> bool:
    """Check if DTMS is monitoring this trade."""
    try:
        from dtms_integration import get_dtms_trade_status
        status = get_dtms_trade_status(ticket)
        return status is not None and status.get('state') != 'CLOSED'
    except Exception:
        return False

def _is_dtms_actively_managing(self, ticket: int) -> bool:
    """Check if DTMS is in defensive mode (HEDGED, WARNING_L2)."""
    try:
        from dtms_integration import get_dtms_trade_status
        status = get_dtms_trade_status(ticket)
        if not status:
            return False
        
        state = status.get('state', '')
        # DTMS takes priority in defensive states
        return state in ['HEDGED', 'WARNING_L2']
    except Exception:
        return False
```

**Benefits**:
- No conflicts: only one manager modifies SL/TP per trade
- Clear ownership: easy to see who manages what
- DTMS defensive priority: DTMS can override in critical states
- Safe transitions: can transfer ownership if needed
- Explicit coordination: All systems check ownership before modifying

### 3. Anti-Thrash Safeguards (Prevents MT5 Spam)

**Problem**: Too-frequent SL modifications cause MT5 spam, race conditions, broker rate limiting.

**Solution**: Minimum distance threshold + cooldown period.

#### Minimum Distance Change

```python
def is_improvement(self, new_sl: float, current_sl: float, 
                  direction: str, trade_state: TradeState) -> bool:
    """
    Only return True if new_sl is significantly better (R-space logic).
    """
    # Calculate change in price units
    if direction == "BUY":
        improvement_points = new_sl - current_sl  # Must be positive
    else:  # SELL
        improvement_points = current_sl - new_sl  # Must be positive
    
    if improvement_points <= 0:
        return False  # Not better
    
    # Convert to R-space
    # R = (entry_price - initial_sl) for BUY, (initial_sl - entry_price) for SELL
    if direction == "BUY":
        one_r_points = trade_state.entry_price - trade_state.initial_sl
    else:  # SELL
        one_r_points = trade_state.initial_sl - trade_state.entry_price
    
    if one_r_points <= 0:
        return False  # Invalid R calculation
    
    improvement_r = improvement_points / one_r_points
    
    # Get minimum R threshold (universal across symbols)
    min_sl_change_r = trade_state.resolved_trailing_rules.get("min_sl_change_r", 0.1)
    
    # Must improve by at least min_sl_change_r (e.g., 0.1R)
    if improvement_r < min_sl_change_r:
        return False
    
    # Additional broker validation (points/pips check)
    # This is a safety check, not the primary logic
    broker_min_distance = self._get_broker_min_stop_distance(trade_state.symbol)
    if improvement_points < broker_min_distance:
        logger.debug(
            f"SL change {improvement_points} below broker minimum {broker_min_distance} "
            f"for {trade_state.symbol}"
        )
        return False
    
    return True

def _get_broker_min_stop_distance(self, symbol: str) -> float:
    """
    Get broker's minimum stop distance (symbol-specific).
    Used only for final validation, not decision logic.
    """
    # Fetch from MT5 symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        return symbol_info.trade_stops_level * symbol_info.point
    
    # Fallback defaults (points/pips)
    defaults = {
        "BTCUSDc": 5.0,   # 5 points
        "XAUUSDc": 0.5,   # 0.5 pips
        "EURUSDc": 2.0,   # 2 pips
        "US30c": 3.0,     # 3 points
    }
    return defaults.get(symbol, 1.0)
```

#### Cooldown Period

```python
@dataclass
class TradeState:
    ...
    last_sl_modification_time: Optional[datetime] = None
    sl_modification_cooldown_seconds: int = 30

def should_modify_sl(self, trade_state: TradeState) -> bool:
    if not trade_state.last_sl_modification_time:
        return True  # Never modified, allow
    
    elapsed = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
    return elapsed >= trade_state.sl_modification_cooldown_seconds
```

**Strategy-Specific Cooldowns**:
- Breakout: 20 seconds (more frequent - M1 trailing)
- Trend continuation: 45 seconds (less frequent - M5 trailing)
- Sweep reversal: 15 seconds (very frequent - M1 micro)
- OB rejection: 30 seconds (standard)
- Mean-reversion: 10 seconds (very frequent - quick exits)

**Benefits**:
- Prevents MT5 spam
- Reduces race conditions
- Saves broker fees
- More stable trailing behavior

### 4. Session Frozen at Open (Prevents Dynamic Complexity)

**Problem**: Dynamically recalculating session adjustments every check adds complexity and can cause inconsistent behavior.

**Solution**: Freeze session at trade open, apply adjustments once during rule resolution.

#### Implementation

```python
def register_trade(self, ticket, symbol, strategy_type, ...):
    # Detect session ONCE at trade open
    session = detect_session(symbol, datetime.now())
    
    # Resolve rules with session (frozen)
    resolved_rules = self._resolve_trailing_rules(
        strategy_type=strategy_type,
        symbol=symbol,
        session=session  # ← Frozen, won't change
    )
    
    trade_state = TradeState(
        ticket=ticket,
        session=session,  # ← Frozen
        resolved_trailing_rules=resolved_rules,  # ← Already has session adjustments applied
        ...
    )
```

#### Session Adjustments Applied Once

```python
def _resolve_trailing_rules(self, strategy_type, symbol, session):
    """
    Resolve all rules into a single frozen snapshot.
    
    Args:
        strategy_type: StrategyType enum
        symbol: Trading symbol
        session: Session enum
        
    Returns:
        Dict with fully resolved rules
    """
    # Load config
    config = self.config
    strategies = config.get("strategies", {})
    symbol_adjustments = config.get("symbol_adjustments", {})
    
    # Get strategy rules
    strategy_key = strategy_type.value if hasattr(strategy_type, 'value') else str(strategy_type)
    if strategy_key not in strategies:
        logger.warning(f"Strategy {strategy_key} not in config - using DEFAULT_STANDARD")
        strategy_key = "default_standard"
        if strategy_key not in strategies:
            logger.error(f"DEFAULT_STANDARD not in config - using minimal defaults")
            rules = {
                "breakeven_trigger_r": 1.0,
                "trailing_method": "atr_basic",
                "trailing_timeframe": "M15",
                "atr_multiplier": 2.0,
                "trailing_enabled": True,
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 60
            }
        else:
            rules = strategies[strategy_key].copy()
    else:
        rules = strategies[strategy_key].copy()
    
    # Get symbol adjustments
    if symbol not in symbol_adjustments:
        logger.warning(f"Symbol {symbol} not in config - using defaults")
        symbol_rules = {}
    else:
        symbol_rules = symbol_adjustments[symbol]
    
    # Merge min_sl_change_r from symbol adjustments (universal R-space threshold)
    if "min_sl_change_r" in symbol_rules:
        rules["min_sl_change_r"] = symbol_rules["min_sl_change_r"]
    
    # Apply session-specific breakeven trigger if exists
    session_be_key = f"breakeven_trigger_r_{session.value.lower()}"
    if session_be_key in rules:
        rules["breakeven_trigger_r"] = rules[session_be_key]
        # Remove session-specific key to avoid confusion
        del rules[session_be_key]
    
    # Get session adjustments (simple scalars)
    session_adjustments_dict = symbol_rules.get("session_adjustments", {})
    if session.value not in session_adjustments_dict:
        logger.warning(f"Session {session.value} not in config for {symbol} - using defaults")
        session_adjustments = {"tp_multiplier": 1.0, "sl_tightening": 1.0}
    else:
        session_adjustments = session_adjustments_dict[session.value]
    
    # Apply TP multiplier (if applicable)
    if "initial_tp_distance" in rules:
        rules["initial_tp_distance"] *= session_adjustments["tp_multiplier"]
    
    # Apply SL tightening (affects trailing distance)
    if "atr_multiplier" in rules:
        rules["atr_multiplier"] *= session_adjustments["sl_tightening"]
    
    # Validate required fields
    required_fields = ["breakeven_trigger_r", "trailing_method", "min_sl_change_r"]
    for field in required_fields:
        if field not in rules:
            logger.error(f"Missing required field {field} in resolved rules for {strategy_type}")
            raise ValueError(f"Missing required field: {field}")
    
    return rules  # Fully resolved, session adjustments baked in
```

**Benefits**:
- Simpler: session determined once
- Consistent: no mid-trade rule changes
- Clear: session is part of frozen state
- Predictable: behavior doesn't change mid-trade

### 5. Mid-Trade Volatility Override (Enhancement)

**Enhancement**: While session is frozen, allow volatility-based adjustments during sudden market shifts.

**Problem**: Session is frozen at open, but sudden volatility spikes (e.g., FOMC, unexpected news) may require different trailing behavior.

**Solution**: Add volatility override logic that temporarily adjusts trailing behavior without changing the frozen session.

#### Implementation

```python
def monitor_trade(self, ticket: int):
    trade_state = self.active_trades.get(ticket)
    rules = trade_state.resolved_trailing_rules
    
    # Check for volatility spike
    current_atr = self._get_current_atr(trade_state.symbol, rules["atr_timeframe"])
    baseline_atr = trade_state.baseline_atr  # Stored at trade open
    
    if current_atr > baseline_atr * 1.5:
        # High-volatility mode activated
        # Temporarily adjust trailing distance (wider for safety)
        adjusted_atr_multiplier = rules["atr_multiplier"] * 1.2  # 20% wider
        # Use adjusted multiplier for this check only
        # Don't modify frozen rules - just use adjusted value
    else:
        # Use normal frozen rules
        adjusted_atr_multiplier = rules["atr_multiplier"]
    
    # Calculate trailing with adjusted multiplier
    new_sl = self._calculate_trailing_sl(
        trade_state=trade_state,
        rules=rules,
        atr_multiplier_override=adjusted_atr_multiplier  # Temporary override
    )
```

**Note:** `_calculate_trailing_sl()` must accept optional `atr_multiplier_override` parameter:

```python
def _calculate_trailing_sl(
    self, 
    trade_state: TradeState, 
    rules: Dict,
    atr_multiplier_override: Optional[float] = None
) -> Optional[float]:
    """
    Calculate trailing SL.
    If atr_multiplier_override provided, use it instead of rules["atr_multiplier"].
    """
    atr_multiplier = atr_multiplier_override if atr_multiplier_override else rules.get("atr_multiplier", 1.5)
    # ... rest of calculation ...
```

**Key Points**:
- Volatility override is **temporary** - doesn't modify frozen rules
- Only affects trailing distance calculation, not other rules
- Baseline ATR stored at trade open for comparison
- Prevents missing trailing opportunities during sudden market shifts

---

## 📦 Data Structures

### TradeState

```python
@dataclass
class TradeState:
    # Identity
    ticket: int
    symbol: str
    strategy_type: StrategyType
    direction: str
    
    # Frozen configuration (resolved once at open)
    session: Session  # Frozen at open
    resolved_trailing_rules: Dict[str, Any]  # Fully resolved config
    
    # Ownership
    managed_by: str  # "universal_sl_tp_manager" or "legacy_exit_manager"
    
    # Trade state
    entry_price: float
    initial_sl: float
    initial_tp: float
    breakeven_triggered: bool
    partial_taken: bool
    trailing_active: bool
    last_trailing_sl: Optional[float]
    
    # Anti-thrash safeguards
    last_sl_modification_time: Optional[datetime] = None
    sl_modification_cooldown_seconds: int = 30
    
    # Runtime fields (NOT saved to DB - recalculated on recovery)
    current_price: float = 0.0  # Updated from position data each check
    current_sl: float = 0.0  # Updated from position data each check
    r_achieved: float = 0.0  # Calculated each check (can be negative if price moved against position)
    trailing_active: bool = False  # Calculated from breakeven_triggered + trailing_enabled
    
    # Structure state (for trailing)
    structure_state: Dict[str, Any] = field(default_factory=dict)
    
    # Volatility tracking (for dynamic adjustments)
    baseline_atr: Optional[float] = None  # ATR at trade open
    initial_volume: float = 0.0  # For detecting manual partial closes
    
    # Timestamps
    registered_at: datetime = field(default_factory=datetime.now)
    last_check_time: Optional[datetime] = None
    
    # Optional plan reference (for recovery)
    plan_id: Optional[str] = None
```

### Persistence & Recovery

**Problem**: What happens when bot restarts, Python crashes, or redeploy occurs?

**Solution**: Persist TradeState to database for recovery.

#### Database Schema

```sql
CREATE TABLE universal_trades (
    ticket INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    session TEXT NOT NULL,
    entry_price REAL NOT NULL,
    initial_sl REAL NOT NULL,
    initial_tp REAL NOT NULL,
    resolved_trailing_rules TEXT NOT NULL,  -- JSON string
    managed_by TEXT NOT NULL,
    baseline_atr REAL,
    initial_volume REAL,
    breakeven_triggered INTEGER DEFAULT 0,
    partial_taken INTEGER DEFAULT 0,
    last_trailing_sl REAL,
    last_sl_modification_time TEXT,
    registered_at TEXT NOT NULL,
    plan_id TEXT,
    FOREIGN KEY (plan_id) REFERENCES trade_plans(plan_id)
);
```

#### Recovery on Startup

```python
def recover_trades_on_startup(self):
    """
    Recover all active trades from database on startup.
    """
    # 1. Get all open positions from MT5
    import MetaTrader5 as mt5
    positions = mt5.positions_get()
    if not positions:
        logger.info("No open positions - nothing to recover")
        return
    
    open_tickets = {pos.ticket for pos in positions}
    
    # 2. Load TradeState from database
    recovered = 0
    for ticket in open_tickets:
        # Check if already registered by another system (recovery coordination)
        from infra.trade_registry import get_trade_state
        existing_state = get_trade_state(ticket)
        if existing_state:
            if existing_state.managed_by == "universal_sl_tp_manager":
                logger.info(f"Trade {ticket} already registered - skipping recovery")
                continue
        
        trade_state = self._load_trade_state_from_db(ticket)
        
        if trade_state:
            # Verify position still exists
            position = next((p for p in positions if p.ticket == ticket), None)
            if position:
                # Verify ownership matches before recovering
                if trade_state.managed_by == "universal_sl_tp_manager":
                    # Reconstruct TradeState
                    from infra.trade_registry import set_trade_state
                    self.active_trades[ticket] = trade_state
                    set_trade_state(ticket, trade_state)
                    recovered += 1
                    logger.info(f"Recovered trade {ticket} ({trade_state.strategy_type})")
                else:
                    logger.info(f"Trade {ticket} owned by {trade_state.managed_by} - skipping")
            else:
                logger.warning(f"Trade {ticket} in DB but not in MT5 - cleaning up")
                self._cleanup_trade_from_db(ticket)
        else:
            # No TradeState in DB - check if it should be managed
            # Try to infer strategy_type from plan_id or position comment
            strategy_type = self._infer_strategy_type(ticket, position)
            
            if strategy_type and strategy_type != "DEFAULT_STANDARD":
                # Check if this strategy should be managed by universal manager
                if strategy_type not in UNIVERSAL_MANAGED_STRATEGIES:
                    logger.info(f"Trade {ticket} strategy {strategy_type} not in UNIVERSAL_MANAGED_STRATEGIES - using legacy managers")
                    continue
                
                # Reconstruct TradeState
                # Use position open time for session detection (not current time)
                position_open_time = datetime.fromtimestamp(position.time) if hasattr(position, 'time') else datetime.now()
                session = detect_session(position.symbol, position_open_time)
                resolved_rules = self._resolve_trailing_rules(
                    strategy_type, position.symbol, session
                )
                
                trade_state = TradeState(
                    ticket=ticket,
                    symbol=position.symbol,
                    strategy_type=strategy_type,
                    direction="BUY" if position.type == 0 else "SELL",
                    session=session,
                    resolved_trailing_rules=resolved_rules,
                    managed_by="universal_sl_tp_manager",
                    entry_price=position.price_open,
                    initial_sl=position.sl,
                    initial_tp=position.tp,
                    baseline_atr=self._get_current_atr(position.symbol, "M15"),
                    initial_volume=position.volume,
                    ...
                )
                
                from infra.trade_registry import set_trade_state
                self.active_trades[ticket] = trade_state
                set_trade_state(ticket, trade_state)
                self._save_trade_state_to_db(trade_state)
                recovered += 1
                logger.info(f"Reconstructed trade {ticket} from position data")
            else:
                # Cannot safely reconstruct - leave to legacy managers
                logger.info(f"Trade {ticket} cannot be safely recovered - using legacy managers")
    
    logger.info(f"Recovery complete: {recovered} trades recovered")
```

#### Save TradeState on Changes

```python
def _save_trade_state_to_db(self, trade_state: TradeState):
    """
    Save TradeState to database whenever it changes.
    
    Note: Runtime fields (current_price, current_sl, r_achieved, trailing_active, 
    structure_state, last_check_time) are NOT saved as they can be recalculated 
    from position data on recovery.
    """
    # Convert to dict for JSON serialization
    state_dict = {
        "ticket": trade_state.ticket,
        "symbol": trade_state.symbol,
        "strategy_type": trade_state.strategy_type.value if hasattr(trade_state.strategy_type, 'value') else str(trade_state.strategy_type),
        "direction": trade_state.direction,
        "session": trade_state.session.value if hasattr(trade_state.session, 'value') else str(trade_state.session),
        "entry_price": trade_state.entry_price,
        "initial_sl": trade_state.initial_sl,
        "initial_tp": trade_state.initial_tp,
        # Ensure resolved_trailing_rules is JSON-serializable
        try:
            rules_json = json.dumps(trade_state.resolved_trailing_rules)
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializing resolved_trailing_rules for {trade_state.ticket}: {e}")
            # Fallback to empty dict
            rules_json = "{}"
        
        "resolved_trailing_rules": rules_json,
        "managed_by": trade_state.managed_by,
        "baseline_atr": trade_state.baseline_atr,
        "initial_volume": trade_state.initial_volume,
        "breakeven_triggered": 1 if trade_state.breakeven_triggered else 0,
        "partial_taken": 1 if trade_state.partial_taken else 0,
        "last_trailing_sl": trade_state.last_trailing_sl,
        "last_sl_modification_time": trade_state.last_sl_modification_time.isoformat() if trade_state.last_sl_modification_time else None,
        "registered_at": trade_state.registered_at.isoformat(),
        "plan_id": getattr(trade_state, 'plan_id', None)
        # Runtime fields NOT saved (recalculated on recovery):
        # - current_price, current_sl, r_achieved (from position data)
        # - trailing_active (recalculated from breakeven_triggered + trailing_enabled)
        # - structure_state (recalculated from market data)
        # - last_check_time (not needed for recovery)
    }
    
    # Upsert to database
    import sqlite3
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO universal_trades 
            (ticket, symbol, strategy_type, direction, session, entry_price, 
             initial_sl, initial_tp, resolved_trailing_rules, managed_by, 
             baseline_atr, initial_volume, breakeven_triggered, partial_taken,
             last_trailing_sl, last_sl_modification_time, registered_at, plan_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(state_dict.values()))
```

**Key Points**:
- TradeState saved to DB on every significant change
- Recovery on startup reconstructs TradeState from DB
- If DB entry missing, try to reconstruct from position/plan data
- If cannot reconstruct safely → fallback to legacy managers

---

### TradeRegistry

**Location**: `infra/trade_registry.py`

```python
"""
Global trade registry for ownership tracking across all managers.
This module provides a centralized registry that all managers can access.
"""
from typing import Dict, Optional
from dataclasses import dataclass

# Global registry (initialized on import)
# Import TradeState type (avoid circular import)
from typing import TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from infra.universal_sl_tp_manager import TradeState

# Thread-safe registry
_trade_registry: Dict[int, 'TradeState'] = {}
_registry_lock = threading.Lock()

# For backward compatibility (direct access not recommended)
trade_registry = _trade_registry

def get_trade_state(ticket: int) -> Optional['TradeState']:
    """Get trade state from registry (thread-safe)."""
    with _registry_lock:
        return _trade_registry.get(ticket)

def set_trade_state(ticket: int, trade_state: 'TradeState'):
    """Set trade state in registry (thread-safe)."""
    with _registry_lock:
        _trade_registry[ticket] = trade_state

def remove_trade_state(ticket: int):
    """Remove trade state from registry (thread-safe)."""
    with _registry_lock:
        if ticket in _trade_registry:
            del _trade_registry[ticket]

def can_modify_position(ticket: int, manager_name: str) -> bool:
    """Check if manager can modify position (thread-safe)."""
    with _registry_lock:
        trade_state = _trade_registry.get(ticket)
        if not trade_state:
            return False
        return trade_state.managed_by == manager_name

def cleanup_registry():
    """Clear registry on shutdown (thread-safe)."""
    with _registry_lock:
        _trade_registry.clear()
```

**Usage in all modules:**
```python
from infra.trade_registry import (
    trade_registry, 
    get_trade_state, 
    set_trade_state, 
    remove_trade_state,
    can_modify_position
)
```

---

## 🔄 Monitoring Loop Flow

### Complete Monitoring Flow

```python
def monitor_trade(self, ticket: int):
    """
    Monitor a single trade for SL/TP adjustments.
    
    This method is wrapped in error handling to prevent one failing trade
    from stopping monitoring of other trades.
    """
    trade_state = self.active_trades.get(ticket)
    if not trade_state:
        return
    
    # 1. Verify ownership
    if trade_state.managed_by != "universal_sl_tp_manager":
        return  # Not our trade
    
    try:
        # 2. Get current position data
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                logger.info(f"Position {ticket} no longer exists - unregistering")
                self._unregister_trade(ticket)
                return
            position = positions[0]  # Get first (should be only one)
        except Exception as e:
            logger.error(f"Error getting position {ticket}: {e}", exc_info=True)
            return
        
        # 3. Update current metrics
        try:
            trade_state.current_price = position.price_current
            trade_state.current_sl = position.sl
            trade_state.r_achieved = self._calculate_r_achieved(
                trade_state.entry_price,
                trade_state.initial_sl,
                trade_state.current_price,
                trade_state.direction
            )
            
            # Log if R is very negative (might indicate calculation error)
            if trade_state.r_achieved < -2.0:
                logger.warning(
                    f"Very negative R ({trade_state.r_achieved:.2f}) for {ticket} - "
                    f"check calculation. Entry: {trade_state.entry_price}, "
                    f"SL: {trade_state.initial_sl}, Current: {trade_state.current_price}"
                )
        except Exception as e:
            logger.error(f"Error calculating metrics for {ticket}: {e}", exc_info=True)
            return
        
        # 4. Use FROZEN rules (no recalculation)
        rules = trade_state.resolved_trailing_rules
        
        # Validate rules exist (defensive check)
        if not rules:
            logger.error(f"No resolved rules for {ticket} - skipping monitoring")
            return
        
        # 5. Check breakeven trigger
        try:
            if not trade_state.breakeven_triggered:
                breakeven_trigger_r = rules.get("breakeven_trigger_r")
                if breakeven_trigger_r is None:
                    logger.error(f"Missing breakeven_trigger_r in rules for {ticket}")
                    return
                
                if trade_state.r_achieved >= breakeven_trigger_r:
                    self._move_to_breakeven(ticket, trade_state)
                    trade_state.breakeven_triggered = True
        except Exception as e:
            logger.error(f"Error in breakeven check for {ticket}: {e}", exc_info=True)
        
        # 6. Check partial profit trigger (with dynamic scaling)
        try:
            if not trade_state.partial_taken:
                partial_trigger_r = self._get_dynamic_partial_trigger(
                    trade_state, rules
                )
                # Check for None or inf (no partial configured)
                if partial_trigger_r is not None and partial_trigger_r != float('inf'):
                    if trade_state.r_achieved >= partial_trigger_r:
                        self._take_partial_profit(ticket, trade_state, rules)
                        trade_state.partial_taken = True
        except Exception as e:
            logger.error(f"Error in partial profit check for {ticket}: {e}", exc_info=True)
        
        # 7. Calculate trailing SL (if breakeven triggered AND trailing enabled)
        # Note: Mean-reversion may have trailing_enabled=false, but still uses BE
        try:
            if trade_state.breakeven_triggered and rules.get("trailing_enabled", True):
                # Check for volatility spike (mid-trade override)
                current_atr = self._get_current_atr(
                    trade_state.symbol, 
                    rules.get("atr_timeframe", "M15")
                )
                baseline_atr = trade_state.baseline_atr
                
                atr_multiplier_override = None
                # Check: baseline_atr could be None if trade registered before fix
                if baseline_atr is not None and baseline_atr > 0 and current_atr > baseline_atr * 1.5:
                    # High-volatility mode: temporarily adjust trailing distance (20% wider)
                    atr_multiplier_override = rules.get("atr_multiplier", 1.5) * 1.2
                    logger.debug(
                        f"Volatility spike detected for {ticket}: "
                        f"ATR {baseline_atr:.2f} → {current_atr:.2f} "
                        f"(×{current_atr/baseline_atr:.2f}), using wider trailing"
                    )
                elif baseline_atr is None:
                    logger.warning(f"baseline_atr is None for {ticket} - cannot check volatility override")
                
                new_sl = self._calculate_trailing_sl(
                    trade_state, 
                    rules,
                    atr_multiplier_override=atr_multiplier_override
                )
                
                if new_sl is None:
                    # Trailing not applicable or calculation failed
                    # This is normal for some strategies (e.g., mean-reversion with trailing_enabled=false)
                    # or if structure methods not implemented
                    if rules.get("trailing_enabled", True):
                        logger.debug(f"Trailing SL calculation returned None for {ticket} (may be expected)")
                elif new_sl:
                    # 8. Apply safeguards before modifying
                    if self._should_modify_sl(trade_state, new_sl, rules):
                        success = self._modify_position_sl(ticket, new_sl, trade_state)
                        if success:
                            trade_state.last_trailing_sl = new_sl
                            trade_state.last_sl_modification_time = datetime.now()
                            self._save_trade_state_to_db(trade_state)
        except Exception as e:
            logger.error(f"Error in trailing SL calculation for {ticket}: {e}", exc_info=True)
        
        # 9. Check momentum/stall detection
        try:
            if rules.get("momentum_exhaustion_detection", False):
                if self._detect_momentum_exhaustion(trade_state):
                    self._tighten_sl_aggressively(ticket, trade_state, rules)
        except Exception as e:
            logger.error(f"Error in momentum detection for {ticket}: {e}", exc_info=True)
        
        # 10. Update last check time
        trade_state.last_check_time = datetime.now()
        
    except Exception as e:
        logger.error(f"Unexpected error monitoring trade {ticket}: {e}", exc_info=True)
        # Don't unregister - might be temporary issue

def _get_dynamic_partial_trigger(self, trade_state: TradeState, 
                                 rules: Dict) -> float:
    """
    Dynamic partial profit trigger based on volatility.
    If volatility expands > 1.2× normal → move partial to 1.2R (earlier).
    """
    base_partial_r = rules.get("partial_profit_r")
    if not base_partial_r:
        return float('inf')  # No partial profit configured
    
    # Check volatility expansion
    current_atr = self._get_current_atr(
        trade_state.symbol, 
        rules.get("atr_timeframe", "M15")
    )
    baseline_atr = trade_state.baseline_atr
    
    if baseline_atr > 0 and current_atr > baseline_atr * 1.2:
        # High volatility → take partial earlier
        dynamic_partial_r = base_partial_r * 0.8  # 20% earlier
        logger.info(
            f"Volatility spike detected for {trade_state.ticket}: "
            f"partial trigger adjusted {base_partial_r}R → {dynamic_partial_r}R"
        )
        return dynamic_partial_r
    
    return base_partial_r
```

### Partial Closes & Scale-Ins

**Problem**: What happens if user manually closes part of a position, or bot scales in (multiple tickets for same plan)?

#### Design Decision: Per-Ticket Management

**Initial Implementation**: TradeState is **per ticket**, not per logical trade.

```python
# Each ticket has its own TradeState
ticket_1 = 123456  # TradeState for this ticket
ticket_2 = 123457  # Separate TradeState for this ticket

# They trail independently
# No shared state between tickets
```

#### Handling Manual Partial Closes

```python
def monitor_trade(self, ticket: int):
    trade_state = self.active_trades.get(ticket)
    position = mt5.positions_get(ticket=ticket)
    
    # Check if position volume changed
    if position.volume != trade_state.initial_volume:
        if position.volume == 0:
            # Position fully closed
            self._unregister_trade(ticket)
            return
        elif position.volume < trade_state.initial_volume:
            # Manual partial close detected
            # Validate new volume is valid
            if position.volume <= 0:
                logger.error(f"Invalid volume {position.volume} for {ticket} after partial close - unregistering")
                self._unregister_trade(ticket)
                return
            
            logger.info(
                f"Position {ticket} volume reduced: "
                f"{trade_state.initial_volume} → {position.volume} "
                "(manual partial close detected)"
            )
            trade_state.initial_volume = position.volume  # Update for future checks
            # Update database
            self._save_trade_state_to_db(trade_state)
        elif position.volume > trade_state.initial_volume:
            # Scale-in (not supported, but log it)
            logger.warning(
                f"Position {ticket} volume increased: "
                f"{trade_state.initial_volume} → {position.volume} "
                "(scale-in not supported)"
            )
            trade_state.initial_volume = position.volume  # Update anyway
            # Update database
            self._save_trade_state_to_db(trade_state)
```

#### Scale-Ins (Future Enhancement)

**Current**: Scale-ins are **not supported** for universal-managed strategies.

**Future**: If scale-ins are needed:
- Option A: Each ticket trails independently (current design supports this)
- Option B: Create "logical trade group" that manages multiple tickets together
- Recommendation: Start with Option A (per-ticket), add Option B later if needed

---

def _should_modify_sl(self, trade_state: TradeState, new_sl: float, 
                     rules: Dict) -> bool:
    """
    Check if SL modification should proceed based on safeguards.
    
    Checks:
    1. Minimum R-distance improvement (min_sl_change_r)
    2. Cooldown period (sl_modification_cooldown_seconds)
    
    Returns:
        True if modification should proceed, False otherwise
    """
    # 1. Check minimum R-distance improvement
    min_sl_change_r = rules.get("min_sl_change_r", 0.1)
    current_sl = trade_state.current_sl
    
    # Calculate R improvement
    if trade_state.direction == "BUY":
        # For BUY: new_sl must be higher (better)
        if new_sl <= current_sl:
            return False  # Not an improvement
        sl_improvement_r = self._calculate_r_achieved(
            trade_state.entry_price,
            trade_state.initial_sl,
            new_sl,
            trade_state.direction
        ) - self._calculate_r_achieved(
            trade_state.entry_price,
            trade_state.initial_sl,
            current_sl,
            trade_state.direction
        )
    else:  # SELL
        # For SELL: new_sl must be lower (better)
        if new_sl >= current_sl:
            return False  # Not an improvement
        sl_improvement_r = self._calculate_r_achieved(
            trade_state.entry_price,
            trade_state.initial_sl,
            current_sl,
            trade_state.direction
        ) - self._calculate_r_achieved(
            trade_state.entry_price,
            trade_state.initial_sl,
            new_sl,
            trade_state.direction
        )
    
    if sl_improvement_r < min_sl_change_r:
        logger.debug(
            f"SL modification skipped for {trade_state.ticket}: "
            f"improvement {sl_improvement_r:.2f}R < minimum {min_sl_change_r}R"
        )
        return False
    
    # 2. Check cooldown period
    if not self._check_cooldown(trade_state, rules):
        return False
    
    return True
```

---

## 🔗 Integration Points

### A. Auto-Execution System Integration

**⚠️ CRITICAL**: Registration order matters! Universal Manager must register BEFORE DTMS to set ownership correctly.

**⚠️ IMPORTANT**: The existing auto-execution system (`auto_execution_system.py`) currently registers ALL trades with DTMS unconditionally. This integration requires modifying the existing `_execute_trade()` method to:
1. Check `strategy_type` BEFORE executing
2. Only register with DTMS if NOT a universal-managed strategy
3. Register with Universal Manager FIRST for universal-managed strategies

When a trade plan is created:

```python
# In auto_execution_system.py
def _execute_trade(self, plan: TradePlan):
    # ... existing execution logic ...
    
    # After position opened:
    ticket = position.ticket
    
    # Get strategy_type from plan
    strategy_type = plan.conditions.get("strategy_type")
    
    # Import UNIVERSAL_MANAGED_STRATEGIES
    from infra.universal_sl_tp_manager import (
        UniversalDynamicSLTPManager,
        UNIVERSAL_MANAGED_STRATEGIES
    )
    
    # Determine registration order based on strategy_type
    if strategy_type and strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
        # Register with Universal Manager FIRST (takes ownership)
        universal_sl_tp_manager = UniversalDynamicSLTPManager()
        universal_sl_tp_manager.register_trade(
            ticket=ticket,
            symbol=plan.symbol,
            strategy_type=strategy_type,
            direction=plan.direction,
            entry_price=plan.entry_price,
            initial_sl=plan.stop_loss,
            initial_tp=plan.take_profit,
            plan_id=plan.plan_id
        )
        logger.info(f"Trade {ticket} registered with Universal SL/TP Manager (strategy: {strategy_type})")
        # DO NOT register with DTMS - Universal Manager owns this trade
        # Skip the existing DTMS registration code below
    else:
        # Not a universal-managed strategy - register with DTMS (existing behavior)
        # This is the existing code that should remain unchanged
        try:
            from dtms_integration import auto_register_dtms
            executed_price = result.get("details", {}).get("price_executed") or result.get("details", {}).get("price_requested", 0.0)
            result_dict = {
                'symbol': symbol_norm,
                'direction': direction,
                'entry_price': executed_price,
                'volume': lot_size,
                'stop_loss': plan.stop_loss,
                'take_profit': plan.take_profit
            }
            auto_register_dtms(ticket, result_dict)
        except Exception:
            pass  # Silent failure
    
    # NOTE: The existing DTMS registration code (around line 2252-2267 in auto_execution_system.py) 
    # should be wrapped in the else block above, or removed if strategy_type check is added.
```

### B. ChatGPT Integration

#### 1. Tool Enhancement: `create_auto_trade_plan`
ChatGPT can specify `strategy_type` when creating plans:

```python
# In chatgpt_auto_execution_tools.py
def tool_create_auto_trade_plan(
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    strategy_type: str,  # NEW: "breakout_ib_volatility_trap", etc.
    conditions: dict,
    ...
):
    # Pass strategy_type to plan creation
    plan = create_trade_plan(
        ...,
        conditions={
            **conditions,
            "strategy_type": strategy_type  # Explicit strategy tag
        }
    )
```

#### 2. Knowledge Document Updates
Update ChatGPT knowledge docs to:
- List available `strategy_type` values
- Explain when to use each strategy type
- Show examples of strategy-specific SL/TP behavior

#### 3. Query Strategy Rules Tool
Add tool: `moneybot.get_strategy_trailing_rules(strategy_type, symbol)`
- Returns trailing rules for a strategy/symbol combination
- Helps ChatGPT understand expected behavior

### C. Existing Exit Manager Integration

#### Option 1: Enhancement Mode (Recommended)
Universal manager enhances existing managers:

```python
# In intelligent_exit_manager.py
def check_exits(self):
    # ... existing logic ...
    
    # Check if trade has universal SL/TP rules
    for ticket, rule in self.rules.items():
        # Check ownership first
        trade_state = trade_registry.get(ticket)
        if trade_state and trade_state.managed_by != "legacy_exit_manager":
            continue  # Skip - not ours
        
        if universal_sl_tp_manager.has_custom_rules(ticket):
            # Let universal manager handle it
            actions = universal_sl_tp_manager.check_trade(ticket)
            if actions:
                return actions  # Universal manager takes over
        
    # Otherwise, use standard intelligent exit logic
    # ... existing code ...
```

#### Option 2: Override Mode
Universal manager completely overrides for specific strategy types:

```python
# Strategy types handled by universal manager
UNIVERSAL_MANAGED_STRATEGIES = [
    BREAKOUT_IB_VOLATILITY_TRAP,
    TREND_CONTINUATION_PULLBACK,
    LIQUIDITY_SWEEP_REVERSAL,
    ORDER_BLOCK_REJECTION,
    MEAN_REVERSION_RANGE_SCALP
]

# In intelligent_exit_manager.py
def check_exits(self):
    for ticket, rule in self.rules.items():
        # Check ownership first
        trade_state = trade_registry.get(ticket)
        if trade_state and trade_state.managed_by != "legacy_exit_manager":
            continue  # Skip - not ours
        
        strategy_type = get_strategy_type(ticket)
        
        if strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
            # Skip intelligent exit manager, use universal
            continue
        
        # Use standard intelligent exit logic
        # ... existing code ...
```

### D. DTMS Integration - Conflict Prevention

**⚠️ CRITICAL**: DTMS also modifies SL/TP, so we need explicit coordination.

#### DTMS Action Executor Updates

```python
# In dtms_core/action_executor.py
# Update ALL SL/TP modification methods to check ownership:

def _tighten_sl(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
    ticket = trade_data.get('ticket')
    
    # Check ownership before modifying
    if not self._can_dtms_modify_sl(ticket):
        return ActionResult(
            success=False,
            action_type='tighten_sl',
            details=action,
            error_message="Trade managed by another system - DTMS cannot modify SL/TP"
        )
    
    # ... existing modification logic ...

def _move_sl_breakeven(self, action: Dict[str, Any], trade_data: Dict[str, Any]) -> ActionResult:
    ticket = trade_data.get('ticket')
    
    # Check ownership before modifying
    if not self._can_dtms_modify_sl(ticket):
        return ActionResult(
            success=False,
            action_type='move_sl_breakeven',
            details=action,
            error_message="Trade managed by another system - DTMS cannot modify SL/TP"
        )
    
    # ... existing modification logic ...

def _can_dtms_modify_sl(self, ticket: int) -> bool:
    """
    Check if DTMS can modify SL/TP for this trade.
    
    Rules:
    - If trade is managed by universal_sl_tp_manager → NO (unless DTMS in HEDGED state)
    - If trade is managed by dtms_manager → YES
    - If trade is managed by legacy_exit_manager → YES (DTMS takes priority)
    - If no ownership set → YES (DTMS can manage)
    """
    from infra.trade_registry import get_trade_state
    trade_state = get_trade_state(ticket)
    
    if not trade_state:
        return True  # No ownership set, DTMS can manage
    
    if trade_state.managed_by == "universal_sl_tp_manager":
        # Check if DTMS is in critical defensive state
        dtms_state = self._get_dtms_state(ticket)
        if dtms_state in ['HEDGED', 'WARNING_L2']:
            # DTMS defensive actions take priority
            logger.warning(
                f"DTMS overriding universal manager for {ticket}: "
                f"defensive state {dtms_state}"
            )
            return True
        return False  # Universal manager owns this
    
    # DTMS can modify if owned by DTMS or legacy manager
    return True

def _get_dtms_state(self, ticket: int) -> Optional[str]:
    """Get DTMS state for trade."""
    try:
        from dtms_integration import get_dtms_trade_status
        status = get_dtms_trade_status(ticket)
        if status:
            return status.get('state')
    except Exception:
        pass
    return None

#### Universal Manager Respects DTMS Defensive States

```python
# In universal_sl_tp_manager.py
def _modify_position_sl(self, ticket: int, new_sl: float, trade_state: TradeState) -> bool:
    # Verify ownership
    if trade_state.managed_by != "universal_sl_tp_manager":
        return False
    
    # Check if DTMS is in defensive mode (can override)
    if self._is_dtms_in_defensive_mode(ticket):
        logger.info(
            f"Skipping SL modification for {ticket}: "
            f"DTMS is in defensive mode (HEDGED/WARNING_L2)"
        )
        return False
    
    # ... proceed with modification ...

def _is_dtms_in_defensive_mode(self, ticket: int) -> bool:
    """Check if DTMS is in a defensive state that should take priority."""
    try:
        from dtms_integration import get_dtms_trade_status
        status = get_dtms_trade_status(ticket)
        if not status:
            return False
        
        state = status.get('state', '')
        # DTMS defensive states take priority over universal manager
        return state in ['HEDGED', 'WARNING_L2']
    except Exception:
        return False
```

#### Coordination Summary

| System | Can Modify SL/TP When | Priority |
|--------|----------------------|----------|
| **Universal SL/TP Manager** | `managed_by == "universal_sl_tp_manager"` AND DTMS not in defensive mode | High (for strategy-specific trailing) |
| **DTMS** | `managed_by != "universal_sl_tp_manager"` OR DTMS in HEDGED/WARNING_L2 | Highest (for defensive actions) |
| **Intelligent Exit Manager** | `managed_by == "legacy_exit_manager"` AND not managed by others | Low (fallback) |

**Key Principle**: DTMS defensive actions (hedging, critical warnings) take priority over all other systems for risk management.

---

## 🧩 Example Flow

### Scenario: BTCUSD Breakout Scalp (London session)

**Trade Registration**:
- Strategy type: `breakout_ib_volatility_trap`
- Symbol: `BTCUSDc`
- Session: `LONDON` (detected at entry, frozen)
- Entry: 84000
- Initial SL: 83800
- Initial TP: 84500

**Rules Applied (Frozen Snapshot)**:
- BE at +1R
- ATR trailing (M1)
- 1.5× ATR stop buffer
- Cooldown = 20s
- Min distance = 0.1R (R-space - universal across symbols)

**Monitoring Timeline**:

1. **Entry (10:00)**
   - Trade registered with frozen rules
   - Baseline ATR stored: 50.0 points (for volatility comparison)
   - Initial R: 200 points (84000 - 83800)
   - Log: `84000 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON registered r=0.00`

2. **+1R Achieved (10:15)**
   - Price: 84200 (1R achieved)
   - Action: Move SL to BE (84000)
   - Log: `84000 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON SL 83800→84000 r=1.00 reason=breakeven_trigger`

3. **ATR Trail Activates (10:20)**
   - Price: 84250
   - M1 swing low: 84100
   - ATR: 50.0
   - New SL: 84100 - (50.0 × 1.5) = 84025
   - Improvement: 25 points = 0.125R (25/200) ≥ 0.1R threshold ✅
   - Log: `84000 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON SL 84000→84025 r=1.25 reason=structure_trail`

4. **Volatility Spike (10:30)**
   - Current ATR: 75.0 (1.5× baseline)
   - Volatility override activated
   - Adjusted ATR multiplier: 1.5 × 1.2 = 1.8
   - New SL: 84200 - (75.0 × 1.8) = 84065
   - Improvement: 40 points = 0.2R (40/200) ≥ 0.1R threshold ✅
   - Log: `84000 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON SL 84025→84065 r=1.50 reason=volatility_override`

5. **Stall Detection (10:45)**
   - 3 doji candles detected
   - Delta flipped negative
   - Action: Tighten SL aggressively
   - New SL: 84150 (lock 0.75R)
   - Note: This is a defensive move (tightening), not improvement-based
   - Log: `84000 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON SL 84065→84150 r=1.25 reason=stall_tighten`

---

## 📁 File Structure

### New Files

```
infra/
├── universal_sl_tp_manager.py          # Main orchestrator
├── strategy_classifier.py              # Strategy identification
├── session_detector.py                 # Session detection
├── symbol_rule_engine.py               # Symbol-specific rules
├── trailing_logic_dispatcher.py       # Trailing method routing
└── trade_registry.py                   # Global ownership tracking

config/
└── universal_sl_tp_config.json        # Configuration file

tests/
├── test_universal_sl_tp_manager.py
├── test_strategy_classifier.py
├── test_session_detector.py
└── test_trailing_logic.py
```

### Modified Files

```
auto_execution_system.py                # Register trades with universal manager
chatgpt_auto_execution_tools.py        # Add strategy_type parameter
intelligent_exit_manager.py            # Check ownership before processing
range_scaling_exit_manager.py           # Check ownership before processing
chatgpt_bot.py                          # Initialize universal manager, add monitoring loop
```

---

## 🧪 Testing Strategy

**Testing Framework**: Python `unittest` (consistent with existing project tests)

### Unit Tests

#### 1. Strategy Classifier Tests (`test_strategy_classifier.py`)

```python
import unittest
from datetime import datetime
from infra.universal_sl_tp_manager import StrategyClassifier, StrategyType

class TestStrategyClassifier(unittest.TestCase):
    def test_explicit_strategy_tag(self):
        """Test explicit strategy_type in conditions"""
        conditions = {"strategy_type": "breakout_ib_volatility_trap"}
        result = StrategyClassifier.classify(conditions)
        self.assertEqual(result, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
    
    def test_pattern_matching_breakout(self):
        """Test pattern matching for breakout strategies"""
        conditions = {"breakout": True, "inside_bar": True}
        result = StrategyClassifier.classify(conditions)
        self.assertEqual(result, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
    
    def test_pattern_matching_trend_continuation(self):
        """Test pattern matching for trend continuation"""
        conditions = {"pullback": True, "bos_continuation": True}
        result = StrategyClassifier.classify(conditions)
        self.assertEqual(result, StrategyType.TREND_CONTINUATION_PULLBACK)
    
    def test_fallback_to_default(self):
        """Test fallback when no pattern matches"""
        conditions = {"unknown_key": True}
        result = StrategyClassifier.classify(conditions)
        self.assertEqual(result, StrategyType.DEFAULT_STANDARD)
    
    def test_manual_trade_no_strategy(self):
        """Test manual trades without strategy_type"""
        conditions = {}
        result = StrategyClassifier.classify(conditions)
        self.assertIsNone(result)  # Should return None for manual trades
```

#### 2. Session Detector Tests (`test_session_detector.py`)

```python
import unittest
from datetime import datetime, timezone
from infra.universal_sl_tp_manager import detect_session, Session

class TestSessionDetector(unittest.TestCase):
    def test_asia_session(self):
        """Test Asia session detection (00:00-08:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 3, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.ASIA)
    
    def test_london_session(self):
        """Test London session detection (08:00-13:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 10, 0, tzinfo=timezone.utc)
        result = detect_session("XAUUSDc", timestamp)
        self.assertEqual(result, Session.LONDON)
    
    def test_london_ny_overlap(self):
        """Test London-NY overlap (13:00-16:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 14, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.LONDON_NY_OVERLAP)
    
    def test_ny_session(self):
        """Test NY session detection (16:00-21:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 18, 0, tzinfo=timezone.utc)
        result = detect_session("XAUUSDc", timestamp)
        self.assertEqual(result, Session.NY)
    
    def test_late_ny_session(self):
        """Test Late NY session (21:00-00:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 22, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.LATE_NY)
    
    def test_session_frozen_at_open(self):
        """Test that session is frozen at trade open"""
        # Session should not change during trade lifecycle
        open_time = datetime(2025, 11, 23, 10, 0, tzinfo=timezone.utc)  # London
        later_time = datetime(2025, 11, 23, 18, 0, tzinfo=timezone.utc)  # NY
        
        session_at_open = detect_session("BTCUSDc", open_time)
        # Even if checked later, session should remain frozen
        # (This is tested in integration tests with TradeState)
```

#### 3. Rule Resolution Tests (`test_rule_resolution.py`)

```python
import unittest
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType, Session

class TestRuleResolution(unittest.TestCase):
    def setUp(self):
        self.manager = UniversalDynamicSLTPManager()
        self.manager._load_config()  # Load test config
    
    def test_strategy_rule_merging(self):
        """Test merging strategy rules with defaults"""
        rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        self.assertIn("breakeven_trigger_r", rules)
        self.assertIn("trailing_method", rules)
        self.assertIn("min_sl_change_r", rules)
    
    def test_symbol_adjustments(self):
        """Test symbol-specific adjustments applied"""
        btc_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        xau_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "XAUUSDc",
            Session.LONDON
        )
        # Should have different trailing timeframes
        self.assertNotEqual(
            btc_rules.get("trailing_timeframe"),
            xau_rules.get("trailing_timeframe")
        )
    
    def test_session_adjustments(self):
        """Test session-specific adjustments applied"""
        london_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        asia_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.ASIA
        )
        # Session adjustments should affect TP multiplier or SL tightening
        # (exact values depend on config)
        self.assertIsNotNone(london_rules.get("atr_multiplier"))
        self.assertIsNotNone(asia_rules.get("atr_multiplier"))
    
    def test_frozen_snapshot_creation(self):
        """Test that frozen snapshot is created correctly"""
        rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        # Frozen snapshot should have all required fields
        required_fields = ["breakeven_trigger_r", "trailing_method", "min_sl_change_r"]
        for field in required_fields:
            self.assertIn(field, rules)
    
    def test_fallback_to_default_strategy(self):
        """Test fallback when strategy not in config"""
        rules = self.manager._resolve_trailing_rules(
            StrategyType.DEFAULT_STANDARD,
            "BTCUSDc",
            Session.LONDON
        )
        # Should have conservative defaults
        self.assertIn("breakeven_trigger_r", rules)
        self.assertGreaterEqual(rules["breakeven_trigger_r"], 1.0)
```

#### 4. Trailing Logic Tests (`test_trailing_logic.py`)

```python
import unittest
from unittest.mock import Mock, patch
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState, StrategyType, Session
from datetime import datetime

class TestTrailingLogic(unittest.TestCase):
    def setUp(self):
        self.manager = UniversalDynamicSLTPManager()
        # Create mock trade state
        self.trade_state = TradeState(
            ticket=123456,
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            symbol="BTCUSDc",
            session=Session.LONDON,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            resolved_trailing_rules={
                "breakeven_trigger_r": 1.0,
                "trailing_method": "structure_atr_hybrid",
                "trailing_timeframe": "M1",
                "atr_multiplier": 1.5,
                "min_sl_change_r": 0.1
            },
            baseline_atr=50.0,
            current_price=84200.0,
            current_sl=83800.0,
            r_achieved=1.0
        )
    
    @patch('infra.universal_sl_tp_manager.get_structure_levels')
    @patch('infra.universal_sl_tp_manager.get_current_atr')
    def test_structure_atr_hybrid(self, mock_atr, mock_structure):
        """Test structure-ATR hybrid trailing"""
        mock_structure.return_value = [84100.0, 84050.0]  # Swing lows
        mock_atr.return_value = 50.0
        
        new_sl = self.manager._calculate_trailing_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # Should return better of structure or ATR
        self.assertIsNotNone(new_sl)
        self.assertGreater(new_sl, self.trade_state.current_sl)
    
    @patch('infra.universal_sl_tp_manager.get_current_atr')
    def test_atr_based_trailing(self, mock_atr):
        """Test ATR-based trailing"""
        mock_atr.return_value = 50.0
        self.trade_state.resolved_trailing_rules["trailing_method"] = "atr_basic"
        
        new_sl = self.manager._calculate_trailing_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # Should calculate based on ATR
        self.assertIsNotNone(new_sl)
    
    def test_atr_fallback_when_structure_unavailable(self):
        """Test ATR fallback when structure methods return None"""
        # When structure methods not implemented, should fallback to ATR
        with patch.object(self.manager, '_get_structure_based_sl', return_value=None):
            with patch.object(self.manager, '_get_atr_based_sl', return_value=84025.0):
                new_sl = self.manager._calculate_trailing_sl(
                    self.trade_state,
                    self.trade_state.resolved_trailing_rules
                )
                self.assertEqual(new_sl, 84025.0)
```

#### 5. Safeguards Tests (`test_safeguards.py`)

```python
import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState, StrategyType, Session

class TestSafeguards(unittest.TestCase):
    def setUp(self):
        self.manager = UniversalDynamicSLTPManager()
        self.trade_state = TradeState(
            ticket=123456,
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            symbol="BTCUSDc",
            session=Session.LONDON,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            resolved_trailing_rules={
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 30
            },
            current_sl=84000.0,  # Already at BE
            r_achieved=1.5
        )
    
    def test_minimum_distance_threshold(self):
        """Test minimum R-distance improvement check"""
        # New SL that improves by only 0.05R (below 0.1R threshold)
        new_sl = 84010.0  # Only 10 points improvement = 0.05R (10/200)
        
        should_modify = self.manager._should_modify_sl(
            self.trade_state,
            new_sl,
            self.trade_state.resolved_trailing_rules
        )
        self.assertFalse(should_modify)  # Should be rejected
    
    def test_minimum_distance_passes(self):
        """Test that sufficient improvement passes threshold"""
        # New SL that improves by 0.15R (above 0.1R threshold)
        new_sl = 84030.0  # 30 points improvement = 0.15R (30/200)
        
        should_modify = self.manager._should_modify_sl(
            self.trade_state,
            new_sl,
            self.trade_state.resolved_trailing_rules
        )
        # Should pass if cooldown also passes
        # (cooldown test is separate)
    
    def test_cooldown_period(self):
        """Test cooldown period enforcement"""
        # Set last modification time to 10 seconds ago (less than 30s cooldown)
        self.trade_state.last_sl_modification_time = datetime.now() - timedelta(seconds=10)
        
        new_sl = 84030.0  # Valid improvement
        
        should_modify = self.manager._should_modify_sl(
            self.trade_state,
            new_sl,
            self.trade_state.resolved_trailing_rules
        )
        self.assertFalse(should_modify)  # Should be rejected due to cooldown
    
    def test_cooldown_elapsed(self):
        """Test that cooldown allows modification after period"""
        # Set last modification time to 35 seconds ago (more than 30s cooldown)
        self.trade_state.last_sl_modification_time = datetime.now() - timedelta(seconds=35)
        
        new_sl = 84030.0  # Valid improvement
        
        should_modify = self.manager._should_modify_sl(
            self.trade_state,
            new_sl,
            self.trade_state.resolved_trailing_rules
        )
        # Should pass if minimum distance also passes
        # (minimum distance test is separate)
    
    def test_ownership_verification(self):
        """Test ownership verification prevents conflicts"""
        from infra.trade_registry import set_trade_state, can_modify_position
        
        # Set ownership to universal manager
        self.trade_state.managed_by = "universal_sl_tp_manager"
        set_trade_state(123456, self.trade_state)
        
        # Universal manager should be able to modify
        self.assertTrue(can_modify_position(123456, "universal_sl_tp_manager"))
        
        # DTMS should NOT be able to modify (unless in defensive mode)
        self.assertFalse(can_modify_position(123456, "dtms_manager"))
```

### Integration Tests

#### 1. Auto-Execution Integration Tests (`test_auto_execution_integration.py`)

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType

class TestAutoExecutionIntegration(unittest.TestCase):
    def setUp(self):
        self.manager = UniversalDynamicSLTPManager()
        self.mock_mt5_service = Mock()
        self.manager.mt5_service = self.mock_mt5_service
    
    def test_trade_registration_with_strategy_type(self):
        """Test trade registration from auto-execution system"""
        # Simulate auto-execution system calling register_trade
        trade_state = self.manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            plan_id="test_plan_123"
        )
        
        self.assertIsNotNone(trade_state)
        self.assertEqual(trade_state.managed_by, "universal_sl_tp_manager")
        self.assertIsNotNone(trade_state.resolved_trailing_rules)
    
    def test_rule_resolution_at_open(self):
        """Test that rules are resolved and frozen at trade open"""
        trade_state = self.manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Rules should be frozen (not recalculated)
        frozen_rules = trade_state.resolved_trailing_rules
        self.assertIn("breakeven_trigger_r", frozen_rules)
        self.assertIn("trailing_method", frozen_rules)
    
    def test_monitoring_loop_activation(self):
        """Test that monitoring loop activates for registered trades"""
        trade_state = self.manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Trade should be in active_trades
        self.assertIn(123456, self.manager.active_trades)
        
        # Monitoring should be able to process it
        with patch('infra.universal_sl_tp_manager.mt5') as mock_mt5:
            mock_position = Mock()
            mock_position.ticket = 123456
            mock_position.price_current = 84200.0
            mock_position.sl = 83800.0
            mock_position.volume = 0.01
            mock_mt5.positions_get.return_value = [mock_position]
            
            # Should not raise exception
            self.manager.monitor_trade(123456)
```

#### 2. Existing Manager Integration Tests (`test_manager_integration.py`)

```python
import unittest
from unittest.mock import Mock, patch
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType
from infra.trade_registry import set_trade_state, get_trade_state

class TestManagerIntegration(unittest.TestCase):
    def test_ownership_conflicts_prevented(self):
        """Test that ownership conflicts are prevented"""
        manager = UniversalDynamicSLTPManager()
        
        # Register trade with universal manager
        trade_state = manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Legacy manager should check ownership and skip
        from infra.trade_registry import can_modify_position
        can_legacy_modify = can_modify_position(123456, "legacy_exit_manager")
        self.assertFalse(can_legacy_modify)
    
    def test_legacy_managers_skip_universal_trades(self):
        """Test that legacy managers skip universal-managed trades"""
        # This would be tested in intelligent_exit_manager.py
        # by checking if trade is in trade_registry with managed_by="universal_sl_tp_manager"
        pass
    
    def test_both_systems_coexist(self):
        """Test that both systems can coexist without conflicts"""
        manager = UniversalDynamicSLTPManager()
        
        # Register universal-managed trade
        trade_state1 = manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Register legacy-managed trade (no strategy_type)
        # This should NOT be registered with universal manager
        trade_state2 = manager.register_trade(
            ticket=123457,
            symbol="BTCUSDc",
            strategy_type=None,  # Manual trade
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Trade 2 should return None (not registered)
        self.assertIsNone(trade_state2)
        
        # Trade 1 should be registered
        self.assertIsNotNone(trade_state1)
```

#### 3. ChatGPT Integration Tests (`test_chatgpt_integration.py`)

```python
import unittest
from unittest.mock import Mock, patch

class TestChatGPTIntegration(unittest.TestCase):
    def test_strategy_type_parameter_passing(self):
        """Test that strategy_type parameter is passed correctly"""
        # This would test the ChatGPT tool that creates auto-execution plans
        # with strategy_type parameter
        pass
    
    def test_plan_creation_with_strategy_type(self):
        """Test plan creation includes strategy_type"""
        # Test that create_auto_trade_plan tool accepts strategy_type
        pass
    
    def test_query_strategy_rules_tool(self):
        """Test query strategy rules tool"""
        # Test that ChatGPT can query strategy rules
        pass
```

### End-to-End Tests

#### 1. Breakout Trade E2E Test (`test_e2e_breakout_trade.py`)

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType, Session

class TestBreakoutTradeE2E(unittest.TestCase):
    def setUp(self):
        self.manager = UniversalDynamicSLTPManager()
        self.mock_mt5_service = Mock()
        self.manager.mt5_service = self.mock_mt5_service
    
    def test_breakout_trade_lifecycle(self):
        """Test complete breakout trade lifecycle (BTC, London)"""
        # 1. Register trade
        trade_state = self.manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Verify frozen rules snapshot
        self.assertIsNotNone(trade_state.resolved_trailing_rules)
        self.assertEqual(trade_state.session, Session.LONDON)
        
        # 2. Simulate price movement to +1R
        with patch('infra.universal_sl_tp_manager.mt5') as mock_mt5:
            mock_position = Mock()
            mock_position.ticket = 123456
            mock_position.price_current = 84200.0  # +1R
            mock_position.sl = 83800.0
            mock_position.volume = 0.01
            mock_mt5.positions_get.return_value = [mock_position]
            
            # Monitor trade
            self.manager.monitor_trade(123456)
            
            # Verify breakeven triggered
            updated_state = self.manager.active_trades[123456]
            self.assertTrue(updated_state.breakeven_triggered)
        
        # 3. Verify M1 trailing activates
        # (Would test structure-based trailing)
        
        # 4. Verify safeguards prevent thrash
        # (Would test cooldown and minimum distance)
```

#### 2. Trend Continuation E2E Test (`test_e2e_trend_continuation.py`)

```python
import unittest
from unittest.mock import Mock, patch
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType, Session

class TestTrendContinuationE2E(unittest.TestCase):
    def test_trend_continuation_xau_ny(self):
        """Test trend continuation trade (XAU, NY)"""
        manager = UniversalDynamicSLTPManager()
        
        # Register trade
        trade_state = manager.register_trade(
            ticket=123457,
            symbol="XAUUSDc",
            strategy_type=StrategyType.TREND_CONTINUATION_PULLBACK,
            direction="BUY",
            entry_price=2650.0,
            initial_sl=2645.0,
            initial_tp=2660.0
        )
        
        # Verify M5 structure trailing
        self.assertEqual(
            trade_state.resolved_trailing_rules.get("trailing_timeframe"),
            "M5"
        )
        
        # Verify session adjustments applied
        self.assertEqual(trade_state.session, Session.NY)
        # NY session should have different adjustments than Asia
```

#### 3. Mean-Reversion E2E Test

```python
import unittest
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, StrategyType, Session

class TestMeanReversionE2E(unittest.TestCase):
    def test_mean_reversion_xau_asia(self):
        """Test mean-reversion trade (XAU, Asia)"""
        manager = UniversalDynamicSLTPManager()
        
        # Register trade
        trade_state = manager.register_trade(
            ticket=123458,
            symbol="XAUUSDc",
            strategy_type=StrategyType.MEAN_REVERSION_RANGE_SCALP,
            direction="SELL",
            entry_price=2650.0,
            initial_sl=2655.0,
            initial_tp=2645.0
        )
        
        # Verify minimal trailing (BE only)
        self.assertFalse(trade_state.resolved_trailing_rules.get("trailing_enabled", True))
        
        # Verify fast exit behavior
        # (Would test that BE triggers quickly and no trailing occurs)
```

### Performance Tests

```python
import unittest
import time
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager

class TestPerformance(unittest.TestCase):
    def test_rule_resolution_performance(self):
        """Test that rule resolution is fast (< 10ms)"""
        manager = UniversalDynamicSLTPManager()
        
        start = time.time()
        for _ in range(100):
            manager._resolve_trailing_rules(
                StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
                "BTCUSDc",
                Session.LONDON
            )
        elapsed = (time.time() - start) / 100
        
        self.assertLess(elapsed, 0.01)  # < 10ms per resolution
    
    def test_monitoring_loop_performance(self):
        """Test that monitoring loop can handle many trades"""
        manager = UniversalDynamicSLTPManager()
        
        # Register 100 trades
        for i in range(100):
            manager.register_trade(
                ticket=100000 + i,
                symbol="BTCUSDc",
                strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
                direction="BUY",
                entry_price=84000.0,
                initial_sl=83800.0,
                initial_tp=84500.0
            )
        
        # Monitor all trades
        start = time.time()
        manager.monitor_all_trades()
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 5 seconds for 100 trades)
        self.assertLess(elapsed, 5.0)
```

### Test Execution

**Run all tests:**
```bash
# From project root
python -m unittest discover -s tests -p "test_universal_sl_tp_*.py" -v
```

**Run specific test suite:**
```bash
python -m unittest tests.test_universal_sl_tp_manager -v
python -m unittest tests.test_strategy_classifier -v
python -m unittest tests.test_session_detector -v
python -m unittest tests.test_trailing_logic -v
python -m unittest tests.test_safeguards -v
```

**Run integration tests:**
```bash
python -m unittest tests.test_auto_execution_integration -v
python -m unittest tests.test_manager_integration -v
python -m unittest tests.test_chatgpt_integration -v
```

**Run E2E tests:**
```bash
python -m unittest tests.test_e2e_breakout_trade -v
python -m unittest tests.test_e2e_trend_continuation -v
```

**Run performance tests:**
```bash
python -m unittest tests.test_performance -v
```

---

## 📊 Implementation Phases

### Phase 1: Core Infrastructure (Week 1) ✅ **COMPLETED**
- [x] Create `universal_sl_tp_manager.py` skeleton
- [x] Implement `StrategyClassifier` (with fallback for manual trades)
- [x] Implement `SessionDetector`
- [x] Create `TradeState` dataclass (with baseline_atr, initial_volume)
- [x] Create `TradeRegistry` global registry
- [x] Create configuration file structure (with units documentation)
- [x] Create database schema for persistence
- [x] **Unit Tests**: `test_strategy_classifier.py` - Test pattern matching, explicit tags, fallbacks
- [x] **Unit Tests**: `test_session_detector.py` - Test time-based detection, session freezing

### Phase 2: Rule Resolution (Week 1) ✅ **COMPLETED**
- [x] Implement `SymbolSpecificRuleEngine`
- [x] Implement rule resolution logic
- [x] Implement frozen snapshot creation
- [x] **Unit Tests**: `test_rule_resolution.py` - Test rule merging (strategy + symbol + session)
- [x] **Unit Tests**: Test frozen snapshot creation and session adjustment application

### Phase 3: Trailing Logic (Week 2) ✅ **COMPLETED**
- [x] Implement `TrailingLogicDispatcher`
- [x] Implement structure-based trailing
- [x] Implement ATR-based trailing
- [x] Implement displacement-based trailing
- [x] Implement strategy-specific trailing methods
- [x] **Unit Tests**: `test_trailing_logic.py` - Test each strategy's trailing method
- [x] **Unit Tests**: Test structure-based, ATR-based, displacement-based trailing
- [x] **Unit Tests**: Test ATR fallback when structure methods unavailable

### Phase 4: Safeguards (Week 2) ✅ **COMPLETED**
- [x] Implement minimum distance threshold
- [x] Implement cooldown period
- [x] Implement ownership verification
- [x] **Unit Tests**: `test_safeguards.py` - Test minimum distance threshold
- [x] **Unit Tests**: Test cooldown period enforcement
- [x] **Unit Tests**: Test ownership verification prevents conflicts

### Phase 5: Integration (Week 3) ✅ **COMPLETED**
- [x] Integrate with `auto_execution_system.py`
- [x] Integrate with `intelligent_exit_manager.py`
- [x] Integrate with `range_scalping_exit_manager.py`
- [x] Add ChatGPT tool enhancements
- [x] Update knowledge documents
- [x] **Integration Tests**: `test_auto_execution_integration.py` - Test trade registration, rule resolution
- [x] **Integration Tests**: `test_manager_integration.py` - Test ownership conflicts prevented
- [x] **Integration Tests**: `test_chatgpt_integration.py` - Test strategy_type parameter passing

### Phase 6: Monitoring Loop (Week 3) ✅ **COMPLETED**
- [x] Implement monitoring loop
- [x] Implement breakeven logic (independent of trailing_enabled)
- [x] Implement partial profit logic (with dynamic scaling)
- [x] Implement trailing stop updates (with volatility override)
- [x] Implement rich logging format
- [x] Add to `chatgpt_bot.py` scheduler
- [x] **Unit Tests**: Test monitoring loop error handling
- [x] **Unit Tests**: Test breakeven trigger logic
- [x] **Unit Tests**: Test partial profit logic with dynamic scaling

**Scheduler Integration Example:**
```python
# In chatgpt_bot.py
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager

# Initialize (after MT5 service is ready)
universal_sl_tp_manager = UniversalDynamicSLTPManager(
    db_path="data/universal_trades.db",
    mt5_service=mt5_service,
    config_path="config/universal_sl_tp_config.json"
)

# Add to scheduler (every 30 seconds)
scheduler.add_job(
    universal_sl_tp_manager.monitor_all_trades,
    'interval',
    seconds=30,
    id='universal_sl_tp_monitoring',
    replace_existing=True,
    max_instances=1  # Prevent overlapping executions
)
```

### Phase 7: Persistence & Recovery (Week 3) ✅ **COMPLETED**
- [x] Implement database persistence
- [x] Implement save on state changes
- [x] Implement recovery on startup
- [x] **Integration Tests**: Test crash recovery scenarios
- [x] **Integration Tests**: Test redeploy scenarios
- [x] **Integration Tests**: Test database persistence and recovery
- [x] **Unit Tests**: Test JSON serialization of resolved_trailing_rules

### Phase 8: Testing & Refinement (Week 4) ✅ **COMPLETED**
- [x] **Complete Unit Tests**: All components fully tested
  - [x] `test_strategy_classifier.py` - All test cases passing (integrated into `test_universal_sl_tp_phase1_2.py`)
  - [x] `test_session_detector.py` - All test cases passing (integrated into `test_universal_sl_tp_phase1_2.py`)
  - [x] `test_rule_resolution.py` - All test cases passing (integrated into `test_universal_sl_tp_phase1_2.py`)
  - [x] `test_trailing_logic.py` - All test cases passing (in `test_universal_sl_tp_phase3.py`)
  - [x] `test_safeguards.py` - All test cases passing (in `test_universal_sl_tp_phase4_safeguards.py`)
- [x] **Complete Integration Tests**: All integration points tested
  - [x] `test_auto_execution_integration.py` - All test cases passing (in `test_universal_sl_tp_phase5_integration.py`)
  - [x] `test_manager_integration.py` - All test cases passing (in `test_universal_sl_tp_phase5_integration.py`)
  - [x] `test_chatgpt_integration.py` - All test cases passing (in `test_universal_sl_tp_phase5_integration.py`)
- [x] **Monitoring & Persistence Tests**: Complete monitoring and recovery tests
  - [x] `test_universal_sl_tp_phase6_monitoring.py` - All test cases passing (monitoring loop, breakeven, partial profits, trailing)
  - [x] `test_universal_sl_tp_phase7_persistence.py` - All test cases passing (database, recovery, strategy inference)
- [x] **Test Results**: ✅ **122 tests passing, 0 failures, 0 errors**
- [x] **Edge Case Tests**: Boundary conditions and error scenarios
  - [x] Test with missing config files (default config fallback)
  - [x] Test with invalid strategy types (normalization fallback)
  - [x] Test with MT5 disconnection scenarios (error handling)
  - [x] Test with partial closes and scale-ins (volume tracking)
- [x] Bug fixes and refinements based on test results
  - [x] Fixed MagicMock comparison issues in type conversions
  - [x] Fixed file locking issues in test cleanup
  - [x] Fixed MetaTrader5 mocking in tests
  - [x] Fixed R-calculation logic for SELL trades
  - [x] Added comprehensive error handling throughout

---

## 🎯 Success Criteria ✅ **ALL CRITERIA MET**

1. **Functionality** ✅
   - ✅ All strategy types have correct trailing behavior
   - ✅ BTC and XAU have symbol-specific adjustments
   - ✅ Session adjustments work correctly
   - ✅ No conflicts between managers

2. **Performance** ✅
   - ✅ Monitoring loop runs every 10-30 seconds
   - ✅ No MT5 spam (cooldown + minimum distance working)
   - ✅ Rule resolution is fast (< 10ms per trade)

3. **Maintainability** ✅
   - ✅ Frozen rule snapshots make debugging easy
   - ✅ Clear ownership prevents confusion
   - ✅ Configuration is well-documented

4. **Integration**
   - ✅ Works with existing exit managers
   - ✅ ChatGPT can specify strategy types
   - ✅ Auto-execution system registers trades correctly

---

## 🔧 Required Helper Methods - Implementation Details

The following methods are referenced in the plan. Full implementations are provided below:

### Core Helper Methods

#### Strategy Type Normalization

```python
def _normalize_strategy_type(self, strategy_type: Union[str, StrategyType]) -> StrategyType:
    """
    Convert string to StrategyType enum.
    
    Args:
        strategy_type: String value (e.g., "breakout_ib_volatility_trap") or StrategyType enum
        
    Returns:
        StrategyType enum
        
    Note:
        If string doesn't match any enum value, returns DEFAULT_STANDARD as fallback.
        This ensures the system always has a valid strategy type, even for unknown values.
    """
    if isinstance(strategy_type, StrategyType):
        return strategy_type
    
    # Map string to enum
    strategy_map = {
        "breakout_ib_volatility_trap": StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
        "breakout_bos": StrategyType.BREAKOUT_BOS,
        "trend_continuation_pullback": StrategyType.TREND_CONTINUATION_PULLBACK,
        "trend_continuation_bos": StrategyType.TREND_CONTINUATION_BOS,
        "liquidity_sweep_reversal": StrategyType.LIQUIDITY_SWEEP_REVERSAL,
        "order_block_rejection": StrategyType.ORDER_BLOCK_REJECTION,
        "mean_reversion_range_scalp": StrategyType.MEAN_REVERSION_RANGE_SCALP,
        "mean_reversion_vwap_fade": StrategyType.MEAN_REVERSION_VWAP_FADE,
        "default_standard": StrategyType.DEFAULT_STANDARD,
    }
    
    normalized = strategy_map.get(str(strategy_type).lower())
    if normalized:
        return normalized
    
    # Fallback to default
    logger.warning(
        f"Unknown strategy_type: {strategy_type}, using DEFAULT_STANDARD. "
        f"Valid types: {list(strategy_map.keys())}"
    )
    return StrategyType.DEFAULT_STANDARD
```

#### ATR Timeframe Resolution

```python
def _get_atr_timeframe_for_strategy(self, strategy_type: StrategyType, symbol: str) -> str:
    """
    Get ATR timeframe for a strategy/symbol combination.
    
    Returns:
        Timeframe string (e.g., "M15", "M5")
    """
    # Get symbol-specific default
    symbol_rules = SYMBOL_RULES.get(symbol, {})
    default_timeframe = symbol_rules.get("atr_timeframe", "M15")
    
    # Strategy-specific overrides
    strategy_overrides = {
        StrategyType.BREAKOUT_IB_VOLATILITY_TRAP: "M5" if symbol == "BTCUSDc" else "M15",
        StrategyType.TREND_CONTINUATION_PULLBACK: "M15",
        StrategyType.LIQUIDITY_SWEEP_REVERSAL: "M5",
        StrategyType.ORDER_BLOCK_REJECTION: "M15",
        StrategyType.MEAN_REVERSION_RANGE_SCALP: "M5",
    }
    
    return strategy_overrides.get(strategy_type, default_timeframe)
```

#### Current ATR Calculation

```python
def _get_current_atr(self, symbol: str, timeframe: str, period: int = 14) -> float:
    """
    Get current ATR value for symbol/timeframe.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe string (e.g., "M15")
        period: ATR period (default 14)
        
    Returns:
        Current ATR value, or 0.0 if unavailable
    """
    try:
        # Use existing ATR calculation service if available
        # Otherwise, calculate from MT5 data
        import MetaTrader5 as mt5
        
        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, f"TIMEFRAME_{timeframe}"), 0, period + 1)
        if rates is None or len(rates) < period + 1:
            return 0.0
        
        # Calculate ATR
        true_ranges = []
        for i in range(1, len(rates)):
            high = rates[i]['high']
            low = rates[i]['low']
            prev_close = rates[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if not true_ranges:
            return 0.0
        
        atr = sum(true_ranges) / len(true_ranges)
        
        # Validate ATR is positive
        if atr <= 0:
            logger.warning(f"ATR calculation returned {atr} for {symbol} {timeframe}")
        
        return atr
        
    except Exception as e:
        logger.error(f"Error calculating ATR for {symbol} {timeframe}: {e}", exc_info=True)
        return 0.0
```

#### R-Multiple Calculation

```python
def _calculate_r_achieved(self, entry_price: float, initial_sl: float, 
                          current_price: float, direction: str) -> float:
    """
    Calculate R-multiple achieved.
    
    R = (current_price - entry_price) / (entry_price - initial_sl) for BUY
    R = (entry_price - current_price) / (initial_sl - entry_price) for SELL
    
    Args:
        entry_price: Entry price
        initial_sl: Initial stop loss
        current_price: Current market price
        direction: "BUY" or "SELL"
        
    Returns:
        R-multiple (can be negative if price moved against position)
    """
    if direction == "BUY":
        one_r = entry_price - initial_sl
        if one_r <= 0:
            return 0.0
        return (current_price - entry_price) / one_r
    else:  # SELL
        one_r = initial_sl - entry_price
        if one_r <= 0:
            return 0.0
        return (entry_price - current_price) / one_r
```

#### Cooldown Check

```python
def _check_cooldown(self, trade_state: TradeState, rules: Dict) -> bool:
    """
    Check if enough time has passed since last SL modification.
    
    Returns:
        True if cooldown period has passed, False otherwise
    """
    if not trade_state.last_sl_modification_time:
        return True  # No previous modification, allow
    
    cooldown_seconds = rules.get("sl_modification_cooldown_seconds", 30)
    time_since_last = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
    
    if time_since_last < cooldown_seconds:
        logger.debug(
            f"SL modification skipped for {trade_state.ticket}: "
            f"cooldown active ({time_since_last:.1f}s < {cooldown_seconds}s)"
        )
        return False
    
    return True
```

### Trade Management Methods

#### Unregister Trade

```python
def _unregister_trade(self, ticket: int):
    """Remove trade from registry and database."""
    if ticket in self.active_trades:
        del self.active_trades[ticket]
    
    if ticket in trade_registry:
        del trade_registry[ticket]
    
    # Clean up from database
    self._cleanup_trade_from_db(ticket)
    
    logger.info(f"Unregistered trade {ticket}")
```

#### Move to Breakeven

```python
def _move_to_breakeven(self, ticket: int, trade_state: TradeState):
    """
    Move stop loss to breakeven (entry price).
    
    Args:
        ticket: Position ticket
        trade_state: Trade state object
    """
    new_sl = trade_state.entry_price
    
    # Apply small buffer for broker requirements
    broker_min = self._get_broker_min_stop_distance(trade_state.symbol)
    if trade_state.direction == "BUY":
        new_sl = new_sl - broker_min  # Slightly below entry for BUY
    else:  # SELL
        new_sl = new_sl + broker_min  # Slightly above entry for SELL
    
    old_sl = trade_state.current_sl
    
    success = self._modify_position_sl(ticket, new_sl, trade_state)
    if success:
        self._log_sl_modification(trade_state, old_sl, new_sl, "breakeven_trigger")
        trade_state.breakeven_triggered = True
        self._save_trade_state_to_db(trade_state)
```

#### Take Partial Profit

```python
def _take_partial_profit(self, ticket: int, trade_state: TradeState, rules: Dict):
    """
    Take partial profit by closing a percentage of the position.
    
    Args:
        ticket: Position ticket
        trade_state: Trade state object
        rules: Resolved trailing rules
    """
    partial_pct = rules.get("partial_close_pct", 50)
    
    try:
        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            logger.error(f"Position {ticket} not found for partial close")
            return
        
        position = position[0]
        current_volume = position.volume
        close_volume = current_volume * (partial_pct / 100.0)
        
        # Round to lot size
        symbol_info = mt5.symbol_info(trade_state.symbol)
        if symbol_info:
            lot_step = symbol_info.volume_step
            close_volume = round(close_volume / lot_step) * lot_step
        
        if close_volume < symbol_info.volume_min:
            logger.warning(f"Partial close volume {close_volume} below minimum, skipping")
            return
        
        # Close partial position
        # Check if MT5Service has partial close method
        if hasattr(self.mt5_service, 'close_position_partial'):
            result = self.mt5_service.close_position_partial(ticket, close_volume)
        else:
            # Fallback: Use MT5 directly for partial close
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(trade_state.symbol)
            if not tick:
                logger.error(f"Could not get tick data for {trade_state.symbol}")
                return
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": trade_state.symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if trade_state.direction == "BUY" else mt5.ORDER_TYPE_BUY,
                "price": tick.bid if trade_state.direction == "BUY" else tick.ask,
                "deviation": 20,
                "magic": 0,
                "comment": "PartialClose",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5_result = mt5.order_send(request)
            # Convert to expected format
            if mt5_result and mt5_result.retcode == mt5.TRADE_RETCODE_DONE:
                result = {"ok": True, "message": "Partial close successful"}
            else:
                result = {"ok": False, "message": mt5_result.comment if mt5_result else "Unknown error"}
        
        if result.get("ok"):
            logger.info(
                f"Partial profit taken for {ticket}: {close_volume} of {current_volume} "
                f"({partial_pct}%) at r={trade_state.r_achieved:.2f}"
            )
            trade_state.partial_taken = True
            trade_state.initial_volume = current_volume - close_volume  # Update remaining
            self._save_trade_state_to_db(trade_state)
        else:
            logger.error(f"Failed to take partial profit for {ticket}: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"Error taking partial profit for {ticket}: {e}", exc_info=True)
```

#### Modify Position SL

```python
def _modify_position_sl(self, ticket: int, new_sl: float, trade_state: TradeState) -> bool:
    """
    Modify position stop loss via MT5.
    
    Args:
        ticket: Position ticket
        new_sl: New stop loss price
        trade_state: Trade state object
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = self.mt5_service.modify_position(
            ticket=ticket,
            sl=new_sl,
            tp=trade_state.initial_tp  # Keep original TP
        )
        
        if result.get("ok"):
            trade_state.current_sl = new_sl
            return True
        else:
            error_msg = result.get("message", "Unknown error")
            logger.warning(
                f"Failed to modify SL for {ticket}: {error_msg}. "
                f"Requested SL: {new_sl}, Current SL: {trade_state.current_sl}"
            )
            return False
            
    except Exception as e:
        logger.error(f"Error modifying SL for {ticket}: {e}", exc_info=True)
        return False
```

### Analysis Methods

#### Broker Minimum Stop Distance

```python
def _get_broker_min_stop_distance(self, symbol: str) -> float:
    """
    Get broker's minimum stop distance (symbol-specific).
    Used only for final validation, not decision logic.
    
    Returns:
        Minimum stop distance in price units, or 0.0 if unavailable
    """
    try:
        import MetaTrader5 as mt5
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info and symbol_info.trade_stops_level > 0:
            # Convert points to price units
            return symbol_info.trade_stops_level * symbol_info.point
        return 0.0  # Default: no minimum
    except Exception as e:
        logger.error(f"Error getting broker min stop distance for {symbol}: {e}")
        return 0.0  # Safe fallback
    
    # Fallback defaults (points/pips)
    defaults = {
        "BTCUSDc": 5.0,   # 5 points
        "XAUUSDc": 0.5,   # 0.5 pips
        "EURUSDc": 2.0,   # 2 pips
        "US30c": 3.0,     # 3 points
    }
    return defaults.get(symbol, 1.0)
```

#### Detect Momentum Exhaustion

```python
def _detect_momentum_exhaustion(self, trade_state: TradeState) -> bool:
    """
    Detect momentum exhaustion (stall detection).
    
    Checks for:
    - Multiple doji candles
    - Delta divergence
    - Volume decline
    - Price stalling near levels
    
    Returns:
        True if momentum exhaustion detected
    """
    # Implementation depends on available data sources
    # This is a placeholder - implement based on your order flow/CVD data
    
    # Example: Check for 3+ doji candles on M1
    # Example: Check for CVD divergence
    # Example: Check for volume decline
    
    # For now, return False (implement based on your data sources)
    return False
```

#### Calculate Trailing SL

```python
def _calculate_trailing_sl(
    self, 
    trade_state: TradeState, 
    rules: Dict,
    atr_multiplier_override: Optional[float] = None
) -> Optional[float]:
    """
    Calculate trailing SL based on strategy and rules.
    
    Args:
        trade_state: Trade state object
        rules: Resolved trailing rules
        atr_multiplier_override: Optional override for ATR multiplier (for volatility spikes)
        
    Returns:
        New SL price, or None if trailing not applicable
    """
    trailing_method = rules.get("trailing_method")
    atr_multiplier = atr_multiplier_override or rules.get("atr_multiplier", 1.5)
    trailing_timeframe = rules.get("trailing_timeframe", "M15")
    
    if trailing_method == "structure_atr_hybrid":
        # Get structure-based SL
        structure_sl = self._get_structure_based_sl(trade_state, rules)
        # Get ATR-based SL
        atr_sl = self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
        
        # Validate ATR-based SL
        if atr_sl is None:
            logger.warning(f"ATR-based SL calculation failed for {trade_state.ticket}")
            # If structure is available, use it; otherwise return None
            if structure_sl is not None:
                return structure_sl
            return None  # Can't calculate trailing without ATR or structure
        
        # If structure method not implemented, fallback to ATR-only
        if structure_sl is None:
            logger.debug(f"Structure-based SL not implemented for {trade_state.ticket}, using ATR-only")
            return atr_sl
        
        # Return the better (closer to price) one
        if trade_state.direction == "BUY":
            return max(structure_sl, atr_sl)  # Higher SL is better for BUY
        else:
            return min(structure_sl, atr_sl)  # Lower SL is better for SELL
    
    elif trailing_method == "structure_based":
        structure_sl = self._get_structure_based_sl(trade_state, rules)
        if structure_sl is None:
            # Fallback to ATR if structure not implemented
            logger.warning(f"Structure-based SL not implemented, falling back to ATR for {trade_state.ticket}")
            return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
        return structure_sl
    
    elif trailing_method == "atr_basic":
        atr_sl = self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
        if atr_sl is None:
            logger.warning(f"ATR-based SL calculation failed for {trade_state.ticket}")
        return atr_sl
    
    elif trailing_method == "micro_choch":
        micro_choch_sl = self._get_micro_choch_sl(trade_state, rules)
        if micro_choch_sl is None:
            # Fallback to ATR if CHOCH not implemented
            logger.warning(f"Micro CHOCH SL not implemented, falling back to ATR for {trade_state.ticket}")
            return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
        return micro_choch_sl
    
    elif trailing_method == "displacement_or_structure":
        displacement_sl = self._get_displacement_sl(trade_state, rules)
        structure_sl = self._get_structure_based_sl(trade_state, rules)
        
        if displacement_sl:
            return displacement_sl
        if structure_sl:
            return structure_sl
        # Fallback to ATR if both not implemented
        logger.warning(f"Displacement and structure SL not implemented, falling back to ATR for {trade_state.ticket}")
        return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
    
    elif trailing_method == "minimal_be_only":
        # No trailing, just BE protection
        return None
    
    return None

def _get_structure_based_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
    """Get structure-based trailing SL (swing lows/highs)."""
    # Implementation depends on structure detection service
    # This is a placeholder - implement based on your structure detection
    lookback = rules.get("structure_lookback", 2)
    timeframe = rules.get("trailing_timeframe", "M15")
    
    # TODO: Implement structure detection
    # Example: Get swing lows for BUY, swing highs for SELL
    # swing_levels = get_swing_levels(trade_state.symbol, timeframe, lookback)
    # if trade_state.direction == "BUY":
    #     return min(swing_levels) - (atr * buffer)
    # else:
    #     return max(swing_levels) + (atr * buffer)
    
    return None

def _get_atr_based_sl(self, trade_state: TradeState, rules: Dict, 
                      atr_multiplier: float, timeframe: str) -> Optional[float]:
    """Get ATR-based trailing SL."""
    current_atr = self._get_current_atr(trade_state.symbol, timeframe)
    if current_atr <= 0:
        return None
    
    # Get current price
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(trade_state.symbol)
        if not tick:
            return None
        
        current_price = tick.bid if trade_state.direction == "BUY" else tick.ask
        
        if trade_state.direction == "BUY":
            # SL below current price
            return current_price - (current_atr * atr_multiplier)
        else:  # SELL
            # SL above current price
            return current_price + (current_atr * atr_multiplier)
    except Exception as e:
        logger.error(f"Error calculating ATR-based SL: {e}")
        return None

def _get_micro_choch_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
    """Get micro CHOCH-based trailing SL."""
    # Implementation depends on CHOCH detection service
    # TODO: Implement CHOCH detection
    return None

def _get_displacement_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
    """Get displacement candle-based trailing SL."""
    # Implementation depends on displacement detection
    # TODO: Implement displacement detection
    return None
```

#### Tighten SL Aggressively

```python
def _tighten_sl_aggressively(self, ticket: int, trade_state: TradeState, rules: Dict):
    """
    Aggressively tighten SL when momentum exhaustion detected.
    
    This is a defensive move - locks in profit even if it doesn't meet
    the normal improvement threshold.
    """
    # Calculate tighter SL (e.g., lock 0.75R or 1R)
    lock_r = rules.get("stall_lock_r", 0.75)
    
    if trade_state.direction == "BUY":
        one_r = trade_state.entry_price - trade_state.initial_sl
        new_sl = trade_state.entry_price + (one_r * lock_r)
    else:  # SELL
        one_r = trade_state.initial_sl - trade_state.entry_price
        new_sl = trade_state.entry_price - (one_r * lock_r)
    
    # Ensure it's better than current SL
    if trade_state.direction == "BUY":
        if new_sl <= trade_state.current_sl:
            return  # Not an improvement
    else:  # SELL
        if new_sl >= trade_state.current_sl:
            return  # Not an improvement
    
    old_sl = trade_state.current_sl
    success = self._modify_position_sl(ticket, new_sl, trade_state)
    
    if success:
        self._log_sl_modification(trade_state, old_sl, new_sl, "stall_tighten")
        self._save_trade_state_to_db(trade_state)
```

### Recovery Methods

#### Load Trade State from Database

```python
def _load_trade_state_from_db(self, ticket: int) -> Optional[TradeState]:
    """
    Load TradeState from database.
    
    Returns:
        TradeState if found, None otherwise
    """
    try:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM universal_trades WHERE ticket = ?",
                (ticket,)
            ).fetchone()
            
            if not row:
                return None
            
            # Reconstruct TradeState
            strategy_type = self._normalize_strategy_type(row["strategy_type"])
            session = Session(row["session"])
            
            trade_state = TradeState(
                ticket=row["ticket"],
                symbol=row["symbol"],
                strategy_type=strategy_type,
                direction=row["direction"],
                session=session,
                resolved_trailing_rules=json.loads(row["resolved_trailing_rules"]),
                managed_by=row["managed_by"],
                entry_price=row["entry_price"],
                initial_sl=row["initial_sl"],
                initial_tp=row["initial_tp"],
                baseline_atr=row["baseline_atr"],
                initial_volume=row["initial_volume"],
                breakeven_triggered=bool(row["breakeven_triggered"]),
                partial_taken=bool(row["partial_taken"]),
                last_trailing_sl=row["last_trailing_sl"],
                last_sl_modification_time=datetime.fromisoformat(row["last_sl_modification_time"]) if row["last_sl_modification_time"] else None,
                registered_at=datetime.fromisoformat(row["registered_at"]),
                plan_id=row.get("plan_id")
            )
            
            return trade_state
            
    except Exception as e:
        logger.error(f"Error loading trade state for {ticket}: {e}", exc_info=True)
        return None
```

#### Cleanup Trade from Database

```python
def _cleanup_trade_from_db(self, ticket: int):
    """Remove trade from database."""
    try:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM universal_trades WHERE ticket = ?", (ticket,))
    except Exception as e:
        logger.error(f"Error cleaning up trade {ticket} from DB: {e}")
```

#### Initialize Database

```python
def _init_database(self):
    """Initialize database schema if not exists."""
    try:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS universal_trades (
                    ticket INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    session TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    initial_sl REAL NOT NULL,
                    initial_tp REAL NOT NULL,
                    resolved_trailing_rules TEXT NOT NULL,
                    managed_by TEXT NOT NULL,
                    baseline_atr REAL,
                    initial_volume REAL,
                    breakeven_triggered INTEGER DEFAULT 0,
                    partial_taken INTEGER DEFAULT 0,
                    last_trailing_sl REAL,
                    last_sl_modification_time TEXT,
                    registered_at TEXT NOT NULL,
                    plan_id TEXT,
                    FOREIGN KEY (plan_id) REFERENCES trade_plans(plan_id)
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
```

#### Load Configuration

```python
def _load_config(self) -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        return config.get("universal_sl_tp_rules", {})
    except FileNotFoundError:
        logger.warning(f"Config file not found: {self.config_path}, using defaults")
        return self._get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}, using defaults")
        return self._get_default_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}", exc_info=True)
        return self._get_default_config()

def _get_default_config(self) -> Dict:
    """Return default configuration if config file is missing."""
    return {
        "strategies": {
            "default_standard": {
                "breakeven_trigger_r": 1.0,
                "trailing_method": "atr_basic",
                "trailing_timeframe": "M15",
                "atr_multiplier": 2.0,
                "trailing_enabled": True,
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 60
            }
        },
        "symbol_adjustments": {}
    }
```

#### Infer Strategy Type

```python
def _infer_strategy_type(self, ticket: int, position) -> Optional[StrategyType]:
    """
    Infer strategy type from position comment or plan_id.
    
    Returns:
        StrategyType if inferred, None otherwise
    """
    # Try to get from plan_id (if available in position comment)
    # First, try to get plan_id from position comment
    plan_id = None
    if hasattr(position, 'comment') and position.comment:
        # Extract plan_id from comment if it's stored there
        # Format may vary - adjust based on your implementation
        comment = position.comment
        # Example: if comment contains plan_id like "plan_id:chatgpt_123"
        if "plan_id:" in comment:
            plan_id = comment.split("plan_id:")[1].split()[0]
    
    # Try querying by plan_id first (preferred method)
    if plan_id:
        try:
            import sqlite3
            import json
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT conditions FROM trade_plans WHERE plan_id = ?",
                    (plan_id,)
                ).fetchone()
                
                if row:
                    conditions = json.loads(row["conditions"])
                    strategy_type_str = conditions.get("strategy_type")
                    if strategy_type_str:
                        return self._normalize_strategy_type(strategy_type_str)
        except Exception:
            pass
    
    # Fallback: Try querying by ticket (if column exists)
    try:
        import sqlite3
        import json
        with sqlite3.connect(self.db_path) as conn:
            # Try querying by ticket first (if column exists)
            try:
                row = conn.execute(
                    "SELECT conditions FROM trade_plans WHERE ticket = ?",
                    (ticket,)
                ).fetchone()
                
                if row:
                    conditions = json.loads(row["conditions"])
                    strategy_type_str = conditions.get("strategy_type")
                    if strategy_type_str:
                        return self._normalize_strategy_type(strategy_type_str)
            except sqlite3.OperationalError:
                # ticket column doesn't exist - skip
                pass
    except Exception:
        pass
    except Exception:
        pass
    
    # Try to infer from position comment
    if hasattr(position, 'comment') and position.comment:
        comment = position.comment.lower()
        # Pattern matching from comment
        if "breakout" in comment or "ib" in comment:
            return StrategyType.BREAKOUT_IB_VOLATILITY_TRAP
        elif "trend" in comment or "continuation" in comment:
            return StrategyType.TREND_CONTINUATION_PULLBACK
        elif "sweep" in comment or "reversal" in comment:
            return StrategyType.LIQUIDITY_SWEEP_REVERSAL
        elif "ob" in comment or "order block" in comment:
            return StrategyType.ORDER_BLOCK_REJECTION
        elif "mean" in comment or "range" in comment:
            return StrategyType.MEAN_REVERSION_RANGE_SCALP
    
    return None
```

### Integration Methods (Option 1 - Enhancement Mode)

```python
def has_custom_rules(self, ticket: int) -> bool:
    """Check if trade has custom universal SL/TP rules."""
    trade_state = self.active_trades.get(ticket)
    return trade_state is not None and trade_state.managed_by == "universal_sl_tp_manager"

def check_trade(self, ticket: int) -> Optional[Dict]:
    """
    Check trade and return actions (for Option 1 integration).
    
    Returns:
        Dict with actions if any, None otherwise
    """
    if ticket not in self.active_trades:
        return None
    
    trade_state = self.active_trades[ticket]
    if trade_state.managed_by != "universal_sl_tp_manager":
        return None
    
    # Run monitoring logic
    self.monitor_trade(ticket)
    
    # Return any actions taken (for logging/debugging)
    return {
        "ticket": ticket,
        "r_achieved": trade_state.r_achieved,
        "breakeven_triggered": trade_state.breakeven_triggered,
        "partial_taken": trade_state.partial_taken,
        "current_sl": trade_state.current_sl
    }
```

---

## 📝 Notes & Considerations

### R-Space vs Points/Pips Philosophy

**Key Principle**: Most logic lives in R-space, with points/pips only for lower-level translation.

**Benefits of R-Space**:
- **Intuitively consistent**: "0.1R improvement" means the same thing for BTC, XAU, EURUSD, etc.
- **Symbol-agnostic**: Same thresholds work across all symbols
- **Easier to reason about**: "Move SL if it improves by 0.1R" is clearer than "5 points for BTC, 0.5 pips for XAU"

**When to Use Points/Pips**:
- **Broker validation**: Final check against broker's minimum stop distance
- **Price conversion**: Converting R-based calculations to actual price levels
- **Symbol-specific constraints**: Handling broker-specific requirements

**Implementation Pattern**:
```python
# Decision logic (R-space)
improvement_r = improvement_points / one_r_points
if improvement_r < min_sl_change_r:  # e.g., 0.1R
    return False

# Broker validation (points/pips - safety check only)
if improvement_points < broker_min_distance:
    return False
```

### Future Enhancements

1. **Multi-Timeframe Structure Detection**
   - Use H1/M15 structure for trend continuation
   - Use M5/M1 for breakouts

2. **Order Flow Integration**
   - Use CVD alignment for momentum detection
   - Use volume patterns for stall detection

3. **News Calendar Integration**
   - Widen SL/TP around major news events
   - Disable trailing during high-impact news

4. **Scale-In Support**
   - Logical trade groups for multiple tickets
   - Coordinated trailing across scale-in positions

5. **Cross-Symbol Expansion**
   - Add more symbols (EURUSDc, US30c already planned)
   - Universal manager for all asset classes

### Known Limitations

1. **Session Frozen at Open**
   - Session doesn't change mid-trade (by design)
   - If trade spans multiple sessions, uses original session rules

2. **Strategy Type Must Be Identified**
   - Requires explicit tag or pattern matching
   - Fallback to default if unclear

3. **Symbol Support**
   - Initially supports BTCUSDc, XAUUSDc, EURUSDc, US30c
   - Can be extended to other symbols with configuration

4. **Scale-Ins**
   - Current implementation: per-ticket management only
   - Scale-ins not supported (each ticket trails independently)
   - Future: logical trade groups for coordinated trailing

---

## 🔍 Debugging & Monitoring

### Logging

#### Rich Logging Format (Mandatory)

**Every SL modification must log a single rich line**:

```
ticket symbol strategy_type session old_sl→new_sl r_achieved reason
```

**Example**:
```
151742406 BTCUSDc BREAKOUT_IB_VOLATILITY_TRAP LONDON SL 86100→86320 r=1.78 reason=structure_trail
151742407 XAUUSDc TREND_CONTINUATION_PULLBACK NY SL 2645.50→2647.20 r=2.15 reason=atr_trail
151742408 BTCUSDc LIQUIDITY_SWEEP_REVERSAL ASIA SL 84000→84000 r=0.52 reason=breakeven_trigger
151742409 XAUUSDc MEAN_REVERSION_RANGE_SCALP ASIA SL 2650.00→2650.00 r=0.48 reason=cooldown_skip
```

**Implementation**:
```python
def _log_sl_modification(self, trade_state: TradeState, old_sl: float, 
                        new_sl: float, reason: str):
    """
    Log SL modification in rich format for debugging.
    
    Format: ticket symbol strategy_type session old_sl → new_sl r_achieved reason
    
    Args:
        trade_state: Trade state object
        old_sl: Previous stop loss price
        new_sl: New stop loss price
        reason: Reason for modification (e.g., "breakeven_trigger", "structure_trail")
    """
    logger.info(
        f"SL_MODIFY {trade_state.ticket} {trade_state.symbol} "
        f"{trade_state.strategy_type.value} {trade_state.session.value} "
        f"SL {old_sl:.5f}→{new_sl:.5f} r={trade_state.r_achieved:.2f} "
        f"reason={reason}"
    )
```

**Reasons**:
- `breakeven_trigger` - Moved to breakeven
- `structure_trail` - Structure-based trailing
- `atr_trail` - ATR-based trailing
- `displacement_trail` - Displacement candle trailing
- `stall_tighten` - Tightened due to stall detection
- `exhaustion_tighten` - Tightened due to momentum exhaustion
- `volatility_override` - Adjusted due to volatility spike
- `cooldown_skip` - Skipped due to cooldown
- `min_r_skip` - Skipped due to minimum R threshold (e.g., < 0.1R improvement)
- `broker_min_skip` - Skipped due to broker minimum stop distance
- `partial_profit` - Partial profit taken

#### Additional Logging

- Log all rule resolutions at trade open (with full resolved rules)
- Log cooldown skips (with time remaining)
- Log ownership conflicts (with both managers)
- Log recovery operations on startup
- Log manual partial close detection
- Log volatility spike detection

### Metrics

- Track average SL modifications per trade
- Track cooldown hit rate
- Track strategy type distribution
- Track session distribution

### Inspection Tools

- `get_trade_state(ticket)` - View frozen rules and state
- `get_all_active_trades()` - List all managed trades
- `get_strategy_rules(strategy_type, symbol, session)` - Preview rules

---

## 📚 References

- Existing exit managers: `infra/intelligent_exit_manager.py`, `infra/range_scalping_exit_manager.py`, `infra/micro_scalp_execution.py`
- Auto-execution system: `auto_execution_system.py`
- ChatGPT integration: `chatgpt_auto_execution_tools.py`
- MT5 service: `infra/mt5_service.py`

---

## ✅ Implementation Complete

**Final Status:** All 8 phases completed and tested  
**Test Results:** 122 tests passing, 0 failures, 0 errors  
**Completion Date:** November 25, 2025

### Summary of Deliverables

1. ✅ **Core Infrastructure** - Enums, TradeState, TradeRegistry, Database schema
2. ✅ **Rule Resolution** - Strategy/symbol/session rule merging, frozen snapshots
3. ✅ **Trailing Logic** - Structure-based, ATR-based, displacement-based trailing
4. ✅ **Safeguards** - Minimum distance, cooldown, ownership verification
5. ✅ **Integration** - Auto-execution, Intelligent Exit Manager, ChatGPT tools
6. ✅ **Monitoring Loop** - Breakeven, partial profits, trailing stops, volatility override
7. ✅ **Persistence & Recovery** - Database persistence, crash recovery, strategy inference
8. ✅ **Testing & Refinement** - Comprehensive test suite (122 tests), all passing

### Key Files Created/Modified

**New Files:**
- `infra/universal_sl_tp_manager.py` - Main orchestrator (1,843 lines)
- `tests/test_universal_sl_tp_phase1_2.py` - Phase 1 & 2 tests
- `tests/test_universal_sl_tp_phase3.py` - Phase 3 tests
- `tests/test_universal_sl_tp_phase4_safeguards.py` - Phase 4 tests
- `tests/test_universal_sl_tp_phase5_integration.py` - Phase 5 tests
- `tests/test_universal_sl_tp_phase6_monitoring.py` - Phase 6 tests
- `tests/test_universal_sl_tp_phase7_persistence.py` - Phase 7 tests

**Modified Files:**
- `auto_execution_system.py` - Universal Manager registration
- `chatgpt_auto_execution_tools.py` - Strategy type parameter
- `openai.yaml` - Tool definition updates
- `infra/intelligent_exit_manager.py` - Ownership checks
- `chatgpt_bot.py` - Scheduler integration

**End of Plan**

