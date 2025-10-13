#!/usr/bin/env python3
"""
WSL2 Discord Bot with Real Voice Recording
Tests actual voice capture from Discord users
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
import wave
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from backend_client import BackendClient
from config import Config
from clean_logger import setup_clean_logging

# Setup clean logging
setup_clean_logging()

logger = logging.getLogger(__name__)

# Suppress Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Force load Opus
logger.info("[SETUP] Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "[OK] Loaded" if discord.opus.is_loaded() else "[ERROR] Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"[ERROR] Opus error: {e}")

class VoiceRecorder:
    """Records voice data from Discord users"""
    
    def __init__(self, voice_handler):
        self.voice_handler = voice_handler
        self.recording_users = {}  # user_id -> audio_buffer
        self.is_recording = True
        
    def add_user_audio(self, user, audio_data):
        """Add audio data from a user"""
        user_id = user.id
        user_name = user.display_name
        
        if user_id not in self.recording_users:
            self.recording_users[user_id] = {
                'name': user_name,
                'audio_chunks': [],
                'last_audio_time': asyncio.get_event_loop().time()
            }
        
        # Add audio chunk
        self.recording_users[user_id]['audio_chunks'].append(audio_data)
        self.recording_users[user_id]['last_audio_time'] = asyncio.get_event_loop().time()
        
        # If we have enough audio (about 2 seconds), process it
        total_duration = len(self.recording_users[user_id]['audio_chunks']) * 0.02  # 20ms per chunk
        if total_duration >= 2.0:
            asyncio.create_task(self.process_user_audio(user_id))
    
    async def process_user_audio(self, user_id):
        """Process accumulated audio from a user"""
        if user_id not in self.recording_users:
            return
        
        user_data = self.recording_users[user_id]
        user_name = user_data['name']
        audio_chunks = user_data['audio_chunks']
        
        # Clear the buffer
        self.recording_users[user_id]['audio_chunks'] = []
        
        if not audio_chunks:
            return
        
        logger.info(f"[VOICE] Processing {len(audio_chunks)} audio chunks from {user_name}")
        
        try:
            # Combine audio chunks into a single audio file
            audio_data = self.combine_audio_chunks(audio_chunks)
            if audio_data:
                # Process through backend
                await self.voice_handler.process_audio(audio_data, user_name)
        except Exception as e:
            logger.error(f"[ERROR] Failed to process audio from {user_name}: {e}")
    
    def combine_audio_chunks(self, chunks: List[bytes]) -> Optional[bytes]:
        """Combine audio chunks into a WAV file"""
        try:
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Discord audio is 48kHz, 2 channels, 16-bit
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(2)  # stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(48000)  # 48kHz
                
                # Write all chunks
                for chunk in chunks:
                    wav_file.writeframes(chunk)
            
            # Read the WAV file back
            with open(temp_path, 'rb') as f:
                wav_data = f.read()
            
            # Clean up
            os.unlink(temp_path)
            
            logger.info(f"[AUDIO] Combined {len(chunks)} chunks into {len(wav_data)} bytes")
            return wav_data
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to combine audio chunks: {e}")
            return None

class CustomSink(discord.sinks.Sink):
    """Custom audio sink for capturing user voice"""
    
    def __init__(self, voice_recorder: VoiceRecorder):
        super().__init__()
        self.voice_recorder = voice_recorder
        
    def wants_opus(self) -> bool:
        return False  # We want PCM data
    
    def write(self, data, user):
        """Called when audio data is available"""
        if user and data:
            # Add to our voice recorder
            self.voice_recorder.add_user_audio(user, data)

class VoiceListeningHandler:
    """Voice handler that actually listens to users"""
    
    def __init__(self, bot, guild_id: int, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.backend_client = backend_client
        self.recording = False
        self.voice_client = None
        self.voice_recorder = None
        self.sink = None
        
        logger.info(f"[OK] Voice listening handler initialized for guild {guild_id}")
    
    async def start_listening(self, voice_client):
        """Start voice processing with real recording"""
        self.voice_client = voice_client
        self.recording = True
        
        # Create voice recorder
        self.voice_recorder = VoiceRecorder(self)
        
        # Create custom sink
        self.sink = CustomSink(self.voice_recorder)
        
        # Start recording
        logger.info("[VOICE] Starting real voice recording...")
        
        try:
            # Start recording with our custom sink
            self.voice_client.start_recording(self.sink, self._recording_finished)
            logger.info("[OK] Voice recording started successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to start recording: {e}")
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_recording())
    
    async def stop_listening(self):
        """Stop voice processing"""
        self.recording = False
        
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
        
        if self.voice_client and hasattr(self.voice_client, 'stop_recording'):
            try:
                self.voice_client.stop_recording()
                logger.info("[STOP] Voice recording stopped")
            except Exception as e:
                logger.error(f"[ERROR] Error stopping recording: {e}")
        
        logger.info("[MUTE] Voice pipeline stopped")
    
    async def _monitor_recording(self):
        """Monitor the recording process"""
        try:
            while self.recording:
                await asyncio.sleep(5)
                if self.voice_recorder:
                    active_users = len(self.voice_recorder.recording_users)
                    logger.info(f"[MONITOR] Recording active, {active_users} users detected")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Monitor error: {e}")
    
    def _recording_finished(self, sink, error=None):
        """Called when recording finishes"""
        if error:
            logger.error(f"[ERROR] Recording finished with error: {error}")
        else:
            logger.info("[STOP] Recording finished normally")
    
    async def process_audio(self, audio_data: bytes, user_name: str):
        """Process audio through backend"""
        try:
            if not audio_data or len(audio_data) < 1000:
                logger.warning(f"[WARN] Audio too short from {user_name}: {len(audio_data) if audio_data else 0} bytes")
                return
            
            logger.info(f"[VOICE] Processing {len(audio_data)} bytes from {user_name}")
            
            # Test: just confirm we received audio
            logger.info(f"[TEST] Received audio from {user_name} - {len(audio_data)} bytes")
            
            # For now, let's just send a confirmation message instead of full processing
            # This tests if voice capture is working
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    embed = discord.Embed(
                        title="Voice Detected!",
                        description=f"Heard {len(audio_data)} bytes of audio from **{user_name}**",
                        color=0x00ff00
                    )
                    await channel.send(embed=embed)
            
            # Optional: Uncomment below for full processing
            """
            # Transcribe through backend
            text = await self.backend_client.transcribe_audio(audio_data)
            if not text or text.strip() == "":
                logger.warning("[WARN] Empty transcription")
                return
            
            logger.info(f"[TEXT] Transcribed: {text}")
            
            # Get AI response through backend
            response = await self.backend_client.send_message(
                user_id=user_name,
                message=text,
                context={"source": "voice", "guild_id": str(self.guild_id)}
            )
            
            if response:
                logger.info(f"[BOT] AI Response: {response[:100]}...")
                
                # Convert to speech and play
                audio_response = await self.backend_client.text_to_speech(response)
                if audio_response:
                    await self.play_audio(audio_response)
            """
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio processing error: {e}")
    
    async def speak_text(self, text: str):
        """Convert text to speech and play"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                logger.warning("[WARN] No voice connection")
                return False
            
            logger.info(f"[SPEAK] Generating speech: {text[:50]}...")
            audio_data = await self.backend_client.text_to_speech(text)
            
            if not audio_data:
                logger.warning("[WARN] No audio generated")
                return False
            
            logger.info(f"[OK] Generated {len(audio_data)} bytes of audio")
            success = await self.play_audio(audio_data)
            return success
            
        except Exception as e:
            logger.error(f"[ERROR] TTS error: {e}")
            return False
    
    async def play_audio(self, audio_data: bytes) -> bool:
        """Play audio through Discord voice"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return False
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(
                    temp_path,
                    options='-loglevel error'
                )
                
                self.voice_client.play(audio_source)
                
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                logger.info("[OK] Audio playback complete")
                return True
                
            finally:
                await asyncio.sleep(0.5)
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio playback error: {e}")
            return False

class VoiceRecordingBot(discord.Client):
    """Discord bot with real voice recording"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers: Dict[int, VoiceListeningHandler] = {}
        self.backend_client = None
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Initialize backend client
        try:
            self.backend_client = BackendClient(
                base_url=Config.BACKEND_API_URL,
                api_key=Config.BACKEND_API_KEY
            )
            
            if await self.backend_client.health_check():
                logger.info("[OK] Backend API connected")
            else:
                logger.warning("[WARN] Backend health check failed")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend initialization error: {e}")
            self.backend_client = None
        
        # Show component status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        
        logger.info(f"[STATUS] Components: Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!listen':
            await self._start_listening(message)
        elif content == '!stop':
            await self._stop_listening(message)
        elif content.startswith('!speak '):
            await self._speak_text(message, content[7:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_listening(self, message):
        """Start listening for voice"""
        if not message.author.voice:
            await message.reply("You need to be in a voice channel!")
            return
        
        if not self.backend_client:
            await message.reply("Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await asyncio.sleep(1)
            
            # Connect
            voice_client = await channel.connect(timeout=20.0, reconnect=False)
            await asyncio.sleep(1)
            
            if voice_client and voice_client.is_connected():
                # Initialize voice handler
                handler = VoiceListeningHandler(self, guild_id, self.backend_client)
                self.voice_handlers[guild_id] = handler
                await handler.start_listening(voice_client)
                
                embed = discord.Embed(
                    title="Voice Recording Active!",
                    description=f"Connected to **{channel.name}** and listening for voice input!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Test Instructions",
                    value="1. **Speak into your microphone**\n2. Bot will detect voice and show confirmation\n3. Use `!stop` to stop listening",
                    inline=False
                )
                embed.add_field(
                    name="What's Happening",
                    value="• Recording your voice in real-time\n• Processing audio chunks\n• Will show detection messages",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[OK] Voice recording started in {channel.name}")
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            await message.reply(f"Failed to start listening: {str(e)}")
            logger.error(f"[ERROR] Listen error: {e}")
    
    async def _stop_listening(self, message):
        """Stop listening"""
        guild_id = message.guild.id
        
        try:
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].stop_listening()
                del self.voice_handlers[guild_id]
            
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await message.reply("Stopped listening and left voice channel!")
            else:
                await message.reply("Not currently listening!")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak text"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("Not listening! Use `!listen` first.")
            return
        
        if not text.strip():
            await message.reply("Provide text to speak!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            await message.reply(f"Speaking: *{text[:100]}...*")
            
            success = await handler.speak_text(text)
            if not success:
                await message.reply("TTS playback issue - check logs")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show status"""
        embed = discord.Embed(title="Voice Recording Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        listening_count = len(self.voice_handlers)
        
        embed.add_field(
            name="Bot Status",
            value=f"Latency: {round(self.latency * 1000)}ms\nGuilds: {len(self.guilds)}\nListening: {listening_count} channels",
            inline=True
        )
        
        embed.add_field(
            name="Components",
            value=f"Opus: {opus_status}\nBackend API: {backend_status}\nVoice Recording: OK",
            inline=True
        )
        
        if listening_count > 0:
            embed.add_field(
                name="Active Channels",
                value=f"{listening_count} voice channels being monitored",
                inline=False
            )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="Voice Recording Test Bot",
            description="Tests real voice capture from Discord users",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Commands",
            value="`!listen` - Start listening in your voice channel\n"
                  "`!stop` - Stop listening and disconnect\n"
                  "`!speak <text>` - Test TTS playback",
            inline=False
        )
        
        embed.add_field(
            name="Info Commands",
            value="`!status` - Show bot status\n"
                  "`!help` - Show this help",
            inline=False
        )
        
        embed.add_field(
            name="Testing Steps",
            value="1. Join a voice channel\n"
                  "2. Use `!listen` to start recording\n"
                  "3. **Speak into your microphone**\n"
                  "4. Watch for voice detection messages\n"
                  "5. Use `!stop` when done",
            inline=False
        )
        
        await message.reply(embed=embed)

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = VoiceRecordingBot()
    
    try:
        logger.info("[START] Starting Voice Recording Test Bot...")
        logger.info(f"[API] Backend URL: {Config.BACKEND_API_URL}")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()