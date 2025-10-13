#!/usr/bin/env python3
"""Test Faster-Whisper directly on port 8001"""

import asyncio
import websockets
import json
import base64
import logging
import sounddevice as sd
import numpy as np
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def capture_audio_sample(duration=3, sample_rate=16000):
    """Capture real audio from microphone"""
    logger.info(f"🎤 Recording {duration} seconds of audio...")
    
    # Record audio
    audio_data = sd.rec(int(duration * sample_rate), 
                       samplerate=sample_rate, 
                       channels=1, 
                       dtype=np.float32)
    sd.wait()  # Wait for recording to complete
    
    # Convert to int16 PCM
    audio_int16 = (audio_data.flatten() * 32767).astype(np.int16)
    return audio_int16.tobytes()

async def test_whisper_port8001():
    """Test Faster-Whisper on port 8001"""
    
    uri = "ws://localhost:8001"
    logger.info(f"Testing Faster-Whisper on {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=10) as websocket:
            logger.info("✅ Connected to port 8001!")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent start message")
            
            # Capture real audio
            audio_bytes = capture_audio_sample(duration=3)
            
            # Send audio data
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            
            await websocket.send(json.dumps(audio_msg))
            logger.info(f"📤 Sent real audio: {len(audio_bytes)} bytes")
            
            # Listen for responses
            logger.info("👂 Listening for Faster-Whisper response...")
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "transcription":
                            transcription = data.get('text', '')
                            logger.info(f"🗣️ Faster-Whisper transcribed: '{transcription}'")
                        elif msg_type == "text_output":
                            response = data.get('text', '')
                            logger.info(f"💬 AI Response: '{response[:100]}...'")
                        elif msg_type == "audio_output":
                            audio_len = len(data.get('data', ''))
                            logger.info(f"🔊 TTS audio received: {audio_len} chars")
                        else:
                            logger.info(f"📨 Received: {msg_type}")
                        
                    except asyncio.TimeoutError:
                        logger.info("⏱️ No more responses")
                        break
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("🔌 Connection closed")
            
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    logger.info("🎯 Testing if Faster-Whisper is actually working on port 8001")
    logger.info("Speak clearly when prompted for recording!")
    asyncio.run(test_whisper_port8001())