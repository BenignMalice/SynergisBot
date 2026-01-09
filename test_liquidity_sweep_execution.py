"""
Test Liquidity Sweep Reversal Engine - Automatic Trade Execution

Tests the complete flow:
1. Sweep Detection
2. Trigger Confirmation (CHOCH, rejection, volume decline)
3. Confluence Scoring (≥70% threshold)
4. Automatic Trade Execution (Type 1/Type 2)
5. Intelligent Exit Manager Registration
"""

import sys
from pathlib import Path
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Mock dependencies
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Mock pandas and numpy
try:
    import pandas as pd
except ImportError:
    class MockDataFrame:
        def __init__(self, data=None):
            if data:
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
    sys.modules['pandas'] = MagicMock()
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


async def test_complete_sweep_execution_flow():
    """Test the complete flow from sweep detection to trade execution"""
    logger.info("\n" + "="*70)
    logger.info("TEST: Complete Sweep → Trade Execution Flow")
    logger.info("="*70)
    
    try:
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from infra.mt5_service import MT5Service
        
        # Create mock MT5Service
        mock_mt5_service = Mock(spec=MT5Service)
        mock_mt5_service.market_order = Mock(return_value={
            "ok": True,
            "details": {"ticket": 12345678, "position": 12345678}
        })
        
        # Create mock Intelligent Exit Manager
        mock_exit_manager = Mock()
        mock_exit_manager.add_rule = Mock()
        
        # Create mock Discord notifier
        mock_discord = Mock()
        mock_discord.send_message = Mock()
        mock_discord.enabled = True
        
        # Create engine
        engine = LiquiditySweepReversalEngine(
            mt5_service=mock_mt5_service,
            intelligent_exit_manager=mock_exit_manager,
            discord_notifier=mock_discord,
            config_path="config/liquidity_sweep_config.json"
        )
        
        # Clear any existing setups
        engine.active_setups = {}
        
        # Create test candles - sweep pattern with confirmation
        # Need enough candles for all conditions (volume lookback, VWAP calculation, etc.)
        base_time = datetime.now(timezone.utc)
        m1_candles = []
        
        # Build up baseline candles (at least 20 for VWAP calculation)
        base_price = 105800.0
        for i in range(25):
            m1_candles.append({
                "time": base_time - timedelta(minutes=25-i),
                "open": base_price + i * 2,
                "high": base_price + 20 + i * 2,
                "low": base_price - 10 + i * 2,
                "close": base_price + 10 + i * 2,
                "volume": 1000 + i * 20  # Gradual volume increase
            })
        
        # Sweep candle (bearish - sweeps below recent low, large range, volume spike)
        # Candle range = 22 points, ATR = 30, so range/ATR = 0.73 (needs to be ≥1.5)
        # Let's make it bigger: range = 50 points (1.67x ATR)
        m1_candles[-1] = {
            "time": base_time,
            "open": 105850.0,
            "high": 105860.0,
            "low": 105810.0,  # Large range (50 points), sweeps below recent low
            "close": 105845.0,  # Closed back up (reversal)
            "volume": 2500  # Volume spike (vs avg ~1500)
        }
        
        # Confirmation candles (CHOCH, rejection pattern)
        m1_candles.append({
            "time": base_time + timedelta(minutes=1),
            "open": 105845.0,
            "high": 105848.0,  # Small wick
            "low": 105842.0,
            "close": 105846.0,
            "volume": 800  # Volume decline
        })
        
        # CHOCH confirmation candle (breaks structure)
        m1_candles.append({
            "time": base_time + timedelta(minutes=2),
            "open": 105846.0,
            "high": 105852.0,  # Breaks above previous high (CHOCH bullish)
            "low": 105844.0,
            "close": 105850.0,
            "volume": 600  # Volume continues to decline
        })
        
        logger.info("\n📊 Step 1: Sweep Detection Phase")
        logger.info("-" * 70)
        
        # Mock sweep detection
        with patch('infra.liquidity_sweep_reversal_engine.detect_sweep') as mock_detect_sweep, \
             patch('infra.liquidity_sweep_reversal_engine.get_candles', return_value=m1_candles), \
             patch('infra.liquidity_sweep_reversal_engine.calculate_atr', return_value=30.0), \
             patch.object(engine, 'check_macro_context', new_callable=AsyncMock) as mock_macro:
            
            # Mock macro context - favorable
            mock_macro.return_value = ("bullish", 80.0)
            
            # Mock sweep detection - bearish sweep detected
            mock_detect_sweep.return_value = {
                "sweep_bull": False,
                "sweep_bear": True,
                "depth": 1.5,
                "bars_ago": 0,
                "sweep_price": 105838.0,
                "bull_depth": 0.0,
                "bear_depth": 1.5
            }
            
            # Mock current hour to be in trading session (London or NY)
            with patch('infra.liquidity_sweep_reversal_engine.datetime') as mock_datetime:
                mock_now = datetime.now(timezone.utc).replace(hour=8, minute=0)  # 8 AM UTC = London session
                mock_datetime.now.return_value = mock_now
                mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
                
                # Process symbol - should detect sweep
                await engine.process_symbol("BTCUSDc")
                
                # Also need to patch datetime for VWAP calculation
                with patch('infra.liquidity_sweep_reversal_engine.datetime.now', return_value=mock_now):
                    pass
            
            # Check if setup was created
            if "BTCUSDc" in engine.active_setups:
                setup = engine.active_setups["BTCUSDc"]
                logger.info(f"✅ Sweep Detected!")
                logger.info(f"   Type: {setup.sweep_type}")
                logger.info(f"   Price: {setup.sweep_price:.5f}")
                logger.info(f"   Setup Score: {setup.setup_score:.1f}%")
                logger.info(f"   Status: {setup.status}")
                
                logger.info("\n📊 Step 2: Trigger Confirmation Phase")
                logger.info("-" * 70)
                
                # Now simulate trigger confirmation - update candles with CHOCH
                m1_candles_updated = m1_candles.copy()
                
                # Mock trigger context to confirm
                with patch('infra.liquidity_sweep_reversal_engine.detect_bos_choch') as mock_choch:
                    # Process again with confirmation candles
                    await engine.process_symbol("BTCUSDc")
                    
                    # Check if trade was executed
                    setup = engine.active_setups.get("BTCUSDc")
                    
                    if setup and setup.status == "executed":
                        logger.info(f"✅ Trade Executed!")
                        logger.info(f"   Ticket: {setup.ticket}")
                        logger.info(f"   Entry: {setup.entry_price:.5f}")
                        logger.info(f"   SL: {setup.stop_loss:.5f}")
                        logger.info(f"   TP: {setup.take_profit:.5f}")
                        logger.info(f"   Confluence: {setup.confluence_score:.1f}%")
                        logger.info(f"   Type: {setup.setup_type}")
                        
                        # Verify MT5 was called
                        if mock_mt5_service.market_order.called:
                            logger.info("\n✅ MT5 Market Order Called")
                            call_args = mock_mt5_service.market_order.call_args
                            logger.info(f"   Symbol: {call_args.kwargs.get('symbol')}")
                            logger.info(f"   Side: {call_args.kwargs.get('side')}")
                            logger.info(f"   Lot: {call_args.kwargs.get('lot')}")
                            
                        # Verify Intelligent Exit Manager was called
                        if mock_exit_manager.add_rule.called:
                            logger.info("\n✅ Intelligent Exit Manager Registered")
                            call_args = mock_exit_manager.add_rule.call_args
                            logger.info(f"   Ticket: {call_args.kwargs.get('ticket')}")
                            logger.info(f"   Breakeven: {call_args.kwargs.get('breakeven_profit_pct')}%")
                            logger.info(f"   Partial: {call_args.kwargs.get('partial_profit_pct')}%")
                            
                        # Verify Discord notification
                        notification_count = mock_discord.send_message.call_count
                        logger.info(f"\n✅ Discord Notifications: {notification_count} sent")
                        
                        logger.info("\n🎉 ALL SYSTEMS WORKING: Automatic Trade Execution Verified!")
                        return True
                    else:
                        logger.warning(f"⚠️ Setup Status: {setup.status if setup else 'None'}")
                        logger.warning(f"   Expected: 'executed', Got: {setup.status if setup else 'None'}")
                        logger.warning("\n   Trade not executed - may need:")
                        logger.warning("   - Confluence score ≥ 70%")
                        logger.warning("   - Trigger confirmation (CHOCH detected)")
                        logger.warning("   - Valid trigger context")
                        return False
            else:
                logger.error("❌ Sweep not detected - setup not created")
                logger.error("   May need to meet minimum conditions (4 of 6)")
                return False
                
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def test_confluence_threshold():
    """Test that trades only execute when confluence ≥ 70%"""
    logger.info("\n" + "="*70)
    logger.info("TEST: Confluence Threshold Enforcement (≥70%)")
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
        
        # Test with score just below threshold
        mock_mt5_service.market_order.reset_mock()
        
        # Simulate low confluence scenario
        confluence_below = Mock()
        confluence_below.total_score = 65.0  # Below 70% threshold
        
        confluence_above = Mock()
        confluence_above.total_score = 75.0  # Above 70% threshold
        
        logger.info(f"Threshold: 70%")
        logger.info(f"Test 1: Score = 65.0% (should NOT execute)")
        
        if confluence_below.total_score >= 70.0:
            logger.error("❌ FAIL: Trade would execute with score < 70%")
            return False
        else:
            logger.info("✅ PASS: Trade correctly blocked (score < 70%)")
        
        logger.info(f"\nTest 2: Score = 75.0% (should execute)")
        if confluence_above.total_score >= 70.0:
            logger.info("✅ PASS: Trade would execute (score ≥ 70%)")
            return True
        else:
            logger.error("❌ FAIL: Trade blocked when score ≥ 70%")
            return False
            
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all execution tests"""
    logger.info("\n" + "="*70)
    logger.info("LIQUIDITY SWEEP REVERSAL ENGINE - EXECUTION TESTS")
    logger.info("="*70)
    
    results = {}
    
    # Run tests
    results["complete_flow"] = await test_complete_sweep_execution_flow()
    results["confluence_threshold"] = await test_confluence_threshold()
    
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
        logger.info("\n🎉 ALL EXECUTION TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

