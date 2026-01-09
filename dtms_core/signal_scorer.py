"""
DTMS Signal Scorer
Hierarchical weighted scoring system for defensive trade management
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from dtms_config import get_config, get_adaptive_weights, SIGNAL_WEIGHTS

logger = logging.getLogger(__name__)

class DTMSSignalScorer:
    """
    Hierarchical weighted scoring system for DTMS signals.
    
    Signal Hierarchy (by weight):
    1. Structure (±3): BOS/CHOCH - highest authority
    2. VWAP + Volume (±2): Institutional flow signals
    3. Momentum (±2): RSI + MACD trend strength
    4. EMA Alignment (±1.5): Trend context
    5. Delta Pressure (±1): Order flow pressure
    6. Candle Conviction (±0.5 to ±2): Micro confirmation
    """
    
    def __init__(self):
        self.config = get_config()
        self.base_weights = SIGNAL_WEIGHTS.copy()
        
        logger.info("DTMSSignalScorer initialized")
    
    def calculate_signal_score(
        self, 
        symbol: str,
        trade_direction: str,
        m5_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        regime: Dict[str, str],
        vwap_current: float,
        vwap_slope: float,
        vwap_cross_counter: int,
        binance_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive signal score for defensive management.
        
        Args:
            symbol: Trading symbol
            trade_direction: 'BUY' or 'SELL'
            m5_data: M5 DataFrame
            m15_data: M15 DataFrame
            regime: Market regime classification
            vwap_current: Current VWAP
            vwap_slope: VWAP slope over last 3 M5 periods
            vwap_cross_counter: Consecutive periods on opposite side of VWAP
            binance_data: Optional Binance order flow data
            
        Returns:
            Dict with scores, warnings, and analysis
        """
        try:
            # Get adaptive weights based on regime
            adaptive_weights = get_adaptive_weights(
                regime['structure'], 
                regime['session'], 
                regime['volatility']
            )
            
            # Get adaptive thresholds
            from dtms_core.regime_classifier import DTMSRegimeClassifier
            classifier = DTMSRegimeClassifier()
            thresholds = classifier.get_adaptive_thresholds(symbol, regime)
            
            # Calculate individual signal scores
            scores = {}
            warnings = {}
            
            # 1. Structure signals (±3)
            structure_score, structure_warnings = self._score_structure(
                trade_direction, m15_data
            )
            scores['structure'] = structure_score
            warnings['structural'] = structure_warnings
            
            # 2. VWAP + Volume signals (±2)
            vwap_volume_score, vwap_warnings = self._score_vwap_volume(
                trade_direction, vwap_slope, vwap_cross_counter, 
                thresholds['vwap_threshold'], m5_data, binance_data
            )
            scores['vwap_volume'] = vwap_volume_score
            warnings['vwap'] = vwap_warnings
            
            # 3. Momentum signals (±2)
            momentum_score, momentum_warnings = self._score_momentum(
                trade_direction, m15_data, thresholds['rsi_threshold']
            )
            scores['momentum'] = momentum_score
            warnings['momentum'] = momentum_warnings
            
            # 4. EMA alignment (±1.5)
            ema_score = self._score_ema_alignment(trade_direction, m15_data)
            scores['ema_alignment'] = ema_score
            
            # 5. Delta pressure (±1)
            delta_score = self._score_delta_pressure(
                trade_direction, binance_data
            )
            scores['delta_pressure'] = delta_score
            
            # 6. Candle conviction (±0.5 to ±2)
            candle_score = self._score_candle_conviction(
                trade_direction, m5_data, vwap_current
            )
            scores['candle_conviction'] = candle_score
            
            # Calculate weighted total score
            total_score = self._calculate_weighted_score(scores, adaptive_weights)
            
            # Detect signal confluence
            confluence = self._detect_confluence(scores, adaptive_weights)
            
            # Compile result
            result = {
                'total_score': total_score,
                'individual_scores': scores,
                'adaptive_weights': adaptive_weights,
                'warnings': warnings,
                'confluence': confluence,
                'regime': regime,
                'thresholds': thresholds,
                'analysis': self._generate_analysis(scores, total_score, confluence)
            }
            
            logger.debug(f"Signal score for {symbol}: {total_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate signal score for {symbol}: {e}")
            return {
                'total_score': 0.0,
                'individual_scores': {},
                'adaptive_weights': self.base_weights,
                'warnings': {},
                'confluence': {'direction': 'NEUTRAL', 'ratio': 0.0},
                'regime': regime,
                'thresholds': {},
                'analysis': 'Error in signal calculation'
            }
    
    def _score_structure(self, trade_direction: str, m15_data: pd.DataFrame) -> Tuple[float, int]:
        """Score structure signals (BOS/CHOCH)"""
        try:
            if m15_data is None or len(m15_data) < 20:
                return 0.0, 0
            
            # Check for BOS (Break of Structure)
            bos_score = self._check_bos(m15_data, trade_direction)
            
            # Check for CHOCH (Change of Character)
            choch_score = self._check_choch(m15_data, trade_direction)
            
            # Structure score is the sum of BOS and CHOCH
            structure_score = bos_score + choch_score
            
            # Count structural warnings
            warnings = 0
            if choch_score < 0:
                warnings += 1
            if bos_score < 0:
                warnings += 1
            
            return structure_score, warnings
            
        except Exception as e:
            logger.error(f"Failed to score structure: {e}")
            return 0.0, 0
    
    def _check_bos(self, data: pd.DataFrame, trade_direction: str) -> float:
        """Check for Break of Structure"""
        try:
            if len(data) < 10:
                return 0.0
            
            # Find last swing high and low
            highs = data['high'].values
            lows = data['low'].values
            
            # Look for recent swing points (simplified)
            last_swing_high = np.max(highs[-10:])
            last_swing_low = np.min(lows[-10:])
            current_price = data['close'].iloc[-1]
            
            if trade_direction == 'BUY':
                # For long trades, bullish BOS = break above last swing high
                if current_price > last_swing_high * 1.0003:  # 0.03% break
                    return 3.0  # Strong bullish BOS
                elif current_price < last_swing_low * 0.9997:  # 0.03% break below
                    return -3.0  # Bearish BOS (bad for long)
            else:  # SELL
                # For short trades, bearish BOS = break below last swing low
                if current_price < last_swing_low * 0.9997:  # 0.03% break
                    return 3.0  # Strong bearish BOS
                elif current_price > last_swing_high * 1.0003:  # 0.03% break above
                    return -3.0  # Bullish BOS (bad for short)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to check BOS: {e}")
            return 0.0
    
    def _check_choch(self, data: pd.DataFrame, trade_direction: str) -> float:
        """Check for Change of Character"""
        try:
            if len(data) < 20:
                return 0.0
            
            # Look for CHOCH pattern (simplified)
            # CHOCH = price breaks previous HL/LH by significant amount
            
            highs = data['high'].values
            lows = data['low'].values
            current_price = data['close'].iloc[-1]
            
            # Find last significant HL/LH
            last_hl = np.min(lows[-15:])  # Last significant low
            last_lh = np.max(highs[-15:])  # Last significant high
            
            if trade_direction == 'BUY':
                # For long trades, CHOCH = break below last HL
                if current_price < last_hl * 0.9975:  # 0.25% break (0.25% of ATR equivalent)
                    return -3.0  # Strong CHOCH against long
            else:  # SELL
                # For short trades, CHOCH = break above last LH
                if current_price > last_lh * 1.0025:  # 0.25% break
                    return -3.0  # Strong CHOCH against short
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to check CHOCH: {e}")
            return 0.0
    
    def _score_vwap_volume(
        self, 
        trade_direction: str, 
        vwap_slope: float, 
        vwap_cross_counter: int,
        vwap_threshold: float,
        m5_data: pd.DataFrame,
        binance_data: Optional[Dict]
    ) -> Tuple[float, int]:
        """Score VWAP and volume signals"""
        try:
            score = 0.0
            warnings = 0
            
            # VWAP flip detection
            vwap_flip_active = False
            if abs(vwap_slope) >= vwap_threshold and vwap_cross_counter >= 2:
                vwap_flip_active = True
                
                # Determine if flip is against trade direction
                if trade_direction == 'BUY' and vwap_slope < 0:
                    score -= 2.0  # VWAP flipping bearish (bad for long)
                    warnings += 1
                elif trade_direction == 'SELL' and vwap_slope > 0:
                    score -= 2.0  # VWAP flipping bullish (bad for short)
                    warnings += 1
                else:
                    score += 1.0  # VWAP flipping in favor of trade
            
            # Volume analysis (if Binance data available)
            if binance_data:
                volume_score = self._analyze_volume_pressure(
                    trade_direction, binance_data
                )
                score += volume_score
                
                if volume_score < -1.0:
                    warnings += 1
            
            return score, warnings
            
        except Exception as e:
            logger.error(f"Failed to score VWAP/volume: {e}")
            return 0.0, 0
    
    def _analyze_volume_pressure(self, trade_direction: str, binance_data: Dict) -> float:
        """Analyze volume pressure from Binance data"""
        try:
            # Get buy/sell volume ratio
            buy_volume = binance_data.get('buy_volume', 0)
            sell_volume = binance_data.get('sell_volume', 0)
            total_volume = buy_volume + sell_volume
            
            if total_volume == 0:
                return 0.0
            
            # Calculate opposite volume share
            if trade_direction == 'BUY':
                opposite_share = sell_volume / total_volume
            else:  # SELL
                opposite_share = buy_volume / total_volume
            
            # Score based on opposite volume dominance
            if opposite_share > 0.65:  # 65% opposite volume
                return -1.0  # Strong opposite pressure
            elif opposite_share > 0.55:  # 55% opposite volume
                return -0.5  # Moderate opposite pressure
            elif opposite_share < 0.35:  # 35% opposite volume (65% in favor)
                return 1.0  # Strong favorable pressure
            else:
                return 0.0  # Neutral
            
        except Exception as e:
            logger.error(f"Failed to analyze volume pressure: {e}")
            return 0.0
    
    def _score_momentum(self, trade_direction: str, m15_data: pd.DataFrame, rsi_threshold: float) -> Tuple[float, int]:
        """Score momentum signals (RSI + MACD)"""
        try:
            if m15_data is None or len(m15_data) < 20:
                return 0.0, 0
            
            score = 0.0
            warnings = 0
            
            # RSI analysis
            rsi_score = self._analyze_rsi(trade_direction, m15_data, rsi_threshold)
            score += rsi_score
            
            if rsi_score < -1.0:
                warnings += 1
            
            # MACD analysis
            macd_score = self._analyze_macd(trade_direction, m15_data)
            score += macd_score
            
            if macd_score < -0.5:
                warnings += 1
            
            return score, warnings
            
        except Exception as e:
            logger.error(f"Failed to score momentum: {e}")
            return 0.0, 0
    
    def _analyze_rsi(self, trade_direction: str, data: pd.DataFrame, threshold: float) -> float:
        """Analyze RSI momentum"""
        try:
            if len(data) < 14:
                return 0.0
            
            # Calculate RSI
            rsi = self._calculate_rsi(data['close'], period=14)
            if rsi is None:
                return 0.0
            
            # Check RSI trend (last 3 values)
            if len(data) >= 17:
                rsi_values = []
                for i in range(3):
                    # Fix: Use proper slice - need at least 15 periods for RSI(14)
                    start_idx = -(14 + i + 1)  # Need 14 periods + i offset + 1 for diff
                    end_idx = -(i) if i > 0 else None
                    try:
                        price_slice = data['close'].iloc[start_idx:end_idx]
                        if len(price_slice) >= 15:  # Need at least 15 for RSI(14)
                            rsi_val = self._calculate_rsi(price_slice, period=14)
                            if rsi_val is not None and not pd.isna(rsi_val):
                                rsi_values.append(float(rsi_val))
                    except (IndexError, ValueError):
                        continue
                
                if len(rsi_values) >= 2:
                    # Ensure both values are valid numbers before subtraction
                    try:
                        rsi_trend = float(rsi_values[0]) - float(rsi_values[-1])  # Current - 2 periods ago
                    except (ValueError, TypeError):
                        rsi_trend = 0
                else:
                    rsi_trend = 0
            else:
                rsi_trend = 0
            
            # Score based on trade direction
            if trade_direction == 'BUY':
                if rsi < threshold and rsi_trend < 0:  # RSI declining below threshold
                    return -2.0  # Strong bearish momentum
                elif rsi > 70 and rsi_trend > 0:  # RSI overbought and rising
                    return -1.0  # Moderate bearish momentum
                elif rsi > 50 and rsi_trend > 0:  # RSI above 50 and rising
                    return 1.0  # Bullish momentum
            else:  # SELL
                if rsi > (100 - threshold) and rsi_trend > 0:  # RSI rising above threshold
                    return -2.0  # Strong bullish momentum
                elif rsi < 30 and rsi_trend < 0:  # RSI oversold and falling
                    return -1.0  # Moderate bullish momentum
                elif rsi < 50 and rsi_trend < 0:  # RSI below 50 and falling
                    return 1.0  # Bearish momentum
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to analyze RSI: {e}")
            return 0.0
    
    def _analyze_macd(self, trade_direction: str, data: pd.DataFrame) -> float:
        """Analyze MACD momentum"""
        try:
            if len(data) < 26:
                return 0.0
            
            # Calculate MACD
            macd_line, macd_signal, macd_hist = self._calculate_macd(data['close'])
            
            if macd_hist is None or len(macd_hist) < 3:
                return 0.0
            
            # Check MACD histogram trend
            current_hist = macd_hist.iloc[-1]
            prev_hist = macd_hist.iloc[-2]
            prev2_hist = macd_hist.iloc[-3]
            
            # Score based on histogram trend
            if current_hist < prev_hist < prev2_hist:  # Declining for 2 periods
                if trade_direction == 'BUY':
                    return -1.0  # Bearish momentum
                else:
                    return 1.0  # Bearish momentum (good for short)
            elif current_hist > prev_hist > prev2_hist:  # Rising for 2 periods
                if trade_direction == 'BUY':
                    return 1.0  # Bullish momentum
                else:
                    return -1.0  # Bullish momentum (bad for short)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to analyze MACD: {e}")
            return 0.0
    
    def _score_ema_alignment(self, trade_direction: str, m15_data: pd.DataFrame) -> float:
        """Score EMA alignment"""
        try:
            if m15_data is None or len(m15_data) < 200:
                return 0.0
            
            # Calculate EMA slopes
            ema50_slope = self._calculate_ema_slope(m15_data['close'], 50)
            ema200_slope = self._calculate_ema_slope(m15_data['close'], 200)
            
            if ema50_slope is None or ema200_slope is None:
                return 0.0
            
            # Check for divergence
            if ema50_slope * ema200_slope < 0:  # Opposite slopes
                return -1.5  # Strong divergence
            
            # Check alignment with trade direction
            if trade_direction == 'BUY':
                if ema50_slope < 0:  # EMA50 declining
                    return -1.0  # Bearish alignment
                elif ema50_slope > 0 and ema200_slope > 0:  # Both rising
                    return 1.0  # Bullish alignment
            else:  # SELL
                if ema50_slope > 0:  # EMA50 rising
                    return -1.0  # Bullish alignment
                elif ema50_slope < 0 and ema200_slope < 0:  # Both falling
                    return 1.0  # Bearish alignment
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to score EMA alignment: {e}")
            return 0.0
    
    def _score_delta_pressure(self, trade_direction: str, binance_data: Optional[Dict]) -> float:
        """Score order flow delta pressure"""
        try:
            if not binance_data:
                return 0.0
            
            # Get delta Z-score
            delta_z = binance_data.get('delta_z_score', 0.0)
            
            # Score based on delta direction vs trade direction
            if abs(delta_z) > 0.5:  # Significant delta
                if trade_direction == 'BUY' and delta_z < -0.5:  # Sell pressure
                    return -1.0
                elif trade_direction == 'SELL' and delta_z > 0.5:  # Buy pressure
                    return -1.0
                elif trade_direction == 'BUY' and delta_z > 0.5:  # Buy pressure
                    return 1.0
                elif trade_direction == 'SELL' and delta_z < -0.5:  # Sell pressure
                    return 1.0
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to score delta pressure: {e}")
            return 0.0
    
    def _score_candle_conviction(self, trade_direction: str, m5_data: pd.DataFrame, vwap_current: float) -> float:
        """Score candle conviction patterns"""
        try:
            if m5_data is None or len(m5_data) < 1:
                return 0.0
            
            last_bar = m5_data.iloc[-1]
            
            # Calculate conviction metrics
            body_size = abs(last_bar['close'] - last_bar['open'])
            range_size = last_bar['high'] - last_bar['low']
            body_ratio = body_size / range_size if range_size > 0 else 0
            
            # Check if conviction bar (body >= 65% of range)
            if body_ratio < 0.65:
                return 0.0
            
            # Check if closes through VWAP
            closes_through_vwap = False
            if trade_direction == 'BUY':
                closes_through_vwap = last_bar['close'] < vwap_current < last_bar['open']
            else:  # SELL
                closes_through_vwap = last_bar['close'] > vwap_current > last_bar['open']
            
            # Score based on conviction and direction
            if closes_through_vwap:
                return -2.0  # Strong conviction against trade
            else:
                return -1.0  # Moderate conviction against trade
            
        except Exception as e:
            logger.error(f"Failed to score candle conviction: {e}")
            return 0.0
    
    def _calculate_weighted_score(self, scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """Calculate weighted total score"""
        total_score = 0.0
        
        for signal_type, score in scores.items():
            weight = weights.get(signal_type, 1.0)
            total_score += score * weight
        
        return total_score
    
    def _detect_confluence(self, scores: Dict[str, float], weights: Dict[str, float]) -> Dict[str, Any]:
        """Detect signal confluence"""
        bullish_signals = []
        bearish_signals = []
        
        for signal_type, score in scores.items():
            weight = weights.get(signal_type, 1.0)
            weighted_score = score * weight
            
            if weighted_score > 0:
                bullish_signals.append((signal_type, weighted_score))
            elif weighted_score < 0:
                bearish_signals.append((signal_type, abs(weighted_score)))
        
        total_bullish_weight = sum(weight for _, weight in bullish_signals)
        total_bearish_weight = sum(weight for _, weight in bearish_signals)
        total_weight = total_bullish_weight + total_bearish_weight
        
        if total_weight == 0:
            return {'direction': 'NEUTRAL', 'ratio': 0.0}
        
        agreement_ratio = max(total_bullish_weight, total_bearish_weight) / total_weight
        
        if agreement_ratio >= 0.7:  # 70% agreement threshold
            direction = 'BULLISH' if total_bullish_weight > total_bearish_weight else 'BEARISH'
            return {'direction': direction, 'ratio': agreement_ratio}
        
        return {'direction': 'MIXED', 'ratio': agreement_ratio}
    
    def _generate_analysis(self, scores: Dict[str, float], total_score: float, confluence: Dict[str, Any]) -> str:
        """Generate human-readable analysis"""
        analysis_parts = []
        
        # Overall score interpretation
        if total_score >= 3:
            analysis_parts.append("Strong bullish signals")
        elif total_score >= 1:
            analysis_parts.append("Moderate bullish signals")
        elif total_score <= -3:
            analysis_parts.append("Strong bearish signals")
        elif total_score <= -1:
            analysis_parts.append("Moderate bearish signals")
        else:
            analysis_parts.append("Neutral signals")
        
        # Confluence analysis
        if confluence['ratio'] >= 0.7:
            analysis_parts.append(f"High confluence ({confluence['direction']})")
        elif confluence['ratio'] >= 0.5:
            analysis_parts.append(f"Moderate confluence ({confluence['direction']})")
        else:
            analysis_parts.append("Mixed signals")
        
        # Key signal highlights
        key_signals = []
        for signal_type, score in scores.items():
            if abs(score) >= 2:
                direction = "bullish" if score > 0 else "bearish"
                key_signals.append(f"{signal_type} ({direction})")
        
        if key_signals:
            analysis_parts.append(f"Key signals: {', '.join(key_signals)}")
        
        return " | ".join(analysis_parts)
    
    # Technical indicator calculation methods
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        try:
            if len(prices) < period + 1:
                return None
            
            # Ensure prices are numeric and drop NaN values
            prices = pd.to_numeric(prices, errors='coerce').dropna()
            if len(prices) < period + 1:
                return None
            
            delta = prices.diff()
            
            # Handle None/NaN values before applying unary minus
            # For gains: positive changes, zero otherwise
            gain = delta.where(delta > 0, 0.0).fillna(0.0)
            
            # For losses: negative changes (make positive), zero otherwise
            # Use abs() on negative values instead of unary minus to avoid NoneType error
            loss = delta.where(delta < 0, 0.0).abs().fillna(0.0)
            
            # Calculate rolling means
            gain_mean = gain.rolling(window=period).mean()
            loss_mean = loss.rolling(window=period).mean()
            
            # Avoid division by zero and handle NaN values
            loss_val = loss_mean.iloc[-1]
            gain_val = gain_mean.iloc[-1]
            
            # Check for NaN or None values
            if pd.isna(loss_val) or pd.isna(gain_val):
                return None
            
            if loss_val == 0 or loss_val == 0.0:
                return 100.0 if gain_val > 0 else 50.0
            
            rs = float(gain_val) / float(loss_val)
            rsi = 100 - (100 / (1 + rs))
            
            # Ensure RSI is in valid range
            rsi = max(0.0, min(100.0, rsi))
            
            return float(rsi)
            
        except Exception as e:
            logger.error(f"Failed to calculate RSI: {e}", exc_info=True)
            return None
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """Calculate MACD"""
        try:
            if len(prices) < slow:
                return None, None, None
            
            ema_fast = prices.ewm(span=fast).mean()
            ema_slow = prices.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            macd_signal = macd_line.ewm(span=signal).mean()
            macd_histogram = macd_line - macd_signal
            
            return macd_line, macd_signal, macd_histogram
            
        except Exception as e:
            logger.error(f"Failed to calculate MACD: {e}")
            return None, None, None
    
    def _calculate_ema_slope(self, prices: pd.Series, period: int) -> Optional[float]:
        """Calculate EMA slope over last 10 periods"""
        try:
            if len(prices) < period + 10:
                return None
            
            ema = prices.ewm(span=period).mean()
            
            if len(ema) < 10:
                return None
            
            # Calculate slope: (current - 10 periods ago) / 10 periods ago
            current_ema = ema.iloc[-1]
            old_ema = ema.iloc[-10]
            
            if old_ema == 0:
                return None
            
            slope = (current_ema - old_ema) / old_ema
            return float(slope)
            
        except Exception as e:
            logger.error(f"Failed to calculate EMA slope: {e}")
            return None
