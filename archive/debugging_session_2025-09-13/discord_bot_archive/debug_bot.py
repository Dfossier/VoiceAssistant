"""Debug bot to isolate voice connection issues"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
from dotenv import load_dotenv

# Apply voice gateway patch BEFORE anything else
import voice_fix_patch

load_dotenv()

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'[DEBUG] Bot ready: {bot.user}')

@bot.command()
async def join(ctx):
    """Ultra minimal join"""
    if not ctx.author.voice:
        await ctx.send("Not in voice channel")
        return
    
    channel = ctx.author.voice.channel
    print(f'[DEBUG] Connecting to: {channel.name}')
    
    try:
        # Absolutely minimal connection
        vc = await channel.connect()
        print(f'[DEBUG] Connected! VC: {vc}')
        print(f'[DEBUG] Is connected: {vc.is_connected()}')
        await ctx.send(f"Connected to {channel.name}")
        
    except Exception as e:
        print(f'[DEBUG] Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        await ctx.send(f"Failed: {e}")

@bot.command()
async def leave(ctx):
    """Leave voice"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left voice")
    else:
        await ctx.send("Not in voice")

@bot.command()
async def shutdown(ctx):
    """Clean shutdown"""
    print('[DEBUG] Shutdown requested')
    for vc in bot.voice_clients:
        print(f'[DEBUG] Disconnecting from {vc.channel.name}')
        await vc.disconnect(force=True)
    await ctx.send("Shutting down...")
    await bot.close()

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    bot.run(token)