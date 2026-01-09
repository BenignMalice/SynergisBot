"""
VWAP Reversion Strategy Checker

Implements VWAP mean reversion strategy with:
- Price deviation ≥2σ from VWAP
- CHOCH at deviation extreme
- Volume confirmation
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from infra.micro_scalp_strategies.base_strategy_checker import BaseStrategyChecker
from infra.micro_scalp_conditions import ConditionCheckResult

logger = logging.getLogger(__name__)


class VWAPReversionChecker(BaseStrategyChecker):
    """
    Strategy checker for VWAP Reversion Scalp.
    
    Entry Logic:
    - Price deviated ≥2σ from VWAP (mean reversion setup)
    - CHOCH at deviation extreme (reversal signal)
    - Volume spike confirmation
    - VWAP slope not strongly trending
    """
    
    def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                              current_price: float, vwap: float, 
                              atr1: Optional[float]) -> Dict[str, Any]:
        """
        VWAP Reversion-specific location filter.
        
        Checks:
        - Price deviation ≥2σ from VWAP
        - VWAP slope (not strongly trending)
        - Volume spike confirmation
        """
        if vwap == 0:
            return {'passed': False, 'reasons': ['VWAP is zero']}
        
        # Calculate VWAP deviation in standard deviations
        vwap_std = self._calculate_vwap_std(candles, vwap)
        if vwap_std == 0:
            return {'passed': False, 'reasons': ['VWAP std is zero']}
        
        deviation_sigma = abs(current_price - vwap) / vwap_std
        deviation_pct = abs(current_price - vwap) / vwap if vwap > 0 else 0
        
        # Symbol-specific thresholds
        if symbol.upper().startswith('BTC'):
            min_deviation = 2.0
            min_deviation_pct = 0.005  # 0.5%
        else:  # XAU
            min_deviation = 2.0
            min_deviation_pct = 0.002  # 0.20%
        
        # Check deviation threshold
        deviation_ok = deviation_sigma >= min_deviation or deviation_pct >= min_deviation_pct
        
        # Check VWAP slope (not strongly trending)
        vwap_slope = self._calculate_vwap_slope(candles, vwap)
        if atr1 and atr1 > 0:
            vwap_slope_normalized = abs(vwap_slope) / atr1
            max_slope_normalized = 0.1  # 10% of ATR per bar
            vwap_slope_ok = vwap_slope_normalized < max_slope_normalized
        else:
            max_slope = 0.0001
            vwap_slope_ok = abs(vwap_slope) < max_slope
        
        # Check volume spike
        volume_spike = self._check_volume_spike(candles)
        
        passed = deviation_ok and vwap_slope_ok
        
        reasons = []
        if not deviation_ok:
            reasons.append(f'Deviation {deviation_sigma:.2f}σ < {min_deviation}σ')
        if not vwap_slope_ok:
            reasons.append('VWAP slope too steep')
        
        return {
            'passed': passed,
            'deviation_sigma': deviation_sigma,
            'deviation_pct': deviation_pct,
            'vwap_slope': vwap_slope,
            'vwap_slope_ok': vwap_slope_ok,
            'volume_spike': volume_spike,
            'reasons': reasons
        }
    
    def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                             current_price: float, vwap: float, atr1: Optional[float],
                             btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        VWAP Reversion-specific candle signals.
        
        Checks:
        - Primary: M1 CHOCH at deviation extreme
        - Secondary: Volume confirmation OR absorption wick
        """
        primary_triggers = []
        secondary_confluence = []
        
        # Primary: CHOCH at deviation extreme
        choch_detected = False
        choch_direction = None
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                choch_bos = analysis.get('choch_bos', {})
                choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
                choch_direction = choch_bos.get('direction', '')
                
                # Verify CHOCH is at deviation extreme
                if choch_detected:
                    # Check if price is at deviation (far from VWAP)
                    vwap_std = self._calculate_vwap_std(candles, vwap)
                    if vwap_std > 0:
                        deviation_sigma = abs(current_price - vwap) / vwap_std
                        if deviation_sigma >= 2.0:
                            primary_triggers.append('CHOCH_AT_EXTREME')
            except Exception as e:
                logger.debug(f"Error checking CHOCH: {e}")
        
        # Secondary: Volume confirmation
        volume_spike = self._check_volume_spike(candles)
        if volume_spike:
            secondary_confluence.append('VOLUME_CONFIRMED')
        
        # Secondary: Absorption wick (long wick into extension)
        if len(candles) >= 1:
            last_candle = candles[-1]
            high = last_candle.get('high', 0)
            low = last_candle.get('low', 0)
            close = last_candle.get('close', 0)
            open_price = last_candle.get('open', 0)
            
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            total_range = high - low
            
            if total_range > 0:
                # Absorption wick: wick > 2× body
                if upper_wick > body * 2 or lower_wick > body * 2:
                    secondary_confluence.append('ABSORPTION_WICK')
        
        return {
            'primary_count': len(primary_triggers),
            'secondary_count': len(secondary_confluence),
            'primary_triggers': primary_triggers,
            'secondary_confluence': secondary_confluence
        }
    
    def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                                   current_price: float, vwap: float, atr1: Optional[float],
                                   location_result: Dict[str, Any],
                                   signal_result: Dict[str, Any]) -> float:
        """
        VWAP Reversion-specific confluence scoring.
        
        Uses strategy-specific weights from config.
        """
        # Get strategy-specific weights
        weights = self.config.get('regime_detection', {}).get('confluence_weights', {}).get('vwap_reversion', {})
        
        # Default weights if not configured
        default_weights = {
            'deviation_sigma': 2.0,
            'choch_quality': 2.0,
            'volume_confirmation': 2.0,
            'vwap_slope': 1.0,
            'absorption_wick': 1.0
        }
        
        # Use configured weights or defaults
        w_deviation = weights.get('deviation_sigma', default_weights['deviation_sigma'])
        w_choch = weights.get('choch_quality', default_weights['choch_quality'])
        w_volume = weights.get('volume_confirmation', default_weights['volume_confirmation'])
        w_slope = weights.get('vwap_slope', default_weights['vwap_slope'])
        w_wick = weights.get('absorption_wick', default_weights['absorption_wick'])
        
        score = 0.0
        
        # Deviation strength (0-2)
        deviation_sigma = location_result.get('deviation_sigma', 0)
        if deviation_sigma >= 2.5:
            score += 2.0 * w_deviation
        elif deviation_sigma >= 2.0:
            score += 1.5 * w_deviation
        elif deviation_sigma >= 1.5:
            score += 1.0 * w_deviation
        
        # CHOCH quality (0-2)
        if 'CHOCH_AT_EXTREME' in signal_result.get('primary_triggers', []):
            score += 2.0 * w_choch
        elif signal_result.get('primary_count', 0) > 0:
            score += 1.0 * w_choch
        
        # Volume confirmation (0-2)
        if location_result.get('volume_spike', False):
            score += 2.0 * w_volume
        elif 'VOLUME_CONFIRMED' in signal_result.get('secondary_confluence', []):
            score += 1.0 * w_volume
        
        # VWAP slope (0-1)
        if location_result.get('vwap_slope_ok', False):
            score += 1.0 * w_slope
        
        # Absorption wick (0-1)
        if 'ABSORPTION_WICK' in signal_result.get('secondary_confluence', []):
            score += 1.0 * w_wick
        
        return score
    
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """
        Generate VWAP Reversion trade idea.
        
        Direction: Opposite of deviation (mean reversion)
        - Price below VWAP → BUY (expect reversion up)
        - Price above VWAP → SELL (expect reversion down)
        """
        symbol = snapshot.get('symbol', '')
        current_price = snapshot.get('current_price', 0)
        vwap = snapshot.get('vwap', 0)
        atr1 = snapshot.get('atr1')
        candles = snapshot.get('candles', [])
        
        if vwap == 0 or current_price == 0:
            return None
        
        # Determine direction from CHOCH or price position
        direction = self._get_direction_from_choch(symbol, candles, vwap, current_price)
        
        # Calculate entry, SL, TP
        if atr1 and atr1 > 0:
            # Ultra-tight stops for micro-scalp
            sl_distance = atr1 * 0.5  # 0.5× ATR
            tp_distance = atr1 * 1.0  # 1.0× ATR (1:2 R:R)
        else:
            # Fallback to percentage-based
            if symbol.upper().startswith('BTC'):
                sl_distance = current_price * 0.001  # 0.1%
                tp_distance = current_price * 0.002  # 0.2%
            else:  # XAU
                sl_distance = current_price * 0.0005  # 0.05%
                tp_distance = current_price * 0.001  # 0.1%
        
        if direction == 'BUY':
            entry_price = current_price
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:  # SELL
            entry_price = current_price
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'sl': stop_loss,
            'tp': take_profit,
            'strategy': 'vwap_reversion',
            'confluence_score': result.confluence_score,
            'is_aplus': result.is_aplus_setup
        }
    
    def _get_direction_from_choch(self, symbol: str, candles: List[Dict], 
                                  vwap: float, current_price: float) -> str:
        """Extract direction from CHOCH signal"""
        if not self.m1_analyzer:
            # Fallback: use price position relative to VWAP
            return 'BUY' if current_price < vwap else 'SELL'
        
        try:
            analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
            choch_bos = analysis.get('choch_bos', {})
            choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
            choch_direction = choch_bos.get('direction', '')
            
            if choch_detected:
                if choch_direction == 'BULLISH' or 'bull' in str(choch_direction).lower():
                    return 'BUY'
                elif choch_direction == 'BEARISH' or 'bear' in str(choch_direction).lower():
                    return 'SELL'
            
            # Fallback: use price position relative to VWAP
            if current_price < vwap:
                return 'BUY'  # Price below VWAP, expect reversion up
            else:
                return 'SELL'  # Price above VWAP, expect reversion down
        except Exception as e:
            logger.debug(f"Error getting direction from CHOCH: {e}")
            # Fallback
            return 'BUY' if current_price < vwap else 'SELL'

