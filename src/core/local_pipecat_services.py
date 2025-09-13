#!/usr/bin/env python3
"""
Local Pipecat Services
Integrates local models (Parakeet, Phi-3, Kokoro) with Pipecat's service architecture
for real-time streaming voice conversations.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, List

from pipecat.frames.frames import (
    AudioRawFrame, 
    LLMMessagesFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    TextFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    StartFrame
)
# Pipecat service imports
from pipecat.services.ai_services import AIService, LLMService, STTService, TTSService

from .local_models import local_model_manager

logger = logging.getLogger(__name__)

class FasterWhisperSTTService(STTService):
    """Faster-Whisper STT service for real-time transcription"""
    
    def __init__(self, model="small", device="auto", compute_type="auto"):
        super().__init__()
        self._model_name = model  # Use private attribute instead of property
        self.device = device  
        self.compute_type = compute_type
        self._model = None
        self._started = False
        
    async def start(self, frame: StartFrame):
        """Initialize the Faster-Whisper model"""
        logger.info(f"🎤 FasterWhisperSTTService.start() called")
        if self._started:
            logger.info("✅ Already started, skipping initialization")
            return
            
        try:
            from faster_whisper import WhisperModel
            import time
            
            start_time = time.time()
            logger.info(f"🔄 Loading Faster-Whisper {self._model_name} model...")
            
            # Create the model with optimized settings
            self._model = WhisperModel(
                self._model_name,
                device=self.device,
                compute_type=self.compute_type
            )
            
            load_time = time.time() - start_time
            self._started = True
            logger.info(f"✅ Faster-Whisper {self._model_name} model loaded in {load_time:.2f}s!")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Faster-Whisper model: {e}")
            raise
    
    async def run_stt(self, audio: bytes) -> AsyncGenerator[TextFrame, None]:
        """Transcribe audio using Faster-Whisper"""
        if not self._started or not self._model:
            logger.error("❌ Faster-Whisper model not initialized")
            return
            
        try:
            logger.info(f"🎤 Transcribing {len(audio)} bytes with Faster-Whisper {self._model_name}...")
            
            # Convert bytes to numpy array for Faster-Whisper
            import numpy as np
            import tempfile
            import wave
            import time
            
            # Convert raw PCM bytes to proper audio format
            audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Write to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(audio)
            
            start_time = time.time()
            
            # Transcribe with Faster-Whisper
            segments, info = self._model.transcribe(temp_path, beam_size=5, language="en")
            
            # Collect all segments
            transcription = ""
            for segment in segments:
                transcription += segment.text + " "
            
            transcription = transcription.strip()
            
            # Clean up temp file
            try:
                import os
                os.unlink(temp_path)
            except:
                pass
                
            duration = time.time() - start_time
            logger.info(f"✅ Faster-Whisper transcription ({duration:.2f}s): '{transcription[:100]}...'")
            
            if transcription:
                yield TextFrame(text=transcription)
                
        except Exception as e:
            logger.error(f"❌ Faster-Whisper transcription failed: {e}")
            import traceback
            traceback.print_exc()

class LocalParakeetSTT(STTService):
    """Local Parakeet STT service for Pipecat"""
    
    def __init__(self):
        super().__init__()
        self._model_manager = local_model_manager
        self._started = False
        
    async def run_stt(self, audio: bytes) -> AsyncGenerator[TextFrame, None]:
        """Convert audio to text using local Parakeet model"""
        try:
            # Ensure service is properly initialized
            if not self._started:
                logger.debug("🎤 STT service not started, auto-initializing...")
                self._started = True
                
            if not self._model_manager.models['stt']:
                logger.error("❌ Parakeet model not loaded")
                return
                
            logger.debug(f"🎤 Transcribing {len(audio)} bytes with Parakeet...")
            
            # Use local Parakeet transcription
            text = await self._model_manager.transcribe_audio(audio)
            
            if text and text.strip():
                logger.info(f"✅ Parakeet transcribed: '{text[:50]}...'")
                yield TextFrame(text=text.strip())
            else:
                logger.debug("🔇 Empty transcription from Parakeet")
                
        except Exception as e:
            logger.error(f"❌ Parakeet STT error: {e}")

class LocalPhi3LLM(LLMService):
    """Local Phi-3 LLM service for Pipecat"""
    
    def __init__(self):
        super().__init__()
        self._model_manager = local_model_manager
        self._conversation_history = []
        self._started = False
        
    async def _process_context(self, context):
        """Process the conversation context"""
        # Extract messages from context
        messages = []
        
        # Handle LLMMessagesFrame
        if hasattr(context, 'messages'):
            # If messages is already a list of dicts
            if isinstance(context.messages, list):
                messages = context.messages
            else:
                # If messages is some other format, try to extract
                for msg in context.messages:
                    if hasattr(msg, 'content') and hasattr(msg, 'role'):
                        messages.append({
                            'role': msg.role, 
                            'content': msg.content
                        })
                    elif isinstance(msg, dict):
                        messages.append(msg)
        
        logger.debug(f"Processed context messages: {messages}")
        return messages
        
    async def _generate_chat(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        """Generate chat response using local Phi-3"""
        try:
            if not self._model_manager.models['llm']:
                logger.error("❌ Phi-3 model not loaded")
                return
                
            # Get the latest user message
            user_message = ""
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
                    
            if not user_message:
                logger.warning("⚠️  No user message found in context")
                return
                
            logger.info(f"🧠 Phi-3 processing: '{user_message[:50]}...'")
            
            # Generate response with Phi-3
            response = await self._model_manager.generate_response(
                user_message,
                system_prompt="You are a helpful AI assistant. Provide natural, conversational responses."
            )
            
            if response:
                logger.info(f"✅ Phi-3 generated: '{response[:50]}...'")
                
                # Stream the response word by word for more natural conversation
                words = response.split()
                current_phrase = []
                
                for word in words:
                    current_phrase.append(word)
                    
                    # Send phrase every 3-5 words for natural streaming
                    if len(current_phrase) >= 4 or word.endswith(('.', '!', '?', ',')):
                        phrase = ' '.join(current_phrase)
                        yield phrase + ' '
                        current_phrase = []
                        
                        # Small delay for natural pacing
                        await asyncio.sleep(0.1)
                
                # Send any remaining words
                if current_phrase:
                    yield ' '.join(current_phrase)
            else:
                logger.error("❌ Empty response from Phi-3")
                
        except Exception as e:
            logger.error(f"❌ Phi-3 LLM error: {e}")
            
    async def run_llm(self, context) -> AsyncGenerator[LLMFullResponseStartFrame | TextFrame | LLMFullResponseEndFrame, None]:
        """Run the LLM and yield response frames"""
        try:
            # Ensure service is properly initialized
            if not self._started:
                logger.warning("🤖 LLM service not started, auto-initializing...")
                self._started = True
                
            logger.info(f"🤖 LLM run_llm called with context type: {type(context)}")
            
            # Signal start of LLM response
            yield LLMFullResponseStartFrame()
            
            # Process context and generate response
            messages = await self._process_context(context)
            
            if not messages:
                logger.warning("⚠️ No messages found in context")
                yield LLMFullResponseEndFrame()
                return
            
            logger.info(f"📨 Processing {len(messages)} messages")
            
            async for text_chunk in self._generate_chat(messages):
                if text_chunk.strip():
                    yield TextFrame(text=text_chunk)
            
            # Signal end of LLM response
            yield LLMFullResponseEndFrame()
            
        except Exception as e:
            logger.error(f"❌ LLM processing error: {e}", exc_info=True)
            yield LLMFullResponseEndFrame()

class LocalKokoroTTS(TTSService):
    """Local Kokoro TTS service for Pipecat"""
    
    def __init__(self):
        super().__init__()
        self._model_manager = local_model_manager
        self._kokoro_service = None
        self._started = False
        
    async def run_tts(self, text: str) -> AsyncGenerator[TTSStartedFrame | AudioRawFrame | TTSStoppedFrame, None]:
        """Convert text to speech using local Kokoro model"""
        try:
            # Ensure service is properly initialized
            if not self._started:
                logger.debug("🔊 TTS service not started, auto-initializing...")
                self._started = True
                
                # Initialize Kokoro service if available
                try:
                    from .kokoro_tts_service import kokoro_service
                    self._kokoro_service = kokoro_service
                    await self._kokoro_service.initialize()
                    logger.info("✅ Kokoro TTS service initialized")
                except ImportError:
                    logger.warning("❌ Kokoro package not available, will use fallback TTS")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize Kokoro service: {e}")
                
            if not text.strip():
                return
                
            logger.debug(f"🔊 Synthesizing speech: '{text[:50]}...'")
            
            # Signal TTS start
            yield TTSStartedFrame()
            
            # Try proper Kokoro TTS first if available
            audio_data = None
            if self._kokoro_service:
                try:
                    audio_data = await self._kokoro_service.synthesize(text, voice='af_heart')
                    if audio_data and len(audio_data) > 0:
                        logger.info(f"✅ Kokoro TTS service generated {len(audio_data)} bytes at 24kHz")
                except Exception as e:
                    logger.error(f"❌ Kokoro TTS service failed: {e}")
                    audio_data = None
                    
            # Fallback to model manager if Kokoro service failed
            if not audio_data or len(audio_data) == 0:
                audio_data = await self._model_manager.synthesize_speech(text)
            
            if audio_data and len(audio_data) > 0:
                logger.info(f"✅ TTS generated {len(audio_data)} bytes")
                
                # Convert audio to the format expected by Pipecat
                # Pipecat expects raw PCM audio frames
                yield AudioRawFrame(
                    audio=audio_data,
                    sample_rate=24000,  # Kokoro's sample rate
                    num_channels=1      # Mono audio
                )
            else:
                logger.warning("⚠️  TTS failed, audio generation skipped")
                
            # Signal TTS end
            yield TTSStoppedFrame()
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            yield TTSStoppedFrame()

class LocalAudioProcessor(AIService):
    """Audio processing service for format conversion and optimization"""
    
    def __init__(self):
        super().__init__()
        self._started = False
        
    async def process_frame(self, frame, direction):
        """Process audio frames for optimal quality"""
        try:
            # Handle StartFrame properly
            if isinstance(frame, StartFrame):
                self._started = True
                logger.debug("🎵 AudioProcessor received StartFrame - ready to process audio")
                return frame
                
            # Only process frames after StartFrame
            if not self._started:
                logger.debug("AudioProcessor: Ignoring frame before StartFrame received")
                return None
                
            if isinstance(frame, AudioRawFrame):
                # Ensure audio is in the correct format for processing
                # Discord uses 48kHz, models may use different rates
                
                # For now, pass through - add resampling if needed
                return frame
                
            return frame
            
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}")
            return frame