#!/usr/bin/env python3
"""
Basic Voice Connection Test - Just test if we can connect without Error 4006
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Suppress Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Force load Opus
logger.info("[SETUP] Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "[OK] Loaded" if discord.opus.is_loaded() else "[ERROR] Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"[ERROR] Opus error: {e}")

class VoiceTestBot(discord.Client):
    """Simple bot to test voice connections"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        logger.info("[READY] Bot ready for voice connection tests!")
    
    async def on_message(self, message):
        """Handle all messages"""
        if message.author == self.user:
            return
        
        content = message.content.strip()
        
        if content.lower() == '!connect':
            await self._test_voice_connection(message)
        elif content.lower() == '!disconnect':
            await self._disconnect_voice(message)
        elif content.lower() == '!status':
            await self._show_status(message)
        elif content.lower() == '!help':
            await self._show_help(message)
    
    async def _test_voice_connection(self, message):
        """Test voice connection"""
        if not message.author.voice:
            await message.reply("You need to be in a voice channel!")
            return
        
        channel = message.author.voice.channel
        logger.info(f"[TEST] Attempting to connect to {channel.name}")
        
        try:
            # Test connection
            voice_client = await channel.connect(timeout=10.0)
            
            if voice_client and voice_client.is_connected():
                await message.reply(f"✅ Successfully connected to {channel.name}!")
                logger.info(f"[SUCCESS] Connected to {channel.name}")
                
                # Test staying connected
                await asyncio.sleep(3)
                await message.reply("✅ Connection stable for 3 seconds!")
                
                # Auto-disconnect after 10 seconds
                await asyncio.sleep(7) 
                await voice_client.disconnect()
                await message.reply("✅ Disconnected successfully!")
                logger.info("[SUCCESS] Disconnected cleanly")
            else:
                await message.reply("❌ Connection failed")
                logger.error("[ERROR] Connection returned None or not connected")
                
        except Exception as e:
            await message.reply(f"❌ Connection failed: {str(e)}")
            logger.error(f"[ERROR] Connection error: {e}")
    
    async def _disconnect_voice(self, message):
        """Disconnect from voice"""
        if message.guild.voice_client:
            try:
                await message.guild.voice_client.disconnect()
                await message.reply("Disconnected from voice!")
                logger.info("[DISCONNECT] Manual disconnect successful")
            except Exception as e:
                await message.reply(f"Error: {str(e)}")
        else:
            await message.reply("Not connected to voice!")
    
    async def _show_status(self, message):
        """Show status"""
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        connected = "Yes" if message.guild.voice_client else "No"
        
        status = f"""**Voice Connection Test Status**
Opus: {opus_status}
Connected: {connected}
Bot Latency: {round(self.latency * 1000)}ms"""
        
        await message.reply(status)
    
    async def _show_help(self, message):
        """Show help"""
        help_text = """**Voice Connection Test Commands:**
`!connect` - Test voice connection (auto-disconnects in 10s)
`!disconnect` - Manual disconnect
`!status` - Show connection status
`!help` - Show this help

**Test Instructions:**
1. Join a voice channel
2. Use `!connect` to test if Error 4006 is fixed
3. Watch for success/failure messages"""
        
        await message.reply(help_text)

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = VoiceTestBot()
    
    try:
        logger.info("[START] Starting Voice Connection Test Bot...")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()