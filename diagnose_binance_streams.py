"""
Diagnose Binance WebSocket streams and trade data collection
"""

import asyncio
import json
import websockets
import time
import logging
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_aggTrades_connection(symbol: str = "btcusdt"):
    """Test direct connection to Binance aggTrades stream"""
    uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@aggTrade"
    
    print(f"\n{'='*70}")
    print(f"TESTING BINANCE AGGTRADES STREAM")
    print(f"{'='*70}")
    print(f"Symbol: {symbol.upper()}")
    print(f"URI: {uri}")
    print(f"\nConnecting...")
    
    try:
        async with websockets.connect(uri) as ws:
            print(f"[PASS] Connected to {symbol.upper()} aggTrades stream")
            
            trade_count = 0
            start_time = time.time()
            timeout = 30  # 30 seconds
            
            print(f"\nListening for trades (timeout: {timeout}s)...")
            
            try:
                async for message in ws:
                    if time.time() - start_time > timeout:
                        print(f"\n[INFO] Timeout reached ({timeout}s)")
                        break
                    
                    try:
                        data = json.loads(message)
                        
                        trade = {
                            "symbol": symbol.upper(),
                            "timestamp": time.time(),
                            "trade_id": data.get("a"),
                            "price": float(data.get("p", 0)),
                            "quantity": float(data.get("q", 0)),
                            "buyer_maker": data.get("m", False),
                            "trade_time": data.get("T"),
                            "event_time": data.get("E")
                        }
                        
                        trade["usd_value"] = trade["price"] * trade["quantity"]
                        trade["side"] = "SELL" if trade["buyer_maker"] else "BUY"
                        
                        trade_count += 1
                        
                        if trade_count == 1:
                            print(f"\n[PASS] First trade received!")
                            print(f"   Trade ID: {trade['trade_id']}")
                            print(f"   Price: ${trade['price']:,.2f}")
                            print(f"   Quantity: {trade['quantity']:.6f}")
                            print(f"   Side: {trade['side']}")
                            print(f"   USD Value: ${trade['usd_value']:,.2f}")
                        
                        if trade_count % 10 == 0:
                            elapsed = time.time() - start_time
                            rate = trade_count / elapsed if elapsed > 0 else 0
                            print(f"   [INFO] Received {trade_count} trades in {elapsed:.1f}s ({rate:.1f} trades/sec)")
                        
                        if trade_count >= 50:
                            print(f"\n[PASS] Received {trade_count} trades - stream is working!")
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Failed to parse message: {e}")
                    except Exception as e:
                        print(f"[ERROR] Error processing trade: {e}")
                        
            except asyncio.TimeoutError:
                print(f"\n[WARN] Connection timeout")
            except Exception as e:
                print(f"\n[ERROR] Error in message loop: {e}")
            
            if trade_count == 0:
                print(f"\n[FAIL] No trades received in {timeout}s")
                print("   Possible issues:")
                print("   - Network/firewall blocking WebSocket")
                print("   - Binance API issues")
                print("   - Symbol not trading")
            else:
                print(f"\n[PASS] Stream test completed: {trade_count} trades received")
                
    except websockets.exceptions.InvalidURI as e:
        print(f"[FAIL] Invalid URI: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[FAIL] Connection closed: {e}")
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        import traceback
        traceback.print_exc()

async def check_order_flow_service():
    """Check if order flow service is accessible and has data"""
    print(f"\n{'='*70}")
    print(f"CHECKING ORDER FLOW SERVICE")
    print(f"{'='*70}")
    
    try:
        from desktop_agent import registry
        
        if not hasattr(registry, 'order_flow_service'):
            print("[FAIL] Order flow service not in registry")
            return
        
        service = registry.order_flow_service
        if not service:
            print("[FAIL] Order flow service is None")
            return
        
        print(f"[PASS] Order flow service found in registry")
        print(f"   Running: {getattr(service, 'running', False)}")
        print(f"   Symbols: {getattr(service, 'symbols', [])}")
        
        if hasattr(service, 'analyzer') and hasattr(service.analyzer, 'whale_detector'):
            whale_detector = service.analyzer.whale_detector
            trade_history = getattr(whale_detector, 'trade_history', {})
            
            print(f"\n   Trade History Status:")
            if trade_history:
                for symbol, trades in trade_history.items():
                    trade_count = len(trades) if hasattr(trades, '__len__') else 0
                    print(f"   - {symbol}: {trade_count} trades")
            else:
                print(f"   - [FAIL] trade_history is empty")
                print(f"   - Available symbols: {list(trade_history.keys())}")
        
        # Check if streams are running
        if hasattr(service, 'trades_stream'):
            trades_stream = service.trades_stream
            print(f"\n   AggTrades Stream Status:")
            print(f"   - Running: {getattr(trades_stream, 'running', False)}")
            print(f"   - Tasks: {len(getattr(trades_stream, 'tasks', []))}")
            
            # Check if tasks are running
            tasks = getattr(trades_stream, 'tasks', [])
            if tasks:
                for i, task in enumerate(tasks):
                    print(f"   - Task {i+1}: {task.done()=}, {task.cancelled()=}")
        
    except ImportError:
        print("[FAIL] Cannot import desktop_agent.registry")
    except Exception as e:
        print(f"[FAIL] Error checking service: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run diagnostics"""
    print("\n" + "="*70)
    print("BINANCE STREAM DIAGNOSTICS")
    print("="*70)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Direct WebSocket connection
    await test_aggTrades_connection("btcusdt")
    
    # Test 2: Check order flow service
    await check_order_flow_service()
    
    print("\n" + "="*70)
    print("DIAGNOSTICS COMPLETE")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())

