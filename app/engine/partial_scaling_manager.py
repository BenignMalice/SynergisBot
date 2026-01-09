"""
Partial Scaling Manager
Structure-based position sizing and scaling
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ScalingType(Enum):
    """Scaling types"""
    STRUCTURE_BREAK = "structure_break"
    MOMENTUM_CONFIRMATION = "momentum_confirmation"
    VOLUME_CONFIRMATION = "volume_confirmation"
    TIME_BASED = "time_based"
    PROFIT_BASED = "profit_based"

class ScalingAction(Enum):
    """Scaling actions"""
    ADD_POSITION = "add_position"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    HOLD_POSITION = "hold_position"

@dataclass
class ScalingSignal:
    """Scaling signal data structure"""
    symbol: str
    scaling_type: ScalingType
    action: ScalingAction
    size_change: float
    price_level: float
    confidence: float
    reasoning: str
    timestamp_ms: int
    context: Dict[str, Any]

class PartialScalingManager:
    """Partial scaling management system"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Scaling configuration
        self.scaling_config = symbol_config.get('scaling_config', {})
        self.max_position_size = self.scaling_config.get('max_position_size', 1.0)
        self.scaling_increment = self.scaling_config.get('scaling_increment', 0.25)
        self.structure_break_threshold = self.scaling_config.get('structure_break_threshold', 0.7)
        self.momentum_threshold = self.scaling_config.get('momentum_threshold', 0.6)
        self.volume_threshold = self.scaling_config.get('volume_threshold', 1.5)
        
        # Position tracking
        self.current_position = 0.0
        self.position_history = []
        self.scaling_history = []
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_structure_strength(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        current_price: float,
        lookback: int
    ) -> float:
        """Calculate structure break strength using Numba"""
        if len(highs) < lookback:
            return 0.0
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        # Find swing points
        swing_high = np.max(recent_highs)
        swing_low = np.min(recent_lows)
        
        # Calculate break strength
        if current_price > swing_high:
            strength = (current_price - swing_high) / swing_high
        elif current_price < swing_low:
            strength = (swing_low - current_price) / swing_low
        else:
            strength = 0.0
        
        return strength
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_momentum_score(
        prices: np.ndarray,
        volumes: np.ndarray,
        lookback: int
    ) -> float:
        """Calculate momentum score using Numba"""
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
        
        # Combined momentum
        momentum = (price_change * 0.7) + (volume_change * 0.3)
        
        return momentum
    
    def analyze_scaling_opportunities(
        self, 
        market_data: Dict[str, Dict[str, Any]], 
        current_trade: Dict[str, Any]
    ) -> List[ScalingSignal]:
        """Analyze scaling opportunities across timeframes"""
        try:
            scaling_signals = []
            
            # Analyze each timeframe
            for timeframe, data in market_data.items():
                if not data or 'ohlcv' not in data:
                    continue
                
                ohlcv = data['ohlcv']
                if len(ohlcv.get('close', [])) < 20:
                    continue
                
                current_price = ohlcv['close'][-1]
                
                # Analyze scaling opportunities
                signals = self._analyze_timeframe_scaling(
                    timeframe, ohlcv, current_price, current_trade
                )
                scaling_signals.extend(signals)
            
            # Filter and prioritize signals
            filtered_signals = self._filter_scaling_signals(scaling_signals)
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"Error analyzing scaling opportunities: {e}")
            return []
    
    def _analyze_timeframe_scaling(
        self, 
        timeframe: str, 
        ohlcv: Dict[str, List[float]], 
        current_price: float,
        current_trade: Dict[str, Any]
    ) -> List[ScalingSignal]:
        """Analyze scaling opportunities for a specific timeframe"""
        signals = []
        
        try:
            # Convert to numpy arrays
            highs = np.array(ohlcv['high'], dtype=np.float32)
            lows = np.array(ohlcv['low'], dtype=np.float32)
            closes = np.array(ohlcv['close'], dtype=np.float32)
            volumes = np.array(ohlcv.get('volume', [1.0] * len(closes)), dtype=np.float32)
            
            trade_direction = 1 if current_trade.get('direction') == 'BUY' else -1
            current_size = current_trade.get('position_size', 0.0)
            
            # 1. Structure break analysis
            structure_strength = self.calculate_structure_strength(
                highs, lows, closes, current_price, 20
            )
            
            if structure_strength > self.structure_break_threshold:
                # Determine scaling action based on direction and strength
                if trade_direction == 1:  # Long trade
                    if current_price > closes[-2]:  # Price moving up
                        action = ScalingAction.ADD_POSITION
                        size_change = min(self.scaling_increment, self.max_position_size - current_size)
                    else:  # Price moving down
                        action = ScalingAction.REDUCE_POSITION
                        size_change = -min(self.scaling_increment, current_size)
                else:  # Short trade
                    if current_price < closes[-2]:  # Price moving down
                        action = ScalingAction.ADD_POSITION
                        size_change = min(self.scaling_increment, self.max_position_size - current_size)
                    else:  # Price moving up
                        action = ScalingAction.REDUCE_POSITION
                        size_change = -min(self.scaling_increment, current_size)
                
                if size_change != 0:
                    signals.append(ScalingSignal(
                        symbol=self.symbol,
                        scaling_type=ScalingType.STRUCTURE_BREAK,
                        action=action,
                        size_change=size_change,
                        price_level=current_price,
                        confidence=min(structure_strength, 1.0),
                        reasoning=f"Structure break on {timeframe} with strength {structure_strength:.3f}",
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        context={
                            'timeframe': timeframe,
                            'structure_strength': structure_strength,
                            'trade_direction': trade_direction
                        }
                    ))
            
            # 2. Momentum confirmation analysis
            momentum_score = self.calculate_momentum_score(closes, volumes, 10)
            
            if abs(momentum_score) > self.momentum_threshold:
                # Check if momentum aligns with trade direction
                momentum_aligned = (trade_direction == 1 and momentum_score > 0) or \
                                (trade_direction == -1 and momentum_score < 0)
                
                if momentum_aligned and current_size < self.max_position_size:
                    signals.append(ScalingSignal(
                        symbol=self.symbol,
                        scaling_type=ScalingType.MOMENTUM_CONFIRMATION,
                        action=ScalingAction.ADD_POSITION,
                        size_change=min(self.scaling_increment, self.max_position_size - current_size),
                        price_level=current_price,
                        confidence=abs(momentum_score),
                        reasoning=f"Momentum confirmation on {timeframe} with score {momentum_score:.3f}",
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        context={
                            'timeframe': timeframe,
                            'momentum_score': momentum_score,
                            'trade_direction': trade_direction
                        }
                    ))
                elif not momentum_aligned and current_size > 0:
                    signals.append(ScalingSignal(
                        symbol=self.symbol,
                        scaling_type=ScalingType.MOMENTUM_CONFIRMATION,
                        action=ScalingAction.REDUCE_POSITION,
                        size_change=-min(self.scaling_increment, current_size),
                        price_level=current_price,
                        confidence=abs(momentum_score),
                        reasoning=f"Momentum divergence on {timeframe} with score {momentum_score:.3f}",
                        timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                        context={
                            'timeframe': timeframe,
                            'momentum_score': momentum_score,
                            'trade_direction': trade_direction
                        }
                    ))
            
            # 3. Volume confirmation analysis
            if len(volumes) >= 10:
                recent_volume_avg = np.mean(volumes[-5:])
                historical_volume_avg = np.mean(volumes[-20:-5])
                
                if historical_volume_avg > 0:
                    volume_ratio = recent_volume_avg / historical_volume_avg
                    
                    if volume_ratio > self.volume_threshold:
                        # High volume confirmation
                        if current_size < self.max_position_size:
                            signals.append(ScalingSignal(
                                symbol=self.symbol,
                                scaling_type=ScalingType.VOLUME_CONFIRMATION,
                                action=ScalingAction.ADD_POSITION,
                                size_change=min(self.scaling_increment, self.max_position_size - current_size),
                                price_level=current_price,
                                confidence=min(volume_ratio / self.volume_threshold, 1.0),
                                reasoning=f"Volume confirmation on {timeframe} with ratio {volume_ratio:.3f}",
                                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                                context={
                                    'timeframe': timeframe,
                                    'volume_ratio': volume_ratio,
                                    'trade_direction': trade_direction
                                }
                            ))
            
            # 4. Profit-based scaling
            if 'entry_price' in current_trade:
                entry_price = current_trade['entry_price']
                profit_ratio = abs(current_price - entry_price) / entry_price
                
                if profit_ratio >= 0.5:  # 50% profit
                    # Scale out some position
                    scale_out_size = min(current_size * 0.25, self.scaling_increment)
                    if scale_out_size > 0:
                        signals.append(ScalingSignal(
                            symbol=self.symbol,
                            scaling_type=ScalingType.PROFIT_BASED,
                            action=ScalingAction.REDUCE_POSITION,
                            size_change=-scale_out_size,
                            price_level=current_price,
                            confidence=min(profit_ratio, 1.0),
                            reasoning=f"Profit-based scaling at {profit_ratio:.3f} profit ratio",
                            timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                            context={
                                'timeframe': timeframe,
                                'profit_ratio': profit_ratio,
                                'trade_direction': trade_direction
                            }
                        ))
            
        except Exception as e:
            logger.error(f"Error analyzing timeframe scaling for {timeframe}: {e}")
        
        return signals
    
    def _filter_scaling_signals(self, signals: List[ScalingSignal]) -> List[ScalingSignal]:
        """Filter and prioritize scaling signals"""
        if not signals:
            return []
        
        # Remove conflicting signals
        filtered_signals = []
        seen_actions = set()
        
        for signal in signals:
            key = (signal.scaling_type, signal.action)
            if key not in seen_actions:
                seen_actions.add(key)
                filtered_signals.append(signal)
        
        # Sort by confidence
        filtered_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return filtered_signals
    
    def execute_scaling(self, signal: ScalingSignal, current_position: float) -> float:
        """Execute scaling based on signal"""
        try:
            new_position = current_position + signal.size_change
            
            # Ensure position is within limits
            new_position = max(0.0, min(new_position, self.max_position_size))
            
            # Update position history
            self.position_history.append({
                'timestamp': signal.timestamp_ms,
                'old_position': current_position,
                'new_position': new_position,
                'change': signal.size_change,
                'signal': signal
            })
            
            # Update scaling history
            self.scaling_history.append(signal)
            
            # Update current position
            self.current_position = new_position
            
            logger.info(f"Scaling executed: {signal.size_change:.3f} -> {new_position:.3f} ({signal.reasoning})")
            
            return new_position
            
        except Exception as e:
            logger.error(f"Error executing scaling: {e}")
            return current_position
    
    def get_scaling_recommendation(self, signals: List[ScalingSignal]) -> Optional[ScalingSignal]:
        """Get the highest priority scaling recommendation"""
        if not signals:
            return None
        
        # Return the highest confidence signal
        return signals[0]
    
    def get_scaling_statistics(self) -> Dict[str, Any]:
        """Get scaling statistics"""
        if not self.scaling_history:
            return {'symbol': self.symbol}
        
        # Count by scaling type
        scaling_type_counts = {}
        for signal in self.scaling_history:
            scaling_type = signal.scaling_type.value
            scaling_type_counts[scaling_type] = scaling_type_counts.get(scaling_type, 0) + 1
        
        # Count by action
        action_counts = {}
        for signal in self.scaling_history:
            action = signal.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Calculate average confidence
        avg_confidence = sum(signal.confidence for signal in self.scaling_history) / len(self.scaling_history)
        
        # Calculate total position changes
        total_additions = sum(signal.size_change for signal in self.scaling_history if signal.size_change > 0)
        total_reductions = sum(abs(signal.size_change) for signal in self.scaling_history if signal.size_change < 0)
        
        return {
            'total_signals': len(self.scaling_history),
            'current_position': self.current_position,
            'scaling_type_counts': scaling_type_counts,
            'action_counts': action_counts,
            'average_confidence': avg_confidence,
            'total_additions': total_additions,
            'total_reductions': total_reductions,
            'symbol': self.symbol
        }

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'EURGBPc',
        'scaling_config': {
            'max_position_size': 1.0,
            'scaling_increment': 0.25,
            'structure_break_threshold': 0.7,
            'momentum_threshold': 0.6,
            'volume_threshold': 1.5
        }
    }
    
    # Create scaling manager
    scaling_manager = PartialScalingManager(test_config)
    
    # Simulate market data
    market_data = {
        'H1': {
            'ohlcv': {
                'high': [0.8500, 0.8510, 0.8520, 0.8530, 0.8540],
                'low': [0.8490, 0.8500, 0.8510, 0.8520, 0.8530],
                'close': [0.8495, 0.8505, 0.8515, 0.8525, 0.8535],
                'volume': [1000, 1200, 1100, 1300, 1400]
            }
        },
        'M15': {
            'ohlcv': {
                'high': [0.8500, 0.8505, 0.8510, 0.8515, 0.8520],
                'low': [0.8495, 0.8500, 0.8505, 0.8510, 0.8515],
                'close': [0.8498, 0.8502, 0.8507, 0.8512, 0.8517],
                'volume': [200, 250, 300, 350, 400]
            }
        }
    }
    
    # Simulate current trade
    current_trade = {
        'entry_price': 0.8500,
        'direction': 'BUY',
        'position_size': 0.5
    }
    
    print("Testing Partial Scaling Manager:")
    
    # Analyze scaling opportunities
    scaling_signals = scaling_manager.analyze_scaling_opportunities(market_data, current_trade)
    
    print(f"Found {len(scaling_signals)} scaling signals:")
    for signal in scaling_signals:
        print(f"  {signal.scaling_type.value}: {signal.action.value} {signal.size_change:.3f} ({signal.reasoning})")
    
    # Get recommendation
    recommendation = scaling_manager.get_scaling_recommendation(scaling_signals)
    if recommendation:
        print(f"\nScaling Recommendation: {recommendation.action.value} {recommendation.size_change:.3f}")
        print(f"Reasoning: {recommendation.reasoning}")
        
        # Execute scaling
        new_position = scaling_manager.execute_scaling(recommendation, current_trade['position_size'])
        print(f"New Position Size: {new_position:.3f}")
    
    # Get statistics
    stats = scaling_manager.get_scaling_statistics()
    print(f"\nScaling Statistics: {stats}")
