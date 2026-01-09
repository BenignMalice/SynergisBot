"""
Check trade_history status in order flow service
"""

import sys
import time
from datetime import datetime

def check_trade_history():
    """Check if trade_history has data"""
    print("\n" + "="*70)
    print("TRADE HISTORY STATUS CHECK")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        from desktop_agent import registry
        
        if not hasattr(registry, 'order_flow_service'):
            print("[FAIL] Order flow service not in registry")
            return False
        
        service = registry.order_flow_service
        if not service:
            print("[FAIL] Order flow service is None")
            return False
        
        print("[PASS] Order flow service found in registry")
        print(f"   Running: {getattr(service, 'running', False)}")
        print(f"   Symbols: {getattr(service, 'symbols', [])}")
        
        # Check whale detector
        if hasattr(service, 'analyzer') and hasattr(service.analyzer, 'whale_detector'):
            whale_detector = service.analyzer.whale_detector
            trade_history = getattr(whale_detector, 'trade_history', {})
            
            print(f"\n   Trade History Status:")
            if trade_history:
                total_trades = 0
                for symbol, trades in trade_history.items():
                    if hasattr(trades, '__len__'):
                        trade_count = len(trades)
                        total_trades += trade_count
                        print(f"   - {symbol}: {trade_count} trades")
                        
                        # Show sample trade if available
                        if trade_count > 0 and hasattr(trades, '__getitem__'):
                            try:
                                sample = trades[-1] if trade_count > 0 else None
                                if sample:
                                    print(f"     Latest: {sample.get('side', 'N/A')} ${sample.get('usd_value', 0):,.2f} @ ${sample.get('price', 0):,.2f}")
                            except:
                                pass
                    else:
                        print(f"   - {symbol}: Unknown format")
                
                if total_trades > 0:
                    print(f"\n[PASS] Trade history populated: {total_trades} total trades")
                    return True
                else:
                    print(f"\n[WARN] Trade history exists but empty")
                    return False
            else:
                print(f"   - [FAIL] trade_history is empty")
                print(f"   - Available symbols: {list(trade_history.keys())}")
                return False
        else:
            print("[FAIL] Whale detector not found in analyzer")
            return False
        
        # Check stream tasks
        if hasattr(service, 'trades_stream'):
            trades_stream = service.trades_stream
            print(f"\n   AggTrades Stream Status:")
            print(f"   - Running: {getattr(trades_stream, 'running', False)}")
            
            tasks = getattr(trades_stream, 'tasks', [])
            if tasks:
                active_tasks = [t for t in tasks if not t.done()]
                print(f"   - Total tasks: {len(tasks)}")
                print(f"   - Active tasks: {len(active_tasks)}")
                
                for i, task in enumerate(tasks):
                    status = "ACTIVE" if not task.done() else ("DONE" if not task.cancelled() else "CANCELLED")
                    exc = task.exception() if task.done() else None
                    print(f"   - Task {i+1}: {status}" + (f" (Error: {exc})" if exc else ""))
            else:
                print(f"   - [WARN] No tasks found")
        
    except ImportError as e:
        print(f"[FAIL] Cannot import desktop_agent.registry: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Error checking service: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_order_flow_metrics():
    """Check if order flow metrics are available"""
    print("\n" + "="*70)
    print("ORDER FLOW METRICS CHECK")
    print("="*70)
    
    try:
        from desktop_agent import registry
        
        if not hasattr(registry, 'order_flow_service') or not registry.order_flow_service:
            print("[FAIL] Order flow service not available")
            return False
        
        service = registry.order_flow_service
        
        # Try to get buy/sell pressure (requires trade_history)
        try:
            pressure = service.get_buy_sell_pressure("BTCUSDT", window=30)
            if pressure:
                print("[PASS] Buy/sell pressure available")
                print(f"   Buy volume: {pressure.get('buy_volume', 0):,.2f}")
                print(f"   Sell volume: {pressure.get('sell_volume', 0):,.2f}")
                print(f"   Delta: {pressure.get('buy_volume', 0) - pressure.get('sell_volume', 0):,.2f}")
                print(f"   Dominant side: {pressure.get('dominant_side', 'N/A')}")
                return True
            else:
                print("[WARN] Buy/sell pressure returned None")
                return False
        except Exception as e:
            print(f"[WARN] Error getting pressure: {e}")
            return False
        
    except Exception as e:
        print(f"[FAIL] Error checking metrics: {e}")
        return False

def main():
    """Main check function"""
    print("\n" + "="*70)
    print("BINANCE STREAM STATUS CHECK")
    print("="*70)
    
    # Check trade history
    history_ok = check_trade_history()
    
    # Check metrics
    metrics_ok = check_order_flow_metrics()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Trade History: {'[PASS]' if history_ok else '[FAIL]'}")
    print(f"Order Flow Metrics: {'[PASS]' if metrics_ok else '[FAIL]'}")
    
    if history_ok and metrics_ok:
        print("\n[SUCCESS] Order flow system is working correctly!")
        print("   - Trade data is being collected")
        print("   - Metrics are available")
        print("   - Order flow plans can now execute")
    elif history_ok:
        print("\n[PARTIAL] Trade data collected but metrics not available yet")
        print("   - May need more time for data accumulation")
    else:
        print("\n[FAIL] Trade data not being collected")
        print("   - Check connection logs")
        print("   - Verify WebSocket streams are connected")
    
    print("="*70)

if __name__ == "__main__":
    main()

