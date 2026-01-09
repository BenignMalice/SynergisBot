"""
Test to verify tick metrics are now included after the fix
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_verify_fix():
    """Test that tick metrics are now accessible"""
    try:
        from desktop_agent import registry
        
        # Initialize MT5 service
        if not registry.mt5_service:
            from infra.mt5_service import MT5Service
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                print("ERROR: Failed to connect to MT5")
                return
        
        # Check if tick metrics generator is accessible
        from infra.tick_metrics import get_tick_metrics_instance
        tick_generator = get_tick_metrics_instance()
        
        print("="*80)
        print("VERIFICATION TEST - Tick Metrics Fix")
        print("="*80)
        
        if tick_generator:
            print("\n✅ Tick metrics generator instance IS accessible")
            # Check XAUUSDc metrics directly
            metrics = tick_generator.get_latest_metrics("XAUUSDc")
            if metrics:
                metadata = metrics.get("metadata", {})
                print(f"✅ Direct metrics check for XAUUSDc:")
                print(f"   - data_available: {metadata.get('data_available')}")
                print(f"   - market_status: {metadata.get('market_status')}")
                m5 = metrics.get("M5", {})
                if m5:
                    print(f"   - M5 tick_count: {m5.get('tick_count', 0)}")
            else:
                print("⚠️ No metrics from generator for XAUUSDc")
        else:
            print("\n❌ Tick metrics generator instance NOT accessible")
            print("   This means the fix didn't work or generator isn't running")
            return
        
        # Test the tool
        tool_func = registry.tools.get("moneybot.analyse_symbol_full")
        if not tool_func:
            print("\n❌ Tool not found")
            return
        
        print("\n" + "="*80)
        print("TESTING XAUUSD ANALYSIS")
        print("="*80)
        
        result = await tool_func({"symbol": "XAUUSD"})
        
        # Check tick_metrics in response
        data = result.get("data", {})
        tick_metrics = data.get("tick_metrics")
        
        print("\n" + "="*80)
        print("VERIFICATION RESULTS")
        print("="*80)
        
        # Check 1: tick_metrics in data object
        if tick_metrics is None:
            print("\n❌ FAIL: tick_metrics is NULL in response.data")
            print("   The fix did not work - instance still not accessible")
        else:
            print("\n✅ PASS: tick_metrics IS PRESENT in response.data")
            metadata = tick_metrics.get("metadata", {})
            print(f"   - symbol: {metadata.get('symbol')}")
            print(f"   - data_available: {metadata.get('data_available')}")
            print(f"   - market_status: {metadata.get('market_status')}")
            
            # Check M5
            m5 = tick_metrics.get("M5")
            if m5:
                print(f"\n   ✅ M5 Metrics Present:")
                print(f"   - tick_count: {m5.get('tick_count', 'N/A')}")
                print(f"   - realized_volatility: {m5.get('realized_volatility', 'N/A')}")
                print(f"   - delta_volume: {m5.get('delta_volume', 'N/A')}")
                print(f"   - cvd_slope: {m5.get('cvd_slope', 'N/A')}")
            else:
                print("\n   ⚠️ M5 metrics not found")
        
        # Check 2: TICK MICROSTRUCTURE in summary
        summary = result.get("summary", "")
        if "TICK MICROSTRUCTURE" in summary:
            print("\n✅ PASS: TICK MICROSTRUCTURE found in summary")
            # Extract the section
            lines = summary.split("\n")
            for i, line in enumerate(lines):
                if "TICK MICROSTRUCTURE" in line:
                    print(f"\n   Summary section (next 6 lines):")
                    # Print next 5 lines
                    for j in range(i, min(i+6, len(lines))):
                        print(f"   {lines[j]}")
                    break
        else:
            print("\n❌ FAIL: TICK MICROSTRUCTURE NOT in summary")
            if tick_metrics:
                print("   BUT tick_metrics IS in data - formatting may have failed")
            else:
                print("   AND tick_metrics is NULL - instance not accessible")
        
        # Overall result
        print("\n" + "="*80)
        print("OVERALL RESULT")
        print("="*80)
        if tick_metrics and "TICK MICROSTRUCTURE" in summary:
            print("✅ SUCCESS: Both requirements met!")
            print("   - tick_metrics present in data object")
            print("   - TICK MICROSTRUCTURE section in summary")
        elif tick_metrics:
            print("⚠️ PARTIAL: tick_metrics present but not in summary")
            print("   - Check format_tick_metrics_summary function")
        else:
            print("❌ FAILED: tick_metrics not accessible")
            print("   - The fix needs further investigation")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_verify_fix())

