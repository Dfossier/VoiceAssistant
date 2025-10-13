#!/usr/bin/env python3
"""
Simple Voice Test Bot
Tests if voice commands work by responding to voice channel events
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

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

class SimpleVoiceBot(discord.Client):
    """Simple bot that responds to voice activity"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.my_voice_clients = {}
        self.backend_client = None
        self.listening_channels = set()
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Initialize backend
        try:
            self.backend_client = BackendClient(
                base_url=Config.BACKEND_API_URL,
                api_key=Config.BACKEND_API_KEY
            )
            
            if await self.backend_client.health_check():
                logger.info("[OK] Backend API connected")
            else:
                logger.warning("[WARN] Backend not available")
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        logger.info(f"[STATUS] Components: Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_voice_state_update(self, member, before, after):
        """Detect when users speak or join/leave voice"""
        # Skip if it's the bot itself
        if member == self.user:
            return
        
        guild_id = member.guild.id
        
        # Only monitor if we're listening in this guild
        if guild_id not in self.listening_channels:
            return
        
        # Check if user joined/left voice while we're connected
        if before.channel != after.channel:
            if after.channel and guild_id in self.my_voice_clients:
                # User joined the channel we're in
                if after.channel == self.my_voice_clients[guild_id].channel:
                    logger.info(f"[VOICE] {member.display_name} joined voice channel")
                    await self.send_voice_update(guild_id, f"{member.display_name} joined voice")
            
            if before.channel and guild_id in self.my_voice_clients:
                # User left the channel we're in
                if before.channel == self.my_voice_clients[guild_id].channel:
                    logger.info(f"[VOICE] {member.display_name} left voice channel")
                    await self.send_voice_update(guild_id, f"{member.display_name} left voice")
        
        # Check for speaking state changes (mute/unmute)
        if hasattr(before, 'self_mute') and hasattr(after, 'self_mute'):
            if before.self_mute != after.self_mute:
                if after.self_mute:
                    logger.info(f"[VOICE] {member.display_name} muted")
                    await self.send_voice_update(guild_id, f"{member.display_name} muted microphone")
                else:
                    logger.info(f"[VOICE] {member.display_name} unmuted - ready to speak!")
                    await self.send_voice_update(guild_id, f"{member.display_name} unmuted - I'm listening!")
    
    async def send_voice_update(self, guild_id: int, message: str):
        """Send voice update to text channel"""
        try:
            guild = self.get_guild(guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    embed = discord.Embed(
                        title="Voice Activity Detected",
                        description=message,
                        color=0x00ff00
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"[ERROR] Failed to send voice update: {e}")
    
    async def on_message(self, message):
        """Handle text commands"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!listen':
            await self._start_listening(message)
        elif content == '!stop':
            await self._stop_listening(message)
        elif content.startswith('!speak '):
            await self._speak_text(message, content[7:])
        elif content.startswith('!ask '):
            await self._ask_question(message, content[5:])
        elif content == '!test':
            await self._test_voice_processing(message)
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_listening(self, message):
        """Start listening in voice channel"""
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if guild_id in self.my_voice_clients:
                await self.my_voice_clients[guild_id].disconnect()
                del self.my_voice_clients[guild_id]
            
            # Connect to voice
            voice_client = await channel.connect(timeout=20.0)
            self.my_voice_clients[guild_id] = voice_client
            self.listening_channels.add(guild_id)
            
            embed = discord.Embed(
                title="Voice Monitoring Active!",
                description=f"Connected to **{channel.name}** and monitoring voice activity",
                color=0x00ff00
            )
            embed.add_field(
                name="What I'm Watching",
                value="• User join/leave events\n• Mute/unmute status\n• Voice state changes",
                inline=False
            )
            embed.add_field(
                name="Test Commands",
                value="`!test` - Test voice processing with sample text\n`!speak <text>` - Test TTS\n`!ask <question>` - Test AI chat",
                inline=False
            )
            embed.add_field(
                name="Voice Tests",
                value="• **Mute/unmute** your microphone\n• **Join/leave** the voice channel\n• Bot will detect and respond!",
                inline=False
            )
            
            await message.reply(embed=embed)
            logger.info(f"[OK] Started voice monitoring in {channel.name}")
            
        except Exception as e:
            await message.reply(f"Failed to connect: {str(e)}")
            logger.error(f"[ERROR] Connection error: {e}")
    
    async def _stop_listening(self, message):
        """Stop listening"""
        guild_id = message.guild.id
        
        if guild_id not in self.my_voice_clients:
            await message.reply("Not currently listening!")
            return
        
        try:
            await self.my_voice_clients[guild_id].disconnect()
            del self.my_voice_clients[guild_id]
            self.listening_channels.discard(guild_id)
            await message.reply("Stopped listening and disconnected from voice!")
            logger.info("[STOP] Voice monitoring stopped")
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _test_voice_processing(self, message):
        """Test the voice processing pipeline"""
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        try:
            await message.reply("Testing voice processing pipeline...")
            
            # Simulate voice input
            test_text = "Hello, this is a test of voice processing"
            
            # Step 1: Simulate transcription (normally from audio)
            logger.info("[TEST] Simulating voice transcription...")
            await message.channel.send(f"**Step 1**: Simulated transcription: '{test_text}'")
            
            # Step 2: Get AI response
            logger.info("[TEST] Getting AI response...")
            response = await self.backend_client.send_message(
                user_id=str(message.author.id),
                message=test_text,
                context={"source": "voice_test", "guild_id": str(message.guild.id)}
            )
            
            await message.channel.send(f"**Step 2**: AI Response: {response}")
            
            # Step 3: Convert to speech
            logger.info("[TEST] Generating speech...")
            audio_data = await self.backend_client.text_to_speech(response)
            
            if audio_data:
                await message.channel.send(f"**Step 3**: Generated {len(audio_data)} bytes of audio")
                
                # Step 4: Play audio if connected to voice
                guild_id = message.guild.id
                if guild_id in self.my_voice_clients:
                    await message.channel.send("**Step 4**: Playing audio...")
                    success = await self.play_audio(guild_id, audio_data)
                    if success:
                        await message.channel.send("**Voice pipeline test complete!** All steps working.")
                    else:
                        await message.channel.send("**Audio playback failed** - check logs")
                else:
                    await message.channel.send("**Step 4**: Not in voice channel - audio generated but not played")
            else:
                await message.channel.send("**Step 3 failed**: No audio generated")
            
        except Exception as e:
            await message.reply(f"Test failed: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak text through TTS"""
        guild_id = message.guild.id
        
        if guild_id not in self.my_voice_clients:
            await message.reply("Not in voice! Use `!listen` first.")
            return
        
        if not text.strip():
            await message.reply("Provide text to speak!")
            return
        
        try:
            await message.reply(f"Speaking: *{text[:100]}...*")
            
            if not self.backend_client:
                await message.reply("Backend not connected!")
                return
            
            # Generate speech
            audio_data = await self.backend_client.text_to_speech(text)
            if audio_data:
                success = await self.play_audio(guild_id, audio_data)
                if not success:
                    await message.reply("Playback failed - check logs")
            else:
                await message.reply("TTS generation failed")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _ask_question(self, message, question: str):
        """Ask AI a question"""
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        if not question.strip():
            await message.reply("Ask a question!")
            return
        
        try:
            await message.reply("Processing with Phi-3...")
            
            response = await self.backend_client.send_message(
                user_id=str(message.author.id),
                message=question,
                context={"source": "text", "guild_id": str(message.guild.id)}
            )
            
            if len(response) > 1900:
                response = response[:1900] + "..."
            
            await message.reply(response)
            
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def play_audio(self, guild_id: int, audio_data: bytes) -> bool:
        """Play audio in voice channel"""
        try:
            voice_client = self.my_voice_clients.get(guild_id)
            if not voice_client or not voice_client.is_connected():
                return False
            
            # Save to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Play audio
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                voice_client.play(audio_source)
                
                # Wait for playback
                while voice_client.is_playing():
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
            logger.error(f"[ERROR] Playback error: {e}")
            return False
    
    async def _show_status(self, message):
        """Show bot status"""
        embed = discord.Embed(title="Simple Voice Test Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Components",
            value=f"Opus: {opus_status}\nBackend: {backend_status}",
            inline=True
        )
        
        embed.add_field(
            name="Voice Monitoring",
            value=f"Active channels: {len(self.listening_channels)}\nConnected: {len(self.my_voice_clients)}",
            inline=True
        )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="Simple Voice Test Bot",
            description="Tests voice activity detection and AI processing",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Commands",
            value="`!listen` - Start monitoring voice activity\n"
                  "`!stop` - Stop monitoring\n"
                  "`!speak <text>` - Test TTS",
            inline=False
        )
        
        embed.add_field(
            name="Test Commands",
            value="`!test` - Test full voice pipeline\n"
                  "`!ask <question>` - Test AI chat\n"
                  "`!status` - Show status",
            inline=False
        )
        
        embed.add_field(
            name="How to Test Voice",
            value="1. Join voice channel, use `!listen`\n"
                  "2. **Mute/unmute** your mic (I'll detect it!)\n"
                  "3. Use `!test` to test full pipeline\n"
                  "4. Use `!speak` to test TTS output",
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
    
    bot = SimpleVoiceBot()
    
    try:
        logger.info("[START] Starting Simple Voice Test Bot...")
        logger.info("[INFO] This bot detects voice activity and tests the pipeline")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()