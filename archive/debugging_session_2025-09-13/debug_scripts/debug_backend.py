#!/usr/bin/env python3
"""
Maximum debug backend to see what's happening with WebSocket connections
"""

import asyncio
import logging
import sys

# Enable ALL Pipecat debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    stream=sys.stdout
)

# Enable specific logger debugging
loggers_to_debug = [
    'pipecat.transports.websocket.server',
    'pipecat.transports.websocket', 
    'pipecat.pipeline',
    'pipecat.serializers',
    'src.core.json_frame_serializer',
    'src.core.logging_serializer_wrapper',
    'src.core.debug_websocket_server',
    'src.core.debug_websocket_transport',
]

for logger_name in loggers_to_debug:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

from src.core.robust_pipecat_pipeline import robust_voice_pipeline

async def main():
    print("🔧 Starting MAXIMUM DEBUG backend...")
    
    pipeline = robust_voice_pipeline
    await pipeline.start()
    
    print("✅ Debug backend running - check for detailed logs")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Stopping debug backend...")
        await pipeline.stop()

if __name__ == "__main__":
    asyncio.run(main())