"""Test Discord regions and voice servers"""
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
    print(f'[TEST] Bot ready: {bot.user}')
    
    # List all guilds and voice regions
    for guild in bot.guilds:
        print(f'\n[GUILD] {guild.name} (ID: {guild.id})')
        print(f'  Region: {guild.region if hasattr(guild, "region") else "Unknown"}')
        print(f'  Voice channels:')
        
        for vc in guild.voice_channels:
            print(f'    - {vc.name} (ID: {vc.id})')
            if hasattr(vc, 'rtc_region'):
                print(f'      RTC Region: {vc.rtc_region}')
            print(f'      Bitrate: {vc.bitrate}')
            print(f'      User limit: {vc.user_limit}')

@bot.command()
async def testvc(ctx):
    """Test voice connection with detailed logging"""
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"Testing connection to **{channel.name}**...")
    
    # Try with different settings
    settings = [
        {"timeout": 60.0, "reconnect": False},
        {"timeout": 30.0, "reconnect": False, "self_deaf": True},
        {"timeout": 30.0, "reconnect": False, "self_mute": True},
    ]
    
    for i, setting in enumerate(settings):
        try:
            await ctx.send(f"Attempt {i+1}: {setting}")
            
            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)
                await asyncio.sleep(2)
            
            vc = await channel.connect(**setting)
            
            await ctx.send(f"✅ SUCCESS with settings: {setting}")
            print(f"[SUCCESS] Connected with: {setting}")
            
            # Test the connection
            await asyncio.sleep(3)
            if vc.is_connected():
                await ctx.send("✅ Still connected after 3 seconds!")
                return
            else:
                await ctx.send("❌ Connection dropped")
                
        except Exception as e:
            await ctx.send(f"❌ Failed: {type(e).__name__}")
            print(f"[FAIL] {setting} -> {e}")
            continue
    
    await ctx.send("❌ All connection attempts failed")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left voice channel")

token = os.getenv('DISCORD_BOT_TOKEN')
bot.run(token)