"""Fix Discord voice region issues"""
import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'[FIX] Bot ready: {bot.user}')

@bot.command()
async def fixregion(ctx):
    """Try to fix voice channel region"""
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("❌ You need Manage Channels permission!")
        return
    
    # List voice channels
    guild = ctx.guild
    await ctx.send("🔍 Checking voice channels...")
    
    for vc in guild.voice_channels:
        region = vc.rtc_region if vc.rtc_region else "automatic"
        await ctx.send(f"**{vc.name}**: Region = `{region}`")
        
        if not vc.rtc_region:
            await ctx.send(f"⚠️ {vc.name} has no region set - this causes Error 4006!")
    
    await ctx.send("\n**To fix:**")
    await ctx.send("1. Right-click the voice channel in Discord")
    await ctx.send("2. Click 'Edit Channel'")
    await ctx.send("3. Go to 'Overview' tab")
    await ctx.send("4. Set 'Region Override' to 'US Central' or your nearest region")
    await ctx.send("5. Save changes")
    await ctx.send("\n**Or I can create a new voice channel with proper settings.**")

@bot.command()
async def createvc(ctx, *, name="Bot Voice Test"):
    """Create a new voice channel with proper settings"""
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.send("❌ You need Manage Channels permission!")
        return
    
    guild = ctx.guild
    
    try:
        # Create voice channel with explicit settings
        channel = await guild.create_voice_channel(
            name=name,
            bitrate=64000,
            user_limit=0,
            rtc_region="us-central"  # Force a region
        )
        
        await ctx.send(f"✅ Created voice channel: **{channel.name}**")
        await ctx.send(f"Region: `{channel.rtc_region}`")
        await ctx.send("Try joining this channel and using `!join`")
        
    except Exception as e:
        await ctx.send(f"❌ Failed to create channel: {e}")

@bot.command()
async def join(ctx):
    """Test join after region fix"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    
    # Show channel info
    await ctx.send(f"📊 **Channel Info:**")
    await ctx.send(f"Name: {channel.name}")
    await ctx.send(f"Region: `{channel.rtc_region if channel.rtc_region else 'Not Set (ERROR!)'}`")
    
    if not channel.rtc_region:
        await ctx.send("❌ **This channel has no region set!**")
        await ctx.send("This causes Error 4006. Please:")
        await ctx.send("1. Set a region for this channel, or")
        await ctx.send("2. Use `!createvc` to create a properly configured channel")
        return
    
    try:
        vc = await channel.connect(timeout=30.0, reconnect=False)
        await ctx.send(f"✅ Connected to **{channel.name}**!")
        
        # Test stability
        await asyncio.sleep(3)
        if vc.is_connected():
            await ctx.send("✅ Connection stable!")
        else:
            await ctx.send("❌ Connection dropped")
            
    except Exception as e:
        await ctx.send(f"❌ Failed: {type(e).__name__}: {str(e)}")

@bot.command() 
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left voice channel")

token = os.getenv('DISCORD_BOT_TOKEN')
bot.run(token)