#!/usr/bin/env python3
"""
Discord bot using Pipecat's WebSocket client transport for proper frame handling
This should work properly with the Pipecat server
"""

import asyncio
import logging
import threading
from typing import Optional
import sounddevice as sd
import numpy as np
import io
import sys

import discord
from discord.ext import commands

# Pipecat imports
from pipecat.transports.websocket.client import WebsocketClientTransport
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.audio.utils import resample_audio

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class AudioCaptureProcessor(FrameProcessor):
    """Processor that captures incoming audio frames and sends them to Pipecat"""
    
    def __init__(self, transport_output):
        super().__init__()
        self.transport_output = transport_output
        
    async def process_frame(self, frame, direction):
        """Forward all frames - no processing needed"""
        await self.push_frame(frame, direction)
        
        # Log received audio for debugging
        if isinstance(frame, OutputAudioRawFrame):
            logger.info(f"🔊 Received TTS audio: {len(frame.audio)} bytes at {frame.sample_rate}Hz")

class PipecatDiscordBot:
    """Discord bot that uses Pipecat's WebSocket client transport"""
    
    def __init__(self, discord_token: str, pipecat_uri: str):
        self.discord_token = discord_token
        self.pipecat_uri = pipecat_uri
        
        # Discord setup
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_discord_events()
        
        # Pipecat setup
        self.transport = None
        self.pipeline = None
        self.pipeline_task = None
        self.runner = None
        self.loop = None
        
        # Audio capture
        self.audio_stream = None
        self.is_capturing = False
        self.chunks_sent = 0
        
    def setup_discord_events(self):
        """Setup Discord bot events and commands"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Discord bot logged in as {self.bot.user}")
            
        @self.bot.command(name='pipecat')
        async def start_pipecat(ctx):
            """Start Pipecat-based voice conversation"""
            if ctx.author.voice is None:
                await ctx.send("❌ You need to be in a voice channel!")
                return
                
            voice_channel = ctx.author.voice.channel
            
            try:
                # Connect to voice channel
                voice_client = await voice_channel.connect()
                logger.info(f"🎤 Connected to voice channel: {voice_channel.name}")
                
                # Start Pipecat pipeline
                await self.start_pipecat_pipeline()
                
                # Start audio capture
                await self.start_audio_capture()
                
                await ctx.send("🟢 **Pipecat Voice Assistant Started!**\n"
                              "Speak naturally - I'm listening with proper Pipecat protocol!")
                
            except Exception as e:
                logger.error(f"❌ Failed to start voice session: {e}")
                await ctx.send(f"❌ Failed to start: {e}")
                
        @self.bot.command(name='stopcat')
        async def stop_pipecat(ctx):
            """Stop Pipecat voice conversation"""
            await self.stop_audio_capture()
            await self.stop_pipecat_pipeline()
            
            # Disconnect from voice
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                
            await ctx.send("⏹️ **Pipecat Voice Assistant Stopped**")
                
    async def start_pipecat_pipeline(self):
        """Start the Pipecat WebSocket client pipeline"""
        try:
            logger.info("🚀 Starting Pipecat client pipeline...")
            
            # Create WebSocket transport
            self.transport = WebsocketClientTransport(self.pipecat_uri)
            
            # Create audio capture processor
            audio_processor = AudioCaptureProcessor(self.transport.output())
            
            # Create pipeline: transport.input() → processor → transport.output()
            self.pipeline = Pipeline([
                self.transport.input(),   # Receive from server
                audio_processor,          # Process frames
                self.transport.output()   # Send to server
            ])
            
            # Create pipeline task
            self.pipeline_task = PipelineTask(
                self.pipeline,
                params=PipelineParams(
                    allow_interruptions=True,
                    enable_metrics=False,
                    enable_usage_metrics=False
                )
            )
            
            # Create runner
            self.runner = PipelineRunner()
            
            # Start pipeline in background
            self.loop = asyncio.get_event_loop()
            asyncio.create_task(self.runner.run(self.pipeline_task))
            
            logger.info("✅ Pipecat client pipeline started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Pipecat pipeline: {e}")
            raise
            
    async def stop_pipecat_pipeline(self):
        """Stop the Pipecat pipeline"""
        try:
            if self.pipeline_task:
                await self.pipeline_task.stop()
            if self.runner:
                await self.runner.stop()
                
            self.transport = None
            self.pipeline = None
            self.pipeline_task = None
            self.runner = None
            
            logger.info("✅ Pipecat pipeline stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping pipeline: {e}")
            
    async def start_audio_capture(self):
        """Start capturing audio from microphone"""
        if self.is_capturing:
            logger.warning("⚠️ Audio capture already running")
            return
            
        logger.info("🎤 Starting audio capture...")
        self.is_capturing = True
        self.chunks_sent = 0
        
        def audio_callback(indata, frames, time, status):
            """Audio callback - runs in separate thread"""
            if status:
                logger.warning(f"⚠️ Audio status: {status}")
                
            if not self.is_capturing:
                return
                
            # Convert to 16-bit PCM
            audio_data = (indata[:, 0] * 32767).astype(np.int16)
            
            # Send to Pipecat via asyncio
            if self.loop and not self.loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._send_audio_frame(audio_data.tobytes()), 
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
            
    async def stop_audio_capture(self):
        """Stop audio capture"""
        self.is_capturing = False
        
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            
        logger.info("⏹️ Audio capture stopped")
        
    async def _send_audio_frame(self, audio_bytes: bytes):
        """Send audio frame to Pipecat transport"""
        try:
            if not self.transport or not self.is_capturing:
                return
                
            # Create Pipecat InputAudioRawFrame
            audio_frame = InputAudioRawFrame(
                audio=audio_bytes,
                sample_rate=16000,
                num_channels=1
            )
            
            # Send via transport output
            transport_output = self.transport.output()
            if transport_output and hasattr(transport_output, 'push_frame'):
                await transport_output.push_frame(audio_frame)
                self.chunks_sent += 1
                
                if self.chunks_sent % 10 == 0:  # Log every 10 chunks (1 second)
                    logger.info(f"📡 Sent {self.chunks_sent} audio frames to Pipecat")
            else:
                logger.error("❌ Transport output not available for sending frames")
                
        except Exception as e:
            logger.error(f"❌ Failed to send audio frame: {e}")
            
    def run(self):
        """Run the Discord bot"""
        logger.info("🚀 Starting Discord bot with Pipecat integration...")
        self.bot.run(self.discord_token)

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment")
        sys.exit(1)
        
    pipecat_uri = "ws://172.20.104.13:8001"
    
    bot = PipecatDiscordBot(discord_token, pipecat_uri)
    bot.run()