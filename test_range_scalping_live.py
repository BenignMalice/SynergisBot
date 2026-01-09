"""
Live Integration Test for Range Scalping System
Tests with actual MT5 connection and real market data.

Usage:
    python test_range_scalping_live.py BTCUSD
    python test_range_scalping_live.py XAUUSD
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


async def test_live_analysis(symbol: str = "BTCUSD"):
    """Test range scalping analysis with live MT5 connection"""
    
    logger.info("=" * 80)
    logger.info(f"🧪 LIVE TEST: Range Scalping Analysis for {symbol}")
    logger.info("=" * 80)
    
    try:
        # Import required modules
        from infra.range_scalping_analysis import analyse_range_scalp_opportunity
        from infra.indicator_bridge import IndicatorBridge
        from infra.mt5_service import MT5Service
        from infra.feature_builder_advanced import build_features_advanced
        
        # Initialize MT5
        logger.info("📡 Connecting to MT5...")
        mt5_service = MT5Service()
        if not mt5_service.connect():
            logger.error("❌ Failed to connect to MT5")
            return False
        
        logger.info("✅ MT5 connected")
        
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
                
                multi_tf_streamer = MultiTimeframeStreamer(streamer_config, mt5_service=mt5_service)
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
        
        # Normalize symbol
        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
        logger.info(f"📊 Symbol: {symbol_normalized}")
        
        # Initialize indicator bridge
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data
        logger.info("📈 Fetching market data...")
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, h1_data]):
            logger.error("❌ Failed to fetch market data")
            return False
        
        logger.info("✅ Market data fetched")
        
        # Get current price
        try:
            quote = mt5_service.get_quote(symbol_normalized)
            current_price = (quote.bid + quote.ask) / 2 if quote else 0
        except Exception as e:
            logger.warning(f"⚠️ Could not get current price: {e}, using bid from tick")
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol_normalized)
            current_price = (tick.bid + tick.ask) / 2 if tick else 0
        
        logger.info(f"💰 Current price: {current_price}")
        
        # Prepare indicators
        indicators = {
            "rsi": m5_data.get("indicators", {}).get("rsi", 50),
            "bb_upper": m5_data.get("indicators", {}).get("bb_upper"),
            "bb_lower": m5_data.get("indicators", {}).get("bb_lower"),
            "bb_middle": m5_data.get("indicators", {}).get("bb_middle"),
            "stoch_k": m5_data.get("indicators", {}).get("stoch_k", 50),
            "stoch_d": m5_data.get("indicators", {}).get("stoch_d", 50),
            "adx_h1": h1_data.get("indicators", {}).get("adx", 20),
            "atr_5m": m5_data.get("indicators", {}).get("atr14", 0)
        }
        
        logger.info(f"📊 Indicators: RSI={indicators['rsi']:.1f}, ADX(H1)={indicators['adx_h1']:.1f}, ATR={indicators['atr_5m']:.2f}")
        
        # Get PDH/PDL and VWAP from advanced features
        logger.info("🔍 Building advanced features...")
        pdh = None
        pdl = None
        vwap = None
        
        try:
            advanced_features = build_features_advanced(
                symbol=symbol_normalized,
                mt5svc=mt5_service,
                bridge=bridge,
                timeframes=["M5", "M15", "H1"]
            )
            
            if advanced_features and "features" in advanced_features:
                m15_features = advanced_features["features"].get("M15", {})
                liquidity = m15_features.get("liquidity", {})
                pdh = liquidity.get("pdh")
                pdl = liquidity.get("pdl")
                
                vwap_data = m15_features.get("vwap")
                if vwap_data:
                    vwap = vwap_data.get("value")
                
                pdh_str = f"{pdh:.2f}" if pdh is not None else "N/A"
                pdl_str = f"{pdl:.2f}" if pdl is not None else "N/A"
                vwap_str = f"{vwap:.2f}" if vwap is not None else "N/A"
                logger.info(f"📊 Liquidity: PDH={pdh_str}, PDL={pdl_str}, VWAP={vwap_str}")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch PDH/PDL/VWAP: {e}")
        
        # Get volume data
        volume_current = 0
        volume_1h_avg = 0
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc") and len(df_m5) > 0:
                    volume_current = float(df_m5.iloc[-1].get("tick_volume", 0))
                    volume_1h_avg = float(df_m5.iloc[-12:]["tick_volume"].mean()) if len(df_m5) >= 12 else volume_current
            except Exception as e:
                logger.debug(f"Volume calculation error: {e}")
        
        # Get recent candles
        recent_candles = []
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc"):
                    for i in range(max(0, len(df_m5) - 5), len(df_m5)):
                        recent_candles.append({
                            "open": float(df_m5.iloc[i]["open"]),
                            "high": float(df_m5.iloc[i]["high"]),
                            "low": float(df_m5.iloc[i]["low"]),
                            "close": float(df_m5.iloc[i]["close"]),
                            "volume": int(df_m5.iloc[i].get("tick_volume", 0))
                        })
            except Exception as e:
                logger.debug(f"Candle extraction error: {e}")
        
        # Calculate bb_width safely
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper is not None and bb_lower is not None and current_price > 0:
            bb_width = (bb_upper - bb_lower) / current_price
        else:
            bb_width = 0
        
        # Convert M15 data to DataFrame if it's in list format (from IndicatorBridge)
        m15_df = None
        if m15_data:
            m15_df = m15_data.get("df")
            # If df is None, try to convert from list format
            if m15_df is None and isinstance(m15_data, dict):
                # Check if we have list format data
                if "opens" in m15_data or "highs" in m15_data:
                    import pandas as pd
                    try:
                        times = m15_data.get("times", [])
                        opens = m15_data.get("opens", [])
                        highs = m15_data.get("highs", [])
                        lows = m15_data.get("lows", [])
                        closes = m15_data.get("closes", [])
                        volumes = m15_data.get("tick_volumes", [])
                        
                        if len(opens) > 0:
                            m15_df = pd.DataFrame({
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "tick_volume": volumes
                            })
                            logger.info(f"✅ Converted M15 data from list format to DataFrame ({len(m15_df)} rows)")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not convert M15 list data to DataFrame: {e}")
        
        # Prepare market_data dict
        market_data = {
            "current_price": current_price,
            "vwap": vwap,
            "atr": indicators.get("atr_5m", 0),
            "atr_5m": indicators.get("atr_5m", 0),
            "bb_width": bb_width,
            "pdh": pdh,
            "pdl": pdl,
            "volume_current": volume_current,
            "volume_1h_avg": volume_1h_avg,
            "recent_candles": recent_candles,
            "order_flow": {
                "signal": "NEUTRAL",
                "confidence": 0
            },
            "m15_df": m15_df,  # Required for dynamic range detection
            "mt5_service": mt5_service  # Pass MT5Service for risk filters
        }
        
        # Run analysis
        logger.info("🔍 Running range scalping analysis...")
        logger.info("-" * 80)
        
        result = await analyse_range_scalp_opportunity(
            symbol=symbol_normalized,
            strategy_filter=None,  # Test all strategies
            check_risk_filters=True,
            market_data=market_data,
            indicators=indicators
        )
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ANALYSIS RESULTS")
        logger.info("=" * 80)
        
        if result.get("error"):
            logger.error(f"❌ Error: {result['error']}")
            if result.get("warnings"):
                for warning in result["warnings"]:
                    logger.warning(f"⚠️ {warning}")
            return False
        
        # Range detection
        if result.get("range_detected"):
            logger.info("✅ Range Detected")
            range_structure = result.get("range_structure", {})
            logger.info(f"   Type: {range_structure.get('range_type', 'unknown')}")
            logger.info(f"   High: {range_structure.get('range_high', 0):.2f}")
            logger.info(f"   Low: {range_structure.get('range_low', 0):.2f}")
            logger.info(f"   Mid: {range_structure.get('range_mid', 0):.2f}")
            logger.info(f"   Width (ATR): {range_structure.get('range_width_atr', 0):.2f}")
        else:
            logger.warning("⚠️ No range detected")
            return False
        
        # Risk checks
        risk_checks = result.get("risk_checks", {})
        if risk_checks.get("risk_filters_skipped"):
            logger.info("⚠️ Risk filters skipped")
        else:
            logger.info("🔍 Risk Checks:")
            logger.info(f"   3-Confluence Score: {risk_checks.get('confluence_score', 0)}/100")
            logger.info(f"   Confluence Passed: {'✅' if risk_checks.get('3_confluence_passed') else '❌'}")
            logger.info(f"   False Range: {'❌ Detected' if risk_checks.get('false_range_detected') else '✅ None'}")
            logger.info(f"   Range Valid: {'✅' if risk_checks.get('range_valid') else '❌'}")
            logger.info(f"   Session Allows: {'✅' if risk_checks.get('session_allows_trading') else '❌'}")
            logger.info(f"   Trade Activity: {'✅' if risk_checks.get('trade_activity_sufficient') else '❌'}")
            
            if not risk_checks.get("risk_passed", False):
                logger.warning("⚠️ Risk filters failed - trade not recommended")
        
        # Top strategy
        top_strategy = result.get("top_strategy")
        if top_strategy:
            logger.info("")
            logger.info("🎯 Top Strategy:")
            logger.info(f"   Name: {top_strategy.get('name', 'unknown')}")
            logger.info(f"   Direction: {top_strategy.get('direction', 'N/A')}")
            logger.info(f"   Entry: {top_strategy.get('entry_price', 0):.2f}")
            logger.info(f"   Stop Loss: {top_strategy.get('stop_loss', 0):.2f}")
            logger.info(f"   Take Profit: {top_strategy.get('take_profit', 0):.2f}")
            logger.info(f"   R:R Ratio: {top_strategy.get('r_r_ratio', 0):.2f}")
            logger.info(f"   Confidence: {top_strategy.get('confidence', 0)}/100")
            logger.info(f"   Confluence Score: {top_strategy.get('confluence_score', 0)}/100")
            logger.info(f"   Reason: {top_strategy.get('reason', 'N/A')}")
        else:
            logger.warning("⚠️ No strategy scored above threshold")
        
        # Early exit triggers
        early_exit_triggers = result.get("early_exit_triggers", [])
        if early_exit_triggers:
            logger.info("")
            logger.info("🚨 Early Exit Triggers to Watch:")
            for trigger in early_exit_triggers:
                logger.info(f"   • {trigger}")
        
        # Warnings
        warnings = result.get("warnings", [])
        if warnings:
            logger.info("")
            logger.info("⚠️ Warnings:")
            for warning in warnings:
                logger.warning(f"   • {warning}")
        
        # Session context
        session_context = result.get("session_context", "Unknown")
        logger.info("")
        logger.info(f"🕒 Session: {session_context}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ LIVE TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Live test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Get symbol from command line or use default
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    
    success = asyncio.run(test_live_analysis(symbol))
    
    sys.exit(0 if success else 1)

