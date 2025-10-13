#!/usr/bin/env python3
"""
Pipecat-ready Discord bot with robust chunked streaming
Sends properly formatted audio chunks to Pipecat backend
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

sys.path.append(str(Path(__file__).parent))
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("PipecatBot")

# Suppress discord warnings
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class PipecatWebSocketClient:
    """WebSocket client for Pipecat backend communication"""
    
    def __init__(self, url="ws://127.0.0.1:8001"):
        self.url = url
        self.websocket = None
        self.is_connected = False
        
    async def connect(self):
        """Connect to Pipecat backend"""
        try:
            logger.info(f"🔌 Connecting to Pipecat at {self.url}...")
            self.websocket = await websockets.connect(self.url)
            self.is_connected = True
            logger.info("✅ Connected to Pipecat backend")
            
            # Start response listener
            asyncio.create_task(self._listen_for_responses())
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            self.is_connected = False
            return False
            
    async def disconnect(self):
        """Disconnect from backend"""
        self.is_connected = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
    async def send_audio_chunk(self, audio_data, sample_rate=16000):
        """Send audio chunk to Pipecat"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            # Create Pipecat-compatible message
            message = {
                "type": "audio",
                "data": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": sample_rate,
                "format": "pcm16",  # 16-bit PCM
                "channels": 1,
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            self.is_connected = False
            return False
            
    async def _listen_for_responses(self):
        """Listen for Pipecat responses"""
        try:
            while self.is_connected and self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                msg_type = data.get("type", "unknown")
                
                if msg_type == "transcript":
                    logger.info(f"📝 Transcript: {data.get('text', '')}")
                elif msg_type == "response":
                    logger.info(f"🤖 AI: {data.get('text', '')[:100]}...")
                elif msg_type == "audio_output":
                    logger.info(f"🔊 Received audio response ({len(data.get('data', ''))} bytes)")
                else:
                    logger.debug(f"📨 {msg_type}: {data}")
                    
        except Exception as e:
            logger.debug(f"Response listener stopped: {e}")

class AudioChunkRecorder:
    """Handles chunked audio recording from Discord"""
    
    def __init__(self, voice_client, chunk_duration=1.0):
        self.voice_client = voice_client
        self.chunk_duration = chunk_duration
        self.is_recording = False
        self.recordings_completed = 0
        
    async def record_chunk(self):
        """Record a single audio chunk"""
        if self.is_recording:
            logger.warning("Already recording!")
            return None
            
        self.is_recording = True
        
        try:
            # Create sink
            sink = discord.sinks.WaveSink()
            
            # Simple completion tracking
            recording_done = asyncio.Event()
            
            def callback(sink, error=None):
                # Simple non-async callback
                if error:
                    logger.debug(f"Recording callback error: {error}")
                recording_done.set()
                
            # Start recording
            self.voice_client.start_recording(sink, callback)
            
            # Record for specified duration
            await asyncio.sleep(self.chunk_duration)
            
            # Stop recording
            self.voice_client.stop_recording()
            
            # Wait for completion (max 0.5s)
            try:
                await asyncio.wait_for(recording_done.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                logger.debug("Recording callback timeout (normal)")
            
            # Extract audio data
            audio_data = self._extract_audio_from_sink(sink)
            
            self.recordings_completed += 1
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

class PipecatDiscordBot(discord.Client):
    """Discord bot with Pipecat integration"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.pipecat_client = PipecatWebSocketClient()
        self.stream_tasks = {}  # guild_id -> task
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("🎤 Pipecat-ready voice streaming bot")
        logger.info("Commands: !voice, !leave")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!voice':
            await self._start_voice_stream(message)
        elif content == '!leave':
            await self._stop_voice_stream(message)
            
    async def _start_voice_stream(self, message):
        """Start voice streaming"""
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        guild_id = message.guild.id
        
        # Stop existing stream
        if guild_id in self.stream_tasks:
            self.stream_tasks[guild_id].cancel()
            
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
            
            # Connect to Pipecat
            if not self.pipecat_client.is_connected:
                if not await self.pipecat_client.connect():
                    await message.reply("❌ Failed to connect to Pipecat backend")
                    return
                    
            # Start streaming task
            task = asyncio.create_task(self._streaming_loop(vc, guild_id))
            self.stream_tasks[guild_id] = task
            
            embed = discord.Embed(
                title="🎙️ Voice Streaming Active",
                description=f"Streaming from **{channel.name}** to Pipecat",
                color=0x00ff00
            )
            embed.add_field(
                name="Features",
                value="• 1-second audio chunks\n• 16kHz mono PCM\n• Real-time processing\n• Voice Activity Detection",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="🟢 **Speak naturally** - I'm listening!",
                inline=False
            )
            
            await message.reply(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_voice_stream(self, message):
        """Stop voice streaming"""
        guild_id = message.guild.id
        
        try:
            # Cancel streaming task
            if guild_id in self.stream_tasks:
                self.stream_tasks[guild_id].cancel()
                del self.stream_tasks[guild_id]
                
            # Disconnect voice
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                
            await message.reply("👋 **Left voice channel!**")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}")
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _streaming_loop(self, voice_client, guild_id):
        """Main streaming loop"""
        recorder = AudioChunkRecorder(voice_client, chunk_duration=1.0)
        chunks_sent = 0
        
        try:
            logger.info("🎤 Starting streaming loop...")
            
            while voice_client.is_connected():
                try:
                    # Record chunk
                    audio_data = await recorder.record_chunk()
                    
                    if audio_data and len(audio_data) > 100:  # Minimum size check
                        # Send to Pipecat
                        if await self.pipecat_client.send_audio_chunk(audio_data):
                            chunks_sent += 1
                            logger.info(f"📡 Sent chunk #{chunks_sent}: {len(audio_data)} bytes")
                        else:
                            logger.warning("Failed to send chunk")
                            
                    await asyncio.sleep(0.1)  # Small gap between recordings
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"❌ Loop error: {e}")
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            logger.info(f"🛑 Streaming stopped. Sent {chunks_sent} chunks")
        finally:
            # Ensure we're not recording
            if recorder.is_recording:
                voice_client.stop_recording()

def main():
    Config.validate()
    bot = PipecatDiscordBot()
    logger.info("🚀 Starting Pipecat-ready Discord bot...")
    logger.info("📝 1-second chunks, 16kHz mono PCM")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()