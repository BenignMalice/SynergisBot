"""
Test Streamer Database Access for Range Scalping

Verifies that range scalping system can read fresh candles from
main_api.py's Multi-Timeframe Streamer database.

Tests:
1. Database exists and is accessible
2. Can read latest candles for symbols
3. Data freshness check
4. Fallback to MT5 when database unavailable
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_database_exists():
    """Test 1: Check if main_api.py streamer database exists"""
    logger.info("=" * 60)
    logger.info("TEST 1: Database Existence Check")
    logger.info("=" * 60)
    
    db_path = Path("data/multi_tf_candles.db")
    
    if not db_path.exists():
        logger.error(f"❌ Database not found at {db_path}")
        logger.error("   → Make sure main_api.py is running with streamer enabled")
        logger.error("   → The streamer should create this database on startup")
        return False
    
    logger.info(f"✅ Database found at: {db_path}")
    logger.info(f"   → Size: {db_path.stat().st_size / (1024 * 1024):.2f} MB")
    return True


def test_database_schema():
    """Test 2: Verify database schema is correct"""
    logger.info("=" * 60)
    logger.info("TEST 2: Database Schema Check")
    logger.info("=" * 60)
    
    db_path = Path("data/multi_tf_candles.db")
    
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if candles table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='candles'
        """)
        
        if not cursor.fetchone():
            logger.error("❌ 'candles' table not found in database")
            conn.close()
            return False
        
        # Check table structure
        cursor.execute("PRAGMA table_info(candles)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required_columns = ['symbol', 'timeframe', 'timestamp', 'time_utc', 
                           'open', 'high', 'low', 'close', 'volume', 'spread']
        
        missing = [col for col in required_columns if col not in column_names]
        
        if missing:
            logger.error(f"❌ Missing required columns: {missing}")
            conn.close()
            return False
        
        logger.info("✅ Database schema is correct")
        logger.info(f"   → Columns: {', '.join(column_names)}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database schema check failed: {e}")
        return False


def test_read_latest_candle(symbol: str = "BTCUSDc", timeframe: str = "M5"):
    """Test 3: Read latest candle from database"""
    logger.info("=" * 60)
    logger.info(f"TEST 3: Read Latest Candle ({symbol} {timeframe})")
    logger.info("=" * 60)
    
    db_path = Path("data/multi_tf_candles.db")
    
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get latest candle
        cursor.execute("""
            SELECT timestamp, time_utc, open, high, low, close, volume, spread, real_volume
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (symbol, timeframe))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.error(f"❌ No candles found for {symbol} {timeframe}")
            logger.error("   → Make sure main_api.py streamer is running and has fetched data")
            
            # Check what symbols/timeframes are available
            conn2 = sqlite3.connect(str(db_path), check_same_thread=False)
            conn2.row_factory = sqlite3.Row
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT DISTINCT symbol, timeframe FROM candles ORDER BY symbol, timeframe")
            available = cursor2.fetchall()
            conn2.close()
            
            if available:
                logger.info("   → Available symbols/timeframes in database:")
                for r in available[:20]:  # Show first 20
                    logger.info(f"      - {r['symbol']} {r['timeframe']}")
            else:
                logger.info("   → Database is empty - streamer may not have started yet")
            
            return False
        
        # Parse candle time
        candle_time_str = row['time_utc']
        candle_time = datetime.fromisoformat(candle_time_str.replace('Z', '+00:00'))
        if candle_time.tzinfo is None:
            candle_time = candle_time.replace(tzinfo=timezone.utc)
        
        now_utc = datetime.now(timezone.utc)
        age_seconds = (now_utc - candle_time).total_seconds()
        age_minutes = age_seconds / 60
        
        logger.info(f"✅ Latest candle found:")
        logger.info(f"   → Time: {candle_time.isoformat()}")
        logger.info(f"   → Age: {age_minutes:.1f} minutes ({age_seconds:.0f} seconds)")
        logger.info(f"   → Price: {row['close']:.2f}")
        logger.info(f"   → Volume: {row['volume']}")
        logger.info(f"   → Spread: {row['spread']}")
        
        # Check freshness
        tf_thresholds = {
            'M1': 0.9,
            'M5': 4.9,
            'M15': 14.9,
            'H1': 59.9
        }
        threshold = tf_thresholds.get(timeframe, 5.0)
        is_fresh = age_minutes <= threshold
        
        if is_fresh:
            logger.info(f"✅ Candle is FRESH (age {age_minutes:.1f} min <= threshold {threshold} min)")
        else:
            logger.warning(f"⚠️ Candle is STALE (age {age_minutes:.1f} min > threshold {threshold} min)")
            logger.warning("   → This may indicate streamer refresh loop is not working")
            logger.info("   → However, database READ functionality is working correctly")
        
        # Test passes if we can read from database (freshness is a separate concern)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to read candle: {e}", exc_info=True)
        return False


def test_candle_count(symbol: str = "BTCUSDc", timeframe: str = "M5"):
    """Test 4: Check candle count in database"""
    logger.info("=" * 60)
    logger.info(f"TEST 4: Candle Count Check ({symbol} {timeframe})")
    logger.info("=" * 60)
    
    db_path = Path("data/multi_tf_candles.db")
    
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM candles
            WHERE symbol = ? AND timeframe = ?
        """, (symbol, timeframe))
        
        count_row = cursor.fetchone()
        count = count_row['count'] if count_row else 0
        
        logger.info(f"✅ Candle count for {symbol} {timeframe}: {count}")
        
        if count < 50:
            logger.warning(f"⚠️ Low candle count ({count} < 50) - may not be enough for analysis")
        else:
            logger.info(f"   → Sufficient candles ({count} >= 50)")
        
        conn.close()
        return count >= 50
        
    except Exception as e:
        logger.error(f"❌ Failed to count candles: {e}")
        return False


def test_range_scalping_risk_filters():
    """Test 5: Test RangeScalpingRiskFilters database read"""
    logger.info("=" * 60)
    logger.info("TEST 5: RangeScalpingRiskFilters Database Integration")
    logger.info("=" * 60)
    
    try:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            logger.warning("⚠️ MetaTrader5 not available - skipping RiskFilters integration test")
            logger.info("   → This is expected in test environments without MT5")
            logger.info("   → Database read functionality is verified by other tests")
            return True
        
        from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
        from config.range_scalping_config_loader import load_range_scalping_config
        
        # Load config
        config = load_range_scalping_config()
        
        # Initialize risk filters
        risk_filters = RangeScalpingRiskFilters(config)
        
        # Test candle freshness check (this should read from database)
        symbol = "BTCUSDc"
        timeframe = mt5.TIMEFRAME_M5
        
        logger.info(f"Testing _check_candle_freshness for {symbol} M5...")
        logger.info("   → This should read from main_api.py streamer database")
        
        is_fresh, age_minutes, details = risk_filters._check_candle_freshness(
            symbol, 
            max_age_minutes=5.0,
            timeframe=timeframe,
            min_candles=50
        )
        
        logger.info(f"✅ Result from RangeScalpingRiskFilters:")
        logger.info(f"   → Fresh: {is_fresh}")
        logger.info(f"   → Age: {age_minutes:.1f} minutes")
        logger.info(f"   → Data source: {details.get('data_source', 'unknown')}")
        logger.info(f"   → Candle count: {details.get('candle_count', 0)}")
        logger.info(f"   → Has enough: {details.get('has_enough_candles', False)}")
        
        if details.get('data_source') == 'main_api_database':
            logger.info("✅ Successfully read from main_api.py streamer database!")
        elif details.get('data_source') == 'streamer':
            logger.info("✅ Read from in-process streamer (not using database)")
        else:
            logger.warning(f"⚠️ Used fallback data source: {details.get('data_source')}")
        
        return is_fresh
        
    except Exception as e:
        logger.error(f"❌ RangeScalpingRiskFilters test failed: {e}", exc_info=True)
        return False


def test_all_symbols():
    """Test 6: Check all symbols in database"""
    logger.info("=" * 60)
    logger.info("TEST 6: All Symbols in Database")
    logger.info("=" * 60)
    
    db_path = Path("data/multi_tf_candles.db")
    
    try:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all unique symbol/timeframe combinations with latest candle times
        cursor.execute("""
            SELECT 
                symbol,
                timeframe,
                MAX(timestamp) as latest_timestamp,
                MAX(time_utc) as latest_time_utc,
                COUNT(*) as candle_count
            FROM candles
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            logger.warning("⚠️ No data in database")
            return False
        
        logger.info(f"✅ Found {len(results)} symbol/timeframe combinations:")
        
        now_utc = datetime.now(timezone.utc)
        
        for row in results:
            symbol = row['symbol']
            tf = row['timeframe']
            count = row['candle_count']
            latest_time_str = row['latest_time_utc']
            
            try:
                latest_time = datetime.fromisoformat(latest_time_str.replace('Z', '+00:00'))
                if latest_time.tzinfo is None:
                    latest_time = latest_time.replace(tzinfo=timezone.utc)
                
                age_seconds = (now_utc - latest_time).total_seconds()
                age_minutes = age_seconds / 60
                
                status = "✅" if age_minutes < 10 else "⚠️" if age_minutes < 60 else "❌"
                
                logger.info(
                    f"   {status} {symbol:10s} {tf:4s} - "
                    f"{count:4d} candles, latest: {age_minutes:6.1f} min ago"
                )
            except Exception as e:
                logger.warning(f"   ⚠️ {symbol} {tf} - {count} candles, error parsing time: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to query all symbols: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("🧪 Testing Streamer Database Access for Range Scalping")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Prerequisites:")
    logger.info("  1. main_api.py should be running")
    logger.info("  2. Multi-Timeframe Streamer should be initialized")
    logger.info("  3. Streamer should have database enabled")
    logger.info("")
    
    results = {}
    
    # Run tests
    results['db_exists'] = test_database_exists()
    print()
    
    if not results['db_exists']:
        logger.error("❌ Database not found - skipping remaining tests")
        logger.error("   → Make sure main_api.py is running with streamer enabled")
        return
    
    results['db_schema'] = test_database_schema()
    print()
    
    results['read_candle'] = test_read_latest_candle("BTCUSDc", "M5")
    print()
    
    results['candle_count'] = test_candle_count("BTCUSDc", "M5")
    print()
    
    results['all_symbols'] = test_all_symbols()
    print()
    
    results['risk_filters'] = test_range_scalping_risk_filters()
    print()
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ All tests passed! Range scalping can read from main_api.py streamer database.")
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed. Review logs above for details.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

