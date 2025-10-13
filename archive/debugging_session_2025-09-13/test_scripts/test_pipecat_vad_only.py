#!/usr/bin/env python3
"""
Test Pipecat VAD functionality with minimal setup
This isolates the VAD testing from the heavy model loading
"""

import asyncio
import logging
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.transports.websocket.server import WebsocketServerTransport, WebsocketServerParams
from src.core.json_frame_serializer import JSONFrameSerializer
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import Frame, InputAudioRawFrame, TextFrame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleFrameLogger(FrameProcessor):
    """Simple processor that logs frames"""
    
    async def process_frame(self, frame: Frame, direction):
        logger.info(f"🔄 Processing frame: {type(frame).__name__}")
        if isinstance(frame, InputAudioRawFrame):
            logger.info(f"🎵 Audio frame: {len(frame.audio)} bytes, {frame.sample_rate}Hz")
        elif isinstance(frame, TextFrame):
            logger.info(f"📝 Text frame: {frame.text}")
        
        await self.push_frame(frame, direction)

async def test_minimal_vad_pipeline():
    """Test minimal Pipecat pipeline with VAD"""
    
    logger.info("🚀 Creating minimal VAD pipeline...")
    
    # Voice Activity Detection
    vad_params = VADParams(
        confidence=0.6,
        start_secs=0.3,
        stop_secs=0.5,
        min_volume=0.6
    )
    vad = SileroVADAnalyzer(
        sample_rate=16000,
        params=vad_params
    )
    
    # WebSocket transport with JSON serializer
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=False,  # Disable audio output for testing
            vad_analyzer=vad,
            audio_in_sample_rate=16000,
            serializer=JSONFrameSerializer(),
        ),
        host="0.0.0.0",
        port=8001
    )
    
    # Simple frame logger
    frame_logger = SimpleFrameLogger()
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),
        frame_logger,
        transport.output()
    ])
    
    # Create task with disabled idle timeout
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
            enable_usage_metrics=False
        ),
        idle_timeout_secs=None  # Disable idle timeout
    )
    
    # Add connection handlers
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, websocket):
        logger.info(f"🔌 Client connected: {websocket.remote_address}")
        
    @transport.event_handler("on_client_disconnected") 
    async def on_disconnected(transport, websocket):
        logger.info(f"👋 Client disconnected: {websocket.remote_address}")
        
    @transport.event_handler("on_websocket_ready")
    async def on_ready(transport):
        logger.info("🟢 WebSocket server ready on ws://0.0.0.0:8001")
    
    # Run pipeline
    runner = PipelineRunner()
    
    logger.info("✅ Starting minimal VAD pipeline...")
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(test_minimal_vad_pipeline())