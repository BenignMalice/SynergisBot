"""
Micro Liquidity Sweep Detector for Micro-Scalp Strategy

Detects micro liquidity sweeps on M1 timeframe:
- Price breaks above/below local high/low (last 5-10 M1 candles)
- Validates return below/above the broken level (rejection)
- Confirms with wick rejection or volume spike
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MicroSweepResult:
    """Result of micro liquidity sweep detection"""
    sweep_detected: bool
    direction: Optional[str]  # "BULLISH" or "BEARISH"
    sweep_level: float  # Price level that was swept
    sweep_candle_index: int  # Index of candle that made the sweep
    return_confirmed: bool  # Whether price returned below/above the level
    confidence: float  # Confidence score (0.0-1.0)
    wick_rejection: bool  # Whether wick rejection confirmed the sweep
    volume_spike: bool  # Whether volume spike confirmed the sweep


class MicroLiquiditySweepDetector:
    """
    Detects micro liquidity sweeps on M1 timeframe.
    
    A micro sweep is:
    1. Price breaks above local high (M1 HH) or below local low (M1 LL)
    2. Price returns below/above the broken level (rejection)
    3. Confirmed by wick rejection or volume spike
    """
    
    def __init__(self, lookback: int = 10, min_return_candles: int = 1):
        """
        Initialize Micro Liquidity Sweep Detector.
        
        Args:
            lookback: Number of M1 candles to look back for local high/low (default: 10)
            min_return_candles: Minimum candles to confirm return (default: 1)
        """
        self.lookback = lookback
        self.min_return_candles = min_return_candles
    
    def detect_micro_sweep(self, candles: List[Dict[str, Any]], 
                          atr: Optional[float] = None) -> MicroSweepResult:
        """
        Detect micro liquidity sweep from M1 candles.
        
        Args:
            candles: List of M1 candle dicts with keys: 'time', 'open', 'high', 'low', 'close', 'volume'
            atr: Optional ATR value for validation
        
        Returns:
            MicroSweepResult with sweep detection details
        """
        if len(candles) < self.lookback + 2:
            return MicroSweepResult(
                sweep_detected=False,
                direction=None,
                sweep_level=0.0,
                sweep_candle_index=-1,
                return_confirmed=False,
                confidence=0.0,
                wick_rejection=False,
                volume_spike=False
            )
        
        # Get recent candles (last lookback + 2 for comparison)
        recent_candles = candles[-(self.lookback + 2):]
        
        # Find local high and low in lookback period (excluding last candle)
        lookback_candles = recent_candles[:-1]
        local_high = max(c['high'] for c in lookback_candles)
        local_low = min(c['low'] for c in lookback_candles)
        
        # Get last candle (potential sweep candle)
        last_candle = recent_candles[-1]
        
        # Check for bullish sweep (breaks above local high, then returns below)
        bull_sweep = self._check_bullish_sweep(
            last_candle, local_high, recent_candles, atr
        )
        
        # Check for bearish sweep (breaks below local low, then returns above)
        bear_sweep = self._check_bearish_sweep(
            last_candle, local_low, recent_candles, atr
        )
        
        # Return the stronger signal
        if bull_sweep['detected'] and bear_sweep['detected']:
            # Both detected, choose the one with higher confidence
            if bull_sweep['confidence'] >= bear_sweep['confidence']:
                return MicroSweepResult(
                    sweep_detected=True,
                    direction="BULLISH",
                    sweep_level=local_high,
                    sweep_candle_index=len(candles) - 1,
                    return_confirmed=bull_sweep['return_confirmed'],
                    confidence=bull_sweep['confidence'],
                    wick_rejection=bull_sweep['wick_rejection'],
                    volume_spike=bull_sweep['volume_spike']
                )
            else:
                return MicroSweepResult(
                    sweep_detected=True,
                    direction="BEARISH",
                    sweep_level=local_low,
                    sweep_candle_index=len(candles) - 1,
                    return_confirmed=bear_sweep['return_confirmed'],
                    confidence=bear_sweep['confidence'],
                    wick_rejection=bear_sweep['wick_rejection'],
                    volume_spike=bear_sweep['volume_spike']
                )
        elif bull_sweep['detected']:
            return MicroSweepResult(
                sweep_detected=True,
                direction="BULLISH",
                sweep_level=local_high,
                sweep_candle_index=len(candles) - 1,
                return_confirmed=bull_sweep['return_confirmed'],
                confidence=bull_sweep['confidence'],
                wick_rejection=bull_sweep['wick_rejection'],
                volume_spike=bull_sweep['volume_spike']
            )
        elif bear_sweep['detected']:
            return MicroSweepResult(
                sweep_detected=True,
                direction="BEARISH",
                sweep_level=local_low,
                sweep_candle_index=len(candles) - 1,
                return_confirmed=bear_sweep['return_confirmed'],
                confidence=bear_sweep['confidence'],
                wick_rejection=bear_sweep['wick_rejection'],
                volume_spike=bear_sweep['volume_spike']
            )
        
        # No sweep detected
        return MicroSweepResult(
            sweep_detected=False,
            direction=None,
            sweep_level=0.0,
            sweep_candle_index=-1,
            return_confirmed=False,
            confidence=0.0,
            wick_rejection=False,
            volume_spike=False
        )
    
    def _check_bullish_sweep(self, candle: Dict[str, Any], local_high: float,
                            recent_candles: List[Dict[str, Any]],
                            atr: Optional[float]) -> Dict[str, Any]:
        """Check for bullish sweep (breaks above local high, returns below)"""
        # Check if price broke above local high
        if candle['high'] <= local_high:
            return {'detected': False, 'confidence': 0.0, 'return_confirmed': False,
                   'wick_rejection': False, 'volume_spike': False}
        
        # Price broke above local high - potential sweep
        break_distance = candle['high'] - local_high
        
        # Check if closed back below local high (rejection)
        return_confirmed = candle['close'] < local_high
        
        # Check for wick rejection (long upper wick)
        body_size = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        wick_rejection = False
        if body_size > 0:
            wick_ratio = upper_wick / body_size
            wick_rejection = wick_ratio >= 1.5  # Wick >= 1.5× body
        
        # Check for volume spike (if volume data available)
        volume_spike = False
        if 'volume' in candle and len(recent_candles) >= 5:
            avg_volume = sum(c.get('volume', 0) for c in recent_candles[:-1]) / (len(recent_candles) - 1)
            if avg_volume > 0:
                volume_ratio = candle['volume'] / avg_volume
                volume_spike = volume_ratio >= 1.5  # Volume >= 1.5× average
        
        # Calculate confidence
        confidence = 0.0
        if return_confirmed:
            confidence += 0.5  # Base confidence for return
        if wick_rejection:
            confidence += 0.3  # Wick rejection adds confidence
        if volume_spike:
            confidence += 0.2  # Volume spike adds confidence
        
        # Validate break distance (if ATR available)
        if atr is not None and atr > 0:
            break_atr_ratio = break_distance / atr
            if break_atr_ratio < 0.1:  # Too small, might be noise
                confidence *= 0.5
        
        return {
            'detected': True,
            'confidence': min(1.0, confidence),
            'return_confirmed': return_confirmed,
            'wick_rejection': wick_rejection,
            'volume_spike': volume_spike
        }
    
    def _check_bearish_sweep(self, candle: Dict[str, Any], local_low: float,
                            recent_candles: List[Dict[str, Any]],
                            atr: Optional[float]) -> Dict[str, Any]:
        """Check for bearish sweep (breaks below local low, returns above)"""
        # Check if price broke below local low
        if candle['low'] >= local_low:
            return {'detected': False, 'confidence': 0.0, 'return_confirmed': False,
                   'wick_rejection': False, 'volume_spike': False}
        
        # Price broke below local low - potential sweep
        break_distance = local_low - candle['low']
        
        # Check if closed back above local low (rejection)
        return_confirmed = candle['close'] > local_low
        
        # Check for wick rejection (long lower wick)
        body_size = abs(candle['close'] - candle['open'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        wick_rejection = False
        if body_size > 0:
            wick_ratio = lower_wick / body_size
            wick_rejection = wick_ratio >= 1.5  # Wick >= 1.5× body
        
        # Check for volume spike (if volume data available)
        volume_spike = False
        if 'volume' in candle and len(recent_candles) >= 5:
            avg_volume = sum(c.get('volume', 0) for c in recent_candles[:-1]) / (len(recent_candles) - 1)
            if avg_volume > 0:
                volume_ratio = candle['volume'] / avg_volume
                volume_spike = volume_ratio >= 1.5  # Volume >= 1.5× average
        
        # Calculate confidence
        confidence = 0.0
        if return_confirmed:
            confidence += 0.5  # Base confidence for return
        if wick_rejection:
            confidence += 0.3  # Wick rejection adds confidence
        if volume_spike:
            confidence += 0.2  # Volume spike adds confidence
        
        # Validate break distance (if ATR available)
        if atr is not None and atr > 0:
            break_atr_ratio = break_distance / atr
            if break_atr_ratio < 0.1:  # Too small, might be noise
                confidence *= 0.5
        
        return {
            'detected': True,
            'confidence': min(1.0, confidence),
            'return_confirmed': return_confirmed,
            'wick_rejection': wick_rejection,
            'volume_spike': volume_spike
        }
    
    def validate_post_sweep(self, candles: List[Dict[str, Any]], 
                          sweep_level: float, direction: str) -> bool:
        """
        Validate that price has returned after sweep.
        
        Args:
            candles: List of M1 candles (should include post-sweep candles)
            sweep_level: Price level that was swept
            direction: "BULLISH" or "BEARISH"
        
        Returns:
            True if return validated, False otherwise
        """
        if len(candles) < 2:
            return False
        
        last_candle = candles[-1]
        
        if direction == "BULLISH":
            # For bullish sweep, price should return below the swept high
            return last_candle['close'] < sweep_level
        else:  # BEARISH
            # For bearish sweep, price should return above the swept low
            return last_candle['close'] > sweep_level
    
    def get_sweep_confidence(self, sweep_result: MicroSweepResult) -> float:
        """
        Get confidence score for a sweep result.
        
        Args:
            sweep_result: MicroSweepResult from detect_micro_sweep
        
        Returns:
            Confidence score (0.0-1.0)
        """
        return sweep_result.confidence

