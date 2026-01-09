"""
Hot-Path Architecture for Multi-Timeframe Trading
Memory-first approach with ring buffers and async DB writes
"""

import numpy as np
import asyncio
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import queue
import json

logger = logging.getLogger(__name__)

@dataclass
class TickEvent:
    """Tick event for hot path processing"""
    symbol: str
    timestamp_utc: int
    bid: float
    ask: float
    volume: float
    source: str  # 'mt5' or 'binance'
    sequence_id: int

@dataclass
class FeatureVector:
    """Feature vector for hot path computation"""
    symbol: str
    timestamp_utc: int
    vwap: float
    atr: float
    delta: float
    spread: float
    volume: float
    features: Dict[str, float]

@dataclass
class DecisionEvent:
    """Decision event for hot path processing"""
    symbol: str
    timestamp_utc: int
    decision: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    reasoning: str

class RingBuffer:
    """High-performance ring buffer for hot path data"""
    
    def __init__(self, capacity: int, dtype=np.float32):  # Use float32 instead of float64
        # Further reduce capacity for memory efficiency
        self.capacity = min(capacity, 2000)  # Cap at 2k for memory efficiency
        self.buffer = np.zeros(self.capacity, dtype=dtype)
        self.write_index = 0
        self.size = 0
        self.lock = threading.RLock()
        
    def append(self, value: float):
        """Append value to ring buffer"""
        with self.lock:
            self.buffer[self.write_index] = value
            self.write_index = (self.write_index + 1) % self.capacity
            if self.size < self.capacity:
                self.size += 1
                
    def get_latest(self, n: int = 1) -> np.ndarray:
        """Get latest n values"""
        with self.lock:
            if self.size == 0:
                return np.array([])
                
            if n >= self.size:
                return self.buffer[:self.size]
                
            start_idx = (self.write_index - n) % self.capacity
            if start_idx + n <= self.capacity:
                return self.buffer[start_idx:start_idx + n]
            else:
                # Wrap around case
                part1 = self.buffer[start_idx:]
                part2 = self.buffer[:n - len(part1)]
                return np.concatenate([part1, part2])
                
    def get_all(self) -> np.ndarray:
        """Get all values in chronological order"""
        with self.lock:
            if self.size == 0:
                return np.array([])
                
            if self.size < self.capacity:
                return self.buffer[:self.size]
            else:
                # Full buffer, need to reorder
                return np.concatenate([
                    self.buffer[self.write_index:],
                    self.buffer[:self.write_index]
                ])

class HotPathProcessor:
    """Hot path processor for real-time trading decisions"""
    
    def __init__(self, symbol: str, config: Dict[str, Any]):
        self.symbol = symbol
        self.config = config
        # Reduce capacity for memory efficiency and laptop safety
        self.capacity = min(config.get('buffer_capacity', 1000), 1000)  # Cap at 1k (safe for laptops)
        
        # Ring buffers for different data types (use float32 for memory efficiency)
        self.price_buffer = RingBuffer(self.capacity, dtype=np.float32)
        self.volume_buffer = RingBuffer(self.capacity, dtype=np.float32)
        self.spread_buffer = RingBuffer(self.capacity, dtype=np.float32)
        self.timestamp_buffer = RingBuffer(self.capacity, dtype=np.int32)  # Use int32
        
        # Feature buffers (use float32)
        self.vwap_buffer = RingBuffer(self.capacity, dtype=np.float32)
        self.atr_buffer = RingBuffer(self.capacity, dtype=np.float32)
        self.delta_buffer = RingBuffer(self.capacity, dtype=np.float32)
        
        # Decision queue (reduced size)
        self.decision_queue = queue.Queue(maxsize=100)  # Reduced from 1000
        
        # Performance tracking (reduced size)
        self.latency_histogram = deque(maxlen=100)  # Reduced from 1000
        self.queue_depths = deque(maxlen=50)  # Reduced from 100
        
        # Thread safety
        self.lock = threading.RLock()
        self.running = False
        
    def add_tick(self, tick: TickEvent):
        """Add tick to hot path processing"""
        try:
            start_time = time.perf_counter_ns()
            
            with self.lock:
                # Add to buffers
                mid_price = (tick.bid + tick.ask) / 2
                spread = tick.ask - tick.bid
                
                self.price_buffer.append(mid_price)
                self.volume_buffer.append(tick.volume)
                self.spread_buffer.append(spread)
                self.timestamp_buffer.append(tick.timestamp_utc)
                
                # Only compute features every 10th tick to reduce CPU load
                if len(self.latency_histogram) % 10 == 0:
                    self._compute_features()
                    
                    # Make decision if conditions met
                    decision = self._make_decision(tick)
                    if decision:
                        try:
                            self.decision_queue.put(decision, block=False)
                        except queue.Full:
                            pass  # Silently drop if queue is full
                    
            # Track latency
            end_time = time.perf_counter_ns()
            latency_ms = (end_time - start_time) / 1_000_000
            self.latency_histogram.append(latency_ms)
            
        except Exception as e:
            logger.error(f"Error processing tick for {self.symbol}: {e}")
            
    def _compute_features(self):
        """Compute features in-place using NumPy"""
        try:
            # Get recent data
            prices = self.price_buffer.get_latest(100)  # Last 100 ticks
            volumes = self.volume_buffer.get_latest(100)
            spreads = self.spread_buffer.get_latest(100)
            
            if len(prices) < 10:  # Need minimum data
                return
                
            # Compute VWAP
            if len(volumes) > 0 and np.sum(volumes) > 0:
                vwap = np.sum(prices * volumes) / np.sum(volumes)
                self.vwap_buffer.append(vwap)
                
            # Compute ATR (simplified)
            if len(prices) >= 14:
                price_changes = np.abs(np.diff(prices[-14:]))
                atr = np.mean(price_changes)
                self.atr_buffer.append(atr)
                
            # Compute delta proxy
            if len(prices) >= 2:
                delta = prices[-1] - prices[-2]
                self.delta_buffer.append(delta)
                
        except Exception as e:
            logger.error(f"Error computing features for {self.symbol}: {e}")
            
    def _make_decision(self, tick: TickEvent) -> Optional[DecisionEvent]:
        """Make trading decision based on current state"""
        try:
            # Get latest features
            latest_prices = self.price_buffer.get_latest(5)
            latest_vwap = self.vwap_buffer.get_latest(1)
            latest_atr = self.atr_buffer.get_latest(1)
            latest_delta = self.delta_buffer.get_latest(1)
            
            if len(latest_prices) < 5 or len(latest_vwap) == 0:
                return None
                
            current_price = latest_prices[-1]
            
            # Simple decision logic (would be replaced with full MTF analysis)
            vwap = latest_vwap[0] if len(latest_vwap) > 0 else current_price
            atr = latest_atr[0] if len(latest_atr) > 0 else 0.001
            delta = latest_delta[0] if len(latest_delta) > 0 else 0
            
            # Check for signal conditions
            price_above_vwap = current_price > vwap
            positive_delta = delta > 0
            sufficient_atr = atr > 0.0005  # Minimum volatility
            
            if price_above_vwap and positive_delta and sufficient_atr:
                # Generate buy signal
                stop_loss = current_price - (atr * 2)
                take_profit = current_price + (atr * 6)
                
                return DecisionEvent(
                    symbol=self.symbol,
                    timestamp_utc=tick.timestamp_utc,
                    decision="BUY",
                    confidence=0.7,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    lot_size=0.01,
                    reasoning="Hot path signal: price above VWAP, positive delta, sufficient ATR"
                )
                
            return None
            
        except Exception as e:
            logger.error(f"Error making decision for {self.symbol}: {e}")
            return None
            
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        try:
            with self.lock:
                if not self.latency_histogram:
                    return {}
                    
                latencies = list(self.latency_histogram)
                
                return {
                    "symbol": self.symbol,
                    "latency_p50": np.percentile(latencies, 50),
                    "latency_p95": np.percentile(latencies, 95),
                    "latency_p99": np.percentile(latencies, 99),
                    "queue_depth": self.decision_queue.qsize(),
                    "buffer_utilization": self.price_buffer.size / self.capacity,
                    "total_ticks_processed": len(self.latency_histogram)
                }
                
        except Exception as e:
            logger.error(f"Error getting performance metrics for {self.symbol}: {e}")
            return {}

class AsyncDBWriter:
    """Async database writer for hot path data"""
    
    def __init__(self, db_schema, batch_size: int = 100, flush_interval: float = 1.0):
        self.db_schema = db_schema
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.write_queue = asyncio.Queue(maxsize=10000)
        self.running = False
        self.writer_task = None
        
    async def start(self):
        """Start async writer"""
        self.running = True
        self.writer_task = asyncio.create_task(self._writer_loop())
        
    async def stop(self):
        """Stop async writer"""
        self.running = False
        if self.writer_task:
            await self.writer_task
            
    async def write_decision(self, decision: DecisionEvent):
        """Queue decision for writing"""
        try:
            await self.write_queue.put(decision)
        except asyncio.QueueFull:
            logger.warning("Write queue full, dropping decision")
            
    async def _writer_loop(self):
        """Main writer loop"""
        batch = []
        last_flush = time.time()
        
        while self.running:
            try:
                # Get item from queue with timeout
                try:
                    item = await asyncio.wait_for(
                        self.write_queue.get(), 
                        timeout=0.1
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass
                    
                # Flush if batch is full or time interval passed
                current_time = time.time()
                if (len(batch) >= self.batch_size or 
                    (batch and current_time - last_flush >= self.flush_interval)):
                    
                    if batch:
                        await self._flush_batch(batch)
                        batch = []
                        last_flush = current_time
                        
            except Exception as e:
                logger.error(f"Error in writer loop: {e}")
                await asyncio.sleep(0.1)
                
        # Flush remaining items
        if batch:
            await self._flush_batch(batch)
            
    async def _flush_batch(self, batch: List[DecisionEvent]):
        """Flush batch to database"""
        try:
            for decision in batch:
                # Convert to database format and write
                # This would use the actual database schema
                pass
                
            logger.debug(f"Flushed {len(batch)} decisions to database")
            
        except Exception as e:
            logger.error(f"Error flushing batch: {e}")

class HotPathManager:
    """Manager for hot path architecture"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processors: Dict[str, HotPathProcessor] = {}
        self.db_writer = None
        self.running = False
        
    def add_symbol(self, symbol: str, symbol_config: Dict[str, Any]):
        """Add symbol to hot path processing"""
        try:
            processor = HotPathProcessor(symbol, symbol_config)
            self.processors[symbol] = processor
            logger.info(f"Added {symbol} to hot path processing")
            
        except Exception as e:
            logger.error(f"Error adding symbol {symbol}: {e}")
            
    def process_tick(self, symbol: str, tick: TickEvent):
        """Process tick through hot path"""
        try:
            if symbol in self.processors:
                self.processors[symbol].add_tick(tick)
            else:
                logger.warning(f"No processor found for symbol {symbol}")
                
        except Exception as e:
            logger.error(f"Error processing tick for {symbol}: {e}")
            
    def get_decision(self, symbol: str) -> Optional[DecisionEvent]:
        """Get latest decision for symbol"""
        try:
            if symbol in self.processors:
                processor = self.processors[symbol]
                try:
                    return processor.decision_queue.get_nowait()
                except queue.Empty:
                    return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting decision for {symbol}: {e}")
            return None
            
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all symbols"""
        metrics = {}
        for symbol, processor in self.processors.items():
            metrics[symbol] = processor.get_performance_metrics()
        return metrics
        
    async def start_db_writer(self, db_schema):
        """Start async database writer"""
        try:
            self.db_writer = AsyncDBWriter(db_schema)
            await self.db_writer.start()
            logger.info("Started async database writer")
            
        except Exception as e:
            logger.error(f"Error starting database writer: {e}")
            
    async def stop_db_writer(self):
        """Stop async database writer"""
        try:
            if self.db_writer:
                await self.db_writer.stop()
                logger.info("Stopped async database writer")
                
        except Exception as e:
            logger.error(f"Error stopping database writer: {e}")


# Example usage and testing
if __name__ == "__main__":
    # Test hot path architecture
    config = {
        'buffer_capacity': 1000,
        'batch_size': 50,
        'flush_interval': 1.0
    }
    
    manager = HotPathManager(config)
    
    # Add test symbols
    manager.add_symbol("BTCUSDc", config)
    manager.add_symbol("XAUUSDc", config)
    
    # Test with sample ticks
    current_time = int(datetime.now(timezone.utc).timestamp())
    
    for i in range(100):
        tick = TickEvent(
            symbol="BTCUSDc",
            timestamp_utc=current_time + i,
            bid=50000.0 + i * 0.1,
            ask=50000.5 + i * 0.1,
            volume=100 + i,
            source="mt5",
            sequence_id=i
        )
        
        manager.process_tick("BTCUSDc", tick)
        
        # Check for decisions
        decision = manager.get_decision("BTCUSDc")
        if decision:
            print(f"Decision: {decision.decision} at {decision.entry_price:.2f}")
            
    # Get performance metrics
    metrics = manager.get_performance_metrics()
    print(f"Performance metrics: {metrics}")
