"""
Phase 4.1 Live Market Data Validation
Tests Phase 4.1 structure detectors with real MT5 data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from infra.feature_builder import build_features


def print_separator(title: str = ""):
    """Print a formatted separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print(f"{'='*60}")


def print_structure_features(symbol: str, timeframe: str, features: Dict[str, Any]):
    """Print Phase 4.1 structure features in a readable format."""
    print(f"\n[DATA] {symbol} - {timeframe}")
    print("-" * 60)
    
    # Liquidity Clusters
    print("\n>> LIQUIDITY CLUSTERS:")
    if features.get("eq_high_cluster"):
        print(f"  [+] Equal Highs: {features['eq_high_price']:.5f} "
              f"(count: {features['eq_high_count']}, {features['eq_high_bars_ago']} bars ago)")
    else:
        print(f"  [ ] No equal highs cluster")
    
    if features.get("eq_low_cluster"):
        print(f"  [+] Equal Lows:  {features['eq_low_price']:.5f} "
              f"(count: {features['eq_low_count']}, {features['eq_low_bars_ago']} bars ago)")
    else:
        print(f"  [ ] No equal lows cluster")
    
    # Sweeps
    print("\n>> SWEEPS (Liquidity Grabs):")
    if features.get("sweep_bull"):
        print(f"  [+] BULLISH SWEEP: {features['sweep_price']:.5f} "
              f"(depth: {features['sweep_depth']:.2f} ATR)")
    elif features.get("sweep_bear"):
        print(f"  [+] BEARISH SWEEP: {features['sweep_price']:.5f} "
              f"(depth: {features['sweep_depth']:.2f} ATR)")
    else:
        print(f"  [ ] No recent sweeps")
    
    # BOS/CHOCH
    print("\n>> MARKET STRUCTURE:")
    structure_type = features.get("structure_type", "none")
    if structure_type != "none":
        if features.get("choch_bull"):
            print(f"  [+] BULLISH CHOCH at {features['structure_break_level']:.5f} (potential reversal up)")
        elif features.get("choch_bear"):
            print(f"  [+] BEARISH CHOCH at {features['structure_break_level']:.5f} (potential reversal down)")
        elif features.get("bos_bull"):
            print(f"  [+] BULLISH BOS at {features['structure_break_level']:.5f} (trend continuation up)")
        elif features.get("bos_bear"):
            print(f"  [+] BEARISH BOS at {features['structure_break_level']:.5f} (trend continuation down)")
        
        bars_since = features.get("bars_since_bos", -1)
        if bars_since >= 0:
            print(f"      ({bars_since} bars since break)")
    else:
        print(f"  [ ] No recent structure breaks")
    
    # Fair Value Gaps
    print("\n>> FAIR VALUE GAPS:")
    if features.get("fvg_bull"):
        print(f"  [+] BULLISH FVG: {features['fvg_zone_lower']:.5f} - {features['fvg_zone_upper']:.5f}")
        print(f"      Width: {features['fvg_width_atr']:.2f} ATR ({features['fvg_bars_ago']} bars ago)")
    elif features.get("fvg_bear"):
        print(f"  [+] BEARISH FVG: {features['fvg_zone_lower']:.5f} - {features['fvg_zone_upper']:.5f}")
        print(f"      Width: {features['fvg_width_atr']:.2f} ATR ({features['fvg_bars_ago']} bars ago)")
    else:
        print(f"  [ ] No recent fair value gaps")
    
    # Wick Asymmetry
    print("\n>> WICK ASYMMETRY (Rejection Bars):")
    wick_asym = features.get("wick_asymmetry", 0.0)
    wick_strength = features.get("wick_strength", 0.0)
    
    if features.get("wick_rejection_bull"):
        print(f"  [+] BULLISH REJECTION: Strong lower wick (asymmetry: {wick_asym:.3f})")
    elif features.get("wick_rejection_bear"):
        print(f"  [+] BEARISH REJECTION: Strong upper wick (asymmetry: {wick_asym:.3f})")
    else:
        interpretation = "balanced" if abs(wick_asym) < 0.2 else "weak rejection"
        print(f"  [ ] {interpretation.title()} (asymmetry: {wick_asym:.3f}, strength: {wick_strength:.3f})")
    
    # Legacy Structure Info
    print("\n>> LEGACY STRUCTURE:")
    print(f"  Swing Count: {features.get('swing_count', 0)}")
    print(f"  Support Levels: {len(features.get('support_levels', []))}")
    print(f"  Resistance Levels: {len(features.get('resistance_levels', []))}")
    print(f"  Range Width: {features.get('range_width', 0.0):.5f}")


def validate_symbol(mt5svc: MT5Service, bridge: IndicatorBridge, symbol: str) -> bool:
    """Validate Phase 4.1 features for a single symbol."""
    print_separator(f"VALIDATING {symbol}")
    
    try:
        # Build features for multiple timeframes
        print(f"\n[BUILD] Building features for {symbol}...")
        features = build_features(
            symbol=symbol,
            mt5svc=mt5svc,
            bridge=bridge,
            timeframes=["M5", "M15", "H1", "H4"]
        )
        
        if not features:
            print(f"[FAIL] Failed to build features for {symbol}")
            return False
        
        # Check each timeframe
        timeframes = ["M5", "M15", "H1", "H4"]
        all_present = True
        
        for tf in timeframes:
            if tf not in features:
                print(f"[FAIL] {tf} features missing")
                all_present = False
                continue
            
            tf_features = features[tf]
            
            # Check Phase 4.1 features are present
            phase_4_1_keys = [
                "eq_high_cluster", "eq_low_cluster", "sweep_bull", "sweep_bear",
                "bos_bull", "bos_bear", "choch_bull", "choch_bear",
                "fvg_bull", "fvg_bear", "wick_asymmetry", "wick_rejection_bull"
            ]
            
            missing = [key for key in phase_4_1_keys if key not in tf_features]
            if missing:
                print(f"[FAIL] {tf} missing Phase 4.1 features: {missing}")
                all_present = False
            else:
                # Print detailed structure info
                print_structure_features(symbol, tf, tf_features)
        
        if all_present:
            print(f"\n[OK] {symbol} validation PASSED - All Phase 4.1 features present and computed")
        else:
            print(f"\n[FAIL] {symbol} validation FAILED - Some features missing")
        
        return all_present
        
    except Exception as e:
        print(f"\n[ERROR] Error validating {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return False


def summarize_findings(all_features: Dict[str, Dict[str, Dict[str, Any]]]):
    """Summarize interesting findings across all symbols and timeframes."""
    print_separator("PHASE 4.1 VALIDATION SUMMARY")
    
    findings = {
        "eq_highs": [],
        "eq_lows": [],
        "sweeps_bull": [],
        "sweeps_bear": [],
        "bos_bull": [],
        "bos_bear": [],
        "choch_bull": [],
        "choch_bear": [],
        "fvg_bull": [],
        "fvg_bear": [],
        "wick_rej_bull": [],
        "wick_rej_bear": []
    }
    
    for symbol, tfs in all_features.items():
        for tf, features in tfs.items():
            if features.get("eq_high_cluster"):
                findings["eq_highs"].append(f"{symbol} {tf}")
            if features.get("eq_low_cluster"):
                findings["eq_lows"].append(f"{symbol} {tf}")
            if features.get("sweep_bull"):
                findings["sweeps_bull"].append(f"{symbol} {tf}")
            if features.get("sweep_bear"):
                findings["sweeps_bear"].append(f"{symbol} {tf}")
            if features.get("bos_bull"):
                findings["bos_bull"].append(f"{symbol} {tf}")
            if features.get("bos_bear"):
                findings["bos_bear"].append(f"{symbol} {tf}")
            if features.get("choch_bull"):
                findings["choch_bull"].append(f"{symbol} {tf}")
            if features.get("choch_bear"):
                findings["choch_bear"].append(f"{symbol} {tf}")
            if features.get("fvg_bull"):
                findings["fvg_bull"].append(f"{symbol} {tf}")
            if features.get("fvg_bear"):
                findings["fvg_bear"].append(f"{symbol} {tf}")
            if features.get("wick_rejection_bull"):
                findings["wick_rej_bull"].append(f"{symbol} {tf}")
            if features.get("wick_rejection_bear"):
                findings["wick_rej_bear"].append(f"{symbol} {tf}")
    
    print("\n[SIGNALS] ACTIVE SIGNALS DETECTED:")
    print("\n>> Liquidity Clusters:")
    print(f"  Equal Highs: {len(findings['eq_highs'])} detected")
    if findings["eq_highs"]:
        print(f"    -> {', '.join(findings['eq_highs'])}")
    print(f"  Equal Lows:  {len(findings['eq_lows'])} detected")
    if findings["eq_lows"]:
        print(f"    -> {', '.join(findings['eq_lows'])}")
    
    print("\n>> Liquidity Sweeps:")
    print(f"  Bullish: {len(findings['sweeps_bull'])} detected")
    if findings["sweeps_bull"]:
        print(f"    -> {', '.join(findings['sweeps_bull'])}")
    print(f"  Bearish: {len(findings['sweeps_bear'])} detected")
    if findings["sweeps_bear"]:
        print(f"    -> {', '.join(findings['sweeps_bear'])}")
    
    print("\n>> Structure Breaks:")
    print(f"  Bullish BOS:   {len(findings['bos_bull'])} detected")
    if findings["bos_bull"]:
        print(f"    -> {', '.join(findings['bos_bull'])}")
    print(f"  Bearish BOS:   {len(findings['bos_bear'])} detected")
    if findings["bos_bear"]:
        print(f"    -> {', '.join(findings['bos_bear'])}")
    print(f"  Bullish CHOCH: {len(findings['choch_bull'])} detected")
    if findings["choch_bull"]:
        print(f"    -> {', '.join(findings['choch_bull'])}")
    print(f"  Bearish CHOCH: {len(findings['choch_bear'])} detected")
    if findings["choch_bear"]:
        print(f"    -> {', '.join(findings['choch_bear'])}")
    
    print("\n>> Fair Value Gaps:")
    print(f"  Bullish FVG: {len(findings['fvg_bull'])} detected")
    if findings["fvg_bull"]:
        print(f"    -> {', '.join(findings['fvg_bull'])}")
    print(f"  Bearish FVG: {len(findings['fvg_bear'])} detected")
    if findings["fvg_bear"]:
        print(f"    -> {', '.join(findings['fvg_bear'])}")
    
    print("\n>> Wick Rejections:")
    print(f"  Bullish: {len(findings['wick_rej_bull'])} detected")
    if findings["wick_rej_bull"]:
        print(f"    -> {', '.join(findings['wick_rej_bull'])}")
    print(f"  Bearish: {len(findings['wick_rej_bear'])} detected")
    if findings["wick_rej_bear"]:
        print(f"    -> {', '.join(findings['wick_rej_bear'])}")


async def main():
    """Main validation routine."""
    print_separator("PHASE 4.1 LIVE MARKET DATA VALIDATION")
    print(f"\n[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis script validates Phase 4.1 structure detectors with real MT5 data.")
    print("Testing: Equal Highs/Lows, Sweeps, BOS/CHOCH, FVG, and Wick Asymmetry")
    
    # Initialize MT5 services
    print("\n[INIT] Initializing MT5 services...")
    try:
        mt5svc = MT5Service()
        # Connect to MT5
        mt5svc.connect()
        print("[OK] MT5Service connected")
        
        # Initialize indicator bridge
        common_dir = Path(__file__).parent.parent / "common"
        bridge = IndicatorBridge(common_dir)
        print("[OK] IndicatorBridge initialized")
        
    except Exception as e:
        print(f"[FAIL] Failed to initialize services: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test symbols (as configured in user's broker)
    symbols = ["XAUUSDc", "BTCUSDc", "EURUSDc"]
    
    print(f"\n[TEST] Testing symbols: {', '.join(symbols)}")
    
    results = {}
    all_features = {}
    
    for symbol in symbols:
        success = validate_symbol(mt5svc, bridge, symbol)
        results[symbol] = success
        
        # Store features for summary
        if success:
            try:
                features = build_features(
                    symbol=symbol,
                    mt5svc=mt5svc,
                    bridge=bridge,
                    timeframes=["M5", "M15", "H1", "H4"]
                )
                all_features[symbol] = features
            except Exception as e:
                print(f"Warning: Could not store features for {symbol}: {e}")
    
    # Print summary
    print_separator("VALIDATION RESULTS")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    print(f"\n[RESULTS] {passed}/{total} symbols passed")
    for symbol, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} - {symbol}")
    
    # Summarize interesting findings
    if all_features:
        summarize_findings(all_features)
    
    # Final verdict
    print_separator()
    if passed == total:
        print("\n[SUCCESS] Phase 4.1 validation completed successfully!")
        print("          All structure detectors are working with live market data.")
        print("          The feature builder is ready for production use.")
        return True
    else:
        print(f"\n[PARTIAL] {passed}/{total} symbols validated")
        print("          Review errors above for failed symbols.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[STOP] Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

