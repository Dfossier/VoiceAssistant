#!/usr/bin/env python3
"""
Debug continuous audio capture in Discord
"""

import asyncio
import discord
import logging
import time
import io
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

class ContinuousAudioDebugger:
    """Debug continuous audio capture"""
    
    def __init__(self, bot):
        self.bot = bot
        self.is_capturing = False
        self.chunk_count = 0
        self.total_bytes = 0
        self.monitor_task = None
        
    async def start_continuous_debug(self, voice_client):
        """Start continuous capture debug"""
        if self.is_capturing:
            logger.warning("Already capturing!")
            return
            
        logger.info("🎤 Starting continuous capture debug...")
        self.is_capturing = True
        self.chunk_count = 0
        self.total_bytes = 0
        
        # Create a custom sink to monitor data flow
        sink = discord.sinks.WaveSink()
        
        # Start recording
        voice_client.start_recording(
            sink,
            self._finished_callback,  # This is called when stop_recording is called
            None  # No context needed
        )
        
        # Monitor the sink continuously
        self.monitor_task = asyncio.create_task(self._monitor_sink_continuously(sink))
        
        logger.info("✅ Recording started - monitoring audio data...")
        
    async def stop_continuous_debug(self, voice_client):
        """Stop continuous capture debug"""
        if not self.is_capturing:
            return
            
        logger.info("🛑 Stopping continuous capture debug...")
        self.is_capturing = False
        
        # Cancel monitor task
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
        # Stop recording
        if voice_client.recording:
            voice_client.stop_recording()
            
        logger.info(f"📊 Final stats: {self.chunk_count} checks, {self.total_bytes} total bytes")
        
    def _finished_callback(self, sink, error=None):
        """Called when recording is stopped"""
        if error:
            logger.error(f"❌ Recording error: {error}")
        else:
            logger.info("✅ Recording stopped cleanly")
            
        # Final analysis
        self._analyze_sink_data(sink, final=True)
        
    async def _monitor_sink_continuously(self, sink):
        """Monitor sink data continuously"""
        try:
            last_report_time = time.time()
            last_byte_counts = {}
            
            while self.is_capturing:
                await asyncio.sleep(0.5)  # Check every 500ms
                
                self.chunk_count += 1
                current_time = time.time()
                
                # Analyze current state
                stats = self._analyze_sink_data(sink)
                
                # Check for new data
                new_data = False
                for user_id, byte_count in stats['user_bytes'].items():
                    if user_id not in last_byte_counts:
                        last_byte_counts[user_id] = 0
                        
                    if byte_count > last_byte_counts[user_id]:
                        new_bytes = byte_count - last_byte_counts[user_id]
                        logger.info(f"  📡 User {user_id}: +{new_bytes} new bytes (total: {byte_count})")
                        new_data = True
                        last_byte_counts[user_id] = byte_count
                        
                if not new_data and current_time - last_report_time > 2.0:
                    logger.info(f"  ⏳ Check #{self.chunk_count}: No new data...")
                    last_report_time = current_time
                    
        except asyncio.CancelledError:
            logger.info("Monitor task cancelled")
        except Exception as e:
            logger.error(f"❌ Monitor error: {e}", exc_info=True)
            
    def _analyze_sink_data(self, sink, final=False):
        """Analyze sink data structure"""
        stats = {
            'user_count': 0,
            'total_bytes': 0,
            'user_bytes': {}
        }
        
        prefix = "FINAL" if final else f"Check #{self.chunk_count}"
        
        try:
            if hasattr(sink, 'audio_data') and sink.audio_data:
                stats['user_count'] = len(sink.audio_data)
                
                for user_id, audio_obj in sink.audio_data.items():
                    if hasattr(audio_obj, 'file'):
                        # Try different methods to get file size
                        try:
                            # Method 1: Get current position
                            current_pos = audio_obj.file.tell()
                            
                            # Method 2: Seek to end to get size
                            audio_obj.file.seek(0, 2)
                            file_size = audio_obj.file.tell()
                            
                            # Restore position
                            audio_obj.file.seek(current_pos)
                            
                            stats['user_bytes'][user_id] = file_size
                            stats['total_bytes'] += file_size
                            
                            if final:
                                # Read actual data
                                audio_obj.file.seek(0)
                                data = audio_obj.file.read()
                                logger.info(f"  👤 User {user_id}: {len(data)} bytes total")
                                
                        except Exception as e:
                            logger.error(f"  ❌ Error reading user {user_id} data: {e}")
                            
                if stats['total_bytes'] != self.total_bytes:
                    self.total_bytes = stats['total_bytes']
                    logger.info(f"📊 {prefix}: {stats['user_count']} users, {stats['total_bytes']} total bytes")
                    
            else:
                logger.debug(f"  {prefix}: No audio_data attribute or empty")
                
        except Exception as e:
            logger.error(f"❌ Analysis error: {e}", exc_info=True)
            
        return stats

class DebugBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.debugger = ContinuousAudioDebugger(self)
        
    async def on_ready(self):
        logger.info(f"✅ Bot ready as {self.user}")
        logger.info("Commands: !debug_start, !debug_stop")
        
    async def on_message(self, message):
        if message.author == self.user:
            return
            
        content = message.content.lower().strip()
        
        if content == '!debug_start':
            await self._start_debug(message)
        elif content == '!debug_stop':
            await self._stop_debug(message)
            
    async def _start_debug(self, message):
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
            
        try:
            channel = message.author.voice.channel
            
            # Connect to voice
            if message.guild.voice_client:
                vc = message.guild.voice_client
                if vc.channel != channel:
                    await vc.disconnect()
                    vc = await channel.connect()
            else:
                vc = await channel.connect()
                
            logger.info(f"✅ Connected to {channel.name}")
            
            # Start continuous debug
            await self.debugger.start_continuous_debug(vc)
            
            await message.reply(
                "🎤 **Continuous capture debug started!**\n"
                "• Monitoring audio data every 500ms\n"
                "• Speak to generate audio data\n"
                "• Use `!debug_stop` to stop and see final stats"
            )
            
        except Exception as e:
            logger.error(f"❌ Start error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")
            
    async def _stop_debug(self, message):
        try:
            vc = message.guild.voice_client
            if not vc:
                await message.reply("Not connected to voice!")
                return
                
            # Stop debug
            await self.debugger.stop_continuous_debug(vc)
            
            # Disconnect
            await vc.disconnect()
            
            await message.reply("🛑 Debug stopped! Check console for final stats.")
            
        except Exception as e:
            logger.error(f"❌ Stop error: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")

def main():
    Config.validate()
    bot = DebugBot()
    logger.info("🚀 Starting continuous capture debug bot...")
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()