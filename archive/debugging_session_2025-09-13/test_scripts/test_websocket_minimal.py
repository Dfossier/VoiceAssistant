#!/usr/bin/env python
"""
Minimal WebSocket server test for Pipecat 0.0.83
Tests basic connectivity without complex processing
"""

import asyncio
import logging
from loguru import logger

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.frames.frames import TextFrame
    from pipecat.transports.websocket.server import (
        WebsocketServerParams,
        WebsocketServerTransport,
    )
    print("✅ Pipecat imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you have activated the virtual environment:")
    print("  source venv/bin/activate")
    exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def main():
    """Run minimal WebSocket server"""
    
    logger.info("Starting minimal Pipecat WebSocket server...")
    
    try:
        # Create transport with minimal configuration
        transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                audio_in_enabled=False,  # Disable audio for simplicity
                audio_out_enabled=False,
                vad_enabled=False,
            ),
            host="127.0.0.1",  # Localhost only for testing
            port=8765,
        )
        logger.info("✅ Transport created")
        
        # Create minimal pipeline
        pipeline = Pipeline([
            transport.input(),
            transport.output(),
        ])
        logger.info("✅ Pipeline created")
        
        # Create task
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=False,
            ),
        )
        logger.info("✅ Task created")
        
        # Event handlers
        @transport.event_handler("on_websocket_ready")
        async def on_ready(transport):
            logger.info("🟢 WebSocket server is ready!")
            logger.info("Connect to: ws://127.0.0.1:8765")
            logger.info("Press Ctrl+C to stop")
        
        @transport.event_handler("on_client_connected")
        async def on_connected(transport, websocket):
            logger.info(f"👤 Client connected: {websocket.remote_address}")
            # Send a welcome message
            welcome = TextFrame(text="Welcome to Pipecat WebSocket Server!")
            await task.queue_frames([welcome])
        
        @transport.event_handler("on_client_disconnected")
        async def on_disconnected(transport, websocket):
            logger.info(f"👋 Client disconnected: {websocket.remote_address}")
        
        # Create and run pipeline runner
        runner = PipelineRunner()
        logger.info("🚀 Starting pipeline runner...")
        
        await runner.run(task)
        
    except KeyboardInterrupt:
        logger.info("\n⏹️  Shutting down server...")
    except Exception as e:
        logger.error(f"❌ Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    print("\n" + "="*50)
    print("Pipecat WebSocket Server Test (Minimal)")
    print("="*50 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()