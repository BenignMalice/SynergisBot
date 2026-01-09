# =====================================
# infra/m1_monitoring.py
# =====================================
"""
M1 Monitoring Module

Tracks resource usage, refresh performance, and data quality metrics for M1 microstructure analysis.
"""

from __future__ import annotations

import logging
import time
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

# Try to import psutil (optional)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("psutil not available - resource monitoring will be limited. Install with: pip install psutil")

logger = logging.getLogger(__name__)


class M1Monitoring:
    """
    Monitors M1 microstructure analysis performance and resource usage.
    
    Tracks:
    - CPU and memory usage per symbol
    - Refresh frequency and success rate
    - Data freshness (age of latest candle)
    - Snapshot creation time
    - Average refresh latency
    - Data age drift
    - Refresh diagnostics
    """
    
    def __init__(self, max_history: int = 100):
        """
        Initialize M1 Monitoring.
        
        Args:
            max_history: Maximum number of historical records to keep per metric
        """
        self.max_history = max_history
        
        # Per-symbol metrics
        self._refresh_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._refresh_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._refresh_success: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._data_ages: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._data_age_drifts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._snapshot_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Resource usage tracking
        self._cpu_usage: deque = deque(maxlen=max_history)
        self._memory_usage: deque = deque(maxlen=max_history)
        self._process = psutil.Process() if PSUTIL_AVAILABLE else None
        
        # Refresh diagnostics
        self._refresh_diagnostics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        logger.info("M1Monitoring initialized")
    
    def record_refresh(
        self,
        symbol: str,
        success: bool,
        latency_ms: float,
        data_age_seconds: Optional[float] = None,
        expected_age_seconds: Optional[float] = None
    ):
        """
        Record a refresh operation.
        
        Args:
            symbol: Symbol name
            success: Whether refresh was successful
            latency_ms: Refresh latency in milliseconds
            data_age_seconds: Age of latest candle in seconds (if available)
            expected_age_seconds: Expected data age in seconds (if available)
        """
        timestamp = time.time()
        
        self._refresh_times[symbol].append(timestamp)
        self._refresh_latencies[symbol].append(latency_ms)
        self._refresh_success[symbol].append(1 if success else 0)
        
        if data_age_seconds is not None:
            self._data_ages[symbol].append(data_age_seconds)
        
        if data_age_seconds is not None and expected_age_seconds is not None:
            drift = data_age_seconds - expected_age_seconds
            self._data_age_drifts[symbol].append(drift)
        
        # Record diagnostic data
        diagnostic = {
            'timestamp': timestamp,
            'symbol': symbol,
            'success': success,
            'latency_ms': latency_ms,
            'data_age_seconds': data_age_seconds,
            'expected_age_seconds': expected_age_seconds,
            'drift_seconds': data_age_seconds - expected_age_seconds if (data_age_seconds and expected_age_seconds) else None
        }
        self._refresh_diagnostics[symbol].append(diagnostic)
        
        # Keep only recent diagnostics (last 50 per symbol)
        if len(self._refresh_diagnostics[symbol]) > 50:
            self._refresh_diagnostics[symbol] = self._refresh_diagnostics[symbol][-50:]
    
    def record_snapshot(self, symbol: str, snapshot_time_ms: float):
        """
        Record snapshot creation time.
        
        Args:
            symbol: Symbol name
            snapshot_time_ms: Snapshot creation time in milliseconds
        """
        self._snapshot_times[symbol].append(snapshot_time_ms)
    
    def update_resource_usage(self):
        """Update current CPU and memory usage."""
        if not PSUTIL_AVAILABLE or not self._process:
            # Return default values if psutil not available
            self._cpu_usage.append(0.0)
            self._memory_usage.append(0.0)
            return
        
        try:
            cpu_percent = self._process.cpu_percent(interval=0.1)
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
            
            self._cpu_usage.append(cpu_percent)
            self._memory_usage.append(memory_mb)
        except Exception as e:
            logger.debug(f"Error updating resource usage: {e}")
            # Append default values on error
            self._cpu_usage.append(0.0)
            self._memory_usage.append(0.0)
    
    def get_refresh_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Get refresh metrics for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dict with refresh metrics
        """
        latencies = list(self._refresh_latencies[symbol])
        successes = list(self._refresh_success[symbol])
        data_ages = list(self._data_ages[symbol])
        drifts = list(self._data_age_drifts[symbol])
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        success_rate = sum(successes) / len(successes) if successes else 0
        avg_data_age = sum(data_ages) / len(data_ages) if data_ages else None
        avg_drift = sum(drifts) / len(drifts) if drifts else None
        
        return {
            'symbol': symbol,
            'total_refreshes': len(latencies),
            'avg_latency_ms': round(avg_latency, 2),
            'min_latency_ms': round(min(latencies), 2) if latencies else None,
            'max_latency_ms': round(max(latencies), 2) if latencies else None,
            'success_rate': round(success_rate * 100, 2),
            'avg_data_age_seconds': round(avg_data_age, 2) if avg_data_age is not None else None,
            'avg_drift_seconds': round(avg_drift, 2) if avg_drift is not None else None,
            'last_refresh': datetime.fromtimestamp(self._refresh_times[symbol][-1], tz=timezone.utc).isoformat() if self._refresh_times[symbol] else None
        }
    
    def get_all_refresh_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get refresh metrics for all symbols.
        
        Returns:
            Dict mapping symbol to metrics
        """
        all_symbols = set(self._refresh_times.keys())
        return {symbol: self.get_refresh_metrics(symbol) for symbol in all_symbols}
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage.
        
        Returns:
            Dict with CPU and memory usage
        """
        self.update_resource_usage()
        
        cpu_values = list(self._cpu_usage)
        memory_values = list(self._memory_usage)
        
        return {
            'cpu_percent': {
                'current': round(cpu_values[-1], 2) if cpu_values else 0,
                'avg': round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
                'max': round(max(cpu_values), 2) if cpu_values else 0,
                'min': round(min(cpu_values), 2) if cpu_values else 0
            },
            'memory_mb': {
                'current': round(memory_values[-1], 2) if memory_values else 0,
                'avg': round(sum(memory_values) / len(memory_values), 2) if memory_values else 0,
                'max': round(max(memory_values), 2) if memory_values else 0,
                'min': round(min(memory_values), 2) if memory_values else 0
            }
        }
    
    def get_snapshot_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Get snapshot metrics for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dict with snapshot metrics
        """
        snapshot_times = list(self._snapshot_times[symbol])
        
        if not snapshot_times:
            return {
                'symbol': symbol,
                'total_snapshots': 0,
                'avg_time_ms': None,
                'min_time_ms': None,
                'max_time_ms': None
            }
        
        return {
            'symbol': symbol,
            'total_snapshots': len(snapshot_times),
            'avg_time_ms': round(sum(snapshot_times) / len(snapshot_times), 2),
            'min_time_ms': round(min(snapshot_times), 2),
            'max_time_ms': round(max(snapshot_times), 2)
        }
    
    def get_refresh_diagnostics(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent refresh diagnostics for a symbol.
        
        Args:
            symbol: Symbol name
            limit: Maximum number of diagnostics to return
            
        Returns:
            List of diagnostic dicts
        """
        diagnostics = self._refresh_diagnostics.get(symbol, [])
        return diagnostics[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring summary.
        
        Returns:
            Dict with all monitoring data
        """
        return {
            'resource_usage': self.get_resource_usage(),
            'refresh_metrics': self.get_all_refresh_metrics(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def log_summary(self):
        """Log monitoring summary to logger."""
        summary = self.get_summary()
        
        logger.info("=" * 70)
        logger.info("M1 Monitoring Summary")
        logger.info("=" * 70)
        
        # Resource usage
        resource = summary['resource_usage']
        logger.info(f"CPU Usage: {resource['cpu_percent']['current']}% (avg: {resource['cpu_percent']['avg']}%)")
        logger.info(f"Memory Usage: {resource['memory_mb']['current']} MB (avg: {resource['memory_mb']['avg']} MB)")
        
        # Refresh metrics
        refresh_metrics = summary['refresh_metrics']
        if refresh_metrics:
            logger.info("\nRefresh Metrics:")
            for symbol, metrics in refresh_metrics.items():
                logger.info(f"  {symbol}:")
                logger.info(f"    Refreshes: {metrics['total_refreshes']}")
                logger.info(f"    Avg Latency: {metrics['avg_latency_ms']} ms")
                logger.info(f"    Success Rate: {metrics['success_rate']}%")
                if metrics['avg_data_age_seconds']:
                    logger.info(f"    Avg Data Age: {metrics['avg_data_age_seconds']}s")
                if metrics['avg_drift_seconds']:
                    logger.info(f"    Avg Drift: {metrics['avg_drift_seconds']}s")
        
        logger.info("=" * 70)
    
    def reset(self, symbol: Optional[str] = None):
        """
        Reset metrics for a symbol or all symbols.
        
        Args:
            symbol: Symbol name (if None, resets all)
        """
        if symbol:
            self._refresh_times[symbol].clear()
            self._refresh_latencies[symbol].clear()
            self._refresh_success[symbol].clear()
            self._data_ages[symbol].clear()
            self._data_age_drifts[symbol].clear()
            self._snapshot_times[symbol].clear()
            self._refresh_diagnostics[symbol].clear()
        else:
            self._refresh_times.clear()
            self._refresh_latencies.clear()
            self._refresh_success.clear()
            self._data_ages.clear()
            self._data_age_drifts.clear()
            self._snapshot_times.clear()
            self._refresh_diagnostics.clear()
            self._cpu_usage.clear()
            self._memory_usage.clear()

