"""
Professional Trading Filters
Used by algo desks and prop firms to protect against:
- False breakouts
- Volatility spikes
- Macro shifts
- Low-quality entries
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result from a trading filter check"""
    passed: bool
    reason: str
    confidence: float = 1.0
    action: str = "allow"  # "allow", "delay", "block"


class ProfessionalFilters:
    """
    Professional trading filters used by algo desks and prop firms.
    
    Implements:
    1. Pre-Volatility Filter (ATR surge + spread checks)
    2. Early-Exit AI Mode (structure collapse detection)
    3. Structure-Based Stop-Loss (swing-based stops)
    4. Correlation Filter (USD strength alignment)
    """
    
    def __init__(self, dxy_service=None):
        self.logger = logging.getLogger(__name__)
        self.dxy_service = dxy_service
        
        # Try to initialize DXY service if not provided
        if self.dxy_service is None:
            try:
                from infra.dxy_service import create_dxy_service
                self.dxy_service = create_dxy_service()
            except Exception as e:
                self.logger.warning(f"Could not initialize DXY service: {e}")
        
        self.logger.info(f"ProfessionalFilters initialized (DXY: {'enabled' if self.dxy_service else 'disabled'})")
    
    # ==================== 1. PRE-VOLATILITY FILTER ====================
    
    def check_pre_volatility(
        self,
        symbol: str,
        current_atr: float,
        avg_atr: float,
        current_spread: float,
        avg_spread: float
    ) -> FilterResult:
        """
        Pre-Volatility Filter: Blocks trades during volatility spikes.
        
        Checks:
        - ATR surge: Current ATR > 1.5x average
        - Spread surge: Current spread > 2x average
        
        Args:
            symbol: Trading symbol
            current_atr: Current ATR value
            avg_atr: 14-period average ATR
            current_spread: Current bid-ask spread
            avg_spread: Average spread
            
        Returns:
            FilterResult with passed=True if conditions are stable
        """
        # ATR Surge Check
        atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        if atr_ratio > 1.5:
            return FilterResult(
                passed=False,
                reason=f"ATR surge detected ({atr_ratio:.2f}x normal). Wait for volatility to stabilize.",
                confidence=0.3,
                action="delay"
            )
        
        # Spread Check
        spread_ratio = current_spread / avg_spread if avg_spread > 0 else 1.0
        if spread_ratio > 2.0:
            return FilterResult(
                passed=False,
                reason=f"Spread widened ({spread_ratio:.2f}x normal). Low liquidity detected.",
                confidence=0.2,
                action="block"
            )
        
        # All checks passed
        return FilterResult(
            passed=True,
            reason="Volatility conditions stable for entry",
            confidence=1.0,
            action="allow"
        )
    
    # ==================== 2. EARLY-EXIT AI MODE ====================
    
    def check_early_exit_signals(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[Any] = None
    ) -> FilterResult:
        """
        Early-Exit AI Mode: Detects structure collapse before SL hit.
        
        Checks for 2+ of these conditions:
        1. RSI divergence (momentum fading)
        2. MACD crossover against trade
        3. ADX below 25 (weak trend)
        
        Args:
            direction: "buy" or "sell"
            features: Technical indicators (RSI, MACD, ADX)
            bars: Price bars for divergence detection
            
        Returns:
            FilterResult with passed=False if early exit recommended
        """
        exit_signals = []
        
        # 1. RSI Momentum Check
        rsi = features.get('rsi', 50)
        if direction == "buy" and rsi < 45:
            exit_signals.append("RSI momentum fading (< 45)")
        elif direction == "sell" and rsi > 55:
            exit_signals.append("RSI momentum fading (> 55)")
        
        # 2. MACD Crossover Check
        macd_hist = features.get('macd_hist', 0)
        macd_hist_prev = features.get('macd_hist_prev', macd_hist)
        
        if direction == "buy" and macd_hist < 0 and macd_hist < macd_hist_prev:
            exit_signals.append("MACD crossed bearish")
        elif direction == "sell" and macd_hist > 0 and macd_hist > macd_hist_prev:
            exit_signals.append("MACD crossed bullish")
        
        # 3. ADX Trend Strength Check
        adx = features.get('adx', 20)
        if adx < 25:
            exit_signals.append(f"ADX weak ({adx:.1f} < 25) - trend losing strength")
        
        # Early exit if 2+ signals present
        if len(exit_signals) >= 2:
            return FilterResult(
                passed=False,
                reason=f"Structure collapse: {', '.join(exit_signals)}",
                confidence=0.8 + (0.1 * len(exit_signals)),
                action="exit_early"
            )
        
        return FilterResult(
            passed=True,
            reason="Trade structure intact",
            confidence=1.0,
            action="hold"
        )
    
    # ==================== 3. STRUCTURE-BASED STOP-LOSS ====================
    
    def calculate_structure_stop_loss(
        self,
        direction: str,
        entry_price: float,
        bars: Optional[Any] = None,
        lookback_bars: int = 20,
        buffer_pips: float = 5.0
    ) -> Tuple[float, str]:
        """
        Structure-Based Stop-Loss: Uses swing highs/lows instead of fixed pips.
        
        For BUY: Places SL below recent swing low
        For SELL: Places SL above recent swing high
        
        Args:
            direction: "buy" or "sell"
            entry_price: Trade entry price
            bars: Price bars DataFrame with 'high' and 'low' columns
            lookback_bars: How many bars to look back for swings
            buffer_pips: Extra buffer beyond swing point
            
        Returns:
            Tuple of (stop_loss_price, reason)
        """
        if bars is None or len(bars) < lookback_bars:
            # Fallback: 2 ATR stop if no bars available
            fallback_sl = entry_price * 0.995 if direction == "buy" else entry_price * 1.005
            return fallback_sl, "No bars available, using 0.5% stop"
        
        try:
            # Find swing points
            if direction == "buy":
                # Find lowest low in lookback period
                swing_low = bars['low'].tail(lookback_bars).min()
                stop_loss = swing_low - (buffer_pips * 0.0001)  # Convert pips to price
                reason = f"SL below swing low ({swing_low:.5f}) - {buffer_pips} pip buffer"
            else:  # sell
                # Find highest high in lookback period
                swing_high = bars['high'].tail(lookback_bars).max()
                stop_loss = swing_high + (buffer_pips * 0.0001)
                reason = f"SL above swing high ({swing_high:.5f}) + {buffer_pips} pip buffer"
            
            # Validate stop is reasonable (not too far from entry)
            max_distance = entry_price * 0.02  # 2% max
            if abs(entry_price - stop_loss) > max_distance:
                # Too far, use 2% stop instead
                stop_loss = entry_price * 0.98 if direction == "buy" else entry_price * 1.02
                reason = "Swing too far, using 2% stop"
            
            return stop_loss, reason
            
        except Exception as e:
            self.logger.error(f"Error calculating structure stop: {e}")
            # Fallback
            fallback_sl = entry_price * 0.995 if direction == "buy" else entry_price * 1.005
            return fallback_sl, "Error in calculation, using 0.5% stop"
    
    # ==================== 4. CORRELATION FILTER ====================
    
    def check_usd_correlation(
        self,
        symbol: str,
        direction: str,
        dxy_trend: Optional[str] = None,
        us10y_trend: Optional[str] = None
    ) -> FilterResult:
        """
        Correlation Filter: Checks USD strength before USD-quoted trades.
        
        Blocks trades that fight against USD macro flow:
        - Don't buy XAUUSD/BTCUSD when DXY is strengthening
        - Don't sell EURUSD/GBPUSD when DXY is weakening
        
        Args:
            symbol: Trading symbol
            direction: "buy" or "sell"
            dxy_trend: "up", "down", or "neutral" (fetched from DXY service if None)
            us10y_trend: "up", "down", or "neutral"
            
        Returns:
            FilterResult with passed=False if fighting USD flow
        """
        # Only applies to USD-quoted instruments
        usd_symbols = ['XAUUSD', 'BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD']
        if not any(usd in symbol.upper() for usd in usd_symbols):
            return FilterResult(
                passed=True,
                reason="Not a USD-quoted instrument, correlation filter not applicable",
                confidence=1.0,
                action="allow"
            )
        
        # Fetch DXY trend from service if not provided
        if dxy_trend is None and self.dxy_service:
            try:
                dxy_trend = self.dxy_service.get_dxy_trend()
                if dxy_trend:
                    cache_info = self.dxy_service.get_cache_info()
                    self.logger.info(f"DXY trend: {dxy_trend} (cached: {cache_info['age_minutes']:.1f}m ago)")
            except Exception as e:
                self.logger.warning(f"Failed to fetch DXY trend: {e}")
        
        # If no DXY data available, allow trade (neutral stance)
        if dxy_trend is None:
            return FilterResult(
                passed=True,
                reason="No DXY data available, allowing trade",
                confidence=0.7,
                action="allow"
            )
        
        # Check for USD strength conflicts
        is_usd_strong = (dxy_trend == "up" or us10y_trend == "up")
        is_usd_weak = (dxy_trend == "down" or us10y_trend == "down")
        
        # For commodity pairs (XAUUSD, BTCUSD)
        if 'XAU' in symbol.upper() or 'BTC' in symbol.upper() or 'ETH' in symbol.upper():
            if direction == "buy" and is_usd_strong:
                return FilterResult(
                    passed=False,
                    reason=f"USD strengthening (DXY {dxy_trend}) - avoid buying Gold/Crypto",
                    confidence=0.4,
                    action="delay"
                )
            elif direction == "sell" and is_usd_weak:
                return FilterResult(
                    passed=False,
                    reason=f"USD weakening (DXY {dxy_trend}) - avoid selling Gold/Crypto",
                    confidence=0.4,
                    action="delay"
                )
        
        # For EUR/GBP/AUD pairs (inverse correlation)
        elif any(pair in symbol.upper() for pair in ['EURUSD', 'GBPUSD', 'AUDUSD']):
            if direction == "buy" and is_usd_strong:
                return FilterResult(
                    passed=False,
                    reason=f"USD strengthening (DXY {dxy_trend}) - avoid buying EUR/GBP/AUD",
                    confidence=0.4,
                    action="delay"
                )
            elif direction == "sell" and is_usd_weak:
                return FilterResult(
                    passed=False,
                    reason=f"USD weakening (DXY {dxy_trend}) - avoid selling EUR/GBP/AUD",
                    confidence=0.4,
                    action="delay"
                )
        
        return FilterResult(
            passed=True,
            reason="USD correlation aligned with trade direction",
            confidence=1.0,
            action="allow"
        )
    
    # ==================== COMBINED FILTER CHECK ====================
    
    def run_all_filters(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        features: Dict[str, Any],
        bars: Optional[Any] = None,
        check_volatility: bool = True,
        check_correlation: bool = True
    ) -> Dict[str, Any]:
        """
        Run all professional filters and return comprehensive result.
        
        Returns:
            Dictionary with:
            - overall_passed: bool
            - filters: dict of individual filter results
            - recommended_action: "allow", "delay", "block"
            - warnings: list of warnings
            - suggested_sl: float (if structure-based SL calculated)
        """
        results = {
            "overall_passed": True,
            "filters": {},
            "recommended_action": "allow",
            "warnings": [],
            "suggested_sl": None,
            "confidence": 1.0
        }
        
        # 1. Pre-Volatility Filter
        if check_volatility:
            current_atr = features.get('atr', 10.0)
            avg_atr = current_atr  # TODO: Calculate 14-period average
            current_spread = features.get('spread', 0.0)
            avg_spread = current_spread * 0.8  # Estimate
            
            volatility_result = self.check_pre_volatility(
                symbol, current_atr, avg_atr, current_spread, avg_spread
            )
            results["filters"]["pre_volatility"] = volatility_result
            
            if not volatility_result.passed:
                results["overall_passed"] = False
                results["recommended_action"] = volatility_result.action
                results["warnings"].append(volatility_result.reason)
                results["confidence"] *= volatility_result.confidence
        
        # 2. Correlation Filter
        if check_correlation:
            # TODO: Get actual DXY trend from market data
            dxy_trend = None  # Will be "up", "down", or "neutral"
            us10y_trend = None
            
            correlation_result = self.check_usd_correlation(
                symbol, direction, dxy_trend, us10y_trend
            )
            results["filters"]["correlation"] = correlation_result
            
            if not correlation_result.passed:
                results["overall_passed"] = False
                if results["recommended_action"] == "allow":
                    results["recommended_action"] = correlation_result.action
                results["warnings"].append(correlation_result.reason)
                results["confidence"] *= correlation_result.confidence
        
        # 3. Structure-Based Stop-Loss
        if bars is not None:
            suggested_sl, sl_reason = self.calculate_structure_stop_loss(
                direction, entry_price, bars
            )
            results["suggested_sl"] = suggested_sl
            results["filters"]["structure_sl"] = {
                "stop_loss": suggested_sl,
                "reason": sl_reason
            }
        
        return results
    
    def check_for_early_exit(
        self,
        position: Any,
        features: Dict[str, Any],
        bars: Optional[Any] = None
    ) -> FilterResult:
        """
        Check if position should be exited early (before SL).
        To be called during position monitoring.
        """
        direction = "buy" if position.type == 0 else "sell"
        
        return self.check_early_exit_signals(direction, features, bars)


# Factory function
def create_professional_filters() -> ProfessionalFilters:
    """Create a ProfessionalFilters instance"""
    return ProfessionalFilters()

