"""
MT5 Proxy Service
=================
Thread-safe proxy for MT5 API calls to prevent cross-thread access issues.
All MT5 calls are serialized through a single-thread executor.
"""

import asyncio
import threading
import logging
from typing import Dict, Any, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

from infra.mt5_service import MT5Service, Quote

logger = logging.getLogger(__name__)

@dataclass
class MT5Quote:
    """Thread-safe quote data"""
    symbol: str
    bid: float
    ask: float
    mid: float
    timestamp: datetime
    
    @property
    def age_seconds(self) -> float:
        """Age of quote in seconds"""
        return (datetime.utcnow() - self.timestamp).total_seconds()

class MT5QuoteCache:
    """Thread-safe cache for MT5 quotes"""
    
    def __init__(self, max_age_seconds: float = 5.0):
        self._cache: Dict[str, MT5Quote] = {}
        self._lock = threading.RLock()
        self.max_age_seconds = max_age_seconds
    
    def update_quote(self, symbol: str, bid: float, ask: float) -> None:
        """Update quote in cache"""
        with self._lock:
            mid = (bid + ask) / 2
            self._cache[symbol] = MT5Quote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                mid=mid,
                timestamp=datetime.utcnow()
            )
    
    def get_quote(self, symbol: str) -> Optional[MT5Quote]:
        """Get latest quote from cache"""
        with self._lock:
            quote = self._cache.get(symbol)
            if quote and quote.age_seconds <= self.max_age_seconds:
                return quote
            return None
    
    def get_all_quotes(self) -> Dict[str, MT5Quote]:
        """Get all valid quotes"""
        with self._lock:
            now = datetime.utcnow()
            valid_quotes = {}
            for symbol, quote in self._cache.items():
                if (now - quote.timestamp).total_seconds() <= self.max_age_seconds:
                    valid_quotes[symbol] = quote
            return valid_quotes
    
    def clear_expired(self) -> int:
        """Clear expired quotes and return count"""
        with self._lock:
            now = datetime.utcnow()
            expired = []
            for symbol, quote in self._cache.items():
                if (now - quote.timestamp).total_seconds() > self.max_age_seconds:
                    expired.append(symbol)
            
            for symbol in expired:
                del self._cache[symbol]
            
            return len(expired)

class MT5ProxyService:
    """
    Thread-safe proxy for MT5 API calls.
    
    Features:
    - Single-thread executor for all MT5 calls
    - Thread-safe quote cache
    - Periodic quote updates
    - Async interface for non-blocking calls
    """
    
    def __init__(self, mt5_service: MT5Service, update_interval: float = 0.5):
        self.mt5_service = mt5_service
        self.update_interval = update_interval
        self.quote_cache = MT5QuoteCache(max_age_seconds=5.0)
        
        # Single-thread executor for MT5 calls
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MT5Proxy")
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        
        # Track active symbols for periodic updates
        self._active_symbols: set = set()
        self._symbols_lock = threading.RLock()
        
        logger.info("MT5ProxyService initialized with single-thread executor")
    
    async def start(self) -> None:
        """Start the proxy service"""
        if self._running:
            logger.warning("MT5ProxyService already running")
            return
        
        self._running = True
        self._update_task = asyncio.create_task(self._periodic_update())
        logger.info("MT5ProxyService started with periodic updates")
    
    async def stop(self) -> None:
        """Stop the proxy service"""
        if not self._running:
            return
        
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        self._executor.shutdown(wait=True)
        logger.info("MT5ProxyService stopped")
    
    def register_symbol(self, symbol: str) -> None:
        """Register symbol for periodic updates"""
        with self._symbols_lock:
            self._active_symbols.add(symbol)
            logger.debug(f"Registered symbol for updates: {symbol}")
    
    def unregister_symbol(self, symbol: str) -> None:
        """Unregister symbol from periodic updates"""
        with self._symbols_lock:
            self._active_symbols.discard(symbol)
            logger.debug(f"Unregistered symbol: {symbol}")
    
    async def _periodic_update(self) -> None:
        """Periodic task to update quote cache"""
        while self._running:
            try:
                await asyncio.sleep(self.update_interval)
                
                if not self._running:
                    break
                
                # Get active symbols
                with self._symbols_lock:
                    symbols = list(self._active_symbols)
                
                if not symbols:
                    continue
                
                # Update quotes for active symbols
                for symbol in symbols:
                    try:
                        quote = await self.get_quote_async(symbol)
                        if quote:
                            self.quote_cache.update_quote(symbol, quote.bid, quote.ask)
                    except Exception as e:
                        logger.debug(f"Failed to update quote for {symbol}: {e}")
                
                # Clean expired quotes
                expired_count = self.quote_cache.clear_expired()
                if expired_count > 0:
                    logger.debug(f"Cleared {expired_count} expired quotes")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def get_quote_async(self, symbol: str) -> Optional[Quote]:
        """Get quote asynchronously through executor"""
        if not self._running:
            return None
        
        loop = asyncio.get_event_loop()
        try:
            quote = await loop.run_in_executor(
                self._executor,
                self._get_quote_sync,
                symbol
            )
            return quote
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None
    
    def _get_quote_sync(self, symbol: str) -> Optional[Quote]:
        """Synchronous MT5 quote call (runs in executor thread)"""
        try:
            return self.mt5_service.get_quote(symbol)
        except Exception as e:
            logger.error(f"MT5 get_quote failed for {symbol}: {e}")
            return None
    
    def get_quote_from_cache(self, symbol: str) -> Optional[MT5Quote]:
        """Get quote from cache (thread-safe, no MT5 call)"""
        return self.quote_cache.get_quote(symbol)
    
    async def get_account_info_async(self) -> Optional[Tuple[float, float]]:
        """Get account balance and equity asynchronously"""
        if not self._running:
            return None
        
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._get_account_info_sync
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return None
    
    def _get_account_info_sync(self) -> Optional[Tuple[float, float]]:
        """Synchronous MT5 account info call"""
        try:
            return self.mt5_service.account_bal_eq()
        except Exception as e:
            logger.error(f"MT5 account_bal_eq failed: {e}")
            return None
    
    async def get_positions_async(self) -> List[Dict[str, Any]]:
        """Get positions asynchronously"""
        if not self._running:
            return []
        
        loop = asyncio.get_event_loop()
        try:
            positions = await loop.run_in_executor(
                self._executor,
                self._get_positions_sync
            )
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def _get_positions_sync(self) -> List[Dict[str, Any]]:
        """Synchronous MT5 positions call"""
        try:
            return self.mt5_service.list_positions()
        except Exception as e:
            logger.error(f"MT5 list_positions failed: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        quotes = self.quote_cache.get_all_quotes()
        return {
            "total_quotes": len(quotes),
            "active_symbols": len(self._active_symbols),
            "cache_age_seconds": max([q.age_seconds for q in quotes.values()], default=0),
            "symbols": list(quotes.keys())
        }

# Global proxy instance
_proxy_instance: Optional[MT5ProxyService] = None

def get_mt5_proxy() -> Optional[MT5ProxyService]:
    """Get global MT5 proxy instance"""
    return _proxy_instance

def initialize_mt5_proxy(mt5_service: MT5Service, update_interval: float = 0.5) -> MT5ProxyService:
    """Initialize global MT5 proxy instance"""
    global _proxy_instance
    _proxy_instance = MT5ProxyService(mt5_service, update_interval)
    return _proxy_instance

async def start_mt5_proxy() -> None:
    """Start global MT5 proxy"""
    if _proxy_instance:
        await _proxy_instance.start()

async def stop_mt5_proxy() -> None:
    """Stop global MT5 proxy"""
    if _proxy_instance:
        await _proxy_instance.stop()
