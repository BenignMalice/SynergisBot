"""
Optimized Ring Buffers for High-Performance Trading
Memory-efficient, thread-safe ring buffers with Numba optimization
"""

import numpy as np
import threading
from typing import Dict, Any, List, Optional, TypeVar, Generic
from dataclasses import dataclass
from numba import jit, float32, int64, boolean
import time
import logging
from collections import deque

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class RingBufferStats:
    """Statistics for ring buffer performance"""
    total_writes: int = 0
    total_reads: int = 0
    buffer_overflows: int = 0
    average_write_latency_ns: float = 0.0
    average_read_latency_ns: float = 0.0
    memory_usage_bytes: int = 0

class OptimizedRingBuffer:
    """
    High-performance ring buffer with Numba optimization
    Uses pre-allocated numpy arrays for maximum efficiency
    """
    
    def __init__(self, capacity: int, dtype=np.float32, name: str = "ring_buffer"):
        self.capacity = min(capacity, 2000)  # Cap at 2k for laptop safety (reduced from 50k)
        self.dtype = dtype
        self.name = name
        
        # Pre-allocate arrays
        self.buffer = np.zeros(self.capacity, dtype=dtype)
        self.timestamps = np.zeros(self.capacity, dtype=np.int64)
        
        # Ring buffer state
        self.write_index = 0
        self.read_index = 0
        self.size = 0
        self.overflow_count = 0
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = RingBufferStats()
        self.stats.memory_usage_bytes = self.buffer.nbytes + self.timestamps.nbytes
        
        # Performance tracking
        self._write_times = deque(maxlen=1000)
        self._read_times = deque(maxlen=1000)
    
    def append(self, value: float, timestamp_ms: Optional[int] = None) -> bool:
        """
        Append value to ring buffer
        Returns True if successful, False if buffer is full
        """
        start_time = time.perf_counter_ns()
        
        with self.lock:
            if timestamp_ms is None:
                timestamp_ms = int(time.time() * 1000)
            
            # Check for overflow
            if self.size >= self.capacity:
                self.overflow_count += 1
                self.stats.buffer_overflows += 1
                logger.warning(f"Ring buffer {self.name} overflow detected")
            
            # Write to buffer
            self.buffer[self.write_index] = self.dtype(value)
            self.timestamps[self.write_index] = timestamp_ms
            
            # Update indices
            self.write_index = (self.write_index + 1) % self.capacity
            if self.size < self.capacity:
                self.size += 1
            else:
                # Buffer is full, advance read index
                self.read_index = (self.read_index + 1) % self.capacity
            
            # Update statistics
            self.stats.total_writes += 1
            end_time = time.perf_counter_ns()
            latency_ns = end_time - start_time
            self._write_times.append(latency_ns)
            self.stats.average_write_latency_ns = np.mean(self._write_times)
            
            return True
    
    def get_latest(self, count: int) -> np.ndarray:
        """Get latest N elements from buffer"""
        start_time = time.perf_counter_ns()
        
        with self.lock:
            if count <= 0 or self.size == 0:
                return np.array([], dtype=self.dtype)
            
            count = min(count, self.size)
            
            if self.write_index >= count:
                # No wrap-around needed
                result = self.buffer[self.write_index - count:self.write_index]
            else:
                # Wrap-around case
                remaining = count - self.write_index
                result = np.concatenate([
                    self.buffer[self.capacity - remaining:],
                    self.buffer[:self.write_index]
                ])
            
            # Update statistics
            self.stats.total_reads += 1
            end_time = time.perf_counter_ns()
            latency_ns = end_time - start_time
            self._read_times.append(latency_ns)
            self.stats.average_read_latency_ns = np.mean(self._read_times)
            
            return result
    
    def get_all(self) -> np.ndarray:
        """Get all elements currently in buffer"""
        return self.get_latest(self.size)
    
    def get_timestamps(self, count: int) -> np.ndarray:
        """Get timestamps for latest N elements"""
        with self.lock:
            if count <= 0 or self.size == 0:
                return np.array([], dtype=np.int64)
            
            count = min(count, self.size)
            
            if self.write_index >= count:
                return self.timestamps[self.write_index - count:self.write_index]
            else:
                remaining = count - self.write_index
                return np.concatenate([
                    self.timestamps[self.capacity - remaining:],
                    self.timestamps[:self.write_index]
                ])
    
    def clear(self):
        """Clear the buffer"""
        with self.lock:
            self.write_index = 0
            self.read_index = 0
            self.size = 0
            self.overflow_count = 0
    
    def __len__(self) -> int:
        return self.size
    
    def is_full(self) -> bool:
        return self.size >= self.capacity
    
    def get_usage_percentage(self) -> float:
        """Get buffer usage percentage"""
        with self.lock:
            return (self.size / self.capacity) * 100.0 if self.capacity > 0 else 0.0
    
    def get_stats(self) -> RingBufferStats:
        """Get buffer statistics"""
        return self.stats

class MultiSymbolRingBuffer:
    """
    Ring buffer manager for multiple symbols
    Optimized for memory efficiency and performance
    """
    
    def __init__(self, symbols: List[str], capacity_per_symbol: int = 1000):
        self.symbols = symbols
        self.capacity_per_symbol = min(capacity_per_symbol, 2000)  # Cap at 2k per symbol (reduced from 20k for laptop safety)
        
        # Per-symbol buffers
        self.buffers: Dict[str, OptimizedRingBuffer] = {}
        self.timestamp_buffers: Dict[str, OptimizedRingBuffer] = {}
        self.volume_buffers: Dict[str, OptimizedRingBuffer] = {}
        self.spread_buffers: Dict[str, OptimizedRingBuffer] = {}
        
        # Initialize buffers for each symbol
        for symbol in symbols:
            self.buffers[symbol] = OptimizedRingBuffer(
                self.capacity_per_symbol, 
                dtype=np.float32, 
                name=f"price_{symbol}"
            )
            self.timestamp_buffers[symbol] = OptimizedRingBuffer(
                self.capacity_per_symbol, 
                dtype=np.int64, 
                name=f"timestamp_{symbol}"
            )
            self.volume_buffers[symbol] = OptimizedRingBuffer(
                self.capacity_per_symbol, 
                dtype=np.float32, 
                name=f"volume_{symbol}"
            )
            self.spread_buffers[symbol] = OptimizedRingBuffer(
                self.capacity_per_symbol, 
                dtype=np.float32, 
                name=f"spread_{symbol}"
            )
    
    def add_tick(self, symbol: str, price: float, volume: float, spread: float, timestamp_ms: int):
        """Add tick data for a symbol"""
        if symbol not in self.buffers:
            logger.warning(f"Symbol {symbol} not found in ring buffer manager")
            return
        
        self.buffers[symbol].append(price, timestamp_ms)
        self.volume_buffers[symbol].append(volume, timestamp_ms)
        self.spread_buffers[symbol].append(spread, timestamp_ms)
        self.timestamp_buffers[symbol].append(timestamp_ms, timestamp_ms)
    
    def get_latest_prices(self, symbol: str, count: int) -> np.ndarray:
        """Get latest prices for a symbol"""
        if symbol not in self.buffers:
            return np.array([], dtype=np.float32)
        return self.buffers[symbol].get_latest(count)
    
    def get_latest_volumes(self, symbol: str, count: int) -> np.ndarray:
        """Get latest volumes for a symbol"""
        if symbol not in self.volume_buffers:
            return np.array([], dtype=np.float32)
        return self.volume_buffers[symbol].get_latest(count)
    
    def get_latest_spreads(self, symbol: str, count: int) -> np.ndarray:
        """Get latest spreads for a symbol"""
        if symbol not in self.spread_buffers:
            return np.array([], dtype=np.float32)
        return self.spread_buffers[symbol].get_latest(count)
    
    def get_all_data(self, symbol: str) -> Dict[str, np.ndarray]:
        """Get all data for a symbol"""
        if symbol not in self.buffers:
            return {}
        
        return {
            'prices': self.buffers[symbol].get_all(),
            'volumes': self.volume_buffers[symbol].get_all(),
            'spreads': self.spread_buffers[symbol].get_all(),
            'timestamps': self.timestamp_buffers[symbol].get_all()
        }
    
    def get_stats(self) -> Dict[str, RingBufferStats]:
        """Get statistics for all symbols"""
        stats = {}
        for symbol in self.symbols:
            if symbol in self.buffers:
                stats[symbol] = {
                    'price_buffer': self.buffers[symbol].get_stats(),
                    'volume_buffer': self.volume_buffers[symbol].get_stats(),
                    'spread_buffer': self.spread_buffers[symbol].get_stats(),
                    'timestamp_buffer': self.timestamp_buffers[symbol].get_stats()
                }
        return stats

# Numba-optimized calculations for ring buffers
@jit(nopython=True, cache=True)
def calculate_rolling_mean_numba(data: np.ndarray, window: int) -> np.ndarray:
    """Calculate rolling mean using Numba for performance"""
    n = len(data)
    result = np.zeros(n, dtype=np.float32)
    
    for i in range(n):
        start_idx = max(0, i - window + 1)
        window_data = data[start_idx:i+1]
        result[i] = np.mean(window_data)
    
    return result

@jit(nopython=True, cache=True)
def calculate_rolling_std_numba(data: np.ndarray, window: int) -> np.ndarray:
    """Calculate rolling standard deviation using Numba"""
    n = len(data)
    result = np.zeros(n, dtype=np.float32)
    
    for i in range(n):
        start_idx = max(0, i - window + 1)
        window_data = data[start_idx:i+1]
        if len(window_data) > 1:
            result[i] = np.std(window_data)
        else:
            result[i] = 0.0
    
    return result

@jit(nopython=True, cache=True)
def calculate_rolling_median_numba(data: np.ndarray, window: int) -> np.ndarray:
    """Calculate rolling median using Numba"""
    n = len(data)
    result = np.zeros(n, dtype=np.float32)
    
    for i in range(n):
        start_idx = max(0, i - window + 1)
        window_data = data[start_idx:i+1]
        result[i] = np.median(window_data)
    
    return result

class FeatureRingBuffer:
    """
    Ring buffer specifically for calculated features
    Optimized for VWAP, ATR, Delta calculations
    """
    
    def __init__(self, capacity: int = 5000):
        self.capacity = min(capacity, 10000)  # Cap at 10k for memory efficiency
        
        # Feature buffers
        self.vwap_buffer = OptimizedRingBuffer(capacity, dtype=np.float32, name="vwap")
        self.atr_buffer = OptimizedRingBuffer(capacity, dtype=np.float32, name="atr")
        self.delta_buffer = OptimizedRingBuffer(capacity, dtype=np.float32, name="delta")
        self.volume_delta_buffer = OptimizedRingBuffer(capacity, dtype=np.float32, name="volume_delta")
        
        # Timestamps for feature calculations
        self.timestamp_buffer = OptimizedRingBuffer(capacity, dtype=np.int64, name="feature_timestamps")
        
        # Calculation state
        self.last_calculation_time = 0
        self.calculation_interval_ms = 100  # Calculate features every 100ms
    
    def add_tick_data(self, price: float, volume: float, timestamp_ms: int):
        """Add tick data and calculate features if needed"""
        current_time = timestamp_ms
        
        # Only calculate features at specified intervals
        if current_time - self.last_calculation_time < self.calculation_interval_ms:
            return
        
        self.last_calculation_time = current_time
        
        # Get recent data for calculations
        recent_prices = self.vwap_buffer.get_latest(100)
        recent_volumes = self.volume_delta_buffer.get_latest(100)
        
        # Calculate VWAP
        if len(recent_prices) > 0:
            vwap = self._calculate_vwap(recent_prices, recent_volumes)
            self.vwap_buffer.append(vwap, timestamp_ms)
        
        # Calculate ATR (simplified)
        if len(recent_prices) > 14:
            atr = self._calculate_atr(recent_prices)
            self.atr_buffer.append(atr, timestamp_ms)
        
        # Calculate Delta
        if len(recent_prices) > 1:
            delta = recent_prices[-1] - recent_prices[-2]
            self.delta_buffer.append(delta, timestamp_ms)
        
        # Calculate Volume Delta
        if len(recent_volumes) > 1:
            volume_delta = recent_volumes[-1] - recent_volumes[-2]
            self.volume_delta_buffer.append(volume_delta, timestamp_ms)
        
        self.timestamp_buffer.append(timestamp_ms, timestamp_ms)
    
    def _calculate_vwap(self, prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate VWAP from recent data"""
        if len(prices) == 0 or np.sum(volumes) == 0:
            return prices[-1] if len(prices) > 0 else 0.0
        
        return np.sum(prices * volumes) / np.sum(volumes)
    
    def _calculate_atr(self, prices: np.ndarray) -> float:
        """Calculate ATR from recent prices (simplified)"""
        if len(prices) < 14:
            return 0.0
        
        # Simplified ATR calculation
        price_changes = np.abs(np.diff(prices))
        return np.mean(price_changes[-14:])
    
    def get_latest_features(self, count: int) -> Dict[str, np.ndarray]:
        """Get latest calculated features"""
        return {
            'vwap': self.vwap_buffer.get_latest(count),
            'atr': self.atr_buffer.get_latest(count),
            'delta': self.delta_buffer.get_latest(count),
            'volume_delta': self.volume_delta_buffer.get_latest(count),
            'timestamps': self.timestamp_buffer.get_latest(count)
        }
    
    def get_usage_percentage(self) -> float:
        """Get average usage percentage across all feature buffers"""
        usage_percentages = [
            self.vwap_buffer.get_usage_percentage(),
            self.atr_buffer.get_usage_percentage(),
            self.delta_buffer.get_usage_percentage(),
            self.volume_delta_buffer.get_usage_percentage(),
            self.timestamp_buffer.get_usage_percentage()
        ]
        return sum(usage_percentages) / len(usage_percentages) if usage_percentages else 0.0
    
    def get_stats(self) -> Dict[str, RingBufferStats]:
        """Get statistics for all feature buffers"""
        return {
            'vwap': self.vwap_buffer.get_stats(),
            'atr': self.atr_buffer.get_stats(),
            'delta': self.delta_buffer.get_stats(),
            'volume_delta': self.volume_delta_buffer.get_stats(),
            'timestamps': self.timestamp_buffer.get_stats()
        }

# Memory usage monitoring
class RingBufferMonitor:
    """Monitor ring buffer memory usage and performance"""
    
    def __init__(self):
        self.buffers: List[OptimizedRingBuffer] = []
        self.monitor_interval_seconds = 60
        self.last_monitor_time = 0
    
    def register_buffer(self, buffer: OptimizedRingBuffer):
        """Register a buffer for monitoring"""
        self.buffers.append(buffer)
    
    def get_total_memory_usage(self) -> int:
        """Get total memory usage of all registered buffers"""
        total_bytes = 0
        for buffer in self.buffers:
            total_bytes += buffer.stats.memory_usage_bytes
        return total_bytes
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of all buffers"""
        total_writes = sum(buffer.stats.total_writes for buffer in self.buffers)
        total_reads = sum(buffer.stats.total_reads for buffer in self.buffers)
        total_overflows = sum(buffer.stats.buffer_overflows for buffer in self.buffers)
        
        avg_write_latency = np.mean([buffer.stats.average_write_latency_ns for buffer in self.buffers])
        avg_read_latency = np.mean([buffer.stats.average_read_latency_ns for buffer in self.buffers])
        
        return {
            'total_buffers': len(self.buffers),
            'total_memory_bytes': self.get_total_memory_usage(),
            'total_writes': total_writes,
            'total_reads': total_reads,
            'total_overflows': total_overflows,
            'avg_write_latency_ns': avg_write_latency,
            'avg_read_latency_ns': avg_read_latency,
            'overflow_rate': total_overflows / max(total_writes, 1)
        }
