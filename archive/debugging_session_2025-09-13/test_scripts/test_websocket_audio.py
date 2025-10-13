#!/usr/bin/env python3
"""
Test script to send audio frames to the backend WebSocket server
Simulates what the Discord bot would send
"""

import asyncio
import websockets
import json
import base64
import numpy as np

async def test_audio_pipeline():
    # Try the fallback simple WebSocket server
    uri = "ws://127.0.0.1:8002"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Send start frame
            start_msg = json.dumps({"type": "start"})
            await websocket.send(start_msg)
            print("✅ Sent start frame")
            
            # Generate and send test audio (1 second of silence at 16kHz)
            sample_rate = 16000
            duration = 1.0
            num_samples = int(sample_rate * duration)
            
            # Create a simple sine wave for testing
            frequency = 440  # A4 note
            t = np.linspace(0, duration, num_samples)
            audio_data = (0.3 * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
            
            # Convert to bytes
            audio_bytes = audio_data.tobytes()
            
            # Create audio message
            audio_msg = json.dumps({
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": sample_rate,
                "channels": 1
            })
            
            await websocket.send(audio_msg)
            print(f"✅ Sent audio frame: {len(audio_bytes)} bytes")
            
            # Listen for responses
            print("📡 Listening for responses...")
            timeout = 10  # 10 seconds timeout
            
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    msg = json.loads(response) if isinstance(response, str) else response
                    print(f"📥 Received: {msg.get('type', 'unknown')} - {str(msg)[:100]}...")
                    
            except asyncio.TimeoutError:
                print(f"⏰ Timeout after {timeout} seconds")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_audio_pipeline())