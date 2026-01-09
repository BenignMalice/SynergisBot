"""
Dynamic Lot Size Calculator
Calculates lot size based on plan confidence and symbol type.
"""

from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class LotSizeCalculator:
    """Calculate dynamic lot sizes based on plan confidence"""
    
    # Condition weights
    HIGH_VALUE_WEIGHT = 3
    MEDIUM_VALUE_WEIGHT = 2
    
    # High-value conditions
    HIGH_VALUE_CONDITIONS = [
        "structure_confirmation",
        "choch_bull", "choch_bear",
        "order_block", "breaker_block",
        "mss_bull", "mss_bear",
        "liquidity_sweep"
    ]
    
    # Medium-value conditions
    MEDIUM_VALUE_CONDITIONS = [
        "rejection_wick",
        "bos_bull", "bos_bear",
        "fvg_bull", "fvg_bear",
        "mitigation_block_bull", "mitigation_block_bear",
        "equal_highs", "equal_lows",
        "vwap_deviation",
        "volume_confirmation", "volume_spike"
    ]
    
    def calculate_confidence(self, conditions: Dict[str, Any]) -> float:
        """
        Calculate confidence score (0-1) based on conditions.
        
        Args:
            conditions: Plan conditions dictionary
        
        Returns:
            float: Confidence score from 0.0 to 1.0
        """
        # Handle None or empty conditions
        if not conditions or conditions is None:
            return 0.0
        
        score = 0
        max_possible_score = 40  # FIXED: Lowered from 60 to 40 for better confidence distribution
        
        # Count high-value conditions
        for condition in self.HIGH_VALUE_CONDITIONS:
            if conditions.get(condition) is True:
                score += self.HIGH_VALUE_WEIGHT
        
        # Count medium-value conditions
        for condition in self.MEDIUM_VALUE_CONDITIONS:
            if conditions.get(condition) is True:
                score += self.MEDIUM_VALUE_WEIGHT
        
        # Add confluence bonus (ONLY counts once, prevents double-counting)
        confluence = conditions.get("range_scalp_confluence") or conditions.get("min_confluence")
        if confluence and isinstance(confluence, (int, float)):
            if confluence >= 90:
                score += 10
            elif confluence >= 80:
                score += 8
            elif confluence >= 70:
                score += 5
            elif confluence >= 60:
                score += 3
            elif confluence >= 50:
                score += 1
            # < 50: no bonus points
        
        # Normalize to 0-1 range
        confidence = min(score / max_possible_score, 1.0)
        
        logger.debug(f"Plan confidence calculated: {confidence:.2f} (score: {score})")
        
        return confidence
    
    def calculate_lot_size(
        self,
        symbol: str,
        confidence: float,
        base_lot_size: float = 0.01
    ) -> float:
        """
        Calculate lot size based on symbol type and confidence.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc", "XAUUSDc", "EURUSDc")
            confidence: Confidence score (0.0 to 1.0)
            base_lot_size: Minimum lot size (default: 0.01)
        
        Returns:
            float: Calculated lot size
        """
        # Validate symbol
        if not symbol or not isinstance(symbol, str):
            logger.warning(f"Invalid symbol provided: {symbol}, using Forex default max")
            max_lot_size = 0.05
            symbol = "UNKNOWN"
        else:
            # Determine max lot size based on symbol type
            symbol_upper = symbol.upper()
            # Check for BTC, XAU, or GOLD in symbol name
            # Symbols are normalized (e.g., "BTCUSDc", "XAUUSDc"), so this is safe
            if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
                max_lot_size = 0.03
            else:
                # Forex pairs (default)
                max_lot_size = 0.05
        
        # Validate confidence is non-negative
        if confidence < 0:
            logger.warning(f"Negative confidence detected: {confidence}, clamping to 0.0")
            confidence = 0.0
        
        # Calculate lot size: base + (confidence * (max - base))
        lot_size = base_lot_size + (confidence * (max_lot_size - base_lot_size))
        
        # Round to nearest 0.01 increment (standard lot precision)
        # This ensures lot sizes are always in 0.01 increments (0.01, 0.02, 0.03, etc.)
        # Not fractional sizes like 0.015 or 0.023
        lot_size = round(lot_size / 0.01) * 0.01
        lot_size = round(lot_size, 2)  # Clean up floating point errors
        
        # Ensure it's within bounds (safety check)
        lot_size = max(base_lot_size, min(lot_size, max_lot_size))
        
        # Final validation: ensure lot_size is positive and reasonable
        if lot_size <= 0:
            logger.error(f"Calculated invalid lot size: {lot_size}, using base_lot_size")
            lot_size = base_lot_size
        
        logger.info(
            f"Calculated lot size for {symbol}: {lot_size} "
            f"(confidence: {confidence:.2f}, max: {max_lot_size})"
        )
        
        return lot_size
    
    def calculate_plan_lot_size(
        self,
        symbol: str,
        conditions: Dict[str, Any],
        base_lot_size: float = 0.01
    ) -> Tuple[float, float]:
        """
        Calculate lot size for a plan based on conditions.
        
        Args:
            symbol: Trading symbol
            conditions: Plan conditions dictionary
            base_lot_size: Minimum lot size (default: 0.01)
        
        Returns:
            tuple: (lot_size, confidence) - Calculated lot size and confidence score
        """
        confidence = self.calculate_confidence(conditions)
        lot_size = self.calculate_lot_size(symbol, confidence, base_lot_size)
        
        return lot_size, confidence
