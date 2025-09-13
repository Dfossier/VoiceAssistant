#!/usr/bin/env python3
"""
Robust Pipecat Pipeline with improved WebSocket connection handling
This prevents client disconnections from crashing the entire pipeline
"""

import asyncio
import logging
from typing import Optional
import traceback

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.frames.frames import LLMMessagesUpdateFrame, TextFrame, Frame, StartFrame, MetricsFrame, ControlFrame, SystemFrame
from pipecat.transports.websocket.server import WebsocketServerTransport, WebsocketServerParams
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer

# Import our local model services  
from .local_pipecat_services import FasterWhisperSTTService, LocalParakeetSTT, LocalPhi3LLM, LocalKokoroTTS
from .local_models import local_model_manager
from .hybrid_serializer import HybridFrameSerializer
from .logging_serializer_wrapper import LoggingSerializerWrapper
from .debug_websocket_server import DebugWebsocketServerInputTransport
from .debug_websocket_transport import DebugWebsocketServerTransport
from .json_frame_serializer import JSONFrameSerializer

logger = logging.getLogger(__name__)

class RobustWebSocketWrapper:
    """Wrapper that manages WebSocket connections and prevents pipeline crashes"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.current_pipeline_task = None
        self.current_runner = None
        self.is_running = False
        self.restart_lock = asyncio.Lock()
        
    async def create_pipeline_components(self):
        """Create the pipeline components that can be reused"""
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
        
        # Create services
        stt = None
        tts = None
        llm_processor = None
        
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
            logger.error(f"❌ Failed to create Faster-Whisper STT: {e}")
            logger.info("⚠️ Falling back to Parakeet STT...")
            try:
                stt = LocalParakeetSTT()
                logger.info("✅ Using LocalParakeetSTT as fallback")
            except Exception as e2:
                logger.error(f"❌ Parakeet fallback failed: {e2}")
                stt = None
            
        # Enable TTS to send audio responses back
        try:
            logger.info("🔧 Creating local Kokoro TTS service...")
            tts = LocalKokoroTTS()
            logger.info("✅ Using LocalKokoroTTS for text-to-speech")
        except Exception as e:
            logger.error(f"❌ Failed to create LocalKokoroTTS: {e}")
            tts = None
        
        # Create LocalPhi3LLM service for text processing
        try:
            logger.info("🔧 Creating LocalPhi3LLM service...")
            llm_processor = LocalPhi3LLM()
            logger.info("✅ LocalPhi3LLM service created")
        except Exception as e:
            logger.error(f"❌ Failed to create LocalPhi3LLM: {e}")
            llm_processor = None
            
        return vad, stt, tts, llm_processor
    
    async def create_single_pipeline(self):
        """Create a single pipeline instance"""
        logger.info("🔧 ENTERING create_single_pipeline()")
        logger.info("🔧 About to call create_pipeline_components()...")
        vad, stt, tts, llm_processor = await self.create_pipeline_components()
        logger.info("🔧 create_pipeline_components() completed")
        
        # WebSocket transport for Discord integration
        logger.info("🔧 Setting up WebSocket transport...")
        
        # Use standard WebSocket transport (debug transport has protocol issues)
        # Using JSONFrameSerializer for our proven JSON protocol  
        transport = WebsocketServerTransport(
            params=WebsocketServerParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=vad,
                audio_in_sample_rate=16000,    # Silero VAD sample rate
                audio_out_sample_rate=16000,   # Keep consistent
                serializer=LoggingSerializerWrapper(JSONFrameSerializer()),  # Use JSON for Discord bot compatibility
            ),
            host=self.host,
            port=self.port
        )
        logger.info("✅ WebSocket transport created with JSONFrameSerializer (proven JSON protocol)")
        
        # Add event handlers for debugging
        @transport.event_handler("on_client_connected")
        async def on_connected(transport, websocket):
            logger.info(f"🔌 DEBUG: Client connected from {websocket.remote_address}")
            
        @transport.event_handler("on_client_disconnected") 
        async def on_disconnected(transport, websocket):
            logger.info(f"👋 DEBUG: Client disconnected from {websocket.remote_address}")
            
        @transport.event_handler("on_websocket_ready")
        async def on_ready(transport):
            logger.info("🟢 DEBUG: WebSocket server is ready and accepting connections")
        
        # Processing aggregators and converters
        sentence_aggregator = SentenceAggregator()
        
        # Build pipeline components
        pipeline_components = [
            transport.input(),           # Receive messages from Discord WebSocket
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
        
        return transport, pipeline
    
    async def run_pipeline_with_recovery(self):
        """Run pipeline with automatic recovery on client disconnect"""
        logger.info("🔄 Recovery loop starting...")
        
        while self.is_running:
            try:
                logger.info("🚀 Starting new pipeline instance...")
                
                # Create pipeline with detailed error handling
                try:
                    transport, pipeline = await self.create_single_pipeline()
                    logger.info("✅ Pipeline components created successfully!")
                except Exception as e:
                    logger.error(f"❌ Failed to create pipeline components: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
                
                # Create pipeline task
                task = PipelineTask(
                    pipeline,
                    params=PipelineParams(
                        allow_interruptions=True,    # Allow users to interrupt AI
                        enable_metrics=False,        # Disable metrics to avoid observer issues
                        enable_usage_metrics=False   # Disable usage metrics to avoid observer issues
                    ),
                    idle_timeout_secs=None           # Disable idle timeout to prevent auto-cancellation
                )
                
                # Create runner
                runner = PipelineRunner()
                
                # Store current instances
                self.current_pipeline_task = task
                self.current_runner = runner
                
                logger.info(f"✅ Pipeline ready on ws://{self.host}:{self.port}")
                logger.info("🔄 Waiting for client connections...")
                
                # Run the pipeline - this will block until completion or error
                await runner.run(task)
                
                logger.warning("🔄 Pipeline ended, checking if restart is needed...")
                
            except asyncio.CancelledError:
                logger.info("🛑 Pipeline cancelled, exiting recovery loop")
                break
            except Exception as e:
                logger.error(f"❌ Pipeline error: {e}")
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                
                if self.is_running:
                    logger.info("🔄 Restarting pipeline in 2 seconds...")
                    await asyncio.sleep(2)  # Brief pause before restart
                else:
                    logger.info("🛑 Not restarting - service is stopping")
                    break
    
    async def start(self):
        """Start the robust pipeline service"""
        logger.info("🔧 ENTERING start() method")
        
        if self.is_running:
            logger.warning("⚠️ Pipeline already running")
            return True
            
        logger.info("🚀 Starting Robust Voice Pipeline with auto-recovery...")
        
        # Don't require models to be loaded - they'll load on first use
        logger.info("ℹ️  Models will be loaded on demand during first use")
            
        self.is_running = True
        logger.info("🔧 Set is_running = True")
        
        # Don't use recovery loop - it causes FastAPI lifespan conflicts
        # Instead, create components directly and let Pipecat handle reconnections
        logger.info("🔧 Creating pipeline components directly (no recovery loop)...")
        
        try:
            logger.info("🔧 About to call create_single_pipeline()...")
            # Create transport and pipeline immediately
            transport, pipeline = await self.create_single_pipeline()
            logger.info("✅ Pipeline components created successfully!")
            
            # Create and store pipeline task
            task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    allow_interruptions=True,    # Allow users to interrupt AI
                    enable_metrics=False,        # Disable metrics to avoid observer issues
                    enable_usage_metrics=False   # Disable usage metrics to avoid observer issues
                ),
                idle_timeout_secs=None           # Disable idle timeout to prevent auto-cancellation
            )
            
            # Create runner and start pipeline immediately
            runner = PipelineRunner()
            
            # Store current instances
            self.current_pipeline_task = task
            self.current_runner = runner
            
            # Start pipeline in background (don't await - let it run continuously)
            pipeline_bg_task = asyncio.create_task(runner.run(task))
            self.recovery_task = pipeline_bg_task
            
            logger.info("✅ Pipeline started in background")
            
        except Exception as e:
            logger.error(f"❌ Failed to create pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        logger.info("🎤 Robust Voice Assistant Pipeline Started:")
        logger.info("  • Automatic client disconnect recovery")
        logger.info("  • Silero VAD (automatic speech detection)")
        logger.info("  • Faster-Whisper Small STT (245MB, ~0.3s transcription)")  
        logger.info("  • Local Phi-3 Mini LLM (2.3GB, pre-loaded)")
        logger.info("  • Local Kokoro TTS (312MB, speech synthesis)")
        logger.info("  • Real-time interruptions")
        logger.info("  • Discord WebSocket integration")
        logger.info("  • Full audio-to-audio conversation loop")
        logger.info("  • Pipeline auto-restart on client disconnect")
        
        return True
        
    async def stop(self):
        """Stop the pipeline gracefully"""
        logger.info("🛑 Stopping robust voice pipeline...")
        
        self.is_running = False
        
        # Stop current runner if exists
        if self.current_runner:
            try:
                await self.current_runner.stop()
            except Exception as e:
                logger.error(f"Error stopping runner: {e}")
        
        # Cancel current task if exists
        if self.current_pipeline_task:
            try:
                await self.current_pipeline_task.cancel()
            except Exception as e:
                logger.error(f"Error cancelling task: {e}")
        
        logger.info("✅ Robust voice pipeline stopped")

# Global robust pipeline instance
robust_voice_pipeline = RobustWebSocketWrapper()

async def start_robust_voice_pipeline():
    """Start the robust voice pipeline server"""
    await robust_voice_pipeline.start()

async def stop_robust_voice_pipeline():
    """Stop the robust voice pipeline server"""
    await robust_voice_pipeline.stop()