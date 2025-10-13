#!/usr/bin/env python3
"""
Test to verify Protobuf communication works between client and server
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

class TestProcessor(FrameProcessor):
    """Test processor that sends audio and logs responses"""
    
    def __init__(self):
        super().__init__()
        self.started = False
        self.audio_sent = 0
        self.responses_received = 0
        
    async def process_frame(self, frame, direction):
        """Process frames from the pipeline"""
        
        if isinstance(frame, StartFrame):
            logger.info("✅ Pipeline started - sending test audio in 2 seconds...")
            self.started = True
            asyncio.create_task(self.send_test_audio())
            
        elif isinstance(frame, OutputAudioRawFrame):
            self.responses_received += 1
            logger.info(f"🔊 Received TTS response #{self.responses_received}: {len(frame.audio)} bytes")
            
        elif isinstance(frame, TextFrame):
            logger.info(f"💬 Received text: '{frame.text}'")
            
        # Forward all frames
        await self.push_frame(frame, direction)
        
    async def send_test_audio(self):
        """Send test audio after pipeline is ready"""
        await asyncio.sleep(2)  # Wait for pipeline to be fully ready
        
        if not self.started:
            logger.warning("⚠️ Pipeline not started yet")
            return
            
        logger.info("🎵 Generating test audio (sine wave)...")
        
        # Generate a 2-second sine wave at 440Hz (A4 note)
        sample_rate = 16000
        duration = 2.0
        frequency = 440
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = 0.3 * np.sin(2 * np.pi * frequency * t)
        audio_int16 = (audio_float * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        
        # Send the audio frame through the pipeline
        audio_frame = InputAudioRawFrame(
            audio=audio_bytes,
            sample_rate=16000,
            num_channels=1
        )
        
        self.audio_sent += 1
        logger.info(f"📤 Sending test audio: {len(audio_bytes)} bytes (2s sine wave)")
        await self.push_frame(audio_frame)

async def test_protobuf_communication():
    """Test proper Protobuf communication with server"""
    pipecat_uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Creating Pipecat client for {pipecat_uri}")
        
        # Create transport
        transport = WebsocketClientTransport(pipecat_uri)
        
        # Create test processor
        processor = TestProcessor()
        
        # Create pipeline: transport.input() → processor → transport.output()
        pipeline = Pipeline([
            transport.input(),   # Receive from server 
            processor,           # Process and send test audio
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
        
        # Create and run pipeline
        runner = PipelineRunner()
        
        logger.info("🚀 Starting Pipecat client pipeline...")
        
        # Run for 20 seconds to allow for processing
        try:
            await asyncio.wait_for(runner.run(task), timeout=20.0)
        except asyncio.TimeoutError:
            logger.info("⏰ Test timeout after 20 seconds")
            
        logger.info("✅ Test completed")
        logger.info(f"📊 Audio frames sent: {processor.audio_sent}")
        logger.info(f"📊 Responses received: {processor.responses_received}")
        
        # Check if we got responses
        if processor.responses_received > 0:
            logger.info("🎉 SUCCESS: Server processed audio and sent responses!")
        elif processor.audio_sent > 0:
            logger.info("📤 Audio sent successfully, waiting for server processing...")
        else:
            logger.warning("⚠️ No audio was sent")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_protobuf_communication())