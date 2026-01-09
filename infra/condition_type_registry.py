"""
Condition Type Registry

Single source of truth for strategy types and their required/optional conditions.
Ensures consistency across strategy selection, auto-execution, and ChatGPT integration.
"""

from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


# Registry mapping strategy types to their conditions
CONDITION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "order_block_rejection": {
        "required": ["order_block"],
        "optional": ["price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "ob_strength",
        "description": "Order Block Rejection - Price rejects from institutional order block zone"
    },
    "fvg_retracement": {
        "required": ["fvg_bull", "fvg_bear"],  # At least one
        "optional": ["price_near", "timeframe", "fvg_fill_pct", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "fvg_strength",
        "description": "FVG Retracement - Price retraces to Fair Value Gap zone"
    },
    "breaker_block": {
        "required": ["breaker_block", "ob_broken"],
        "optional": ["price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "breaker_block_strength",
        "description": "Breaker Block - Order block that broke previous structure"
    },
    "mitigation_block": {
        "required": ["mitigation_block_bull", "mitigation_block_bear"],  # At least one
        "optional": ["structure_broken", "price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "mitigation_block_strength",
        "description": "Mitigation Block - Order block that mitigates previous structure"
    },
    "market_structure_shift": {
        "required": ["mss_bull", "mss_bear"],  # At least one
        "optional": ["pullback_to_mss", "price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "mss_strength",
        "description": "Market Structure Shift - Structure break with pullback confirmation"
    },
    "inducement_reversal": {
        "required": ["liquidity_grab_bull", "liquidity_grab_bear"],  # At least one
        "optional": ["rejection_detected", "price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "inducement_strength",
        "description": "Inducement + Reversal - Liquidity grab followed by reversal"
    },
    "premium_discount_array": {
        "required": ["price_in_discount", "price_in_premium"],  # At least one
        "optional": ["fib_level", "price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "fib_strength",  # ⚠️ TODO: Verify if this field exists
        "description": "Premium/Discount Array - Price at Fibonacci premium/discount zone"
    },
    "session_liquidity_run": {
        "required": ["session_liquidity_run"],
        "optional": ["asian_session_high", "asian_session_low", "london_session_active", "price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": "session_liquidity_strength",
        "description": "Session Liquidity Run - Price runs to session highs/lows"
    },
    "kill_zone": {
        "required": ["kill_zone_active"],
        "optional": ["price_near", "timeframe", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": None,  # Time-based, no confidence score
        "description": "Kill Zone - High-probability trading session (London/NY open)"
    },
    "breakout_ib_volatility_trap": {
        "required": ["bb_expansion", "timeframe"],
        "optional": ["price_above", "price_near", "min_confluence", "min_validation_score", "risk_filters"],
        "confidence_field": None,
        "description": "Inside Bar Volatility Trap - Breakout from compression pattern"
    }
}


def validate_conditions(strategy_type: str, conditions: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate conditions for a strategy type.
    
    Args:
        strategy_type: Strategy type string
        conditions: Conditions dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if strategy_type not in CONDITION_REGISTRY:
        return False, f"Unknown strategy type: {strategy_type}"
    
    registry_entry = CONDITION_REGISTRY[strategy_type]
    required = registry_entry.get("required", [])
    
    # Check required conditions
    missing = []
    for req in required:
        # Handle "at least one" requirements (list of alternatives)
        if isinstance(req, list):
            if not any(cond in conditions for cond in req):
                missing.append(f"one of {req}")
        else:
            if req not in conditions:
                missing.append(req)
    
    if missing:
        return False, f"Missing required conditions: {', '.join(missing)}"
    
    return True, None


def get_condition_types_for_strategy(strategy_type: str) -> Dict[str, Any]:
    """
    Get condition types (required and optional) for a strategy.
    
    Args:
        strategy_type: Strategy type string
    
    Returns:
        Dict with 'required' and 'optional' lists, or empty dict if not found
    """
    return CONDITION_REGISTRY.get(strategy_type, {})


def get_confidence_field(strategy_type: str) -> Optional[str]:
    """
    Get confidence field name for a strategy type.
    
    Args:
        strategy_type: Strategy type string
    
    Returns:
        Confidence field name or None if not applicable
    """
    registry_entry = CONDITION_REGISTRY.get(strategy_type, {})
    return registry_entry.get("confidence_field")


def get_all_strategy_types() -> List[str]:
    """Get list of all registered strategy types"""
    return list(CONDITION_REGISTRY.keys())


def is_valid_strategy_type(strategy_type: str) -> bool:
    """Check if strategy type is registered"""
    return strategy_type in CONDITION_REGISTRY

