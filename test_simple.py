#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
print("Test script starting...", file=sys.stderr)
print("Test script starting...")

try:
    from infra.volatility_regime_detector import VolatilityRegime, RegimeDetector
    print("✅ Import successful")
    
    # Test enum
    print(f"PRE_BREAKOUT_TENSION = {VolatilityRegime.PRE_BREAKOUT_TENSION.value}")
    print(f"POST_BREAKOUT_DECAY = {VolatilityRegime.POST_BREAKOUT_DECAY.value}")
    print(f"FRAGMENTED_CHOP = {VolatilityRegime.FRAGMENTED_CHOP.value}")
    print(f"SESSION_SWITCH_FLARE = {VolatilityRegime.SESSION_SWITCH_FLARE.value}")
    
    # Test config
    from config import volatility_regime_config
    print(f"BB_WIDTH_NARROW_THRESHOLD = {volatility_regime_config.BB_WIDTH_NARROW_THRESHOLD}")
    
    # Test detector initialization
    detector = RegimeDetector()
    print("✅ RegimeDetector initialized")
    
    # Test tracking structures
    detector._ensure_symbol_tracking("BTCUSDc")
    print("✅ Tracking structures initialized for BTCUSDc")
    
    print("\n✅ All basic tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

