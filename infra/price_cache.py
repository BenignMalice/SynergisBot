"""
Price Cache - In-Memory Tick Storage
Stores real-time price data from Binance for indicator computation.

Features:
- Rolling window (keeps last N ticks)
- Thread-safe access
- Fast retrieval for V8 indicators
- Optional Redis backup (Phase 2)

Usage:
    cache = PriceCache(max_ticks=1000)
    cache.update("BTCUSDT", tick_data)
    latest = cache.get_latest("BTCUSDT")
    history = cache.get_history("BTCUSDT", count=200)
"""

import time
import logging
from collections import deque
from typing import Dict, List, Optional
from threading import Lock
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

logger = logging.getLogger(__name__)


class PriceCache:
    """
    In-memory cache for streaming tick data.
    Stores last N ticks per symbol for indicator computation.
    
    Thread-safe for concurrent access from multiple streams.
    """
    
    def __init__(self, max_ticks: int = 1000):
        """
        Args:
            max_ticks: Maximum number of ticks to store per symbol
        """
        self.cache: Dict[str, deque] = {}
        self.max_ticks = max_ticks
        self.locks: Dict[str, Lock] = {}
        self.stats: Dict[str, dict] = {}
        
        logger.info(f"📦 PriceCache initialized (max_ticks={max_ticks})")
        
    def update(self, symbol: str, tick: dict):
        """
        Update cache with new tick data.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            tick: Tick data dictionary with keys:
                  {price, open, high, low, close, volume, timestamp, ...}
        """
        symbol = symbol.upper()
        
        # Initialize if new symbol
        if symbol not in self.cache:
            self.cache[symbol] = deque(maxlen=self.max_ticks)
            self.locks[symbol] = Lock()
            self.stats[symbol] = {
                "first_tick": time.time(),
                "last_tick": time.time(),
                "total_ticks": 0
            }
            logger.info(f"📊 Added new symbol to cache: {symbol}")
            
        # Thread-safe update
        with self.locks[symbol]:
            self.cache[symbol].append(tick)
            self.stats[symbol]["last_tick"] = time.time()
            self.stats[symbol]["total_ticks"] += 1
            
    def get_latest(self, symbol: str) -> Optional[dict]:
        """
        Get the most recent tick for a symbol.
        
        Returns:
            Latest tick dict or None if symbol not found
        """
        symbol = symbol.upper()
        
        if symbol not in self.cache or len(self.cache[symbol]) == 0:
            return None
            
        with self.locks[symbol]:
            return dict(self.cache[symbol][-1])
            
    def get_history(self, symbol: str, count: int = 200) -> List[dict]:
        """
        Get recent tick history for a symbol.
        
        Args:
            symbol: Trading symbol
            count: Number of recent ticks to retrieve
            
        Returns:
            List of tick dicts (oldest to newest)
        """
        symbol = symbol.upper()
        
        if symbol not in self.cache:
            return []
            
        with self.locks[symbol]:
            history = list(self.cache[symbol])
            return history[-count:] if len(history) > count else history
            
    def get_ohlcv_arrays(self, symbol: str, count: int = 200) -> Dict[str, List[float]]:
        """
        Get OHLCV data as separate arrays (for indicator computation).
        
        Returns:
            {
                "open": [o1, o2, ...],
                "high": [h1, h2, ...],
                "low": [l1, l2, ...],
                "close": [c1, c2, ...],
                "volume": [v1, v2, ...],
                "timestamp": [t1, t2, ...]
            }
        """
        history = self.get_history(symbol, count)
        
        if not history:
            return {
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "timestamp": []
            }
            
        return {
            "open": [t["open"] for t in history],
            "high": [t["high"] for t in history],
            "low": [t["low"] for t in history],
            "close": [t["close"] for t in history],
            "volume": [t["volume"] for t in history],
            "timestamp": [t["timestamp"] for t in history]
        }
        
    def get_tick_count(self, symbol: str) -> int:
        """
        Get number of ticks stored for a symbol.
        """
        symbol = symbol.upper()
        return len(self.cache.get(symbol, []))
        
    def get_age_seconds(self, symbol: str) -> Optional[float]:
        """
        Get age of latest tick in seconds.
        Returns None if symbol not found.
        """
        latest = self.get_latest(symbol)
        if not latest:
            return None
            
        return time.time() - latest.get("timestamp", time.time())
        
    def is_stale(self, symbol: str, max_age_seconds: int = 60) -> bool:
        """
        Check if data is stale (too old).
        
        Args:
            symbol: Trading symbol
            max_age_seconds: Maximum acceptable age in seconds
            
        Returns:
            True if stale or no data, False if fresh
        """
        age = self.get_age_seconds(symbol)
        if age is None:
            return True
        return age > max_age_seconds
        
    def get_stats(self, symbol: str) -> Optional[dict]:
        """
        Get cache statistics for a symbol.
        
        Returns:
            {
                "tick_count": int,
                "age_seconds": float,
                "is_stale": bool,
                "total_ticks": int,
                "uptime_seconds": float
            }
        """
        symbol = symbol.upper()
        
        if symbol not in self.stats:
            return None
            
        age = self.get_age_seconds(symbol)
        uptime = time.time() - self.stats[symbol]["first_tick"]
        
        return {
            "symbol": symbol,
            "tick_count": self.get_tick_count(symbol),
            "age_seconds": age,
            "is_stale": self.is_stale(symbol),
            "total_ticks": self.stats[symbol]["total_ticks"],
            "uptime_seconds": uptime,
            "ticks_per_second": self.stats[symbol]["total_ticks"] / uptime if uptime > 0 else 0
        }
        
    def get_all_symbols(self) -> List[str]:
        """
        Get list of all symbols in cache.
        """
        return list(self.cache.keys())
        
    def clear(self, symbol: str = None):
        """
        Clear cache for a symbol or all symbols.
        
        Args:
            symbol: Symbol to clear, or None to clear all
        """
        if symbol:
            symbol = symbol.upper()
            if symbol in self.cache:
                with self.locks[symbol]:
                    self.cache[symbol].clear()
                logger.info(f"🗑️ Cleared cache for {symbol}")
        else:
            for sym in list(self.cache.keys()):
                with self.locks[sym]:
                    self.cache[sym].clear()
            logger.info("🗑️ Cleared all cache")
            
    def print_summary(self):
        """
        Print cache summary for all symbols.
        """
        print("\n" + "="*60)
        print("📦 PRICE CACHE SUMMARY")
        print("="*60)
        
        for symbol in sorted(self.get_all_symbols()):
            stats = self.get_stats(symbol)
            if stats:
                status = "🟢" if not stats["is_stale"] else "🔴"
                print(f"{status} {symbol:12s} | "
                      f"Ticks: {stats['tick_count']:4d} | "
                      f"Age: {stats['age_seconds']:5.1f}s | "
                      f"Rate: {stats['ticks_per_second']:.2f}/s")
                      
        print("="*60 + "\n")


# Example usage
async def example_usage():
    """
    Example of how to use PriceCache with BinanceStream.
    """
    from infra.binance_stream import BinanceStream
    
    # Create cache
    cache = PriceCache(max_ticks=1000)
    
    # Callback to update cache
    async def on_tick(tick: dict):
        cache.update(tick['symbol'], tick)
        
        # Print status every 10 ticks
        if cache.get_tick_count(tick['symbol']) % 10 == 0:
            cache.print_summary()
            
    # Start streaming
    stream = BinanceStream(
        symbols=["btcusdt", "ethusdt"],
        callback=on_tick,
        interval="1m"
    )
    
    try:
        await stream.start_all()
    except KeyboardInterrupt:
        stream.stop()
        print("\n✅ Stream stopped")
        cache.print_summary()


if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing PriceCache with Binance Stream")
    print("Press Ctrl+C to stop\n")
    
    asyncio.run(example_usage())



