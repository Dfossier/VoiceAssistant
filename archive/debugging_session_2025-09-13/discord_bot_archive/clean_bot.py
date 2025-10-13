"""Clean Discord bot with proper state management and shutdown"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import signal
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Simple intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Global state tracking
voice_connection_state = {}
shutdown_requested = False

@bot.event
async def on_ready():
    logger.info(f"✅ Bot ready: {bot.user}")
    logger.info(f"Guilds: {len(bot.guilds)}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice state changes"""
    if member == bot.user:
        guild_id = member.guild.id
        if after.channel:
            voice_connection_state[guild_id] = {
                'connected': True,
                'channel': after.channel.name,
                'channel_id': after.channel.id
            }
            logger.info(f"Bot connected to voice: {after.channel.name}")
        else:
            voice_connection_state[guild_id] = {'connected': False}
            logger.info("Bot disconnected from voice")

async def cleanup_voice_connections():
    """Properly cleanup all voice connections"""
    logger.info("🧹 Cleaning up voice connections...")
    
    # Disconnect all voice clients
    for guild_id in list(voice_connection_state.keys()):
        voice_connection_state[guild_id] = {'connected': False}
    
    for voice_client in bot.voice_clients:
        try:
            logger.info(f"Disconnecting from {voice_client.channel.name}")
            await voice_client.disconnect(force=True)
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    # Clear internal Discord.py state
    bot._connection._voice_clients.clear()
    
    # Wait for cleanup
    await asyncio.sleep(2)
    logger.info("✅ Voice cleanup complete")

@bot.command(name='clean_join')
async def clean_join(ctx):
    """Join voice with proper state management"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    guild_id = ctx.guild.id
    
    try:
        # Check our state first
        current_state = voice_connection_state.get(guild_id, {'connected': False})
        
        if current_state.get('connected'):
            await ctx.send("⚠️ Bot thinks it's already connected. Cleaning up first...")
            await cleanup_voice_connections()
        
        await ctx.send(f"🔄 Connecting to {channel.name}...")
        
        # Simple connection
        voice_client = await channel.connect(timeout=20.0)
        
        if voice_client and voice_client.is_connected():
            voice_connection_state[guild_id] = {
                'connected': True,
                'channel': channel.name,
                'channel_id': channel.id
            }
            await ctx.send("✅ Connected successfully!")
        else:
            await ctx.send("❌ Connection failed")
            
    except Exception as e:
        logger.error(f"Join error: {e}")
        await ctx.send(f"❌ Error: {e}")

@bot.command(name='clean_leave')
async def clean_leave(ctx):
    """Leave voice with proper cleanup"""
    guild_id = ctx.guild.id
    
    if ctx.voice_client:
        try:
            await ctx.send("👋 Disconnecting...")
            await ctx.voice_client.disconnect()
            voice_connection_state[guild_id] = {'connected': False}
            await ctx.send("✅ Disconnected successfully")
        except Exception as e:
            logger.error(f"Leave error: {e}")
            await ctx.send(f"❌ Error leaving: {e}")
    else:
        await ctx.send("❌ Not connected to voice")

@bot.command(name='state')
async def check_state(ctx):
    """Check bot's voice connection state"""
    guild_id = ctx.guild.id
    
    # Our internal state
    our_state = voice_connection_state.get(guild_id, {'connected': False})
    
    # Discord.py's state
    discord_connected = ctx.voice_client is not None and ctx.voice_client.is_connected()
    
    # Voice clients count
    voice_clients = len(bot.voice_clients)
    
    embed = discord.Embed(title="🔍 Voice Connection State", color=0x00ff00 if discord_connected else 0xff0000)
    embed.add_field(name="Our State", value=f"Connected: {our_state.get('connected')}", inline=True)
    embed.add_field(name="Discord State", value=f"Connected: {discord_connected}", inline=True)
    embed.add_field(name="Voice Clients", value=str(voice_clients), inline=True)
    
    if our_state.get('connected') and 'channel' in our_state:
        embed.add_field(name="Channel", value=our_state['channel'], inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='force_clean')
async def force_clean(ctx):
    """Force cleanup everything"""
    await ctx.send("🧹 **Force cleaning all connections...**")
    await cleanup_voice_connections()
    await ctx.send("✅ **Cleanup complete**")

@bot.command(name='shutdown')
async def shutdown_bot(ctx):
    """Properly shutdown bot"""
    global shutdown_requested
    
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only!")
        return
    
    await ctx.send("🛑 **Shutting down properly...**")
    shutdown_requested = True
    
    # Clean shutdown
    await cleanup_voice_connections()
    await ctx.send("✅ **Goodbye!**")
    
    # Close bot
    await bot.close()

# Signal handlers for proper shutdown
def signal_handler(signum, frame):
    global shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_requested = True
    
    # Force exit if needed
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    logger.info("🚀 Starting clean Discord bot...")
    logger.info("Commands: !clean_join, !clean_leave, !state, !force_clean, !shutdown")
    
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt - shutting down")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Bot terminated")
        os._exit(0)