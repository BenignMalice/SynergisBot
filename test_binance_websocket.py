"""
Test direct Binance WebSocket connection
"""

import asyncio
import websockets
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_binance_connection():
    """Test direct connection to Binance aggTrades stream"""
    uri = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"
    
    print("\n" + "="*70)
    print("TESTING DIRECT BINANCE WEBSOCKET CONNECTION")
    print("="*70)
    print(f"URI: {uri}")
    print(f"Timeout: 10 seconds")
    print()
    
    try:
        print("Attempting connection...")
        start_time = time.time()
        
        # Test with timeout
        try:
            ws = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=10.0
            )
            async with ws:
                elapsed = time.time() - start_time
                print(f"[PASS] Connected in {elapsed:.2f} seconds!")
                
                # Try to receive a message
                print("Waiting for trade message...")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    print(f"[PASS] Received trade message!")
                    print(f"   Trade ID: {data.get('a', 'N/A')}")
                    print(f"   Price: ${float(data.get('p', 0)):,.2f}")
                    print(f"   Quantity: {float(data.get('q', 0)):.6f}")
                    print(f"   Side: {'SELL' if data.get('m', False) else 'BUY'}")
                    return True
                except asyncio.TimeoutError:
                    print("[WARN] Connected but no message received in 5s")
                    return True  # Connection works, just no message
                except Exception as e:
                    print(f"[WARN] Error receiving message: {e}")
                    return True  # Connection works
                    
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"[FAIL] Connection timeout after {elapsed:.2f} seconds")
            print("   Possible causes:")
            print("   - Network/firewall blocking WebSocket")
            print("   - Binance API issues")
            print("   - DNS resolution problems")
            return False
            
    except websockets.exceptions.InvalidURI as e:
        print(f"[FAIL] Invalid URI: {e}")
        return False
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[FAIL] Connection closed: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_event_loop():
    """Test event loop status"""
    print("\n" + "="*70)
    print("TESTING EVENT LOOP STATUS")
    print("="*70)
    
    try:
        loop = asyncio.get_event_loop()
        print(f"Event loop: {loop}")
        print(f"Is running: {loop.is_running()}")
        print(f"Current task: {asyncio.current_task()}")
        
        # Test if we can create and run a simple task
        async def simple_task():
            await asyncio.sleep(0.1)
            return "Task completed"
        
        result = await simple_task()
        print(f"[PASS] Simple task executed: {result}")
        return True
    except Exception as e:
        print(f"[FAIL] Event loop error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("BINANCE WEBSOCKET DIAGNOSTICS")
    print("="*70)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Event loop
    loop_ok = await test_event_loop()
    
    # Test 2: Direct connection
    connection_ok = await test_binance_connection()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Event Loop: {'[PASS]' if loop_ok else '[FAIL]'}")
    print(f"Direct Connection: {'[PASS]' if connection_ok else '[FAIL]'}")
    
    if connection_ok:
        print("\n[SUCCESS] Binance WebSocket is accessible!")
        print("   The issue is likely in the application code, not network connectivity.")
    else:
        print("\n[FAIL] Binance WebSocket is not accessible.")
        print("   Check network/firewall settings.")
    
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())

