"""Bot with session reset to fix Error 4006"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# Simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger('discord').setLevel(logging.ERROR)
logger = logging.getLogger('session_reset')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Bot ready: {bot.user}")

@bot.command()
async def resetjoin(ctx):
    """Join with session reset"""
    if not ctx.author.voice:
        await ctx.send("❌ You're not in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    logger.info(f"Attempting session reset join to: {channel.name}")
    
    try:
        # 1. Disconnect from ALL voice channels in ALL guilds
        logger.info("Step 1: Full voice disconnect")
        for guild in bot.guilds:
            if guild.voice_client:
                await guild.voice_client.disconnect(force=True)
                logger.info(f"Disconnected from {guild.name}")
        
        # 2. Wait longer for Discord to process the disconnect
        logger.info("Step 2: Waiting for Discord to process disconnection...")
        await asyncio.sleep(5)
        
        # 3. Try to force a new session by reconnecting to Discord gateway
        logger.info("Step 3: Attempting fresh voice connection")
        await ctx.send("🔄 Attempting fresh voice connection...")
        
        # 4. Connect with fresh session
        voice_client = await channel.connect(
            timeout=30.0, 
            reconnect=False
        )
        
        # 5. Verify and report
        await asyncio.sleep(2)
        if voice_client and voice_client.is_connected():
            await ctx.send(f"✅ **Successfully connected to {channel.name}!**")
            logger.info("SUCCESS: Voice connection established")
        else:
            await ctx.send("❌ Connection failed")
            logger.error("Connection failed after reset attempt")
            
    except discord.errors.ClientException as e:
        if "4006" in str(e):
            await ctx.send("❌ Error 4006 persists - trying nuclear reset...")
            logger.error("4006 persists after reset, trying nuclear option")
            
            # Nuclear option: full bot reconnect
            await ctx.send("🔄 **Performing full bot reconnect...**")
            try:
                await bot.close()
                await asyncio.sleep(2)
                # This will cause the bot to restart
                
            except Exception as e2:
                logger.error(f"Nuclear reset failed: {e2}")
                
        else:
            await ctx.send(f"❌ Error: {e}")
            logger.error(f"Other error: {e}")
            
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: {type(e).__name__}")
        logger.error(f"Unexpected error: {e}")

@bot.command()
async def quickjoin(ctx):
    """Quick join without reset (for comparison)"""
    if not ctx.author.voice:
        await ctx.send("❌ You're not in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    
    try:
        voice_client = await channel.connect(timeout=30.0, reconnect=False)
        await asyncio.sleep(2)
        
        if voice_client and voice_client.is_connected():
            await ctx.send(f"✅ Quick join successful: {channel.name}")
        else:
            await ctx.send("❌ Quick join failed")
            
    except Exception as e:
        await ctx.send(f"❌ Quick join error: {e}")

@bot.command()
async def leave(ctx):
    """Clean leave"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("👋 Left voice channel")
    else:
        await ctx.send("❌ Not in a voice channel")

@bot.command()
async def nukeclean(ctx):
    """Nuclear cleanup - disconnect from everything"""
    count = 0
    for guild in bot.guilds:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)
            count += 1
    
    await ctx.send(f"🧹 Nuked {count} voice connections")
    await asyncio.sleep(3)
    await ctx.send("✅ Ready for fresh connection attempts")

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    logger.info("Starting session reset bot...")
    bot.run(token)