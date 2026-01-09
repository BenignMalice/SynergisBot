"""
Simple verification script to check Phase 0 and Phase 1 implementation
Verifies code structure without requiring all dependencies
"""
import re
from pathlib import Path

def verify_phase0_imports():
    """Verify Phase 0 imports are present"""
    print("=" * 80)
    print("VERIFYING: Phase 0 - Imports")
    print("=" * 80)
    
    analyzer_file = Path("infra/multi_timeframe_analyzer.py")
    if not analyzer_file.exists():
        print("❌ multi_timeframe_analyzer.py not found")
        return False
    
    content = analyzer_file.read_text(encoding='utf-8', errors='ignore')
    
    checks = [
        ("pandas import", "import pandas as pd" in content or "import pandas" in content),
        ("_symmetric_swings import", "_symmetric_swings" in content and "from domain.market_structure import" in content),
        ("label_swings import", "label_swings" in content),
        ("detect_bos_choch import", "detect_bos_choch" in content),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def verify_phase0_methods():
    """Verify Phase 0 methods have CHOCH/BOS detection"""
    print("\n" + "=" * 80)
    print("VERIFYING: Phase 0 - Method Signatures and CHOCH/BOS Detection")
    print("=" * 80)
    
    analyzer_file = Path("infra/multi_timeframe_analyzer.py")
    content = analyzer_file.read_text(encoding='utf-8', errors='ignore')
    
    methods = [
        ("_analyze_h4_bias", "symbol: str"),
        ("_analyze_h1_context", "symbol: str"),
        ("_analyze_m30_setup", "symbol: str"),
        ("_analyze_m15_trigger", "symbol: str"),
        ("_analyze_m5_execution", "symbol: str"),
    ]
    
    all_passed = True
    for method_name, param in methods:
        # Check method signature has symbol parameter
        pattern = f"def {method_name}\\([^)]*{param}"
        has_param = bool(re.search(pattern, content))
        
        # Check method has CHOCH/BOS initialization
        method_start = content.find(f"def {method_name}")
        if method_start == -1:
            print(f"❌ {method_name}: Method not found")
            all_passed = False
            continue
        
        # Find method body (next def or end of file)
        method_end = content.find("\n    def ", method_start + 1)
        if method_end == -1:
            method_end = len(content)
        
        method_body = content[method_start:method_end]
        
        has_choch_init = "choch_detected = False" in method_body
        has_bos_init = "bos_detected = False" in method_body
        has_detect_call = "detect_bos_choch" in method_body
        has_return_fields = '"choch_detected"' in method_body and '"bos_detected"' in method_body
        
        status = "✅" if (has_param and has_choch_init and has_bos_init and has_detect_call and has_return_fields) else "❌"
        print(f"{status} {method_name}:")
        print(f"   - symbol parameter: {'✅' if has_param else '❌'}")
        print(f"   - CHOCH/BOS init: {'✅' if (has_choch_init and has_bos_init) else '❌'}")
        print(f"   - detect_bos_choch call: {'✅' if has_detect_call else '❌'}")
        print(f"   - return fields: {'✅' if has_return_fields else '❌'}")
        
        if not (has_param and has_choch_init and has_bos_init and has_detect_call and has_return_fields):
            all_passed = False
    
    return all_passed


def verify_phase0_analyze_method():
    """Verify analyze() method passes symbol parameter"""
    print("\n" + "=" * 80)
    print("VERIFYING: Phase 0 - analyze() Method")
    print("=" * 80)
    
    analyzer_file = Path("infra/multi_timeframe_analyzer.py")
    content = analyzer_file.read_text(encoding='utf-8', errors='ignore')
    
    # Check analyze method calls pass symbol
    checks = [
        ("h4_analysis call", "_analyze_h4_bias" in content and ", symbol" in content.split("_analyze_h4_bias")[1].split("\n")[0]),
        ("h1_analysis call", "_analyze_h1_context" in content and ", symbol" in content.split("_analyze_h1_context")[1].split("\n")[0]),
        ("m30_analysis call", "_analyze_m30_setup" in content and ", symbol" in content.split("_analyze_m30_setup")[1].split("\n")[0]),
        ("m15_analysis call", "_analyze_m15_trigger" in content and ", symbol" in content.split("_analyze_m15_trigger")[1].split("\n")[0]),
        ("m5_analysis call", "_analyze_m5_execution" in content and ", symbol" in content.split("_analyze_m5_execution")[1].split("\n")[0]),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def verify_phase1_calculation_code():
    """Verify Phase 1 calculation code is present"""
    print("\n" + "=" * 80)
    print("VERIFYING: Phase 1 - Calculation Code")
    print("=" * 80)
    
    agent_file = Path("desktop_agent.py")
    if not agent_file.exists():
        print("❌ desktop_agent.py not found")
        return False
    
    content = agent_file.read_text(encoding='utf-8', errors='ignore')
    
    # Count occurrences (should be 2 - one for each function)
    choch_calc_count = content.count("choch_detected = False")
    bos_calc_count = content.count("bos_detected = False")
    trend_calc_count = content.count("structure_trend = h4_data.get")
    recommendation_extract_count = content.count("recommendation = smc.get")
    
    checks = [
        ("CHOCH calculation code", choch_calc_count >= 2),
        ("BOS calculation code", bos_calc_count >= 2),
        ("Trend calculation code", trend_calc_count >= 2),
        ("Recommendation extraction", recommendation_extract_count >= 2),
        ("Timeframe loop", content.count("for tf_name, tf_data in smc.get(\"timeframes\"") >= 2),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name} (found {choch_calc_count if 'CHOCH' in check_name else bos_calc_count if 'BOS' in check_name else trend_calc_count if 'Trend' in check_name else recommendation_extract_count if 'Recommendation' in check_name else 0} occurrences)")
        if not passed:
            all_passed = False
    
    return all_passed


def verify_phase1_smc_dict():
    """Verify Phase 1 expanded smc dict"""
    print("\n" + "=" * 80)
    print("VERIFYING: Phase 1 - Expanded SMC Dict")
    print("=" * 80)
    
    agent_file = Path("desktop_agent.py")
    content = agent_file.read_text(encoding='utf-8', errors='ignore')
    
    # Check for expanded smc dict fields
    # Look for fields that appear after "smc": { and before the next major section
    required_fields = [
        ('"timeframes"', '"timeframes": smc.get'),
        ('"alignment_score"', '"alignment_score": smc.get'),
        ('"recommendation"', '"recommendation": recommendation'),
        ('"market_bias"', '"market_bias": recommendation.get'),
        ('"trade_opportunities"', '"trade_opportunities": recommendation.get'),
        ('"volatility_regime"', '"volatility_regime": recommendation.get'),
        ('"volatility_weights"', '"volatility_weights": recommendation.get'),
        ('"advanced_insights"', '"advanced_insights": smc.get'),
        ('"advanced_summary"', '"advanced_summary": smc.get'),
        ('"confidence_score"', '"confidence_score": recommendation.get')
    ]
    
    # Find all "smc": { occurrences
    smc_positions = [m.start() for m in re.finditer(r'"smc":\s*\{', content)]
    
    if len(smc_positions) < 2:
        print(f"❌ Expected 2 'smc' dict sections, found {len(smc_positions)}")
        return False
    
    all_passed = True
    for i, pos in enumerate(smc_positions[:2], 1):
        # Get context around this smc dict (next 2000 chars should contain all fields)
        context = content[pos:pos+2000]
        
        print(f"\nChecking smc dict #{i}:")
        section_passed = True
        for field_name, field_pattern in required_fields:
            # Check if field pattern appears in context (more reliable than regex)
            has_field = field_pattern in context
            # Also check for just the field name in quotes as fallback
            if not has_field:
                field_name_clean = field_name.replace('"', '')
                has_field = f'"{field_name_clean}"' in context
            status = "✅" if has_field else "❌"
            print(f"   {status} {field_name}")
            if not has_field:
                section_passed = False
                all_passed = False
        
        if section_passed:
            print(f"   ✅ All fields present in smc dict #{i}")
    
    return all_passed


def main():
    """Run all verifications"""
    print("=" * 80)
    print("MTF CHOCH/BOS Implementation Verification")
    print("=" * 80)
    print()
    
    results = []
    
    results.append(("Phase 0: Imports", verify_phase0_imports()))
    results.append(("Phase 0: Method Signatures", verify_phase0_methods()))
    results.append(("Phase 0: analyze() Method", verify_phase0_analyze_method()))
    results.append(("Phase 1: Calculation Code", verify_phase1_calculation_code()))
    results.append(("Phase 1: Expanded SMC Dict", verify_phase1_smc_dict()))
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for check_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 ALL VERIFICATIONS PASSED!")
        print("\nThe implementation appears to be correct.")
        print("Note: Full functional testing requires dependencies (pandas, MT5, etc.)")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("\nPlease review the failed checks above.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

