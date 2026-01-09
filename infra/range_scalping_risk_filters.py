"""
Range Scalping Risk Filters
Pre-trade risk filters to prevent bad setups for range scalping strategies.

Implements:
- Data quality validation
- Weighted 3-Confluence Rule
- False range detection
- Range validity checks
- Session filters
- Trade activity criteria
- Nested range alignment
- Adaptive anchor refresh
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from infra.range_boundary_detector import RangeStructure, RangeBoundaryDetector
from infra.session_analyzer import SessionAnalyzer

logger = logging.getLogger(__name__)


class RangeScalpingRiskFilters:
    """
    Pre-trade risk filters to prevent bad setups.
    Implements the 3-Confluence Rule and all risk mitigation checks.
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        mt5_service=None,
        binance_service=None,
        order_flow_service=None,
        news_service=None,
        data_manager=None
    ):
        """
        Initialize risk filters.
        
        Args:
            config: Range scalping config dict
            mt5_service: Optional MT5 service for candle data
            binance_service: Optional Binance service for order flow
            order_flow_service: Optional order flow service
            news_service: Optional news service for calendar checks
            data_manager: Optional data manager for VWAP/indicator data
        """
        self.config = config
        self.mt5_service = mt5_service
        self.binance_service = binance_service
        self.order_flow_service = order_flow_service
        self.news_service = news_service
        self.data_manager = data_manager
        
        self.range_detector = RangeBoundaryDetector(config.get("range_detection", {}))
        self.session_analyzer = SessionAnalyzer()
        
        # Extract config sections
        self.entry_filters = config.get("entry_filters", {})
        self.risk_mitigation = config.get("risk_mitigation", {})
        self.range_invalidation = config.get("range_invalidation", {})
        self.false_range_detection = config.get("false_range_detection", {})
        self.broker_timezone = config.get("broker_timezone", {})
    
    @staticmethod
    def _is_crypto_symbol(symbol: str) -> bool:
        """
        Detect if symbol is cryptocurrency (24/7 trading).
        
        Crypto symbols typically:
        - Start with BTC, ETH, LTC, XRP, ADA, BNB, SOL, DOGE, etc.
        - Trade 24/7 (no weekend closure)
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc", "BTCUSD", "ETHUSDc")
        
        Returns:
            True if crypto (24/7), False if forex/other (has market hours)
        """
        symbol_upper = symbol.upper()
        # Remove common suffixes
        symbol_clean = symbol_upper.rstrip('C')
        
        # Common crypto prefixes
        crypto_prefixes = ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'BNB', 'SOL', 'DOGE', 'DOT', 'LINK', 'AVAX', 'MATIC']
        
        for prefix in crypto_prefixes:
            if symbol_clean.startswith(prefix):
                return True
        
        return False
    
    def check_data_quality(
        self,
        symbol: str,
        required_sources: List[str],
        use_cached_data: bool = False,
        vwap_value: Optional[float] = None  # If provided, assume it's fresh
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        🔴 CRITICAL: Check data quality before trading.
        
        Validates:
        - MT5 candle freshness (<2 min old)
        - VWAP recency (<5 min old)
        - Binance order flow availability (<30 min old, optional)
        - News calendar availability (<60 min old, optional)
        
        Returns: (all_available, quality_report, warnings)
        
        Fallback strategy:
        - Required sources (candles, VWAP): BLOCK_TRADE if stale
        - Optional sources (Binance, news): Use fallback (skip_confirmation, skip_news_check)
        """
        quality_report = {}
        warnings = []
        all_available = True
        
        # Check each required source
        for source in required_sources:
            is_fresh, age_minutes, details = False, float('inf'), {}
            
            if source == "mt5_candles":
                # Check M5 candles (primary timeframe for range scalping)
                # Note: max_age_minutes is overridden by timeframe-specific thresholds in _check_candle_freshness
                # M5 candles: Allow up to 5.5 min (5 min candle period + 0.5 min buffer for processing delay)
                is_fresh, age_minutes, details = self._check_candle_freshness(
                    symbol, 
                    max_age_minutes=30,  # Fallback (not used for M5 due to timeframe-specific threshold)
                    timeframe=mt5.TIMEFRAME_M5,
                    force_fresh=False  # Don't shutdown - use existing MT5Service connection
                )
                if not is_fresh:
                    all_available = False
                    if details.get("market_likely_closed"):
                        warnings.append(f"🚫 Market likely closed ({age_minutes:.1f} min old candles) - TRADING BLOCKED")
                    else:
                        warnings.append(f"❌ MT5 candles unavailable/stale ({age_minutes:.1f} min old) - BLOCKING TRADE")
            
            elif source == "vwap":
                # If VWAP is provided, assume it's freshly calculated and skip the check
                if vwap_value is not None and vwap_value > 0:
                    is_fresh = True
                    age_minutes = 0.0
                    details = {
                        "vwap_value": vwap_value,
                        "source": "pre_calculated_fresh",
                        "note": "VWAP provided from market_data (assumed fresh)"
                    }
                    logger.debug(f"✅ VWAP provided ({vwap_value:.2f}), assuming fresh")
                else:
                    is_fresh, age_minutes, details = self._check_vwap_recency(symbol, max_age_minutes=5)
                
                if not is_fresh:
                    all_available = False
                    warnings.append(f"❌ VWAP unavailable/stale ({age_minutes:.1f} min old) - BLOCKING TRADE")
            
            elif source == "binance_orderflow":
                is_fresh, age_minutes, details = self._check_binance_orderflow(symbol, max_age_minutes=30)
                if not is_fresh:
                    warnings.append(f"⚠️ Binance order flow unavailable/stale ({age_minutes:.1f} min old) - using fallback: skip_confirmation")
            
            elif source == "news_calendar":
                is_fresh, age_minutes, details = self._check_news_calendar(symbol, max_age_minutes=60)
                if not is_fresh:
                    warnings.append(f"⚠️ News calendar unavailable/stale ({age_minutes:.1f} min old) - using fallback: skip_news_check")
            
            quality_report[source] = {
                "available": is_fresh,
                "age_minutes": age_minutes,
                "required": source in ["mt5_candles", "vwap"],
                "fallback": "BLOCK_TRADE" if source in ["mt5_candles", "vwap"] else "skip_confirmation" if source == "binance_orderflow" else "skip_news_check",
                "details": details
            }
        
        return all_available, quality_report, warnings
    
    def _check_candle_freshness(
        self,
        symbol: str,
        max_age_minutes: int = 2,
        timeframe: int = mt5.TIMEFRAME_M5,
        force_fresh: bool = True
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Check if MT5 candles are fresh.
        
        PRIORITY: Use Multi-Timeframe Streamer if available (fresh data)
        FALLBACK: Direct MT5 fetch if streamer not available
        
        Note: MT5 only provides COMPLETED candles, not forming ones.
        For M5 candles, a 3-4 minute age is NORMAL during the 5-minute formation period.
        
        Example: At 12:43:15, the latest complete M5 candle is from 12:40:00 (age: 3.25 min) ✅
        """
        try:
            # Try to use Multi-Timeframe Streamer first (preferred - fresh data)
            try:
                from infra.streamer_data_access import get_streamer
                streamer = get_streamer()
                
                # Try reading from main_api.py's database if streamer is None or not running
                # main_api.py streamer has database enabled, so we can read from it
                if not streamer or not streamer.is_running:
                    # Try reading from shared database
                    # Use absolute path to avoid working directory issues
                    import os
                    base_dir = Path(__file__).parent.parent  # Go up from infra/ to project root
                    db_path = base_dir / "data" / "multi_tf_candles.db"
                    
                    logger.info(f"🔍 Checking main_api.py streamer database at: {db_path} (exists={db_path.exists()})")
                    
                    if db_path.exists():
                        try:
                            import sqlite3
                            # CRITICAL: Use WAL mode and ensure we see latest data
                            # Add timeout and isolation level to see uncommitted WAL data
                            conn = sqlite3.connect(
                                str(db_path), 
                                check_same_thread=False,
                                timeout=10.0,
                                isolation_level=None  # Autocommit mode for WAL
                            )
                            # Enable WAL mode if not already enabled
                            conn.execute("PRAGMA journal_mode=WAL")
                            # Ensure we can read uncommitted data from WAL
                            conn.execute("PRAGMA read_uncommitted=1")
                            conn.row_factory = sqlite3.Row
                            
                            # Map MT5 timeframe to string
                            tf_map = {
                                mt5.TIMEFRAME_M1: 'M1',
                                mt5.TIMEFRAME_M5: 'M5',
                                mt5.TIMEFRAME_M15: 'M15',
                                mt5.TIMEFRAME_M30: 'M30',
                                mt5.TIMEFRAME_H1: 'H1',
                                mt5.TIMEFRAME_H4: 'H4'
                            }
                            tf_string = tf_map.get(timeframe, 'M5')
                            
                            # Get latest candle from database (main_api.py's streamer writes here)
                            cursor = conn.cursor()
                            
                            # First, check what symbols/timeframes are in the database
                            cursor.execute("""
                                SELECT DISTINCT symbol, timeframe, COUNT(*) as count
                                FROM candles
                                GROUP BY symbol, timeframe
                                ORDER BY symbol, timeframe
                            """)
                            available_data = cursor.fetchall()
                            if available_data:
                                # Use tuple indexing (works for both tuples and Row objects)
                                db_info = [(row[0], row[1], row[2]) for row in available_data]
                                logger.info(f"📊 Database contains data for: {db_info}")
                            
                            # Check when database was last updated (check latest timestamp across all symbols/timeframes)
                            cursor.execute("""
                                SELECT MAX(timestamp) as last_update
                                FROM candles
                            """)
                            last_update_row = cursor.fetchone()
                            if last_update_row and last_update_row[0]:
                                last_update_ts = last_update_row[0]
                                last_update_dt = datetime.fromtimestamp(last_update_ts, tz=timezone.utc)
                                age_seconds = (datetime.now(timezone.utc) - last_update_dt).total_seconds()
                                age_minutes = age_seconds / 60
                                logger.debug(f"   Database last updated: {last_update_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} ({age_minutes:.1f} min ago)")
                                if age_minutes > 10:
                                    logger.warning(f"   ⚠️ Database appears stale - last update was {age_minutes:.1f} minutes ago")
                                    logger.warning(f"      Possible causes:")
                                    logger.warning(f"      1. main_api.py streamer not running or stopped")
                                    logger.warning(f"      2. Streamer refresh cycle delayed (M5 refresh: 240s = 4 min)")
                                    logger.warning(f"      3. Database write queue delayed (flush interval: 30s)")
                                    logger.warning(f"      4. No new candles available from MT5")
                            
                            # Now query for the specific symbol/timeframe
                            cursor.execute("""
                                SELECT timestamp, time_utc, open, high, low, close, volume, spread, real_volume
                                FROM candles
                                WHERE symbol = ? AND timeframe = ?
                                ORDER BY timestamp DESC
                                LIMIT 1
                            """, (symbol, tf_string))
                            
                            row = cursor.fetchone()
                            conn.close()
                            
                            if not row:
                                # Try to find the symbol with different casing or variations
                                logger.warning(f"⚠️ No data found for exact match: symbol={symbol}, timeframe={tf_string}")
                                logger.warning(f"   → Checking for similar symbols in database...")
                                # Re-open connection for diagnostic query
                                conn_diag = sqlite3.connect(str(db_path), check_same_thread=False)
                                conn_diag.row_factory = sqlite3.Row
                                cursor_diag = conn_diag.cursor()
                                cursor_diag.execute("""
                                    SELECT DISTINCT symbol, timeframe
                                    FROM candles
                                    WHERE timeframe = ?
                                    ORDER BY symbol
                                """, (tf_string,))
                                similar_symbols = cursor_diag.fetchall()
                                conn_diag.close()
                                if similar_symbols:
                                    # Use tuple indexing (works for both tuples and Row objects)
                                    logger.warning(f"   → Available symbols for {tf_string}: {[r[0] for r in similar_symbols]}")
                            
                            if row:
                                # Parse timestamp
                                candle_time = datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00'))
                                if candle_time.tzinfo is None:
                                    candle_time = candle_time.replace(tzinfo=timezone.utc)
                                
                                now_utc = datetime.now(timezone.utc)
                                age_seconds = (now_utc - candle_time).total_seconds()
                                age_minutes = age_seconds / 60
                                
                                # CRITICAL FIX: Handle negative age (candle timestamp in future)
                                if age_minutes < 0:
                                    logger.warning(
                                        f"⚠️ NEGATIVE CANDLE AGE DETECTED (database) for {symbol}: {age_minutes:.1f} min\n"
                                        f"   └─ Candle time: {candle_time.isoformat()}\n"
                                        f"   └─ Current time: {now_utc.isoformat()}\n"
                                        f"   └─ Possible causes: Database timestamp timezone issue\n"
                                        f"   └─ Action: Clamping age to 0 (treating as fresh)"
                                    )
                                    age_minutes = 0.0  # Clamp negative age to 0
                                    age_seconds = 0.0
                                
                                # Apply timeframe-specific threshold
                                # MT5 provides completed candles, so allow up to full period + 0.5 min buffer
                                tf_thresholds = {
                                    mt5.TIMEFRAME_M1: 1.5,   # M1: Allow up to 1.5 min (1 min period + 0.5 min buffer)
                                    mt5.TIMEFRAME_M5: 5.5,   # M5: Allow up to 5.5 min (5 min period + 0.5 min buffer)
                                    mt5.TIMEFRAME_M15: 15.5, # M15: Allow up to 15.5 min (15 min period + 0.5 min buffer)
                                    mt5.TIMEFRAME_H1: 60.5   # H1: Allow up to 60.5 min (60 min period + 0.5 min buffer)
                                }
                                effective_threshold = tf_thresholds.get(timeframe, max_age_minutes)
                                is_fresh = age_minutes <= effective_threshold
                                
                                # Check if market might be closed (for database path)
                                is_crypto = self._is_crypto_symbol(symbol)
                                market_likely_closed = not is_crypto and age_minutes > 360  # 6 hours (forex only)
                                
                                # If database data is stale, fetch fresh from MT5 immediately
                                if not is_fresh and not market_likely_closed:
                                    # Database data is stale - fetch fresh from MT5 immediately
                                    age_diff = age_minutes - effective_threshold
                                    logger.warning(
                                        f"⚠️ Could not read from main_api.py database ({db_path}): Database data stale: {age_minutes:.1f} min > {effective_threshold:.1f} min threshold, forcing immediate MT5 fetch, falling back to MT5"
                                    )
                                    logger.debug(
                                        f"   └─ Database candle age: {age_minutes:.2f} minutes\n"
                                        f"   └─ Freshness threshold: {effective_threshold:.2f} minutes\n"
                                        f"   └─ Age difference: +{age_diff:.2f} minutes (STALE)\n"
                                        f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                                        f"   └─ Current time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                                        f"   └─ Possible causes:\n"
                                        f"      1. main_api.py streamer not writing to database frequently enough\n"
                                        f"      2. Database write queue delayed (batch writes every 10 seconds)\n"
                                        f"      3. Streamer refresh cycle longer than expected\n"
                                        f"      4. Market closed or no new candles available\n"
                                        f"   └─ Action: Fetching fresh data from MT5 on-demand"
                                    )
                                    
                                    # Trigger immediate MT5 fetch (will happen in fallback section below)
                                    # Break out of database block to use MT5 fallback with immediate fetch
                                    raise ValueError(f"Database data stale: {age_minutes:.1f} min > {effective_threshold:.1f} min threshold, forcing immediate MT5 fetch")
                                
                                # Get candle count
                                conn2 = sqlite3.connect(str(db_path), check_same_thread=False)
                                conn2.row_factory = sqlite3.Row  # Enable column name access
                                cursor2 = conn2.cursor()
                                cursor2.execute("""
                                    SELECT COUNT(*) as count
                                    FROM candles
                                    WHERE symbol = ? AND timeframe = ?
                                """, (symbol, tf_string))
                                count_row = cursor2.fetchone()
                                candle_count = count_row[0] if count_row else 0  # COUNT(*) returns tuple, use index 0
                                conn2.close()
                                
                                min_candles = self.risk_mitigation.get("min_candles", 50)
                                has_enough = candle_count >= min_candles
                                
                                logger.info(
                                    f"✅ DATABASE DATA FRESH for {symbol} {tf_string}\n"
                                    f"   └─ Candle age: {age_minutes:.2f} minutes (threshold: {effective_threshold:.2f} min)\n"
                                    f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                                    f"   └─ Candle count: {candle_count} (min required: {min_candles})\n"
                                    f"   └─ Data source: main_api.py streamer database"
                                )
                                
                                return is_fresh and has_enough, age_minutes, {
                                    "candle_time": candle_time.isoformat(),
                                    "current_time_utc": now_utc.isoformat(),
                                    "candle_count": candle_count,
                                    "has_enough_candles": has_enough,
                                    "threshold_used": effective_threshold,
                                    "timeframe": timeframe,
                                    "data_source": "main_api_database",
                                    "is_fresh": is_fresh,
                                    "symbol_checked": symbol
                                }
                            else:
                                # Database exists but no data for this symbol/timeframe
                                logger.warning(f"⚠️ Database exists but no candles found for {symbol} {tf_string} in main_api.py database")
                        except Exception as db_error:
                            logger.warning(f"⚠️ Could not read from main_api.py database ({db_path}): {db_error}, falling back to MT5")
                            logger.debug(f"   Database path: {db_path}")
                            logger.debug(f"   Database exists: {db_path.exists()}")
                            if db_path.exists():
                                logger.debug(f"   Database size: {db_path.stat().st_size / 1024:.1f} KB")
                            logger.debug(f"   Error details: {type(db_error).__name__}: {str(db_error)}")
                    else:
                        # Database file doesn't exist
                        logger.info(f"ℹ️ main_api.py streamer database not found at {db_path}, will use MT5 fallback")
                
                # Use INFO level so we can see what's happening
                streamer_status = "None"
                if streamer is None:
                    streamer_status = "None (not initialized or set_streamer(None) was called)"
                    logger.info(f"🔍 Streamer check for {symbol}: streamer={streamer_status}")
                    logger.debug("   Reason: get_streamer() returned None")
                    logger.debug("   Possible causes:")
                    logger.debug("     1. Streamer not initialized in this process (desktop_agent sets it to None intentionally)")
                    logger.debug("     2. main_api.py streamer is in separate process, using database access instead")
                    logger.debug("     3. set_streamer(None) was called to rely on main_api.py database")
                elif not hasattr(streamer, 'is_running'):
                    streamer_status = f"Invalid (missing 'is_running' attribute)"
                    logger.info(f"🔍 Streamer check for {symbol}: streamer={streamer_status}")
                elif not streamer.is_running:
                    streamer_status = f"Not running (is_running=False)"
                    logger.info(f"🔍 Streamer check for {symbol}: streamer={streamer_status}")
                    logger.debug(f"   Streamer exists but is_running=False")
                    logger.debug("   Possible causes:")
                    logger.debug("     1. Streamer was stopped")
                    logger.debug("     2. Streamer failed to start")
                    logger.debug("     3. Streamer is in different process")
                else:
                    streamer_status = f"Running (is_running=True)"
                    logger.info(f"🔍 Streamer check for {symbol}: streamer={streamer_status}")
                
                if streamer and streamer.is_running:
                    # Map MT5 timeframe to string
                    tf_map = {
                        mt5.TIMEFRAME_M1: 'M1',
                        mt5.TIMEFRAME_M5: 'M5',
                        mt5.TIMEFRAME_M15: 'M15',
                        mt5.TIMEFRAME_M30: 'M30',
                        mt5.TIMEFRAME_H1: 'H1',
                        mt5.TIMEFRAME_H4: 'H4'
                    }
                    tf_string = tf_map.get(timeframe, 'M5')
                    
                    # Get latest candle from streamer
                    latest_candle = streamer.get_latest_candle(symbol, tf_string)
                    
                    logger.info(f"🔍 Streamer get_latest_candle for {symbol} {tf_string}: {latest_candle}")
                    if latest_candle is None:
                        logger.warning(f"⚠️ Streamer returned None for {symbol} {tf_string} - checking if symbol is in streamer buffers...")
                        # Check what symbols/timeframes are available
                        if hasattr(streamer, 'buffers'):
                            available_symbols = list(streamer.buffers.keys())
                            logger.warning(f"   Available symbols in streamer: {available_symbols}")
                            if symbol in streamer.buffers:
                                available_tfs = list(streamer.buffers[symbol].keys())
                                logger.warning(f"   Available timeframes for {symbol}: {available_tfs}")
                    
                    if latest_candle:
                        # Convert Candle object to datetime
                        try:
                            if hasattr(latest_candle, 'time'):
                                candle_time = latest_candle.time
                            elif isinstance(latest_candle, dict):
                                candle_time_str = latest_candle.get('time')
                                if isinstance(candle_time_str, str):
                                    candle_time = datetime.fromisoformat(candle_time_str.replace('Z', '+00:00'))
                                else:
                                    candle_time = datetime.fromtimestamp(candle_time_str, tz=timezone.utc)
                            else:
                                raise ValueError(f"Unexpected candle format: {type(latest_candle)}")
                        except Exception as convert_error:
                            logger.warning(f"⚠️ Failed to convert candle time: {convert_error}, falling back to MT5")
                            raise convert_error
                        
                        # Ensure UTC-aware
                        if candle_time.tzinfo is None:
                            candle_time = candle_time.replace(tzinfo=timezone.utc)
                        
                        now_utc = datetime.now(timezone.utc)
                        age_seconds = (now_utc - candle_time).total_seconds()
                        age_minutes = age_seconds / 60
                        
                        # CRITICAL FIX: Handle negative age (candle timestamp in future)
                        if age_minutes < 0:
                            logger.warning(
                                f"⚠️ NEGATIVE CANDLE AGE DETECTED (streamer) for {symbol}: {age_minutes:.1f} min\n"
                                f"   └─ Candle time: {candle_time.isoformat()}\n"
                                f"   └─ Current time: {now_utc.isoformat()}\n"
                                f"   └─ Possible causes: Timezone mismatch or clock sync issue\n"
                                f"   └─ Action: Clamping age to 0 (treating as fresh)"
                            )
                            age_minutes = 0.0  # Clamp negative age to 0
                            age_seconds = 0.0
                        
                        # Check if market might be closed (for streamer path)
                        # Crypto symbols trade 24/7, so don't assume market closure for stale data
                        is_crypto = self._is_crypto_symbol(symbol)
                        market_likely_closed = not is_crypto and age_minutes > 360  # 6 hours (forex only)
                        
                        # Get enough candles count from streamer
                        min_candles = self.risk_mitigation.get("min_candles", 50)
                        all_candles = streamer.get_candles(symbol, tf_string, limit=min_candles)
                        has_enough = len(all_candles) >= min_candles
                        
                        # Apply timeframe-specific threshold
                        # MT5 provides completed candles, so allow up to full period + 0.5 min buffer
                        tf_thresholds = {
                            mt5.TIMEFRAME_M1: 1.5,   # M1: Allow up to 1.5 min (1 min period + 0.5 min buffer)
                            mt5.TIMEFRAME_M5: 5.5,   # M5: Allow up to 5.5 min (5 min period + 0.5 min buffer)
                            mt5.TIMEFRAME_M15: 15.5, # M15: Allow up to 15.5 min (15 min period + 0.5 min buffer)
                            mt5.TIMEFRAME_H1: 60.5   # H1: Allow up to 60.5 min (60 min period + 0.5 min buffer)
                        }
                        effective_threshold = tf_thresholds.get(timeframe, max_age_minutes)
                        is_fresh = age_minutes <= effective_threshold
                        
                        # OPTION C: If streamer data is stale, fetch immediately from MT5 (on-demand refresh)
                        if not is_fresh and not market_likely_closed:
                            # Streamer data is stale - fetch fresh from MT5 immediately
                            age_diff = age_minutes - effective_threshold
                            logger.warning(
                                f"🔄 STREAMER FALLBACK TRIGGERED for {symbol} {tf_string}\n"
                                f"   └─ Streamer candle age: {age_minutes:.2f} minutes\n"
                                f"   └─ Freshness threshold: {effective_threshold:.2f} minutes\n"
                                f"   └─ Age difference: +{age_diff:.2f} minutes (STALE)\n"
                                f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                                f"   └─ Current time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                                f"   └─ Action: Fetching fresh data from MT5 on-demand"
                            )
                            
                            # Trigger immediate MT5 fetch (will happen in fallback section below)
                            # Break out of streamer block to use MT5 fallback with immediate fetch
                            raise ValueError(f"Streamer data stale: {age_minutes:.1f} min > {effective_threshold:.1f} min threshold, forcing immediate MT5 fetch")
                        
                        logger.info(
                            f"✅ STREAMER DATA FRESH for {symbol} {tf_string}\n"
                            f"   └─ Candle age: {age_minutes:.2f} minutes (threshold: {effective_threshold:.2f} min)\n"
                            f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                            f"   └─ Candle count: {len(all_candles)} (min required: {min_candles})\n"
                            f"   └─ Data source: Multi-Timeframe Streamer (RAM buffer)"
                        )
                        
                        return is_fresh and has_enough, age_minutes, {
                            "candle_time": candle_time.isoformat(),
                            "current_time_utc": now_utc.isoformat(),
                            "candle_count": len(all_candles),
                            "has_enough_candles": has_enough,
                            "threshold_used": effective_threshold,
                            "timeframe": timeframe,
                            "data_source": "streamer",
                            "is_fresh": is_fresh,
                            "symbol_checked": symbol
                        }
                    else:
                        logger.warning(f"⚠️ Streamer returned None for {symbol} {tf_string} - no candles available, falling back to MT5")
            except Exception as streamer_error:
                logger.warning(f"⚠️ Streamer exception for {symbol}, falling back to direct MT5: {streamer_error}", exc_info=True)
            except Exception as outer_error:
                # Catch any other exceptions in streamer block
                logger.error(f"❌ Unexpected error in streamer block for {symbol}: {outer_error}", exc_info=True)
            
            # FALLBACK: Direct MT5 fetch (with on-demand refresh capability)
            # Convert timeframe constant to readable string for logging
            tf_map = {
                mt5.TIMEFRAME_M1: "M1",
                mt5.TIMEFRAME_M5: "M5",
                mt5.TIMEFRAME_M15: "M15",
                mt5.TIMEFRAME_M30: "M30",
                mt5.TIMEFRAME_H1: "H1",
                mt5.TIMEFRAME_H4: "H4"
            }
            tf_string = tf_map.get(timeframe, f"TF{timeframe}")
            
            # Determine fallback reason
            fallback_reason = "unknown"
            try:
                # Check if we have a ValueError with stale data message
                import sys
                if hasattr(sys, 'last_value') and isinstance(sys.last_value, ValueError):
                    error_msg = str(sys.last_value)
                    if "stale" in error_msg.lower():
                        if "database" in error_msg.lower():
                            fallback_reason = "database_data_stale"
                        elif "streamer" in error_msg.lower():
                            fallback_reason = "streamer_data_stale"
                    elif "none" in error_msg.lower() or "not found" in error_msg.lower():
                        fallback_reason = "streamer_unavailable"
            except:
                pass
            
            logger.info(
                f"🔄 MT5 FALLBACK ACTIVATED for {symbol} {tf_string}\n"
                f"   └─ Reason: {fallback_reason}\n"
                f"   └─ Action: Fetching fresh data directly from MT5\n"
                f"   └─ This ensures latest candle data even if streamer/database is behind"
            )
            
            # Adjust threshold based on timeframe period
            # MT5 returns completed candles, so allow up to full period + 0.5 min buffer
            # This accounts for:
            # 1. Candle formation period (e.g., M5 candle completes at 5.0 min)
            # 2. Small network/processing delay (0.5 min buffer)
            tf_thresholds = {
                mt5.TIMEFRAME_M1: 1.5,   # M1: Allow up to 1.5 min (1 min period + 0.5 min buffer)
                mt5.TIMEFRAME_M5: 5.5,   # M5: Allow up to 5.5 min (5 min period + 0.5 min buffer)
                mt5.TIMEFRAME_M15: 15.5, # M15: Allow up to 15.5 min (15 min period + 0.5 min buffer)
                mt5.TIMEFRAME_H1: 60.5   # H1: Allow up to 60.5 min (60 min period + 0.5 min buffer)
            }
            
            # Use timeframe-specific threshold, fallback to provided max_age_minutes
            effective_threshold = tf_thresholds.get(timeframe, max_age_minutes)
            
            # Ensure MT5 is initialized and connected
            # NOTE: Don't call mt5.shutdown() - it breaks existing MT5Service connections!
            # Use MT5Service if available, otherwise check/initialize MT5 directly
            mt5_initialized = False
            
            # Try using MT5Service first if available
            if self.mt5_service:
                try:
                    if self.mt5_service.connect():
                        mt5_initialized = True
                        logger.debug(f"✅ MT5Service connection active")
                except Exception as svc_error:
                    logger.warning(f"⚠️ MT5Service.connect() failed: {svc_error}, trying direct MT5")
            
            # Fallback to direct MT5 initialization
            if not mt5_initialized:
                try:
                    # Check if MT5 is already initialized by checking terminal_info
                    terminal_info = mt5.terminal_info()
                    if terminal_info and terminal_info.connected:
                        mt5_initialized = True
                        logger.debug(f"✅ MT5 already initialized and connected")
                except:
                    pass
                
                if not mt5_initialized:
                    if not mt5.initialize():
                        error = mt5.last_error()
                        logger.error(f"❌ MT5 initialization failed for {symbol}: {error}")
                        logger.error(f"   → This is why candles show as 'inf min old' - MT5 not initialized")
                        return False, float('inf'), {"error": f"MT5 initialization failed: {error}", "stage": "initialization"}
                    else:
                        logger.info(f"✅ MT5 initialized successfully for {symbol}")
            
            # Ensure symbol exists and is visible/selected in Market Watch
            # NOTE: This MUST happen BEFORE fetching data to avoid stale candles
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} does not exist in MT5")
                return False, float('inf'), {"error": f"Symbol {symbol} does not exist in MT5"}
            
            # Store initial selection status for diagnostics
            initial_selected = symbol_info.select if symbol_info else False
            initial_visible = symbol_info.visible if symbol_info else False
            
            # Check if symbol needs to be selected
            symbol_needs_selection = False
            if not symbol_info.visible:
                logger.warning(f"Symbol {symbol} exists but not visible - attempting to make visible and select")
                symbol_needs_selection = True
            elif not symbol_info.select:
                logger.debug(f"Symbol {symbol} visible but not selected - selecting now")
                symbol_needs_selection = True
            
            # Attempt to select symbol if needed
            select_result = False
            if symbol_needs_selection:
                select_result = mt5.symbol_select(symbol, True)
                if not select_result:
                    logger.error(f"❌ Failed to select symbol {symbol} in Market Watch - data may be stale")
                    logger.error(f"   → MT5 error: {mt5.last_error()}")
                    # Don't return error immediately - try to fetch anyway, but log warning
                else:
                    logger.info(f"✅ Successfully selected symbol {symbol} in Market Watch")
                    # CRITICAL: Wait for MT5 to refresh symbol data after selection
                    # MT5 may return cached/stale data immediately after selection
                    import time
                    time.sleep(1.0)  # Give MT5 1 second to refresh symbol data
            
            # Double-check selection status after attempt (refresh symbol_info)
            symbol_info_check = mt5.symbol_info(symbol)
            is_selected = symbol_info_check.select if symbol_info_check else False
            
            if not is_selected:
                logger.warning(f"⚠️ Symbol {symbol} still not selected in Market Watch after attempt")
                logger.warning(f"   → Initial state: visible={initial_visible}, selected={initial_selected}")
                logger.warning(f"   → After select() call: visible={symbol_info_check.visible if symbol_info_check else False}, selected={is_selected}")
                logger.warning(f"   → select() returned: {select_result}")
                logger.warning(f"   → Candle data may be stale if symbol not in Market Watch")
            
            # CRITICAL: Force MT5 to refresh symbol data before fetching candles
            # Sometimes MT5 returns cached data even after symbol selection
            # Try refreshing symbol info to force data update
            try:
                # Request symbol info again to force refresh
                mt5.symbol_info(symbol)
                # Small delay to allow MT5 to update
                import time
                time.sleep(0.5)
            except Exception as refresh_error:
                logger.debug(f"Symbol refresh attempt failed (non-critical): {refresh_error}")
            
            # Get latest completed candle AND enough candles for count check
            # Use copy_rates_from_pos with explicit fresh fetch
            min_candles = self.risk_mitigation.get("min_candles", 50)
            
            # Try fetching with current time to force fresh data
            # If copy_rates_from_pos returns stale data, try copy_rates_from with recent timestamp
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, max(50, min_candles))
            
            # If we got data but it's suspiciously old, try forcing a fresh fetch
            now_utc = datetime.now(timezone.utc)
            if rates is not None and len(rates) > 0:
                # FIX: copy_rates_from_pos returns oldest first, newest last
                # Use rates[-1] for the latest (newest) candle, not rates[0]
                latest_candle_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
                if latest_candle_time.tzinfo is None:
                    latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)
                age_minutes = (now_utc - latest_candle_time).total_seconds() / 60
                
                # If candle is more than 15 minutes old (suspicious for M5), try fresh fetch
                if age_minutes > 15:
                    logger.warning(
                        f"⚠️ MT5 returned suspiciously old candle ({age_minutes:.1f} min old) - "
                        f"attempting fresh fetch with copy_rates_from"
                    )
                    
                    # Try multiple strategies to get fresh data
                    fresh_rates = None
                    best_age = age_minutes
                    
                    # Strategy 1: Fetch from last 30 minutes
                    try:
                        from_timestamp = int((now_utc - timedelta(minutes=30)).timestamp())
                        fresh_rates_1 = mt5.copy_rates_from(symbol, timeframe, from_timestamp, max(50, min_candles))
                        if fresh_rates_1 is not None and len(fresh_rates_1) > 0:
                            # FIX: Use [-1] for newest candle
                            fresh_latest_time = datetime.fromtimestamp(fresh_rates_1[-1]['time'], tz=timezone.utc)
                            if fresh_latest_time.tzinfo is None:
                                fresh_latest_time = fresh_latest_time.replace(tzinfo=timezone.utc)
                            fresh_age = (now_utc - fresh_latest_time).total_seconds() / 60
                            if fresh_age < best_age:
                                fresh_rates = fresh_rates_1
                                best_age = fresh_age
                                logger.info(f"   → Strategy 1 (30min): {fresh_age:.1f} min old")
                    except Exception as e:
                        logger.debug(f"   → Strategy 1 failed: {e}")
                    
                    # Strategy 2: Fetch from last 60 minutes (wider range)
                    if best_age > 10:
                        try:
                            from_timestamp = int((now_utc - timedelta(minutes=60)).timestamp())
                            fresh_rates_2 = mt5.copy_rates_from(symbol, timeframe, from_timestamp, max(50, min_candles))
                            if fresh_rates_2 is not None and len(fresh_rates_2) > 0:
                                # FIX: Use [-1] for newest candle
                                fresh_latest_time = datetime.fromtimestamp(fresh_rates_2[-1]['time'], tz=timezone.utc)
                                if fresh_latest_time.tzinfo is None:
                                    fresh_latest_time = fresh_latest_time.replace(tzinfo=timezone.utc)
                                fresh_age = (now_utc - fresh_latest_time).total_seconds() / 60
                                if fresh_age < best_age:
                                    fresh_rates = fresh_rates_2
                                    best_age = fresh_age
                                    logger.info(f"   → Strategy 2 (60min): {fresh_age:.1f} min old")
                        except Exception as e:
                            logger.debug(f"   → Strategy 2 failed: {e}")
                    
                    # Strategy 3: Try copy_rates_from_pos with larger offset (skip cached data)
                    if best_age > 10:
                        try:
                            # Try fetching from position 1 instead of 0 (skip most recent, might be cached)
                            fresh_rates_3 = mt5.copy_rates_from_pos(symbol, timeframe, 1, max(50, min_candles))
                            if fresh_rates_3 is not None and len(fresh_rates_3) > 0:
                                # FIX: Use [-1] for newest candle
                                fresh_latest_time = datetime.fromtimestamp(fresh_rates_3[-1]['time'], tz=timezone.utc)
                                if fresh_latest_time.tzinfo is None:
                                    fresh_latest_time = fresh_latest_time.replace(tzinfo=timezone.utc)
                                fresh_age = (now_utc - fresh_latest_time).total_seconds() / 60
                                if fresh_age < best_age:
                                    fresh_rates = fresh_rates_3
                                    best_age = fresh_age
                                    logger.info(f"   → Strategy 3 (pos=1): {fresh_age:.1f} min old")
                        except Exception as e:
                            logger.debug(f"   → Strategy 3 failed: {e}")
                    
                    if fresh_rates is not None and best_age < age_minutes:
                        logger.info(
                            f"✅ Fresh fetch successful: {best_age:.1f} min old (was {age_minutes:.1f} min) - "
                            f"using fresh data"
                        )
                        rates = fresh_rates
                    else:
                        logger.error(
                            f"❌ All fresh fetch strategies failed - MT5 is returning stale data ({best_age:.1f} min old)\n"
                            f"   → This indicates MT5 is not receiving fresh data from broker\n"
                            f"   → Possible causes: Broker connection issue, market closed, or symbol not subscribed"
                        )
            
            if rates is None or len(rates) == 0:
                error = mt5.last_error()
                logger.error(f"❌ No candles from MT5 for {symbol} {timeframe}: error={error}, last_error_code={mt5.last_error()[0] if isinstance(mt5.last_error(), tuple) else 'unknown'}")
                
                # Try to diagnose the issue
                if not mt5.terminal_info():
                    logger.error(f"   → MT5 terminal not connected!")
                else:
                    terminal_info = mt5.terminal_info()
                    logger.error(f"   → MT5 terminal connected: {terminal_info.connected}, build={terminal_info.build}")
                
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    logger.error(f"   → Symbol {symbol} exists: visible={symbol_info.visible}, select={symbol_info.select}")
                else:
                    logger.error(f"   → Symbol {symbol} does not exist in MT5!")
                
                return False, float('inf'), {"error": f"No candles available: {error}"}
            
            # FIX: copy_rates_from_pos returns oldest first, newest last
            # Use rates[-1] for the latest (newest) candle, not rates[0]
            latest_candle = rates[-1]
            # CRITICAL FIX: MT5 timestamps are UTC, must use tz=timezone.utc
            # Without this, fromtimestamp interprets as local time, causing negative age
            candle_time = datetime.fromtimestamp(latest_candle['time'], tz=timezone.utc)
            
            # Log for debugging
            logger.debug(f"Candle freshness check for {symbol}: latest candle time={candle_time}, count={len(rates)}")
            
            # Already UTC-aware from fromtimestamp with tz parameter
            
            now_utc = datetime.now(timezone.utc)
            age_seconds = (now_utc - candle_time).total_seconds()
            age_minutes = age_seconds / 60
            
            # CRITICAL FIX: Handle negative age (candle timestamp in future)
            # This indicates timezone/clock sync issue - clamp to 0 and log warning
            if age_minutes < 0:
                logger.warning(
                    f"⚠️ NEGATIVE CANDLE AGE DETECTED for {symbol}: {age_minutes:.1f} min\n"
                    f"   └─ Candle time: {candle_time.isoformat()}\n"
                    f"   └─ Current time: {now_utc.isoformat()}\n"
                    f"   └─ Time difference: {age_seconds:.0f} seconds (candle in future)\n"
                    f"   └─ Possible causes:\n"
                    f"      1. MT5 server time ahead of system time\n"
                    f"      2. Timezone mismatch in timestamp parsing\n"
                    f"      3. Clock synchronization issue\n"
                    f"   └─ Action: Clamping age to 0 (treating as fresh) and continuing"
                )
                age_minutes = 0.0  # Clamp negative age to 0 (treat as fresh)
                age_seconds = 0.0
            
            # Enhanced diagnostics for stale data investigation
            if age_minutes > 10:
                tick = mt5.symbol_info_tick(symbol)
                mt5_server_time = datetime.fromtimestamp(tick.time, tz=timezone.utc) if tick else None
                terminal_info = mt5.terminal_info()
                
                # Get terminal info (without time - TerminalInfo doesn't have time attribute)
                terminal_name = terminal_info.name if terminal_info else None
                terminal_connected = terminal_info.connected if terminal_info else False
                
                # Check tick data freshness
                tick_age = None
                if tick:
                    tick_time = datetime.fromtimestamp(tick.time, tz=timezone.utc)
                    tick_age = (now_utc - tick_time).total_seconds() / 60
                
                logger.warning(
                    f"🔍 DIAGNOSTIC - Stale candle detected for {symbol}:\n"
                    f"  Latest candle time: {candle_time.isoformat()}\n"
                    f"  Current UTC time: {now_utc.isoformat()}\n"
                    f"  Candle age: {age_minutes:.1f} minutes ({age_seconds:.0f} seconds)\n"
                    f"  MT5 server time (from tick): {mt5_server_time.isoformat() if mt5_server_time else 'N/A'}\n"
                    f"  Tick data age: {tick_age:.1f} min" if tick_age is not None else "  Tick data: N/A"
                    f"  MT5 terminal: {terminal_name if terminal_name else 'Unknown'}, connected={terminal_connected}\n"
                    f"  Symbol in Market Watch: {is_selected} (checked after selection attempt)\n"
                    f"  Symbol visible: {symbol_info_check.visible if symbol_info_check else False}\n"
                    f"  Checking if this is data fetch or storage issue..."
                )
                
                # Check if MT5 server time (from tick) matches local time (timezone check)
                if mt5_server_time:
                    server_time_diff = (now_utc - mt5_server_time).total_seconds() / 60
                    if abs(server_time_diff) > 5:
                        logger.warning(
                            f"⚠️ TIMEZONE MISMATCH: MT5 server time differs from local UTC by {server_time_diff:.1f} minutes. "
                            f"This may cause incorrect age calculation!"
                        )
                
                # Check if tick data is also stale (indicates broker connection issue)
                if tick_age is not None and tick_age > 5:
                    logger.error(
                        f"❌ CRITICAL: Tick data is also stale ({tick_age:.1f} min old) - "
                        f"MT5 is not receiving fresh data from broker!\n"
                        f"   → This indicates a broker connection issue, not a code problem\n"
                        f"   → Check: MT5 terminal connection, broker server status, symbol subscription"
                    )
                elif tick_age is not None and tick_age <= 5:
                    logger.warning(
                        f"⚠️ Tick data is fresh ({tick_age:.1f} min old) but candles are stale ({age_minutes:.1f} min old)\n"
                        f"   → This suggests MT5 is receiving ticks but not forming new candles\n"
                        f"   → Possible causes: Market closed, low volume, or MT5 candle formation delay"
                    )
            
            # Check if market might be closed (candle age > 6 hours = 360 min)
            # Crypto symbols trade 24/7, so don't assume market closure for stale data
            # Only apply market closure logic to forex/other symbols (not crypto)
            is_crypto = self._is_crypto_symbol(symbol)
            market_likely_closed = not is_crypto and age_minutes > 360  # 6 hours (forex only)
            
            # Check freshness (primary check)
            if market_likely_closed:
                # Market likely closed (forex) - BLOCK TRADES (don't allow trading with stale data)
                logger.warning(
                    f"🚫 Market likely closed for {symbol}: candle age {age_minutes:.1f} min (>6h). "
                    f"TRADING BLOCKED - Market must be open for range scalping."
                )
                is_fresh = False  # Block trades if market closed
            elif not is_crypto and age_minutes > 360:
                # Forex symbol with very old data (>6h) - likely market closure
                logger.warning(
                    f"⚠️ Very old candles for {symbol} ({age_minutes:.1f} min) - Market may be closed. "
                    f"TRADING BLOCKED until fresh data available."
                )
                is_fresh = False
            else:
                # Check against timeframe-specific threshold
                is_fresh = age_minutes <= effective_threshold
                
                # Log final result with detailed information
                if is_fresh:
                    logger.info(
                        f"✅ MT5 FALLBACK SUCCESS for {symbol} {tf_string}\n"
                        f"   └─ Candle age: {age_minutes:.2f} minutes (threshold: {effective_threshold:.2f} min)\n"
                        f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                        f"   └─ Candle count: {len(rates)} (min required: {min_candles})\n"
                        f"   └─ Data source: Direct MT5 fetch (on-demand refresh)\n"
                        f"   └─ Status: FRESH - Ready for trading"
                    )
                else:
                    age_diff = age_minutes - effective_threshold
                    logger.warning(
                        f"⚠️ MT5 FALLBACK - STALE DATA for {symbol} {tf_string}\n"
                        f"   └─ Candle age: {age_minutes:.2f} minutes (threshold: {effective_threshold:.2f} min)\n"
                        f"   └─ Age difference: +{age_diff:.2f} minutes (STALE)\n"
                        f"   └─ Candle time: {candle_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                        f"   └─ Current time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                        f"   └─ Data source: Direct MT5 fetch\n"
                        f"   └─ Status: STALE - Trading may be blocked\n"
                        f"   └─ Note: This is the freshest available from MT5 (market may be slow/closed)"
                    )
            
            # Check if we have enough historical candles (secondary check)
            has_enough = len(rates) >= min_candles if isinstance(rates, (list, tuple)) else False
            
            # ALWAYS require both fresh AND has_enough (no exceptions for market closed)
            # Market closed = stale data = BLOCK TRADES
            final_check = is_fresh and has_enough
            
            # OPTION C: Trigger async streamer update (if available) - don't wait for it
            # This helps keep streamer data fresh for next request
            if not market_likely_closed and has_enough:
                try:
                    from infra.streamer_data_access import get_streamer
                    streamer = get_streamer()
                    if streamer and streamer.is_running:
                        # Note: Streamer will pick up new candles in its next refresh cycle
                        # We're just ensuring it knows we fetched fresh data
                        logger.debug(f"📡 On-demand MT5 fetch completed for {symbol} {tf_string} (streamer will update on next cycle)")
                except Exception:
                    pass  # Ignore errors - streamer update is optional
            
            return final_check, age_minutes, {
                "candle_time": candle_time.isoformat(),
                "current_time_utc": now_utc.isoformat(),
                "candle_count": len(rates) if isinstance(rates, (list, tuple)) else 1,
                "has_enough_candles": has_enough,
                "threshold_used": effective_threshold,
                "timeframe": timeframe,
                "market_likely_closed": market_likely_closed,
                "is_fresh": is_fresh,
                "data_source": "mt5_direct_on_demand",
                "symbol_checked": symbol
            }
        except Exception as e:
            logger.error(f"Error checking candle freshness: {e}")
            return False, float('inf'), {"error": str(e)}
    
    def _check_vwap_recency(
        self,
        symbol: str,
        max_age_minutes: int = 5
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Check if VWAP calculation is recent"""
        try:
            # Try data manager first
            if self.data_manager:
                vwap = self.data_manager.get_current_vwap(symbol)
                if vwap > 0:
                    # VWAP is available, assume it's updated regularly
                    # TODO: Track actual VWAP update timestamp if available
                    return True, 0.0, {
                        "vwap_value": vwap,
                        "source": "data_manager"
                    }
            
            # Fallback: Try streamer first, then direct MT5
            rates = None
            
            # Try streamer first
            try:
                from infra.streamer_data_access import get_streamer
                streamer = get_streamer()
                
                if streamer and streamer.is_running:
                    candles = streamer.get_candles(symbol, 'M5', limit=20)
                    if candles:
                        # Convert Candle objects to rate-like format
                        rates = []
                        for candle in candles:
                            if hasattr(candle, 'time'):
                                candle_time = candle.time
                                rates.append({
                                    'time': int(candle_time.timestamp()),
                                    'high': candle.high,
                                    'low': candle.low,
                                    'close': candle.close,
                                    'tick_volume': candle.volume
                                })
                        logger.debug(f"✅ Used streamer for VWAP calculation: {len(rates)} candles")
            except Exception as e:
                logger.debug(f"Streamer not available for VWAP, using MT5: {e}")
            
            # Fallback to direct MT5
            if not rates:
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 20)
            
            if rates is None or len(rates) == 0:
                return False, float('inf'), {"error": "No candles for VWAP calculation"}
            
            # Calculate VWAP from last 20 M5 candles
            typical_prices = [(r['high'] + r['low'] + r['close']) / 3 for r in rates]
            volumes = [r['tick_volume'] for r in rates]
            vwap = sum(tp * v for tp, v in zip(typical_prices, volumes)) / sum(volumes) if sum(volumes) > 0 else 0
            
            if vwap > 0:
                # Use latest candle time as proxy for VWAP age
                # CRITICAL FIX: MT5 timestamps are UTC, must use tz=timezone.utc
                latest_time = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                age_seconds = (now_utc - latest_time).total_seconds()
                age_minutes = age_seconds / 60
                
                # CRITICAL FIX: Handle negative age (candle timestamp in future)
                if age_minutes < 0:
                    logger.warning(
                        f"⚠️ NEGATIVE CANDLE AGE DETECTED (VWAP check) for {symbol}: {age_minutes:.1f} min\n"
                        f"   └─ Candle time: {latest_time.isoformat()}\n"
                        f"   └─ Current time: {now_utc.isoformat()}\n"
                        f"   └─ Action: Clamping age to 0 (treating as fresh)"
                    )
                    age_minutes = 0.0  # Clamp negative age to 0
                
                is_fresh = age_minutes <= max_age_minutes
                
                return is_fresh, age_minutes, {
                    "vwap_value": vwap,
                    "source": "calculated_from_candles",
                    "candle_age_minutes": age_minutes
                }
            
            return False, float('inf'), {"error": "VWAP calculation failed"}
        except Exception as e:
            logger.error(f"Error checking VWAP recency: {e}")
            return False, float('inf'), {"error": str(e)}
    
    def _check_binance_orderflow(
        self,
        symbol: str,
        max_age_minutes: int = 30
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Check if Binance order flow data is available and fresh"""
        try:
            # Try order flow service first
            if self.order_flow_service and hasattr(self.order_flow_service, 'get_order_flow_signal'):
                # Convert MT5 symbol to Binance format
                binance_symbol = self._convert_to_binance_symbol(symbol)
                order_flow = self.order_flow_service.get_order_flow_signal(binance_symbol)
                
                if order_flow and isinstance(order_flow, dict):
                    # Check timestamp if available
                    timestamp = order_flow.get("timestamp")
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            age_minutes = (datetime.now().timestamp() - timestamp) / 60
                        else:
                            age_minutes = 0  # Assume fresh if timestamp format unknown
                        
                        is_fresh = age_minutes <= max_age_minutes
                        return is_fresh, age_minutes, {
                            "source": "order_flow_service",
                            "signal": order_flow.get("signal", "NEUTRAL"),
                            "imbalance": order_flow.get("imbalance")
                        }
                    
                    # No timestamp, assume available if data exists
                    return True, 0.0, {
                        "source": "order_flow_service",
                        "signal": order_flow.get("signal", "NEUTRAL")
                    }
            
            # Try binance service as fallback
            if self.binance_service and hasattr(self.binance_service, 'get_order_flow'):
                order_flow = self.binance_service.get_order_flow(symbol)
                if order_flow:
                    return True, 0.0, {
                        "source": "binance_service"
                    }
            
            return False, float('inf'), {"error": "No order flow service available", "fallback": "skip_confirmation"}
        except Exception as e:
            logger.debug(f"Error checking Binance order flow: {e}")
            return False, float('inf'), {"error": str(e), "fallback": "skip_confirmation"}
    
    def _check_news_calendar(
        self,
        symbol: str,
        max_age_minutes: int = 60
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Check if news calendar data is available and fresh"""
        try:
            if not self.news_service:
                return False, float('inf'), {"error": "No news service available", "fallback": "skip_news_check"}
            
            # Check if news service has recent data
            # Most news services update daily, so 60 min is reasonable
            # In practice, news calendar is static for the day
            
            # Try to get upcoming events to verify service is working
            upcoming = self.news_service.get_upcoming_events(hours_ahead=24) if hasattr(self.news_service, 'get_upcoming_events') else []
            
            return True, 0.0, {
                "source": "news_service",
                "upcoming_events_count": len(upcoming) if isinstance(upcoming, list) else 0
            }
        except Exception as e:
            logger.debug(f"Error checking news calendar: {e}")
            return False, float('inf'), {"error": str(e), "fallback": "skip_news_check"}
    
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> str:
        """Convert MT5 symbol (e.g., BTCUSDc) to Binance format (e.g., btcusdt)"""
        symbol = mt5_symbol.upper()
        # Remove 'c' suffix if present
        if symbol.endswith('C'):
            symbol = symbol[:-1]
        # Convert to Binance format
        if symbol.startswith(('BTC', 'ETH', 'LTC', 'XRP', 'ADA')):
            if not symbol.endswith('USDT'):
                symbol = symbol.replace('USD', 'USDT')
        return symbol.lower()
    
    def check_3_confluence_rule_weighted(
        self,
        range_data: RangeStructure,
        price_position: float,
        signals: Dict[str, Any],
        atr: float
    ) -> Tuple[int, Dict[str, int], List[str]]:
        """
        Weighted 3-Confluence Scoring (0-100):
        1. Structure: Range clearly defined (3-touch rule) = 40 pts
        2. Location: Price at edge (VWAP ± 0.75ATR or PDH/PDL or Critical Gap) = 35 pts
        3. Confirmation: ONE signal (RSI OR rejection wick OR tape pressure) = 25 pts
        
        Threshold: 80+ to allow trade
        
        Returns: (total_score, component_scores, missing_components)
        """
        component_scores = {}
        missing_components = []
        
        # Get weights from config
        weights = self.entry_filters.get("confluence_weights", {
            "structure": 40,
            "location": 35,
            "confirmation": 25
        })
        
        # 1. Structure Score (40 pts)
        structure_score = 0
        min_touches = self.entry_filters.get("min_touch_count", 3)
        total_touches = range_data.touch_count.get("total_touches", 0)
        
        if total_touches >= min_touches:
            # Perfect score if 3+ touches
            structure_score = weights["structure"]
        elif total_touches >= 2:
            # Partial score for 2 touches
            structure_score = int(weights["structure"] * 0.7)
        else:
            missing_components.append("structure")
        
        component_scores["structure"] = structure_score
        
        # 2. Location Score (35 pts)
        location_score = 0
        price_edge_threshold = self.entry_filters.get("price_edge_threshold_atr", 0.75)
        
        # Convert price_position (0-1) to absolute price
        absolute_price = range_data.range_low + (price_position * (range_data.range_high - range_data.range_low))
        
        # Check if price is at range edge (VWAP ± threshold*ATR)
        distance_from_vwap = abs(absolute_price - range_data.range_mid)
        atr_distance = distance_from_vwap / atr if atr > 0 else 0
        
        # Check if in critical gap zones (absolute prices)
        in_upper_gap = (range_data.critical_gaps.upper_zone_start <= absolute_price <= range_data.critical_gaps.upper_zone_end)
        in_lower_gap = (range_data.critical_gaps.lower_zone_start <= absolute_price <= range_data.critical_gaps.lower_zone_end)
        
        # Check if at PDH/PDL (if provided in signals)
        at_pdh = signals.get("at_pdh", False)
        at_pdl = signals.get("at_pdl", False)
        
        # Location criteria (any of these qualifies)
        if atr_distance >= price_edge_threshold:
            location_score = weights["location"]
        elif in_upper_gap or in_lower_gap:
            location_score = weights["location"]
        elif at_pdh or at_pdl:
            location_score = weights["location"]
        else:
            # Partial score if close to edge
            if atr_distance >= (price_edge_threshold * 0.5):
                location_score = int(weights["location"] * 0.6)
            else:
                missing_components.append("location")
        
        component_scores["location"] = location_score
        
        # 3. Confirmation Score (25 pts)
        confirmation_score = 0
        allowed_signals = self.entry_filters.get("allowed_signals", ["rsi_extreme", "rejection_wick", "tape_pressure"])
        
        # Check for at least one confirmation signal
        has_rsi_extreme = signals.get("rsi_extreme", False)
        has_rejection_wick = signals.get("rejection_wick", False)
        has_tape_pressure = signals.get("tape_pressure", False)
        
        if ("rsi_extreme" in allowed_signals and has_rsi_extreme) or \
           ("rejection_wick" in allowed_signals and has_rejection_wick) or \
           ("tape_pressure" in allowed_signals and has_tape_pressure):
            confirmation_score = weights["confirmation"]
        else:
            missing_components.append("confirmation")
        
        component_scores["confirmation"] = confirmation_score
        
        # Calculate total score
        total_score = sum(component_scores.values())
        
        return total_score, component_scores, missing_components
    
    def calculate_effective_atr(
        self,
        atr_5m: float,
        bb_width: float,
        price_mid: float
    ) -> float:
        """
        Effective ATR calculation for dynamic volatility scaling.
        
        Formula: max(atr_5m, bb_width × price_mid / 2)
        
        Uses whichever is larger to account for fast volatility expansion.
        """
        if not self.config.get("effective_atr", {}).get("enabled", True):
            return atr_5m
        
        bb_width_multiplier = self.config.get("effective_atr", {}).get("bb_width_multiplier", 0.5)
        bb_atr_equivalent = bb_width * bb_width_multiplier
        
        effective_atr = max(atr_5m, bb_atr_equivalent)
        
        return effective_atr
    
    def calculate_vwap_momentum(
        self,
        vwap_values: List[float],
        atr: float,
        price_mid: float,
        bars: int = 5
    ) -> float:
        """
        Calculate VWAP momentum as % of ATR per bar (instead of degrees).
        
        Args:
            vwap_values: List of VWAP values (most recent first)
            atr: Average True Range for normalization
            price_mid: Mid price (for percentage calculation)
            bars: Number of bars to analyze (default: 5)
        
        Returns:
            Momentum percentage (0.0-1.0 = 0-100% of ATR per bar)
            Negative = downward momentum, Positive = upward momentum
        """
        if not self.config.get("vwap_momentum", {}).get("enabled", True):
            return 0.0
        
        if len(vwap_values) < 2 or atr <= 0 or price_mid <= 0:
            return 0.0
        
        # Take most recent N bars
        recent_vwap = vwap_values[:min(bars, len(vwap_values))]
        
        if len(recent_vwap) < 2:
            return 0.0
        
        # Calculate total change over N bars
        oldest_vwap = recent_vwap[-1]
        newest_vwap = recent_vwap[0]
        total_change = newest_vwap - oldest_vwap
        
        # Normalize by price mid to get percentage
        change_pct = total_change / price_mid if price_mid > 0 else 0
        
        # Convert to ATR percentage per bar
        bars_analyzed = len(recent_vwap) - 1 if len(recent_vwap) > 1 else 1
        momentum_per_bar_atr = (change_pct / (atr / price_mid)) / bars_analyzed if (atr / price_mid) > 0 else 0
        
        return momentum_per_bar_atr
    
    def detect_false_range(
        self,
        range_data: RangeStructure,
        volume_trend: Dict[str, float],
        candles_df: Optional[pd.DataFrame] = None,
        vwap_slope_pct_atr: Optional[float] = None,
        cvd_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Detect imbalanced consolidation (pre-breakout trap / false range).
        
        Uses RangeBoundaryDetector's detect_imbalanced_consolidation method.
        
        Returns:
            (is_false_range, list_of_red_flags)
        """
        if not self.risk_mitigation.get("check_false_range", True):
            return False, []
        
        # Prepare parameters for range detector
        volume_increase = volume_trend.get("current_vs_1h_avg", 0)
        volume_trend_dict = {"current_vs_1h_avg": volume_increase}
        
        # Calculate VWAP momentum if not provided
        if vwap_slope_pct_atr is None and candles_df is not None:
            # Get VWAP values from candles
            typical_prices = (candles_df['high'] + candles_df['low'] + candles_df['close']) / 3
            volumes = candles_df.get('volume', candles_df.get('tick_volume', pd.Series([1] * len(candles_df))))
            vwap_values = []
            cumulative_pv = 0
            cumulative_v = 0
            
            for i, (tp, vol) in enumerate(zip(typical_prices, volumes)):
                cumulative_pv += tp * vol
                cumulative_v += vol
                if cumulative_v > 0:
                    vwap_values.append(cumulative_pv / cumulative_v)
            
            if len(vwap_values) >= 5:
                atr = range_data.range_width_atr
                price_mid = range_data.range_mid
                vwap_slope_pct_atr = self.calculate_vwap_momentum(vwap_values[-5:], atr, price_mid, bars=5)
            else:
                vwap_slope_pct_atr = 0.0
        elif vwap_slope_pct_atr is None:
            vwap_slope_pct_atr = 0.0
        
        # Call range detector's imbalanced consolidation method
        is_false, red_flags = self.range_detector.detect_imbalanced_consolidation(
            range_data=range_data,
            volume_trend=volume_trend_dict,
            vwap_slope_pct_atr=vwap_slope_pct_atr,
            candles_df=candles_df,
            cvd_data=cvd_data
        )
        
        return is_false, red_flags
    
    def check_range_validity(
        self,
        range_data: RangeStructure,
        current_price: float,
        recent_candles: List[Dict[str, Any]],
        vwap_slope_pct_atr: Optional[float] = None,
        bb_width_expansion: Optional[float] = None,
        candles_df_m15: Optional[pd.DataFrame] = None,
        atr_m15: Optional[float] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if range is still valid for trading.
        
        Uses RangeBoundaryDetector's check_range_invalidation method.
        
        Returns:
            (is_valid, list_of_invalidation_signals)
        """
        if not self.risk_mitigation.get("check_range_validity", True):
            return True, []
        
        # Convert recent_candles to format expected by range detector
        # (already in dict format, just need to ensure 'close' key exists)
        
        # Call range detector's invalidation check
        is_invalidated, invalidation_signals = self.range_detector.check_range_invalidation(
            range_data=range_data,
            current_price=current_price,
            candles=recent_candles,
            vwap_slope_pct_atr=vwap_slope_pct_atr,
            bb_width_expansion=bb_width_expansion,
            candles_df_m15=candles_df_m15,
            atr_m15=atr_m15
        )
        
        # Return inverted (is_valid = not is_invalidated)
        return not is_invalidated, invalidation_signals
    
    def check_session_filters(
        self,
        current_time: Optional[datetime] = None,
        broker_timezone_offset_hours: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Check if current session allows range scalping.
        
        BLOCKED PERIODS (UTC + broker_timezone_offset_hours):
        - London-NY Overlap (12:00-15:00 UTC) → NO SCALPING
        - First 30 min of London (08:00-08:30 UTC) → NO SCALPING
        - First 30 min of NY (13:00-13:30 UTC) → NO SCALPING
        
        ALLOWED PERIODS:
        - Asian (00:00-08:00 UTC) → ✅ VWAP, BB Fade, PDH/PDL
        - London Mid (09:00-12:00 UTC) → ✅ Mean reversion
        - Post-NY (16:00-18:00 UTC) → ✅ VWAP reversion
        - NY Late (19:00-22:00 UTC) → ✅ RSI bounce only
        
        Args:
            current_time: Current time (defaults to now UTC)
            broker_timezone_offset_hours: Offset from UTC for broker server time
            
        Returns:
            (is_allowed, reason_string)
        """
        if not self.risk_mitigation.get("check_session_filters", True):
            return True, "Session filters disabled"
        
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Apply broker timezone offset
        offset = broker_timezone_offset_hours or self.broker_timezone.get("offset_hours", 0)
        broker_time = current_time + timedelta(hours=offset)
        broker_hour = broker_time.hour
        broker_minute = broker_time.minute
        
        # Get session info (for logging/reference)
        session_info = self.session_analyzer.get_current_session(broker_time)
        
        # Check blocked periods
        blocked_config = self.risk_mitigation.get("blocked_sessions", {})
        
        # London-NY Overlap (12:00-15:00 UTC)
        overlap_config = blocked_config.get("london_ny_overlap", {})
        if overlap_config.get("enabled", True):
            overlap_start = overlap_config.get("start_utc", 12)
            overlap_end = overlap_config.get("end_utc", 15)
            if overlap_start <= broker_hour < overlap_end:
                return False, f"London-NY Overlap blocked ({broker_hour:02d}:00-{overlap_end:02d}:00 UTC)"
        
        # London open buffer (first 30 min)
        london_buffer_config = blocked_config.get("london_open_buffer", {})
        if london_buffer_config.get("enabled", True):
            london_buffer_minutes = london_buffer_config.get("minutes", 30)
            # London starts at 08:00 UTC
            if broker_hour == 8 and broker_minute < london_buffer_minutes:
                return False, f"London open buffer ({london_buffer_minutes} min)"
        
        # NY open buffer (first 30 min)
        ny_buffer_config = blocked_config.get("ny_open_buffer", {})
        if ny_buffer_config.get("enabled", True):
            ny_buffer_minutes = ny_buffer_config.get("minutes", 30)
            # NY starts at 13:00 UTC
            if broker_hour == 13 and broker_minute < ny_buffer_minutes:
                return False, f"NY open buffer ({ny_buffer_minutes} min)"
        
        # All checks passed
        return True, f"Session allowed ({session_info.get('name', 'Unknown')})"
    
    def check_trade_activity_criteria(
        self,
        symbol: str,
        volume_current: float,
        volume_1h_avg: float,
        price_deviation_from_vwap: float,
        atr: float,
        minutes_since_last_trade: int,
        upcoming_news: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if market conditions are active enough to trade.
        
        Required Criteria (ALL must be true):
        - Volume > 50% of 1h average
        - Price touches ±0.5ATR from VWAP
        - Time elapsed since last scalp > 15 min
        - No major red news inside 1 hour
        
        Returns:
            (sufficient_activity, list_of_failure_reasons)
        """
        if not self.risk_mitigation.get("check_trade_activity", True):
            return True, []
        
        failures = []
        
        # Check 1: Volume > 50% of 1h average
        min_volume_pct = self.risk_mitigation.get("min_volume_percent_of_1h_avg", 0.5)
        volume_ratio = volume_current / volume_1h_avg if volume_1h_avg > 0 else 0
        if volume_ratio < min_volume_pct:
            failures.append(f"Volume too low ({volume_ratio:.1%} < {min_volume_pct:.0%} of 1h avg)")
        
        # Check 2: Price touches ±0.5ATR from VWAP
        min_deviation = self.risk_mitigation.get("min_price_deviation_atr", 0.5)
        deviation_in_atr = abs(price_deviation_from_vwap) / atr if atr > 0 else 0
        if deviation_in_atr < min_deviation:
            failures.append(f"Price not at edge ({deviation_in_atr:.2f}ATR < {min_deviation}ATR from VWAP)")
        
        # Check 3: Cooldown period
        min_cooldown = self.risk_mitigation.get("min_minutes_between_trades", 15)
        if minutes_since_last_trade < min_cooldown:
            failures.append(f"Cooldown not met ({minutes_since_last_trade} min < {min_cooldown} min)")
        
        # Check 4: No major news
        block_news_minutes = self.risk_mitigation.get("block_major_news_minutes", 60)
        if upcoming_news:
            for news_event in upcoming_news:
                event_time = news_event.get("time")
                if isinstance(event_time, str):
                    try:
                        event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                    except:
                        continue
                elif isinstance(event_time, datetime):
                    pass
                else:
                    continue
                
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                
                time_until_event = (event_time - datetime.now(timezone.utc)).total_seconds() / 60
                
                if 0 <= time_until_event <= block_news_minutes:
                    impact = news_event.get("impact", "low")
                    if impact in ["high", "ultra"]:
                        failures.append(f"Major news upcoming ({impact} impact in {time_until_event:.0f} min)")
        
        sufficient = len(failures) == 0
        return sufficient, failures
    
    def check_nested_range_alignment(
        self,
        h1_range: Optional[RangeStructure],
        m15_range: RangeStructure,
        m5_range: Optional[RangeStructure],
        trade_direction: str
    ) -> Tuple[bool, str]:
        """
        Check multi-timeframe range alignment.
        
        Hierarchy:
        - H1 defines regime (trending vs balanced)
        - M15 defines active range (trade bias)
        - M5 defines entry trigger (must align with M15)
        
        Rules:
        - If M15 and M5 conflict → do nothing
        - If all 3 align (nested balance) → high confidence (>75% win rate historically)
        
        Returns:
            (is_aligned, reason_string)
        """
        alignment_issues = []
        
        # Check M15 vs M5 alignment
        if m5_range:
            # M5 range should be nested within M15 range
            if not (m15_range.range_low <= m5_range.range_low and m5_range.range_high <= m15_range.range_high):
                alignment_issues.append("M5 range not nested within M15")
            
            # Check direction alignment
            # For LONG: price should be at lower edge of both ranges
            # For SHORT: price should be at upper edge of both ranges
            m15_mid = m15_range.range_mid
            m5_mid = m5_range.range_mid
            m15_lower_third = m15_range.range_low + (m15_range.range_high - m15_range.range_low) / 3
            m15_upper_third = m15_range.range_high - (m15_range.range_high - m15_range.range_low) / 3
            
            if trade_direction == "BUY":
                # Long: prefer lower third of M15 range
                if m5_mid > m15_upper_third:
                    alignment_issues.append("M5 position conflicts with LONG bias (upper third)")
            elif trade_direction == "SELL":
                # Short: prefer upper third of M15 range
                if m5_mid < m15_lower_third:
                    alignment_issues.append("M5 position conflicts with SHORT bias (lower third)")
        
        # Check H1 vs M15 alignment
        if h1_range:
            # H1 range should contain M15 range
            if not (h1_range.range_low <= m15_range.range_low and m15_range.range_high <= h1_range.range_high):
                alignment_issues.append("M15 range not nested within H1 (regime mismatch)")
        
        if alignment_issues:
            return False, "; ".join(alignment_issues)
        
        return True, "All timeframes aligned"
    
    def adaptive_anchor_refresh(
        self,
        current_pdh: float,
        current_pdl: float,
        current_atr_h1: float,
        previous_atr_h1: float,
        session_high: float,
        session_low: float
    ) -> Tuple[float, float, bool]:
        """
        Refresh PDH/PDL if volatility regime shifts.
        
        Refresh Conditions:
        - ATR (H1) changes >40% from previous day → recalc
        - New session high/low exceeds PDH/PDL by >0.25% and holds 15 min → replace
        
        Returns:
            (new_pdh, new_pdl, was_refreshed)
        """
        if not self.config.get("adaptive_anchors", {}).get("enabled", True):
            return current_pdh, current_pdl, False
        
        adaptive_config = self.config.get("adaptive_anchors", {})
        atr_change_threshold = adaptive_config.get("atr_change_threshold_percent", 40) / 100
        drift_threshold = adaptive_config.get("pdh_pdl_drift_threshold_percent", 0.25) / 100
        hold_time_minutes = adaptive_config.get("hold_time_minutes", 15)
        
        new_pdh = current_pdh
        new_pdl = current_pdl
        was_refreshed = False
        
        # Check ATR change
        if previous_atr_h1 > 0:
            atr_change_ratio = abs(current_atr_h1 - previous_atr_h1) / previous_atr_h1
            if atr_change_ratio > atr_change_threshold:
                # Significant ATR change - refresh anchors
                new_pdh = session_high
                new_pdl = session_low
                was_refreshed = True
                logger.info(f"PDH/PDL refreshed due to ATR change ({atr_change_ratio:.1%} > {atr_change_threshold:.0%})")
        
        # Check session high/low drift
        if session_high > current_pdh * (1 + drift_threshold):
            # Session high exceeds PDH by threshold
            # TODO: Check if it held for hold_time_minutes (requires state tracking)
            # For now, refresh if exceeded
            new_pdh = session_high
            was_refreshed = True
            logger.debug(f"PDH refreshed: session high {session_high} exceeds PDH by {drift_threshold:.1%}")
        
        if session_low < current_pdl * (1 - drift_threshold):
            # Session low below PDL by threshold
            new_pdl = session_low
            was_refreshed = True
            logger.debug(f"PDL refreshed: session low {session_low} below PDL by {drift_threshold:.1%}")
        
        return new_pdh, new_pdl, was_refreshed

