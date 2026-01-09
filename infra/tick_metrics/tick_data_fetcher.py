"""
Tick Data Fetcher

Fetches raw tick data from MT5 using copy_ticks_range().
Handles chunking for large requests and validates tick structure.
"""
import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

# MT5 tick limit per request (conservative estimate)
MAX_TICKS_PER_REQUEST = 100000
ESTIMATED_TICKS_PER_HOUR = 50000  # Conservative estimate for chunking


class TickDataFetcher:
    """Fetches tick data from MT5 with chunking support for large requests."""
    
    def __init__(self):
        """Initialize the tick data fetcher."""
        self._ensure_mt5_connection()
    
    def _ensure_mt5_connection(self) -> bool:
        """Ensure MT5 is initialized and connected."""
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                # MT5 not initialized - try to initialize
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    logger.warning(f"MT5 initialization failed: {error_code}")
                    return False
                terminal_info = mt5.terminal_info()
            
            if not terminal_info.connected:
                logger.warning("MT5 initialized but not connected to broker")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking MT5 connection: {e}")
            return False
    
    def fetch_ticks_for_period(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch ticks within a time range.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDc')
            start_time: Start datetime (UTC)
            end_time: End datetime (UTC)
        
        Returns:
            List of tick dictionaries or None if failed
        """
        if not self._ensure_mt5_connection():
            logger.warning(f"MT5 not connected, cannot fetch ticks for {symbol}")
            return None
        
        try:
            # Convert datetime to Unix timestamp
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # Use chunking for large requests
            ticks = self._chunk_large_requests(symbol, start_timestamp, end_timestamp)
            
            if ticks is None:
                return None
            
            # Validate and convert to list of dicts
            validated_ticks = self._validate_tick_data(ticks)
            
            if len(validated_ticks) == 0:
                raw_count = len(ticks) if ticks is not None else 0
                logger.warning(f"No valid ticks returned for {symbol} from {start_time} to {end_time} (raw ticks: {raw_count}, validated: 0)")
                if raw_count > 0:
                    logger.warning(f"   ⚠️ All {raw_count} raw ticks were filtered out by validation - checking validation logic...")
                return []
            
            logger.info(f"Fetched {len(validated_ticks)} validated ticks for {symbol} (from {len(ticks)} raw ticks)")
            return validated_ticks
            
        except Exception as e:
            logger.error(f"Error fetching ticks for {symbol}: {e}", exc_info=True)
            return None
    
    def fetch_previous_hour_ticks(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch ticks from the last 60 minutes (rolling window).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            List of tick dictionaries or None if failed
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        return self.fetch_ticks_for_period(symbol, start_time, end_time)
    
    def fetch_previous_day_ticks(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch ticks from the last 24 hours.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            List of tick dictionaries or None if failed
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        return self.fetch_ticks_for_period(symbol, start_time, end_time)
    
    def fetch_previous_clock_hour_ticks(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch ticks from the complete previous clock hour (e.g., 13:00-14:00 if current is 14:35).
        
        Args:
            symbol: Trading symbol
        
        Returns:
            List of tick dictionaries or None if failed
        """
        now = datetime.utcnow()
        # Get the start of the current hour
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        # Previous hour is one hour before
        previous_hour_start = current_hour_start - timedelta(hours=1)
        previous_hour_end = current_hour_start
        
        return self.fetch_ticks_for_period(symbol, previous_hour_start, previous_hour_end)
    
    def _chunk_large_requests(
        self,
        symbol: str,
        start_time: int,
        end_time: int
    ) -> Optional[List]:
        """
        Fetch ticks in chunks to handle MT5's ~100K tick limit.
        For 24-hour requests (previous_day), may need multiple chunks.
        
        Args:
            symbol: Trading symbol
            start_time: Start Unix timestamp
            end_time: End Unix timestamp
        
        Returns:
            List of tick arrays or None if failed
        """
        # Calculate expected tick count
        hours = (end_time - start_time) / 3600
        estimated_ticks = hours * ESTIMATED_TICKS_PER_HOUR
        
        if estimated_ticks <= MAX_TICKS_PER_REQUEST:
            # Single request sufficient
            ticks = mt5.copy_ticks_range(symbol, start_time, end_time, mt5.COPY_TICKS_ALL)
            if ticks is None:
                error_code = mt5.last_error()
                logger.warning(f"MT5 copy_ticks_range failed for {symbol}: {error_code}")
                return None
            return ticks
        
        # Need to chunk - split by time intervals
        all_ticks = []
        chunk_hours = MAX_TICKS_PER_REQUEST / ESTIMATED_TICKS_PER_HOUR
        current_start = start_time
        
        logger.debug(f"Chunking large request for {symbol}: {hours:.1f} hours, estimated {estimated_ticks:.0f} ticks")
        
        while current_start < end_time:
            current_end = min(current_start + int(chunk_hours * 3600), end_time)
            
            chunk = mt5.copy_ticks_range(symbol, current_start, current_end, mt5.COPY_TICKS_ALL)
            if chunk is None:
                error_code = mt5.last_error()
                logger.warning(f"MT5 copy_ticks_range chunk failed for {symbol}: {error_code}")
                # Continue with next chunk instead of failing entirely
                current_start = current_end
                continue
            
            if len(chunk) > 0:
                all_ticks.extend(chunk)
            
            current_start = current_end
            
            # Small delay to avoid overwhelming MT5
            time.sleep(0.01)
        
        logger.debug(f"Chunked request completed: {len(all_ticks)} total ticks")
        return all_ticks
    
    def _validate_tick_data(self, ticks: List) -> List[Dict[str, Any]]:
        """
        Validate tick structure and convert to list of dictionaries.
        
        Args:
            ticks: Raw tick array from MT5
        
        Returns:
            List of validated tick dictionaries
        """
        if ticks is None or len(ticks) == 0:
            return []
        
        validated = []
        invalid_samples = []  # Collect samples of invalid ticks for debugging
        
        # Check dtype to understand structure
        if len(ticks) > 0:
            first_tick = ticks[0]
            dtype_names = None
            if hasattr(first_tick, 'dtype') and hasattr(first_tick.dtype, 'names') and first_tick.dtype.names:
                dtype_names = first_tick.dtype.names
                logger.debug(f"Tick dtype fields: {dtype_names}")
        
        for i, tick in enumerate(ticks):
            try:
                # MT5 returns numpy structured array (numpy.void)
                # Access fields using item access (tick['field']) which works for numpy.void
                if hasattr(tick, 'dtype') and hasattr(tick.dtype, 'names') and tick.dtype.names:
                    # Numpy structured array - use item access with field names
                    time_val = int(tick['time'])
                    time_msc_val = int(tick['time_msc']) if 'time_msc' in tick.dtype.names else int(tick['time'] * 1000)
                    bid_val = float(tick['bid'])
                    ask_val = float(tick['ask'])
                    last_val = float(tick['last']) if 'last' in tick.dtype.names else float(tick['bid'])
                    volume_val = int(tick['volume']) if 'volume' in tick.dtype.names else 0
                    volume_real_val = float(tick['volume_real']) if 'volume_real' in tick.dtype.names else 0.0
                    flags_val = int(tick['flags'])
                elif isinstance(tick, dict):
                    # Dictionary access (fallback)
                    time_val = int(tick['time'])
                    time_msc_val = int(tick.get('time_msc', tick['time'] * 1000))
                    bid_val = float(tick['bid'])
                    ask_val = float(tick['ask'])
                    last_val = float(tick.get('last', tick['bid']))
                    volume_val = int(tick.get('volume', 0))
                    volume_real_val = float(tick.get('volume_real', 0))
                    flags_val = int(tick['flags'])
                else:
                    # Try attribute access as last resort
                    time_val = int(tick.time)
                    time_msc_val = int(getattr(tick, 'time_msc', tick.time * 1000))
                    bid_val = float(tick.bid)
                    ask_val = float(tick.ask)
                    last_val = float(getattr(tick, 'last', tick.bid))
                    volume_val = int(getattr(tick, 'volume', 0))
                    volume_real_val = float(getattr(tick, 'volume_real', 0))
                    flags_val = int(tick.flags)
                
                tick_dict = {
                    'time': time_val,
                    'time_msc': time_msc_val,
                    'bid': bid_val,
                    'ask': ask_val,
                    'last': last_val,
                    'volume': volume_val,
                    'volume_real': volume_real_val,
                    'flags': flags_val
                }
                
                # Basic validation - check bid/ask are valid and ask > bid
                bid = tick_dict['bid']
                ask = tick_dict['ask']
                if bid > 0 and ask > 0 and ask > bid:
                    validated.append(tick_dict)
                else:
                    # Collect samples of invalid ticks (first 5)
                    if len(invalid_samples) < 5:
                        invalid_samples.append({
                            'bid': bid,
                            'ask': ask,
                            'last': last_val,
                            'reason': 'bid<=0' if bid <= 0 else 'ask<=0' if ask <= 0 else 'ask<=bid' if ask <= bid else 'unknown'
                        })
                    
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                if len(invalid_samples) < 5:
                    invalid_samples.append({'error': str(e)})
                continue
        
        # Log invalid samples if all ticks were filtered
        if len(validated) == 0 and len(ticks) > 0 and invalid_samples:
            logger.warning(f"All {len(ticks)} ticks filtered out. Sample invalid ticks: {invalid_samples[:3]}")
        
        return validated
        
        return validated

