#!/usr/bin/env python3
"""
Test using Pipecat's WebSocket client to understand proper protocol
"""

import asyncio
import logging
import numpy as np
from pipecat.transports.websocket.client import WebsocketClientTransport
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.frame_processor import FrameProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class TestAudioProcessor(FrameProcessor):
    """Processor that generates test audio and logs responses"""
    
    def __init__(self):
        super().__init__()
        self.audio_sent = 0
        self.responses_received = 0
        self.started = False
        
    async def process_frame(self, frame, direction):
        """Process incoming frames and log responses"""
        
        if isinstance(frame, StartFrame):
            logger.info("✅ Received StartFrame - pipeline ready")
            self.started = True
            # Send test audio after StartFrame
            asyncio.create_task(self.send_test_audio())
            
        elif isinstance(frame, OutputAudioRawFrame):
            self.responses_received += 1
            logger.info(f"🔊 Received TTS audio response #{self.responses_received}: {len(frame.audio)} bytes")
            
        elif isinstance(frame, TextFrame):
            logger.info(f"💬 Received text response: '{frame.text}'")
            
        # Forward the frame
        await self.push_frame(frame, direction)
        
    async def send_test_audio(self):
        """Send test audio frames after StartFrame"""
        if not self.started:
            logger.warning("⚠️ Cannot send audio - not started yet")
            return
            
        # Wait a bit for pipeline to be fully ready
        await asyncio.sleep(1)
        
        logger.info("🎵 Generating test audio...")
        
        # Generate a 1-second sine wave at 440Hz (A4 note)
        sample_rate = 16000
        duration = 1.0
        frequency = 440
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = 0.3 * np.sin(2 * np.pi * frequency * t)
        audio_int16 = (audio_float * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        
        # Send the audio frame
        audio_frame = InputAudioRawFrame(
            audio=audio_bytes,
            sample_rate=16000,
            num_channels=1
        )
        
        self.audio_sent += 1
        logger.info(f"📤 Sending test audio frame #{self.audio_sent}: {len(audio_bytes)} bytes")
        await self.push_frame(audio_frame)

async def test_pipecat_client():
    """Test Pipecat WebSocket client"""
    pipecat_uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Creating Pipecat WebSocket client for {pipecat_uri}")
        
        # Create transport
        transport = WebsocketClientTransport(pipecat_uri)
        
        # Create test processor
        processor = TestAudioProcessor()
        
        # Create pipeline: transport.input() → processor → transport.output()
        pipeline = Pipeline([
            transport.input(),   # Receive from server 
            processor,           # Process and generate test audio
            transport.output()   # Send to server
        ])
        
        # Create pipeline task
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=False,
                enable_usage_metrics=False
            )
        )
        
        # Create and start runner
        runner = PipelineRunner()
        
        logger.info("🚀 Starting Pipecat client pipeline...")
        
        # Run pipeline for a limited time to test
        try:
            await asyncio.wait_for(runner.run(task), timeout=15.0)
        except asyncio.TimeoutError:
            logger.info("⏰ Test timeout - stopping pipeline")
            
        # Stop pipeline
        try:
            await runner.stop()
        except Exception as e:
            logger.warning(f"⚠️ Error stopping runner: {e}")
        
        logger.info("✅ Test completed")
        logger.info(f"📊 Audio frames sent: {processor.audio_sent}")
        logger.info(f"📊 Responses received: {processor.responses_received}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipecat_client())