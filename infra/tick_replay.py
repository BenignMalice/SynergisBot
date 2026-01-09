"""
Advanced Tick Replay System
Deterministic testing for 4 symbols with MT5 I/O shim
"""

import asyncio
import logging
import time
import threading
import json
import sqlite3
import csv
import os
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict, deque
import queue as py_queue
from concurrent.futures import ThreadPoolExecutor
import struct
import gzip

logger = logging.getLogger(__name__)

class ReplayMode(Enum):
    """Tick replay modes."""
    HISTORICAL = "historical"
    LIVE_SIMULATION = "live_simulation"
    STRESS_TEST = "stress_test"
    DETERMINISTIC = "deterministic"

class ReplaySpeed(Enum):
    """Replay speed options."""
    REAL_TIME = "real_time"
    FAST_2X = "fast_2x"
    FAST_5X = "fast_5x"
    FAST_10X = "fast_10x"
    INSTANT = "instant"

class ReplayStatus(Enum):
    """Replay status."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class TickData:
    """Tick data structure."""
    symbol: str
    timestamp_ms: int
    bid: float
    ask: float
    volume: float
    source: str = "replay"
    sequence_id: int = 0

@dataclass
class ReplayConfig:
    """Tick replay configuration."""
    symbols: List[str]
    start_time: datetime
    end_time: datetime
    mode: ReplayMode = ReplayMode.DETERMINISTIC
    speed: ReplaySpeed = ReplaySpeed.REAL_TIME
    data_source: str = "database"  # database, csv, binary
    data_path: str = ""
    batch_size: int = 1000
    max_ticks_per_second: int = 1000
    enable_compression: bool = True
    enable_validation: bool = True
    callback_interval_ms: int = 100

@dataclass
class ReplayStats:
    """Replay statistics."""
    total_ticks: int = 0
    processed_ticks: int = 0
    skipped_ticks: int = 0
    error_ticks: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0
    ticks_per_second: float = 0.0
    symbols_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

class TickReplayEngine:
    """Advanced tick replay engine for deterministic testing."""
    
    def __init__(self, config: ReplayConfig):
        self.config = config
        self.status = ReplayStatus.STOPPED
        self.stats = ReplayStats()
        self.tick_callbacks: List[Callable[[TickData], None]] = []
        self.progress_callbacks: List[Callable[[float], None]] = []
        self.error_callbacks: List[Callable[[Exception], None]] = []
        self.lock = threading.RLock()
        self.replay_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start unpaused
        
        # Data storage
        self.tick_data: Dict[str, List[TickData]] = {}
        self.current_positions: Dict[str, int] = {}
        self.symbol_sequences: Dict[str, int] = defaultdict(int)
        
        # Performance tracking
        self.last_callback_time = 0.0
        self.ticks_processed_this_second = 0
        self.current_second = 0
        
    def add_tick_callback(self, callback: Callable[[TickData], None]):
        """Add tick data callback."""
        self.tick_callbacks.append(callback)
    
    def add_progress_callback(self, callback: Callable[[float], None]):
        """Add progress callback."""
        self.progress_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[Exception], None]):
        """Add error callback."""
        self.error_callbacks.append(callback)
    
    def load_data(self) -> bool:
        """Load tick data from configured source."""
        try:
            if self.config.data_source == "database":
                return self._load_from_database()
            elif self.config.data_source == "csv":
                return self._load_from_csv()
            elif self.config.data_source == "binary":
                return self._load_from_binary()
            else:
                raise ValueError(f"Unsupported data source: {self.config.data_source}")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self._trigger_error_callback(e)
            return False
    
    def _load_from_database(self) -> bool:
        """Load tick data from database."""
        try:
            # This would connect to the actual database
            # For now, we'll simulate loading data
            logger.info("Loading tick data from database...")
            
            for symbol in self.config.symbols:
                self.tick_data[symbol] = []
                self.current_positions[symbol] = 0
                
                # Simulate loading historical data
                # In real implementation, this would query the database
                logger.info(f"Loaded data for {symbol}")
            
            return True
        except Exception as e:
            logger.error(f"Error loading from database: {e}")
            return False
    
    def _load_from_csv(self) -> bool:
        """Load tick data from CSV files."""
        try:
            for symbol in self.config.symbols:
                csv_file = os.path.join(self.config.data_path, f"{symbol}_ticks.csv")
                if not os.path.exists(csv_file):
                    logger.warning(f"CSV file not found: {csv_file}")
                    continue
                
                self.tick_data[symbol] = []
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tick = TickData(
                            symbol=symbol,
                            timestamp_ms=int(row['timestamp_ms']),
                            bid=float(row['bid']),
                            ask=float(row['ask']),
                            volume=float(row['volume']),
                            source="replay"
                        )
                        self.tick_data[symbol].append(tick)
                
                logger.info(f"Loaded {len(self.tick_data[symbol])} ticks for {symbol}")
            
            return True
        except Exception as e:
            logger.error(f"Error loading from CSV: {e}")
            return False
    
    def _load_from_binary(self) -> bool:
        """Load tick data from binary files."""
        try:
            for symbol in self.config.symbols:
                binary_file = os.path.join(self.config.data_path, f"{symbol}_ticks.bin")
                if not os.path.exists(binary_file):
                    logger.warning(f"Binary file not found: {binary_file}")
                    continue
                
                self.tick_data[symbol] = []
                
                if self.config.enable_compression:
                    with gzip.open(binary_file, 'rb') as f:
                        data = f.read()
                else:
                    with open(binary_file, 'rb') as f:
                        data = f.read()
                
                # Parse binary data (assuming specific format)
                offset = 0
                while offset < len(data):
                    # Unpack tick data (timestamp_ms, bid, ask, volume)
                    tick_data = struct.unpack('Qddd', data[offset:offset+32])
                    tick = TickData(
                        symbol=symbol,
                        timestamp_ms=tick_data[0],
                        bid=tick_data[1],
                        ask=tick_data[2],
                        volume=tick_data[3],
                        source="replay"
                    )
                    self.tick_data[symbol].append(tick)
                    offset += 32
                
                logger.info(f"Loaded {len(self.tick_data[symbol])} ticks for {symbol}")
            
            return True
        except Exception as e:
            logger.error(f"Error loading from binary: {e}")
            return False
    
    def start_replay(self) -> bool:
        """Start tick replay."""
        with self.lock:
            if self.status == ReplayStatus.RUNNING:
                logger.warning("Replay is already running")
                return False
            
            if not self.tick_data:
                logger.error("No tick data loaded")
                return False
            
            self.status = ReplayStatus.RUNNING
            self.stats.start_time = time.time()
            self.stop_event.clear()
            self.pause_event.set()
            
            # Start replay thread
            self.replay_thread = threading.Thread(target=self._replay_loop, daemon=True)
            self.replay_thread.start()
            
            logger.info("Started tick replay")
            return True
    
    def stop_replay(self):
        """Stop tick replay."""
        with self.lock:
            if self.status != ReplayStatus.RUNNING:
                return
            
            self.status = ReplayStatus.STOPPED
            self.stop_event.set()
            
            if self.replay_thread:
                self.replay_thread.join(timeout=2.0)
            
            self.stats.end_time = time.time()
            self.stats.duration_seconds = self.stats.end_time - self.stats.start_time
            
            logger.info("Stopped tick replay")
    
    def pause_replay(self):
        """Pause tick replay."""
        with self.lock:
            if self.status == ReplayStatus.RUNNING:
                self.status = ReplayStatus.PAUSED
                self.pause_event.clear()
                logger.info("Paused tick replay")
    
    def resume_replay(self):
        """Resume tick replay."""
        with self.lock:
            if self.status == ReplayStatus.PAUSED:
                self.status = ReplayStatus.RUNNING
                self.pause_event.set()
                logger.info("Resumed tick replay")
    
    def _replay_loop(self):
        """Main replay loop."""
        try:
            while not self.stop_event.is_set():
                # Wait for pause to be cleared
                self.pause_event.wait()
                
                if self.stop_event.is_set():
                    break
                
                # Process ticks for all symbols
                self._process_ticks()
                
                # Check if replay is complete
                if self._is_replay_complete():
                    self.status = ReplayStatus.COMPLETED
                    break
                
                # Rate limiting
                self._apply_rate_limiting()
                
        except Exception as e:
            logger.error(f"Error in replay loop: {e}")
            self.status = ReplayStatus.ERROR
            self._trigger_error_callback(e)
    
    def _process_ticks(self):
        """Process ticks for all symbols."""
        current_time = time.time()
        
        for symbol in self.config.symbols:
            if symbol not in self.tick_data:
                continue
            
            symbol_data = self.tick_data[symbol]
            current_pos = self.current_positions[symbol]
            
            # Process ticks in batches
            batch_end = min(current_pos + self.config.batch_size, len(symbol_data))
            
            for i in range(current_pos, batch_end):
                if self.stop_event.is_set():
                    break
                
                tick = symbol_data[i]
                
                # Apply speed multiplier
                if self.config.speed != ReplaySpeed.INSTANT:
                    self._apply_speed_control(tick.timestamp_ms)
                
                # Process tick
                self._process_tick(tick)
                
                # Update position
                self.current_positions[symbol] = i + 1
                self.stats.processed_ticks += 1
                
                # Update symbol stats
                if symbol not in self.stats.symbols_stats:
                    self.stats.symbols_stats[symbol] = {
                        'total_ticks': len(symbol_data),
                        'processed_ticks': 0,
                        'start_time': tick.timestamp_ms
                    }
                
                self.stats.symbols_stats[symbol]['processed_ticks'] += 1
            
            # Update progress
            if current_time - self.last_callback_time > (self.config.callback_interval_ms / 1000.0):
                self._update_progress()
                self.last_callback_time = current_time
    
    def _process_tick(self, tick: TickData):
        """Process individual tick."""
        try:
            # Add sequence ID
            tick.sequence_id = self.symbol_sequences[tick.symbol]
            self.symbol_sequences[tick.symbol] += 1
            
            # Validate tick data
            if self.config.enable_validation:
                if not self._validate_tick(tick):
                    self.stats.skipped_ticks += 1
                    return
            
            # Trigger callbacks
            for callback in self.tick_callbacks:
                try:
                    callback(tick)
                except Exception as e:
                    logger.error(f"Error in tick callback: {e}")
                    self._trigger_error_callback(e)
            
            self.stats.total_ticks += 1
            
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
            self.stats.error_ticks += 1
            self._trigger_error_callback(e)
    
    def _validate_tick(self, tick: TickData) -> bool:
        """Validate tick data."""
        try:
            # Check timestamp
            if tick.timestamp_ms <= 0:
                return False
            
            # Check price data
            if tick.bid <= 0 or tick.ask <= 0:
                return False
            
            if tick.bid >= tick.ask:
                return False
            
            # Check volume
            if tick.volume < 0:
                return False
            
            return True
        except Exception:
            return False
    
    def _apply_speed_control(self, tick_timestamp_ms: int):
        """Apply speed control based on replay speed."""
        if self.config.speed == ReplaySpeed.INSTANT:
            return
        
        # Calculate delay based on speed
        speed_multiplier = {
            ReplaySpeed.REAL_TIME: 1.0,
            ReplaySpeed.FAST_2X: 0.5,
            ReplaySpeed.FAST_5X: 0.2,
            ReplaySpeed.FAST_10X: 0.1
        }.get(self.config.speed, 1.0)
        
        # Calculate time difference
        if hasattr(self, '_last_tick_time'):
            time_diff = (tick_timestamp_ms - self._last_tick_time) / 1000.0
            delay = time_diff * speed_multiplier
            
            if delay > 0:
                time.sleep(delay)
        
        self._last_tick_time = tick_timestamp_ms
    
    def _apply_rate_limiting(self):
        """Apply rate limiting to prevent overwhelming the system."""
        current_time = int(time.time())
        
        if current_time != self.current_second:
            self.current_second = current_time
            self.ticks_processed_this_second = 0
        
        if self.ticks_processed_this_second >= self.config.max_ticks_per_second:
            time.sleep(0.001)  # Small delay to prevent overwhelming
        
        self.ticks_processed_this_second += 1
    
    def _is_replay_complete(self) -> bool:
        """Check if replay is complete."""
        for symbol in self.config.symbols:
            if symbol in self.tick_data:
                current_pos = self.current_positions[symbol]
                total_ticks = len(self.tick_data[symbol])
                if current_pos < total_ticks:
                    return False
        return True
    
    def _update_progress(self):
        """Update progress and trigger callbacks."""
        total_ticks = sum(len(data) for data in self.tick_data.values())
        processed_ticks = sum(self.current_positions.values())
        
        if total_ticks > 0:
            progress = processed_ticks / total_ticks
            for callback in self.progress_callbacks:
                try:
                    callback(progress)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
    
    def _trigger_error_callback(self, error: Exception):
        """Trigger error callback."""
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def get_stats(self) -> ReplayStats:
        """Get replay statistics."""
        with self.lock:
            # Update current stats
            if self.stats.start_time > 0:
                current_time = time.time()
                self.stats.duration_seconds = current_time - self.stats.start_time
                
                if self.stats.duration_seconds > 0:
                    self.stats.ticks_per_second = self.stats.processed_ticks / self.stats.duration_seconds
            
            return self.stats
    
    def get_progress(self) -> float:
        """Get replay progress (0.0 to 1.0)."""
        total_ticks = sum(len(data) for data in self.tick_data.values())
        processed_ticks = sum(self.current_positions.values())
        
        if total_ticks > 0:
            return processed_ticks / total_ticks
        return 0.0
    
    def reset_replay(self):
        """Reset replay to beginning."""
        with self.lock:
            self.current_positions.clear()
            self.symbol_sequences.clear()
            self.stats = ReplayStats()
            self.status = ReplayStatus.STOPPED
            logger.info("Reset replay to beginning")

class MT5ReplayShim:
    """MT5 I/O shim for replay testing."""
    
    def __init__(self, replay_engine: TickReplayEngine):
        self.replay_engine = replay_engine
        self.symbol_info_cache: Dict[str, Dict[str, Any]] = {}
        self.account_info_cache: Dict[str, Any] = {}
        self.positions_cache: List[Dict[str, Any]] = []
        self.orders_cache: List[Dict[str, Any]] = []
        
        # Register for tick data
        self.replay_engine.add_tick_callback(self._on_tick_data)
    
    def _on_tick_data(self, tick: TickData):
        """Handle tick data from replay engine."""
        # Update symbol info cache
        if tick.symbol not in self.symbol_info_cache:
            self.symbol_info_cache[tick.symbol] = {
                'symbol': tick.symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'volume': tick.volume,
                'time': tick.timestamp_ms
            }
        else:
            self.symbol_info_cache[tick.symbol].update({
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'volume': tick.volume,
                'time': tick.timestamp_ms
            })
    
    def symbol_info_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol info tick (MT5 equivalent)."""
        return self.symbol_info_cache.get(symbol)
    
    def symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol info (MT5 equivalent)."""
        return self.symbol_info_cache.get(symbol)
    
    def account_info(self) -> Dict[str, Any]:
        """Get account info (MT5 equivalent)."""
        return self.account_info_cache
    
    def positions_get(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get positions (MT5 equivalent)."""
        if symbol:
            return [pos for pos in self.positions_cache if pos.get('symbol') == symbol]
        return self.positions_cache
    
    def orders_get(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get orders (MT5 equivalent)."""
        if symbol:
            return [order for order in self.orders_cache if order.get('symbol') == symbol]
        return self.orders_cache
    
    def order_send(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send order (MT5 equivalent)."""
        # Simulate order sending
        order_result = {
            'retcode': 10009,  # TRADE_RETCODE_DONE
            'deal': 12345,
            'order': 67890,
            'volume': request.get('volume', 0.01),
            'price': request.get('price', 0.0),
            'comment': request.get('comment', ''),
            'request_id': request.get('request_id', 0)
        }
        
        # Add to orders cache
        self.orders_cache.append({
            'ticket': order_result['order'],
            'symbol': request.get('symbol', ''),
            'type': request.get('type', 0),
            'volume': order_result['volume'],
            'price': order_result['price'],
            'comment': order_result['comment'],
            'time_setup': int(time.time() * 1000)
        })
        
        return order_result
    
    def position_close(self, ticket: int) -> Dict[str, Any]:
        """Close position (MT5 equivalent)."""
        # Simulate position closing
        close_result = {
            'retcode': 10009,  # TRADE_RETCODE_DONE
            'deal': 12346,
            'volume': 0.01,
            'price': 0.0,
            'comment': 'Position closed'
        }
        
        # Remove from positions cache
        self.positions_cache = [pos for pos in self.positions_cache if pos.get('ticket') != ticket]
        
        return close_result

class TickReplayManager:
    """Manager for multiple tick replay instances."""
    
    def __init__(self):
        self.replay_engines: Dict[str, TickReplayEngine] = {}
        self.mt5_shims: Dict[str, MT5ReplayShim] = {}
        self.global_callbacks: List[Callable] = []
        self.lock = threading.RLock()
    
    def create_replay(self, name: str, config: ReplayConfig) -> TickReplayEngine:
        """Create a new replay instance."""
        with self.lock:
            if name in self.replay_engines:
                raise ValueError(f"Replay '{name}' already exists")
            
            engine = TickReplayEngine(config)
            self.replay_engines[name] = engine
            
            # Create MT5 shim
            shim = MT5ReplayShim(engine)
            self.mt5_shims[name] = shim
            
            logger.info(f"Created replay '{name}' with {len(config.symbols)} symbols")
            return engine
    
    def get_replay(self, name: str) -> Optional[TickReplayEngine]:
        """Get replay instance by name."""
        return self.replay_engines.get(name)
    
    def get_mt5_shim(self, name: str) -> Optional[MT5ReplayShim]:
        """Get MT5 shim by name."""
        return self.mt5_shims.get(name)
    
    def start_replay(self, name: str) -> bool:
        """Start replay by name."""
        engine = self.get_replay(name)
        if engine:
            return engine.start_replay()
        return False
    
    def stop_replay(self, name: str):
        """Stop replay by name."""
        engine = self.get_replay(name)
        if engine:
            engine.stop_replay()
    
    def pause_replay(self, name: str):
        """Pause replay by name."""
        engine = self.get_replay(name)
        if engine:
            engine.pause_replay()
    
    def resume_replay(self, name: str):
        """Resume replay by name."""
        engine = self.get_replay(name)
        if engine:
            engine.resume_replay()
    
    def get_all_stats(self) -> Dict[str, ReplayStats]:
        """Get statistics for all replays."""
        with self.lock:
            stats = {}
            for name, engine in self.replay_engines.items():
                stats[name] = engine.get_stats()
            return stats
    
    def cleanup_replay(self, name: str):
        """Cleanup replay instance."""
        with self.lock:
            if name in self.replay_engines:
                self.replay_engines[name].stop_replay()
                del self.replay_engines[name]
                del self.mt5_shims[name]
                logger.info(f"Cleaned up replay '{name}'")

# Global replay manager instance
replay_manager = TickReplayManager()

def get_replay_manager() -> TickReplayManager:
    """Get the global replay manager instance."""
    return replay_manager

def create_replay(name: str, config: ReplayConfig) -> TickReplayEngine:
    """Create a new replay instance."""
    return replay_manager.create_replay(name, config)

def get_replay(name: str) -> Optional[TickReplayEngine]:
    """Get replay instance by name."""
    return replay_manager.get_replay(name)

def get_mt5_shim(name: str) -> Optional[MT5ReplayShim]:
    """Get MT5 shim by name."""
    return replay_manager.get_mt5_shim(name)

if __name__ == "__main__":
    # Example usage
    config = ReplayConfig(
        symbols=["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc"],
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now(),
        mode=ReplayMode.DETERMINISTIC,
        speed=ReplaySpeed.REAL_TIME,
        data_source="database"
    )
    
    # Create replay
    engine = create_replay("test_replay", config)
    
    # Add callbacks
    def on_tick(tick: TickData):
        print(f"Tick: {tick.symbol} {tick.bid}/{tick.ask} @ {tick.timestamp_ms}")
    
    def on_progress(progress: float):
        print(f"Progress: {progress:.2%}")
    
    engine.add_tick_callback(on_tick)
    engine.add_progress_callback(on_progress)
    
    # Load data and start replay
    if engine.load_data():
        engine.start_replay()
        
        # Wait for completion
        while engine.status == ReplayStatus.RUNNING:
            time.sleep(1.0)
        
        # Print stats
        stats = engine.get_stats()
        print(f"Replay completed: {stats.processed_ticks} ticks in {stats.duration_seconds:.2f}s")
