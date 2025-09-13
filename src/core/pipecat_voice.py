"""Natural voice conversations using Pipecat framework"""
import asyncio
import logging
from typing import AsyncGenerator
from loguru import logger

try:
    from pipecat.frames.frames import (
        AudioRawFrame, TextFrame, TranscriptionFrame, TTSAudioRawFrame
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.cartesia import CartesiaTTSService
    from pipecat.services.deepgram import DeepgramSTTService
    from pipecat.services.openai import OpenAILLMService
    from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper
    from pipecat.vad.silero import SileroVADAnalyzer
    
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False
    logger.warning("Pipecat not fully available")

class NaturalVoiceConversation:
    """Handle natural voice conversations with Pipecat"""
    
    def __init__(self, llm_handler, settings):
        self.llm_handler = llm_handler
        self.settings = settings
        self.pipeline = None
        self.runner = None
        self.conversation_active = False
        
    async def start_conversation(self):
        """Start a natural voice conversation"""
        if not PIPECAT_AVAILABLE:
            return {"error": "Pipecat not available. Install with: pip install pipecat-ai[all]"}
            
        try:
            # Configure services
            stt_service = self._create_stt_service()
            llm_service = self._create_llm_service()
            tts_service = self._create_tts_service()
            vad_analyzer = SileroVADAnalyzer()
            
            # Create pipeline
            self.pipeline = Pipeline([
                stt_service,
                llm_service,
                tts_service
            ])
            
            # Set up WebRTC or WebSocket transport
            transport = await self._create_transport()
            
            # Create and start runner
            self.runner = PipelineRunner(
                pipeline=self.pipeline,
                transport=transport
            )
            
            await self.runner.run()
            
            self.conversation_active = True
            return {"status": "conversation_started"}
            
        except Exception as e:
            logger.error(f"Failed to start conversation: {e}")
            return {"error": str(e)}
    
    def _create_stt_service(self):
        """Create Speech-to-Text service"""
        # Try multiple STT options
        if hasattr(self.settings, 'deepgram_api_key') and self.settings.deepgram_api_key:
            return DeepgramSTTService(api_key=self.settings.deepgram_api_key)
        else:
            # Use our local Whisper as fallback
            from .local_whisper import LocalWhisperHandler
            return LocalWhisperSTTService()
    
    def _create_llm_service(self):
        """Create LLM service"""
        if self.settings.openai_api_key:
            return OpenAILLMService(
                api_key=self.settings.openai_api_key,
                model="gpt-4"
            )
        else:
            # Use our local LLM handler
            return LocalLLMService(self.llm_handler)
    
    def _create_tts_service(self):
        """Create Text-to-Speech service"""
        # Try multiple TTS options
        if hasattr(self.settings, 'cartesia_api_key') and self.settings.cartesia_api_key:
            return CartesiaTTSService(
                api_key=self.settings.cartesia_api_key,
                voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22"  # British Lady
            )
        else:
            # Use our local TTS
            from .browser_voice import BrowserVoiceHandler
            return LocalTTSService()
    
    async def _create_transport(self):
        """Create WebRTC transport for real-time audio"""
        # For now, return WebSocket transport
        # TODO: Implement WebRTC for better real-time performance
        return WebSocketTransport()
    
    async def stop_conversation(self):
        """Stop the conversation"""
        self.conversation_active = False
        if self.runner:
            await self.runner.cleanup()
        return {"status": "conversation_stopped"}

class LocalWhisperSTTService:
    """Pipecat STT service using our local Whisper"""
    
    def __init__(self):
        from .local_whisper import LocalWhisperHandler
        self.whisper = LocalWhisperHandler()
    
    async def run_stt(self, audio: AudioRawFrame) -> AsyncGenerator[TranscriptionFrame, None]:
        """Convert audio to text"""
        try:
            # Convert audio frame to base64
            import base64
            audio_data = base64.b64encode(audio.audio).decode()
            
            # Transcribe
            result = await self.whisper.transcribe_audio(audio_data)
            
            if result["success"]:
                yield TranscriptionFrame(result["text"], "", int(audio.timestamp))
        except Exception as e:
            logger.error(f"STT error: {e}")

class LocalLLMService:
    """Pipecat LLM service using our local LLM handler"""
    
    def __init__(self, llm_handler):
        self.llm_handler = llm_handler
    
    async def run_llm(self, text: str) -> AsyncGenerator[TextFrame, None]:
        """Generate conversational response"""
        try:
            response = await self.llm_handler.generate_response(
                prompt=text,
                system_prompt="""You are in a natural voice conversation. Keep responses:
- Conversational and natural
- Brief (1-2 sentences max)
- Easy to understand when spoken
- Engaging and human-like
- No special formatting or symbols"""
            )
            
            yield TextFrame(response)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            yield TextFrame("I didn't catch that, could you repeat?")

class LocalTTSService:
    """Pipecat TTS service using local synthesis"""
    
    async def run_tts(self, text: str) -> AsyncGenerator[TTSAudioRawFrame, None]:
        """Convert text to speech"""
        try:
            # Use browser synthesis for now
            # TODO: Implement proper audio generation
            yield TTSAudioRawFrame(
                audio=b"",  # Empty for now
                text=text,
                sample_rate=16000
            )
        except Exception as e:
            logger.error(f"TTS error: {e}")

class WebSocketTransport:
    """Simple WebSocket transport for audio streaming"""
    
    def __init__(self):
        self.websocket = None
    
    async def send_audio(self, audio_data: bytes):
        """Send audio to client"""
        if self.websocket:
            await self.websocket.send(audio_data)
    
    async def receive_audio(self) -> bytes:
        """Receive audio from client"""
        if self.websocket:
            return await self.websocket.receive_bytes()
        return b""