#!/usr/bin/env python3
"""
Simple connection test to debug WebSocket issues
"""

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test basic WebSocket connection"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"Connecting to {uri}...")
        async with websockets.connect(uri, timeout=10) as websocket:
            logger.info("✅ Connection established!")
            
            # Try to send a simple message
            await websocket.send("test")
            logger.info("📤 Sent test message")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                logger.info("⏰ No response received")
                
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())