"""
Quick validation script to test enhanced data fields in analyse_symbol_full.

This script tests that all enhanced data fields are calculated and included
in the analyse_symbol_full response.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from desktop_agent import tool_analyse_symbol_full


async def test_enhanced_fields(symbol: str = "XAUUSD"):
    """Test that enhanced data fields are present in analyse_symbol_full response."""
    print(f"\n{'='*60}")
    print(f"Testing Enhanced Data Fields for {symbol}")
    print(f"{'='*60}\n")
    
    try:
        # Call analyse_symbol_full
        args = {"symbol": symbol}
        result = await tool_analyse_symbol_full(args)
        
        # Check response structure
        if "data" not in result:
            print("❌ ERROR: 'data' key missing from response")
            return False
        
        data = result["data"]
        
        # Check for all enhanced data fields
        required_fields = [
            "correlation_context",
            "htf_levels",
            "session_risk",
            "execution_context",
            "strategy_stats",  # Can be None
            "structure_summary",
            "symbol_constraints"
        ]
        
        print("📊 Checking Enhanced Data Fields:\n")
        all_present = True
        
        for field in required_fields:
            if field in data:
                field_data = data[field]
                if field_data is None:
                    print(f"   ⚠️  {field}: None (may be expected)")
                elif isinstance(field_data, dict) and len(field_data) == 0:
                    print(f"   ⚠️  {field}: Empty dict (may be expected)")
                else:
                    # Check for data_quality if it's a dict
                    if isinstance(field_data, dict):
                        data_quality = field_data.get("data_quality", "unknown")
                        print(f"   ✅ {field}: Present (data_quality: {data_quality})")
                    else:
                        print(f"   ✅ {field}: Present")
            else:
                print(f"   ❌ {field}: MISSING")
                all_present = False
        
        # Check summary includes enhanced data fields section
        if "summary" in result:
            summary = result["summary"]
            if "ENHANCED DATA FIELDS" in summary.upper():
                print(f"\n   ✅ Enhanced Data Fields section found in summary")
            else:
                print(f"\n   ⚠️  Enhanced Data Fields section NOT found in summary")
        
        # Print sample data for each field
        print(f"\n📋 Sample Data:\n")
        
        if data.get("correlation_context"):
            corr = data["correlation_context"]
            print(f"   Correlation Context:")
            print(f"      - DXY: {corr.get('dxy_correlation', 'N/A')}")
            print(f"      - SP500: {corr.get('sp500_correlation', 'N/A')}")
            print(f"      - Data Quality: {corr.get('data_quality', 'N/A')}")
        
        if data.get("htf_levels"):
            htf = data["htf_levels"]
            print(f"   HTF Levels:")
            print(f"      - Weekly Open: {htf.get('weekly_open', 'N/A')}")
            print(f"      - Price Position: {htf.get('price_position', 'N/A')}")
            print(f"      - Data Quality: {htf.get('data_quality', 'N/A')}")
        
        if data.get("session_risk"):
            session = data["session_risk"]
            print(f"   Session Risk:")
            print(f"      - Risk Level: {session.get('risk_level', 'N/A')}")
            print(f"      - In Rollover: {session.get('in_rollover_window', 'N/A')}")
            print(f"      - Data Quality: {session.get('data_quality', 'N/A')}")
        
        if data.get("execution_context"):
            exec_ctx = data["execution_context"]
            print(f"   Execution Context:")
            print(f"      - Spread Quality: {exec_ctx.get('spread_quality', 'N/A')}")
            print(f"      - Execution Score: {exec_ctx.get('execution_quality_score', 'N/A')}")
            print(f"      - Data Quality: {exec_ctx.get('data_quality', 'N/A')}")
        
        if data.get("strategy_stats"):
            stats = data["strategy_stats"]
            print(f"   Strategy Stats:")
            print(f"      - Strategy: {stats.get('strategy_name', 'N/A')}")
            print(f"      - Win Rate: {stats.get('win_rate_pct', 'N/A')}%")
            print(f"      - Sample Size: {stats.get('sample_size', 'N/A')}")
        else:
            print(f"   Strategy Stats: None (no strategy selected or no data)")
        
        if data.get("structure_summary"):
            structure = data["structure_summary"]
            print(f"   Structure Summary:")
            print(f"      - Range Type: {structure.get('current_range_type', 'N/A')}")
            print(f"      - Range State: {structure.get('range_state', 'N/A')}")
            print(f"      - Has Sweep: {structure.get('has_liquidity_sweep', 'N/A')}")
        
        if data.get("symbol_constraints"):
            constraints = data["symbol_constraints"]
            print(f"   Symbol Constraints:")
            print(f"      - Max Concurrent Trades: {constraints.get('max_concurrent_trades_for_symbol', 'N/A')}")
            print(f"      - Risk Profile: {constraints.get('risk_profile', 'N/A')}")
            print(f"      - Banned Strategies: {constraints.get('banned_strategies', [])}")
        
        print(f"\n{'='*60}")
        if all_present:
            print("✅ ALL ENHANCED DATA FIELDS PRESENT")
        else:
            print("❌ SOME ENHANCED DATA FIELDS MISSING")
        print(f"{'='*60}\n")
        
        return all_present
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run validation tests for multiple symbols."""
    symbols = ["XAUUSD", "BTCUSD", "EURUSD"]
    
    results = {}
    for symbol in symbols:
        try:
            result = await test_enhanced_fields(symbol)
            results[symbol] = result
        except Exception as e:
            print(f"❌ Failed to test {symbol}: {e}")
            results[symbol] = False
        print("\n")
    
    # Summary
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}\n")
    for symbol, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {symbol}: {status}")
    
    all_passed = all(results.values())
    print(f"\n{'='*60}")
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print(f"{'='*60}\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

