#!/usr/bin/env python3
"""
Simple Discord bot that directly uses WebSocket for audio streaming
"""

import asyncio
import logging
import json
import base64
import struct
from typing import Optional
import sounddevice as sd
import numpy as np
import sys

import discord
from discord.ext import commands
import websockets

# Import Pipecat's protobuf definitions
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame
from pipecat.serializers.protobuf import ProtobufFrameSerializer

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class SimpleDiscordBot:
    """Simple Discord bot with direct WebSocket audio streaming"""
    
    def __init__(self, discord_token: str, websocket_uri: str):
        self.discord_token = discord_token
        self.websocket_uri = websocket_uri
        
        # Discord setup
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_discord_events()
        
        # Audio and WebSocket
        self.websocket = None
        self.audio_stream = None
        self.is_capturing = False
        self.chunks_sent = 0
        self.loop = None
        
        # Pipecat serializer
        self.serializer = ProtobufFrameSerializer()
        self.start_frame_sent = False
        
    def setup_discord_events(self):
        """Setup Discord bot events and commands"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Discord bot logged in as {self.bot.user}")
            
        @self.bot.command(name='test')
        async def test_voice(ctx):
            """Test voice with direct WebSocket"""
            if ctx.author.voice is None:
                await ctx.send("❌ You need to be in a voice channel!")
                return
                
            voice_channel = ctx.author.voice.channel
            
            try:
                # Connect to voice channel
                voice_client = await voice_channel.connect()
                logger.info(f"🎤 Connected to voice channel: {voice_channel.name}")
                
                # Connect to WebSocket
                await self.connect_websocket()
                
                # Start audio capture
                self.start_audio_capture()
                
                await ctx.send("🟢 **Simple Voice Test Started!**\n"
                              "Audio is being sent to the backend via WebSocket.")
                
            except Exception as e:
                logger.error(f"❌ Failed to start: {e}")
                import traceback
                traceback.print_exc()
                await ctx.send(f"❌ Failed to start: {e}")
                
        @self.bot.command(name='stop')
        async def stop_voice(ctx):
            """Stop voice test"""
            await self.stop_everything()
            
            # Disconnect from voice
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                
            await ctx.send("⏹️ **Voice Test Stopped**")
            
    async def connect_websocket(self):
        """Connect to the WebSocket server"""
        try:
            logger.info(f"🔌 Connecting to WebSocket: {self.websocket_uri}")
            self.websocket = await websockets.connect(self.websocket_uri)
            logger.info("✅ WebSocket connected")
            
            # Start message handler
            self.loop = asyncio.get_event_loop()
            asyncio.create_task(self.websocket_handler())
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            raise
            
    async def websocket_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                # Try to deserialize Protobuf frames
                try:
                    frame = await self.serializer.deserialize(message)
                    if frame:
                        if isinstance(frame, OutputAudioRawFrame):
                            logger.info(f"🔊 Received TTS audio: {len(frame.audio)} bytes")
                        else:
                            logger.info(f"📥 Received frame: {type(frame).__name__}")
                    else:
                        logger.info(f"📥 Received non-frame data: {len(message)} bytes")
                except Exception as deserialize_error:
                    logger.info(f"📥 Could not deserialize: {deserialize_error}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("📡 WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ WebSocket handler error: {e}")
            
    def start_audio_capture(self):
        """Start capturing audio from microphone"""
        if self.audio_stream:
            return
            
        logger.info("🎤 Starting audio capture...")
        self.is_capturing = True
        self.chunks_sent = 0
        
        def audio_callback(indata, frames, time, status):
            """Audio callback - runs in separate thread"""
            if status:
                logger.warning(f"⚠️ Audio status: {status}")
                
            if not self.is_capturing or not self.websocket:
                return
                
            # Convert to 16-bit PCM
            audio_data = (indata[:, 0] * 32767).astype(np.int16).tobytes()
            
            # Send via WebSocket using asyncio
            if self.loop and not self.loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.send_audio_data(audio_data), 
                    self.loop
                )
        
        try:
            # Start audio stream
            self.audio_stream = sd.InputStream(
                callback=audio_callback,
                channels=1,
                samplerate=16000,
                dtype='float32',
                blocksize=1600  # 100ms at 16kHz
            )
            self.audio_stream.start()
            logger.info("✅ Audio capture started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start audio capture: {e}")
            self.is_capturing = False
            
    async def send_audio_data(self, audio_bytes: bytes):
        """Send audio data via WebSocket using Protobuf protocol"""
        try:
            if self.websocket:
                # Send StartFrame first
                if not self.start_frame_sent:
                    await self.send_start_frame()
                    
                # Create InputAudioRawFrame
                audio_frame = InputAudioRawFrame(
                    audio=audio_bytes,
                    sample_rate=16000,
                    num_channels=1
                )
                
                # Serialize to Protobuf
                serialized = await self.serializer.serialize(audio_frame)
                
                if serialized:
                    await self.websocket.send(serialized)
                    
                    self.chunks_sent += 1
                    if self.chunks_sent % 20 == 0:  # Log every 2 seconds
                        logger.info(f"📤 Sent {self.chunks_sent} Protobuf audio frames")
                    
        except Exception as e:
            logger.error(f"❌ Failed to send audio: {e}")
            
    async def send_start_frame(self):
        """Send StartFrame to initialize the pipeline"""
        try:
            start_frame = StartFrame(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
                audio_in_enabled=True,
                audio_out_enabled=True
            )
            
            # Setup serializer
            await self.serializer.setup(start_frame)
            
            # Serialize and send
            serialized = await self.serializer.serialize(start_frame)
            if serialized:
                await self.websocket.send(serialized)
                logger.info("📤 Sent StartFrame")
                self.start_frame_sent = True
                
        except Exception as e:
            logger.error(f"❌ Failed to send StartFrame: {e}")
            
    async def stop_everything(self):
        """Stop audio capture and close WebSocket"""
        self.is_capturing = False
        
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            logger.info("⏹️ Audio capture stopped")
            
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("📡 WebSocket closed")
            
    def run(self):
        """Run the Discord bot"""
        logger.info("🚀 Starting simple Discord bot...")
        self.bot.run(self.discord_token)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment")
        sys.exit(1)
        
    # Use the confirmed working WSL2 IP
    websocket_uri = "ws://172.20.104.13:8001"
    
    bot = SimpleDiscordBot(discord_token, websocket_uri)
    bot.run()