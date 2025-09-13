#!/usr/bin/env python3
"""
Discord bot that properly integrates with Pipecat's WebSocket client transport
This version uses the full Pipecat pipeline architecture
"""

import asyncio
import logging
import threading
import time
from typing import Optional
import sounddevice as sd
import numpy as np
import sys

import discord
from discord.ext import commands

# Pipecat imports
from pipecat.transports.websocket.client import WebsocketClientTransport
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, EndFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.frame_processor import FrameProcessor
# from pipecat.audio.vad.silero import SileroVADAnalyzer
# from pipecat.audio.vad.vad_analyzer import VADParams

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class AudioInputProcessor(FrameProcessor):
    """Processor that receives audio from microphone and injects it into the pipeline"""
    
    def __init__(self):
        super().__init__()
        self.audio_buffer = asyncio.Queue()
        self.is_capturing = False
        self.frames_sent = 0
        
    async def process_frame(self, frame, direction):
        """Process frames from the pipeline"""
        
        if isinstance(frame, StartFrame):
            logger.info("🚀 Pipeline started - ready for audio input")
            
        elif isinstance(frame, OutputAudioRawFrame):
            logger.info(f"🔊 Received TTS audio: {len(frame.audio)} bytes")
            
        elif isinstance(frame, TextFrame):
            logger.info(f"💬 Received text: '{frame.text}'")
            
        # Forward all frames
        await self.push_frame(frame, direction)
        
    async def send_audio_chunk(self, audio_bytes: bytes):
        """Send audio chunk to the pipeline"""
        if not self.is_capturing:
            return
            
        audio_frame = InputAudioRawFrame(
            audio=audio_bytes,
            sample_rate=16000,
            num_channels=1
        )
        
        self.frames_sent += 1
        if self.frames_sent % 20 == 0:  # Log every 20 frames (2 seconds)
            logger.info(f"📤 Sent {self.frames_sent} audio frames to pipeline")
            
        await self.push_frame(audio_frame)
        
    def start_capture(self):
        """Start audio capture"""
        self.is_capturing = True
        self.frames_sent = 0
        logger.info("🎤 Audio capture started")
        
    def stop_capture(self):
        """Stop audio capture"""
        self.is_capturing = False
        logger.info("⏹️ Audio capture stopped")

class PipecatDiscordBot:
    """Discord bot with proper Pipecat integration"""
    
    def __init__(self, discord_token: str, pipecat_uri: str):
        self.discord_token = discord_token
        self.pipecat_uri = pipecat_uri
        
        # Discord setup
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_discord_events()
        
        # Pipecat pipeline components
        self.transport = None
        self.pipeline = None
        self.pipeline_task = None
        self.runner = None
        self.audio_processor = None
        
        # Audio capture
        self.audio_stream = None
        self.loop = None
        
    def setup_discord_events(self):
        """Setup Discord bot events and commands"""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"🤖 Discord bot logged in as {self.bot.user}")
            
        @self.bot.command(name='voice')
        async def start_voice(ctx):
            """Start voice conversation with Pipecat"""
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
                self.start_audio_capture()
                
                await ctx.send("🟢 **Pipecat Voice Assistant Started!**\n"
                              "Speak naturally - using proper Protobuf protocol!")
                
            except Exception as e:
                logger.error(f"❌ Failed to start voice session: {e}")
                await ctx.send(f"❌ Failed to start: {e}")
                
        @self.bot.command(name='stop')
        async def stop_voice(ctx):
            """Stop voice conversation"""
            self.stop_audio_capture()
            await self.stop_pipecat_pipeline()
            
            # Disconnect from voice
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                
            await ctx.send("⏹️ **Voice Assistant Stopped**")
                
    async def start_pipecat_pipeline(self):
        """Start the complete Pipecat pipeline"""
        try:
            logger.info("🚀 Starting Pipecat client pipeline...")
            
            # Create transport
            self.transport = WebsocketClientTransport(self.pipecat_uri)
            
            # Skip VAD for now to simplify testing
            # vad_params = VADParams(
            #     confidence=0.6,
            #     start_secs=0.2,
            #     stop_secs=0.3,
            #     min_volume=0.6
            # )
            # vad = SileroVADAnalyzer(sample_rate=16000, params=vad_params)
            
            # Create audio processor
            self.audio_processor = AudioInputProcessor()
            
            # Create pipeline: transport.input() → audio_processor → transport.output()
            self.pipeline = Pipeline([
                self.transport.input(),    # Receive from server
                self.audio_processor,      # Process audio and responses
                self.transport.output()    # Send to server
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
            
            # Create and start runner
            self.runner = PipelineRunner()
            
            # Store event loop for audio capture
            self.loop = asyncio.get_event_loop()
            
            # Start pipeline in background
            asyncio.create_task(self.runner.run(self.pipeline_task))
            
            # Wait a moment for connection
            await asyncio.sleep(2)
            
            logger.info("✅ Pipecat client pipeline started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Pipecat pipeline: {e}")
            import traceback
            traceback.print_exc()
            raise
            
    async def stop_pipecat_pipeline(self):
        """Stop the Pipecat pipeline"""
        try:
            if self.runner:
                # Note: PipelineRunner doesn't have a stop() method
                # The pipeline will stop when the task completes
                pass
                
            self.transport = None
            self.pipeline = None
            self.pipeline_task = None
            self.runner = None
            self.audio_processor = None
            
            logger.info("✅ Pipecat pipeline stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping pipeline: {e}")
            
    def start_audio_capture(self):
        """Start capturing audio from microphone"""
        if self.audio_stream or not self.audio_processor:
            return
            
        logger.info("🎤 Starting microphone capture...")
        
        def audio_callback(indata, frames, time, status):
            """Audio callback - runs in separate thread"""
            if status:
                logger.warning(f"⚠️ Audio status: {status}")
                
            if not self.audio_processor.is_capturing:
                return
                
            # Convert to 16-bit PCM
            audio_data = (indata[:, 0] * 32767).astype(np.int16)
            
            # Send to pipeline via asyncio
            if self.loop and not self.loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.audio_processor.send_audio_chunk(audio_data.tobytes()), 
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
            
            # Start capture in processor
            self.audio_processor.start_capture()
            
            logger.info("✅ Microphone capture started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start audio capture: {e}")
            
    def stop_audio_capture(self):
        """Stop audio capture"""
        if self.audio_processor:
            self.audio_processor.stop_capture()
            
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            
        logger.info("⏹️ Audio capture stopped")
        
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
        
    # Get current WSL2 IP dynamically or use localhost
    pipecat_uri = "ws://172.20.104.13:8001"  # Use the confirmed working IP
    
    bot = PipecatDiscordBot(discord_token, pipecat_uri)
    bot.run()