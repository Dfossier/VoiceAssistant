"""Fix Opus loading for Discord voice"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger('discord').setLevel(logging.ERROR)
logger = logging.getLogger('opus_fix')

# Try to load Opus manually
try:
    import discord.opus
    logger.info("discord.opus imported successfully")
    
    # Try to load opus library
    if not discord.opus.is_loaded():
        logger.info("Opus not loaded, attempting to load...")
        
        # Try different methods to load opus
        opus_paths = [
            "opus",
            "libopus",
            "libopus.so",
            "libopus.dll", 
            "opus.dll",
            "./opus.dll",
            "./venv/Scripts/opus.dll",
            r"C:\Windows\System32\opus.dll",
            r"C:\Windows\SysWOW64\opus.dll",
            # Common Discord installation paths
            os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-1.0.9025\modules\discord_voice\discord_voice.node"),
            # Try to find it in current directory
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "opus.dll"),
        ]
        
        for path in opus_paths:
            try:
                discord.opus.load_opus(path)
                if discord.opus.is_loaded():
                    logger.info(f"✅ Successfully loaded Opus from: {path}")
                    break
            except Exception as e:
                logger.debug(f"Failed to load opus from {path}: {e}")
        
        if not discord.opus.is_loaded():
            logger.error("❌ Could not load Opus from any location")
    else:
        logger.info("✅ Opus already loaded")
        
except Exception as e:
    logger.error(f"Error with discord.opus: {e}")

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Bot ready: {bot.user}")
    opus_status = "✅ Loaded" if discord.opus.is_loaded() else "❌ Not Loaded"
    logger.info(f"Opus status: {opus_status}")

@bot.command()
async def opustest(ctx):
    """Test Opus loading"""
    if discord.opus.is_loaded():
        await ctx.send("✅ **Opus is loaded!** Voice should work now.")
    else:
        await ctx.send("❌ **Opus still not loaded.** Need to install Opus library.")
        await ctx.send("**To fix:**")
        await ctx.send("1. Install Opus: `pip install PyOpus`")
        await ctx.send("2. Or download opus.dll to Windows/System32")
        await ctx.send("3. Restart bot and test again")

@bot.command()
async def voicetest(ctx):
    """Test voice with Opus status"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    if not discord.opus.is_loaded():
        await ctx.send("❌ **Cannot test - Opus not loaded!**")
        await ctx.send("Use `!opustest` for fix instructions")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"🧪 **Testing voice with Opus loaded in {channel.name}**")
    
    try:
        voice_client = await channel.connect(timeout=15.0, reconnect=False)
        await asyncio.sleep(2)
        
        if voice_client and voice_client.is_connected():
            await ctx.send("🎉 **SUCCESS! Voice connection working with Opus!**")
            await asyncio.sleep(3)
            await voice_client.disconnect()
            await ctx.send("👋 Disconnected - voice is fixed!")
        else:
            await ctx.send("❌ Connection failed even with Opus")
            
    except discord.ClientException as e:
        if "4006" in str(e):
            await ctx.send("❌ Still getting Error 4006 - may need different Opus version")
        else:
            await ctx.send(f"❌ Different error: {e}")
    except Exception as e:
        await ctx.send(f"❌ Error: {type(e).__name__}")

@bot.command()
async def installfix(ctx):
    """Show install instructions"""
    await ctx.send("🔧 **How to Fix Missing Opus:**")
    await ctx.send("**Method 1 - Install PyOpus:**")
    await ctx.send("```")
    await ctx.send("pip install PyOpus")
    await ctx.send("```")
    await ctx.send("**Method 2 - Download opus.dll:**")
    await ctx.send("1. Download from: https://archive.mozilla.org/pub/opus/win32/")
    await ctx.send("2. Place opus.dll in: C:\\Windows\\System32\\")
    await ctx.send("3. Restart bot")
    await ctx.send("**Method 3 - Reinstall discord.py with voice:**")
    await ctx.send("```")
    await ctx.send("pip uninstall discord.py")
    await ctx.send("pip install discord.py[voice]")
    await ctx.send("```")

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    logger.info("Starting Opus fix bot...")
    bot.run(token)