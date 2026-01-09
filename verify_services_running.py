"""
Verify Binance and Order Flow Services are Running
Checks service status after restart
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try to activate venv if available
venv_path = project_root / '.venv'
if venv_path.exists():
    if sys.platform == 'win32':
        venv_python = venv_path / 'Scripts' / 'python.exe'
    else:
        venv_python = venv_path / 'bin' / 'python'
    if venv_python.exists():
        # Note: This won't change the current process, but helps with imports
        pass

async def verify_services():
    """Verify both Binance and Order Flow services are running"""
    
    print("=" * 80)
    print("SERVICE VERIFICATION - Binance & Order Flow Services")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        from desktop_agent import registry
        
        # ====================================================================
        # 1. BINANCE SERVICE CHECK
        # ====================================================================
        print("[1/2] BINANCE SERVICE")
        print("-" * 80)
        
        if not hasattr(registry, 'binance_service'):
            print("   [ERROR] binance_service attribute not found in registry")
            print("   → Service was never initialized")
        elif registry.binance_service is None:
            print("   [NOT INITIALIZED] binance_service is None")
            print("   → Service initialization failed or was not attempted")
            print("   → Check desktop_agent.log for initialization errors")
        else:
            binance = registry.binance_service
            print(f"   [OK] [INITIALIZED] Binance service object exists")
            
            # Check if running
            if hasattr(binance, 'running'):
                if binance.running:
                    print(f"   [OK] [RUNNING] Service is active")
                    
                    # Check symbols
                    if hasattr(binance, 'symbols'):
                        symbols = binance.symbols
                        if symbols:
                            print(f"   [OK] [SYMBOLS] Streaming: {', '.join(s.upper() for s in symbols)}")
                        else:
                            print(f"   [WARN] [SYMBOLS] No symbols configured")
                    else:
                        print(f"   [WARN] [SYMBOLS] Cannot check symbols (attribute missing)")
                    
                    # Check stream
                    if hasattr(binance, 'stream') and binance.stream:
                        print(f"   [OK] [STREAM] Stream object exists")
                        if hasattr(binance.stream, 'connections'):
                            conn_count = len(binance.stream.connections) if binance.stream.connections else 0
                            print(f"   [OK] [CONNECTIONS] {conn_count} active connection(s)")
                    else:
                        print(f"   [WARN] [STREAM] Stream object not found")
                    
                    # Try to get status
                    try:
                        if hasattr(binance, 'get_feed_health'):
                            health = binance.get_feed_health()
                            if health and 'sync' in health:
                                healthy_count = sum(1 for h in health['sync'].values() 
                                                   if isinstance(h, dict) and h.get('status') == 'healthy')
                                total_count = len(health['sync'])
                                print(f"   [OK] [HEALTH] {healthy_count}/{total_count} symbol(s) healthy")
                    except Exception as e:
                        print(f"   [WARN] [HEALTH] Could not check health: {e}")
                    
                else:
                    print(f"   [ERROR] [STOPPED] Service exists but is not running")
                    print(f"   → Service was initialized but start() was not called or failed")
                    print(f"   → Check desktop_agent.log for start errors")
            else:
                print(f"   ⚠️  [UNKNOWN] Service exists but 'running' attribute not found")
        
        print()
        
        # ====================================================================
        # 2. ORDER FLOW SERVICE CHECK
        # ====================================================================
        print("[2/2] ORDER FLOW SERVICE")
        print("-" * 80)
        
        if not hasattr(registry, 'order_flow_service'):
            print("   [ERROR] order_flow_service attribute not found in registry")
            print("   -> Service was never initialized")
        elif registry.order_flow_service is None:
            print("   [NOT INITIALIZED] order_flow_service is None")
            
            # Check if Binance is required
            if hasattr(registry, 'binance_service') and registry.binance_service:
                if hasattr(registry.binance_service, 'running') and registry.binance_service.running:
                    print("   [WARNING] Binance is running but Order Flow is not initialized")
                    print("   -> Order Flow initialization may have failed")
                    print("   -> Check desktop_agent.log for Order Flow initialization errors")
                else:
                    print("   [INFO] Binance service is not running")
                    print("   -> Order Flow requires Binance to be running first")
            else:
                print("   [INFO] Binance service is not available")
                print("   -> Order Flow requires Binance service to be initialized first")
        else:
            ofs = registry.order_flow_service
            print(f"   [OK] [INITIALIZED] Order Flow service object exists")
            
            # Check if running
            if hasattr(ofs, 'running'):
                if ofs.running:
                    print(f"   [OK] [RUNNING] Service is active")
                    
                    # Check symbols
                    if hasattr(ofs, 'symbols'):
                        symbols = ofs.symbols
                        if symbols:
                            print(f"   [OK] [SYMBOLS] Monitoring: {', '.join(s.upper() for s in symbols)}")
                        else:
                            print(f"   [WARN] [SYMBOLS] No symbols configured")
                    else:
                        print(f"   [WARN] [SYMBOLS] Cannot check symbols (attribute missing)")
                    
                    # Check if it has order flow data
                    try:
                        if hasattr(ofs, 'get_order_flow_signal'):
                            # Try to get signal for BTCUSDT
                            signal = ofs.get_order_flow_signal('btcusdt')
                            if signal:
                                print(f"   [OK] [DATA] Order flow data available")
                            else:
                                print(f"   [WARN] [DATA] Order flow data not yet available")
                    except Exception as e:
                        print(f"   [WARN] [DATA] Could not check order flow data: {e}")
                    
                else:
                    print(f"   [ERROR] [STOPPED] Service exists but is not running")
                    print(f"   -> Service was initialized but start() was not called or failed")
                    print(f"   -> Check desktop_agent.log for start errors")
            else:
                print(f"   [WARN] [UNKNOWN] Service exists but 'running' attribute not found")
        
        print()
        
        # ====================================================================
        # 3. SUMMARY
        # ====================================================================
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        binance_ok = (hasattr(registry, 'binance_service') and 
                     registry.binance_service is not None and
                     hasattr(registry.binance_service, 'running') and
                     registry.binance_service.running)
        
        order_flow_ok = (hasattr(registry, 'order_flow_service') and 
                        registry.order_flow_service is not None and
                        hasattr(registry.order_flow_service, 'running') and
                        registry.order_flow_service.running)
        
        if binance_ok:
            print("[OK] Binance Service: RUNNING")
        else:
            print("[ERROR] Binance Service: NOT RUNNING")
        
        if order_flow_ok:
            print("[OK] Order Flow Service: RUNNING")
        else:
            print("[ERROR] Order Flow Service: NOT RUNNING")
        
        print()
        
        if binance_ok and order_flow_ok:
            print("[SUCCESS] All services are running correctly!")
            print("   -> Order flow conditions in auto-execution plans will work")
        elif binance_ok and not order_flow_ok:
            print("[WARNING] Binance is running but Order Flow is not")
            print("   -> Order flow conditions will NOT work")
            print("   -> Check logs for Order Flow initialization errors")
        elif not binance_ok:
            print("[ERROR] Binance service is not running")
            print("   -> Order flow conditions will NOT work")
            print("   -> Check desktop_agent.log for initialization errors")
        
        print()
        print("=" * 80)
        print()
        print("Next Steps:")
        print("  1. If services are not running, check desktop_agent.log")
        print("  2. Look for these log messages:")
        print("     - '✅ Binance Service initialized and started'")
        print("     - '✅ Order Flow Service initialized'")
        print("  3. If errors found, check the initialization code in desktop_agent.py")
        print("  4. Services should auto-start when desktop_agent.py runs")
        print()
        
    except ImportError as e:
        print(f"[ERROR] Failed to import desktop_agent: {e}")
        print("   -> desktop_agent.py may not be running")
        print("   -> Or the module path is incorrect")
        print("   -> Try running from venv: .venv\\Scripts\\python.exe verify_services_running.py")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_services())
