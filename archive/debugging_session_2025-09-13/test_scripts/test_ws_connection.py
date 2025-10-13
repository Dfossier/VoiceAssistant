#!/usr/bin/env python3
"""Test WebSocket connection from Windows to WSL2"""

import asyncio
import websockets
import sys

async def test_connection(url):
    """Test WebSocket connection"""
    print(f"Testing connection to {url}...")
    try:
        # Try to connect with a timeout
        async with websockets.connect(url, timeout=5) as ws:
            print("✅ Connection successful!")
            
            # Try to ping
            await ws.ping()
            print("✅ Ping successful!")
            
            # Send a test message
            test_msg = '{"type": "test", "data": "hello"}'
            await ws.send(test_msg)
            print(f"✅ Sent test message: {test_msg}")
            
            # Wait for any response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2)
                print(f"✅ Received response: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response received (timeout)")
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

if __name__ == "__main__":
    # Test different URLs
    urls = [
        "ws://172.20.104.13:8001",
        "ws://localhost:8001", 
        "ws://127.0.0.1:8001",
        "ws://172.20.104.13:8002",  # Fallback port
        "ws://localhost:8002"
    ]
    
    for url in urls:
        print(f"\n{'='*50}")
        asyncio.run(test_connection(url))