#!/usr/bin/env python3
"""WSL2 Voice Test Bot - Testing Opus and voice connections"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Suppress Discord library logs except errors
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('discord.client').setLevel(logging.ERROR)

# Force load Opus on startup
logger.info("🔧 Force loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "✅ Loaded" if discord.opus.is_loaded() else "❌ Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"❌ Error loading Opus: {e}")

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

# Initialize bot
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f"✅ {bot.user} connected to Discord!")
    logger.info(f"📊 Bot in {len(bot.guilds)} guilds")
    
    # Re-check Opus status
    opus_loaded = discord.opus.is_loaded()
    logger.info(f"🎵 Opus loaded: {'✅ Yes' if opus_loaded else '❌ No'}")

@bot.event
async def on_message(message):
    """Handle messages"""
    if message.author == bot.user:
        return
    
    content = message.content.lower().strip()
    
    if content == '!opustest':
        await opus_test(message)
    elif content == '!voicetest':
        await voice_test(message)
    elif content == '!voiceleave':
        await voice_leave(message)
    elif content == '!help':
        await show_help(message)

async def opus_test(message):
    """Test Opus library status"""
    logger.info("🧪 Running Opus test...")
    
    opus_loaded = discord.opus.is_loaded()
    embed = discord.Embed(
        title="🎵 Opus Library Test",
        color=0x00ff00 if opus_loaded else 0xff0000
    )
    
    embed.add_field(
        name="Library Status",
        value=f"{'✅ Loaded' if opus_loaded else '❌ Not Loaded'}",
        inline=False
    )
    
    # Try to get library info
    try:
        if hasattr(discord.opus, '_lib') and discord.opus._lib:
            lib_info = str(discord.opus._lib)
            embed.add_field(
                name="Library Object",
                value=f"```{lib_info[:100]}{'...' if len(lib_info) > 100 else ''}```",
                inline=False
            )
    except Exception as e:
        embed.add_field(
            name="Library Info Error", 
            value=f"```{str(e)}```",
            inline=False
        )
    
    # System info
    embed.add_field(
        name="System Info",
        value=f"Platform: {sys.platform}\nPython: {sys.version.split()[0]}\nDiscord.py: {discord.__version__}",
        inline=False
    )
    
    await message.channel.send(embed=embed)

async def voice_test(message):
    """Test voice connection"""
    logger.info("🎤 Running voice connection test...")
    
    if not message.author.voice:
        await message.channel.send("❌ You need to be in a voice channel!")
        return
    
    channel = message.author.voice.channel
    logger.info(f"🎯 Target channel: {channel.name}")
    
    try:
        # Check if already connected
        guild = message.guild
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
            await asyncio.sleep(1)
        
        # Attempt connection
        await message.channel.send(f"🔄 Connecting to **{channel.name}**...")
        
        voice_client = await channel.connect(timeout=20.0, reconnect=False)
        
        # Wait to verify stable connection
        await asyncio.sleep(2)
        
        if voice_client and voice_client.is_connected():
            embed = discord.Embed(
                title="✅ Voice Connection Successful!",
                color=0x00ff00
            )
            embed.add_field(
                name="Connected To",
                value=f"**{channel.name}**\nGuild: {guild.name}",
                inline=False
            )
            embed.add_field(
                name="Connection Info",
                value=f"Latency: {voice_client.latency*1000:.1f}ms\nChannel Users: {len(channel.members)}",
                inline=False
            )
            
            logger.info(f"✅ Successfully connected to {channel.name}")
            await message.channel.send(embed=embed)
            
            # Test speaking (just stay connected)
            await message.channel.send("🎵 **Voice connected successfully!** Use `!voiceleave` to disconnect.")
            
        else:
            raise Exception("Connection established but not stable")
            
    except discord.errors.ClientException as e:
        logger.error(f"❌ Discord error: {e}")
        await message.channel.send(f"❌ **Discord Error:** {str(e)}")
    except asyncio.TimeoutError:
        logger.error("❌ Connection timeout")
        await message.channel.send("❌ **Timeout:** Voice connection took too long")
    except Exception as e:
        logger.error(f"❌ Voice connection failed: {e}")
        await message.channel.send(f"❌ **Connection Failed:** {str(e)}")

async def voice_leave(message):
    """Leave voice channel"""
    guild = message.guild
    
    if not guild.voice_client:
        await message.channel.send("❌ Not connected to voice!")
        return
    
    try:
        channel_name = guild.voice_client.channel.name
        await guild.voice_client.disconnect(force=True)
        await message.channel.send(f"👋 Left **{channel_name}**")
        logger.info(f"✅ Disconnected from {channel_name}")
    except Exception as e:
        logger.error(f"❌ Error disconnecting: {e}")
        await message.channel.send(f"❌ Error disconnecting: {str(e)}")

async def show_help(message):
    """Show help message"""
    embed = discord.Embed(
        title="🧪 WSL2 Voice Test Bot",
        description="Testing Opus library and voice connections in WSL2",
        color=0x0099ff
    )
    
    embed.add_field(
        name="Test Commands",
        value="`!opustest` - Check Opus library status\n"
              "`!voicetest` - Test voice connection\n"
              "`!voiceleave` - Leave voice channel\n"
              "`!help` - Show this help",
        inline=False
    )
    
    embed.add_field(
        name="Usage",
        value="1. Join a voice channel\n"
              "2. Use `!opustest` to verify Opus\n"
              "3. Use `!voicetest` to test connection\n"
              "4. Check for Error 4006!",
        inline=False
    )
    
    await message.channel.send(embed=embed)

if __name__ == "__main__":
    # Load environment from parent directory
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✅ Loaded .env from {env_path}")
    else:
        logger.warning(f"⚠️ .env not found at {env_path}")
    
    # Get Discord token (try both variable names)
    token = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ Discord token not found!")
        logger.info("💡 Make sure .env file has DISCORD_TOKEN or DISCORD_BOT_TOKEN")
        sys.exit(1)
    
    try:
        logger.info("🚀 Starting WSL2 Voice Test Bot...")
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
    finally:
        logger.info("🏁 Bot shutdown complete")