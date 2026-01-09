"""
Test Binance/Order Flow Integration with Intelligent Exit Manager
"""

import logging
from infra.mt5_service import MT5Service
from infra.binance_service import BinanceService
from infra.order_flow_service import OrderFlowService
from infra.intelligent_exit_manager import create_exit_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_exit_manager_integration():
    """Test that exit manager correctly integrates with Binance and order flow"""
    
    print("\n" + "="*70)
    print("🧪 Testing Intelligent Exit Manager Integration")
    print("="*70 + "\n")
    
    # Initialize services
    logger.info("1️⃣ Initializing MT5 service...")
    mt5_service = MT5Service()
    if not mt5_service.connect():
        logger.error("❌ MT5 connection failed")
        return False
    logger.info("✅ MT5 connected")
    
    logger.info("\n2️⃣ Initializing Binance service...")
    binance_service = BinanceService()
    # Note: Not starting streams for this test, just checking integration
    logger.info("✅ Binance service initialized")
    
    logger.info("\n3️⃣ Initializing Order Flow service...")
    order_flow_service = OrderFlowService()
    logger.info("✅ Order Flow service initialized")
    
    logger.info("\n4️⃣ Creating Exit Manager with all services...")
    try:
        exit_manager = create_exit_manager(
            mt5_service,
            binance_service=binance_service,
            order_flow_service=order_flow_service
        )
        logger.info("✅ Exit manager created successfully!")
        
        # Verify integration
        assert exit_manager.binance_service is not None, "Binance service not attached"
        assert exit_manager.order_flow_service is not None, "Order flow service not attached"
        logger.info("✅ Services correctly attached to exit manager")
        
    except Exception as e:
        logger.error(f"❌ Exit manager creation failed: {e}")
        return False
    
    logger.info("\n5️⃣ Testing fallback (no services)...")
    try:
        exit_manager_basic = create_exit_manager(mt5_service)
        assert exit_manager_basic.binance_service is None, "Should have no Binance service"
        assert exit_manager_basic.order_flow_service is None, "Should have no order flow service"
        logger.info("✅ Fallback mode works (MT5 only)")
    except Exception as e:
        logger.error(f"❌ Fallback test failed: {e}")
        return False
    
    logger.info("\n6️⃣ Checking exit manager methods...")
    methods_to_check = [
        '_check_binance_momentum',
        '_check_whale_orders',
        '_check_liquidity_voids',
        '_calculate_momentum'
    ]
    
    for method_name in methods_to_check:
        if hasattr(exit_manager, method_name):
            logger.info(f"   ✅ {method_name} - found")
        else:
            logger.error(f"   ❌ {method_name} - MISSING")
            return False
    
    logger.info("\n7️⃣ Checking graceful degradation...")
    # Create exit manager with services but not started
    exit_manager_offline = create_exit_manager(
        mt5_service,
        binance_service=binance_service,  # Initialized but not running
        order_flow_service=order_flow_service  # Initialized but not running
    )
    
    # Check that it won't crash if we call check_exits with offline services
    try:
        actions = exit_manager_offline.check_exits()
        logger.info(f"✅ check_exits() works with offline services (returned {len(actions)} actions)")
    except Exception as e:
        logger.error(f"❌ check_exits() crashed with offline services: {e}")
        return False
    
    print("\n" + "="*70)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("="*70)
    print("\n📊 Summary:")
    print("   ✅ Exit manager creates with Binance + order flow")
    print("   ✅ Exit manager creates without services (fallback)")
    print("   ✅ All new methods present")
    print("   ✅ Graceful degradation when services offline")
    print("\n🚀 Ready for live trade testing!")
    print("\n📋 Next steps:")
    print("   1. Start desktop_agent.py")
    print("   2. Execute a trade")
    print("   3. Monitor logs for:")
    print("      - 🔴 Momentum reversal alerts")
    print("      - 🐋 Whale order alerts")
    print("      - ⚠️ Liquidity void warnings")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = test_exit_manager_integration()
        if not success:
            print("\n❌ Integration tests FAILED")
            exit(1)
    except Exception as e:
        logger.error(f"❌ Test error: {e}", exc_info=True)
        exit(1)

