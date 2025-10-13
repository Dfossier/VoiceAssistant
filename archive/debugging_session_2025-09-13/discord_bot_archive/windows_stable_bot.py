#!/usr/bin/env python3
"""
Windows Stable Voice Bot with Enhanced Error 4006 Handling
Designed specifically for running on native Windows with proper connection state management
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

# Suppress Discord logs except errors
for logger_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Force load Opus
logger.info("[SETUP] Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "[OK] Loaded" if discord.opus.is_loaded() else "[ERROR] Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"[ERROR] Opus error: {e}")

class Enhanced4006Handler:
    """Handles Error 4006 with intelligent connection management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.connection_attempts = {}  # guild_id -> attempt info
        self.cooldown_periods = {}     # guild_id -> cooldown end time
        self.failed_connections = {}   # guild_id -> failure count
        
    def should_attempt_connection(self, guild_id: int) -> bool:
        """Check if we should attempt connection (not in cooldown)"""
        current_time = time.time()
        cooldown_end = self.cooldown_periods.get(guild_id, 0)
        
        if current_time < cooldown_end:
            remaining = int(cooldown_end - current_time)
            logger.info(f"[COOLDOWN] Connection on cooldown for {remaining}s")
            return False
        
        return True
    
    def record_connection_failure(self, guild_id: int):
        """Record a connection failure and set appropriate cooldown"""
        self.failed_connections[guild_id] = self.failed_connections.get(guild_id, 0) + 1
        failure_count = self.failed_connections[guild_id]
        
        # Progressive cooldown: 10s, 30s, 60s, 120s, 300s (max 5 minutes)
        cooldown_duration = min(10 * (2 ** (failure_count - 1)), 300)
        self.cooldown_periods[guild_id] = time.time() + cooldown_duration
        
        logger.warning(f"[4006] Connection failure #{failure_count}, cooldown: {cooldown_duration}s")
    
    def record_connection_success(self, guild_id: int):
        """Record successful connection and reset failure count"""
        self.failed_connections[guild_id] = 0
        self.cooldown_periods[guild_id] = 0
        logger.info("[SUCCESS] Connection successful, failure count reset")
    
    async def safe_connect(self, channel, guild_id: int, max_retries: int = 3):
        """Safely attempt voice connection with 4006 handling"""
        if not self.should_attempt_connection(guild_id):
            return None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"[CONNECT] Attempt {attempt + 1}/{max_retries} to {channel.name}")
                
                # Clean up any existing connection first
                if channel.guild.voice_client:
                    try:
                        await channel.guild.voice_client.disconnect(force=True)
                        await asyncio.sleep(2)  # Give Discord time to clean up
                    except:
                        pass
                
                # Attempt connection with timeout
                voice_client = await channel.connect(
                    timeout=15.0,
                    reconnect=False,  # Disable automatic reconnects
                    self_deaf=False,
                    self_mute=False
                )
                
                if voice_client and voice_client.is_connected():
                    self.record_connection_success(guild_id)
                    logger.info(f"[SUCCESS] Connected to {channel.name}")
                    return voice_client
                else:
                    logger.warning(f"[WARN] Connection returned None or not connected")
                    
            except discord.errors.ConnectionClosed as e:
                if e.code == 4006:
                    logger.error(f"[4006] Session no longer valid - attempt {attempt + 1}")
                    self.record_connection_failure(guild_id)
                    
                    if attempt < max_retries - 1:
                        wait_time = 5 + (attempt * 5)  # 5s, 10s, 15s
                        logger.info(f"[RETRY] Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error("[4006] Max retries reached, entering cooldown")
                        return None
                else:
                    logger.error(f"[ERROR] Connection closed with code {e.code}: {e}")
                    return None
                    
            except discord.ClientException as e:
                if "already connected" in str(e).lower():
                    logger.warning("[WARN] Already connected, attempting cleanup...")
                    try:
                        if channel.guild.voice_client:
                            await channel.guild.voice_client.disconnect(force=True)
                            await asyncio.sleep(3)
                    except:
                        pass
                else:
                    logger.error(f"[ERROR] Client exception: {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"[ERROR] Unexpected connection error: {e}")
                return None
        
        logger.error(f"[FAILED] All connection attempts failed for {channel.name}")
        return None

class RobustVoiceHandler:
    """Voice handler with robust connection management"""
    
    def __init__(self, bot, guild_id: int, voice_client, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_client = voice_client
        self.backend_client = backend_client
        self.current_channel = voice_client.channel if voice_client else None
        self.is_active = True
        self.last_activity = time.time()
        
        # Start health monitoring
        self.health_task = asyncio.create_task(self._monitor_connection_health())
    
    async def _monitor_connection_health(self):
        """Monitor connection health and handle disconnections"""
        try:
            while self.is_active:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                if not self.voice_client or not self.voice_client.is_connected():
                    logger.warning("[HEALTH] Voice connection lost, attempting recovery...")
                    await self._attempt_recovery()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Health monitor error: {e}")
    
    async def _attempt_recovery(self):
        """Attempt to recover from connection loss"""
        if not self.current_channel:
            logger.error("[RECOVERY] No channel to recover to")
            return
        
        try:
            handler = self.bot.error_handler
            new_client = await handler.safe_connect(self.current_channel, self.guild_id)
            
            if new_client:
                self.voice_client = new_client
                logger.info("[RECOVERY] Connection recovered successfully")
                
                # Notify in text channel
                await self._send_notification("✅ Voice connection recovered!")
            else:
                logger.error("[RECOVERY] Failed to recover connection")
                await self._send_notification("❌ Voice connection lost and could not be recovered")
                
        except Exception as e:
            logger.error(f"[ERROR] Recovery attempt failed: {e}")
    
    async def process_simulated_voice(self, user):
        """Process simulated voice input"""
        try:
            logger.info(f"[VOICE] Simulating voice processing for {user.display_name}")
            
            # Update last activity
            self.last_activity = time.time()
            
            # Simulate transcription
            simulated_text = f"Hello from {user.display_name}, testing voice processing"
            
            # Send notification
            await self._send_notification(f"🎤 Processing voice from **{user.display_name}**...")
            
            # Get AI response
            response = await self.backend_client.send_message(
                user_id=user.display_name,
                message=simulated_text,
                context={"source": "voice", "guild_id": str(self.guild_id)}
            )
            
            if response:
                # Generate TTS
                audio_data = await self.backend_client.text_to_speech(response)
                
                if audio_data:
                    success = await self._play_audio_safely(audio_data)
                    
                    # Send conversation summary
                    embed = discord.Embed(
                        title="🤖 Voice Conversation",
                        color=0x00ff00
                    )
                    embed.add_field(name="You said:", value=simulated_text, inline=False)
                    embed.add_field(name="AI replied:", value=response[:1000], inline=False)
                    embed.add_field(name="Status:", value=f"Audio playback: {'✅ Success' if success else '❌ Failed'}", inline=False)
                    
                    await self._send_embed(embed)
                    
        except Exception as e:
            logger.error(f"[ERROR] Voice processing error: {e}")
            await self._send_notification(f"❌ Voice processing error: {str(e)}")
    
    async def _play_audio_safely(self, audio_data: bytes) -> bool:
        """Play audio with connection safety checks"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                logger.warning("[AUDIO] No voice connection for playback")
                return False
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                
                if self.voice_client.is_connected():
                    self.voice_client.play(audio_source)
                    
                    # Wait for playback with connection checks
                    while self.voice_client.is_playing() and self.voice_client.is_connected():
                        await asyncio.sleep(0.1)
                    
                    logger.info("[OK] Audio playback complete")
                    return True
                else:
                    logger.warning("[AUDIO] Connection lost during setup")
                    return False
                    
            finally:
                await asyncio.sleep(0.5)
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio playback error: {e}")
            return False
    
    async def _send_notification(self, message: str):
        """Send notification to text channel"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(message)
        except Exception as e:
            logger.error(f"[ERROR] Failed to send notification: {e}")
    
    async def _send_embed(self, embed):
        """Send embed to text channel"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"[ERROR] Failed to send embed: {e}")
    
    async def cleanup(self):
        """Clean up handler resources"""
        self.is_active = False
        if hasattr(self, 'health_task'):
            self.health_task.cancel()
            try:
                await self.health_task
            except asyncio.CancelledError:
                pass

class WindowsStableBot(discord.Client):
    """Stable Discord bot optimized for Windows with 4006 handling"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers: Dict[int, RobustVoiceHandler] = {}
        self.backend_client = None
        self.error_handler = Enhanced4006Handler(self)
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        logger.info(f"[PLATFORM] Running on Windows with enhanced 4006 handling")
        
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
        logger.info(f"[STATUS] Opus: {opus_status} | Backend: {backend_status} | 4006 Handler: [OK]")
    
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates with enhanced detection"""
        # Skip bot's own state changes (handled elsewhere)
        if member == self.user:
            return
        
        guild_id = member.guild.id
        if guild_id not in self.voice_handlers:
            return
        
        handler = self.voice_handlers[guild_id]
        
        # Enhanced mute/unmute detection
        if hasattr(before, 'self_mute') and hasattr(after, 'self_mute'):
            if before.self_mute != after.self_mute:
                if not after.self_mute:  # User unmuted
                    logger.info(f"[VOICE] {member.display_name} unmuted - processing voice")
                    await handler.process_simulated_voice(member)
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!join':
            await self._join_voice_safely(message)
        elif content == '!leave':
            await self._leave_voice_safely(message)
        elif content.startswith('!test '):
            await self._test_pipeline(message, content[6:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _join_voice_safely(self, message):
        """Join voice with enhanced 4006 handling"""
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
        
        if not self.backend_client:
            await message.reply("❌ Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        # Check cooldown
        if not self.error_handler.should_attempt_connection(guild_id):
            cooldown_end = self.error_handler.cooldown_periods.get(guild_id, 0)
            remaining = int(cooldown_end - time.time())
            await message.reply(f"⏳ Connection on cooldown for {remaining} seconds due to Error 4006")
            return
        
        try:
            await message.reply("🔄 Attempting to join voice channel...")
            
            # Use safe connection method
            voice_client = await self.error_handler.safe_connect(channel, guild_id)
            
            if voice_client:
                # Create robust handler
                handler = RobustVoiceHandler(self, guild_id, voice_client, self.backend_client)
                self.voice_handlers[guild_id] = handler
                
                embed = discord.Embed(
                    title="✅ Voice Connection Established!",
                    description=f"Connected to **{channel.name}** with enhanced stability!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Enhanced Features",
                    value="• Error 4006 handling with progressive cooldown\n• Connection health monitoring\n• Automatic recovery attempts\n• Robust state management",
                    inline=False
                )
                embed.add_field(
                    name="Voice Processing",
                    value="• **Mute/unmute** detection\n• Voice activity simulation\n• Backend AI integration\n• Automatic cleanup",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[SUCCESS] Robust connection established in {channel.name}")
            else:
                await message.reply("❌ Failed to connect to voice channel. Please try again later.")
                
        except Exception as e:
            await message.reply(f"❌ Connection error: {str(e)}")
            logger.error(f"[ERROR] Voice join error: {e}")
    
    async def _leave_voice_safely(self, message):
        """Leave voice with proper cleanup"""
        guild_id = message.guild.id
        
        try:
            # Clean up handler
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].cleanup()
                del self.voice_handlers[guild_id]
            
            # Disconnect voice client
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await message.reply("👋 Left voice channel!")
            else:
                await message.reply("❌ Not in voice!")
            
            # Reset error handler state for this guild
            self.error_handler.failed_connections[guild_id] = 0
            self.error_handler.cooldown_periods[guild_id] = 0
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _test_pipeline(self, message, text: str):
        """Test AI pipeline"""
        if not text.strip():
            await message.reply("❌ Provide text to test!")
            return
        
        if not self.backend_client:
            await message.reply("❌ Backend not connected!")
            return
        
        try:
            await message.reply(f"🧪 Testing pipeline with: *{text}*")
            
            response = await self.backend_client.send_message(
                user_id=message.author.display_name,
                message=text,
                context={"source": "test", "guild_id": str(message.guild.id)}
            )
            
            if response:
                # Test TTS if in voice
                audio_success = False
                if message.guild.voice_client:
                    handler = self.voice_handlers.get(message.guild.id)
                    if handler:
                        audio_data = await self.backend_client.text_to_speech(response)
                        if audio_data:
                            audio_success = await handler._play_audio_safely(audio_data)
                
                embed = discord.Embed(
                    title="🧪 Pipeline Test Results",
                    color=0x0099ff
                )
                embed.add_field(name="Input:", value=text, inline=False)
                embed.add_field(name="Response:", value=response[:1000], inline=False)
                embed.add_field(name="TTS Status:", value=f"{'✅ Success' if audio_success else '❌ Failed or not in voice'}", inline=False)
                
                await message.reply(embed=embed)
            else:
                await message.reply("❌ No response from backend")
                
        except Exception as e:
            await message.reply(f"❌ Test error: {str(e)}")
    
    async def _show_status(self, message):
        """Show enhanced bot status"""
        embed = discord.Embed(title="🏠 Windows Stable Voice Bot Status", color=0x0099ff)
        
        opus_status = "✅ OK" if discord.opus.is_loaded() else "❌ ERROR"
        backend_status = "✅ OK" if self.backend_client else "❌ ERROR"
        
        embed.add_field(
            name="Core Components",
            value=f"Platform: Windows Optimized\nOpus: {opus_status}\nBackend: {backend_status}",
            inline=True
        )
        
        embed.add_field(
            name="Error 4006 Handler",
            value=f"Active: ✅\nConnections: {len(self.voice_handlers)}\nFailed guilds: {len([g for g, c in self.error_handler.failed_connections.items() if c > 0])}",
            inline=True
        )
        
        # Show connection states
        if self.voice_handlers:
            connection_info = []
            for guild_id, handler in self.voice_handlers.items():
                guild = self.get_guild(guild_id)
                if guild and handler.current_channel:
                    status = "✅ Connected" if handler.voice_client.is_connected() else "❌ Disconnected"
                    connection_info.append(f"• {guild.name}: {handler.current_channel.name} ({status})")
            
            if connection_info:
                embed.add_field(
                    name="Active Connections",
                    value="\n".join(connection_info),
                    inline=False
                )
        
        # Show failure counts
        failed_guilds = [(gid, count) for gid, count in self.error_handler.failed_connections.items() if count > 0]
        if failed_guilds:
            failure_info = []
            for guild_id, count in failed_guilds:
                guild = self.get_guild(guild_id)
                guild_name = guild.name if guild else f"Guild {guild_id}"
                cooldown_end = self.error_handler.cooldown_periods.get(guild_id, 0)
                remaining = max(0, int(cooldown_end - time.time()))
                failure_info.append(f"• {guild_name}: {count} failures, cooldown: {remaining}s")
            
            embed.add_field(
                name="Connection Issues",
                value="\n".join(failure_info),
                inline=False
            )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help with Windows-specific info"""
        embed = discord.Embed(
            title="🏠 Windows Stable Voice Bot",
            description="Enhanced voice bot with Error 4006 handling for Windows",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Commands",
            value="`!join` - Join voice with 4006 protection\n`!leave` - Leave voice safely\n`!test <text>` - Test AI pipeline\n`!status` - Show detailed status\n`!help` - This help",
            inline=False
        )
        
        embed.add_field(
            name="Error 4006 Handling",
            value="• Progressive cooldown on failures\n• Connection health monitoring\n• Automatic recovery attempts\n• Safe reconnection logic",
            inline=False
        )
        
        embed.add_field(
            name="Windows Optimizations",
            value="• Native Windows compatibility\n• Enhanced connection stability\n• Robust state management\n• Graceful error recovery",
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
    
    bot = WindowsStableBot()
    
    try:
        logger.info("[START] Starting Windows Stable Voice Bot...")
        logger.info("[INFO] Enhanced Error 4006 handling enabled")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()