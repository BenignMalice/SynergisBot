"""
Diagnose Binance WebSocket connection issues
"""

import websocket
import json
import threading
import time
import ssl

def test_binance_websocket():
    print('🔍 Testing Binance WebSocket connection...')
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            print(f'✅ Received data: {data.get("stream", "unknown")}')
            if 'data' in data:
                print(f'   Price: {data["data"].get("c", "N/A")}')
            ws.close()
        except Exception as e:
            print(f'❌ Error parsing message: {e}')
    
    def on_error(ws, error):
        print(f'❌ WebSocket error: {error}')
    
    def on_close(ws, close_status_code, close_msg):
        print('🔌 WebSocket closed')
    
    def on_open(ws):
        print('✅ WebSocket connection opened')
        # Subscribe to BTCUSDT ticker
        subscribe_msg = {
            'method': 'SUBSCRIBE',
            'params': ['btcusdt@ticker'],
            'id': 1
        }
        ws.send(json.dumps(subscribe_msg))
        print('📡 Subscribed to BTCUSDT ticker')
    
    # Test connection
    ws_url = 'wss://stream.binance.com:9443/ws/btcusdt@ticker'
    print(f'🔗 Connecting to: {ws_url}')
    
    try:
        ws = websocket.WebSocketApp(ws_url,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        
        # Run for 5 seconds
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        time.sleep(5)
        ws.close()
        print('🏁 Test completed')
        
    except Exception as e:
        print(f'❌ Connection failed: {e}')

if __name__ == "__main__":
    test_binance_websocket()
