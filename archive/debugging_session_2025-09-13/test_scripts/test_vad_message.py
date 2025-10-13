#!/usr/bin/env python3
"""Test VAD with audio that should trigger speech detection"""

import asyncio
import websockets
import json
import base64
import logging
import numpy as np
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_test_audio(frequency=440, duration=1.0, sample_rate=16000):
    """Generate a sine wave audio signal"""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, False)
    # Generate sine wave
    audio = np.sin(2 * np.pi * frequency * t)
    # Convert to int16 PCM
    audio_int16 = (audio * 16000).astype(np.int16)
    return audio_int16.tobytes()

async def test_vad_audio():
    """Test VAD with actual audio signal"""
    
    uri = "ws://172.20.104.13:8003"
    logger.info(f"Testing VAD with {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=5) as websocket:
            logger.info("✅ Connected to VAD test server!")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent start message")
            
            # Generate test audio - sine wave that should trigger VAD
            test_audio = generate_test_audio(frequency=440, duration=0.5, sample_rate=16000)
            
            # Send audio in chunks like Discord bot would
            chunk_size = 1600  # 100ms chunks
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i+chunk_size]
                
                audio_msg = {
                    "type": "audio_input",
                    "data": base64.b64encode(chunk).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm",
                    "timestamp": datetime.now(timezone.utc).timestamp()
                }
                await websocket.send(json.dumps(audio_msg))
                
                if i == 0:
                    logger.info(f"📤 Started sending audio chunks ({len(test_audio)} bytes total)")
                
                # Small delay between chunks
                await asyncio.sleep(0.1)
            
            logger.info("📤 Finished sending audio chunks")
            
            # Wait a moment for VAD processing
            await asyncio.sleep(2.0)
            
            # Send silence to trigger stop
            silence = b'\x00' * 1600
            for _ in range(10):  # Send 1 second of silence
                silence_msg = {
                    "type": "audio_input",
                    "data": base64.b64encode(silence).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm",
                    "timestamp": datetime.now(timezone.utc).timestamp()
                }
                await websocket.send(json.dumps(silence_msg))
                await asyncio.sleep(0.1)
            
            logger.info("📤 Sent silence to trigger VAD stop")
            
            # Wait for final processing
            await asyncio.sleep(2.0)
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_vad_audio())