"""
GPT-4o Reasoner - Fast Preliminary Trade Analysis

Purpose: Quick 2-5 second AI validation of trade setups.
Uses GPT-4o (cheap, fast) for preliminary screening.

Decision Flow:
- STRONG → Pass to GPT-5 validator
- WEAK → Reject immediately
- NEUTRAL → Log as observation, no action

Cost: ~$0.01 per analysis
"""

import logging
import json
from typing import Dict, Optional, Any
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)


class GPT4oReasoner:
    """
    Fast AI reasoner using GPT-4o for preliminary trade validation.
    
    Analyzes:
    - MT5 technical setup
    - Binance real-time data
    - Order flow signals
    - V8 indicators
    
    Returns:
    - Signal strength (STRONG/WEAK/NEUTRAL)
    - Confidence (0-100%)
    - Reasoning
    - Risk warnings
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize GPT-4o reasoner.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Fast and cheap
        
        logger.info(f"🤖 GPT-4o Reasoner initialized (model: {self.model})")
    
    async def analyze_setup(
        self,
        symbol: str,
        mt5_analysis: Dict,
        binance_enrichment: Dict,
        order_flow: Optional[Dict] = None,
        advanced_features: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze trade setup with GPT-4o.
        
        Args:
            symbol: Trading symbol
            mt5_analysis: MT5 technical analysis result
            binance_enrichment: Real-time Binance data
            order_flow: Order flow signals (optional)
            advanced_features: V8 indicator features (optional)
        
        Returns:
            {
                "signal": "STRONG" | "WEAK" | "NEUTRAL",
                "confidence": 0-100,
                "reasoning": "...",
                "should_validate": bool,  # Pass to GPT-5?
                "warnings": [...],
                "summary": "..."
            }
        """
        try:
            # Build analysis prompt
            prompt = self._build_prompt(
                symbol, mt5_analysis, binance_enrichment, 
                order_flow, advanced_features
            )
            
            logger.info(f"🤖 GPT-4o analyzing {symbol}...")
            
            # Call GPT-4o
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower = more consistent
                max_tokens=500,   # Keep it fast
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result["model"] = self.model
            result["tokens_used"] = response.usage.total_tokens
            result["cost_usd"] = self._estimate_cost(response.usage.total_tokens)
            
            # Determine if should pass to GPT-5
            result["should_validate"] = (
                result.get("signal") == "STRONG" and 
                result.get("confidence", 0) >= 70
            )
            
            logger.info(
                f"✅ GPT-4o: {symbol} → {result['signal']} "
                f"({result['confidence']}%) "
                f"[{result['tokens_used']} tokens, ${result['cost_usd']:.4f}]"
            )
            
            if result.get("warnings"):
                for warning in result["warnings"]:
                    logger.warning(f"   ⚠️ {warning}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ GPT-4o analysis failed for {symbol}: {e}", exc_info=True)
            return {
                "signal": "NEUTRAL",
                "confidence": 0,
                "reasoning": f"Analysis failed: {str(e)}",
                "should_validate": False,
                "warnings": ["GPT-4o analysis error"],
                "summary": "Analysis unavailable",
                "error": str(e)
            }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for GPT-4o reasoner"""
        return """You are an expert forex/crypto trading analyst specializing in scalp and day trading.

Your role: Fast preliminary analysis of trade setups (2-5 seconds).

Analyze the provided data and return a JSON response with:
{
    "signal": "STRONG" | "WEAK" | "NEUTRAL",
    "confidence": 0-100,
    "reasoning": "Brief explanation (2-3 sentences)",
    "warnings": ["list of risk warnings"],
    "summary": "One sentence verdict"
}

Decision criteria:
- STRONG: Multiple confluences, clean setup, good risk/reward → Send to deep validator
- WEAK: Conflicting signals, poor setup, high risk → Reject immediately  
- NEUTRAL: Insufficient data or unclear conditions → Wait

Focus on:
1. Multi-timeframe alignment (H4, H1, M15, M5)
2. Binance real-time momentum confirmation
3. Order flow alignment (if provided)
4. V8 indicator warnings (especially RMAG >2σ)
5. Risk factors (liquidity voids, fake breakouts, etc.)

Be conservative - when in doubt, mark as WEAK or NEUTRAL.
Only STRONG setups with 70%+ confidence should be validated further."""

    def _build_prompt(
        self,
        symbol: str,
        mt5_analysis: Dict,
        binance_enrichment: Dict,
        order_flow: Optional[Dict],
        advanced_features: Optional[Dict]
    ) -> str:
        """Build analysis prompt from trade data"""
        
        prompt_parts = [f"# Trade Setup Analysis: {symbol}\n"]
        
        # MT5 Analysis
        prompt_parts.append("## MT5 Technical Analysis")
        prompt_parts.append(f"Direction: {mt5_analysis.get('direction', 'N/A')}")
        prompt_parts.append(f"Confidence: {mt5_analysis.get('confidence', 0)}%")
        prompt_parts.append(f"Strategy: {mt5_analysis.get('strategy', 'N/A')}")
        prompt_parts.append(f"Regime: {mt5_analysis.get('regime', 'N/A')}")
        
        if mt5_analysis.get('reasoning'):
            prompt_parts.append(f"Reasoning: {mt5_analysis['reasoning']}")
        
        # Entry details
        if mt5_analysis.get('entry') and mt5_analysis.get('stop_loss') and mt5_analysis.get('take_profit'):
            entry = mt5_analysis['entry']
            sl = mt5_analysis['stop_loss']
            tp = mt5_analysis['take_profit']
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else 0
            prompt_parts.append(f"Entry: {entry}, SL: {sl}, TP: {tp}")
            prompt_parts.append(f"Risk/Reward: {rr:.2f}")
        
        # Binance Real-Time Data
        prompt_parts.append("\n## Binance Real-Time Data")
        prompt_parts.append(f"Price: ${binance_enrichment.get('binance_price', 'N/A')}")
        prompt_parts.append(f"Micro Momentum: {binance_enrichment.get('micro_momentum', 0):+.2f}%")
        prompt_parts.append(f"Feed Health: {binance_enrichment.get('feed_health', 'unknown')}")
        
        if binance_enrichment.get('price_velocity'):
            prompt_parts.append(f"Price Velocity: {binance_enrichment['price_velocity']:+.4f}")
        if binance_enrichment.get('volume_acceleration'):
            prompt_parts.append(f"Volume Accel: {binance_enrichment['volume_acceleration']:+.2f}")
        
        # Order Flow
        if order_flow:
            prompt_parts.append("\n## Order Flow (Institutional Signals)")
            prompt_parts.append(f"Signal: {order_flow.get('signal', 'N/A')}")
            prompt_parts.append(f"Confidence: {order_flow.get('confidence', 0)}%")
            
            if order_flow.get('imbalance'):
                prompt_parts.append(f"Order Book Imbalance: {order_flow['imbalance']:.2f}")
            
            if order_flow.get('whale_count'):
                prompt_parts.append(f"Whale Orders (60s): {order_flow['whale_count']}")
            
            if order_flow.get('pressure_side'):
                prompt_parts.append(f"Order Flow Pressure: {order_flow['pressure_side']}")
            
            if order_flow.get('liquidity_voids'):
                prompt_parts.append(f"Liquidity Voids: {order_flow['liquidity_voids']}")
            
            if order_flow.get('warnings'):
                prompt_parts.append(f"Order Flow Warnings: {', '.join(order_flow['warnings'][:2])}")
        
        # Advanced Features
        if advanced_features and advanced_features.get('features'):
            prompt_parts.append("\n## V8 Indicators (Institutional Grade)")
            features = advanced_features['features']
            
            # RMAG stretch (critical warning)
            if features.get('M15', {}).get('rmag_stretch'):
                rmag = features['M15']['rmag_stretch']
                if abs(rmag) > 2:
                    prompt_parts.append(f"⚠️ RMAG Stretch: {rmag:.2f}σ (EXTREME - mean reversion risk!)")
                else:
                    prompt_parts.append(f"RMAG Stretch: {rmag:.2f}σ")
            
            # Momentum quality
            if features.get('M15', {}).get('fake_momentum_score'):
                fake_score = features['M15']['fake_momentum_score']
                if fake_score > 0.7:
                    prompt_parts.append(f"⚠️ Fake Momentum: {fake_score:.2f} (possibly false breakout)")
            
            # Liquidity proximity
            if features.get('M15', {}).get('near_liquidity'):
                prompt_parts.append(f"Near Liquidity: {features['M15']['near_liquidity']}")
            
            # V8 summary if available
            if advanced_features.get('v8_summary'):
                summary_preview = advanced_features['v8_summary'][:200]  # First 200 chars
                prompt_parts.append(f"\nV8 Summary: {summary_preview}...")
        
        prompt_parts.append("\n## Your Task")
        prompt_parts.append("Analyze this setup and provide your assessment in JSON format.")
        prompt_parts.append("Focus on: confluence, risk factors, and whether this deserves deeper validation.")
        
        return "\n".join(prompt_parts)
    
    def _estimate_cost(self, total_tokens: int) -> float:
        """
        Estimate API cost.
        GPT-4o-mini pricing: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
        Using average: ~$0.30 per 1M tokens
        """
        return (total_tokens / 1_000_000) * 0.30
    
    async def batch_analyze(
        self,
        setups: list[Dict]
    ) -> list[Dict]:
        """
        Analyze multiple setups in parallel.
        
        Args:
            setups: List of setup dicts with symbol, mt5_analysis, etc.
        
        Returns:
            List of analysis results
        """
        import asyncio
        
        tasks = [
            self.analyze_setup(
                setup['symbol'],
                setup['mt5_analysis'],
                setup['binance_enrichment'],
                setup.get('order_flow'),
                setup.get('advanced_features')
            )
            for setup in setups
        ]
        
        results = await asyncio.gather(*tasks)
        return results


# Example usage
async def example_usage():
    """Example of using GPT-4o Reasoner"""
    
    reasoner = GPT4oReasoner()
    
    # Mock data
    mt5_analysis = {
        "direction": "BUY",
        "confidence": 75,
        "strategy": "breakout",
        "regime": "trend",
        "reasoning": "Clean H1 trend, M15 breakout above resistance",
        "entry": 114000,
        "stop_loss": 113800,
        "take_profit": 114500
    }
    
    binance_enrichment = {
        "binance_price": 114020,
        "micro_momentum": 0.15,
        "feed_health": "healthy",
        "price_velocity": 0.0025,
        "volume_acceleration": 1.8
    }
    
    order_flow = {
        "signal": "BULLISH",
        "confidence": 70,
        "imbalance": 1.45,
        "whale_count": 3,
        "pressure_side": "BUY",
        "liquidity_voids": 2,
        "warnings": ["Volume spike 4x normal"]
    }
    
    advanced_features = {
        "features": {
            "M15": {
                "rmag_stretch": 1.2,
                "fake_momentum_score": 0.3,
                "near_liquidity": False
            }
        },
        "v8_summary": "Strong trend alignment, no critical warnings"
    }
    
    result = await reasoner.analyze_setup(
        "BTCUSD",
        mt5_analysis,
        binance_enrichment,
        order_flow,
        advanced_features
    )
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

