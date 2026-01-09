"""
Trading Event Schemas
Defines standardized event schemas for the multi-timeframe trading system
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import numpy as np
from datetime import datetime, timezone

class EventType(Enum):
    """Event types for the trading system"""
    TICK = "tick"
    OHLCV_BAR = "ohlcv_bar"
    MARKET_STRUCTURE = "market_structure"
    M1_FILTER_SIGNAL = "m1_filter_signal"
    TRADE_DECISION = "trade_decision"
    DTMS_EXIT_SIGNAL = "dtms_exit_signal"
    PERFORMANCE_METRIC = "performance_metric"
    BINANCE_ORDER_BOOK = "binance_order_book"

class SourceType(Enum):
    """Data source types"""
    MT5 = "mt5"
    BINANCE = "binance"
    CALCULATED = "calculated"

class DirectionType(Enum):
    """Direction types for market structure"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

@dataclass
class TickEvent:
    """Standardized tick event schema"""
    symbol: str
    timestamp_ms: int
    bid: float
    ask: float
    last: Optional[float] = None
    volume: float = 0.0
    source: SourceType = SourceType.MT5
    sequence_id: int = 0
    
    def __post_init__(self):
        """Validate tick event data"""
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("Bid and ask must be positive")
        if self.bid > self.ask:
            raise ValueError("Bid cannot be greater than ask")
        if self.timestamp_ms <= 0:
            raise ValueError("Timestamp must be positive")

@dataclass
class OHLCVBarEvent:
    """Standardized OHLCV bar event schema"""
    symbol: str
    timeframe: str
    timestamp_open_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    tick_volume: int = 0
    spread: float = 0.0
    
    def __post_init__(self):
        """Validate OHLCV bar data"""
        if not all(x > 0 for x in [self.open, self.high, self.low, self.close]):
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("Invalid OHLC relationships")

@dataclass
class MarketStructureEvent:
    """Standardized market structure event schema"""
    symbol: str
    timeframe: str
    timestamp_ms: int
    structure_type: str  # 'CHOCH', 'BOS', 'OrderBlock', 'Liquidity'
    price_level: float
    direction: Optional[DirectionType] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate market structure data"""
        if self.price_level <= 0:
            raise ValueError("Price level must be positive")
        if self.structure_type not in ['CHOCH', 'BOS', 'OrderBlock', 'Liquidity']:
            raise ValueError("Invalid structure type")

@dataclass
class M1FilterSignalEvent:
    """Standardized M1 filter signal event schema"""
    symbol: str
    timestamp_ms: int
    filter_type: str  # 'VWAP_Reclaim', 'Volume_Delta_Spike', 'Micro_BOS', 'ATR_Ratio', 'Spread_Filter'
    signal_value: float
    is_confirmed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate M1 filter signal data"""
        if self.filter_type not in ['VWAP_Reclaim', 'Volume_Delta_Spike', 'Micro_BOS', 'ATR_Ratio', 'Spread_Filter']:
            raise ValueError("Invalid filter type")

@dataclass
class TradeDecisionEvent:
    """Standardized trade decision event schema"""
    symbol: str
    timestamp_ms: int
    decision_type: str  # 'ENTRY', 'EXIT', 'ADJUSTMENT'
    direction: Optional[str] = None  # 'BUY', 'SELL'
    price: Optional[float] = None
    volume: Optional[float] = None
    reason: str = ""
    decision_context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate trade decision data"""
        if self.decision_type not in ['ENTRY', 'EXIT', 'ADJUSTMENT']:
            raise ValueError("Invalid decision type")
        if self.direction and self.direction not in ['BUY', 'SELL']:
            raise ValueError("Invalid direction")

@dataclass
class DTMSExitSignalEvent:
    """Standardized DTMS exit signal event schema"""
    symbol: str
    trade_id: Optional[str] = None
    timestamp_ms: int = 0
    exit_type: str = ""  # 'StopLoss', 'TakeProfit', 'TrailingStop', 'AdaptiveHedge', 'IntelligentExit'
    exit_price: float = 0.0
    reason: str = ""
    exit_context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate DTMS exit signal data"""
        if self.exit_type not in ['StopLoss', 'TakeProfit', 'TrailingStop', 'AdaptiveHedge', 'IntelligentExit']:
            raise ValueError("Invalid exit type")
        if self.exit_price <= 0:
            raise ValueError("Exit price must be positive")

@dataclass
class PerformanceMetricEvent:
    """Standardized performance metric event schema"""
    symbol: str
    timeframe: Optional[str] = None
    timestamp_ms: int = 0
    metric_name: str = ""
    metric_value: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BinanceOrderBookEvent:
    """Standardized Binance order book event schema"""
    symbol: str
    timestamp_ms: int
    bids: List[List[float]] = field(default_factory=list)  # [[price, quantity], ...]
    asks: List[List[float]] = field(default_factory=list)  # [[price, quantity], ...]
    last_update_id: int = 0
    
    def __post_init__(self):
        """Validate Binance order book data"""
        for bid in self.bids:
            if len(bid) != 2 or bid[0] <= 0 or bid[1] <= 0:
                raise ValueError("Invalid bid format")
        for ask in self.asks:
            if len(ask) != 2 or ask[0] <= 0 or ask[1] <= 0:
                raise ValueError("Invalid ask format")

# Ring Buffer Configuration
@dataclass
class RingBufferConfig:
    """Configuration for ring buffers"""
    tick_capacity: int = 10000
    ohlcv_capacity: int = 5000
    structure_capacity: int = 1000
    signal_capacity: int = 2000
    decision_capacity: int = 1000
    exit_capacity: int = 500
    performance_capacity: int = 1000
    order_book_capacity: int = 1000
    
    # Memory optimization settings
    use_float32: bool = True
    use_int32: bool = True
    compression_enabled: bool = True
    
    def get_capacity(self, event_type: EventType) -> int:
        """Get capacity for specific event type"""
        capacity_map = {
            EventType.TICK: self.tick_capacity,
            EventType.OHLCV_BAR: self.ohlcv_capacity,
            EventType.MARKET_STRUCTURE: self.structure_capacity,
            EventType.M1_FILTER_SIGNAL: self.signal_capacity,
            EventType.TRADE_DECISION: self.decision_capacity,
            EventType.DTMS_EXIT_SIGNAL: self.exit_capacity,
            EventType.PERFORMANCE_METRIC: self.performance_capacity,
            EventType.BINANCE_ORDER_BOOK: self.order_book_capacity
        }
        return capacity_map.get(event_type, 1000)

# Event Serialization
class EventSerializer:
    """Serializes events for storage and transmission"""
    
    @staticmethod
    def serialize_tick(tick: TickEvent) -> Dict[str, Any]:
        """Serialize tick event"""
        return {
            'symbol': tick.symbol,
            'timestamp_ms': tick.timestamp_ms,
            'bid': tick.bid,
            'ask': tick.ask,
            'last': tick.last,
            'volume': tick.volume,
            'source': tick.source.value,
            'sequence_id': tick.sequence_id
        }
    
    @staticmethod
    def deserialize_tick(data: Dict[str, Any]) -> TickEvent:
        """Deserialize tick event"""
        return TickEvent(
            symbol=data['symbol'],
            timestamp_ms=data['timestamp_ms'],
            bid=data['bid'],
            ask=data['ask'],
            last=data.get('last'),
            volume=data.get('volume', 0.0),
            source=SourceType(data.get('source', 'mt5')),
            sequence_id=data.get('sequence_id', 0)
        )
    
    @staticmethod
    def serialize_ohlcv(bar: OHLCVBarEvent) -> Dict[str, Any]:
        """Serialize OHLCV bar event"""
        return {
            'symbol': bar.symbol,
            'timeframe': bar.timeframe,
            'timestamp_open_ms': bar.timestamp_open_ms,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'tick_volume': bar.tick_volume,
            'spread': bar.spread
        }
    
    @staticmethod
    def deserialize_ohlcv(data: Dict[str, Any]) -> OHLCVBarEvent:
        """Deserialize OHLCV bar event"""
        return OHLCVBarEvent(
            symbol=data['symbol'],
            timeframe=data['timeframe'],
            timestamp_open_ms=data['timestamp_open_ms'],
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=data.get('volume', 0.0),
            tick_volume=data.get('tick_volume', 0),
            spread=data.get('spread', 0.0)
        )

# Event Validation
class EventValidator:
    """Validates events for consistency and correctness"""
    
    @staticmethod
    def validate_tick_sequence(ticks: List[TickEvent]) -> bool:
        """Validate tick sequence for consistency"""
        if not ticks:
            return True
        
        # Check timestamp ordering
        for i in range(1, len(ticks)):
            if ticks[i].timestamp_ms < ticks[i-1].timestamp_ms:
                return False
        
        # Check sequence ID ordering
        for i in range(1, len(ticks)):
            if ticks[i].sequence_id <= ticks[i-1].sequence_id:
                return False
        
        return True
    
    @staticmethod
    def validate_ohlcv_sequence(bars: List[OHLCVBarEvent]) -> bool:
        """Validate OHLCV bar sequence for consistency"""
        if not bars:
            return True
        
        # Check timestamp ordering
        for i in range(1, len(bars)):
            if bars[i].timestamp_open_ms <= bars[i-1].timestamp_open_ms:
                return False
        
        return True
    
    @staticmethod
    def validate_price_consistency(ticks: List[TickEvent], bars: List[OHLCVBarEvent]) -> bool:
        """Validate price consistency between ticks and bars"""
        if not ticks or not bars:
            return True
        
        # This would implement more sophisticated price validation
        # For now, just return True
        return True

# Event Statistics
@dataclass
class EventStatistics:
    """Statistics for event processing"""
    total_events: int = 0
    events_by_type: Dict[EventType, int] = field(default_factory=dict)
    events_by_symbol: Dict[str, int] = field(default_factory=dict)
    events_by_source: Dict[SourceType, int] = field(default_factory=dict)
    processing_latency_ms: List[float] = field(default_factory=list)
    error_count: int = 0
    
    def add_event(self, event_type: EventType, symbol: str, source: SourceType, latency_ms: float = 0.0):
        """Add event statistics"""
        self.total_events += 1
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1
        self.events_by_symbol[symbol] = self.events_by_symbol.get(symbol, 0) + 1
        self.events_by_source[source] = self.events_by_source.get(source, 0) + 1
        if latency_ms > 0:
            self.processing_latency_ms.append(latency_ms)
    
    def get_average_latency(self) -> float:
        """Get average processing latency"""
        if not self.processing_latency_ms:
            return 0.0
        return sum(self.processing_latency_ms) / len(self.processing_latency_ms)
    
    def get_p95_latency(self) -> float:
        """Get 95th percentile latency"""
        if not self.processing_latency_ms:
            return 0.0
        sorted_latencies = sorted(self.processing_latency_ms)
        p95_index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]
