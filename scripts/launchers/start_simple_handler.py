#!/usr/bin/env python3
"""
Start the SimpleAudioWebSocketHandler directly
"""

import asyncio
import logging
from src.core.simple_websocket_handler import start_simple_audio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 Starting SimpleAudioWebSocketHandler on port 8002...")
    try:
        success = await start_simple_audio_server()
        if success:
            logger.info("✅ SimpleAudioWebSocketHandler started successfully!")
            # Keep running
            while True:
                await asyncio.sleep(1)
        else:
            logger.error("❌ Failed to start SimpleAudioWebSocketHandler")
    except Exception as e:
        logger.error(f"❌ Exception starting handler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())