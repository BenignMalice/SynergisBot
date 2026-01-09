"""
Price Synchronization Manager
Handles Binance-MT5 price offset calibration.

Problem: Binance and MT5 broker may differ by 20-70 pips for crypto CFDs.
Solution: Track dynamic offset and adjust SL/TP before execution.

Example:
    Binance BTC: 112,180
    MT5 BTC: 112,120
    Offset: +60 pips
    → Adjust GPT signals by -60 before MT5 execution

Usage:
    sync_manager = PriceSyncManager()
    sync_manager.update_offset("BTCUSDT", binance_price=112180, mt5_price=112120)
    adjusted_signal = sync_manager.adjust_signal_for_mt5("BTCUSDT", signal)
"""

import time
import logging
from collections import deque
from typing import Dict, Optional, Tuple
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


class PriceSyncManager:
    """
    Synchronize Binance and MT5 price feeds.
    
    Tracks price offset and adjusts signals for MT5 execution.
    """
    
    def __init__(self, calibration_window: int = 60, alert_threshold: float = 50.0):
        """
        Args:
            calibration_window: Number of offset samples to keep (default: 60)
            alert_threshold: Log warning if offset exceeds this (pips)
        """
        self.offsets: Dict[str, deque] = {}  # symbol -> deque of (timestamp, offset)
        self.calibration_window = calibration_window
        self.alert_threshold = alert_threshold
        self.last_sync: Dict[str, float] = {}  # symbol -> timestamp
        self.locks: Dict[str, Lock] = {}
        
        logger.info(f"🔄 PriceSyncManager initialized (window={calibration_window}s)")
        
    def update_offset(self, symbol: str, binance_price: float, mt5_price: float):
        """
        Update price offset between Binance and MT5.
        Stores last N offsets for rolling average.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            binance_price: Current Binance price
            mt5_price: Current MT5 broker price
        """
        symbol = symbol.upper()
        offset = binance_price - mt5_price
        timestamp = time.time()
        
        # Initialize if new symbol
        if symbol not in self.offsets:
            self.offsets[symbol] = deque(maxlen=self.calibration_window)
            self.locks[symbol] = Lock()
            logger.info(f"📊 Tracking offset for new symbol: {symbol}")
            
        # Thread-safe update
        with self.locks[symbol]:
            self.offsets[symbol].append((timestamp, offset))
            self.last_sync[symbol] = timestamp
            
        # Alert on large offsets
        if abs(offset) > self.alert_threshold:
            logger.warning(f"⚠️ Large price offset detected: {symbol} = {offset:.2f} pips "
                          f"(Binance: {binance_price:.2f}, MT5: {mt5_price:.2f})")
            
    def get_current_offset(self, symbol: str) -> Optional[float]:
        """
        Get current price offset (average of recent samples).
        Returns None if no data or stale data.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Average offset in pips, or None if unavailable
        """
        symbol = symbol.upper()
        
        if symbol not in self.offsets or len(self.offsets[symbol]) == 0:
            return None
            
        # Check if data is stale (>5 minutes old)
        if time.time() - self.last_sync.get(symbol, 0) > 300:
            logger.warning(f"⚠️ Stale price sync data for {symbol}")
            return None
            
        # Calculate rolling average
        with self.locks[symbol]:
            recent_offsets = list(self.offsets[symbol])
            
        if len(recent_offsets) == 0:
            return None
            
        # Simple average of all samples in window
        avg_offset = sum(o[1] for o in recent_offsets) / len(recent_offsets)
        return avg_offset
        
    def adjust_signal_for_mt5(self, symbol: str, signal: dict) -> dict:
        """
        Adjust Binance-based signal for MT5 execution.
        
        Subtracts the offset from all price levels to match MT5 prices.
        
        Args:
            symbol: Trading symbol
            signal: Signal dict with keys: {entry, sl, tp, ...}
            
        Returns:
            Adjusted signal with MT5-compatible prices
            
        Example:
            Input: {entry: 112150, sl: 112300, tp: 111800}  # Binance prices
            Offset: +60 pips (Binance > MT5)
            Output: {entry: 112090, sl: 112240, tp: 111740}  # MT5 prices
        """
        symbol = symbol.upper()
        offset = self.get_current_offset(symbol)
        
        if offset is None:
            logger.warning(f"⚠️ No price offset available for {symbol}, using Binance prices as-is")
            return signal.copy()
            
        # Adjust all price levels
        adjusted = signal.copy()
        
        for field in ['entry', 'stop_loss', 'take_profit', 'sl', 'tp']:
            if field in adjusted and adjusted[field] is not None:
                adjusted[field] = adjusted[field] - offset
                
        logger.info(f"📊 {symbol}: Adjusted signal by {offset:.2f} pips for MT5 execution")
        logger.debug(f"   Original: entry={signal.get('entry')}, sl={signal.get('sl' or 'stop_loss')}, tp={signal.get('tp' or 'take_profit')}")
        logger.debug(f"   Adjusted: entry={adjusted.get('entry')}, sl={adjusted.get('sl' or 'stop_loss')}, tp={adjusted.get('tp' or 'take_profit')}")
        
        # Add metadata
        adjusted['_offset_applied'] = offset
        adjusted['_source'] = 'binance_adjusted_to_mt5'
        
        return adjusted
        
    def get_sync_health(self, symbol: str) -> dict:
        """
        Check synchronization health for a symbol.
        
        Returns:
            {
                "status": "healthy" | "warning" | "critical",
                "offset": float | None,
                "last_sync_age": float,
                "data_points": int,
                "reason": str
            }
        """
        symbol = symbol.upper()
        
        if symbol not in self.offsets:
            return {
                "status": "critical",
                "offset": None,
                "last_sync_age": None,
                "data_points": 0,
                "reason": "No sync data available"
            }
            
        offset = self.get_current_offset(symbol)
        age = time.time() - self.last_sync.get(symbol, 0)
        data_points = len(self.offsets[symbol])
        
        # Determine health status
        if offset is None or age > 300:
            status = "critical"
            reason = f"Stale data (age: {age:.0f}s)" if age > 300 else "No offset data"
        elif abs(offset) > 100 or age > 60:
            status = "warning"
            reason = f"Large offset ({offset:.1f}) or aging data ({age:.0f}s)"
        else:
            status = "healthy"
            reason = "All checks passed"
            
        return {
            "status": status,
            "offset": offset,
            "last_sync_age": age,
            "data_points": data_points,
            "reason": reason
        }
        
    def get_all_health(self) -> Dict[str, dict]:
        """
        Get health status for all tracked symbols.
        
        Returns:
            {symbol: health_dict, ...}
        """
        return {symbol: self.get_sync_health(symbol) for symbol in self.offsets.keys()}
        
    def print_summary(self):
        """
        Print synchronization summary for all symbols.
        """
        print("\n" + "="*70)
        print("🔄 PRICE SYNCHRONIZATION SUMMARY")
        print("="*70)
        
        for symbol in sorted(self.offsets.keys()):
            health = self.get_sync_health(symbol)
            
            if health["status"] == "healthy":
                status_emoji = "✅"
            elif health["status"] == "warning":
                status_emoji = "⚠️"
            else:
                status_emoji = "🔴"
                
            offset_str = f"{health['offset']:+7.2f}" if health['offset'] is not None else "  N/A  "
            age_str = f"{health['last_sync_age']:5.1f}s" if health['last_sync_age'] is not None else "  N/A  "
            
            print(f"{status_emoji} {symbol:12s} | "
                  f"Offset: {offset_str} pips | "
                  f"Age: {age_str} | "
                  f"Samples: {health['data_points']:3d} | "
                  f"{health['reason']}")
                  
        print("="*70 + "\n")
        
    def clear(self, symbol: str = None):
        """
        Clear offset data for a symbol or all symbols.
        
        Args:
            symbol: Symbol to clear, or None to clear all
        """
        if symbol:
            symbol = symbol.upper()
            if symbol in self.offsets:
                with self.locks[symbol]:
                    self.offsets[symbol].clear()
                logger.info(f"🗑️ Cleared offset data for {symbol}")
        else:
            for sym in list(self.offsets.keys()):
                with self.locks[sym]:
                    self.offsets[sym].clear()
            logger.info("🗑️ Cleared all offset data")


# Example usage
async def example_usage():
    """
    Example of how to use PriceSyncManager.
    """
    from infra.binance_stream import BinanceStream
    from infra.mt5_service import MT5Service
    
    # Initialize
    sync_manager = PriceSyncManager()
    mt5 = MT5Service()
    mt5.connect()
    
    # Callback to update offsets
    async def on_tick(tick: dict):
        symbol = tick['symbol']
        binance_price = tick['price']
        
        # Get MT5 price
        try:
            mt5_symbol = symbol.replace("USDT", "USD") + "c"  # BTCUSDT -> BTCUSDc
            quote = mt5.get_quote(mt5_symbol)
            if quote:
                mt5_price = (quote.bid + quote.ask) / 2
                sync_manager.update_offset(symbol, binance_price, mt5_price)
                
                # Print summary every 20 ticks
                if len(sync_manager.offsets.get(symbol, [])) % 20 == 0:
                    sync_manager.print_summary()
        except Exception as e:
            logger.error(f"Error getting MT5 price: {e}")
            
    # Start streaming
    stream = BinanceStream(
        symbols=["btcusdt"],
        callback=on_tick,
        interval="1m"
    )
    
    try:
        await stream.start_all()
    except KeyboardInterrupt:
        stream.stop()
        print("\n✅ Stream stopped")
        sync_manager.print_summary()


if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing PriceSyncManager")
    print("Press Ctrl+C to stop\n")
    
    asyncio.run(example_usage())



