"""
Dynamic Stop Management System
Adaptive stop loss management based on market structure and volatility
"""

import numpy as np
from numba import jit, prange
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class StopType(Enum):
    """Stop loss types"""
    FIXED = "fixed"
    TRAILING = "trailing"
    BREAKEVEN = "breakeven"
    STRUCTURE_BASED = "structure_based"
    VOLATILITY_BASED = "volatility_based"
    TIME_BASED = "time_based"

class StopStatus(Enum):
    """Stop loss status"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    UPDATED = "updated"

@dataclass
class StopLoss:
    """Stop loss data structure"""
    symbol: str
    stop_type: StopType
    stop_price: float
    entry_price: float
    current_price: float
    atr_value: float
    confidence: float
    reasoning: str
    timestamp_ms: int
    status: StopStatus
    context: Dict[str, Any]

class DynamicStopManager:
    """Dynamic stop loss management system"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.symbol = symbol_config.get('symbol', 'unknown')
        
        # Stop configuration
        self.stop_config = symbol_config.get('stop_config', {})
        self.initial_stop_atr_multiplier = self.stop_config.get('initial_stop_atr_multiplier', 2.0)
        self.trailing_stop_atr_multiplier = self.stop_config.get('trailing_stop_atr_multiplier', 1.5)
        self.breakeven_threshold = self.stop_config.get('breakeven_threshold', 1.0)
        self.max_stop_distance = self.stop_config.get('max_stop_distance', 0.05)  # 5%
        
        # Active stops
        self.active_stops = {}
        self.stop_history = []
        
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_atr_stop(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        atr_period: int,
        atr_multiplier: float,
        trade_direction: int  # 1 for long, -1 for short
    ) -> float:
        """Calculate ATR-based stop using Numba"""
        if len(highs) < atr_period:
            return 0.0
        
        # Calculate True Range
        tr_values = np.zeros(len(highs))
        tr_values[0] = highs[0] - lows[0]
        
        for i in range(1, len(highs)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr_values[i] = max(hl, hc, lc)
        
        # Calculate ATR
        atr = np.mean(tr_values[-atr_period:])
        
        # Calculate stop based on trade direction
        if trade_direction == 1:  # Long trade
            stop_price = closes[-1] - (atr * atr_multiplier)
        else:  # Short trade
            stop_price = closes[-1] + (atr * atr_multiplier)
        
        return stop_price
    
    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_structure_stop(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        trade_direction: int,
        lookback: int
    ) -> float:
        """Calculate structure-based stop using Numba"""
        if len(highs) < lookback:
            return 0.0
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        if trade_direction == 1:  # Long trade
            # Find recent swing low
            swing_low = np.min(recent_lows)
            # Add small buffer
            stop_price = swing_low * 0.999
        else:  # Short trade
            # Find recent swing high
            swing_high = np.max(recent_highs)
            # Add small buffer
            stop_price = swing_high * 1.001
        
        return stop_price
    
    def create_initial_stop(
        self, 
        trade_data: Dict[str, Any], 
        market_data: Dict[str, Any]
    ) -> StopLoss:
        """Create initial stop loss for a trade"""
        try:
            entry_price = trade_data['entry_price']
            direction = trade_data['direction']
            trade_direction = 1 if direction == 'BUY' else -1
            
            # Get OHLCV data
            ohlcv = market_data.get('ohlcv', {})
            if not ohlcv:
                raise ValueError("No OHLCV data available")
            
            highs = np.array(ohlcv['high'], dtype=np.float32)
            lows = np.array(ohlcv['low'], dtype=np.float32)
            closes = np.array(ohlcv['close'], dtype=np.float32)
            
            # Calculate ATR
            atr_period = 14
            atr_stop = self.calculate_atr_stop(
                highs, lows, closes, atr_period, 
                self.initial_stop_atr_multiplier, trade_direction
            )
            
            # Calculate structure stop
            structure_stop = self.calculate_structure_stop(
                highs, lows, closes, trade_direction, 20
            )
            
            # Choose the more conservative stop
            if trade_direction == 1:  # Long
                stop_price = max(atr_stop, structure_stop)
            else:  # Short
                stop_price = min(atr_stop, structure_stop)
            
            # Ensure stop is within maximum distance
            max_distance = entry_price * self.max_stop_distance
            if trade_direction == 1:  # Long
                stop_price = max(stop_price, entry_price - max_distance)
            else:  # Short
                stop_price = min(stop_price, entry_price + max_distance)
            
            # Calculate confidence
            atr_distance = abs(entry_price - atr_stop) / entry_price
            structure_distance = abs(entry_price - structure_stop) / entry_price
            confidence = 1.0 - min(atr_distance, structure_distance) / self.max_stop_distance
            
            stop_loss = StopLoss(
                symbol=self.symbol,
                stop_type=StopType.FIXED,
                stop_price=stop_price,
                entry_price=entry_price,
                current_price=entry_price,
                atr_value=atr_distance * entry_price,
                confidence=confidence,
                reasoning=f"Initial stop: ATR={atr_stop:.4f}, Structure={structure_stop:.4f}",
                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                status=StopStatus.ACTIVE,
                context={
                    'atr_stop': atr_stop,
                    'structure_stop': structure_stop,
                    'trade_direction': trade_direction
                }
            )
            
            # Store active stop
            trade_id = trade_data.get('trade_id', f"{self.symbol}_{int(datetime.now().timestamp())}")
            self.active_stops[trade_id] = stop_loss
            
            return stop_loss
            
        except Exception as e:
            logger.error(f"Error creating initial stop: {e}")
            raise
    
    def update_stop_loss(
        self, 
        trade_id: str, 
        current_price: float, 
        market_data: Dict[str, Any]
    ) -> Optional[StopLoss]:
        """Update stop loss based on current market conditions"""
        try:
            if trade_id not in self.active_stops:
                return None
            
            current_stop = self.active_stops[trade_id]
            trade_direction = 1 if current_stop.entry_price < current_price else -1
            
            # Check if stop should be triggered
            if self._should_trigger_stop(current_stop, current_price):
                current_stop.status = StopStatus.TRIGGERED
                current_stop.current_price = current_price
                self.stop_history.append(current_stop)
                del self.active_stops[trade_id]
                return current_stop
            
            # Update stop based on market conditions
            updated_stop = self._calculate_updated_stop(
                current_stop, current_price, market_data
            )
            
            if updated_stop and updated_stop.stop_price != current_stop.stop_price:
                current_stop.stop_price = updated_stop.stop_price
                current_stop.stop_type = updated_stop.stop_type
                current_stop.reasoning = updated_stop.reasoning
                current_stop.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                current_stop.status = StopStatus.UPDATED
                current_stop.current_price = current_price
                
                return current_stop
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating stop loss: {e}")
            return None
    
    def _should_trigger_stop(self, stop: StopLoss, current_price: float) -> bool:
        """Check if stop should be triggered"""
        trade_direction = 1 if stop.entry_price < current_price else -1
        
        if trade_direction == 1:  # Long trade
            return current_price <= stop.stop_price
        else:  # Short trade
            return current_price >= stop.stop_price
    
    def _calculate_updated_stop(
        self, 
        current_stop: StopLoss, 
        current_price: float, 
        market_data: Dict[str, Any]
    ) -> Optional[StopLoss]:
        """Calculate updated stop based on market conditions"""
        try:
            trade_direction = 1 if current_stop.entry_price < current_price else -1
            
            # Check for breakeven opportunity
            profit_ratio = abs(current_price - current_stop.entry_price) / current_stop.entry_price
            
            if profit_ratio >= self.breakeven_threshold:
                # Move to breakeven
                new_stop = StopLoss(
                    symbol=current_stop.symbol,
                    stop_type=StopType.BREAKEVEN,
                    stop_price=current_stop.entry_price,
                    entry_price=current_stop.entry_price,
                    current_price=current_price,
                    atr_value=current_stop.atr_value,
                    confidence=1.0,
                    reasoning="Moved to breakeven due to profit threshold",
                    timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                    status=StopStatus.ACTIVE,
                    context=current_stop.context
                )
                return new_stop
            
            # Check for trailing stop opportunity
            if profit_ratio >= 0.5:  # 50% profit
                ohlcv = market_data.get('ohlcv', {})
                if ohlcv:
                    highs = np.array(ohlcv['high'], dtype=np.float32)
                    lows = np.array(ohlcv['low'], dtype=np.float32)
                    closes = np.array(ohlcv['close'], dtype=np.float32)
                    
                    # Calculate trailing stop
                    atr_stop = self.calculate_atr_stop(
                        highs, lows, closes, 14, 
                        self.trailing_stop_atr_multiplier, trade_direction
                    )
                    
                    # Only update if trailing stop is better
                    if trade_direction == 1:  # Long
                        if atr_stop > current_stop.stop_price:
                            new_stop = StopLoss(
                                symbol=current_stop.symbol,
                                stop_type=StopType.TRAILING,
                                stop_price=atr_stop,
                                entry_price=current_stop.entry_price,
                                current_price=current_price,
                                atr_value=current_stop.atr_value,
                                confidence=0.8,
                                reasoning="Trailing stop updated based on ATR",
                                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                                status=StopStatus.ACTIVE,
                                context=current_stop.context
                            )
                            return new_stop
                    else:  # Short
                        if atr_stop < current_stop.stop_price:
                            new_stop = StopLoss(
                                symbol=current_stop.symbol,
                                stop_type=StopType.TRAILING,
                                stop_price=atr_stop,
                                entry_price=current_stop.entry_price,
                                current_price=current_price,
                                atr_value=current_stop.atr_value,
                                confidence=0.8,
                                reasoning="Trailing stop updated based on ATR",
                                timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000),
                                status=StopStatus.ACTIVE,
                                context=current_stop.context
                            )
                            return new_stop
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating updated stop: {e}")
            return None
    
    def cancel_stop(self, trade_id: str, reason: str = "Manual cancellation"):
        """Cancel an active stop loss"""
        if trade_id in self.active_stops:
            stop = self.active_stops[trade_id]
            stop.status = StopStatus.CANCELLED
            stop.reasoning = reason
            stop.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            self.stop_history.append(stop)
            del self.active_stops[trade_id]
            return stop
        return None
    
    def get_active_stops(self) -> Dict[str, StopLoss]:
        """Get all active stop losses"""
        return self.active_stops.copy()
    
    def get_stop_statistics(self) -> Dict[str, Any]:
        """Get stop loss statistics"""
        if not self.stop_history:
            return {'symbol': self.symbol}
        
        # Count by stop type
        stop_type_counts = {}
        for stop in self.stop_history:
            stop_type = stop.stop_type.value
            stop_type_counts[stop_type] = stop_type_counts.get(stop_type, 0) + 1
        
        # Count by status
        status_counts = {}
        for stop in self.stop_history:
            status = stop.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate average confidence
        avg_confidence = sum(stop.confidence for stop in self.stop_history) / len(self.stop_history)
        
        return {
            'total_stops': len(self.stop_history),
            'active_stops': len(self.active_stops),
            'stop_type_counts': stop_type_counts,
            'status_counts': status_counts,
            'average_confidence': avg_confidence,
            'symbol': self.symbol
        }

# Example usage and testing
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'symbol': 'GBPJPYc',
        'stop_config': {
            'initial_stop_atr_multiplier': 2.0,
            'trailing_stop_atr_multiplier': 1.5,
            'breakeven_threshold': 1.0,
            'max_stop_distance': 0.05
        }
    }
    
    # Create stop manager
    stop_manager = DynamicStopManager(test_config)
    
    # Simulate trade data
    trade_data = {
        'trade_id': 'test_trade_1',
        'entry_price': 150.0,
        'direction': 'BUY'
    }
    
    # Simulate market data
    market_data = {
        'ohlcv': {
            'high': [150.0, 151.0, 152.0, 153.0, 154.0],
            'low': [149.0, 150.0, 151.0, 152.0, 153.0],
            'close': [149.5, 150.5, 151.5, 152.5, 153.5],
            'volume': [1000, 1200, 1100, 1300, 1400]
        }
    }
    
    print("Testing Dynamic Stop Manager:")
    
    # Create initial stop
    initial_stop = stop_manager.create_initial_stop(trade_data, market_data)
    print(f"Initial Stop: {initial_stop.stop_price:.4f} ({initial_stop.reasoning})")
    
    # Update stop with higher price
    updated_stop = stop_manager.update_stop_loss(
        'test_trade_1', 152.0, market_data
    )
    if updated_stop:
        print(f"Updated Stop: {updated_stop.stop_price:.4f} ({updated_stop.reasoning})")
    
    # Get statistics
    stats = stop_manager.get_stop_statistics()
    print(f"\nStop Statistics: {stats}")
