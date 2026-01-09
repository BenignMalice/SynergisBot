"""
GPT-5 Validator - Deep Trade Validation

Purpose: Comprehensive 10-30 second AI validation for STRONG setups.
Uses GPT-4 (or GPT-5 when available) for deep analysis.

Only runs when:
- GPT-4o Reasoner marks as STRONG (70%+ confidence)
- Setup has multiple confluences
- Worth the extra cost/time

Decision Flow:
- EXECUTE → Trade immediately
- WAIT → Monitor, conditions not optimal
- REJECT → Don't trade, too risky

Cost: ~$0.10 per validation
"""

import logging
import json
from typing import Dict, Optional, Any
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)


class GPT5Validator:
    """
    Deep AI validator using GPT-4 (preparing for GPT-5) for final trade approval.
    
    Performs comprehensive analysis:
    - Historical pattern recognition
    - Multi-timeframe context
    - Risk scenario analysis
    - Entry/exit optimization
    - Psychological traps detection
    
    Returns:
    - Final decision (EXECUTE/WAIT/REJECT)
    - Confidence (0-100%)
    - Detailed reasoning
    - Risk assessment
    - Position sizing recommendation
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize GPT-5 validator.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4-turbo-preview"  # Use GPT-5 when available
        
        logger.info(f"🧠 GPT-5 Validator initialized (model: {self.model})")
    
    async def validate_setup(
        self,
        symbol: str,
        mt5_analysis: Dict,
        binance_enrichment: Dict,
        order_flow: Optional[Dict],
        advanced_features: Optional[Dict],
        gpt4o_preliminary: Dict
    ) -> Dict[str, Any]:
        """
        Deep validation of trade setup with GPT-4/GPT-5.
        
        Args:
            symbol: Trading symbol
            mt5_analysis: MT5 technical analysis
            binance_enrichment: Real-time Binance data
            order_flow: Order flow signals
            advanced_features: V8 indicators
            gpt4o_preliminary: GPT-4o preliminary analysis
        
        Returns:
            {
                "decision": "EXECUTE" | "WAIT" | "REJECT",
                "confidence": 0-100,
                "reasoning": "Detailed explanation",
                "risk_assessment": {...},
                "entry_optimization": {...},
                "warnings": [...],
                "position_sizing": "FULL" | "HALF" | "QUARTER"
            }
        """
        try:
            # Build validation prompt
            prompt = self._build_prompt(
                symbol, mt5_analysis, binance_enrichment,
                order_flow, advanced_features, gpt4o_preliminary
            )
            
            logger.info(f"🧠 GPT-5 deep validation for {symbol}...")
            
            # Call GPT-4/GPT-5
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
                temperature=0.2,  # Very low for consistency
                max_tokens=1500,  # Detailed analysis
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result["model"] = self.model
            result["tokens_used"] = response.usage.total_tokens
            result["cost_usd"] = self._estimate_cost(response.usage.total_tokens)
            
            logger.info(
                f"✅ GPT-5: {symbol} → {result['decision']} "
                f"({result['confidence']}%) "
                f"[{result['tokens_used']} tokens, ${result['cost_usd']:.4f}]"
            )
            
            if result.get("warnings"):
                for warning in result["warnings"]:
                    logger.warning(f"   ⚠️ {warning}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ GPT-5 validation failed for {symbol}: {e}", exc_info=True)
            return {
                "decision": "REJECT",
                "confidence": 0,
                "reasoning": f"Validation failed: {str(e)}",
                "risk_assessment": {"level": "UNKNOWN"},
                "warnings": ["GPT-5 validation error - rejecting for safety"],
                "position_sizing": "NONE",
                "error": str(e)
            }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for GPT-5 validator"""
        return """You are a master forex/crypto trader with 20+ years of experience.

Your role: Final validation before trade execution (deep 10-30 second analysis).

You receive STRONG setups that passed preliminary screening. Your job is to:
1. Find hidden risks the fast analyzer missed
2. Validate the confluence is genuine
3. Optimize entry/exit levels
4. Recommend position sizing based on setup quality

Return JSON:
{
    "decision": "EXECUTE" | "WAIT" | "REJECT",
    "confidence": 0-100,
    "reasoning": "Detailed multi-paragraph explanation covering:
                  - Why this setup is/isn't valid
                  - Key confluence factors
                  - Risk scenarios and likelihood
                  - Historical similar patterns",
    "risk_assessment": {
        "level": "LOW" | "MEDIUM" | "HIGH",
        "primary_risk": "Main risk factor",
        "stop_hunt_probability": 0-100,
        "fake_breakout_probability": 0-100
    },
    "entry_optimization": {
        "recommended_entry": number,
        "optimal_stop_loss": number,
        "optimal_take_profit": number,
        "reason": "Why these levels are better"
    },
    "warnings": ["List of specific warnings"],
    "position_sizing": "FULL" | "HALF" | "QUARTER",
    "market_context": "Current market phase and how it affects this trade"
}

Decision criteria:
- EXECUTE: High-quality setup, low hidden risks, good R:R → Trade now
- WAIT: Good setup but timing not ideal → Wait for better entry
- REJECT: Hidden risks found, poor confluence → Don't trade

Be extremely analytical and conservative. Consider:
1. Could this be a liquidity grab/stop hunt?
2. Is the breakout genuine or fake momentum?
3. Are we chasing or entering at value?
4. What's the probability of each risk scenario?
5. Does order flow confirm or contradict?
6. Are we overextended (RMAG >2σ)?
7. What's the market structure context?

Only approve EXECUTE for genuinely high-quality, low-risk setups."""

    def _build_prompt(
        self,
        symbol: str,
        mt5_analysis: Dict,
        binance_enrichment: Dict,
        order_flow: Optional[Dict],
        advanced_features: Optional[Dict],
        gpt4o_preliminary: Dict
    ) -> str:
        """Build comprehensive validation prompt"""
        
        prompt_parts = [
            f"# Deep Validation: {symbol}",
            "\nThis setup passed preliminary screening. Perform final validation.\n"
        ]
        
        # GPT-4o Preliminary Assessment
        prompt_parts.append("## Preliminary Assessment (GPT-4o)")
        prompt_parts.append(f"Signal: {gpt4o_preliminary.get('signal', 'N/A')}")
        prompt_parts.append(f"Confidence: {gpt4o_preliminary.get('confidence', 0)}%")
        prompt_parts.append(f"Reasoning: {gpt4o_preliminary.get('reasoning', 'N/A')}")
        if gpt4o_preliminary.get('warnings'):
            prompt_parts.append(f"Warnings: {', '.join(gpt4o_preliminary['warnings'])}")
        
        # Complete MT5 Analysis
        prompt_parts.append("\n## Complete MT5 Technical Analysis")
        prompt_parts.append(json.dumps(mt5_analysis, indent=2))
        
        # Binance Real-Time Context
        prompt_parts.append("\n## Binance Real-Time Context")
        prompt_parts.append(json.dumps(binance_enrichment, indent=2))
        
        # Order Flow (if available)
        if order_flow:
            prompt_parts.append("\n## Order Flow Analysis (Institutional Positioning)")
            prompt_parts.append(json.dumps(order_flow, indent=2))
        
        # Advanced Features (if available)
        if advanced_features:
            prompt_parts.append("\n## V8 Institutional Indicators")
            prompt_parts.append(json.dumps(advanced_features, indent=2))
        
        prompt_parts.append("\n## Your Task")
        prompt_parts.append("""Perform comprehensive validation:

1. **Confluence Analysis**: Are all signals genuinely aligned or just coincidence?

2. **Risk Scenario Analysis**: 
   - What could go wrong?
   - Stop hunt probability?
   - Fake breakout likelihood?
   - RMAG overextension risk?

3. **Entry Optimization**:
   - Is the proposed entry optimal?
   - Better levels available?
   - Should we wait for pullback?

4. **Order Flow Validation**:
   - Does order flow support the technical setup?
   - Any institutional contradiction?
   - Liquidity void concerns?

5. **Historical Pattern Recognition**:
   - Similar patterns in this market?
   - What usually happens next?

6. **Position Sizing**:
   - FULL (0.01 lots): High quality, low risk
   - HALF (0.005 lots): Good but some uncertainty  
   - QUARTER (0.0025 lots): Marginal setup, testing

Provide your deep analysis in JSON format.""")
        
        return "\n".join(prompt_parts)
    
    def _estimate_cost(self, total_tokens: int) -> float:
        """
        Estimate API cost.
        GPT-4 pricing: ~$10 per 1M input tokens, ~$30 per 1M output tokens
        Using average: ~$15 per 1M tokens
        """
        return (total_tokens / 1_000_000) * 15.0


# Example usage
async def example_usage():
    """Example of using GPT-5 Validator"""
    
    validator = GPT5Validator()
    
    # Mock data (same as GPT-4o example)
    mt5_analysis = {
        "direction": "BUY",
        "confidence": 75,
        "strategy": "breakout",
        "regime": "trend",
        "reasoning": "Clean H1 trend, M15 breakout above resistance",
        "entry": 114000,
        "stop_loss": 113800,
        "take_profit": 114500,
        "timeframes": {
            "H4": "BULLISH trend",
            "H1": "BULLISH breakout",
            "M15": "BULLISH momentum",
            "M5": "BULLISH entry"
        }
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
    
    gpt4o_preliminary = {
        "signal": "STRONG",
        "confidence": 82,
        "reasoning": "Multiple confluences: H1 trend + M15 breakout + order flow bullish + V8 clean",
        "warnings": ["Volume spike may indicate exhaustion"]
    }
    
    result = await validator.validate_setup(
        "BTCUSD",
        mt5_analysis,
        binance_enrichment,
        order_flow,
        advanced_features,
        gpt4o_preliminary
    )
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

