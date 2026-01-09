"""
Binance Service - High-Level Integration Layer
Manages the full Binance streaming pipeline for MoneyBot.

Provides:
- Easy start/stop of Binance streams
- Integrated price cache + sync + validation
- Health monitoring and diagnostics
- Thread-safe access for concurrent tools

Usage:
    # In your main application or desktop_agent.py
    binance_service = BinanceService()
    await binance_service.start(["btcusdt", "ethusdt", "xauusd"])
    
    # Get latest price
    price = binance_service.get_latest_price("BTCUSDT")
    
    # Validate before execution
    is_safe, reason = binance_service.validate_execution("BTCUSDT", mt5_bid, mt5_ask)
    
    # Adjust signal for MT5
    adjusted = binance_service.adjust_signal_for_mt5("BTCUSDT", signal)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

from infra.binance_stream import BinanceStream
from infra.price_cache import PriceCache
from infra.price_sync_manager import PriceSyncManager
from infra.feed_validator import FeedValidator

logger = logging.getLogger(__name__)


class BinanceService:
    """
    High-level service for Binance streaming integration.
    
    Manages the full pipeline:
    Stream → Cache → Sync → Validate
    """
    
    def __init__(
        self,
        interval: str = "1m",
        max_cache_ticks: int = 1000,
        max_offset: float = 100.0
    ):
        """
        Args:
            interval: Kline interval (1m, 5m, 15m, 1h, 4h)
            max_cache_ticks: Maximum ticks to cache per symbol
            max_offset: Maximum acceptable offset in pips
        """
        self.interval = interval
        self.cache = PriceCache(max_ticks=max_cache_ticks)
        self.sync_manager = PriceSyncManager(calibration_window=60)
        self.feed_validator = FeedValidator(max_offset=max_offset)
        self.stream: Optional[BinanceStream] = None
        self.symbols: List[str] = []
        self.running = False
        self._mt5_service = None  # Will be set externally
        
        logger.info(f"📡 BinanceService initialized (interval={interval})")
        
    def set_mt5_service(self, mt5_service):
        """
        Set the MT5Service for automatic offset calibration.
        
        Args:
            mt5_service: Instance of MT5Service
        """
        self._mt5_service = mt5_service
        logger.info("🔗 MT5Service linked to BinanceService")
        
    async def _on_tick(self, tick: dict):
        """
        Internal callback for each Binance tick.
        Updates cache and calculates offset if MT5 is available.
        """
        symbol = tick['symbol']
        
        # Update cache
        self.cache.update(symbol, tick)
        
        # MT5 calls removed to prevent cross-thread access
        # Offset calibration now handled by periodic task on main thread
        # This prevents WebSocket stalls and disconnects
        pass
                
    def _convert_to_mt5_symbol(self, binance_symbol: str) -> str:
        """
        Convert Binance symbol to MT5 broker symbol.
        
        Examples:
            BTCUSDT → BTCUSDc
            ETHUSDT → ETHUSDc
            XAUUSD → XAUUSDc
            BTCUSDc → BTCUSDc (already correct)
        """
        symbol = binance_symbol.upper()
        
        # Remove USDT suffix if present (but not if it's already ending in 'c')
        if symbol.endswith("USDT"):
            symbol = symbol.replace("USDT", "USD")
        
        # Remove 'c' suffix if present (to normalize)
        if symbol.endswith("C"):
            symbol = symbol[:-1]
            
        # Add 'c' suffix for broker
        if not symbol.endswith("c"):
            symbol += "c"
            
        return symbol
        
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> str:
        """
        Convert MT5 symbol to Binance symbol.
        
        Examples:
            BTCUSDc → BTCUSDT
            XAUUSDc → XAUUSD
        """
        symbol = mt5_symbol.upper()
        
        # Remove 'c' suffix
        if symbol.endswith("C"):
            symbol = symbol[:-1]
            
        # Add USDT for crypto pairs
        if symbol.startswith(("BTC", "ETH", "LTC", "XRP", "ADA")):
            if not symbol.endswith("USDT"):
                symbol = symbol.replace("USD", "USDT")
                
        return symbol.lower()
        
    async def start(self, symbols: List[str], background: bool = True):
        """
        Start Binance streaming for specified symbols.
        
        Args:
            symbols: List of symbols (Binance format: btcusdt, ethusdt)
            background: If True, run in background task
            
        Example:
            await binance_service.start(["btcusdt", "ethusdt"])
            
        Note: Only crypto pairs are supported. Forex/commodity pairs are filtered out.
        """
        if self.running:
            logger.warning("⚠️ BinanceService already running")
            return
        
        # Filter to only crypto pairs (Binance doesn't support forex/commodities)
        # Valid crypto pairs: btcusdt, ethusdt, ltcusdt, etc.
        crypto_symbols = []
        for s in symbols:
            symbol_lower = s.lower()
            # Check if it's a valid crypto pair (ends with usdt and is a known crypto)
            if symbol_lower.endswith('usdt') and any(crypto in symbol_lower for crypto in ['btc', 'eth', 'ltc', 'xrp', 'ada', 'bnb', 'sol', 'dot', 'link']):
                crypto_symbols.append(symbol_lower)
            elif symbol_lower == 'btcusd':  # Also accept BTCUSD (without T)
                crypto_symbols.append('btcusdt')
            else:
                logger.debug(f"Skipping non-crypto symbol {s} (Binance only supports crypto pairs)")
        
        if not crypto_symbols:
            logger.warning("⚠️ No valid crypto symbols provided for Binance streaming")
            return
            
        self.symbols = crypto_symbols
        self.running = True
        
        # Create stream
        self.stream = BinanceStream(
            symbols=self.symbols,
            callback=self._on_tick,
            interval=self.interval
        )
        
        logger.info(f"🚀 Starting Binance streams: {', '.join(self.symbols)}")
        
        if background:
            # Run in background task
            asyncio.create_task(self.stream.start_all())
            await asyncio.sleep(2)  # Give it time to connect
            logger.info("✅ Binance streams running in background")
        else:
            # Run in foreground (blocks)
            await self.stream.start_all()
            
    def stop(self):
        """
        Stop all Binance streams.
        """
        if not self.running:
            return
            
        logger.info("🛑 Stopping Binance streams...")
        self.running = False
        
        if self.stream:
            self.stream.stop()
            
        logger.info("✅ Binance streams stopped")
        
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest price for a symbol.
        
        Args:
            symbol: Symbol (MT5 or Binance format)
            
        Returns:
            Latest price or None if not available
        """
        # Convert to Binance format if needed
        if symbol.endswith(('c', 'C')):
            symbol = self._convert_to_binance_symbol(symbol)
        else:
            symbol = symbol.upper()
            
        tick = self.cache.get_latest(symbol)
        return tick['price'] if tick else None
        
    def get_latest_tick(self, symbol: str) -> Optional[dict]:
        """
        Get the latest full tick data for a symbol.
        
        Returns:
            {price, open, high, low, close, volume, timestamp, ...}
        """
        if symbol.endswith(('c', 'C')):
            symbol = self._convert_to_binance_symbol(symbol)
        else:
            symbol = symbol.upper()
            
        return self.cache.get_latest(symbol)
        
    def get_history(self, symbol: str, count: int = 200) -> List[dict]:
        """
        Get recent price history for a symbol.
        
        Args:
            symbol: Symbol name
            count: Number of ticks to retrieve
            
        Returns:
            List of tick dicts (oldest to newest)
        """
        if symbol.endswith(('c', 'C')):
            symbol = self._convert_to_binance_symbol(symbol)
        else:
            symbol = symbol.upper()
            
        return self.cache.get_history(symbol, count)
        
    def validate_execution(
        self,
        symbol: str,
        mt5_bid: float,
        mt5_ask: float
    ) -> Tuple[bool, str]:
        """
        Validate if it's safe to execute a trade.
        
        Args:
            symbol: Symbol (MT5 or Binance format)
            mt5_bid: Current MT5 bid price
            mt5_ask: Current MT5 ask price
            
        Returns:
            (is_safe, reason)
            
        Example:
            is_safe, reason = binance_service.validate_execution(
                "BTCUSDc", 112120, 112125
            )
            if not is_safe:
                print(f"⚠️ Trade blocked: {reason}")
        """
        # Convert to Binance format
        binance_symbol = self._convert_to_binance_symbol(symbol)
        
        # Get latest Binance price
        tick = self.cache.get_latest(binance_symbol)
        if not tick:
            return False, f"No Binance data available for {binance_symbol}"
            
        binance_price = tick['price']
        
        # Check data freshness
        age = self.cache.get_age_seconds(binance_symbol)
        if age and age > 60:
            return False, f"Binance data is stale ({age:.0f}s old)"
            
        # Get offset
        offset = self.sync_manager.get_current_offset(binance_symbol)
        
        # Validate
        return self.feed_validator.validate_execution_safety(
            symbol=binance_symbol,
            binance_price=binance_price,
            mt5_bid=mt5_bid,
            mt5_ask=mt5_ask,
            offset=offset
        )
        
    def adjust_signal_for_mt5(self, symbol: str, signal: dict) -> dict:
        """
        Adjust a Binance-based signal for MT5 execution.
        
        Args:
            symbol: Symbol (MT5 or Binance format)
            signal: Signal dict with {entry, sl, tp, ...}
            
        Returns:
            Adjusted signal with MT5-compatible prices
            
        Example:
            signal = {"entry": 112150, "sl": 112000, "tp": 112400}
            adjusted = binance_service.adjust_signal_for_mt5("BTCUSDc", signal)
            # Now ready for MT5 execution
        """
        binance_symbol = self._convert_to_binance_symbol(symbol)
        return self.sync_manager.adjust_signal_for_mt5(binance_symbol, signal)
        
    def get_feed_health(self, symbol: str = None) -> dict:
        """
        Get feed health status.
        
        Args:
            symbol: Check specific symbol, or None for all symbols
            
        Returns:
            Health status dict
        """
        if symbol:
            binance_symbol = self._convert_to_binance_symbol(symbol)
            
            cache_stats = self.cache.get_stats(binance_symbol)
            sync_health = self.sync_manager.get_sync_health(binance_symbol)
            
            return {
                "symbol": binance_symbol,
                "cache": cache_stats,
                "sync": sync_health,
                "overall_status": sync_health["status"]
            }
        else:
            # All symbols
            return {
                "cache": {s: self.cache.get_stats(s) for s in self.cache.get_all_symbols()},
                "sync": self.sync_manager.get_all_health()
            }
            
    def is_healthy(self, symbol: str = None) -> bool:
        """
        Quick health check.
        
        Args:
            symbol: Check specific symbol, or None to check if any feed is healthy
            
        Returns:
            True if healthy, False otherwise
        """
        if symbol:
            health = self.get_feed_health(symbol)
            return health["overall_status"] == "healthy"
        else:
            # Check if at least one symbol is healthy
            all_health = self.sync_manager.get_all_health()
            return any(h["status"] == "healthy" for h in all_health.values())
            
    def get_status_summary(self) -> str:
        """
        Get a human-readable status summary.
        
        Returns:
            Multi-line status string
        """
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════╗")
        lines.append("║           BINANCE SERVICE STATUS                         ║")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        lines.append(f"Running: {'✅ YES' if self.running else '❌ NO'}")
        lines.append(f"Symbols: {', '.join(s.upper() for s in self.symbols) if self.symbols else 'None'}")
        lines.append(f"Connected: {len(self.stream.connections) if self.stream else 0}/{len(self.symbols)}")
        lines.append("")
        
        # Cache stats
        for symbol in self.cache.get_all_symbols():
            stats = self.cache.get_stats(symbol)
            health = self.sync_manager.get_sync_health(symbol)
            
            status_emoji = "✅" if health["status"] == "healthy" else "⚠️" if health["status"] == "warning" else "🔴"
            offset_str = f"{health['offset']:+.1f}" if health['offset'] is not None else "N/A"
            
            lines.append(f"{status_emoji} {symbol:12s} | "
                        f"Ticks: {stats['tick_count']:4d} | "
                        f"Age: {stats['age_seconds']:5.1f}s | "
                        f"Offset: {offset_str}")
                        
        return "\n".join(lines)
        
    def print_status(self):
        """
        Print status summary to console.
        """
        print(self.get_status_summary())


# Example usage
async def example_usage():
    """
    Example of how to use BinanceService.
    """
    from infra.mt5_service import MT5Service
    
    # Initialize services
    mt5 = MT5Service()
    mt5.connect()
    
    binance_service = BinanceService(interval="1m")
    binance_service.set_mt5_service(mt5)
    
    # Start streaming
    await binance_service.start(["btcusdt", "ethusdt"])
    
    # Wait for data to accumulate
    await asyncio.sleep(10)
    
    # Check status
    binance_service.print_status()
    
    # Get latest price
    btc_price = binance_service.get_latest_price("BTCUSDc")
    print(f"\n💰 BTC Price: ${btc_price:,.2f}")
    
    # Validate execution
    quote = mt5.get_quote("BTCUSDc")
    if quote:
        is_safe, reason = binance_service.validate_execution(
            "BTCUSDc",
            quote['bid'],
            quote['ask']
        )
        print(f"🛡️ Execution Safety: {is_safe} - {reason}")
        
    # Stop
    binance_service.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing BinanceService\n")
    
    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        print("\n👋 Test stopped")

