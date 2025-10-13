#!/usr/bin/env python3
"""
REAL Voice Capture Bot using py-cord
Actually captures and processes voice audio from Discord users
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
            if len(audio_data) < 8000:  # Too short (less than ~0.5 seconds)
                logger.info(f"[VOICE] Audio too short from {user.display_name}: {len(audio_data)} bytes")
                return
            
            logger.info(f"[VOICE] Processing {len(audio_data)} bytes from {user.display_name}")
            
            # Send status update
            guild = self.bot.get_guild(guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(f"🎤 **REAL VOICE CAPTURED** from {user.display_name} ({len(audio_data)} bytes)")
            
            # Step 1: Send audio to backend for transcription
            logger.info("[ASR] Sending audio to backend for transcription...")
            text = await self.backend_client.transcribe_audio(audio_data)
            
            if not text or not text.strip():
                logger.warning("[WARN] Empty transcription from backend")
                if channel:
                    await channel.send(f"❓ Could not transcribe speech from {user.display_name}")
                return
            
            logger.info(f"[ASR] Transcribed: '{text}'")
            
            # Step 2: Get AI response from backend
            logger.info("[LLM] Getting AI response from backend...")
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
                logger.warning("[WARN] Empty AI response from backend")
                return
            
            logger.info(f"[LLM] AI Response: {response[:100]}...")
            
            # Step 3: Generate TTS response
            logger.info("[TTS] Generating speech response...")
            audio_response = await self.backend_client.text_to_speech(response)
            
            if not audio_response:
                logger.warning("[WARN] TTS generation failed")
                if channel:
                    await channel.send(f"🔇 TTS generation failed")
                return
            
            logger.info(f"[TTS] Generated {len(audio_response)} bytes of speech")
            
            # Step 4: Play response in voice channel
            if guild.voice_client and guild.voice_client.is_connected():
                logger.info("[AUDIO] Playing AI response...")
                success = await self._play_audio_response(audio_response, guild.voice_client)
                
                # Show conversation in text
                if channel:
                    embed = discord.Embed(
                        title="🎙️ REAL Voice Conversation",
                        description="Actual voice captured and processed!",
                        color=0x00ff00
                    )
                    embed.add_field(name="🎤 You said:", value=text, inline=False)
                    embed.add_field(name="🤖 AI replied:", value=response[:1000], inline=False)
                    embed.add_field(
                        name="📊 Processing Stats:", 
                        value=f"Voice: {len(audio_data)} bytes\\nResponse: {len(audio_response)} bytes\\nPlayback: {'✅ Success' if success else '❌ Failed'}", 
                        inline=False
                    )
                    await channel.send(embed=embed)
                
                logger.info("[SUCCESS] ✅ REAL voice conversation completed!")
            else:
                logger.warning("[WARN] No voice connection for audio playback")
                
        except Exception as e:
            logger.error(f"[ERROR] Voice processing error: {e}")
            # Send error notification
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
                
                # Wait for playback to complete
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

class RealVoiceCaptureBot(discord.Bot):  # Use discord.Bot for py-cord
    """Bot that actually captures voice using py-cord sinks"""
    
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
                
                # Initialize voice processor
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
        else:
            logger.error("❌ Voice capture not available - py-cord sinks missing")
    
    @discord.slash_command(name="capture", description="Start capturing real voice from users")
    async def capture_voice(self, ctx):
        """Start real voice capture"""
        if not ctx.author.voice:
            await ctx.respond("❌ You need to be in a voice channel!")
            return
        
        if not self.backend_client:
            await ctx.respond("❌ Backend API not connected!")
            return
        
        channel = ctx.author.voice.channel
        guild_id = ctx.guild.id
        
        try:
            # Connect to voice if not already connected
            if not ctx.guild.voice_client:
                voice_client = await channel.connect()
                logger.info(f"[CONNECT] Connected to {channel.name}")
            else:
                voice_client = ctx.guild.voice_client
            
            # Create a WaveSink to capture audio
            sink = discord.sinks.WaveSink()
            
            # Start recording with our callback
            voice_client.start_recording(
                sink, 
                self._recording_finished_callback,
                ctx
            )
            
            self.recording_guilds.add(guild_id)
            
            embed = discord.Embed(
                title="🎙️ REAL Voice Capture Started!",
                description=f"Now capturing actual voice from **{channel.name}**!",
                color=0x00ff00
            )
            embed.add_field(
                name="🔥 This is REAL capture!",
                value="• Actually recording voice audio\\n• Processing through your AI models\\n• Real speech-to-text\\n• Real AI responses\\n• Real text-to-speech",
                inline=False
            )
            embed.add_field(
                name="How to test:",
                value="• **Speak into your microphone**\\n• Bot will capture your voice\\n• Process with Parakeet + Phi-3 + Kokoro\\n• Play AI response back",
                inline=False
            )
            embed.add_field(
                name="Commands:",
                value="`/stop` - Stop voice capture\\n`/test <text>` - Test without voice",
                inline=False
            )
            
            await ctx.respond(embed=embed)
            logger.info(f"🎤 REAL voice capture started in {channel.name}")
            
        except Exception as e:
            await ctx.respond(f"❌ Failed to start capture: {str(e)}")
            logger.error(f"[ERROR] Capture start error: {e}")
    
    @discord.slash_command(name="stop", description="Stop voice capture")
    async def stop_capture(self, ctx):
        """Stop voice capture"""
        try:
            if ctx.guild.voice_client and ctx.guild.voice_client.recording:
                ctx.guild.voice_client.stop_recording()
                self.recording_guilds.discard(ctx.guild.id)
                await ctx.respond("🔇 Voice capture stopped!")
            else:
                await ctx.respond("❌ Not currently capturing voice!")
                
        except Exception as e:
            await ctx.respond(f"❌ Error: {str(e)}")
    
    @discord.slash_command(name="leave", description="Leave voice channel")
    async def leave_voice(self, ctx):
        """Leave voice channel"""
        try:
            if ctx.guild.voice_client:
                if ctx.guild.voice_client.recording:
                    ctx.guild.voice_client.stop_recording()
                await ctx.guild.voice_client.disconnect()
                self.recording_guilds.discard(ctx.guild.id)
                await ctx.respond("👋 Left voice channel!")
            else:
                await ctx.respond("❌ Not in voice!")
                
        except Exception as e:
            await ctx.respond(f"❌ Error: {str(e)}")
    
    @discord.slash_command(name="test", description="Test AI pipeline with text")
    async def test_pipeline(self, ctx, text: str):
        """Test AI pipeline without voice"""
        if not self.backend_client:
            await ctx.respond("❌ Backend not connected!")
            return
        
        try:
            await ctx.defer()
            
            # Test AI response
            response = await self.backend_client.send_message(
                user_id=ctx.author.display_name,
                message=text,
                context={"source": "test", "guild_id": str(ctx.guild.id)}
            )
            
            if response:
                # Test TTS
                audio_data = await self.backend_client.text_to_speech(response)
                
                playback_success = False
                if audio_data and ctx.guild.voice_client:
                    playback_success = await self.voice_processor._play_audio_response(
                        audio_data, ctx.guild.voice_client
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
                
                await ctx.followup.send(embed=embed)
            else:
                await ctx.followup.send("❌ No response from AI")
                
        except Exception as e:
            await ctx.followup.send(f"❌ Test error: {str(e)}")
    
    @discord.slash_command(name="status", description="Show bot status")
    async def show_status(self, ctx):
        """Show bot status"""
        embed = discord.Embed(title="🎙️ Real Voice Capture Bot Status", color=0x0099ff)
        
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
        
        await ctx.respond(embed=embed)
    
    async def _recording_finished_callback(self, sink: discord.sinks.Sink, ctx):
        """Called when recording finishes or processes audio"""
        try:
            if not sink.audio_data:
                logger.info("[RECORD] No audio data captured")
                return
            
            logger.info(f"[RECORD] Captured audio from {len(sink.audio_data)} users")
            
            # Process each user's audio
            for user_id, audio in sink.audio_data.items():
                user = self.get_user(user_id)
                if user and not user.bot:
                    # Get the raw audio data
                    audio_bytes = audio.file.getvalue()
                    
                    if len(audio_bytes) > 0:
                        logger.info(f"[CAPTURE] Processing {len(audio_bytes)} bytes from {user.display_name}")
                        
                        # Process through AI pipeline
                        if self.voice_processor:
                            await self.voice_processor.process_voice_data(
                                audio_bytes, user, ctx.guild.id
                            )
                    else:
                        logger.info(f"[CAPTURE] Empty audio from {user.display_name}")
                        
        except Exception as e:
            logger.error(f"[ERROR] Recording callback error: {e}")

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = RealVoiceCaptureBot()
    
    try:
        logger.info("[START] Starting REAL Voice Capture Bot...")
        logger.info("[INFO] Using py-cord with actual voice recording!")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()