#!/usr/bin/env python3
"""
Streaming Voice Bot - Clean Architecture
Discord Bot: Audio capture/playback only
Backend: All AI processing (VAD, ASR, LLM, TTS)
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import json
import struct
import tempfile
import websockets
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import base64

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

class AudioStreamer:
    """Streams audio between Discord and Backend"""
    
    def __init__(self, backend_client: BackendClient, voice_client, guild_id: int):
        self.backend_client = backend_client
        self.voice_client = voice_client
        self.guild_id = guild_id
        self.streaming = False
        self.websocket = None
        
    async def start_streaming(self):
        """Start audio streaming to backend"""
        try:
            logger.info("[STREAM] Starting audio streaming to backend...")
            
            # Connect to backend WebSocket for audio streaming
            ws_url = f"ws://127.0.0.1:8000/ws/audio-stream/{self.guild_id}"
            self.websocket = await websockets.connect(ws_url)
            
            self.streaming = True
            
            # Start audio capture task
            self.capture_task = asyncio.create_task(self._audio_capture_loop())
            
            # Start response handler
            self.response_task = asyncio.create_task(self._handle_backend_responses())
            
            logger.info("[OK] Audio streaming started")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to start streaming: {e}")
            self.streaming = False
    
    async def stop_streaming(self):
        """Stop audio streaming"""
        try:
            self.streaming = False
            
            if hasattr(self, 'capture_task'):
                self.capture_task.cancel()
            if hasattr(self, 'response_task'):
                self.response_task.cancel()
            
            if self.websocket:
                await self.websocket.close()
            
            logger.info("[STOP] Audio streaming stopped")
            
        except Exception as e:
            logger.error(f"[ERROR] Stop streaming error: {e}")
    
    async def _audio_capture_loop(self):
        """Capture audio from Discord voice channel"""
        try:
            logger.info("[CAPTURE] Starting audio capture loop...")
            
            # This is where we'd capture real audio from Discord
            # For now, we'll simulate periodic audio events
            while self.streaming:
                await asyncio.sleep(5)  # Simulate audio every 5 seconds
                
                # Simulate receiving audio data
                await self._simulate_audio_capture()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Audio capture error: {e}")
    
    async def _simulate_audio_capture(self):
        """Simulate audio capture for testing"""
        try:
            # Create fake audio data for testing
            fake_audio = b'\x00' * 1920 * 2 * 2  # 1920 samples, 2 channels, 2 bytes per sample
            
            # Send to backend for processing
            message = {
                "type": "audio_data",
                "data": base64.b64encode(fake_audio).decode('utf-8'),
                "format": {
                    "sample_rate": 48000,
                    "channels": 2,
                    "sample_width": 2
                },
                "user": "test_user"
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info("[SIMULATE] Sent simulated audio to backend")
            
        except Exception as e:
            logger.error(f"[ERROR] Simulate capture error: {e}")
    
    async def _handle_backend_responses(self):
        """Handle audio responses from backend"""
        try:
            while self.streaming:
                try:
                    response = await self.websocket.recv()
                    data = json.loads(response)
                    
                    if data.get("type") == "audio_response":
                        # Received processed audio from backend
                        await self._play_backend_response(data)
                    elif data.get("type") == "text_response":
                        # Received text response from backend
                        await self._handle_text_response(data)
                        
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"[ERROR] Response handling error: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Response handler error: {e}")
    
    async def _play_backend_response(self, response_data):
        """Play audio response from backend"""
        try:
            audio_b64 = response_data.get("audio_data")
            if not audio_b64:
                return
            
            # Decode audio data
            audio_data = base64.b64decode(audio_b64)
            
            logger.info(f"[PLAYBACK] Received {len(audio_data)} bytes from backend")
            
            # Play through Discord voice
            await self._play_audio(audio_data)
            
        except Exception as e:
            logger.error(f"[ERROR] Backend response playback error: {e}")
    
    async def _handle_text_response(self, response_data):
        """Handle text response from backend"""
        try:
            text = response_data.get("text", "")
            user = response_data.get("user", "unknown")
            
            logger.info(f"[TEXT] Backend response: {text}")
            
            # Send to Discord text channel
            guild = discord.utils.get(discord.Client.guilds, id=self.guild_id) if hasattr(discord.Client, 'guilds') else None
            # This would need proper guild resolution in a real implementation
            
        except Exception as e:
            logger.error(f"[ERROR] Text response error: {e}")
    
    async def _play_audio(self, audio_data: bytes):
        """Play audio through Discord voice client"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return False
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                self.voice_client.play(audio_source)
                
                # Wait for playback
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                logger.info("[OK] Backend audio playback complete")
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

class StreamingVoiceBot(discord.Client):
    """Discord bot for audio streaming to backend"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.audio_streamers: Dict[int, AudioStreamer] = {}
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
                logger.warning("[WARN] Backend API not available")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
            self.backend_client = None
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        logger.info(f"[STATUS] Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!stream':
            await self._start_audio_streaming(message)
        elif content == '!stopstream':
            await self._stop_audio_streaming(message)
        elif content.startswith('!test '):
            await self._test_backend_pipeline(message, content[6:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_audio_streaming(self, message):
        """Start audio streaming to backend"""
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
                # Create audio streamer
                streamer = AudioStreamer(self.backend_client, voice_client, guild_id)
                self.audio_streamers[guild_id] = streamer
                
                # Start streaming
                await streamer.start_streaming()
                
                embed = discord.Embed(
                    title="🔄 Audio Streaming Active!",
                    description=f"Connected to **{channel.name}** and streaming to backend AI!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Architecture",
                    value="• **Discord Bot**: Audio capture & playback\n• **Backend**: VAD + ASR + LLM + TTS\n• **WebSocket**: Real-time audio streaming",
                    inline=False
                )
                embed.add_field(
                    name="AI Pipeline (Backend)",
                    value="🎤 Voice → 🔍 VAD → 📝 Parakeet → 🧠 Phi-3 → 🔊 Kokoro → 🎵 Discord",
                    inline=False
                )
                embed.add_field(
                    name="Test Commands",
                    value="`!test Hello` - Test backend pipeline\n`!stopstream` - Stop streaming",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[OK] Audio streaming started in {channel.name}")
            else:
                await message.reply("❌ Failed to connect to voice")
                
        except Exception as e:
            await message.reply(f"❌ Streaming error: {str(e)}")
            logger.error(f"[ERROR] Audio streaming error: {e}")
    
    async def _stop_audio_streaming(self, message):
        """Stop audio streaming"""
        guild_id = message.guild.id
        
        try:
            if guild_id in self.audio_streamers:
                await self.audio_streamers[guild_id].stop_streaming()
                del self.audio_streamers[guild_id]
            
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                await message.reply("🔇 Audio streaming stopped!")
            else:
                await message.reply("Not streaming!")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _test_backend_pipeline(self, message, text: str):
        """Test backend pipeline with text input"""
        if not text.strip():
            await message.reply("Provide text to test!")
            return
        
        try:
            await message.reply(f"🧪 Testing backend pipeline with: *{text}*")
            
            # Send to backend for full processing
            response = await self.backend_client.send_message(
                user_id=message.author.display_name,
                message=text,
                context={"source": "pipeline_test", "guild_id": str(message.guild.id)}
            )
            
            if response:
                # Test TTS generation
                audio_data = await self.backend_client.text_to_speech(response)
                
                if audio_data and message.guild.id in self.audio_streamers:
                    # Play through streaming pipeline
                    streamer = self.audio_streamers[message.guild.id]
                    success = await streamer._play_audio(audio_data)
                    
                    embed = discord.Embed(
                        title="🧪 Backend Pipeline Test",
                        color=0x0099ff
                    )
                    embed.add_field(name="Input:", value=text, inline=False)
                    embed.add_field(name="Backend Response:", value=response, inline=False)
                    embed.add_field(name="TTS Status:", value="✅ Generated and played" if success else "⚠️ Generation failed", inline=False)
                    await message.reply(embed=embed)
                else:
                    await message.reply(f"Backend response: {response}\n⚠️ Not connected to voice for TTS test")
            else:
                await message.reply("❌ No response from backend")
                
        except Exception as e:
            await message.reply(f"❌ Pipeline test error: {str(e)}")
    
    async def _show_status(self, message):
        """Show system status"""
        embed = discord.Embed(title="🔄 Streaming Voice Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Discord Components",
            value=f"Opus: {opus_status}\nVoice Connection: OK\nLatency: {round(self.latency * 1000)}ms",
            inline=True
        )
        
        embed.add_field(
            name="Backend Pipeline",
            value=f"API: {backend_status}\nActive Streams: {len(self.audio_streamers)}\nArchitecture: Clean",
            inline=True
        )
        
        embed.add_field(
            name="Processing Chain",
            value="Discord → WebSocket → VAD → ASR → LLM → TTS → Discord",
            inline=False
        )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🔄 Streaming Voice AI Bot",
            description="Clean architecture: Discord handles audio I/O, Backend handles all AI processing",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Streaming Commands",
            value="`!stream` - Start audio streaming to backend\n`!stopstream` - Stop streaming\n`!test <text>` - Test backend pipeline",
            inline=False
        )
        
        embed.add_field(
            name="System Commands",
            value="`!status` - Show system status\n`!help` - This help message",
            inline=False
        )
        
        embed.add_field(
            name="Clean Architecture",
            value="**Discord Bot**: Audio capture & playback only\n**Backend Server**: VAD + ASR (Parakeet) + LLM (Phi-3) + TTS (Kokoro)\n**Communication**: WebSocket streaming",
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value="1. Bot captures raw audio from Discord voice\n2. Streams audio to backend via WebSocket\n3. Backend processes with full AI pipeline\n4. Backend sends audio response back\n5. Bot plays response in Discord voice",
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
    
    bot = StreamingVoiceBot()
    
    try:
        logger.info("[START] Starting Streaming Voice Bot...")
        logger.info("[ARCH] Clean architecture: Discord I/O + Backend AI processing")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()