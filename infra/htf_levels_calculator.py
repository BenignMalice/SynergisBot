"""
HTF Levels Calculator
Calculates higher timeframe key levels (weekly/monthly opens, previous week/day highs/lows)
"""

import logging
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class HTFLevelsCalculator:
    """Calculate higher timeframe key levels"""
    
    def __init__(self, mt5_service=None):
        self.mt5_service = mt5_service
    
    async def calculate_htf_levels(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Calculate higher timeframe key levels.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc")
        
        Returns:
            {
                "weekly_open": 4175.0,  # Current week's open (Monday 00:00 UTC)
                "monthly_open": 4120.0,  # Current month's open (1st day 00:00 UTC)
                "previous_week_high": 4225.0,
                "previous_week_low": 4085.0,
                "previous_day_high": 4210.0,  # Align with PDH naming
                "previous_day_low": 4190.0,   # Align with PDL naming
                "range_reference": "weekly_range",  # "weekly_range" | "asia_session_range" | "daily_range"
                "current_price_position": "premium",  # "discount" | "equilibrium" | "premium"
                "discount_threshold": 0.33,  # Bottom 33% of range
                "premium_threshold": 0.66,   # Top 33% of range
                "timezone": "UTC"  # Timezone used for calculations
            }
        """
        try:
            if not self.mt5_service:
                logger.warning("MT5 service not available for HTF levels")
                return self._create_unavailable_response()
            
            # Get current price
            loop = asyncio.get_event_loop()
            current_price = await loop.run_in_executor(
                None,
                lambda: self._get_current_price(symbol)
            )
            
            if current_price is None:
                logger.warning(f"Could not get current price for {symbol}")
                return self._create_unavailable_response()
            
            # Fetch historical bars in parallel
            d1_bars, w1_bars, mn1_bars = await asyncio.gather(
                self._fetch_bars(symbol, "D1", 30),  # Last 30 days
                self._fetch_bars(symbol, "W1", 4),   # Last 4 weeks
                self._fetch_bars(symbol, "MN1", 3),  # Last 3 months
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(d1_bars, Exception):
                logger.error(f"Error fetching D1 bars: {d1_bars}")
                d1_bars = None
            if isinstance(w1_bars, Exception):
                logger.error(f"Error fetching W1 bars: {w1_bars}")
                w1_bars = None
            if isinstance(mn1_bars, Exception):
                logger.error(f"Error fetching MN1 bars: {mn1_bars}")
                mn1_bars = None
            
            # Calculate levels
            weekly_open = None
            monthly_open = None
            previous_week_high = None
            previous_week_low = None
            previous_day_high = None
            previous_day_low = None
            
            # Get current week/month boundaries in UTC
            now_utc = datetime.now(timezone.utc)
            current_week_start = self._get_week_start(now_utc)
            current_month_start = self._get_month_start(now_utc)
            
            # Calculate previous day high/low from D1 bars
            if d1_bars is not None and len(d1_bars) > 0:
                # Previous day is the second-to-last bar (last bar is current day)
                if len(d1_bars) >= 2:
                    prev_day = d1_bars.iloc[-2]
                    previous_day_high = float(prev_day['high'])
                    previous_day_low = float(prev_day['low'])
                
                # Current day open (for weekly/monthly open calculation)
                if len(d1_bars) >= 1:
                    current_day = d1_bars.iloc[-1]
                    # Check if current day is the start of week/month
                    current_day_time = pd.to_datetime(current_day['time'])
                    if current_day_time.tz is None:
                        current_day_time = current_day_time.replace(tzinfo=timezone.utc)
                    
                    # Weekly open: if current day is Monday (week start)
                    if current_day_time.date() == current_week_start.date():
                        weekly_open = float(current_day['open'])
                    else:
                        # Find the Monday bar
                        for i in range(len(d1_bars) - 1, -1, -1):
                            bar_time = pd.to_datetime(d1_bars.iloc[i]['time'])
                            if bar_time.tz is None:
                                bar_time = bar_time.replace(tzinfo=timezone.utc)
                            if bar_time.date() == current_week_start.date():
                                weekly_open = float(d1_bars.iloc[i]['open'])
                                break
                    
                    # Monthly open: if current day is 1st of month
                    if current_day_time.date() == current_month_start.date():
                        monthly_open = float(current_day['open'])
                    else:
                        # Find the 1st of month bar
                        for i in range(len(d1_bars) - 1, -1, -1):
                            bar_time = pd.to_datetime(d1_bars.iloc[i]['time'])
                            if bar_time.tz is None:
                                bar_time = bar_time.replace(tzinfo=timezone.utc)
                            if bar_time.date() == current_month_start.date():
                                monthly_open = float(d1_bars.iloc[i]['open'])
                                break
            
            # Calculate previous week high/low from W1 bars
            if w1_bars is not None and len(w1_bars) >= 2:
                prev_week = w1_bars.iloc[-2]
                previous_week_high = float(prev_week['high'])
                previous_week_low = float(prev_week['low'])
            
            # Calculate current price position and range reference
            range_reference, current_price_position = self._calculate_price_position(
                current_price,
                previous_week_high,
                previous_week_low,
                previous_day_high,
                previous_day_low
            )
            
            return {
                "weekly_open": weekly_open,
                "monthly_open": monthly_open,
                "previous_week_high": previous_week_high,
                "previous_week_low": previous_week_low,
                "previous_day_high": previous_day_high,
                "previous_day_low": previous_day_low,
                "range_reference": range_reference,
                "current_price_position": current_price_position,
                "discount_threshold": 0.33,
                "premium_threshold": 0.66,
                "timezone": "UTC"
            }
            
        except Exception as e:
            logger.error(f"Error calculating HTF levels for {symbol}: {e}", exc_info=True)
            return self._create_unavailable_response()
    
    async def _fetch_bars(self, symbol: str, timeframe: str, count: int) -> Optional[pd.DataFrame]:
        """Fetch historical bars from MT5"""
        try:
            loop = asyncio.get_event_loop()
            bars = await loop.run_in_executor(
                None,
                lambda: self.mt5_service.get_bars(symbol, timeframe, count)
            )
            return bars
        except Exception as e:
            logger.error(f"Error fetching {timeframe} bars for {symbol}: {e}")
            return None
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from MT5"""
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            return (tick.bid + tick.ask) / 2.0
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def _get_week_start(self, dt: datetime) -> datetime:
        """Get Monday 00:00 UTC for the week containing dt"""
        # Get Monday of the week
        days_since_monday = dt.weekday()  # Monday = 0
        monday = dt - timedelta(days=days_since_monday)
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _get_month_start(self, dt: datetime) -> datetime:
        """Get 1st of month 00:00 UTC for the month containing dt"""
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    def _calculate_price_position(
        self,
        current_price: float,
        previous_week_high: Optional[float],
        previous_week_low: Optional[float],
        previous_day_high: Optional[float],
        previous_day_low: Optional[float]
    ) -> tuple[str, str]:
        """
        Calculate range reference and current price position.
        
        Returns:
            (range_reference, current_price_position)
        """
        # Determine range reference
        range_reference = "daily_range"  # Default
        
        # Check if price is within weekly range
        if previous_week_high is not None and previous_week_low is not None:
            if previous_week_low <= current_price <= previous_week_high:
                range_reference = "weekly_range"
            elif current_price > previous_week_high or current_price < previous_week_low:
                # Price broke weekly range
                if previous_day_high is not None and previous_day_low is not None:
                    if previous_day_low <= current_price <= previous_day_high:
                        range_reference = "daily_range"
                    else:
                        range_reference = "asia_session_range"  # Broke daily too
        
        # Calculate current price position
        current_price_position = "equilibrium"  # Default
        
        # Use weekly range if available, otherwise daily
        range_high = previous_week_high if previous_week_high is not None else previous_day_high
        range_low = previous_week_low if previous_week_low is not None else previous_day_low
        
        if range_high is not None and range_low is not None:
            range_width = range_high - range_low
            if range_width > 0:
                position_in_range = (current_price - range_low) / range_width
                
                if position_in_range < 0.33:
                    current_price_position = "discount"
                elif position_in_range > 0.66:
                    current_price_position = "premium"
                else:
                    current_price_position = "equilibrium"
        
        return range_reference, current_price_position
    
    def _create_unavailable_response(self) -> Dict[str, Any]:
        """Create response dict for unavailable data"""
        return {
            "weekly_open": None,
            "monthly_open": None,
            "previous_week_high": None,
            "previous_week_low": None,
            "previous_day_high": None,
            "previous_day_low": None,
            "range_reference": "daily_range",
            "current_price_position": "equilibrium",
            "discount_threshold": 0.33,
            "premium_threshold": 0.66,
            "timezone": "UTC"
        }

