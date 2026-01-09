import asyncio
import websockets
import json

async def test_websocket_connection():
    try:
        print("Testing WebSocket connection to command hub...")
        async with websockets.connect('ws://localhost:8001/agent/connect') as ws:
            print("SUCCESS: WebSocket connected successfully")
            
            # Send authentication
            auth_msg = {"type": "auth", "secret": "phone_control_bearer_token_2025_v1_secure"}
            await ws.send(json.dumps(auth_msg))
            print("SUCCESS: Authentication message sent")
            
            # Wait for response
            response = await ws.recv()
            print(f"SUCCESS: Response received: {response}")
            
    except Exception as e:
        print(f"ERROR: WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
