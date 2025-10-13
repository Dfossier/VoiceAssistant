"""Pipecat-based voice pipeline for Discord integration with VAD"""
import asyncio
import logging
from typing import Dict, Any, Optional, AsyncIterator
from pathlib import Path

# Pipecat imports with graceful fallback
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.services.ai_services import AIService
    from pipecat.services.openai import OpenAILLMService, OpenAITTSService
    from pipecat.processors.frame_processor import FrameDirection
    from pipecat.frames.frames import (
        AudioRawFrame, TextFrame, LLMMessagesFrame, TTSAudioRawFrame,
        EndFrame, StartFrame, CancelFrame
    )
    PIPECAT_CORE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Pipecat core not available: {e}")
    PIPECAT_CORE_AVAILABLE = False

# VAD imports with fallback
try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    VAD_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Silero VAD not available: {e}")
    VAD_AVAILABLE = False
    SileroVADAnalyzer = None

# Transport imports with fallback  
try:
    from pipecat.transports.discord_transport import DiscordTransport
    DISCORD_TRANSPORT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Discord transport not available: {e}")
    DISCORD_TRANSPORT_AVAILABLE = False
    DiscordTransport = None

# Pipecat doesn't have a Discord transport yet, so just disable it
DISCORD_TRANSPORT_AVAILABLE = False

PIPECAT_AVAILABLE = PIPECAT_CORE_AVAILABLE and VAD_AVAILABLE and DISCORD_TRANSPORT_AVAILABLE

logger = logging.getLogger(__name__)

if PIPECAT_CORE_AVAILABLE:
    class LocalModelService(AIService):
        """Custom Pipecat service for local models"""
        
        def __init__(self, backend_client, **kwargs):
            super().__init__(**kwargs)
            self.backend_client = backend_client
            self._is_processing = False
            
        async def run_tts(self, text: str) -> AsyncIterator[TTSAudioRawFrame]:
            """Generate TTS audio using local/backend models"""
            try:
                logger.info(f"Generating TTS for: {text[:50]}...")
                
                # Use backend client to generate audio
                audio_data = await self.backend_client.text_to_speech(text)
                
                if audio_data and len(audio_data) > 0:
                    # Convert from MP3 to raw audio for Pipecat
                    # This would need actual audio conversion
                    # For now, yield a placeholder frame
                    yield TTSAudioRawFrame(
                        audio=audio_data,
                        sample_rate=24000,
                        num_channels=1
                    )
                    logger.info("TTS audio generated successfully")
                else:
                    logger.warning("No TTS audio generated")
                    
            except Exception as e:
                logger.error(f"TTS error: {e}")
                
        async def run_llm(self, messages) -> AsyncIterator[TextFrame]:
            """Generate LLM response using local/backend models"""
            try:
                if self._is_processing:
                    return
                    
                self._is_processing = True
                
                # Extract the latest message
                if messages and len(messages) > 0:
                    latest_message = messages[-1].get("content", "")
                    logger.info(f"Processing LLM request: {latest_message[:50]}...")
                    
                    # Use backend client to generate response
                    response = await self.backend_client.send_message(
                        user_id="pipecat_user",
                        message=latest_message,
                        context={"source": "voice", "pipeline": "pipecat"}
                    )
                    
                    if response:
                        logger.info(f"LLM response generated: {response[:50]}...")
                        yield TextFrame(text=response)
                    else:
                        logger.warning("No LLM response generated")
                        
            except Exception as e:
                logger.error(f"LLM error: {e}")
            finally:
                self._is_processing = False
else:
    # Dummy class when Pipecat not available
    class LocalModelService:
        def __init__(self, backend_client, **kwargs):
            self.backend_client = backend_client


class PipecatVoiceHandler:
    """Pipecat-based voice handler with VAD"""
    
    def __init__(self, bot, voice_client, backend_client):
        self.bot = bot
        self.voice_client = voice_client
        self.backend_client = backend_client
        self.pipeline = None
        self.pipeline_task = None
        self.is_running = False
        
    async def start_voice_pipeline(self):
        """Start the Pipecat voice processing pipeline"""
        if not PIPECAT_AVAILABLE:
            logger.error("Pipecat not available - cannot start voice pipeline")
            return False
            
        try:
            logger.info("Starting Pipecat voice pipeline...")
            
            # Create services
            llm_service = LocalModelService(self.backend_client)
            
            # Use OpenAI TTS as fallback (could be replaced with local)
            # tts_service = OpenAITTSService(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Create VAD analyzer
            vad = SileroVADAnalyzer(
                params={
                    "confidence": 0.7,
                    "pad_start_ms": 100,
                    "pad_end_ms": 500,
                    "min_volume": 0.1
                }
            )
            
            # Create Discord transport
            transport = DiscordTransport(
                voice_client=self.voice_client,
                params={
                    "audio_in_enabled": True,
                    "audio_out_enabled": True,
                    "vad_enabled": True,
                    "vad_analyzer": vad
                }
            )
            
            # Create pipeline
            pipeline = Pipeline([
                transport,
                vad,
                llm_service,
                # tts_service,  # Add back when working
                transport
            ])
            
            # Pipeline parameters
            params = PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True
            )
            
            # Create and start pipeline task
            self.pipeline_task = PipelineTask(pipeline, params)
            
            # Start the pipeline
            await self.pipeline_task.queue_frames([StartFrame()])
            
            self.is_running = True
            logger.info("✅ Pipecat voice pipeline started successfully")
            
            # Run the pipeline
            asyncio.create_task(self._run_pipeline())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Pipecat pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
    async def _run_pipeline(self):
        """Run the pipeline task"""
        try:
            await self.pipeline_task.run()
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.is_running = False
            
    async def stop_voice_pipeline(self):
        """Stop the Pipecat voice processing pipeline"""
        try:
            if self.pipeline_task and self.is_running:
                logger.info("Stopping Pipecat voice pipeline...")
                
                # Send end frame
                await self.pipeline_task.queue_frames([EndFrame()])
                
                # Cancel the task
                if hasattr(self.pipeline_task, 'cancel'):
                    await self.pipeline_task.cancel()
                
                self.is_running = False
                logger.info("Pipecat voice pipeline stopped")
                
        except Exception as e:
            logger.error(f"Error stopping pipeline: {e}")
            
    async def process_interruption(self, text: str):
        """Handle voice interruptions"""
        try:
            if self.pipeline_task and self.is_running:
                logger.info(f"Processing interruption: {text}")
                
                # Cancel current processing
                await self.pipeline_task.queue_frames([CancelFrame()])
                
                # Queue new message
                await self.pipeline_task.queue_frames([
                    LLMMessagesFrame(messages=[{"role": "user", "content": text}])
                ])
                
        except Exception as e:
            logger.error(f"Error handling interruption: {e}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status"""
        return {
            "pipecat_available": PIPECAT_AVAILABLE,
            "pipeline_running": self.is_running,
            "vad_enabled": True if PIPECAT_AVAILABLE else False,
            "local_models": {
                "stt": "parakeet_tdt",
                "llm": "phi3_mini", 
                "tts": "kokoro_tts"
            }
        }


class SimplifiedVoiceHandler:
    """Fallback voice handler without Pipecat"""
    
    def __init__(self, bot, voice_client, backend_client):
        self.bot = bot
        self.voice_client = voice_client
        self.backend_client = backend_client
        self.is_running = False
        
    async def start_voice_pipeline(self):
        """Start simplified voice processing"""
        logger.warning("Using simplified voice handler (Pipecat not available)")
        self.is_running = True
        
        # Start basic voice activity detection
        asyncio.create_task(self._basic_vad_loop())
        
        return True
        
    async def _basic_vad_loop(self):
        """Basic voice activity detection loop"""
        while self.is_running:
            try:
                # Simple approach: record for short periods
                await asyncio.sleep(2.0)  # Check every 2 seconds
                
                # This would capture and process audio
                # For now, just log that we're listening
                logger.debug("Basic VAD listening...")
                
            except Exception as e:
                logger.error(f"Basic VAD error: {e}")
                break
                
    async def stop_voice_pipeline(self):
        """Stop simplified voice processing"""
        self.is_running = False
        logger.info("Simplified voice handler stopped")
        
    def get_status(self) -> Dict[str, Any]:
        return {
            "pipecat_available": False,
            "pipeline_running": self.is_running,
            "vad_enabled": False,
            "fallback_mode": True
        }


def create_voice_handler(bot, voice_client, backend_client):
    """Factory function to create appropriate voice handler"""
    if PIPECAT_AVAILABLE:
        logger.info("Creating Pipecat-based voice handler")
        return PipecatVoiceHandler(bot, voice_client, backend_client)
    else:
        logger.warning("Pipecat not available, using simplified handler")
        return SimplifiedVoiceHandler(bot, voice_client, backend_client)