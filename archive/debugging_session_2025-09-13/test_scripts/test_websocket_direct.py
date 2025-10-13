#!/usr/bin/env python3
"""
Direct WebSocket test to see what Pipecat actually receives
"""

import asyncio
import websockets
import json
import base64
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_websocket():
    """Test direct connection to Pipecat WebSocket"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to Pipecat WebSocket")
            
            # Send start frame
            start_message = {
                "type": "start",
                "audio_in_sample_rate": 16000,
                "audio_out_sample_rate": 16000,
                "allow_interruptions": True
            }
            
            await websocket.send(json.dumps(start_message))
            logger.info("📤 Sent StartFrame")
            
            # Generate test audio data (silence)
            import struct
            sample_rate = 16000
            duration = 0.5  # 0.5 seconds
            samples = int(sample_rate * duration)
            audio_data = struct.pack('<' + 'h' * samples, *([0] * samples))
            
            # Test 1: Send JSON audio message
            audio_message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            await websocket.send(json.dumps(audio_message))
            logger.info(f"📤 Sent JSON audio message: {len(audio_data)} bytes")
            
            # Test 2: Send raw binary audio
            await websocket.send(audio_data)
            logger.info(f"📤 Sent BINARY audio data: {len(audio_data)} bytes")
            
            # Wait for responses
            logger.info("👂 Listening for responses...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"📥 Received response: {type(response)}, length={len(response) if hasattr(response, '__len__') else 'N/A'}")
                    
                    if isinstance(response, str):
                        try:
                            data = json.loads(response)
                            logger.info(f"   → JSON response type: {data.get('type', 'unknown')}")
                            if data.get('type') == 'transcription':
                                logger.info(f"   → TRANSCRIPTION: '{data.get('text', '')}'")
                        except:
                            logger.info(f"   → Non-JSON string: {response[:100]}...")
                    elif isinstance(response, bytes):
                        logger.info(f"   → Binary response: {len(response)} bytes")
                        
            except asyncio.TimeoutError:
                logger.info("⏰ No more responses after 5 seconds")
                
    except Exception as e:
        logger.error(f"❌ WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())