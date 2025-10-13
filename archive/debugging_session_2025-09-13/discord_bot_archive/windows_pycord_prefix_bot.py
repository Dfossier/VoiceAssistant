#!/usr/bin/env python3
"""
Windows py-cord Voice Bot with Prefix Commands (!commands)
Real voice capture with immediate command response
"""

import asyncio
import discord
import discord.opus
import discord.sinks
import logging
import sys
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import io

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

class VoiceProcessor:
    """Processes captured voice data"""
    
    def __init__(self, bot, backend_client: BackendClient):
        self.bot = bot
        self.backend_client = backend_client
        
    async def process_voice_data(self, audio_data: bytes, user, guild_id: int):
        """Process captured voice data through AI pipeline"""
        try:
            logger.info(f"[DEBUG] process_voice_data called with {len(audio_data)} bytes from {user.display_name}")
            
            if len(audio_data) < 100:  # Very short check
                logger.info(f"[VOICE] Audio too short from {user.display_name}: {len(audio_data)} bytes")
                return
            
            logger.info(f"[VOICE] 🎉 REAL VOICE CAPTURED from {user.display_name}: {len(audio_data)} bytes")
            
            # Send status update
            guild = self.bot.get_guild(guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(f"🎤 **REAL VOICE CAPTURED!** Processing {len(audio_data)} bytes from **{user.display_name}**...")
            
            # Debug: Check if audio_data is valid
            logger.info(f"[DEBUG] Audio data first 20 bytes: {audio_data[:20]}")
            
            # Step 1: Send audio to backend for transcription
            logger.info("[ASR] 🔄 Sending real audio to backend for transcription...")
            text = await self.backend_client.transcribe_audio(audio_data)
            
            logger.info(f"[ASR] 📝 Raw transcription result: '{text}' (length: {len(text) if text else 0})")
            
            if not text or not text.strip():
                logger.warning("[WARN] ❌ Empty or None transcription from backend!")
                if channel:
                    await channel.send(f"❓ Could not transcribe speech from **{user.display_name}** - got empty result")
                return
            
            logger.info(f"[ASR] ✅ Successfully transcribed: '{text}'")
            
            # Step 2: Get AI response
            logger.info("[LLM] Getting AI response...")
            response = await self.backend_client.send_message(
                user_id=user.display_name,
                message=text,
                context={
                    "source": "real_voice", 
                    "guild_id": str(guild_id),
                    "audio_length": len(audio_data)
                }
            )
            
            if not response:
                logger.warning("[WARN] Empty AI response")
                return
            
            logger.info(f"[LLM] ✅ AI Response: {response[:100]}...")
            
            # Step 3: Generate TTS
            logger.info("[TTS] Generating speech...")
            audio_response = await self.backend_client.text_to_speech(response)
            
            if not audio_response:
                logger.warning("[WARN] TTS generation failed")
                if channel:
                    await channel.send("🔇 TTS generation failed")
                return
            
            logger.info(f"[TTS] ✅ Generated {len(audio_response)} bytes of speech")
            
            # Step 4: Play response
            if guild.voice_client and guild.voice_client.is_connected():
                logger.info("[AUDIO] Playing AI response...")
                success = await self._play_audio_response(audio_response, guild.voice_client)
                
                # Show conversation
                if channel:
                    embed = discord.Embed(
                        title="🎙️ REAL Voice Conversation Complete!",
                        description="Your actual voice was captured and processed!",
                        color=0x00ff00
                    )
                    embed.add_field(name="🎤 You said:", value=text, inline=False)
                    embed.add_field(name="🤖 AI replied:", value=response[:1000], inline=False)
                    embed.add_field(
                        name="📊 Stats:", 
                        value=f"Voice: {len(audio_data)} bytes\\nResponse: {len(audio_response)} bytes\\nPlayback: {'✅ Success' if success else '❌ Failed'}", 
                        inline=False
                    )
                    await channel.send(embed=embed)
                
                logger.info("🎉 REAL VOICE CONVERSATION COMPLETED!")
            else:
                logger.warning("[WARN] No voice connection for playback")
                
        except Exception as e:
            logger.error(f"[ERROR] Voice processing error: {e}")
            try:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                    if channel:
                        await channel.send(f"❌ Voice processing error: {str(e)}")
            except:
                pass
    
    async def _play_audio_response(self, audio_data: bytes, voice_client) -> bool:
        """Play AI audio response"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                voice_client.play(audio_source)
                
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                logger.info("[OK] AI response playback complete")
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

class WindowsPyCordBot(discord.Client):  # Use discord.Client with prefix commands
    """py-cord bot with prefix commands for immediate response"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.backend_client = None
        self.voice_processor = None
        self.recording_guilds = set()
    
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
                self.voice_processor = VoiceProcessor(self, self.backend_client)
                logger.info("[OK] Voice processor initialized")
            else:
                logger.warning("[WARN] Backend API not available")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
            self.backend_client = None
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        sinks_status = "[OK]" if hasattr(discord, 'sinks') else "[ERROR]"
        
        logger.info(f"[STATUS] Opus: {opus_status} | Backend: {backend_status} | Sinks: {sinks_status}")
        
        if sinks_status == "[OK]":
            logger.info("🎉 REAL VOICE CAPTURE READY!")
            logger.info("💬 Use !help to see commands")
        else:
            logger.error("❌ Voice capture not available")
    
    async def on_message(self, message):
        """Handle prefix commands (!command)"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!capture' or content == '!record':
            await self._start_capture(message)
        elif content == '!stop':
            await self._stop_capture(message)
        elif content == '!leave':
            await self._leave_voice(message)
        elif content.startswith('!test '):
            await self._test_pipeline(message, content[6:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_capture(self, message):
        """Start real voice capture"""
        if not message.author.voice:
            await message.reply("❌ You need to be in a voice channel!")
            return
        
        if not self.backend_client:
            await message.reply("❌ Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        # Debug: Show who's in the voice channel
        logger.info(f"[DEBUG] Voice channel members:")
        for member in channel.members:
            logger.info(f"[DEBUG] - {member.display_name} (ID: {member.id}, bot: {member.bot})")
        logger.info(f"[DEBUG] Message author: {message.author.display_name} (ID: {message.author.id})")
        
        try:
            # Connect to voice if not already connected
            if not message.guild.voice_client:
                await message.reply("🔄 Connecting to voice...")
                voice_client = await channel.connect()
                logger.info(f"[CONNECT] Connected to {channel.name}")
            else:
                voice_client = message.guild.voice_client
            
            # Create a WaveSink to capture audio
            sink = discord.sinks.WaveSink()
            
            # Start recording
            voice_client.start_recording(
                sink, 
                self._recording_finished_callback,
                message
            )
            
            self.recording_guilds.add(guild_id)
            
            embed = discord.Embed(
                title="🎙️ REAL Voice Capture Started!",
                description=f"Now capturing actual voice from **{channel.name}**!",
                color=0x00ff00
            )
            embed.add_field(
                name="🔥 This is REAL capture!",
                value="• Actually recording voice audio\\n• Processing through Parakeet + Phi-3 + Kokoro\\n• Real speech-to-text → AI response → text-to-speech",
                inline=False
            )
            embed.add_field(
                name="How to test:",
                value="• **Speak into your microphone**\\n• Bot will capture your voice\\n• Process with AI models\\n• Play AI response back",
                inline=False
            )
            embed.add_field(
                name="Commands:",
                value="`!stop` - Stop capture\\n`!test <text>` - Test AI pipeline\\n`!leave` - Leave voice",
                inline=False
            )
            
            await message.reply(embed=embed)
            logger.info(f"🎤 REAL voice capture started in {channel.name}")
            
        except Exception as e:
            await message.reply(f"❌ Failed to start capture: {str(e)}")
            logger.error(f"[ERROR] Capture start error: {e}")
    
    async def _stop_capture(self, message):
        """Stop voice capture"""
        try:
            if message.guild.voice_client and hasattr(message.guild.voice_client, 'recording') and message.guild.voice_client.recording:
                message.guild.voice_client.stop_recording()
                self.recording_guilds.discard(message.guild.id)
                await message.reply("🔇 Voice capture stopped!")
                logger.info("[STOP] Voice capture stopped")
            else:
                await message.reply("❌ Not currently capturing voice!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _leave_voice(self, message):
        """Leave voice channel"""
        try:
            if message.guild.voice_client:
                if hasattr(message.guild.voice_client, 'recording') and message.guild.voice_client.recording:
                    message.guild.voice_client.stop_recording()
                await message.guild.voice_client.disconnect()
                self.recording_guilds.discard(message.guild.id)
                await message.reply("👋 Left voice channel!")
                logger.info("[LEAVE] Left voice channel")
            else:
                await message.reply("❌ Not in voice!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _test_pipeline(self, message, text: str):
        """Test AI pipeline without voice"""
        if not self.backend_client:
            await message.reply("❌ Backend not connected!")
            return
        
        try:
            await message.reply(f"🧪 Testing pipeline with: *{text}*")
            
            # Test AI response
            response = await self.backend_client.send_message(
                user_id=message.author.display_name,
                message=text,
                context={"source": "test", "guild_id": str(message.guild.id)}
            )
            
            if response:
                # Test TTS
                audio_data = await self.backend_client.text_to_speech(response)
                
                playback_success = False
                if audio_data and message.guild.voice_client:
                    playback_success = await self.voice_processor._play_audio_response(
                        audio_data, message.guild.voice_client
                    )
                
                embed = discord.Embed(
                    title="🧪 Pipeline Test Results",
                    color=0x0099ff
                )
                embed.add_field(name="Input:", value=text, inline=False)
                embed.add_field(name="AI Response:", value=response[:1000], inline=False)
                embed.add_field(
                    name="TTS Status:", 
                    value=f"Generated: {'✅' if audio_data else '❌'}\\nPlayed: {'✅' if playback_success else '❌'}", 
                    inline=False
                )
                
                await message.reply(embed=embed)
            else:
                await message.reply("❌ No response from AI")
                
        except Exception as e:
            await message.reply(f"❌ Test error: {str(e)}")
    
    async def _show_status(self, message):
        """Show bot status"""
        embed = discord.Embed(title="🏠 Windows py-cord Voice Bot Status", color=0x0099ff)
        
        opus_status = "✅ OK" if discord.opus.is_loaded() else "❌ ERROR"
        backend_status = "✅ OK" if self.backend_client else "❌ ERROR"
        sinks_status = "✅ OK" if hasattr(discord, 'sinks') else "❌ ERROR"
        
        embed.add_field(
            name="Core Components",
            value=f"py-cord: {discord.__version__}\\nOpus: {opus_status}\\nSinks: {sinks_status}\\nBackend: {backend_status}",
            inline=False
        )
        
        embed.add_field(
            name="Voice Capture",
            value=f"Recording: {len(self.recording_guilds)} guilds\\nReal Capture: {'✅ Enabled' if sinks_status == '✅ OK' else '❌ Disabled'}",
            inline=False
        )
        
        if self.recording_guilds:
            recording_info = []
            for guild_id in self.recording_guilds:
                guild = self.get_guild(guild_id)
                if guild and guild.voice_client:
                    channel_name = guild.voice_client.channel.name if guild.voice_client.channel else "Unknown"
                    recording_info.append(f"• {guild.name}: {channel_name}")
            
            if recording_info:
                embed.add_field(
                    name="Active Recordings",
                    value="\\n".join(recording_info),
                    inline=False
                )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🏠 Windows py-cord Voice Bot",
            description="REAL voice capture with py-cord sinks + Windows compatibility",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Commands",
            value="`!capture` - Start REAL voice capture\\n`!stop` - Stop capture\\n`!leave` - Leave voice channel",
            inline=False
        )
        
        embed.add_field(
            name="Test Commands",
            value="`!test <text>` - Test AI pipeline\\n`!status` - Show system status\\n`!help` - This help",
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value="1. Use `!capture` to start real voice recording\\n2. **Speak into your microphone**\\n3. py-cord captures actual audio\\n4. Backend processes: Voice → ASR → LLM → TTS\\n5. Bot speaks AI response back",
            inline=False
        )
        
        embed.add_field(
            name="AI Models",
            value="• **Parakeet**: Speech recognition\\n• **Phi-3**: Language model\\n• **Kokoro**: Text-to-speech",
            inline=False
        )
        
        await message.reply(embed=embed)
    
    async def _recording_finished_callback(self, sink: discord.sinks.Sink, message):
        """Called when recording processes audio"""
        try:
            logger.info(f"[DEBUG] Recording callback triggered. Sink type: {type(sink)}")
            
            if not sink.audio_data:
                logger.info("[RECORD] ❌ No audio data in sink")
                return
            
            logger.info(f"[RECORD] 🎉 Captured audio from {len(sink.audio_data)} users")
            logger.info(f"[DEBUG] Audio data keys: {list(sink.audio_data.keys())}")
            
            # Process each user's audio
            for user_id, audio in sink.audio_data.items():
                logger.info(f"[DEBUG] Processing user_id: {user_id}, audio type: {type(audio)}")
                
                # Get the raw audio data first
                audio_bytes = audio.file.getvalue()
                logger.info(f"[DEBUG] Audio bytes length: {len(audio_bytes)}")
                logger.info(f"[DEBUG] First 20 bytes: {audio_bytes[:20] if len(audio_bytes) >= 20 else audio_bytes}")
                
                # Try to get user object
                user = self.get_user(user_id)
                if not user:
                    guild = message.guild
                    user = guild.get_member(user_id)
                
                # Create a fallback user name
                user_name = user.display_name if user else f"User{user_id}"
                is_bot = user.bot if user else False
                
                logger.info(f"[DEBUG] User: {user_name}, is_bot: {is_bot}")
                
                if not is_bot and len(audio_bytes) > 0:
                    logger.info(f"[CAPTURE] 🎤 Processing {len(audio_bytes)} bytes from {user_name}")
                    
                    # Process through AI pipeline (create a mock user object if needed)
                    if self.voice_processor:
                        logger.info(f"[DEBUG] Calling voice_processor.process_voice_data...")
                        # Create a mock user object if we couldn't find the real one
                        if not user:
                            class MockUser:
                                def __init__(self, user_id, name):
                                    self.id = user_id
                                    self.display_name = name
                                    self.bot = False
                            user = MockUser(user_id, user_name)
                        
                        await self.voice_processor.process_voice_data(
                            audio_bytes, user, message.guild.id
                        )
                    else:
                        logger.error(f"[ERROR] No voice_processor available!")
                else:
                    if is_bot:
                        logger.info(f"[DEBUG] Skipping bot user: {user_name}")
                    else:
                        logger.warning(f"[CAPTURE] ❌ Empty audio from {user_name}")
                        
        except Exception as e:
            logger.error(f"[ERROR] Recording callback error: {e}")
            import traceback
            logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = WindowsPyCordBot()
    
    try:
        logger.info("[START] Starting Windows py-cord Voice Bot...")
        logger.info("[INFO] Using prefix commands (!capture, !help, etc.)")
        logger.info("[INFO] REAL voice recording with py-cord sinks!")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()