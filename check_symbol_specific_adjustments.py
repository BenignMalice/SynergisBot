"""
Check what symbol-specific adjustments are available in Universal Manager
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 80)
print("SYMBOL-SPECIFIC TRAILING STOP ADJUSTMENTS")
print("=" * 80)
print()

# Check Universal Manager config
print("1. Current Symbol-Specific Adjustments in Universal Manager:")
print()
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    config = manager.config
    symbol_adjustments = config.get("symbol_adjustments", {})
    
    print(f"   Available symbols with adjustments: {list(symbol_adjustments.keys())}")
    print()
    
    # Check BTC
    if "BTCUSDc" in symbol_adjustments:
        print(f"   📊 BTCUSDc adjustments:")
        for key, value in symbol_adjustments["BTCUSDc"].items():
            print(f"      • {key}: {value}")
    else:
        print(f"   ⚠️  BTCUSDc: No specific adjustments (uses defaults)")
    
    print()
    
    # Check XAU
    if "XAUUSDc" in symbol_adjustments:
        print(f"   📊 XAUUSDc adjustments:")
        for key, value in symbol_adjustments["XAUUSDc"].items():
            print(f"      • {key}: {value}")
    else:
        print(f"   ⚠️  XAUUSDc: No specific adjustments (uses defaults)")
    
    print()
    
    # Check what parameters CAN be adjusted
    print("   💡 Adjustable parameters:")
    print("      • trailing_timeframe (e.g., M1, M5, M15, H1)")
    print("      • min_sl_change_r (minimum R change for SL modification)")
    print("      • session_adjustments (session-specific overrides)")
    print()
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check what SHOULD be different for BTC vs XAU
print("2. Characteristics That SHOULD Be Different:")
print()
print("   📊 BTC (Bitcoin) Characteristics:")
print("      • High volatility (large ATR)")
print("      • 24/7 trading (sessions less relevant)")
print("      • Large price movements")
print("      • Should use: Larger trailing distance, shorter timeframe")
print()
print("   📊 XAU (Gold) Characteristics:")
print("      • Lower volatility (smaller ATR)")
print("      • Session-based trading (London/NY sessions matter)")
print("      • More stable price movements")
print("      • Should use: Smaller trailing distance, longer timeframe")
print()

# Check current ATR values
print("3. Current ATR Values (for comparison):")
print()
try:
    import MetaTrader5 as mt5
    
    if mt5.initialize():
        symbols = ["BTCUSDc", "XAUUSDc"]
        timeframes = ["M1", "M15", "H1"]
        
        for symbol in symbols:
            print(f"   {symbol}:")
            for tf in timeframes:
                atr = manager._get_current_atr(symbol, tf)
                if atr:
                    print(f"      {tf}: {atr:.2f} points")
                else:
                    print(f"      {tf}: N/A")
            print()
    else:
        print("   ⚠️  MT5 not initialized")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Recommendations
print("=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print()
print("💡 Symbol-Specific Adjustments That Should Be Added:")
print()
print("   For BTCUSDc:")
print("   • trailing_timeframe: M1 (faster response to volatility)")
print("   • atr_multiplier: 1.5-2.0 (wider trailing for high volatility)")
print("   • min_sl_change_r: 0.05-0.08 (smaller threshold for frequent adjustments)")
print("   • sl_modification_cooldown_seconds: 30 (faster updates)")
print()
print("   For XAUUSDc:")
print("   • trailing_timeframe: M15 or H1 (slower, more stable)")
print("   • atr_multiplier: 1.2-1.5 (tighter trailing for lower volatility)")
print("   • min_sl_change_r: 0.1-0.15 (larger threshold, less frequent)")
print("   • sl_modification_cooldown_seconds: 60 (slower updates)")
print()
print("   💡 These adjustments should be in config['symbol_adjustments']")
print()

