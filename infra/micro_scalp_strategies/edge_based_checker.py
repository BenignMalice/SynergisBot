"""
Edge-Based Strategy Checker

Fallback strategy checker that uses the existing generic micro-scalp logic.
This maintains backward compatibility and serves as a fallback when no regime is detected.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from infra.micro_scalp_strategies.base_strategy_checker import BaseStrategyChecker
from infra.micro_scalp_conditions import ConditionCheckResult

logger = logging.getLogger(__name__)


class EdgeBasedChecker(BaseStrategyChecker):
    """
    Edge-Based strategy checker (fallback).
    
    Uses the existing generic micro-scalp logic from MicroScalpConditionsChecker.
    This is the fallback strategy when no specific regime is detected.
    
    Note: This checker uses the base class implementations of _check_location_filter()
    and _check_candle_signals() which provide generic edge detection logic.
    """
    
    # Note: EdgeBasedChecker does NOT override _check_location_filter, _check_candle_signals,
    # or _calculate_confluence_score. This allows it to use the base class implementations
    # from MicroScalpConditionsChecker, which provide generic edge detection logic.
    
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """
        Generate Edge-Based trade idea.
        
        Uses generic trade idea generation logic similar to the existing
        MicroScalpEngine._generate_trade_idea() method.
        """
        symbol = snapshot.get('symbol', '')
        current_price = snapshot.get('current_price', 0)
        atr1 = snapshot.get('atr1')
        candles = snapshot.get('candles', [])
        
        if not symbol or current_price == 0:
            return None
        
        # Determine direction from signals
        direction = self._determine_direction_from_signals(snapshot, result)
        
        if direction == 'UNKNOWN':
            return None
        
        # Get symbol-specific rules
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        
        # Calculate SL/TP (ultra-tight)
        sl_range = rules.get('sl_range', [0.5, 1.2])
        tp_range = rules.get('tp_range', [1.0, 2.0])
        
        if atr1 and atr1 > 0:
            # Use ATR-based SL/TP
            sl_distance = atr1 * (sl_range[0] + sl_range[1]) / 2  # Average
            tp_distance = atr1 * (tp_range[0] + tp_range[1]) / 2  # Average
        else:
            # Fallback to percentage-based
            if symbol.upper().startswith('BTC'):
                sl_distance = current_price * 0.001  # 0.1%
                tp_distance = current_price * 0.002  # 0.2%
            else:  # XAU
                sl_distance = current_price * 0.0005  # 0.05%
                tp_distance = current_price * 0.001  # 0.1%
        
        # Entry price (current price)
        entry_price = current_price
        
        # Calculate SL/TP
        if direction == 'BUY':
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:  # SELL
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'sl': stop_loss,
            'tp': take_profit,
            'volume': 0.01,
            'atr1': atr1,
            'strategy': 'edge_based',
            'confluence_score': result.confluence_score,
            'is_aplus': result.is_aplus_setup
        }
    
    def _determine_direction_from_signals(self, snapshot: Dict[str, Any],
                                          result: ConditionCheckResult) -> str:
        """
        Determine trade direction from signals (similar to MicroScalpEngine._determine_direction).
        
        Priority:
        1. CHOCH direction
        2. Sweep direction
        3. Price position relative to VWAP
        """
        symbol = snapshot.get('symbol', '')
        candles = snapshot.get('candles', [])
        current_price = snapshot.get('current_price', 0)
        vwap = snapshot.get('vwap', 0)
        atr1 = snapshot.get('atr1')
        
        # 1. Check CHOCH direction
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                choch_bos = analysis.get('choch_bos', {})
                choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
                choch_direction = choch_bos.get('direction', '')
                
                if choch_detected:
                    if 'BULLISH' in str(choch_direction).upper() or 'bull' in str(choch_direction).lower():
                        return 'BUY'
                    elif 'BEARISH' in str(choch_direction).upper() or 'bear' in str(choch_direction).lower():
                        return 'SELL'
            except Exception as e:
                logger.debug(f"Error checking CHOCH for direction: {e}")
        
        # 2. Check sweep direction
        if atr1 and len(candles) >= 5:
            try:
                sweep_result = self.sweep_detector.detect_micro_sweep(candles, atr1)
                if sweep_result.sweep_detected:
                    if sweep_result.sweep_direction == 'BULLISH':
                        return 'BUY'
                    elif sweep_result.sweep_direction == 'BEARISH':
                        return 'SELL'
            except Exception as e:
                logger.debug(f"Error checking sweep for direction: {e}")
        
        # 3. Fallback: Price position relative to VWAP
        if vwap > 0:
            if current_price < vwap:
                return 'BUY'  # Price below VWAP, expect bounce up
            else:
                return 'SELL'  # Price above VWAP, expect bounce down
        
        return 'UNKNOWN'

