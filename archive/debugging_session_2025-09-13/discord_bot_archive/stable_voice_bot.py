#!/usr/bin/env python3
"""
Stable Voice Bot with Proper State Handling
Handles disconnections, reconnections, and voice state changes properly
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import time

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

class VoiceStateManager:
    """Manages voice connections and handles disconnections properly"""
    
    def __init__(self, bot):
        self.bot = bot
        self.connection_states = {}  # guild_id -> state info
        self.reconnect_tasks = {}
        
    async def handle_voice_state_update(self, member, before, after):
        """Handle all voice state updates"""
        guild_id = member.guild.id
        
        # Handle bot's own voice state changes
        if member == self.bot.user:
            await self._handle_bot_voice_state(guild_id, before, after)
        # Handle user voice state changes
        else:
            await self._handle_user_voice_state(member, before, after)
    
    async def _handle_bot_voice_state(self, guild_id, before, after):
        """Handle bot's voice state changes (disconnections, moves, etc)"""
        # Bot was disconnected from voice
        if before.channel and not after.channel:
            logger.warning(f"[VOICE] Bot was disconnected from {before.channel.name}")
            
            # Store the channel we were in
            self.connection_states[guild_id] = {
                'last_channel': before.channel,
                'disconnect_time': time.time(),
                'should_reconnect': True
            }
            
            # Cancel any existing reconnect task
            if guild_id in self.reconnect_tasks:
                self.reconnect_tasks[guild_id].cancel()
            
            # Start reconnection task
            self.reconnect_tasks[guild_id] = asyncio.create_task(
                self._attempt_reconnect(guild_id)
            )
        
        # Bot was moved to a different channel
        elif before.channel and after.channel and before.channel != after.channel:
            logger.info(f"[VOICE] Bot was moved from {before.channel.name} to {after.channel.name}")
            
            # Update our tracking
            if guild_id in self.bot.voice_handlers:
                self.bot.voice_handlers[guild_id].current_channel = after.channel
        
        # Bot connected to voice
        elif not before.channel and after.channel:
            logger.info(f"[VOICE] Bot connected to {after.channel.name}")
            
            # Clear reconnection state
            if guild_id in self.connection_states:
                self.connection_states[guild_id]['should_reconnect'] = False
    
    async def _handle_user_voice_state(self, member, before, after):
        """Handle user voice state changes"""
        guild_id = member.guild.id
        
        # Only process if we have an active voice handler
        if guild_id not in self.bot.voice_handlers:
            return
        
        handler = self.bot.voice_handlers[guild_id]
        
        # User joined our channel
        if after.channel and after.channel == handler.current_channel:
            if not before.channel or before.channel != after.channel:
                logger.info(f"[VOICE] {member.display_name} joined our channel")
                await handler.user_joined(member)
        
        # User left our channel
        elif before.channel and before.channel == handler.current_channel:
            if not after.channel or after.channel != before.channel:
                logger.info(f"[VOICE] {member.display_name} left our channel")
                await handler.user_left(member)
        
        # User mute/unmute in our channel
        if after.channel == handler.current_channel:
            # Check self mute changes
            if hasattr(before, 'self_mute') and hasattr(after, 'self_mute'):
                if before.self_mute != after.self_mute:
                    if after.self_mute:
                        logger.info(f"[VOICE] {member.display_name} muted")
                        await handler.user_muted(member)
                    else:
                        logger.info(f"[VOICE] {member.display_name} unmuted")
                        await handler.user_unmuted(member)
            
            # Check self deaf changes
            if hasattr(before, 'self_deaf') and hasattr(after, 'self_deaf'):
                if before.self_deaf != after.self_deaf:
                    if after.self_deaf:
                        logger.info(f"[VOICE] {member.display_name} deafened")
                    else:
                        logger.info(f"[VOICE] {member.display_name} undeafened")
    
    async def _attempt_reconnect(self, guild_id, max_attempts=5):
        """Attempt to reconnect to voice channel"""
        state = self.connection_states.get(guild_id, {})
        
        if not state.get('should_reconnect'):
            return
        
        last_channel = state.get('last_channel')
        if not last_channel:
            return
        
        for attempt in range(max_attempts):
            try:
                # Wait before attempting (exponential backoff)
                wait_time = min(2 ** attempt, 30)  # Max 30 seconds
                logger.info(f"[RECONNECT] Waiting {wait_time}s before attempt {attempt + 1}/{max_attempts}")
                await asyncio.sleep(wait_time)
                
                # Check if we should still reconnect
                if not self.connection_states.get(guild_id, {}).get('should_reconnect'):
                    logger.info("[RECONNECT] Reconnection cancelled")
                    return
                
                # Attempt to reconnect
                logger.info(f"[RECONNECT] Attempting to reconnect to {last_channel.name}")
                voice_client = await last_channel.connect(timeout=20.0)
                
                if voice_client and voice_client.is_connected():
                    logger.info(f"[RECONNECT] Successfully reconnected to {last_channel.name}")
                    
                    # Restore voice handler if needed
                    if guild_id in self.bot.voice_handlers:
                        self.bot.voice_handlers[guild_id].voice_client = voice_client
                        await self.bot.voice_handlers[guild_id].on_reconnect()
                    
                    # Clear reconnection state
                    self.connection_states[guild_id]['should_reconnect'] = False
                    return
                    
            except discord.ClientException as e:
                logger.error(f"[RECONNECT] Already connected: {e}")
                return
            except Exception as e:
                logger.error(f"[RECONNECT] Attempt {attempt + 1} failed: {e}")
        
        logger.error(f"[RECONNECT] Failed to reconnect after {max_attempts} attempts")
        
        # Notify in text channel if possible
        guild = self.bot.get_guild(guild_id)
        if guild:
            channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
            if channel:
                await channel.send("❌ Failed to reconnect to voice channel after multiple attempts.")

class VoiceHandler:
    """Handles voice operations with stability"""
    
    def __init__(self, bot, guild_id: int, voice_client, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_client = voice_client
        self.backend_client = backend_client
        self.current_channel = voice_client.channel
        self.active_users = set()
        self.is_active = True
        
    async def user_joined(self, member):
        """Handle user joining the voice channel"""
        self.active_users.add(member.id)
        # Send notification
        await self._send_voice_notification(f"👋 {member.display_name} joined the voice channel")
    
    async def user_left(self, member):
        """Handle user leaving the voice channel"""
        self.active_users.discard(member.id)
        # Send notification
        await self._send_voice_notification(f"👋 {member.display_name} left the voice channel")
        
        # Check if channel is empty (except for bot)
        if len(self.current_channel.members) <= 1:
            await self._send_voice_notification("🔇 Voice channel is empty. Disconnecting in 30 seconds...")
            await asyncio.sleep(30)
            
            # Check again before disconnecting
            if len(self.current_channel.members) <= 1 and self.voice_client.is_connected():
                await self.voice_client.disconnect()
                await self._send_voice_notification("🔇 Disconnected from empty voice channel")
    
    async def user_muted(self, member):
        """Handle user muting"""
        await self._send_voice_notification(f"🔇 {member.display_name} muted microphone")
    
    async def user_unmuted(self, member):
        """Handle user unmuting"""
        await self._send_voice_notification(f"🎤 {member.display_name} unmuted - ready to speak!")
        
        # Simulate voice processing since we can't actually capture
        await asyncio.sleep(2)
        await self._process_simulated_voice(member)
    
    async def on_reconnect(self):
        """Handle reconnection to voice"""
        await self._send_voice_notification("✅ Reconnected to voice channel!")
        self.is_active = True
    
    async def _process_simulated_voice(self, member):
        """Process simulated voice (since discord.py can't capture)"""
        try:
            await self._send_voice_notification(f"🎤 Processing voice from {member.display_name}...")
            
            # Simulate transcription
            simulated_text = f"Hello from {member.display_name}"
            
            # Get AI response
            response = await self.backend_client.send_message(
                user_id=member.display_name,
                message=simulated_text,
                context={"source": "voice", "guild_id": str(self.guild_id)}
            )
            
            if response:
                # Generate TTS
                audio_data = await self.backend_client.text_to_speech(response)
                
                if audio_data and self.voice_client.is_connected():
                    await self._play_audio(audio_data)
                
                # Send text response
                embed = discord.Embed(
                    title="🤖 Voice Conversation",
                    color=0x00ff00
                )
                embed.add_field(name="You said:", value=simulated_text, inline=False)
                embed.add_field(name="AI replied:", value=response, inline=False)
                
                await self._send_embed(embed)
                
        except Exception as e:
            logger.error(f"[ERROR] Voice processing error: {e}")
    
    async def _play_audio(self, audio_data: bytes):
        """Play audio response"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                if self.voice_client and self.voice_client.is_connected():
                    audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                    self.voice_client.play(audio_source)
                    
                    while self.voice_client.is_playing():
                        await asyncio.sleep(0.1)
                    
                    logger.info("[OK] Audio playback complete")
                    
            finally:
                await asyncio.sleep(0.5)
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio playback error: {e}")
    
    async def _send_voice_notification(self, message: str):
        """Send a notification to the text channel"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(message)
        except Exception as e:
            logger.error(f"[ERROR] Failed to send notification: {e}")
    
    async def _send_embed(self, embed):
        """Send an embed to the text channel"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"[ERROR] Failed to send embed: {e}")

class StableVoiceBot(discord.Client):
    """Discord bot with stable voice connection handling"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers: Dict[int, VoiceHandler] = {}
        self.backend_client = None
        self.state_manager = VoiceStateManager(self)
    
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
                logger.warning("[WARN] Backend API not available")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
            self.backend_client = None
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        logger.info(f"[STATUS] Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_voice_state_update(self, member, before, after):
        """Handle all voice state updates"""
        await self.state_manager.handle_voice_state_update(member, before, after)
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!join':
            await self._join_voice(message)
        elif content == '!leave':
            await self._leave_voice(message)
        elif content.startswith('!test '):
            await self._test_pipeline(message, content[6:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _join_voice(self, message):
        """Join voice channel with stable connection"""
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
        
        if not self.backend_client:
            await message.reply("Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                await asyncio.sleep(1)
            
            # Connect to voice
            voice_client = await channel.connect(timeout=20.0)
            
            if voice_client and voice_client.is_connected():
                # Create voice handler
                handler = VoiceHandler(self, guild_id, voice_client, self.backend_client)
                self.voice_handlers[guild_id] = handler
                
                # Clear any reconnection state
                self.state_manager.connection_states[guild_id] = {
                    'should_reconnect': False,
                    'last_channel': channel
                }
                
                embed = discord.Embed(
                    title="🎙️ Voice Connection Stable!",
                    description=f"Connected to **{channel.name}** with auto-reconnect enabled!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Features",
                    value="• Auto-reconnect on disconnect\n• Empty channel detection\n• Voice state tracking\n• Stable connection handling",
                    inline=False
                )
                embed.add_field(
                    name="Voice Events",
                    value="• Join/leave notifications\n• Mute/unmute detection\n• Automatic cleanup",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[OK] Stable voice connection established in {channel.name}")
            else:
                await message.reply("❌ Failed to connect to voice")
                
        except Exception as e:
            await message.reply(f"❌ Connection error: {str(e)}")
            logger.error(f"[ERROR] Voice connection error: {e}")
    
    async def _leave_voice(self, message):
        """Leave voice channel properly"""
        guild_id = message.guild.id
        
        try:
            # Disable auto-reconnect
            if guild_id in self.state_manager.connection_states:
                self.state_manager.connection_states[guild_id]['should_reconnect'] = False
            
            # Remove handler
            if guild_id in self.voice_handlers:
                self.voice_handlers[guild_id].is_active = False
                del self.voice_handlers[guild_id]
            
            # Disconnect
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                await message.reply("🔇 Left voice channel!")
            else:
                await message.reply("Not in voice!")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _test_pipeline(self, message, text: str):
        """Test the AI pipeline"""
        if not text.strip():
            await message.reply("Provide text to test!")
            return
        
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        try:
            await message.reply(f"🧪 Testing pipeline with: *{text}*")
            
            # Get AI response
            response = await self.backend_client.send_message(
                user_id=message.author.display_name,
                message=text,
                context={"source": "test", "guild_id": str(message.guild.id)}
            )
            
            if response:
                # Test TTS if in voice
                if message.guild.voice_client:
                    audio_data = await self.backend_client.text_to_speech(response)
                    if audio_data:
                        handler = self.voice_handlers.get(message.guild.id)
                        if handler:
                            await handler._play_audio(audio_data)
                
                embed = discord.Embed(
                    title="🧪 Pipeline Test",
                    color=0x0099ff
                )
                embed.add_field(name="Input:", value=text, inline=False)
                embed.add_field(name="Response:", value=response[:1000], inline=False)
                await message.reply(embed=embed)
            else:
                await message.reply("❌ No response from backend")
                
        except Exception as e:
            await message.reply(f"❌ Test error: {str(e)}")
    
    async def _show_status(self, message):
        """Show bot status"""
        embed = discord.Embed(title="🎙️ Stable Voice Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Components",
            value=f"Discord.py: 2.6.3\nOpus: {opus_status}\nBackend: {backend_status}",
            inline=True
        )
        
        embed.add_field(
            name="Voice Status",
            value=f"Active: {len(self.voice_handlers)} channels\nAuto-reconnect: Enabled",
            inline=True
        )
        
        # Show active connections
        if self.voice_handlers:
            connections = []
            for guild_id, handler in self.voice_handlers.items():
                guild = self.get_guild(guild_id)
                if guild and handler.current_channel:
                    connections.append(f"• {guild.name}: {handler.current_channel.name} ({len(handler.active_users)} users)")
            
            if connections:
                embed.add_field(
                    name="Active Connections",
                    value="\n".join(connections),
                    inline=False
                )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🎙️ Stable Voice Bot",
            description="Voice bot with proper state handling and auto-reconnect",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Commands",
            value="`!join` - Join voice with auto-reconnect\n`!leave` - Leave voice channel\n`!test <text>` - Test AI pipeline\n`!status` - Show bot status\n`!help` - This help",
            inline=False
        )
        
        embed.add_field(
            name="Voice Features",
            value="• **Auto-reconnect** on disconnect\n• **Empty channel** detection\n• **Voice state** tracking\n• **Join/leave** notifications\n• **Mute detection** triggers processing",
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value="1. Bot joins and monitors voice states\n2. Detects mute/unmute events\n3. Simulates voice input (discord.py limitation)\n4. Processes through AI pipeline\n5. Plays TTS response",
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
    
    bot = StableVoiceBot()
    
    try:
        logger.info("[START] Starting Stable Voice Bot...")
        logger.info("[INFO] Features: Auto-reconnect, state tracking, empty channel detection")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()