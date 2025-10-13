"""Windows-optimized voice handler for Discord bot"""
import asyncio
import discord
import logging
import tempfile
import os
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class WindowsVoiceHandler:
    """Windows-optimized voice handler with proper audio support"""
    
    def __init__(self, bot, voice_client: discord.VoiceClient):
        self.bot = bot
        self.voice_client = voice_client
        self.is_listening = False
        self.temp_dir = Path(tempfile.gettempdir()) / "discord_bot_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
    async def start_listening(self):
        """Start listening for voice input"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Cannot start listening - voice client not connected")
            return False
            
        self.is_listening = True
        logger.info(f"Voice handler ready for {self.voice_client.channel.name}")
        
        # Set up voice receive using discord.py recording functionality
        try:
            # Start recording from voice channel
            await self._setup_voice_recording()
            logger.info("✅ Voice input listening enabled - bot can now hear you!")
            logger.info("🎤 Speak in the voice channel and bot will respond")
        except Exception as e:
            logger.warning(f"Could not enable voice receiving: {e}")
            logger.info("Bot can speak but voice input is limited")
            
        return True
    
    async def _setup_voice_recording(self):
        """Set up voice recording using discord.py recording features"""
        try:
            # Import discord recording components
            import discord
            
            # Check if recording is available
            if not hasattr(discord, 'sinks'):
                logger.warning("discord.py version doesn't support recording sinks")
                raise ImportError("Recording sinks not available")
            
            from discord.sinks import WaveSink
            
            # Create a recording sink
            self.recording_sink = WaveSink()
            
            # Check if voice client supports recording
            if not hasattr(self.voice_client, 'start_recording'):
                logger.warning("Voice client doesn't support recording")
                raise Exception("Voice client recording not supported")
            
            # Start recording all users in the voice channel
            self.voice_client.start_recording(
                self.recording_sink,
                self._on_recording_finished,
                sync_start=False
            )
            
            logger.info("Voice recording started successfully")
            
            # Set up periodic processing of audio data
            asyncio.create_task(self._process_voice_loop())
            
        except ImportError as e:
            logger.warning(f"discord.py recording components not available: {e}")
            logger.info("💡 To enable voice input, try: pip install discord.py[voice]")
            raise Exception("Recording not supported - install discord.py[voice]")
        except Exception as e:
            logger.error(f"Failed to setup voice recording: {e}")
            raise
    
    async def _on_recording_finished(self, sink, channel, *args):
        """Called when recording finishes"""
        logger.info(f"Recording finished for channel: {channel}")
        logger.info(f"Number of users with audio data: {len(sink.audio_data)}")
        
        # Process recorded audio for each user
        for user_id, audio in sink.audio_data.items():
            logger.debug(f"Processing user {user_id}, has file: {audio.file is not None}")
            
            if audio.file:
                try:
                    # Read audio data
                    audio.file.seek(0)
                    audio_bytes = audio.file.read()
                    logger.info(f"Read {len(audio_bytes)} bytes of audio for user {user_id}")
                    
                    if len(audio_bytes) > 1000:  # Only process if there's substantial audio
                        # Get the user object
                        user = self.bot.get_user(user_id)
                        if user:
                            logger.info(f"📊 Processing {len(audio_bytes)} bytes of audio from {user.display_name}")
                            
                            # Send to backend for transcription
                            asyncio.create_task(self._process_user_audio(user, audio_bytes))
                        else:
                            logger.warning(f"Could not find user object for ID {user_id}")
                    else:
                        logger.debug(f"Audio too short ({len(audio_bytes)} bytes) for user {user_id}")
                
                except Exception as e:
                    logger.error(f"Error processing audio for user {user_id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.debug(f"No audio file for user {user_id}")
    
    async def _process_voice_loop(self):
        """Periodically process voice input"""
        recording_duration = 5  # Process audio every 5 seconds
        
        while self.is_listening and self.voice_client.is_connected():
            try:
                logger.debug("Voice processing loop - waiting for audio...")
                await asyncio.sleep(recording_duration)
                
                # Stop recording to process the audio
                if self.voice_client.recording:
                    logger.info("Stopping recording to process audio...")
                    self.voice_client.stop_recording()
                    
                    # Wait a moment for the callback to process
                    await asyncio.sleep(0.5)
                    
                    # Restart recording for the next cycle
                    logger.info("Restarting voice recording for next cycle...")
                    from discord.sinks import WaveSink
                    self.recording_sink = WaveSink()  # Create new sink
                    self.voice_client.start_recording(
                        self.recording_sink,
                        self._on_recording_finished,
                        sync_start=False
                    )
                else:
                    logger.warning("Voice client not recording, attempting to start...")
                    from discord.sinks import WaveSink
                    self.recording_sink = WaveSink()
                    self.voice_client.start_recording(
                        self.recording_sink,
                        self._on_recording_finished,
                        sync_start=False
                    )
                    
            except Exception as e:
                logger.error(f"Error in voice processing loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break
    
    async def _process_user_audio(self, user, audio_bytes):
        """Process audio from a specific user"""
        try:
            logger.info(f"🎙️ Processing {len(audio_bytes)} bytes of audio from {user.display_name}")
            
            # Skip bot's own audio to prevent feedback loops
            if user.id == self.bot.user.id:
                logger.debug("Skipping bot's own audio")
                return
            
            # Transcribe audio using backend
            transcription = await self.bot.backend_client.transcribe_audio(audio_bytes)
            
            if transcription and len(transcription.strip()) > 3:  # Require meaningful length
                logger.info(f"👤 {user.display_name} said: '{transcription}'")
                
                # Get AI response
                context = {
                    "source": "voice", 
                    "user_name": user.display_name,
                    "channel_id": str(self.voice_client.channel.id),
                    "voice_input": True
                }
                
                response = await self.bot.backend_client.send_message(
                    user_id=str(user.id),
                    message=transcription,
                    context=context
                )
                
                if response and len(response.strip()) > 0:
                    logger.info(f"🤖 Responding: '{response[:100]}...'")
                    
                    # Send text response to channel (optional - for debugging)
                    try:
                        text_channel = None
                        for channel in self.voice_client.guild.text_channels:
                            if (channel.name.lower() in ['general', 'chat', 'ai-chat', 'bot'] or 
                                channel.permissions_for(self.voice_client.guild.me).send_messages):
                                text_channel = channel
                                break
                        
                        if text_channel:
                            embed = discord.Embed(
                                title="🎤 Voice Conversation",
                                color=0x00ff00
                            )
                            embed.add_field(name=f"👤 {user.display_name}", value=transcription, inline=False)
                            embed.add_field(name="🤖 AI Response", value=response[:1000], inline=False)
                            await text_channel.send(embed=embed)
                    except Exception as embed_error:
                        logger.warning(f"Could not send text response: {embed_error}")
                    
                    # Play response as speech - this is the main interaction
                    success = await self.play_text_as_speech(response)
                    if not success:
                        logger.warning("Failed to play voice response")
                        
                else:
                    logger.warning("No AI response generated")
                
            else:
                logger.debug(f"No meaningful transcription for {user.display_name}'s audio (got: '{transcription}')")
                
        except Exception as e:
            logger.error(f"Error processing audio from {user.display_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
    async def stop_listening(self):
        """Stop listening for voice input"""
        self.is_listening = False
        logger.info("Voice handler stopped listening")
        
        # Stop recording if active
        try:
            if hasattr(self, 'voice_client') and self.voice_client and hasattr(self.voice_client, 'stop_recording'):
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
    
    async def process_voice_data(self, user, audio_data: bytes) -> Optional[str]:
        """Process voice audio data and return transcription"""
        if not audio_data or len(audio_data) == 0:
            return None
            
        try:
            # Save audio to temp file
            temp_path = self.temp_dir / f"voice_{user.id}_{asyncio.get_event_loop().time()}.wav"
            
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # Send to backend for transcription
            transcription = await self.bot.backend_client.transcribe_audio(audio_data)
            
            # Clean up temp file
            try:
                temp_path.unlink()
            except:
                pass
                
            if transcription and transcription.strip():
                logger.info(f"Transcribed: {transcription[:100]}...")
                return transcription.strip()
            else:
                logger.debug("No transcription returned from backend")
                return None
                
        except Exception as e:
            logger.error(f"Error processing voice data: {e}")
            return None
    
    async def play_text_as_speech(self, text: str, voice: str = "default"):
        """Convert text to speech and play it"""
        if not self.voice_client or not self.voice_client.is_connected():
            logger.error("Cannot play speech - voice client not connected")
            return False
            
        try:
            # Get TTS audio from backend
            audio_data = await self.bot.backend_client.text_to_speech(text, voice)
            
            if not audio_data or len(audio_data) == 0:
                logger.warning("No audio data received from TTS")
                return False
            
            logger.info(f"Received {len(audio_data)} bytes of audio data from backend")
            # Check if it's actually MP3 data by looking at header
            if (audio_data[:3] == b'ID3' or  # ID3 tag
                audio_data[:2] == b'\xff\xfb' or  # MP3 sync frame
                audio_data[:2] == b'\xff\xf3' or  # MP3 sync frame  
                audio_data[:2] == b'\xff\xf2'):   # MP3 sync frame
                logger.info("Audio data appears to be MP3 format")
            else:
                logger.warning(f"Audio data doesn't appear to be MP3. First 10 bytes: {audio_data[:10]}")
            
            # Save to temp file with correct MP3 extension
            temp_path = self.temp_dir / f"tts_{asyncio.get_event_loop().time()}.mp3"
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # Play the audio
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.1)
            
            try:
                # Simplified Windows-compatible FFmpeg options
                ffmpeg_options = {
                    'before_options': '-loglevel verbose',
                    'options': '-vn'
                }
                
                logger.info(f"Creating FFmpeg audio source from: {temp_path}")
                logger.info(f"File size: {temp_path.stat().st_size} bytes")
                
                # Verify file exists and has content before creating audio source
                if not temp_path.exists():
                    logger.error("Audio file doesn't exist")
                    return False
                
                if temp_path.stat().st_size == 0:
                    logger.error("Audio file is empty")
                    return False
                
                audio_source = discord.FFmpegPCMAudio(
                    str(temp_path),
                    **ffmpeg_options
                )
                
                logger.info(f"Created audio source, starting playback...")
                
                # Add error callback to catch audio source errors
                def after_audio(error):
                    if error:
                        logger.error(f"Audio playback error: {error}")
                    else:
                        logger.info("Audio playback completed successfully")
                
                self.voice_client.play(audio_source, after=after_audio)
                
                # Check if playback started
                if not self.voice_client.is_playing():
                    logger.error("Audio playback failed to start!")
                    return False
                
                logger.info("Audio playback started successfully")
                
                # Wait for playback to complete with timeout
                playback_time = 0
                max_wait_time = 30  # Maximum 30 seconds
                
                while self.voice_client.is_playing() and playback_time < max_wait_time:
                    await asyncio.sleep(0.1)
                    playback_time += 0.1
                    if playback_time % 2.0 < 0.1:  # Log every 2 seconds
                        logger.info(f"Playing audio... {playback_time:.1f}s")
                
                if playback_time >= max_wait_time:
                    logger.warning(f"Audio playback timed out after {max_wait_time}s")
                    self.voice_client.stop()
                    return False
                
                logger.info(f"Audio playback finished after {playback_time:.1f}s - Text: {text[:50]}...")
                
                # Test if Discord voice connection is healthy
                if self.voice_client.is_connected():
                    logger.info("Voice client still connected after playback")
                else:
                    logger.warning("Voice client disconnected during playback")
                
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
    
    async def cleanup(self):
        """Clean up voice handler resources"""
        await self.stop_listening()
        
        # Clean up all temp files
        try:
            for file in self.temp_dir.glob("*"):
                file.unlink()
            self.temp_dir.rmdir()
        except Exception as e:
            logger.error(f"Error during voice handler cleanup: {e}")


