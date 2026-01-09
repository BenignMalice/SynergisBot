"""
Micro-Scalp Regime Detector

Detects current market regime (VWAP Reversion, Range Scalp, Balanced Zone)
and assigns confidence scores for strategy routing.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from collections import deque
from datetime import datetime, timedelta

from infra.range_boundary_detector import RangeBoundaryDetector, RangeStructure

logger = logging.getLogger(__name__)


class MicroScalpRegimeDetector:
    """
    Detects market regime for adaptive micro-scalp strategy selection.
    
    Regimes:
    - VWAP Reversion: Price deviated from VWAP, mean reversion expected
    - Range Scalp: Price in tight range, bouncing at edges
    - Balanced Zone: Low volatility, equilibrium state, fade opportunities
    """
    
    def __init__(self, config: Dict[str, Any], 
                 range_detector: RangeBoundaryDetector,
                 volatility_filter=None,
                 m1_analyzer=None,
                 vwap_filter=None,
                 streamer=None,
                 news_service=None,
                 mt5_service=None):
        """
        Initialize Regime Detector.
        
        Args:
            config: Configuration dict
            range_detector: RangeBoundaryDetector instance
            volatility_filter: Optional MicroScalpVolatilityFilter (for ATR calculations)
            m1_analyzer: Optional M1MicrostructureAnalyzer (for PDH/PDL)
            vwap_filter: Optional VWAPMicroFilter (for VWAP calculations)
            streamer: Optional MultiTimeframeStreamer (for M5/M15 data)
            news_service: Optional NewsService (for news blackout checks)
            mt5_service: Optional MT5Service (for direct data access if needed)
        """
        self.config = config
        self.range_detector = range_detector
        self.volatility_filter = volatility_filter
        self.m1_analyzer = m1_analyzer
        self.vwap_filter = vwap_filter
        self.streamer = streamer
        self.news_service = news_service
        self.mt5_service = mt5_service
        
        # Regime cache (rolling 3-bar memory)
        self.regime_cache: Dict[str, deque] = {}
        self.cache_size = 3
        self.cache_ttl_minutes = 5  # Cache expires after 5 minutes
    
    def detect_regime(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        Returns:
            Dict with:
            - regime: 'vwap_reversion', 'range_scalp', 'balanced_zone', or None
            - confidence: 0-100
            - characteristics: Dict with regime-specific data
            - vwap_reversion_result: Full detection result
            - range_result: Full detection result
            - balanced_zone_result: Full detection result
        """
        symbol = snapshot.get('symbol', '')
        
        # Check cache first
        cached = self._get_cached_regime(symbol)
        if cached:
            logger.debug(f"Using cached regime for {symbol}: {cached.get('regime')} (confidence: {cached.get('confidence')})")
            return cached
        
        # Detect all three regimes
        vwap_result = self._detect_vwap_reversion(snapshot)
        range_result = self._detect_range(snapshot)
        balanced_result = self._detect_balanced_zone(snapshot)
        
        # Select best regime with anti-flip-flop logic
        regime_result = self._select_regime(
            vwap_result, range_result, balanced_result, symbol
        )
        
        # Update cache
        self._update_regime_cache(symbol, regime_result)
        
        return regime_result
    
    def _select_regime(self, vwap_result: Dict, range_result: Dict, 
                      balanced_result: Dict, symbol: str) -> Dict[str, Any]:
        """
        Select best regime with anti-flip-flop logic.
        
        Prevents rapid switching between similar regimes.
        """
        vwap_conf = vwap_result.get('confidence', 0)
        range_conf = range_result.get('confidence', 0)
        balanced_conf = balanced_result.get('confidence', 0)
        
        # Anti-flip-flop: If two regimes are close, prefer the one with higher confidence
        # and avoid rapid switching
        vwap_threshold = vwap_result.get('min_confidence_threshold', 70)
        range_threshold = range_result.get('min_confidence_threshold', 55)
        balanced_threshold = balanced_result.get('min_confidence_threshold', 60)
        
        # Check cache for previous regime
        cached = self._get_cached_regime(symbol, min_confidence=0)  # Get any cached regime
        prev_regime = cached.get('regime') if cached else None
        prev_confidence = cached.get('confidence', 0) if cached else 0
        
        # Anti-flip-flop: If previous regime confidence is high, require significant
        # improvement to switch (hysteresis)
        if prev_regime and prev_confidence >= 70:
            # Require new regime to be at least 15 points higher to switch
            hysteresis_threshold = 15
            
            if prev_regime == 'vwap_reversion' and vwap_conf < prev_confidence + hysteresis_threshold:
                # Keep VWAP if new confidence isn't significantly higher
                if vwap_conf >= vwap_threshold:
                    return {
                        'regime': 'vwap_reversion',
                        'confidence': vwap_conf,
                        'characteristics': vwap_result,
                        'vwap_reversion_result': vwap_result,
                        'range_result': range_result,
                        'balanced_zone_result': balanced_result,
                        'anti_flip_flop': True,
                        'prev_regime': prev_regime,
                        'prev_confidence': prev_confidence
                    }
            
            if prev_regime == 'range_scalp' and range_conf < prev_confidence + hysteresis_threshold:
                if range_conf >= range_threshold:
                    return {
                        'regime': 'range_scalp',
                        'confidence': range_conf,
                        'characteristics': range_result,
                        'vwap_reversion_result': vwap_result,
                        'range_result': range_result,
                        'balanced_zone_result': balanced_result,
                        'anti_flip_flop': True,
                        'prev_regime': prev_regime,
                        'prev_confidence': prev_confidence
                    }
            
            if prev_regime == 'balanced_zone' and balanced_conf < prev_confidence + hysteresis_threshold:
                if balanced_conf >= balanced_threshold:
                    return {
                        'regime': 'balanced_zone',
                        'confidence': balanced_conf,
                        'characteristics': balanced_result,
                        'vwap_reversion_result': vwap_result,
                        'range_result': range_result,
                        'balanced_zone_result': balanced_result,
                        'anti_flip_flop': True,
                        'prev_regime': prev_regime,
                        'prev_confidence': prev_confidence
                    }
        
        # Normal selection: pick highest confidence above threshold
        candidates = []
        
        if vwap_conf >= vwap_threshold:
            candidates.append(('vwap_reversion', vwap_conf, vwap_result))
        if range_conf >= range_threshold:
            candidates.append(('range_scalp', range_conf, range_result))
        if balanced_conf >= balanced_threshold:
            candidates.append(('balanced_zone', balanced_conf, balanced_result))
        
        if not candidates:
            # No regime detected - log why
            logger.info(f"[{symbol}] No regime detected - VWAP: {vwap_conf}% (need {vwap_threshold}%), Range: {range_conf}% (need {range_threshold}%), Balanced: {balanced_conf}% (need {balanced_threshold}%)")
            return {
                'regime': None,
                'confidence': 0,
                'detected': False,
                'characteristics': {},
                'vwap_reversion_result': vwap_result,
                'range_result': range_result,
                'balanced_zone_result': balanced_result,
                'reason': f'No regime met thresholds: VWAP={vwap_conf}/{vwap_threshold}, Range={range_conf}/{range_threshold}, Balanced={balanced_conf}/{balanced_threshold}'
            }
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        best_regime, best_conf, best_result = candidates[0]
        
        return {
            'regime': best_regime,
            'confidence': best_conf,
            'characteristics': best_result,
            'vwap_reversion_result': vwap_result,
            'range_result': range_result,
            'balanced_zone_result': balanced_result
        }
    
    def _detect_vwap_reversion(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Detect VWAP Reversion regime"""
        symbol = snapshot.get('symbol', '')
        current_price = snapshot.get('current_price', 0)
        vwap = snapshot.get('vwap', 0)
        candles = snapshot.get('candles', [])
        atr1 = snapshot.get('atr1')
        
        if vwap == 0 or len(candles) < 10:
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 70}
        
        # Calculate VWAP deviation
        vwap_std = snapshot.get('vwap_std', 0)
        if vwap_std == 0:
            # Calculate VWAP std if not in snapshot
            vwap_std = self._calculate_vwap_std(candles, vwap)
        
        if vwap_std == 0:
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 70}
        
        deviation_sigma = abs(current_price - vwap) / vwap_std if vwap_std > 0 else 0
        
        # Symbol-specific thresholds
        if symbol.upper().startswith('BTC'):
            min_deviation = 2.0
            min_deviation_pct = 0.005
        else:  # XAU
            min_deviation = 2.0
            min_deviation_pct = 0.002
        
        deviation_pct = abs(current_price - vwap) / vwap if vwap > 0 else 0
        deviation_ok = deviation_sigma >= min_deviation or deviation_pct >= min_deviation_pct
        
        if not deviation_ok:
            return {
                'detected': False,
                'confidence': 0,
                'min_confidence_threshold': 70,
                'reason': f'deviation_sigma {deviation_sigma:.2f} < {min_deviation}'
            }
        
        # Check volume spike
        volume_spike = self._check_volume_spike(candles)
        
        # Check VWAP slope
        vwap_slope = self._calculate_vwap_slope(candles, vwap)
        if atr1 and atr1 > 0:
            vwap_slope_normalized = abs(vwap_slope) / atr1
            max_slope_normalized = 0.1
            max_slope_check = vwap_slope_normalized < max_slope_normalized
        else:
            max_slope = 0.0001
            max_slope_check = abs(vwap_slope) < max_slope
        
        # Check ATR stability
        atr_stable = self._check_atr_stability(candles, snapshot)
        
        # Calculate confidence
        confidence = 0
        if deviation_sigma >= min_deviation:
            confidence += 40
        if volume_spike:
            confidence += 20
        if max_slope_check:
            confidence += 20
        if atr_stable:
            confidence += 20
        
        min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('vwap_reversion', 70)
        
        return {
            'detected': confidence >= min_confidence,
            'confidence': confidence,
            'deviation_sigma': deviation_sigma,
            'deviation_pct': deviation_pct,
            'vwap_slope': vwap_slope,
            'volume_spike': volume_spike,
            'atr_stable': atr_stable,
            'min_confidence_threshold': min_confidence
        }
    
    def _detect_range(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Detect Range Scalp regime"""
        symbol = snapshot.get('symbol', '')
        candles = snapshot.get('candles', [])
        current_price = snapshot.get('current_price', 0)
        m15_candles = snapshot.get('m15_candles', [])
        
        # Use RangeBoundaryDetector
        if m15_candles:
            m15_df = self._candles_to_df(m15_candles)
        else:
            m15_df = self._candles_to_df(candles)
        
        if m15_df is None or len(m15_df) < 20:
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55}
        
        range_structure = self.range_detector.detect_range(
            symbol=symbol,
            timeframe="M15",
            range_type="dynamic",
            candles_df=m15_df,
            vwap=snapshot.get('vwap'),
            atr=snapshot.get('atr1')
        )
        
        # Fallback to PDH/PDL if range detector fails
        if not range_structure and self.m1_analyzer:
            try:
                analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                liquidity_zones = analysis.get('liquidity_zones', {})
                pdh = liquidity_zones.get('pdh')
                pdl = liquidity_zones.get('pdl')
                
                if pdh and pdl:
                    range_structure = self._create_range_from_pdh_pdl(pdh, pdl, snapshot)
            except Exception as e:
                logger.debug(f"Error getting PDH/PDL: {e}")
        
        if not range_structure:
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55}
        
        # Check range width
        range_high = range_structure.range_high
        range_low = range_structure.range_low
        range_width = range_high - range_low
        
        atr14 = snapshot.get('atr14')
        atr1 = snapshot.get('atr1')
        atr_for_comparison = atr14 if atr14 and atr14 > 0 else atr1 if atr1 and atr1 > 0 else None
        
        if atr_for_comparison:
            range_width_atr_ratio = range_width / atr_for_comparison
            if range_width_atr_ratio >= 1.2:
                return {
                    'detected': False,
                    'confidence': 0,
                    'min_confidence_threshold': 55,
                    'reason': f'range_width_atr_ratio {range_width_atr_ratio:.2f} >= 1.2'
                }
        
        # Check if price is near edge
        tolerance = range_width * 0.005
        near_high = abs(current_price - range_high) <= tolerance
        near_low = abs(current_price - range_low) <= tolerance
        
        if not (near_high or near_low):
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 55}
        
        # Check additional conditions
        bb_compression = self._check_bb_compression(candles)
        range_respects = self._count_range_respects(candles, range_high, range_low)
        m15_trend = self._check_m15_trend(symbol, snapshot)
        
        confidence = 0
        if near_high or near_low:
            confidence += 30
        if range_respects >= 2:
            confidence += 30
        if bb_compression:
            confidence += 20
        if m15_trend == 'NEUTRAL':
            confidence += 20
        
        min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('range_scalp', 55)
        
        return {
            'detected': confidence >= min_confidence,
            'confidence': confidence,
            'range_structure': range_structure,
            'near_high': near_high,
            'near_low': near_low,
            'range_respects': range_respects,
            'bb_compression': bb_compression,
            'm15_trend': m15_trend,
            'min_confidence_threshold': min_confidence
        }
    
    def _detect_balanced_zone(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Detect Balanced Zone regime"""
        candles = snapshot.get('candles', [])
        m5_candles = snapshot.get('m5_candles', [])
        current_price = snapshot.get('current_price', 0)
        vwap = snapshot.get('vwap', 0)
        
        if len(candles) < 20:
            return {'detected': False, 'confidence': 0, 'min_confidence_threshold': 60}
        
        # Check BB compression
        bb_compression = self._check_bb_compression(candles)
        
        # Check compression block (M1-M5 multi-timeframe)
        compression_block = self._check_compression_block_mtf(candles, m5_candles, snapshot)
        
        # Check ATR dropping
        atr_dropping = self._check_atr_dropping(candles, snapshot)
        
        # Check choppy liquidity
        choppy_liquidity = self._check_choppy_liquidity(candles)
        
        # Check EMA(20) - VWAP distance (equilibrium filter)
        ema20 = self._calculate_ema(candles, period=20)
        if ema20 and vwap > 0:
            ema_vwap_distance = abs(ema20 - vwap) / vwap
            equilibrium_ok = ema_vwap_distance < 0.001  # 0.1% distance
        else:
            equilibrium_ok = False
        
        confidence = 0
        if bb_compression:
            confidence += 30
        if compression_block:
            confidence += 30
        if atr_dropping:
            confidence += 20
        if choppy_liquidity:
            confidence += 10
        if equilibrium_ok:
            confidence += 10
        
        min_confidence = self.config.get('regime_detection', {}).get('strategy_confidence_thresholds', {}).get('balanced_zone', 60)
        
        return {
            'detected': confidence >= min_confidence,
            'confidence': confidence,
            'bb_compression': bb_compression,
            'compression_block': compression_block,
            'atr_dropping': atr_dropping,
            'choppy_liquidity': choppy_liquidity,
            'equilibrium_ok': equilibrium_ok,
            'min_confidence_threshold': min_confidence
        }
    
    # ============================================================================
    # HELPER METHODS - Shared with BaseStrategyChecker
    # ============================================================================
    
    def _calculate_vwap_std(self, candles: List[Dict], vwap: float) -> float:
        """Calculate VWAP standard deviation"""
        if len(candles) < 10 or vwap == 0:
            return 0.0
        
        try:
            import statistics
            
            typical_prices = []
            volumes = []
            
            for candle in candles[-20:]:
                high = candle.get('high', 0)
                low = candle.get('low', 0)
                close = candle.get('close', 0)
                volume = candle.get('volume', 0)
                
                if volume > 0:
                    typical_price = (high + low + close) / 3
                    typical_prices.append(typical_price)
                    volumes.append(volume)
            
            if not typical_prices:
                return 0.0
            
            total_volume = sum(volumes)
            if total_volume == 0:
                return 0.0
            
            weighted_mean = sum(tp * vol for tp, vol in zip(typical_prices, volumes)) / total_volume
            weighted_variance = sum(vol * (tp - weighted_mean) ** 2 for tp, vol in zip(typical_prices, volumes)) / total_volume
            std = weighted_variance ** 0.5
            
            return std
        except Exception as e:
            logger.debug(f"Error calculating VWAP std: {e}")
            return 0.0
    
    def _calculate_vwap_slope(self, candles: List[Dict[str, Any]], vwap: float) -> float:
        """Calculate VWAP slope over last N candles"""
        if len(candles) < 5 or vwap == 0:
            return 0.0
        
        recent_candles = candles[-5:]
        previous_candles = candles[-10:-5] if len(candles) >= 10 else candles[:5]
        
        recent_vwap = self._calculate_vwap_from_candles(recent_candles)
        previous_vwap = self._calculate_vwap_from_candles(previous_candles)
        
        if previous_vwap == 0:
            return 0.0
        
        slope = (recent_vwap - previous_vwap) / previous_vwap
        return slope
    
    def _calculate_vwap_from_candles(self, candles: List[Dict[str, Any]]) -> float:
        """Calculate VWAP from candle list"""
        if not candles:
            return 0.0
        
        total_pv = 0.0
        total_volume = 0.0
        
        for candle in candles:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)
            
            if volume <= 0:
                continue
            
            typical_price = (high + low + close) / 3
            total_pv += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return 0.0
        
        return total_pv / total_volume
    
    def _check_volume_spike(self, candles: List[Dict]) -> bool:
        """Check volume spike using configurable normalization"""
        volume_normalization = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_normalization', 'multiplier')
        
        if volume_normalization == 'z_score':
            return self._check_volume_spike_zscore(candles)
        else:
            return self._check_volume_spike_multiplier(candles)
    
    def _check_volume_spike_multiplier(self, candles: List[Dict]) -> bool:
        """Check if volume ≥ multiplier × 10-bar average"""
        if len(candles) < 11:
            return False
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-11:-1]]
        avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
        
        if avg_volume == 0:
            return False
        
        volume_multiplier = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_spike_multiplier', 1.3)
        return last_volume >= avg_volume * volume_multiplier
    
    def _check_volume_spike_zscore(self, candles: List[Dict]) -> bool:
        """Check volume spike using Z-score normalization"""
        if len(candles) < 31:
            return self._check_volume_spike_multiplier(candles)
        
        last_volume = candles[-1].get('volume', 0)
        if last_volume == 0:
            return False
        
        recent_volumes = [c.get('volume', 0) for c in candles[-31:-1]]
        
        if not recent_volumes or all(v == 0 for v in recent_volumes):
            return False
        
        import statistics
        mean_volume = statistics.mean(recent_volumes)
        std_volume = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
        
        if std_volume == 0:
            return self._check_volume_spike_multiplier(candles)
        
        z_score = (last_volume - mean_volume) / std_volume
        z_score_threshold = self.config.get('regime_detection', {}).get('vwap_reversion', {}).get('volume_z_score_threshold', 1.5)
        
        return z_score >= z_score_threshold
    
    def _check_bb_compression(self, candles: List[Dict]) -> bool:
        """Check if Bollinger Band width is contracting"""
        if len(candles) < 20:
            return False
        
        try:
            import pandas as pd
            import numpy as np
            
            df = self._candles_to_df(candles)
            if df is None or len(df) < 20:
                return False
            
            period = 20
            std_dev = 2.0
            
            close = df['close']
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            bb_upper = sma + (std * std_dev)
            bb_lower = sma - (std * std_dev)
            bb_width_pct = (bb_upper - bb_lower) / sma
            
            if len(bb_width_pct) < 5:
                return False
            
            # Check absolute threshold (BB width < 0.02 = 2%)
            recent_width_pct = bb_width_pct.iloc[-1]
            if recent_width_pct < 0.02:
                return True
            
            # Fallback: relative compression
            if len(bb_width_pct) >= 10:
                recent_avg = bb_width_pct.iloc[-5:].mean()
                avg_width = bb_width_pct.iloc[-20:].mean()
                
                if avg_width > 0:
                    compression_threshold = self.config.get('regime_detection', {}).get('balanced_zone', {}).get('bb_compression_threshold', 0.9)
                    compression_ratio = recent_avg / avg_width
                    return compression_ratio < compression_threshold
            
            return False
        except Exception as e:
            logger.debug(f"Error checking BB compression: {e}")
            return False
    
    def _check_compression_block(self, candles: List[Dict], atr1: Optional[float] = None) -> bool:
        """Check for inside bars / tight structure"""
        if len(candles) < 3:
            return False
        
        if not all(isinstance(c, dict) and 'high' in c and 'low' in c for c in candles):
            logger.warning("Invalid candle structure in compression check")
            return False
        
        inside_count = 0
        for i in range(max(1, len(candles) - 2), len(candles)):
            current = candles[i]
            previous = candles[i-1]
            
            current_high = current.get('high', 0)
            current_low = current.get('low', 0)
            previous_high = previous.get('high', 0)
            previous_low = previous.get('low', 0)
            
            if current_high < previous_high and current_low > previous_low:
                inside_count += 1
        
        if len(candles) >= 5 and atr1:
            recent_candles = candles[-5:]
            avg_range = sum(c.get('high', 0) - c.get('low', 0) for c in recent_candles) / len(recent_candles)
            
            if atr1 > 0 and avg_range < atr1 * 0.5:
                return True
        
        return inside_count >= 2
    
    def _check_compression_block_mtf(self, m1_candles: List[Dict], m5_candles: Optional[List[Dict]], snapshot: Optional[Dict[str, Any]] = None) -> bool:
        """M1-M5 multi-timeframe compression confirmation"""
        atr1 = snapshot.get('atr1') if snapshot else None
        m1_compression = self._check_compression_block(m1_candles, atr1)
        if not m1_compression:
            return False
        
        if not m5_candles or not isinstance(m5_candles, list) or len(m5_candles) < 3:
            return m1_compression
        
        m5_dicts = []
        for candle in m5_candles:
            try:
                if isinstance(candle, dict):
                    m5_dicts.append(candle)
                elif hasattr(candle, 'to_dict'):
                    candle_dict = candle.to_dict()
                    if candle_dict and isinstance(candle_dict, dict):
                        m5_dicts.append(candle_dict)
                elif hasattr(candle, '__dict__'):
                    candle_dict = candle.__dict__
                    if candle_dict and isinstance(candle_dict, dict):
                        m5_dicts.append(candle_dict)
            except Exception as e:
                logger.debug(f"Error converting M5 candle to dict: {e}")
                continue
        
        if not m5_dicts:
            return m1_compression
        
        m5_compression = self._check_compression_block(m5_dicts, atr1)
        return m1_compression and m5_compression
    
    def _count_range_respects(self, candles: List[Dict], range_high: float, range_low: float) -> int:
        """Count how many times price bounced at range edges"""
        if len(candles) < 10 or range_high <= range_low:
            return 0
        
        tolerance = (range_high - range_low) * 0.01
        respects = 0
        
        for i in range(1, len(candles)):
            prev_candle = candles[i-1]
            curr_candle = candles[i]
            
            prev_high = prev_candle.get('high', 0)
            prev_low = prev_candle.get('low', 0)
            curr_high = curr_candle.get('high', 0)
            curr_low = curr_candle.get('low', 0)
            
            if abs(prev_high - range_high) <= tolerance:
                if curr_low < prev_low:
                    respects += 1
            
            if abs(prev_low - range_low) <= tolerance:
                if curr_high > prev_high:
                    respects += 1
        
        return respects
    
    def _check_m15_trend(self, symbol: str, snapshot: Dict[str, Any]) -> str:
        """Check M15 trend - should be NEUTRAL for range detection"""
        m15_candles = snapshot.get('m15_candles', [])
        
        if not m15_candles or len(m15_candles) < 20:
            return 'UNKNOWN'
        
        try:
            recent_closes = [c.get('close', 0) for c in m15_candles[-20:]]
            
            if len(recent_closes) < 20 or any(c == 0 for c in recent_closes):
                return 'UNKNOWN'
            
            first_half = recent_closes[:10]
            second_half = recent_closes[10:]
            
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            
            if first_avg == 0 or second_avg == 0:
                return 'UNKNOWN'
            
            trend_pct = abs(second_avg - first_avg) / first_avg if first_avg > 0 else 0
            
            if trend_pct < 0.002:
                return 'NEUTRAL'
            elif second_avg > first_avg:
                return 'BULLISH'
            else:
                return 'BEARISH'
        except Exception as e:
            logger.debug(f"Error checking M15 trend: {e}")
            return 'UNKNOWN'
    
    def _check_atr_stability(self, candles: List[Dict], snapshot: Dict[str, Any]) -> bool:
        """Check if ATR(14) is stable or rising using memoized ATR14"""
        atr14_recent = snapshot.get('atr14')
        
        if not atr14_recent or len(candles) < 28:
            return False
        
        if not self.volatility_filter:
            return False
        
        previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
        atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
        
        if atr14_previous <= 0:
            return atr14_recent > 0
        
        atr_ratio = atr14_recent / atr14_previous
        return 0.9 <= atr_ratio <= 1.5
    
    def _check_atr_dropping(self, candles: List[Dict], snapshot: Dict[str, Any]) -> bool:
        """Check if ATR is decreasing"""
        atr14_recent = snapshot.get('atr14')
        
        if not atr14_recent or len(candles) < 28:
            return False
        
        if not self.volatility_filter:
            return False
        
        previous_candles = candles[-28:-14] if len(candles) >= 28 else candles[:14]
        atr14_previous = self.volatility_filter.calculate_atr14(previous_candles)
        
        if atr14_previous <= 0:
            return False
        
        # ATR dropping if recent < previous by more than 5%
        return atr14_recent < atr14_previous * 0.95
    
    def _check_choppy_liquidity(self, candles: List[Dict]) -> bool:
        """Check for wicks but no displacement (choppy liquidity)"""
        if len(candles) < 10:
            return False
        
        wick_count = 0
        displacement_count = 0
        
        for candle in candles[-5:]:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            open_price = candle.get('open', 0)
            close = candle.get('close', 0)
            
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            total_range = high - low
            
            if total_range > 0:
                wick_ratio = (upper_wick + lower_wick) / total_range
                if wick_ratio > 0.5:
                    wick_count += 1
                
                body_ratio = body / total_range
                if body_ratio > 0.7:
                    displacement_count += 1
        
        return wick_count >= 3 and displacement_count < 2
    
    def _calculate_ema(self, candles: List[Dict], period: int = 20) -> Optional[float]:
        """Calculate EMA(period) from candles"""
        if len(candles) < period:
            return None
        
        try:
            import pandas as pd
            
            closes = [c.get('close', 0) for c in candles[-period:]]
            if any(c == 0 for c in closes):
                return None
            
            series = pd.Series(closes)
            ema = series.ewm(span=period, adjust=False).mean().iloc[-1]
            return float(ema)
        except Exception as e:
            logger.debug(f"Error calculating EMA: {e}")
            return None
    
    def _candles_to_df(self, candles: List[Dict[str, Any]]) -> Optional[Any]:
        """Convert candle list to DataFrame with datetime index"""
        if not candles:
            return None
        
        try:
            import pandas as pd
            
            times = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for candle in candles:
                time_val = candle.get('time')
                if isinstance(time_val, (int, float)):
                    times.append(pd.Timestamp.fromtimestamp(time_val, tz='UTC'))
                elif isinstance(time_val, str):
                    times.append(pd.Timestamp(time_val))
                elif hasattr(time_val, 'timestamp'):
                    times.append(pd.Timestamp.fromtimestamp(time_val.timestamp(), tz='UTC'))
                else:
                    times.append(pd.Timestamp.now(tz='UTC'))
                
                opens.append(candle.get('open', 0))
                highs.append(candle.get('high', 0))
                lows.append(candle.get('low', 0))
                closes.append(candle.get('close', 0))
                volumes.append(candle.get('volume', 0))
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            }, index=times)
            
            return df
        except Exception as e:
            logger.error(f"Error converting candles to DataFrame: {e}")
            return None
    
    def _create_range_from_pdh_pdl(self, pdh: float, pdl: float, snapshot: Dict[str, Any]) -> Optional[RangeStructure]:
        """Create RangeStructure from PDH/PDL"""
        if pdh <= pdl:
            return None
        
        try:
            from infra.range_boundary_detector import CriticalGapZones
            
            return RangeStructure(
                range_high=pdh,
                range_low=pdl,
                range_type='pdh_pdl',
                timeframe='M1',
                detected_at=snapshot.get('timestamp', datetime.now()),
                confidence=0.7,
                critical_gap_zones=CriticalGapZones(
                    upper_gap_start=pdh * 0.999,
                    upper_gap_end=pdh,
                    lower_gap_start=pdl,
                    lower_gap_end=pdl * 1.001
                ),
                range_width=pdh - pdl,
                range_center=(pdh + pdl) / 2
            )
        except Exception as e:
            logger.debug(f"Error creating range from PDH/PDL: {e}")
            return None
    
    def _get_cached_regime(self, symbol: str, min_confidence: int = 70) -> Optional[Dict[str, Any]]:
        """Get cached regime from rolling memory"""
        if symbol not in self.regime_cache:
            return None
        
        cache = self.regime_cache[symbol]
        if not cache:
            return None
        
        # Check TTL
        now = datetime.now()
        valid_entries = []
        for entry in cache:
            cache_time = entry.get('cache_timestamp')
            if cache_time:
                age = (now - cache_time).total_seconds() / 60
                if age < self.cache_ttl_minutes:
                    valid_entries.append(entry)
        
        if not valid_entries:
            return None
        
        # Check consistency (last N entries agree)
        if len(valid_entries) >= 2:
            last_regime = valid_entries[-1].get('regime')
            last_confidence = valid_entries[-1].get('confidence', 0)
            
            if last_confidence < min_confidence:
                return None
            
            consistent_count = sum(1 for e in valid_entries if e.get('regime') == last_regime)
            if consistent_count < len(valid_entries) * 0.6:  # Less than 60% consistent
                return None
        
        return valid_entries[-1]
    
    def _update_regime_cache(self, symbol: str, regime_result: Dict[str, Any]):
        """Update rolling regime cache"""
        if symbol not in self.regime_cache:
            self.regime_cache[symbol] = deque(maxlen=self.cache_size)
        
        regime_result['cache_timestamp'] = datetime.now()
        self.regime_cache[symbol].append(regime_result)

