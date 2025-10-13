#!/usr/bin/env python3
"""
Final working voice bot - bypasses py-cord callback issues
Uses a different approach without relying on recording callbacks
"""

import asyncio
import discord
import logging
import websockets
import json
import base64
import time
import wave
import io
import struct
from pathlib import Path
import sys
import threading

sys.path.append(str(Path(__file__).parent))
from config import Config

# Load Opus codec for voice support
def load_opus():
    """Load Opus codec for Discord voice"""
    if not discord.opus.is_loaded():
        logger.info("🔄 Loading Opus codec...")
        
        # Try common Opus library locations and names on Windows
        opus_locations = [
            # Current directory first (where you placed opus.dll)
            './opus.dll',
            'opus.dll',
            './libopus.dll',
            'libopus.dll',
            './libopus-0.dll',
            'libopus-0.dll',
            # Standard Windows library names (system will find in PATH)
            'opus',
            'libopus',
            'libopus-0',
            # System paths where Windows might have Opus
            r'C:\Windows\System32\opus.dll',
            r'C:\Windows\SysWOW64\opus.dll',
        ]
        
        for opus_lib in opus_locations:
            try:
                logger.info(f"🔍 Trying Opus library: {opus_lib}")
                discord.opus.load_opus(opus_lib)
                if discord.opus.is_loaded():
                    logger.info(f"✅ Successfully loaded Opus from: {opus_lib}")
                    return True
                else:
                    logger.warning(f"⚠️ Load attempt didn't fail but Opus not loaded: {opus_lib}")
            except Exception as e:
                logger.warning(f"❌ Failed to load {opus_lib}: {e}")
                
        # If all else fails, try without specifying a path (system default)
        try:
            logger.debug("Trying system default Opus loading...")
            discord.opus.load_opus()
            if discord.opus.is_loaded():
                logger.info("✅ Loaded Opus using system default")
                return True
        except Exception as e:
            logger.debug(f"System default Opus load failed: {e}")
                
        logger.error("❌ Could not load Opus library from any location")
        logger.info("💡 Solutions:")
        logger.info("   1. Download opus.dll and place it in this directory")
        logger.info("   2. Install FFmpeg with Opus support")  
        logger.info("   3. Install system-wide Opus library")
        logger.info("   4. Use conda: conda install opus")
        return False
    else:
        logger.info("✅ Opus already loaded")
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("FinalBot")

# Suppress discord warnings  
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class SimpleVoiceStreamer:
    """Simple voice streaming without callback complications"""
    
    def __init__(self, websocket_url="ws://127.0.0.1:8001"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.is_connected = False
        self.chunks_sent = 0
        
    async def connect(self):
        """Connect to backend"""
        try:
            logger.info(f"🔌 Connecting to {self.websocket_url}...")
            self.websocket = await websockets.connect(self.websocket_url)
            self.is_connected = True
            logger.info("✅ Connected to backend")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
            
    async def disconnect(self):
        """Disconnect from backend"""
        self.is_connected = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
    async def send_audio_chunk(self, audio_data):
        """Send audio chunk to backend"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            self.chunks_sent += 1
            
            message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16",
                "chunk_id": self.chunks_sent,
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📡 Sent chunk #{self.chunks_sent}: {len(audio_data)} bytes")
            return True
            
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            self.is_connected = False
            return False

class CallbackFreeRecorder:
    """Records audio without using problematic callbacks"""
    
    def __init__(self, voice_client):
        self.voice_client = voice_client
        self.current_sink = None
        self.is_recording = False
        
    async def record_timed_chunk(self, duration=2.0):
        """Record audio for specified duration"""
        if self.is_recording:
            logger.warning("Already recording")
            return None
            
        self.is_recording = True
        
        try:
            # Create sink
            sink = discord.sinks.WaveSink()
            
            # Simple completion tracking
            recording_done = asyncio.Event()
            
            async def callback(sink, error=None):
                # Async callback for py-cord v2.7.0
                if error:
                    logger.debug(f"Recording callback error: {error}")
                recording_done.set()
                
            # Start recording
            self.voice_client.start_recording(sink, callback)
            logger.info(f"🔴 Recording started for {duration}s...")
            
            # Record for specified duration
            await asyncio.sleep(duration)
            
            # Stop recording
            self.voice_client.stop_recording()
            logger.info("🛑 Recording stopped")
            
            # Wait for completion (max 0.5s)
            try:
                await asyncio.wait_for(recording_done.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                logger.debug("Recording callback timeout (normal)")
            
            # Extract audio data
            audio_data = self._extract_audio_from_sink(sink)
            
            if audio_data:
                logger.info(f"✅ Extracted {len(audio_data)} bytes of audio")
            else:
                logger.info("⚠️ No audio data extracted")
                
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ Recording error: {e}")
            return None
            
        finally:
            self.is_recording = False
            
    def _extract_audio_from_sink(self, sink):
        """Extract and combine audio data from sink"""
        try:
            if not hasattr(sink, 'audio_data') or not sink.audio_data:
                return None
                
            combined_audio = bytearray()
            
            for user_id, audio_obj in sink.audio_data.items():
                if hasattr(audio_obj, 'file'):
                    audio_obj.file.seek(0)
                    user_data = audio_obj.file.read()
                    
                    if user_data:
                        # Parse WAV to get raw PCM
                        pcm_data = self._extract_pcm_from_wav(user_data)
                        if pcm_data:
                            combined_audio.extend(pcm_data)
                            logger.debug(f"User {user_id}: {len(pcm_data)} PCM bytes")
                            
            return bytes(combined_audio) if combined_audio else None
            
        except Exception as e:
            logger.error(f"❌ Audio extraction error: {e}")
            return None
            
    def _extract_pcm_from_wav(self, wav_data):
        """Extract raw PCM from WAV data"""
        try:
            wav_io = io.BytesIO(wav_data)
            
            with wave.open(wav_io, 'rb') as wav:
                # Get parameters
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                framerate = wav.getframerate()
                frames = wav.readframes(wav.getnframes())
                
                logger.debug(f"WAV: {framerate}Hz, {channels}ch, {sample_width*8}-bit")
                
                # Convert to mono if stereo
                if channels == 2 and sample_width == 2:
                    # Convert stereo to mono by averaging channels
                    mono_frames = bytearray()
                    for i in range(0, len(frames), 4):  # 4 bytes per stereo sample
                        if i + 3 < len(frames):
                            # Get left and right samples
                            left = struct.unpack('<h', frames[i:i+2])[0]
                            right = struct.unpack('<h', frames[i+2:i+4])[0]
                            # Average and pack
                            mono = struct.pack('<h', int((left + right) / 2))
                            mono_frames.extend(mono)
                    frames = bytes(mono_frames)
                    
                # Resample if needed (simple decimation for 48kHz to 16kHz)
                if framerate == 48000:
                    # Simple 3:1 decimation
                    resampled = bytearray()
                    for i in range(0, len(frames), 6):  # Take every 3rd sample
                        if i + 1 < len(frames):
                            resampled.extend(frames[i:i+2])
                    frames = bytes(resampled)
                    
                return frames
                
        except Exception as e:
            logger.error(f"❌ WAV parsing error: {e}")
            return None

class FinalVoiceBot(discord.Client):
    """Final working voice bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.streamer = SimpleVoiceStreamer()
        self.streaming_tasks = {}
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("🎤 Final voice streaming bot - callback-free approach")
        logger.info("Commands: !final, !stop")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!final':
            await self._start_final_streaming(message)
        elif content == '!stop':
            await self._stop_final_streaming(message)
            
    async def _start_final_streaming(self, message):
        """Start final streaming approach"""
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        guild_id = message.guild.id
        
        # Stop existing task
        if guild_id in self.streaming_tasks:
            self.streaming_tasks[guild_id].cancel()
            
        try:
            channel = message.author.voice.channel
            
            # Connect to voice
            if message.guild.voice_client:
                vc = message.guild.voice_client
                if vc.channel != channel:
                    await vc.move_to(channel)
            else:
                vc = await channel.connect()
                
            logger.info(f"✅ Connected to {channel.name}")
            
            # Connect to backend
            if not await self.streamer.connect():
                await message.reply("❌ Failed to connect to backend")
                return
                
            # Start streaming task
            task = asyncio.create_task(self._streaming_loop(vc, guild_id))
            self.streaming_tasks[guild_id] = task
            
            embed = discord.Embed(
                title="🎙️ Final Voice Streaming!",
                description=f"Callback-free streaming from **{channel.name}**",
                color=0x00ff00
            )
            embed.add_field(
                name="Approach",
                value="• 2-second timed recordings\n• No callback complications\n• Direct audio extraction\n• 16kHz mono PCM output",
                inline=False
            )
            
            await message.reply(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_final_streaming(self, message):
        """Stop streaming"""
        guild_id = message.guild.id
        
        try:
            # Cancel task
            if guild_id in self.streaming_tasks:
                self.streaming_tasks[guild_id].cancel()
                del self.streaming_tasks[guild_id]
                
            # Disconnect
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                
            await self.streamer.disconnect()
            await message.reply("👋 **Streaming stopped!**")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}")
            
    async def _streaming_loop(self, voice_client, guild_id):
        """Main streaming loop without callbacks"""
        recorder = CallbackFreeRecorder(voice_client)
        
        try:
            logger.info("🎤 Starting callback-free streaming loop...")
            logger.info(f"Voice client connected: {voice_client.is_connected()}")
            logger.info(f"Voice client channel: {voice_client.channel}")
            
            loop_count = 0
            while voice_client.is_connected():
                try:
                    loop_count += 1
                    logger.info(f"🔄 Loop iteration #{loop_count}")
                    # Record 2-second chunk
                    logger.info("📀 Starting recording cycle...")
                    audio_data = await recorder.record_timed_chunk(2.0)
                    
                    if audio_data and len(audio_data) > 100:
                        # Send to backend
                        logger.info(f"📤 Sending {len(audio_data)} bytes...")
                        if not await self.streamer.send_audio_chunk(audio_data):
                            logger.warning("Failed to send chunk")
                            break
                    else:
                        logger.warning("❌ No audio captured this cycle")
                        
                    # Small gap between recordings
                    await asyncio.sleep(0.1)
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"❌ Loop error: {e}")
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info(f"🛑 Streaming stopped. Sent {self.streamer.chunks_sent} chunks")
        except Exception as e:
            logger.error(f"❌ Streaming loop error: {e}")
        finally:
            if recorder.is_recording:
                try:
                    voice_client.stop_recording()
                except:
                    pass

def main():
    Config.validate()
    
    # Try to load Opus codec before starting bot
    opus_loaded = load_opus()
    if not opus_loaded:
        logger.warning("⚠️ Opus codec not loaded - voice recording may not work properly")
        logger.info("💡 Bot will attempt to run without Opus (limited functionality)")
        logger.info("💡 For full voice support, install proper Opus library")
    else:
        logger.info("✅ Opus codec loaded successfully")
        
    bot = FinalVoiceBot()
    logger.info("🚀 Starting final voice bot...")
    logger.info("📝 Callback-free 2s chunks, 16kHz mono")
    
    if not opus_loaded:
        logger.warning("⚠️ Running without Opus - expect audio decoding issues")
        
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()