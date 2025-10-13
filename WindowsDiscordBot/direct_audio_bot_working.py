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
import tempfile
import os
import wave
from pathlib import Path
import sys
import numpy as np

sys.path.append(str(Path(__file__).parent))
from config import Config
from robust_websocket_client import RobustWebSocketClient
try:
    from load_config import config as services_config
except ImportError:
    services_config = {}

# Ensure logs directory exists
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "discord_bot.log"

# Configure logging to both file and console
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

class DirectAudioCapture:
    """Direct microphone capture bypassing Discord Opus"""
    
    def __init__(self, websocket_url=None):
        # Use centralized config or fallback
        if websocket_url is None:
            websocket_url = services_config.get('websocket_url', 'ws://127.0.0.1:8002')
        self.websocket_url = websocket_url
        self.websocket_client = RobustWebSocketClient(websocket_url, self._handle_websocket_message)
        self.is_capturing = False
        self.chunks_sent = 0
        self.audio_thread = None
        # Use asyncio event loop for all async operations
        self.loop = None
        
        # Smart echo prevention system
        self.tts_start_time = 0  # When TTS started playing
        self.tts_duration = 0  # Expected TTS duration
        self.conversation_state = "listening"  # listening, brief_mute, tts_playing, post_tts_pause
        
        # Smart interrupt detection
        self.consecutive_speech_chunks = 0
        self.speech_chunk_threshold = 3  # Require 3 consecutive chunks to confirm interrupt
        self.normal_speech_threshold = 0.15
        self.tts_speech_threshold = 0.3  # Higher threshold during TTS
        
        # Voice client reference for audio playback
        self.active_voice_client = None
        
    async def _handle_websocket_message(self, message):
        """Handle messages received from the WebSocket server"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                if data.get("type") == "audio_output":
                    # Handle audio response with smart conversation state management
                    logger.info("🔊 Received audio response from server")
                    await self._handle_tts_start(data)
                    await self._play_audio_response(data)
                elif data.get("type") == "audio_response":
                    # Handle audio response in different format  
                    logger.info("🔊 Received audio_response from server")
                    await self._handle_tts_start(data)
                    await self._play_audio_response(data)
                elif data.get("type") == "text":
                    # Handle text response from server
                    logger.info(f"💬 Server response: {data.get('text', '')[:50]}...")
                elif data.get("type") == "transcription":
                    logger.info(f"📝 Transcription: {data.get('text', '')}")
                elif data.get("type") == "tts_interrupted":
                    # Handle TTS interruption confirmation
                    logger.info("⚡ TTS playback interrupted by user")
                    self.conversation_state = "listening"
                    self.consecutive_speech_chunks = 0
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
    
    async def _handle_tts_start(self, data):
        """Handle the start of TTS playback with smart conversation state"""
        try:
            # Calculate TTS duration for state management
            audio_b64 = data.get("data", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                # Estimate duration: 22050Hz, 16-bit (2 bytes per sample), mono
                self.tts_duration = len(audio_bytes) / (22050 * 2)
                self.tts_start_time = time.time()
                self.conversation_state = "brief_mute"  # Start with brief mute
                self.consecutive_speech_chunks = 0
                
                logger.info(f"🎵 TTS starting - {self.tts_duration:.1f}s duration, brief mute period")
                
                # Schedule state transitions
                async def transition_to_tts_playing():
                    await asyncio.sleep(0.5)  # 500ms brief mute
                    if self.conversation_state == "brief_mute":
                        self.conversation_state = "tts_playing"
                        logger.info("🎤 Smart interrupt detection enabled")
                
                async def transition_to_post_pause():
                    await asyncio.sleep(self.tts_duration + 0.1)  # Wait for TTS to finish
                    if self.conversation_state == "tts_playing":
                        self.conversation_state = "post_tts_pause"
                        logger.info("⏸️ Post-TTS pause started")
                        
                async def return_to_listening():
                    await asyncio.sleep(self.tts_duration + 0.6)  # TTS + 500ms pause
                    if self.conversation_state == "post_tts_pause":
                        self.conversation_state = "listening"
                        self.consecutive_speech_chunks = 0
                        logger.info("👂 Full listening mode resumed")
                
                # Schedule all transitions
                asyncio.create_task(transition_to_tts_playing())
                asyncio.create_task(transition_to_post_pause())
                asyncio.create_task(return_to_listening())
                
        except Exception as e:
            logger.error(f"❌ Error in TTS start handler: {e}")
            self.conversation_state = "listening"  # Fallback to normal mode
    
    async def _play_audio_response(self, data):
        """Play audio response through Discord voice client"""
        try:
            # Extract audio data
            audio_b64 = data.get("data", "")
            if not audio_b64:
                logger.warning("⚠️ No audio data in response")
                return
                
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_b64)
            logger.info(f"🎵 Decoded {len(audio_bytes)} bytes of audio")
            
            # Check if we have an active voice client
            if not self.active_voice_client or not self.active_voice_client.is_connected():
                logger.warning("⚠️ No active voice connection for audio playback")
                return
                
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write raw PCM data as WAV format
                
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(22050)  # Sample rate from Kokoro TTS
                    wav_file.writeframes(audio_bytes)
                
                temp_path = temp_file.name
                
            logger.info(f"🎵 Created temporary audio file: {temp_path}")
            
            # Play audio through Discord
            try:
                if self.active_voice_client.is_playing():
                    self.active_voice_client.stop()
                    
                audio_source = discord.FFmpegPCMAudio(temp_path)
                self.active_voice_client.play(audio_source)
                logger.info("🔊 Playing audio response through Discord")
                
                # Clean up temp file after a delay
                def cleanup_temp_file():
                    try:
                        os.unlink(temp_path)
                        logger.debug(f"🗑️ Cleaned up temp file: {temp_path}")
                    except:
                        pass
                        
                # Schedule cleanup after 30 seconds
                threading.Timer(30.0, cleanup_temp_file).start()
                
            except Exception as e:
                logger.error(f"❌ Failed to play audio: {e}")
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ Error playing audio response: {e}")
        
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
        self.active_voice_client = None  # Clear voice client reference
        self.conversation_state = "listening"  # Reset conversation state
        self.consecutive_speech_chunks = 0
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
            
            def audio_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                    
                # Smart conversation state-aware audio processing
                current_time = time.time()
                audio_amplitude = np.max(np.abs(indata))
                
                if self.conversation_state == "brief_mute":
                    # Complete silence during brief mute to prevent immediate feedback
                    logger.debug(f"🔇 Brief mute period - ignoring audio (amplitude: {audio_amplitude:.3f})")
                    return
                    
                elif self.conversation_state == "tts_playing":
                    # Smart interrupt detection during TTS playback
                    if audio_amplitude > self.tts_speech_threshold:
                        self.consecutive_speech_chunks += 1
                        logger.debug(f"🎤 Speech detected during TTS: {self.consecutive_speech_chunks}/{self.speech_chunk_threshold} (amp: {audio_amplitude:.3f})")
                        
                        if self.consecutive_speech_chunks >= self.speech_chunk_threshold:
                            # Confirmed interrupt - user is speaking over TTS
                            logger.info(f"⚡ Interrupt confirmed! User speaking over TTS (amp: {audio_amplitude:.3f})")
                            self.conversation_state = "listening"
                            self.consecutive_speech_chunks = 0
                            
                            # Stop TTS playback
                            if self.active_voice_client and self.active_voice_client.is_playing():
                                self.active_voice_client.stop()
                                logger.info("🛑 TTS playback stopped")
                            
                            # Send interrupt signal to backend
                            interrupt_msg = {
                                "type": "interrupt_tts",
                                "timestamp": current_time,
                                "amplitude": float(audio_amplitude)
                            }
                            asyncio.run_coroutine_threadsafe(
                                self.websocket_client.send(interrupt_msg), 
                                self.loop
                            )
                        else:
                            # Not confirmed yet - don't send audio
                            return
                    else:
                        # Reset counter if amplitude drops
                        if self.consecutive_speech_chunks > 0:
                            logger.debug(f"🔉 Speech amplitude dropped - resetting counter")
                        self.consecutive_speech_chunks = 0
                        return
                        
                elif self.conversation_state == "post_tts_pause":
                    # Brief pause after TTS - higher threshold to avoid immediate re-trigger
                    if audio_amplitude > self.tts_speech_threshold:
                        self.consecutive_speech_chunks += 1
                        if self.consecutive_speech_chunks >= 2:  # Shorter confirmation needed
                            logger.info(f"🎤 User speech detected in post-TTS pause - resuming listening")
                            self.conversation_state = "listening"
                            self.consecutive_speech_chunks = 0
                            # Fall through to normal processing
                        else:
                            return
                    else:
                        self.consecutive_speech_chunks = 0
                        return
                
                # Normal listening mode or confirmed interrupt
                if self.conversation_state == "listening":
                    # Reset consecutive counter for normal mode
                    self.consecutive_speech_chunks = 0
                    
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
                voice_client = message.guild.voice_client
            else:
                voice_client = await voice_channel.connect()
                
            logger.info(f"✅ Connected to {voice_channel.name}")
            
            # Set the active voice client reference for audio playback
            self.audio_capture.active_voice_client = voice_client
            
            # Wait for services to be ready if config available
            if services_config:
                initial_delay = services_config.get('connection', {}).get('initial_delay', 5)
                logger.info(f"⏳ Waiting {initial_delay}s for services to initialize...")
                await asyncio.sleep(initial_delay)
            
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
    logger.info(f"📄 Logging to: {log_file}")
    
    config = Config()
    bot = DirectAudioBot()
    
    await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())