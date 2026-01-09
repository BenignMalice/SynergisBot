"""
Test to check if tick_metrics exists in raw response data for XAUUSD
"""
import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_xau_raw_response():
    """Test XAU analysis and check raw response for tick_metrics"""
    try:
        from desktop_agent import registry
        
        # Initialize MT5 service
        if not registry.mt5_service:
            from infra.mt5_service import MT5Service
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                print("ERROR: Failed to connect to MT5")
                return
        
        # Check if tick metrics generator is running
        from infra.tick_metrics import get_tick_metrics_instance
        tick_generator = get_tick_metrics_instance()
        
        if tick_generator:
            print("OK: Tick metrics generator instance found")
            # Check XAUUSDc metrics directly
            metrics = tick_generator.get_latest_metrics("XAUUSDc")
            if metrics:
                metadata = metrics.get("metadata", {})
                print(f"OK: Direct metrics check for XAUUSDc:")
                print(f"   - data_available: {metadata.get('data_available')}")
                print(f"   - market_status: {metadata.get('market_status')}")
                m5 = metrics.get("M5", {})
                if m5:
                    print(f"   - M5 tick_count: {m5.get('tick_count', 0)}")
            else:
                print("WARNING: No metrics from generator for XAUUSDc")
        else:
            print("WARNING: Tick metrics generator not available")
        
        # Test the tool
        tool_func = registry.tools.get("moneybot.analyse_symbol_full")
        if not tool_func:
            print("ERROR: Tool not found")
            return
        
        print("\n" + "="*80)
        print("TESTING XAUUSD ANALYSIS - CHECKING RAW RESPONSE")
        print("="*80)
        
        result = await tool_func({"symbol": "XAUUSD"})
        
        # Check tick_metrics in response
        data = result.get("data", {})
        tick_metrics = data.get("tick_metrics")
        
        print("\n" + "="*80)
        print("RAW RESPONSE DATA CHECK")
        print("="*80)
        
        if tick_metrics is None:
            print("\nERROR: tick_metrics is NULL in response.data")
            print("   This means tick_metrics was not included in the response")
        else:
            print("\nOK: tick_metrics IS PRESENT in response.data")
            print(f"   Type: {type(tick_metrics)}")
            
            metadata = tick_metrics.get("metadata", {})
            print(f"\n   Metadata:")
            print(f"   - symbol: {metadata.get('symbol')}")
            print(f"   - data_available: {metadata.get('data_available')}")
            print(f"   - market_status: {metadata.get('market_status')}")
            print(f"   - last_updated: {metadata.get('last_updated')}")
            
            # Check M5
            m5 = tick_metrics.get("M5")
            if m5:
                print(f"\n   M5 Metrics Present:")
                print(f"   - tick_count: {m5.get('tick_count', 'N/A')}")
                print(f"   - realized_volatility: {m5.get('realized_volatility', 'N/A')}")
                print(f"   - delta_volume: {m5.get('delta_volume', 'N/A')}")
                print(f"   - cvd_slope: {m5.get('cvd_slope', 'N/A')}")
            else:
                print("\n   WARNING: M5 metrics not found")
            
            # Check M15
            m15 = tick_metrics.get("M15")
            if m15:
                print(f"\n   M15 Metrics Present:")
                print(f"   - tick_count: {m15.get('tick_count', 'N/A')}")
            else:
                print("\n   WARNING: M15 metrics not found")
            
            # Check H1
            h1 = tick_metrics.get("H1")
            if h1:
                print(f"\n   H1 Metrics Present:")
                print(f"   - tick_count: {h1.get('tick_count', 'N/A')}")
            else:
                print("\n   WARNING: H1 metrics not found")
            
            # Check previous_hour
            prev_hour = tick_metrics.get("previous_hour")
            if prev_hour:
                print(f"\n   Previous Hour Present:")
                print(f"   - tick_count: {prev_hour.get('tick_count', 'N/A')}")
            else:
                print("\n   WARNING: previous_hour not found")
        
        # Check summary
        summary = result.get("summary", "")
        if "TICK MICROSTRUCTURE" in summary:
            print("\n" + "="*80)
            print("SUMMARY CHECK")
            print("="*80)
            print("OK: TICK MICROSTRUCTURE found in summary")
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
            print("\n" + "="*80)
            print("SUMMARY CHECK")
            print("="*80)
            print("WARNING: TICK MICROSTRUCTURE NOT in summary")
            if tick_metrics:
                print("   BUT tick_metrics IS in data - formatting may have failed")
        
        # Save full response to file
        output_file = project_root / "test_xau_raw_response.json"
        def convert_to_json(obj):
            if isinstance(obj, dict):
                return {k: convert_to_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_json(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj
        
        json_result = convert_to_json(result)
        with open(output_file, 'w') as f:
            json.dump(json_result, f, indent=2, default=str)
        
        print(f"\n📄 Full response saved to: {output_file}")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_xau_raw_response())

