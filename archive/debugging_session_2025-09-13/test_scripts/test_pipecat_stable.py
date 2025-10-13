#!/usr/bin/env python3
"""
Test Pipecat 0.0.83 stable version compatibility
"""

import asyncio
import logging
from pipecat.transports.websocket.server import WebsocketServerTransport, WebsocketServerParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_pipeline():
    """Test basic pipeline creation with stable Pipecat"""
    try:
        # Create WebSocket transport
        transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
            ),
            host="0.0.0.0",
            port=8001
        )
        
        # Create simple pipeline
        pipeline = Pipeline([
            transport.input(),
            transport.output()
        ])
        
        logger.info("✅ Pipeline created successfully with Pipecat 0.0.83")
        
        # Create and start task
        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        logger.info("🚀 Starting pipeline task...")
        
        # Start the pipeline briefly to test it works
        start_task = asyncio.create_task(runner.run(task))
        
        # Let it run for a couple seconds
        await asyncio.sleep(2)
        
        logger.info("✅ Pipeline started successfully!")
        
        # Cancel the task
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass
        logger.info("🛑 Pipeline stopped")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pipeline test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_basic_pipeline())
    if result:
        print("🎉 Pipecat 0.0.83 compatibility test PASSED!")
    else:
        print("💥 Pipecat 0.0.83 compatibility test FAILED!")