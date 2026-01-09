"""
Hot Path Manager
Ensures the hot path never blocks on I/O operations
All database writes are async and non-blocking
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from collections import deque
import queue
import weakref

from .async_db_writer import AsyncDBWriter, WriteOperation
from .optimized_ring_buffers import OptimizedRingBuffer, MultiSymbolRingBuffer, FeatureRingBuffer
from app.schemas.trading_events import TickEvent, OHLCVBarEvent, MarketStructureEvent, EventType

logger = logging.getLogger(__name__)

@dataclass
class HotPathConfig:
    """Configuration for hot path processing"""
    max_queue_size: int = 10000
    batch_size: int = 100
    batch_timeout_ms: int = 50
    enable_circuit_breakers: bool = True
    memory_limit_mb: int = 500
    cpu_limit_percent: float = 80.0
    latency_threshold_ms: float = 200.0
    db_path: Optional[str] = None

class HotPathManager:
    """
    Manages the hot path processing pipeline
    Ensures no I/O blocking in the critical path
    """
    
    def __init__(self, config: Optional[Union[HotPathConfig, str]] = None):
        if isinstance(config, str):
            # If string is passed, create config with db_path
            self.config = HotPathConfig(db_path=config)
        else:
            self.config = config or HotPathConfig()
        
        # Async database writer
        self.db_writer: Optional[AsyncDBWriter] = None
        
        # Ring buffers for different data types
        self.tick_buffers: Dict[str, OptimizedRingBuffer] = {}
        self.feature_buffers: Dict[str, FeatureRingBuffer] = {}
        self.multi_symbol_buffer: Optional[MultiSymbolRingBuffer] = None
        
        # Processing queues (non-blocking)
        self.tick_queue = queue.Queue(maxsize=self.config.max_queue_size)
        self.feature_queue = queue.Queue(maxsize=self.config.max_queue_size)
        self.decision_queue = queue.Queue(maxsize=self.config.max_queue_size)
        
        # Performance monitoring
        self.stats = {
            'ticks_processed': 0,
            'features_calculated': 0,
            'decisions_made': 0,
            'queue_overflows': 0,
            'avg_processing_time_ns': 0.0,
            'max_processing_time_ns': 0.0,
            'current_queue_sizes': {
                'tick_queue': 0,
                'feature_queue': 0,
                'decision_queue': 0
            }
        }
        
        # Thread safety
        self.lock = threading.RLock()
        self.running = False
        
        # Processing threads
        self.tick_processor_thread: Optional[threading.Thread] = None
        self.feature_processor_thread: Optional[threading.Thread] = None
        self.decision_processor_thread: Optional[threading.Thread] = None
        
        # Callbacks for different stages
        self.tick_callbacks: List[Callable[[TickEvent], None]] = []
        self.feature_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.decision_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        logger.info("HotPathManager initialized")
    
    async def initialize(self, db_path: str):
        """Initialize the hot path manager with database"""
        try:
            # Initialize async database writer
            self.db_writer = AsyncDBWriter(db_path)
            await self.db_writer.start()
            
            # Initialize ring buffers for common symbols
            symbols = ['BTCUSDc', 'XAUUSDc', 'EURUSDc', 'GBPUSDc', 'USDJPYc', 'BTCUSDT']
            self.multi_symbol_buffer = MultiSymbolRingBuffer(symbols)
            
            for symbol in symbols:
                self.tick_buffers[symbol] = OptimizedRingBuffer(
                    capacity=1000,  # Reduced from 10000: ~4KB per symbol (safe for laptops)
                    dtype=float,
                    name=f"tick_{symbol}"
                )
                self.feature_buffers[symbol] = FeatureRingBuffer(
                    capacity=1000  # Reduced from 5000
                )
            
            # Start processing threads
            self._start_processing_threads()
            
            logger.info("HotPathManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize HotPathManager: {e}")
            return False
    
    async def stop(self):
        """Stop the hot path manager and flush remaining operations"""
        try:
            self.running = False
            
            # Stop processing threads
            if hasattr(self, 'tick_thread') and self.tick_thread.is_alive():
                self.tick_thread.join(timeout=1.0)
            if hasattr(self, 'feature_thread') and self.feature_thread.is_alive():
                self.feature_thread.join(timeout=1.0)
            if hasattr(self, 'decision_thread') and self.decision_thread.is_alive():
                self.decision_thread.join(timeout=1.0)
            
            # Stop database writer
            if self.db_writer:
                await self.db_writer.stop()
            
            logger.info("HotPathManager stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping HotPathManager: {e}")
    
    def _start_processing_threads(self):
        """Start background processing threads"""
        self.running = True
        
        # Start tick processing thread
        self.tick_processor_thread = threading.Thread(
            target=self._tick_processing_loop,
            name="HotPathTickProcessor",
            daemon=True
        )
        self.tick_processor_thread.start()
        
        # Start feature processing thread
        self.feature_processor_thread = threading.Thread(
            target=self._feature_processing_loop,
            name="HotPathFeatureProcessor",
            daemon=True
        )
        self.feature_processor_thread.start()
        
        # Start decision processing thread
        self.decision_processor_thread = threading.Thread(
            target=self._decision_processing_loop,
            name="HotPathDecisionProcessor",
            daemon=True
        )
        self.decision_processor_thread.start()
        
        logger.info("Hot path processing threads started")
    
    def process_tick(self, tick: TickEvent) -> bool:
        """
        Process a tick in the hot path (non-blocking)
        Returns True if queued successfully, False if dropped
        """
        try:
            # Add to tick queue (non-blocking)
            self.tick_queue.put_nowait(tick)
            
            with self.lock:
                self.stats['ticks_processed'] += 1
                self.stats['current_queue_sizes']['tick_queue'] = self.tick_queue.qsize()
            
            return True
            
        except queue.Full:
            with self.lock:
                self.stats['queue_overflows'] += 1
            logger.warning("Tick queue is full, dropping tick")
            return False
    
    def _tick_processing_loop(self):
        """Background tick processing loop"""
        while self.running:
            try:
                # Get tick from queue (with timeout)
                try:
                    tick = self.tick_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                start_time = time.perf_counter_ns()
                
                # Process tick
                self._process_tick_internal(tick)
                
                # Update statistics
                end_time = time.perf_counter_ns()
                processing_time_ns = end_time - start_time
                
                with self.lock:
                    self.stats['avg_processing_time_ns'] = (
                        (self.stats['avg_processing_time_ns'] * (self.stats['ticks_processed'] - 1) + processing_time_ns) 
                        / self.stats['ticks_processed']
                    )
                    self.stats['max_processing_time_ns'] = max(
                        self.stats['max_processing_time_ns'], 
                        processing_time_ns
                    )
                    self.stats['current_queue_sizes']['tick_queue'] = self.tick_queue.qsize()
                
                # Notify callbacks
                for callback in self.tick_callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        logger.error(f"Tick callback error: {e}")
                
            except Exception as e:
                logger.error(f"Error in tick processing loop: {e}")
                time.sleep(0.01)  # Brief pause on error
    
    def _process_tick_internal(self, tick: TickEvent):
        """Internal tick processing (no I/O blocking)"""
        try:
            # Add to ring buffer
            if tick.symbol in self.tick_buffers:
                self.tick_buffers[tick.symbol].append(tick.bid, tick.timestamp_ms)
            
            # Add to multi-symbol buffer
            if self.multi_symbol_buffer:
                self.multi_symbol_buffer.add_tick(
                    tick.symbol,
                    (tick.bid + tick.ask) / 2,  # Mid price
                    tick.volume,
                    tick.ask - tick.bid,  # Spread
                    tick.timestamp_ms
                )
            
            # Add to feature buffer
            if tick.symbol in self.feature_buffers:
                self.feature_buffers[tick.symbol].add_tick_data(
                    (tick.bid + tick.ask) / 2,
                    tick.volume,
                    tick.timestamp_ms
                )
            
            # Queue for async database write (non-blocking)
            if self.db_writer:
                operation = WriteOperation(
                    operation_type='insert',
                    table_name='raw_ticks',
                    data={
                        'symbol': tick.symbol,
                        'timestamp_ms': tick.timestamp_ms,
                        'bid': tick.bid,
                        'ask': tick.ask,
                        'volume': tick.volume,
                        'source': tick.source
                    },
                    timestamp_ns=time.perf_counter_ns(),
                    priority=1  # High priority for ticks
                )
                
                # Try to queue write operation (non-blocking)
                if not self.db_writer.write_sync(operation):
                    logger.warning("Failed to queue tick for database write")
            
        except Exception as e:
            logger.error(f"Error processing tick internally: {e}")
    
    async def process_binance_data(self, binance_data: Any) -> bool:
        """Process Binance order book data"""
        try:
            # Convert binance data to tick format if needed
            if hasattr(binance_data, 'bids') and hasattr(binance_data, 'asks'):
                # Calculate mid price from order book
                if binance_data.bids and binance_data.asks:
                    bid_price = float(binance_data.bids[0][0])
                    ask_price = float(binance_data.asks[0][0])
                    mid_price = (bid_price + ask_price) / 2
                    
                    # Create tick event from order book data
                    tick = TickEvent(
                        symbol=binance_data.symbol,
                        timestamp_ms=binance_data.timestamp_ms,
                        bid=bid_price,
                        ask=ask_price,
                        last=mid_price,
                        volume=0.0,
                        source="binance"
                    )
                    
                    return self.process_tick(tick)
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing Binance data: {e}")
            return False
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        buffer_usage = {}
        for symbol, buffer in self.tick_buffers.items():
            buffer_usage[symbol] = {
                'tick_buffer': buffer.get_usage_percentage(),
                'feature_buffer': self.feature_buffers.get(symbol).get_usage_percentage() if symbol in self.feature_buffers else 0.0
            }
        
        return {
            'ticks_processed': self.stats.get('ticks_processed', 0),
            'features_calculated': self.stats.get('features_calculated', 0),
            'decisions_made': self.stats.get('decisions_made', 0),
            'queue_depths': {
                'tick_queue': self.tick_queue.qsize(),
                'feature_queue': self.feature_queue.qsize(),
                'decision_queue': self.decision_queue.qsize()
            },
            'buffer_usage': buffer_usage,
            'running': self.running
        }
    
    def _feature_processing_loop(self):
        """Background feature processing loop"""
        while self.running:
            try:
                # Process features for each symbol
                for symbol, feature_buffer in self.feature_buffers.items():
                    try:
                        # Get latest features
                        features = feature_buffer.get_latest_features(10)
                        
                        if features['timestamps'].size > 0:
                            # Queue feature data for async write
                            if self.db_writer:
                                operation = WriteOperation(
                                    operation_type='insert_m1_filter',
                                    table_name='m1_filter_signals',
                                    data={
                                        'symbol': symbol,
                                        'timestamp_ms': int(features['timestamps'][-1]),
                                        'filter_type': 'feature_calculation',
                                        'signal_value': float(features['vwap'][-1]) if features['vwap'].size > 0 else 0.0,
                                        'is_confirmed': True,
                                        'vwap': float(features['vwap'][-1]) if features['vwap'].size > 0 else 0.0,
                                        'atr': float(features['atr'][-1]) if features['atr'].size > 0 else 0.0,
                                        'delta': float(features['delta'][-1]) if features['delta'].size > 0 else 0.0,
                                        'volume_delta': float(features['volume_delta'][-1]) if features['volume_delta'].size > 0 else 0.0,
                                        'details': {
                                            'feature_calculation': True,
                                            'timestamp': int(features['timestamps'][-1])
                                        }
                                    },
                                    timestamp_ns=time.perf_counter_ns(),
                                    priority=2  # Medium priority for features
                                )
                                
                                self.db_writer.write_sync(operation)
                        
                    except Exception as e:
                        logger.error(f"Error processing features for {symbol}: {e}")
                
                time.sleep(0.1)  # Process features every 100ms
                
            except Exception as e:
                logger.error(f"Error in feature processing loop: {e}")
                time.sleep(0.1)
    
    def _decision_processing_loop(self):
        """Background decision processing loop"""
        while self.running:
            try:
                # This would implement decision processing logic
                # For now, just a placeholder
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in decision processing loop: {e}")
                time.sleep(0.1)
    
    def get_latest_ticks(self, symbol: str, count: int = 100) -> List[Dict[str, Any]]:
        """Get latest ticks for a symbol (non-blocking)"""
        try:
            if symbol in self.tick_buffers:
                prices = self.tick_buffers[symbol].get_latest(count)
                timestamps = self.tick_buffers[symbol].get_timestamps(count)
                
                return [
                    {
                        'price': float(price),
                        'timestamp_ms': int(timestamp)
                    }
                    for price, timestamp in zip(prices, timestamps)
                ]
            return []
            
        except Exception as e:
            logger.error(f"Error getting latest ticks for {symbol}: {e}")
            return []
    
    def get_latest_features(self, symbol: str, count: int = 10) -> Dict[str, Any]:
        """Get latest features for a symbol (non-blocking)"""
        try:
            if symbol in self.feature_buffers:
                return self.feature_buffers[symbol].get_latest_features(count)
            return {}
            
        except Exception as e:
            logger.error(f"Error getting latest features for {symbol}: {e}")
            return {}
    
    def add_tick_callback(self, callback: Callable[[TickEvent], None]):
        """Add callback for tick processing"""
        self.tick_callbacks.append(callback)
    
    def add_feature_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for feature processing"""
        self.feature_callbacks.append(callback)
    
    def add_decision_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for decision processing"""
        self.decision_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hot path statistics"""
        with self.lock:
            stats = dict(self.stats)
            
            # Add database writer stats if available
            if self.db_writer:
                stats['db_writer'] = self.db_writer.get_stats()
            
            # Add ring buffer stats
            stats['ring_buffers'] = {}
            for symbol, buffer in self.tick_buffers.items():
                stats['ring_buffers'][symbol] = buffer.get_stats()
            
            return stats
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of hot path"""
        with self.lock:
            return {
                'running': self.running,
                'queue_sizes': dict(self.stats['current_queue_sizes']),
                'queue_overflows': self.stats['queue_overflows'],
                'avg_processing_time_ms': self.stats['avg_processing_time_ns'] / 1_000_000,
                'max_processing_time_ms': self.stats['max_processing_time_ns'] / 1_000_000,
                'db_writer_healthy': self.db_writer is not None and self.db_writer.running if self.db_writer else False
            }
    
    async def shutdown(self):
        """Shutdown the hot path manager"""
        logger.info("Shutting down HotPathManager...")
        
        self.running = False
        
        # Wait for processing threads to finish
        if self.tick_processor_thread and self.tick_processor_thread.is_alive():
            self.tick_processor_thread.join(timeout=5.0)
        
        if self.feature_processor_thread and self.feature_processor_thread.is_alive():
            self.feature_processor_thread.join(timeout=5.0)
        
        if self.decision_processor_thread and self.decision_processor_thread.is_alive():
            self.decision_processor_thread.join(timeout=5.0)
        
        # Shutdown database writer
        if self.db_writer:
            await self.db_writer.stop()
        
        logger.info("HotPathManager shutdown complete")

# Global hot path manager instance
_hot_path_manager: Optional[HotPathManager] = None

def get_hot_path_manager() -> Optional[HotPathManager]:
    """Get the global hot path manager instance"""
    return _hot_path_manager

def initialize_hot_path_manager(db_path: str) -> bool:
    """Initialize the global hot path manager"""
    global _hot_path_manager
    
    try:
        _hot_path_manager = HotPathManager()
        return asyncio.run(_hot_path_manager.initialize(db_path))
    except Exception as e:
        logger.error(f"Failed to initialize hot path manager: {e}")
        return False

async def shutdown_hot_path_manager():
    """Shutdown the global hot path manager"""
    global _hot_path_manager
    
    if _hot_path_manager:
        await _hot_path_manager.shutdown()
        _hot_path_manager = None
