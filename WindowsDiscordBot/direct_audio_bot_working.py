#!/usr/bin/env python3
"""
Working direct audio capture bot - bypasses Discord Opus issues
Simplified version that fixes event loop issues
"""

import asyncio
import discord
import logging
import websockets
import json
import base64
import time
import threading
from pathlib import Path
import sys
import numpy as np

sys.path.append(str(Path(__file__).parent))
from config import Config
from robust_websocket_client import RobustWebSocketClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress discord warnings  
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class DirectAudioCapture:
    """Direct microphone capture bypassing Discord Opus"""
    
    def __init__(self, websocket_url="ws://172.20.104.13:8001"):
        self.websocket_url = websocket_url
        self.websocket_client = RobustWebSocketClient(websocket_url, self._handle_websocket_message)
        self.is_capturing = False
        self.chunks_sent = 0
        self.audio_thread = None
        # Use asyncio event loop for all async operations
        self.loop = None
        
    async def _handle_websocket_message(self, message):
        """Handle messages received from the WebSocket server"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                if data.get("type") == "audio_output":
                    # Handle audio response from server
                    logger.info("🔊 Received audio response from server")
                elif data.get("type") == "text":
                    # Handle text response from server
                    logger.info(f"💬 Server response: {data.get('text', '')[:50]}...")
                elif data.get("type") == "transcription":
                    logger.info(f"📝 Transcription: {data.get('text', '')}")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
        
    async def connect(self):
        """Connect to backend using robust WebSocket client"""
        try:
            logger.info(f"🔌 Connecting to {self.websocket_url}...")
            # Store the current event loop
            self.loop = asyncio.get_event_loop()
            success = await self.websocket_client.connect()
            if success:
                logger.info("✅ Connected to backend with robust WebSocket client")
                return True
            else:
                logger.error("❌ Failed to connect with robust WebSocket client")
                return False
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
            
    async def disconnect(self):
        """Disconnect from backend using robust WebSocket client"""
        self.is_capturing = False
        await self.websocket_client.disconnect()
            
    async def send_start_frame(self):
        """Send StartFrame to initialize Pipecat pipeline"""
        if not self.websocket_client.connected:
            logger.error("❌ Cannot send StartFrame - not connected")
            return
            
        try:
            start_message = {
                "type": "start",
                "audio_in_sample_rate": 16000,
                "audio_out_sample_rate": 16000,
                "allow_interruptions": True,
                "enable_metrics": True,
                "enable_usage_metrics": True
            }
            
            success = await self.websocket_client.send(start_message)
            if not success:
                logger.error("❌ Failed to send StartFrame")
                return
            logger.info("✅ Sent StartFrame to initialize pipeline")
            
        except Exception as e:
            logger.error(f"❌ Failed to send StartFrame: {e}")
    
    def _send_audio_async(self, audio_data):
        """Send audio data by scheduling it in the event loop"""
        if self.loop and not self.loop.is_closed():
            # Schedule the coroutine to run in the event loop
            asyncio.run_coroutine_threadsafe(self._send_audio_coro(audio_data), self.loop)
    
    async def _send_audio_coro(self, audio_data):
        """Async coroutine to send audio data"""
        try:
            if not self.websocket_client.connected or not self.is_capturing:
                return
                
            self.chunks_sent += 1
            
            # Send in backend's expected JSON format
            message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            success = await self.websocket_client.send(message)
            if success:
                logger.info(f"📡 Sent audio chunk #{self.chunks_sent}: {len(audio_data)} bytes as audio_input")
            else:
                logger.error(f"❌ Failed to send audio chunk #{self.chunks_sent}")
                
        except Exception as e:
            logger.error(f"❌ Error sending audio: {e}")
    
    async def start_capture(self):
        """Start direct audio capture"""
        if self.is_capturing:
            logger.warning("⚠️ Already capturing")
            return False
            
        self.is_capturing = True
        self.chunks_sent = 0
        logger.info("🎤 Starting direct audio capture loop...")
        
        # Try different audio capture methods
        if await self._try_sounddevice():
            return True
        elif await self._try_pyaudio():
            return True
        else:
            return await self._fallback_test_audio()
            
    async def stop_capture(self):
        """Stop audio capture"""
        logger.info("🛑 Stopping audio capture...")
        self.is_capturing = False
        
    async def _try_sounddevice(self):
        """Try sounddevice for audio capture"""
        try:
            import sounddevice as sd
            import numpy as np
            
            logger.info("🎤 Using sounddevice for audio capture...")
            
            sample_rate = 16000
            channels = 1
            chunk_duration = 0.5  # Send chunks every 0.5 seconds
            chunk_samples = int(sample_rate * chunk_duration)
            
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                    
                if self.is_capturing and len(indata) > 0:
                    audio_int16 = (indata * 32767).astype(np.int16)
                    # Send audio from thread using event loop
                    self._send_audio_async(audio_int16.tobytes())
            
            with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                callback=audio_callback,
                blocksize=chunk_samples,
                dtype=np.float32
            ):
                logger.info(f"✅ sounddevice active: {sample_rate}Hz, {channels}ch")
                while self.is_capturing:
                    await asyncio.sleep(1)
                    
            return True
            
        except ImportError:
            logger.debug("sounddevice not available")
            return False
            
    async def _try_pyaudio(self):
        """Try PyAudio capture"""
        try:
            import pyaudio
            import struct
            
            self.is_capturing = True
            logger.info("🎤 Using PyAudio for audio capture...")
            
            sample_rate = 16000
            channels = 1
            chunk_size = 1024
            format = pyaudio.paInt16
            
            audio = pyaudio.PyAudio()
            
            stream = audio.open(
                format=format,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            
            logger.info(f"✅ PyAudio active: {sample_rate}Hz, {channels}ch")
            
            while self.is_capturing:
                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    # Send audio from thread using event loop
                    self._send_audio_async(data)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"PyAudio read error: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            return True
            
        except ImportError:
            logger.debug("PyAudio not available")
            return False
            
    async def _fallback_test_audio(self):
        """Fallback: generate test audio"""
        logger.warning("⚠️ No audio library available, using test audio")
        
        # Send test audio data
        import struct
        sample_rate = 16000
        duration = 2.0
        samples = int(sample_rate * duration)
        
        while self.is_capturing:
            # Generate silent test data
            test_audio = struct.pack('<' + 'h' * samples, *([0] * samples))
            # Send test audio using event loop
            self._send_audio_async(test_audio)
            await asyncio.sleep(2)
            
        return True

class DirectAudioBot(discord.Client):
    """Discord bot with direct audio capture"""
    
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.audio_capture = DirectAudioCapture()
        self.capture_tasks = {}
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info(f"🎤 Direct audio capture bot - bypasses Discord Opus")
        logger.info(f"Commands: !direct, !stop")
        
    async def on_message(self, message):
        if message.author.bot:
            return
            
        if message.content == '!direct':
            await self._handle_direct(message)
        elif message.content == '!stop':
            await self._handle_stop(message)
            
    async def _handle_direct(self, message):
        """Handle !direct command"""
        if not message.author.voice:
            await message.reply("❌ You need to be in a voice channel!")
            return
            
        voice_channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Connect to voice
            if message.guild.voice_client:
                await message.guild.voice_client.move_to(voice_channel)
            else:
                await voice_channel.connect()
                
            logger.info(f"✅ Connected to {voice_channel.name}")
            
            # Connect to backend
            if not await self.audio_capture.connect():
                await message.reply("❌ Failed to connect to backend")
                return
                
            # Send StartFrame to initialize the pipeline
            await self.audio_capture.send_start_frame()
                
            # Start direct audio capture task
            task = asyncio.create_task(self._capture_loop(guild_id))
            self.capture_tasks[guild_id] = task
            
            await message.reply("🟢 **Speak now** - I'm capturing directly!")
            
        except Exception as e:
            logger.error(f"❌ Direct error: {e}")
            await message.reply(f"❌ Failed to start: {str(e)[:100]}...")
            
    async def _capture_loop(self, guild_id):
        """Audio capture loop"""
        try:
            await self.audio_capture.start_capture()
        except Exception as e:
            logger.error(f"❌ Capture error: {e}")
        finally:
            logger.info("📍 Capture loop ended")
            
    async def _handle_stop(self, message):
        """Handle !stop command"""
        guild_id = message.guild.id
        
        try:
            # Stop capture
            await self.audio_capture.stop_capture()
            
            # Cancel tasks
            if guild_id in self.capture_tasks:
                self.capture_tasks[guild_id].cancel()
                del self.capture_tasks[guild_id]
                
            # Disconnect audio
            await self.audio_capture.disconnect()
            
            # Disconnect voice
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                
            await message.reply("👋 **Direct capture stopped!**")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}")
            await message.reply(f"❌ Error stopping: {str(e)[:100]}...")

async def main():
    logger.info("🚀 Starting direct audio capture bot...")
    logger.info("📝 Bypassing Discord Opus completely")
    
    config = Config()
    bot = DirectAudioBot()
    
    await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())