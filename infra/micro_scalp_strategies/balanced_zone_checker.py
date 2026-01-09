"""
Balanced Zone Strategy Checker

Implements balanced zone strategy with:
- Compression block (inside bars)
- Equal highs/lows
- VWAP + mid-range alignment
- Fade or breakout entry types
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from infra.micro_scalp_strategies.base_strategy_checker import BaseStrategyChecker
from infra.micro_scalp_conditions import ConditionCheckResult

logger = logging.getLogger(__name__)


class BalancedZoneChecker(BaseStrategyChecker):
    """
    Strategy checker for Balanced Zone Scalp.
    
    Entry Logic:
    - Compression block (inside bars / tight structure)
    - Equal highs/lows detected
    - VWAP + mid-range alignment
    - Fade mini-extremes OR breakout from compression
    """
    
    def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                              current_price: float, vwap: float, 
                              atr1: Optional[float]) -> Dict[str, Any]:
        """
        Balanced Zone-specific location filter with EMA-VWAP equilibrium check.
        
        Checks:
        - Compression block (inside bars)
        - Equal highs/lows detected
        - VWAP + mid-range alignment
        - EMA-VWAP equilibrium (for fade entries)
        """
        # Check compression block (inside bars)
        # ENHANCED: Use M1-M5 multi-timeframe compression if available
        compression = False
        if hasattr(self, '_current_snapshot') and self._current_snapshot:
            m5_candles = self._current_snapshot.get('m5_candles', [])
            if m5_candles:
                compression = self._check_compression_block_mtf(candles, m5_candles, self._current_snapshot)
            else:
                compression = self._check_compression_block(candles, atr1)
        else:
            compression = self._check_compression_block(candles, atr1)
        
        # Check equal highs/lows
        equal_highs = False
        equal_lows = False
        if self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                liquidity_zones = analysis.get('liquidity_zones', {})
                equal_highs = liquidity_zones.get('equal_highs_detected', False)
                equal_lows = liquidity_zones.get('equal_lows_detected', False)
            except Exception as e:
                logger.debug(f"Error checking equal highs/lows: {e}")
        
        # Check VWAP + mid-range alignment
        vwap_alignment = False
        if vwap and len(candles) >= 20:
            intraday_high = max(c.get('high', 0) for c in candles[-20:])
            intraday_low = min(c.get('low', 0) for c in candles[-20:])
            mid_range = (intraday_high + intraday_low) / 2
            if mid_range > 0:
                vwap_alignment = abs(vwap - mid_range) / mid_range < 0.001  # Within 0.1%
        
        # Detect entry type (fade or breakout)
        entry_type = self._detect_entry_type_from_candles(candles)
        
        # NEW: EMA(20)-VWAP distance filter for fade entries
        if entry_type == 'fade':
            # For fade entries, require EMA-VWAP alignment (equilibrium)
            if len(candles) >= 20 and vwap:
                # Calculate EMA(20)
                ema20 = self._calculate_ema(candles, period=20)
                
                if ema20:
                    # Check EMA-VWAP distance
                    ema_vwap_distance = abs(ema20 - vwap) / vwap if vwap > 0 else float('inf')
                    
                    # Equilibrium: EMA and VWAP within threshold
                    equilibrium_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('ema_vwap_equilibrium_threshold', 0.001)
                    
                    if ema_vwap_distance > equilibrium_threshold:
                        reasons = [f"EMA-VWAP distance {ema_vwap_distance:.4f} > {equilibrium_threshold} (not in equilibrium)"]
                        return {
                            'passed': False,
                            'compression': compression,
                            'equal_highs': equal_highs,
                            'equal_lows': equal_lows,
                            'vwap_alignment': vwap_alignment,
                            'entry_type': entry_type,
                            'reasons': reasons
                        }
        
        # Return location filter result
        passed = compression and (equal_highs or equal_lows) and vwap_alignment
        
        reasons = []
        if not compression:
            reasons.append('No compression block')
        if not (equal_highs or equal_lows):
            reasons.append('No equal highs/lows')
        if not vwap_alignment:
            reasons.append('VWAP not aligned with mid-range')
        
        return {
            'passed': passed,
            'compression': compression,
            'equal_highs': equal_highs,
            'equal_lows': equal_lows,
            'vwap_alignment': vwap_alignment,
            'entry_type': entry_type,
            'reasons': reasons
        }
    
    def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                             current_price: float, vwap: float, atr1: Optional[float],
                             btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Balanced Zone-specific candle signals.
        
        Checks:
        - Primary (fade): Mini-extreme tap + opposite CHOCH
        - OR Primary (breakout): Inside bar/coil break + volume
        - Secondary: Compression confirmation
        """
        primary_triggers = []
        secondary_confluence = []
        volume_on_breakout = False
        
        # Get entry type from location filter (stored in snapshot context)
        entry_type = 'fade'  # Default
        if hasattr(self, '_current_snapshot') and self._current_snapshot:
            location_details = self._current_snapshot.get('location', {})
            if isinstance(location_details, dict):
                entry_type = location_details.get('entry_type', 'fade')
        
        if entry_type == 'fade':
            # Primary: Mini-extreme tap + opposite CHOCH
            if self.m1_analyzer:
                try:
                    analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                    choch_bos = analysis.get('choch_bos', {})
                    choch_detected = choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False)
                    choch_direction = choch_bos.get('direction', '')
                    
                    if choch_detected:
                        # Check if price is at mini-extreme
                        if len(candles) >= 5:
                            recent_high = max(c.get('high', current_price) for c in candles[-5:])
                            recent_low = min(c.get('low', current_price) for c in candles[-5:])
                            
                            # Check if price is near extreme
                            distance_to_high = abs(recent_high - current_price)
                            distance_to_low = abs(current_price - recent_low)
                            
                            if distance_to_high < distance_to_low:
                                # Near high, expect bearish CHOCH
                                if 'BEARISH' in str(choch_direction).upper() or 'bear' in str(choch_direction).lower():
                                    primary_triggers.append('FADE_EXTREME_BEARISH_CHOCH')
                            else:
                                # Near low, expect bullish CHOCH
                                if 'BULLISH' in str(choch_direction).upper() or 'bull' in str(choch_direction).lower():
                                    primary_triggers.append('FADE_EXTREME_BULLISH_CHOCH')
                except Exception as e:
                    logger.debug(f"Error checking fade signals: {e}")
        else:  # breakout
            # Primary: Inside bar/coil break + volume
            if len(candles) >= 3:
                compression_high = max(c.get('high', 0) for c in candles[-3:])
                compression_low = min(c.get('low', 0) for c in candles[-3:])
                last_close = candles[-1].get('close', 0)
                
                # Check if price broke out
                if last_close > compression_high or last_close < compression_low:
                    primary_triggers.append('COMPRESSION_BREAKOUT')
                    
                    # Check volume on breakout
                    volume_spike = self._check_volume_spike(candles)
                    if volume_spike:
                        volume_on_breakout = True
                        secondary_confluence.append('VOLUME_ON_BREAKOUT')
        
        # Secondary: Compression confirmation
        if len(candles) >= 3:
            compression = self._check_compression_block(candles, atr1)
            if compression:
                secondary_confluence.append('COMPRESSION_CONFIRMED')
        
        return {
            'primary_count': len(primary_triggers),
            'secondary_count': len(secondary_confluence),
            'primary_triggers': primary_triggers,
            'secondary_confluence': secondary_confluence,
            'volume_on_breakout': volume_on_breakout
        }
    
    def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                                   current_price: float, vwap: float, atr1: Optional[float],
                                   location_result: Dict[str, Any],
                                   signal_result: Dict[str, Any]) -> float:
        """
        Balanced Zone-specific confluence scoring.
        
        Uses strategy-specific weights from config.
        """
        # Get strategy-specific weights
        weights = self.config.get('regime_detection', {}).get('confluence_weights', {}).get('balanced_zone', {})
        
        # Default weights if not configured
        default_weights = {
            'compression_quality': 2.0,
            'equal_highs_lows': 2.0,
            'vwap_alignment': 2.0,
            'volume_on_breakout': 1.0,
            'fade_quality': 1.0
        }
        
        # Use configured weights or defaults
        w_compression = weights.get('compression_quality', default_weights['compression_quality'])
        w_equals = weights.get('equal_highs_lows', default_weights['equal_highs_lows'])
        w_vwap = weights.get('vwap_alignment', default_weights['vwap_alignment'])
        w_volume = weights.get('volume_on_breakout', default_weights['volume_on_breakout'])
        w_fade = weights.get('fade_quality', default_weights['fade_quality'])
        
        score = 0.0
        
        # Compression quality (0-2)
        if location_result.get('compression', False):
            score += 2.0 * w_compression
        
        # Equal highs/lows (0-2)
        equal_highs = location_result.get('equal_highs', False)
        equal_lows = location_result.get('equal_lows', False)
        if equal_highs and equal_lows:
            score += 2.0 * w_equals
        elif equal_highs or equal_lows:
            score += 1.0 * w_equals
        
        # VWAP alignment (0-2)
        if location_result.get('vwap_alignment', False):
            score += 2.0 * w_vwap
        
        # Volume on breakout (0-1)
        if signal_result.get('volume_on_breakout', False):
            score += 1.0 * w_volume
        
        # Fade quality (0-1)
        if 'FADE_EXTREME' in ' '.join(signal_result.get('primary_triggers', [])):
            score += 1.0 * w_fade
        
        return score
    
    def generate_trade_idea(self, snapshot: Dict[str, Any], 
                           result: ConditionCheckResult) -> Optional[Dict[str, Any]]:
        """
        Generate Balanced Zone trade idea.
        
        Entry types:
        - Fade: Mean reversion from mini-extremes
        - Breakout: Compression breakout with volume
        """
        symbol = snapshot.get('symbol', '')
        current_price = snapshot.get('current_price', 0)
        atr1 = snapshot.get('atr1')
        candles = snapshot.get('candles', [])
        
        # Get entry type from result details
        entry_type = result.details.get('entry_type', 'fade')
        
        if not entry_type:
            # Fallback: detect from candles
            if len(candles) >= 3:
                compression_high = max(c.get('high', 0) for c in candles[-3:])
                compression_low = min(c.get('low', 0) for c in candles[-3:])
                last_close = candles[-1].get('close', 0)
                
                if last_close > compression_high or last_close < compression_low:
                    entry_type = 'breakout'
                else:
                    entry_type = 'fade'
            else:
                entry_type = 'fade'
        
        if entry_type == 'fade':
            # Fade mini-extremes
            direction = self._get_fade_direction(candles, current_price)
            entry_price = current_price
            
            # SL: Super tight (0.10-0.20%)
            if symbol.upper().startswith('BTC'):
                sl_distance = current_price * 0.0015  # 0.15%
                sl = entry_price - sl_distance if direction == 'BUY' else entry_price + sl_distance
            else:  # XAU
                sl = entry_price - 2 if direction == 'BUY' else entry_price + 2  # 2 points
            
            # TP: 1.0R to 1.5R (small, trading noise)
            risk = abs(entry_price - sl)
            tp = entry_price + (risk * 1.25) if direction == 'BUY' else entry_price - (risk * 1.25)
        else:  # breakout
            # Compression breakout
            direction = self._get_breakout_direction(candles)
            last_candle = candles[-1] if candles else {}
            entry_price = last_candle.get('high', current_price) if direction == 'BUY' else last_candle.get('low', current_price)
            
            # SL: Inside bar low/high
            inside_bar_low = min(c.get('low', current_price) for c in candles[-3:]) if len(candles) >= 3 else current_price
            inside_bar_high = max(c.get('high', current_price) for c in candles[-3:]) if len(candles) >= 3 else current_price
            sl = inside_bar_low if direction == 'BUY' else inside_bar_high
            
            # TP: 1.0R to 1.5R
            risk = abs(entry_price - sl)
            tp = entry_price + (risk * 1.25) if direction == 'BUY' else entry_price - (risk * 1.25)
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'volume': 0.01,
            'atr1': atr1,
            'strategy': 'balanced_zone',
            'confluence_score': result.confluence_score,
            'is_aplus': result.is_aplus_setup
        }
    
    def _calculate_ema(self, candles: List[Dict], period: int) -> Optional[float]:
        """Calculate EMA(period) from candles (no DataFrame dependency)"""
        if len(candles) < period:
            return None
        
        try:
            # Get closes
            closes = [c.get('close', 0) for c in candles[-period:]]
            
            if not closes or all(c == 0 for c in closes):
                return None
            
            # Calculate EMA manually (no pandas dependency)
            multiplier = 2.0 / (period + 1)
            ema = closes[0]  # Start with first close
            
            for close in closes[1:]:
                ema = (close * multiplier) + (ema * (1 - multiplier))
            
            return ema
        except Exception as e:
            logger.debug(f"Error calculating EMA: {e}")
            return None
    
    def _detect_entry_type_from_candles(self, candles: List[Dict[str, Any]]) -> str:
        """Detect entry type (fade or breakout) for balanced zone from candles"""
        if len(candles) < 3:
            return 'fade'
        
        compression_high = max(c.get('high', 0) for c in candles[-3:])
        compression_low = min(c.get('low', 0) for c in candles[-3:])
        last_close = candles[-1].get('close', 0)
        
        if last_close > compression_high or last_close < compression_low:
            return 'breakout'
        else:
            return 'fade'
    
    def _get_fade_direction(self, candles: List[Dict], current_price: float) -> str:
        """Determine fade direction (opposite of mini-extreme)"""
        if len(candles) < 5:
            return 'UNKNOWN'
        
        # Find mini-extreme (recent high or low)
        recent_high = max(c.get('high', current_price) for c in candles[-5:])
        recent_low = min(c.get('low', current_price) for c in candles[-5:])
        
        # Check which extreme is closer
        distance_to_high = abs(recent_high - current_price)
        distance_to_low = abs(current_price - recent_low)
        
        if distance_to_high < distance_to_low:
            # Near high, fade down (SELL)
            return 'SELL'
        else:
            # Near low, fade up (BUY)
            return 'BUY'
    
    def _get_breakout_direction(self, candles: List[Dict]) -> str:
        """Determine breakout direction from compression"""
        if len(candles) < 3:
            return 'UNKNOWN'
        
        # Check if price broke above or below compression range
        compression_high = max(c.get('high', 0) for c in candles[-3:])
        compression_low = min(c.get('low', 0) for c in candles[-3:])
        last_close = candles[-1].get('close', 0)
        
        # Check breakout direction
        if last_close > compression_high:
            return 'BUY'
        elif last_close < compression_low:
            return 'SELL'
        else:
            return 'UNKNOWN'

