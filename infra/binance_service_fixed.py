"""
Fixed Binance Service
=====================
Binance service with MT5 calls removed from tick callback to prevent cross-thread access.
Uses MT5 proxy service for thread-safe access to MT5 data.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from infra.binance_stream import BinanceStream
from infra.mt5_proxy_service import MT5ProxyService, get_mt5_proxy

logger = logging.getLogger(__name__)

class BinanceServiceFixed:
    """
    Fixed Binance service that doesn't call MT5 directly from tick callbacks.
    
    Changes from original:
    - No direct MT5 calls in _on_tick()
    - Uses MT5 proxy service for thread-safe access
    - Lightweight tick processing for better WebSocket stability
    - Periodic offset calibration on main thread
    """
    
    def __init__(self, interval: str = "1m"):
        self.interval = interval
        self.symbols: List[str] = []
        self.running = False
        self.stream: Optional[BinanceStream] = None
        
        # Cache for Binance prices (thread-safe)
        self.price_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = asyncio.Lock()
        
        # Sync manager for offset tracking (no MT5 calls here)
        self.sync_manager = None  # Will be set by main thread
        
        # Performance monitoring
        self.tick_count = 0
        self.last_tick_time = 0
        self.max_tick_duration = 0
        
        logger.info("BinanceServiceFixed initialized (MT5-decoupled)")
    
    def set_sync_manager(self, sync_manager):
        """Set sync manager for offset tracking"""
        self.sync_manager = sync_manager
        logger.info("Sync manager linked to BinanceServiceFixed")
    
    async def _on_tick(self, tick: dict):
        """
        Lightweight tick callback - NO MT5 CALLS.
        
        This callback now only:
        - Updates Binance price cache
        - Tracks performance metrics
        - Returns quickly to avoid WebSocket stalls
        """
        start_time = time.time()
        symbol = tick['symbol']
        
        try:
            # Update cache (thread-safe)
            async with self.cache_lock:
                self.price_cache[symbol] = {
                    'price': tick['price'],
                    'timestamp': datetime.utcnow(),
                    'volume': tick.get('volume', 0),
                    'bid': tick.get('bid', tick['price']),
                    'ask': tick.get('ask', tick['price'])
                }
            
            # Update sync manager if available (no MT5 calls)
            if self.sync_manager:
                try:
                    # Only update with Binance price - no MT5 call here
                    self.sync_manager.update_binance_price(symbol, tick['price'])
                except Exception as e:
                    logger.debug(f"Sync manager update failed for {symbol}: {e}")
            
            # Performance tracking
            self.tick_count += 1
            tick_duration = time.time() - start_time
            self.max_tick_duration = max(self.max_tick_duration, tick_duration)
            self.last_tick_time = start_time
            
            # Log slow ticks (should be < 1ms)
            if tick_duration > 0.001:  # 1ms
                logger.warning(f"Slow tick processing: {tick_duration*1000:.2f}ms for {symbol}")
                
        except Exception as e:
            logger.error(f"Error in tick callback for {symbol}: {e}")
    
    def get_latest_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest price from cache (thread-safe)"""
        return self.price_cache.get(symbol)
    
    def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached prices"""
        return self.price_cache.copy()
    
    async def start(self, symbols: List[str], background: bool = True):
        """
        Start Binance streaming for specified symbols.
        
        Args:
            symbols: List of symbols (Binance format: btcusdt, ethusdt)
            background: If True, run in background task
        """
        if self.running:
            logger.warning("BinanceServiceFixed already running")
            return
            
        self.symbols = [s.lower() for s in symbols]
        self.running = True
        
        # Create stream with fixed callback
        self.stream = BinanceStream(
            symbols=self.symbols,
            callback=self._on_tick,
            interval=self.interval
        )
        
        logger.info(f"Starting Binance streams (fixed): {', '.join(self.symbols)}")
        logger.info("  → No MT5 calls in tick callback")
        logger.info("  → Lightweight processing for stability")
        logger.info("  → Thread-safe price caching")
        
        if background:
            # Run in background task
            asyncio.create_task(self.stream.start_all())
            await asyncio.sleep(2)  # Give it time to connect
            logger.info("Binance streams running in background (fixed)")
        else:
            # Run in foreground (blocks)
            await self.stream.start_all()
    
    def stop(self):
        """Stop all Binance streams"""
        if not self.running:
            return
            
        self.running = False
        if self.stream:
            self.stream.stop()
        
        logger.info("BinanceServiceFixed stopped")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "tick_count": self.tick_count,
            "max_tick_duration": self.max_tick_duration,
            "last_tick_time": self.last_tick_time,
            "cached_symbols": list(self.price_cache.keys()),
            "running": self.running
        }
    
    def get_price_summary(self) -> Dict[str, Any]:
        """Get summary of cached prices"""
        summary = {}
        for symbol, data in self.price_cache.items():
            summary[symbol] = {
                "price": data['price'],
                "age_seconds": (datetime.utcnow() - data['timestamp']).total_seconds()
            }
        return summary

class PeriodicOffsetCalibrator:
    """
    Periodic offset calibration that runs on main thread.
    
    This replaces the MT5 calls that were in the Binance tick callback.
    Runs periodically to maintain price synchronization.
    """
    
    def __init__(self, binance_service: BinanceServiceFixed, mt5_proxy: MT5ProxyService, interval: float = 1.0):
        self.binance_service = binance_service
        self.mt5_proxy = mt5_proxy
        self.interval = interval
        self.running = False
        self.calibration_task: Optional[asyncio.Task] = None
        
        logger.info(f"PeriodicOffsetCalibrator initialized (interval: {interval}s)")
    
    async def start(self):
        """Start periodic calibration"""
        if self.running:
            return
        
        self.running = True
        self.calibration_task = asyncio.create_task(self._calibration_loop())
        logger.info("PeriodicOffsetCalibrator started")
    
    async def stop(self):
        """Stop periodic calibration"""
        if not self.running:
            return
        
        self.running = False
        if self.calibration_task:
            self.calibration_task.cancel()
            try:
                await self.calibration_task
            except asyncio.CancelledError:
                pass
        
        logger.info("PeriodicOffsetCalibrator stopped")
    
    async def _calibration_loop(self):
        """Main calibration loop"""
        while self.running:
            try:
                await asyncio.sleep(self.interval)
                
                if not self.running:
                    break
                
                # Get Binance prices from cache
                binance_prices = self.binance_service.get_all_prices()
                
                if not binance_prices:
                    continue
                
                # Calibrate each symbol
                for symbol, binance_data in binance_prices.items():
                    try:
                        await self._calibrate_symbol(symbol, binance_data)
                    except Exception as e:
                        logger.debug(f"Calibration failed for {symbol}: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in calibration loop: {e}")
                await asyncio.sleep(1)
    
    async def _calibrate_symbol(self, symbol: str, binance_data: Dict[str, Any]):
        """Calibrate offset for a single symbol"""
        try:
            # Convert Binance symbol to MT5 symbol
            mt5_symbol = self._convert_to_mt5_symbol(symbol)
            
            # Get MT5 quote through proxy (thread-safe)
            mt5_quote = await self.mt5_proxy.get_quote_async(mt5_symbol)
            if not mt5_quote:
                return
            
            # Calculate offset
            binance_price = binance_data['price']
            mt5_mid = (mt5_quote.bid + mt5_quote.ask) / 2
            
            # Update sync manager if available
            if self.binance_service.sync_manager:
                self.binance_service.sync_manager.update_offset(symbol, binance_price, mt5_mid)
                
        except Exception as e:
            logger.debug(f"Symbol calibration failed for {symbol}: {e}")
    
    def _convert_to_mt5_symbol(self, binance_symbol: str) -> str:
        """Convert Binance symbol to MT5 broker symbol"""
        symbol = binance_symbol.upper()
        
        # Remove USDT suffix if present
        if symbol.endswith("USDT"):
            symbol = symbol.replace("USDT", "USD")
        
        # Remove 'c' suffix if present
        if symbol.endswith("C"):
            symbol = symbol[:-1]
            
        # Add 'c' suffix for broker
        if not symbol.endswith("c"):
            symbol = symbol + "c"
            
        return symbol
