#!/usr/bin/env python3
"""Test connection to Pipecat pipeline on port 8001"""

import asyncio
import websockets
import json
import base64
import logging
import numpy as np
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_test_audio(duration=0.5, sample_rate=16000):
    """Generate test audio signal"""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, False)
    # Generate a sine wave at 440Hz
    audio = np.sin(2 * np.pi * 440 * t) * 0.5
    # Convert to int16 PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    return audio_int16.tobytes()

async def test_pipecat_connection():
    """Test connection to Pipecat WebSocket"""
    
    uri = "ws://localhost:8001"
    logger.info(f"Testing connection to {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=10) as websocket:
            logger.info("✅ Connected to Pipecat WebSocket!")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent start message")
            
            # Generate and send test audio
            test_audio = generate_test_audio()
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(test_audio).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            
            await websocket.send(json.dumps(audio_msg))
            logger.info(f"📤 Sent audio data: {len(test_audio)} bytes")
            
            # Listen for responses
            logger.info("👂 Listening for responses...")
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(message)
                        msg_type = data.get("type")
                        logger.info(f"📨 Received: {msg_type}")
                        
                        if msg_type == "transcription":
                            logger.info(f"🗣️ Transcription: {data.get('text', '')}")
                        elif msg_type == "text_output":
                            logger.info(f"💬 Response: {data.get('text', '')}")
                        elif msg_type == "audio_output":
                            audio_len = len(data.get('data', ''))
                            logger.info(f"🔊 Audio response: {audio_len} chars")
                        
                    except asyncio.TimeoutError:
                        logger.info("⏱️ No response within 5 seconds")
                        break
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("🔌 Connection closed by server")
            
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_pipecat_connection())