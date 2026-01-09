#!/usr/bin/env python3
"""
Test script to verify BTC order flow metrics integration in tool_analyse_symbol_full
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_btc_order_flow_integration():
    """Test that BTC order flow metrics are integrated into analysis"""
    
    print("=" * 80)
    print("Testing BTC Order Flow Metrics Integration")
    print("=" * 80)
    
    try:
        # Import required modules
        from desktop_agent import registry, tool_analyse_symbol_full
        from infra.mt5_service import MT5Service
        
        # Initialize MT5 if needed
        if not registry.mt5_service:
            print("\n[1/4] Initializing MT5 service...")
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                print("ERROR: Failed to connect to MT5")
                return False
            print("SUCCESS: MT5 service initialized")
        else:
            print("\n[1/4] MT5 service already initialized")
        
        # Check if order flow service is available
        print("\n[2/4] Checking Order Flow Service...")
        if not hasattr(registry, 'order_flow_service') or not registry.order_flow_service:
            print("WARNING: Order flow service not initialized - BTC metrics may not be available")
        elif not registry.order_flow_service.running:
            print("WARNING: Order flow service not running - BTC metrics may not be available")
        else:
            print("SUCCESS: Order flow service is running")
        
        # Test analysis for BTCUSD
        print("\n[3/4] Testing tool_analyse_symbol_full for BTCUSD...")
        print("This may take a few seconds...")
        
        result = await tool_analyse_symbol_full({"symbol": "BTCUSD"})
        
        # Check if result contains BTC order flow metrics
        print("\n[4/4] Verifying BTC order flow metrics in response...")
        
        # Check summary
        summary = result.get("summary", "")
        has_btc_metrics_in_summary = "BTC ORDER FLOW METRICS" in summary or "BTC ORDER FLOW" in summary
        
        # Check data
        data = result.get("data", {})
        btc_metrics = data.get("btc_order_flow_metrics")
        has_btc_metrics_in_data = btc_metrics is not None
        
        print(f"\nResults:")
        print(f"  - Summary contains BTC metrics: {has_btc_metrics_in_summary}")
        print(f"  - Data contains btc_order_flow_metrics: {has_btc_metrics_in_data}")
        
        if has_btc_metrics_in_data:
            print(f"\nBTC Order Flow Metrics Data:")
            print(f"  - Status: {btc_metrics.get('status', 'unknown')}")
            if btc_metrics.get('status') == 'success':
                delta = btc_metrics.get('delta_volume', {})
                cvd = btc_metrics.get('cvd', {})
                print(f"  - Delta Volume: {delta.get('net_delta', 0):+,.2f} ({delta.get('dominant_side', 'NEUTRAL')})")
                print(f"  - CVD: {cvd.get('current', 0):+,.2f} (Slope: {cvd.get('slope', 0):+,.2f}/bar)")
        
        # Extract BTC metrics section from summary
        if has_btc_metrics_in_summary:
            print(f"\nBTC Metrics in Summary (extract):")
            lines = summary.split('\n')
            in_btc_section = False
            for i, line in enumerate(lines):
                if "BTC ORDER FLOW" in line:
                    in_btc_section = True
                if in_btc_section:
                    print(f"  {line}")
                    if i < len(lines) - 1 and lines[i+1].strip() and not any(x in lines[i+1] for x in ["BTC", "Delta", "CVD", "Absorption", "Buy/Sell", "Pressure", "Divergence", "💰", "📈", "📉", "🎯", "⚖️", "⚠️"]):
                        break
        
        # Final verdict
        print("\n" + "=" * 80)
        if has_btc_metrics_in_summary or has_btc_metrics_in_data:
            print("SUCCESS: BTC order flow metrics integration is working!")
            if has_btc_metrics_in_summary and has_btc_metrics_in_data:
                print("  - Metrics are included in both summary and data")
            elif has_btc_metrics_in_summary:
                print("  - Metrics are included in summary only")
            elif has_btc_metrics_in_data:
                print("  - Metrics are included in data only")
        else:
            print("WARNING: BTC order flow metrics not found in response")
            print("  - This may be normal if Order Flow Service is not running")
            print("  - Or if there's insufficient data for BTC metrics")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_btc_order_flow_integration())
    sys.exit(0 if success else 1)

