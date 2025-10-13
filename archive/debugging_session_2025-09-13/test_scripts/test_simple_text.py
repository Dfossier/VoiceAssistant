#!/usr/bin/env python3
"""
Simple test to send just text messages to Pipecat and see if JSON serializer processes them
"""
import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleTextTest")

async def test_text_messages():
    """Test simple text messages"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected successfully!")
            
            # Test different text message formats
            messages = [
                # Format 1: Simple text message
                {"type": "text", "text": "Hello, this is a test message"},
                
                # Format 2: Start frame (might be needed to initialize pipeline)
                {"type": "start", "audio_in_sample_rate": 16000, "audio_out_sample_rate": 16000},
                
                # Format 3: Another text message after start
                {"type": "text", "text": "Second test message after start frame"},
                
                # Format 4: End frame
                {"type": "end"}
            ]
            
            for i, message in enumerate(messages, 1):
                logger.info(f"📤 Sending message #{i}: {message}")
                
                try:
                    await websocket.send(json.dumps(message))
                    logger.info(f"✅ Message #{i} sent successfully")
                    
                    # Wait for response
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        logger.info(f"📨 Response #{i}: {response[:200]}...")
                    except asyncio.TimeoutError:
                        logger.info(f"⏰ No response #{i} within 5 seconds")
                        
                except Exception as e:
                    logger.error(f"❌ Message #{i} failed: {e}")
                
                # Small delay between messages
                await asyncio.sleep(1)
            
            logger.info("🔚 All messages sent - keeping connection open for 5 seconds...")
            await asyncio.sleep(5)
                
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_text_messages())