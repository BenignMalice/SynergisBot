"""
Numba Compute Engine
High-performance GIL-free computations using Numba JIT compilation
Optimized for VWAP, ATR, Delta calculations and market structure analysis
"""

import numpy as np
from numba import jit, prange, float32, int64, boolean, types
from numba.typed import List
from typing import Dict, Any, List as TypingList, Optional, Tuple
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ComputeStats:
    """Statistics for compute operations"""
    total_operations: int = 0
    avg_execution_time_ns: float = 0.0
    max_execution_time_ns: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

class NumbaComputeEngine:
    """
    High-performance compute engine using Numba JIT compilation
    All functions are GIL-free and can run in parallel
    """
    
    def __init__(self):
        self.stats = ComputeStats()
        self._cache = {}
        self._cache_size_limit = 1000
        
    def _update_stats(self, execution_time_ns: float):
        """Update compute statistics"""
        self.stats.total_operations += 1
        self.stats.avg_execution_time_ns = (
            (self.stats.avg_execution_time_ns * (self.stats.total_operations - 1) + execution_time_ns) 
            / self.stats.total_operations
        )
        self.stats.max_execution_time_ns = max(self.stats.max_execution_time_ns, execution_time_ns)

# VWAP Calculations
@jit(nopython=True, cache=True, parallel=True)
def calculate_vwap_numba(prices: np.ndarray, volumes: np.ndarray) -> float32:
    """
    Calculate VWAP using Numba for maximum performance
    GIL-free and can run in parallel
    """
    if len(prices) == 0 or len(volumes) == 0:
        return float32(0.0)
    
    total_volume = np.sum(volumes)
    if total_volume == 0.0:
        return float32(prices[-1]) if len(prices) > 0 else float32(0.0)
    
    weighted_sum = np.sum(prices * volumes)
    return float32(weighted_sum / total_volume)

@jit(nopython=True, cache=True, parallel=True)
def calculate_vwap_rolling_numba(prices: np.ndarray, volumes: np.ndarray, window: int) -> np.ndarray:
    """
    Calculate rolling VWAP using Numba
    Returns array of VWAP values for each window
    """
    n = len(prices)
    if n == 0 or window <= 0:
        return np.zeros(n, dtype=float32)
    
    result = np.zeros(n, dtype=float32)
    
    for i in prange(n):
        start_idx = max(0, i - window + 1)
        window_prices = prices[start_idx:i+1]
        window_volumes = volumes[start_idx:i+1]
        
        total_volume = np.sum(window_volumes)
        if total_volume > 0.0:
            result[i] = np.sum(window_prices * window_volumes) / total_volume
        else:
            result[i] = window_prices[-1] if len(window_prices) > 0 else 0.0
    
    return result

# ATR Calculations
@jit(nopython=True, cache=True, parallel=True)
def calculate_atr_numba(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate ATR using Numba for maximum performance
    GIL-free and can run in parallel
    """
    n = len(closes)
    if n < period:
        return np.zeros(n, dtype=float32)
    
    atr = np.zeros(n, dtype=float32)
    
    # Calculate True Range
    tr = np.zeros(n, dtype=float32)
    tr[0] = highs[0] - lows[0]
    
    for i in prange(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr[i] = max(hl, hc, lc)
    
    # Calculate ATR as SMA of TR
    if n >= period:
        atr[period-1] = np.mean(tr[:period])
        for i in prange(period, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    return atr

@jit(nopython=True, cache=True, parallel=True)
def calculate_atr_ratio_numba(m1_atr: np.ndarray, m5_atr: np.ndarray) -> np.ndarray:
    """
    Calculate ATR ratio (M1 ATR vs M5 ATR) using Numba
    """
    n = min(len(m1_atr), len(m5_atr))
    if n == 0:
        return np.zeros(0, dtype=float32)
    
    ratio = np.zeros(n, dtype=float32)
    
    for i in prange(n):
        if m5_atr[i] > 0.0:
            ratio[i] = m1_atr[i] / m5_atr[i]
        else:
            ratio[i] = 0.0
    
    return ratio

# Volume Delta Calculations
@jit(nopython=True, cache=True, parallel=True)
def calculate_volume_delta_numba(prices: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """
    Calculate volume delta using Numba
    Positive delta = buying pressure, Negative delta = selling pressure
    """
    n = len(prices)
    if n < 2:
        return np.zeros(n, dtype=float32)
    
    delta = np.zeros(n, dtype=float32)
    
    for i in prange(1, n):
        price_change = prices[i] - prices[i-1]
        if price_change > 0:
            delta[i] = volumes[i]  # Up-tick volume
        elif price_change < 0:
            delta[i] = -volumes[i]  # Down-tick volume
        else:
            delta[i] = 0.0  # No change
    
    return delta

@jit(nopython=True, cache=True, parallel=True)
def calculate_volume_delta_cumulative_numba(prices: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """
    Calculate cumulative volume delta using Numba
    """
    n = len(prices)
    if n < 2:
        return np.zeros(n, dtype=float32)
    
    delta = calculate_volume_delta_numba(prices, volumes)
    cumulative = np.zeros(n, dtype=float32)
    cumulative[0] = delta[0]
    
    for i in prange(1, n):
        cumulative[i] = cumulative[i-1] + delta[i]
    
    return cumulative

# Market Structure Calculations
@jit(nopython=True, cache=True, parallel=True)
def detect_swing_highs_numba(highs: np.ndarray, lookback: int) -> np.ndarray:
    """
    Detect swing highs using Numba
    Returns boolean array where True indicates swing high
    """
    n = len(highs)
    if n < lookback * 2 + 1:
        return np.zeros(n, dtype=boolean)
    
    swing_highs = np.zeros(n, dtype=boolean)
    
    for i in prange(lookback, n - lookback):
        is_swing_high = True
        current_high = highs[i]
        
        # Check left side
        for j in prange(i - lookback, i):
            if highs[j] >= current_high:
                is_swing_high = False
                break
        
        # Check right side
        if is_swing_high:
            for j in prange(i + 1, i + lookback + 1):
                if highs[j] >= current_high:
                    is_swing_high = False
                    break
        
        swing_highs[i] = is_swing_high
    
    return swing_highs

@jit(nopython=True, cache=True, parallel=True)
def detect_swing_lows_numba(lows: np.ndarray, lookback: int) -> np.ndarray:
    """
    Detect swing lows using Numba
    Returns boolean array where True indicates swing low
    """
    n = len(lows)
    if n < lookback * 2 + 1:
        return np.zeros(n, dtype=boolean)
    
    swing_lows = np.zeros(n, dtype=boolean)
    
    for i in prange(lookback, n - lookback):
        is_swing_low = True
        current_low = lows[i]
        
        # Check left side
        for j in prange(i - lookback, i):
            if lows[j] <= current_low:
                is_swing_low = False
                break
        
        # Check right side
        if is_swing_low:
            for j in prange(i + 1, i + lookback + 1):
                if lows[j] <= current_low:
                    is_swing_low = False
                    break
        
        swing_lows[i] = is_swing_low
    
    return swing_lows

# Momentum Calculations
@jit(nopython=True, cache=True, parallel=True)
def calculate_momentum_numba(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate momentum using Numba
    """
    n = len(prices)
    if n < period:
        return np.zeros(n, dtype=float32)
    
    momentum = np.zeros(n, dtype=float32)
    
    for i in prange(period, n):
        momentum[i] = prices[i] - prices[i - period]
    
    return momentum

@jit(nopython=True, cache=True, parallel=True)
def calculate_rsi_numba(prices: np.ndarray, period: int) -> np.ndarray:
    """
    Calculate RSI using Numba
    """
    n = len(prices)
    if n < period + 1:
        return np.zeros(n, dtype=float32)
    
    rsi = np.zeros(n, dtype=float32)
    gains = np.zeros(n, dtype=float32)
    losses = np.zeros(n, dtype=float32)
    
    # Calculate price changes
    for i in prange(1, n):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = -change
    
    # Calculate initial averages
    avg_gain = np.mean(gains[1:period+1])
    avg_loss = np.mean(losses[1:period+1])
    
    if avg_loss == 0.0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))
    
    # Calculate subsequent RSI values
    for i in prange(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0.0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi

# Spread and Volatility Calculations
@jit(nopython=True, cache=True, parallel=True)
def calculate_spread_median_numba(spreads: np.ndarray, window: int) -> np.ndarray:
    """
    Calculate rolling median of spreads using Numba
    """
    n = len(spreads)
    if n == 0:
        return np.zeros(0, dtype=float32)
    
    median = np.zeros(n, dtype=float32)
    
    for i in prange(n):
        start_idx = max(0, i - window + 1)
        window_data = spreads[start_idx:i+1]
        median[i] = np.median(window_data)
    
    return median

@jit(nopython=True, cache=True, parallel=True)
def calculate_volatility_numba(returns: np.ndarray, window: int) -> np.ndarray:
    """
    Calculate rolling volatility using Numba
    """
    n = len(returns)
    if n == 0:
        return np.zeros(0, dtype=float32)
    
    volatility = np.zeros(n, dtype=float32)
    
    for i in prange(window, n):
        window_returns = returns[i-window:i]
        volatility[i] = np.std(window_returns)
    
    return volatility

# Micro-BOS/CHOCH Detection
@jit(nopython=True, cache=True, parallel=True)
def detect_micro_bos_numba(highs: np.ndarray, lows: np.ndarray, atr: np.ndarray, 
                          displacement_ratio: float32, cooldown: int) -> np.ndarray:
    """
    Detect micro Break of Structure using Numba
    """
    n = len(highs)
    if n < 2:
        return np.zeros(n, dtype=boolean)
    
    micro_bos = np.zeros(n, dtype=boolean)
    last_bos_time = -cooldown - 1
    
    for i in prange(1, n):
        # Check if enough time has passed since last BOS
        if i - last_bos_time < cooldown:
            continue
        
        # Check for bullish BOS (break above recent high)
        recent_high = np.max(highs[max(0, i-10):i])
        if highs[i] > recent_high and atr[i] > 0:
            displacement = highs[i] - recent_high
            if displacement >= atr[i] * displacement_ratio:
                micro_bos[i] = True
                last_bos_time = i
        
        # Check for bearish BOS (break below recent low)
        recent_low = np.min(lows[max(0, i-10):i])
        if lows[i] < recent_low and atr[i] > 0:
            displacement = recent_low - lows[i]
            if displacement >= atr[i] * displacement_ratio:
                micro_bos[i] = True
                last_bos_time = i
    
    return micro_bos

# Performance Monitoring
@jit(nopython=True, cache=True)
def calculate_performance_metrics_numba(execution_times: np.ndarray) -> Tuple[float32, float32, float32]:
    """
    Calculate performance metrics using Numba
    Returns (mean, p95, p99)
    """
    n = len(execution_times)
    if n == 0:
        return float32(0.0), float32(0.0), float32(0.0)
    
    # Sort for percentile calculation
    sorted_times = np.sort(execution_times)
    
    mean_time = np.mean(execution_times)
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)
    
    p95_time = sorted_times[p95_idx] if p95_idx < n else sorted_times[-1]
    p99_time = sorted_times[p99_idx] if p99_idx < n else sorted_times[-1]
    
    return float32(mean_time), float32(p95_time), float32(p99_time)

class NumbaComputeEngine:
    """
    Main compute engine class with caching and performance monitoring
    """
    
    def __init__(self):
        self.stats = ComputeStats()
        self._cache = {}
        self._cache_size_limit = 1000
    
    def calculate_vwap(self, prices: np.ndarray, volumes: np.ndarray, 
                      use_cache: bool = True) -> float32:
        """Calculate VWAP with caching and performance monitoring"""
        start_time = time.perf_counter_ns()
        
        # Check cache
        cache_key = f"vwap_{hash(prices.tobytes())}_{hash(volumes.tobytes())}"
        if use_cache and cache_key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[cache_key]
        
        # Calculate VWAP
        result = calculate_vwap_numba(prices.astype(np.float32), volumes.astype(np.float32))
        
        # Update cache
        if use_cache and len(self._cache) < self._cache_size_limit:
            self._cache[cache_key] = result
        else:
            self.stats.cache_misses += 1
        
        # Update statistics
        end_time = time.perf_counter_ns()
        self._update_stats(end_time - start_time)
        
        return result
    
    def calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
                     period: int, use_cache: bool = True) -> np.ndarray:
        """Calculate ATR with caching and performance monitoring"""
        start_time = time.perf_counter_ns()
        
        # Check cache
        cache_key = f"atr_{hash(highs.tobytes())}_{hash(lows.tobytes())}_{hash(closes.tobytes())}_{period}"
        if use_cache and cache_key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[cache_key]
        
        # Calculate ATR
        result = calculate_atr_numba(
            highs.astype(np.float32), 
            lows.astype(np.float32), 
            closes.astype(np.float32), 
            period
        )
        
        # Update cache
        if use_cache and len(self._cache) < self._cache_size_limit:
            self._cache[cache_key] = result
        else:
            self.stats.cache_misses += 1
        
        # Update statistics
        end_time = time.perf_counter_ns()
        self._update_stats(end_time - start_time)
        
        return result
    
    def calculate_volume_delta(self, prices: np.ndarray, volumes: np.ndarray, 
                             use_cache: bool = True) -> np.ndarray:
        """Calculate volume delta with caching and performance monitoring"""
        start_time = time.perf_counter_ns()
        
        # Check cache
        cache_key = f"delta_{hash(prices.tobytes())}_{hash(volumes.tobytes())}"
        if use_cache and cache_key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[cache_key]
        
        # Calculate volume delta
        result = calculate_volume_delta_numba(
            prices.astype(np.float32), 
            volumes.astype(np.float32)
        )
        
        # Update cache
        if use_cache and len(self._cache) < self._cache_size_limit:
            self._cache[cache_key] = result
        else:
            self.stats.cache_misses += 1
        
        # Update statistics
        end_time = time.perf_counter_ns()
        self._update_stats(end_time - start_time)
        
        return result
    
    def detect_market_structure(self, highs: np.ndarray, lows: np.ndarray, 
                              lookback: int, use_cache: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """Detect market structure with caching and performance monitoring"""
        start_time = time.perf_counter_ns()
        
        # Check cache
        cache_key = f"structure_{hash(highs.tobytes())}_{hash(lows.tobytes())}_{lookback}"
        if use_cache and cache_key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[cache_key]
        
        # Detect structure
        swing_highs = detect_swing_highs_numba(highs.astype(np.float32), lookback)
        swing_lows = detect_swing_lows_numba(lows.astype(np.float32), lookback)
        
        result = (swing_highs, swing_lows)
        
        # Update cache
        if use_cache and len(self._cache) < self._cache_size_limit:
            self._cache[cache_key] = result
        else:
            self.stats.cache_misses += 1
        
        # Update statistics
        end_time = time.perf_counter_ns()
        self._update_stats(end_time - start_time)
        
        return result
    
    def _update_stats(self, execution_time_ns: float):
        """Update compute statistics"""
        self.stats.total_operations += 1
        self.stats.avg_execution_time_ns = (
            (self.stats.avg_execution_time_ns * (self.stats.total_operations - 1) + execution_time_ns) 
            / self.stats.total_operations
        )
        self.stats.max_execution_time_ns = max(self.stats.max_execution_time_ns, execution_time_ns)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compute engine statistics"""
        return {
            'total_operations': self.stats.total_operations,
            'avg_execution_time_ns': self.stats.avg_execution_time_ns,
            'avg_execution_time_ms': self.stats.avg_execution_time_ns / 1_000_000,
            'max_execution_time_ns': self.stats.max_execution_time_ns,
            'max_execution_time_ms': self.stats.max_execution_time_ns / 1_000_000,
            'cache_hits': self.stats.cache_hits,
            'cache_misses': self.stats.cache_misses,
            'cache_hit_rate': self.stats.cache_hits / max(self.stats.cache_hits + self.stats.cache_misses, 1),
            'cache_size': len(self._cache)
        }
    
    def clear_cache(self):
        """Clear the computation cache"""
        self._cache.clear()
        logger.info("Compute cache cleared")
    
    def warmup(self, data_size: int = 1000):
        """Warmup the JIT compiler with sample data"""
        logger.info("Warming up Numba JIT compiler...")
        
        # Create sample data
        prices = np.random.rand(data_size).astype(np.float32) * 100 + 1000
        volumes = np.random.rand(data_size).astype(np.float32) * 1000
        highs = prices + np.random.rand(data_size).astype(np.float32) * 10
        lows = prices - np.random.rand(data_size).astype(np.float32) * 10
        closes = prices
        
        # Warmup all functions
        _ = calculate_vwap_numba(prices, volumes)
        _ = calculate_atr_numba(highs, lows, closes, 14)
        _ = calculate_volume_delta_numba(prices, volumes)
        _ = detect_swing_highs_numba(highs, 5)
        _ = detect_swing_lows_numba(lows, 5)
        _ = calculate_momentum_numba(prices, 10)
        _ = calculate_rsi_numba(prices, 14)
        
        logger.info("Numba JIT compiler warmup completed")

# Global compute engine instance
_compute_engine: Optional[NumbaComputeEngine] = None

def get_compute_engine() -> NumbaComputeEngine:
    """Get the global compute engine instance"""
    global _compute_engine
    if _compute_engine is None:
        _compute_engine = NumbaComputeEngine()
        _compute_engine.warmup()
    return _compute_engine

def initialize_compute_engine() -> NumbaComputeEngine:
    """Initialize the global compute engine"""
    global _compute_engine
    _compute_engine = NumbaComputeEngine()
    _compute_engine.warmup()
    return _compute_engine
