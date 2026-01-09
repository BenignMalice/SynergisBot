"""
Multi-Timeframe Exit Logic Engine
Advanced exit logic based on market structure across multiple timeframes
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ExitType(Enum):
    """Exit types for multi-timeframe analysis"""
    STRUCTURE_BREAK = "structure_break"
    MOMENTUM_LOSS = "momentum_loss"
    VOLUME_DECLINE = "volume_decline"
    TIME_BASED = "time_based"
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"

class ExitPriority(Enum):
    """Exit priority levels"""
    CRITICAL = 1  # Immediate exit required
    HIGH = 2      # Exit within current bar
    MEDIUM = 3    # Exit within next few bars
    LOW = 4       # Monitor for better exit

@dataclass
class ExitSignal:
    """Exit signal data structure"""
    symbol: str
    timeframe: str
    exit_type: ExitType
    priority: ExitPriority
    price_level: float
    confidence: float
    reasoning: str
    timestamp_ms: int
    context: Dict[str, Any]

class MultiTimeframeExitEngine:
    """Multi-timeframe exit logic engine"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Exit configuration
        self.exit_thresholds = symbol_config.get('exit_thresholds', {})
        self.structure_break_threshold = self.exit_thresholds.get('structure_break', 0.7)
        self.momentum_loss_threshold = self.exit_thresholds.get('momentum_loss', 0.6)
        self.volume_decline_threshold = self.exit_thresholds.get('volume_decline', 0.5)
        
        # Time-based exits
        self.max_hold_time_hours = symbol_config.get('max_hold_time_hours', 24)
        self.profit_target_ratio = symbol_config.get('profit_target_ratio', 2.0)
        
        # Exit history
        self.exit_history = []
        self.active_exits = {}
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_momentum_score(
        prices: np.ndarray, 
        volumes: np.ndarray, 
        lookback: int
    ) -> float:
        """Calculate momentum score using Numba for performance"""
        if len(prices) < lookback:
            return 0.0
        
        recent_prices = prices[-lookback:]
        recent_volumes = volumes[-lookback:]
        
        # Price momentum
        price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        
        # Volume momentum
        if len(recent_volumes) > 1:
            volume_change = (recent_volumes[-1] - recent_volumes[0]) / recent_volumes[0]
        else:
            volume_change = 0.0
        
        # Combined momentum score
        momentum_score = (price_change * 0.7) + (volume_change * 0.3)
        
        return momentum_score
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def detect_structure_break(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        current_price: float,
        lookback: int
    ) -> Tuple[bool, float]:
        """Detect structure break using Numba"""
        if len(highs) < lookback:
            return False, 0.0
        
        # Find recent swing high/low
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        swing_high = np.max(recent_highs)
        swing_low = np.min(recent_lows)
        
        # Check for break of structure
        structure_broken = False
        break_strength = 0.0
        
        if current_price > swing_high:
            # Bullish structure break
            structure_broken = True
            break_strength = (current_price - swing_high) / swing_high
        elif current_price < swing_low:
            # Bearish structure break
            structure_broken = True
            break_strength = (swing_low - current_price) / swing_low
        
        return structure_broken, break_strength
    
    def analyze_multi_timeframe_exits(
        self, 
        market_data: Dict[str, Dict[str, Any]], 
        current_trade: Dict[str, Any]
    ) -> List[ExitSignal]:
        """Analyze exits across multiple timeframes"""
        try:
            exit_signals = []
            
            # Analyze each timeframe
            for timeframe, data in market_data.items():
                if not data or 'ohlcv' not in data:
                    continue
                
                ohlcv = data['ohlcv']
                if len(ohlcv.get('close', [])) < 20:  # Need minimum data
                    continue
                
                # Get current price
                current_price = ohlcv['close'][-1]
                
                # Analyze different exit types
                signals = self._analyze_timeframe_exits(
                    timeframe, ohlcv, current_price, current_trade
                )
                exit_signals.extend(signals)
            
            # Prioritize and filter signals
            prioritized_signals = self._prioritize_exit_signals(exit_signals)
            
            return prioritized_signals
            
        except Exception as e:
            logger.error(f"Error analyzing multi-timeframe exits: {e}")
            return []
    
    def _analyze_timeframe_exits(
        self, 
        timeframe: str, 
        ohlcv: Dict[str, List[float]], 
        current_price: float,
        current_trade: Dict[str, Any]
    ) -> List[ExitSignal]:
        """Analyze exits for a specific timeframe"""
        signals = []
        
        try:
            # Convert to numpy arrays for Numba functions
            highs = np.array(ohlcv['high'], dtype=np.float32)
            lows = np.array(ohlcv['low'], dtype=np.float32)
            closes = np.array(ohlcv['close'], dtype=np.float32)
            volumes = np.array(ohlcv.get('volume', [1.0] * len(closes)), dtype=np.float32)
            
            # 1. Structure break analysis
            structure_broken, break_strength = self.detect_structure_break(
                highs, lows, closes, current_price, 20
            )
            
            if structure_broken and break_strength > self.structure_break_threshold:
                signals.append(ExitSignal(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    exit_type=ExitType.STRUCTURE_BREAK,
                    priority=ExitPriority.HIGH,
                    price_level=current_price,
                    confidence=min(break_strength, 1.0),
                    reasoning=f"Structure break detected on {timeframe} with strength {break_strength:.3f}",
                    timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                    context={'break_strength': break_strength, 'timeframe': timeframe}
                ))
            
            # 2. Momentum loss analysis
            momentum_score = self.calculate_momentum_score(closes, volumes, 10)
            
            if momentum_score < -self.momentum_loss_threshold:
                signals.append(ExitSignal(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    exit_type=ExitType.MOMENTUM_LOSS,
                    priority=ExitPriority.MEDIUM,
                    price_level=current_price,
                    confidence=abs(momentum_score),
                    reasoning=f"Momentum loss detected on {timeframe} with score {momentum_score:.3f}",
                    timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                    context={'momentum_score': momentum_score, 'timeframe': timeframe}
                ))
            
            # 3. Volume decline analysis
            if len(volumes) >= 10:
                recent_volume_avg = np.mean(volumes[-5:])
                historical_volume_avg = np.mean(volumes[-20:-5])
                
                if historical_volume_avg > 0:
                    volume_ratio = recent_volume_avg / historical_volume_avg
                    
                    if volume_ratio < self.volume_decline_threshold:
                        signals.append(ExitSignal(
                            symbol=self.symbol,
                            timeframe=timeframe,
                            exit_type=ExitType.VOLUME_DECLINE,
                            priority=ExitPriority.MEDIUM,
                            price_level=current_price,
                            confidence=1.0 - volume_ratio,
                            reasoning=f"Volume decline detected on {timeframe} with ratio {volume_ratio:.3f}",
                            timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                            context={'volume_ratio': volume_ratio, 'timeframe': timeframe}
                        ))
            
            # 4. Time-based exit analysis
            if current_trade and 'entry_time' in current_trade:
                entry_time = current_trade['entry_time']
                current_time = datetime.now(timezone.utc).timestamp()
                hold_time_hours = (current_time - entry_time) / 3600
                
                if hold_time_hours > self.max_hold_time_hours:
                    signals.append(ExitSignal(
                        symbol=self.symbol,
                        timeframe=timeframe,
                        exit_type=ExitType.TIME_BASED,
                        priority=ExitPriority.HIGH,
                        price_level=current_price,
                        confidence=min(hold_time_hours / self.max_hold_time_hours, 1.0),
                        reasoning=f"Time-based exit triggered after {hold_time_hours:.1f} hours",
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        context={'hold_time_hours': hold_time_hours, 'timeframe': timeframe}
                    ))
            
            # 5. Profit target analysis
            if current_trade and 'entry_price' in current_trade:
                entry_price = current_trade['entry_price']
                trade_direction = current_trade.get('direction', 'BUY')
                
                if trade_direction == 'BUY':
                    profit_ratio = (current_price - entry_price) / entry_price
                else:
                    profit_ratio = (entry_price - current_price) / entry_price
                
                if profit_ratio >= self.profit_target_ratio:
                    signals.append(ExitSignal(
                        symbol=self.symbol,
                        timeframe=timeframe,
                        exit_type=ExitType.PROFIT_TARGET,
                        priority=ExitPriority.HIGH,
                        price_level=current_price,
                        confidence=min(profit_ratio / self.profit_target_ratio, 1.0),
                        reasoning=f"Profit target reached with ratio {profit_ratio:.3f}",
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        context={'profit_ratio': profit_ratio, 'timeframe': timeframe}
                    ))
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe exits for {timeframe}: {e}")
        
        return signals
    
    def _prioritize_exit_signals(self, signals: List[ExitSignal]) -> List[ExitSignal]:
        """Prioritize exit signals based on type and confidence"""
        if not signals:
            return []
        
        # Sort by priority and confidence
        prioritized = sorted(signals, key=lambda x: (x.priority.value, -x.confidence))
        
        # Remove duplicates (same exit type for same timeframe)
        seen = set()
        filtered_signals = []
        
        for signal in prioritized:
            key = (signal.exit_type, signal.timeframe)
            if key not in seen:
                seen.add(key)
                filtered_signals.append(signal)
        
        return filtered_signals
    
    def get_exit_recommendation(self, signals: List[ExitSignal]) -> Optional[ExitSignal]:
        """Get the highest priority exit recommendation"""
        if not signals:
            return None
        
        # Return the highest priority signal
        return signals[0]
    
    def update_exit_history(self, signal: ExitSignal):
        """Update exit history for analysis"""
        self.exit_history.append(signal)
        
        # Keep only recent history (last 1000 signals)
        if len(self.exit_history) > 1000:
            self.exit_history = self.exit_history[-1000:]
    
    def get_exit_statistics(self) -> Dict[str, Any]:
        """Get exit statistics for analysis"""
        if not self.exit_history:
            return {'symbol': self.symbol}
        
        # Count by exit type
        exit_type_counts = {}
        for signal in self.exit_history:
            exit_type = signal.exit_type.value
            exit_type_counts[exit_type] = exit_type_counts.get(exit_type, 0) + 1
        
        # Calculate average confidence
        avg_confidence = sum(signal.confidence for signal in self.exit_history) / len(self.exit_history)
        
        # Count by priority
        priority_counts = {}
        for signal in self.exit_history:
            priority = signal.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            'total_signals': len(self.exit_history),
            'exit_type_counts': exit_type_counts,
            'priority_counts': priority_counts,
            'average_confidence': avg_confidence,
            'symbol': self.symbol
        }

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'EURJPYc',
        'exit_thresholds': {
            'structure_break': 0.7,
            'momentum_loss': 0.6,
            'volume_decline': 0.5
        },
        'max_hold_time_hours': 24,
        'profit_target_ratio': 2.0
    }
    
    # Create exit engine
    exit_engine = MultiTimeframeExitEngine(test_config)
    
    # Simulate market data
    market_data = {
        'H1': {
            'ohlcv': {
                'high': [150.0, 151.0, 152.0, 153.0, 154.0],
                'low': [149.0, 150.0, 151.0, 152.0, 153.0],
                'close': [149.5, 150.5, 151.5, 152.5, 153.5],
                'volume': [1000, 1200, 1100, 1300, 1400]
            }
        },
        'M15': {
            'ohlcv': {
                'high': [150.0, 150.5, 151.0, 151.5, 152.0],
                'low': [149.5, 150.0, 150.5, 151.0, 151.5],
                'close': [149.8, 150.2, 150.7, 151.2, 151.7],
                'volume': [200, 250, 300, 350, 400]
            }
        }
    }
    
    # Simulate current trade
    current_trade = {
        'entry_price': 150.0,
        'entry_time': datetime.now(timezone.utc).timestamp() - 3600,  # 1 hour ago
        'direction': 'BUY'
    }
    
    print("Testing Multi-Timeframe Exit Engine:")
    
    # Analyze exits
    exit_signals = exit_engine.analyze_multi_timeframe_exits(market_data, current_trade)
    
    print(f"Found {len(exit_signals)} exit signals:")
    for signal in exit_signals:
        print(f"  {signal.exit_type.value}: {signal.reasoning} (confidence: {signal.confidence:.3f})")
    
    # Get recommendation
    recommendation = exit_engine.get_exit_recommendation(exit_signals)
    if recommendation:
        print(f"\nExit Recommendation: {recommendation.exit_type.value}")
        print(f"Reasoning: {recommendation.reasoning}")
    
    # Get statistics
    stats = exit_engine.get_exit_statistics()
    print(f"\nExit Statistics: {stats}")
