"""
Macro Bias Calculator
Converts macro drivers (DXY, yields, etc.) into unified bias score (-1 to +1)

Bias Score:
- +1.0: Strong bullish macro environment
- 0.0: Neutral/mixed signals
- -1.0: Strong bearish macro environment

Used to influence confidence and SL/TP direction in trade recommendations.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MacroBiasCalculator:
    """
    Calculate macro bias scores for different trading symbols
    
    Pair-Specific Rules:
    - XAUUSD: DXY + US10Y (inverse correlation)
    - EURUSD/GBPUSD: DXY mirror + EU/UK yields
    - USDJPY: US-JP yield spread
    - GBPJPY/EURJPY: Risk sentiment + respective yields
    - BTCUSD: NASDAQ correlation + VIX
    """
    
    def __init__(self, market_indices_service=None, fred_service=None):
        """
        Initialize Macro Bias Calculator
        
        Args:
            market_indices_service: MarketIndicesService instance (for DXY, VIX, US10Y, NASDAQ)
            fred_service: FREDService instance (for real yields, Fed expectations)
        """
        self.market_indices = market_indices_service
        self.fred_service = fred_service
        self.logger = logging.getLogger(__name__)
    
    def calculate_bias(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate macro bias score for a symbol (-1 to +1)
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD', 'BTCUSD', 'EURUSD')
        
        Returns:
            {
                'bias_score': 0.75,  # -1.0 to +1.0
                'bias_strength': 'strong',  # strong/moderate/weak
                'bias_direction': 'bullish',  # bullish/bearish/neutral
                'factors': {...},  # Contributing factors
                'explanation': 'Rising DXY and yields maintain downside pressure...',
                'timestamp': '2025-10-09T20:00:00'
            }
        """
        symbol_normalized = symbol.upper().replace('C', '')
        
        if symbol_normalized == 'XAUUSD':
            return self._calculate_gold_bias()
        elif symbol_normalized in ['EURUSD', 'GBPUSD']:
            return self._calculate_usd_pair_bias(symbol_normalized)
        elif symbol_normalized == 'USDJPY':
            return self._calculate_usdjpy_bias()
        elif symbol_normalized in ['GBPJPY', 'EURJPY']:
            return self._calculate_cross_pair_bias(symbol_normalized)
        elif symbol_normalized == 'BTCUSD':
            return self._calculate_btc_bias()
        else:
            # Generic bias (just DXY for USD pairs)
            return self._calculate_generic_bias(symbol_normalized)
    
    def _calculate_gold_bias(self) -> Dict[str, Any]:
        """
        Calculate bias for XAUUSD (Gold)
        
        Factors:
        - DXY: Inverse correlation (DXY up = Gold down)
        - US10Y/Real Yield: Inverse correlation (Yields up = Gold down)
        - VIX: Risk-off sentiment (VIX up = Gold up)
        """
        if not self.market_indices:
            return self._empty_bias("XAUUSD", "Market indices service unavailable")
        
        try:
            dxy_data = self.market_indices.get_dxy()
            us10y_data = self.market_indices.get_us10y()
            vix_data = self.market_indices.get_vix()
            
            factors = {}
            bias_points = 0.0
            
            # DXY factor (-0.4 points if DXY rising, +0.4 if falling)
            dxy_trend = dxy_data.get('trend', 'neutral')
            if dxy_trend == 'up':
                factors['dxy'] = {'value': -0.4, 'reason': 'USD strengthening (bearish for Gold)'}
                bias_points -= 0.4
            elif dxy_trend == 'down':
                factors['dxy'] = {'value': +0.4, 'reason': 'USD weakening (bullish for Gold)'}
                bias_points += 0.4
            else:
                factors['dxy'] = {'value': 0.0, 'reason': 'DXY neutral'}
            
            # US10Y factor (-0.4 points if yields rising, +0.4 if falling)
            us10y_trend = us10y_data.get('trend', 'neutral')
            if us10y_trend == 'up':
                factors['us10y'] = {'value': -0.4, 'reason': 'Rising yields (bearish for Gold - opportunity cost)'}
                bias_points -= 0.4
            elif us10y_trend == 'down':
                factors['us10y'] = {'value': +0.4, 'reason': 'Falling yields (bullish for Gold)'}
                bias_points += 0.4
            else:
                factors['us10y'] = {'value': 0.0, 'reason': 'Yields neutral'}
            
            # Real yield (if FRED available, more accurate)
            if self.fred_service:
                us10y_nominal = us10y_data.get('price')
                real_yield = self.fred_service.calculate_real_yield(us10y_nominal)
                if real_yield is not None:
                    # Real yield > 1.5% = bearish, < 0.5% = bullish
                    if real_yield > 1.5:
                        factors['real_yield'] = {'value': -0.2, 'reason': f'Real yield elevated ({real_yield:.2f}%) - bearish headwind'}
                        bias_points -= 0.2
                    elif real_yield < 0.5:
                        factors['real_yield'] = {'value': +0.2, 'reason': f'Real yield low ({real_yield:.2f}%) - bullish tailwind'}
                        bias_points += 0.2
                
                # Fed expectations tracking (2Y-10Y spread)
                spread_2y10y = self.fred_service.get_2y10y_spread()
                if spread_2y10y is not None:
                    # Inverted spread (< -0.2%) = recession signal → Fed likely to cut → bullish for Gold
                    # Steep spread (> +0.5%) = growth expectations → Fed likely to hold/hike → bearish for Gold
                    # Flat spread (-0.2% to +0.5%) = neutral
                    if spread_2y10y < -0.2:
                        # Inverted yield curve - recession warning
                        factors['fed_expectations'] = {
                            'value': +0.15,
                            'reason': f'2Y-10Y spread inverted ({spread_2y10y:.2f}%) - recession signal, Fed likely to cut (bullish for Gold)'
                        }
                        bias_points += 0.15
                    elif spread_2y10y > 0.5:
                        # Steep curve - growth expectations
                        factors['fed_expectations'] = {
                            'value': -0.15,
                            'reason': f'2Y-10Y spread steep ({spread_2y10y:.2f}%) - growth expectations, Fed likely to hold/hike (bearish for Gold)'
                        }
                        bias_points -= 0.15
                    else:
                        # Flat curve - neutral
                        factors['fed_expectations'] = {
                            'value': 0.0,
                            'reason': f'2Y-10Y spread flat ({spread_2y10y:.2f}%) - neutral Fed expectations'
                        }
            
            # VIX factor (+0.2 if high, -0.1 if low)
            vix_level = vix_data.get('level', 'normal')
            if vix_level == 'high':
                factors['vix'] = {'value': +0.2, 'reason': 'High VIX - risk-off sentiment (bullish for Gold as safe haven)'}
                bias_points += 0.2
            elif vix_level == 'low':
                factors['vix'] = {'value': -0.1, 'reason': 'Low VIX - risk-on sentiment (slightly bearish)'}
                bias_points -= 0.1
            
            # Clamp to -1.0 to +1.0
            bias_score = max(-1.0, min(1.0, bias_points))
            
            # Determine strength and direction
            if abs(bias_score) >= 0.7:
                strength = 'strong'
            elif abs(bias_score) >= 0.4:
                strength = 'moderate'
            else:
                strength = 'weak'
            
            direction = 'bullish' if bias_score > 0.1 else 'bearish' if bias_score < -0.1 else 'neutral'
            
            # Generate explanation
            explanation = self._generate_gold_explanation(bias_score, factors, dxy_data, us10y_data)
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': strength,
                'bias_direction': direction,
                'factors': factors,
                'explanation': explanation,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating Gold bias: {e}", exc_info=True)
            return self._empty_bias("XAUUSD", f"Error: {str(e)}")
    
    def _calculate_usd_pair_bias(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate bias for EURUSD or GBPUSD
        
        Factors:
        - DXY: Mirror (DXY up = EURUSD/GBPUSD down)
        - EU/UK yields: If diverging from US yields
        """
        if not self.market_indices:
            return self._empty_bias(symbol, "Market indices service unavailable")
        
        try:
            dxy_data = self.market_indices.get_dxy()
            
            factors = {}
            bias_points = 0.0
            
            # DXY factor (primary driver for USD pairs)
            dxy_trend = dxy_data.get('trend', 'neutral')
            if dxy_trend == 'up':
                factors['dxy'] = {'value': -0.5, 'reason': 'USD strengthening (bearish for ' + symbol + ')'}
                bias_points -= 0.5
            elif dxy_trend == 'down':
                factors['dxy'] = {'value': +0.5, 'reason': 'USD weakening (bullish for ' + symbol + ')'}
                bias_points += 0.5
            else:
                factors['dxy'] = {'value': 0.0, 'reason': 'DXY neutral'}
            
            # Fed expectations tracking (2Y-10Y spread) - affects USD strength
            if self.fred_service:
                spread_2y10y = self.fred_service.get_2y10y_spread()
                if spread_2y10y is not None:
                    # Inverted spread = recession signal → Fed likely to cut → USD weakens (bullish for EUR/GBP)
                    # Steep spread = growth expectations → Fed likely to hold/hike → USD strengthens (bearish for EUR/GBP)
                    if spread_2y10y < -0.2:
                        factors['fed_expectations'] = {
                            'value': +0.2,
                            'reason': f'2Y-10Y spread inverted ({spread_2y10y:.2f}%) - recession signal, Fed likely to cut (USD weakens, bullish for {symbol})'
                        }
                        bias_points += 0.2
                    elif spread_2y10y > 0.5:
                        factors['fed_expectations'] = {
                            'value': -0.2,
                            'reason': f'2Y-10Y spread steep ({spread_2y10y:.2f}%) - growth expectations, Fed likely to hold/hike (USD strengthens, bearish for {symbol})'
                        }
                        bias_points -= 0.2
                    else:
                        factors['fed_expectations'] = {
                            'value': 0.0,
                            'reason': f'2Y-10Y spread flat ({spread_2y10y:.2f}%) - neutral Fed expectations'
                        }
            
            # Note: EU/UK yields could be added if Yahoo Finance symbols available
            # For now, DXY and Fed expectations are the primary drivers
            
            bias_score = max(-1.0, min(1.0, bias_points))
            strength = 'strong' if abs(bias_score) >= 0.5 else 'moderate' if abs(bias_score) >= 0.3 else 'weak'
            direction = 'bullish' if bias_score > 0.1 else 'bearish' if bias_score < -0.1 else 'neutral'
            
            # Generate explanation with Fed expectations if available
            fed_context = ""
            if self.fred_service:
                spread_2y10y = self.fred_service.get_2y10y_spread()
                if spread_2y10y is not None:
                    if spread_2y10y < -0.2:
                        fed_context = f" (Fed expectations: inverted yield curve, likely to cut)"
                    elif spread_2y10y > 0.5:
                        fed_context = f" (Fed expectations: steep curve, likely to hold/hike)"
            
            explanation = f"{symbol}: DXY {dxy_data.get('trend', 'neutral')}{fed_context} → Bias {direction} ({bias_score:+.2f})"
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': strength,
                'bias_direction': direction,
                'factors': factors,
                'explanation': explanation,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating {symbol} bias: {e}", exc_info=True)
            return self._empty_bias(symbol, f"Error: {str(e)}")
    
    def _calculate_usdjpy_bias(self) -> Dict[str, Any]:
        """
        Calculate bias for USDJPY
        
        Factors:
        - US-JP yield spread (primary driver)
        - DXY (secondary)
        """
        if not self.market_indices:
            return self._empty_bias("USDJPY", "Market indices service unavailable")
        
        try:
            us10y_data = self.market_indices.get_us10y()
            dxy_data = self.market_indices.get_dxy()
            
            factors = {}
            bias_points = 0.0
            
            # US10Y factor (wider spread = bullish USDJPY)
            us10y_trend = us10y_data.get('trend', 'neutral')
            if us10y_trend == 'up':
                factors['us10y'] = {'value': +0.4, 'reason': 'US yields rising → Wider US-JP spread (bullish USDJPY)'}
                bias_points += 0.4
            elif us10y_trend == 'down':
                factors['us10y'] = {'value': -0.4, 'reason': 'US yields falling → Narrower spread (bearish USDJPY)'}
                bias_points -= 0.4
            
            # DXY factor (secondary)
            dxy_trend = dxy_data.get('trend', 'neutral')
            if dxy_trend == 'up':
                factors['dxy'] = {'value': +0.3, 'reason': 'USD strengthening (supportive)'}
                bias_points += 0.3
            elif dxy_trend == 'down':
                factors['dxy'] = {'value': -0.3, 'reason': 'USD weakening'}
                bias_points -= 0.3
            
            bias_score = max(-1.0, min(1.0, bias_points))
            strength = 'strong' if abs(bias_score) >= 0.6 else 'moderate' if abs(bias_score) >= 0.3 else 'weak'
            direction = 'bullish' if bias_score > 0.1 else 'bearish' if bias_score < -0.1 else 'neutral'
            
            explanation = f"USDJPY: US yield spread {us10y_trend} → Bias {direction} ({bias_score:+.2f})"
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': strength,
                'bias_direction': direction,
                'factors': factors,
                'explanation': explanation,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating USDJPY bias: {e}", exc_info=True)
            return self._empty_bias("USDJPY", f"Error: {str(e)}")
    
    def _calculate_cross_pair_bias(self, symbol: str) -> Dict[str, Any]:
        """Calculate bias for GBPJPY or EURJPY (risk sentiment + yields)"""
        if not self.market_indices:
            return self._empty_bias(symbol, "Market indices service unavailable")
        
        try:
            vix_data = self.market_indices.get_vix()
            us10y_data = self.market_indices.get_us10y()
            
            factors = {}
            bias_points = 0.0
            
            # VIX factor (risk sentiment)
            vix_level = vix_data.get('level', 'normal')
            if vix_level == 'low':
                factors['vix'] = {'value': +0.3, 'reason': 'Low VIX - risk-on (supportive for carry trades like ' + symbol + ')'}
                bias_points += 0.3
            elif vix_level == 'high':
                factors['vix'] = {'value': -0.3, 'reason': 'High VIX - risk-off (bearish for carry trades)'}
                bias_points -= 0.3
            
            # Yield factor (if US yields rising, supports carry trades)
            us10y_trend = us10y_data.get('trend', 'neutral')
            if us10y_trend == 'up':
                factors['yields'] = {'value': +0.2, 'reason': 'Rising yields - supportive'}
                bias_points += 0.2
            
            bias_score = max(-1.0, min(1.0, bias_points))
            strength = 'moderate' if abs(bias_score) >= 0.3 else 'weak'
            direction = 'bullish' if bias_score > 0.1 else 'bearish' if bias_score < -0.1 else 'neutral'
            
            explanation = f"{symbol}: Risk sentiment {vix_level} → Bias {direction} ({bias_score:+.2f})"
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': strength,
                'bias_direction': direction,
                'factors': factors,
                'explanation': explanation,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating {symbol} bias: {e}", exc_info=True)
            return self._empty_bias(symbol, f"Error: {str(e)}")
    
    def _calculate_btc_bias(self) -> Dict[str, Any]:
        """
        Calculate bias for BTCUSD
        
        Factors:
        - NASDAQ correlation (risk-on proxy)
        - VIX (risk sentiment)
        - DXY (inverse, weaker USD = bullish BTC)
        """
        if not self.market_indices:
            return self._empty_bias("BTCUSD", "Market indices service unavailable")
        
        try:
            nasdaq_data = self.market_indices.get_nasdaq()
            vix_data = self.market_indices.get_vix()
            dxy_data = self.market_indices.get_dxy()
            
            factors = {}
            bias_points = 0.0
            
            # NASDAQ factor (primary for BTCUSD)
            nasdaq_trend = nasdaq_data.get('trend', 'neutral')
            if nasdaq_trend == 'up':
                factors['nasdaq'] = {'value': +0.4, 'reason': 'NASDAQ rising - risk-on environment (bullish for BTCUSD)'}
                bias_points += 0.4
            elif nasdaq_trend == 'down':
                factors['nasdaq'] = {'value': -0.4, 'reason': 'NASDAQ falling - risk-off (bearish for BTCUSD)'}
                bias_points -= 0.4
            
            # Correlation check (if strongly correlated, weight NASDAQ higher)
            try:
                correlation = self.market_indices.get_nasdaq_correlation("BTCUSD")
                if correlation.get('strength') == 'strong':
                    # Amplify NASDAQ factor if strongly correlated
                    nasdaq_weight = factors['nasdaq'].get('value', 0) * 1.5
                    factors['nasdaq']['value'] = max(-0.6, min(0.6, nasdaq_weight))
                    bias_points = factors['nasdaq']['value']
            except Exception:
                pass  # Correlation unavailable, continue with basic trend
            
            # VIX factor
            vix_level = vix_data.get('level', 'normal')
            if vix_level == 'low':
                factors['vix'] = {'value': +0.2, 'reason': 'Low VIX - risk-on (supportive)'}
                bias_points += 0.2
            elif vix_level == 'high':
                factors['vix'] = {'value': -0.2, 'reason': 'High VIX - risk-off'}
                bias_points -= 0.2
            
            # DXY factor (inverse)
            dxy_trend = dxy_data.get('trend', 'neutral')
            if dxy_trend == 'down':
                factors['dxy'] = {'value': +0.2, 'reason': 'USD weakening (bullish for BTC)'}
                bias_points += 0.2
            elif dxy_trend == 'up':
                factors['dxy'] = {'value': -0.2, 'reason': 'USD strengthening'}
                bias_points -= 0.2
            
            bias_score = max(-1.0, min(1.0, bias_points))
            strength = 'strong' if abs(bias_score) >= 0.6 else 'moderate' if abs(bias_score) >= 0.3 else 'weak'
            direction = 'bullish' if bias_score > 0.1 else 'bearish' if bias_score < -0.1 else 'neutral'
            
            explanation = f"BTCUSD: NASDAQ {nasdaq_trend}, VIX {vix_level} → Bias {direction} ({bias_score:+.2f})"
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': strength,
                'bias_direction': direction,
                'factors': factors,
                'explanation': explanation,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating BTCUSD bias: {e}", exc_info=True)
            return self._empty_bias("BTCUSD", f"Error: {str(e)}")
    
    def _calculate_generic_bias(self, symbol: str) -> Dict[str, Any]:
        """Calculate generic bias (DXY-based for USD pairs)"""
        if not self.market_indices:
            return self._empty_bias(symbol, "Market indices service unavailable")
        
        try:
            dxy_data = self.market_indices.get_dxy()
            dxy_trend = dxy_data.get('trend', 'neutral')
            
            if dxy_trend == 'up':
                bias_score = -0.5  # USD strengthening = bearish for non-USD base currency
            elif dxy_trend == 'down':
                bias_score = +0.5
            else:
                bias_score = 0.0
            
            return {
                'bias_score': round(bias_score, 2),
                'bias_strength': 'moderate',
                'bias_direction': 'bullish' if bias_score > 0 else 'bearish' if bias_score < 0 else 'neutral',
                'factors': {'dxy': {'value': bias_score, 'reason': f'DXY trend: {dxy_trend}'}},
                'explanation': f"{symbol}: DXY-based bias ({bias_score:+.2f})",
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._empty_bias(symbol, f"Error: {str(e)}")
    
    def _generate_gold_explanation(self, bias_score: float, factors: Dict, dxy_data: Dict, us10y_data: Dict) -> str:
        """Generate human-readable explanation for Gold bias"""
        dxy_trend = dxy_data.get('trend', 'neutral')
        us10y_trend = us10y_data.get('trend', 'neutral')
        
        # Get Fed expectations from factors if available
        fed_expectations = factors.get('fed_expectations', {})
        fed_reason = fed_expectations.get('reason', '')
        
        fed_context = ""
        if fed_reason and 'recession signal' in fed_reason.lower():
            fed_context = " Recession risk (inverted yield curve) increases Gold's safe-haven appeal."
        elif fed_reason and 'growth expectations' in fed_reason.lower():
            fed_context = " Growth expectations (steep curve) reduce Gold's safe-haven appeal."
        
        if bias_score < -0.5:
            return f"Rising 10Y ({us10y_trend}) and firm DXY ({dxy_trend}) maintain downside pressure on XAUUSD{fed_context} — only take shorts unless structure strongly flips."
        elif bias_score > 0.5:
            return f"Falling 10Y ({us10y_trend}) and weakening DXY ({dxy_trend}) support XAUUSD{fed_context} — bullish bias valid unless structure breaks down."
        else:
            return f"Mixed macro signals (DXY: {dxy_trend}, US10Y: {us10y_trend}){fed_context} — rely on technical analysis for XAUUSD direction."
    
    def _empty_bias(self, symbol: str, reason: str) -> Dict[str, Any]:
        """Return empty bias result"""
        return {
            'bias_score': 0.0,
            'bias_strength': 'unknown',
            'bias_direction': 'neutral',
            'factors': {},
            'explanation': f"{symbol}: {reason}",
            'timestamp': datetime.now().isoformat()
        }


# Factory function
def create_macro_bias_calculator(market_indices_service=None, fred_service=None) -> MacroBiasCalculator:
    """Create MacroBiasCalculator instance"""
    return MacroBiasCalculator(market_indices_service, fred_service)


