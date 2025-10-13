#!/usr/bin/env python3
"""
Hybrid Discord Bot - Supports both local microphone and remote Discord calling
"""

import asyncio
import discord
import logging
import time
from pathlib import Path
import sys

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from config import Config
from robust_websocket_client import RobustWebSocketClient
from hybrid_audio_manager import HybridAudioManager, AudioConfig, AudioMode
from discord_voice_tracker import DiscordVoiceTracker

try:
    from load_config import config as services_config
except ImportError:
    services_config = {}

# Setup logging
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "hybrid_discord_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress discord warnings
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class HybridDiscordBot:
    """Discord bot with hybrid local/remote audio support"""
    
    def __init__(self, websocket_url=None):
        # Use centralized config or fallback
        if websocket_url is None:
            websocket_url = services_config.get('websocket_url', 'ws://127.0.0.1:8002')
        
        self.websocket_url = websocket_url
        self.websocket_client = RobustWebSocketClient(websocket_url, self._handle_websocket_message)
        
        # Audio configuration
        audio_config = AudioConfig(
            sample_rate=16000,
            channels=1,
            chunk_size=1024
        )
        
        # Initialize hybrid audio manager
        self.audio_manager = HybridAudioManager(audio_config)
        self.audio_manager.set_audio_callback(self._send_audio_async)
        
        # Discord bot setup
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        self.bot = discord.Bot(intents=intents)
        
        # Voice tracking
        self.voice_tracker = DiscordVoiceTracker(self.bot)
        self.voice_tracker.set_state_change_callback(self._on_voice_state_change)
        
        # State
        self.active_voice_client = None
        self.is_active = False
        self.chunks_sent = 0
        
        # Setup bot commands
        self._setup_commands()
        
        logger.info("🤖 Hybrid Discord Bot initialized")
        logger.info(f"🔌 WebSocket URL: {self.websocket_url}")
    
    def _setup_commands(self):
        """Setup Discord bot commands"""
        
        @self.bot.slash_command(name="hybrid", description="Start hybrid audio conversation")
        async def hybrid_command(ctx: discord.ApplicationContext):
            await self._start_hybrid_session(ctx)
        
        @self.bot.slash_command(name="stop", description="Stop audio conversation")
        async def stop_command(ctx: discord.ApplicationContext):
            await self._stop_session(ctx)
        
        @self.bot.slash_command(name="mode", description="Check or set audio mode")
        async def mode_command(ctx: discord.ApplicationContext, mode: str = None):
            await self._mode_command(ctx, mode)
        
        @self.bot.slash_command(name="status", description="Check bot status")
        async def status_command(ctx: discord.ApplicationContext):
            await self._status_command(ctx)
    
    async def _start_hybrid_session(self, ctx: discord.ApplicationContext):
        """Start hybrid audio session"""
        if self.is_active:
            await ctx.respond("⚠️ Session already active! Use `/stop` first.")
            return
        
        # Check if user is in a voice channel
        if not ctx.author.voice:
            await ctx.respond("❌ You must be in a voice channel to start a session!")
            return
        
        voice_channel = ctx.author.voice.channel
        
        try:
            await ctx.respond("🔄 Starting hybrid audio session...")
            
            # Connect to voice channel
            voice_client = await voice_channel.connect()
            self.active_voice_client = voice_client
            
            # Start voice tracking
            await self.voice_tracker.join_voice_channel(voice_channel)
            
            # Wait for services if needed
            if services_config:
                initial_delay = services_config.get('connection', {}).get('initial_delay', 3)
                logger.info(f"⏳ Waiting {initial_delay}s for services to initialize...")
                await asyncio.sleep(initial_delay)
            
            # Connect to backend
            if not await self.websocket_client.connect():
                await ctx.edit(content="❌ Failed to connect to backend")
                return
            
            # Start hybrid audio capture
            if not await self.audio_manager.start_capture():
                await ctx.edit(content="❌ Failed to start audio capture")
                return
            
            self.is_active = True
            
            # Determine current mode
            mode_info = self._get_current_mode_info()
            
            await ctx.edit(content=f"""✅ **Hybrid Audio Session Active**
            
🎤 **Audio Mode**: {mode_info['mode']} 
📊 **Channel**: {mode_info['channel_info']}
🔊 **Source**: {mode_info['source']}

Speak naturally - I'll respond with voice!
Use `/stop` to end the session.""")
            
        except Exception as e:
            logger.error(f"❌ Error starting session: {e}")
            await ctx.edit(content=f"❌ Error starting session: {e}")
            await self._cleanup_session()
    
    async def _stop_session(self, ctx: discord.ApplicationContext):
        """Stop audio session"""
        if not self.is_active:
            await ctx.respond("⚠️ No active session to stop.")
            return
        
        await ctx.respond("🛑 Stopping audio session...")
        await self._cleanup_session()
        await ctx.edit(content="✅ Audio session stopped.")
    
    async def _mode_command(self, ctx: discord.ApplicationContext, mode: str = None):
        """Check or set audio mode"""
        if mode is None:
            # Show current mode
            mode_info = self._get_current_mode_info()
            await ctx.respond(f"""📊 **Current Audio Mode**
            
🎤 **Mode**: {mode_info['mode']}
🔊 **Source**: {mode_info['source']}
📈 **Channel Info**: {mode_info['channel_info']}
            
Available modes: `local`, `remote`, `auto`""")
        else:
            # Set mode
            try:
                if mode.lower() == 'local':
                    self.audio_manager.current_mode = AudioMode.LOCAL
                elif mode.lower() == 'remote':
                    self.audio_manager.current_mode = AudioMode.REMOTE
                elif mode.lower() == 'auto':
                    self.audio_manager.current_mode = AudioMode.AUTO
                else:
                    await ctx.respond("❌ Invalid mode. Use: `local`, `remote`, or `auto`")
                    return
                
                # Restart capture if active
                if self.is_active:
                    await self.audio_manager.start_capture()
                
                mode_info = self._get_current_mode_info()
                await ctx.respond(f"✅ Audio mode set to: {mode_info['mode']}")
                
            except Exception as e:
                await ctx.respond(f"❌ Error setting mode: {e}")
    
    async def _status_command(self, ctx: discord.ApplicationContext):
        """Show bot status"""
        mode_info = self._get_current_mode_info()
        
        status = f"""📊 **Hybrid Discord Bot Status**
        
🤖 **Session**: {'🟢 Active' if self.is_active else '🔴 Inactive'}
🎤 **Audio Mode**: {mode_info['mode']}
🔊 **Audio Source**: {mode_info['source']}
📈 **Chunks Sent**: {self.chunks_sent}
🔌 **WebSocket**: {'🟢 Connected' if self.websocket_client.is_connected() else '🔴 Disconnected'}

**Channel Info**: {mode_info['channel_info']}"""
        
        await ctx.respond(status)
    
    def _get_current_mode_info(self) -> dict:
        """Get current mode information"""
        actual_mode = self.audio_manager._get_actual_mode()
        channel_info = self.voice_tracker.get_channel_info()
        
        if actual_mode == AudioMode.LOCAL:
            source = "Local Microphone"
        elif actual_mode == AudioMode.REMOTE:
            source = "Discord Audio (System)"
        else:
            source = "Unknown"
        
        return {
            'mode': f"{self.audio_manager.current_mode.value.title()} ➜ {actual_mode.value.title()}",
            'source': source,
            'channel_info': f"{channel_info['total_users']} users ({channel_info['remote_users']} remote)"
        }
    
    async def _on_voice_state_change(self, users_in_channel: set, local_user_id: str):
        """Handle voice channel state changes"""
        # Update audio manager with Discord state
        self.audio_manager.update_discord_state(users_in_channel, local_user_id)
        
        # Log the change
        remote_users = len(users_in_channel) - (1 if local_user_id in users_in_channel else 0)
        logger.info(f"👥 Voice channel update: {len(users_in_channel)} total, {remote_users} remote users")
    
    async def _handle_websocket_message(self, message):
        """Handle WebSocket messages from backend"""
        try:
            if message.get("type") == "tts_start":
                await self._handle_tts_start(message)
            elif message.get("type") == "audio_response":
                await self._play_audio_response(message)
            elif message.get("type") == "interrupt_acknowledged":
                logger.info("⚡ TTS interrupt acknowledged")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
    
    async def _handle_tts_start(self, data):
        """Handle TTS start notification"""
        try:
            audio_b64 = data.get("data", "")
            if audio_b64:
                import base64
                audio_bytes = base64.b64decode(audio_b64)
                
                # Notify echo prevention system
                self.audio_manager.set_tts_output(audio_bytes)
                
                logger.info(f"🎵 TTS starting - {len(audio_bytes)} bytes")
        except Exception as e:
            logger.error(f"❌ Error in TTS start handler: {e}")
    
    async def _play_audio_response(self, data):
        """Play audio response through Discord"""
        try:
            if not self.active_voice_client or not self.active_voice_client.is_connected():
                logger.warning("⚠️ No active voice connection for audio playback")
                return
            
            import base64
            import tempfile
            import wave
            import os
            
            audio_b64 = data.get("data", "")
            if not audio_b64:
                return
            
            audio_bytes = base64.b64decode(audio_b64)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(22050)
                    wav_file.writeframes(audio_bytes)
                temp_path = temp_file.name
            
            # Play through Discord
            if self.active_voice_client.is_playing():
                self.active_voice_client.stop()
            
            audio_source = discord.FFmpegPCMAudio(temp_path)
            self.active_voice_client.play(audio_source)
            
            # Clean up after delay
            async def cleanup():
                await asyncio.sleep(30)
                try:
                    os.unlink(temp_path)
                except:
                    pass
            
            asyncio.create_task(cleanup())
            logger.info("🔊 Playing audio response")
            
        except Exception as e:
            logger.error(f"❌ Failed to play audio: {e}")
    
    def _send_audio_async(self, audio_data: bytes):
        """Send audio data to backend asynchronously"""
        if self.websocket_client.is_connected():
            try:
                import base64
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                message = {
                    "type": "audio_chunk",
                    "data": audio_b64,
                    "timestamp": time.time(),
                    "format": "pcm_s16le",
                    "sample_rate": 16000,
                    "channels": 1
                }
                
                # Send via WebSocket
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(
                    self.websocket_client.send(message), 
                    loop
                )
                
                self.chunks_sent += 1
                
            except Exception as e:
                logger.error(f"❌ Error sending audio: {e}")
    
    async def _cleanup_session(self):
        """Clean up active session"""
        self.is_active = False
        
        # Stop audio capture
        await self.audio_manager.stop_capture()
        
        # Disconnect from voice
        if self.active_voice_client:
            await self.active_voice_client.disconnect()
            self.active_voice_client = None
        
        # Stop voice tracking
        await self.voice_tracker.leave_voice_channel()
        
        # Disconnect WebSocket
        await self.websocket_client.disconnect()
        
        logger.info("🧹 Session cleanup completed")
    
    def run(self, token: str):
        """Run the Discord bot"""
        logger.info("🚀 Starting Hybrid Discord Bot...")
        self.bot.run(token)

# Entry point
if __name__ == "__main__":
    config = Config()
    bot = HybridDiscordBot()
    bot.run(config.discord_token)