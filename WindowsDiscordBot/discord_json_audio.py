#!/usr/bin/env python3
"""
Discord bot that sends JSON-formatted audio to backend
This matches our proven SimpleAudioWebSocketHandler format
"""

import os
import sys
import json
import base64
import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone
from queue import Queue
import threading

# Third-party imports
import discord
from discord.ext import commands
from discord import VoiceChannel, VoiceClient
import sounddevice as sd
import numpy as np
from dotenv import load_dotenv
import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment from parent assistant directory
load_dotenv("../.env")

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://localhost:8002")  # Use SimpleAudioWebSocketHandler with Faster-Whisper enabled

if not DISCORD_TOKEN:
    logger.error("❌ DISCORD_TOKEN not found in .env file!")
    sys.exit(1)

class VoiceAssistant(commands.Bot):
    """Discord bot that captures audio and sends as JSON to backend"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.websocket = None
        self.audio_stream = None
        self.is_recording = False
        self.ws_task = None
        self.audio_queue = Queue()
        self.audio_task = None
        
    async def on_ready(self):
        """Called when bot is logged in"""
        logger.info(f'🤖 Discord bot logged in as {self.user}')
        
    async def connect_websocket(self):
        """Connect to backend WebSocket with keepalive"""
        try:
            # Improved keepalive settings for stability
            self.websocket = await websockets.connect(
                BACKEND_WS_URL,
                ping_interval=20,    # Send ping every 20 seconds (more frequent)
                ping_timeout=15,     # Wait 15 seconds for pong (more lenient)
                close_timeout=5,     # Faster close timeout
                max_queue=None,      # Remove queue size limits
                compression=None     # Disable compression for better performance
            )
            logger.info(f"✅ WebSocket connected to {BACKEND_WS_URL}")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await self.websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent JSON start message")
            
            # Start receiving messages from backend
            self.ws_task = asyncio.create_task(self.receive_messages())
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.websocket = None
            
    async def receive_messages(self):
        """Receive messages from backend"""
        try:
            while self.websocket:
                message = await self.websocket.recv()
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "transcription":
                    logger.info(f"📝 Transcription: {data.get('text')}")
                elif msg_type == "text_output":
                    logger.info(f"💬 Assistant: {data.get('text')}")
                elif msg_type == "audio_output":
                    audio_data = data.get('data', '')
                    logger.info(f"🔊 Received audio output: {len(audio_data)} chars")
                    # Decode and play audio through Discord
                    await self.play_audio_response(audio_data, data.get('format', 'mp3'))
                else:
                    logger.debug(f"📨 Received: {msg_type}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            
    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk as JSON to backend"""
        if not self.websocket:
            return
            
        try:
            message = {
                "type": "audio_input",
                "data": base64.b64encode(audio_data).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await self.websocket.send(json.dumps(message))
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed, attempting reconnection...")
            self.websocket = None
            # Try to reconnect
            await self.connect_websocket()
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")
            
    async def process_audio_queue(self):
        """Process audio chunks from the queue"""
        while self.is_recording:
            try:
                # Check for audio in queue (non-blocking)
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()
                    await self.send_audio_chunk(audio_data)
                else:
                    # Small delay to prevent busy waiting
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error processing audio queue: {e}")
            
    def audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice audio stream"""
        if status:
            logger.warning(f"Audio callback status: {status}")
            
        if self.is_recording:
            # Convert float32 audio to int16 PCM
            audio_int16 = (indata * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # Put audio in queue for async processing
            self.audio_queue.put(audio_bytes)
            
    async def play_audio_response(self, audio_b64: str, audio_format: str = 'mp3'):
        """Play TTS audio response through Discord voice channel"""
        try:
            if not audio_b64:
                return
                
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_b64)
            logger.info(f"🔊 Playing {len(audio_bytes)} bytes of {audio_format} audio")
            
            # Save to temporary file for Discord playback
            import tempfile
            import os
            
            # Choose extension based on format
            ext = '.wav' if audio_format == 'wav' else '.mp3'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            # Get voice client and play audio
            voice_clients = self.voice_clients
            if voice_clients:
                voice_client = voice_clients[0]  # Get first voice client
                
                # Create audio source with improved FFmpeg options
                if audio_format == 'wav':
                    # Log WAV file info for debugging
                    logger.info(f"🎵 Playing WAV file: {os.path.getsize(temp_path)} bytes")
                    
                    audio_source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(
                            temp_path, 
                            before_options='-f wav',
                            # Force proper sample rate conversion from source to Discord's 48kHz
                            options='-vn -ar 48000 -ac 2 -acodec pcm_s16le -f s16le -loglevel warning'
                        ),
                        volume=1.2  # Increase volume to ensure it's audible
                    )
                else:
                    # For MP3, use more robust options
                    audio_source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(
                            temp_path, 
                            before_options='-f mp3 -re',  # Add -re for real-time playback
                            options='-vn -ar 48000 -ac 2 -acodec pcm_s16le -f s16le -loglevel error -bufsize 64k'
                        ),
                        volume=0.8  # Slightly lower volume to prevent clipping
                    )
                
                # Play the audio
                if not voice_client.is_playing():
                    voice_client.play(audio_source)
                    logger.info("✅ Started playing TTS audio in Discord")
                    
                    # Wait for playback to finish
                    while voice_client.is_playing():
                        await asyncio.sleep(0.1)
                    
                    logger.info("🔇 Finished playing TTS audio")
                else:
                    logger.warning("⚠️ Voice client already playing audio, skipping")
            else:
                logger.warning("⚠️ No voice client available for audio playback")
            
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"❌ Error playing audio: {e}")

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = VoiceAssistant(command_prefix='!', intents=intents)

@bot.command(name='json')
async def json_voice(ctx):
    """Start JSON-based voice capture"""
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel!")
        return
        
    # Connect to voice channel with timeout handling
    voice_channel = ctx.author.voice.channel
    await ctx.send("🔄 Connecting to voice channel...")
    
    try:
        # Try connecting with increased timeout
        voice_client = await asyncio.wait_for(
            voice_channel.connect(), 
            timeout=30.0  # 30 second timeout instead of default 10
        )
        await ctx.send(f"🎤 Connected to {voice_channel.name}")
        logger.info(f"✅ Connected to voice channel: {voice_channel.name}")
        
    except asyncio.TimeoutError:
        await ctx.send("❌ Voice connection timed out. Trying alternative method...")
        logger.error("Voice connection timeout - attempting reconnection")
        
        # Try disconnecting any existing connections first
        for vc in bot.voice_clients:
            try:
                await vc.disconnect()
            except:
                pass
        
        # Wait a moment then try again
        await asyncio.sleep(2)
        try:
            voice_client = await asyncio.wait_for(
                voice_channel.connect(),
                timeout=15.0
            )
            await ctx.send(f"🎤 Connected to {voice_channel.name} (retry successful)")
            logger.info(f"✅ Connected to voice channel on retry: {voice_channel.name}")
        except (asyncio.TimeoutError, Exception) as e:
            await ctx.send(f"❌ Failed to connect to voice channel: {str(e)}")
            logger.error(f"Failed to connect to voice channel: {e}")
            return
            
    except Exception as e:
        await ctx.send(f"❌ Voice connection error: {str(e)}")
        logger.error(f"Voice connection error: {e}")
        return
    
    # Connect WebSocket
    await bot.connect_websocket()
    
    if not bot.websocket:
        await ctx.send("❌ Failed to connect to backend WebSocket")
        await voice_client.disconnect()
        return
        
    # Start audio capture
    bot.is_recording = True
    bot.audio_stream = sd.InputStream(
        callback=bot.audio_callback,
        channels=1,
        samplerate=16000,
        dtype='float32',
        blocksize=8000  # 500ms chunks for better transcription
    )
    bot.audio_stream.start()
    
    # Start audio queue processing task
    bot.audio_task = asyncio.create_task(bot.process_audio_queue())
    
    await ctx.send("🟢 **Recording audio** - Speak now! Use `!stop` to end.")
    logger.info("🎤 Started audio recording with JSON protocol")
    
    # Keep track of frames sent
    frame_count = 0
    while bot.is_recording:
        await asyncio.sleep(2)
        frame_count += 20  # Approximate
        if frame_count % 20 == 0:
            logger.info(f"📤 Sent approximately {frame_count} JSON audio frames")

@bot.command(name='debug')
async def debug_voice(ctx):
    """Debug voice connection status"""
    embed = discord.Embed(title="🔧 Voice Debug Info", color=0x00ff00)
    
    # Check if user is in voice
    if ctx.author.voice:
        embed.add_field(name="Your Voice Channel", 
                       value=f"✅ {ctx.author.voice.channel.name}", 
                       inline=False)
    else:
        embed.add_field(name="Your Voice Channel", 
                       value="❌ Not in voice channel", 
                       inline=False)
    
    # Check bot voice connections
    if bot.voice_clients:
        vc_info = []
        for i, vc in enumerate(bot.voice_clients):
            status = "🟢 Connected" if vc.is_connected() else "🔴 Disconnected"
            vc_info.append(f"{i+1}. {vc.channel.name} - {status}")
        embed.add_field(name="Bot Voice Connections", 
                       value="\n".join(vc_info), 
                       inline=False)
    else:
        embed.add_field(name="Bot Voice Connections", 
                       value="❌ No voice connections", 
                       inline=False)
    
    # Check WebSocket status
    ws_status = "🟢 Connected" if bot.websocket and not bot.websocket.closed else "🔴 Disconnected"
    embed.add_field(name="WebSocket Status", 
                   value=ws_status, 
                   inline=False)
    
    # Check recording status
    recording_status = "🎤 Recording" if bot.is_recording else "⏸️ Not recording"
    embed.add_field(name="Recording Status", 
                   value=recording_status, 
                   inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='cleanup')
async def cleanup_connections(ctx):
    """Clean up all voice connections and reset state"""
    await ctx.send("🧹 Cleaning up all connections...")
    
    # Stop recording
    bot.is_recording = False
    
    # Stop audio task
    if bot.audio_task:
        bot.audio_task.cancel()
        try:
            await bot.audio_task
        except asyncio.CancelledError:
            pass
        bot.audio_task = None
    
    # Clear audio queue
    while not bot.audio_queue.empty():
        bot.audio_queue.get()
    
    # Stop audio stream
    if bot.audio_stream:
        try:
            bot.audio_stream.stop()
            bot.audio_stream.close()
        except:
            pass
        bot.audio_stream = None
    
    # Close WebSocket
    if bot.websocket:
        try:
            await bot.websocket.close()
        except:
            pass
        bot.websocket = None
    
    # Cancel WebSocket task
    if bot.ws_task:
        bot.ws_task.cancel()
        bot.ws_task = None
    
    # Disconnect all voice clients
    for vc in bot.voice_clients[:]:  # Copy list to avoid modification during iteration
        try:
            await vc.disconnect()
        except:
            pass
    
    await ctx.send("✅ All connections cleaned up. Ready for new connections!")

@bot.command(name='stop')
async def stop_voice(ctx):
    """Stop voice capture"""
    bot.is_recording = False
    
    # Stop audio task
    if bot.audio_task:
        bot.audio_task.cancel()
        try:
            await bot.audio_task
        except asyncio.CancelledError:
            pass
        bot.audio_task = None
    
    # Clear audio queue
    while not bot.audio_queue.empty():
        bot.audio_queue.get()
    
    # Stop audio stream
    if bot.audio_stream:
        bot.audio_stream.stop()
        bot.audio_stream.close()
        bot.audio_stream = None
        
    if bot.websocket:
        try:
            # Send end message
            end_msg = {
                "type": "end",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await bot.websocket.send(json.dumps(end_msg))
            await bot.websocket.close()
        except:
            pass
        bot.websocket = None
        
    # Cancel receive task
    if bot.ws_task:
        bot.ws_task.cancel()
        bot.ws_task = None
        
    # Disconnect from voice
    for vc in bot.voice_clients:
        await vc.disconnect()
        
    await ctx.send("🔴 **Stopped recording** - Disconnected")
    logger.info("Stopped audio recording and disconnected")

# Run the bot
if __name__ == "__main__":
    logger.info("🚀 Starting JSON-based Discord bot...")
    bot.run(DISCORD_TOKEN)