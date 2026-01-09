"""
DTMS Data Manager
Handles rolling windows, incremental data fetching, and caching for DTMS system
"""

import logging
import time
from collections import deque
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DTMSDataManager:
    """
    Manages rolling data windows and incremental fetching for DTMS.
    
    Features:
    - Rolling deques for M5 (600 bars) & M15 (300 bars) per symbol
    - Incremental bar fetching (last 4 M15, last 10 M5)
    - Session-cumulative VWAP tracking
    - Spread median tracking (30-day rolling window)
    - Data integrity checks
    """
    
    def __init__(self, mt5_service, binance_service=None):
        self.mt5_service = mt5_service
        self.binance_service = binance_service
        
        # Rolling data windows
        self.m5_data = {}  # symbol -> deque(maxlen=600)
        self.m15_data = {}  # symbol -> deque(maxlen=300)
        
        # VWAP tracking (session-cumulative)
        self.vwap_data = {}  # symbol -> {'sum_pv': float, 'sum_v': float, 'session_start': datetime}
        
        # Spread tracking
        self.spread_data = {}  # symbol -> deque(maxlen=720)  # 30 days * 24 hours
        
        # Data integrity
        self.last_bar_times = {}  # symbol -> {tf: timestamp}
        self.data_gaps = {}  # symbol -> list of gap periods
        
        # Cache for performance
        self.indicator_cache = {}  # symbol -> {indicator: (value, timestamp)}
        self.cache_ttl = {
            'rsi': 30,      # 30s for momentum indicators
            'atr': 60,      # 1min for volatility
            'vwap': 5,      # 5s for VWAP (real-time)
            'structure': 300  # 5min for structure (changes slowly)
        }
        
        logger.info("DTMSDataManager initialized")
    
    def initialize_symbol(self, symbol: str) -> bool:
        """Initialize data structures for a new symbol"""
        try:
            # Initialize rolling windows
            self.m5_data[symbol] = deque(maxlen=600)
            self.m15_data[symbol] = deque(maxlen=300)
            
            # Initialize VWAP tracking
            self.vwap_data[symbol] = {
                'sum_pv': 0.0,
                'sum_v': 0.0,
                'session_start': self._get_session_start(),
                'current_vwap': 0.0
            }
            
            # Initialize spread tracking
            self.spread_data[symbol] = deque(maxlen=720)
            
            # Initialize integrity tracking
            self.last_bar_times[symbol] = {'M5': 0, 'M15': 0}
            self.data_gaps[symbol] = []
            
            # Initialize cache
            self.indicator_cache[symbol] = {}
            
            # Backfill initial data
            self._backfill_initial_data(symbol)
            
            logger.info(f"Initialized DTMS data for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize {symbol}: {e}")
            return False
    
    def _backfill_initial_data(self, symbol: str):
        """Backfill initial data for a symbol"""
        try:
            # Backfill M5 data (600 bars = ~50 hours)
            m5_bars = self.mt5_service.get_bars(symbol, 'M5', 600)
            if m5_bars is not None and not m5_bars.empty:
                for _, bar in m5_bars.iterrows():
                    # Fix: Convert time to consistent format (Unix timestamp as int)
                    bar_time = bar['time']
                    if isinstance(bar_time, pd.Timestamp):
                        bar_time = int(bar_time.timestamp())
                    elif hasattr(bar_time, 'timestamp'):
                        bar_time = int(bar_time.timestamp())
                    else:
                        try:
                            bar_time = int(bar_time)
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid time format in backfill for {symbol}: {bar_time}")
                            continue
                    
                    self.m5_data[symbol].append({
                        'time': bar_time,
                        'open': float(bar['open']),
                        'high': float(bar['high']),
                        'low': float(bar['low']),
                        'close': float(bar['close']),
                        'volume': float(bar.get('volume', 0))
                    })
            
            # Backfill M15 data (300 bars = ~75 hours)
            m15_bars = self.mt5_service.get_bars(symbol, 'M15', 300)
            if m15_bars is not None and not m15_bars.empty:
                for _, bar in m15_bars.iterrows():
                    # Fix: Convert time to consistent format (Unix timestamp as int)
                    bar_time = bar['time']
                    if isinstance(bar_time, pd.Timestamp):
                        bar_time = int(bar_time.timestamp())
                    elif hasattr(bar_time, 'timestamp'):
                        bar_time = int(bar_time.timestamp())
                    else:
                        try:
                            bar_time = int(bar_time)
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid time format in backfill for {symbol}: {bar_time}")
                            continue
                    
                    self.m15_data[symbol].append({
                        'time': bar_time,
                        'open': float(bar['open']),
                        'high': float(bar['high']),
                        'low': float(bar['low']),
                        'close': float(bar['close']),
                        'volume': float(bar.get('volume', 0))
                    })
            
            # Initialize VWAP from backfilled data
            self._initialize_vwap(symbol)
            
            logger.info(f"Backfilled initial data for {symbol}: {len(self.m5_data[symbol])} M5, {len(self.m15_data[symbol])} M15")
            
        except Exception as e:
            logger.error(f"Failed to backfill {symbol}: {e}")
    
    def _initialize_vwap(self, symbol: str):
        """Initialize VWAP from backfilled data"""
        if symbol not in self.m5_data or not self.m5_data[symbol]:
            return
        
        vwap_data = self.vwap_data[symbol]
        session_start = vwap_data['session_start']
        
        # Calculate VWAP from current session
        sum_pv = 0.0
        sum_v = 0.0
        
        for bar in self.m5_data[symbol]:
            bar_time = pd.to_datetime(bar['time'], unit='s')
            if bar_time >= session_start:
                typical_price = (bar['high'] + bar['low'] + bar['close']) / 3
                sum_pv += typical_price * bar['volume']
                sum_v += bar['volume']
        
        vwap_data['sum_pv'] = sum_pv
        vwap_data['sum_v'] = sum_v
        vwap_data['current_vwap'] = sum_pv / sum_v if sum_v > 0 else 0.0
        
        # If no session data, use simple average of recent bars
        if vwap_data['current_vwap'] == 0.0 and self.m5_data[symbol]:
            recent_bars = list(self.m5_data[symbol])[-10:]  # Last 10 bars
            if recent_bars:
                typical_prices = [(bar['high'] + bar['low'] + bar['close']) / 3 for bar in recent_bars]
                vwap_data['current_vwap'] = sum(typical_prices) / len(typical_prices)
    
    def update_incremental_data(self, symbol: str, timeframe: str) -> bool:
        """Update data with incremental bars"""
        try:
            if timeframe == 'M5':
                return self._update_m5_data(symbol)
            elif timeframe == 'M15':
                return self._update_m15_data(symbol)
            else:
                logger.warning(f"Unsupported timeframe: {timeframe}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update {symbol} {timeframe}: {e}")
            return False
    
    def _update_m5_data(self, symbol: str) -> bool:
        """Update M5 data with last 10 bars"""
        try:
            # Fetch last 10 M5 bars
            new_bars = self.mt5_service.get_bars(symbol, 'M5', 10)
            if new_bars is None or new_bars.empty:
                return False
            
            # Check for data gaps
            self._check_data_gaps(symbol, 'M5', new_bars)
            
            # Add new bars to rolling window
            for _, bar in new_bars.iterrows():
                # Fix: Convert time to consistent format (Unix timestamp as int)
                bar_time = bar['time']
                if isinstance(bar_time, pd.Timestamp):
                    bar_time = int(bar_time.timestamp())
                elif hasattr(bar_time, 'timestamp'):
                    bar_time = int(bar_time.timestamp())
                else:
                    try:
                        bar_time = int(bar_time)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid time format for {symbol}: {bar_time}")
                        continue
                
                bar_data = {
                    'time': bar_time,
                    'open': float(bar['open']),
                    'high': float(bar['high']),
                    'low': float(bar['low']),
                    'close': float(bar['close']),
                    'volume': float(bar.get('volume', 0))
                }
                
                # Avoid duplicates - ensure both times are int for comparison
                if not self.m5_data[symbol]:
                    self.m5_data[symbol].append(bar_data)
                else:
                    last_time = self.m5_data[symbol][-1]['time']
                    # Ensure last_time is also int
                    if isinstance(last_time, (pd.Timestamp, datetime)):
                        last_time = int(last_time.timestamp() if hasattr(last_time, 'timestamp') else last_time)
                    elif not isinstance(last_time, (int, float)):
                        last_time = int(last_time)
                    
                    if bar_time > last_time:
                        self.m5_data[symbol].append(bar_data)
                    
                    # Update VWAP
                    self._update_vwap(symbol, bar_data)
            
            # Update last bar time (convert to int if Timestamp)
            if new_bars is not None and not new_bars.empty:
                last_time = new_bars.iloc[-1]['time']
                if isinstance(last_time, pd.Timestamp):
                    self.last_bar_times[symbol]['M5'] = int(last_time.timestamp())
                elif hasattr(last_time, 'timestamp'):
                    self.last_bar_times[symbol]['M5'] = int(last_time.timestamp())
                else:
                    self.last_bar_times[symbol]['M5'] = int(last_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update M5 data for {symbol}: {e}")
            return False
    
    def _update_m15_data(self, symbol: str) -> bool:
        """Update M15 data with last 4 bars"""
        try:
            # Fetch last 4 M15 bars
            new_bars = self.mt5_service.get_bars(symbol, 'M15', 4)
            if new_bars is None or new_bars.empty:
                return False
            
            # Check for data gaps
            self._check_data_gaps(symbol, 'M15', new_bars)
            
            # Add new bars to rolling window
            for _, bar in new_bars.iterrows():
                # Fix: Convert time to consistent format (Unix timestamp as int)
                bar_time = bar['time']
                if isinstance(bar_time, pd.Timestamp):
                    bar_time = int(bar_time.timestamp())
                elif hasattr(bar_time, 'timestamp'):
                    bar_time = int(bar_time.timestamp())
                else:
                    try:
                        bar_time = int(bar_time)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid time format for {symbol}: {bar_time}")
                        continue
                
                bar_data = {
                    'time': bar_time,
                    'open': float(bar['open']),
                    'high': float(bar['high']),
                    'low': float(bar['low']),
                    'close': float(bar['close']),
                    'volume': float(bar.get('volume', 0))
                }
                
                # Avoid duplicates - ensure both times are int for comparison
                if not self.m15_data[symbol]:
                    self.m15_data[symbol].append(bar_data)
                else:
                    last_time = self.m15_data[symbol][-1]['time']
                    # Ensure last_time is also int
                    if isinstance(last_time, (pd.Timestamp, datetime)):
                        last_time = int(last_time.timestamp() if hasattr(last_time, 'timestamp') else last_time)
                    elif not isinstance(last_time, (int, float)):
                        last_time = int(last_time)
                    
                    if bar_time > last_time:
                        self.m15_data[symbol].append(bar_data)
            
            # Update last bar time (convert to int if Timestamp)
            if new_bars is not None and not new_bars.empty:
                last_time = new_bars.iloc[-1]['time']
                if isinstance(last_time, pd.Timestamp):
                    self.last_bar_times[symbol]['M15'] = int(last_time.timestamp())
                elif hasattr(last_time, 'timestamp'):
                    self.last_bar_times[symbol]['M15'] = int(last_time.timestamp())
                else:
                    self.last_bar_times[symbol]['M15'] = int(last_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update M15 data for {symbol}: {e}")
            return False
    
    def _update_vwap(self, symbol: str, bar_data: Dict):
        """Update session VWAP with new bar"""
        if symbol not in self.vwap_data:
            return
        
        vwap_data = self.vwap_data[symbol]
        current_time = pd.to_datetime(bar_data['time'], unit='s')
        
        # Check if new session started
        if current_time.date() != vwap_data['session_start'].date():
            # Reset VWAP for new session
            vwap_data['sum_pv'] = 0.0
            vwap_data['sum_v'] = 0.0
            vwap_data['session_start'] = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Add bar to VWAP calculation
        typical_price = (bar_data['high'] + bar_data['low'] + bar_data['close']) / 3
        vwap_data['sum_pv'] += typical_price * bar_data['volume']
        vwap_data['sum_v'] += bar_data['volume']
        
        # Update current VWAP
        if vwap_data['sum_v'] > 0:
            vwap_data['current_vwap'] = vwap_data['sum_pv'] / vwap_data['sum_v']
    
    def _check_data_gaps(self, symbol: str, timeframe: str, new_bars: pd.DataFrame):
        """Check for data gaps and log them"""
        if new_bars is None or new_bars.empty:
            return
        
        last_known_time = self.last_bar_times[symbol].get(timeframe, 0)
        first_new_time_raw = new_bars.iloc[0]['time']
        
        # Convert first_new_time to int (Unix timestamp) for comparison
        if isinstance(first_new_time_raw, pd.Timestamp):
            first_new_time = int(first_new_time_raw.timestamp())
        elif hasattr(first_new_time_raw, 'timestamp'):
            first_new_time = int(first_new_time_raw.timestamp())
        else:
            try:
                first_new_time = int(first_new_time_raw)
            except (ValueError, TypeError):
                # Can't compare if we can't convert, skip gap check
                return
        
        # Ensure last_known_time is also int
        if not isinstance(last_known_time, (int, float)):
            if isinstance(last_known_time, pd.Timestamp):
                last_known_time = int(last_known_time.timestamp())
            elif hasattr(last_known_time, 'timestamp'):
                last_known_time = int(last_known_time.timestamp())
            else:
                try:
                    last_known_time = int(last_known_time)
                except (ValueError, TypeError):
                    last_known_time = 0
        
        # Check for gap (more than 2 bar periods)
        expected_interval = 300 if timeframe == 'M5' else 900  # 5min or 15min
        max_gap = expected_interval * 2
        
        if last_known_time > 0 and (first_new_time - last_known_time) > max_gap:
            gap_duration = first_new_time - last_known_time
            gap_info = {
                'symbol': symbol,
                'timeframe': timeframe,
                'gap_start': last_known_time,
                'gap_end': first_new_time,
                'duration_seconds': gap_duration
            }
            
            self.data_gaps[symbol].append(gap_info)
            logger.warning(f"Data gap detected: {symbol} {timeframe} - {gap_duration}s gap")
    
    def get_current_vwap(self, symbol: str) -> float:
        """Get current session VWAP"""
        if symbol not in self.vwap_data:
            return 0.0
        return self.vwap_data[symbol]['current_vwap']
    
    def get_vwap_slope(self, symbol: str, periods: int = 3) -> float:
        """Calculate VWAP slope over last N M5 periods"""
        if symbol not in self.m5_data or len(self.m5_data[symbol]) < periods:
            return 0.0
        
        # Get VWAP values for last N periods
        vwap_values = []
        for i in range(periods):
            if i < len(self.m5_data[symbol]):
                bar = self.m5_data[symbol][-(i+1)]
                typical_price = (bar['high'] + bar['low'] + bar['close']) / 3
                vwap_values.append(typical_price)
        
        if len(vwap_values) < 2:
            return 0.0
        
        # Calculate slope (newest - oldest) / oldest
        current_vwap = vwap_values[0]
        old_vwap = vwap_values[-1]
        
        if old_vwap == 0:
            return 0.0
        
        return (current_vwap - old_vwap) / old_vwap
    
    def get_spread_median(self, symbol: str, days: int = 30) -> float:
        """Get median spread over last N days"""
        if symbol not in self.spread_data or not self.spread_data[symbol]:
            return 0.0
        
        spreads = list(self.spread_data[symbol])
        if len(spreads) < 10:  # Need minimum data
            return 0.0
        
        return float(np.median(spreads))
    
    def update_spread(self, symbol: str, spread: float):
        """Update spread tracking"""
        if symbol not in self.spread_data:
            self.spread_data[symbol] = deque(maxlen=720)
        
        self.spread_data[symbol].append(spread)
    
    def get_cached_indicator(self, symbol: str, indicator: str) -> Optional[float]:
        """Get cached indicator value if fresh"""
        if symbol not in self.indicator_cache:
            return None
        
        value, timestamp = self.indicator_cache[symbol].get(indicator, (None, 0))
        ttl = self.cache_ttl.get(indicator, 60)
        
        if time.time() - timestamp < ttl:
            return value
        return None
    
    def cache_indicator(self, symbol: str, indicator: str, value: float):
        """Cache indicator value with timestamp"""
        if symbol not in self.indicator_cache:
            self.indicator_cache[symbol] = {}
        
        self.indicator_cache[symbol][indicator] = (value, time.time())
    
    def get_m5_dataframe(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get M5 data as DataFrame"""
        if symbol not in self.m5_data or not self.m5_data[symbol]:
            return None
        
        return pd.DataFrame(list(self.m5_data[symbol]))
    
    def get_m15_dataframe(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get M15 data as DataFrame"""
        if symbol not in self.m15_data or not self.m15_data[symbol]:
            return None
        
        return pd.DataFrame(list(self.m15_data[symbol]))
    
    def get_last_m5_bar(self, symbol: str) -> Optional[Dict]:
        """Get last M5 bar"""
        if symbol not in self.m5_data or not self.m5_data[symbol]:
            return None
        
        return self.m5_data[symbol][-1]
    
    def get_last_m15_bar(self, symbol: str) -> Optional[Dict]:
        """Get last M15 bar"""
        if symbol not in self.m15_data or not self.m15_data[symbol]:
            return None
        
        return self.m15_data[symbol][-1]
    
    def _get_session_start(self) -> datetime:
        """Get current session start time"""
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def get_data_health(self, symbol: str) -> Dict[str, Any]:
        """Get data health status for a symbol"""
        health = {
            'symbol': symbol,
            'm5_bars': len(self.m5_data.get(symbol, [])),
            'm15_bars': len(self.m15_data.get(symbol, [])),
            'data_gaps': len(self.data_gaps.get(symbol, [])),
            'last_m5_time': self.last_bar_times.get(symbol, {}).get('M5', 0),
            'last_m15_time': self.last_bar_times.get(symbol, {}).get('M15', 0),
            'vwap_current': self.get_current_vwap(symbol),
            'spread_median': self.get_spread_median(symbol)
        }
        
        # Check for stale data
        current_time = time.time()
        m5_age = current_time - health['last_m5_time'] if health['last_m5_time'] > 0 else 999
        m15_age = current_time - health['last_m15_time'] if health['last_m15_time'] > 0 else 999
        
        health['m5_stale'] = m5_age > 600  # 10 minutes
        health['m15_stale'] = m15_age > 1800  # 30 minutes
        
        return health
