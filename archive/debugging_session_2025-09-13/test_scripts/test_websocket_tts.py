#!/usr/bin/env python3
"""Test WebSocket TTS functionality"""

import asyncio
import json
import base64
import websockets
import wave

async def test_websocket_tts():
    """Test TTS through WebSocket"""
    uri = "ws://localhost:8002"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Wait for welcome message
            welcome = await websocket.recv()
            print(f"📨 Received: {json.loads(welcome)['type']}")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": asyncio.get_event_loop().time()
            }
            await websocket.send(json.dumps(start_msg))
            print("📤 Sent start message")
            
            # Create some dummy audio data (silence) to trigger TTS response
            import numpy as np
            
            # Generate 2 seconds of silence at 16kHz
            sample_rate = 16000
            duration = 2.0
            samples = int(sample_rate * duration)
            
            # Add a bit of noise so it's not completely silent
            audio_data = np.random.randint(-100, 100, samples, dtype=np.int16)
            audio_bytes = audio_data.tobytes()
            
            # Send audio input to trigger response
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm",
                "chunk_id": "test_001",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await websocket.send(json.dumps(audio_msg))
            print("📤 Sent audio input")
            
            # Listen for responses
            responses = 0
            while responses < 5:  # Wait for a few responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    msg_type = data.get("type")
                    
                    print(f"📨 Received {msg_type}")
                    
                    if msg_type == "audio_output":
                        # We got TTS audio!
                        audio_b64 = data.get("data", "")
                        if audio_b64:
                            audio_data = base64.b64decode(audio_b64)
                            print(f"🔊 Received {len(audio_data)} bytes of TTS audio")
                            
                            # Save to file
                            with open("websocket_tts_test.wav", "wb") as f:
                                f.write(audio_data)
                            print("💾 Saved as websocket_tts_test.wav")
                            break
                    elif msg_type == "transcription":
                        print(f"📝 Transcription: {data.get('text', 'N/A')}")
                    elif msg_type == "text_output":
                        print(f"💬 AI Response: {data.get('text', 'N/A')}")
                    
                    responses += 1
                    
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for response")
                    break
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_tts())