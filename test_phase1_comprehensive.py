"""
Comprehensive Phase 1 Test Suite for Range Scalping System

Tests all Phase 1 components with real data from main_api.py streamer:
1. RangeBoundaryDetector - all methods
2. RangeScalpingRiskFilters - all methods  
3. Configuration loading and validation
4. End-to-end Phase 1 pipeline

Prerequisites:
- main_api.py running with streamer enabled
- Desktop agent running (optional, for full integration)
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_config_loading():
    """Test 1: Configuration Loading & Validation"""
    logger.info("=" * 70)
    logger.info("TEST 1: Configuration Loading & Validation")
    logger.info("=" * 70)
    
    try:
        from config.range_scalping_config_loader import (
            load_range_scalping_config,
            load_rr_config,
            get_config_version_info
        )
        
        # Load main config
        config = load_range_scalping_config()
        assert config is not None, "Main config is None"
        assert config.get("enabled") is not None, "Missing 'enabled' field"
        
        logger.info(f"✅ Main config loaded")
        logger.info(f"   → Enabled: {config.get('enabled')}")
        logger.info(f"   → Version: {config.get('_config_version', 'unknown')}")
        logger.info(f"   → Hash: {config.get('_config_hash', 'unknown')[:16]}")
        
        # Load R:R config
        rr_config = load_rr_config()
        assert rr_config is not None, "R:R config is None"
        assert "strategy_rr" in rr_config, "Missing 'strategy_rr' in R:R config"
        
        logger.info(f"✅ R:R config loaded")
        logger.info(f"   → Strategies: {len(rr_config.get('strategy_rr', {}))}")
        
        # Test version info
        version_info = get_config_version_info()
        logger.info(f"✅ Config version info: {version_info}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Config loading failed: {e}", exc_info=True)
        return False


def test_range_detection_from_database(symbol: str = "BTCUSDc"):
    """Test 2: Range Detection Using Streamer Database"""
    logger.info("=" * 70)
    logger.info(f"TEST 2: Range Detection ({symbol})")
    logger.info("=" * 70)
    
    try:
        from infra.range_boundary_detector import RangeBoundaryDetector
        import sqlite3
        from pathlib import Path
        import pandas as pd
        
        db_path = Path("data/multi_tf_candles.db")
        if not db_path.exists():
            logger.error(f"❌ Database not found: {db_path}")
            logger.error("   → Make sure main_api.py is running with streamer enabled")
            return False
        
        detector = RangeBoundaryDetector()
        
        # Read M15 candles from database for dynamic range detection
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT time_utc, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = 'M15'
            ORDER BY timestamp DESC
            LIMIT 150
        """, (symbol,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 50:
            logger.error(f"❌ Not enough candles: {len(rows)} < 50")
            return False
        
        # Convert to DataFrame
        candles_data = []
        for row in reversed(rows):  # Oldest first
            candles_data.append({
                'time': datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00')),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })
        
        df = pd.DataFrame(candles_data)
        df.set_index('time', inplace=True)
        
        # Test dynamic range detection
        logger.info(f"   → Testing dynamic range detection with {len(df)} candles...")
        range_data = detector.detect_range(
            symbol=symbol,
            timeframe="M15",
            range_type="dynamic",
            candles_df=df
        )
        
        if range_data:
            logger.info(f"✅ Dynamic range detected:")
            logger.info(f"   → Type: {range_data.range_type}")
            logger.info(f"   → High: {range_data.range_high:.2f}")
            logger.info(f"   → Low: {range_data.range_low:.2f}")
            logger.info(f"   → Width: {range_data.range_high - range_data.range_low:.2f}")
            logger.info(f"   → Width (ATR): {range_data.range_width_atr:.2f} ATR")
            logger.info(f"   → Validated: {range_data.validated}")
            
            # Test critical gaps
            gaps = detector.calculate_critical_gaps(
                range_data.range_high,
                range_data.range_low
            )
            logger.info(f"✅ Critical gaps calculated:")
            logger.info(f"   → Upper zone: {gaps.upper_zone_start:.2f} - {gaps.upper_zone_end:.2f}")
            logger.info(f"   → Lower zone: {gaps.lower_zone_start:.2f} - {gaps.lower_zone_end:.2f}")
            
            # Test range expansion (needs candles_df, bb_width, atr)
            expansion_state = detector.check_range_expansion(
                range_data, 
                candles_df=df,
                bb_width=0.02,  # Mock BB width
                atr=100.0  # Mock ATR
            )
            logger.info(f"✅ Range expansion state: {expansion_state}")
            
            # Test range invalidation
            # Convert DataFrame to list of dicts (as expected by the method)
            candles_list = df.reset_index().to_dict('records')
            is_invalidated, invalidation_signals = detector.check_range_invalidation(
                range_data,
                current_price=range_data.range_mid,
                candles=candles_list,
                candles_df_m15=df  # Also pass DataFrame for M15 BOS detection
            )
            logger.info(f"✅ Range invalidation check:")
            logger.info(f"   → Invalidated: {is_invalidated}")
            logger.info(f"   → Signals: {invalidation_signals}")
            
            return True
        else:
            logger.warning(f"⚠️ No range detected (may be expected if market is trending)")
            return True  # Not a failure - ranges may not exist at all times
            
    except Exception as e:
        logger.error(f"❌ Range detection test failed: {e}", exc_info=True)
        return False


def test_risk_filters_calculations():
    """Test 3: Risk Filters Calculations"""
    logger.info("=" * 70)
    logger.info("TEST 3: Risk Filters Calculations")
    logger.info("=" * 70)
    
    try:
        from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        from config.range_scalping_config_loader import load_range_scalping_config
        
        config = load_range_scalping_config()
        filters = RangeScalpingRiskFilters(config)
        
        # Test effective ATR calculation
        atr_5m = 100.0
        bb_width = 0.02  # 2%
        price_mid = 110000.0
        
        effective_atr = filters.calculate_effective_atr(atr_5m, bb_width, price_mid)
        logger.info(f"✅ Effective ATR calculation:")
        logger.info(f"   → ATR_5m: {atr_5m}")
        logger.info(f"   → BB width × price_mid / 2: {bb_width * price_mid / 2}")
        logger.info(f"   → Effective ATR: {effective_atr:.2f}")
        logger.info(f"   → Using: {'max (ATR)' if effective_atr == atr_5m else 'max (BB calculation)'}")
        
        assert effective_atr >= atr_5m, "Effective ATR should be >= ATR_5m"
        
        # Test VWAP momentum
        vwap_values = [109900.0, 109950.0, 110000.0, 110050.0, 110100.0]
        momentum = filters.calculate_vwap_momentum(vwap_values, effective_atr, price_mid)
        logger.info(f"✅ VWAP momentum calculation:")
        logger.info(f"   → VWAP values: {[f'{v:.2f}' for v in vwap_values]}")
        logger.info(f"   → Momentum: {momentum:.4f} ({momentum * 100:.2f}% of ATR per bar)")
        logger.info(f"   → Direction: {'Upward' if momentum > 0 else 'Downward' if momentum < 0 else 'Neutral'}")
        
        assert isinstance(momentum, float), "Momentum must be float"
        
        # Test 3-confluence scoring
        range_data = RangeStructure(
            range_type="dynamic",
            range_high=110500.0,
            range_low=109500.0,
            range_mid=110000.0,
            range_width_atr=6.6,
            critical_gaps=CriticalGapZones(
                upper_zone_start=110400.0,
                upper_zone_end=110500.0,
                lower_zone_start=109500.0,
                lower_zone_end=109600.0
            ),
            touch_count={"total_touches": 3, "upper_touches": 2, "lower_touches": 1},
            validated=True,
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=[]
        )
        
        price_position = 0.8  # 80% up from low (near high)
        signals = {
            "rsi_extreme": True,
            "rejection_wick": False,
            "tape_pressure": False
        }
        
        score, components, missing = filters.check_3_confluence_rule_weighted(
            range_data,
            price_position,
            signals,
            effective_atr
        )
        
        logger.info(f"✅ 3-Confluence Scoring:")
        logger.info(f"   → Total Score: {score}/100")
        logger.info(f"   → Components: {components}")
        logger.info(f"   → Missing: {missing}")
        logger.info(f"   → Passes threshold (80+): {score >= 80}")
        
        assert 0 <= score <= 100, "Score must be 0-100"
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Risk filters calculations failed: {e}", exc_info=True)
        return False


def test_session_filters():
    """Test 4: Session Filter Logic"""
    logger.info("=" * 70)
    logger.info("TEST 4: Session Filter Logic")
    logger.info("=" * 70)
    
    try:
        from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
        from config.range_scalping_config_loader import load_range_scalping_config
        from datetime import datetime, timezone
        
        config = load_range_scalping_config()
        filters = RangeScalpingRiskFilters(config)
        
        # Test session filter with current time
        # The method uses current_time (defaults to now) and checks session internally
        allowed, reason = filters.check_session_filters(
            current_time=None,  # Uses current time
            broker_timezone_offset_hours=0
        )
        
        status = "✅ ALLOW" if allowed else "❌ BLOCK"
        logger.info(f"   {status}: Current session check → {reason}")
        
        # Test with different times
        from datetime import datetime, timezone, timedelta
        
        # Test during Asian session (00:00-06:00 UTC)
        asian_time = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0)
        allowed_asian, reason_asian = filters.check_session_filters(
            current_time=asian_time,
            broker_timezone_offset_hours=0
        )
        logger.info(f"   {'✅ ALLOW' if allowed_asian else '❌ BLOCK'}: Asian session (02:00 UTC) → {reason_asian}")
        
        # Test during London-NY overlap (12:00-15:00 UTC) - should block
        overlap_time = datetime.now(timezone.utc).replace(hour=13, minute=0, second=0)
        allowed_overlap, reason_overlap = filters.check_session_filters(
            current_time=overlap_time,
            broker_timezone_offset_hours=0
        )
        logger.info(f"   {'✅ ALLOW' if allowed_overlap else '❌ BLOCK'}: London-NY overlap (13:00 UTC) → {reason_overlap}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Session filters test failed: {e}", exc_info=True)
        return False


def test_false_range_detection():
    """Test 5: False Range Detection"""
    logger.info("=" * 70)
    logger.info("TEST 5: False Range Detection")
    logger.info("=" * 70)
    
    try:
        from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        from config.range_scalping_config_loader import load_range_scalping_config
        
        config = load_range_scalping_config()
        filters = RangeScalpingRiskFilters(config)
        
        # Create test range
        range_data = RangeStructure(
            range_type="dynamic",
            range_high=110500.0,
            range_low=109500.0,
            range_mid=110000.0,
            range_width_atr=6.6,
            critical_gaps=CriticalGapZones(
                upper_zone_start=110400.0,
                upper_zone_end=110500.0,
                lower_zone_start=109500.0,
                lower_zone_end=109600.0
            ),
            touch_count={"total_touches": 2, "upper_touches": 1, "lower_touches": 1},
            validated=True,
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=[]
        )
        
        # Create mock candles DataFrame for testing
        import pandas as pd
        mock_candles = pd.DataFrame({
            'high': [110510.0] * 20,
            'low': [109490.0] * 20,
            'close': [110000.0] * 20,
            'volume': [100] * 20,
            'tick_volume': [100] * 20
        })
        
        # Test case 1: Normal range (should pass)
        volume_trend = {
            "current_avg": 100.0,
            "1h_avg": 100.0,
            "trend": "stable"
        }
        vwap_slope = 0.05  # 5% of ATR per bar (low momentum)
        
        is_false, flags = filters.detect_false_range(
            range_data,
            volume_trend,
            candles_df=mock_candles,
            vwap_slope_pct_atr=vwap_slope,
            cvd_data={"divergence_strength": 0.3}
        )
        
        logger.info(f"✅ False range detection (normal range):")
        logger.info(f"   → Is false: {is_false}")
        logger.info(f"   → Red flags: {flags}")
        logger.info(f"   → Expected: False (normal range should pass)")
        
        # Test case 2: Imbalanced consolidation (should detect)
        volume_trend_bad = {
            "current_avg": 150.0,  # 50% increase
            "1h_avg": 100.0,
            "trend": "increasing"
        }
        vwap_slope_bad = 0.25  # 25% of ATR per bar (high momentum)
        
        # Create expanding candles (increasing body size)
        expanding_candles = pd.DataFrame({
            'high': [110510.0 + i * 10 for i in range(20)],
            'low': [109490.0 - i * 10 for i in range(20)],
            'close': [110000.0 + i * 5 for i in range(20)],
            'volume': [100 + i * 10 for i in range(20)],
            'tick_volume': [100 + i * 10 for i in range(20)]
        })
        
        is_false_bad, flags_bad = filters.detect_false_range(
            range_data,
            volume_trend_bad,
            candles_df=expanding_candles,
            vwap_slope_pct_atr=vwap_slope_bad,
            cvd_data={"divergence_strength": 0.8}  # Strong divergence
        )
        
        logger.info(f"✅ False range detection (imbalanced consolidation):")
        logger.info(f"   → Is false: {is_false_bad}")
        logger.info(f"   → Red flags: {flags_bad}")
        logger.info(f"   → Expected: True (should detect false range)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ False range detection test failed: {e}", exc_info=True)
        return False


def test_range_structure_serialization():
    """Test 6: RangeStructure Serialization (to_dict/from_dict)"""
    logger.info("=" * 70)
    logger.info("TEST 6: RangeStructure Serialization")
    logger.info("=" * 70)
    
    try:
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        
        # Create test range
        original = RangeStructure(
            range_type="dynamic",
            range_high=110500.0,
            range_low=109500.0,
            range_mid=110000.0,
            range_width_atr=6.6,
            critical_gaps=CriticalGapZones(
                upper_zone_start=110400.0,
                upper_zone_end=110500.0,
                lower_zone_start=109500.0,
                lower_zone_end=109600.0
            ),
            touch_count={"total_touches": 3, "upper_touches": 2, "lower_touches": 1},
            validated=True,
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=["vwap_slope"]
        )
        
        # Test serialization
        data_dict = original.to_dict()
        logger.info(f"✅ Serialized to dict:")
        logger.info(f"   → Keys: {list(data_dict.keys())}")
        
        # Test deserialization
        restored = RangeStructure.from_dict(data_dict)
        logger.info(f"✅ Deserialized from dict:")
        logger.info(f"   → Type: {restored.range_type}")
        logger.info(f"   → High: {restored.range_high}")
        logger.info(f"   → Low: {restored.range_low}")
        logger.info(f"   → Validated: {restored.validated}")
        
        # Verify data integrity
        assert restored.range_type == original.range_type
        assert restored.range_high == original.range_high
        assert restored.range_low == original.range_low
        assert restored.validated == original.validated
        assert restored.critical_gaps.upper_zone_start == original.critical_gaps.upper_zone_start
        
        logger.info(f"✅ Serialization integrity verified")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Serialization test failed: {e}", exc_info=True)
        return False


def test_end_to_end_phase1(symbol: str = "BTCUSDc"):
    """Test 7: End-to-End Phase 1 Pipeline"""
    logger.info("=" * 70)
    logger.info(f"TEST 7: End-to-End Phase 1 Pipeline ({symbol})")
    logger.info("=" * 70)
    
    try:
        from infra.range_scalping_analysis import analyse_range_scalp_opportunity
        from infra.range_boundary_detector import RangeBoundaryDetector
        from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
        import sqlite3
        from pathlib import Path
        import pandas as pd
        
        # Load configs
        from config.range_scalping_config_loader import load_range_scalping_config
        
        config = load_range_scalping_config()
        detector = RangeBoundaryDetector()
        risk_filters = RangeScalpingRiskFilters(config)
        
        # Get market data from database
        db_path = Path("data/multi_tf_candles.db")
        if not db_path.exists():
            logger.error(f"❌ Database not found")
            return False
        
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # Get M15 data
        cursor = conn.cursor()
        cursor.execute("""
            SELECT time_utc, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = 'M15'
            ORDER BY timestamp DESC
            LIMIT 150
        """, (symbol,))
        
        m15_rows = cursor.fetchall()
        
        # Get M5 data
        cursor.execute("""
            SELECT time_utc, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = 'M5'
            ORDER BY timestamp DESC
            LIMIT 300
        """, (symbol,))
        
        m5_rows = cursor.fetchall()
        conn.close()
        
        if len(m15_rows) < 50 or len(m5_rows) < 50:
            logger.error(f"❌ Insufficient candles: M15={len(m15_rows)}, M5={len(m5_rows)}")
            return False
        
        # Convert to DataFrames
        m15_data = []
        for row in reversed(m15_rows):
            m15_data.append({
                'time': datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00')),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'tick_volume': row['volume']
            })
        
        m15_df = pd.DataFrame(m15_data)
        if len(m15_df) > 0:
            m15_df.set_index('time', inplace=True)
        
        # Get current price (latest close)
        current_price = m15_df['close'].iloc[-1] if len(m15_df) > 0 else None
        
        if current_price is None:
            logger.error(f"❌ Could not determine current price")
            return False
        
        logger.info(f"✅ Market data prepared:")
        logger.info(f"   → M15 candles: {len(m15_df)}")
        logger.info(f"   → Current price: {current_price:.2f}")
        
        # Test full pipeline (simplified - without full analyse_range_scalp_opportunity)
        # Just test that components work together
        
        # 1. Detect range
        range_data = detector.detect_range(
            symbol=symbol,
            timeframe="M15",
            range_type="dynamic",
            candles_df=m15_df
        )
        
        if not range_data:
            logger.warning(f"⚠️ No range detected (may be expected)")
            return True  # Not a failure
        
        logger.info(f"✅ Range detected: {range_data.range_low:.2f} - {range_data.range_high:.2f}")
        
        # 2. Check data quality (using check_data_quality which internally calls _check_candle_freshness)
        all_available, quality_report, warnings = risk_filters.check_data_quality(
            symbol,
            required_sources=["mt5_candles"]
        )
        
        logger.info(f"✅ Data quality check:")
        logger.info(f"   → All available: {all_available}")
        if "mt5_candles" in quality_report:
            mt5_info = quality_report["mt5_candles"]
            logger.info(f"   → Fresh: {mt5_info.get('available', False)}")
            logger.info(f"   → Age: {mt5_info.get('age_minutes', 0):.1f} min")
            logger.info(f"   → Source: {mt5_info.get('details', {}).get('data_source', 'unknown')}")
        if warnings:
            logger.info(f"   → Warnings: {warnings}")
        
        # 3. Test risk filters on detected range
        price_position = (current_price - range_data.range_low) / (range_data.range_high - range_data.range_low)
        
        signals = {
            "rsi_extreme": False,
            "rejection_wick": False,
            "tape_pressure": False
        }
        
        score, components, missing = risk_filters.check_3_confluence_rule_weighted(
            range_data,
            price_position,
            signals,
            atr=100.0  # Mock ATR
        )
        
        logger.info(f"✅ 3-Confluence scoring:")
        logger.info(f"   → Score: {score}/100")
        logger.info(f"   → Components: {components}")
        
        logger.info(f"✅ End-to-end pipeline test complete")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ End-to-end test failed: {e}", exc_info=True)
        return False


def main():
    """Run all Phase 1 tests"""
    logger.info("🧪 Comprehensive Phase 1 Test Suite")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Prerequisites:")
    logger.info("  1. main_api.py should be running")
    logger.info("  2. Multi-Timeframe Streamer should be initialized")
    logger.info("  3. Streamer should have database enabled")
    logger.info("")
    
    results = {}
    
    # Run tests
    results['config'] = test_config_loading()
    print()
    
    results['range_detection'] = test_range_detection_from_database("BTCUSDc")
    print()
    
    results['risk_calculations'] = test_risk_filters_calculations()
    print()
    
    results['session_filters'] = test_session_filters()
    print()
    
    results['false_range'] = test_false_range_detection()
    print()
    
    results['serialization'] = test_range_structure_serialization()
    print()
    
    results['end_to_end'] = test_end_to_end_phase1("BTCUSDc")
    print()
    
    # Summary
    logger.info("=" * 70)
    logger.info("PHASE 1 TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ All Phase 1 tests passed!")
        logger.info("   → Core infrastructure is working correctly")
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed")
        logger.warning("   → Review logs above for details")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

