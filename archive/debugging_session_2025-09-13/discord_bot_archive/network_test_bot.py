"""Test different network configurations for Discord voice"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
import socket
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger('discord').setLevel(logging.ERROR)
logger = logging.getLogger('network_test')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Bot ready: {bot.user}")

@bot.command()
async def nettest(ctx):
    """Test network connectivity to Discord voice"""
    await ctx.send("🔍 **Network Diagnostic Test**")
    
    # Test 1: Basic connectivity
    await ctx.send("**Test 1: DNS Resolution**")
    try:
        import socket
        voice_endpoint = "c-dfw07-1c36ec2d.discord.media"
        ip = socket.gethostbyname(voice_endpoint)
        await ctx.send(f"✅ DNS OK: {voice_endpoint} → {ip}")
        logger.info(f"DNS resolution successful: {voice_endpoint} → {ip}")
    except Exception as e:
        await ctx.send(f"❌ DNS failed: {e}")
        logger.error(f"DNS resolution failed: {e}")
    
    # Test 2: Port connectivity
    await ctx.send("**Test 2: Port Connectivity**")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, 443))
        sock.close()
        
        if result == 0:
            await ctx.send("✅ Port 443 accessible")
            logger.info("Port 443 connection successful")
        else:
            await ctx.send(f"❌ Port 443 blocked (error {result})")
            logger.error(f"Port 443 connection failed: {result}")
    except Exception as e:
        await ctx.send(f"❌ Port test failed: {e}")
        logger.error(f"Port test failed: {e}")
    
    # Test 3: System info
    await ctx.send("**Test 3: System Info**")
    import platform
    await ctx.send(f"Platform: {platform.system()} {platform.release()}")
    await ctx.send(f"Python: {sys.version.split()[0]}")
    
    # Test 4: Check for WSL
    try:
        with open('/proc/version', 'r') as f:
            version = f.read()
            if 'microsoft' in version.lower() or 'wsl' in version.lower():
                await ctx.send("⚠️ **WARNING: Running in WSL2!**")
                await ctx.send("WSL2 causes Discord voice Error 4006")
                await ctx.send("Bot should run in native Windows")
                logger.warning("Detected WSL2 environment")
            else:
                await ctx.send("✅ Native Linux environment")
    except FileNotFoundError:
        await ctx.send("✅ Windows environment (no /proc/version)")
        logger.info("Windows environment detected")

@bot.command()
async def hostinfo(ctx):
    """Show detailed host information"""
    import platform
    import os
    
    embed = discord.Embed(title="Host Information", color=0x0099ff)
    
    embed.add_field(
        name="System",
        value=f"OS: {platform.system()}\n"
              f"Release: {platform.release()}\n"
              f"Version: {platform.version()}\n"
              f"Machine: {platform.machine()}",
        inline=False
    )
    
    embed.add_field(
        name="Python",
        value=f"Version: {sys.version}\n"
              f"Executable: {sys.executable}",
        inline=False
    )
    
    # Check environment variables that might indicate WSL
    wsl_indicators = []
    for key in os.environ:
        if 'wsl' in key.lower() or 'microsoft' in key.lower():
            wsl_indicators.append(f"{key}={os.environ[key]}")
    
    if wsl_indicators:
        embed.add_field(
            name="⚠️ WSL Indicators",
            value="\n".join(wsl_indicators[:5]),  # Limit to 5
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command() 
async def voicetest(ctx):
    """Test voice connection with different approaches"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    
    await ctx.send("🧪 **Testing Multiple Voice Approaches**")
    
    # Approach 1: Minimal connection
    await ctx.send("**Approach 1: Minimal Connection**")
    try:
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(2)
        
        vc = await channel.connect()
        await asyncio.sleep(1)
        
        if vc.is_connected():
            await ctx.send("✅ Minimal connection successful!")
            await vc.disconnect()
        else:
            await ctx.send("❌ Minimal connection failed")
            
    except Exception as e:
        await ctx.send(f"❌ Minimal: {type(e).__name__}: {str(e)[:100]}")
    
    await asyncio.sleep(3)
    
    # Approach 2: With timeout
    await ctx.send("**Approach 2: With Timeout**")
    try:
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(2)
            
        vc = await channel.connect(timeout=60.0)
        await asyncio.sleep(1)
        
        if vc.is_connected():
            await ctx.send("✅ Timeout connection successful!")
            await vc.disconnect()
        else:
            await ctx.send("❌ Timeout connection failed")
            
    except Exception as e:
        await ctx.send(f"❌ Timeout: {type(e).__name__}: {str(e)[:100]}")
    
    await ctx.send("🏁 **Voice test complete**")

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    logger.info("Starting network test bot...")
    bot.run(token)