#!/usr/bin/env python3
"""Test WebSocket connection using WSL2 IP"""

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test WebSocket connection"""
    
    # Test port 8002 (SimpleAudioWebSocketHandler)
    uri = "ws://172.20.104.13:8002"
    logger.info(f"Testing {uri}...")
    
    try:
        websocket = await asyncio.wait_for(
            websockets.connect(uri),
            timeout=2.0
        )
        logger.info("✅ Connected!")
        
        # Try to receive welcome message
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            logger.info(f"📥 Received: {msg}")
        except asyncio.TimeoutError:
            logger.info("⏱️ No message received")
        
        await websocket.close()
        
    except asyncio.TimeoutError:
        logger.error("❌ Connection timeout")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    
    # Test port 8001 (Pipecat)
    uri = "ws://172.20.104.13:8001"
    logger.info(f"\nTesting {uri}...")
    
    try:
        websocket = await asyncio.wait_for(
            websockets.connect(uri),
            timeout=2.0
        )
        logger.info("✅ Connected to Pipecat!")
        
        # Send a test message
        test_msg = '{"type": "test", "data": "hello"}'
        await websocket.send(test_msg)
        logger.info(f"📤 Sent: {test_msg}")
        
        await websocket.close()
        
    except asyncio.TimeoutError:
        logger.error("❌ Connection timeout")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())