"""Try various Discord-specific fixes for Error 4006"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger('discord').setLevel(logging.WARNING)
logger = logging.getLogger('discord_fixes')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Bot ready: {bot.user}")

@bot.command()
async def fix1(ctx):
    """Fix 1: Try different voice region"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"🔧 **Fix 1: Testing different voice regions**")
    
    # Show current region
    current_region = channel.rtc_region or "automatic"
    await ctx.send(f"Current region: `{current_region}`")
    
    # Try to change region if we have permissions
    if ctx.author.guild_permissions.manage_channels:
        regions_to_try = ["us-central", "us-east", "us-west", "us-south"]
        
        for region in regions_to_try:
            if region == current_region:
                continue
                
            try:
                await ctx.send(f"Trying region: `{region}`...")
                await channel.edit(rtc_region=region)
                await asyncio.sleep(2)
                
                # Test connection
                vc = await channel.connect(timeout=15.0, reconnect=False)
                if vc and vc.is_connected():
                    await ctx.send(f"✅ **SUCCESS with region: {region}**")
                    await vc.disconnect()
                    return
                else:
                    await vc.disconnect()
                    
            except Exception as e:
                await ctx.send(f"❌ Region {region} failed: {str(e)[:50]}")
    else:
        await ctx.send("⚠️ Need Manage Channels permission to test regions")

@bot.command()
async def fix2(ctx):
    """Fix 2: Try with Discord app closed"""
    await ctx.send("🔧 **Fix 2: Discord Desktop App Interference**")
    await ctx.send("**IMPORTANT:** Close Discord desktop app completely")
    await ctx.send("1. Right-click Discord in system tray")  
    await ctx.send("2. Select 'Quit Discord'")
    await ctx.send("3. Wait 10 seconds")
    await ctx.send("4. Use `!testconnect` to test")
    await ctx.send("*Discord desktop app can interfere with bot voice connections*")

@bot.command()
async def fix3(ctx):
    """Fix 3: Try different connection parameters"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send("🔧 **Fix 3: Different connection parameters**")
    
    connection_tests = [
        {"timeout": 5.0, "reconnect": False, "name": "Fast timeout"},
        {"timeout": 60.0, "reconnect": False, "name": "Long timeout"},
        {"timeout": 30.0, "reconnect": True, "name": "With reconnect"},
        {"name": "Default parameters"}
    ]
    
    for i, params in enumerate(connection_tests):
        name = params.pop("name")
        await ctx.send(f"Test {i+1}: {name}")
        
        try:
            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)
                await asyncio.sleep(2)
            
            if params:
                vc = await channel.connect(**params)
            else:
                vc = await channel.connect()
                
            await asyncio.sleep(1)
            
            if vc and vc.is_connected():
                await ctx.send(f"✅ **SUCCESS with {name}**")
                await vc.disconnect()
                return
            else:
                await ctx.send(f"❌ {name} failed (not connected)")
                if vc:
                    await vc.disconnect()
                    
        except Exception as e:
            await ctx.send(f"❌ {name} error: {str(e)[:60]}")
        
        await asyncio.sleep(3)
    
    await ctx.send("All connection parameter tests failed")

@bot.command()
async def fix4(ctx):
    """Fix 4: Firewall test"""
    await ctx.send("🔧 **Fix 4: Windows Firewall Check**")
    await ctx.send("**Check these firewall settings:**")
    await ctx.send("1. Windows Security → Firewall & network protection")
    await ctx.send("2. Allow an app through firewall")
    await ctx.send("3. Find 'Python' and ensure both Private/Public are checked")
    await ctx.send("4. If not listed, click 'Allow another app' → Browse → Select:")
    await ctx.send(f"`{sys.executable}`")
    await ctx.send("5. Also check your antivirus isn't blocking Python")

@bot.command()
async def testconnect(ctx):
    """Simple connection test"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"🧪 Testing connection to {channel.name}...")
    
    try:
        vc = await channel.connect(timeout=20.0, reconnect=False)
        await asyncio.sleep(2)
        
        if vc and vc.is_connected():
            await ctx.send("✅ **CONNECTION SUCCESSFUL!**")
            await asyncio.sleep(3)
            await vc.disconnect()
            await ctx.send("👋 Disconnected")
        else:
            await ctx.send("❌ Connection failed (not connected)")
            
    except discord.ClientException as e:
        if "4006" in str(e):
            await ctx.send("❌ **Error 4006 persists**")
            await ctx.send("Try: `!fix1` (regions) or `!fix2` (close Discord app)")
        else:
            await ctx.send(f"❌ Error: {e}")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: {type(e).__name__}")

@bot.command()
async def status(ctx):
    """Show current connection status"""
    embed = discord.Embed(title="Connection Status", color=0x0099ff)
    
    if ctx.voice_client:
        vc = ctx.voice_client
        embed.add_field(
            name="Voice Connection",
            value=f"Connected: {vc.is_connected()}\n"
                  f"Channel: {vc.channel.name}\n"
                  f"Endpoint: {vc.endpoint}",
            inline=False
        )
    else:
        embed.add_field(name="Voice Connection", value="Not connected", inline=False)
    
    # Channel info
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        embed.add_field(
            name="Your Voice Channel",
            value=f"Name: {channel.name}\n"
                  f"Region: {channel.rtc_region or 'automatic'}\n"
                  f"Bitrate: {channel.bitrate//1000}kbps",
            inline=False
        )
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    logger.info("Starting Discord fixes bot...")
    bot.run(token)