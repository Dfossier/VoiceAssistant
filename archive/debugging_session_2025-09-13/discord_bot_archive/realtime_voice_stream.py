#!/usr/bin/env python3
"""
Real-time voice streaming for Discord using custom audio receiver
Based on py-cord's lower-level voice handling
"""

import asyncio
import discord
import logging
import websockets
import json
import base64
import struct
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress discord logs
for log_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(log_name).setLevel(logging.ERROR)

class RealtimeAudioReceiver:
    """Custom audio receiver that streams data in real-time"""
    
    def __init__(self, voice_client, websocket_url="ws://127.0.0.1:8001"):
        self.voice_client = voice_client
        self.websocket_url = websocket_url
        self.websocket = None
        self.is_streaming = False
        self.audio_buffer = bytearray()
        self.chunk_count = 0
        self.last_send_time = 0
        self.send_interval = 0.5  # Send every 500ms
        
    async def connect_websocket(self):
        """Connect to streaming backend"""
        try:
            logger.info(f"🔌 Connecting to {self.websocket_url}...")
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info("✅ Connected to streaming backend")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False
            
    async def start_streaming(self):
        """Start real-time audio streaming"""
        if self.is_streaming:
            logger.warning("Already streaming!")
            return
            
        if not await self.connect_websocket():
            return False
            
        self.is_streaming = True
        self.audio_buffer.clear()
        self.chunk_count = 0
        
        # Start receiver task
        asyncio.create_task(self._receive_audio_loop())
        
        logger.info("🎤 Real-time streaming started!")
        return True
        
    async def stop_streaming(self):
        """Stop streaming"""
        self.is_streaming = False
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        logger.info(f"🛑 Streaming stopped. Sent {self.chunk_count} chunks")
        
    async def _receive_audio_loop(self):
        """Main audio receiving loop"""
        try:
            # Access the voice client's socket directly
            if not hasattr(self.voice_client, 'socket') or not self.voice_client.socket:
                logger.error("❌ No voice socket available!")
                return
                
            socket = self.voice_client.socket
            logger.info("✅ Accessing voice socket for real-time audio")
            
            while self.is_streaming and self.voice_client.is_connected():
                try:
                    # Read raw data from socket (non-blocking)
                    # Discord sends RTP packets with Opus audio
                    data = await asyncio.wait_for(
                        asyncio.get_event_loop().sock_recv(socket, 4096), 
                        timeout=0.1
                    )
                    
                    if data:
                        # Process RTP packet
                        await self._process_audio_packet(data)
                        
                except asyncio.TimeoutError:
                    # No data available, check if we should send buffered audio
                    await self._check_send_buffer()
                except Exception as e:
                    logger.error(f"❌ Socket read error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Audio loop error: {e}", exc_info=True)
        finally:
            self.is_streaming = False
            
    async def _process_audio_packet(self, data):
        """Process raw RTP/Opus packet"""
        try:
            # RTP header is 12 bytes
            if len(data) < 12:
                return
                
            # Parse RTP header (simplified)
            # Bytes 0-1: V(2), P(1), X(1), CC(4), M(1), PT(7)
            # Bytes 2-3: Sequence number
            # Bytes 4-7: Timestamp  
            # Bytes 8-11: SSRC
            
            # Extract Opus payload (after RTP header)
            opus_data = data[12:]
            
            if opus_data:
                # Add to buffer
                self.audio_buffer.extend(opus_data)
                
                # Check if we should send
                await self._check_send_buffer()
                
        except Exception as e:
            logger.error(f"❌ Packet processing error: {e}")
            
    async def _check_send_buffer(self):
        """Check if we should send buffered audio"""
        current_time = time.time()
        
        # Send if enough time passed or buffer is large
        if (current_time - self.last_send_time >= self.send_interval and 
            len(self.audio_buffer) > 0) or len(self.audio_buffer) > 8192:
            
            await self._send_audio_chunk()
            self.last_send_time = current_time
            
    async def _send_audio_chunk(self):
        """Send audio chunk to backend"""
        if not self.websocket or not self.audio_buffer:
            return
            
        try:
            self.chunk_count += 1
            
            # Convert buffer to bytes
            audio_data = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            
            # Encode and send
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            message = {
                "type": "audio_input",
                "data": audio_b64,
                "format": "opus",  # Raw Opus packets
                "sample_rate": 48000,
                "chunk_id": self.chunk_count,
                "size": len(audio_data),
                "timestamp": time.time()
            }
            
            await self.websocket.send(json.dumps(message))
            logger.info(f"📡 Sent chunk #{self.chunk_count}: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"❌ Send error: {e}")

class CustomVoiceClient(discord.VoiceClient):
    """Extended VoiceClient with real-time streaming"""
    
    def __init__(self, client, channel):
        super().__init__(client, channel)
        self.audio_receiver = None
        
    async def start_realtime_streaming(self, websocket_url="ws://127.0.0.1:8001"):
        """Start real-time audio streaming"""
        if not self.is_connected():
            logger.error("❌ Not connected to voice!")
            return False
            
        self.audio_receiver = RealtimeAudioReceiver(self, websocket_url)
        return await self.audio_receiver.start_streaming()
        
    async def stop_realtime_streaming(self):
        """Stop real-time streaming"""
        if self.audio_receiver:
            await self.audio_receiver.stop_streaming()
            self.audio_receiver = None

class RealtimeVoiceBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("Commands: !realtime_start, !realtime_stop")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!realtime_start':
            await self._start_realtime(message)
        elif content == '!realtime_stop':
            await self._stop_realtime(message)
            
    async def _start_realtime(self, message):
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
            
        try:
            channel = message.author.voice.channel
            
            # Use custom voice client
            voice_client = await channel.connect(cls=CustomVoiceClient)
            logger.info(f"✅ Connected to {channel.name}")
            
            # Start real-time streaming
            if await voice_client.start_realtime_streaming():
                await message.reply(
                    "🎤 **Real-time streaming started!**\n"
                    "• Streaming raw audio packets\n"
                    "• Sending every 500ms\n"
                    "• Direct socket access"
                )
            else:
                await message.reply("❌ Failed to start streaming")
                
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_realtime(self, message):
        try:
            voice_client = message.guild.voice_client
            if not voice_client:
                await message.reply("Not connected!")
                return
                
            if hasattr(voice_client, 'stop_realtime_streaming'):
                await voice_client.stop_realtime_streaming()
                
            await voice_client.disconnect()
            await message.reply("🛑 Real-time streaming stopped!")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}")
            await message.reply(f"❌ Error: {str(e)}")

def main():
    Config.validate()
    bot = RealtimeVoiceBot()
    logger.info("🚀 Starting real-time voice streaming bot...")
    logger.info("⚠️  This uses low-level socket access for true streaming")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()