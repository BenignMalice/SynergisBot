"""
Diagnostic script to check why candles are stale in the database.

Checks:
1. Streamer status and configuration
2. Database file modification time
3. Latest candle in database vs MT5
4. Streamer write queue status
5. MT5 connection and data freshness
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_streamer_status() -> Dict[str, Any]:
    """Check if streamer is running and configured"""
    result = {
        'streamer_exists': False,
        'streamer_running': False,
        'database_enabled': False,
        'metrics': None,
        'error': None
    }
    
    try:
        from infra.streamer_data_access import get_streamer
        streamer = get_streamer()
        
        if streamer is None:
            result['error'] = 'Streamer is None - not initialized'
            return result
        
        result['streamer_exists'] = True
        result['streamer_running'] = streamer.is_running if hasattr(streamer, 'is_running') else False
        result['database_enabled'] = streamer.config.enable_database if hasattr(streamer, 'config') else False
        result['metrics'] = streamer.metrics if hasattr(streamer, 'metrics') else None
        
        # Check write queue
        if hasattr(streamer, 'write_queue'):
            result['write_queue_size'] = len(streamer.write_queue)
        else:
            result['write_queue_size'] = 0
        
        # Check buffers
        if hasattr(streamer, 'buffers'):
            buffer_info = {}
            for symbol, timeframes in streamer.buffers.items():
                buffer_info[symbol] = {}
                for tf, buffer in timeframes.items():
                    buffer_info[symbol][tf] = len(buffer) if hasattr(buffer, '__len__') else 0
            result['buffer_info'] = buffer_info
        
    except ImportError as e:
        result['error'] = f'Cannot import streamer: {e}'
    except Exception as e:
        result['error'] = f'Error checking streamer: {e}'
    
    return result


def check_streamer_config() -> Dict[str, Any]:
    """Check streamer configuration file"""
    result = {
        'config_exists': False,
        'database_enabled': False,
        'symbols': [],
        'refresh_intervals': {},
        'error': None
    }
    
    try:
        config_path = Path('config/multi_tf_streamer_config.json')
        if not config_path.exists():
            result['error'] = f'Config file not found: {config_path}'
            return result
        
        result['config_exists'] = True
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        result['database_enabled'] = config.get('enable_database', False)
        result['symbols'] = config.get('symbols', [])
        result['refresh_intervals'] = config.get('refresh_intervals', {})
        result['db_path'] = config.get('db_path', 'data/multi_tf_candles.db')
        
    except Exception as e:
        result['error'] = f'Error reading config: {e}'
    
    return result


def check_database_file(db_path: str) -> Dict[str, Any]:
    """Check database file status"""
    result = {
        'exists': False,
        'size_mb': 0,
        'last_modified': None,
        'age_minutes': None,
        'error': None
    }
    
    try:
        db_file = Path(db_path)
        if not db_file.exists():
            result['error'] = f'Database file not found: {db_path}'
            return result
        
        result['exists'] = True
        result['size_mb'] = db_file.stat().st_size / (1024 * 1024)
        
        # Get last modification time
        mod_time = datetime.fromtimestamp(db_file.stat().st_mtime, tz=timezone.utc)
        result['last_modified'] = mod_time.isoformat()
        
        now = datetime.now(timezone.utc)
        age = (now - mod_time).total_seconds() / 60
        result['age_minutes'] = age
        
    except Exception as e:
        result['error'] = f'Error checking database file: {e}'
    
    return result


def check_database_latest_candle(db_path: str, symbol: str, timeframe: str = 'M5') -> Dict[str, Any]:
    """Check latest candle in database"""
    result = {
        'found': False,
        'candle_time': None,
        'age_minutes': None,
        'candle_count': 0,
        'error': None
    }
    
    try:
        if not Path(db_path).exists():
            result['error'] = f'Database file not found: {db_path}'
            return result
        
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get latest candle
        cursor.execute("""
            SELECT timestamp, time_utc, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (symbol, timeframe))
        
        row = cursor.fetchone()
        
        if row:
            result['found'] = True
            candle_time = datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00'))
            if candle_time.tzinfo is None:
                candle_time = candle_time.replace(tzinfo=timezone.utc)
            
            result['candle_time'] = candle_time.isoformat()
            
            now = datetime.now(timezone.utc)
            age = (now - candle_time).total_seconds() / 60
            result['age_minutes'] = age
            result['candle_data'] = {
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            }
        
        # Get total count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM candles
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        
        count_row = cursor.fetchone()
        result['candle_count'] = count_row[0] if count_row else 0
        
        conn.close()
        
    except Exception as e:
        result['error'] = f'Error checking database: {e}'
    
    return result


def check_mt5_latest_candle(symbol: str, timeframe: int = mt5.TIMEFRAME_M5) -> Dict[str, Any]:
    """Check latest candle from MT5 directly"""
    result = {
        'found': False,
        'candle_time': None,
        'age_minutes': None,
        'candle_data': None,
        'error': None
    }
    
    try:
        # Initialize MT5 if needed
        if not mt5.initialize():
            error = mt5.last_error()
            result['error'] = f'MT5 initialization failed: {error}'
            return result
        
        # Ensure symbol is selected
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            result['error'] = f'Symbol {symbol} not found in MT5'
            return result
        
        if not symbol_info.select:
            mt5.symbol_select(symbol, True)
            # Small delay for MT5 to refresh
            import time
            time.sleep(0.5)
        
        # Fetch latest candle
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
        
        if rates is None or len(rates) == 0:
            result['error'] = f'No candles returned from MT5: {mt5.last_error()}'
            return result
        
        latest = rates[0]
        candle_time = datetime.fromtimestamp(latest['time'], tz=timezone.utc)
        
        result['found'] = True
        result['candle_time'] = candle_time.isoformat()
        
        now = datetime.now(timezone.utc)
        age = (now - candle_time).total_seconds() / 60
        result['age_minutes'] = age
        
        result['candle_data'] = {
            'open': float(latest['open']),
            'high': float(latest['high']),
            'low': float(latest['low']),
            'close': float(latest['close']),
            'volume': int(latest['tick_volume'])
        }
        
    except Exception as e:
        result['error'] = f'Error checking MT5: {e}'
    
    return result


def main():
    """Run all diagnostic checks"""
    print("=" * 80)
    print("CANDLE STALENESS DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Symbol to check
    symbol = 'XAUUSDc'
    timeframe = 'M5'
    
    print(f"Checking symbol: {symbol} ({timeframe})")
    print()
    
    # 1. Check streamer status
    print("1. STREAMER STATUS")
    print("-" * 80)
    streamer_status = check_streamer_status()
    if streamer_status['error']:
        print(f"   [ERROR] Error: {streamer_status['error']}")
    else:
            print(f"   Streamer exists: {streamer_status['streamer_exists']}")
            print(f"   Streamer running: {streamer_status['streamer_running']}")
            print(f"   Database enabled: {streamer_status['database_enabled']}")
            if streamer_status.get('write_queue_size') is not None:
                print(f"   Write queue size: {streamer_status['write_queue_size']}")
            if streamer_status.get('metrics'):
                metrics = streamer_status['metrics']
                print(f"   Total candles fetched: {metrics.get('total_candles_fetched', 0)}")
                print(f"   Total candles stored: {metrics.get('total_candles_stored', 0)}")
                print(f"   Last update: {metrics.get('last_update', 'N/A')}")
    print()
    
    # 2. Check streamer config
    print("2. STREAMER CONFIGURATION")
    print("-" * 80)
    config = check_streamer_config()
    if config['error']:
        print(f"   [ERROR] Error: {config['error']}")
    else:
        print(f"   Config exists: {config['config_exists']}")
        print(f"   Database enabled: {config['database_enabled']}")
        print(f"   Symbols configured: {len(config['symbols'])}")
        if symbol in config['symbols']:
            print(f"   [OK] {symbol} is in configured symbols")
        else:
            print(f"   [WARNING] {symbol} is NOT in configured symbols")
        print(f"   Refresh intervals: {config['refresh_intervals']}")
        print(f"   Database path: {config.get('db_path', 'N/A')}")
    print()
    
    # 3. Check database file
    db_path = config.get('db_path', 'data/multi_tf_candles.db')
    print("3. DATABASE FILE STATUS")
    print("-" * 80)
    db_file = check_database_file(db_path)
    if db_file['error']:
        print(f"   [ERROR] Error: {db_file['error']}")
    else:
        print(f"   Database exists: {db_file['exists']}")
        print(f"   Size: {db_file['size_mb']:.2f} MB")
        print(f"   Last modified: {db_file['last_modified']}")
        print(f"   Age: {db_file['age_minutes']:.1f} minutes")
        if db_file['age_minutes'] and db_file['age_minutes'] > 10:
            print(f"   [WARNING] Database file is {db_file['age_minutes']:.1f} minutes old - not being updated!")
    print()
    
    # 4. Check latest candle in database
    print("4. LATEST CANDLE IN DATABASE")
    print("-" * 80)
    db_candle = check_database_latest_candle(db_path, symbol, timeframe)
    if db_candle['error']:
        print(f"   [ERROR] Error: {db_candle['error']}")
    else:
        if db_candle['found']:
            print(f"   [OK] Found candle in database")
            print(f"   Candle time: {db_candle['candle_time']}")
            print(f"   Age: {db_candle['age_minutes']:.1f} minutes")
            print(f"   Total candles in DB: {db_candle['candle_count']}")
            if db_candle.get('candle_data'):
                cd = db_candle['candle_data']
                print(f"   Close: {cd['close']}, Volume: {cd['volume']}")
            
            # Check if stale
            if db_candle['age_minutes'] and db_candle['age_minutes'] > 5.5:
                print(f"   [STALE] {db_candle['age_minutes']:.1f} min > 5.5 min threshold")
        else:
            print(f"   [ERROR] No candle found in database for {symbol} {timeframe}")
    print()
    
    # 5. Check MT5 latest candle
    print("5. LATEST CANDLE FROM MT5 (DIRECT)")
    print("-" * 80)
    mt5_tf = mt5.TIMEFRAME_M5 if timeframe == 'M5' else mt5.TIMEFRAME_M1
    mt5_candle = check_mt5_latest_candle(symbol, mt5_tf)
    if mt5_candle['error']:
        print(f"   [ERROR] Error: {mt5_candle['error']}")
    else:
        if mt5_candle['found']:
            print(f"   [OK] Found candle from MT5")
            print(f"   Candle time: {mt5_candle['candle_time']}")
            print(f"   Age: {mt5_candle['age_minutes']:.1f} minutes")
            if mt5_candle.get('candle_data'):
                cd = mt5_candle['candle_data']
                print(f"   Close: {cd['close']}, Volume: {cd['volume']}")
            
            # Check if stale
            if mt5_candle['age_minutes'] and mt5_candle['age_minutes'] > 5.5:
                print(f"   [STALE] {mt5_candle['age_minutes']:.1f} min > 5.5 min threshold")
                print(f"   [WARNING] This means MT5 itself is returning old data!")
        else:
            print(f"   [ERROR] No candle found from MT5")
    print()
    
    # 6. Compare database vs MT5
    print("6. DATABASE vs MT5 COMPARISON")
    print("-" * 80)
    if db_candle.get('found') and mt5_candle.get('found'):
        db_time = datetime.fromisoformat(db_candle['candle_time'])
        mt5_time = datetime.fromisoformat(mt5_candle['candle_time'])
        
        time_diff = (mt5_time - db_time).total_seconds() / 60
        
        print(f"   Database candle time: {db_candle['candle_time']}")
        print(f"   MT5 candle time: {mt5_candle['candle_time']}")
        print(f"   Time difference: {time_diff:.1f} minutes")
        
        if abs(time_diff) < 1.0:
            print(f"   [OK] Database and MT5 are in sync (same candle)")
        elif time_diff > 0:
            print(f"   [WARNING] MT5 has NEWER candle ({time_diff:.1f} min newer)")
            print(f"   [WARNING] Database is NOT being updated!")
        else:
            print(f"   [WARNING] Database has NEWER candle ({abs(time_diff):.1f} min newer)")
            print(f"   [WARNING] This is unexpected - database should not be ahead of MT5")
        
        # Compare prices
        if db_candle.get('candle_data') and mt5_candle.get('candle_data'):
            db_close = db_candle['candle_data']['close']
            mt5_close = mt5_candle['candle_data']['close']
            price_diff = abs(mt5_close - db_close)
            print(f"   Price difference: {price_diff:.5f}")
            if price_diff > 0.01:
                print(f"   [WARNING] Prices differ significantly - different candles!")
    else:
        print("   [WARNING] Cannot compare - missing data from database or MT5")
    print()
    
    # 7. Recommendations
    print("7. RECOMMENDATIONS")
    print("-" * 80)
    recommendations = []
    
    if not streamer_status.get('streamer_running'):
        recommendations.append("[CRITICAL] Streamer is not running - start the streamer to update database")
    
    if not streamer_status.get('database_enabled'):
        recommendations.append("[CRITICAL] Database is disabled in streamer - enable it in config")
    
    if db_file.get('age_minutes') and db_file['age_minutes'] > 10:
        recommendations.append(f"[CRITICAL] Database file is {db_file['age_minutes']:.1f} min old - not being updated")
    
    if db_candle.get('age_minutes') and db_candle['age_minutes'] > 5.5:
        recommendations.append(f"[STALE] Database candle is {db_candle['age_minutes']:.1f} min old - stale")
    
    if mt5_candle.get('age_minutes') and mt5_candle['age_minutes'] > 5.5:
        recommendations.append(f"[STALE] MT5 candle is {mt5_candle['age_minutes']:.1f} min old - market may be closed or MT5 issue")
    
    if db_candle.get('found') and mt5_candle.get('found'):
        db_time = datetime.fromisoformat(db_candle['candle_time'])
        mt5_time = datetime.fromisoformat(mt5_candle['candle_time'])
        time_diff = (mt5_time - db_time).total_seconds() / 60
        if time_diff > 5:
            recommendations.append(f"[CRITICAL] Database is {time_diff:.1f} min behind MT5 - streamer not updating database")
    
    if not recommendations:
        print("   [OK] No issues found - system appears healthy")
    else:
        for rec in recommendations:
            print(f"   {rec}")
    
    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()

