"""Simple Discord voice bot with Error 4006 fixes"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.guild_messages = True

# Create bot with specific settings for Windows
bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    # Disable automatic sharding which can cause issues
    shard_count=None,
    shard_id=None
)

@bot.event
async def on_ready():
    print(f'[OK] Bot connected as {bot.user}')
    print(f'Discord.py version: {discord.__version__}')
    print(f'Python version: {sys.version}')
    print(f'Guilds: {len(bot.guilds)}')

@bot.command(name='join')
async def join_voice(ctx):
    """Join the voice channel"""
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    
    # Check permissions explicitly
    permissions = channel.permissions_for(ctx.guild.me)
    if not permissions.connect or not permissions.speak:
        await ctx.send("❌ I don't have permission to connect or speak in that channel!")
        return
    
    try:
        # Disconnect from any existing voice connection first
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(1)  # Wait a moment
        
        # Connect with specific parameters to avoid Error 4006
        voice_client = await channel.connect(
            timeout=30.0,
            reconnect=True,
            self_deaf=False,  # Don't self-deafen
            self_mute=False   # Don't self-mute
        )
        
        await ctx.send(f"✅ Connected to {channel.name}!")
        
        # Play a test sound after connecting
        await asyncio.sleep(1)
        if voice_client.is_connected():
            await ctx.send("🔊 Voice connection established successfully!")
        
    except discord.errors.ClientException as e:
        await ctx.send(f"❌ Already connected to a voice channel: {e}")
    except asyncio.TimeoutError:
        await ctx.send("❌ Connection timed out. Please try again.")
    except Exception as e:
        await ctx.send(f"❌ Failed to connect: {type(e).__name__}: {str(e)}")
        print(f"Voice connection error: {e}")

@bot.command(name='leave')
async def leave_voice(ctx):
    """Leave the voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("👋 Disconnected from voice channel")
    else:
        await ctx.send("❌ I'm not in a voice channel!")

@bot.command(name='status')
async def voice_status(ctx):
    """Check voice connection status"""
    if ctx.voice_client:
        await ctx.send(f"✅ Connected to: {ctx.voice_client.channel.name}")
        await ctx.send(f"Is connected: {ctx.voice_client.is_connected()}")
        await ctx.send(f"Latency: {round(bot.latency * 1000)}ms")
    else:
        await ctx.send("❌ Not connected to any voice channel")

@bot.command(name='fix')
async def fix_connection(ctx):
    """Force fix connection issues"""
    await ctx.send("🔧 Attempting to fix connection...")
    
    # Force disconnect all voice clients
    for vc in bot.voice_clients:
        try:
            await vc.disconnect(force=True)
        except:
            pass
    
    await asyncio.sleep(2)
    await ctx.send("✅ Cleared all voice connections. Try !join again.")

# Error handler
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"❌ Error: {error}")
    print(f"Command error: {error}")

# Run bot
if __name__ == "__main__":
    print("Starting simple voice bot...")
    print("Make sure you're running this from native Windows, not WSL!")
    bot.run(TOKEN)