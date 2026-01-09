"""
DTMS Regime Classifier
Classifies market regime (session, volatility, structure) for adaptive thresholds
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time
from dtms_config import get_config

logger = logging.getLogger(__name__)

class DTMSRegimeClassifier:
    """
    Classifies market regime for adaptive DTMS thresholds.
    
    Regimes:
    - Session: Asian, London, NY, Overlap
    - Volatility: Low, Normal, High (based on ATR ratio)
    - Structure: Range, Trend (based on BB width)
    """
    
    def __init__(self):
        self.config = get_config()
        
        # Session boundaries (UTC times)
        self.session_times = {
            'Asian': (time(0, 0), time(8, 0)),      # 00:00 - 08:00 UTC
            'London': (time(8, 0), time(16, 0)),    # 08:00 - 16:00 UTC
            'NY': (time(13, 0), time(21, 0)),       # 13:00 - 21:00 UTC
            'Overlap': (time(13, 0), time(16, 0))   # 13:00 - 16:00 UTC (London/NY overlap)
        }
        
        # ATR ratio thresholds
        self.atr_thresholds = self.config.thresholds['atr_ratio_thresholds']
        self.bb_width_threshold = self.config.thresholds['bb_width_threshold']
        
        logger.info("DTMSRegimeClassifier initialized")
    
    def classify_regime(self, symbol: str, m5_data: pd.DataFrame, m15_data: pd.DataFrame) -> Dict[str, str]:
        """
        Classify complete market regime for a symbol.
        
        Args:
            symbol: Trading symbol
            m5_data: M5 DataFrame with OHLCV data
            m15_data: M15 DataFrame with OHLCV data
            
        Returns:
            Dict with 'session', 'volatility', 'structure' classifications
        """
        try:
            regime = {
                'session': self._classify_session(),
                'volatility': self._classify_volatility(m15_data),
                'structure': self._classify_structure(m15_data)
            }
            
            logger.debug(f"Regime classification for {symbol}: {regime}")
            return regime
            
        except Exception as e:
            logger.error(f"Failed to classify regime for {symbol}: {e}")
            return {
                'session': 'Unknown',
                'volatility': 'Normal',
                'structure': 'Trend'
            }
    
    def _classify_session(self) -> str:
        """Classify current trading session"""
        try:
            # Get current UTC time
            utc_now = datetime.utcnow().time()
            
            # Check for overlap first (highest priority)
            if self._time_in_range(utc_now, self.session_times['Overlap']):
                return 'Overlap'
            
            # Check other sessions
            for session, (start_time, end_time) in self.session_times.items():
                if session == 'Overlap':  # Skip, already checked
                    continue
                
                if self._time_in_range(utc_now, (start_time, end_time)):
                    return session
            
            # Default to Asian if no match (weekend/off-hours)
            return 'Asian'
            
        except Exception as e:
            logger.error(f"Failed to classify session: {e}")
            return 'Unknown'
    
    def _time_in_range(self, current_time: time, time_range: Tuple[time, time]) -> bool:
        """Check if current time is within a time range"""
        start_time, end_time = time_range
        
        if start_time <= end_time:
            # Normal case: start < end (e.g., 08:00 - 16:00)
            return start_time <= current_time <= end_time
        else:
            # Overnight case: start > end (e.g., 22:00 - 06:00)
            return current_time >= start_time or current_time <= end_time
    
    def _classify_volatility(self, m15_data: pd.DataFrame) -> str:
        """Classify volatility regime based on ATR ratio"""
        try:
            if m15_data is None or len(m15_data) < 20:
                return 'Normal'
            
            # Calculate current ATR
            current_atr = self._calculate_atr(m15_data, period=14)
            if current_atr is None or current_atr <= 0:
                return 'Normal'
            
            # Calculate ATR SMA (20 periods)
            atr_values = []
            for i in range(20, len(m15_data)):
                atr = self._calculate_atr(m15_data.iloc[i-14:i+1], period=14)
                if atr is not None:
                    atr_values.append(atr)
            
            if len(atr_values) < 10:
                return 'Normal'
            
            atr_sma = np.mean(atr_values)
            atr_ratio = current_atr / atr_sma if atr_sma > 0 else 1.0
            
            # Classify based on ratio
            if atr_ratio < self.atr_thresholds['low_vol']:
                return 'Low'
            elif atr_ratio > self.atr_thresholds['high_vol']:
                return 'High'
            else:
                return 'Normal'
                
        except Exception as e:
            logger.error(f"Failed to classify volatility: {e}")
            return 'Normal'
    
    def _classify_structure(self, m15_data: pd.DataFrame) -> str:
        """Classify market structure based on Bollinger Band width"""
        try:
            if m15_data is None or len(m15_data) < 20:
                return 'Trend'
            
            # Calculate Bollinger Bands
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(m15_data, period=20)
            
            if bb_upper is None or bb_middle is None or bb_lower is None:
                return 'Trend'
            
            # Calculate BB width as percentage of middle band
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            
            # Classify based on width
            if bb_width < self.bb_width_threshold:
                return 'Range'
            else:
                return 'Trend'
                
        except Exception as e:
            logger.error(f"Failed to classify structure: {e}")
            return 'Trend'
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        try:
            if len(data) < period + 1:
                return None
            
            # Calculate True Range
            high = data['high'].values
            low = data['low'].values
            close = data['close'].values
            
            tr_values = []
            for i in range(1, len(data)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr = max(tr1, tr2, tr3)
                tr_values.append(tr)
            
            if len(tr_values) < period:
                return None
            
            # Calculate ATR as SMA of TR
            atr = np.mean(tr_values[-period:])
            return float(atr)
            
        except Exception as e:
            logger.error(f"Failed to calculate ATR: {e}")
            return None
    
    def _calculate_bollinger_bands(self, data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Bollinger Bands"""
        try:
            if len(data) < period:
                return None, None, None
            
            close = data['close'].values
            sma = np.mean(close[-period:])
            std = np.std(close[-period:])
            
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            
            return float(upper), float(sma), float(lower)
            
        except Exception as e:
            logger.error(f"Failed to calculate Bollinger Bands: {e}")
            return None, None, None
    
    def get_adaptive_thresholds(self, symbol: str, regime: Dict[str, str]) -> Dict[str, float]:
        """
        Get adaptive thresholds based on regime classification.
        
        Args:
            symbol: Trading symbol
            regime: Dict with 'session', 'volatility', 'structure'
            
        Returns:
            Dict with adaptive thresholds
        """
        try:
            # Base thresholds
            base_vwap = self.config.thresholds['vwap_base'].get(symbol, 0.001)
            base_rsi = self.config.thresholds['rsi_thresholds']['normal']
            base_volume_flip = self.config.thresholds['volume_flip_thresholds']['normal']
            
            # Get multipliers
            session_mult = self.config.adaptive_multipliers['session'].get(regime['session'], 1.0)
            vol_mult = self.config.adaptive_multipliers['volatility'].get(regime['volatility'], 1.0)
            structure_mult = self.config.adaptive_multipliers['structure'].get(regime['structure'], 1.0)
            
            # Calculate adaptive VWAP threshold
            adaptive_vwap = base_vwap * session_mult * vol_mult * structure_mult
            
            # Apply clamping
            min_threshold = base_vwap * self.config.adaptive_multipliers['clamp_limits']['min_threshold']
            max_threshold = base_vwap * self.config.adaptive_multipliers['clamp_limits']['max_threshold']
            adaptive_vwap = max(min_threshold, min(adaptive_vwap, max_threshold))
            
            # Adjust RSI threshold for low volatility
            if regime['volatility'] == 'Low':
                adaptive_rsi = self.config.thresholds['rsi_thresholds']['low_vol']
            else:
                adaptive_rsi = base_rsi
            
            # Adjust volume flip threshold for low volatility
            if regime['volatility'] == 'Low':
                adaptive_volume_flip = self.config.thresholds['volume_flip_thresholds']['low_vol']
            else:
                adaptive_volume_flip = base_volume_flip
            
            thresholds = {
                'vwap_threshold': adaptive_vwap,
                'rsi_threshold': adaptive_rsi,
                'volume_flip_threshold': adaptive_volume_flip,
                'session_multiplier': session_mult,
                'volatility_multiplier': vol_mult,
                'structure_multiplier': structure_mult
            }
            
            logger.debug(f"Adaptive thresholds for {symbol}: {thresholds}")
            return thresholds
            
        except Exception as e:
            logger.error(f"Failed to get adaptive thresholds for {symbol}: {e}")
            return {
                'vwap_threshold': 0.001,
                'rsi_threshold': 45,
                'volume_flip_threshold': 0.65,
                'session_multiplier': 1.0,
                'volatility_multiplier': 1.0,
                'structure_multiplier': 1.0
            }
    
    def get_regime_summary(self, symbol: str, regime: Dict[str, str], thresholds: Dict[str, float]) -> str:
        """Get human-readable regime summary"""
        session = regime.get('session', 'Unknown')
        volatility = regime.get('volatility', 'Normal')
        structure = regime.get('structure', 'Trend')
        
        vwap_thresh = thresholds.get('vwap_threshold', 0.001)
        rsi_thresh = thresholds.get('rsi_threshold', 45)
        
        summary = f"{symbol} Regime: {session} session, {volatility} volatility, {structure} structure"
        summary += f" | VWAP threshold: {vwap_thresh:.4f}, RSI threshold: {rsi_thresh}"
        
        return summary
