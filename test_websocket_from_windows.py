#!/usr/bin/env python3
"""
Test WebSocket connection from Windows Python to WSL service
"""

import asyncio
import websockets
import json

async def test_connection():
    """Test WebSocket connection"""
    url = "ws://192.168.50.60:8002"
    
    try:
        print(f"Testing connection to {url}...")
        
        async with websockets.connect(url, timeout=10) as websocket:
            print("Connected successfully!")
            
            # Send a test message
            test_message = {
                "type": "test",
                "message": "Hello from Windows!"
            }
            
            await websocket.send(json.dumps(test_message))
            print("Message sent")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"Received response: {response}")
            except asyncio.TimeoutError:
                print("No response received (timeout)")
                
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    print("Testing WebSocket connection from Windows to WSL...")
    asyncio.run(test_connection())