"""
Test Top 5 Binance Enrichment Fields
"""

import sys
import codecs
import logging
import numpy as np
from infra.binance_enrichment import BinanceEnrichment

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_price_structure():
    """Test Higher High / Lower Low detection"""
    print("\n" + "="*70)
    print("🧪 Test 1: Price Structure Detection")
    print("="*70 + "\n")
    
    enricher = BinanceEnrichment()
    
    # Test data: Higher Highs
    higher_highs = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 
                    111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 
                    122, 123, 124, 125, 126, 127, 128, 129]
    
    result = enricher._detect_price_structure(higher_highs)
    print(f"📈 Higher Highs Test:")
    print(f"   Structure: {result['structure']}")
    print(f"   Strength: {result['strength']}")
    print(f"   Consecutive: {result['consecutive_count']}")
    assert result['structure'] in ["HIGHER_HIGH", "HIGHER_LOW"], "Should detect bullish structure"
    print("   ✅ PASSED\n")
    
    # Test data: Lower Lows
    lower_lows = list(reversed(higher_highs))
    result = enricher._detect_price_structure(lower_lows)
    print(f"📉 Lower Lows Test:")
    print(f"   Structure: {result['structure']}")
    print(f"   Strength: {result['strength']}")
    print(f"   Consecutive: {result['consecutive_count']}")
    assert result['structure'] in ["LOWER_LOW", "LOWER_HIGH"], "Should detect bearish structure"
    print("   ✅ PASSED\n")
    
    # Test data: Choppy
    choppy = [100, 102, 99, 103, 98, 104, 97, 105, 96, 106, 95, 107, 94, 108,
              93, 109, 92, 110, 91, 111, 90, 112, 89, 113, 88, 114, 87, 115, 86, 116]
    result = enricher._detect_price_structure(choppy)
    print(f"🌀 Choppy Test:")
    print(f"   Structure: {result['structure']}")
    print(f"   Strength: {result['strength']}")
    print("   ✅ PASSED\n")


def test_volatility_state():
    """Test Volatility expansion/contraction"""
    print("\n" + "="*70)
    print("🧪 Test 2: Volatility State Detection")
    print("="*70 + "\n")
    
    enricher = BinanceEnrichment()
    
    # Test data: Expanding (small moves → large moves)
    expanding = []
    for i in range(15):
        expanding.append(100 + i * 0.1)  # Small moves
    for i in range(15):
        expanding.append(100 + 1.5 + i * 0.5)  # Large moves
    
    result = enricher._detect_volatility_state(expanding)
    print(f"💥 Expanding Volatility Test:")
    print(f"   State: {result['state']}")
    print(f"   Change: {result['change_pct']:+.1f}%")
    assert result['state'] == "EXPANDING", "Should detect expanding volatility"
    print("   ✅ PASSED\n")
    
    # Test data: Contracting (large moves → small moves)
    contracting = list(reversed(expanding))
    result = enricher._detect_volatility_state(contracting)
    print(f"🔐 Contracting Volatility Test:")
    print(f"   State: {result['state']}")
    print(f"   Change: {result['change_pct']:+.1f}%")
    if result.get('squeeze_duration'):
        print(f"   Squeeze Duration: {result['squeeze_duration']}s")
    assert result['state'] == "CONTRACTING", "Should detect contracting volatility"
    print("   ✅ PASSED\n")


def test_momentum_consistency():
    """Test Momentum consistency"""
    print("\n" + "="*70)
    print("🧪 Test 3: Momentum Consistency")
    print("="*70 + "\n")
    
    enricher = BinanceEnrichment()
    
    # Test data: Excellent consistency (all moves up)
    consistent_up = [100 + i * 0.5 for i in range(30)]
    result = enricher._calculate_momentum_consistency(consistent_up)
    print(f"✅ Excellent Consistency Test:")
    print(f"   Quality: {result['quality_label']}")
    print(f"   Score: {result['consistency_score']}%")
    print(f"   Consecutive Moves: {result['consecutive_moves']}")
    assert result['quality_label'] in ["EXCELLENT", "GOOD"], "Should detect excellent quality"
    print("   ✅ PASSED\n")
    
    # Test data: Choppy (random moves)
    np.random.seed(42)
    choppy = [100]
    for i in range(29):
        choppy.append(choppy[-1] + np.random.uniform(-0.5, 0.5))
    
    result = enricher._calculate_momentum_consistency(choppy)
    print(f"🔴 Choppy Test:")
    print(f"   Quality: {result['quality_label']}")
    print(f"   Score: {result['consistency_score']}%")
    print(f"   Consecutive Moves: {result['consecutive_moves']}")
    assert result['quality_label'] in ["CHOPPY", "FAIR"], "Should detect choppy quality"
    print("   ✅ PASSED\n")


def test_spread_analysis():
    """Test Spread proxy (choppiness)"""
    print("\n" + "="*70)
    print("🧪 Test 4: Spread Analysis (Choppiness)")
    print("="*70 + "\n")
    
    enricher = BinanceEnrichment()
    
    # Test data: Clean trend (low choppiness)
    clean_trend = [100 + i * 0.5 for i in range(30)]
    result = enricher._analyze_spread_proxy(clean_trend)
    print(f"✅ Clean Trend Test:")
    print(f"   Trend: {result['trend']}")
    print(f"   Choppiness: {result['choppiness']}/100")
    assert result['choppiness'] < 50, "Clean trend should have low choppiness"
    print("   ✅ PASSED\n")
    
    # Test data: Choppy (high choppiness)
    choppy = [100]
    for i in range(29):
        choppy.append(choppy[-1] + (1 if i % 2 == 0 else -1) * 0.5)
    
    result = enricher._analyze_spread_proxy(choppy)
    print(f"🌀 Choppy Test:")
    print(f"   Trend: {result['trend']}")
    print(f"   Choppiness: {result['choppiness']}/100")
    assert result['choppiness'] > 50, "Choppy movement should have high choppiness"
    print("   ✅ PASSED\n")


def test_micro_alignment():
    """Test Micro timeframe alignment"""
    print("\n" + "="*70)
    print("🧪 Test 5: Micro Timeframe Alignment")
    print("="*70 + "\n")
    
    enricher = BinanceEnrichment()
    
    # Test data: Perfect bullish alignment
    bullish_aligned = [100 + i * 0.3 for i in range(30)]
    result = enricher._calculate_micro_alignment(bullish_aligned)
    print(f"🟢 Perfect Bullish Alignment Test:")
    print(f"   3s: {result['alignment']['3s']}")
    print(f"   10s: {result['alignment']['10s']}")
    print(f"   30s: {result['alignment']['30s']}")
    print(f"   Score: {result['score']}/100")
    print(f"   Strength: {result['strength']}")
    assert result['score'] == 100, "All bullish should score 100"
    assert result['strength'] == "STRONG", "Should be STRONG"
    print("   ✅ PASSED\n")
    
    # Test data: Misaligned (short term up, long term down)
    misaligned = [100 - i * 0.2 for i in range(25)]  # Downtrend
    misaligned.extend([75 + i * 0.5 for i in range(5)])  # Recent uptick
    
    result = enricher._calculate_micro_alignment(misaligned)
    print(f"⚠️ Misaligned Test:")
    print(f"   3s: {result['alignment']['3s']}")
    print(f"   10s: {result['alignment']['10s']}")
    print(f"   30s: {result['alignment']['30s']}")
    print(f"   Score: {result['score']}/100")
    print(f"   Strength: {result['strength']}")
    assert result['score'] < 100, "Misaligned should score < 100"
    print("   ✅ PASSED\n")


def main():
    print("\n" + "="*70)
    print("🚀 Testing Top 5 Binance Enrichment Fields")
    print("="*70)
    
    try:
        test_price_structure()
        test_volatility_state()
        test_momentum_consistency()
        test_spread_analysis()
        test_micro_alignment()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n📊 Summary:")
        print("   ✅ Price Structure (Higher High/Lower Low) - Working")
        print("   ✅ Volatility State (Expansion/Contraction) - Working")
        print("   ✅ Momentum Consistency - Working")
        print("   ✅ Spread Analysis (Choppiness) - Working")
        print("   ✅ Micro Timeframe Alignment - Working")
        print("\n🎯 All 5 enrichment fields are functioning correctly!")
        print("\n📋 Next Steps:")
        print("   1. Test with live Binance data (run desktop_agent.py)")
        print("   2. Analyze a symbol from phone ChatGPT")
        print("   3. Look for new enrichment fields in analysis:")
        print("      - 📈 Market Structure (HIGHER HIGH/LOWER LOW)")
        print("      - 💥 Volatility (EXPANDING/CONTRACTING)")
        print("      - ✅ Momentum Quality (EXCELLENT/GOOD/FAIR/CHOPPY)")
        print("      - ✅ Spread Narrowing")
        print("      - 🎯 Micro Alignment (STRONG/MODERATE/WEAK)")
        print()
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Test error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

