"""
Test GPT Hybrid System (Phases 5-7)

Tests:
1. GPT-4o Reasoner - Fast screening
2. GPT-5 Validator - Deep validation
3. GPT Orchestrator - Full pipeline
4. Cost tracking
5. Decision flow logic
"""

import asyncio
import sys
import codecs
import logging
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

from infra.gpt_reasoner import GPT4oReasoner
from infra.gpt_validator import GPT5Validator
from infra.gpt_orchestrator import GPTOrchestrator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Mock data generators
def get_strong_setup():
    """Generate a strong trade setup"""
    return {
        "symbol": "BTCUSD",
        "mt5_analysis": {
            "direction": "BUY",
            "confidence": 82,
            "strategy": "breakout",
            "regime": "trend",
            "reasoning": "Clean H1 uptrend, M15 breakout above key resistance with volume confirmation",
            "entry": 114000,
            "stop_loss": 113700,
            "take_profit": 114600,
            "risk_reward": 2.0
        },
        "binance_enrichment": {
            "binance_price": 114020,
            "micro_momentum": 0.22,
            "feed_health": "healthy",
            "price_velocity": 0.0035,
            "volume_acceleration": 2.1
        },
        "order_flow": {
            "signal": "BULLISH",
            "confidence": 78,
            "imbalance": 1.62,
            "whale_count": 4,
            "pressure_side": "BUY",
            "liquidity_voids": 1,
            "warnings": []
        },
        "advanced_features": {
            "features": {
                "M15": {
                    "rmag_stretch": 1.1,
                    "fake_momentum_score": 0.2,
                    "near_liquidity": False
                }
            },
            "v8_summary": "Strong trend alignment, clean breakout, no critical warnings"
        }
    }


def get_weak_setup():
    """Generate a weak trade setup"""
    return {
        "symbol": "EURUSD",
        "mt5_analysis": {
            "direction": "SELL",
            "confidence": 52,
            "strategy": "range",
            "regime": "chop",
            "reasoning": "Choppy price action, conflicting timeframes",
            "entry": 1.0850,
            "stop_loss": 1.0880,
            "take_profit": 1.0800,
            "risk_reward": 1.7
        },
        "binance_enrichment": {
            "binance_price": 1.0852,
            "micro_momentum": -0.05,
            "feed_health": "warning",
            "price_velocity": 0.0001,
            "volume_acceleration": 0.6
        },
        "order_flow": {
            "signal": "NEUTRAL",
            "confidence": 45,
            "imbalance": 0.98,
            "whale_count": 0,
            "pressure_side": "NEUTRAL",
            "liquidity_voids": 5,
            "warnings": ["High liquidity voids", "Low volume"]
        },
        "advanced_features": {
            "features": {
                "M15": {
                    "rmag_stretch": 2.3,  # Overextended!
                    "fake_momentum_score": 0.8,  # Likely fake breakout
                    "near_liquidity": True
                }
            },
            "v8_summary": "⚠️ RMAG overextended (2.3σ), high fake momentum risk"
        }
    }


def get_marginal_setup():
    """Generate a marginal/neutral setup"""
    return {
        "symbol": "XAUUSD",
        "mt5_analysis": {
            "direction": "BUY",
            "confidence": 65,
            "strategy": "pullback",
            "regime": "trend",
            "reasoning": "Trend pullback, support zone, but no confirmation yet",
            "entry": 2650,
            "stop_loss": 2640,
            "take_profit": 2670,
            "risk_reward": 2.0
        },
        "binance_enrichment": {
            "binance_price": 2651,
            "micro_momentum": 0.08,
            "feed_health": "healthy",
            "price_velocity": 0.0015,
            "volume_acceleration": 1.1
        },
        "order_flow": None,  # No order flow data
        "advanced_features": {
            "features": {
                "M15": {
                    "rmag_stretch": 0.8,
                    "fake_momentum_score": 0.5,
                    "near_liquidity": False
                }
            },
            "v8_summary": "Neutral conditions, waiting for confirmation"
        }
    }


async def test_gpt_hybrid():
    """Test complete GPT hybrid system"""
    
    logger.info("=" * 70)
    logger.info("🧪 TESTING GPT HYBRID SYSTEM (PHASES 5-7)")
    logger.info("=" * 70)
    
    # Initialize components
    logger.info("\n📦 Initializing GPT Components...")
    
    try:
        gpt4o = GPT4oReasoner()
        logger.info("✅ GPT-4o Reasoner initialized")
    except Exception as e:
        logger.error(f"❌ GPT-4o initialization failed: {e}")
        return
    
    try:
        gpt5 = GPT5Validator()
        logger.info("✅ GPT-5 Validator initialized")
    except Exception as e:
        logger.error(f"❌ GPT-5 initialization failed: {e}")
        return
    
    try:
        orchestrator = GPTOrchestrator(gpt4o, gpt5)
        logger.info("✅ GPT Orchestrator initialized")
    except Exception as e:
        logger.error(f"❌ Orchestrator initialization failed: {e}")
        return
    
    # ==================================================================
    # TEST 1: Strong Setup (should go through full pipeline)
    # ==================================================================
    logger.info("\n" + "="*70)
    logger.info("TEST 1: STRONG SETUP (Expected: GPT-4o → GPT-5 → EXECUTE)")
    logger.info("="*70)
    
    strong_setup = get_strong_setup()
    
    result1 = await orchestrator.analyze_and_decide(
        strong_setup["symbol"],
        strong_setup["mt5_analysis"],
        strong_setup["binance_enrichment"],
        strong_setup["order_flow"],
        strong_setup["advanced_features"]
    )
    
    logger.info(f"\n✅ TEST 1 RESULT:")
    logger.info(f"   Decision: {result1['final_decision']}")
    logger.info(f"   Confidence: {result1['confidence']}%")
    logger.info(f"   Cost: ${result1['total_cost']:.4f}")
    logger.info(f"   Time: {result1['analysis_time']:.2f}s")
    
    # ==================================================================
    # TEST 2: Weak Setup (should stop at GPT-4o)
    # ==================================================================
    logger.info("\n" + "="*70)
    logger.info("TEST 2: WEAK SETUP (Expected: GPT-4o → REJECT, no GPT-5)")
    logger.info("="*70)
    
    weak_setup = get_weak_setup()
    
    result2 = await orchestrator.analyze_and_decide(
        weak_setup["symbol"],
        weak_setup["mt5_analysis"],
        weak_setup["binance_enrichment"],
        weak_setup["order_flow"],
        weak_setup["advanced_features"]
    )
    
    logger.info(f"\n✅ TEST 2 RESULT:")
    logger.info(f"   Decision: {result2['final_decision']}")
    logger.info(f"   Confidence: {result2['confidence']}%")
    logger.info(f"   Cost: ${result2['total_cost']:.4f}")
    logger.info(f"   Time: {result2['analysis_time']:.2f}s")
    
    if result2.get("gpt5_result"):
        logger.warning(f"   ⚠️ GPT-5 ran on WEAK setup (should have been skipped)")
    else:
        logger.info(f"   ✅ GPT-5 correctly skipped")
    
    # ==================================================================
    # TEST 3: Marginal Setup (should stop at GPT-4o)
    # ==================================================================
    logger.info("\n" + "="*70)
    logger.info("TEST 3: MARGINAL SETUP (Expected: GPT-4o → SKIP/NEUTRAL)")
    logger.info("="*70)
    
    marginal_setup = get_marginal_setup()
    
    result3 = await orchestrator.analyze_and_decide(
        marginal_setup["symbol"],
        marginal_setup["mt5_analysis"],
        marginal_setup["binance_enrichment"],
        marginal_setup["order_flow"],
        marginal_setup["advanced_features"]
    )
    
    logger.info(f"\n✅ TEST 3 RESULT:")
    logger.info(f"   Decision: {result3['final_decision']}")
    logger.info(f"   Confidence: {result3['confidence']}%")
    logger.info(f"   Cost: ${result3['total_cost']:.4f}")
    logger.info(f"   Time: {result3['analysis_time']:.2f}s")
    
    # ==================================================================
    # FINAL STATISTICS
    # ==================================================================
    logger.info("\n" + "="*70)
    logger.info("📊 FINAL STATISTICS")
    logger.info("="*70)
    
    orchestrator.print_statistics()
    
    # ==================================================================
    # SUMMARY
    # ==================================================================
    logger.info("\n" + "="*70)
    logger.info("✅ ALL TESTS COMPLETED")
    logger.info("="*70)
    
    logger.info(f"\nTest 1 (Strong): {result1['final_decision']} - "
                f"GPT-5 {'✅ RAN' if result1.get('gpt5_result') else '❌ SKIPPED'}")
    logger.info(f"Test 2 (Weak): {result2['final_decision']} - "
                f"GPT-5 {'⚠️ RAN' if result2.get('gpt5_result') else '✅ SKIPPED'}")
    logger.info(f"Test 3 (Marginal): {result3['final_decision']} - "
                f"GPT-5 {'⚠️ RAN' if result3.get('gpt5_result') else '✅ SKIPPED'}")
    
    logger.info(f"\n💰 Total Cost: ${result1['total_cost'] + result2['total_cost'] + result3['total_cost']:.4f}")
    logger.info(f"⏱️ Total Time: {result1['analysis_time'] + result2['analysis_time'] + result3['analysis_time']:.2f}s")
    
    logger.info("\n✅ GPT Hybrid System is operational!")


if __name__ == "__main__":
    try:
        asyncio.run(test_gpt_hybrid())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)

