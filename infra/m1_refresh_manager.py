# =====================================
# infra/m1_refresh_manager.py
# =====================================
"""
M1 Refresh Manager Module

Manages periodic refresh of M1 data for active symbols.
Handles background refresh loops, weekend detection, and batch operations.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class M1RefreshManager:
    """
    Manages periodic refresh of M1 data for active symbols.
    
    Features:
    - Background refresh loop with configurable intervals
    - Weekend detection and handling
    - Batch refresh with asyncio for parallel operations
    - Refresh diagnostics and monitoring
    - Graceful error handling
    """
    
    def __init__(
        self,
        fetcher,
        refresh_interval_active: int = 30,
        refresh_interval_inactive: int = 300,
        monitoring: Optional[Any] = None
    ):
        """
        Initialize M1 Refresh Manager.
        
        Args:
            fetcher: M1DataFetcher instance
            refresh_interval_active: Refresh interval for active symbols (seconds, default: 30)
            refresh_interval_inactive: Refresh interval for inactive symbols (seconds, default: 300)
            monitoring: Optional M1Monitoring instance for metrics tracking
        """
        self.fetcher = fetcher
        self.refresh_interval_active = refresh_interval_active
        self.refresh_interval_inactive = refresh_interval_inactive
        self.monitoring = monitoring
        
        # Track refresh state
        self._refresh_times: Dict[str, datetime] = {}  # symbol -> last refresh time
        self._refresh_success: Dict[str, bool] = {}  # symbol -> last refresh success
        self._refresh_latencies: Dict[str, List[float]] = defaultdict(list)  # symbol -> list of latencies (ms)
        self._refresh_errors: Dict[str, int] = defaultdict(int)  # symbol -> error count
        
        # Background refresh control
        self._refresh_thread: Optional[threading.Thread] = None
        self._refresh_running = False
        self._refresh_lock = threading.Lock()
        self._active_symbols: set = set()
        
        # Refresh statistics
        self._total_refreshes = 0
        self._successful_refreshes = 0
        self._failed_refreshes = 0
        
        logger.info(
            f"M1RefreshManager initialized "
            f"(active: {refresh_interval_active}s, inactive: {refresh_interval_inactive}s)"
        )
    
    def _is_weekend(self) -> bool:
        """
        Check if current time is weekend (Friday 21:00 UTC to Sunday 22:00 UTC).
        
        Returns:
            True if weekend, False otherwise
        """
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Monday, 4=Friday, 6=Sunday
        hour = now.hour
        
        # Friday after 21:00 UTC
        if weekday == 4 and hour >= 21:
            return True
        
        # Saturday (all day)
        if weekday == 5:
            return True
        
        # Sunday before 22:00 UTC
        if weekday == 6 and hour < 22:
            return True
        
        return False
    
    def _should_refresh_on_weekend(self, symbol: str) -> bool:
        """
        Check if symbol should be refreshed on weekends.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if should refresh on weekend, False otherwise
        """
        # BTCUSD trades 24/7
        if 'BTC' in symbol.upper():
            return True
        
        # XAUUSD and Forex pairs: skip weekend (limited trading)
        return False
    
    def start_background_refresh(self, symbols: List[str]):
        """
        Start background refresh loop for specified symbols.
        
        Args:
            symbols: List of symbols to refresh periodically
        """
        with self._refresh_lock:
            if self._refresh_running:
                logger.warning("Background refresh already running")
                return
            
            # Normalize symbols
            normalized_symbols = [self._normalize_symbol(s) for s in symbols]
            self._active_symbols = set(normalized_symbols)
            self._refresh_running = True
            
            # Start background thread
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop,
                daemon=True,
                name="M1RefreshManager"
            )
            self._refresh_thread.start()
            
            logger.info(f"Background refresh started for {len(symbols)} symbols: {symbols}")
    
    def stop_refresh(self):
        """Stop background refresh loop."""
        with self._refresh_lock:
            if not self._refresh_running:
                return
            
            self._refresh_running = False
            
            # Wait for thread to finish (with timeout)
            if self._refresh_thread and self._refresh_thread.is_alive():
                self._refresh_thread.join(timeout=5.0)
            
            logger.info("Background refresh stopped")
    
    def _refresh_loop(self):
        """Background refresh loop (runs in separate thread)."""
        logger.info("M1 refresh loop started")
        
        try:
            while self._refresh_running:
                try:
                    # Validate fetcher exists
                    if not self.fetcher:
                        logger.warning("M1 fetcher is None - cannot refresh")
                        time.sleep(10)  # Wait before retrying
                        continue
                    
                    # Check if weekend
                    try:
                        is_weekend = self._is_weekend()
                    except Exception as e:
                        logger.warning(f"Error checking weekend status: {e}")
                        is_weekend = False  # Default to not weekend
                    
                    # Refresh each active symbol
                    try:
                        symbols_to_refresh = list(self._active_symbols)
                    except Exception as e:
                        logger.error(f"Error getting active symbols: {e}", exc_info=True)
                        symbols_to_refresh = []
                    
                    for symbol in symbols_to_refresh:
                        if not self._refresh_running:
                            break
                        
                        try:
                            # Get base symbol (without 'c') for weekend check
                            base_symbol = symbol.rstrip('c') if symbol else ''
                            
                            if not base_symbol:
                                continue
                            
                            # Check weekend handling
                            if is_weekend and not self._should_refresh_on_weekend(base_symbol):
                                logger.debug(f"Skipping {symbol} refresh (weekend)")
                                continue
                            
                            # Check if refresh is needed
                            last_refresh = self._refresh_times.get(symbol)
                            if last_refresh:
                                # Determine refresh interval
                                if base_symbol in ['XAUUSD', 'BTCUSD']:
                                    interval = self.refresh_interval_active
                                else:
                                    interval = self.refresh_interval_inactive
                                
                                # Check if enough time has passed
                                try:
                                    time_since_refresh = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                                    if time_since_refresh < interval:
                                        continue  # Skip, not time yet
                                except Exception as e:
                                    logger.warning(f"Error calculating time since refresh for {symbol}: {e}")
                                    # Continue with refresh anyway
                            
                            # Perform refresh (use base symbol, fetcher will normalize)
                            self.refresh_symbol(base_symbol, force=False)
                        except Exception as e:
                            logger.error(f"Error refreshing symbol {symbol}: {e}", exc_info=True)
                            # Continue with next symbol
                    
                    # Sleep before next iteration
                    time.sleep(min(self.refresh_interval_active, 10))  # Check at least every 10 seconds
                    
                except Exception as e:
                    logger.error(f"Error in refresh loop iteration: {e}", exc_info=True)
                    time.sleep(5)  # Wait before retrying
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in M1 refresh loop: {fatal_error}", exc_info=True)
            self._refresh_running = False
        finally:
            logger.info("M1 refresh loop stopped")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol name (add 'c' suffix if needed, matching M1DataFetcher).
        
        Args:
            symbol: Symbol name
            
        Returns:
            Normalized symbol (with 'c' suffix)
        """
        if not symbol.endswith('c'):
            return f"{symbol}c"
        return symbol
    
    def refresh_symbol(self, symbol: str, force: bool = False) -> bool:
        """
        Refresh M1 data for a symbol.
        
        Args:
            symbol: Symbol name
            force: Force refresh even if recently refreshed (for error recovery)
            
        Returns:
            True if refresh successful, False otherwise
        """
        start_time = time.time()
        normalized_symbol = self._normalize_symbol(symbol)
        expected_age = self.refresh_interval_active  # Expected data age in seconds
        
        try:
            # Check if refresh is needed (unless forced)
            if not force:
                last_refresh = self._refresh_times.get(normalized_symbol)
                if last_refresh:
                    # Determine refresh interval
                    base_symbol = symbol.rstrip('c').upper()
                    if base_symbol in ['XAUUSD', 'BTCUSD']:
                        interval = self.refresh_interval_active
                    else:
                        interval = self.refresh_interval_inactive
                    
                    time_since_refresh = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                    if time_since_refresh < interval:
                        return True  # Already fresh enough
            
            # Perform refresh
            if not self.fetcher:
                logger.warning(f"M1 fetcher is None - cannot refresh {symbol}")
                return False
            
            try:
                success = self.fetcher.refresh_symbol(symbol)
            except Exception as e:
                logger.error(f"Error calling fetcher.refresh_symbol for {symbol}: {e}", exc_info=True)
                success = False
            
            # Update tracking (use normalized symbol)
            latency_ms = (time.time() - start_time) * 1000
            self._refresh_times[normalized_symbol] = datetime.now(timezone.utc)
            self._refresh_success[normalized_symbol] = success
            self._refresh_latencies[normalized_symbol].append(latency_ms)
            
            # Keep only last 100 latencies per symbol
            if len(self._refresh_latencies[normalized_symbol]) > 100:
                self._refresh_latencies[normalized_symbol] = self._refresh_latencies[normalized_symbol][-100:]
            
            # Calculate data age and drift
            data_age_seconds = None
            expected_age_seconds = None
            if success:
                # Get latest candle timestamp if available
                candles = self.fetcher.fetch_m1_data(normalized_symbol, count=1, use_cache=True)
                if candles and len(candles) > 0:
                    latest_candle = candles[-1] if isinstance(candles, list) else list(candles)[-1]
                    candle_time = latest_candle.get('timestamp') or latest_candle.get('time')
                    if candle_time:
                        if isinstance(candle_time, str):
                            candle_time = datetime.fromisoformat(candle_time.replace('Z', '+00:00'))
                        if isinstance(candle_time, datetime):
                            data_age_seconds = (datetime.now(timezone.utc) - candle_time.replace(tzinfo=timezone.utc)).total_seconds()
                
                # Expected age based on refresh interval
                base_symbol = symbol.rstrip('c').upper()
                if base_symbol in ['XAUUSD', 'BTCUSD']:
                    expected_age_seconds = self.refresh_interval_active
                else:
                    expected_age_seconds = self.refresh_interval_inactive
            
            # Record to monitoring system if available
            if self.monitoring:
                self.monitoring.record_refresh(
                    symbol=normalized_symbol,
                    success=success,
                    latency_ms=latency_ms,
                    data_age_seconds=data_age_seconds,
                    expected_age_seconds=expected_age_seconds
                )
            
            # Update statistics
            self._total_refreshes += 1
            if success:
                self._successful_refreshes += 1
                self._refresh_errors[normalized_symbol] = 0  # Reset error count on success
                logger.debug(f"Refreshed M1 data for {normalized_symbol} ({latency_ms:.1f}ms)")
            else:
                self._failed_refreshes += 1
                self._refresh_errors[normalized_symbol] += 1
                logger.warning(f"Failed to refresh M1 data for {normalized_symbol} (error count: {self._refresh_errors[normalized_symbol]})")
            
            return success
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._failed_refreshes += 1
            self._refresh_errors[normalized_symbol] += 1
            
            # Record failure to monitoring system if available
            if self.monitoring:
                self.monitoring.record_refresh(
                    symbol=normalized_symbol,
                    success=False,
                    latency_ms=latency_ms,
                    data_age_seconds=None,
                    expected_age_seconds=None
                )
            
            logger.error(f"Error refreshing {normalized_symbol}: {e}", exc_info=True)
            return False
    
    async def refresh_symbol_async(self, symbol: str) -> bool:
        """
        Async version of refresh_symbol for concurrent operations.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if refresh successful, False otherwise
        """
        # Run sync refresh in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.refresh_symbol, symbol, False)
    
    async def refresh_symbols_batch(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Refresh multiple symbols in parallel using asyncio.gather().
        
        Args:
            symbols: List of symbols to refresh
            
        Returns:
            Dict mapping normalized symbol -> success status
        """
        # Create refresh tasks
        tasks = [self.refresh_symbol_async(symbol) for symbol in symbols]
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict (use normalized symbols)
        result_dict = {}
        for symbol, result in zip(symbols, results):
            normalized_symbol = self._normalize_symbol(symbol)
            if isinstance(result, Exception):
                logger.error(f"Error refreshing {normalized_symbol}: {result}")
                result_dict[normalized_symbol] = False
            else:
                result_dict[normalized_symbol] = result
        
        return result_dict
    
    def check_and_refresh_stale(self, symbol: str, max_age_seconds: int = 180) -> bool:
        """
        Check if data is stale and refresh if needed.
        
        Args:
            symbol: Symbol name
            max_age_seconds: Maximum age in seconds before considered stale (default: 180 = 3 minutes)
            
        Returns:
            True if data was refreshed or already fresh, False if refresh failed
        """
        # Check if data is stale
        if self.fetcher.is_data_stale(symbol, max_age_seconds=max_age_seconds):
            logger.debug(f"Data stale for {symbol}, refreshing...")
            return self.refresh_symbol(symbol, force=True)
        
        return True  # Data is fresh
    
    def get_refresh_status(self) -> Dict[str, Any]:
        """
        Get refresh status for all symbols.
        
        Returns:
            Dict with refresh status information
        """
        status = {
            'running': self._refresh_running,
            'active_symbols': list(self._active_symbols),
            'symbols': {}
        }
        
        for symbol in self._active_symbols:
            last_refresh = self._refresh_times.get(symbol)
            last_success = self._refresh_success.get(symbol, False)
            error_count = self._refresh_errors.get(symbol, 0)
            
            # Calculate data age
            data_age = None
            if last_refresh:
                data_age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
            
            status['symbols'][symbol] = {
                'last_refresh': last_refresh.isoformat() if last_refresh else None,
                'data_age_seconds': data_age,
                'last_success': last_success,
                'error_count': error_count,
                'avg_latency_ms': self._get_avg_latency(symbol)
            }
        
        return status
    
    def get_refresh_diagnostics(self) -> Dict[str, Any]:
        """
        Get refresh diagnostics for optimization reporting.
        
        Returns:
            Dict with diagnostics:
            - avg_latency_ms: Average refresh latency across all symbols
            - data_age_drift_seconds: Average data age drift
            - refresh_success_rate: Percentage of successful refreshes
        """
        # Calculate average latency
        all_latencies = []
        for symbol_latencies in self._refresh_latencies.values():
            all_latencies.extend(symbol_latencies)
        
        avg_latency_ms = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
        
        # Calculate data age drift (how old is the oldest data)
        max_age = 0.0
        for symbol in self._active_symbols:
            last_refresh = self._refresh_times.get(symbol)
            if last_refresh:
                age = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                max_age = max(max_age, age)
        
        # Calculate success rate
        success_rate = 0.0
        if self._total_refreshes > 0:
            success_rate = (self._successful_refreshes / self._total_refreshes) * 100
        
        return {
            'avg_latency_ms': round(avg_latency_ms, 2),
            'data_age_drift_seconds': round(max_age, 1),
            'refresh_success_rate': round(success_rate, 1),
            'total_refreshes': self._total_refreshes,
            'successful_refreshes': self._successful_refreshes,
            'failed_refreshes': self._failed_refreshes
        }
    
    def get_last_refresh_time(self, symbol: str) -> Optional[datetime]:
        """
        Get last refresh timestamp for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Last refresh datetime or None if never refreshed
        """
        normalized_symbol = self._normalize_symbol(symbol)
        return self._refresh_times.get(normalized_symbol)
    
    def get_all_refresh_times(self) -> Dict[str, datetime]:
        """
        Get last refresh time for all symbols.
        
        Returns:
            Dict mapping symbol -> last refresh datetime
        """
        return self._refresh_times.copy()
    
    def _get_avg_latency(self, symbol: str) -> Optional[float]:
        """Get average latency for a symbol."""
        latencies = self._refresh_latencies.get(symbol, [])
        if not latencies:
            return None
        return round(sum(latencies) / len(latencies), 2)
    
    def force_refresh(self, symbol: str) -> bool:
        """
        Force refresh on error/stale data (alias for refresh_symbol with force=True).
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if refresh successful, False otherwise
        """
        return self.refresh_symbol(symbol, force=True)

