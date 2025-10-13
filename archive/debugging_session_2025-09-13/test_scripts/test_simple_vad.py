#!/usr/bin/env python3
"""
Simple Pipecat VAD test without complex logging
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
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    Frame, 
    InputAudioRawFrame, 
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptionFrame
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleVADLogger(FrameProcessor):
    """Simple processor that only logs VAD events"""
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, UserStartedSpeakingFrame):
            logger.info("🗣️ STARTED speaking!")
            
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info("🤐 STOPPED speaking!")
            
        elif isinstance(frame, InputAudioRawFrame):
            # Just count audio frames silently
            pass
        
        # Always push downstream
        await self.push_frame(frame, direction)

async def test_simple_vad():
    """Test simple VAD pipeline"""
    
    logger.info("🚀 Starting simple VAD test...")
    
    # VAD with sensitive settings
    vad_params = VADParams(
        confidence=0.3,      # Very sensitive
        start_secs=0.1,      # Quick to start
        stop_secs=0.5,       # Quick to stop
        min_volume=0.3       # Low volume threshold
    )
    vad = SileroVADAnalyzer(sample_rate=16000, params=vad_params)
    
    # Transport
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=False,
            vad_analyzer=vad,
            audio_in_sample_rate=16000,
            serializer=JSONFrameSerializer(),
        ),
        host="0.0.0.0",
        port=8003  # Different port to avoid conflicts
    )
    
    # Simple logger
    vad_logger = SimpleVADLogger()
    
    # Pipeline
    pipeline = Pipeline([
        transport.input(),
        vad_logger,
        transport.output()
    ])
    
    # Task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
        ),
        idle_timeout_secs=None
    )
    
    # Event handlers
    @transport.event_handler("on_websocket_ready")
    async def on_ready(transport):
        logger.info("🟢 Simple VAD ready on ws://0.0.0.0:8003")
    
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, websocket):
        logger.info(f"🔌 Client connected: {websocket.remote_address}")
        
    # Run
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(test_simple_vad())