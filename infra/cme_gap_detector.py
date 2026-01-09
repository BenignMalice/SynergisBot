"""
CME Gap Detector
Detects CME gaps for BTCUSDc weekend trading.

Gap = difference between Sunday reopening price and Friday CME close.
CME closes at 22:00 UTC on Friday.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class CMEGapDetector:
    """
    Detects CME gaps for BTCUSDc weekend trading.
    Gap = difference between Sunday reopening price and Friday CME close.
    """
    
    GAP_THRESHOLD_PCT = 0.5  # 0.5% minimum gap
    REVERSION_TARGET_PCT = 0.8  # Target 80% gap fill
    
    def __init__(self, mt5_service=None, binance_service=None):
        """
        Initialize CME Gap Detector.
        
        Args:
            mt5_service: Optional MT5Service instance
            binance_service: Optional BinanceService instance (fallback)
        """
        self.mt5_service = mt5_service
        self.binance_service = binance_service
    
    def detect_gap(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Detect CME gap for symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc")
        
        Returns:
            Dict with:
                - gap_pct: Gap percentage
                - gap_direction: "up" or "down"
                - friday_close: Friday CME close price
                - sunday_open: Sunday reopening price
                - target_price: 80% gap fill target
                - should_trade: bool (gap > 0.5%)
        
        Implementation:
        - Get Friday CME close: Last Friday 22:00 UTC (CME closes at 22:00 UTC on Friday)
          - Data source: MT5 historical data (H1 or M15 timeframe) - get candle at or before 22:00 UTC
          - If MT5 unavailable: Use Binance historical data (if available)
        - Get Sunday reopening price: First Sunday 00:00 UTC (or first Sunday candle after 00:00)
          - Data source: MT5 current price or first Sunday candle
        - Calculate gap percentage: abs(sunday_open - friday_close) / friday_close * 100
        - Return gap information
        - **NOTE**: CME closes at 22:00 UTC Friday, so use last candle at or before 22:00 UTC
        """
        if symbol.upper() not in ["BTCUSDc", "BTCUSD"]:
            logger.debug(f"CME gap detection only for BTCUSDc, skipping {symbol}")
            return None
        
        friday_close = self._get_friday_cme_close(symbol)
        sunday_open = self._get_sunday_reopening_price(symbol)
        
        if friday_close is None or sunday_open is None:
            logger.warning(f"Could not get Friday close or Sunday open for {symbol}. Cannot detect CME gap.")
            return None
        
        gap_raw = sunday_open - friday_close
        gap_pct = (abs(gap_raw) / friday_close) * 100
        gap_direction = "up" if gap_raw > 0 else "down"
        
        should_trade = gap_pct >= self.GAP_THRESHOLD_PCT
        
        # Calculate target price (80% gap fill)
        target_price = friday_close + (gap_raw * self.REVERSION_TARGET_PCT)
        
        return {
            "gap_pct": gap_pct,
            "gap_direction": gap_direction,
            "friday_close": friday_close,
            "sunday_open": sunday_open,
            "target_price": target_price,
            "should_trade": should_trade,
            "gap_raw": gap_raw
        }
    
    def _get_friday_cme_close(self, symbol: str) -> Optional[float]:
        """
        Get Friday CME close price (last candle at or before Friday 22:00 UTC).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Friday CME close price or None if unavailable
        """
        try:
            # Get current date/time
            now = datetime.now(timezone.utc)
            
            # Find last Friday
            days_since_friday = (now.weekday() - 4) % 7
            if days_since_friday == 0 and now.hour < 22:
                # Today is Friday but before 22:00 UTC, use last Friday
                days_since_friday = 7
            
            if days_since_friday == 0:
                # Today is Friday and after 22:00 UTC, use today
                friday_date = now.date()
            else:
                # Go back to last Friday
                friday_date = now.date() - timedelta(days=days_since_friday)
            
            # Friday 22:00 UTC (CME close time)
            friday_close_time = datetime.combine(friday_date, datetime.min.time().replace(hour=22, minute=0))
            friday_close_time = friday_close_time.replace(tzinfo=timezone.utc)
            
            # Get candles around Friday 22:00 UTC
            # Use H1 timeframe to get the 22:00 candle
            start_time = friday_close_time - timedelta(hours=2)  # Start 2 hours before
            end_time = friday_close_time + timedelta(hours=1)  # End 1 hour after
            
            # Try MT5 first
            if not mt5.initialize():
                logger.warning("MT5 not initialized for CME gap detection")
                # Try fallback to Binance if available
                return self._get_friday_close_binance(symbol, friday_close_time)
            
            # Get H1 candles
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_timestamp, end_timestamp)
            
            if rates is None or len(rates) == 0:
                logger.debug(f"No H1 candles for {symbol} around Friday 22:00 UTC")
                # Try M15 as fallback
                rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_timestamp, end_timestamp)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"Could not get candles for {symbol} around Friday 22:00 UTC")
                return self._get_friday_close_binance(symbol, friday_close_time)
            
            # Find candle at or before 22:00 UTC
            # Rates are sorted by time (oldest first)
            friday_close_price = None
            for rate in rates:
                candle_time = datetime.fromtimestamp(rate['time'], tz=timezone.utc)
                if candle_time <= friday_close_time:
                    friday_close_price = float(rate['close'])
                else:
                    break  # Past 22:00 UTC, use last price found
            
            if friday_close_price is None:
                # Use last candle's close if no candle exactly at 22:00
                friday_close_price = float(rates[-1]['close'])
            
            logger.debug(f"Friday CME close for {symbol}: {friday_close_price:.2f} (at {friday_close_time})")
            return friday_close_price
            
        except Exception as e:
            logger.error(f"Error getting Friday CME close for {symbol}: {e}")
            return None
    
    def _get_sunday_reopening_price(self, symbol: str) -> Optional[float]:
        """
        Get Sunday reopening price (first candle after Sunday 00:00 UTC).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Sunday reopening price or None if unavailable
        """
        try:
            # Get current date/time
            now = datetime.now(timezone.utc)
            
            # Find last Sunday
            days_since_sunday = (now.weekday() - 6) % 7
            if days_since_sunday == 0:
                # Today is Sunday
                sunday_date = now.date()
            else:
                # Go back to last Sunday
                sunday_date = now.date() - timedelta(days=days_since_sunday)
            
            # Sunday 00:00 UTC (market reopening)
            sunday_open_time = datetime.combine(sunday_date, datetime.min.time().replace(hour=0, minute=0))
            sunday_open_time = sunday_open_time.replace(tzinfo=timezone.utc)
            
            # If it's currently Sunday and before 00:00, use previous Sunday
            if now.weekday() == 6 and now.hour < 0:
                sunday_date = sunday_date - timedelta(days=7)
                sunday_open_time = datetime.combine(sunday_date, datetime.min.time().replace(hour=0, minute=0))
                sunday_open_time = sunday_open_time.replace(tzinfo=timezone.utc)
            
            # Get candles around Sunday 00:00 UTC
            start_time = sunday_open_time
            end_time = sunday_open_time + timedelta(hours=2)  # Get first 2 hours of Sunday
            
            # Try MT5 first
            if not mt5.initialize():
                logger.warning("MT5 not initialized for CME gap detection")
                # Try fallback to Binance if available
                return self._get_sunday_open_binance(symbol, sunday_open_time)
            
            # Get H1 candles
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, start_timestamp, end_timestamp)
            
            if rates is None or len(rates) == 0:
                logger.debug(f"No H1 candles for {symbol} around Sunday 00:00 UTC")
                # Try M15 as fallback
                rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_timestamp, end_timestamp)
            
            if rates is None or len(rates) == 0:
                # If no historical data, try current price (if it's Sunday)
                if now.weekday() == 6:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        logger.debug(f"Using current price as Sunday open for {symbol}: {tick.bid:.2f}")
                        return (tick.bid + tick.ask) / 2  # Use mid price
                
                logger.warning(f"Could not get candles for {symbol} around Sunday 00:00 UTC")
                return self._get_sunday_open_binance(symbol, sunday_open_time)
            
            # Use first candle's open price (Sunday reopening)
            sunday_open_price = float(rates[0]['open'])
            
            logger.debug(f"Sunday reopening price for {symbol}: {sunday_open_price:.2f} (at {sunday_open_time})")
            return sunday_open_price
            
        except Exception as e:
            logger.error(f"Error getting Sunday reopening price for {symbol}: {e}")
            return None
    
    def _get_friday_close_binance(self, symbol: str, friday_close_time: datetime) -> Optional[float]:
        """Fallback to Binance for Friday close price"""
        # TODO: Implement Binance fallback if needed
        logger.debug(f"Binance fallback not implemented for Friday close")
        return None
    
    def _get_sunday_open_binance(self, symbol: str, sunday_open_time: datetime) -> Optional[float]:
        """Fallback to Binance for Sunday open price"""
        # TODO: Implement Binance fallback if needed
        logger.debug(f"Binance fallback not implemented for Sunday open")
        return None
    
    def should_create_reversion_plan(self, symbol: str) -> bool:
        """
        Check if gap is large enough to create reversion plan.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if gap > 0.5%, False otherwise
        """
        gap_info = self.detect_gap(symbol)
        if not gap_info:
            return False
        return gap_info.get("should_trade", False)

