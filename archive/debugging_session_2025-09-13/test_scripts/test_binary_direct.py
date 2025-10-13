#!/usr/bin/env python3
"""
Test sending BINARY audio directly to Pipecat (no JSON)
"""

import asyncio
import websockets
import json
import logging
import struct
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_binary_audio():
    """Test sending binary audio directly to Pipecat"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to Pipecat WebSocket")
            
            # Generate actual audio data (not silence) - a simple tone
            sample_rate = 16000
            duration = 1.0  # 1 second
            frequency = 440  # A4 note
            
            # Generate sine wave
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_float = 0.3 * np.sin(2 * np.pi * frequency * t)  # 30% volume
            audio_int16 = (audio_float * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            logger.info(f"🎵 Generated {duration}s sine wave at {frequency}Hz: {len(audio_bytes)} bytes")
            
            # Send the binary audio data directly
            await websocket.send(audio_bytes)
            logger.info("📤 Sent BINARY audio data to Pipecat")
            
            # Wait for responses
            logger.info("👂 Listening for responses...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    logger.info(f"📥 Received: {type(response)}, length={len(response) if hasattr(response, '__len__') else 'N/A'}")
                    
                    if isinstance(response, str):
                        try:
                            data = json.loads(response)
                            logger.info(f"   → JSON type: {data.get('type', 'unknown')}")
                            if data.get('type') == 'transcription':
                                logger.info(f"   → TRANSCRIPTION: '{data.get('text', '')}'")
                        except:
                            logger.info(f"   → Text: {response[:200]}...")
                    elif isinstance(response, bytes):
                        logger.info(f"   → Binary: {len(response)} bytes")
                        
            except asyncio.TimeoutError:
                logger.info("⏰ No responses after 10 seconds")
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_binary_audio())