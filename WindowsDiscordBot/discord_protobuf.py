#!/usr/bin/env python3
"""
Discord bot that sends audio using Pipecat's Protobuf protocol
"""

import asyncio
import logging
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

class ProtobufDiscordBot:
    """Discord bot that sends audio using Protobuf protocol"""
    
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
        
    def setup_discord_events(self):
        """Setup Discord bot events and commands"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Discord bot logged in as {self.bot.user}")
            
        @self.bot.command(name='proto')
        async def test_protobuf(ctx):
            """Test voice with Protobuf protocol"""
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
                
                # Skip StartFrame - Pipecat handles this internally
                # Just start audio capture
                self.start_audio_capture()
                
                await ctx.send("🟢 **Protobuf Voice Test Started!**\n"
                              "Audio is being sent using Pipecat protocol.")
                
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
            logger.info("✅ WebSocket connected with Protobuf protocol")
            
            # No need to setup serializer with StartFrame - just use it directly
            
            # Start message handler
            self.loop = asyncio.get_event_loop()
            asyncio.create_task(self.websocket_handler())
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            raise
            
    # Removed send_start_frame - not needed for Protobuf protocol
            
    async def websocket_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                # Deserialize incoming frames
                frame = await self.serializer.deserialize(message)
                
                if frame:
                    if isinstance(frame, OutputAudioRawFrame):
                        logger.info(f"🔊 Received audio response: {len(frame.audio)} bytes")
                    else:
                        logger.info(f"📥 Received frame: {type(frame).__name__}")
                        
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
                    self.send_audio_frame(audio_data), 
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
            
    async def send_audio_frame(self, audio_bytes: bytes):
        """Send raw audio bytes directly (Pipecat will wrap into frame)"""
        try:
            if self.websocket:
                # Send raw audio bytes directly - Pipecat server expects this!
                await self.websocket.send(audio_bytes)
                
                self.chunks_sent += 1
                if self.chunks_sent % 20 == 0:  # Log every 2 seconds
                    logger.info(f"📤 Sent {self.chunks_sent} raw audio chunks ({len(audio_bytes)} bytes each)")
                    
        except Exception as e:
            logger.error(f"❌ Failed to send audio: {e}")
            
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
        logger.info("🚀 Starting Protobuf Discord bot...")
        self.bot.run(self.discord_token)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment")
        sys.exit(1)
        
    # Use localhost for Pipecat WebSocket server
    websocket_uri = "ws://localhost:8001"
    
    bot = ProtobufDiscordBot(discord_token, websocket_uri)
    bot.run()