#!/usr/bin/env python3
"""
Diagnostic Pipecat Pipeline to debug audio processing issues
"""

import asyncio
import logging
import os
from typing import Optional
import traceback

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.frames.frames import (
    Frame, AudioRawFrame, InputAudioRawFrame, OutputAudioRawFrame, 
    TextFrame, TranscriptionFrame, StartFrame, EndFrame,
    LLMMessagesUpdateFrame, MetricsFrame, ControlFrame, SystemFrame
)
from pipecat.transports.network.websocket_server import WebsocketServerTransport, WebsocketServerParams
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType

import json
import base64

logger = logging.getLogger(__name__)

class DiagnosticFrameLogger(FrameProcessor):
    """Comprehensive frame logger for debugging"""
    
    def __init__(self, logger_name="DiagnosticLogger"):
        super().__init__()
        self._logger_name = logger_name
        self._frame_count = 0
        self._audio_frames_received = 0
        self._text_frames_received = 0
        
    async def process_frame(self, frame: Frame, direction=None):
        """Log every frame with detailed information"""
        self._frame_count += 1
        frame_type = type(frame).__name__
        
        # Log frame details
        logger.info(f"🔍 [{self._logger_name}] Frame #{self._frame_count}: {frame_type}")
        
        if isinstance(frame, (AudioRawFrame, InputAudioRawFrame, OutputAudioRawFrame)):
            self._audio_frames_received += 1
            audio_len = len(frame.audio) if hasattr(frame, 'audio') else 0
            logger.info(f"   → Audio frame #{self._audio_frames_received}: {audio_len} bytes, "
                       f"sample_rate={getattr(frame, 'sample_rate', 'N/A')}, "
                       f"channels={getattr(frame, 'num_channels', 'N/A')}")
            
        elif isinstance(frame, TextFrame):
            self._text_frames_received += 1
            logger.info(f"   → Text frame: '{frame.text[:100]}...'")
            
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"   → 🎤 TRANSCRIPTION: '{frame.text}'")
            
        elif isinstance(frame, StartFrame):
            logger.info(f"   → StartFrame detected - pipeline starting")
            
        elif isinstance(frame, EndFrame):
            logger.info(f"   → EndFrame detected - pipeline ending")
            
        # Pass frame through
        await super().process_frame(frame, direction)

class DiagnosticJSONFrameSerializer(FrameSerializer):
    """JSON serializer with extensive logging"""
    
    def __init__(self):
        super().__init__()
        self._messages_received = 0
        self._messages_sent = 0
    
    @property
    def type(self) -> FrameSerializerType:
        return FrameSerializerType.TEXT
    
    def serialize(self, frame: Frame) -> str | None:
        """Serialize frames to JSON with logging"""
        try:
            self._messages_sent += 1
            
            if isinstance(frame, OutputAudioRawFrame):
                message = {
                    "type": "audio_output",
                    "data": base64.b64encode(frame.audio).decode('utf-8'),
                    "sample_rate": frame.sample_rate,
                    "channels": frame.num_channels,
                    "format": "pcm16"
                }
                logger.info(f"📤 Serializing audio output: {len(frame.audio)} bytes")
                return json.dumps(message)
                
            elif isinstance(frame, TextFrame):
                message = {
                    "type": "text",
                    "text": frame.text
                }
                logger.info(f"📤 Serializing text: '{frame.text[:50]}...'")
                return json.dumps(message)
                
            elif isinstance(frame, TranscriptionFrame):
                message = {
                    "type": "transcription",
                    "text": frame.text
                }
                logger.info(f"📤 Serializing transcription: '{frame.text}'")
                return json.dumps(message)
                
            return None
            
        except Exception as e:
            logger.error(f"❌ Serialization error: {e}")
            return None
    
    def deserialize(self, data: str | bytes) -> Frame | None:
        """Deserialize JSON messages with logging"""
        try:
            self._messages_received += 1
            
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            logger.info(f"📥 Raw message #{self._messages_received} received: {len(data)} chars")
            
            message = json.loads(data)
            msg_type = message.get("type", "unknown")
            
            logger.info(f"📥 Parsed message type: '{msg_type}'")
            
            if msg_type == "audio_input":
                audio_data = base64.b64decode(message["data"])
                sample_rate = message.get("sample_rate", 16000)
                channels = message.get("channels", 1)
                
                logger.info(f"📥 Creating InputAudioRawFrame: {len(audio_data)} bytes, "
                           f"{sample_rate}Hz, {channels}ch")
                
                frame = InputAudioRawFrame(
                    audio=audio_data,
                    sample_rate=sample_rate,
                    num_channels=channels
                )
                return frame
                
            elif msg_type == "text_input":
                text = message.get("text", "")
                logger.info(f"📥 Creating TextFrame: '{text[:50]}...'")
                return TextFrame(text=text)
                
            elif msg_type == "start":
                logger.info(f"📥 Received start message - ignoring (WebSocket transport handles this)")
                # Don't create a StartFrame - the WebSocket transport handles initialization
                return None
                
            else:
                logger.warning(f"⚠️ Unknown message type: '{msg_type}'")
                return None
                
        except Exception as e:
            logger.error(f"❌ Deserialization error: {e}")
            logger.error(f"❌ Data was: {str(data)[:200]}...")
            return None

class DiagnosticVoicePipeline:
    """Diagnostic voice pipeline to debug issues"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.current_pipeline_task = None
        self.current_runner = None
        self.is_running = False
        
    async def create_pipeline(self):
        """Create a diagnostic pipeline"""
        logger.info("🔧 Creating diagnostic pipeline...")
        
        # Voice Activity Detection with verbose settings
        vad_params = VADParams(
            confidence=0.5,      # Lower threshold for testing
            start_secs=0.2,      # Faster start
            stop_secs=0.3,       # Faster stop
            min_volume=0.5       # Lower volume threshold
        )
        vad = SileroVADAnalyzer(
            sample_rate=16000,
            params=vad_params
        )
        logger.info("✅ VAD configured with diagnostic settings")
        
        # Create diagnostic serializer
        serializer = DiagnosticJSONFrameSerializer()
        
        # WebSocket transport
        transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=vad,
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
                serializer=serializer
            ),
            host=self.host,
            port=self.port
        )
        logger.info(f"✅ WebSocket transport created on {self.host}:{self.port}")
        
        # Create diagnostic frame loggers
        input_logger = DiagnosticFrameLogger("INPUT")
        post_vad_logger = DiagnosticFrameLogger("POST-VAD")
        output_logger = DiagnosticFrameLogger("OUTPUT")
        
        # Simple test processor that responds to any text
        class TestProcessor(FrameProcessor):
            async def process_frame(self, frame: Frame, direction=None):
                await super().process_frame(frame, direction)
                
                if isinstance(frame, TextFrame) and frame.text.strip():
                    logger.info(f"🤖 TestProcessor received: '{frame.text}'")
                    response = TextFrame(text=f"Echo: {frame.text}")
                    await self.push_frame(response, direction)
        
        test_processor = TestProcessor()
        
        # Build minimal diagnostic pipeline
        pipeline_components = [
            transport.input(),      # WebSocket input
            input_logger,          # Log all input frames
            post_vad_logger,       # Log frames after VAD
            test_processor,        # Simple echo processor
            output_logger,         # Log output frames
            transport.output()     # WebSocket output
        ]
        
        pipeline = Pipeline(pipeline_components)
        logger.info("✅ Diagnostic pipeline created")
        
        return transport, pipeline
    
    async def start(self):
        """Start the diagnostic pipeline"""
        if self.is_running:
            logger.warning("⚠️ Pipeline already running")
            return True
            
        logger.info("🚀 Starting Diagnostic Voice Pipeline...")
        self.is_running = True
        
        try:
            # Create pipeline
            transport, pipeline = await self.create_pipeline()
            
            # Create pipeline task
            task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    allow_interruptions=True,
                    enable_metrics=False,
                    enable_usage_metrics=False
                )
            )
            
            # Create runner
            runner = PipelineRunner()
            
            self.current_pipeline_task = task
            self.current_runner = runner
            
            logger.info(f"✅ Diagnostic pipeline ready on ws://{self.host}:{self.port}")
            logger.info("📊 Diagnostic features enabled:")
            logger.info("  • Detailed frame logging at every stage")
            logger.info("  • Message serialization/deserialization logging")
            logger.info("  • VAD with lower thresholds for testing")
            logger.info("  • Simple echo processor for text")
            logger.info("  • No STT/LLM/TTS to isolate issues")
            
            # Run the pipeline
            await runner.run(task)
            
        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            self.is_running = False
            return False
            
        return True
    
    async def stop(self):
        """Stop the diagnostic pipeline"""
        logger.info("🛑 Stopping diagnostic pipeline...")
        self.is_running = False
        
        if self.current_runner:
            try:
                await self.current_runner.stop()
            except Exception as e:
                logger.error(f"Error stopping runner: {e}")

# Global instance
diagnostic_pipeline = DiagnosticVoicePipeline()

async def start_diagnostic_pipeline():
    """Start the diagnostic pipeline"""
    await diagnostic_pipeline.start()

async def stop_diagnostic_pipeline():
    """Stop the diagnostic pipeline"""
    await diagnostic_pipeline.stop()