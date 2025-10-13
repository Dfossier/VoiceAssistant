#!/usr/bin/env python3
"""
Test the voice pipeline WebSocket connection
Simulates what the Discord bot would do
"""

import asyncio
import websockets
import json
import base64
import time

async def test_pipeline():
    uri = "ws://127.0.0.1:8001"  # Test with localhost first
    
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=10) as websocket:
            print(f"✅ Connected to backend!")
            
            # Send start frame to initialize pipeline
            start_frame = json.dumps({"type": "start"})
            await websocket.send(start_frame)
            print("✅ Sent StartFrame")
            
            # Wait a bit for initialization
            await asyncio.sleep(0.5)
            
            # Send some test audio frames
            for i in range(3):
                # Create 1 second of silence (16000 samples at 16kHz)
                audio_data = bytes(32000)  # 16000 samples * 2 bytes per sample
                
                audio_frame = json.dumps({
                    "type": "audio_input",
                    "data": base64.b64encode(audio_data).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1
                })
                
                await websocket.send(audio_frame)
                print(f"📡 Sent audio chunk #{i+1}: {len(audio_data)} bytes")
                await asyncio.sleep(1)
            
            # Listen for any responses
            print("\n📥 Waiting for responses...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    if isinstance(response, str):
                        msg = json.loads(response)
                        print(f"📨 Received: {msg.get('type', 'unknown')} - {str(msg)[:100]}...")
                    else:
                        print(f"📨 Received binary data: {len(response)} bytes")
            except asyncio.TimeoutError:
                print("⏰ No more responses (timeout)")
                
            # Send end frame
            end_frame = json.dumps({"type": "end"})
            await websocket.send(end_frame)
            print("✅ Sent EndFrame")
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False
        
    print("\n✅ Test completed successfully!")
    return True

if __name__ == "__main__":
    print("🧪 Testing Voice Pipeline WebSocket Connection")
    print("=" * 50)
    
    # Test using WSL2 IP (as Discord bot would)
    success = asyncio.run(test_pipeline())
    
    if success:
        print("\n✅ WebSocket pipeline is working!")
        print("The issue is likely with Discord voice connection, not the backend.")
    else:
        print("\n❌ WebSocket pipeline test failed!")
        print("Check if backend is running on port 8001")