# Advanced Exits — Gated Trailing Rules (Quick Ref)

Applies to Intelligent Exit Manager. Trailing is enabled only when structure and context support holding. Stops never move backwards.

## Core Sequence

- Enter profit → hold until continuation is confirmed.
- Move SL to breakeven around 0.2R (Advanced-adjusted by market state).
- Take partial at ~0.5R (skip if position volume < 0.02).
- Start ATR trailing only when gates pass (below), otherwise wait.
- If a structure break (CHOCH) appears against the position → tighten or exit (handled by Profit Protector).

## Trailing Gates (all must pass)

- Profit or partial: partial already taken OR `R ≥ 0.6`.
- Volatility regime: not a squeeze (`vol_trend.state` does not contain "squeeze").
- MTF alignment: `mtf_total ≥ 2` timeframes aligned.
- Stretch and mean reversion risk: `|rmag.ema200_atr| ≤ 2.0` AND `vwap.zone != 'outer'`.
- VP gravity: `vp.hvn_dist_atr ≥ 0.3` (avoid trailing near HVN magnet).

Trailing activates only when these gates pass; it pauses updates when they fail (no backward SL move is ever made).

## Baselines and Adjustments

- Breakeven floor: ~0.2R (Advanced may tighten/widen 20–40%).
- Partial: ~0.5R (Advanced may adjust 40–80%).
- ATR trailing distance: ~1.5 × ATR (widen under high VIX or stretch; can tighten modestly in quality trends after partial).
- VIX hybrid: one-time widening before breakeven when VIX exceeds threshold.

## Advanced Factors (examples)

- Tighten early: RMAG stretched `|ema200_atr| > 2.0`, VWAP zone `outer`, squeeze regimes, fake momentum.
- Widen/let it run: quality trend (EMA50/EMA200 slopes) with normal stretch and `mtf_total ≥ 2`.

## Live Refresh

- The manager reads a lightweight Advanced snapshot when you add the rule and refreshes gates each cycle if you provide an `advanced_provider` with either:
  - `get_advanced_features(symbol) -> { features: { M5|M15|H1: {...}, mtf_score, vp } }`, or
  - `get_multi(symbol) -> { M5|M15|H1: {...} }`.

If no provider is set, the snapshot captured at rule creation is used.

## Tuning Knobs (symbol-level defaults)

- `breakeven_profit_pct` (default ~20)
- `partial_profit_pct` (default ~50)
- `partial_close_pct` (default ~50)
- `vix_threshold` (e.g., 18–22)
- `trailing_enabled` (bool)
- Optional per-symbol adjustments in `app/config/strategy_map.json` (recommended)

## Notes

- CHOCH/BOS: BOS confirmation + MTF alignment favors trailing; CHOCH against direction routes to tightening/exit (via Profit Protector).
- Sessions: consider wider buffers in Asia, slightly tighter in London/NY overlap (can be added as a future session modifier).

