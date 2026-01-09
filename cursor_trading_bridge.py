"""
Cursor Trading Bridge
Simple bridge for Cursor AI agent to access trading bot tools directly.
This allows Cursor to analyze markets and provide trade recommendations like ChatGPT.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CursorTradingBridge:
    """
    Bridge between Cursor AI agent and trading bot tools.
    
    Provides simplified interface to desktop_agent.py tool registry.
    """
    
    def __init__(self):
        """Initialize the bridge - imports desktop_agent registry"""
        try:
            from desktop_agent import registry
            self.registry = registry
            self.available = True
            logger.info("Cursor Trading Bridge initialized - desktop_agent available")
        except ImportError as e:
            logger.warning(f"desktop_agent not available: {e}")
            self.registry = None
            self.available = False
    
    async def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze a trading symbol - returns full market analysis.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD", "XAUUSD")
        
        Returns:
            Dict with analysis data, recommendation, entry/SL/TP
        """
        if not self.available:
            return {
                "error": "Trading bot not available",
                "message": "desktop_agent.py must be running"
            }
        
        try:
            result = await self.registry.execute(
                "moneybot.analyse_symbol_full",
                {"symbol": symbol}
            )
            return result
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_trade_recommendation(self, symbol: str) -> Dict[str, Any]:
        """
        Get a trade recommendation for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Dict with direction, entry, SL, TP, reasoning
        """
        analysis = await self.analyze_symbol(symbol)
        
        if "error" in analysis:
            return analysis
        
        # Extract recommendation from analysis
        data = analysis.get("data", {})
        recommendation = data.get("recommendation", {})
        
        return {
            "symbol": symbol,
            "direction": recommendation.get("direction"),
            "entry": recommendation.get("entry"),
            "stop_loss": recommendation.get("stop_loss"),
            "take_profit": recommendation.get("take_profit"),
            "reasoning": recommendation.get("reasoning"),
            "confidence": recommendation.get("confidence"),
            "full_analysis": analysis  # Include full analysis for context
        }
    
    async def get_current_price(self, symbol: str) -> Dict[str, Any]:
        """Get current price for a symbol"""
        if not self.available:
            return {"error": "Trading bot not available"}
        
        try:
            result = await self.registry.execute(
                "moneybot.getCurrentPrice",
                {"symbol": symbol}
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_trade(self, symbol: str, direction: str, 
                           entry_price: float, stop_loss: float, 
                           take_profit: float, order_type: str = "market") -> Dict[str, Any]:
        """
        Execute a trade.
        
        Args:
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            order_type: "market", "buy_limit", "sell_limit", etc.
        
        Returns:
            Dict with execution result
        """
        if not self.available:
            return {"error": "Trading bot not available"}
        
        try:
            result = await self.registry.execute(
                "moneybot.execute_trade",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "order_type": order_type,
                    "reasoning": f"Cursor agent trade recommendation"
                }
            )
            return result
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def analyze_and_recommend(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze symbol and return formatted recommendation.
        This is what Cursor agent will use most often.
        
        Returns:
            Formatted dict ready for display to user
        """
        analysis = await self.analyze_symbol(symbol)
        
        if "error" in analysis:
            return analysis
        
        data = analysis.get("data", {})
        recommendation = data.get("recommendation", {})
        
        # Format for easy display
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "current_price": data.get("current_price"),
            "market_regime": data.get("market_regime"),
            "recommendation": {
                "direction": recommendation.get("direction"),
                "entry": recommendation.get("entry"),
                "stop_loss": recommendation.get("stop_loss"),
                "take_profit": recommendation.get("take_profit"),
                "risk_reward": recommendation.get("risk_reward"),
                "confidence": recommendation.get("confidence"),
                "reasoning": recommendation.get("reasoning")
            },
            "summary": analysis.get("summary", ""),
            "full_data": data  # Keep full data for detailed analysis
        }
    
    async def get_recent_trades(self, days_back: int = 1) -> Dict[str, Any]:
        """Get recent closed trades"""
        if not self.available:
            return {"error": "Trading bot not available"}
        
        try:
            result = await self.registry.execute(
                "moneybot.getRecentTrades",
                {"days_back": days_back, "by_execution_date": False}
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def create_auto_plan(self, symbol: str, direction: str,
                               entry: float, sl: float, tp: float,
                               conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Create an auto-execution plan"""
        if not self.available:
            return {"error": "Trading bot not available"}
        
        try:
            result = await self.registry.execute(
                "moneybot.create_auto_trade_plan",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "conditions": conditions,
                    "volume": 0.01,
                    "notes": "Created by Cursor agent"
                }
            )
            return result
        except Exception as e:
            return {"error": str(e)}


# Global instance
_bridge = None

def get_bridge() -> CursorTradingBridge:
    """Get or create the global bridge instance"""
    global _bridge
    if _bridge is None:
        _bridge = CursorTradingBridge()
    return _bridge


# Convenience functions for direct use
async def analyze(symbol: str) -> Dict[str, Any]:
    """Quick analyze function"""
    bridge = get_bridge()
    return await bridge.analyze_symbol(symbol)

async def recommend(symbol: str) -> Dict[str, Any]:
    """Quick recommendation function"""
    bridge = get_bridge()
    return await bridge.analyze_and_recommend(symbol)

async def execute(symbol: str, direction: str, entry: float, 
                 sl: float, tp: float) -> Dict[str, Any]:
    """Quick execute function"""
    bridge = get_bridge()
    return await bridge.execute_trade(symbol, direction, entry, sl, tp)
