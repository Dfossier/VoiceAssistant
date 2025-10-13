# Discord Bot Setup Instructions

## Overview
The Discord bot is a **separate project** that connects to your backend API. The bot handles Discord interactions while the backend (already built) handles AI processing, file operations, and command execution.

## Prerequisites

1. **Backend API Running** (✅ Already completed)
   - Backend API at `http://localhost:8080`
   - API Key: `your-secure-api-key-here-change-this`

2. **Discord Developer Account**
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Create a bot user

3. **Python Environment** (separate from backend)
   - Python 3.8+
   - New virtual environment

## Step-by-Step Setup

### 1. Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name it (e.g., "AI Assistant Bot")
4. Go to "Bot" section
5. Click "Add Bot"
6. Save the **Bot Token** (you'll need this)
7. Enable these **Privileged Gateway Intents**:
   - Message Content Intent
   - Server Members Intent

### 2. Set Bot Permissions

In the OAuth2 → URL Generator section, select:
- **Scopes**: `bot`, `applications.commands`
- **Bot Permissions**:
  - Send Messages
  - Read Message History
  - Connect (voice)
  - Speak (voice)
  - Use Voice Activity
  - Embed Links
  - Attach Files
  - Add Reactions
  - Use Slash Commands

Copy the generated URL and use it to invite the bot to your server.

## Bot Implementation Examples

### Option A: Simple Text-Only Bot

Create a basic bot that handles text commands:

```python
# simple_bot.py
import discord
from discord.ext import commands
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8080')
BACKEND_API_KEY = os.getenv('BACKEND_API_KEY')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API client
api = httpx.AsyncClient(
    base_url=BACKEND_URL,
    headers={"Authorization": f"Bearer {BACKEND_API_KEY}"},
    timeout=30.0
)

@bot.command()
async def ask(ctx, *, question):
    """Ask the AI assistant a question"""
    async with ctx.typing():
        response = await api.post("/api/conversation/message", json={
            "user_id": str(ctx.author.id),
            "message": question,
            "context": {
                "channel_id": str(ctx.channel.id),
                "current_directory": os.getcwd()
            }
        })
        
        if response.status_code == 200:
            data = response.json()
            await ctx.send(data['response'])
        else:
            await ctx.send("❌ Sorry, I couldn't process that.")

@bot.command()
async def run(ctx, *, command):
    """Execute a command"""
    response = await api.post("/api/exec/command", json={
        "user_id": str(ctx.author.id),
        "command": command,
        "timeout": 30
    })
    
    if response.status_code == 200:
        job_id = response.json()['job_id']
        await ctx.send(f"⚡ Running command... (Job ID: {job_id})")
        
        # Poll for results
        for _ in range(10):
            await asyncio.sleep(2)
            result = await api.get(f"/api/exec/output/{job_id}")
            if result.status_code == 200:
                data = result.json()
                if data['status'] == 'completed':
                    output = data['stdout'] or data['stderr']
                    await ctx.send(f"```\n{output[:1900]}\n```")
                    break

bot.run(DISCORD_TOKEN)
```

### Option B: Voice-Enabled Bot with Pipecat

For voice conversations using Pipecat:

```python
# voice_bot.py
import discord
from discord.ext import commands
import asyncio
from pipecat.pipeline import Pipeline
from pipecat.services.discord import DiscordInputService, DiscordOutputService
from pipecat.services.whisper import WhisperSTTService
from pipecat.services.openai import OpenAITTSService
from pipecat.processors.llm import LLMProcessor
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

class BackendLLMService:
    """Custom LLM service that uses your backend API"""
    def __init__(self, api_client):
        self.api = api_client
    
    async def process(self, text: str, user_id: str) -> str:
        response = await self.api.post("/api/conversation/message", json={
            "user_id": user_id,
            "message": text
        })
        
        if response.status_code == 200:
            return response.json()['response']
        return "I'm having trouble processing that."

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API client
api = httpx.AsyncClient(
    base_url=os.getenv('BACKEND_URL'),
    headers={"Authorization": f"Bearer {os.getenv('BACKEND_API_KEY')}"}
)

@bot.command()
async def join(ctx):
    """Join voice channel"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()
        
        # Create Pipecat pipeline
        pipeline = Pipeline([
            DiscordInputService(voice_client),
            WhisperSTTService(),
            LLMProcessor(BackendLLMService(api)),
            OpenAITTSService(voice_id="nova"),
            DiscordOutputService(voice_client)
        ])
        
        # Store pipeline for this guild
        bot.voice_pipelines[ctx.guild.id] = pipeline
        await pipeline.start()
        
        await ctx.send(f"✅ Joined {channel.name}! Start talking!")
    else:
        await ctx.send("❌ You're not in a voice channel!")

@bot.command()
async def leave(ctx):
    """Leave voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Goodbye!")

bot.voice_pipelines = {}
bot.run(os.getenv('DISCORD_TOKEN'))
```

## Available Commands

### Text Commands
- `!ask <question>` - Ask the AI assistant
- `!debug <error>` - Debug an error
- `!run <command>` - Execute a command
- `!watch <directory>` - Monitor a directory
- `!analyze <file>` - Analyze a file
- `!status` - Check bot status

### Voice Commands (if enabled)
- `!join` - Join your voice channel
- `!leave` - Leave voice channel
- Just talk naturally when bot is in voice channel

## Testing the Bot

1. **Start Backend** (if not already running):
   ```bash
   cd /path/to/backend
   source venv/bin/activate
   PORT=8080 python discord_main.py
   ```

2. **Start Discord Bot**:
   ```bash
   cd /path/to/discord-bot
   source venv/bin/activate
   python bot.py
   ```

3. **Test Commands** in Discord:
   ```
   !ask How do I create a Python virtual environment?
   !run echo "Hello from Discord bot!"
   !debug NameError: name 'x' is not defined
   ```

## Troubleshooting

### Bot Not Responding
1. Check bot has proper permissions in Discord server
2. Verify bot token is correct in `.env`
3. Ensure backend API is running and accessible
4. Check bot logs for errors

### Voice Not Working
1. Ensure bot has voice permissions
2. Install ffmpeg: `sudo apt install ffmpeg`
3. Check Whisper is properly installed
4. Verify microphone permissions in Discord

### API Connection Failed
1. Check backend is running on correct port
2. Verify API key matches in both `.env` files
3. Test backend directly: `curl http://localhost:8080/health`
4. Check firewall/network settings

## Next Steps

1. **Add Error Handling**: Implement proper error handling and retry logic
2. **Add Logging**: Set up comprehensive logging for debugging
3. **Custom Commands**: Add domain-specific commands for your workflow
4. **Persistent State**: Store user preferences and conversation history
5. **Multi-Server Support**: Handle multiple Discord servers properly
6. **Rate Limiting**: Implement rate limiting to prevent abuse

## Resources

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pipecat Documentation](https://github.com/daily-co/pipecat)
- [Discord Developer Portal](https://discord.com/developers/docs)
- Backend API Docs: http://localhost:8080/docs