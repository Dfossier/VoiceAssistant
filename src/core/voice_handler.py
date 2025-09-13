"""Voice conversation handler using Pipecat for real-time voice chat"""
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

from loguru import logger

# Try importing Pipecat components
try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.services.deepgram import DeepgramSTTService
    from pipecat.services.openai import OpenAILLMService
    from pipecat.services.elevenlabs import ElevenLabsTTSService
    from pipecat.transports.services.daily import DailyTransport, DailyParams
    from pipecat.vad.silero import SileroVADAnalyzer
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False
    logger.warning("Pipecat not installed - voice features disabled")

from .config import Settings
from .llm_handler import LLMHandler


@dataclass
class VoiceConfig:
    """Configuration for voice chat"""
    stt_provider: str = "whisper"  # whisper, deepgram, google
    tts_provider: str = "local"    # local, elevenlabs, google
    vad_enabled: bool = True
    sample_rate: int = 16000
    language: str = "en"


class VoiceHandler:
    """Handle real-time voice conversations"""
    
    def __init__(self, settings: Settings, llm_handler: LLMHandler):
        self.settings = settings
        self.llm_handler = llm_handler
        self.voice_config = VoiceConfig()
        self.pipeline = None
        self.runner = None
        self.transport = None
        
    async def initialize_voice_pipeline(self, room_url: Optional[str] = None):
        """Initialize the voice processing pipeline"""
        if not PIPECAT_AVAILABLE:
            logger.error("Pipecat not available - install with: pip install -r requirements-voice.txt")
            return False
            
        try:
            # Create transport (WebRTC via Daily for browser support)
            if room_url:
                transport_params = DailyParams(
                    audio_out_enabled=True,
                    audio_in_enabled=True,
                    camera_out_enabled=False,
                    vad_enabled=self.voice_config.vad_enabled
                )
                self.transport = DailyTransport(
                    room_url,
                    None,  # Token if needed
                    "Assistant",
                    transport_params
                )
            else:
                # Local audio transport for testing
                from pipecat.transports.local.audio import LocalAudioTransport
                self.transport = LocalAudioTransport()
            
            # Create STT service
            stt = self._create_stt_service()
            
            # Create LLM service (use our existing handler)
            llm = self._create_llm_service()
            
            # Create TTS service
            tts = self._create_tts_service()
            
            # Create context aggregator
            context = OpenAILLMContext()
            messages = [
                {
                    "role": "system",
                    "content": """You are a helpful AI assistant specialized in debugging and development. 
                    You're having a voice conversation, so keep responses concise and conversational.
                    Help with code errors, file operations, and development tasks."""
                }
            ]
            context.set_messages(messages)
            
            # Build the pipeline
            self.pipeline = Pipeline([
                self.transport.input(),      # Audio input from user
                stt,                        # Convert speech to text
                context.user(),             # Add user message to context
                llm,                        # Process with LLM
                tts,                        # Convert response to speech
                self.transport.output(),    # Audio output to user
                context.assistant(),        # Add assistant response to context
            ])
            
            # Create runner
            self.runner = PipelineRunner()
            
            logger.info("Voice pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize voice pipeline: {e}")
            return False
    
    def _create_stt_service(self):
        """Create Speech-to-Text service based on configuration"""
        if self.voice_config.stt_provider == "deepgram":
            # Use Deepgram (requires API key)
            return DeepgramSTTService(
                api_key=self.settings.deepgram_api_key or "",
                live_options={"language": self.voice_config.language}
            )
        else:
            # Default to local Whisper
            from pipecat.services.whisper import WhisperSTTService
            return WhisperSTTService(
                model="base",
                language=self.voice_config.language
            )
    
    def _create_llm_service(self):
        """Create LLM service using our existing handler"""
        # Wrapper to use our LLMHandler with Pipecat
        class LocalLLMService:
            def __init__(self, llm_handler):
                self.llm_handler = llm_handler
                
            async def process_frame(self, frame):
                # Process text through our LLM handler
                if hasattr(frame, 'text'):
                    response = await self.llm_handler.generate_response(
                        prompt=frame.text,
                        system_prompt="You are in a voice conversation. Keep responses concise."
                    )
                    return response
                return None
        
        return LocalLLMService(self.llm_handler)
    
    def _create_tts_service(self):
        """Create Text-to-Speech service based on configuration"""
        if self.voice_config.tts_provider == "elevenlabs":
            # Use ElevenLabs (requires API key)
            return ElevenLabsTTSService(
                api_key=self.settings.elevenlabs_api_key or "",
                voice_id="21m00Tcm4TlvDq8ikWAM"  # Default voice
            )
        else:
            # Default to local TTS
            from pipecat.services.local_tts import LocalTTSService
            return LocalTTSService()
    
    async def start_voice_session(self, room_url: Optional[str] = None):
        """Start a voice conversation session"""
        if not self.pipeline:
            success = await self.initialize_voice_pipeline(room_url)
            if not success:
                return False
        
        try:
            # Create pipeline task
            task = PipelineTask(self.pipeline)
            
            # Run the pipeline
            await self.runner.run(task)
            
            logger.info("Voice session started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start voice session: {e}")
            return False
    
    async def stop_voice_session(self):
        """Stop the current voice session"""
        if self.runner:
            await self.runner.stop()
            logger.info("Voice session stopped")
    
    async def create_webrtc_offer(self) -> Dict[str, Any]:
        """Create WebRTC offer for browser-based voice chat"""
        # This would integrate with the web interface
        # to enable voice chat directly in the browser
        pass


class SimpleVoiceChat:
    """Simplified voice chat for local testing"""
    
    def __init__(self, llm_handler: LLMHandler):
        self.llm_handler = llm_handler
        self.is_listening = False
        
    async def start_local_voice_chat(self):
        """Start voice chat using local microphone and speakers"""
        try:
            import speech_recognition as sr
            import pyttsx3
            
            # Initialize speech recognition
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            # Initialize text-to-speech
            tts_engine = pyttsx3.init()
            tts_engine.setProperty('rate', 150)
            
            logger.info("Starting local voice chat - say 'exit' to stop")
            
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
            
            while self.is_listening:
                try:
                    # Listen for speech
                    with microphone as source:
                        logger.info("Listening...")
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    
                    # Convert speech to text
                    text = recognizer.recognize_google(audio)
                    logger.info(f"You said: {text}")
                    
                    if text.lower() == "exit":
                        break
                    
                    # Get AI response
                    response = await self.llm_handler.generate_response(
                        prompt=text,
                        system_prompt="You are in a voice conversation. Keep responses brief and natural."
                    )
                    
                    logger.info(f"Assistant: {response}")
                    
                    # Speak the response
                    tts_engine.say(response)
                    tts_engine.runAndWait()
                    
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    logger.warning("Could not understand audio")
                except Exception as e:
                    logger.error(f"Voice chat error: {e}")
            
        except ImportError:
            logger.error("Voice dependencies not installed. Run: pip install SpeechRecognition pyttsx3 pyaudio")
        except Exception as e:
            logger.error(f"Failed to start voice chat: {e}")
    
    def stop(self):
        """Stop voice chat"""
        self.is_listening = False