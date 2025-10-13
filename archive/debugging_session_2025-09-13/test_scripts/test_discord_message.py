#!/usr/bin/env python3
"""Test Discord-compatible message format with Pipecat"""

import asyncio
import websockets
import json
import base64
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_discord_messages():
    """Test sending Discord-compatible JSON messages to Pipecat"""
    
    uri = "ws://172.20.104.13:8001"
    logger.info(f"Testing Discord JSON format with {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=5) as websocket:
            logger.info("✅ Connected to Pipecat!")
            
            # Send start message (like Discord bot does)
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(start_msg))
            logger.info(f"📤 Sent start: {start_msg}")
            
            # Send fake audio data (like Discord bot does)
            fake_audio = b'\x00' * 1600  # 100ms of silence at 16kHz
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(fake_audio).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(audio_msg))
            logger.info(f"📤 Sent audio: {len(fake_audio)} bytes")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                logger.info(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                logger.info("⏱️ No response received")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_discord_messages())