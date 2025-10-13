#!/usr/bin/env python3
"""
Minimal Pipecat WebSocket server test to isolate the connection issue
"""

import asyncio
import logging
from pipecat.transports.websocket.server import WebsocketServerInputTransport
from pipecat.transports.websocket.server import WebsocketServerParams
from src.core.json_frame_serializer import JSONFrameSerializer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_minimal_pipecat():
    """Test minimal Pipecat WebSocket setup"""
    try:
        logger.info("🔧 Creating minimal Pipecat WebSocket server...")
        
        # Create transport with minimal configuration
        transport = WebsocketServerInputTransport(
            params=WebsocketServerParams(
                serializer=JSONFrameSerializer(),
                audio_in_enabled=False,  # Minimal setup
                audio_out_enabled=False,
            ),
            host="0.0.0.0",
            port=8002  # Different port to avoid conflict
        )
        
        logger.info("✅ WebSocket transport created")
        
        # Create minimal pipeline
        pipeline = Pipeline([
            transport.input(),
        ])
        
        # Create task and runner
        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        logger.info("🚀 Starting Pipecat WebSocket server on 0.0.0.0:8002...")
        await runner.run(task)
        
    except Exception as e:
        logger.error(f"❌ Pipecat WebSocket test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_minimal_pipecat())