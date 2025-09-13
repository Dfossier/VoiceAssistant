#!/usr/bin/env python3
"""
Pipecat Pipeline for Real-time Voice Conversation
Integrates Pipecat's streaming architecture with local models:
- Silero VAD for voice activity detection
- Local Parakeet STT
- Local Phi-3 LLM  
- Local Kokoro TTS
- WebSocket transport for Discord integration
"""

import asyncio
import logging
import os
from typing import Optional

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.frames.frames import LLMMessagesUpdateFrame, TextFrame, Frame, StartFrame, MetricsFrame, ControlFrame, SystemFrame
from pipecat.transports.network.websocket_server import WebsocketServerTransport, WebsocketServerParams
# from pipecat.services.ai_service import AIService  # Not needed for current implementation
from pipecat.processors.frame_processor import FrameProcessor

# Import our local model services  
from .local_pipecat_services import FasterWhisperSTTService, LocalParakeetSTT, LocalPhi3LLM, LocalKokoroTTS
from .local_models import local_model_manager

logger = logging.getLogger(__name__)

class DebugFrameLogger(FrameProcessor):
    """Debug processor that logs all frames passing through the pipeline"""
    
    def __init__(self, logger_name="DebugLogger"):
        super().__init__()
        self._logger_name = logger_name
        self._frame_count = 0
        
    async def process_frame(self, frame: Frame, direction=None):
        """Log every frame that passes through"""
        self._frame_count += 1
        frame_type = type(frame).__name__
        
        # Log basic frame info
        logger.info(f"🔍 [{self._logger_name}] Frame #{self._frame_count}: {frame_type}")
        
        # Log additional details based on frame type
        if hasattr(frame, 'text'):
            logger.info(f"   → Text content: '{frame.text[:100]}...'")
        elif hasattr(frame, 'audio'):
            logger.info(f"   → Audio frame: {len(frame.audio)} bytes")
        elif hasattr(frame, 'data'):
            logger.info(f"   → Data: {str(frame.data)[:100]}...")
        elif isinstance(frame, StartFrame):
            logger.info(f"   → StartFrame detected - pipeline starting")
        elif isinstance(frame, MetricsFrame):
            logger.info(f"   → Metrics: {frame.data if hasattr(frame, 'data') else 'N/A'}")
        elif isinstance(frame, ControlFrame):
            logger.info(f"   → ControlFrame - control signal")
        elif isinstance(frame, SystemFrame):
            logger.info(f"   → SystemFrame - system event")
        
        # Log direction if available
        if direction:
            logger.info(f"   → Direction: {direction}")
            
        # Always pass the frame through unchanged
        await super().process_frame(frame, direction)

class SimpleTextProcessor(FrameProcessor):
    """Text processor that uses local Phi-3 LLM for responses"""
    
    def __init__(self):
        super().__init__()
        self._conversation_count = 0
        
    async def process_frame(self, frame: Frame, direction=None):
        """Process incoming frames"""
        # Log all incoming frames for debugging
        frame_type = type(frame).__name__
        logger.info(f"🔄 SimpleTextProcessor received: {frame_type}")
        
        # Let the base class handle all frames first
        await super().process_frame(frame, direction)
        
        # Only process TextFrames with content
        if isinstance(frame, TextFrame) and frame.text.strip():
            text = frame.text.strip()
            logger.info(f"💬 Received text: '{text[:50]}...'")
            
            # Generate response using Phi-3 LLM
            self._conversation_count += 1
            
            try:
                logger.info("🧠 Generating response with Phi-3...")
                
                # Use the pre-loaded Phi-3 model via local_model_manager
                system_prompt = "You are a helpful voice assistant. Respond briefly and conversationally."
                user_prompt = f"User said: {text}\n\nRespond briefly and conversationally."
                
                # Generate response with Phi-3
                response = await local_model_manager.generate_response(user_prompt, system_prompt)
                
                logger.info(f"✅ Phi-3 response: '{response[:50]}...'")
                
                # Send response as TextFrame
                response_frame = TextFrame(text=response)
                await self.push_frame(response_frame, direction)
                
            except Exception as e:
                logger.error(f"❌ LLM generation failed: {e}")
                # Fallback response
                fallback_response = f"I heard '{text}' but had trouble generating a response. (Error: {str(e)[:30]}...)"
                response_frame = TextFrame(text=fallback_response)
                await self.push_frame(response_frame, direction)

class LocalVoicePipeline:
    """Real-time voice pipeline using Pipecat with local models"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.pipeline = None
        self.task = None
        self.runner = None
        
    def create_pipeline(self) -> Pipeline:
        """Create the Pipecat pipeline with local models"""
        
        # Voice Activity Detection
        vad_params = VADParams(
            confidence=0.6,      # Lower = more sensitive to speech
            start_secs=0.3,      # 300ms of speech to start
            stop_secs=0.5,       # 500ms of silence to stop
            min_volume=0.6       # Minimum volume threshold
        )
        vad = SileroVADAnalyzer(
            sample_rate=16000,   # Silero VAD requires 16kHz or 8kHz
            params=vad_params
        )
        
        # WebSocket transport for Discord integration
        logger.info("🔧 Setting up WebSocket transport...")
        
        # Import and use our custom JSON serializer for Discord bot compatibility
        from .json_serializer import JSONFrameSerializer
        json_serializer = JSONFrameSerializer()
        logger.info("🔧 Using custom JSON serializer for Discord bot compatibility...")
        
        transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=vad,
                audio_in_sample_rate=16000,    # Silero VAD sample rate
                audio_out_sample_rate=16000,   # Keep consistent
                serializer=json_serializer     # Use custom JSON serializer
            ),
            host=self.host,
            port=self.port
        )
        logger.info("✅ WebSocket transport created with JSON serializer")
        
        # Use Faster-Whisper Small for optimized speed and size
        try:
            logger.info("🔧 Creating Faster-Whisper Small STT service...")
            stt = FasterWhisperSTTService(
                model="small",  # 245MB model, ~0.3s transcription
                device="auto",  # Auto-detect GPU/CPU
                compute_type="auto"  # Auto-detect precision
            )
            logger.info("✅ Using Faster-Whisper Small for audio transcription (245MB, ~0.3s)")
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to create Faster-Whisper STT: {e}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            logger.info("⚠️ Falling back to Parakeet STT...")
            try:
                stt = LocalParakeetSTT()
                logger.info("✅ Using LocalParakeetSTT as fallback")
            except Exception as e2:
                logger.error(f"❌ Parakeet fallback failed: {e2}")
                logger.info("⚠️ STT disabled - testing with direct text input only")
                stt = None
            
        # For now, let's use a simple text processor instead of the problematic LLM service
        # This will process the transcribed text and respond
        logger.info("🤖 Using simple text processor instead of LLM service for debugging")
            
        # Enable TTS to send audio responses back
        try:
            logger.info("🔧 Creating local Kokoro TTS service...")
            tts = LocalKokoroTTS()
            logger.info("✅ Using LocalKokoroTTS for text-to-speech")
        except Exception as e:
            logger.error(f"❌ Failed to create LocalKokoroTTS: {e}")
            logger.info("⚠️ TTS disabled - will send text responses only")
            tts = None
        
        # Processing aggregators and converters
        sentence_aggregator = SentenceAggregator()
        
        # Create LocalPhi3LLM service for text processing
        try:
            logger.info("🔧 Creating LocalPhi3LLM service...")
            llm_processor = LocalPhi3LLM()
            logger.info("✅ LocalPhi3LLM service created")
        except Exception as e:
            logger.error(f"❌ Failed to create LocalPhi3LLM: {e}")
            llm_processor = None
        
        # Create debug logger to see all incoming frames
        debug_logger = DebugFrameLogger(logger_name="WebSocket-Input")
        
        # Build pipeline: WebSocket Input → Debug Logger → [STT] → Simple Processor → WebSocket Output  
        pipeline_components = [
            transport.input(),           # Receive messages from Discord WebSocket
            debug_logger,                # Debug log all incoming frames
        ]
        
        # Add STT if available (for audio processing)
        if stt and llm_processor:
            pipeline_components.extend([
                stt,                     # Whisper: Audio → Text
                sentence_aggregator,     # Aggregate sentences for better processing
                llm_processor,           # Process text messages with Phi-3
            ])
        elif llm_processor:
            # If no STT, still add processor for text-only testing
            pipeline_components.append(llm_processor)
        
        # Add TTS if available
        if tts:
            pipeline_components.append(tts)  # Kokoro: Text → Audio
            
        # Always add output to send responses back
        pipeline_components.append(transport.output())  # Send responses back to Discord WebSocket
        
        pipeline = Pipeline(pipeline_components)
        
        return (transport, pipeline)
    
    async def start(self):
        """Start the real-time voice pipeline"""
        logger.info("🚀 Starting Local Voice Pipeline with Pipecat...")
        
        # Don't require models to be loaded - they'll load on first use
        logger.info("ℹ️  Models will be loaded on demand during first use")
            
        # Create pipeline
        logger.info("📋 Creating Pipecat pipeline...")
        try:
            transport, pipeline = self.create_pipeline()
            logger.info("✅ Pipeline creation completed successfully")
        except Exception as e:
            import traceback
            logger.error(f"❌ Pipeline creation failed: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
        
        # Create pipeline task
        self.task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,    # Allow users to interrupt AI
                enable_metrics=False,        # Disable metrics to avoid observer issues
                enable_usage_metrics=False   # Disable usage metrics to avoid observer issues
            )
        )
        
        # Create runner
        self.runner = PipelineRunner()
        
        logger.info(f"✅ Voice pipeline ready on ws://{self.host}:{self.port}")
        logger.info("🎤 Complete Voice Assistant Pipeline:")
        logger.info("  • Silero VAD (automatic speech detection)")
        logger.info("  • Faster-Whisper Small STT (245MB, ~0.3s transcription)")  
        logger.info("  • Local Phi-3 Mini LLM (2.3GB, pre-loaded)")
        logger.info("  • Local Kokoro TTS (312MB, speech synthesis)")
        logger.info("  • Real-time interruptions")
        logger.info("  • Discord WebSocket integration")
        logger.info("  • Full audio-to-audio conversation loop")
        
        # Start the pipeline in the background (non-blocking)
        asyncio.create_task(self.runner.run(self.task))
        
        # Small delay to ensure WebSocket server is listening
        await asyncio.sleep(1)
        
        return True
        
    async def stop(self):
        """Stop the pipeline gracefully"""
        logger.info("🛑 Stopping voice pipeline...")
        if self.runner:
            await self.runner.stop()
        logger.info("✅ Voice pipeline stopped")

# Global pipeline instance
voice_pipeline = LocalVoicePipeline()

async def start_voice_pipeline():
    """Start the voice pipeline server"""
    await voice_pipeline.start()

async def stop_voice_pipeline():
    """Stop the voice pipeline server"""
    await voice_pipeline.stop()