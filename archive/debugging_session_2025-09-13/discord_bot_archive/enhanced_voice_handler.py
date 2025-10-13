"""Enhanced voice handler with VAD and local models"""
import asyncio
import discord
import logging
import tempfile
import os
import numpy as np
from typing import Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import VAD components
try:
    import torch
    import torchaudio
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logger.warning("Audio processing libraries not available")

class SimpleVAD:
    """Simple Voice Activity Detection using volume thresholding"""
    
    def __init__(self, threshold: float = 0.01, min_duration: float = 0.3):
        self.threshold = threshold
        self.min_duration = min_duration  # Minimum duration to consider speech
        
    def detect_speech(self, audio_data: bytes, sample_rate: int = 48000) -> bool:
        """Detect if audio contains speech"""
        try:
            # Convert bytes to numpy array
            if len(audio_data) == 0:
                return False
                
            # Assume 16-bit PCM audio
            audio_samples = np.frombuffer(audio_data, dtype=np.int16)
            
            if len(audio_samples) == 0:
                return False
            
            # Calculate RMS (Root Mean Square) for volume level
            rms = np.sqrt(np.mean(audio_samples.astype(np.float32) ** 2))
            
            # Normalize to 0-1 range
            normalized_rms = rms / 32768.0  # 16-bit max value
            
            # Check duration (rough estimate)
            duration = len(audio_samples) / sample_rate
            
            has_speech = normalized_rms > self.threshold and duration >= self.min_duration
            
            logger.debug(f"VAD: RMS={normalized_rms:.4f}, Duration={duration:.2f}s, Speech={has_speech}")
            
            return has_speech
            
        except Exception as e:
            logger.error(f"VAD error: {e}")
            return False

class EnhancedVoiceHandler:
    """Enhanced voice handler with VAD and local model integration"""
    
    def __init__(self, bot, voice_client, backend_client):
        self.bot = bot
        self.voice_client = voice_client
        self.backend_client = backend_client
        self.is_listening = False
        self.temp_dir = Path(tempfile.gettempdir()) / "discord_bot_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
        # VAD configuration
        self.vad = SimpleVAD(threshold=0.015, min_duration=0.5)
        self.recording_sink = None
        
        # State tracking
        self.last_activity = 0
        self.processing_audio = False
        
    async def start_voice_pipeline(self):
        """Start the enhanced voice processing pipeline"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Cannot start voice pipeline - voice client not connected")
            return False
            
        self.is_listening = True
        logger.info(f"Enhanced voice handler ready for {self.voice_client.channel.name}")
        
        # Set up voice recording with VAD
        try:
            await self._setup_voice_recording()
            logger.info("✅ Voice pipeline started with VAD")
            logger.info("🎤 Speak in the voice channel - I'll respond when you're done talking!")
            
            # Start the VAD processing loop
            asyncio.create_task(self._vad_processing_loop())
            
        except Exception as e:
            logger.warning(f"Could not enable enhanced voice recording: {e}")
            logger.info("Bot can speak but voice input is limited")
            
        return True
        
    async def _setup_voice_recording(self):
        """Set up voice recording"""
        try:
            import discord
            from discord.sinks import WaveSink
            
            # Create a recording sink
            self.recording_sink = WaveSink()
            
            # Start recording all users in the voice channel
            self.voice_client.start_recording(
                self.recording_sink,
                self._on_recording_finished,
                sync_start=False
            )
            
            logger.info("Voice recording started successfully")
            
        except ImportError:
            logger.warning("discord.py recording components not available")
            raise Exception("Recording not supported - install discord.py[voice]")
        except Exception as e:
            logger.error(f"Failed to setup voice recording: {e}")
            raise
            
    async def _vad_processing_loop(self):
        """VAD-based audio processing loop"""
        logger.info("🎙️ VAD processing loop started")
        loop_count = 0
        
        while self.is_listening and self.voice_client.is_connected():
            try:
                loop_count += 1
                if loop_count % 10 == 1:  # Log every 10 seconds
                    logger.info(f"🎤 VAD loop active (cycle {loop_count}), recording: {self.voice_client.recording}")
                
                await asyncio.sleep(1.0)  # Check every second
                
                # Stop recording periodically to check for activity
                if self.voice_client.recording:
                    logger.debug("⏹️ Stopping recording to process audio...")
                    self.voice_client.stop_recording()
                    
                    # Wait for processing
                    await asyncio.sleep(0.2)
                    
                    # Start new recording cycle
                    if self.is_listening and self.voice_client.is_connected():
                        from discord.sinks import WaveSink
                        self.recording_sink = WaveSink()
                        logger.debug("▶️ Starting new recording cycle...")
                        self.voice_client.start_recording(
                            self.recording_sink,
                            self._on_recording_finished,
                            sync_start=False
                        )
                
            except Exception as e:
                logger.error(f"Error in VAD processing loop: {e}")
                break
                
        logger.info("🛑 VAD processing loop ended")
                
    async def _on_recording_finished(self, sink, *args):
        """Called when recording finishes - now with VAD"""
        if self.processing_audio:
            logger.debug("⏭️ Skipping recording - already processing audio")
            return  # Skip if already processing
            
        logger.info(f"🎬 Recording finished - checking {len(sink.audio_data)} users for audio")
        
        # Process recorded audio for each user
        for user_id, audio in sink.audio_data.items():
            if audio.file:
                try:
                    # Read audio data
                    audio.file.seek(0)
                    audio_bytes = audio.file.read()
                    
                    if len(audio_bytes) > 100:  # Minimum audio data
                        # Apply VAD
                        has_speech = self.vad.detect_speech(audio_bytes)
                        
                        if has_speech:
                            # Get the user object
                            user = self.bot.get_user(user_id)
                            if user and user.id != self.bot.user.id:  # Don't process bot's own audio
                                logger.info(f"🎤 Speech detected from {user.display_name} ({len(audio_bytes)} bytes)")
                                
                                # Process with local models
                                asyncio.create_task(self._process_user_audio(user, audio_bytes))
                            
                        else:
                            logger.debug(f"No speech detected for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing audio for user {user_id}: {e}")
                    
    async def _process_user_audio(self, user, audio_bytes):
        """Process audio from a specific user using local models"""
        if self.processing_audio:
            return
            
        self.processing_audio = True
        
        try:
            logger.info(f"🎙️ Processing {len(audio_bytes)} bytes from {user.display_name}")
            
            # Transcribe using local/backend models
            transcription = await self.backend_client.transcribe_audio(audio_bytes)
            
            if transcription and len(transcription.strip()) > 3:
                logger.info(f"👤 {user.display_name} said: '{transcription}'")
                
                # Generate AI response using local models
                context = {
                    "source": "voice",
                    "user_name": user.display_name,
                    "channel_id": str(self.voice_client.channel.id),
                    "voice_input": True,
                    "enhanced_vad": True
                }
                
                response = await self.backend_client.send_message(
                    user_id=str(user.id),
                    message=transcription,
                    context=context
                )
                
                if response and len(response.strip()) > 0:
                    logger.info(f"🤖 Responding: '{response[:100]}...'")
                    
                    # Optional: Send text response to channel
                    try:
                        text_channel = None
                        for channel in self.voice_client.guild.text_channels:
                            if (channel.name.lower() in ['general', 'chat', 'ai-chat', 'bot'] or 
                                channel.permissions_for(self.voice_client.guild.me).send_messages):
                                text_channel = channel
                                break
                        
                        if text_channel:
                            embed = discord.Embed(
                                title="🎤 Voice Conversation (Enhanced VAD)",
                                color=0x00ff00
                            )
                            embed.add_field(name=f"👤 {user.display_name}", value=transcription, inline=False)
                            embed.add_field(name="🤖 AI Response", value=response[:1000], inline=False)
                            embed.set_footer(text="Using local models with Voice Activity Detection")
                            await text_channel.send(embed=embed)
                    except Exception as embed_error:
                        logger.warning(f"Could not send text response: {embed_error}")
                    
                    # Play response as speech using local models
                    success = await self.play_text_as_speech(response)
                    if not success:
                        logger.warning("Failed to play voice response")
                        
                else:
                    logger.warning("No AI response generated")
                    
            else:
                logger.debug(f"No meaningful transcription: '{transcription}'")
                
        except Exception as e:
            logger.error(f"Error processing audio from {user.display_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.processing_audio = False
            
    async def play_text_as_speech(self, text: str, voice: str = "default"):
        """Play text as speech using local/backend TTS"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Cannot play speech - voice client not connected")
            return False
            
        try:
            # Get TTS audio from backend (will use local models first)
            audio_data = await self.backend_client.text_to_speech(text, voice)
            
            if not audio_data or len(audio_data) == 0:
                logger.warning("No audio data received from TTS")
                return False
            
            logger.info(f"Received {len(audio_data)} bytes of audio data")
            
            # Save to temp file
            temp_path = self.temp_dir / f"tts_{asyncio.get_event_loop().time()}.mp3"
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # Play the audio
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.1)
            
            try:
                # Use simplified FFmpeg options
                ffmpeg_options = {
                    'before_options': '-loglevel quiet',
                    'options': '-vn'
                }
                
                audio_source = discord.FFmpegPCMAudio(
                    str(temp_path),
                    **ffmpeg_options
                )
                
                def after_audio(error):
                    if error:
                        logger.error(f"Audio playback error: {error}")
                    else:
                        logger.debug("Audio playback completed")
                
                self.voice_client.play(audio_source, after=after_audio)
                
                # Wait for playback to complete
                playback_time = 0
                max_wait_time = 30  # Maximum 30 seconds
                
                while self.voice_client.is_playing() and playback_time < max_wait_time:
                    await asyncio.sleep(0.1)
                    playback_time += 0.1
                
                logger.info(f"TTS playback finished after {playback_time:.1f}s")
                return True
                
            finally:
                # Clean up temp file
                try:
                    temp_path.unlink()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error playing text as speech: {e}")
            return False
            
    async def stop_voice_pipeline(self):
        """Stop the voice processing pipeline"""
        self.is_listening = False
        logger.info("Enhanced voice handler stopped")
        
        # Stop recording if active
        try:
            if self.voice_client and hasattr(self.voice_client, 'stop_recording'):
                if self.voice_client.recording:
                    self.voice_client.stop_recording()
                    logger.info("Voice recording stopped")
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
        
        # Clean up temp files
        try:
            for file in self.temp_dir.glob("*.wav"):
                file.unlink()
            for file in self.temp_dir.glob("*.mp3"):
                file.unlink()
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
            
    def get_status(self) -> Dict[str, Any]:
        """Get voice handler status"""
        return {
            "pipecat_available": False,
            "pipeline_running": self.is_listening,
            "vad_enabled": True,
            "vad_type": "Simple RMS-based VAD",
            "local_models": {
                "stt": "parakeet_tdt/whisper_fallback",
                "llm": "phi3_mini/api_fallback",
                "tts": "kokoro_tts/openai_fallback"
            },
            "enhanced_mode": True
        }


def create_voice_handler(bot, voice_client, backend_client):
    """Create enhanced voice handler with VAD"""
    logger.info("Creating enhanced voice handler with local VAD")
    return EnhancedVoiceHandler(bot, voice_client, backend_client)