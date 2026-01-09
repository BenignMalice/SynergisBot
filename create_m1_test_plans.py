"""Create test M1 micro-scalp plans to verify 10-second intervals"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatgpt_auto_execution_integration import ChatGPTAutoExecution
from infra.mt5_service import MT5Service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_current_price(symbol: str) -> float:
    """Get current market price for a symbol"""
    try:
        mt5_service = MT5Service()
        quote = mt5_service.get_quote(symbol)
        if quote:
            return (quote.bid + quote.ask) / 2
        return None
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        return None

def create_test_plans():
    """Create test M1 micro-scalp plans for XAUUSD and BTCUSD"""
    
    integration = ChatGPTAutoExecution()
    
    # Get current prices
    xau_price = get_current_price("XAUUSDc")
    btc_price = get_current_price("BTCUSDc")
    
    if not xau_price:
        logger.warning("Could not get XAUUSD price, using default 4330.0")
        xau_price = 4330.0
    
    if not btc_price:
        logger.warning("Could not get BTCUSD price, using default 90000.0")
        btc_price = 90000.0
    
    plans_created = []
    
    # Test Plan 1: XAUUSD M1 Liquidity Sweep BUY
    logger.info("\n" + "="*80)
    logger.info("Creating XAUUSD M1 Liquidity Sweep BUY plan...")
    logger.info("="*80)
    
    try:
        result1 = integration.create_trade_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=xau_price - 5.0,  # 5 points below current price
            stop_loss=xau_price - 10.0,
            take_profit=xau_price + 10.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",  # M1 timeframe
                "liquidity_sweep": True,  # Micro-scalp indicator
                "price_near": xau_price - 5.0,
                "tolerance": 2.0,  # Tight tolerance for M1
                "rejection_wick": True  # Additional confirmation
            },
            expires_hours=2,  # Short expiry for testing
            notes="TEST: M1 Liquidity Sweep BUY - Should use 10s intervals"
        )
        
        if result1.get("success"):
            plans_created.append(("XAUUSDc", "BUY", "liquidity_sweep", result1.get("plan_id")))
            logger.info(f"[OK] Plan created: {result1.get('plan_id')}")
        else:
            logger.error(f"[FAIL] Failed to create plan: {result1.get('message')}")
    except Exception as e:
        logger.error(f"[ERROR] Exception creating XAUUSD plan: {e}", exc_info=True)
    
    # Test Plan 2: XAUUSD M1 Order Block SELL
    logger.info("\n" + "="*80)
    logger.info("Creating XAUUSD M1 Order Block SELL plan...")
    logger.info("="*80)
    
    try:
        result2 = integration.create_trade_plan(
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=xau_price + 5.0,  # 5 points above current price
            stop_loss=xau_price + 10.0,
            take_profit=xau_price - 10.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",  # M1 timeframe
                "order_block": True,  # Micro-scalp indicator
                "order_block_type": "bear",  # Bearish order block
                "price_near": xau_price + 5.0,
                "tolerance": 2.0,  # Tight tolerance for M1
                "min_validation_score": 60
            },
            expires_hours=2,  # Short expiry for testing
            notes="TEST: M1 Order Block SELL - Should use 10s intervals"
        )
        
        if result2.get("success"):
            plans_created.append(("XAUUSDc", "SELL", "order_block", result2.get("plan_id")))
            logger.info(f"[OK] Plan created: {result2.get('plan_id')}")
        else:
            logger.error(f"[FAIL] Failed to create plan: {result2.get('message')}")
    except Exception as e:
        logger.error(f"[ERROR] Exception creating XAUUSD plan: {e}", exc_info=True)
    
    # Test Plan 3: BTCUSD M1 VWAP Deviation BUY
    logger.info("\n" + "="*80)
    logger.info("Creating BTCUSD M1 VWAP Deviation BUY plan...")
    logger.info("="*80)
    
    try:
        result3 = integration.create_trade_plan(
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=btc_price - 100.0,  # 100 points below current price
            stop_loss=btc_price - 200.0,
            take_profit=btc_price + 200.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",  # M1 timeframe
                "vwap_deviation": True,  # Micro-scalp indicator
                "vwap_deviation_direction": "below",  # Price below VWAP = mean reversion BUY
                "price_near": btc_price - 100.0,
                "tolerance": 50.0,  # BTCUSD tolerance
            },
            expires_hours=2,  # Short expiry for testing
            notes="TEST: M1 VWAP Deviation BUY - Should use 10s intervals"
        )
        
        if result3.get("success"):
            plans_created.append(("BTCUSDc", "BUY", "vwap_deviation", result3.get("plan_id")))
            logger.info(f"[OK] Plan created: {result3.get('plan_id')}")
        else:
            logger.error(f"[FAIL] Failed to create plan: {result3.get('message')}")
    except Exception as e:
        logger.error(f"[ERROR] Exception creating BTCUSD plan: {e}", exc_info=True)
    
    # Test Plan 4: BTCUSD M1 Equal Lows BUY
    logger.info("\n" + "="*80)
    logger.info("Creating BTCUSD M1 Equal Lows BUY plan...")
    logger.info("="*80)
    
    try:
        result4 = integration.create_trade_plan(
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=btc_price - 150.0,  # 150 points below current price
            stop_loss=btc_price - 300.0,
            take_profit=btc_price + 300.0,
            volume=0.01,
            conditions={
                "timeframe": "M1",  # M1 timeframe
                "equal_lows": True,  # Micro-scalp indicator
                "price_near": btc_price - 150.0,
                "tolerance": 50.0,  # BTCUSD tolerance
            },
            expires_hours=2,  # Short expiry for testing
            notes="TEST: M1 Equal Lows BUY - Should use 10s intervals"
        )
        
        if result4.get("success"):
            plans_created.append(("BTCUSDc", "BUY", "equal_lows", result4.get("plan_id") ))
            logger.info(f"[OK] Plan created: {result4.get('plan_id')}")
        else:
            logger.error(f"[FAIL] Failed to create plan: {result4.get('message')}")
    except Exception as e:
        logger.error(f"[ERROR] Exception creating BTCUSD plan: {e}", exc_info=True)
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"Created {len(plans_created)} test plans:")
    for symbol, direction, condition_type, plan_id in plans_created:
        logger.info(f"  - {symbol} {direction} ({condition_type}): {plan_id}")
    
    logger.info("\n" + "="*80)
    logger.info("VERIFICATION STEPS")
    logger.info("="*80)
    logger.info("1. Run: python check_10s_intervals.py")
    logger.info("2. Check logs for 'Adaptive interval' debug messages")
    logger.info("3. Look for: 'Skipping {plan_id} - only X.Xs since last check (required: 10s)'")
    logger.info("4. Monitor plan check timestamps - should see checks every 10s when price is near entry")
    logger.info("="*80 + "\n")
    
    return plans_created

if __name__ == "__main__":
    try:
        plans = create_test_plans()
        print(f"\n[SUCCESS] Created {len(plans)} test plans")
    except Exception as e:
        logger.error(f"[ERROR] Failed to create test plans: {e}", exc_info=True)
        sys.exit(1)
