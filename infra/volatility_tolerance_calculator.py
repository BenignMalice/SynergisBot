"""
Volatility-based tolerance calculator using RMAG and ATR
"""

import logging
from typing import Optional, Dict, Any
from infra.tolerance_helper import get_price_tolerance
from infra.tolerance_calculator import ToleranceCalculator

logger = logging.getLogger(__name__)


class VolatilityToleranceCalculator:
    """
    Calculate tolerance adjusted for current volatility (RMAG/ATR)
    """
    
    def __init__(self, tolerance_calculator: Optional[ToleranceCalculator] = None, 
                 enable_rmag_smoothing: bool = True, smoothing_alpha: float = 0.3):
        self.tolerance_calculator = tolerance_calculator or ToleranceCalculator()
        self.base_tolerance_helper = get_price_tolerance
        self.enable_rmag_smoothing = enable_rmag_smoothing
        self.smoothing_alpha = smoothing_alpha  # 0.0-1.0, lower = more smoothing
        # Per-symbol RMAG smoothing state (ephemeral - lost on restart)
        self.rmag_smoothed: Dict[str, float] = {}  # symbol -> smoothed RMAG value
        
        # Load RMAG smoothing config if available
        try:
            import json
            from pathlib import Path
            config_path = Path("config/tolerance_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                rmag_config = config.get("rmag_smoothing", {})
                if "enabled" in rmag_config:
                    self.enable_rmag_smoothing = rmag_config.get("enabled", True)
                if "alpha" in rmag_config:
                    self.smoothing_alpha = float(rmag_config.get("alpha", 0.3))
        except Exception as e:
            logger.debug(f"Could not load RMAG smoothing config: {e}, using defaults")
    
    def calculate_volatility_adjusted_tolerance(
        self,
        symbol: str,
        base_tolerance: Optional[float] = None,
        rmag_data: Optional[Dict[str, Any]] = None,
        atr: Optional[float] = None,
        timeframe: str = "M15"
    ) -> float:
        """
        Calculate tolerance adjusted for volatility.
        
        Args:
            symbol: Trading symbol
            base_tolerance: Base tolerance (if None, uses default)
            rmag_data: RMAG data dict with 'ema200_atr' and 'vwap_atr'
            atr: Current ATR value (if None, calculates)
            timeframe: Timeframe for ATR calculation
        
        Returns:
            Adjusted tolerance value
        """
        # Get base tolerance
        if base_tolerance is None:
            base_tolerance = self.base_tolerance_helper(symbol)
        
        # Start with base tolerance
        adjusted_tolerance = base_tolerance
        
        # Adjustment factor (1.0 = no change)
        adjustment_factor = 1.0
        
        # 1. RMAG-based adjustment
        if rmag_data:
            ema200_atr = abs(rmag_data.get('ema200_atr', 0))
            vwap_atr = abs(rmag_data.get('vwap_atr', 0))
            
            # NEW: Apply smoothing if enabled (before threshold checks)
            if self.enable_rmag_smoothing:
                ema200_atr = self._smooth_rmag(symbol, ema200_atr)
            
            # CRITICAL: Fail-safe kill-switch for extreme volatility (RMAG > 3σ)
            # Get kill-switch threshold (check config for symbol override)
            kill_switch_threshold = self._get_kill_switch_threshold(symbol)
            
            if ema200_atr > kill_switch_threshold:
                # Hard reject - extreme price extension (flash moves, gaps, news spikes)
                # Return minimum tolerance (10% of base) which effectively blocks execution
                # by making tolerance zone too small for price to enter
                # NOTE: This bypasses all other adjustments and minimum tolerance checks
                logger.warning(
                    f"EXTREME VOLATILITY DETECTED: RMAG {ema200_atr:.2f}σ > threshold {kill_switch_threshold:.2f}σ for {symbol}. "
                    f"Execution BLOCKED by kill-switch. kill_switch_triggered=true, symbol={symbol}, "
                    f"rmag_ema200_atr={ema200_atr:.2f}, threshold={kill_switch_threshold:.2f}"
                )
                # Return kill-switch tolerance (bypasses minimum tolerance check below)
                return base_tolerance * 0.1  # 10% of base (effectively blocks execution)
            
            # High RMAG (>2.5σ) = reduce tolerance (price stretched, more volatile)
            if ema200_atr > 2.5:
                adjustment_factor *= 0.6  # Reduce by 40%
                logger.info(
                    f"High RMAG ({ema200_atr:.2f}σ) detected for {symbol}: "
                    f"Reducing tolerance by 40% (volatility adjustment)"
                )
            elif ema200_atr > 2.0:
                adjustment_factor *= 0.75  # Reduce by 25%
                logger.info(
                    f"Elevated RMAG ({ema200_atr:.2f}σ) detected for {symbol}: "
                    f"Reducing tolerance by 25% (volatility adjustment)"
                )
            elif ema200_atr < 1.0:
                # Low RMAG = stable market, can use tighter tolerance
                adjustment_factor *= 0.9  # Slightly tighter
                logger.info(
                    f"Low RMAG ({ema200_atr:.2f}σ) detected for {symbol}: "
                    f"Tightening tolerance by 10% (stable market)"
                )
            
            # VWAP adjustment (similar logic)
            if vwap_atr > 2.0:
                adjustment_factor *= 0.85
                logger.info(
                    f"High VWAP gap ({vwap_atr:.2f}σ) detected for {symbol}: "
                    f"Reducing tolerance by 15% (VWAP deviation)"
                )
        
        # 2. ATR-based adjustment
        if atr is None:
            # Try to get ATR from tolerance calculator
            try:
                atr = self.tolerance_calculator._get_atr(symbol, timeframe)
            except:
                atr = None
        
        if atr and atr > 0:
            # Calculate ATR-based tolerance with symbol-specific multipliers
            # Use min(ATR*multiplier, base_tolerance*cap_multiplier) for tighter control
            symbol_upper = symbol.upper().rstrip('C')
            
            # Symbol-specific ATR multipliers (tighter in thin conditions)
            if "XAU" in symbol_upper or "GOLD" in symbol_upper:
                atr_multiplier = 0.4  # 0.4x ATR for XAU (tighter control)
                cap_multiplier = 1.2  # Max 20% above base tolerance
            elif "BTC" in symbol_upper:
                atr_multiplier = 0.5  # 0.5x ATR for BTC
                cap_multiplier = 1.3  # Max 30% above base tolerance
            else:  # Forex and others
                atr_multiplier = 0.3  # 0.3x ATR for forex (very tight)
                cap_multiplier = 1.1  # Max 10% above base tolerance
            
            atr_tolerance = atr * atr_multiplier
            max_cap_tolerance = base_tolerance * cap_multiplier
            
            # Use the tighter of: ATR-based tolerance or capped base tolerance
            atr_adjusted = min(atr_tolerance, max_cap_tolerance)
            
            # Ensure minimum tolerance for ATR adjustment (50% of base)
            # NOTE: This ATR minimum (50%) is higher than the final minimum (30%) below.
            # This is intentional - ATR-based adjustments should not go below 50% of base
            # to maintain reasonable tolerance for ATR-driven adjustments.
            min_tolerance_atr = base_tolerance * 0.5
            atr_adjusted = max(atr_adjusted, min_tolerance_atr)
            
            # Use tighter of: adjusted base tolerance or ATR-based tolerance
            # Note: adjustment_factor already applied in RMAG section above
            adjusted_tolerance = min(adjusted_tolerance * adjustment_factor, atr_adjusted)
        else:
            # No ATR data: apply RMAG adjustment factor only
            adjusted_tolerance = adjusted_tolerance * adjustment_factor
        
        # Ensure minimum tolerance (prevent too tight)
        # NOTE: Do NOT apply minimum if kill-switch was triggered (tolerance would be 0.1 * base)
        # Kill-switch tolerance (0.1 * base) is intentionally below minimum (0.3 * base) to block execution
        min_tolerance = base_tolerance * 0.3
        # Only apply minimum if tolerance is not already at kill-switch level
        if adjusted_tolerance >= base_tolerance * 0.15:  # Not kill-switch level
            adjusted_tolerance = max(adjusted_tolerance, min_tolerance)
        
        # Ensure maximum tolerance (prevent too wide)
        max_tolerance = self._get_max_tolerance(symbol)
        adjusted_tolerance = min(adjusted_tolerance, max_tolerance)
        
        # Log adjustment if significant (>10% change) at INFO level
        tolerance_change_pct = ((adjusted_tolerance - base_tolerance) / base_tolerance) * 100
        if abs(tolerance_change_pct) > 10:
            logger.info(
                f"Volatility-adjusted tolerance for {symbol}: "
                f"{base_tolerance:.2f} -> {adjusted_tolerance:.2f} "
                f"(change: {tolerance_change_pct:+.1f}%, factor: {adjustment_factor:.2f})"
            )
        else:
            logger.debug(
                f"Volatility-adjusted tolerance for {symbol}: "
                f"{base_tolerance:.2f} -> {adjusted_tolerance:.2f} "
                f"(factor: {adjustment_factor:.2f})"
            )
        
        return adjusted_tolerance
    
    def _smooth_rmag(self, symbol: str, current_rmag: float) -> float:
        """
        Apply exponential weighted moving average to RMAG to prevent oscillation.
        
        Args:
            symbol: Trading symbol
            current_rmag: Current RMAG value
        
        Returns:
            Smoothed RMAG value
        """
        if not self.enable_rmag_smoothing:
            return current_rmag
        
        if symbol not in self.rmag_smoothed:
            # First reading: use current value
            self.rmag_smoothed[symbol] = current_rmag
            return current_rmag
        
        # Exponential weighted moving average
        previous_smoothed = self.rmag_smoothed[symbol]
        smoothed_rmag = (self.smoothing_alpha * current_rmag + 
                         (1 - self.smoothing_alpha) * previous_smoothed)
        self.rmag_smoothed[symbol] = smoothed_rmag
        
        logger.debug(
            f"RMAG smoothing for {symbol}: {current_rmag:.2f}σ -> {smoothed_rmag:.2f}σ "
            f"(alpha={self.smoothing_alpha})"
        )
        
        return smoothed_rmag
    
    def _get_max_tolerance(self, symbol: str) -> float:
        """
        Get maximum tolerance for symbol.
        
        NOTE: This is a fallback method. If AutoExecutionSystem is available,
        its _get_max_tolerance method should be used as the source of truth.
        This method exists for standalone calculator usage or when AutoExecutionSystem
        is not available.
        
        IMPORTANT: Keep this method in sync with AutoExecutionSystem._get_max_tolerance()
        to ensure consistency.
        """
        symbol_upper = symbol.upper().rstrip('C')
        
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return 10.0
        elif "BTC" in symbol_upper:
            return 200.0
        elif "ETH" in symbol_upper:
            return 20.0
        else:
            return 0.01
    
    def _get_kill_switch_threshold(self, symbol: str) -> float:
        """Get kill-switch threshold for symbol (from config or default)"""
        try:
            import json
            from pathlib import Path
            config_path = Path("config/tolerance_config.json")
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                kill_switch_config = config.get("kill_switch", {})
                if not kill_switch_config.get("enabled", True):
                    return float('inf')  # Disabled
                
                # Check for symbol override
                symbol_upper = symbol.upper().rstrip('C')
                symbol_overrides = kill_switch_config.get("symbol_overrides", {})
                if symbol_upper in symbol_overrides:
                    return float(symbol_overrides[symbol_upper])
                
                # Use default threshold
                return float(kill_switch_config.get("rmag_threshold", 3.0))
        except Exception as e:
            logger.debug(f"Could not load kill-switch config: {e}, using defaults")
        
        # Fallback to symbol-specific defaults
        symbol_upper = symbol.upper().rstrip('C')
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return 2.8  # Lower threshold for XAU (more sensitive)
        elif "BTC" in symbol_upper:
            return 3.5  # Higher threshold for BTC (more volatile)
        else:
            return 3.0  # Default threshold
