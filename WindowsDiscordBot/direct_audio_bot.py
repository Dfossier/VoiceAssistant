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
    
    def __init__(self, websocket_url="ws://172.20.104.13:8002", bot=None):
        self.websocket_url = websocket_url
        self.websocket_client = RobustWebSocketClient(websocket_url, self._handle_websocket_message)
        self.is_capturing = False
        self.chunks_sent = 0
        self.audio_thread = None
        self.bot = bot
        self.is_playing_tts = False  # Track when TTS is playing to prevent echo
        self.tts_cooldown_until = 0  # Timestamp for TTS cooldown period
        
    def _should_process_audio(self, audio_data=None):
        """Check if we should process audio (allows interruptions but prevents echo)"""
        import time
        import numpy as np
        current_time = time.time()
        
        # During cooldown, only process if audio is loud enough (interruption)
        if current_time < self.tts_cooldown_until:
            if audio_data is not None:
                # Calculate audio level to detect interruptions
                audio_level = np.abs(audio_data).mean() if len(audio_data) > 0 else 0
                interruption_threshold = 0.05  # Threshold for detecting speech vs echo
                if audio_level > interruption_threshold:
                    logger.info(f"🗣️ Interruption detected during cooldown (level: {audio_level:.3f})")
                    return True
            return False
            
        # During TTS playback, allow interruptions if audio is loud enough
        if self.is_playing_tts:
            if audio_data is not None:
                audio_level = np.abs(audio_data).mean() if len(audio_data) > 0 else 0
                interruption_threshold = 0.08  # Higher threshold during playback
                if audio_level > interruption_threshold:
                    logger.info(f"🛑 TTS interrupted by user speech (level: {audio_level:.3f})")
                    # Stop current TTS playback
                    if self.bot:
                        for vc in self.bot.voice_clients:
                            if vc.is_playing():
                                vc.stop()
                                break
                    self._set_tts_playing(False, cooldown_seconds=0.5)  # Short cooldown after interruption
                    return True
            return False
            
        return True
        
    def _set_tts_playing(self, playing, cooldown_seconds=2.0):
        """Set TTS playback state and cooldown period"""
        import time
        self.is_playing_tts = playing
        if not playing:
            # Set cooldown period after TTS stops
            self.tts_cooldown_until = time.time() + cooldown_seconds
        
    async def _handle_websocket_message(self, message):
        """Handle messages received from the WebSocket server"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                if data.get("type") == "audio_output":
                    # Handle audio response from server
                    logger.info("🔊 Received audio response from server")
                    await self._play_audio_response(data)
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
                    
                # Check if we should process audio (allows interruptions)
                if self.is_capturing and len(indata) > 0 and self._should_process_audio(indata):
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
    
    async def _play_audio_response(self, audio_data):
        """Play audio response through Discord voice channel"""
        try:
            import base64
            import io
            import discord
            
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data.get("data", ""))
            sample_rate = audio_data.get("sample_rate", 22050)
            channels = audio_data.get("channels", 1)
            
            logger.info(f"🔊 Playing audio: {len(audio_bytes)} bytes at {sample_rate}Hz, {channels}ch")
            
            # Trigger playback through the bot instance
            if self.bot:
                await self.bot._play_audio_in_channel(audio_bytes, sample_rate, channels)
            else:
                logger.warning("⚠️ No bot instance - cannot play audio")
                
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")

class DirectAudioBot(discord.Client):
    """Discord bot with direct audio capture"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.audio_capture = DirectAudioCapture(bot=self)
        self.capture_tasks = {}
        self.pending_audio = None
        
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
    
    async def _play_audio_in_channel(self, audio_bytes, sample_rate, channels):
        """Play audio in the current voice channel"""
        try:
            import io
            import discord
            import tempfile
            import os
            import wave
            
            # Set TTS playing state to prevent echo
            self.audio_capture._set_tts_playing(True)
            
            # Find an active voice client
            voice_client = None
            for vc in self.voice_clients:
                if vc.is_connected():
                    voice_client = vc
                    break
            
            if not voice_client:
                logger.warning("⚠️ No active voice connection for audio playback")
                self.audio_capture._set_tts_playing(False)  # Clear state if no playback
                return
            
            # Stop any currently playing audio
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.1)  # Brief pause
            
            # Create temporary WAV file for Discord
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Write PCM data as WAV file
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_bytes)
                
                # Create Discord audio source from file
                audio_source = discord.FFmpegPCMAudio(
                    temp_path,
                    options='-f wav'
                )
                
                # Clean up after playback
                def cleanup_after_play(error):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    if error:
                        logger.error(f"Audio playback error: {error}")
                    # Clear TTS playing state and start cooldown
                    self.audio_capture._set_tts_playing(False)
                
                # Play audio with cleanup callback
                voice_client.play(audio_source, after=cleanup_after_play)
                logger.info(f"🔊 Playing TTS audio in {voice_client.channel.name} ({len(audio_bytes)} bytes at {sample_rate}Hz)")
                
        except Exception as e:
            logger.error(f"❌ Discord audio playback error: {e}")
            # Clear TTS state on error
            self.audio_capture._set_tts_playing(False)
            # Fallback: Try direct PCM
            try:
                if voice_client and not voice_client.is_playing():
                    # Create a BytesIO stream for direct PCM
                    pcm_source = discord.PCMAudio(io.BytesIO(audio_bytes))
                    voice_client.play(pcm_source)
                    logger.info("🔊 Fallback: Playing raw PCM audio")
            except Exception as e2:
                logger.error(f"❌ Fallback PCM playback failed: {e2}")
                # Last resort: Log the issue
                logger.error("❌ All audio playback methods failed - check Discord voice connection")

def main():
    Config.validate()
    bot = DirectAudioBot()
    logger.info("🚀 Starting direct audio capture bot...")
    logger.info("📝 Bypassing Discord Opus completely")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()