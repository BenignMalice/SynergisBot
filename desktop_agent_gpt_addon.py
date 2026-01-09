"""
Desktop Agent GPT Hybrid Add-On

Add this to desktop_agent.py to enable GPT hybrid validation.

New tool: moneybot.gpt_analyse_symbol
- Uses full GPT-4o + GPT-5 pipeline
- More expensive (~$0.01-0.11 per analysis) but maximum AI validation
- Optional - only use for high-stakes trades

Integration:
1. Initialize GPT orchestrator in agent_main()
2. Register the new tool
3. Call from phone: "Use GPT analysis for BTCUSD"
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ADD TO agent_main() INITIALIZATION (after order_flow_service):
async def initialize_gpt_hybrid(registry):
    """Initialize GPT hybrid components"""
    registry.gpt_orchestrator = None
    
    try:
        from infra.gpt_reasoner import GPT4oReasoner
        from infra.gpt_validator import GPT5Validator
        from infra.gpt_orchestrator import GPTOrchestrator
        
        logger.info("🤖 Initializing GPT Hybrid System...")
        
        # Initialize components
        gpt4o = GPT4oReasoner()
        gpt5 = GPT5Validator()
        orchestrator = GPTOrchestrator(
            gpt4o,
            gpt5,
            auto_gpt4o=True,
            auto_gpt5=True,
            gpt5_threshold=70
        )
        
        registry.gpt_orchestrator = orchestrator
        
        logger.info("✅ GPT Hybrid System initialized")
        logger.info("   GPT-4o: Fast screening (~$0.01 per analysis)")
        logger.info("   GPT-5: Deep validation (~$0.10 per strong signal)")
        
    except Exception as e:
        logger.warning(f"⚠️ GPT Hybrid initialization failed: {e}")
        logger.warning("   Continuing without GPT validation...")
        registry.gpt_orchestrator = None


# ADD THIS NEW TOOL TO ToolRegistry:
async def tool_gpt_analyse_symbol(registry, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse symbol with full GPT hybrid validation (GPT-4o + GPT-5).
    
    This is the premium analysis mode with maximum AI validation.
    More expensive but provides deepest insight.
    
    Cost: ~$0.01-0.11 per analysis
    Time: 5-35 seconds
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDc")
    
    Returns:
        Complete analysis with GPT reasoning and final decision
    """
    symbol = args.get("symbol", "").upper()
    
    if not symbol:
        return {
            "summary": "⚠️ Symbol required",
            "data": {"error": "Please specify a symbol to analyze"}
        }
    
    if not registry.gpt_orchestrator:
        return {
            "summary": "⚠️ GPT Hybrid not available",
            "data": {
                "error": "GPT validation system not initialized",
                "fallback": "Use regular 'moneybot.analyse_symbol' instead"
            }
        }
    
    try:
        logger.info(f"🤖 GPT Hybrid Analysis requested for {symbol}")
        
        # Step 1: Get MT5 analysis (same as regular tool)
        from infra.mt5_service import MT5Service
        from infra.indicator_bridge import IndicatorBridge
        from decision_engine import decide_trade
        from domain.models import build_features_advanced
        
        mt5_service = registry.mt5_service or MT5Service()
        if not mt5_service.is_connected():
            mt5_service.connect()
        
        # Normalize symbol
        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
        
        # Get multi-timeframe data
        bridge = IndicatorBridge()
        all_timeframe_data = bridge.get_multi([symbol_normalized], ["M5", "M15", "M30", "H1"])
        
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        m30_data = all_timeframe_data.get("M30")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, m30_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # Enrich with Binance
        binance_enrichment = {}
        if registry.binance_service and registry.binance_service.running:
            from infra.binance_enrichment import BinanceEnrichment
            enricher = BinanceEnrichment(
                registry.binance_service, 
                mt5_service, 
                registry.order_flow_service
            )
            m5_data = enricher.enrich_timeframe(symbol_normalized, m5_data, "M5")
            m15_data = enricher.enrich_timeframe(symbol_normalized, m15_data, "M15")
            
            # Extract binance enrichment for GPT
            binance_enrichment = {
                "binance_price": m5_data.get("binance_price"),
                "micro_momentum": m5_data.get("micro_momentum"),
                "feed_health": m5_data.get("feed_health"),
                "price_velocity": m5_data.get("price_velocity"),
                "volume_acceleration": m5_data.get("volume_acceleration")
            }
        
        # Get order flow
        order_flow = None
        if registry.order_flow_service and registry.order_flow_service.running:
            order_flow_signal = registry.order_flow_service.get_order_flow_signal(symbol_normalized)
            if order_flow_signal:
                order_flow = {
                    "signal": order_flow_signal.get("signal"),
                    "confidence": order_flow_signal.get("confidence"),
                    "imbalance": order_flow_signal.get("order_book", {}).get("imbalance"),
                    "whale_count": order_flow_signal.get("whale_activity", {}).get("total_whales", 0),
                    "pressure_side": order_flow_signal.get("pressure", {}).get("dominant_side"),
                    "liquidity_voids": len(order_flow_signal.get("liquidity_voids", [])),
                    "warnings": order_flow_signal.get("warnings", [])
                }
        
        # Get Advanced features
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            m5_data=m5_data,
            m15_data=m15_data,
            m30_data=m30_data,
            h1_data=h1_data
        )
        
        # Get MT5 decision
        rec = decide_trade(
            symbol=symbol_normalized,
            m5_data=m5_data,
            m15_data=m15_data,
            m30_data=m30_data,
            h1_data=h1_data,
            regime_override=None,
            advanced_features=advanced_features
        )
        
        mt5_analysis = {
            "direction": rec.direction,
            "confidence": rec.confidence,
            "strategy": rec.strategy,
            "regime": rec.regime,
            "reasoning": rec.reasoning,
            "entry": rec.entry,
            "stop_loss": rec.stop_loss,
            "take_profit": rec.take_profit,
            "risk_reward": rec.risk_reward
        }
        
        # Step 2: Run GPT Hybrid Pipeline
        logger.info(f"🤖 Running GPT Hybrid Pipeline for {symbol}...")
        
        gpt_result = await registry.gpt_orchestrator.analyze_and_decide(
            symbol_normalized,
            mt5_analysis,
            binance_enrichment,
            order_flow,
            advanced_features
        )
        
        # Format response
        decision = gpt_result["final_decision"]
        confidence = gpt_result["confidence"]
        
        decision_emoji = {
            "EXECUTE": "✅",
            "WAIT": "⏳",
            "REJECT": "❌",
            "SKIP": "⏭️"
        }.get(decision, "❓")
        
        summary = (
            f"{decision_emoji} GPT Hybrid Analysis - {symbol}\n\n"
            f"Final Decision: {decision} ({confidence}%)\n"
            f"Analysis Time: {gpt_result['analysis_time']:.2f}s\n"
            f"Total Cost: ${gpt_result['total_cost']:.4f}\n\n"
        )
        
        # Add GPT-4o result
        if gpt_result.get("gpt4o_result"):
            gpt4o = gpt_result["gpt4o_result"]
            summary += (
                f"🤖 GPT-4o Screening: {gpt4o.get('signal', 'N/A')} "
                f"({gpt4o.get('confidence', 0)}%)\n"
                f"   {gpt4o.get('summary', '')}\n\n"
            )
        
        # Add GPT-5 result
        if gpt_result.get("gpt5_result"):
            gpt5 = gpt_result["gpt5_result"]
            summary += (
                f"🧠 GPT-5 Validation: {gpt5.get('decision', 'N/A')} "
                f"({gpt5.get('confidence', 0)}%)\n"
                f"   Risk: {gpt5.get('risk_assessment', {}).get('level', 'N/A')}\n"
                f"   Position Size: {gpt5.get('position_sizing', 'N/A')}\n\n"
            )
            
            reasoning = gpt5.get("reasoning", "")
            if reasoning:
                # Truncate for summary (show first 300 chars)
                summary += f"Reasoning:\n{reasoning[:300]}...\n\n"
        
        # Add MT5 baseline
        summary += (
            f"📊 MT5 Baseline:\n"
            f"   Direction: {rec.direction}\n"
            f"   Confidence: {rec.confidence}%\n"
            f"   Strategy: {rec.strategy}\n"
            f"   Entry: {rec.entry}, SL: {rec.stop_loss}, TP: {rec.take_profit}\n"
        )
        
        # Show orchestrator stats
        stats = registry.gpt_orchestrator.get_statistics()
        summary += (
            f"\n📊 Session Stats:\n"
            f"   Total Analyzed: {stats['total_analyzed']}\n"
            f"   Execution Rate: {stats['execution_rate']:.1f}%\n"
            f"   Session Cost: ${stats['total_cost']:.2f}"
        )
        
        return {
            "summary": summary,
            "data": gpt_result
        }
        
    except Exception as e:
        logger.error(f"❌ GPT analysis failed for {symbol}: {e}", exc_info=True)
        return {
            "summary": f"❌ GPT analysis failed: {str(e)}",
            "data": {"error": str(e)}
        }


# REGISTER THE TOOL (add to tool registration section):
# @registry.register("moneybot.gpt_analyse_symbol")
# async def tool_gpt_analyse(args: Dict[str, Any]) -> Dict[str, Any]:
#     return await tool_gpt_analyse_symbol(registry, args)

