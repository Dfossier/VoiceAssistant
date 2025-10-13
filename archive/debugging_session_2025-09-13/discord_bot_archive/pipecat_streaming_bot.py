#!/usr/bin/env python3
"""
Discord Bot with Pipecat Streaming Integration
Real-time voice conversation using:
- Continuous audio streaming (not start/stop)
- Voice Activity Detection (VAD) 
- Local models: Parakeet + Phi-3 + Kokoro
- WebSocket communication with Pipecat backend
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import websockets
import json
import base64
import threading
from pathlib import Path
from typing import Optional
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

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

class PipecatAudioStreamer:
    """Streams audio between Discord and Pipecat pipeline"""
    
    def __init__(self, pipecat_ws_url: str = "ws://127.0.0.1:8001"):
        self.pipecat_ws_url = pipecat_ws_url
        self.websocket = None
        self.is_streaming = False
        self.audio_queue = asyncio.Queue()
        
    async def connect_to_pipecat(self):
        """Connect to Pipecat WebSocket pipeline"""
        try:
            logger.info(f"🔌 Connecting to Pipecat pipeline: {self.pipecat_ws_url}")
            self.websocket = await websockets.connect(self.pipecat_ws_url)
            self.is_streaming = True
            logger.info("✅ Connected to Pipecat pipeline")
            
            # Start listening for responses from Pipecat
            asyncio.create_task(self._listen_for_responses())
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Pipecat: {e}")
            return False
            
    async def disconnect_from_pipecat(self):
        """Disconnect from Pipecat pipeline"""
        self.is_streaming = False
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 Disconnected from Pipecat pipeline")
            
    async def stream_audio_to_pipecat(self, audio_data: bytes):
        """Stream audio data to Pipecat pipeline"""
        if not self.websocket or not self.is_streaming:
            return
            
        try:
            # Convert audio to base64 for WebSocket transmission
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "audio_input",
                "data": audio_b64,
                "format": "wav",
                "sample_rate": 16000,
                "channels": 1
            }
            
            await self.websocket.send(json.dumps(message))
            
        except Exception as e:
            logger.error(f"❌ Error streaming audio to Pipecat: {e}")
            
    async def _listen_for_responses(self):
        """Listen for audio responses from Pipecat"""
        try:
            while self.is_streaming and self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if data.get("type") == "audio_output":
                    # Received audio response from Pipecat
                    audio_data = base64.b64decode(data.get("data", ""))
                    
                    if audio_data:
                        logger.info(f"🔊 Received {len(audio_data)} bytes of response audio")
                        # Queue audio for playback in Discord
                        await self.audio_queue.put(audio_data)
                        
                elif data.get("type") == "text_output":
                    # Received text response (for debugging)
                    text = data.get("text", "")
                    logger.info(f"💬 Pipecat response: {text[:100]}...")
                    
        except Exception as e:
            logger.error(f"❌ Error listening to Pipecat responses: {e}")

class ContinuousVoiceCapture:
    """Captures audio continuously from Discord voice channel"""
    
    def __init__(self, bot, voice_client, streamer: PipecatAudioStreamer):
        self.bot = bot
        self.voice_client = voice_client
        self.streamer = streamer
        self.is_capturing = False
        self.capture_task = None
        
    async def start_continuous_capture(self):
        """Start continuous audio capture"""
        if self.is_capturing:
            logger.warning("⚠️  Already capturing audio")
            return
            
        logger.info("🎤 Starting continuous audio capture with VAD...")
        self.is_capturing = True
        
        # Use Discord's audio sink for continuous capture
        sink = discord.sinks.WaveSink()
        
        # Start recording without end condition (continuous)
        self.voice_client.start_recording(
            sink,
            self._audio_callback,
            None  # No context needed for continuous capture
        )
        
        # Start audio streaming task
        self.capture_task = asyncio.create_task(self._stream_audio_continuously(sink))
        
    async def stop_continuous_capture(self):
        """Stop continuous audio capture"""
        if not self.is_capturing:
            return
            
        logger.info("🛑 Stopping continuous audio capture...")
        self.is_capturing = False
        
        if self.voice_client.recording:
            self.voice_client.stop_recording()
            
        if self.capture_task:
            self.capture_task.cancel()
            try:
                await self.capture_task
            except asyncio.CancelledError:
                pass
                
        logger.info("✅ Continuous capture stopped")
        
    async def _audio_callback(self, sink: discord.sinks.Sink, error=None):
        """Called when audio data is available"""
        if error:
            logger.error(f"❌ Audio callback error: {error}")
            return
            
        # This is called when audio chunks are available
        # The actual streaming happens in _stream_audio_continuously
        
    async def _stream_audio_continuously(self, sink):
        """Stream audio chunks continuously to Pipecat"""
        last_stream_time = 0
        
        try:
            while self.is_capturing:
                await asyncio.sleep(0.1)  # Check every 100ms
                
                # Get accumulated audio data
                current_time = time.time()
                
                # Stream audio every 500ms for real-time processing
                if current_time - last_stream_time >= 0.5:
                    
                    # Process each user's audio
                    if sink.audio_data:
                        for user_id, audio in sink.audio_data.items():
                            user = self.bot.get_user(user_id)
                            
                            # Skip bots and empty audio
                            if not user or user.bot:
                                continue
                                
                            # Get audio bytes
                            audio_bytes = audio.file.getvalue()
                            
                            if len(audio_bytes) > 1000:  # Only process substantial audio
                                logger.debug(f"📡 Streaming {len(audio_bytes)} bytes from {user.display_name}")
                                
                                # Stream to Pipecat for real-time processing
                                await self.streamer.stream_audio_to_pipecat(audio_bytes)
                                
                                # Clear the audio data to prevent reprocessing
                                audio.file.seek(0)
                                audio.file.truncate(0)
                    
                    last_stream_time = current_time
                    
        except asyncio.CancelledError:
            logger.info("🛑 Audio streaming task cancelled")
        except Exception as e:
            logger.error(f"❌ Error in continuous audio streaming: {e}")

class PipecatStreamingBot(discord.Client):
    """Discord bot with Pipecat streaming integration"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.audio_streamer = PipecatAudioStreamer()
        self.voice_captures = {}  # guild_id -> ContinuousVoiceCapture
        
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Connect to Pipecat pipeline
        connected = await self.audio_streamer.connect_to_pipecat()
        if connected:
            logger.info("🎉 REAL-TIME VOICE PIPELINE READY!")
            logger.info("💬 Features:")
            logger.info("  • Continuous audio streaming (no start/stop)")
            logger.info("  • Voice Activity Detection (VAD)")
            logger.info("  • Local Parakeet + Phi-3 + Kokoro")  
            logger.info("  • Real-time conversation")
            logger.info("  • Interruptible AI responses")
            logger.info("Commands: !stream_start, !stream_stop, !status, !help")
        else:
            logger.error("❌ Failed to connect to Pipecat pipeline")
            
    async def on_message(self, message):
        """Handle message commands"""
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!stream_start' or content == '!listen':
            await self._start_streaming(message)
        elif content == '!stream_stop' or content == '!stop':
            await self._stop_streaming(message)
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
            
    async def _start_streaming(self, message):
        """Start continuous audio streaming"""
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        guild_id = message.guild.id
        channel = message.author.voice.channel
        
        try:
            # Connect to voice if needed
            if not message.guild.voice_client:
                voice_client = await channel.connect()
                logger.info(f"🔌 Connected to {channel.name}")
            else:
                voice_client = message.guild.voice_client
                
            # Start continuous capture
            capture = ContinuousVoiceCapture(self, voice_client, self.audio_streamer)
            await capture.start_continuous_capture()
            
            self.voice_captures[guild_id] = capture
            
            embed = discord.Embed(
                title="🎙️ Real-time Voice Streaming Started!",
                description=f"Now streaming audio from **{channel.name}** to Pipecat pipeline!",
                color=0x00ff00
            )
            embed.add_field(
                name="🚀 Features Active:",
                value="• Continuous audio streaming\\n• Voice Activity Detection (VAD)\\n• Local AI models (Parakeet + Phi-3 + Kokoro)\\n• Real-time processing\\n• Interruptible responses",
                inline=False
            )
            embed.add_field(
                name="🎯 How it works:",
                value="• **Just speak naturally** - no commands needed\\n• VAD automatically detects your voice\\n• AI processes and responds in real-time\\n• You can interrupt the AI anytime",
                inline=False
            )
            embed.add_field(
                name="🔧 Commands:",
                value="`!stream_stop` - Stop streaming\\n`!status` - Show pipeline status",
                inline=False
            )
            
            await message.reply(embed=embed)
            logger.info(f"✅ Real-time streaming started in {channel.name}")
            
        except Exception as e:
            await message.reply(f"❌ Failed to start streaming: {str(e)}")
            logger.error(f"❌ Streaming start error: {e}")
            
    async def _stop_streaming(self, message):
        """Stop continuous audio streaming"""
        guild_id = message.guild.id
        
        if guild_id in self.voice_captures:
            capture = self.voice_captures[guild_id]
            await capture.stop_continuous_capture()
            del self.voice_captures[guild_id]
            
        if message.guild.voice_client:
            await message.guild.voice_client.disconnect()
            
        await message.reply("🛑 Real-time streaming stopped!")
        logger.info("✅ Streaming stopped")
        
    async def _show_status(self, message):
        """Show streaming status"""
        embed = discord.Embed(title="📊 Pipecat Streaming Bot Status", color=0x0099ff)
        
        pipecat_status = "✅ Connected" if self.audio_streamer.is_streaming else "❌ Disconnected"
        active_streams = len(self.voice_captures)
        
        embed.add_field(
            name="Pipeline Status",
            value=f"Pipecat Backend: {pipecat_status}\\nActive Streams: {active_streams}",
            inline=False
        )
        
        if self.voice_captures:
            stream_info = []
            for guild_id, capture in self.voice_captures.items():
                guild = self.get_guild(guild_id)
                if guild and capture.voice_client:
                    channel_name = capture.voice_client.channel.name if capture.voice_client.channel else "Unknown"
                    stream_info.append(f"• {guild.name}: {channel_name}")
                    
            if stream_info:
                embed.add_field(
                    name="Active Streams",
                    value="\\n".join(stream_info),
                    inline=False
                )
                
        await message.reply(embed=embed)
        
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🎙️ Pipecat Streaming Bot",
            description="Real-time voice conversation with local AI models",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Commands",
            value="`!stream_start` - Start real-time streaming\\n`!stream_stop` - Stop streaming\\n`!status` - Show pipeline status\\n`!help` - This help",
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value="1. Join a voice channel\\n2. Use `!stream_start`\\n3. **Just speak naturally**\\n4. AI responds in real-time\\n5. No need for start/stop commands!",
            inline=False
        )
        
        embed.add_field(
            name="Technology Stack",
            value="• **Pipecat**: Real-time streaming framework\\n• **Silero VAD**: Automatic voice detection\\n• **Parakeet**: Local speech recognition\\n• **Phi-3**: Local language model\\n• **Kokoro**: Local text-to-speech",
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
    
    bot = PipecatStreamingBot()
    
    try:
        logger.info("[START] Starting Pipecat Streaming Bot...")
        logger.info("[INFO] Real-time voice processing with VAD + local models")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()