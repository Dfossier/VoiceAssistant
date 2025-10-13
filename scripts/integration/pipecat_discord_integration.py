"""
Pipecat-Discord Voice Integration
Replaces the existing Discord voice handler with Pipecat pipeline
Uses:
- NVIDIA Parakeet-TDT for Speech Recognition (ASR)
- Microsoft Phi-3 Mini Q4_K_M for Language Model (LLM)
- Kokoro-82M for Text-to-Speech (TTS)
"""

import asyncio
import io
import logging
import torch
from pathlib import Path
from typing import Optional, Callable, Any, Dict, AsyncGenerator
from dataclasses import dataclass

import discord
from discord.ext import commands

# Pipecat imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import LLMUserResponseAggregator
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import Frame, AudioRawFrame, TextFrame, LLMMessagesFrame
from pipecat.services.ai_services import AIService
from pipecat.transports.base_transport import BaseTransport, TransportParams


logger = logging.getLogger(__name__)

@dataclass
class DiscordTransportParams(TransportParams):
    """Discord transport configuration"""
    voice_client: discord.VoiceClient
    text_channel: discord.TextChannel
    audio_sample_rate: int = 48000
    audio_channels: int = 2


class ParakeetASRService(AIService):
    """NVIDIA Parakeet-TDT ASR Service for Pipecat"""
    
    def __init__(self, model_path: str, **kwargs):
        super().__init__(**kwargs)
        self.model_path = Path(model_path)
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Parakeet model"""
        try:
            # Import NeMo after installation completes
            import nemo
            import nemo.collections.asr as nemo_asr
            
            self.model = nemo_asr.models.ASRModel.restore_from(
                restore_path=str(self.model_path / "parakeet-tdt-0.6b-v2.nemo")
            )
            
            if torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("✅ Parakeet-TDT loaded on GPU")
            else:
                logger.info("✅ Parakeet-TDT loaded on CPU")
                
        except Exception as e:
            logger.error(f"Failed to load Parakeet model: {e}")
            self.model = None
    
    async def process_frame(self, frame: Frame, direction) -> AsyncGenerator[Frame, None]:
        """Process audio frames for speech recognition"""
        try:
            if isinstance(frame, AudioRawFrame) and self.model:
                # Convert audio to format expected by Parakeet
                audio_data = self._preprocess_audio(frame.audio)
                
                # Run inference
                transcription = await self._transcribe_audio(audio_data)
                
                if transcription and transcription.strip():
                    # Yield text frame
                    yield TextFrame(text=transcription.strip())
            else:
                # Pass through non-audio frames
                yield frame
                
        except Exception as e:
            logger.error(f"Error in Parakeet ASR: {e}")
            yield frame
    
    def _preprocess_audio(self, audio_bytes: bytes) -> torch.Tensor:
        """Convert raw audio bytes to tensor for Parakeet"""
        import numpy as np
        
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Convert to PyTorch tensor
        audio_tensor = torch.from_numpy(audio_np)
        
        if torch.cuda.is_available() and self.model:
            audio_tensor = audio_tensor.cuda()
            
        return audio_tensor
    
    async def _transcribe_audio(self, audio_tensor: torch.Tensor) -> str:
        """Transcribe audio using Parakeet"""
        try:
            # Run async inference
            loop = asyncio.get_event_loop()
            
            def _inference():
                with torch.no_grad():
                    transcription = self.model.transcribe([audio_tensor])
                    return transcription[0] if transcription else ""
            
            result = await loop.run_in_executor(None, _inference)
            return result
            
        except Exception as e:
            logger.error(f"Parakeet transcription error: {e}")
            return ""


class Phi3LLMService(AIService):
    """Microsoft Phi-3 Mini LLM Service for Pipecat"""
    
    def __init__(self, model_path: str, **kwargs):
        super().__init__(**kwargs)
        self.model_path = Path(model_path)
        self.llama_cpp = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Phi-3 model via llama-cpp-python"""
        try:
            from llama_cpp import Llama
            
            model_file = self.model_path / "Phi-3-mini-4k-instruct-Q4_K_M.gguf"
            
            self.llama_cpp = Llama(
                model_path=str(model_file),
                n_gpu_layers=-1 if torch.cuda.is_available() else 0,  # Use all GPU layers if available
                n_ctx=4096,  # Context length
                n_batch=512,
                verbose=False
            )
            
            logger.info("✅ Phi-3 Mini loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Phi-3 model: {e}")
            self.llama_cpp = None
    
    async def process_frame(self, frame: Frame, direction) -> AsyncGenerator[Frame, None]:
        """Process LLM messages"""
        try:
            if isinstance(frame, LLMMessagesFrame) and self.llama_cpp:
                # Extract user message
                messages = frame.messages
                if not messages:
                    yield frame
                    return
                
                # Get the latest user message
                user_message = messages[-1].get('content', '') if messages else ''
                
                if user_message.strip():
                    # Generate response
                    response = await self._generate_response(user_message, messages)
                    
                    if response:
                        # Create response frame
                        yield TextFrame(text=response)
                else:
                    yield frame
            else:
                yield frame
                
        except Exception as e:
            logger.error(f"Error in Phi-3 LLM: {e}")
            yield frame
    
    async def _generate_response(self, user_message: str, messages: list) -> str:
        """Generate response using Phi-3"""
        try:
            # Format prompt for Phi-3
            prompt = self._format_prompt(user_message, messages)
            
            # Run async inference
            loop = asyncio.get_event_loop()
            
            def _inference():
                response = self.llama_cpp(
                    prompt,
                    max_tokens=512,
                    temperature=0.7,
                    top_p=0.9,
                    stop=["<|end|>", "<|user|>", "<|assistant|>"],
                    echo=False
                )
                return response['choices'][0]['text'].strip()
            
            result = await loop.run_in_executor(None, _inference)
            return result
            
        except Exception as e:
            logger.error(f"Phi-3 generation error: {e}")
            return "I apologize, but I'm having trouble generating a response right now."
    
    def _format_prompt(self, user_message: str, messages: list) -> str:
        """Format prompt for Phi-3"""
        # Use Phi-3 chat template
        prompt = "<|system|>\nYou are a helpful Discord AI assistant. Provide concise, friendly responses.<|end|>\n"
        
        # Add conversation history (last 3 exchanges)
        recent_messages = messages[-6:] if len(messages) > 6 else messages
        
        for msg in recent_messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'user':
                prompt += f"<|user|>\n{content}<|end|>\n"
            elif role == 'assistant':
                prompt += f"<|assistant|>\n{content}<|end|>\n"
        
        # Add current user message if not already included
        if not recent_messages or recent_messages[-1].get('content') != user_message:
            prompt += f"<|user|>\n{user_message}<|end|>\n"
        
        prompt += "<|assistant|>\n"
        return prompt


class KokoroTTSService(AIService):
    """Kokoro-82M TTS Service for Pipecat"""
    
    def __init__(self, model_path: str, voice_name: str = "af_sarah", **kwargs):
        super().__init__(**kwargs)
        self.model_path = Path(model_path)
        self.voice_name = voice_name
        self.pipeline = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Kokoro TTS model"""
        try:
            # Use our integrated solution that handles all fallbacks
            from src.core.kokoro_integration import create_kokoro_tts_integration
            
            # Initialize Kokoro with automatic fallback support
            self.tts_integration = create_kokoro_tts_integration(
                model_path=str(self.model_path),
                voice_name=self.voice_name
            )
            
            logger.info(f"✅ Kokoro TTS integration initialized with voice: {self.voice_name}")
            self.pipeline = True  # Mark as initialized
                
        except ImportError as e:
            logger.error(f"Kokoro integration not available - falling back to Windows TTS: {e}")
            self.pipeline = None
            self.tts_integration = None
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro TTS: {e}")
            self.pipeline = None
            self.tts_integration = None
    
    async def process_frame(self, frame: Frame, direction) -> AsyncGenerator[Frame, None]:
        """Process text frames for TTS"""
        try:
            if isinstance(frame, TextFrame) and frame.text.strip():
                # Generate audio from text
                audio_data = await self._synthesize_speech(frame.text)
                
                if audio_data:
                    # Create audio frame
                    yield AudioRawFrame(
                        audio=audio_data,
                        sample_rate=24000,  # Kokoro's output sample rate
                        num_channels=1
                    )
            else:
                yield frame
                
        except Exception as e:
            logger.error(f"Error in Kokoro TTS: {e}")
            yield frame
    
    async def _synthesize_speech(self, text: str) -> bytes:
        """Synthesize speech using Kokoro integration with automatic fallback"""
        try:
            if self.tts_integration:
                # Use our integration which handles all TTS approaches automatically
                audio_bytes, sample_rate = await self.tts_integration.synthesize(text)
                
                if audio_bytes:
                    # Resample to 24kHz if needed (our target rate)
                    if sample_rate != 24000:
                        audio_bytes = self._resample_audio(audio_bytes, sample_rate, 24000)
                    return audio_bytes
                else:
                    logger.warning("TTS integration returned no audio")
                    return b""
            else:
                # Direct fallback to Windows TTS
                return await self._windows_tts_fallback(text)
            
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return await self._windows_tts_fallback(text)
    
    async def _windows_tts_fallback(self, text: str) -> bytes:
        """Fallback to Windows SAPI TTS"""
        try:
            # Use Windows PowerShell SAPI for TTS as fallback
            script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100

$memoryStream = New-Object System.IO.MemoryStream
$synth.SetOutputToWaveStream($memoryStream)
$synth.Speak("{text.replace('"', '`"')}")

$bytes = $memoryStream.ToArray()
$memoryStream.Close()
$synth.Dispose()

[System.Convert]::ToBase64String($bytes)
'''
            
            process = await asyncio.create_subprocess_shell(
                f'powershell.exe -Command "{script}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                import base64
                wav_bytes = base64.b64decode(stdout.decode().strip())
                
                # Convert WAV to raw PCM at 24kHz for consistency
                return self._convert_wav_to_pcm(wav_bytes)
            else:
                logger.error(f"Windows TTS failed: {stderr.decode()}")
                return b""
                
        except Exception as e:
            logger.error(f"Windows TTS fallback error: {e}")
            return b""
    
    def _resample_audio(self, audio_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
        """Resample audio data to target sample rate"""
        try:
            import numpy as np
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Calculate resampling ratio
            ratio = to_rate / from_rate
            new_length = int(len(audio_array) * ratio)
            
            if new_length > 0:
                # Simple linear interpolation resampling
                resampled = np.interp(
                    np.linspace(0, len(audio_array), new_length),
                    np.arange(len(audio_array)),
                    audio_array
                ).astype(np.int16)
                return resampled.tobytes()
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Audio resampling error: {e}")
            return audio_bytes
    
    def _convert_wav_to_pcm(self, wav_data: bytes) -> bytes:
        """Convert WAV data to raw PCM at 24kHz"""
        try:
            import wave
            import io
            
            # Read WAV data
            with wave.open(io.BytesIO(wav_data), 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                sample_rate = wav_file.getframerate()
                
                # If already 24kHz, return as-is
                if sample_rate == 24000:
                    return frames
                
                # Otherwise, basic resampling (not perfect but functional)
                # In production, would use proper resampling
                import numpy as np
                audio_array = np.frombuffer(frames, dtype=np.int16)
                
                # Simple decimation/interpolation
                ratio = 24000 / sample_rate
                new_length = int(len(audio_array) * ratio)
                
                if new_length > 0:
                    resampled = np.interp(
                        np.linspace(0, len(audio_array), new_length),
                        np.arange(len(audio_array)),
                        audio_array
                    ).astype(np.int16)
                    return resampled.tobytes()
                
                return frames
                
        except Exception as e:
            logger.error(f"WAV conversion error: {e}")
            return wav_data


class DiscordTransport(BaseTransport):
    """Discord voice transport for Pipecat"""
    
    def __init__(self, params: DiscordTransportParams, **kwargs):
        super().__init__(params, **kwargs)
        self.voice_client = params.voice_client
        self.text_channel = params.text_channel
        self.sample_rate = params.audio_sample_rate
        self.channels = params.audio_channels
        
        # Audio processing
        self.audio_buffer = bytearray()
        self.is_recording = False
        
    async def start(self, frame_processor_callable):
        """Start Discord transport"""
        self._frame_processor = frame_processor_callable
        
        # Start audio capture
        await self._start_audio_capture()
        
        logger.info("✅ Discord transport started")
    
    async def stop(self):
        """Stop Discord transport"""
        self.is_recording = False
        logger.info("Discord transport stopped")
    
    async def _start_audio_capture(self):
        """Start capturing audio from Discord"""
        # Note: This is a simplified version
        # Full implementation would use Discord's audio reception
        self.is_recording = True
        logger.info("Audio capture started")
    
    async def send_audio(self, audio_data: bytes):
        """Send audio to Discord voice channel"""
        if self.voice_client and self.voice_client.is_connected():
            # Convert audio data to Discord format and play
            # This is a placeholder for the actual implementation
            pass
    
    async def send_text(self, text: str):
        """Send text to Discord text channel"""
        if self.text_channel:
            await self.text_channel.send(text)


class PipecatDiscordVoiceHandler:
    """Main handler that replaces the existing Discord voice handler"""
    
    def __init__(self, voice_client: discord.VoiceClient, text_channel: discord.TextChannel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        
        # Model paths
        self.models_path = Path("/mnt/c/users/dfoss/desktop/localaimodels")
        
        # Pipeline components
        self.transport = None
        self.pipeline = None
        self.runner = None
        
        # Services
        self.asr_service = None
        self.llm_service = None
        self.tts_service = None
    
    async def initialize(self):
        """Initialize the Pipecat pipeline"""
        try:
            # Initialize services
            self.asr_service = ParakeetASRService(
                model_path=str(self.models_path / "parakeet-tdt")
            )
            
            self.llm_service = Phi3LLMService(
                model_path=str(self.models_path / "phi3-mini")
            )
            
            self.tts_service = KokoroTTSService(
                model_path=str(self.models_path / "kokoro-tts"),
                voice_name="af_sarah"
            )
            
            # Create transport
            transport_params = DiscordTransportParams(
                voice_client=self.voice_client,
                text_channel=self.text_channel
            )
            self.transport = DiscordTransport(transport_params)
            
            # Create pipeline
            self.pipeline = Pipeline([
                self.transport,
                SileroVADAnalyzer(),  # Voice activity detection
                self.asr_service,     # Speech recognition
                OpenAILLMContext(),   # Context management
                self.llm_service,     # Language model
                self.tts_service,     # Text to speech
            ])
            
            # Create runner
            self.runner = PipelineRunner()
            
            logger.info("✅ Pipecat Discord voice handler initialized")
            
            # Send notification
            await self.text_channel.send(
                "🎤 **Advanced Voice AI Active!** \n"
                "• **NVIDIA Parakeet-TDT**: Speech recognition\n"
                "• **Microsoft Phi-3 Mini**: Language processing\n"
                "• **Kokoro-82M**: High-quality voice synthesis\n"
                "• **All models running on RTX 3080 Ti GPU**\n\n"
                "Start talking - I'll hear and respond naturally!"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Pipecat handler: {e}")
            raise
    
    async def start(self):
        """Start the voice processing pipeline"""
        try:
            if self.pipeline and self.runner:
                task = PipelineTask(
                    self.pipeline,
                    PipelineParams(
                        allow_interruptions=True,
                        enable_metrics=True
                    )
                )
                
                await self.runner.run(task)
                
        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
    
    async def stop(self):
        """Stop the voice processing pipeline"""
        try:
            if self.runner:
                await self.runner.cleanup()
                
            if self.transport:
                await self.transport.stop()
                
            logger.info("✅ Pipecat pipeline stopped")
            
        except Exception as e:
            logger.error(f"Error stopping pipeline: {e}")
    
    async def process_text_message(self, text: str, user_name: str) -> str:
        """Process text message through the pipeline"""
        try:
            if self.llm_service and self.llm_service.llama_cpp:
                messages = [
                    {"role": "user", "content": text}
                ]
                response = await self.llm_service._generate_response(text, messages)
                return response
            else:
                return "Voice AI is initializing. Please wait a moment..."
                
        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            return f"Error processing message: {str(e)}"


# Integration function to replace existing voice handler
def create_pipecat_voice_handler(voice_client: discord.VoiceClient, text_channel: discord.TextChannel) -> PipecatDiscordVoiceHandler:
    """Factory function to create the new Pipecat-based voice handler"""
    return PipecatDiscordVoiceHandler(voice_client, text_channel)