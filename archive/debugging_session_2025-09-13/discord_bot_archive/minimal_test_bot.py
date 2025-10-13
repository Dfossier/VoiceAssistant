"""Minimal Discord bot to test voice connection on Windows"""
import discord
from discord.ext import commands
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

print(f"Discord.py version: {discord.__version__}")
print(f"Bot token loaded: {'✅' if TOKEN else '❌'}")

# Simple intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Simple bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is ready!")
    print(f"Guilds: {len(bot.guilds)}")

@bot.command()
async def test_join(ctx):
    """Minimal voice join test"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    try:
        # Very simple connection attempt
        channel = ctx.author.voice.channel
        await ctx.send(f"🔄 Attempting to connect to {channel.name}...")
        
        # Disconnect any existing connection
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await asyncio.sleep(1)
        
        # Simple connect with minimal parameters
        voice = await channel.connect(timeout=15.0)
        await ctx.send("✅ Connected successfully!")
        
        # Wait 3 seconds then disconnect
        await asyncio.sleep(3)
        await voice.disconnect()
        await ctx.send("👋 Disconnected")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {type(e).__name__}: {e}")
        print(f"Voice error: {e}")

@bot.command()
async def test_speak(ctx, *, text="Hello World"):
    """Test text to speech without voice connection"""
    await ctx.send(f"🗣️ Would speak: {text}")

# Run with minimal setup
if __name__ == "__main__":
    print("Starting minimal Discord bot test...")
    bot.run(TOKEN)