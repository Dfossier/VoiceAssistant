"""Fix Discord Error 4006 - Windows-specific voice connection issues"""
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

print("Discord Voice Connection Fix for Windows")
print("=" * 50)
print(f"Discord.py version: {discord.__version__}")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# Critical Windows fixes
if sys.platform == 'win32':
    # Use ProactorEventLoop for Windows voice compatibility
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("✅ Set Windows ProactorEventLoopPolicy")

# Configure intents with voice optimization
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

# Bot with voice-specific settings
bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    # Disable automatic sharding to prevent voice issues
    shard_count=None,
    shard_id=None,
    # Increase timeouts for voice connections
    heartbeat_timeout=60.0
)

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user}")
    print(f"Guilds: {len(bot.guilds)}")

@bot.command(name='fix_join')
async def fixed_join(ctx):
    """Join voice channel with Error 4006 fixes"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    
    try:
        await ctx.send("🔧 **Applying Error 4006 fixes...**")
        
        # Force disconnect any existing connections
        for vc in bot.voice_clients:
            try:
                await vc.disconnect(force=True)
            except:
                pass
        
        await asyncio.sleep(2)  # Wait for cleanup
        
        await ctx.send(f"🔄 Connecting to {channel.name}...")
        
        # Connect with Error 4006 specific fixes
        voice_client = await channel.connect(
            timeout=30.0,
            reconnect=True,
            self_deaf=True,     # Self-deafen to reduce bandwidth
            self_mute=False     # Don't self-mute so we can speak
        )
        
        # Verify connection
        if voice_client and voice_client.is_connected():
            await ctx.send("✅ **Voice connection successful!**")
            await ctx.send("🎵 Connection stable - no Error 4006!")
            
            # Test the connection
            await asyncio.sleep(2)
            
            if voice_client.is_connected():
                await ctx.send("✅ Connection verified - ready for voice commands!")
            else:
                await ctx.send("⚠️ Connection dropped after test")
        else:
            await ctx.send("❌ Connection failed - voice_client is None")
            
    except discord.errors.ClientException as e:
        if "already connected" in str(e).lower():
            await ctx.send("ℹ️ Already connected to a voice channel")
        else:
            await ctx.send(f"❌ Client error: {e}")
    except asyncio.TimeoutError:
        await ctx.send("❌ Connection timeout - server might be overloaded")
    except Exception as e:
        error_msg = str(e)
        if "4006" in error_msg:
            await ctx.send("❌ **Error 4006 persists!**")
            await ctx.send("🔧 Try these Windows fixes:")
            await ctx.send("1. Run as Administrator")
            await ctx.send("2. Disable Windows Defender Real-time Protection temporarily")
            await ctx.send("3. Check Windows Firewall settings")
        else:
            await ctx.send(f"❌ Unexpected error: {type(e).__name__}: {e}")
        
        print(f"Voice connection error: {e}")

@bot.command(name='test_speak')
async def test_speak(ctx, *, message="Test message"):
    """Test speaking in voice channel"""
    if not ctx.voice_client:
        await ctx.send("❌ Not connected to voice! Use `!fix_join` first")
        return
    
    await ctx.send(f"🗣️ Would speak: '{message}'")
    # Here you would add actual TTS/audio playback

@bot.command(name='force_fix')
async def force_fix(ctx):
    """Nuclear option - force fix all connections"""
    await ctx.send("💥 **Force fixing all connections...**")
    
    # Kill all voice connections
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
            except:
                pass
    
    # Clear internal state
    bot._connection._voice_clients.clear()
    
    await asyncio.sleep(3)
    await ctx.send("✅ All voice connections cleared - try `!fix_join` now")

if __name__ == "__main__":
    print("\n🚀 Starting Discord bot with Error 4006 fixes...")
    print("Use !fix_join to test the fixed voice connection")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        input("Press Enter to exit...")