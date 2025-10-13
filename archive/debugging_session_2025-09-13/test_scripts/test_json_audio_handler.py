#!/usr/bin/env python3
"""
Test JSON Audio Handler

Tests the simple WebSocket handler's ability to process JSON audio data
sent by the Discord bot.
"""

import asyncio
import websockets
import json
import base64
import logging
import sys
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AudioTest")

async def test_json_audio_processing():
    """Test JSON audio processing with simple WebSocket handler"""
    
    # Start the simple WebSocket server first
    sys.path.append('src')
    from core.simple_websocket_handler import simple_audio_handler
    
    logger.info("🚀 Starting simple audio WebSocket server...")
    server_started = await simple_audio_handler.start_server()
    
    if not server_started:
        logger.error("❌ Failed to start server")
        return
    
    try:
        # Connect as a client
        uri = "ws://127.0.0.1:8002"
        logger.info(f"🔌 Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to server")
            
            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            logger.info(f"📨 Welcome: {welcome_data.get('message', 'No message')}")
            
            # Create test audio data (1 second of 16kHz mono sine wave)
            duration = 1.0  # seconds
            sample_rate = 16000
            frequency = 440  # A4 note
            
            # Generate sine wave
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_np = np.sin(2 * np.pi * frequency * t)
            
            # Convert to 16-bit PCM
            audio_pcm = (audio_np * 32767).astype(np.int16)
            audio_bytes = audio_pcm.tobytes()
            
            logger.info(f"🎵 Generated test audio: {len(audio_bytes)} bytes, {sample_rate}Hz")
            
            # Create JSON message in Discord bot format
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            message = {
                "type": "audio_input",
                "data": audio_b64,
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm16",
                "chunk_id": 1,
                "duration": duration,
                "size": len(audio_bytes),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            logger.info("📤 Sending test audio message...")
            await websocket.send(json.dumps(message))
            logger.info("✅ Message sent successfully!")
            
            # Wait for responses
            try:
                for i in range(3):  # Wait for up to 3 responses
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    response_data = json.loads(response)
                    response_type = response_data.get("type", "unknown")
                    
                    logger.info(f"📨 Response #{i+1}: {response_type}")
                    
                    if response_type == "transcription":
                        transcription = response_data.get("text", "")
                        logger.info(f"🗣️ Transcription: '{transcription}'")
                    elif response_type == "ai_response":
                        ai_text = response_data.get("text", "")
                        logger.info(f"🤖 AI Response: '{ai_text[:100]}...'")
                    elif response_type == "error":
                        error = response_data.get("error", "")
                        logger.error(f"❌ Server error: {error}")
                        break
                        
            except asyncio.TimeoutError:
                logger.info("⏰ No more responses (timeout)")
                
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Stop the server
        logger.info("🛑 Stopping server...")
        await simple_audio_handler.stop_server()
        logger.info("✅ Test completed")

if __name__ == "__main__":
    asyncio.run(test_json_audio_processing())