"""
Multi-Timeframe Structure Analysis Engine
H1→M15→M5 structure analysis with Smart Money Concepts (SMC)
"""

import numpy as np
from numba import jit, prange
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@dataclass
class StructureSignal:
    """Structure analysis signal"""
    symbol: str
    timeframe: str
    timestamp_utc: int
    signal_type: str  # 'BOS', 'CHOCH', 'OB', 'FVG'
    price: float
    confidence: float
    data: Dict[str, Any]

@dataclass
class TimeframeData:
    """Timeframe-specific data structure"""
    symbol: str
    timeframe: str
    timestamps: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray
    atr: np.ndarray
    ema_200: np.ndarray

class MTFStructureAnalyzer:
    """Multi-timeframe structure analysis engine"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.structure_cache = {}
        self.last_signals = {}
        
    @staticmethod
    @jit(nopython=True, cache=True)  # Remove parallel=True, add cache=True
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate ATR using Numba for performance"""
        n = len(closes)
        atr = np.zeros(n, dtype=np.float32)  # Use float32 for memory efficiency
        
        if n < period:
            return atr
            
        # Calculate True Range
        tr = np.zeros(n, dtype=np.float32)
        tr[0] = highs[0] - lows[0]
        
        for i in range(1, n):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr[i] = max(hl, hc, lc)
            
        # Calculate ATR as SMA of TR (optimized)
        if n >= period:
            atr[period-1] = np.mean(tr[:period])
            for i in range(period, n):
                atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            
        return atr
        
    @staticmethod
    @jit(nopython=True, cache=True)  # Remove parallel=True, add cache=True
    def calculate_ema(prices: np.ndarray, period: int = 200) -> np.ndarray:
        """Calculate EMA using Numba for performance"""
        n = len(prices)
        ema = np.zeros(n, dtype=np.float32)  # Use float32 for memory efficiency
        
        if n == 0:
            return ema
            
        alpha = 2.0 / (period + 1)
        ema[0] = prices[0]
        
        for i in range(1, n):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
            
        return ema
        
    def detect_bos(self, data: TimeframeData, lookback: int = 20) -> List[StructureSignal]:
        """Detect Break of Structure (BOS)"""
        signals = []
        n = len(data.highs)
        
        if n < lookback + 1:
            return signals
            
        for i in range(lookback, n):
            # Check for bullish BOS
            if self._is_bullish_bos(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="BOS",
                    price=data.highs[i],
                    confidence=self._calculate_bos_confidence(data, i, lookback),
                    data={
                        "direction": "BULLISH",
                        "break_level": data.highs[i],
                        "lookback_bars": lookback,
                        "volume": data.volumes[i] if i < len(data.volumes) else 0
                    }
                )
                signals.append(signal)
                
            # Check for bearish BOS
            elif self._is_bearish_bos(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="BOS",
                    price=data.lows[i],
                    confidence=self._calculate_bos_confidence(data, i, lookback),
                    data={
                        "direction": "BEARISH",
                        "break_level": data.lows[i],
                        "lookback_bars": lookback,
                        "volume": data.volumes[i] if i < len(data.volumes) else 0
                    }
                )
                signals.append(signal)
                
        return signals
        
    def _is_bullish_bos(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bullish BOS"""
        if i < lookback:
            return False
            
        # Find highest high in lookback period
        highest_high = np.max(data.highs[i-lookback:i])
        
        # Current high must break above highest high
        if data.highs[i] <= highest_high:
            return False
            
        # Check for volume confirmation (if available)
        if i < len(data.volumes) and data.volumes[i] > 0:
            avg_volume = np.mean(data.volumes[i-lookback:i])
            if data.volumes[i] < avg_volume * 0.8:  # Volume too low
                return False
                
        return True
        
    def _is_bearish_bos(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bearish BOS"""
        if i < lookback:
            return False
            
        # Find lowest low in lookback period
        lowest_low = np.min(data.lows[i-lookback:i])
        
        # Current low must break below lowest low
        if data.lows[i] >= lowest_low:
            return False
            
        # Check for volume confirmation (if available)
        if i < len(data.volumes) and data.volumes[i] > 0:
            avg_volume = np.mean(data.volumes[i-lookback:i])
            if data.volumes[i] < avg_volume * 0.8:  # Volume too low
                return False
                
        return True
        
    def _calculate_bos_confidence(self, data: TimeframeData, i: int, lookback: int) -> float:
        """Calculate confidence score for BOS signal"""
        confidence = 0.5  # Base confidence
        
        # Volume confirmation
        if i < len(data.volumes) and data.volumes[i] > 0:
            avg_volume = np.mean(data.volumes[i-lookback:i])
            volume_ratio = data.volumes[i] / avg_volume
            confidence += min(0.3, volume_ratio * 0.1)
            
        # ATR-based strength
        if i < len(data.atr) and data.atr[i] > 0:
            price_range = data.highs[i] - data.lows[i]
            atr_ratio = price_range / data.atr[i]
            confidence += min(0.2, atr_ratio * 0.1)
            
        return min(1.0, confidence)
        
    def detect_choch(self, data: TimeframeData, lookback: int = 20) -> List[StructureSignal]:
        """Detect Change of Character (CHOCH)"""
        signals = []
        n = len(data.highs)
        
        if n < lookback + 1:
            return signals
            
        for i in range(lookback, n):
            # Check for bullish CHOCH
            if self._is_bullish_choch(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="CHOCH",
                    price=data.highs[i],
                    confidence=self._calculate_choch_confidence(data, i, lookback),
                    data={
                        "direction": "BULLISH",
                        "change_level": data.highs[i],
                        "lookback_bars": lookback
                    }
                )
                signals.append(signal)
                
            # Check for bearish CHOCH
            elif self._is_bearish_choch(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="CHOCH",
                    price=data.lows[i],
                    confidence=self._calculate_choch_confidence(data, i, lookback),
                    data={
                        "direction": "BEARISH",
                        "change_level": data.lows[i],
                        "lookback_bars": lookback
                    }
                )
                signals.append(signal)
                
        return signals
        
    def _is_bullish_choch(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bullish CHOCH"""
        if i < lookback:
            return False
            
        # Look for sequence of lower highs followed by higher high
        recent_highs = data.highs[i-lookback:i]
        if len(recent_highs) < 3:
            return False
            
        # Check if we had a sequence of lower highs
        lower_highs = 0
        for j in range(1, len(recent_highs)):
            if recent_highs[j] < recent_highs[j-1]:
                lower_highs += 1
                
        # Need at least 2 consecutive lower highs
        if lower_highs < 2:
            return False
            
        # Current high must be higher than previous high
        return data.highs[i] > recent_highs[-1]
        
    def _is_bearish_choch(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bearish CHOCH"""
        if i < lookback:
            return False
            
        # Look for sequence of higher lows followed by lower low
        recent_lows = data.lows[i-lookback:i]
        if len(recent_lows) < 3:
            return False
            
        # Check if we had a sequence of higher lows
        higher_lows = 0
        for j in range(1, len(recent_lows)):
            if recent_lows[j] > recent_lows[j-1]:
                higher_lows += 1
                
        # Need at least 2 consecutive higher lows
        if higher_lows < 2:
            return False
            
        # Current low must be lower than previous low
        return data.lows[i] < recent_lows[-1]
        
    def _calculate_choch_confidence(self, data: TimeframeData, i: int, lookback: int) -> float:
        """Calculate confidence score for CHOCH signal"""
        confidence = 0.6  # Base confidence for CHOCH
        
        # Volume confirmation
        if i < len(data.volumes) and data.volumes[i] > 0:
            avg_volume = np.mean(data.volumes[i-lookback:i])
            volume_ratio = data.volumes[i] / avg_volume
            confidence += min(0.3, volume_ratio * 0.1)
            
        return min(1.0, confidence)
        
    def detect_order_blocks(self, data: TimeframeData, lookback: int = 20) -> List[StructureSignal]:
        """Detect Order Blocks (OB)"""
        signals = []
        n = len(data.highs)
        
        if n < lookback + 1:
            return signals
            
        for i in range(lookback, n):
            # Check for bullish order block
            if self._is_bullish_order_block(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="OB",
                    price=data.lows[i],
                    confidence=self._calculate_ob_confidence(data, i, lookback),
                    data={
                        "direction": "BULLISH",
                        "block_high": data.highs[i],
                        "block_low": data.lows[i],
                        "lookback_bars": lookback
                    }
                )
                signals.append(signal)
                
            # Check for bearish order block
            elif self._is_bearish_order_block(data, i, lookback):
                signal = StructureSignal(
                    symbol=data.symbol,
                    timeframe=data.timeframe,
                    timestamp_utc=int(data.timestamps[i]),
                    signal_type="OB",
                    price=data.highs[i],
                    confidence=self._calculate_ob_confidence(data, i, lookback),
                    data={
                        "direction": "BEARISH",
                        "block_high": data.highs[i],
                        "block_low": data.lows[i],
                        "lookback_bars": lookback
                    }
                )
                signals.append(signal)
                
        return signals
        
    def _is_bullish_order_block(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bullish order block"""
        if i < lookback:
            return False
            
        # Look for strong bullish candle after bearish sequence
        recent_closes = data.closes[i-lookback:i]
        if len(recent_closes) < 3:
            return False
            
        # Check for bearish sequence
        bearish_count = 0
        for j in range(1, len(recent_closes)):
            if recent_closes[j] < recent_closes[j-1]:
                bearish_count += 1
                
        # Need at least 2 bearish candles
        if bearish_count < 2:
            return False
            
        # Current candle must be strongly bullish
        current_range = data.highs[i] - data.lows[i]
        if current_range == 0:
            return False
            
        bullish_ratio = (data.closes[i] - data.lows[i]) / current_range
        return bullish_ratio > 0.7  # Strong bullish candle
        
    def _is_bearish_order_block(self, data: TimeframeData, i: int, lookback: int) -> bool:
        """Check if current bar is a bearish order block"""
        if i < lookback:
            return False
            
        # Look for strong bearish candle after bullish sequence
        recent_closes = data.closes[i-lookback:i]
        if len(recent_closes) < 3:
            return False
            
        # Check for bullish sequence
        bullish_count = 0
        for j in range(1, len(recent_closes)):
            if recent_closes[j] > recent_closes[j-1]:
                bullish_count += 1
                
        # Need at least 2 bullish candles
        if bullish_count < 2:
            return False
            
        # Current candle must be strongly bearish
        current_range = data.highs[i] - data.lows[i]
        if current_range == 0:
            return False
            
        bearish_ratio = (data.highs[i] - data.closes[i]) / current_range
        return bearish_ratio > 0.7  # Strong bearish candle
        
    def _calculate_ob_confidence(self, data: TimeframeData, i: int, lookback: int) -> float:
        """Calculate confidence score for Order Block signal"""
        confidence = 0.7  # Base confidence for OB
        
        # Volume confirmation
        if i < len(data.volumes) and data.volumes[i] > 0:
            avg_volume = np.mean(data.volumes[i-lookback:i])
            volume_ratio = data.volumes[i] / avg_volume
            confidence += min(0.2, volume_ratio * 0.1)
            
        return min(1.0, confidence)
        
    def analyze_timeframe(self, data: TimeframeData) -> List[StructureSignal]:
        """Analyze structure for a specific timeframe"""
        all_signals = []
        
        # Detect different structure types
        bos_signals = self.detect_bos(data)
        choch_signals = self.detect_choch(data)
        ob_signals = self.detect_order_blocks(data)
        
        all_signals.extend(bos_signals)
        all_signals.extend(choch_signals)
        all_signals.extend(ob_signals)
        
        # Sort by timestamp
        all_signals.sort(key=lambda x: x.timestamp_utc)
        
        return all_signals
        
    def analyze_multi_timeframe(self, h1_data: TimeframeData, m15_data: TimeframeData, 
                              m5_data: TimeframeData) -> Dict[str, List[StructureSignal]]:
        """Analyze structure across multiple timeframes"""
        
        results = {
            "H1": self.analyze_timeframe(h1_data),
            "M15": self.analyze_timeframe(m15_data),
            "M5": self.analyze_timeframe(m5_data)
        }
        
        # Cross-timeframe analysis
        results["confluence"] = self._analyze_confluence(results)
        
        return results
        
    def _analyze_confluence(self, timeframe_results: Dict[str, List[StructureSignal]]) -> List[Dict[str, Any]]:
        """Analyze confluence across timeframes"""
        confluence_signals = []
        
        h1_signals = timeframe_results["H1"]
        m15_signals = timeframe_results["M15"]
        m5_signals = timeframe_results["M5"]
        
        # Look for alignment across timeframes
        for h1_signal in h1_signals:
            for m15_signal in m15_signals:
                for m5_signal in m5_signals:
                    if self._signals_align(h1_signal, m15_signal, m5_signal):
                        confluence = {
                            "timestamp": h1_signal.timestamp_utc,
                            "h1_signal": h1_signal.signal_type,
                            "m15_signal": m15_signal.signal_type,
                            "m5_signal": m5_signal.signal_type,
                            "confluence_score": self._calculate_confluence_score(h1_signal, m15_signal, m5_signal),
                            "direction": h1_signal.data.get("direction", "NEUTRAL")
                        }
                        confluence_signals.append(confluence)
                        
        return confluence_signals
        
    def _signals_align(self, h1_signal: StructureSignal, m15_signal: StructureSignal, 
                      m5_signal: StructureSignal) -> bool:
        """Check if signals align across timeframes"""
        # Check if signals are within reasonable time window (e.g., 1 hour)
        time_diff = abs(h1_signal.timestamp_utc - m5_signal.timestamp_utc)
        if time_diff > 3600:  # 1 hour
            return False
            
        # Check if directions align
        h1_dir = h1_signal.data.get("direction", "NEUTRAL")
        m15_dir = m15_signal.data.get("direction", "NEUTRAL")
        m5_dir = m5_signal.data.get("direction", "NEUTRAL")
        
        return h1_dir == m15_dir == m5_dir and h1_dir != "NEUTRAL"
        
    def _calculate_confluence_score(self, h1_signal: StructureSignal, m15_signal: StructureSignal,
                                   m5_signal: StructureSignal) -> float:
        """Calculate confluence score for aligned signals"""
        base_score = 0.5
        
        # Add confidence scores
        base_score += h1_signal.confidence * 0.4
        base_score += m15_signal.confidence * 0.3
        base_score += m5_signal.confidence * 0.3
        
        return min(1.0, base_score)


# Example usage and testing
if __name__ == "__main__":
    # Test structure analyzer
    analyzer = MTFStructureAnalyzer({})
    
    # Create sample data
    n_bars = 100
    timestamps = np.arange(1000, 1000 + n_bars * 3600, 3600)  # 1-hour bars
    opens = np.random.randn(n_bars) * 10 + 50000
    highs = opens + np.abs(np.random.randn(n_bars)) * 5
    lows = opens - np.abs(np.random.randn(n_bars)) * 5
    closes = opens + np.random.randn(n_bars) * 2
    volumes = np.random.randint(100, 1000, n_bars)
    
    # Calculate ATR and EMA
    atr = analyzer.calculate_atr(highs, lows, closes)
    ema_200 = analyzer.calculate_ema(closes, 200)
    
    # Create timeframe data
    data = TimeframeData(
        symbol="BTCUSDc",
        timeframe="H1",
        timestamps=timestamps,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=volumes,
        atr=atr,
        ema_200=ema_200
    )
    
    # Analyze structure
    signals = analyzer.analyze_timeframe(data)
    
    print(f"Detected {len(signals)} structure signals:")
    for signal in signals:
        print(f"  {signal.signal_type} at {signal.price:.2f} (confidence: {signal.confidence:.2f})")

