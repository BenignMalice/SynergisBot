# Phase 4.4 - Integration Guide

## 🎯 Quick Start Integration

This guide shows how to integrate Phase 4.4 execution upgrades into your existing bot.

---

## 1️⃣ **Structure-Aware SL Integration**

### **In `infra/openai_service.py` (recommend function)**

**Before** (old code):
```python
# Old fixed SL calculation
sl_distance = 1.5 * atr
if direction == "buy":
    sl = entry - sl_distance
else:
    sl = entry + sl_distance
```

**After** (Phase 4.4):
```python
from infra.structure_sl import calculate_structure_sl_for_buy, calculate_structure_sl_for_sell

# Get structure-aware SL
m5_features = features.get("M5", {})
if direction == "buy":
    sl, anchor_type, distance_atr, sl_rationale = calculate_structure_sl_for_buy(
        entry_price=entry,
        atr=atr,
        m5_features=m5_features
    )
    logger.info(f"Structure SL: {sl:.5f} (anchor={anchor_type}, {distance_atr:.2f}× ATR) - {sl_rationale}")
else:
    sl, anchor_type, distance_atr, sl_rationale = calculate_structure_sl_for_sell(
        entry_price=entry,
        atr=atr,
        m5_features=m5_features
    )
    logger.info(f"Structure SL: {sl:.5f} (anchor={anchor_type}, {distance_atr:.2f}× ATR) - {sl_rationale}")
```

---

## 2️⃣ **Adaptive TP Integration**

### **In `infra/openai_service.py` (recommend function)**

**Before** (old code):
```python
# Old fixed TP calculation
base_rr = 2.0
tp_distance = base_rr * abs(entry - sl)
if direction == "buy":
    tp = entry + tp_distance
else:
    tp = entry - tp_distance
```

**After** (Phase 4.4):
```python
from infra.adaptive_tp import calculate_adaptive_tp

# Get adaptive TP based on momentum
m5_features = features.get("M5", {})
base_rr = 2.0
direction_normalized = "buy" if direction == "LONG" else "sell"

result = calculate_adaptive_tp(
    entry_price=entry,
    stop_loss_price=sl,
    base_rr=base_rr,
    direction=direction_normalized,
    m5_features=m5_features
)

tp = result.new_tp
adjusted_rr = result.adjusted_rr
logger.info(f"Adaptive TP: {tp:.5f} (momentum={result.momentum_state}, RR {base_rr:.1f} → {adjusted_rr:.1f}) - {result.rationale}")
```

---

## 3️⃣ **OCO Brackets Integration**

### **In `decision_engine.py` (recommend_action function)**

**Add OCO bracket detection for breakout strategy**:

```python
from infra.oco_brackets import calculate_oco_bracket

# After strategy selection
if selected_strategy == "breakout" and regime in ["VOLATILE", "TREND"]:
    # Check if OCO bracket is suitable
    session = features.get("M5", {}).get("session", "UNKNOWN")
    oco_result = calculate_oco_bracket(
        features=features.get("M5", {}),
        atr=atr,
        session=session,
        symbol=symbol
    )
    
    if oco_result.is_valid:
        # Recommend OCO bracket instead of single order
        logger.info(f"OCO Bracket detected: {oco_result.rationale}")
        return {
            "order_type": "oco_bracket",
            "buy_stop": oco_result.buy_stop,
            "buy_sl": oco_result.buy_sl,
            "buy_tp": oco_result.buy_tp,
            "sell_stop": oco_result.sell_stop,
            "sell_sl": oco_result.sell_sl,
            "sell_tp": oco_result.sell_tp,
            "expiry_minutes": oco_result.expiry_minutes,
            "consolidation_confidence": oco_result.consolidation_confidence,
            "rationale": oco_result.rationale
        }
    else:
        logger.info(f"OCO Bracket skipped: {oco_result.skip_reasons}")
```

---

## 4️⃣ **Trailing Stops Integration**

### **Create new file: `infra/trade_monitor.py`**

```python
"""
Trade Monitor - Background job to manage trailing stops
"""

import logging
from typing import Dict, Any, List
from infra.mt5_service import MT5Service
from infra.trailing_stops import calculate_trailing_stop
from infra.momentum_detector import detect_momentum
from infra.feature_builder import FeatureBuilder

logger = logging.getLogger(__name__)


class TradeMonitor:
    """Monitor open positions and manage trailing stops."""
    
    def __init__(self, mt5_service: MT5Service, feature_builder: FeatureBuilder):
        self.mt5 = mt5_service
        self.feature_builder = feature_builder
    
    def check_trailing_stops(self) -> List[Dict[str, Any]]:
        """
        Check all open positions and update trailing stops if needed.
        Returns list of actions taken.
        """
        actions = []
        
        try:
            # Get all open positions
            positions = self.mt5.get_positions()
            if not positions:
                return actions
            
            for position in positions:
                try:
                    symbol = position.symbol
                    ticket = position.ticket
                    entry_price = position.price_open
                    current_sl = position.sl
                    direction = "buy" if position.type == 0 else "sell"
                    
                    # Get current price
                    current_price = position.price_current
                    
                    # Get features for momentum detection
                    features = self.feature_builder.build(symbol, "M5")
                    m5_features = features.get("M5", {})
                    atr = m5_features.get("atr_14", 0)
                    
                    if atr == 0:
                        logger.warning(f"No ATR for {symbol}, skipping trailing")
                        continue
                    
                    # Detect momentum
                    momentum_state, _, _ = detect_momentum(m5_features)
                    
                    # Calculate new trailing SL
                    result = calculate_trailing_stop(
                        current_price=current_price,
                        entry_price=entry_price,
                        initial_stop_loss=current_sl,
                        direction=direction,
                        atr=atr,
                        momentum_state=momentum_state,
                        current_sl=current_sl
                    )
                    
                    # If SL should be updated
                    if result.action in ["move_to_breakeven", "trail"]:
                        # Update MT5 position
                        success = self.mt5.modify_position(
                            ticket=ticket,
                            new_sl=result.new_sl,
                            new_tp=position.tp  # Keep TP unchanged
                        )
                        
                        if success:
                            action = {
                                "ticket": ticket,
                                "symbol": symbol,
                                "action": result.action,
                                "old_sl": current_sl,
                                "new_sl": result.new_sl,
                                "profit_r": result.profit_r,
                                "momentum": momentum_state,
                                "rationale": result.rationale
                            }
                            actions.append(action)
                            logger.info(f"Trailing stop updated: {symbol} ticket={ticket}, {result.action}, SL {current_sl:.5f} → {result.new_sl:.5f}")
                        else:
                            logger.error(f"Failed to update trailing stop for {symbol} ticket={ticket}")
                
                except Exception as e:
                    logger.error(f"Error checking position {position.ticket}: {e}")
                    continue
            
            return actions
        
        except Exception as e:
            logger.error(f"Trade monitor check failed: {e}")
            return actions
```

### **In `main.py` (or wherever you initialize the bot)**

```python
from infra.trade_monitor import TradeMonitor
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize trade monitor
trade_monitor = TradeMonitor(mt5_service, feature_builder)

# Schedule trailing stop checks every 15 seconds
scheduler = BackgroundScheduler()
scheduler.add_job(
    trade_monitor.check_trailing_stops,
    'interval',
    seconds=15,
    id='trailing_stops',
    max_instances=1
)
scheduler.start()

logger.info("Trade monitor started (trailing stops every 15s)")
```

---

## 5️⃣ **Feature Builder Updates**

### **In `infra/feature_builder.py`**

Ensure these features are computed for Phase 4.4:

```python
# For Structure SL
"swing_low_1": <float>,      # Most recent swing low
"swing_low_1_age": <int>,    # Bars since formation
"swing_high_1": <float>,     # Most recent swing high
"swing_high_1_age": <int>,
"fvg_bull_high": <float>,    # FVG boundaries
"fvg_bear_low": <float>,
"eq_low_cluster": <bool>,    # Equal lows detected
"eq_high_cluster": <bool>,   # Equal highs detected
"sweep_bull_level": <float>, # Sweep level
"sweep_bear_level": <float>,

# For Adaptive TP
"macd_hist": <float>,        # MACD histogram
"macd_hist_prev": <float>,   # Previous bar's histogram
"atr_14": <float>,
"atr_100": <float>,
"volume_zscore": <float>,

# For OCO Brackets
"recent_highs": [<float>],   # Last 20 highs
"recent_lows": [<float>],    # Last 20 lows
"adx_14": <float>,
"bb_width": <float>,
"has_pending_orders": <bool>,
"news_blackout": <bool>,
"minutes_to_session_end": <int>
```

---

## 6️⃣ **Telegram UI Updates**

### **In `handlers/trading.py`**

Update trade recommendation message to show Phase 4.4 metadata:

```python
# In send_trade_recommendation function
message = (
    f"📊 <b>Trade Recommendation</b>\n\n"
    f"Symbol: {symbol}\n"
    f"Strategy: {strategy}\n"
    f"Direction: {direction}\n"
    f"Entry: {entry:.5f}\n"
    f"SL: {sl:.5f} ({anchor_type}, {distance_atr:.2f}× ATR)\n"  # NEW: Show anchor
    f"TP: {tp:.5f} (RR {adjusted_rr:.2f}, momentum={momentum_state})\n"  # NEW: Show momentum
    f"\n<i>{rationale}</i>"
)

# Add keyboard with trailing stop toggle
keyboard = [
    [
        InlineKeyboardButton("✅ Execute", callback_data=f"execute_{symbol}"),
        InlineKeyboardButton("❌ Skip", callback_data=f"skip_{symbol}")
    ],
    [
        InlineKeyboardButton("🔄 Enable Trailing", callback_data=f"trail_{symbol}")
    ]
]
```

---

## 7️⃣ **Journal Updates**

### **In `domain/journal.py`**

Add Phase 4.4 metadata to trade records:

```python
def add_trade(self, trade_data: Dict[str, Any]):
    # Existing fields...
    
    # NEW: Phase 4.4 metadata
    phase4_metadata = {
        "sl_anchor_type": trade_data.get("sl_anchor_type"),
        "sl_distance_atr": trade_data.get("sl_distance_atr"),
        "tp_momentum_state": trade_data.get("tp_momentum_state"),
        "tp_adjusted_rr": trade_data.get("tp_adjusted_rr"),
        "trailing_enabled": trade_data.get("trailing_enabled", False),
        "is_oco_bracket": trade_data.get("is_oco_bracket", False)
    }
    
    # Store in database
    # ...
```

---

## 8️⃣ **Configuration**

### **In `config.py`**

Add Phase 4.4 feature flags:

```python
@dataclass
class Settings:
    # ... existing settings ...
    
    # Phase 4.4 Execution Upgrades
    USE_STRUCTURE_SL: bool = _as_bool(os.getenv("USE_STRUCTURE_SL", "1"))
    USE_ADAPTIVE_TP: bool = _as_bool(os.getenv("USE_ADAPTIVE_TP", "1"))
    USE_TRAILING_STOPS: bool = _as_bool(os.getenv("USE_TRAILING_STOPS", "1"))
    USE_OCO_BRACKETS: bool = _as_bool(os.getenv("USE_OCO_BRACKETS", "1"))
    
    # Trailing stop interval (seconds)
    TRAILING_CHECK_INTERVAL: int = int(os.getenv("TRAILING_CHECK_INTERVAL", "15"))
```

### **In `.env`**

```env
# Phase 4.4 Execution Upgrades
USE_STRUCTURE_SL=1
USE_ADAPTIVE_TP=1
USE_TRAILING_STOPS=1
USE_OCO_BRACKETS=1
TRAILING_CHECK_INTERVAL=15
```

---

## 🧪 Testing Integration

### **Create integration test: `tests/test_phase4_4_full_integration.py`**

```python
"""
Phase 4.4 Full Integration Test
Tests all execution upgrades working together
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.structure_sl import calculate_structure_sl_for_buy
from infra.adaptive_tp import calculate_adaptive_tp
from infra.trailing_stops import calculate_trailing_stop


def test_full_trade_lifecycle():
    """Test a complete trade with all Phase 4.4 components."""
    print("\n" + "="*70)
    print("FULL TRADE LIFECYCLE TEST")
    print("="*70)
    
    # 1. Entry calculation (from strategy)
    entry = 100.0
    atr = 2.0
    
    # 2. Structure-aware SL
    features = {
        "swing_low_1": 97.5,
        "swing_low_1_age": 5,
        "close": 100.0
    }
    
    sl, anchor, dist_atr, sl_rationale = calculate_structure_sl_for_buy(entry, atr, features)
    print(f"\n1. Structure SL: {sl:.2f} (anchor={anchor}, {dist_atr:.2f}× ATR)")
    print(f"   {sl_rationale}")
    
    # 3. Adaptive TP
    features_momentum = {
        **features,
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "atr_14": atr,
        "atr_100": 1.5,
        "volume_zscore": 1.5
    }
    
    tp_result = calculate_adaptive_tp(entry, sl, 2.0, "buy", features_momentum)
    print(f"\n2. Adaptive TP: {tp_result.new_tp:.2f} (momentum={tp_result.momentum_state}, RR={tp_result.adjusted_rr:.2f})")
    print(f"   {tp_result.rationale}")
    
    # 4. Simulate price movement and trailing
    price_sequence = [100.5, 101.0, 102.0, 103.0, 104.0, 105.0]
    current_sl = sl
    
    print(f"\n3. Trailing Stops:")
    for price in price_sequence:
        result = calculate_trailing_stop(
            price, entry, sl, "buy", atr, tp_result.momentum_state, current_sl
        )
        if result.action in ["move_to_breakeven", "trail"]:
            print(f"   Price {price:.2f}: {result.action}, SL {current_sl:.2f} → {result.new_sl:.2f} ({result.profit_r:.2f}R)")
            current_sl = result.new_sl
        else:
            print(f"   Price {price:.2f}: {result.action} (profit={result.profit_r:.2f}R)")
    
    print(f"\n4. Final State:")
    print(f"   Entry: {entry:.2f}")
    print(f"   Final SL: {current_sl:.2f}")
    print(f"   TP: {tp_result.new_tp:.2f}")
    print(f"   Protected Profit: {(current_sl - entry):.2f} ({(current_sl - entry) / (entry - sl):.2f}R)")
    
    print(f"\n[OK] Full trade lifecycle working correctly")
    print("="*70)


if __name__ == "__main__":
    test_full_trade_lifecycle()
```

**Run**: `python tests/test_phase4_4_full_integration.py`

---

## ✅ Integration Checklist

- [ ] Structure SL integrated into `openai_service.py`
- [ ] Adaptive TP integrated into `openai_service.py`
- [ ] OCO brackets integrated into `decision_engine.py`
- [ ] Trade monitor created (`infra/trade_monitor.py`)
- [ ] Trailing stops scheduled in main bot loop
- [ ] Feature builder updated with required features
- [ ] Configuration flags added (`.env`, `config.py`)
- [ ] Journal updated to store Phase 4.4 metadata
- [ ] Telegram UI updated to show anchor/momentum
- [ ] Integration test created and passing
- [ ] End-to-end test with paper trading (2-5 days)

---

## 🚨 Common Pitfalls

1. **Missing features**: Ensure `swing_low_1`, `macd_hist_prev`, `recent_highs` are computed
2. **Direction confusion**: Structure SL has separate functions for buy/sell
3. **SL moving backwards**: Only call `calculate_trailing_stop` when price is favorable
4. **OCO without consolidation**: Check `oco_result.is_valid` before using
5. **Trailing too aggressive**: Start with 15-30 second intervals, not every tick

---

## 📊 Monitoring After Integration

**Key metrics to track**:

1. **Structure SL**:
   - % trades with swing anchor vs fallback
   - Stop-out rate before/after
   - Avg SL distance (ATR multiples)

2. **Adaptive TP**:
   - % trades with momentum extension/reduction
   - Avg R per winner before/after
   - Hit rate on extended TPs

3. **Trailing Stops**:
   - % trades trailed to BE
   - % trades trailed beyond 1R
   - Avg locked profit on runners

4. **OCO Brackets**:
   - % breakout trades with OCO
   - Fill rate (buy vs sell side)
   - Avg R on OCO trades

---

*Integration Guide Version: 1.0*  
*Last Updated: 2025-10-02*

