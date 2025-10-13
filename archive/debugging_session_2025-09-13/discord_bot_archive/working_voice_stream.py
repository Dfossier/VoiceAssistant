#!/usr/bin/env python3
"""
Working voice streaming using periodic recording chunks
Since py-cord doesn't support true continuous streaming,
we'll use short recording sessions in a loop
"""

import asyncio
import discord
import logging
import websockets
import json
import base64
import time
from pathlib import Path
import sys
import io
import numpy as np
import librosa

sys.path.append(str(Path(__file__).parent))
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("VoiceStream")

# Suppress discord logs
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class ChunkedVoiceStreamer:
    """Stream voice in chunks using periodic recording"""
    
    def __init__(self, voice_client, websocket_url="ws://127.0.0.1:8001"):
        self.voice_client = voice_client
        self.websocket_url = websocket_url
        self.websocket = None
        self.is_streaming = False
        self.chunk_count = 0
        self.stream_task = None
        self.chunk_duration = 2.0  # Record 2 second chunks
        
    async def connect_websocket(self):
        """Connect to backend WebSocket"""
        try:
            logger.info(f"🔌 Connecting to {self.websocket_url}...")
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info("✅ Connected to backend")
            
            # Start listening for responses
            asyncio.create_task(self._listen_for_responses())
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False
            
    async def _listen_for_responses(self):
        """Listen for responses from backend"""
        try:
            while self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                logger.info(f"📨 Backend response: {data.get('type', 'unknown')}")
        except Exception as e:
            logger.debug(f"Response listener stopped: {e}")
            
    async def start_streaming(self):
        """Start chunked voice streaming"""
        if self.is_streaming:
            return False
            
        if not await self.connect_websocket():
            return False
            
        self.is_streaming = True
        self.chunk_count = 0
        
        # Start the streaming loop
        self.stream_task = asyncio.create_task(self._streaming_loop())
        
        logger.info("🎤 Chunked streaming started!")
        return True
        
    async def stop_streaming(self):
        """Stop streaming"""
        self.is_streaming = False
        
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
                
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        logger.info(f"🛑 Streaming stopped. Processed {self.chunk_count} chunks")
        
    async def _streaming_loop(self):
        """Main streaming loop - record chunks periodically"""
        try:
            while self.is_streaming and self.voice_client.is_connected():
                try:
                    # Record a chunk
                    audio_data = await self._record_chunk()
                    
                    if audio_data and len(audio_data) > 0:
                        # Send to backend
                        await self._send_audio_chunk(audio_data)
                        
                    # Small delay between chunks
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"❌ Chunk error: {e}")
                    await asyncio.sleep(1)  # Longer delay on error
                    
        except asyncio.CancelledError:
            logger.info("Streaming loop cancelled")
        except Exception as e:
            logger.error(f"❌ Streaming loop error: {e}", exc_info=True)
        finally:
            self.is_streaming = False
            
    async def _record_chunk(self):
        """Record a single audio chunk"""
        try:
            # Create a new sink for this chunk
            sink = discord.sinks.WaveSink()
            
            # Use a future to track completion
            done_future = asyncio.Future()
            
            def finished_callback(sink, error=None):
                if error:
                    logger.error(f"Recording error: {error}")
                if not done_future.done():
                    done_future.set_result(sink)
                    
            # Wrap in lambda to avoid coroutine error
            callback_wrapper = lambda *args: finished_callback(*args)
            
            # Start recording
            self.voice_client.start_recording(sink, callback_wrapper)
            
            # Record for chunk_duration seconds
            await asyncio.sleep(self.chunk_duration)
            
            # Stop recording
            self.voice_client.stop_recording()
            
            # Wait for callback (with timeout)
            try:
                sink = await asyncio.wait_for(done_future, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Recording callback timeout")
                sink = sink  # Use original sink
                
            # Extract audio data
            audio_data = bytearray()
            
            if hasattr(sink, 'audio_data') and sink.audio_data:
                for user_id, audio_obj in sink.audio_data.items():
                    if hasattr(audio_obj, 'file'):
                        audio_obj.file.seek(0)
                        user_audio = audio_obj.file.read()
                        if user_audio:
                            audio_data.extend(user_audio)
                            logger.debug(f"User {user_id}: {len(user_audio)} bytes")
                            
            return bytes(audio_data)
            
        except Exception as e:
            logger.error(f"❌ Record chunk error: {e}")
            return None
            
    async def _send_audio_chunk(self, audio_data):
        """Send audio chunk to backend"""
        if not self.websocket or not audio_data:
            return
            
        try:
            self.chunk_count += 1
            
            # Resample audio from 48kHz to 16kHz for Pipecat
            resampled_audio = await self._resample_audio(audio_data)
            
            if not resampled_audio:
                logger.warning("Resampling failed, skipping chunk")
                return
            
            # Create base64 encoded message
            audio_b64 = base64.b64encode(resampled_audio).decode('utf-8')
            
            message = {
                "type": "audio_input",
                "data": audio_b64,
                "format": "wav",  # WaveSink produces WAV format
                "sample_rate": 16000,  # Resampled to 16kHz
                "channels": 1,  # Converted to mono
                "chunk_id": self.chunk_count,
                "duration": self.chunk_duration,
                "size": len(resampled_audio),
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📡 Sent chunk #{self.chunk_count}: {len(audio_data)} → {len(resampled_audio)} bytes (48kHz → 16kHz)")
            
        except Exception as e:
            logger.error(f"❌ Send error: {e}")
            
    async def _resample_audio(self, audio_data):
        """Resample audio from 48kHz stereo to 16kHz mono"""
        try:
            # Parse WAV data to get raw audio
            import wave
            
            # Create BytesIO from audio data
            audio_io = io.BytesIO(audio_data)
            
            # Open as WAV
            with wave.open(audio_io, 'rb') as wav:
                frames = wav.readframes(wav.getnframes())
                sample_rate = wav.getframerate()
                channels = wav.getnchannels()
                
            # Convert bytes to numpy array
            audio_np = np.frombuffer(frames, dtype=np.int16)
            
            # Reshape for stereo if needed
            if channels == 2:
                audio_np = audio_np.reshape(-1, 2)
                # Convert to mono by averaging channels
                audio_np = audio_np.mean(axis=1).astype(np.int16)
                
            # Convert to float32 for librosa
            audio_float = audio_np.astype(np.float32) / 32768.0
            
            # Resample from 48kHz to 16kHz
            if sample_rate != 16000:
                audio_resampled = librosa.resample(
                    audio_float, 
                    orig_sr=sample_rate, 
                    target_sr=16000
                )
            else:
                audio_resampled = audio_float
                
            # Convert back to int16
            audio_int16 = (audio_resampled * 32768).astype(np.int16)
            
            # Create new WAV data
            output_io = io.BytesIO()
            with wave.open(output_io, 'wb') as wav_out:
                wav_out.setnchannels(1)  # Mono
                wav_out.setsampwidth(2)  # 16-bit
                wav_out.setframerate(16000)  # 16kHz
                wav_out.writeframes(audio_int16.tobytes())
                
            return output_io.getvalue()
            
        except Exception as e:
            logger.error(f"❌ Resampling error: {e}")
            return None

class WorkingVoiceBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.streamers = {}  # guild_id -> ChunkedVoiceStreamer
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("This bot uses chunked recording for reliable streaming")
        logger.info("Commands: !stream, !stop")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!stream':
            await self._start_streaming(message)
        elif content == '!stop':
            await self._stop_streaming(message)
            
    async def _start_streaming(self, message):
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        guild_id = message.guild.id
        
        # Stop existing streamer
        if guild_id in self.streamers:
            await self.streamers[guild_id].stop_streaming()
            
        try:
            channel = message.author.voice.channel
            
            # Connect to voice
            if message.guild.voice_client:
                voice_client = message.guild.voice_client
                if voice_client.channel != channel:
                    await voice_client.disconnect()
                    voice_client = await channel.connect()
            else:
                voice_client = await channel.connect()
                
            logger.info(f"✅ Connected to {channel.name}")
            
            # Create and start streamer
            streamer = ChunkedVoiceStreamer(voice_client)
            self.streamers[guild_id] = streamer
            
            if await streamer.start_streaming():
                embed = discord.Embed(
                    title="🎤 Voice Streaming Active!",
                    description=f"Streaming from **{channel.name}** to backend",
                    color=0x00ff00
                )
                embed.add_field(
                    name="How it works:",
                    value=f"• Recording {streamer.chunk_duration}s chunks\n"
                          f"• Sending to ws://127.0.0.1:8001\n"
                          f"• Continuous loop until stopped",
                    inline=False
                )
                embed.add_field(
                    name="To test:",
                    value="• **Speak normally** - chunks are sent automatically\n"
                          "• Check console for chunk uploads\n"
                          "• Use `!stop` when done",
                    inline=False
                )
                await message.reply(embed=embed)
            else:
                await message.reply("❌ Failed to start streaming")
                await voice_client.disconnect()
                
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_streaming(self, message):
        guild_id = message.guild.id
        
        try:
            # Stop streamer
            if guild_id in self.streamers:
                await self.streamers[guild_id].stop_streaming()
                del self.streamers[guild_id]
                
            # Disconnect voice
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                
            await message.reply("🛑 **Streaming stopped!**")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}")
            await message.reply(f"❌ Error: {str(e)}")

def main():
    Config.validate()
    bot = WorkingVoiceBot()
    logger.info("🚀 Starting working voice streaming bot...")
    logger.info("📝 Using chunked recording approach (2s chunks)")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()