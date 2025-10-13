#!/usr/bin/env python3
"""
Test what JSON format Pipecat actually expects
"""

import asyncio
import json
import base64
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pipecat_json():
    """Test various JSON formats to see what Pipecat accepts"""
    
    uri = "ws://localhost:8001"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"✅ Connected to {uri}")
            
            # Test 1: Send a start message (like Discord bot does)
            start_msg = {
                "type": "start",
                "timestamp": 1234567890.0
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent start message")
            
            # Wait for any response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                logger.info(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                logger.info("⏱️ No response to start message")
            
            # Test 2: Send audio_input message
            test_audio = b'\x00\x01' * 1600  # 3200 bytes of test audio
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(test_audio).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm",
                "timestamp": 1234567891.0
            }
            await websocket.send(json.dumps(audio_msg))
            logger.info("📤 Sent audio_input message")
            
            # Test 3: Try just sending raw JSON without type
            raw_msg = {"hello": "world"}
            await websocket.send(json.dumps(raw_msg))
            logger.info("📤 Sent raw JSON message")
            
            # Keep connection open and listen
            logger.info("👂 Listening for responses...")
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.info(f"📥 Received: {response}")
                except asyncio.TimeoutError:
                    logger.info("⏱️ No more responses")
                    break
                    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipecat_json())