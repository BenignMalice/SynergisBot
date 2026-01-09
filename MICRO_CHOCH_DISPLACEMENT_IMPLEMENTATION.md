# Micro CHOCH and Displacement SL Implementation

## Overview

Implemented the missing trailing stop loss features for the Universal Dynamic SL/TP Manager:
1. **Micro CHOCH SL** - Uses M1 microstructure analysis to detect Change of Character and anchor SL to swing points
2. **Displacement SL** - Detects displacement candles (strong moves after order blocks) and uses them for SL anchors

---

## Implementation Details

### 1. Micro CHOCH SL (`_get_micro_choch_sl`)

**Purpose**: Provides precise trailing stop loss based on M1 microstructure CHOCH detection.

**How It Works**:
1. Fetches M1 candles using `StreamerDataAccess` (with MT5 fallback)
2. Uses `M1MicrostructureAnalyzer.detect_choch_bos()` to detect CHOCH and identify swing points
3. For **BUY trades**: Uses most recent swing low as SL anchor, subtracts ATR buffer
4. For **SELL trades**: Uses most recent swing high as SL anchor, adds ATR buffer
5. Validates SL is in correct direction relative to current price

**Configuration**:
- `atr_buffer`: ATR multiplier for buffer below/above swing point (default: 0.5)
- Uses M1 timeframe for microstructure analysis
- Requires minimum 10 M1 candles for analysis

**Fallback**: Returns `None` if:
- Insufficient M1 candles (< 10)
- CHOCH detection fails
- ATR calculation fails
- No valid swing points found
- SL would be in wrong direction

**Usage**: Automatically used for strategies with `trailing_method: "micro_choch"` (e.g., `liquidity_sweep_reversal`)

---

### 2. Displacement SL (`_get_displacement_sl`)

**Purpose**: Provides trailing stop loss based on displacement candles (strong moves after order blocks).

**How It Works**:
1. Fetches candles for the strategy's trailing timeframe (M5 or M15)
2. Analyzes last 15 candles for displacement pattern
3. Validates displacement strength (requires ≥1.5× average range)
4. Identifies the displacement candle (first candle of the strong move)
5. For **BUY trades**: Uses low of displacement candle, subtracts ATR buffer
6. For **SELL trades**: Uses high of displacement candle, adds ATR buffer
7. Validates SL is in correct direction relative to current price

**Configuration**:
- `trailing_timeframe`: Timeframe for displacement detection (default: M5)
- `atr_buffer`: ATR multiplier for buffer (default: 0.3 for displacement)
- Requires minimum 20 candles for analysis
- Requires displacement strength ≥ 1.5× average range

**Fallback**: Returns `None` if:
- Insufficient candles (< 20)
- Displacement not strong enough (< 1.5× average range)
- No displacement candle found
- ATR calculation fails
- SL would be in wrong direction

**Usage**: Automatically used for strategies with `trailing_method: "displacement_or_structure"` (e.g., `order_block_rejection`)

---

## Helper Method

### `_calculate_atr_from_candles`

**Purpose**: Calculates ATR directly from candle data when streamer/MT5 ATR is unavailable.

**How It Works**:
1. Extracts high, low, close from candle list
2. Calculates True Range (TR) for each candle
3. Averages last N periods (default: 14) to get ATR

**Fallback**: Used when `_get_current_atr()` fails or returns invalid value.

---

## Integration

Both methods are automatically called by `_calculate_trailing_sl()` when:
- Strategy has `trailing_method: "micro_choch"` or `"displacement_or_structure"`
- Breakeven has been triggered
- Trailing is enabled

**Fallback Chain**:
1. Try primary method (CHOCH or displacement)
2. If fails, try structure-based SL (if `displacement_or_structure`)
3. If fails, fallback to ATR-based SL

---

## Error Handling

- All methods use try/except blocks to prevent crashes
- Errors are logged with context (ticket, symbol, error details)
- Returns `None` on failure (triggers fallback to ATR-based SL)
- Debug logging for troubleshooting

---

## Testing Recommendations

1. **Micro CHOCH SL**:
   - Test with BUY trade during bullish CHOCH
   - Test with SELL trade during bearish CHOCH
   - Verify SL anchors to swing points correctly
   - Test fallback when M1 data unavailable

2. **Displacement SL**:
   - Test with BUY trade after bullish displacement
   - Test with SELL trade after bearish displacement
   - Verify displacement strength validation (1.5× threshold)
   - Test fallback when displacement not detected

3. **Integration**:
   - Verify both methods work with `liquidity_sweep_reversal` strategy
   - Verify both methods work with `order_block_rejection` strategy
   - Verify fallback to ATR when methods return `None`

---

## Configuration Updates

No configuration changes required. Both methods use existing config parameters:
- `atr_buffer`: Already in config (default: 0.5 for CHOCH, 0.3 for displacement)
- `trailing_timeframe`: Already in config (M1 for CHOCH, M5/M15 for displacement)

---

## Files Modified

- `infra/universal_sl_tp_manager.py`:
  - Implemented `_get_micro_choch_sl()` method (replaced TODO)
  - Implemented `_get_displacement_sl()` method (replaced TODO)
  - Added `_calculate_atr_from_candles()` helper method
  - Added `List` to typing imports

---

## Status

✅ **COMPLETE** - Both features fully implemented and tested for syntax errors.

