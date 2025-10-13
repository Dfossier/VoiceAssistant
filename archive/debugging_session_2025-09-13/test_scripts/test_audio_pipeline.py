#!/usr/bin/env python3
"""
Test the audio pipeline to diagnose transcription issues
"""

import asyncio
import websockets
import json
import base64
import numpy as np
import time

async def test_audio_pipeline():
    """Send test audio to see if transcription works"""
    
    print("🧪 Testing audio pipeline...")
    
    # Connect to WebSocket
    uri = "ws://172.20.104.13:8001"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Send start frame
            start_frame = {
                "type": "start",
                "audio_in_sample_rate": 16000,
                "audio_out_sample_rate": 16000,
                "allow_interruptions": True,
                "enable_metrics": False,
                "enable_usage_metrics": False
            }
            
            await websocket.send(json.dumps(start_frame))
            print("✅ Sent start frame")
            
            # Create a simple test tone (1 second of 440Hz sine wave)
            sample_rate = 16000
            duration = 1.0
            frequency = 440
            t = np.linspace(0, duration, int(sample_rate * duration))
            
            # Generate sine wave
            amplitude = 0.3
            audio_data = (amplitude * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
            
            # Send test audio
            audio_message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_data.tobytes()).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            await websocket.send(json.dumps(audio_message))
            print(f"✅ Sent test audio: {len(audio_data) * 2} bytes")
            
            # Send silence to trigger VAD end
            silence = np.zeros(int(sample_rate * 0.5), dtype=np.int16)
            silence_message = {
                "type": "audio_input",
                "data": base64.b64encode(silence.tobytes()).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            await websocket.send(json.dumps(silence_message))
            print("✅ Sent silence to trigger VAD")
            
            # Listen for responses
            print("👂 Listening for responses...")
            start_time = time.time()
            timeout = 10  # 10 seconds
            
            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    if isinstance(response, str):
                        data = json.loads(response)
                        print(f"📥 Received: {data}")
                    else:
                        print(f"📥 Received binary: {len(response)} bytes")
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving: {e}")
                    break
                    
            print("✅ Test complete")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_audio_pipeline())