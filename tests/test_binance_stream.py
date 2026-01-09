"""
Quick test to verify Binance WebSocket connectivity.
No account or API key required!
"""

import asyncio
import json
import websockets
from datetime import datetime
import sys
import codecs

# Fix Windows console encoding for emoji
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def test_binance_stream():
    """
    Test Binance public WebSocket stream.
    Prints 5 BTC price updates then exits.
    """
    uri = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
    
    print("🔌 Connecting to Binance WebSocket...")
    print(f"📡 Stream: {uri}")
    print("=" * 60)
    
    try:
        async with websockets.connect(uri) as ws:
            print("✅ Connected successfully!")
            print("\n📊 Streaming BTC/USDT prices (1-minute klines)...\n")
            
            for i in range(5):  # Get 5 updates
                message = await ws.recv()
                data = json.loads(message)
                
                if 'k' in data:
                    kline = data['k']
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    print(f"[{timestamp}] Update #{i+1}")
                    print(f"  💰 Price: ${float(kline['c']):,.2f}")
                    print(f"  📈 High:  ${float(kline['h']):,.2f}")
                    print(f"  📉 Low:   ${float(kline['l']):,.2f}")
                    print(f"  📊 Volume: {float(kline['v']):.2f} BTC")
                    print()
                    
        print("✅ Test completed successfully!")
        print("\n🎉 You can connect to Binance - no account needed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPossible issues:")
        print("  - Check internet connection")
        print("  - Firewall blocking WebSocket")
        print("  - Install websockets: pip install websockets")

if __name__ == "__main__":
    print("🧪 Testing Binance WebSocket Connection\n")
    asyncio.run(test_binance_stream())

