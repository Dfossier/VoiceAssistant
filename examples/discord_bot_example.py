#!/usr/bin/env python3
"""
Example Discord Bot that connects to the AI Assistant Backend
This is a complete working example you can use as a starting point
"""
import discord
from discord.ext import commands
import httpx
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # You need to set this!
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8080')
BACKEND_API_KEY = os.getenv('BACKEND_API_KEY', 'your-secure-api-key-here-change-this')

if not DISCORD_TOKEN:
    print("❌ Error: DISCORD_TOKEN not set in .env file!")
    print("Please create a .env file with:")
    print("DISCORD_TOKEN=your_bot_token_here")
    sys.exit(1)

# Bot setup with proper intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API client setup
api = httpx.AsyncClient(
    base_url=BACKEND_URL,
    headers={"Authorization": f"Bearer {BACKEND_API_KEY}"},
    timeout=30.0
)

# Store active jobs per user
active_jobs = {}

@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'✅ {bot.user} is now online!')
    print(f'📡 Backend API: {BACKEND_URL}')
    print(f'🔧 Servers: {len(bot.guilds)}')
    
    # Test backend connection
    try:
        response = await api.get("/health")
        if response.status_code == 200:
            print("✅ Backend API is healthy!")
        else:
            print("⚠️ Backend API returned:", response.status_code)
    except Exception as e:
        print("❌ Could not connect to backend:", e)

@bot.command(name='ask', help='Ask the AI assistant a question')
async def ask(ctx, *, question):
    """Ask the AI assistant a question"""
    async with ctx.typing():
        try:
            response = await api.post("/api/conversation/message", json={
                "user_id": str(ctx.author.id),
                "message": question,
                "context": {
                    "channel_id": str(ctx.channel.id),
                    "server_id": str(ctx.guild.id) if ctx.guild else None,
                    "username": str(ctx.author)
                }
            })
            
            if response.status_code == 200:
                data = response.json()
                
                # Split long responses
                response_text = data['response']
                if len(response_text) > 1900:
                    chunks = [response_text[i:i+1900] for i in range(0, len(response_text), 1900)]
                    for chunk in chunks:
                        await ctx.send(chunk)
                else:
                    await ctx.send(response_text)
                
                # Show suggestions if any
                if data.get('suggestions'):
                    await ctx.send(f"💡 **Suggestions**: {', '.join(data['suggestions'])}")
                    
            else:
                await ctx.send(f"❌ Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            await ctx.send(f"❌ Error connecting to AI: {str(e)}")

@bot.command(name='run', help='Execute a command')
async def run(ctx, *, command):
    """Execute a shell command"""
    try:
        # Check if user already has a running job
        if ctx.author.id in active_jobs:
            await ctx.send("⚠️ You already have a command running. Use `!status` to check.")
            return
        
        response = await api.post("/api/exec/command", json={
            "user_id": str(ctx.author.id),
            "command": command,
            "timeout": 30
        })
        
        if response.status_code == 200:
            job_id = response.json()['job_id']
            active_jobs[ctx.author.id] = job_id
            
            await ctx.send(f"⚡ Running: `{command}`\nJob ID: `{job_id[:8]}...`")
            
            # Poll for results
            for i in range(15):  # Max 30 seconds
                await asyncio.sleep(2)
                
                result = await api.get(f"/api/exec/output/{job_id}")
                if result.status_code == 200:
                    data = result.json()
                    
                    if data['status'] == 'completed':
                        del active_jobs[ctx.author.id]
                        
                        embed = discord.Embed(
                            title="✅ Command Completed",
                            color=discord.Color.green() if data['return_code'] == 0 else discord.Color.red()
                        )
                        
                        if data['stdout']:
                            embed.add_field(
                                name="Output",
                                value=f"```\n{data['stdout'][:1000]}\n```",
                                inline=False
                            )
                        
                        if data['stderr']:
                            embed.add_field(
                                name="Errors",
                                value=f"```\n{data['stderr'][:500]}\n```",
                                inline=False
                            )
                        
                        embed.add_field(name="Return Code", value=data['return_code'])
                        embed.add_field(name="Duration", value=f"{data['duration']:.2f}s")
                        
                        await ctx.send(embed=embed)
                        return
                    
                    elif data['status'] == 'error':
                        del active_jobs[ctx.author.id]
                        await ctx.send(f"❌ Command failed: {data.get('stderr', 'Unknown error')}")
                        return
            
            # Timeout
            del active_jobs[ctx.author.id]
            await ctx.send("⏰ Command timed out after 30 seconds")
            
    except Exception as e:
        await ctx.send(f"❌ Error executing command: {str(e)}")

@bot.command(name='debug', help='Debug an error message')
async def debug(ctx, *, error_message):
    """Get help debugging an error"""
    async with ctx.typing():
        # First analyze the error
        response = await api.post("/api/conversation/message", json={
            "user_id": str(ctx.author.id),
            "message": f"Please help me debug this error: {error_message}",
            "context": {
                "is_debugging": True,
                "error_text": error_message
            }
        })
        
        if response.status_code == 200:
            data = response.json()
            
            embed = discord.Embed(
                title="🔧 Debug Analysis",
                description=data['response'][:2000],
                color=discord.Color.blue()
            )
            
            await ctx.send(embed=embed)

@bot.command(name='file', help='Read a file from the system')
async def read_file(ctx, file_path: str, lines: str = None):
    """Read file content"""
    try:
        params = {"path": file_path}
        if lines:
            params["lines"] = lines
        
        response = await api.get("/api/files/content", params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            embed = discord.Embed(
                title=f"📄 {os.path.basename(file_path)}",
                color=discord.Color.blue()
            )
            
            content = data['content']
            if len(content) > 1000:
                content = content[:1000] + "\n..."
            
            embed.add_field(
                name=f"Content (Lines: {data['lines']})",
                value=f"```\n{content}\n```",
                inline=False
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Could not read file: {response.text}")
            
    except Exception as e:
        await ctx.send(f"❌ Error reading file: {str(e)}")

@bot.command(name='watch', help='Start watching a directory for changes')
async def watch(ctx, directory: str):
    """Watch a directory for file changes"""
    try:
        response = await api.post("/api/files/watch", json={
            "user_id": str(ctx.author.id),
            "directory": directory,
            "patterns": ["*.py", "*.js", "*.log"]
        })
        
        if response.status_code == 200:
            await ctx.send(f"👀 Now watching: `{directory}`")
        else:
            await ctx.send(f"❌ Could not watch directory: {response.text}")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='changes', help='Show recent file changes')
async def changes(ctx, limit: int = 5):
    """Show recent file changes"""
    try:
        response = await api.get("/api/files/changes", params={
            "user_id": str(ctx.author.id),
            "limit": limit
        })
        
        if response.status_code == 200:
            data = response.json()
            changes = data['changes']
            
            if not changes:
                await ctx.send("📭 No recent file changes")
                return
            
            embed = discord.Embed(
                title="📝 Recent File Changes",
                color=discord.Color.blue()
            )
            
            for change in changes[:10]:
                embed.add_field(
                    name=f"{change['event_type'].title()} - {os.path.basename(change['path'])}",
                    value=f"`{change['path']}`\n{change['timestamp']}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='status', help='Check bot and backend status')
async def status(ctx):
    """Check bot and backend status"""
    try:
        response = await api.get("/health")
        
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=discord.Color.green() if response.status_code == 200 else discord.Color.red()
        )
        
        embed.add_field(name="Bot", value="✅ Online", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        
        if response.status_code == 200:
            data = response.json()
            services = data['services']
            
            embed.add_field(
                name="Backend API",
                value="✅ Healthy" if data['status'] == 'healthy' else "❌ Unhealthy",
                inline=True
            )
            
            for service, status in services.items():
                embed.add_field(
                    name=service.replace('_', ' ').title(),
                    value="✅" if status else "❌",
                    inline=True
                )
        else:
            embed.add_field(name="Backend API", value="❌ Unreachable", inline=True)
        
        # Add active jobs
        if active_jobs:
            embed.add_field(
                name="Active Jobs",
                value=f"{len(active_jobs)} commands running",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error checking status: {str(e)}")

@bot.command(name='clear', help='Clear your conversation history')
async def clear(ctx):
    """Clear conversation history"""
    try:
        response = await api.delete(f"/api/conversation/{ctx.author.id}")
        
        if response.status_code == 200:
            await ctx.send("🧹 Conversation history cleared!")
        else:
            await ctx.send("❌ Could not clear history")
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ Unknown command. Use `!help` for available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param.name}")
    else:
        await ctx.send(f"❌ Error: {str(error)}")

# Run the bot
if __name__ == "__main__":
    print("🚀 Starting Discord AI Assistant Bot...")
    bot.run(DISCORD_TOKEN)