#!/usr/bin/env python3
"""
Test connection from Windows to WSL2 backend
"""

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_windows_to_wsl2():
    """Test connection from Windows to WSL2"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"Testing connection from Windows to WSL2: {uri}")
        async with websockets.connect(uri, open_timeout=10) as websocket:
            logger.info("✅ Connection successful!")
            
            # Try to send a simple message
            await websocket.send("test")
            logger.info("📤 Sent test message")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                logger.info("⏰ No response received (expected for Protobuf server)")
                
        logger.info("✅ Test completed successfully")
                
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_windows_to_wsl2())