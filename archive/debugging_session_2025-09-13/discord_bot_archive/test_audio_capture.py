#!/usr/bin/env python3
"""
Simple Discord bot to test audio capture and streaming
"""

import asyncio
import discord
import discord.opus
import logging
import websockets
import json
import base64
import time
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force load Opus
try:
    discord.opus._load_default()
    logger.info(f"Opus loaded: {discord.opus.is_loaded()}")
except Exception as e:
    logger.error(f"Opus error: {e}")

class AudioTester:
    def __init__(self):
        self.websocket = None
        self.chunk_count = 0
        
    async def connect_websocket(self):
        try:
            logger.info("🔌 Connecting to test server...")
            self.websocket = await websockets.connect("ws://127.0.0.1:8001")
            logger.info("✅ Connected to test server")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False
            
    async def send_audio(self, audio_data):
        if not self.websocket:
            return
            
        try:
            self.chunk_count += 1
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "audio_input",
                "data": audio_b64,
                "sample_rate": 48000,
                "channels": 2,
                "chunk_id": self.chunk_count,
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📡 Sent audio chunk #{self.chunk_count}: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"❌ Failed to send audio: {e}")

class TestBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.audio_tester = AudioTester()
        self.is_recording = False
        self.current_sink = None
        
    async def on_ready(self):
        logger.info(f"🤖 {self.user} connected to Discord!")
        
        # Connect to test WebSocket server
        await self.audio_tester.connect_websocket()
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!test_record':
            await self._start_recording(message)
        elif content == '!test_stop':
            await self._stop_recording(message)
            
    async def _start_recording(self, message):
        if not message.author.voice:
            await message.reply("❌ Join a voice channel first!")
            return
            
        channel = message.author.voice.channel
        
        try:
            # Connect to voice channel
            voice_client = await channel.connect()
            logger.info(f"🔌 Connected to {channel.name}")
            
            # Start recording with simple callback
            sink = discord.sinks.WaveSink()
            
            # Store sink for later processing
            self.current_sink = sink
            
            voice_client.start_recording(sink, lambda *args: None)  # Empty callback
            self.is_recording = True
            
            await message.reply("🎤 **Test recording started!** Say something, then use `!test_stop`")
            logger.info("✅ Recording started")
            
        except Exception as e:
            await message.reply(f"❌ Recording failed: {str(e)}")
            logger.error(f"Recording error: {e}")
            
    async def _stop_recording(self, message):
        if not self.is_recording:
            await message.reply("❌ Not currently recording")
            return
            
        try:
            voice_client = message.guild.voice_client
            if voice_client and voice_client.recording:
                voice_client.stop_recording()
                self.is_recording = False
                
            await message.reply("🛑 **Recording stopped!** Processing audio...")
            logger.info("✅ Recording stopped")
            
            # Process the recorded audio
            if hasattr(self, 'current_sink'):
                await self._process_recorded_audio(self.current_sink)
            
        except Exception as e:
            await message.reply(f"❌ Stop failed: {str(e)}")
            logger.error(f"Stop error: {e}")
            
    async def _process_recorded_audio(self, sink):
        """Process recorded audio and send to WebSocket"""
        try:
            logger.info("🔄 Processing recorded audio...")
            
            if not sink.audio_data:
                logger.warning("⚠️ No audio data in sink")
                return
                
            total_sent = 0
            for user_id, audio in sink.audio_data.items():
                user = self.get_user(user_id)
                if not user or user.bot:
                    continue
                    
                audio_bytes = audio.file.getvalue()
                if len(audio_bytes) > 0:
                    logger.info(f"📦 Found {len(audio_bytes)} bytes from {user.display_name}")
                    await self.audio_tester.send_audio(audio_bytes)
                    total_sent += len(audio_bytes)
                    
            logger.info(f"✅ Sent total {total_sent} bytes to WebSocket server")
            
        except Exception as e:
            logger.error(f"❌ Error processing audio: {e}")

def main():
    try:
        Config.validate()
        bot = TestBot()
        
        logger.info("🚀 Starting Discord audio test bot...")
        bot.run(Config.DISCORD_TOKEN)
        
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")

if __name__ == "__main__":
    main()