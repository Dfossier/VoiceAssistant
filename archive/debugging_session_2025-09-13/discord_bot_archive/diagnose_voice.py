"""Diagnostic script for Discord voice connection issues"""
import discord
import asyncio
import sys
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

print("Discord Voice Diagnostic Tool")
print("=" * 50)
print(f"Python: {sys.version}")
print(f"Discord.py: {discord.__version__}")
print(f"Running from: {os.getcwd()}")
print(f"Platform: {sys.platform}")
print("=" * 50)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"\n✅ Bot connected as {client.user}")
    print(f"Guilds: {len(client.guilds)}")
    
    # Check voice permissions
    for guild in client.guilds:
        print(f"\nGuild: {guild.name}")
        bot_member = guild.get_member(client.user.id)
        
        # Check voice channels
        voice_channels = [ch for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]
        print(f"Voice channels: {len(voice_channels)}")
        
        for vc in voice_channels[:2]:  # Check first 2 voice channels
            perms = vc.permissions_for(bot_member)
            print(f"\n  Channel: {vc.name}")
            print(f"  - View: {perms.view_channel}")
            print(f"  - Connect: {perms.connect}")
            print(f"  - Speak: {perms.speak}")
            print(f"  - Use Voice Activity: {perms.use_voice_activation}")
    
    # Try minimal connection
    print("\n🔧 Testing voice connection...")
    for guild in client.guilds:
        for vc in guild.voice_channels:
            if vc.permissions_for(guild.get_member(client.user.id)).connect:
                try:
                    print(f"\nAttempting to connect to: {vc.name}")
                    voice = await vc.connect(timeout=10.0, reconnect=False)
                    print("✅ Successfully connected!")
                    await asyncio.sleep(2)
                    await voice.disconnect()
                    print("✅ Successfully disconnected!")
                    await client.close()
                    return
                except Exception as e:
                    print(f"❌ Failed: {type(e).__name__}: {e}")
    
    await client.close()

@client.event
async def on_error(event, *args, **kwargs):
    print(f"❌ Error in {event}: {sys.exc_info()}")

try:
    client.run(TOKEN)
except Exception as e:
    print(f"\n❌ Fatal error: {e}")