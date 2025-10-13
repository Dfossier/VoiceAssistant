#!/usr/bin/env python3
"""
Test the fixed Pipecat pipeline with custom JSON serializer
"""
import asyncio
import json
import base64
import websockets
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PipecatFormatTest")

async def test_fixed_pipeline():
    """Test the fixed pipeline with Discord bot format"""
    uri = "ws://172.20.104.13:8001"  # WSL2 IP address
    
    # Generate real audio data (sine wave for testing)
    sample_rate = 16000
    duration = 2.0  # 2 seconds
    frequency = 440  # A4 note
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = (0.5 * np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
    audio_bytes = audio_data.tobytes()
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to fixed pipeline!")
            
            # Test 1: Send audio input (Discord bot format)
            logger.info("🎤 Sending audio input...")
            audio_message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm16"
            }
            await websocket.send(json.dumps(audio_message))
            
            # Listen for responses
            logger.info("👂 Listening for responses...")
            timeout_count = 0
            while timeout_count < 3:  # Wait for up to 3 timeouts
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    
                    if response_data.get("type") == "text":
                        logger.info(f"📝 Transcription: {response_data['text']}")
                    elif response_data.get("type") == "audio_output":
                        logger.info(f"🔊 Received audio response ({len(response_data['data'])} bytes)")
                    else:
                        logger.info(f"📨 Response: {response_data}")
                        
                    timeout_count = 0  # Reset timeout counter on successful receive
                    
                except asyncio.TimeoutError:
                    logger.info("⏰ Waiting for more responses...")
                    timeout_count += 1
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON response")
            
            # Test 2: Send text input
            logger.info("💬 Sending text input...")
            text_message = {
                "type": "text_input", 
                "text": "Hello, can you hear me?"
            }
            await websocket.send(json.dumps(text_message))
            
            # Listen for text response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                logger.info(f"📨 Text response: {response_data}")
            except asyncio.TimeoutError:
                logger.info("⏰ No text response received")
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_fixed_pipeline())