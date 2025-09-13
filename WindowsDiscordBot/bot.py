"""Windows Discord Bot - Optimized for native voice support"""
import asyncio
import discord
from discord.ext import commands
import discord.errors
import logging
import sys
from pathlib import Path

# Apply voice gateway patch first
import voice_fix_patch

# Local imports
from config import Config
from backend_client import BackendClient
from voice_handler import WindowsVoiceHandler
from enhanced_voice_handler import create_voice_handler

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Validate configuration
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

# Set up Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

# Initialize bot
bot = commands.Bot(
    command_prefix=Config.COMMAND_PREFIX,
    intents=intents,
    help_command=None
)

# Bot state
bot.voice_handlers = {}
bot.backend_client = None

@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")
    
    # Initialize backend client
    try:
        bot.backend_client = BackendClient(
            base_url=Config.BACKEND_API_URL,
            api_key=Config.BACKEND_API_KEY
        )
        
        # Test backend connection
        if await bot.backend_client.health_check():
            logger.info("Backend connection successful")
        else:
            logger.warning("Backend health check failed, but continuing...")
            
    except Exception as e:
        logger.error(f"Failed to initialize backend client: {e}")
        bot.backend_client = None

@bot.event
async def on_disconnect():
    """Called when bot disconnects"""
    logger.info("Bot disconnected from Discord")

@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler"""
    logger.exception(f"Error in event {event}")

# Graceful shutdown
async def shutdown_handler():
    """Handle graceful shutdown"""
    logger.info("Bot shutting down...")
    
    # Disconnect from all voice channels first
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                logger.info(f"Disconnecting from voice channel in guild {guild.name}")
                await guild.voice_client.disconnect(force=True)
            except Exception as e:
                logger.error(f"Error disconnecting from voice in guild {guild.name}: {e}")
    
    # Clean up voice handlers
    for guild_id, handler in list(bot.voice_handlers.items()):
        try:
            await handler.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up voice handler for guild {guild_id}: {e}")
    
    # Clear collections
    bot.voice_handlers.clear()
    
    # Close backend client
    if bot.backend_client:
        try:
            await bot.backend_client.close()
        except Exception as e:
            logger.error(f"Error closing backend client: {e}")

@bot.command(name='help')
async def help_command(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 AI Voice Assistant Commands",
        description="Windows-optimized Discord bot with voice capabilities",
        color=0x00ff00
    )
    
    embed.add_field(
        name="🗣️ Voice Commands",
        value="`!join` - Join your voice channel\n"
              "`!leave` - Leave voice channel\n"
              "`!speak <text>` - Make bot speak text\n"
              "`!force_disconnect` - Emergency cleanup",
        inline=False
    )
    
    embed.add_field(
        name="💬 Chat Commands", 
        value="`!ask <question>` - Ask AI a question\n"
              "`!run <command>` - Execute system command\n"
              "`!debug` - Analyze recent file changes\n"
              "`!status` - Show system status\n"
              "`!permissions` - Check bot permissions",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Voice Usage",
        value="1. Join a voice channel\n"
              "2. Use `!join` to connect the bot\n" 
              "3. Start talking naturally!\n"
              "4. Bot responds with voice + text",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='join')
async def join_voice(ctx):
    """Join the user's voice channel (simplified version)"""
    logger.info(f"Join command received from {ctx.author}")
    
    if not ctx.author.voice:
        await ctx.send("❌ You're not connected to a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    logger.info(f"Target voice channel: {channel.name}")
    
    # Comprehensive permission check
    bot_member = ctx.guild.me
    permissions = channel.permissions_for(bot_member)
    
    # Required permissions for Discord voice
    required_perms = {
        'view_channel': permissions.view_channel,
        'connect': permissions.connect,
        'speak': permissions.speak,
        'use_voice_activation': permissions.use_voice_activation,
        'priority_speaker': permissions.priority_speaker,
        'stream': permissions.stream,
        'use_embedded_activities': permissions.start_embedded_activities if hasattr(permissions, 'start_embedded_activities') else False
    }
    
    # Check critical permissions
    missing_critical = []
    if not permissions.view_channel:
        missing_critical.append("View Channel")
    if not permissions.connect:
        missing_critical.append("Connect")  
    if not permissions.speak:
        missing_critical.append("Speak")
    
    if missing_critical:
        await ctx.send(f"❌ **Missing critical permissions:** {', '.join(missing_critical)}\n"
                      f"🔧 **Fix:** Have server admin grant these permissions in voice channel settings")
        return
    
    # Check optional but helpful permissions
    missing_optional = []
    if not permissions.use_voice_activation:
        missing_optional.append("Use Voice Activity")
    if not permissions.priority_speaker:
        missing_optional.append("Priority Speaker")
    if not permissions.stream:
        missing_optional.append("Video/Screen Share")
    
    # Display permission status
    embed = discord.Embed(title="🔐 Permission Check", color=0x00ff00)
    embed.add_field(
        name="✅ Critical Permissions", 
        value=f"View Channel: ✅\nConnect: ✅\nSpeak: ✅",
        inline=True
    )
    
    if missing_optional:
        embed.add_field(
            name="⚠️ Optional Permissions Missing",
            value="\n".join(f"❌ {perm}" for perm in missing_optional),
            inline=True
        )
    else:
        embed.add_field(
            name="✅ Optional Permissions",
            value="All voice permissions granted!",
            inline=True
        )
    
    # Bot role information
    bot_roles = [role.name for role in bot_member.roles if role.name != "@everyone"]
    embed.add_field(
        name="🎭 Bot Roles",
        value=", ".join(bot_roles) if bot_roles else "No special roles",
        inline=False
    )
    
    # Channel-specific info
    embed.add_field(
        name="📊 Channel Info",
        value=f"Name: {channel.name}\n"
              f"Users: {len(channel.members)}\n"
              f"Bitrate: {channel.bitrate//1000}kbps\n"
              f"User limit: {channel.user_limit or 'Unlimited'}",
        inline=False
    )
    
    await ctx.send(embed=embed)
    
    try:
        logger.info(f"Attempting to join voice channel: {channel.name}")
        
        # Disconnect from any existing channel first
        if ctx.voice_client:
            await ctx.voice_client.disconnect(force=True)
            await asyncio.sleep(1)
        
        # Extra cleanup for any guild voice clients
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)
            await asyncio.sleep(1)
        
        # Use exact parameters that worked in fix_voice_region.py
        voice_client = await channel.connect(timeout=30.0, reconnect=False)
        
        logger.info(f"Voice client created: {voice_client}")
        logger.info(f"Voice client connected: {voice_client.is_connected() if voice_client else 'None'}")
        
        # Wait to verify connection is stable
        await asyncio.sleep(2)
        
        if voice_client and voice_client.is_connected():
            await ctx.send(f"✅ **Connected to {channel.name}!**")
            logger.info(f"Successfully connected to voice channel: {channel.name}")
            
            # Skip voice handler for now - just maintain connection
            await ctx.send("✅ **Voice connected** (handler disabled for testing)")
        else:
            raise Exception("Voice connection failed or dropped")
            
    except discord.errors.ClientException as e:
        logger.error(f"Discord client error: {e}")
        await ctx.send(f"❌ Discord error: {str(e)}")
    except asyncio.TimeoutError:
        logger.error("Voice connection timed out")
        await ctx.send("❌ Voice connection timed out. Try again.")
    except Exception as e:
        logger.error(f"Error joining voice channel: {e}")
        await ctx.send(f"❌ Failed to join voice channel: {str(e)}")

@bot.command(name='leave')
async def leave_voice(ctx):
    """Leave the current voice channel"""
    if not ctx.voice_client:
        await ctx.send("❌ I'm not connected to a voice channel!")
        return
    
    guild_id = ctx.guild.id
    
    try:
        # Clean up voice handler
        if guild_id in bot.voice_handlers:
            handler = bot.voice_handlers[guild_id]
            if hasattr(handler, 'stop_voice_pipeline'):
                await handler.stop_voice_pipeline()
            elif hasattr(handler, 'cleanup'):
                await handler.cleanup()
            del bot.voice_handlers[guild_id]
        
        # Disconnect
        await ctx.voice_client.disconnect(force=True)
        await ctx.send("👋 Left voice channel!")
        
        logger.info(f"Left voice channel in guild {guild_id}")
        
    except Exception as e:
        logger.error(f"Error leaving voice channel: {e}")
        await ctx.send(f"❌ Error leaving voice channel: {str(e)}")

@bot.command(name='force_disconnect')
async def force_disconnect(ctx):
    """Force disconnect from all voice channels (emergency cleanup)"""
    try:
        disconnected = 0
        
        # Force disconnect from all guilds
        for guild in bot.guilds:
            if guild.voice_client:
                try:
                    await guild.voice_client.disconnect(force=True)
                    logger.info(f"Force disconnected from voice in guild {guild.name}")
                    disconnected += 1
                except Exception as e:
                    logger.error(f"Error force disconnecting from guild {guild.name}: {e}")
        
        # Clear all voice handlers
        bot.voice_handlers.clear()
        
        if disconnected > 0:
            await ctx.send(f"🔧 Force disconnected from {disconnected} voice channel(s)")
        else:
            await ctx.send("ℹ️ No active voice connections found")
            
    except Exception as e:
        logger.error(f"Error during force disconnect: {e}")
        await ctx.send(f"❌ Error during force disconnect: {str(e)}")


@bot.command(name='permissions')
async def check_permissions(ctx):
    """Check bot permissions in detail"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first to check permissions!")
        return
    
    channel = ctx.author.voice.channel
    bot_member = ctx.guild.me
    permissions = channel.permissions_for(bot_member)
    
    # All Discord voice permissions
    voice_perms = {
        '🔍 View Channel': permissions.view_channel,
        '🔌 Connect': permissions.connect,
        '🗣️ Speak': permissions.speak,
        '🎤 Use Voice Activity': permissions.use_voice_activation,
        '📢 Priority Speaker': permissions.priority_speaker,
        '🎥 Video/Stream': permissions.stream,
        '🎮 Use Activities': permissions.start_embedded_activities if hasattr(permissions, 'start_embedded_activities') else False,
        '🔕 Mute Members': permissions.mute_members,
        '🔇 Deafen Members': permissions.deafen_members,
        '↔️ Move Members': permissions.move_members
    }
    
    # Guild-level permissions that might affect voice
    guild_perms = ctx.guild.me.guild_permissions
    guild_voice_perms = {
        '🎤 Use Voice Activity (Guild)': guild_perms.use_voice_activation,
        '📢 Priority Speaker (Guild)': guild_perms.priority_speaker,
        '🎥 Stream (Guild)': guild_perms.stream,
        '🔕 Mute Members (Guild)': guild_perms.mute_members,
        '🔇 Deafen Members (Guild)': guild_perms.deafen_members,
        '↔️ Move Members (Guild)': guild_perms.move_members
    }
    
    embed = discord.Embed(
        title="🔐 Complete Permission Analysis",
        description=f"Permissions for **{channel.name}**",
        color=0x00ff00
    )
    
    # Channel permissions
    granted = [f"✅ {name}" for name, has_perm in voice_perms.items() if has_perm]
    missing = [f"❌ {name}" for name, has_perm in voice_perms.items() if not has_perm]
    
    if granted:
        embed.add_field(
            name="✅ Channel Permissions Granted",
            value="\n".join(granted),
            inline=True
        )
    
    if missing:
        embed.add_field(
            name="❌ Channel Permissions Missing", 
            value="\n".join(missing),
            inline=True
        )
    
    # Guild permissions
    guild_granted = [f"✅ {name}" for name, has_perm in guild_voice_perms.items() if has_perm]
    guild_missing = [f"❌ {name}" for name, has_perm in guild_voice_perms.items() if not has_perm]
    
    if guild_granted or guild_missing:
        embed.add_field(
            name="🏰 Guild-Level Permissions",
            value="\n".join(guild_granted + guild_missing),
            inline=False
        )
    
    # Bot role hierarchy
    bot_top_role = bot_member.top_role
    embed.add_field(
        name="🎭 Bot Role Info",
        value=f"**Highest Role:** {bot_top_role.name}\n"
              f"**Role Position:** {bot_top_role.position}\n"
              f"**Role Color:** {bot_top_role.color}\n"
              f"**Is Bot Role:** {bot_member.premium_since is not None}",
        inline=False
    )
    
    # Critical analysis
    critical_missing = []
    if not permissions.view_channel:
        critical_missing.append("View Channel")
    if not permissions.connect:
        critical_missing.append("Connect")
    if not permissions.speak:
        critical_missing.append("Speak")
    
    if critical_missing:
        embed.add_field(
            name="🚨 CRITICAL ISSUES",
            value=f"**Missing:** {', '.join(critical_missing)}\n"
                  f"**Action:** Grant these permissions immediately!",
            inline=False
        )
        embed.color = 0xff0000
    
    await ctx.send(embed=embed)

@bot.command(name='speak')
async def speak_text(ctx, *, text: str):
    """Make the bot speak text in voice channel"""
    if not text.strip():
        await ctx.send("❌ Please provide text for me to speak!")
        return
    
    guild_id = ctx.guild.id
    
    # Check if bot appears to be in voice (even if connection failed)
    bot_member = ctx.guild.me
    if bot_member.voice and bot_member.voice.channel:
        # Bot shows in channel but voice failed
        await ctx.send(f"🗣️ **Would speak in {bot_member.voice.channel.name}:** *{text}*")
        await ctx.send("⚠️ *Voice connection failed (Error 4006) - text mode only*")
        return
    elif guild_id not in bot.voice_handlers and not ctx.voice_client:
        # Bot not in voice at all
        await ctx.send(f"🗣️ **Would speak:** *{text}*")
        await ctx.send("💡 *Not in voice channel. Use `!join` to connect.*")
        return
    
    try:
        handler = bot.voice_handlers[guild_id]
        await ctx.send(f"🗣️ **Speaking:** *{text[:100]}{'...' if len(text) > 100 else ''}*")
        
        # Try Pipecat pipeline first
        if hasattr(handler, 'pipeline_task') and handler.is_running:
            # Use Pipecat TTS pipeline
            from pipecat.frames.frames import TextFrame
            await handler.pipeline_task.queue_frames([TextFrame(text=text)])
            await ctx.send("✅ Speech queued to Pipecat pipeline!")
        elif hasattr(handler, 'play_text_as_speech'):
            # Fallback to direct TTS
            success = await handler.play_text_as_speech(text)
            if success:
                await ctx.send("✅ Speech played successfully!")
            else:
                await ctx.send("❌ Failed to play speech - check logs for details")
        else:
            # Use backend client directly
            audio_data = await bot.backend_client.text_to_speech(text)
            if audio_data and len(audio_data) > 0:
                await ctx.send("✅ TTS audio generated (no playback handler)")
            else:
                await ctx.send("❌ Failed to generate TTS audio")
            
    except Exception as e:
        logger.error(f"Error with TTS: {e}")
        await ctx.send(f"❌ Error with text-to-speech: {str(e)}")

@bot.command(name='ask')
async def ask_question(ctx, *, question: str):
    """Ask the AI a question"""
    if not bot.backend_client:
        await ctx.send("❌ Backend connection not available!")
        return
    
    if not question.strip():
        await ctx.send("❌ Please ask a question!")
        return
    
    try:
        await ctx.send(f"🤔 Processing: *{question[:100]}...*")
        
        context = {
            "source": "text",
            "channel_id": str(ctx.channel.id),
            "guild_id": str(ctx.guild.id)
        }
        
        response = await bot.backend_client.send_message(
            user_id=str(ctx.author.id),
            message=question,
            context=context
        )
        
        if len(response) > 1900:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)
            
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await ctx.send("❌ Sorry, I couldn't process your question right now.")

@bot.command(name='run')
async def run_command(ctx, *, command: str):
    """Execute a system command"""
    if not bot.backend_client:
        await ctx.send("❌ Backend connection not available!")
        return
    
    if not command.strip():
        await ctx.send("❌ Please provide a command to execute!")
        return
    
    try:
        job_id = await bot.backend_client.execute_command(
            user_id=str(ctx.author.id),
            command=command,
            timeout=30
        )
        
        await ctx.send(f"⚡ Executing command... (Job ID: `{job_id}`)")
        
        # Poll for results
        for attempt in range(15):  # 30 second timeout
            await asyncio.sleep(2)
            
            try:
                output = await bot.backend_client.get_command_output(job_id)
                
                if output.get('status') == 'completed':
                    result = output.get('output', 'No output')
                    if len(result) > 1900:
                        await ctx.send("```\n" + result[:1900] + "\n...\n```")
                    else:
                        await ctx.send(f"```\n{result}\n```")
                    return
                elif output.get('status') == 'failed':
                    error = output.get('error', 'Unknown error')
                    await ctx.send(f"❌ Command failed: {error}")
                    return
                    
            except Exception as e:
                logger.error(f"Error polling command output: {e}")
                
        await ctx.send("⏱️ Command timed out")
        
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        await ctx.send(f"❌ Error executing command: {str(e)}")

@bot.command(name='status')
async def show_status(ctx):
    """Show system status"""
    try:
        # Get backend status
        backend_status = {"status": "disconnected"}
        if bot.backend_client:
            try:
                backend_status = await bot.backend_client.get_api_status()
            except:
                pass
        
        embed = discord.Embed(
            title="🖥️ System Status",
            color=0x00ff00 if backend_status.get("status") == "running" else 0xff0000
        )
        
        # Backend status
        backend_emoji = "✅" if backend_status.get("status") == "running" else "❌"
        embed.add_field(
            name=f"{backend_emoji} Backend API",
            value=f"Status: {backend_status.get('status', 'unknown')}\n"
                  f"URL: {Config.BACKEND_API_URL}",
            inline=False
        )
        
        # Voice status
        voice_active = len(bot.voice_handlers)
        voice_emoji = "🎤" if voice_active > 0 else "🔇"
        embed.add_field(
            name=f"{voice_emoji} Voice Connections",
            value=f"Active: {voice_active}\n"
                  f"Guilds: {list(bot.voice_handlers.keys())}",
            inline=False
        )
        
        # Bot info
        embed.add_field(
            name="🤖 Bot Info",
            value=f"Guilds: {len(bot.guilds)}\n"
                  f"Latency: {round(bot.latency * 1000)}ms",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await ctx.send(f"❌ Error getting status: {str(e)}")

@bot.command(name='restart_backend')
async def restart_backend(ctx):
    """Request backend restart"""
    await ctx.send("⚠️ Backend restart needed to apply fixes")
    await ctx.send("Please run: `python simple_service_manager.py`")
    await ctx.send("Then choose option 4 (Stop Backend) and 1 (Start Backend)")

@bot.command(name='debug')
async def debug_files(ctx):
    """Analyze recent file changes"""
    if not bot.backend_client:
        await ctx.send("❌ Backend connection not available!")
        return
    
    try:
        await ctx.send("🔍 Analyzing recent file changes...")
        
        # This would require additional backend API endpoints
        await ctx.send("📁 Debug functionality requires additional backend implementation")
        
    except Exception as e:
        logger.error(f"Error during debug: {e}")
        await ctx.send(f"❌ Error during debug: {str(e)}")

@bot.command(name='shutdown')
async def shutdown_bot(ctx):
    """Gracefully shutdown the bot (Admin only)"""
    # Check if user is admin/owner
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need administrator permissions to shut down the bot!")
        return
    
    await ctx.send("🛑 **Shutting down bot gracefully...**")
    logger.info(f"Shutdown command issued by {ctx.author}")
    
    # Perform graceful shutdown
    await shutdown_handler()
    
    # Close the bot
    await bot.close()

@bot.command(name='forceleave')
async def force_leave_all(ctx):
    """Force leave all voice channels (Admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need administrator permissions to force disconnect!")
        return
    
    disconnected = 0
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
                disconnected += 1
                logger.info(f"Force disconnected from {guild.name}")
            except Exception as e:
                logger.error(f"Error force disconnecting from {guild.name}: {e}")
    
    # Clear voice handlers
    bot.voice_handlers.clear()
    
    await ctx.send(f"🔌 Force disconnected from {disconnected} voice channels")

@bot.command(name='botinfo')
async def bot_info(ctx):
    """Show detailed bot information"""
    embed = discord.Embed(
        title="🤖 Bot Information",
        color=0x0099ff
    )
    
    # Connection status
    voice_connections = len(bot.voice_clients)
    guilds = len(bot.guilds)
    
    embed.add_field(
        name="🔗 Connections",
        value=f"Guilds: {guilds}\nVoice: {voice_connections}\nLatency: {round(bot.latency * 1000)}ms",
        inline=True
    )
    
    # Version info
    import discord
    embed.add_field(
        name="📋 Version Info",
        value=f"Discord.py: {discord.__version__}\nPython: {sys.version.split()[0]}",
        inline=True
    )
    
    # Voice channels
    if voice_connections > 0:
        voice_info = []
        for vc in bot.voice_clients:
            voice_info.append(f"• {vc.channel.name} ({vc.guild.name})")
        
        embed.add_field(
            name="🎵 Voice Channels",
            value="\n".join(voice_info),
            inline=False
        )
    
    await ctx.send(embed=embed)


if __name__ == "__main__":
    import signal
    import sys
    import os
    import atexit
    
    # Set Windows-specific event loop policy for py-cord
    if sys.platform == 'win32':
        # This is critical for Windows + py-cord compatibility
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Cleanup function that ALWAYS runs
    def cleanup_on_exit():
        logger.info("Cleanup: Disconnecting from all voice channels...")
        try:
            # Force disconnect from all voice channels
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def disconnect_all():
                for vc in bot.voice_clients:
                    try:
                        await vc.disconnect(force=True)
                        logger.info(f"Disconnected from {vc.channel.name}")
                    except:
                        pass
            
            if bot.voice_clients:
                loop.run_until_complete(disconnect_all())
            loop.close()
        except:
            pass
        logger.info("Cleanup complete")
    
    # Register cleanup to run on exit
    atexit.register(cleanup_on_exit)
    
    shutdown_initiated = False
    
    def signal_handler(signum, frame):
        global shutdown_initiated
        if shutdown_initiated:
            logger.warning(f"Force terminating process (PID: {os.getpid()})")
            cleanup_on_exit()
            os._exit(1)
        
        shutdown_initiated = True
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        cleanup_on_exit()
        os._exit(0)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Use bot.run() directly instead of asyncio.run() for better py-cord compatibility
        logger.info("Starting Windows Discord Bot...")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        cleanup_on_exit()
        os._exit(0)
    except SystemExit:
        cleanup_on_exit()
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        cleanup_on_exit()
        os._exit(1)
    finally:
        logger.info("Process terminated")