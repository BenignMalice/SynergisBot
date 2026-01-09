
"""
API Test for Range Scalping Tool
Tests the tool via desktop_agent registry (simulates API call)

Usage:
    python test_range_scalp_api.py BTCUSD
    python test_range_scalp_api.py XAUUSD
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_range_scalp_api(symbol: str = "BTCUSD"):
    """Test range scalping tool via API/registry"""
    
    logger.info("=" * 80)
    logger.info(f"🧪 API TEST: Range Scalping Analysis")
    logger.info(f"Symbol: {symbol}")
    logger.info("=" * 80)
    
    try:
        # Import desktop_agent registry
        from desktop_agent import registry
        from infra.mt5_service import MT5Service
        
        tool_name = "moneybot.analyse_range_scalp_opportunity"
        
        # Check if tool is registered
        if tool_name not in registry.tools:
            logger.error(f"❌ Tool '{tool_name}' is NOT registered")
            logger.info("\n💡 To register the tool:")
            logger.info("   1. Open desktop_agent_range_scalp_tool.py")
            logger.info("   2. Copy all contents")
            logger.info("   3. Paste into desktop_agent.py at line 6119")
            logger.info("   4. Restart desktop_agent.py")
            return False
        
        logger.info(f"✅ Tool '{tool_name}' is registered")
        
        # Initialize MT5 service if not already initialized
        if registry.mt5_service is None:
            logger.info("📡 Initializing MT5 service for test...")
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                logger.error("❌ Failed to connect to MT5 - test requires MT5 connection")
                return False
            logger.info("✅ MT5 service initialized")
        else:
            logger.info("✅ MT5 service already initialized")
        
        # Initialize Multi-Timeframe Streamer if not already initialized
        try:
            from infra.streamer_data_access import get_streamer, set_streamer
            from infra.multi_timeframe_streamer import MultiTimeframeStreamer, StreamerConfig
            from pathlib import Path
            import json
            
            streamer = get_streamer()
            if streamer is None or not streamer.is_running:
                logger.info("📊 Initializing Multi-Timeframe Streamer for test...")
                
                # Load config if available
                config_path = Path("config/multi_tf_streamer_config.json")
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    
                    # Check if it's weekend (Saturday or Sunday) - only stream BTC on weekends
                    current_day = datetime.now().weekday()  # 5 = Saturday, 6 = Sunday
                    is_weekend = current_day >= 5
                    
                    all_symbols = config_data.get("symbols", ["BTCUSDc", "XAUUSDc", "EURUSDc"])
                    if is_weekend:
                        # Filter to only BTC on weekends
                        symbols_to_stream = [s for s in all_symbols if "BTC" in s.upper()]
                        if not symbols_to_stream:
                            symbols_to_stream = ["BTCUSDc"]
                        logger.info(f"   📅 Weekend detected - streaming BTC only: {symbols_to_stream}")
                    else:
                        symbols_to_stream = all_symbols
                        logger.info(f"   📅 Weekday - streaming all symbols: {symbols_to_stream}")
                    
                    streamer_config = StreamerConfig(
                        symbols=symbols_to_stream,
                        buffer_sizes=config_data.get("buffer_sizes", {
                            "M1": 1440, "M5": 300, "M15": 150, "M30": 100, "H1": 100, "H4": 50
                        }),
                        refresh_intervals=config_data.get("refresh_intervals", {
                            "M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400
                        }),
                        enable_database=False,  # RAM only for test
                        db_path=config_data.get("db_path", "data/multi_tf_candles.db"),
                        retention_days=config_data.get("retention_days", 30)
                    )
                else:
                    # Default configuration
                    # Check if it's weekend (Saturday or Sunday) - only stream BTC on weekends
                    current_day = datetime.now().weekday()  # 5 = Saturday, 6 = Sunday
                    is_weekend = current_day >= 5
                    
                    if is_weekend:
                        default_symbols = ["BTCUSDc"]
                        logger.info(f"   📅 Weekend detected - streaming BTC only: {default_symbols}")
                    else:
                        default_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc"]
                        logger.info(f"   📅 Weekday - streaming all symbols: {default_symbols}")
                    
                    streamer_config = StreamerConfig(
                        symbols=default_symbols,
                        enable_database=False  # RAM only for test
                    )
                
                multi_tf_streamer = MultiTimeframeStreamer(streamer_config, mt5_service=registry.mt5_service)
                await multi_tf_streamer.start()
                
                # Register globally for range scalping system to use
                set_streamer(multi_tf_streamer)
                
                logger.info("✅ Multi-Timeframe Streamer initialized for test")
                
                # Wait a moment for streamer to populate initial data
                await asyncio.sleep(2)
                logger.info("   → Streamer buffers populated")
            else:
                logger.info("✅ Multi-Timeframe Streamer already initialized")
        except Exception as e:
            logger.warning(f"⚠️ Multi-Timeframe Streamer initialization failed: {e}")
            logger.warning("   → Will fallback to direct MT5 calls (may have stale data)")
        
        # Prepare API call arguments
        args = {
            "symbol": symbol,
            "check_risk_filters": True
        }
        
        logger.info(f"📡 Calling tool with args: {args}")
        logger.info("-" * 80)
        
        # Execute tool via registry (simulates API call)
        result = await registry.execute(tool_name, args)
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 API RESPONSE")
        logger.info("=" * 80)
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Error: {result['error']}")
            return False
        
        # Get data
        data = result.get("data", {})
        summary = result.get("summary", "N/A")
        
        logger.info(f"Summary: {summary}")
        logger.info("")
        
        # Range detection
        if data.get("range_detected"):
            logger.info("✅ Range Detected")
            range_struct = data.get("range_structure", {})
            logger.info(f"   Type: {range_struct.get('range_type', 'unknown')}")
            logger.info(f"   High: {range_struct.get('range_high', 0):.2f}")
            logger.info(f"   Low: {range_struct.get('range_low', 0):.2f}")
            logger.info(f"   Mid: {range_struct.get('range_mid', 0):.2f}")
            logger.info(f"   Width (ATR): {range_struct.get('range_width_atr', 0):.2f}")
        else:
            logger.warning("⚠️ No range detected")
            if data.get("error"):
                logger.error(f"   Error: {data['error']}")
        
        # Risk checks
        risk_checks = data.get("risk_checks", {})
        if risk_checks:
            logger.info("")
            logger.info("🔍 Risk Checks:")
            
            if risk_checks.get("risk_filters_skipped"):
                logger.info("   ⚠️ Risk filters were skipped")
            else:
                confluence_score = risk_checks.get("confluence_score", 0)
                logger.info(f"   3-Confluence Score: {confluence_score}/100")
                logger.info(f"   Confluence Passed: {'✅' if risk_checks.get('3_confluence_passed') else '❌'}")
                
                if risk_checks.get("false_range_detected"):
                    logger.warning(f"   ❌ False Range Detected: {', '.join(risk_checks.get('false_range_flags', []))}")
                else:
                    logger.info("   ✅ False Range: None detected")
                
                logger.info(f"   Range Valid: {'✅' if risk_checks.get('range_valid') else '❌'}")
                if not risk_checks.get("range_valid"):
                    logger.warning(f"      Invalidation signals: {', '.join(risk_checks.get('invalidation_signals', []))}")
                
                logger.info(f"   Session Allows: {'✅' if risk_checks.get('session_allows_trading') else '❌'}")
                if not risk_checks.get("session_allows_trading"):
                    logger.warning(f"      Reason: {risk_checks.get('session_reason', 'Unknown')}")
                
                logger.info(f"   Trade Activity: {'✅' if risk_checks.get('trade_activity_sufficient') else '❌'}")
                if not risk_checks.get("trade_activity_sufficient"):
                    logger.warning(f"      Failures: {', '.join(risk_checks.get('activity_failures', []))}")
                
                risk_passed = risk_checks.get("risk_passed", False)
                logger.info(f"   Overall Risk Check: {'✅ PASSED' if risk_passed else '❌ FAILED'}")
        
        # Top strategy
        top_strategy = data.get("top_strategy")
        logger.info("")
        if top_strategy:
            logger.info("🎯 Top Strategy:")
            logger.info(f"   Name: {top_strategy.get('name', 'unknown')}")
            logger.info(f"   Direction: {top_strategy.get('direction', 'N/A')}")
            logger.info(f"   Entry Price: {top_strategy.get('entry_price', 0):.2f}")
            logger.info(f"   Stop Loss: {top_strategy.get('stop_loss', 0):.2f}")
            logger.info(f"   Take Profit: {top_strategy.get('take_profit', 0):.2f}")
            logger.info(f"   R:R Ratio: {top_strategy.get('r_r_ratio', 0):.2f}")
            logger.info(f"   Lot Size: {top_strategy.get('lot_size', 0):.4f}")
            logger.info(f"   Confidence: {top_strategy.get('confidence', 0)}/100")
            logger.info(f"   Confluence Score: {top_strategy.get('confluence_score', 0)}/100")
            if top_strategy.get("reason"):
                logger.info(f"   Reason: {top_strategy.get('reason')}")
        else:
            logger.warning("⚠️ No top strategy found")
        
        # Early exit triggers
        early_exit = data.get("early_exit_triggers", [])
        if early_exit:
            logger.info("")
            logger.info("🚨 Early Exit Triggers to Watch:")
            for trigger in early_exit:
                logger.info(f"   • {trigger}")
        
        # Warnings
        warnings = data.get("warnings", [])
        if warnings:
            logger.info("")
            logger.info("⚠️ Warnings:")
            for warning in warnings:
                logger.warning(f"   • {warning}")
        
        # Session context
        session = data.get("session_context", "Unknown")
        logger.info("")
        logger.info(f"🕒 Session: {session}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ API TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.info("\n💡 Make sure desktop_agent.py is running or in Python path")
        return False
    except AttributeError as e:
        logger.error(f"❌ Attribute error: {e}")
        logger.info("\n💡 Tool may not be registered. Check desktop_agent.py")
        return False
    except Exception as e:
        logger.error(f"❌ API test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Get symbol from command line or use default
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    
    logger.info("⚠️  Make sure desktop_agent.py is running or accessible")
    logger.info("")
    
    success = asyncio.run(test_range_scalp_api(symbol))
    
    sys.exit(0 if success else 1)

