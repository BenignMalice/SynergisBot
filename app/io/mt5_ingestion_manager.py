"""
MT5 Ingestion Manager
Dedicated ingestion threads per symbol with non-blocking polling
High-performance MT5 data ingestion system
"""

import threading
import time
import logging
import queue
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import weakref
import json

logger = logging.getLogger(__name__)

class IngestionState(Enum):
    """Ingestion thread states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    STALE = "stale"

@dataclass
class TickData:
    """MT5 tick data structure"""
    symbol: str
    timestamp_ms: int
    bid: float
    ask: float
    last: Optional[float] = None
    volume: float = 0.0
    spread: float = 0.0
    source: str = "mt5"
    quality: DataQuality = DataQuality.GOOD

@dataclass
class IngestionStats:
    """Statistics for ingestion thread"""
    total_ticks: int = 0
    successful_ticks: int = 0
    failed_ticks: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    data_quality_score: float = 1.0
    last_tick_time: float = 0.0
    consecutive_failures: int = 0
    reconnection_count: int = 0

@dataclass
class IngestionConfig:
    """Configuration for ingestion thread"""
    polling_interval_ms: int = 100
    max_retries: int = 3
    retry_delay_ms: int = 1000
    data_timeout_ms: int = 5000
    quality_check_interval: int = 1000
    max_queue_size: int = 1000
    enable_quality_monitoring: bool = True
    enable_reconnection: bool = True

class MT5IngestionThread:
    """
    Dedicated ingestion thread for a single symbol
    Non-blocking polling with quality monitoring
    """
    
    def __init__(self, symbol: str, config: Optional[IngestionConfig] = None):
        self.symbol = symbol
        self.config = config or IngestionConfig()
        
        # Thread state
        self.state = IngestionState.STOPPED
        self.thread: Optional[threading.Thread] = None
        self.running = False
        
        # Data queue
        self.data_queue = queue.Queue(maxsize=self.config.max_queue_size)
        
        # Statistics
        self.stats = IngestionStats()
        self.latency_measurements = deque(maxlen=1000)
        
        # Callbacks
        self.tick_callbacks: List[Callable[[TickData], None]] = []
        self.error_callbacks: List[Callable[[str, Exception], None]] = []
        self.quality_callbacks: List[Callable[[str, DataQuality], None]] = []
        
        # Quality monitoring
        self.last_quality_check = 0.0
        self.quality_history = deque(maxlen=100)
        
        # MT5 connection (would be injected in real implementation)
        self.mt5_connection = None
        
        logger.info(f"MT5IngestionThread initialized for {symbol}")
    
    def start(self):
        """Start the ingestion thread"""
        if self.state != IngestionState.STOPPED:
            logger.warning(f"Ingestion thread for {self.symbol} is not stopped")
            return
        
        self.state = IngestionState.STARTING
        self.running = True
        
        self.thread = threading.Thread(
            target=self._ingestion_loop,
            name=f"MT5Ingestion_{self.symbol}",
            daemon=True
        )
        self.thread.start()
        
        logger.info(f"MT5 ingestion thread started for {self.symbol}")
    
    def stop(self):
        """Stop the ingestion thread"""
        if self.state == IngestionState.STOPPED:
            return
        
        self.state = IngestionState.STOPPING
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
        
        self.state = IngestionState.STOPPED
        logger.info(f"MT5 ingestion thread stopped for {self.symbol}")
    
    def _ingestion_loop(self):
        """Main ingestion loop"""
        self.state = IngestionState.RUNNING
        
        try:
            while self.running:
                try:
                    # Poll for new tick data
                    tick_data = self._poll_tick_data()
                    
                    if tick_data:
                        # Process tick data
                        self._process_tick(tick_data)
                    else:
                        # No new data, check for timeouts
                        self._check_data_timeout()
                    
                    # Quality monitoring
                    self._monitor_data_quality()
                    
                    # Brief pause to prevent CPU spinning
                    time.sleep(self.config.polling_interval_ms / 1000.0)
                    
                except Exception as e:
                    logger.error(f"Error in ingestion loop for {self.symbol}: {e}")
                    self._handle_error(e)
                    time.sleep(1.0)  # 1 second pause on error
                    
        except Exception as e:
            logger.error(f"Fatal error in ingestion loop for {self.symbol}: {e}")
            self.state = IngestionState.ERROR
            self._handle_error(e)
    
    def _poll_tick_data(self) -> Optional[TickData]:
        """Poll MT5 for new tick data (non-blocking)"""
        try:
            # This would be the actual MT5 polling logic
            # For now, simulate with mock data
            current_time = time.time()
            
            # Simulate tick data (in real implementation, this would call MT5 API)
            if hasattr(self, '_last_poll_time'):
                if current_time - self._last_poll_time < 0.1:  # 100ms minimum between polls
                    return None
            self._last_poll_time = current_time
            
            # Mock tick data (replace with actual MT5 call)
            mock_tick = TickData(
                symbol=self.symbol,
                timestamp_ms=int(current_time * 1000),
                bid=50000.0 + (current_time % 100),  # Mock price
                ask=50000.5 + (current_time % 100),
                last=50000.25 + (current_time % 100),
                volume=100.0,
                spread=0.5,
                source="mt5",
                quality=DataQuality.GOOD
            )
            
            return mock_tick
            
        except Exception as e:
            logger.error(f"Error polling tick data for {self.symbol}: {e}")
            return None
    
    def _process_tick(self, tick_data: TickData):
        """Process incoming tick data"""
        start_time = time.perf_counter_ns()
        
        try:
            # Update statistics
            self.stats.total_ticks += 1
            self.stats.last_tick_time = time.time()
            self.stats.consecutive_failures = 0
            
            # Add to data queue
            try:
                self.data_queue.put_nowait(tick_data)
            except queue.Full:
                logger.warning(f"Data queue full for {self.symbol}, dropping tick")
                return
            
            # Notify callbacks
            for callback in self.tick_callbacks:
                try:
                    callback(tick_data)
                except Exception as e:
                    logger.error(f"Error in tick callback for {self.symbol}: {e}")
            
            # Update success statistics
            self.stats.successful_ticks += 1
            
            # Measure latency
            end_time = time.perf_counter_ns()
            latency_ms = (end_time - start_time) / 1_000_000
            self.latency_measurements.append(latency_ms)
            
            # Update latency statistics
            if self.latency_measurements:
                self.stats.avg_latency_ms = sum(self.latency_measurements) / len(self.latency_measurements)
                self.stats.max_latency_ms = max(self.latency_measurements)
            
        except Exception as e:
            logger.error(f"Error processing tick for {self.symbol}: {e}")
            self.stats.failed_ticks += 1
            self.stats.consecutive_failures += 1
            self._handle_error(e)
    
    def _check_data_timeout(self):
        """Check for data timeout"""
        current_time = time.time()
        time_since_last_tick = current_time - self.stats.last_tick_time
        
        if time_since_last_tick > (self.config.data_timeout_ms / 1000.0):
            logger.warning(f"Data timeout for {self.symbol}: {time_since_last_tick:.2f}s since last tick")
            
            # Attempt reconnection if enabled
            if self.config.enable_reconnection:
                self._attempt_reconnection()
    
    def _monitor_data_quality(self):
        """Monitor data quality"""
        if not self.config.enable_quality_monitoring:
            return
        
        current_time = time.time()
        if current_time - self.last_quality_check < (self.config.quality_check_interval / 1000.0):
            return
        
        self.last_quality_check = current_time
        
        # Calculate quality score
        quality_score = self._calculate_quality_score()
        self.quality_history.append(quality_score)
        
        # Determine quality level
        if quality_score >= 0.9:
            quality = DataQuality.EXCELLENT
        elif quality_score >= 0.7:
            quality = DataQuality.GOOD
        elif quality_score >= 0.5:
            quality = DataQuality.FAIR
        elif quality_score >= 0.3:
            quality = DataQuality.POOR
        else:
            quality = DataQuality.STALE
        
        # Update statistics
        self.stats.data_quality_score = quality_score
        
        # Notify quality callbacks
        for callback in self.quality_callbacks:
            try:
                callback(self.symbol, quality)
            except Exception as e:
                logger.error(f"Error in quality callback for {self.symbol}: {e}")
    
    def _calculate_quality_score(self) -> float:
        """Calculate data quality score"""
        score = 1.0
        
        # Factor 1: Recent data availability
        time_since_last_tick = time.time() - self.stats.last_tick_time
        if time_since_last_tick > 5.0:  # 5 seconds
            score *= 0.5
        elif time_since_last_tick > 2.0:  # 2 seconds
            score *= 0.8
        
        # Factor 2: Success rate
        if self.stats.total_ticks > 0:
            success_rate = self.stats.successful_ticks / self.stats.total_ticks
            score *= success_rate
        
        # Factor 3: Latency
        if self.stats.avg_latency_ms > 100:  # 100ms
            score *= 0.8
        elif self.stats.avg_latency_ms > 50:  # 50ms
            score *= 0.9
        
        # Factor 4: Consecutive failures
        if self.stats.consecutive_failures > 5:
            score *= 0.3
        elif self.stats.consecutive_failures > 2:
            score *= 0.7
        
        return max(0.0, min(1.0, score))
    
    def _attempt_reconnection(self):
        """Attempt to reconnect to MT5"""
        try:
            logger.info(f"Attempting reconnection for {self.symbol}")
            self.stats.reconnection_count += 1
            
            # This would be the actual reconnection logic
            # For now, just log the attempt
            time.sleep(1.0)  # Simulate reconnection delay
            
            logger.info(f"Reconnection completed for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Reconnection failed for {self.symbol}: {e}")
            self._handle_error(e)
    
    def _handle_error(self, error: Exception):
        """Handle errors in ingestion"""
        self.stats.failed_ticks += 1
        self.stats.consecutive_failures += 1
        
        # Notify error callbacks
        for callback in self.error_callbacks:
            try:
                callback(self.symbol, error)
            except Exception as e:
                logger.error(f"Error in error callback for {self.symbol}: {e}")
    
    def add_tick_callback(self, callback: Callable[[TickData], None]):
        """Add callback for tick data"""
        self.tick_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, Exception], None]):
        """Add callback for errors"""
        self.error_callbacks.append(callback)
    
    def add_quality_callback(self, callback: Callable[[str, DataQuality], None]):
        """Add callback for quality changes"""
        self.quality_callbacks.append(callback)
    
    def get_tick_data(self, timeout: float = 0.0) -> Optional[TickData]:
        """Get tick data from queue"""
        try:
            if timeout > 0:
                return self.data_queue.get(timeout=timeout)
            else:
                return self.data_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        return {
            'symbol': self.symbol,
            'state': self.state.value,
            'stats': {
                'total_ticks': self.stats.total_ticks,
                'successful_ticks': self.stats.successful_ticks,
                'failed_ticks': self.stats.failed_ticks,
                'success_rate': self.stats.successful_ticks / max(self.stats.total_ticks, 1),
                'avg_latency_ms': self.stats.avg_latency_ms,
                'max_latency_ms': self.stats.max_latency_ms,
                'data_quality_score': self.stats.data_quality_score,
                'consecutive_failures': self.stats.consecutive_failures,
                'reconnection_count': self.stats.reconnection_count,
                'queue_size': self.data_queue.qsize()
            },
            'config': {
                'polling_interval_ms': self.config.polling_interval_ms,
                'data_timeout_ms': self.config.data_timeout_ms,
                'max_queue_size': self.config.max_queue_size
            }
        }

class MT5IngestionManager:
    """
    Manages multiple MT5 ingestion threads
    Coordinates ingestion across multiple symbols
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Ingestion threads per symbol
        self.ingestion_threads: Dict[str, MT5IngestionThread] = {}
        
        # Global callbacks
        self.global_tick_callbacks: List[Callable[[TickData], None]] = []
        self.global_error_callbacks: List[Callable[[str, Exception], None]] = []
        self.global_quality_callbacks: List[Callable[[str, DataQuality], None]] = []
        
        # Manager state
        self.running = False
        self.manager_lock = threading.RLock()
        
        logger.info("MT5IngestionManager initialized")
    
    def add_symbol(self, symbol: str, config: Optional[IngestionConfig] = None) -> bool:
        """Add a symbol for ingestion"""
        with self.manager_lock:
            if symbol in self.ingestion_threads:
                logger.warning(f"Symbol {symbol} already being ingested")
                return False
            
            try:
                # Create ingestion thread
                thread = MT5IngestionThread(symbol, config)
                
                # Add global callbacks
                for callback in self.global_tick_callbacks:
                    thread.add_tick_callback(callback)
                for callback in self.global_error_callbacks:
                    thread.add_error_callback(callback)
                for callback in self.global_quality_callbacks:
                    thread.add_quality_callback(callback)
                
                self.ingestion_threads[symbol] = thread
                
                # Start thread if manager is running
                if self.running:
                    thread.start()
                
                logger.info(f"Added symbol {symbol} for ingestion")
                return True
                
            except Exception as e:
                logger.error(f"Failed to add symbol {symbol}: {e}")
                return False
    
    def remove_symbol(self, symbol: str) -> bool:
        """Remove a symbol from ingestion"""
        with self.manager_lock:
            if symbol not in self.ingestion_threads:
                logger.warning(f"Symbol {symbol} not being ingested")
                return False
            
            try:
                # Stop and remove thread
                thread = self.ingestion_threads[symbol]
                thread.stop()
                del self.ingestion_threads[symbol]
                
                logger.info(f"Removed symbol {symbol} from ingestion")
                return True
                
            except Exception as e:
                logger.error(f"Failed to remove symbol {symbol}: {e}")
                return False
    
    def start_all(self):
        """Start all ingestion threads"""
        with self.manager_lock:
            self.running = True
            
            for symbol, thread in self.ingestion_threads.items():
                try:
                    thread.start()
                except Exception as e:
                    logger.error(f"Failed to start ingestion for {symbol}: {e}")
            
            logger.info("Started all MT5 ingestion threads")
    
    def stop_all(self):
        """Stop all ingestion threads"""
        with self.manager_lock:
            self.running = False
            
            for symbol, thread in self.ingestion_threads.items():
                try:
                    thread.stop()
                except Exception as e:
                    logger.error(f"Failed to stop ingestion for {symbol}: {e}")
            
            logger.info("Stopped all MT5 ingestion threads")
    
    def add_global_tick_callback(self, callback: Callable[[TickData], None]):
        """Add global tick callback"""
        self.global_tick_callbacks.append(callback)
        
        # Add to existing threads
        for thread in self.ingestion_threads.values():
            thread.add_tick_callback(callback)
    
    def add_global_error_callback(self, callback: Callable[[str, Exception], None]):
        """Add global error callback"""
        self.global_error_callbacks.append(callback)
        
        # Add to existing threads
        for thread in self.ingestion_threads.values():
            thread.add_error_callback(callback)
    
    def add_global_quality_callback(self, callback: Callable[[str, DataQuality], None]):
        """Add global quality callback"""
        self.global_quality_callbacks.append(callback)
        
        # Add to existing threads
        for thread in self.ingestion_threads.values():
            thread.add_quality_callback(callback)
    
    def get_symbol_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific symbol"""
        with self.manager_lock:
            if symbol in self.ingestion_threads:
                return self.ingestion_threads[symbol].get_stats()
            return None
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all symbols"""
        with self.manager_lock:
            stats = {
                'manager_running': self.running,
                'total_symbols': len(self.ingestion_threads),
                'symbols': {}
            }
            
            for symbol, thread in self.ingestion_threads.items():
                stats['symbols'][symbol] = thread.get_stats()
            
            return stats
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all ingestion threads"""
        with self.manager_lock:
            healthy_symbols = 0
            total_symbols = len(self.ingestion_threads)
            
            for thread in self.ingestion_threads.values():
                if (thread.state == IngestionState.RUNNING and 
                    thread.stats.data_quality_score > 0.5):
                    healthy_symbols += 1
            
            return {
                'healthy': healthy_symbols == total_symbols and total_symbols > 0,
                'healthy_symbols': healthy_symbols,
                'total_symbols': total_symbols,
                'health_percentage': (healthy_symbols / max(total_symbols, 1)) * 100
            }

# Global ingestion manager instance
_ingestion_manager: Optional[MT5IngestionManager] = None

def get_ingestion_manager() -> Optional[MT5IngestionManager]:
    """Get the global ingestion manager instance"""
    return _ingestion_manager

def initialize_ingestion_manager(config: Optional[Dict[str, Any]] = None) -> MT5IngestionManager:
    """Initialize the global ingestion manager"""
    global _ingestion_manager
    _ingestion_manager = MT5IngestionManager(config)
    return _ingestion_manager

def shutdown_ingestion_manager():
    """Shutdown the global ingestion manager"""
    global _ingestion_manager
    if _ingestion_manager:
        _ingestion_manager.stop_all()
        _ingestion_manager = None
