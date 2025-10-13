#!/usr/bin/env python3
"""
Test Pipecat VAD with proper frame handling
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
    TextFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TranscriptionFrame
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VADFrameLogger(FrameProcessor):
    """Frame processor that logs VAD events and audio"""
    
    def __init__(self):
        super().__init__()
        self._speaking = False
        self._frame_count = 0
        
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        self._frame_count += 1
        
        # Log different frame types
        if isinstance(frame, UserStartedSpeakingFrame):
            self._speaking = True
            logger.info("🗣️ User STARTED speaking")
            
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._speaking = False
            logger.info("🤐 User STOPPED speaking")
            
        elif isinstance(frame, InputAudioRawFrame):
            # Log audio info but not every frame
            if self._frame_count % 10 == 0:  # Log every 10th frame
                logger.info(f"🎵 Audio: {len(frame.audio)} bytes, speaking={self._speaking}")
                
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"📝 Transcription: {frame.text}")
            
        elif isinstance(frame, TextFrame):
            logger.info(f"💬 Text: {frame.text}")
        
        # Always push the frame downstream
        await self.push_frame(frame, direction)

async def test_vad_pipeline():
    """Test Pipecat pipeline with VAD properly configured"""
    
    logger.info("🚀 Creating VAD pipeline with proper configuration...")
    
    # Voice Activity Detection with reasonable settings
    vad_params = VADParams(
        confidence=0.5,      # Lower = more sensitive
        start_secs=0.2,      # 200ms of speech to start
        stop_secs=0.8,       # 800ms of silence to stop
        min_volume=0.5       # Reasonable volume threshold
    )
    vad = SileroVADAnalyzer(
        sample_rate=16000,
        params=vad_params
    )
    logger.info("✅ Silero VAD configured")
    
    # WebSocket transport with VAD enabled
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            serializer=JSONFrameSerializer(),
        ),
        host="0.0.0.0",
        port=8001
    )
    
    # VAD frame logger
    vad_logger = VADFrameLogger()
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),   # WebSocket input with VAD
        vad_logger,          # Log VAD events
        transport.output()   # WebSocket output
    ])
    
    # Create task with proper settings
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
            enable_usage_metrics=False,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000
        ),
        idle_timeout_secs=None  # Disable idle timeout
    )
    
    # Add connection handlers
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, websocket):
        logger.info(f"🔌 Client connected: {websocket.remote_address}")
        # Client is responsible for sending StartFrame
        
    @transport.event_handler("on_client_disconnected") 
    async def on_disconnected(transport, websocket):
        logger.info(f"👋 Client disconnected: {websocket.remote_address}")
        
    @transport.event_handler("on_websocket_ready")
    async def on_ready(transport):
        logger.info("🟢 WebSocket server ready on ws://0.0.0.0:8001")
        logger.info("📌 Waiting for client to send StartFrame...")
    
    # Run pipeline
    runner = PipelineRunner()
    
    logger.info("✅ Starting VAD pipeline...")
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(test_vad_pipeline())