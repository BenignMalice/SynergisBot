"""
Diagnostic script to check database write mechanism and why file is stale.

Checks:
1. Database WAL mode (WAL files are separate from main DB file)
2. Database write queue status
3. Latest candles in database vs what should be there
4. Streamer write activity
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

def check_database_wal_mode(db_path: str) -> Dict[str, Any]:
    """Check if database is using WAL mode"""
    result = {
        'wal_mode': False,
        'wal_file_exists': False,
        'wal_file_size': 0,
        'wal_file_modified': None,
        'wal_file_age_minutes': None,
        'error': None
    }
    
    try:
        if not Path(db_path).exists():
            result['error'] = 'Database file not found'
            return result
        
        # Check WAL mode
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        conn.close()
        
        result['wal_mode'] = (journal_mode.upper() == 'WAL')
        
        # Check WAL file
        wal_path = Path(str(db_path) + '-wal')
        if wal_path.exists():
            result['wal_file_exists'] = True
            result['wal_file_size'] = wal_path.stat().st_size / 1024  # KB
            mod_time = datetime.fromtimestamp(wal_path.stat().st_mtime, tz=timezone.utc)
            result['wal_file_modified'] = mod_time.isoformat()
            
            now = datetime.now(timezone.utc)
            age = (now - mod_time).total_seconds() / 60
            result['wal_file_age_minutes'] = age
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def check_latest_candles_in_db(db_path: str, symbol: str, timeframe: str = 'M5', limit: int = 10) -> List[Dict[str, Any]]:
    """Get latest N candles from database"""
    candles = []
    
    try:
        if not Path(db_path).exists():
            return candles
        
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, time_utc, open, high, low, close, volume, created_at
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (symbol, timeframe, limit))
        
        rows = cursor.fetchall()
        
        for row in rows:
            candle_time = datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00'))
            if candle_time.tzinfo is None:
                candle_time = candle_time.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age = (now - candle_time).total_seconds() / 60
            
            created_at = row['created_at'] if 'created_at' in row.keys() else 'N/A'
            candles.append({
                'time': candle_time.isoformat(),
                'age_minutes': age,
                'close': row['close'],
                'volume': row['volume'],
                'created_at': created_at
            })
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")
    
    return candles


def check_expected_candles() -> List[Dict[str, Any]]:
    """Calculate what candles SHOULD exist based on current time"""
    now = datetime.now(timezone.utc)
    
    # M5 candles close at :00, :05, :10, :15, etc.
    # Get last 10 expected M5 candle times
    expected = []
    
    # Round down to last 5-minute boundary
    current_minute = now.minute
    rounded_minute = (current_minute // 5) * 5
    
    last_candle_time = now.replace(minute=rounded_minute, second=0, microsecond=0)
    
    for i in range(10):
        candle_time = last_candle_time - timedelta(minutes=i*5)
        age = (now - candle_time).total_seconds() / 60
        
        expected.append({
            'time': candle_time.isoformat(),
            'age_minutes': age,
            'expected': True
        })
    
    return expected


def main():
    """Run database write diagnostic"""
    print("=" * 80)
    print("DATABASE WRITE DIAGNOSTIC")
    print("=" * 80)
    print()
    
    symbol = 'XAUUSDc'
    timeframe = 'M5'
    db_path = 'data/multi_tf_candles.db'
    
    print(f"Checking: {symbol} ({timeframe})")
    print(f"Database: {db_path}")
    print()
    
    # 1. Check WAL mode
    print("1. DATABASE WAL MODE CHECK")
    print("-" * 80)
    wal_info = check_database_wal_mode(db_path)
    if wal_info['error']:
        print(f"   [ERROR] {wal_info['error']}")
    else:
        print(f"   WAL mode: {wal_info['wal_mode']}")
        if wal_info['wal_mode']:
            print(f"   [INFO] Database uses WAL mode - file modification time may not reflect writes")
            print(f"   WAL file exists: {wal_info['wal_file_exists']}")
            if wal_info['wal_file_exists']:
                print(f"   WAL file size: {wal_info['wal_file_size']:.2f} KB")
                print(f"   WAL file modified: {wal_info['wal_file_modified']}")
                print(f"   WAL file age: {wal_info['wal_file_age_minutes']:.1f} minutes")
                if wal_info['wal_file_age_minutes'] and wal_info['wal_file_age_minutes'] < 1:
                    print(f"   [OK] WAL file is fresh - database is being written to")
                else:
                    print(f"   [WARNING] WAL file is {wal_info['wal_file_age_minutes']:.1f} min old")
        else:
            print(f"   [INFO] Database uses DELETE mode - file modification time reflects writes")
    print()
    
    # 2. Check latest candles in database
    print("2. LATEST CANDLES IN DATABASE")
    print("-" * 80)
    db_candles = check_latest_candles_in_db(db_path, symbol, timeframe, limit=10)
    if db_candles:
        print(f"   Found {len(db_candles)} latest candles:")
        for i, candle in enumerate(db_candles[:5], 1):
            print(f"   {i}. Time: {candle['time']}")
            print(f"      Age: {candle['age_minutes']:.1f} minutes")
            print(f"      Close: {candle['close']}, Volume: {candle['volume']}")
            if candle.get('created_at') and candle['created_at'] != 'N/A':
                print(f"      Created at: {candle['created_at']}")
            print()
    else:
        print(f"   [ERROR] No candles found in database")
    print()
    
    # 3. Check expected candles
    print("3. EXPECTED CANDLES (Based on Current Time)")
    print("-" * 80)
    expected = check_expected_candles()
    print(f"   Expected last 5 M5 candles:")
    for i, exp in enumerate(expected[:5], 1):
        print(f"   {i}. Time: {exp['time']}")
        print(f"      Age: {exp['age_minutes']:.1f} minutes")
    print()
    
    # 4. Compare expected vs actual
    print("4. EXPECTED vs ACTUAL COMPARISON")
    print("-" * 80)
    if db_candles and expected:
        db_times = {c['time'] for c in db_candles}
        exp_times = {e['time'] for e in expected}
        
        missing = exp_times - db_times
        if missing:
            print(f"   [WARNING] Missing {len(missing)} expected candles:")
            for time in sorted(missing)[:5]:
                print(f"      - {time}")
        else:
            print(f"   [OK] All expected candles are in database")
        
        # Check if latest candle matches
        latest_db = db_candles[0] if db_candles else None
        latest_exp = expected[0] if expected else None
        
        if latest_db and latest_exp:
            if latest_db['time'] == latest_exp['time']:
                print(f"   [OK] Latest candle matches expected: {latest_db['time']}")
            else:
                print(f"   [WARNING] Latest candle mismatch:")
                print(f"      Database: {latest_db['time']} ({latest_db['age_minutes']:.1f} min old)")
                print(f"      Expected: {latest_exp['time']} ({latest_exp['age_minutes']:.1f} min old)")
    print()
    
    # 5. Recommendations
    print("5. RECOMMENDATIONS")
    print("-" * 80)
    recommendations = []
    
    if wal_info.get('wal_mode'):
        if wal_info.get('wal_file_age_minutes') and wal_info['wal_file_age_minutes'] > 5:
            recommendations.append(f"[STALE] WAL file is {wal_info['wal_file_age_minutes']:.1f} min old - streamer may not be writing")
        else:
            recommendations.append("[OK] WAL file is fresh - database is being written to")
    
    if db_candles:
        latest_age = db_candles[0]['age_minutes']
        if latest_age > 5.5:
            recommendations.append(f"[STALE] Latest candle is {latest_age:.1f} min old - should be < 5.5 min")
        else:
            recommendations.append(f"[OK] Latest candle is {latest_age:.1f} min old - fresh")
    
    if db_candles and expected:
        missing_count = len(exp_times - db_times)
        if missing_count > 0:
            recommendations.append(f"[MISSING] {missing_count} expected candles are missing from database")
    
    if not recommendations:
        recommendations.append("[OK] No issues detected")
    
    for rec in recommendations:
        print(f"   {rec}")
    
    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print()
    print("NOTE: If WAL mode is enabled, the database file modification time")
    print("may not reflect actual writes. Check WAL file modification time instead.")


if __name__ == '__main__':
    main()

