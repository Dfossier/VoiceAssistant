#!/usr/bin/env python3
"""
Force sync slash commands for py-cord bot
Run this once to register commands immediately
"""

import discord
import asyncio
from config import Config

bot = discord.Bot()

@bot.event
async def on_ready():
    print(f"Bot {bot.user} is ready!")
    print("Syncing commands...")
    
    # Force sync commands globally
    await bot.sync_commands()
    
    print("Commands synced! You can now use:")
    print("  /capture - Start voice capture")
    print("  /stop - Stop capture")
    print("  /leave - Leave voice")
    print("  /test - Test AI pipeline")
    print("  /status - Show status")
    
    # Show registered commands
    commands = await bot.fetch_global_commands()
    print(f"\nRegistered {len(commands)} commands:")
    for cmd in commands:
        print(f"  /{cmd.name} - {cmd.description}")
    
    print("\nClosing bot...")
    await bot.close()

# Run the bot briefly just to sync commands
asyncio.run(bot.start(Config.DISCORD_TOKEN))