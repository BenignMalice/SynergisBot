"""
Auto Execution Plan Validator

Validates auto-execution trade plans against volatility states to ensure
strategies are compatible with current market conditions.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from infra.volatility_regime_detector import VolatilityRegime

logger = logging.getLogger(__name__)


class AutoExecutionValidator:
    """Validates auto-execution plans against volatility states."""
    
    def validate_volatility_state(
        self,
        plan: Dict[str, Any],
        volatility_regime: VolatilityRegime,
        strategy_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate plan against volatility state.
        
        Args:
            plan: Trade plan dictionary
            volatility_regime: Detected volatility regime
            strategy_type: Strategy type string (extracted from plan if not provided)
        
        Returns:
            (is_valid, rejection_reason)
        """
        # Extract strategy_type from plan if not provided
        if not strategy_type:
            conditions = plan.get("conditions", {})
            strategy_type = conditions.get("strategy_type")
            if not strategy_type and plan.get("notes"):
                # Try to extract from notes (e.g., "[strategy:breakout_ib_volatility_trap]")
                import re
                match = re.search(r'\[strategy:(\w+)\]', plan.get("notes", ""))
                if match:
                    strategy_type = match.group(1)
        
        # SESSION_SWITCH_FLARE: Block ALL plans
        if volatility_regime == VolatilityRegime.SESSION_SWITCH_FLARE:
            return (False, "Cannot create plans during SESSION_SWITCH_FLARE - wait for volatility stabilization")
        
        # FRAGMENTED_CHOP: Only allow micro_scalp and mean_reversion_range_scalp
        if volatility_regime == VolatilityRegime.FRAGMENTED_CHOP:
            allowed = ["micro_scalp", "mean_reversion_range_scalp"]
            if strategy_type and strategy_type not in allowed:
                return (False, f"FRAGMENTED_CHOP only allows {allowed} strategies. Plan uses: {strategy_type}")
        
        # POST_BREAKOUT_DECAY: Block trend continuation
        if volatility_regime == VolatilityRegime.POST_BREAKOUT_DECAY:
            blocked = ["trend_continuation_pullback", "breakout_ib_volatility_trap", "market_structure_shift"]
            if strategy_type and strategy_type in blocked:
                return (False, f"POST_BREAKOUT_DECAY blocks {strategy_type} - momentum is fading")
        
        # PRE_BREAKOUT_TENSION: Discourage mean reversion
        if volatility_regime == VolatilityRegime.PRE_BREAKOUT_TENSION:
            discouraged = ["mean_reversion_range_scalp"]
            if strategy_type and strategy_type in discouraged:
                return (False, f"PRE_BREAKOUT_TENSION discourages {strategy_type} - breakout expected")
        
        return (True, None)

