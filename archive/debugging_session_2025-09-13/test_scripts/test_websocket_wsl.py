#!/usr/bin/env python3
"""
Test WebSocket connection using different addresses
"""

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_addresses():
    """Test WebSocket with different addresses"""
    
    addresses = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "172.20.104.13"  # WSL2 IP
    ]
    
    for addr in addresses:
        for port in [8001, 8002]:
            uri = f"ws://{addr}:{port}"
            logger.info(f"\n🧪 Testing {uri}")
            
            try:
                websocket = await asyncio.wait_for(
                    websockets.connect(uri),
                    timeout=1.0
                )
                logger.info(f"✅ Connected to {uri}")
                await websocket.close()
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout: {uri}")
            except Exception as e:
                logger.error(f"❌ Error {uri}: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_addresses())