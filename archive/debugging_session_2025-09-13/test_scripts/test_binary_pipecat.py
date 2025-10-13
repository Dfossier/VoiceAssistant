#!/usr/bin/env python3
"""
Test what format the default Pipecat WebSocket expects
Based on documentation, it should be binary Protobuf frames
"""
import asyncio
import websockets
import logging
import struct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PipecatBinaryTest")

async def test_binary_connection():
    """Test binary connection to Pipecat WebSocket"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected successfully!")
            
            # Test 1: Send binary audio frame
            logger.info("🧪 Test 1: Sending binary audio data...")
            
            # Create sample 16-bit PCM audio (16kHz, mono, 100ms)
            sample_rate = 16000
            duration_ms = 100
            samples = int(sample_rate * duration_ms / 1000)
            audio_data = b'\x00\x01' * samples  # Simple test pattern
            
            try:
                await websocket.send(audio_data)
                logger.info("✅ Binary audio sent successfully")
                
                # Try to receive response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    if isinstance(response, bytes):
                        logger.info(f"📨 Binary response: {len(response)} bytes")
                    else:
                        logger.info(f"📨 Text response: {response[:100]}...")
                except asyncio.TimeoutError:
                    logger.info("⏰ No response (timeout)")
                    
            except Exception as e:
                logger.error(f"❌ Binary send failed: {e}")
            
            # Test 2: Send structured binary message (minimal Protobuf-like)
            logger.info("🧪 Test 2: Sending structured binary message...")
            
            # Create a minimal binary frame structure
            # Format: [type:1][length:4][data:length]
            frame_type = 1  # Assume 1 = audio
            data_length = len(audio_data)
            binary_frame = struct.pack('>BI', frame_type, data_length) + audio_data
            
            try:
                await websocket.send(binary_frame)
                logger.info("✅ Structured binary sent successfully")
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    if isinstance(response, bytes):
                        logger.info(f"📨 Binary response: {len(response)} bytes")
                    else:
                        logger.info(f"📨 Text response: {response[:100]}...")
                except asyncio.TimeoutError:
                    logger.info("⏰ No response (timeout)")
                    
            except Exception as e:
                logger.error(f"❌ Structured binary send failed: {e}")
                
            # Test 3: Send empty message to see what happens
            logger.info("🧪 Test 3: Sending empty message...")
            try:
                await websocket.send(b"")
                logger.info("✅ Empty message sent successfully")
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    if isinstance(response, bytes):
                        logger.info(f"📨 Binary response: {len(response)} bytes")
                    else:
                        logger.info(f"📨 Text response: {response[:100]}...")
                except asyncio.TimeoutError:
                    logger.info("⏰ No response (timeout)")
                    
            except Exception as e:
                logger.error(f"❌ Empty message send failed: {e}")
                
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_binary_connection())