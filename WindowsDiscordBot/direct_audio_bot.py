#!/usr/bin/env python3
"""
Direct audio capture bot - bypasses Discord Opus issues
Captures audio directly from microphone while connected to Discord voice
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

sys.path.append(str(Path(__file__).parent))
from config import Config
from robust_websocket_client import RobustWebSocketClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("DirectAudioBot")

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
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
        
    async def connect(self):
        """Connect to backend using robust WebSocket client"""
        try:
            logger.info(f"🔌 Connecting to {self.websocket_url}...")
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
            
    async def _receive_loop(self):
        """Receive responses from backend - now handled by RobustWebSocketClient"""
        logger.info("📥 Message receiving is now handled by RobustWebSocketClient automatically")
        # The robust WebSocket client handles message receiving via the callback
        # No need for a separate receive loop
            
    async def start_capture(self):
        """Start direct audio capture"""
        if self.is_capturing:
            return False
            
        # Try different audio libraries in order of preference
        audio_methods = [
            self._try_sounddevice,
            self._try_pyaudio,
            self._try_wave_recording
        ]
        
        for method in audio_methods:
            try:
                result = await method()
                if result:
                    return True
            except Exception as e:
                logger.debug(f"Audio method failed: {e}")
                continue
                
        logger.error("❌ No audio capture methods available")
        logger.info("💡 Install audio library: pip install sounddevice pyaudio")
        return False
        
    async def _try_sounddevice(self):
        """Try sounddevice audio capture"""
        try:
            import sounddevice as sd
            import numpy as np
            
            self.is_capturing = True
            logger.info("🎤 Using sounddevice for audio capture...")
            
            sample_rate = 16000
            channels = 1
            chunk_duration = 0.5  # Send smaller chunks more frequently
            chunk_samples = int(sample_rate * chunk_duration)
            
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                    
                if self.is_capturing and len(indata) > 0:
                    audio_int16 = (indata * 32767).astype(np.int16)
                    threading.Thread(
                        target=self._send_audio_sync,
                        args=(audio_int16.tobytes(),),
                        daemon=True
                    ).start()
            
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
                    threading.Thread(
                        target=self._send_audio_sync,
                        args=(data,),
                        daemon=True
                    ).start()
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
            
    async def _try_wave_recording(self):
        """Fallback: simulate audio capture"""
        logger.warning("⚠️ No audio libraries available - using simulation")
        logger.info("💡 Install: pip install sounddevice pyaudio")
        
        self.is_capturing = True
        
        # Send test audio data
        import struct
        sample_rate = 16000
        duration = 2.0
        samples = int(sample_rate * duration)
        
        while self.is_capturing:
            # Generate silent test data
            test_audio = struct.pack('<' + 'h' * samples, *([0] * samples))
            threading.Thread(
                target=self._send_audio_sync,
                args=(test_audio,),
                daemon=True
            ).start()
            await asyncio.sleep(2)
            
        return True
            
    def _send_audio_sync(self, audio_data):
        """Send audio data synchronously (called from thread)"""
        try:
            if self.websocket_client.connected and self.is_capturing:
                self.chunks_sent += 1
                
                # Create event loop for async operations
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Send in backend's expected JSON format
                    message = {
                        "type": "audio_input",  # Backend's expected type
                        "data": base64.b64encode(audio_data).decode('utf-8'),
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "pcm16"
                    }
                    
                    success = loop.run_until_complete(self.websocket_client.send(message))
                    if success:
                        logger.info(f"📡 Sent audio chunk #{self.chunks_sent}: {len(audio_data)} bytes as audio_input")
                    else:
                        logger.error(f"❌ Failed to send audio chunk #{self.chunks_sent}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to send audio: {e}")
                    # Try fallback - raw binary (in case Pipecat is using protobuf)
                    try:
                        success = loop.run_until_complete(self.websocket_client.send_binary(audio_data))
                        if success:
                            logger.info(f"📡 Sent raw binary audio chunk #{self.chunks_sent} as fallback")
                        else:
                            logger.error(f"❌ Binary fallback failed for chunk #{self.chunks_sent}")
                    except Exception as e2:
                        logger.error(f"❌ Binary fallback exception: {e2}")
                finally:
                    loop.close()
                
        except Exception as e:
            logger.error(f"❌ Send error: {e}")

class DirectAudioBot(discord.Client):
    """Discord bot with direct audio capture"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.audio_capture = DirectAudioCapture()
        self.capture_tasks = {}
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("🎤 Direct audio capture bot - bypasses Discord Opus")
        logger.info("Commands: !direct, !stop")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!direct':
            await self._start_direct_capture(message)
        elif content == '!stop':
            await self._stop_direct_capture(message)
            
    async def _start_direct_capture(self, message):
        """Start direct audio capture"""
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        guild_id = message.guild.id
        
        # Stop existing capture
        if guild_id in self.capture_tasks:
            self.capture_tasks[guild_id].cancel()
            
        try:
            channel = message.author.voice.channel
            
            # Connect to voice (for presence, not audio)
            if message.guild.voice_client:
                vc = message.guild.voice_client
                if vc.channel != channel:
                    await vc.move_to(channel)
            else:
                vc = await channel.connect()
                
            logger.info(f"✅ Connected to {channel.name}")
            
            # Connect to backend
            if not await self.audio_capture.connect():
                await message.reply("❌ Failed to connect to backend")
                return
                
            # Send StartFrame to initialize the pipeline
            await self.audio_capture.send_start_frame()
                
            # Start direct audio capture task
            task = asyncio.create_task(self._capture_loop(guild_id))
            self.capture_tasks[guild_id] = task
            
            embed = discord.Embed(
                title="🎤 Direct Audio Capture!",
                description=f"Bypassing Discord Opus, capturing directly from microphone",
                color=0x00ff00
            )
            embed.add_field(
                name="How it works:",
                value="• Direct microphone access\\n• 16kHz mono PCM\\n• No Discord Opus decoding\\n• Sent directly to Pipecat backend",
                inline=False
            )
            embed.add_field(
                name="Status:",
                value="🟢 **Speak now** - I'm capturing directly!",
                inline=False
            )
            
            await message.reply(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_direct_capture(self, message):
        """Stop direct capture"""
        guild_id = message.guild.id
        
        try:
            # Cancel capture task
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
            
    async def _capture_loop(self, guild_id):
        """Main capture loop"""
        try:
            logger.info("🎤 Starting direct audio capture loop...")
            
            # Start capturing
            await self.audio_capture.start_capture()
            
        except asyncio.CancelledError:
            logger.info(f"🛑 Direct capture stopped. Sent {self.audio_capture.chunks_sent} chunks")
        except Exception as e:
            logger.error(f"❌ Capture loop error: {e}")

def main():
    Config.validate()
    bot = DirectAudioBot()
    logger.info("🚀 Starting direct audio capture bot...")
    logger.info("📝 Bypassing Discord Opus completely")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()