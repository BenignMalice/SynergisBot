"""
Volatility Strategy Mapper

Maps volatility regimes to strategy recommendations, providing:
- Prioritized strategies for each regime
- Strategies to avoid
- Confidence adjustments
- Human-readable recommendations
"""
from typing import Dict, Any, Optional
from infra.volatility_regime_detector import VolatilityRegime

VOLATILITY_STRATEGY_MAP = {
    VolatilityRegime.PRE_BREAKOUT_TENSION: {
        "prioritize": [
            "breakout_ib_volatility_trap",
            "liquidity_sweep_reversal",
            "breaker_block"
        ],
        "avoid": [
            "mean_reversion_range_scalp",
            "trend_continuation_pullback"
        ],
        "confidence_adjustment": +10  # Boost confidence for breakout strategies
    },
    VolatilityRegime.POST_BREAKOUT_DECAY: {
        "prioritize": [
            "mean_reversion_range_scalp",
            "fvg_retracement",
            "order_block_rejection"
        ],
        "avoid": [
            "trend_continuation_pullback",
            "breakout_ib_volatility_trap",
            "market_structure_shift"
        ],
        "confidence_adjustment": -5  # Reduce confidence for continuation
    },
    VolatilityRegime.FRAGMENTED_CHOP: {
        "prioritize": [
            "micro_scalp",
            "mean_reversion_range_scalp"
        ],
        "avoid": [
            "trend_continuation_pullback",
            "breakout_ib_volatility_trap",
            "liquidity_sweep_reversal",
            "market_structure_shift",
            "fvg_retracement"
        ],
        "confidence_adjustment": -15  # Significant reduction
    },
    VolatilityRegime.SESSION_SWITCH_FLARE: {
        "prioritize": [],  # No strategies - WAIT
        "avoid": [
            "ALL"  # Block all strategies during flare
        ],
        "confidence_adjustment": -100  # Force WAIT
    }
}


def get_strategies_for_volatility(
    volatility_regime: VolatilityRegime,
    symbol: str,
    session: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get strategy recommendations for a volatility regime.
    
    Args:
        volatility_regime: Detected volatility regime
        symbol: Trading symbol (for symbol-specific adjustments)
        session: Current session (for session-specific adjustments)
    
    Returns:
        {
            "prioritize": List[str],  # Strategy names to prioritize
            "avoid": List[str],  # Strategy names to avoid
            "confidence_adjustment": int,  # Confidence score adjustment
            "recommendation": str,  # Human-readable recommendation
            "wait_reason": Optional[str]  # If WAIT recommended, reason
        }
    """
    # Get base mapping
    mapping = VOLATILITY_STRATEGY_MAP.get(volatility_regime, {})
    
    if not mapping:
        # Fallback for basic states (STABLE, TRANSITIONAL, VOLATILE)
        return {
            "prioritize": [],
            "avoid": [],
            "confidence_adjustment": 0,
            "recommendation": f"Standard strategies for {volatility_regime.value}",
            "wait_reason": None
        }
    
    # Build recommendation message
    prioritize = mapping.get("prioritize", [])
    avoid = mapping.get("avoid", [])
    
    if volatility_regime == VolatilityRegime.SESSION_SWITCH_FLARE:
        recommendation = "WAIT - Session transition volatility flare detected. Wait for stabilization."
        wait_reason = "SESSION_SWITCH_FLARE"
    elif prioritize:
        recommendation = f"Prioritize: {', '.join(prioritize)}"
        wait_reason = None
    else:
        recommendation = f"Standard strategies for {volatility_regime.value}"
        wait_reason = None
    
    return {
        "prioritize": prioritize,
        "avoid": avoid,
        "confidence_adjustment": mapping.get("confidence_adjustment", 0),
        "recommendation": recommendation,
        "wait_reason": wait_reason
    }

