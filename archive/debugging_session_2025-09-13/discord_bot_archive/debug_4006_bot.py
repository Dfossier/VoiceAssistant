"""Enhanced debugging bot for Error 4006"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
import json
import signal
from dotenv import load_dotenv

# Import voice debug patches FIRST
import voice_debug_patch

load_dotenv()

# Configure logging - application level only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('debug_4006.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Suppress library logs except errors
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.voice_client').setLevel(logging.WARNING)

logger = logging.getLogger('debug_bot')

# Monkey patch to intercept voice gateway data
original_received_message = None

async def debug_received_message(self, msg):
    """Log all voice gateway messages for debugging"""
    try:
        # msg is already a dict, not a JSON string
        data = msg
        op = data.get('op')
        t = data.get('t')
        d = data.get('d', {})
        
        logger.info(f"Voice Gateway Message: op={op}, t={t}")
        
        # Log important voice events
        if op == 8:  # HELLO
            logger.info(f"Voice HELLO: heartbeat_interval={d.get('heartbeat_interval')}")
        elif op == 2:  # READY
            logger.info(f"Voice READY: ssrc={d.get('ssrc')}, ip={d.get('ip')}, port={d.get('port')}")
            logger.info(f"Voice modes available: {d.get('modes', [])}")
            
            # This is where empty modes would cause issues
            if not d.get('modes'):
                logger.error("WARNING: Discord sent empty modes list! This causes Error 4006")
                
        elif op == 4:  # SESSION_DESCRIPTION
            logger.info(f"Voice SESSION_DESCRIPTION: mode={d.get('mode')}")
        elif op == 9:  # RESUMED
            logger.info("Voice connection RESUMED")
            
        # Check for close codes
        if hasattr(self, '_close_code') and self._close_code:
            logger.warning(f"Voice close code detected: {self._close_code}")
            
    except Exception as e:
        logger.error(f"Error in debug handler: {e}")
    
    # Call original handler with self and msg
    return await original_received_message(self, msg)

# Apply debug patch
import discord.gateway
original_received_message = discord.gateway.DiscordVoiceWebSocket.received_message
discord.gateway.DiscordVoiceWebSocket.received_message = debug_received_message

class Debug4006Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_connections = []
        
    async def close(self):
        """Proper cleanup on close"""
        logger.info("Bot closing - cleaning up voice connections")
        for vc in self.voice_connections:
            try:
                if vc and vc.is_connected():
                    await vc.disconnect(force=True)
                    logger.info(f"Disconnected from {vc.channel.name}")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
        
        self.voice_connections.clear()
        await super().close()

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = Debug4006Bot(command_prefix='!', intents=intents)

# Global reference for signal handler
bot_instance = None

def signal_handler(sig, frame):
    """Handle Ctrl+C properly"""
    logger.info("Received interrupt signal - cleaning up...")
    if bot_instance:
        try:
            # Schedule coroutine in the event loop
            asyncio.create_task(cleanup_and_exit())
        except RuntimeError:
            # If no event loop, just exit
            sys.exit(0)

async def cleanup_and_exit():
    """Async cleanup function"""
    await bot_instance.close()
    sys.exit(0)

@bot.event
async def on_ready():
    global bot_instance
    bot_instance = bot
    logger.info(f"Bot ready: {bot.user}")
    
    # Log connection info
    logger.info(f"Latency: {bot.latency*1000:.2f}ms")
    logger.info(f"Guilds: {len(bot.guilds)}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Track voice state changes"""
    if member == bot.user:
        if before.channel and not after.channel:
            logger.info(f"Bot left voice channel: {before.channel.name}")
        elif not before.channel and after.channel:
            logger.info(f"Bot joined voice channel: {after.channel.name}")

@bot.command()
async def debug(ctx):
    """Show debug information"""
    embed = discord.Embed(title="Debug Information", color=0x00ff00)
    
    # System info
    embed.add_field(
        name="System",
        value=f"Python: {sys.version.split()[0]}\n"
              f"discord.py: {discord.__version__}\n"
              f"Platform: {sys.platform}",
        inline=False
    )
    
    # Connection info
    if ctx.voice_client:
        embed.add_field(
            name="Voice Connection",
            value=f"Connected: {ctx.voice_client.is_connected()}\n"
                  f"Channel: {ctx.voice_client.channel.name}\n"
                  f"Endpoint: {ctx.voice_client.endpoint}\n"
                  f"Protocol: {getattr(ctx.voice_client, 'protocol', 'Unknown')}",
            inline=False
        )
    
    # Guild info
    embed.add_field(
        name="Guild Voice Info",
        value=f"Region: {ctx.guild.region if hasattr(ctx.guild, 'region') else 'N/A'}\n"
              f"Voice Channels: {len(ctx.guild.voice_channels)}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def join(ctx):
    """Join with enhanced debugging"""
    if not ctx.author.voice:
        await ctx.send("❌ You're not in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    logger.info(f"Attempting to join: {channel.name} (ID: {channel.id})")
    
    # Log channel details
    logger.info(f"Channel region: {channel.rtc_region}")
    logger.info(f"Channel bitrate: {channel.bitrate}")
    logger.info(f"Channel permissions: {channel.permissions_for(ctx.guild.me).value}")
    
    try:
        # Clean disconnect first
        if ctx.voice_client:
            logger.info("Disconnecting from current channel")
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(1)
            
        # Try connection with minimal parameters
        logger.info("Starting connection attempt")
        voice_client = await channel.connect(timeout=30.0, reconnect=False)
        
        # Track connection
        bot.voice_connections.append(voice_client)
        
        logger.info(f"Initial connection result: {voice_client}")
        logger.info(f"Is connected: {voice_client.is_connected()}")
        
        # Wait and verify
        await asyncio.sleep(2)
        
        if voice_client.is_connected():
            await ctx.send(f"✅ Connected to **{channel.name}**!")
            logger.info("Voice connection successful and stable")
            
            # Log connection details
            logger.info(f"Voice endpoint: {voice_client.endpoint}")
            logger.info(f"Voice token: {voice_client.token[:10]}...")
            logger.info(f"Session ID: {voice_client.session_id}")
        else:
            await ctx.send("❌ Connection dropped after initial success")
            logger.error("Connection was established but then dropped")
            
    except discord.errors.ClientException as e:
        logger.error(f"Discord ClientException: {e}")
        await ctx.send(f"❌ Discord error: {e}")
    except asyncio.TimeoutError:
        logger.error("Connection timed out")
        await ctx.send("❌ Connection timed out")
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        await ctx.send(f"❌ Error: {type(e).__name__}")

@bot.command()
async def leave(ctx):
    """Leave voice channel"""
    if ctx.voice_client:
        channel_name = ctx.voice_client.channel.name
        await ctx.voice_client.disconnect(force=True)
        
        # Remove from tracked connections
        if ctx.voice_client in bot.voice_connections:
            bot.voice_connections.remove(ctx.voice_client)
            
        await ctx.send(f"👋 Left {channel_name}")
        logger.info(f"Left voice channel: {channel_name}")
    else:
        await ctx.send("❌ Not in a voice channel!")

@bot.command()
async def cleanup(ctx):
    """Force cleanup all connections"""
    count = 0
    for vc in list(bot.voice_connections):
        try:
            if vc.is_connected():
                await vc.disconnect(force=True)
                count += 1
        except:
            pass
    
    bot.voice_connections.clear()
    
    # Also cleanup guild voice clients
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
                count += 1
            except:
                pass
    
    await ctx.send(f"🧹 Cleaned up {count} voice connections")
    logger.info(f"Forced cleanup of {count} connections")

# Install signal handler
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("No Discord token found!")
        sys.exit(1)
        
    logger.info("Starting Debug 4006 Bot...")
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt - cleaning up...")
    finally:
        logger.info("Bot shut down")