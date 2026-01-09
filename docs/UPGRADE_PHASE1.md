# TelegramMoneyBot v6 – Phase 1 Upgrades
_Last updated: 2025-08-27 12:47:24_

## What changed
- **TP2 partial exit**: added configurable TP2 at `+2R` with partial close ratio, and **minimum remainder** guard so runners keep a tail.
- **Regime-aware ATR trailing**: per-regime ATR multiplier overrides (`TREND`, `RANGE`, `VOLATILE`) for more intelligent trailing.

## Files modified
- `infra/position_watcher.py`: new `tp2_done` and `base_volume` state, TP2 block, regime-based ATR override.
- `config/settings.py`: added `POS_TP2_R`, `POS_TP2_PART_CLOSE`, `POS_EXIT_MIN_REMAINDER`, `POS_TRAIL_ATR_MULT_BY_REGIME`.

## New/Updated Settings
```python
# Trigger TP2 at +2R, close 40%
POS_TP2_R = 2.0
POS_TP2_PART_CLOSE = 0.40

# Keep at least 10% of original position after partials
POS_EXIT_MIN_REMAINDER = 0.10

# Regime-specific ATR multipliers for trailing
POS_TRAIL_ATR_MULT_BY_REGIME = {"TREND": 2.0, "RANGE": 1.2, "VOLATILE": 1.6}
```
