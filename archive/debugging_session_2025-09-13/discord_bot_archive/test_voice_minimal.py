"""Minimal test to diagnose Error 4006"""
import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Test with minimal intents
intents = discord.Intents.default()
intents.voice_states = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'[TEST] Bot logged in as {client.user}')
    print(f'[TEST] Guilds: {len(client.guilds)}')
    
    # Print debug info
    for guild in client.guilds:
        print(f'[TEST] Guild: {guild.name} (ID: {guild.id})')
        
        # Find a voice channel
        for channel in guild.voice_channels:
            print(f'[TEST] Found voice channel: {channel.name}')
            
            # Try minimal connection
            try:
                print('[TEST] Attempting connection with NO parameters...')
                vc = await channel.connect()
                print('[TEST] SUCCESS! Connected to voice!')
                await asyncio.sleep(5)
                await vc.disconnect()
                break
            except Exception as e:
                print(f'[TEST] FAILED: {type(e).__name__}: {e}')
                
                # Try with reconnect=False
                try:
                    print('[TEST] Attempting with reconnect=False...')
                    vc = await channel.connect(reconnect=False)
                    print('[TEST] SUCCESS with reconnect=False!')
                    await asyncio.sleep(5)
                    await vc.disconnect()
                    break
                except Exception as e2:
                    print(f'[TEST] FAILED again: {type(e2).__name__}: {e2}')
            break
    
    print('[TEST] Test complete. Shutting down...')
    await client.close()

token = os.getenv('DISCORD_BOT_TOKEN')
if not token:
    print('[ERROR] No DISCORD_BOT_TOKEN in .env file!')
else:
    print('[TEST] Starting minimal voice test...')
    print('[TEST] If this fails with 4006, regenerate your bot token!')
    client.run(token)