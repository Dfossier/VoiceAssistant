#!/usr/bin/env python3
"""
Discord bot that manually constructs Protobuf messages for Pipecat
This version avoids Windows compatibility issues by manually creating frames
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

# Manual Protobuf frame construction to avoid Windows import issues
class FrameType:
    START_FRAME = "pipecat.frames.frames.StartFrame"
    INPUT_AUDIO_RAW_FRAME = "pipecat.frames.frames.InputAudioRawFrame"
    OUTPUT_AUDIO_RAW_FRAME = "pipecat.frames.frames.OutputAudioRawFrame"
    TEXT_FRAME = "pipecat.frames.frames.TextFrame"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class ManualProtobufBot:
    """Discord bot that manually constructs Protobuf frames without Pipecat imports"""
    
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
        self.start_frame_sent = False
        
    def setup_discord_events(self):
        """Setup Discord bot events and commands"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Discord bot logged in as {self.bot.user}")
            
        @self.bot.command(name='manual')
        async def test_manual_protobuf(ctx):
            """Test voice with manual Protobuf construction"""
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
                
                # Send StartFrame
                await self.send_start_frame()
                
                # Start audio capture
                self.start_audio_capture()
                
                await ctx.send("🟢 **Manual Protobuf Voice Test Started!**\n"
                              "Using manually constructed frames to avoid Windows issues.")
                
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
            logger.info("✅ WebSocket connected with manual Protobuf")
            
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
                try:
                    # Try to parse the message structure
                    if isinstance(message, bytes) and len(message) > 10:
                        # Check if it looks like audio data
                        if b'audio' in message[:50]:
                            logger.info(f"🔊 Received audio response: {len(message)} bytes")
                        else:
                            logger.info(f"📥 Received frame data: {len(message)} bytes")
                    else:
                        logger.info(f"📥 Received message: {len(message)} bytes")
                        
                except Exception as parse_error:
                    logger.info(f"📥 Could not parse message: {parse_error}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("📡 WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ WebSocket handler error: {e}")
            
    async def send_start_frame(self):
        """Send StartFrame using manual construction"""
        try:
            # Construct a simple StartFrame-like message
            # This is a simplified version that should be compatible
            start_data = {
                'frame_type': FrameType.START_FRAME,
                'audio_in_sample_rate': 16000,
                'audio_out_sample_rate': 16000,
                'audio_in_enabled': True,
                'audio_out_enabled': True,
                'allow_interruptions': True
            }
            
            # Convert to a simple binary format
            message = self.pack_frame_data(FrameType.START_FRAME, start_data)
            
            if message and self.websocket:
                await self.websocket.send(message)
                logger.info("📤 Sent manual StartFrame")
                self.start_frame_sent = True
                
        except Exception as e:
            logger.error(f"❌ Failed to send StartFrame: {e}")
            
    def pack_frame_data(self, frame_type: str, data: dict) -> bytes:
        """Pack frame data into a binary format"""
        try:
            # Simple binary packing format
            # [4 bytes: frame_type_len][frame_type][4 bytes: data_len][data_json]
            
            import json
            
            frame_type_bytes = frame_type.encode('utf-8')
            data_json = json.dumps(data).encode('utf-8')
            
            # Pack the message
            message = struct.pack('!I', len(frame_type_bytes)) + frame_type_bytes
            message += struct.pack('!I', len(data_json)) + data_json
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Failed to pack frame data: {e}")
            return b''
            
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
        """Send audio frame using manual construction"""
        try:
            if self.websocket and self.start_frame_sent:
                # Construct audio frame data
                audio_data = {
                    'frame_type': FrameType.INPUT_AUDIO_RAW_FRAME,
                    'audio': list(audio_bytes),  # Convert to list for JSON
                    'sample_rate': 16000,
                    'num_channels': 1
                }
                
                # Pack the frame
                message = self.pack_frame_data(FrameType.INPUT_AUDIO_RAW_FRAME, audio_data)
                
                if message:
                    await self.websocket.send(message)
                    
                    self.chunks_sent += 1
                    if self.chunks_sent % 20 == 0:  # Log every 2 seconds
                        logger.info(f"📤 Sent {self.chunks_sent} manual audio frames")
                        
        except Exception as e:
            logger.error(f"❌ Failed to send audio frame: {e}")
            
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
        logger.info("🚀 Starting manual Protobuf Discord bot...")
        self.bot.run(self.discord_token)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment")
        sys.exit(1)
        
    # Use the confirmed working WSL2 IP with main backend
    websocket_uri = "ws://172.20.104.13:8001"
    
    bot = ManualProtobufBot(discord_token, websocket_uri)
    bot.run()