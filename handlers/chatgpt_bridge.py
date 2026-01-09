"""
ChatGPT Bridge Handler
======================

Allows users to interact with ChatGPT directly from Telegram.
ChatGPT can analyze markets, execute trades, and provide insights using its API access.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)
import httpx
import json
from datetime import datetime
from infra.recommendation_tracker import RecommendationTracker

logger = logging.getLogger(__name__)

# Initialize recommendation tracker
recommendation_tracker = RecommendationTracker()

# Conversation states
CHATTING = 1

# Store conversation history per user
user_conversations = {}

# Import logging infrastructure
try:
    from infra.chatgpt_logger import ChatGPTLogger
    from infra.analytics_logger import AnalyticsLogger
    chatgpt_logger = ChatGPTLogger()
    analytics_logger = AnalyticsLogger()
    logger.info("✅ ChatGPT logging infrastructure loaded")
except Exception as e:
    logger.warning(f"⚠️ Could not load logging infrastructure: {e}")
    chatgpt_logger = None
    analytics_logger = None


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    For safe text display, we'll escape ALL special characters.
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


# Helper functions to execute tool calls
async def get_historical_performance(symbol: str = None, trade_type: str = None) -> dict:
    """Fetch historical performance stats for recommendations"""
    try:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if trade_type:
            params["trade_type"] = trade_type
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/api/v1/recommendation_stats",
                params=params
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"stats": {}, "best_setups": []}
            
    except Exception as e:
        logger.error(f"Error fetching historical performance: {e}", exc_info=True)
        return {"stats": {}, "best_setups": []}


async def execute_bracket_trade(
    symbol: str,
    buy_entry: float,
    buy_sl: float,
    buy_tp: float,
    sell_entry: float,
    sell_sl: float,
    sell_tp: float,
    reasoning: str = "Bracket trade"
) -> dict:
    """Execute OCO bracket trade"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/execute_bracket",
                params={
                    "symbol": symbol,
                    "buy_entry": buy_entry,
                    "buy_sl": buy_sl,
                    "buy_tp": buy_tp,
                    "sell_entry": sell_entry,
                    "sell_sl": sell_sl,
                    "sell_tp": sell_tp,
                    "reasoning": reasoning
                }
            )
        if response.status_code == 200:
            result = response.json()
            
            # Add bracket trades to DTMS monitoring if tickets are available
            if result.get('ok') and result.get('tickets'):
                try:
                    from dtms_integration import add_trade_to_dtms
                    
                    tickets = result.get('tickets', {})
                    
                    # Add buy trade to DTMS
                    if tickets.get('buy_ticket'):
                        dtms_added = add_trade_to_dtms(
                            ticket=tickets['buy_ticket'],
                            symbol=symbol,
                            direction='BUY',
                            entry_price=buy_entry,
                            volume=0.01,  # Default volume
                            stop_loss=buy_sl,
                            take_profit=buy_tp
                        )
                        if dtms_added:
                            logger.info(f"✅ Bracket BUY trade {tickets['buy_ticket']} added to DTMS monitoring")
                    
                    # Add sell trade to DTMS
                    if tickets.get('sell_ticket'):
                        dtms_added = add_trade_to_dtms(
                            ticket=tickets['sell_ticket'],
                            symbol=symbol,
                            direction='SELL',
                            entry_price=sell_entry,
                            volume=0.01,  # Default volume
                            stop_loss=sell_sl,
                            take_profit=sell_tp
                        )
                        if dtms_added:
                            logger.info(f"✅ Bracket SELL trade {tickets['sell_ticket']} added to DTMS monitoring")
                            
                except Exception as e:
                    logger.error(f"❌ Failed to add bracket trades to DTMS: {e}")
            
            return result
        else:
            return {"ok": False, "error": response.text}
    except Exception as e:
        logger.error(f"Error executing bracket trade: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


async def get_multi_timeframe_analysis(symbol: str) -> dict:
    """Get H4→H1→M30→M15→M5 alignment analysis"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://localhost:8000/api/v1/multi_timeframe/{symbol}"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting multi-timeframe analysis: {e}", exc_info=True)
        return {"error": str(e)}


async def get_confluence_score(symbol: str) -> dict:
    """Get confluence score (0-100) with grade A-F"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://localhost:8000/api/v1/confluence/{symbol}"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting confluence score: {e}", exc_info=True)
        return {"error": str(e)}


async def get_session_analysis() -> dict:
    """Get current trading session with recommendations"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/api/v1/session/current"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting session analysis: {e}", exc_info=True)
        return {"error": str(e)}


async def get_recommendation_stats(
    symbol: str = None,
    trade_type: str = None,
    days_back: int = 30
) -> dict:
    """Get historical performance statistics"""
    try:
        params = {"days_back": days_back}
        if symbol:
            params["symbol"] = symbol
        if trade_type:
            params["trade_type"] = trade_type
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/api/v1/recommendation_stats",
                params=params
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting recommendation stats: {e}", exc_info=True)
        return {"error": str(e)}


async def get_news_status(category: str = "both", hours_ahead: int = 12) -> dict:
    """Check if in news blackout window"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/news/status",
                params={"category": category, "hours_ahead": hours_ahead}
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting news status: {e}", exc_info=True)
        return {"error": str(e)}


async def get_news_events(
    category: str = None,
    impact: str = None,
    hours_ahead: int = 24
) -> dict:
    """Get upcoming economic news events"""
    try:
        params = {"hours_ahead": hours_ahead}
        if category:
            params["category"] = category
        if impact:
            params["impact"] = impact
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/news/events",
                params=params
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting news events: {e}", exc_info=True)
        return {"error": str(e)}


async def get_intelligent_exits(symbol: str) -> dict:
    """Get AI-powered exit strategy recommendations"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://localhost:8000/ai/exits/{symbol}"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting intelligent exits: {e}", exc_info=True)
        return {"error": str(e)}


async def get_market_sentiment() -> dict:
    """Get Fear & Greed Index and market sentiment"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/sentiment/market"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.text}
    except Exception as e:
        logger.error(f"Error getting market sentiment: {e}", exc_info=True)
        return {"error": str(e)}


async def add_alert(args: dict) -> dict:
    """Add a custom alert via the desktop agent"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8000/dispatch",
                json={
                    "tool": "moneybot.add_alert",
                    "arguments": args,
                    "timeout": 30
                },
                headers={"Authorization": "Bearer phone_control_bearer_token_2025_v1_secure"}
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "alert_id": result.get("data", {}).get("alert_id"),
                "message": result.get("summary", "Alert created successfully")
            }
        else:
            return {"error": f"Failed to create alert: {response.text}"}
    except Exception as e:
        logger.error(f"Error creating alert: {e}", exc_info=True)
        return {"error": str(e)}


async def get_unified_news_analysis(args: dict) -> dict:
    """Get comprehensive news analysis combining economic calendar, breaking news, and market sentiment"""
    try:
        category = args.get("category", "macro")
        hours_ahead = args.get("hours_ahead", 24)
        hours_back = args.get("hours_back", 24)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8000/news/unified",
                params={
                    "category": category,
                    "hours_ahead": hours_ahead,
                    "hours_back": hours_back
                }
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"Failed to get news analysis: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error getting unified news analysis: {e}", exc_info=True)
        return {
            "error": str(e)
        }


async def get_breaking_news_summary(args: dict) -> dict:
    """Get summary of recent breaking news"""
    try:
        hours_back = args.get("hours_back", 24)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:8000/news/breaking",
                params={"hours_back": hours_back}
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"Failed to get breaking news: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error getting breaking news summary: {e}", exc_info=True)
        return {
            "error": str(e)
        }


async def enable_intelligent_exits(
    ticket: int,
    symbol: str,
    entry_price: float,
    direction: str,
    initial_sl: float,
    initial_tp: float,
    breakeven_profit_pct: float = 30.0,
    partial_profit_pct: float = 60.0,
    partial_close_pct: float = 50.0,
    vix_threshold: float = 18.0,
    use_hybrid_stops: bool = True
) -> dict:
    """Enable intelligent exit management for a position"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/enable_intelligent_exits",
                params={
                    "ticket": ticket,
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "direction": direction,
                    "initial_sl": initial_sl,
                    "initial_tp": initial_tp,
                    "breakeven_profit_pct": breakeven_profit_pct,
                    "partial_profit_pct": partial_profit_pct,
                    "partial_close_pct": partial_close_pct,
                    "vix_threshold": vix_threshold,
                    "use_hybrid_stops": use_hybrid_stops
                }
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"ok": False, "error": response.text}
    except Exception as e:
        logger.error(f"Error enabling intelligent exits: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


async def get_intelligent_exits_status() -> dict:
    """Get status of all active intelligent exit rules"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://localhost:8000/mt5/intelligent_exits/status"
            )
        if response.status_code == 200:
            return response.json()
        else:
            return {"ok": False, "error": response.text, "rules": []}
    except Exception as e:
        logger.error(f"Error getting intelligent exits status: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "rules": []}


def _analyze_market_structure(
    current_price: float,
    h4_data: dict,
    h1_data: dict,
    m15_data: dict,
    recommendation: dict
) -> dict:
    """
    Analyze market structure to provide context for ChatGPT.
    This helps ChatGPT understand WHY a trade might be good or bad.
    """
    structure = {
        "summary": "",
        "price_position": "",
        "trend_strength": "",
        "momentum_state": "",
        "risk_warning": "",
        "optimal_entry_zone": "",
        "avoid_entry_reason": ""
    }
    
    # Analyze price position relative to EMAs
    h4_rsi = h4_data.get("rsi", 50.0)
    h4_adx = h4_data.get("adx", 0.0)
    h4_bias = h4_data.get("bias", "UNKNOWN")
    m15_rsi = m15_data.get("rsi", 50.0)
    
    # Determine if price is at extreme
    if h4_rsi > 70:
        structure["price_position"] = "⚠️ OVERBOUGHT (RSI 70+) - High risk for BUY entries"
        structure["avoid_entry_reason"] = "Price at resistance, likely to reverse. Wait for pullback."
        structure["risk_warning"] = "HIGH RISK: Buying at tops often leads to immediate losses"
    elif h4_rsi < 30:
        structure["price_position"] = "⚠️ OVERSOLD (RSI 30-) - High risk for SELL entries"
        structure["avoid_entry_reason"] = "Price at support, likely to bounce. Wait for rally."
        structure["risk_warning"] = "HIGH RISK: Selling at bottoms often leads to immediate losses"
    elif 45 < h4_rsi < 55:
        structure["price_position"] = "✅ NEUTRAL (RSI 45-55) - Balanced entry zone"
        structure["optimal_entry_zone"] = "Good zone for entries with confirmation"
    else:
        structure["price_position"] = f"Moderate (RSI {h4_rsi:.0f})"
    
    # Analyze trend strength
    if h4_adx > 40:
        structure["trend_strength"] = f"🔥 STRONG TREND (ADX {h4_adx:.0f}) - Momentum trades favored"
    elif h4_adx > 25:
        structure["trend_strength"] = f"✅ TRENDING (ADX {h4_adx:.0f}) - Trend following viable"
    elif h4_adx < 20:
        structure["trend_strength"] = f"⚠️ WEAK/CHOPPY (ADX {h4_adx:.0f}) - Range-bound, avoid breakouts"
        structure["avoid_entry_reason"] = "Weak trend, high risk of false breakouts"
    else:
        structure["trend_strength"] = f"Moderate trend (ADX {h4_adx:.0f})"
    
    # Analyze momentum alignment
    if h4_bias == "BULLISH" and m15_rsi > 50:
        structure["momentum_state"] = "✅ ALIGNED BULLISH - H4 and M15 both bullish"
    elif h4_bias == "BEARISH" and m15_rsi < 50:
        structure["momentum_state"] = "✅ ALIGNED BEARISH - H4 and M15 both bearish"
    elif h4_bias == "BULLISH" and m15_rsi < 50:
        structure["momentum_state"] = "⚠️ CONFLICTING - H4 bullish but M15 bearish (wait for alignment)"
        structure["avoid_entry_reason"] = "Multi-timeframe conflict, wait for M15 to align with H4"
    elif h4_bias == "BEARISH" and m15_rsi > 50:
        structure["momentum_state"] = "⚠️ CONFLICTING - H4 bearish but M15 bullish (wait for alignment)"
        structure["avoid_entry_reason"] = "Multi-timeframe conflict, wait for M15 to align with H4"
    else:
        structure["momentum_state"] = "NEUTRAL - No clear momentum direction"
    
    # Generate summary
    action = recommendation.get("action", "WAIT")
    confidence = recommendation.get("confidence", 0)
    
    if action == "WAIT":
        structure["summary"] = f"⏳ WAIT recommended ({confidence}% confidence). Market conditions not optimal."
    elif structure["avoid_entry_reason"]:
        structure["summary"] = f"🚫 CAUTION: {structure['avoid_entry_reason']}"
    else:
        structure["summary"] = f"✅ {action} conditions acceptable ({confidence}% confidence)"
    
    return structure


def _build_context_from_market_data(market_data: dict, symbol: str, data_timestamp: str) -> str:
    """Build context string from market data"""
    return (
        f"\n\n[CURRENT MARKET DATA FOR {symbol}]\n"
        f"📅 Data as of: {data_timestamp}\n"
        f"Current Price: ${market_data.get('current_price', 0):.2f}\n"
        f"Bid: ${market_data.get('bid', 0):.2f}\n"
        f"Ask: ${market_data.get('ask', 0):.2f}\n"
        f"RSI: {market_data.get('rsi', 50):.1f}\n"
        f"ADX: {market_data.get('adx', 0):.1f}\n"
        f"EMA20: ${market_data.get('ema20', 0):.2f}\n"
        f"EMA50: ${market_data.get('ema50', 0):.2f}\n"
        f"EMA200: ${market_data.get('ema200', 0):.2f}\n"
        f"ATR14: {market_data.get('atr14', 0):.2f}\n"
        f"Market Regime: {market_data.get('market_regime', 'UNKNOWN')}\n"
        f"Technical Recommendation: {market_data.get('recommendation', 'HOLD')}\n"
        f"[END MARKET DATA]\n\n"
        f"CRITICAL: You MUST include the timestamp '📅 Data as of: {data_timestamp}' in your response header.\n"
        f"Use these ACTUAL numbers in your analysis. Do not make up numbers."
    )


async def execute_get_market_data(symbol: str) -> dict:
    """Fetch market data with proper multi-timeframe analysis"""
    try:
        # Don't normalize here - API handles it
        symbol = symbol.upper()
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get price
            price_response = await client.get(f"http://localhost:8000/api/v1/price/{symbol}")
            price_data = price_response.json() if price_response.status_code == 200 else {}
            
            # Get multi-timeframe analysis (proper top-down analysis)
            mtf_response = await client.get(f"http://localhost:8000/api/v1/multi_timeframe/{symbol}")
            mtf_data = mtf_response.json() if mtf_response.status_code == 200 else {}
            
            # Get confluence score
            confluence_response = await client.get(f"http://localhost:8000/api/v1/confluence/{symbol}")
            confluence_data = confluence_response.json() if confluence_response.status_code == 200 else {}
            
            # Get current session
            session_response = await client.get(f"http://localhost:8000/api/v1/session/current")
            session_data = session_response.json() if session_response.status_code == 200 else {}
        
        # Get historical performance (async call outside the client context)
        historical_perf = await get_historical_performance(symbol=symbol)
        
        # Build comprehensive result with multi-timeframe data
        result = {
            "symbol": symbol,
            "current_price": price_data.get("mid", 0),
            "bid": price_data.get("bid", 0),
            "ask": price_data.get("ask", 0),
            "spread": price_data.get("spread", 0),
            # Add backward-compatible fields for ChatGPT (use H4 as primary)
            "rsi": 50.0,  # Will be updated from H4 data
            "adx": 0.0,   # Will be updated from H4 data
            "ema20": 0.0,  # Will be extracted from H4 ema_stack
            "ema50": 0.0,  # Will be extracted from H4 ema_stack
            "ema200": 0.0,  # Will be extracted from H4 ema_stack
            "atr14": 0.0,  # Will be updated from M30 data
            "market_regime": "UNKNOWN",  # Will be updated from recommendation
        }
        
        # Add multi-timeframe analysis
        if mtf_data and "timeframes" in mtf_data:
            timeframes = mtf_data.get("timeframes", {})
            recommendation = mtf_data.get("recommendation", {})
            
            # Extract new hierarchical fields (Phase 2)
            market_bias = recommendation.get("market_bias", {})
            trade_opportunities = recommendation.get("trade_opportunities", {})
            
            result.update({
                # H4 - Macro Bias
                "h4_bias": timeframes.get("H4", {}).get("bias", "UNKNOWN"),
                "h4_confidence": timeframes.get("H4", {}).get("confidence", 0),
                "h4_reason": timeframes.get("H4", {}).get("reason", ""),
                "h4_rsi": timeframes.get("H4", {}).get("rsi", 50.0),
                "h4_adx": timeframes.get("H4", {}).get("adx", 0.0),
                "h4_ema_stack": timeframes.get("H4", {}).get("ema_stack", ""),
                
                # H1 - Swing Context
                "h1_status": timeframes.get("H1", {}).get("status", "UNKNOWN"),
                "h1_confidence": timeframes.get("H1", {}).get("confidence", 0),
                "h1_reason": timeframes.get("H1", {}).get("reason", ""),
                "h1_rsi": timeframes.get("H1", {}).get("rsi", 50.0),
                "h1_macd_cross": timeframes.get("H1", {}).get("macd_cross", "neutral"),
                "h1_price_vs_ema20": timeframes.get("H1", {}).get("price_vs_ema20", "neutral"),
                
                # M30 - Setup Frame
                "m30_setup": timeframes.get("M30", {}).get("setup", "NONE"),
                "m30_confidence": timeframes.get("M30", {}).get("confidence", 0),
                "m30_reason": timeframes.get("M30", {}).get("reason", ""),
                "m30_rsi": timeframes.get("M30", {}).get("rsi", 50.0),
                "m30_atr": timeframes.get("M30", {}).get("atr", 0.0),
                "m30_ema_alignment": timeframes.get("M30", {}).get("ema_alignment", "neutral"),
                
                # M15 - Trigger Frame
                "m15_trigger": timeframes.get("M15", {}).get("trigger", "NONE"),
                "m15_confidence": timeframes.get("M15", {}).get("confidence", 0),
                "m15_reason": timeframes.get("M15", {}).get("reason", ""),
                "m15_rsi": timeframes.get("M15", {}).get("rsi", 50.0),
                "m15_macd_status": timeframes.get("M15", {}).get("macd_status", "neutral"),
                "m15_price_vs_ema20": timeframes.get("M15", {}).get("price_vs_ema20", "neutral"),
                
                # M5 - Execution Frame
                "m5_execution": timeframes.get("M5", {}).get("execution", "NONE"),
                "m5_confidence": timeframes.get("M5", {}).get("confidence", 0),
                "m5_reason": timeframes.get("M5", {}).get("reason", ""),
                "m5_entry": timeframes.get("M5", {}).get("entry_price"),
                "m5_stop": timeframes.get("M5", {}).get("stop_loss"),
                "m5_rsi": timeframes.get("M5", {}).get("rsi", 50.0),
                "m5_atr": timeframes.get("M5", {}).get("atr", 0.0),
                
                # Overall (backward compatible)
                "alignment_score": mtf_data.get("alignment_score", 0),
                "recommendation": recommendation.get("action", "WAIT"),
                "recommendation_confidence": recommendation.get("confidence", 0),
                "recommendation_reason": recommendation.get("reason", ""),
                "mtf_summary": recommendation.get("summary", ""),
                
                # NEW: Hierarchical trend analysis fields (Phase 2)
                "primary_trend": market_bias.get("trend", "UNKNOWN"),
                "trend_strength": market_bias.get("strength", "UNKNOWN"),
                "trend_stability": market_bias.get("stability", "UNKNOWN"),
                "trade_opportunity_type": trade_opportunities.get("type", "NONE"),
                "risk_level": trade_opportunities.get("risk_level", "UNKNOWN"),
                "risk_adjustments": trade_opportunities.get("risk_adjustments", {}),
                "counter_trend_warning": True if "COUNTER_TREND" in trade_opportunities.get("type", "") else False,
                "volatility_regime": recommendation.get("volatility_regime", "medium"),
                "volatility_weights": recommendation.get("volatility_weights", {})
            })
            
            # Update backward-compatible fields from H4 data
            result["rsi"] = timeframes.get("H4", {}).get("rsi", 50.0)
            result["adx"] = timeframes.get("H4", {}).get("adx", 0.0)
            result["atr14"] = timeframes.get("M30", {}).get("atr", 0.0)
            result["market_regime"] = timeframes.get("H4", {}).get("bias", "UNKNOWN")
            
            # Extract EMA values from H4 ema_stack string
            ema_stack = timeframes.get("H4", {}).get("ema_stack", "")
            if ema_stack:
                import re
                ema20_match = re.search(r'EMA20=([\d.]+)', ema_stack)
                ema50_match = re.search(r'EMA50=([\d.]+)', ema_stack)
                ema200_match = re.search(r'EMA200=([\d.]+)', ema_stack)
                
                if ema20_match:
                    result["ema20"] = float(ema20_match.group(1))
                if ema50_match:
                    result["ema50"] = float(ema50_match.group(1))
                if ema200_match:
                    result["ema200"] = float(ema200_match.group(1))
            
            # Add market structure context for better decision-making
            result["market_structure"] = _analyze_market_structure(
                current_price=result["current_price"],
                h4_data=timeframes.get("H4", {}),
                h1_data=timeframes.get("H1", {}),
                m15_data=timeframes.get("M15", {}),
                recommendation=recommendation
            )
        
        # Add confluence data
        if confluence_data:
            result.update({
                "confluence_score": confluence_data.get("confluence_score", 0),
                "confluence_grade": confluence_data.get("grade", "F"),
                "confluence_recommendation": confluence_data.get("recommendation", ""),
                "confluence_factors": confluence_data.get("factors", {})
            })
        
        # Add session data
        if session_data:
            result.update({
                "session_name": session_data.get("name", "Unknown"),
                "session_volatility": session_data.get("volatility", "unknown"),
                "session_strategy": session_data.get("strategy", "unknown"),
                "session_best_pairs": session_data.get("best_pairs", []),
                "session_stop_multiplier": session_data.get("risk_adjustments", {}).get("stop_loss_multiplier", 1.0),
                "session_recommendations": session_data.get("recommendations", [])
            })
        
        # Add historical performance data
        if historical_perf and "stats" in historical_perf:
            stats = historical_perf.get("stats", {})
            result.update({
                "historical_win_rate": stats.get("win_rate", 0),
                "historical_avg_rr": stats.get("avg_rr_achieved", 0),
                "historical_total_trades": stats.get("total_recommendations", 0),
                "historical_executed_trades": stats.get("executed_count", 0),
                "best_setups": historical_perf.get("best_setups", [])
            })
        
        # Add Advanced Technical Features
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                advanced_response = await client.get(f"http://localhost:8000/api/v1/features/advanced/{symbol}")
                if advanced_response.status_code == 200:
                    advanced_data = advanced_response.json()
                    if advanced_data and "features" in advanced_data:
                        result["advanced"] = advanced_data.get("features", {})
                        logger.info(f"✅ Advanced features added for {symbol}")
        except Exception as advanced_error:
            logger.debug(f"Advanced features not available: {advanced_error}")
            # Advanced features are optional, continue without them
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching market data: {e}", exc_info=True)
        return {"error": str(e)}


async def execute_get_full_analysis(symbol: str) -> dict:
    """
    Get full unified analysis with all new features:
    - Stop cluster detection
    - Fed expectations tracking
    - Volatility forecasting
    - Order flow signals
    - Enhanced macro bias
    
    This uses the same analysis as Custom GPT (/api/v1/analyse/{symbol}/full)
    """
    try:
        symbol = symbol.upper()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"http://localhost:8000/api/v1/analyse/{symbol}/full")
            
            if response.status_code != 200:
                logger.error(f"Full analysis endpoint returned {response.status_code}: {response.text}")
                # Fallback to regular market data
                return await execute_get_market_data(symbol)
            
            data = response.json()
            
            # Extract summary and structured data
            summary = data.get("summary", "")
            
            # Build result compatible with existing context format
            result = {
                "symbol": symbol,
                "full_analysis_summary": summary,
                "source": "full_unified_analysis",
                # Extract key metrics from summary if available
                "has_stop_clusters": "stop cluster" in summary.lower() or "wick" in summary.lower(),
                "has_fed_expectations": "fed expectations" in summary.lower() or "2y-10y" in summary.lower() or "spread" in summary.lower(),
                "has_volatility_forecast": "volatility" in summary.lower() or "atr momentum" in summary.lower(),
                "has_order_flow": "order flow" in summary.lower() or "liquidity" in summary.lower(),
            }
            
            # If data contains structured fields, add them
            if "data" in data:
                result.update(data["data"])
            
            logger.info(f"✅ Full unified analysis retrieved for {symbol}")
            return result
            
    except Exception as e:
        logger.error(f"Error fetching full analysis: {e}", exc_info=True)
        # Fallback to regular market data
        return await execute_get_market_data(symbol)


async def execute_get_economic_indicator(indicator: str = "GDP") -> dict:
    """
    Fetch US economic indicator data from Alpha Vantage
    
    Args:
        indicator: GDP, INFLATION, UNEMPLOYMENT, RETAIL_SALES, etc.
    """
    try:
        from infra.alpha_vantage_service import create_alpha_vantage_service
        
        av_service = create_alpha_vantage_service()
        if not av_service:
            return {
                "error": "Alpha Vantage API key not configured",
                "help": "Add ALPHA_VANTAGE_API_KEY to .env file"
            }
        
        result = av_service.get_economic_indicator(indicator)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching economic indicator: {e}", exc_info=True)
        return {
            "error": str(e),
            "indicator": indicator
        }


async def execute_get_news_sentiment(tickers: list = None) -> dict:
    """
    Fetch news sentiment analysis from Alpha Vantage
    
    Args:
        tickers: List of tickers to analyze (optional)
    """
    try:
        from infra.alpha_vantage_service import create_alpha_vantage_service
        
        av_service = create_alpha_vantage_service()
        if not av_service:
            return {
                "error": "Alpha Vantage API key not configured",
                "help": "Add ALPHA_VANTAGE_API_KEY to .env file"
            }
        
        result = av_service.get_news_sentiment(tickers)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching news sentiment: {e}", exc_info=True)
        return {
            "error": str(e),
            "overall_sentiment": "neutral"
        }


async def execute_get_market_indices() -> dict:
    """
    Fetch DXY (US Dollar Index) and VIX (Volatility Index) from Yahoo Finance
    
    Returns:
        {
            'dxy': {'price': 99.428, 'trend': 'up', 'interpretation': '...'},
            'vix': {'price': 16.90, 'level': 'normal', 'interpretation': '...'},
            'implications': ['USD strengthening...', 'Low volatility...'],
            'summary': 'DXY 99.43 (USD strengthening) | VIX 16.90 (Normal volatility)'
        }
    """
    try:
        from infra.market_indices_service import create_market_indices_service
        
        indices_service = create_market_indices_service()
        result = indices_service.get_market_context()
        return result
        
    except Exception as e:
        logger.error(f"Error fetching market indices: {e}", exc_info=True)
        return {
            "error": str(e),
            "summary": "Market indices unavailable"
        }


async def execute_get_account_balance() -> dict:
    """Fetch MT5 account balance from API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/api/v1/account")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Error fetching account balance: {e}", exc_info=True)
        return {"error": str(e)}


async def modify_position(
    ticket: int,
    stop_loss: float = None,
    take_profit: float = None,
    symbol: str = None
) -> dict:
    """Modify an existing MT5 position's stop loss and/or take profit"""
    try:
        # Prepare modification data
        modify_data = {
            "ticket": ticket
        }
        
        if stop_loss is not None:
            modify_data["stop_loss"] = stop_loss
        
        if take_profit is not None:
            modify_data["take_profit"] = take_profit
        
        if symbol:
            modify_data["symbol"] = symbol
        
        logger.info(f"Modifying position via API: {modify_data}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/modify_position",
                json=modify_data
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Position modified successfully: {result}")
            return result
        else:
            error_data = response.json() if response.status_code != 500 else {}
            error_msg = error_data.get("detail", f"API returned {response.status_code}")
            logger.error(f"Position modification failed: {error_msg}")
            return {"error": error_msg, "ok": False}
            
    except Exception as e:
        logger.error(f"Error modifying position: {e}", exc_info=True)
        return {"error": str(e), "ok": False}


async def get_pending_orders() -> dict:
    """Get all pending orders from MT5"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/api/v1/orders")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned {response.status_code}", "orders": []}
            
    except Exception as e:
        logger.error(f"Error fetching pending orders: {e}", exc_info=True)
        return {"error": str(e), "orders": []}


async def modify_pending_order(
    ticket: int,
    price: float = None,
    stop_loss: float = None,
    take_profit: float = None
) -> dict:
    """Modify an existing pending order's entry price, stop loss, and/or take profit"""
    try:
        # Prepare modification data
        modify_data = {
            "ticket": ticket
        }
        
        if price is not None:
            modify_data["price"] = price
        
        if stop_loss is not None:
            modify_data["stop_loss"] = stop_loss
        
        if take_profit is not None:
            modify_data["take_profit"] = take_profit
        
        logger.info(f"Modifying pending order via API: {modify_data}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/modify_order",
                json=modify_data
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Pending order modified successfully: {result}")
            return result
        else:
            error_data = response.json() if response.status_code != 500 else {}
            error_msg = error_data.get("detail", f"API returned {response.status_code}")
            logger.error(f"Pending order modification failed: {error_msg}")
            return {"error": error_msg, "ok": False}
            
    except Exception as e:
        logger.error(f"Error modifying pending order: {e}", exc_info=True)
        return {"error": str(e), "ok": False}


async def execute_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    order_type: str = "market",
    reasoning: str = "ChatGPT recommendation"
) -> dict:
    """Execute a trade via MT5 API"""
    try:
        # Prepare trade signal
        trade_data = {
            "symbol": symbol,
            "timeframe": "H1",  # Default timeframe
            "direction": direction.lower(),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "order_type": order_type.lower(),
            "confidence": 75,
            "reasoning": reasoning
        }
        
        logger.info(f"Executing trade via API: {trade_data}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/execute",
                json=trade_data
            )
        
        if response.status_code == 200:
            result = response.json()
            ticket = result.get('ticket')
            
            # Add trade to DTMS monitoring if ticket is available
            if ticket:
                try:
                    from dtms_integration import add_trade_to_dtms
                    
                    # Add trade to DTMS monitoring
                    dtms_added = add_trade_to_dtms(
                        ticket=ticket,
                        symbol=symbol,
                        direction=direction.upper(),
                        entry_price=entry_price,
                        volume=result.get('volume', 0.01),  # Default to 0.01 if not provided
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    
                    if dtms_added:
                        logger.info(f"✅ Trade {ticket} added to DTMS monitoring")
                    else:
                        logger.warning(f"⚠️ Failed to add trade {ticket} to DTMS monitoring")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to add trade {ticket} to DTMS: {e}")
            
            return {
                "success": True,
                "message": f"Trade executed successfully! Ticket: {ticket}",
                "details": result
            }
        else:
            error_text = response.text
            logger.error(f"Trade execution failed: {response.status_code} - {error_text}")
            return {
                "success": False,
                "error": f"Execution failed: {response.status_code}",
                "details": error_text
            }
            
    except Exception as e:
        logger.error(f"Error executing trade: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def chatgpt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a ChatGPT conversation"""
    logger.info(f"🎯 ChatGPT start called by user {update.effective_user.id}")
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Initialize conversation
    user_conversations[user_id] = {
        "messages": [],
        "started_at": datetime.now().isoformat(),
        "chat_id": chat_id,
        "conversation_id": None  # Will be set after DB logging
    }
    
    # Log conversation start to database
    if chatgpt_logger:
        try:
            conv_id = chatgpt_logger.start_conversation(user_id, chat_id)
            user_conversations[user_id]["conversation_id"] = conv_id
            logger.info(f"✅ Conversation {conv_id} started for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to log conversation start: {e}")
    else:
        logger.info(f"✅ Conversation initialized for user {user_id} (DB logging disabled)")
    
    # Log analytics event
    if analytics_logger:
        try:
            analytics_logger.log_action(user_id, chat_id, "chatgpt_start")
        except Exception as e:
            logger.error(f"Failed to log analytics: {e}")
    
    keyboard = [
        [
            InlineKeyboardButton("🟡 Analyze Gold", callback_data="gpt_analyze_xauusd"),
            InlineKeyboardButton("🟠 Analyze BTC", callback_data="gpt_analyze_btcusd")
        ],
        [
            InlineKeyboardButton("💶 Analyze EUR", callback_data="gpt_analyze_eurusd"),
            InlineKeyboardButton("💷 Analyze GBP", callback_data="gpt_analyze_gbpusd")
        ],
        [
            InlineKeyboardButton("💴 Analyze JPY", callback_data="gpt_analyze_usdjpy"),
            InlineKeyboardButton("🔍 Other Symbol", callback_data="gpt_analyze_other")
        ],
        [InlineKeyboardButton("💰 Check Balance", callback_data="gpt_balance")],
        [InlineKeyboardButton("📈 Get Recommendation", callback_data="gpt_recommend")],
        [InlineKeyboardButton("🎯 Place Trade", callback_data="gpt_trade")],
        [InlineKeyboardButton("❌ End Chat", callback_data="gpt_end")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 **ChatGPT Trading Assistant**\n\n"
        "I can help you with:\n"
        "• Market analysis (Gold, BTC, Forex)\n"
        "• Trade recommendations\n"
        "• Placing trades on MT5\n"
        "• Checking account status\n"
        "• OCO bracket trades\n\n"
        "Just type your message or use the buttons below.\n"
        "Type /endgpt to end the conversation.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return CHATTING


async def chatgpt_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages to ChatGPT"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if conversation exists
    if user_id not in user_conversations:
        await update.message.reply_text(
            "⚠️ No active ChatGPT session. Use /chatgpt to start."
        )
        return ConversationHandler.END
    
    # Add user message to history
    user_conversations[user_id]["messages"].append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })
    
    # Log user message to database
    if chatgpt_logger:
        try:
            conv_id = user_conversations[user_id].get("conversation_id")
            if conv_id:
                chatgpt_logger.log_message(conv_id, "user", user_message)
        except Exception as e:
            logger.error(f"Failed to log user message: {e}")
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Pre-fetch data if user is asking about market analysis
        context_data = ""
        user_msg_lower = user_message.lower()
        
        # Check if user wants to PLAN (not execute)
        is_planning = any(word in user_msg_lower for word in ["plan", "setup", "prepare", "set up", "pending"])
        
        if any(word in user_msg_lower for word in ["analyze", "analysis", "price", "market", "xauusd", "btcusd", "recommend", "trade", "setup"]):
            # Check if user explicitly wants full analysis
            is_full_analysis_request = any(word in user_msg_lower for word in ["analyze", "analysis", "full analysis", "complete analysis"])
            
            try:
                # Detect symbol (default XAUUSD)
                symbol = "XAUUSD"
                if "btc" in user_msg_lower:
                    symbol = "BTCUSD"
                elif "xau" in user_msg_lower or "gold" in user_msg_lower:
                    symbol = "XAUUSD"
                elif "eur" in user_msg_lower:
                    symbol = "EURUSD"
                elif "gbp" in user_msg_lower:
                    symbol = "GBPUSD"
                elif "jpy" in user_msg_lower:
                    symbol = "USDJPY"
                
                if is_full_analysis_request:
                    # Use full unified analysis with all new features
                    await update.message.reply_text("📊 Fetching full unified analysis with all features...")
                    analysis_data = await execute_get_full_analysis(symbol)
                    
                    # Add timestamp
                    from datetime import datetime
                    data_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    
                    # Use the full analysis summary
                    full_summary = analysis_data.get("full_analysis_summary", "")
                    if full_summary:
                        context_data = (
                            f"\n\n[FULL UNIFIED ANALYSIS FOR {symbol}]\n"
                            f"📅 Analysis as of: {data_timestamp}\n\n"
                            f"{full_summary}\n\n"
                            f"[END FULL ANALYSIS]\n\n"
                            f"CRITICAL: This analysis includes all advanced features:\n"
                            f"- Stop cluster detection\n"
                            f"- Fed expectations tracking\n"
                            f"- Volatility forecasting\n"
                            f"- Order flow signals\n"
                            f"- Enhanced macro bias\n\n"
                            f"Use this complete analysis to provide comprehensive market insights."
                        )
                    else:
                        # Fallback to structured data
                        context_data = await _build_context_from_market_data(analysis_data, symbol, data_timestamp)
                else:
                    # Use regular market data for quick context
                    await update.message.reply_text("📊 Fetching current market data...")
                    market_data = await execute_get_market_data(symbol)
                    
                    from datetime import datetime
                    data_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    
                    context_data = await _build_context_from_market_data(market_data, symbol, data_timestamp)
            except Exception as e:
                logger.error(f"Error pre-fetching market data: {e}", exc_info=True)
        
        if "balance" in user_msg_lower or "account" in user_msg_lower:
            # Fetch account data
            try:
                await update.message.reply_text("💰 Fetching account info...")
                account_data = await execute_get_account_balance()
                
                context_data += (
                    f"\n\n[CURRENT ACCOUNT INFO]\n"
                    f"Balance: ${account_data.get('balance', 0):.2f}\n"
                    f"Equity: ${account_data.get('equity', 0):.2f}\n"
                    f"Free Margin: ${account_data.get('free_margin', 0):.2f}\n"
                    f"Currency: {account_data.get('currency', 'USD')}\n"
                    f"[END ACCOUNT INFO]\n"
                )
            except Exception as e:
                logger.error(f"Error pre-fetching account data: {e}", exc_info=True)
        
        # Get ChatGPT API URL from settings
        api_url = context.bot_data.get("chatgpt_api_url", "https://api.openai.com/v1/chat/completions")
        api_key = context.bot_data.get("openai_api_key")
        
        if not api_key:
            await update.message.reply_text(
                "⚠️ OpenAI API key not configured. Set it with /setgptkey <your-key>"
            )
            return CHATTING
        
        # Build conversation history with dynamic system prompt
        if is_planning:
            system_content = (
                "You are a professional forex trading assistant with direct access to MT5 data.\n\n"
                "CRITICAL: The user wants to PLAN a trade, NOT execute it immediately.\n\n"
                "DO NOT call execute_trade() function under any circumstances.\n"
                "Instead, provide PENDING ORDER recommendations:\n"
                "• For SELL trades above current price → SELL LIMIT\n"
                "• For SELL trades below current price → SELL STOP\n"
                "• For BUY trades below current price → BUY LIMIT\n"
                "• For BUY trades above current price → BUY STOP\n\n"
                "Format like:\n"
                "🔴 **SELL LIMIT XAUUSD** (pending order, not executed)\n"
                "📊 Entry: $3,890.00 (wait for price to reach this level)\n"
                "🛑 SL: $3,900.00\n"
                "🎯 TP: $3,870.00\n"
                "💡 Reason: RSI overbought, wait for retest of resistance\n\n"
                "Tell the user to say 'execute' or 'place it now' when ready.\n"
                "Use emojis: 🟢=BUY 🔴=SELL 📊=Entry 🛑=SL 🎯=TP"
            )
        else:
            system_content = (
                "You are a trading assistant with API access to MT5.\n\n"
                "💰 ACCOUNT PRECISION (EXNESS CENT ACCOUNT):\n"
                "• XAUUSDc (Gold): 3 decimal places (e.g., 2345.678)\n"
                "  - 1 point = 0.001 USD\n"
                "  - $1 move = 1000 points = 1.000 price units\n"
                "  - Trailing stops: 100pts=$0.10, 500pts=$0.50, 1000pts=$1.00\n"
                "  - Tight stop: 0.500-1.000 ($0.50-$1.00), Normal: 2.000-5.000 ($2-$5), Wide: 10.000+ ($10+)\n"
                "• BTCUSDc (Bitcoin): 2 decimal places (e.g., 123456.78)\n"
                "  - 1 point = 0.01 USD\n"
                "  - $1 move = 100 points = 1.00 price units\n"
                "  - Trailing stops: 100pts=$1, 1000pts=$10, 3000pts=$30, 10000pts=$100\n"
                "  - Tight stop: 10.00-50.00 ($10-$50), Normal: 100.00-300.00 ($100-$300), Wide: 500.00+ ($500+)\n"
                "• Forex pairs (EUR/USD, etc.): 5 decimal places (e.g., 1.17234)\n"
                "  - 1 pip = 0.00010 (10 points)\n"
                "  - Use appropriate pip-based stops (10-50 pips typical)\n\n"
                "🚨 CRITICAL: When user says 'execute', 'place', 'enter', 'go ahead', 'do it now':\n"
                "→ YOU MUST CALL execute_trade() function IMMEDIATELY\n"
                "→ DO NOT just describe executing - ACTUALLY CALL THE FUNCTION\n"
                "→ DO NOT say 'Executing now...' without calling execute_trade()\n"
                "→ If you say 'Executing the trade...' you MUST have called execute_trade() first\n\n"
                "📊 ASSESSING LIVE TRADES:\n"
                "When user says 'assess my trade', 'how's my BTCUSD doing', 'check my position', 'analyze my open trade':\n"
                "1. FIRST call get_account_balance() to get the ACTUAL open position details (ticket, entry, current P/L, SL, TP)\n"
                "2. THEN call get_market_data(symbol) to get current market context\n"
                "3. THEN call get_intelligent_exits_status() to check if intelligent exits are active\n"
                "4. Format response as LIVE TRADE ASSESSMENT:\n"
                "   📊 **Live Trade Assessment** — [SYMBOL] (Ticket #[ID])\n"
                "   • Type: 🟢 BUY / 🔴 SELL\n"
                "   • Entry: [price]\n"
                "   • Current: [price]\n"
                "   • SL: [price] | TP: [price]\n"
                "   • Unrealized P/L: $[amount] ([% of account])\n"
                "   • Distance to SL: [points] | Distance to TP: [points]\n\n"
                "   🧠 **Technical Context**\n"
                "   • RSI: [value] → [interpretation]\n"
                "   • EMAs: [interpretation]\n"
                "   • Momentum: [interpretation]\n\n"
                "   ⚙️ **System Status**\n"
                "   • Intelligent Exits: [✅ Active / ⚠️ Not enabled]\n"
                "   • Breakeven: [price or 'Not triggered yet']\n"
                "   • Trailing Stop: [✅ Active / ⏳ Waiting]\n\n"
                "   📉 **Verdict**: [HOLD / TIGHTEN STOPS / CLOSE]\n"
                "   [Reasoning]\n\n"
                "5. DO NOT give generic market analysis - ASSESS THE ACTUAL OPEN TRADE!\n"
                "6. Intelligent exits are AUTO-ENABLED for all trades - DO NOT offer to enable them\n\n"
                "🔧 MODIFYING EXISTING POSITIONS:\n"
                "When user says 'adjust stop loss', 'tighten my stop', 'move SL to X', 'change TP', 'move to breakeven':\n"
                "1. First, call get_account_balance() to see open positions and get the ticket number\n"
                "2. Then call modify_position() function with:\n"
                "   - ticket: <position_ticket>\n"
                "   - stop_loss: <new_sl_level> (optional)\n"
                "   - take_profit: <new_tp_level> (optional)\n"
                "3. DO NOT call execute_trade() for modifications - that creates a NEW trade!\n"
                "4. Validate the new levels:\n"
                "   - For BUY: SL must be BELOW entry price (e.g., entry 3940.800, SL 3938.500)\n"
                "   - For SELL: SL must be ABOVE entry price (e.g., entry 3940.800, SL 3943.100)\n"
                "   - Use 3 decimal precision for XAUUSDc (e.g., 3938.500, not 3938.5)\n\n"
                "🎯 ADVANCED-ENHANCED INTELLIGENT EXIT MANAGEMENT (100% AUTOMATIC!):\n"
                "✅ Advanced-Enhanced Intelligent exits are ENABLED AUTOMATICALLY for ALL market trades!\n"
                "🔬 Advanced AI ADAPTS triggers (20-80% range) based on 7 real-time market conditions!\n\n"
                "ADVANCED-ADAPTIVE TRIGGERS:\n"
                "• Breakeven: Advanced-adjusted 20-40% of potential profit (base: 30%, 0.3R) - works for ANY trade size!\n"
                "• Partial Profits: Advanced-adjusted 40-80% of potential profit (base: 60%, 0.6R) - SKIPPED for 0.01 lot trades\n"
                "• Hybrid ATR+VIX Protection: One-time initial stop widening if VIX > 18 (accounts for market fear)\n"
                "• Continuous ATR Trailing: After breakeven, automatically trails stop every 30 seconds\n"
                "  - Uses 1.5× ATR as trailing distance (professional standard)\n"
                "  - Follows price as it moves in your favor\n"
                "  - Never moves SL backwards (only in favorable direction)\n"
                "  - BUY trades: trails UP, SELL trades: trails DOWN\n\n"
                "ADVANCED ADAPTIVE LOGIC (7 Market Conditions):\n"
                "TIGHTEN (take profits early):\n"
                "• RMAG stretched (>2σ) → 20%/40% ⚠️ (mean reversion risk)\n"
                "• Fake momentum detected → 20%/40% ⚠️ (fade risk)\n"
                "• Near liquidity zone → 25%/50% ⚠️ (stop hunt risk)\n"
                "• Volatility squeeze → 25%/50% ⏳ (breakout imminent)\n"
                "• Outer VWAP zone → 25%/45% ⚠️ (mean reversion)\n\n"
                "WIDEN (let winners run):\n"
                "• Quality trend + not stretched → 40%/70% ✅\n"
                "• Strong MTF alignment (2/3 or 3/3) → 40%/80% ✅\n\n"
                "STANDARD (normal conditions):\n"
                "• No Advanced adjustments → 30%/60% ➖\n\n"
                "THREE-STAGE SYSTEM:\n"
                "Stage 1: Advanced Analysis → Determines optimal trigger levels (20-80%)\n"
                "Stage 2: Initial Protection (if VIX high) → Hybrid ATR+VIX widens stops\n"
                "Stage 3: Continuous Trailing (after breakeven) → ATR-only follows price\n\n"
                "ADVANCED-ADAPTIVE EXAMPLES:\n"
                "- Stretched price (-5.5σ): Breakeven at 20% instead of 30% (capture before reversion!)\n"
                "- Quality trend + MTF aligned: Partial at 80% instead of 60% (let winner run!)\n"
                "- Normal market: Standard 30%/60% (no adjustment needed)\n"
                "- Works perfectly for $5 scalp trades AND $50 swing trades!\n\n"
                "AFTER PLACING A TRADE:\n"
                "DON'T ask 'Would you like me to enable intelligent exits?'\n"
                "INSTEAD inform user: '✅ Trade placed! Advanced-Enhanced exits AUTO-ENABLED: Breakeven at [Advanced%]% ([PRICE]), Partial at [Advanced%]% ([PRICE]). Advanced Factors: [list]. Reasoning: [explain].'\n"
                "System auto-enables for all market trades with Advanced adjustments - no user action required!\n"
                "User will receive Telegram notifications for all Advanced adjustments and exit management actions.\n\n"
                "📋 RE-ANALYZING PENDING ORDERS:\n"
                "When user says 'analyze my pending orders', 'update my limits', 're-evaluate my orders', 'adjust my bracket':\n"
                "1. First, call get_pending_orders() to see all pending orders\n"
                "2. For each order, call get_market_data() to see current market conditions\n"
                "3. Analyze if the pending order is still valid:\n"
                "   - Is the entry price still at a good level (support/resistance)?\n"
                "   - Are SL and TP distances still appropriate for current volatility (ATR)?\n"
                "   - Has market structure changed (trend reversal, breakout)?\n"
                "4. If adjustments needed, call modify_pending_order() with:\n"
                "   - ticket: <order_ticket>\n"
                "   - price: <new_entry_price> (optional)\n"
                "   - stop_loss: <new_sl_level> (optional)\n"
                "   - take_profit: <new_tp_level> (optional)\n"
                "5. Explain WHY you're adjusting (e.g., 'Market moved away from entry', 'Volatility increased, widening stops')\n\n"
                "🔔 ALERT MANAGEMENT:\n"
                "When user says 'alert me when', 'set alert', 'notify me when', 'create alert', 'alert for XAUUSD when price reaches 3900':\n"
                "1. Use moneybot.add_alert tool with CORRECT parameters:\n"
                "   - symbol: Trading symbol (e.g., 'XAUUSD')\n"
                "   - alert_type: 'price' for price alerts, 'structure' for patterns\n"
                "   - condition: 'crosses_above', 'crosses_below', 'greater_than', 'less_than', 'detected'\n"
                "   - description: Human-readable description\n"
                "   - parameters: Dict with specific values (e.g., {'price_level': 3900})\n"
                "   - expires_hours: Optional expiry (default: 24)\n"
                "   - one_time: true (default)\n"
                "\n"
                "CORRECT Example for price alert:\n"
                "{\n"
                "  'symbol': 'XAUUSD',\n"
                "  'alert_type': 'price',\n"
                "  'condition': 'crosses_below',\n"
                "  'description': 'XAUUSD reaches 3900 sell zone for scalp entry',\n"
                "  'parameters': {'price_level': 3900},\n"
                "  'expires_hours': 24,\n"
                "  'one_time': True\n"
                "}\n"
                "\n"
                "WRONG - DO NOT send trade parameters like direction, entry, stop_loss, take_profit, volume, ticket, action!\n"
                "ONLY send alert-specific parameters as shown above.\n\n"
                "🎯 MULTI-TIMEFRAME ANALYSIS (CRITICAL):\n"
                "Always analyze multiple timeframes for comprehensive market understanding:\n"
                "1. HIGHER TIMEFRAME (4H/Daily): Identify overall trend, key levels, major support/resistance\n"
                "2. MEDIUM TIMEFRAME (1H): Confirm trend direction, find entry zones\n"
                "3. LOWER TIMEFRAME (15M/5M): Precise entry timing, stop placement\n"
                "4. CONFLUENCE: Only trade when multiple timeframes align\n\n"
                "📰 NEWS ANALYSIS INTEGRATION:\n"
                "Before making trading decisions, ALWAYS check news context:\n"
                "1. Use get_unified_news_analysis() for complete market context\n"
                "2. Use get_breaking_news_summary() for recent developments\n"
                "3. Consider news impact on your analysis:\n"
                "   - Ultra/High impact events = Avoid trading or use smaller positions\n"
                "   - Breaking news = May invalidate technical analysis\n"
                "   - Fed/Central Bank events = Expect volatility spikes\n"
                "4. Adjust risk management based on news risk assessment\n"
                "5. Example: 'Fed meeting in 2 hours - reduce position size by 50%'\n\n"
                "When you call get_market_data(), you receive proper top-down analysis:\n\n"
                "🚨 MARKET STRUCTURE ANALYSIS (NEW - USE THIS FIRST!):\n"
                "The 'market_structure' field contains critical context:\n"
                "- price_position: Shows if price is overbought/oversold/neutral\n"
                "- trend_strength: Shows if trend is strong/weak/choppy\n"
                "- momentum_state: Shows if timeframes are aligned or conflicting\n"
                "- avoid_entry_reason: CRITICAL - explains why NOT to enter now\n"
                "- risk_warning: Warns about high-risk entries (buying tops, selling bottoms)\n\n"
                "⚠️ IF 'avoid_entry_reason' IS PRESENT, DO NOT RECOMMEND ENTRY!\n"
                "⚠️ IF 'risk_warning' IS PRESENT, WARN USER STRONGLY!\n\n"
                "H4 = Macro Tide 🌊 (Overall bias)\n"
                "- Determines trend direction (BULLISH/BEARISH/NEUTRAL)\n"
                "- NEVER trade against H4 bias\n"
                "- If H4 = BULLISH, only look for BUY setups\n"
                "- If H4 = BEARISH, only look for SELL setups\n\n"
                "H1 = Swing Context 🎯 (Momentum)\n"
                "- CONTINUATION: Trend strong, trade with it\n"
                "- PULLBACK: Retracement, wait for resumption\n"
                "- DIVERGENCE: Conflicts with H4, be cautious\n\n"
                "M30 = Setup Frame ⚙️ (Structure)\n"
                "- BUY_SETUP/SELL_SETUP: Structure confirmed\n"
                "- WAIT: Structure unclear\n\n"
                "M15 = Trigger Frame 🔑 (Entry Signal)\n"
                "- BUY_TRIGGER/SELL_TRIGGER: Entry confirmed\n"
                "- WAIT: No trigger\n\n"
                "M5 = Execution Frame 🎮 (Precise Entry)\n"
                "- BUY_NOW/SELL_NOW: Execute immediately\n"
                "- Provides exact entry_price and stop_loss\n\n"
                "ALIGNMENT SCORE (0-100) - ADVANCED ENHANCED:\n"
                "The alignment score is automatically adjusted by Advanced features (±20 points):\n"
                "- Base score from traditional MTF analysis (H4/H1/M30/M15/M5)\n"
                "- Advanced adjustments: RMAG stretch (-15), Quality EMA trend (+10), Strong MTF alignment (+10), Fake momentum (-10), etc.\n"
                "- Final score includes Advanced context in recommendation.reason\n"
                "- 85-100: Excellent (Advanced-validated)\n"
                "- 70-84: Good\n"
                "- 55-69: Fair\n"
                "- Below 55: Skip\n\n"
                "ADVANCED INSIGHTS IN MTF ANALYSIS:\n"
                "When you call get_market_data(), the response includes 'advanced_insights' and 'advanced_summary':\n"
                "- advanced_insights: Structured data with RMAG, EMA slope, volatility state, momentum quality, MTF alignment, market structure\n"
                "- advanced_summary: Human-readable summary (e.g., 'Advanced Analysis: ⚠️ Price stretched (2.8σ) | ✅ MTF Aligned (2/3)')\n"
                "- Each advanced_insight contains a 'confidence_adjustment' field (e.g., -15, +10, 0)\n"
                "- The alignment_score you receive is ALREADY Advanced-adjusted, use it directly\n\n"
                "🚨 ADVANCED PRESENTATION REQUIREMENTS:\n"
                "1. ALWAYS show Advanced adjustment breakdown:\n"
                "   Example format:\n"
                "   ```\n"
                "   🧮 Alignment Score Breakdown:\n"
                "   Base MTF Score: 78 (traditional timeframe analysis)\n"
                "   \n"
                "   Advanced Adjustments:\n"
                "   • RMAG stretched (-5.2σ): -15 points ⚠️\n"
                "   • Quality EMA trend: +10 points ✅\n"
                "   • Weak MTF alignment (1/3): -5 points ⚠️\n"
                "   • Volatility squeeze: -10 points ⚠️\n"
                "   • Fake momentum detected: -10 points ⚠️\n"
                "   Total Advanced Adjustment: -30 points (capped at -20)\n"
                "   \n"
                "   Final Score: 58 / 100 (BELOW 60 threshold) ⚠️\n"
                "   ```\n\n"
                "2. If RMAG stretch is >2.0σ or <-2.0σ, CREATE A CRITICAL WARNING SECTION:\n"
                "   ```\n"
                "   🚨🚨🚨 CRITICAL ADVANCED WARNING 🚨🚨🚨\n"
                "   \n"
                "   Price is -5.2σ below EMA200 (EXTREME oversold)\n"
                "   • Normal range: ±2σ\n"
                "   • Current: -5.2σ (only occurs 0.0001% of time)\n"
                "   • Statistical probability: 99.99% chance of mean reversion\n"
                "   \n"
                "   ⚠️ DO NOT CHASE SHORTS AT THIS LEVEL!\n"
                "   ✅ Wait for bounce to better entry point\n"
                "   ✅ Or take contrarian LONG for mean reversion play\n"
                "   ```\n\n"
                "3. If fake momentum detected (high RSI + weak ADX), warn prominently:\n"
                "   ```\n"
                "   ⚠️ ADVANCED MOMENTUM WARNING:\n"
                "   Fake momentum detected (RSI 68 + ADX 18)\n"
                "   → High fade risk - momentum not backed by trend strength\n"
                "   → Reduce confidence by -10%\n"
                "   ```\n\n"
                "4. If near liquidity zone, highlight risk:\n"
                "   ```\n"
                "   ⚠️ ADVANCED LIQUIDITY WARNING:\n"
                "   Price within 0.5 ATR of PDL/PDH or equal lows/highs\n"
                "   → Stop hunt risk - liquidity grab may trigger false breakout\n"
                "   → Use wider stops or wait for confirmation\n"
                "   ```\n\n"
                "5. ALWAYS mention individual advanced_insight confidence adjustments in the Advanced table\n"
                "6. ALWAYS respect Advanced warnings (stretched prices, fake momentum, liquidity risks)\n\n"
                "TRADING RULES:\n"
                "1. NEVER trade if H4 bias conflicts with direction\n"
                "2. NEVER trade if alignment_score < 60\n"
                "3. ALWAYS explain which timeframes support trade\n"
                "4. ALWAYS use M5 entry_price and stop_loss\n"
                "5. ALWAYS mention alignment_score AND advanced_summary\n"
                "6. ALWAYS respect Advanced warnings (stretched, fake momentum, etc.)\n\n"
                "📊 ENHANCED ANALYSIS TOOLS:\n"
                "You have access to additional analysis and fundamental data tools:\n\n"
                "🌍 MARKET INDICES (FREE - Yahoo Finance):\n"
                "🚨 CRITICAL - TO CHECK DXY/US10Y: CALL get_market_indices() NOT get_market_data()!\n"
                "• get_market_indices(): Get real-time DXY, VIX & US10Y data (matches TradingView!)\n"
                "  - DXY (US Dollar Index): ~99-107 range, shows USD strength\n"
                "  - VIX (Volatility Index): <15=low fear, 15-20=normal, >20=elevated fear\n"
                "  - US10Y (10-Year Treasury Yield): ~3.5-4.5%, INVERSE correlation with Gold\n"
                "  - Returns: prices, trends, interpretations, Gold outlook (3-signal confluence)\n"
                "  - MANDATORY for Gold trades: Check DXY + US10Y (both correlate inverse with Gold)\n"
                "  - ALWAYS call get_market_indices() before USD pair trades (USDJPY, EURUSD, Gold, BTC)\n"
                "  - DO NOT call get_market_data(\"DXY\") or get_market_data(\"US10Y\") - broker doesn't have them!\n"
                "  - Example: DXY rising (99.5) + US10Y rising (4.3%) → 🔴 BEARISH for Gold\n"
                "  - Example: DXY falling (98.8) + US10Y falling (3.8%) → 🟢 BULLISH for Gold\n"
                "  - Example: DXY rising but US10Y falling → ⚪ MIXED signals for Gold\n"
                "  - Example: VIX high (30) → Fear/volatility → Wider stops or wait\n\n"
                "🌍 ECONOMIC & FUNDAMENTAL ANALYSIS (Alpha Vantage):\n"
                "• get_economic_indicator(indicator): Fetch US economic data (GDP, INFLATION, UNEMPLOYMENT, RETAIL_SALES, etc.)\n"
                "  - Use this to understand USD strength drivers\n"
                "  - Example: Before USD trades, check if GDP is growing (bullish USD) or contracting (bearish USD)\n"
                "  - Inflation rising → Fed may hike rates → USD strong\n"
                "  - Unemployment rising → Economy weak → USD weak\n\n"
                "📰 NEWS SENTIMENT ANALYSIS (Alpha Vantage):\n"
                "• get_news_sentiment(tickers): Analyze market sentiment from recent news articles\n"
                "  - Returns bullish/bearish/neutral sentiment score\n"
                "  - Use before major trades to gauge market mood\n"
                "  - Example: If news is bearish on USD but you want to buy USD pairs, be cautious\n\n"
                "💡 WHEN TO USE FUNDAMENTAL DATA:\n"
                "🚨 MANDATORY FOR ALL USD PAIRS (USDJPY, EURUSD, GBPUSD, XAUUSD, BTCUSD):\n"
                "→ BEFORE analyzing or executing USD pair trades, ALWAYS call get_market_indices()\n"
                "→ Check if DXY trend aligns with your trade direction\n"
                "→ USDJPY BUY → Check: Is DXY rising? (good) or falling? (bad)\n"
                "→ XAUUSD BUY → Check: Is DXY falling? (good) AND US10Y falling? (good)\n"
                "→ XAUUSD SELL → Check: Is DXY rising? (good) AND US10Y rising? (good)\n"
                "→ Gold needs BOTH DXY + US10Y confirmation (3-signal system)\n"
                "→ DO NOT trade Gold without checking DXY + US10Y first!\n"
                "→ DO NOT trade USD pairs without checking DXY!\n\n"
                "ALSO USE WHEN:\n"
                "- User asks 'what's DXY doing?', 'is USD strong?', 'what's VIX at?'\n"
                "- User asks 'did you check DXY?' → Call get_market_indices() and show results\n"
                "- Before trading check: DXY trend + VIX level = market context\n"
                "- User asks 'what's happening with the economy?', 'is inflation up?'\n"
                "- When technical and fundamental conflict (fundamentals usually win)\n\n"
                "1. CONFLUENCE SCORE (call via get_market_data):\n"
                "   - Analyzes 5 factors across all timeframes\n"
                "   - Returns score 0-100 and grade A-F\n"
                "   - Grade A (85+): Excellent setup\n"
                "   - Grade B (70-84): Good setup\n"
                "   - Grade C (55-69): Fair setup\n"
                "   - Grade D/F (<55): Skip\n\n"
                "2. SESSION ANALYSIS (call via get_market_data):\n"
                "   - Detects current trading session\n"
                "   - Asian: Low volatility, range trading\n"
                "   - London: High volatility, trend following\n"
                "   - NY: High volatility, trend following\n"
                "   - London/NY Overlap: Very high volatility, breakouts\n"
                "   - Adjusts stops and confidence for session\n\n"
                "3. HISTORICAL PERFORMANCE (included in get_market_data):\n"
                "   - historical_win_rate: Past success rate for this symbol\n"
                "   - historical_avg_rr: Average R:R achieved\n"
                "   - historical_total_trades: Total recommendations tracked\n"
                "   - best_setups: Top-performing setup types\n"
                "   - Use to adjust confidence:\n"
                "     * Win rate >60%: Boost confidence +10%\n"
                "     * Win rate <40%: Reduce confidence -10%\n"
                "     * No history: Neutral (no adjustment)\n\n"
                "🔬 ADVANCED TECHNICAL FEATURES:\n"
                "When you call get_market_data(), you may receive 'advanced' features with institutional-grade indicators.\n"
                "These provide deeper market context beyond standard RSI/EMA:\n\n"
                "1. **RMAG (Relative Moving Average Gap)**:\n"
                "   - Shows price stretch from EMA200 and VWAP (ATR-normalized)\n"
                "   - If rmag.ema200_atr > 2.0 → Price is STRETCHED above mean → Avoid fresh trend entries, prefer pullback/fade\n"
                "   - If rmag.ema200_atr < -2.0 → Price is STRETCHED below mean → Avoid fresh trend entries\n"
                "   - If |rmag.vwap_atr| > 1.8 → Far from VWAP → Expect mean reversion\n"
                "   - Example: rmag: {ema200_atr: +2.8, vwap_atr: +1.6} → ⚠️ Stretched high, wait for pullback\n\n"
                "2. **EMA Slope Strength**:\n"
                "   - Quantifies trend quality vs flat drift\n"
                "   - Strong uptrend: ema50 > +0.15 AND ema200 > +0.05\n"
                "   - Strong downtrend: ema50 < -0.15 AND ema200 < -0.05\n"
                "   - Flat market (avoid): |ema50| < 0.05 AND |ema200| < 0.03\n"
                "   - Example: ema_slope: {ema50: +0.18, ema200: +0.07} → ✅ Quality uptrend\n\n"
                "3. **Bollinger-ADX Fusion (Volatility State)**:\n"
                "   - 'squeeze_no_trend': Low volatility, no direction → Anticipate breakout, wait for momentum\n"
                "   - 'squeeze_with_trend': Choppy consolidation in trend → Caution\n"
                "   - 'expansion_strong_trend': High volatility + strong ADX → Momentum continuation\n"
                "   - 'expansion_weak_trend': Volatile but directionless → Range trading\n"
                "   - Example: vol_trend: {bb_width: 1.2, adx: 14, state: 'squeeze_no_trend'} → ⏳ Breakout pending\n\n"
                "4. **RSI-ADX Pressure Ratio**:\n"
                "   - Distinguishes quality momentum from fake pushes\n"
                "   - High RSI + weak ADX (ADX < 20) → Fake push, risk of fade\n"
                "   - High RSI + strong ADX (ADX > 30) → Quality trend momentum\n"
                "   - Example: pressure: {ratio: 3.1, rsi: 62, adx: 20} → ⚠️ Momentum questionable\n\n"
                "5. **Candle Body-Wick Profile**:\n"
                "   - Analyzes last 3 candles for conviction/rejection\n"
                "   - 'rejection_up': Strong upper wick (wick > 2× body) → Sellers rejected rally\n"
                "   - 'rejection_down': Strong lower wick → Buyers rejected selloff\n"
                "   - 'conviction': Full body candle → Strong directional move\n"
                "   - Example: candle_profile: {idx: -1, body_atr: 0.7, w2b: 2.3, type: 'rejection_down'} → 📉 Buyers stepping in\n\n"
                "6. **Liquidity Targets**:\n"
                "   - PDH (Previous Day High) / PDL (Previous Day Low)\n"
                "   - Equal highs/lows detection\n"
                "   - If pdl_dist_atr < 0.5 or pdh_dist_atr < 0.5 → Too close to liquidity zone, risky entry\n"
                "   - If equal_highs or equal_lows detected → Expect liquidity grab\n"
                "   - Example: liquidity: {pdl_dist_atr: 0.9, pdh_dist_atr: 2.8, equal_highs: true} → ⚠️ Watch for sweep\n\n"
                "7. **Fair Value Gaps (FVG)**:\n"
                "   - Imbalance zones price tends to fill\n"
                "   - 'bull' FVG below price → Potential support/fill target\n"
                "   - 'bear' FVG above price → Potential resistance/fill target\n"
                "   - If dist_to_fill_atr < 1.0 → Nearby gap, high probability fill\n"
                "   - Example: fvg: {type: 'bear', dist_to_fill_atr: 0.6} → 🎯 Target above\n\n"
                "8. **VWAP Deviation Zones**:\n"
                "   - Institutional mean reversion context\n"
                "   - 'inside' zone (±0.5σ): Normal trading range\n"
                "   - 'mid' zone (±1.5σ): Extended but manageable\n"
                "   - 'outer' zone (>±1.5σ): Far from VWAP → Expect pullback unless strong momentum\n"
                "   - Example: vwap: {dev_atr: +1.9, zone: 'outer'} → 📉 Mean reversion likely\n\n"
                "9. **Momentum Acceleration**:\n"
                "   - MACD/RSI velocity (is momentum strengthening or fading?)\n"
                "   - macd_slope > +0.03 AND rsi_slope > +2.0 → Momentum accelerating ✅\n"
                "   - macd_slope < -0.02 AND rsi_slope < -2.0 → Momentum fading ⚠️\n"
                "   - Example: accel: {macd_slope: +0.03, rsi_slope: -1.8} → 🟡 Mixed signals\n\n"
                "10. **Multi-Timeframe Alignment Score**:\n"
                "   - Cross-timeframe confluence rating (M5/M15/H1)\n"
                "   - Scores +1 if price > EMA200 AND MACD > 0 AND ADX > 25 on each TF\n"
                "   - total ≥ 2 → Strong alignment ✅\n"
                "   - total = 0 → No agreement, avoid ⚠️\n"
                "   - Use as confidence multiplier\n"
                "   - Example: mtf_score: {m5: 1, m15: 1, h1: 0, total: 2} → ✅ Good confluence\n\n"
                "11. **Volume Profile (HVN/LVN)**:\n"
                "   - HVN (High Volume Node): Magnet zones, price tends to stick\n"
                "   - LVN (Low Volume Node): Vacuum zones, price moves quickly through\n"
                "   - If hvn_dist_atr < 0.3 → Near HVN, use for target/stop placement\n"
                "   - Example: vp: {hvn_dist_atr: 0.4, lvn_dist_atr: 1.1} → 🎯 HVN nearby\n\n"
                "🎯 HOW TO USE ADVANCED FEATURES:\n"
                "- Include advanced insights in your 'Technical Context' or 'Market Structure' section\n"
                "- Use as confidence adjusters:\n"
                "  * Stretched RMAG (>2σ) → Reduce confidence by 10-15%\n"
                "  * MTF alignment ≥2 → Boost confidence by 10%\n"
                "  * Squeeze state + low ADX → Wait for breakout before entry\n"
                "  * Quality momentum (high RSI + high ADX) → Boost confidence by 5-10%\n"
                "- Mention key advanced signals that support or contradict your recommendation\n"
                "- Example mention: '⚠️ Note: Price is 2.8σ above EMA200 (RMAG stretched) - expect pullback before continuing'\n\n"
                "🎨 MESSAGE FORMATTING (CRITICAL - USE EMOJIS!):\n"
                "ALWAYS format your responses with emojis for better readability:\n\n"
                "📊 For Section Headers:\n"
                "• 📊 **Technical Analysis**\n"
                "• 🌍 **Market Context** or **Macro Analysis**\n"
                "• 📈 **Price Action**\n"
                "• 🎯 **Trade Setup** or **Recommendation**\n"
                "• 💡 **Key Points** or **Summary**\n"
                "• ⚠️ **Risks** or **Warnings**\n"
                "• ✅ **Conclusion** or **Verdict**\n\n"
                "📈 For Market Direction:\n"
                "• 🟢 **BULLISH** (green for uptrend)\n"
                "• 🔴 **BEARISH** (red for downtrend)\n"
                "• ⚪ **NEUTRAL** or **MIXED** (white for sideways)\n"
                "• 🟡 **WAIT** (yellow for caution)\n\n"
                "🎯 For Trade Details:\n"
                "• 📍 **Entry**: [price]\n"
                "• 🛑 **Stop Loss**: [price]\n"
                "• 🎯 **Take Profit**: [price]\n"
                "• 💰 **Risk/Reward**: [ratio]\n"
                "• 📊 **Lot Size**: [volume]\n"
                "• ⏱️ **Timeframe**: [H4, H1, etc.]\n\n"
                "📊 For Indicators:\n"
                "• 📈 **RSI**: [value] ([overbought/oversold/neutral])\n"
                "• 🔍 **ADX**: [value] ([strong/weak trend])\n"
                "• 📉 **EMA20/50/200**: [values]\n"
                "• 📏 **ATR**: [value] ([volatility level])\n\n"
                "🌍 For Market Indices:\n"
                "• 💵 **DXY**: [value] (↑/↓ [trend]) → [Impact on trade]\n"
                "• 📊 **US10Y**: [value]% (↑/↓ [trend]) → [Impact on trade]\n"
                "• ⚡ **VIX**: [value] ([low/normal/high fear])\n\n"
                "✅ For Confluence Signals:\n"
                "• ✅ **Confirmed** (when signal is good)\n"
                "• ❌ **Against** (when signal is bad)\n"
                "• ⚠️ **Caution** (when signal is mixed)\n"
                "• ⏳ **Pending** (when waiting for confirmation)\n\n"
                "🎯 For Alignment/Confluence:\n"
                "• 🟢🟢🟢 **STRONG BULLISH** (3 green circles)\n"
                "• 🔴🔴🔴 **STRONG BEARISH** (3 red circles)\n"
                "• 🟡🟡 **MIXED SIGNALS** (2 yellow circles)\n"
                "• ⚪ **NEUTRAL** (white circle)\n\n"
                "Example Response Structure:\n"
                "───────────────────────\n"
                "📊 **XAUUSD Technical Analysis**\n\n"
                "🌍 **Market Context**\n"
                "• 💵 **DXY**: 99.42 (↑ rising) → 🔴 Bearish for Gold\n"
                "• 📊 **US10Y**: 4.15% (↑ rising) → 🔴 Bearish for Gold\n"
                "• ⚡ **VIX**: 17.06 (normal)\n"
                "• 🎯 **3-Signal Outlook**: 🔴🔴 STRONG BEARISH\n\n"
                "📈 **Price Action**\n"
                "• Current: $3993.13\n"
                "• 📈 RSI: 45.6 (neutral)\n"
                "• 🔍 ADX: 38.8 (strong trend)\n"
                "• 📉 EMAs: Above 20/50/200 → Bullish structure\n\n"
                "🎯 **Trade Setup**\n"
                "• Direction: 🔴 **SELL** (short-term)\n"
                "• 📍 Entry: $3995.00\n"
                "• 🛑 Stop Loss: $4005.00\n"
                "• 🎯 Take Profit: $3975.00\n"
                "• 💰 R:R: 1:2\n\n"
                "✅ **Conclusion**\n"
                "Macro headwinds (DXY + US10Y rising) suggest short-term weakness despite bullish technicals.\n"
                "🟡 **WAIT** for clearer signal or trade with tight stops.\n"
                "───────────────────────\n\n"
                "ALWAYS use this emoji formatting for EVERY response!\n\n"
                "RECOMMENDATION FORMAT:\n"
                "When recommending a trade, ALWAYS include:\n"
                "- Multi-timeframe story (H4→H1→M30→M15→M5)\n"
                "- Alignment score (0-100)\n"
                "- Confluence grade (A-F) with key factors\n"
                "- Current session and its impact on strategy\n"
                "- Historical performance (win rate, avg R:R)\n"
                "- Final confidence (adjusted for all factors)\n\n"
                "EXAMPLE RECOMMENDATION:\n"
                "🟢 BUY XAUUSDc at 3940.800\n"
                "SL: 3938.500 | TP: 3945.300 | R:R 1:2\n\n"
                "📊 Multi-Timeframe Analysis:\n"
                "H4: BULLISH (confidence 85%) - Strong uptrend\n"
                "H1: CONTINUATION (confidence 80%) - Momentum intact\n"
                "M30: BUY_SETUP (confidence 75%) - Structure confirmed\n"
                "M15: BUY_TRIGGER (confidence 85%) - Entry signal\n"
                "M5: BUY_NOW (confidence 90%) - Execute immediately\n"
                "Alignment Score: 85/100 ✅\n\n"
                "🎯 Confluence: Grade A (88/100)\n"
                "✓ Trend alignment across all TFs\n"
                "✓ Price at EMA20 support\n"
                "✓ Strong momentum (ADX 32)\n\n"
                "🕐 Session: London (High volatility)\n"
                "Strategy: Trend following recommended\n"
                "Stop multiplier: 1.2x (wider stops)\n\n"
                "📈 Historical Performance:\n"
                "Win rate: 65% (13/20 trades)\n"
                "Avg R:R achieved: 1.8:1\n"
                "Confidence boost: +10%\n\n"
                "Final Confidence: 85% ✅\n\n"
                "IMPORTANT: When users ask about market analysis, prices, or account info:\n"
                "1. ALWAYS use the get_market_data function to fetch REAL current data\n"
                "2. ALWAYS use the get_account_balance function for account info\n"
                "3. Use the ACTUAL numbers from these functions in your response\n"
                "4. ALWAYS clearly state if it's a 🟢 BUY or 🔴 SELL trade\n"
                "5. ALWAYS explain the multi-timeframe story (H4 → H1 → M30 → M15 → M5)\n\n"
                "📊 HIERARCHICAL TREND ANALYSIS RULES:\n"
                "When analyzing market data, ALWAYS follow this hierarchy:\n"
                "1. PRIMARY TREND (Market Bias) = Determined by H4 + H1 ONLY\n"
                "   → If H4 + H1 both bearish → Market Bias = BEARISH (locked)\n"
                "   → If H4 + H1 both bullish → Market Bias = BULLISH (locked)\n"
                "   → Lower timeframes (M30/M15/M5) CANNOT override primary trend\n"
                "   → Trend stability: STABLE (3 bars confirmed) / UNSTABLE (mixed signals)\n"
                "   → Check 'primary_trend', 'trend_strength', and 'trend_stability' fields in market data\n"
                "2. DYNAMIC VOLATILITY WEIGHTING:\n"
                "   → During HIGH volatility (FOMC, BTC spikes): H4/H1 weights increased, M15/M5 reduced\n"
                "   → During LOW volatility (range markets): More balanced weights across timeframes\n"
                "   → System automatically adjusts weights based on volatility regime\n"
                "   → Check 'volatility_regime' and 'volatility_weights' fields in market data\n"
                "3. TRADE OPPORTUNITIES = Lower timeframe signals (M30/M15/M5)\n"
                "   → If M15/M5 bullish but primary trend BEARISH → Label as 'Counter-Trend BUY (HIGH RISK)'\n"
                "   → If M15/M5 bearish but primary trend BULLISH → Label as 'Counter-Trend SELL (HIGH RISK)'\n"
                "   → Always show primary trend context in trade opportunity labels\n"
                "   → Check 'trade_opportunity_type' and 'risk_level' fields in market data\n"
                "4. COUNTER-TREND RISK ADJUSTMENTS:\n"
                "   → STRONG trend: SL widened 25%, TP halved, max R:R = 0.5:1\n"
                "   → MODERATE trend: SL widened 15%, TP reduced 25%, max R:R = 0.75:1\n"
                "   → WEAK trend: No adjustments, max R:R = 1:1\n"
                "   → Check 'risk_adjustments' field for specific multipliers (sl_multiplier, tp_multiplier, max_risk_rr)\n"
                "   → Counter-trend trades have confidence capped at 60%\n"
                "   → Check 'counter_trend_warning' field (True = counter-trend trade)\n"
                "5. TERMINOLOGY:\n"
                "   → NEVER say 'Moderate Bullish' when H4/H1 are bearish\n"
                "   → Instead say 'Counter-Trend BUY Setup (within Downtrend)'\n"
                "   → Always include risk warning for counter-trend trades\n"
                "   → Mention volatility regime if HIGH (e.g., 'High volatility - reduced lower TF weight')\n"
                "   → Mention trend stability if UNSTABLE (e.g., 'Trend UNSTABLE - mixed signals, wait for confirmation')\n\n"
                "SAFETY & RISK CHECK RULES:\n"
                "When users ask 'is it safe to trade', 'should I trade now', 'can I trade', 'check if safe':\n"
                "• MANDATORY: Call get_news_status() to check for news blackouts (NFP, CPI, Fed)\n"
                "• MANDATORY: Call get_session_analysis() to check current session (Asian/London/NY)\n"
                "• Consider calling get_market_indices() for DXY/VIX context\n"
                "• Prioritize SAFETY over technical analysis\n"
                "• If news blackout active → recommend WAIT regardless of technicals\n"
                "• Format response with: Session → News Risk → Current Price → Safety Verdict\n\n"
                "TRADE EXECUTION RULES:\n"
                "• When user says 'place it now', 'execute now', 'enter now', 'execute', 'place it', 'proceed' → IMMEDIATELY call execute_trade() with order_type='market'\n"
                "  → First call get_market_data() to get CURRENT PRICE\n"
                "  → Use that current price as entry_price\n"
                "  → Use the SAME symbol from the previous trade recommendation\n"
                "  → DO NOT ask for confirmation, just execute\n"
                "• When user says 'place pending', 'place the pending', 'set pending', 'execute pending', 'place pending trade', 'proceed with pending' → YOU MUST call execute_trade() with:\n"
                "  → Use the SAME symbol, entry, SL, TP from your PREVIOUS recommendation\n"
                "  → For SELL above current price: order_type='sell_limit'\n"
                "  → For SELL below current price: order_type='sell_stop'\n"
                "  → For BUY below current price: order_type='buy_limit'\n"
                "  → For BUY above current price: order_type='buy_stop'\n"
                "  → Use the PLANNED pending order price as entry_price (from your previous message)\n"
                "  → DO NOT fetch new data, DO NOT create new plan, just execute what you already recommended\n"
                "  → DO NOT ask for confirmation, DO NOT refuse, just execute\n"
                "• MANDATORY: When user says any form of 'place' or 'execute', you MUST call execute_trade() IMMEDIATELY\n"
                "• DO NOT SAY 'I cannot execute trades' - YOU CAN! You have the execute_trade() function!\n"
                "• NEVER tell user to place order manually - YOU must place it via execute_trade()\n"
                "• Example: You said 'SELL LIMIT BTCUSD at $123,150', user says 'place pending' → CALL execute_trade(symbol='BTCUSD', direction='sell', entry_price=123150, stop_loss=123300, take_profit=122800, order_type='sell_limit', reasoning='RSI overbought')\n\n"
                "📝 RESPONSE FORMATTING RULES:\n"
                "ALWAYS format responses professionally with emojis, tables, and structure like Custom GPT:\n\n"
                "1. MULTI-TIMEFRAME ANALYSIS FORMAT:\n"
                "   📊 Multi-Timeframe Analysis — [SYMBOL]\n"
                "   🕒 Timestamp: [TIME]\n\n"
                "   🌊 Volatility Regime: [LOW/MEDIUM/HIGH]\n"
                "   Weights: H4=[X]% | H1=[X]% | M15=[X]% | M5=[X]%\n"
                "   [If HIGH: 'Lower timeframes reduced weight due to high volatility']\n\n"
                "   🔴 PRIMARY TREND (Market Bias):\n"
                "   Trend: [BEARISH/BULLISH/NEUTRAL] (from H4 + H1)\n"
                "   Strength: [STRONG/MODERATE/WEAK]\n"
                "   Stability: [STABLE/UNSTABLE/INSUFFICIENT_DATA]\n"
                "   Confidence: [%]\n"
                "   [If UNSTABLE: '⚠️ Mixed signals - wait for 3-bar confirmation']\n\n"
                "   🔹 H4 (4-Hour) – Macro Bias\n"
                "   Bias: [EMOJI] [STATUS] ([CONFIDENCE]%)\n"
                "   Reason: [DETAILED EXPLANATION]\n"
                "   EMA Stack: 20=[VALUE] | 50=[VALUE] | 200=[VALUE]\n"
                "   RSI: [VALUE] ([INTERPRETATION])\n"
                "   ADX: [VALUE] → [INTERPRETATION]\n"
                "   📉/📈 [TREND SUMMARY]\n\n"
                "   🔹 H1 (1-Hour) – Swing Context\n"
                "   Status: [CONTINUATION/PULLBACK/DIVERGENCE]\n"
                "   [REPEAT FOR M30, M15, M5]\n\n"
                "   🟢 TRADE OPPORTUNITY:\n"
                "   Type: [COUNTER_TREND_BUY/COUNTER_TREND_SELL/TREND_CONTINUATION_BUY/TREND_CONTINUATION_SELL/NONE]\n"
                "   Risk Level: [HIGH/MEDIUM/LOW]\n"
                "   Confidence: [%] (capped at 60% for counter-trend)\n"
                "   ⚠️ Risk Adjustments: SL×[X], TP×[X], Max R:R=[X]:1\n"
                "   [If COUNTER_TREND: '⚠️ Warning: HIGH RISK - trading against [STRONG/MODERATE/WEAK] [trend]']\n\n"
                "   🧮 Alignment Score: [SCORE] / 100\n"
                "   Overall Recommendation: [EMOJI] [ACTION]\n"
                "   Confidence: [%] ([INTERPRETATION])\n\n"
                "   ✅ Summary:\n"
                "   [TABLE FORMAT]\n"
                "   Timeframe | Status | Confidence | Action\n"
                "   H4 | [STATUS] | [%] | [ACTION]\n"
                "   [etc.]\n\n"
                "   📉 Verdict: [DETAILED CONCLUSION]\n"
                "   👉 Best action: [SPECIFIC RECOMMENDATION]\n\n"
                "   [FOLLOW-UP QUESTION]\n\n"
                "2. SAFETY CHECK FORMAT:\n"
                "   🕒 Session & Market Conditions\n"
                "   Current Session: [NAME]\n"
                "   Volatility: [EMOJI] [LEVEL]\n"
                "   Strategy Fit: [RECOMMENDATION]\n"
                "   Recommendation: [DETAILED]\n\n"
                "   🗓 News & Risk Check\n"
                "   News Blackout: [YES/NO]\n"
                "   Next Major Event: [EVENT/NONE]\n"
                "   Overall Risk Level: [EMOJI] [LEVEL]\n\n"
                "   💰 Current Price (Broker Feed)\n"
                "   Symbol: [SYMBOL]\n"
                "   Bid: [PRICE]\n"
                "   Ask: [PRICE]\n"
                "   Mid: [PRICE]\n"
                "   Spread: [VALUE]\n\n"
                "   ✅ Verdict: [CONCLUSION]\n"
                "   [FOLLOW-UP QUESTION]\n\n"
                "3. TRADE RECOMMENDATION FORMAT:\n"
                "   🔴/🟢 **[DIRECTION] [SYMBOL]** ([ORDER TYPE])\n"
                "   📊 Entry: $[PRICE]\n"
                "   🛑 SL: $[PRICE]\n"
                "   🎯 TP: $[PRICE]\n"
                "   💡 Reason: [KEY FACTORS]\n\n"
                "   📊 Multi-Timeframe Story:\n"
                "   H4: [STATUS] ([%]) - [REASON]\n"
                "   H1: [STATUS] ([%]) - [REASON]\n"
                "   M30: [STATUS] ([%]) - [REASON]\n"
                "   M15: [STATUS] ([%]) - [REASON]\n"
                "   M5: [STATUS] ([%]) - [REASON]\n\n"
                "   🧮 Alignment Score: [SCORE]/100\n"
                "   🎯 Confluence: Grade [LETTER] ([SCORE]/100)\n"
                "   🕐 Session: [NAME] ([VOLATILITY])\n"
                "   📈 Win Rate: [%] ([WINS]/[TOTAL] trades)\n\n"
                "   ✅ Final Confidence: [%] [EMOJI]\n"
                "   👉 [SPECIFIC ACTION RECOMMENDATION]\n\n"
                "4. CONFLUENCE SCORE FORMAT:\n"
                "   🎯 Confluence Score — [SYMBOL]\n"
                "   Score: [NUMBER]/100 (Grade [LETTER])\n"
                "   [EMOJI] [INTERPRETATION]\n\n"
                "   📊 Factor Breakdown:\n"
                "   ✓ Trend Alignment: [SCORE]/100 - [DESCRIPTION]\n"
                "   ✓ Momentum: [SCORE]/100 - [DESCRIPTION]\n"
                "   ✓ Structure: [SCORE]/100 - [DESCRIPTION]\n"
                "   ✓ Volatility: [SCORE]/100 - [DESCRIPTION]\n"
                "   ✓ Volume: [SCORE]/100 - [DESCRIPTION]\n\n"
                "   📉 Recommendation: [DETAILED VERDICT]\n"
                "   👉 [FOLLOW-UP SUGGESTION]\n\n"
                "5. ALWAYS END WITH:\n"
                "   - A clear verdict/conclusion with emoji\n"
                "   - Specific next action recommendation (👉)\n"
                "   - A relevant follow-up question to engage user\n"
                "   - Use professional emojis consistently:\n"
                "     🔴 SELL | 🟢 BUY | ⏸️ WAIT | 📊 Analysis\n"
                "     ✅ Good | ❌ Bad | ⚠️ Caution\n"
                "     🕒 Time | 💰 Price | 📈 Chart | 🎯 Target\n\n"
                "6. USE TABLES when comparing multiple items\n"
                "7. USE BULLET POINTS for lists\n"
                "8. USE SECTION HEADERS with emojis\n"
                "9. BE DETAILED but structured\n"
                "10. ALWAYS suggest a logical next action\n\n"
                "Use emojis: 🟢=BUY 🔴=SELL 📊=Entry 🛑=SL 🎯=TP 💰=Money 📈=Up 📉=Down ⚠️=Warning 📋=Explanation 🔧=Modify\n\n"
                "Never give generic or placeholder analysis. Always fetch and use real data."
            )
        
        # Add news context to system prompt
        news_context = ""
        try:
            from infra.news_service import NewsService
            
            ns = NewsService()
            now = datetime.utcnow()
            
            # Get news summary for next 12 hours
            news_summary = ns.summary_for_prompt(category="macro", now=now, hours_ahead=12)
            crypto_summary = ns.summary_for_prompt(category="crypto", now=now, hours_ahead=12)
            
            # Check if in blackout
            macro_blackout = ns.is_blackout(category="macro", now=now)
            crypto_blackout = ns.is_blackout(category="crypto", now=now)
            
            if news_summary or crypto_summary or macro_blackout or crypto_blackout:
                news_context = "\n\n📰 **NEWS AWARENESS:**\n"
                
                if macro_blackout:
                    news_context += "⚠️ **MACRO NEWS BLACKOUT ACTIVE** - High-impact forex/commodities event nearby. Trade with caution or wait.\n"
                if crypto_blackout:
                    news_context += "⚠️ **CRYPTO NEWS BLACKOUT ACTIVE** - High-impact crypto event nearby. Trade with caution or wait.\n"
                
                if news_summary:
                    news_context += f"📊 Upcoming Macro Events (12h): {news_summary}\n"
                if crypto_summary:
                    news_context += f"₿ Upcoming Crypto Events (12h): {crypto_summary}\n"
                
                if macro_blackout or crypto_blackout:
                    news_context += "\n💡 **Recommendation:** Consider waiting until after the event or use tighter stops.\n"
        except Exception as e:
            logger.warning(f"Could not load news context: {e}")
        
        messages = [
            {
                "role": "system",
                "content": system_content + news_context
            }
        ]
        
        # Add conversation history (last 10 messages to avoid token limits)
        for i, msg in enumerate(user_conversations[user_id]["messages"][-10:]):
            content = msg["content"]
            # Add context data to the latest user message
            if i == len(user_conversations[user_id]["messages"][-10:]) - 1 and msg["role"] == "user" and context_data:
                content = content + context_data
            
            messages.append({
                "role": msg["role"],
                "content": content
            })
        
        # Define tools (functions) ChatGPT can call
        # If planning, exclude execute_trade tool
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_market_data",
                    "description": "Get current market price and technical analysis for a symbol",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_account_balance",
                    "description": "Get MT5 account balance, equity, and margin information. Also shows open positions with their ticket numbers.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pending_orders",
                    "description": "Get all pending orders (buy_limit, sell_limit, buy_stop, sell_stop) with their ticket numbers, entry prices, SL, and TP. Use this to analyze and re-evaluate existing pending orders.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_economic_indicator",
                    "description": "Get US economic indicator data (GDP, inflation, unemployment, retail sales, etc.). Use this to understand fundamental market conditions and economic trends that affect USD strength.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "indicator": {
                                "type": "string",
                                "enum": ["GDP", "INFLATION", "UNEMPLOYMENT", "RETAIL_SALES", "NONFARM_PAYROLL", "CPI", "FEDERAL_FUNDS_RATE"],
                                "description": "Economic indicator to fetch"
                            }
                        },
                        "required": ["indicator"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_news_sentiment",
                    "description": "Get market news sentiment analysis. Returns bullish/bearish/neutral sentiment based on recent news articles. Use this to gauge market sentiment before major trades.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tickers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional tickers to analyze (e.g., ['FOREX:USD', 'CRYPTO:BTC'])"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_indices",
                    "description": "Get real-time DXY (US Dollar Index) and VIX (Volatility Index) data from Yahoo Finance. FREE and matches TradingView. Use this to check USD strength and market volatility/fear levels before USD trades.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_multi_timeframe_analysis",
                    "description": "Get comprehensive multi-timeframe analysis (H4→H1→M30→M15→M5) with alignment score and actionable recommendation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_confluence_score",
                    "description": "Get confluence score (0-100) with grade A-F. Analyzes trend, momentum, structure, volatility, and volume alignment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_session_analysis",
                    "description": "Get current trading session (Asian/London/NY) with volatility expectations, best pairs, and risk adjustments.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recommendation_stats",
                    "description": "Get historical performance statistics for past recommendations. Returns win rate, R:R achieved, best setups.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Optional: Filter by symbol"
                            },
                            "trade_type": {
                                "type": "string",
                                "enum": ["scalp", "pending", "swing"],
                                "description": "Optional: Filter by trade type"
                            },
                            "days_back": {
                                "type": "integer",
                                "description": "Days to look back (default 30)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_news_status",
                    "description": "Check if currently in news blackout window. Returns blackout status and upcoming high-impact events (NFP, CPI, Fed).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["macro", "crypto", "both"],
                                "description": "Event category (default: both)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_news_events",
                    "description": "Get list of upcoming economic news events with impact levels and timing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["macro", "crypto"],
                                "description": "Filter by category"
                            },
                            "impact": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "ultra"],
                                "description": "Minimum impact level"
                            },
                            "hours_ahead": {
                                "type": "integer",
                                "description": "Hours ahead to check (default 24)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_intelligent_exits",
                    "description": "Get AI-powered exit strategy recommendations for a symbol (trailing stops, partial profits, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_intelligent_exits_status",
                    "description": "Get status of all active intelligent exit rules. Returns list of positions with intelligent exits enabled, showing which actions have triggered (breakeven, partial profit, trailing stops). CRITICAL: Use this when user asks 'assess my trade' or 'how's my position' to check if protection is active.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_sentiment",
                    "description": "Get current market sentiment including Fear & Greed Index and trading implications.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "moneybot.add_alert",
                    "description": "Create a custom alert for any trading symbol based on analysis recommendations. Use when user wants to be notified of specific price levels, structure patterns, or market conditions.",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol", "alert_type", "condition", "description"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., BTCUSD, XAUUSD, EURUSD)",
                                "example": "XAUUSD"
                            },
                            "alert_type": {
                                "type": "string",
                                "enum": ["price", "structure", "indicator", "volatility"],
                                "description": "Type of alert to create",
                                "example": "price"
                            },
                            "condition": {
                                "type": "string",
                                "enum": ["crosses_above", "crosses_below", "greater_than", "less_than", "detected", "exceeds", "drops_below"],
                                "description": "Condition that triggers the alert",
                                "example": "crosses_below"
                            },
                            "description": {
                                "type": "string",
                                "description": "Human-readable description of the alert",
                                "example": "XAUUSD reaches 3900 sell zone for scalp entry"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Alert-specific parameters (e.g., price_level for price alerts, pattern for structure alerts)",
                                "example": {"price_level": 3900}
                            },
                            "expires_hours": {
                                "type": "integer",
                                "description": "Optional expiry in hours (default: 24)",
                                "example": 24
                            },
                            "one_time": {
                                "type": "boolean",
                                "description": "Auto-remove after first trigger (default: true)",
                                "example": true
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_unified_news_analysis",
                    "description": "Get comprehensive news analysis combining economic calendar, breaking news, and market sentiment. Use for complete market context before trading decisions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["macro", "crypto"],
                                "description": "News category to analyze (default: macro)",
                                "example": "macro"
                            },
                            "hours_ahead": {
                                "type": "integer",
                                "description": "Hours ahead to look for upcoming events (default: 24)",
                                "example": 24
                            },
                            "hours_back": {
                                "type": "integer",
                                "description": "Hours back to include breaking news (default: 24)",
                                "example": 24
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_breaking_news_summary",
                    "description": "Get summary of recent breaking news for quick market context. Use when user asks about recent news or market developments.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hours_back": {
                                "type": "integer",
                                "description": "Hours back to include breaking news (default: 24)",
                                "example": 24
                            }
                        },
                        "required": []
                    }
                }
            }
        ]
        
        # Only add execute_trade, modify_position, modify_pending_order, and execute_bracket_trade tools if NOT planning
        if not is_planning:
            tools.append({
                "type": "function",
                "function": {
                    "name": "execute_trade",
                    "description": "REQUIRED: Execute a trade in MT5. You MUST call this when user says 'execute', 'place', 'enter', 'go ahead', 'do it', 'proceed'. DO NOT just say you're executing - CALL THIS FUNCTION. If you tell the user you're executing a trade, you MUST call this function first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["buy", "sell"],
                                "description": "Trade direction: buy or sell"
                            },
                            "entry_price": {
                                "type": "number",
                                "description": "Entry price for the trade"
                            },
                            "stop_loss": {
                                "type": "number",
                                "description": "Stop loss price"
                            },
                            "take_profit": {
                                "type": "number",
                                "description": "Take profit price"
                            },
                            "order_type": {
                                "type": "string",
                                "enum": ["market", "buy_limit", "sell_limit", "buy_stop", "sell_stop"],
                                "description": "Order type: market (immediate), buy_limit (below price), sell_limit (above price), buy_stop (above price), sell_stop (below price)"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reason for the trade"
                            }
                        },
                        "required": ["symbol", "direction", "entry_price", "stop_loss", "take_profit"]
                    }
                }
            })
            
            tools.append({
                "type": "function",
                "function": {
                    "name": "modify_position",
                    "description": "CRITICAL: Modify an EXISTING position's stop loss and/or take profit. Use this when user says 'adjust', 'tighten', 'move stop', 'change TP', 'lock in profit', 'move to breakeven'. DO NOT use execute_trade for modifications - that creates a NEW trade!",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket": {
                                "type": "integer",
                                "description": "MT5 position ticket number (get from get_account_balance)"
                            },
                            "stop_loss": {
                                "type": "number",
                                "description": "New stop loss level (optional)"
                            },
                            "take_profit": {
                                "type": "number",
                                "description": "New take profit level (optional)"
                            },
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol for validation (optional)"
                            }
                        },
                        "required": ["ticket"]
                    }
                }
            })
            
            tools.append({
                "type": "function",
                "function": {
                    "name": "modify_pending_order",
                    "description": "CRITICAL: Modify an EXISTING pending order's entry price, stop loss, and/or take profit. Use this when user says 'adjust my pending order', 'update my limit order', 're-analyze my orders', 'move my entry', 'adjust my bracket'. First call get_pending_orders to see all orders, then modify as needed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket": {
                                "type": "integer",
                                "description": "MT5 order ticket number (get from get_pending_orders)"
                            },
                            "price": {
                                "type": "number",
                                "description": "New entry price level (optional)"
                            },
                            "stop_loss": {
                                "type": "number",
                                "description": "New stop loss level (optional)"
                            },
                            "take_profit": {
                                "type": "number",
                                "description": "New take profit level (optional)"
                            }
                        },
                        "required": ["ticket"]
                    }
                }
            })
            
            tools.append({
                "type": "function",
                "function": {
                    "name": "execute_bracket_trade",
                    "description": "Execute OCO bracket trade (range breakout). Places BUY and SELL pending orders; when one fills, the other cancels automatically within 3 seconds. Use for consolidation ranges, news events, triangle breakouts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            },
                            "buy_entry": {
                                "type": "number",
                                "description": "BUY entry price (above range)"
                            },
                            "buy_sl": {
                                "type": "number",
                                "description": "BUY stop loss (below buy_entry)"
                            },
                            "buy_tp": {
                                "type": "number",
                                "description": "BUY take profit (above buy_entry)"
                            },
                            "sell_entry": {
                                "type": "number",
                                "description": "SELL entry price (below range)"
                            },
                            "sell_sl": {
                                "type": "number",
                                "description": "SELL stop loss (above sell_entry)"
                            },
                            "sell_tp": {
                                "type": "number",
                                "description": "SELL take profit (below sell_entry)"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reason for bracket trade"
                            }
                        },
                        "required": ["symbol", "buy_entry", "buy_sl", "buy_tp", "sell_entry", "sell_sl", "sell_tp"]
                    }
                }
            })
        
        # Call OpenAI API with tools
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"ChatGPT API error: {response.status_code} - {error_text}")
            await update.message.reply_text(
                f"⚠️ ChatGPT API error: {response.status_code}\n{error_text[:200]}"
            )
            return CHATTING
        
        # Extract response
        result = response.json()
        assistant_msg = result["choices"][0]["message"]
        
        # Log the full response for debugging
        logger.info(f"ChatGPT response: {json.dumps(assistant_msg, indent=2)}")
        
        # Check if ChatGPT wants to call a function
        tool_calls = assistant_msg.get("tool_calls")
        
        if tool_calls:
            logger.info(f"✅ ChatGPT is calling {len(tool_calls)} function(s)")
        else:
            logger.info("ℹ️ ChatGPT returned text response (no function calls)")
        
        if tool_calls:
            # ChatGPT wants to call a function - execute it
            await update.message.reply_text("🔄 Fetching data...")
            
            # Add assistant's tool call message ONCE before processing
            messages.append(assistant_msg)
            
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                logger.info(f"ChatGPT calling function: {function_name} with args: {function_args}")
                
                # Execute the function
                if function_name == "get_market_data":
                    symbol = function_args.get("symbol", "XAUUSD")
                    await update.message.reply_text(f"📊 Getting {symbol} market data...")
                    function_result = await execute_get_market_data(symbol)
                elif function_name == "get_account_balance":
                    await update.message.reply_text("💰 Getting account balance...")
                    function_result = await execute_get_account_balance()
                elif function_name == "get_economic_indicator":
                    indicator = function_args.get("indicator", "GDP")
                    await update.message.reply_text(f"📊 Fetching {indicator} data...")
                    function_result = await execute_get_economic_indicator(indicator)
                elif function_name == "get_news_sentiment":
                    await update.message.reply_text("📰 Analyzing news sentiment...")
                    tickers = function_args.get("tickers", None)
                    function_result = await execute_get_news_sentiment(tickers)
                elif function_name == "get_market_indices":
                    await update.message.reply_text("📊 Fetching DXY & VIX from Yahoo Finance...")
                    function_result = await execute_get_market_indices()
                elif function_name == "execute_trade":
                    await update.message.reply_text("🔄 Executing trade...")
                    function_result = await execute_trade(
                        symbol=function_args.get("symbol"),
                        direction=function_args.get("direction"),
                        entry_price=function_args.get("entry_price"),
                        stop_loss=function_args.get("stop_loss"),
                        take_profit=function_args.get("take_profit"),
                        order_type=function_args.get("order_type", "market"),
                        reasoning=function_args.get("reasoning", "ChatGPT trade")
                    )
                    
                    # Log recommendation for tracking
                    if function_result.get("ok"):
                        try:
                            symbol = function_args.get("symbol", "").upper()
                            direction = function_args.get("direction", "").upper()
                            entry = function_args.get("entry_price", 0)
                            sl = function_args.get("stop_loss", 0)
                            tp = function_args.get("take_profit", 0)
                            order_type = function_args.get("order_type", "market")
                            
                            # Determine trade type
                            trade_type = "SCALP" if order_type == "market" else "PENDING"
                            
                            # Calculate R:R
                            risk = abs(entry - sl) if entry and sl else 0
                            reward = abs(tp - entry) if entry and tp else 0
                            risk_reward = reward / risk if risk > 0 else 0
                            
                            # Get ticket from result
                            ticket = function_result.get("ticket") or function_result.get("order_id")
                            
                            # Log recommendation
                            rec_id = recommendation_tracker.log_recommendation(
                                symbol=symbol,
                                trade_type=trade_type,
                                direction=direction,
                                entry_price=entry,
                                stop_loss=sl,
                                take_profit=tp,
                                confidence=function_result.get("confidence", 70),
                                reasoning=function_args.get("reasoning", "ChatGPT trade"),
                                order_type=order_type,
                                timeframe="M5"  # Default to M5 for execution
                            )
                            
                            # Mark as executed with MT5 ticket
                            if ticket:
                                recommendation_tracker.mark_executed(
                                    recommendation_id=rec_id,
                                    mt5_ticket=ticket
                                )
                            
                            logger.info(f"Logged recommendation #{rec_id} for {symbol} {direction} (ticket: {ticket})")
                        except Exception as e:
                            logger.error(f"Failed to log recommendation: {e}", exc_info=True)
                elif function_name == "modify_position":
                    await update.message.reply_text("🔧 Modifying position...")
                    function_result = await modify_position(
                        ticket=function_args.get("ticket"),
                        stop_loss=function_args.get("stop_loss"),
                        take_profit=function_args.get("take_profit"),
                        symbol=function_args.get("symbol")
                    )
                
                elif function_name == "get_pending_orders":
                    await update.message.reply_text("📋 Fetching pending orders...")
                    function_result = await get_pending_orders()
                
                elif function_name == "modify_pending_order":
                    await update.message.reply_text("🔧 Modifying pending order...")
                    function_result = await modify_pending_order(
                        ticket=function_args.get("ticket"),
                        price=function_args.get("price"),
                        stop_loss=function_args.get("stop_loss"),
                        take_profit=function_args.get("take_profit")
                    )
                
                elif function_name == "execute_bracket_trade":
                    await update.message.reply_text("📊 Executing bracket trade...")
                    function_result = await execute_bracket_trade(
                        symbol=function_args.get("symbol"),
                        buy_entry=function_args.get("buy_entry"),
                        buy_sl=function_args.get("buy_sl"),
                        buy_tp=function_args.get("buy_tp"),
                        sell_entry=function_args.get("sell_entry"),
                        sell_sl=function_args.get("sell_sl"),
                        sell_tp=function_args.get("sell_tp"),
                        reasoning=function_args.get("reasoning", "Bracket trade")
                    )
                
                elif function_name == "get_multi_timeframe_analysis":
                    symbol = function_args.get("symbol", "XAUUSD")
                    await update.message.reply_text(f"📊 Analyzing {symbol} multi-timeframe...")
                    function_result = await get_multi_timeframe_analysis(symbol)
                
                elif function_name == "get_confluence_score":
                    symbol = function_args.get("symbol", "XAUUSD")
                    await update.message.reply_text(f"📊 Calculating {symbol} confluence score...")
                    function_result = await get_confluence_score(symbol)
                
                elif function_name == "get_session_analysis":
                    await update.message.reply_text("🕐 Analyzing current trading session...")
                    function_result = await get_session_analysis()
                
                elif function_name == "get_recommendation_stats":
                    await update.message.reply_text("📊 Fetching historical performance...")
                    function_result = await get_recommendation_stats(
                        symbol=function_args.get("symbol"),
                        trade_type=function_args.get("trade_type"),
                        days_back=function_args.get("days_back", 30)
                    )
                
                elif function_name == "get_news_status":
                    await update.message.reply_text("📰 Checking news blackout status...")
                    function_result = await get_news_status(
                        category=function_args.get("category", "both")
                    )
                
                elif function_name == "get_news_events":
                    await update.message.reply_text("📰 Fetching upcoming news events...")
                    function_result = await get_news_events(
                        category=function_args.get("category"),
                        impact=function_args.get("impact"),
                        hours_ahead=function_args.get("hours_ahead", 24)
                    )
                
                elif function_name == "get_intelligent_exits":
                    symbol = function_args.get("symbol", "XAUUSD")
                    await update.message.reply_text(f"🎯 Analyzing {symbol} exit strategies...")
                    function_result = await get_intelligent_exits(symbol)
                
                elif function_name == "get_intelligent_exits_status":
                    await update.message.reply_text("🔍 Checking intelligent exit status...")
                    function_result = await get_intelligent_exits_status()
                
                elif function_name == "get_market_sentiment":
                    await update.message.reply_text("💭 Analyzing market sentiment...")
                    function_result = await get_market_sentiment()
                
                elif function_name == "moneybot.add_alert":
                    await update.message.reply_text("🔔 Creating alert...")
                    function_result = await add_alert(function_args)
                
                elif function_name == "get_unified_news_analysis":
                    await update.message.reply_text("📰 Analyzing comprehensive news...")
                    function_result = await get_unified_news_analysis(function_args)
                
                elif function_name == "get_breaking_news_summary":
                    await update.message.reply_text("📰 Getting breaking news...")
                    function_result = await get_breaking_news_summary(function_args)
                
                else:
                    function_result = {"error": "Unknown function"}
                
                logger.info(f"Function result: {json.dumps(function_result, indent=2)}")
                
                # Add the function result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(function_result)
                })
            
            # Call ChatGPT again with the function results
            await update.message.reply_text("🤖 Processing results...")
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response2 = await client.post(
                        api_url,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 500
                        }
                    )
                
                if response2.status_code == 200:
                    result2 = response2.json()
                    assistant_message = result2["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Second API call failed: {response2.status_code} - {response2.text}")
                    assistant_message = f"⚠️ Error processing function results: {response2.status_code}"
            except Exception as e2:
                logger.error(f"Second API call exception: {e2}", exc_info=True)
                assistant_message = f"⚠️ Error: {str(e2)}"
        else:
            # Normal text response
            assistant_message = assistant_msg.get("content", "No response")
        
        # Add assistant response to history
        user_conversations[user_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Log assistant message to database
        if chatgpt_logger:
            try:
                conv_id = user_conversations[user_id].get("conversation_id")
                if conv_id:
                    # Count tokens (rough estimate)
                    tokens_used = len(assistant_message.split()) * 1.3
                    chatgpt_logger.log_message(conv_id, "assistant", assistant_message, int(tokens_used))
            except Exception as e:
                logger.error(f"Failed to log assistant message: {e}")
        
        # Send response to user (without Markdown to avoid parsing errors)
        await update.message.reply_text(
            f"🤖 ChatGPT:\n\n{assistant_message}"
        )
        
    except Exception as e:
        logger.error(f"ChatGPT bridge error: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Error communicating with ChatGPT: {str(e)}"
        )
    
    return CHATTING


async def chatgpt_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick action buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    action = query.data
    
    # Pre-filled prompts for common actions
    prompts = {
        "gpt_analyze_xauusd": "Analyze the current XAUUSD (Gold) market with DXY, US10Y, and VIX context. Give me a technical breakdown with 3-signal confluence.",
        "gpt_analyze_btcusd": "Analyze the current BTCUSD market and give me a technical breakdown with entry opportunities.",
        "gpt_analyze_eurusd": "Analyze the current EURUSD market with DXY correlation. Give me a technical breakdown.",
        "gpt_analyze_gbpusd": "Analyze the current GBPUSD market with DXY correlation. Give me a technical breakdown.",
        "gpt_analyze_usdjpy": "Analyze the current USDJPY market with DXY correlation. Give me a technical breakdown.",
        "gpt_analyze_other": "What symbol would you like me to analyze? (e.g., AUDCAD, NZDUSD, EURJPY, etc.)",
        "gpt_balance": "What's my current MT5 account balance and equity?",
        "gpt_recommend": "Give me your top trade recommendation right now across all major symbols (Gold, BTC, EUR, GBP, JPY) with entry, SL, and TP.",
        "gpt_trade": "Show me my open positions and pending orders. Then suggest what I should do next.",
        "gpt_end": None
    }
    
    if action == "gpt_end":
        return await chatgpt_end(update, context)
    
    prompt = prompts.get(action)
    if not prompt:
        return CHATTING
    
    # Check if conversation exists
    if user_id not in user_conversations:
        await query.message.reply_text(
            "⚠️ No active ChatGPT session. Use /chatgpt to start."
        )
        return ConversationHandler.END
    
    # Show what user "said"
    await query.message.reply_text(f"📝 You: {prompt}")
    
    # Add user message to history
    user_conversations[user_id]["messages"].append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat()
    })
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Pre-fetch data if needed
        context_data = ""
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ["analyze", "analysis", "price", "market", "xauusd", "btcusd", "eurusd", "gbpusd", "usdjpy", "recommend", "trade", "setup"]):
            # Button clicks are explicit analysis requests - use full analysis
            is_full_analysis_request = any(word in prompt_lower for word in ["analyze", "analysis"])
            
            try:
                # Detect symbol from prompt or action
                symbol = "XAUUSD"  # default
                if "btc" in prompt_lower or "btcusd" in action:
                    symbol = "BTCUSD"
                elif "eur" in prompt_lower or "eurusd" in action:
                    symbol = "EURUSD"
                elif "gbp" in prompt_lower or "gbpusd" in action:
                    symbol = "GBPUSD"
                elif "jpy" in prompt_lower or "usdjpy" in action:
                    symbol = "USDJPY"
                elif "xau" in prompt_lower or "gold" in prompt_lower or "xauusd" in action:
                    symbol = "XAUUSD"
                
                if is_full_analysis_request:
                    # Use full unified analysis for button clicks (explicit analysis requests)
                    await query.message.reply_text("📊 Fetching full unified analysis with all features...")
                    analysis_data = await execute_get_full_analysis(symbol)
                    
                    from datetime import datetime
                    data_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    
                    full_summary = analysis_data.get("full_analysis_summary", "")
                    if full_summary:
                        context_data = (
                            f"\n\n[FULL UNIFIED ANALYSIS FOR {symbol}]\n"
                            f"📅 Analysis as of: {data_timestamp}\n\n"
                            f"{full_summary}\n\n"
                            f"[END FULL ANALYSIS]\n\n"
                            f"CRITICAL: This analysis includes all advanced features:\n"
                            f"- Stop cluster detection\n"
                            f"- Fed expectations tracking\n"
                            f"- Volatility forecasting\n"
                            f"- Order flow signals\n"
                            f"- Enhanced macro bias\n\n"
                            f"Use this complete analysis to provide comprehensive market insights."
                        )
                    else:
                        market_data = analysis_data
                        context_data = _build_context_from_market_data(market_data, symbol, data_timestamp)
                else:
                    # Use regular market data for other requests
                    await query.message.reply_text("📊 Fetching current market data...")
                    market_data = await execute_get_market_data(symbol)
                    
                    from datetime import datetime
                    data_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    
                    context_data = _build_context_from_market_data(market_data, symbol, data_timestamp)
                
                # Append context to the last message
                user_conversations[user_id]["messages"][-1]["content"] += context_data
                
            except Exception as e:
                logger.error(f"Error pre-fetching market data: {e}", exc_info=True)
        
        if "balance" in prompt_lower or "account" in prompt_lower:
            # Fetch account data
            try:
                await query.message.reply_text("💰 Fetching account info...")
                account_data = await execute_get_account_balance()
                
                context_data += (
                    f"\n\n[CURRENT ACCOUNT INFO]\n"
                    f"Balance: ${account_data.get('balance', 0):.2f}\n"
                    f"Equity: ${account_data.get('equity', 0):.2f}\n"
                    f"Free Margin: ${account_data.get('free_margin', 0):.2f}\n"
                    f"Currency: {account_data.get('currency', 'USD')}\n"
                    f"[END ACCOUNT INFO]\n"
                )
                
                # Append context to the last message
                user_conversations[user_id]["messages"][-1]["content"] += context_data
                
            except Exception as e:
                logger.error(f"Error pre-fetching account data: {e}", exc_info=True)
        
        # Get ChatGPT API settings
        api_url = context.bot_data.get("chatgpt_api_url", "https://api.openai.com/v1/chat/completions")
        api_key = context.bot_data.get("openai_api_key")
        
        if not api_key:
            await query.message.reply_text(
                "⚠️ OpenAI API key not configured. Set it with /setgptkey <your-key>"
            )
            return CHATTING
        
        # Build conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional forex trading assistant integrated with MT5. "
                    "You have access to:\n"
                    "- Real-time market data via /api/v1/price/{symbol}\n"
                    "- Account information via /api/v1/account\n"
                    "- Trade execution via /mt5/execute or /mt5/execute_bracket\n"
                    "- OCO bracket trades for range-bound strategies\n"
                    "- Technical analysis via /ai/analysis/{symbol}\n\n"
                    "When users ask for trades, ALWAYS:\n"
                    "1. Clearly state if it's a 🟢 BUY or 🔴 SELL\n"
                    "2. Provide specific entry, SL, and TP with emojis\n"
                    "3. Ask for confirmation before executing\n\n"
                    "Format: 🟢 **BUY** or 🔴 **SELL** | 📊 Entry | 🛑 SL | 🎯 TP\n"
                    "Be concise and professional."
                )
            }
        ]
        
        # Add conversation history (last 10 messages)
        for msg in user_conversations[user_id]["messages"][-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Call OpenAI API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"ChatGPT API error: {response.status_code} - {error_text}")
            await query.message.reply_text(
                f"⚠️ ChatGPT API error: {response.status_code}\n{error_text[:200]}"
            )
            return CHATTING
        
        # Extract response
        result = response.json()
        assistant_message = result["choices"][0]["message"]["content"]
        
        # Add assistant response to history
        user_conversations[user_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send response to user (without Markdown to avoid parsing errors)
        await query.message.reply_text(
            f"🤖 ChatGPT:\n\n{assistant_message}"
        )
        
    except Exception as e:
        logger.error(f"ChatGPT button error: {e}", exc_info=True)
        await query.message.reply_text(
            f"⚠️ Error: {str(e)}"
        )
    
    return CHATTING


async def chatgpt_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End ChatGPT conversation"""
    user_id = update.effective_user.id
    
    if user_id in user_conversations:
        msg_count = len(user_conversations[user_id]["messages"])
        conv_id = user_conversations[user_id].get("conversation_id")
        
        # Log conversation end to database
        if chatgpt_logger and conv_id:
            try:
                chatgpt_logger.end_conversation(conv_id)
                logger.info(f"✅ Conversation {conv_id} ended for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to log conversation end: {e}")
        
        # Log analytics event
        if analytics_logger:
            try:
                chat_id = user_conversations[user_id].get("chat_id", update.effective_chat.id)
                analytics_logger.log_action(user_id, chat_id, "chatgpt_end", {"message_count": msg_count})
            except Exception as e:
                logger.error(f"Failed to log analytics: {e}")
        
        del user_conversations[user_id]
        
        text = (
            "👋 ChatGPT conversation ended.\n\n"
            f"Messages exchanged: {msg_count}\n"
            "Use /chatgpt to start a new conversation."
        )
    else:
        text = "No active ChatGPT session."
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text)
    else:
        await update.message.reply_text(text)
    
    return ConversationHandler.END


async def chatgpt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ChatGPT conversation"""
    return await chatgpt_end(update, context)


async def set_gpt_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set OpenAI API key"""
    if not context.args:
        await update.message.reply_text(
            "Usage: /setgptkey <your-openai-api-key>\n\n"
            "⚠️ Your key will be stored in memory only (not saved to disk).\n\n"
            "Get your key at: https://platform.openai.com/api-keys"
        )
        return
    
    api_key = context.args[0]
    context.bot_data["openai_api_key"] = api_key
    
    # Test the key
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            test_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Test"}],
                    "max_tokens": 5
                }
            )
            
            if test_response.status_code == 200:
                await update.message.reply_text(
                    "✅ OpenAI API key set and verified!\n\n"
                    "You can now use /chatgpt to start a conversation."
                )
            elif test_response.status_code == 401:
                await update.message.reply_text(
                    "❌ Invalid API key!\n\n"
                    "Please check your key and try again.\n"
                    "Get your key at: https://platform.openai.com/api-keys"
                )
            else:
                await update.message.reply_text(
                    f"⚠️ API key set, but verification returned: {test_response.status_code}\n\n"
                    "You can try /chatgpt anyway."
                )
    except Exception as e:
        logger.error(f"API key test failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ API key set, but test failed: {str(e)[:100]}\n\n"
            "You can try /chatgpt anyway."
        )


async def check_gpt_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check ChatGPT bridge status"""
    api_key = context.bot_data.get("openai_api_key")
    
    if api_key:
        masked_key = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
        status = f"✅ API key set: {masked_key}"
    else:
        status = "❌ No API key set. Use /setgptkey"
    
    active_convs = len(user_conversations)
    
    await update.message.reply_text(
        f"🤖 ChatGPT Bridge Status\n\n"
        f"{status}\n"
        f"Active conversations: {active_convs}\n\n"
        f"Model: gpt-4o-mini\n"
        f"Timeout: 30s\n"
        f"Max tokens: 500"
    )


async def test_chatgpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test if ChatGPT bridge is working"""
    await update.message.reply_text(
        "✅ ChatGPT bridge is loaded!\n\n"
        "Commands:\n"
        "• /chatgpt - Start conversation\n"
        "• /setgptkey <key> - Set API key\n"
        "• /gptstatus - Check status\n"
        "• /testchatgpt - This command"
    )


def register_chatgpt_handlers(application):
    """Register all ChatGPT bridge handlers"""
    
    try:
        # Simple test command first
        application.add_handler(CommandHandler("testchatgpt", test_chatgpt))
        logger.info("ChatGPT test command registered")
        
        # Conversation handler for ChatGPT
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("chatgpt", chatgpt_start)],
            states={
                CHATTING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, chatgpt_message),
                    CallbackQueryHandler(chatgpt_button, pattern="^gpt_"),
                ],
            },
            fallbacks=[
                CommandHandler("endgpt", chatgpt_cancel),
                CallbackQueryHandler(chatgpt_end, pattern="^gpt_end$")
            ],
            name="chatgpt_conversation",
            persistent=False
        )
        
        application.add_handler(conv_handler)
        logger.info("ChatGPT conversation handler registered")
        
        application.add_handler(CommandHandler("setgptkey", set_gpt_key))
        application.add_handler(CommandHandler("gptstatus", check_gpt_status))
        
        logger.info("ChatGPT bridge handlers registered successfully")
        
    except Exception as e:
        logger.error(f"Failed to register ChatGPT handlers: {e}", exc_info=True)
        raise


async def setgptkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set OpenAI API key"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /setgptkey <your-openai-api-key>\n\n"
            "Example:\n"
            "/setgptkey sk-proj-abc123...\n\n"
            "Get your API key from: https://platform.openai.com/api-keys"
        )
        return
    
    # Get the key
    api_key = context.args[0]
    
    # Validate format (basic check)
    if not api_key.startswith('sk-'):
        await update.message.reply_text(
            "⚠️ Invalid API key format. OpenAI keys start with 'sk-'\n"
            "Get your key from: https://platform.openai.com/api-keys"
        )
        return
    
    # Store in bot_data (shared across all users)
    context.bot_data["openai_api_key"] = api_key
    
    logger.info(f"OpenAI API key updated by user {update.effective_user.id}")
    
    await update.message.reply_text(
        "✅ OpenAI API key saved successfully!\n\n"
        "You can now use /chatgpt to start conversations.\n"
        "The key is stored in memory and will be cleared on bot restart.\n\n"
        "💡 Tip: Add OPENAI_API_KEY to your .env file for permanent storage."
    )

