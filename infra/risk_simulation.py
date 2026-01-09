"""
Risk simulation module for pre-trade analysis.

This module defines a `simulate` function that estimates the
probabilities of hitting a stop-loss (SL) or take-profit (TP) level
given the current price distance to each and the average true range
(ATR).  It uses a simplified "gambler's ruin" approximation to
calculate probabilities and expected return in R units (risk
multiples).  While simplistic, this provides a quick sanity check
before committing to a trade.

Example:

    from infra.risk_simulation import simulate
    sim = simulate(entry=100.0, sl=99.0, tp=101.0, atr=0.2)
    print(sim)  # {'p_hit_sl': 0.4, 'p_hit_tp': 0.6, 'expected_r': 0.2}

The returned values are:

 - `p_hit_sl`: Probability of hitting the stop-loss first.
 - `p_hit_tp`: Probability of hitting the take-profit first.
 - `expected_r`: Expected return in R (risk units), computed as
   p_hit_tp - p_hit_sl.
"""

from __future__ import annotations

from typing import Dict


def simulate(entry: float, sl: float, tp: float, atr: float) -> Dict[str, float]:
    """Simulate probabilities of hitting SL or TP based on gambler's ruin logic."""
    # Distances to SL/TP in points
    dist_sl = abs(entry - sl)
    dist_tp = abs(tp - entry)
    if dist_sl <= 0 or dist_tp <= 0 or atr <= 0:
        return {'p_hit_sl': 0.0, 'p_hit_tp': 0.0, 'expected_r': 0.0}
    # Normalise distances by ATR (roughly number of ATRs to each level)
    n_sl = dist_sl / atr
    n_tp = dist_tp / atr
    # Probability of hitting TP first in unbiased random walk ~ n_sl/(n_sl+n_tp)
    p_tp = n_sl / (n_sl + n_tp)
    p_sl = 1.0 - p_tp
    # Expected R = p_tp - p_sl
    exp_r = p_tp - p_sl
    return {'p_hit_sl': p_sl, 'p_hit_tp': p_tp, 'expected_r': exp_r}