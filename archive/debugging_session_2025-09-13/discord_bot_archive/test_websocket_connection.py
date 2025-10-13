#!/usr/bin/env python3
"""
Test WebSocket connection to Pipecat backend
"""
import asyncio
import websockets
import json
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WSTest")

async def test_pipecat_connection():
    """Test connection to Audio WebSocket server"""
    # Try Pipecat port first, then fallback port
    for uri in ["ws://127.0.0.1:8001", "ws://127.0.0.1:8002"]:
        logger.info(f"🔌 Testing connection to {uri}...")
        
        try:
            return await test_connection(uri)
        except Exception as e:
            logger.warning(f"❌ Failed to connect to {uri}: {e}")
            continue
    
    logger.error("❌ Failed to connect to any voice server")
    return False

async def test_connection(uri):
    """Test connection to specific URI"""
    
    async with websockets.connect(uri) as websocket:
        logger.info("✅ Connected successfully!")
        
        # Wait for welcome message
        try:
            welcome = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome)
            logger.info(f"📨 Welcome: {welcome_data.get('message', 'No message')}")
        except asyncio.TimeoutError:
            logger.info("⏰ No welcome message (may be Pipecat)")
        
        # Test sending a sample audio message (WAV format like Discord bot)
        import wave
        import io
        
        # Create a 1-second WAV file with silence
        sample_rate = 16000
        duration = 1.0
        frames = int(sample_rate * duration)
        
        # Create WAV data in memory
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            
            # Write silence
            silence = b'\x00' * (frames * 2)  # 2 bytes per 16-bit sample
            wav.writeframes(silence)
        
        wav_data = wav_io.getvalue()
        
        message = {
            "type": "audio_input",
            "data": base64.b64encode(wav_data).decode('utf-8'),
            "sample_rate": sample_rate,
            "channels": 1,
            "format": "wav",
            "chunk_id": 1,
            "duration": duration,
            "size": len(wav_data)
        }
        
        logger.info(f"📤 Sending WAV audio message ({len(wav_data)} bytes)...")
        await websocket.send(json.dumps(message))
        logger.info("✅ Message sent successfully!")
        
        # Wait for responses
        try:
            for i in range(3):
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                response_type = response_data.get("type", "unknown")
                logger.info(f"📨 Response #{i+1}: {response_type}")
                
                if response_type == "transcription":
                    text = response_data.get("text", "")
                    logger.info(f"🗣️ Transcription: '{text}'")
                elif response_type == "ai_response":
                    text = response_data.get("text", "")
                    logger.info(f"🤖 AI: '{text[:100]}...'")
                elif response_type == "error":
                    error = response_data.get("error", "")
                    logger.error(f"❌ Error: {error}")
                    break
                    
        except asyncio.TimeoutError:
            logger.info("⏰ No more responses (timeout)")
        
        return True
        
if __name__ == "__main__":
    asyncio.run(test_pipecat_connection())