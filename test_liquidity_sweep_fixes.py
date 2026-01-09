"""
Quick Test Script for Liquidity Sweep Reversal Engine Fixes

Tests:
1. Price extraction fallback when detect_sweep returns 0.0
2. Score normalization capped at 100%
3. Duplicate notification prevention
4. Proper sweep type/price extraction
"""

import sys
from pathlib import Path
import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, AsyncMock

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock dependencies
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Mock pandas and numpy if not available
try:
    import pandas as pd
except ImportError:
    sys.modules['pandas'] = MagicMock()
    # Create minimal DataFrame mock
    class MockDataFrame:
        def __init__(self, data=None):
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                self.data = data
                self.columns = list(data[0].keys()) if data else []
            else:
                self.data = []
                self.columns = []
        def __len__(self):
            return len(self.data) if hasattr(self, 'data') else 0
        def __getitem__(self, key):
            if key in self.columns:
                return [row.get(key, 0) for row in self.data]
            return []
        def tail(self, n):
            return MockDataFrame(self.data[-n:]) if self.data else MockDataFrame()
        def iloc(self, index):
            if isinstance(index, int):
                return self.data[index] if 0 <= index < len(self.data) else {}
            elif hasattr(index, '__iter__'):
                return [self.data[i] if 0 <= i < len(self.data) else {} for i in index]
            return {}
    sys.modules['pandas'].DataFrame = MockDataFrame

try:
    import numpy as np
except ImportError:
    sys.modules['numpy'] = MagicMock()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def test_price_extraction_fallback():
    """Test that price is extracted from candle data when detect_sweep returns 0.0"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Price Extraction Fallback")
    logger.info("="*70)
    
    try:
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from infra.mt5_service import MT5Service
        
        # Create mock MT5Service
        mock_mt5_service = Mock(spec=MT5Service)
        
        # Create engine
        engine = LiquiditySweepReversalEngine(
            mt5_service=mock_mt5_service,
            intelligent_exit_manager=None,
            discord_notifier=None,
            config_path="config/liquidity_sweep_config.json"
        )
        
        # Mock candles with a clear sweep pattern - need at least 10 candles for proper analysis
        base_time = datetime.now(timezone.utc)
        m1_candles = []
        for i in range(20):
            m1_candles.append({
                "time": base_time,
                "open": 105800.0 + i * 5,
                "high": 105820.0 + i * 5,
                "low": 105790.0 + i * 5,
                "close": 105810.0 + i * 5,
                "volume": 1000 + i * 50
            })
        # Last candle - bearish sweep (large range, volume spike)
        m1_candles[-1] = {
            "time": base_time,
            "open": 105900.0,
            "high": 105910.0,
            "low": 105830.0,  # Swept below recent low
            "close": 105870.0,  # Closed back up
            "volume": 2000  # Volume spike
        }
        
        # Mock detect_sweep to return sweep detected but price = 0.0 (simulating the bug)
        with patch('infra.liquidity_sweep_reversal_engine.detect_sweep') as mock_detect_sweep, \
             patch('infra.liquidity_sweep_reversal_engine.get_candles') as mock_get_candles, \
             patch('infra.liquidity_sweep_reversal_engine.calculate_atr') as mock_atr:
            
            # Mock detect_sweep returning sweep but price = 0.0
            mock_detect_sweep.return_value = {
                "sweep_bull": False,
                "sweep_bear": True,  # Bearish sweep detected
                "depth": 1.5,
                "bars_ago": 0,
                "sweep_price": 0.0,  # BUG: Price is 0.0
                "bull_depth": 0.0,
                "bear_depth": 1.5
            }
            
            # ATR = 30 points, candle range = 80 points (2.67x ATR - meets condition)
            mock_atr.return_value = 30.0
            
            # Mock other required conditions to pass
            with patch.object(engine, 'check_macro_context', new_callable=AsyncMock) as mock_macro:
                mock_macro.return_value = ("bearish", 75.0)
                
                # Test setup context check
                setup_detected, setup_score, setup_details = await engine.check_setup_context(
                    "BTCUSDc", m1_candles
                )
                
                logger.info(f"Setup Detected: {setup_detected}")
                logger.info(f"Setup Score: {setup_score:.1f}%")
                logger.info(f"Setup Details: {setup_details}")
                
                # Verify price fallback worked - check setup_details even if not fully detected
                sweep_type = setup_details.get("sweep_type", "")
                sweep_price = setup_details.get("sweep_price", 0.0)
                
                logger.info(f"\n✓ Sweep Type: {sweep_type}")
                logger.info(f"✓ Sweep Price: {sweep_price}")
                
                # The key test: even though detect_sweep returned price=0.0,
                # the fallback should extract price from candle low (105830.0)
                if sweep_type == "bear":
                    # Handle numpy types
                    price_value = float(sweep_price) if hasattr(sweep_price, '__float__') else sweep_price
                    if price_value > 0 and price_value == 105830.0:
                        logger.info("✅ PASS: Price extraction fallback worked!")
                        logger.info(f"   → Price extracted from candle low: {price_value:.5f}")
                        logger.info(f"   → Original detect_sweep price was 0.0, fallback used candle data")
                        return True
                    else:
                        logger.error(f"❌ FAIL: Price={price_value}, expected 105830.0")
                        return False
                else:
                    logger.error(f"❌ FAIL: Type={sweep_type}, expected 'bear'")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def test_score_normalization():
    """Test that scores are properly normalized and capped at 100%"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Score Normalization (Max 100%)")
    logger.info("="*70)
    
    try:
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from infra.mt5_service import MT5Service
        
        mock_mt5_service = Mock(spec=MT5Service)
        engine = LiquiditySweepReversalEngine(
            mt5_service=mock_mt5_service,
            intelligent_exit_manager=None,
            discord_notifier=None
        )
        
        # Create test candles with all conditions met (should score > 100% before fix)
        m1_candles = []
        for i in range(30):
            m1_candles.append({
                "time": datetime.now(timezone.utc),
                "open": 105800.0 + i * 10,
                "high": 105820.0 + i * 10,
                "low": 105790.0 + i * 10,
                "close": 105810.0 + i * 10,
                "volume": 1500 + i * 50
            })
        
        with patch('infra.liquidity_sweep_reversal_engine.detect_sweep') as mock_detect_sweep, \
             patch('infra.liquidity_sweep_reversal_engine.calculate_atr') as mock_atr:
            
            mock_detect_sweep.return_value = {
                "sweep_bull": True,
                "sweep_bear": False,
                "depth": 2.0,
                "bars_ago": 0,
                "sweep_price": 105850.0,
                "bull_depth": 2.0,
                "bear_depth": 0.0
            }
            
            mock_atr.return_value = 30.0
            
            with patch.object(engine, 'check_macro_context', new_callable=AsyncMock) as mock_macro:
                mock_macro.return_value = ("bullish", 80.0)
                
                setup_detected, setup_score, setup_details = await engine.check_setup_context(
                    "BTCUSDc", m1_candles
                )
                
                logger.info(f"Setup Score: {setup_score:.1f}%")
                
                if setup_score <= 100.0:
                    logger.info("✅ PASS: Score is properly capped at 100%")
                    return True
                else:
                    logger.error(f"❌ FAIL: Score exceeds 100%: {setup_score:.1f}%")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def test_duplicate_notification_prevention():
    """Test that duplicate notifications are prevented"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Duplicate Notification Prevention")
    logger.info("="*70)
    
    try:
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from infra.mt5_service import MT5Service
        
        # Create mock Discord notifier
        mock_discord = Mock()
        mock_discord.send_message = Mock()
        
        mock_mt5_service = Mock(spec=MT5Service)
        engine = LiquiditySweepReversalEngine(
            mt5_service=mock_mt5_service,
            intelligent_exit_manager=None,
            discord_notifier=mock_discord
        )
        
        # Set notification tracking
        engine.recent_notifications = {}
        
        # Simulate first notification
        notification_key = "BTCUSDc_bear_105838.62"
        now = datetime.now(timezone.utc)
        engine.recent_notifications[notification_key] = now
        
        # Try to send duplicate notification immediately (should be suppressed)
        from datetime import timedelta
        m1_candles = [
            {"time": now, "open": 105800.0, "high": 105850.0, "low": 105820.0, "close": 105840.0, "volume": 1000},
        ]
        
        with patch('infra.liquidity_sweep_reversal_engine.detect_sweep') as mock_detect_sweep, \
             patch('infra.liquidity_sweep_reversal_engine.calculate_atr') as mock_atr, \
             patch('infra.liquidity_sweep_reversal_engine.get_candles') as mock_get_candles:
            
            mock_detect_sweep.return_value = {
                "sweep_bull": False,
                "sweep_bear": True,
                "depth": 1.5,
                "bars_ago": 0,
                "sweep_price": 105838.62,
                "bull_depth": 0.0,
                "bear_depth": 1.5
            }
            
            mock_atr.return_value = 50.0
            mock_get_candles.return_value = m1_candles
            
            with patch.object(engine, 'check_macro_context', new_callable=AsyncMock) as mock_macro:
                mock_macro.return_value = ("bearish", 75.0)
                
                # Process symbol (should detect duplicate and skip)
                await engine.process_symbol("BTCUSDc")
                
                # Check if notification was sent
                notification_count = mock_discord.send_message.call_count
                
                logger.info(f"Notification calls: {notification_count}")
                
                if notification_count == 0:
                    logger.info("✅ PASS: Duplicate notification was suppressed")
                    return True
                else:
                    logger.warning(f"⚠️ Notification was sent ({notification_count} times)")
                    # Check if it's been more than 2 minutes
                    if notification_key in engine.recent_notifications:
                        time_diff = (datetime.now(timezone.utc) - engine.recent_notifications[notification_key]).total_seconds()
                        if time_diff < 120:
                            logger.error("❌ FAIL: Duplicate notification sent within 2 minutes")
                            return False
                        else:
                            logger.info("✓ Notification allowed (more than 2 minutes passed)")
                            return True
                    return False
                    
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def test_sweep_type_extraction():
    """Test that sweep type is correctly extracted (bull vs bear)"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Sweep Type Extraction")
    logger.info("="*70)
    
    try:
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from infra.mt5_service import MT5Service
        
        mock_mt5_service = Mock(spec=MT5Service)
        engine = LiquiditySweepReversalEngine(
            mt5_service=mock_mt5_service,
            intelligent_exit_manager=None,
            discord_notifier=None
        )
        
        # Test bullish sweep - need enough candles for all conditions
        base_time = datetime.now(timezone.utc)
        m1_candles_bull = []
        for i in range(20):
            m1_candles_bull.append({
                "time": base_time,
                "open": 105800.0 + i * 5,
                "high": 105820.0 + i * 5,
                "low": 105790.0 + i * 5,
                "close": 105810.0 + i * 5,
                "volume": 1000 + i * 50
            })
        # Last candle - bullish sweep (large range, volume spike)
        m1_candles_bull[-1] = {
            "time": base_time,
            "open": 105900.0,
            "high": 105980.0,  # Swept above recent high
            "low": 105890.0,
            "close": 105920.0,  # Closed back down
            "volume": 2000  # Volume spike
        }
        
        with patch('infra.liquidity_sweep_reversal_engine.detect_sweep') as mock_detect_sweep, \
             patch('infra.liquidity_sweep_reversal_engine.calculate_atr') as mock_atr:
            
            mock_detect_sweep.return_value = {
                "sweep_bull": True,
                "sweep_bear": False,
                "depth": 1.5,
                "bars_ago": 0,
                "sweep_price": 105980.0,
                "bull_depth": 1.5,
                "bear_depth": 0.0
            }
            
            # ATR = 30 points, candle range = 90 points (3x ATR - meets condition)
            mock_atr.return_value = 30.0
            
            setup_detected, setup_score, setup_details = await engine.check_setup_context(
                "BTCUSDc", m1_candles_bull
            )
            
            # Check setup_details regardless of full detection
            sweep_type = setup_details.get("sweep_type", "")
            sweep_price = setup_details.get("sweep_price", 0.0)
            
            logger.info(f"Bullish Sweep Test:")
            logger.info(f"  Type: {sweep_type}")
            logger.info(f"  Price: {sweep_price}")
            logger.info(f"  Setup Detected: {setup_detected} (not required for this test)")
            
            # Handle numpy types
            price_value = float(sweep_price) if hasattr(sweep_price, '__float__') else sweep_price
            
            if sweep_type == "bull" and price_value == 105980.0:
                logger.info("✅ PASS: Bullish sweep correctly identified")
                logger.info(f"   → Type: {sweep_type}, Price: {price_value:.5f}")
                return True
            else:
                logger.error(f"❌ FAIL: Expected bull/105980.0, got {sweep_type}/{price_value}")
                return False
                
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all tests and report results"""
    logger.info("\n" + "="*70)
    logger.info("LIQUIDITY SWEEP REVERSAL ENGINE - FIX VALIDATION TESTS")
    logger.info("="*70)
    
    results = {}
    
    # Run tests
    results["price_extraction"] = await test_price_extraction_fallback()
    results["score_normalization"] = await test_score_normalization()
    results["duplicate_prevention"] = await test_duplicate_notification_prevention()
    results["type_extraction"] = await test_sweep_type_extraction()
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

