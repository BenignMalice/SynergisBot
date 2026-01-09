# =====================================
# infra/m1_data_fetcher.py
# =====================================
"""
M1 Data Fetcher Module

Fetches M1 (1-minute) candlestick data from data source (MT5, Binance, etc.)
Maintains rolling window buffer in RAM for efficient access.
Handles symbol normalization and error recovery.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class M1DataFetcher:
    """
    Fetches and caches M1 candlestick data from a data source.
    
    Supports pluggable data sources (MT5Service, BinanceService, etc.)
    Maintains rolling window buffer in RAM (100-200 candles per symbol).
    """
    
    def __init__(self, data_source, max_candles: int = 200, cache_ttl: int = 300):
        """
        Initialize M1 Data Fetcher.
        
        Args:
            data_source: Data source object (MT5Service, BinanceService, etc.)
                        Must have get_bars(symbol, timeframe, count) method
            max_candles: Maximum candles to store per symbol (default: 200)
            cache_ttl: Cache TTL in seconds (default: 300 = 5 minutes)
        """
        self.data_source = data_source
        self.max_candles = max_candles
        self.cache_ttl = cache_ttl
        
        # In-memory storage: symbol -> deque of candles
        self._data_cache: Dict[str, deque] = {}
        
        # Track last fetch time per symbol
        self._last_fetch_time: Dict[str, float] = {}
        
        # Track last successful fetch time per symbol
        self._last_success_time: Dict[str, float] = {}
        
        logger.info(f"M1DataFetcher initialized (max_candles={max_candles}, cache_ttl={cache_ttl}s)")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol name (add 'c' suffix if needed).
        
        Args:
            symbol: Symbol name (e.g., 'XAUUSD' or 'XAUUSDc' or 'XAUUSDC')
            
        Returns:
            Normalized symbol (e.g., 'XAUUSDc')
        """
        # Case-insensitive check: remove any existing 'c' or 'C' suffix, then add lowercase 'c'
        symbol_upper = symbol.upper()
        if symbol_upper.endswith('C'):
            # Already has 'c' suffix (case-insensitive), just ensure it's lowercase
            return symbol_upper[:-1] + 'c'
        else:
            # No 'c' suffix, add it
            return symbol_upper + 'c'
    
    def _convert_to_dict(self, candle_data: Any, symbol: str) -> Dict[str, Any]:
        """
        Convert candle data from data source format to standard dict format.
        
        Handles both DataFrame (from MT5Service) and dict formats.
        
        Args:
            candle_data: Candle data from data source
            symbol: Symbol name
            
        Returns:
            Standardized candle dict
        """
        if isinstance(candle_data, dict):
            # Already a dict, ensure all fields present
            return {
                "timestamp": candle_data.get("timestamp") or candle_data.get("time"),
                "open": float(candle_data.get("open", 0)),
                "high": float(candle_data.get("high", 0)),
                "low": float(candle_data.get("low", 0)),
                "close": float(candle_data.get("close", 0)),
                "volume": int(candle_data.get("volume", 0) or candle_data.get("tick_volume", 0)),
                "symbol": self._normalize_symbol(symbol)
            }
        
        # Handle pandas DataFrame (from MT5Service.get_bars)
        try:
            import pandas as pd
            if isinstance(candle_data, pd.DataFrame):
                # Convert DataFrame row to dict
                return {
                    "timestamp": candle_data.get("time") if hasattr(candle_data, "get") else candle_data.get("time"),
                    "open": float(candle_data.get("open", 0)),
                    "high": float(candle_data.get("high", 0)),
                    "low": float(candle_data.get("low", 0)),
                    "close": float(candle_data.get("close", 0)),
                    "volume": int(candle_data.get("volume", 0) or candle_data.get("tick_volume", 0)),
                    "symbol": self._normalize_symbol(symbol)
                }
        except ImportError:
            pass
        
        # Handle numpy structured array (from MT5)
        try:
            import numpy as np
            if isinstance(candle_data, np.ndarray) or hasattr(candle_data, '__getitem__'):
                # Access fields directly
                return {
                    "timestamp": datetime.fromtimestamp(candle_data['time'], tz=timezone.utc) if 'time' in candle_data.dtype.names else datetime.now(timezone.utc),
                    "open": float(candle_data['open']),
                    "high": float(candle_data['high']),
                    "low": float(candle_data['low']),
                    "close": float(candle_data['close']),
                    "volume": int(candle_data.get('tick_volume', candle_data.get('volume', 0))),
                    "symbol": self._normalize_symbol(symbol)
                }
        except (ImportError, (TypeError, KeyError)):
            pass
        
        # Fallback: try to access as dict-like object
        return {
            "timestamp": getattr(candle_data, 'time', getattr(candle_data, 'timestamp', datetime.now(timezone.utc))),
            "open": float(getattr(candle_data, 'open', 0)),
            "high": float(getattr(candle_data, 'high', 0)),
            "low": float(getattr(candle_data, 'low', 0)),
            "close": float(getattr(candle_data, 'close', 0)),
            "volume": int(getattr(candle_data, 'volume', getattr(candle_data, 'tick_volume', 0))),
            "symbol": self._normalize_symbol(symbol)
        }
    
    def _fetch_from_source(self, symbol: str, count: int) -> List[Dict[str, Any]]:
        """
        Fetch M1 data from data source.
        
        Args:
            symbol: Symbol name
            count: Number of candles to fetch
            
        Returns:
            List of candle dicts (oldest first)
        """
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            # Try to use get_bars method (MT5Service, etc.)
            if hasattr(self.data_source, 'get_bars'):
                bars = self.data_source.get_bars(normalized_symbol, 'M1', count)
                
                if bars is None:
                    logger.warning(f"No M1 bars returned for {normalized_symbol}")
                    return []
                
                # Convert to list of dicts
                candles = []
                
                # Handle pandas DataFrame
                try:
                    import pandas as pd
                    if isinstance(bars, pd.DataFrame):
                        for _, row in bars.iterrows():
                            candle = {
                                "timestamp": row.get("time") if pd.notna(row.get("time")) else datetime.now(timezone.utc),
                                "open": float(row.get("open", 0)),
                                "high": float(row.get("high", 0)),
                                "low": float(row.get("low", 0)),
                                "close": float(row.get("close", 0)),
                                "volume": int(row.get("volume", 0) or row.get("tick_volume", 0)),
                                "symbol": normalized_symbol
                            }
                            candles.append(candle)
                        return candles
                except ImportError:
                    pass
                
                # Handle list of dicts
                if isinstance(bars, list):
                    for candle_data in bars:
                        candle = self._convert_to_dict(candle_data, normalized_symbol)
                        candles.append(candle)
                    return candles
                
                # Handle numpy array
                try:
                    import numpy as np
                    if isinstance(bars, np.ndarray):
                        for candle_data in bars:
                            candle = self._convert_to_dict(candle_data, normalized_symbol)
                            candles.append(candle)
                        return candles
                except ImportError:
                    pass
                
                logger.warning(f"Unsupported data format from get_bars for {normalized_symbol}")
                return []
            
            # Fallback: try direct MT5 access if data_source is MT5Service
            if hasattr(self.data_source, 'ensure_symbol'):
                try:
                    import MetaTrader5 as mt5
                    self.data_source.ensure_symbol(normalized_symbol)
                    rates = mt5.copy_rates_from_pos(normalized_symbol, mt5.TIMEFRAME_M1, 0, count)
                    
                    if rates is None or len(rates) == 0:
                        logger.warning(f"No M1 rates from MT5 for {normalized_symbol}")
                        return []
                    
                    candles = []
                    for rate in rates:
                        candle = {
                            "timestamp": datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                            "open": float(rate['open']),
                            "high": float(rate['high']),
                            "low": float(rate['low']),
                            "close": float(rate['close']),
                            "volume": int(rate.get('tick_volume', rate.get('real_volume', 0))),
                            "symbol": normalized_symbol
                        }
                        candles.append(candle)
                    return candles
                except Exception as e:
                    logger.error(f"Error fetching M1 from MT5 for {normalized_symbol}: {e}")
                    return []
            
            logger.error(f"Data source does not support M1 fetching: {type(self.data_source)}")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching M1 data for {normalized_symbol}: {e}")
            return []
    
    def fetch_m1_data(self, symbol: str, count: int = 200, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch M1 candlestick data for a symbol.
        
        Args:
            symbol: Symbol name (e.g., 'XAUUSD')
            count: Number of candles to fetch (default: 200, max: max_candles)
            use_cache: Whether to use cached data if fresh (default: True)
            
        Returns:
            List of candle dicts (oldest first), empty list on error
        """
        normalized_symbol = self._normalize_symbol(symbol)
        count = min(count, self.max_candles)
        
        # Check cache if enabled
        if use_cache and normalized_symbol in self._data_cache:
            cache = self._data_cache[normalized_symbol]
            last_fetch = self._last_fetch_time.get(normalized_symbol, 0)
            
            # Check if cache is fresh
            if time.time() - last_fetch < self.cache_ttl and len(cache) > 0:
                # Return cached data (convert deque to list)
                return list(cache)
        
        # Fetch fresh data
        self._last_fetch_time[normalized_symbol] = time.time()
        candles = self._fetch_from_source(normalized_symbol, count)
        
        if candles:
            # Update cache with rolling window
            if normalized_symbol not in self._data_cache:
                self._data_cache[normalized_symbol] = deque(maxlen=self.max_candles)
            
            # Clear and repopulate cache
            self._data_cache[normalized_symbol].clear()
            for candle in candles:
                self._data_cache[normalized_symbol].append(candle)
            
            self._last_success_time[normalized_symbol] = time.time()
            logger.debug(f"Fetched {len(candles)} M1 candles for {normalized_symbol}")
        else:
            logger.warning(f"No M1 candles fetched for {normalized_symbol}")
        
        return candles
    
    async def fetch_m1_data_async(self, symbol: str, count: int = 200, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Async variant of fetch_m1_data for concurrent batch updates.
        
        Args:
            symbol: Symbol name
            count: Number of candles to fetch
            use_cache: Whether to use cached data if fresh
            
        Returns:
            List of candle dicts (oldest first)
        """
        # For now, just call sync version (can be optimized later)
        return self.fetch_m1_data(symbol, count, use_cache)
    
    def get_latest_m1(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent M1 candle for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Latest candle dict or None if not available
        """
        normalized_symbol = self._normalize_symbol(symbol)
        
        if normalized_symbol in self._data_cache:
            cache = self._data_cache[normalized_symbol]
            if len(cache) > 0:
                return cache[-1]  # Last item in deque
        
        # Try to fetch if not in cache
        candles = self.fetch_m1_data(symbol, count=1, use_cache=False)
        if candles:
            return candles[-1]
        
        return None
    
    def refresh_symbol(self, symbol: str) -> bool:
        """
        Refresh M1 data for a symbol (force fresh fetch).
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if refresh successful, False otherwise
        """
        normalized_symbol = self._normalize_symbol(symbol)
        
        # Clear cache for this symbol
        if normalized_symbol in self._data_cache:
            self._data_cache[normalized_symbol].clear()
        
        # Fetch fresh data
        candles = self.fetch_m1_data(symbol, count=self.max_candles, use_cache=False)
        
        return len(candles) > 0
    
    def force_refresh(self, symbol: str) -> bool:
        """
        Force refresh on error/stale data (same as refresh_symbol).
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if refresh successful, False otherwise
        """
        return self.refresh_symbol(symbol)
    
    def get_data_age(self, symbol: str) -> Optional[float]:
        """
        Get age of cached data in seconds.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Age in seconds, or None if no data available
        """
        normalized_symbol = self._normalize_symbol(symbol)
        
        if normalized_symbol not in self._last_success_time:
            return None
        
        return time.time() - self._last_success_time[normalized_symbol]
    
    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols with cached data.
        
        Returns:
            List of symbol names
        """
        return list(self._data_cache.keys())
    
    def is_data_stale(self, symbol: str, max_age_seconds: int = 180) -> bool:
        """
        Check if cached data is stale.
        
        Args:
            symbol: Symbol name
            max_age_seconds: Maximum age in seconds before considered stale (default: 180 = 3 minutes)
            
        Returns:
            True if data is stale or not available, False if fresh
        """
        age = self.get_data_age(symbol)
        if age is None:
            return True
        
        return age > max_age_seconds
    
    def clear_cache(self, symbol: str = None):
        """
        Clear cache for a symbol or all symbols.
        
        Args:
            symbol: Symbol name to clear, or None to clear all
        """
        if symbol is None:
            self._data_cache.clear()
            self._last_fetch_time.clear()
            self._last_success_time.clear()
            logger.info("Cleared all M1 data cache")
        else:
            normalized_symbol = self._normalize_symbol(symbol)
            if normalized_symbol in self._data_cache:
                del self._data_cache[normalized_symbol]
            if normalized_symbol in self._last_fetch_time:
                del self._last_fetch_time[normalized_symbol]
            if normalized_symbol in self._last_success_time:
                del self._last_success_time[normalized_symbol]
            logger.debug(f"Cleared M1 cache for {normalized_symbol}")

