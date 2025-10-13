#!/usr/bin/env python3
"""
Test Discord bot format with actual speech audio data
"""
import asyncio
import json
import base64
import websockets
import logging
import struct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SpeechTest")

async def test_with_speech_audio():
    """Test with more realistic speech-like audio data"""
    uri = "ws://127.0.0.1:8001"
    
    # Generate more realistic audio data (sine wave pattern simulating speech)
    sample_rate = 16000
    duration_seconds = 2.0  # 2 seconds of audio
    samples = int(sample_rate * duration_seconds)
    
    # Generate a simple sine wave at 440Hz (simulating speech frequencies)
    import math
    frequency = 440  # Hz
    audio_data = []
    for i in range(samples):
        # Create a sine wave with some variation
        t = i / sample_rate
        amplitude = 16000  # 16-bit PCM amplitude
        sample = int(amplitude * 0.3 * math.sin(2 * math.pi * frequency * t) * (1 + 0.1 * math.sin(2 * math.pi * 50 * t)))
        audio_data.append(sample)
    
    # Pack as 16-bit PCM
    audio_bytes = struct.pack('<' + 'h' * len(audio_data), *audio_data)
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected successfully!")
            
            # Send StartFrame
            start_message = {
                "type": "start",
                "audio_in_sample_rate": 16000,
                "audio_out_sample_rate": 16000,
                "allow_interruptions": True,
                "enable_metrics": True,
                "enable_usage_metrics": True
            }
            
            logger.info("📡 Sending StartFrame...")
            await websocket.send(json.dumps(start_message))
            await asyncio.sleep(1)
            
            # Send audio_input with speech-like data
            audio_message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm16"
            }
            
            logger.info(f"🎤 Sending speech audio: {len(audio_bytes)} bytes ({duration_seconds}s @ {sample_rate}Hz)...")
            await websocket.send(json.dumps(audio_message))
            
            # Listen longer for STT/LLM/TTS responses
            logger.info("👂 Listening for responses (STT → LLM → TTS)...")
            for i in range(10):  # Listen for up to 10 responses
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    
                    try:
                        data = json.loads(response)
                        msg_type = data.get('type', 'unknown')
                        logger.info(f"📨 Response #{i+1}: {msg_type}")
                        
                        if msg_type == 'transcription':
                            logger.info(f"   📝 Transcribed: '{data.get('text', '')}'")
                        elif msg_type == 'text':
                            logger.info(f"   💬 LLM said: '{data.get('text', '')}'")
                        elif msg_type == 'audio_output':
                            audio_len = len(base64.b64decode(data.get('data', ''))) if data.get('data') else 0
                            logger.info(f"   🔊 TTS audio: {audio_len} bytes")
                        else:
                            logger.info(f"   ℹ️  Other: {str(data)[:100]}...")
                            
                    except json.JSONDecodeError:
                        logger.info(f"   📦 Binary response: {len(response)} bytes")
                        
                except asyncio.TimeoutError:
                    logger.info("⏰ No more responses")
                    break
                    
            logger.info("✅ Speech test completed!")
                
    except Exception as e:
        logger.error(f"❌ Speech test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_with_speech_audio())