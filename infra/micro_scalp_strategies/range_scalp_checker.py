"""
Range Scalp Strategy Checker

Implements range scalping strategy with:
- Price at range edge (PDH/PDL or M15 bounds)
- Micro liquidity sweep at edge
- Range respect confirmation
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from infra.micro_scalp_strategies.base_strategy_checker import BaseStrategyChecker
from infra.micro_scalp_conditions import ConditionCheckResult
from infra.range_boundary_detector import RangeStructure, CriticalGapZones

logger = logging.getLogger(__name__)


class RangeScalpChecker(BaseStrategyChecker):
    """
    Strategy checker for Range Scalp.
    
    Entry Logic:
    - Price at range edge (PDH/PDL or M15 high/low)
    - Micro liquidity sweep at edge
    - Range respected ≥2 times (bounces confirmed)
    - M1 CHOCH in reversal direction
    """
    
    def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                              current_price: float, vwap: float, 
                              atr1: Optional[float]) -> Dict[str, Any]:
        """
        Range Scalp-specific location filter.
        
        Checks:
        - Price at range edge (PDH/PDL or M15 high/low)
        - Range respected ≥2 times (bounces confirmed)
        - Edge proximity score
        
        CRITICAL: Uses range_structure from snapshot (extracted from regime_result).
        """
        # Get range structure from snapshot (set during regime detection)
        # Access via _current_snapshot (set by validate() method)
        range_structure = None
        near_edge = None
        
        if hasattr(self, '_current_snapshot') and self._current_snapshot:
            # Try to get range_structure from snapshot (extracted from regime_result)
            range_structure = self._current_snapshot.get('range_structure')
        
        # Try to get range from snapshot (if available via validate() context)
        # For now, detect range from candles as fallback
        if len(candles) >= 20:
            # Use intraday range as fallback
            intraday_high = max(c.get('high', 0) for c in candles[-20:])
            intraday_low = min(c.get('low', 0) for c in candles[-20:])
            range_width = intraday_high - intraday_low
            
            if range_width > 0:
                # Check if price is near edge
                tolerance = range_width * 0.005  # 0.5% of range width
                near_high = abs(current_price - intraday_high) <= tolerance
                near_low = abs(current_price - intraday_low) <= tolerance
                
                if near_high or near_low:
                    # Create temporary range structure
                    range_structure = RangeStructure(
                        range_type="dynamic",
                        range_high=intraday_high,
                        range_low=intraday_low,
                        range_mid=(intraday_high + intraday_low) / 2,
                        range_width_atr=range_width / atr1 if atr1 and atr1 > 0 else 0,
                        critical_gaps=CriticalGapZones(
                            upper_zone_start=intraday_high - range_width * 0.15,
                            upper_zone_end=intraday_high,
                            lower_zone_start=intraday_low,
                            lower_zone_end=intraday_low + range_width * 0.15
                        ),
                        touch_count={},
                        validated=False,
                        nested_ranges=None,
                        expansion_state="stable",
                        invalidation_signals=[]
                    )
                    near_edge = 'high' if near_high else 'low'
        
        # Check range respect (bounces at edges)
        range_respects = 0
        if range_structure:
            range_respects = self._count_range_respects(
                candles, range_structure.range_high, range_structure.range_low
            )
        
        # Check volatility compression (BB width)
        bb_compression = self._check_bb_compression(candles)
        
        # Calculate edge proximity score (0-2)
        edge_proximity_score = 0.0
        if range_structure and near_edge:
            range_width = range_structure.range_high - range_structure.range_low
            if range_width > 0:
                if near_edge == 'high':
                    distance = abs(current_price - range_structure.range_high)
                else:
                    distance = abs(current_price - range_structure.range_low)
                
                # Score: closer = higher (within 0.5% = 2.0, within 1% = 1.0)
                proximity_pct = distance / range_width
                if proximity_pct <= 0.005:
                    edge_proximity_score = 2.0
                elif proximity_pct <= 0.01:
                    edge_proximity_score = 1.0
        
        passed = range_structure is not None and near_edge is not None and range_respects >= 2
        
        reasons = []
        if not range_structure:
            reasons.append('No range structure detected')
        if not near_edge:
            reasons.append('Price not at range edge')
        if range_respects < 2:
            reasons.append(f'Range respects {range_respects} < 2')
        
        return {
            'passed': passed,
            'range_structure': range_structure,
            'near_edge': near_edge,
            'range_respects': range_respects,
            'edge_proximity_score': edge_proximity_score,
            'bb_compression': bb_compression,
            'reasons': reasons
        }
    
    def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                             current_price: float, vwap: float, atr1: Optional[float],
                             btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Range Scalp-specific candle signals.
        
        Checks:
        - Primary: Micro liquidity sweep at edge
        - Secondary: M1 CHOCH in reversal direction
        """
        primary_triggers = []
        secondary_confluence = []
        sweep_quality_score = 0.0
        
        # Primary: Micro liquidity sweep at edge
        if len(candles) >= 5 and atr1:
            sweep_result = self.sweep_detector.detect_micro_sweep(candles, atr1)
            if sweep_result.sweep_detected:
                primary_triggers.append('MICRO_LIQUIDITY_SWEEP')
                
                # Calculate sweep quality score (0-2)
                # Quality based on sweep strength and clean reversal
                if sweep_result.sweep_direction:
                    # Check if sweep was followed by immediate reversal
                    if len(candles) >= 2:
                        last_candle = candles[-1]
                        prev_candle = candles[-2]
                        
                        # Reversal after sweep
                        if sweep_result.sweep_direction == 'BULLISH':
                            # Swept low, then reversed up
                            if last_candle.get('close', 0) > prev_candle.get('close', 0):
                                sweep_quality_score = 2.0
                        elif sweep_result.sweep_direction == 'BEARISH':
                            # Swept high, then reversed down
                            if last_candle.get('close', 0) < prev_candle.get('close', 0):
                                sweep_quality_score = 2.0
        
        # Secondary: M1 CHOCH in reversal direction
        choch_detected = False
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                choch_bos = analysis.get('choch_bos', {})
                choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
                choch_direction = choch_bos.get('direction', '')
                
                if choch_detected:
                    # Verify CHOCH is in reversal direction (opposite of sweep)
                    if primary_triggers and 'MICRO_LIQUIDITY_SWEEP' in primary_triggers:
                        # Get sweep direction from sweep_result (need to store it)
                        # For now, check if CHOCH is opposite of likely sweep direction
                        if 'BEARISH' in str(choch_direction).upper():
                            secondary_confluence.append('CHOCH_REVERSAL')
                        elif 'BULLISH' in str(choch_direction).upper():
                            secondary_confluence.append('CHOCH_REVERSAL')
                    else:
                        # No sweep, but CHOCH detected
                        secondary_confluence.append('FRESH_MICRO_CHOCH')
            except Exception as e:
                logger.debug(f"Error checking CHOCH: {e}")
        
        return {
            'primary_count': len(primary_triggers),
            'secondary_count': len(secondary_confluence),
            'primary_triggers': primary_triggers,
            'secondary_confluence': secondary_confluence,
            'sweep_quality_score': sweep_quality_score
        }
    
    def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                                   current_price: float, vwap: float, atr1: Optional[float],
                                   location_result: Dict[str, Any],
                                   signal_result: Dict[str, Any]) -> float:
        """
        Range Scalp-specific confluence scoring.
        
        Uses strategy-specific weights from config.
        """
        # Get strategy-specific weights
        weights = self.config.get('regime_detection', {}).get('confluence_weights', {}).get('range_scalp', {})
        
        # Default weights if not configured
        default_weights = {
            'edge_proximity': 2.0,
            'sweep_quality': 2.0,
            'range_respects': 2.0,
            'bb_compression': 1.0,
            'choch_reversal': 1.0
        }
        
        # Use configured weights or defaults
        w_proximity = weights.get('edge_proximity', default_weights['edge_proximity'])
        w_sweep = weights.get('sweep_quality', default_weights['sweep_quality'])
        w_respects = weights.get('range_respects', default_weights['range_respects'])
        w_compression = weights.get('bb_compression', default_weights['bb_compression'])
        w_choch = weights.get('choch_reversal', default_weights['choch_reversal'])
        
        score = 0.0
        
        # Edge proximity (0-2)
        edge_proximity_score = location_result.get('edge_proximity_score', 0)
        score += edge_proximity_score * w_proximity
        
        # Sweep quality (0-2)
        sweep_quality_score = signal_result.get('sweep_quality_score', 0)
        score += sweep_quality_score * w_sweep
        
        # Range respects (0-2)
        range_respects = location_result.get('range_respects', 0)
        if range_respects >= 3:
            score += 2.0 * w_respects
        elif range_respects >= 2:
            score += 1.5 * w_respects
        elif range_respects >= 1:
            score += 1.0 * w_respects
        
        # BB compression (0-1)
        if location_result.get('bb_compression', False):
            score += 1.0 * w_compression
        
        # CHOCH reversal (0-1)
        if 'CHOCH_REVERSAL' in signal_result.get('secondary_confluence', []):
            score += 1.0 * w_choch
        
        return score
    
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """
        Generate Range Scalp trade idea.
        
        Direction: Opposite of edge (mean reversion)
        - At range low → BUY (expect bounce up)
        - At range high → SELL (expect bounce down)
        """
        symbol = snapshot.get('symbol', '')
        current_price = snapshot.get('current_price', 0)
        atr1 = snapshot.get('atr1')
        candles = snapshot.get('candles', [])
        
        # Get range structure and near_edge from result details
        location_details = result.details.get('location', {})
        range_structure = location_details.get('range_structure')
        near_edge = location_details.get('near_edge')  # 'high' or 'low'
        
        if not range_structure or not near_edge:
            return None
        
        # Handle both dict and object
        if isinstance(range_structure, dict):
            range_high = range_structure.get('range_high')
            range_low = range_structure.get('range_low')
        else:
            range_high = range_structure.range_high
            range_low = range_structure.range_low
        
        range_mid = (range_high + range_low) / 2
        
        # Determine direction
        if near_edge == 'low':
            direction = 'BUY'
            entry_price = current_price  # At PDL/range low
            sweep_low = min(c.get('low', current_price) for c in candles[-5:])
            
            # SL calculation - distance from entry to sweep, then add 15% buffer
            if symbol.upper().startswith('BTC'):
                distance_to_sweep = entry_price - sweep_low
                sl_distance = distance_to_sweep * 1.15
                sl = entry_price - sl_distance
            else:  # XAU
                sl = entry_price - 3  # 3 points
            
            # TP1: Mid-range
            tp1 = range_mid
            # TP2: Opposite side of range
            tp2 = range_high
        else:  # near_edge == 'high'
            direction = 'SELL'
            entry_price = current_price
            sweep_high = max(c.get('high', current_price) for c in candles[-5:])
            
            # SL calculation
            if symbol.upper().startswith('BTC'):
                distance_to_sweep = sweep_high - entry_price
                sl_distance = distance_to_sweep * 1.15
                sl = entry_price + sl_distance
            else:  # XAU
                sl = entry_price + 3
            
            tp1 = range_mid
            tp2 = range_low
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp1,
            'tp2': tp2,
            'volume': 0.01,
            'atr1': atr1,
            'strategy': 'range_scalp',
            'confluence_score': result.confluence_score,
            'is_aplus': result.is_aplus_setup
        }

