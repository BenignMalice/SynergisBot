"""
GPT Hybrid Orchestrator

Coordinates the complete AI validation pipeline:
1. Binance Stream → Real-time data
2. MT5 Analysis → Technical setup
3. Advanced Features → Institutional indicators
4. Order Flow → Microstructure signals
5. GPT-4o Reasoner → Fast screening (2-5s, ~$0.01)
6. GPT-5 Validator → Deep validation (10-30s, ~$0.10)
7. Execution → Trade if approved

Decision Flow:
Binance + MT5 + V8 + OrderFlow → GPT-4o → [STRONG?] → GPT-5 → [EXECUTE?] → Trade
                                        ↓ [WEAK/NEUTRAL]
                                     Skip/Reject
"""

import logging
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class GPTOrchestrator:
    """
    Orchestrates the complete GPT hybrid trading pipeline.
    
    Features:
    - Automatic GPT-4o screening for all setups
    - GPT-5 validation for STRONG signals only
    - Cost tracking and optimization
    - Decision logging
    - Error handling and fallbacks
    """
    
    def __init__(
        self,
        gpt4o_reasoner,
        gpt5_validator,
        auto_gpt4o: bool = True,
        auto_gpt5: bool = True,
        gpt5_threshold: int = 70
    ):
        """
        Initialize orchestrator.
        
        Args:
            gpt4o_reasoner: GPT4oReasoner instance
            gpt5_validator: GPT5Validator instance
            auto_gpt4o: Automatically run GPT-4o on all setups
            auto_gpt5: Automatically run GPT-5 on STRONG setups
            gpt5_threshold: Minimum GPT-4o confidence to trigger GPT-5
        """
        self.gpt4o = gpt4o_reasoner
        self.gpt5 = gpt5_validator
        self.auto_gpt4o = auto_gpt4o
        self.auto_gpt5 = auto_gpt5
        self.gpt5_threshold = gpt5_threshold
        
        # Statistics tracking
        self.stats = {
            "total_analyzed": 0,
            "gpt4o_runs": 0,
            "gpt5_runs": 0,
            "strong_signals": 0,
            "weak_signals": 0,
            "neutral_signals": 0,
            "executed": 0,
            "rejected": 0,
            "total_cost": 0.0
        }
        
        logger.info(f"🎭 GPT Orchestrator initialized")
        logger.info(f"   Auto GPT-4o: {auto_gpt4o}")
        logger.info(f"   Auto GPT-5: {auto_gpt5} (threshold: {gpt5_threshold}%)")
    
    async def analyze_and_decide(
        self,
        symbol: str,
        mt5_analysis: Dict,
        binance_enrichment: Dict,
        order_flow: Optional[Dict] = None,
        advanced_features: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Complete analysis pipeline with GPT reasoning.
        
        Args:
            symbol: Trading symbol
            mt5_analysis: MT5 technical analysis
            binance_enrichment: Binance real-time data
            order_flow: Order flow signals (optional)
            advanced_features: V8 indicators (optional)
        
        Returns:
            {
                "final_decision": "EXECUTE" | "WAIT" | "REJECT" | "SKIP",
                "confidence": 0-100,
                "gpt4o_result": {...},
                "gpt5_result": {...} or None,
                "reasoning": "...",
                "total_cost": float,
                "analysis_time": float
            }
        """
        start_time = datetime.now()
        self.stats["total_analyzed"] += 1
        
        result = {
            "symbol": symbol,
            "timestamp": start_time.isoformat(),
            "final_decision": "SKIP",
            "confidence": 0,
            "gpt4o_result": None,
            "gpt5_result": None,
            "reasoning": "",
            "total_cost": 0.0,
            "analysis_time": 0.0
        }
        
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"🎭 GPT HYBRID ANALYSIS: {symbol}")
            logger.info(f"{'='*70}")
            
            # STAGE 1: GPT-4o Fast Screening
            if self.auto_gpt4o:
                logger.info(f"⚡ Stage 1: GPT-4o Fast Screening...")
                
                gpt4o_result = await self.gpt4o.analyze_setup(
                    symbol,
                    mt5_analysis,
                    binance_enrichment,
                    order_flow,
                    advanced_features
                )
                
                result["gpt4o_result"] = gpt4o_result
                result["total_cost"] += gpt4o_result.get("cost_usd", 0)
                self.stats["gpt4o_runs"] += 1
                
                # Track signal strength
                signal = gpt4o_result.get("signal", "NEUTRAL")
                if signal == "STRONG":
                    self.stats["strong_signals"] += 1
                elif signal == "WEAK":
                    self.stats["weak_signals"] += 1
                else:
                    self.stats["neutral_signals"] += 1
                
                logger.info(f"   GPT-4o Result: {signal} ({gpt4o_result.get('confidence', 0)}%)")
                logger.info(f"   Cost: ${gpt4o_result.get('cost_usd', 0):.4f}")
                
                # Check if should proceed to GPT-5
                if not gpt4o_result.get("should_validate", False):
                    result["final_decision"] = "REJECT" if signal == "WEAK" else "SKIP"
                    result["confidence"] = gpt4o_result.get("confidence", 0)
                    result["reasoning"] = f"GPT-4o: {gpt4o_result.get('summary', 'Not strong enough for validation')}"
                    
                    logger.info(f"   ❌ Stopping at GPT-4o: {signal} signal")
                    logger.info(f"{'='*70}\n")
                    return result
            else:
                logger.info(f"   ⏭️ Skipping GPT-4o (auto_gpt4o=False)")
                gpt4o_result = {"signal": "UNKNOWN", "confidence": 0}
                result["gpt4o_result"] = gpt4o_result
            
            # STAGE 2: GPT-5 Deep Validation
            if self.auto_gpt5 and gpt4o_result.get("should_validate", False):
                logger.info(f"\n🧠 Stage 2: GPT-5 Deep Validation...")
                
                gpt5_result = await self.gpt5.validate_setup(
                    symbol,
                    mt5_analysis,
                    binance_enrichment,
                    order_flow,
                    advanced_features,
                    gpt4o_result
                )
                
                result["gpt5_result"] = gpt5_result
                result["total_cost"] += gpt5_result.get("cost_usd", 0)
                self.stats["gpt5_runs"] += 1
                
                decision = gpt5_result.get("decision", "REJECT")
                logger.info(f"   GPT-5 Decision: {decision} ({gpt5_result.get('confidence', 0)}%)")
                logger.info(f"   Cost: ${gpt5_result.get('cost_usd', 0):.4f}")
                
                # Set final decision
                result["final_decision"] = decision
                result["confidence"] = gpt5_result.get("confidence", 0)
                result["reasoning"] = gpt5_result.get("reasoning", "")
                
                if decision == "EXECUTE":
                    self.stats["executed"] += 1
                    logger.info(f"   ✅ APPROVED FOR EXECUTION")
                else:
                    self.stats["rejected"] += 1
                    logger.info(f"   ❌ {decision}: {gpt5_result.get('reasoning', '')[:100]}...")
            
            # Track total cost
            self.stats["total_cost"] += result["total_cost"]
            
            # Calculate analysis time
            end_time = datetime.now()
            result["analysis_time"] = (end_time - start_time).total_seconds()
            
            logger.info(f"\n📊 Pipeline Complete:")
            logger.info(f"   Decision: {result['final_decision']} ({result['confidence']}%)")
            logger.info(f"   Total Cost: ${result['total_cost']:.4f}")
            logger.info(f"   Analysis Time: {result['analysis_time']:.2f}s")
            logger.info(f"{'='*70}\n")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Orchestrator error for {symbol}: {e}", exc_info=True)
            result["final_decision"] = "REJECT"
            result["reasoning"] = f"Pipeline error: {str(e)}"
            result["error"] = str(e)
            return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            **self.stats,
            "avg_cost_per_analysis": (
                self.stats["total_cost"] / self.stats["total_analyzed"]
                if self.stats["total_analyzed"] > 0 else 0
            ),
            "gpt5_trigger_rate": (
                self.stats["gpt5_runs"] / self.stats["gpt4o_runs"] * 100
                if self.stats["gpt4o_runs"] > 0 else 0
            ),
            "execution_rate": (
                self.stats["executed"] / self.stats["total_analyzed"] * 100
                if self.stats["total_analyzed"] > 0 else 0
            )
        }
    
    def print_statistics(self):
        """Print formatted statistics"""
        stats = self.get_statistics()
        
        logger.info("\n" + "="*70)
        logger.info("📊 GPT ORCHESTRATOR STATISTICS")
        logger.info("="*70)
        logger.info(f"Total Analyzed: {stats['total_analyzed']}")
        logger.info(f"")
        logger.info(f"GPT-4o Screenings: {stats['gpt4o_runs']}")
        logger.info(f"  ✅ Strong: {stats['strong_signals']}")
        logger.info(f"  ⚠️ Neutral: {stats['neutral_signals']}")
        logger.info(f"  ❌ Weak: {stats['weak_signals']}")
        logger.info(f"")
        logger.info(f"GPT-5 Validations: {stats['gpt5_runs']} ({stats['gpt5_trigger_rate']:.1f}% of screenings)")
        logger.info(f"  ✅ Executed: {stats['executed']}")
        logger.info(f"  ❌ Rejected: {stats['rejected']}")
        logger.info(f"")
        logger.info(f"Execution Rate: {stats['execution_rate']:.1f}%")
        logger.info(f"Total Cost: ${stats['total_cost']:.2f}")
        logger.info(f"Avg Cost/Analysis: ${stats['avg_cost_per_analysis']:.4f}")
        logger.info("="*70 + "\n")
    
    async def batch_analyze(
        self,
        setups: list[Dict]
    ) -> list[Dict]:
        """
        Analyze multiple setups sequentially.
        
        Args:
            setups: List of setup dicts
        
        Returns:
            List of analysis results
        """
        results = []
        
        for setup in setups:
            result = await self.analyze_and_decide(
                setup['symbol'],
                setup['mt5_analysis'],
                setup['binance_enrichment'],
                setup.get('order_flow'),
                setup.get('advanced_features')
            )
            results.append(result)
        
        return results


# Example usage
async def example_usage():
    """Example of using GPT Orchestrator"""
    from infra.gpt_reasoner import GPT4oReasoner
    from infra.gpt_validator import GPT5Validator
    
    # Initialize components
    gpt4o = GPT4oReasoner()
    gpt5 = GPT5Validator()
    orchestrator = GPTOrchestrator(gpt4o, gpt5)
    
    # Mock setup
    mt5_analysis = {
        "direction": "BUY",
        "confidence": 75,
        "strategy": "breakout",
        "regime": "trend",
        "reasoning": "Clean H1 trend, M15 breakout",
        "entry": 114000,
        "stop_loss": 113800,
        "take_profit": 114500
    }
    
    binance_enrichment = {
        "binance_price": 114020,
        "micro_momentum": 0.15,
        "feed_health": "healthy"
    }
    
    order_flow = {
        "signal": "BULLISH",
        "confidence": 70,
        "imbalance": 1.45
    }
    
    # Run full pipeline
    result = await orchestrator.analyze_and_decide(
        "BTCUSD",
        mt5_analysis,
        binance_enrichment,
        order_flow
    )
    
    print(json.dumps(result, indent=2))
    
    # Show statistics
    orchestrator.print_statistics()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())

