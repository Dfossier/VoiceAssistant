#!/usr/bin/env python3
"""
Test raw WebSocket connection to see if server accepts connections
"""

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_raw_websocket():
    """Test raw WebSocket connection"""
    
    # Test both ports
    for port in [8001, 8002]:
        uri = f"ws://localhost:{port}"
        logger.info(f"\n🧪 Testing {uri}")
        
        try:
            websocket = await asyncio.wait_for(
                websockets.connect(uri),
                timeout=2.0
            )
            logger.info(f"✅ Connected to port {port}")
            
            # Try to receive any welcome message
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                logger.info(f"📥 Received welcome: {msg}")
            except asyncio.TimeoutError:
                logger.info("⏱️ No welcome message")
            
            await websocket.close()
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Connection timeout on port {port}")
        except Exception as e:
            logger.error(f"❌ Error on port {port}: {e}")

if __name__ == "__main__":
    asyncio.run(test_raw_websocket())