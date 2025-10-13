"""Final diagnostic tests for persistent Error 4006"""
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger('discord').setLevel(logging.ERROR)
logger = logging.getLogger('final_diagnosis')

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Bot ready: {bot.user}")
    logger.info(f"Discord.py version: {discord.__version__}")

@bot.command()
async def diagnosis(ctx):
    """Final comprehensive diagnosis"""
    await ctx.send("🔬 **Final Error 4006 Diagnosis**")
    
    # 1. Check bot permissions in detail
    await ctx.send("**1. Checking Bot Permissions**")
    bot_member = ctx.guild.me
    guild_perms = bot_member.guild_permissions
    
    # Voice-related permissions
    voice_perms = {
        "Connect": guild_perms.connect,
        "Speak": guild_perms.speak, 
        "Use Voice Activity": guild_perms.use_voice_activation,
        "Move Members": guild_perms.move_members,
        "Mute Members": guild_perms.mute_members,
        "Deafen Members": guild_perms.deafen_members
    }
    
    for perm, has_it in voice_perms.items():
        status = "✅" if has_it else "❌"
        await ctx.send(f"{status} {perm}")
    
    # 2. Check guild/server info
    await ctx.send("**2. Server Information**")
    await ctx.send(f"Server: {ctx.guild.name}")
    await ctx.send(f"Server ID: {ctx.guild.id}")
    await ctx.send(f"Server Region: {getattr(ctx.guild, 'region', 'Unknown')}")
    await ctx.send(f"Server Owner: {ctx.guild.owner}")
    await ctx.send(f"Server Boost Level: {ctx.guild.premium_tier}")
    
    # 3. Bot info
    await ctx.send("**3. Bot Information**")
    await ctx.send(f"Bot ID: {bot.user.id}")
    await ctx.send(f"Bot Created: {bot.user.created_at.strftime('%Y-%m-%d')}")
    await ctx.send(f"In Server Since: {bot_member.joined_at.strftime('%Y-%m-%d') if bot_member.joined_at else 'Unknown'}")
    
    # 4. Voice channel analysis
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await ctx.send("**4. Voice Channel Analysis**")
        await ctx.send(f"Channel: {channel.name}")
        await ctx.send(f"Channel ID: {channel.id}")
        await ctx.send(f"Region: {channel.rtc_region or 'Automatic'}")
        await ctx.send(f"Bitrate: {channel.bitrate}")
        await ctx.send(f"User Limit: {channel.user_limit or 'Unlimited'}")
        await ctx.send(f"Category: {channel.category.name if channel.category else 'None'}")
        
        # Channel permissions
        channel_perms = channel.permissions_for(bot_member)
        critical = ["view_channel", "connect", "speak"]
        for perm in critical:
            has_perm = getattr(channel_perms, perm, False)
            status = "✅" if has_perm else "❌"
            await ctx.send(f"{status} Channel {perm.replace('_', ' ').title()}")

@bot.command()
async def servertest(ctx):
    """Ask user to test in different server"""
    await ctx.send("🔄 **Different Server Test**")
    await ctx.send("**To isolate if this is server-specific:**")
    await ctx.send("1. Create a test Discord server")
    await ctx.send("2. Invite this bot to the new server")
    await ctx.send("3. Try voice connection there")
    await ctx.send("4. Report if Error 4006 persists")
    await ctx.send("*This will tell us if it's your server configuration vs bot/system issue*")

@bot.command()
async def libinfo(ctx):
    """Show library information"""
    import discord as discord_lib  # Avoid name collision
    
    embed = discord_lib.Embed(title="Library Information", color=0x0099ff)
    
    embed.add_field(
        name="Discord Library", 
        value=f"Library: discord.py\nVersion: {discord_lib.__version__}",
        inline=False
    )
    
    embed.add_field(
        name="Python",
        value=f"Version: {sys.version.split()[0]}\nPath: {sys.executable}",
        inline=False
    )
    
    # Check voice libraries
    voice_status = []
    
    # Check Opus
    try:
        import discord.opus
        opus_loaded = discord.opus.is_loaded()
        voice_status.append(f"Opus loaded: {opus_loaded}")
        if not opus_loaded:
            voice_status.append("⚠️ Opus not loaded - voice will fail!")
    except ImportError:
        voice_status.append("❌ discord.opus not available")
    except Exception as e:
        voice_status.append(f"Opus error: {e}")
    
    # Check PyNaCl  
    try:
        import nacl
        voice_status.append(f"PyNaCl: {nacl.__version__}")
    except ImportError:
        voice_status.append("❌ PyNaCl NOT INSTALLED (Required for voice!)")
    
    # Check FFmpeg by trying to find it
    try:
        import shutil
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            voice_status.append(f"FFmpeg: Found at {ffmpeg_path}")
        else:
            voice_status.append("⚠️ FFmpeg: Not found in PATH")
    except Exception as e:
        voice_status.append(f"FFmpeg check error: {e}")
    
    embed.add_field(
        name="Voice Libraries",
        value="\n".join(voice_status),
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def rawtest(ctx):
    """Most basic possible voice test"""
    if not ctx.author.voice:
        await ctx.send("❌ Join a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    await ctx.send(f"🧪 **Raw Voice Test on {channel.name}**")
    
    try:
        # Most minimal possible connection
        logger.info("Starting raw voice connection test")
        voice_client = await channel.connect()
        logger.info(f"Voice client created: {voice_client}")
        
        # Check every second for 10 seconds
        for i in range(10):
            connected = voice_client.is_connected() if voice_client else False
            await ctx.send(f"Second {i+1}: Connected = {connected}")
            
            if not connected:
                await ctx.send("💀 Connection died")
                break
                
            await asyncio.sleep(1)
        
        # Cleanup
        if voice_client:
            await voice_client.disconnect(force=True)
            await ctx.send("🧹 Cleaned up")
            
    except Exception as e:
        await ctx.send(f"❌ Raw test failed: {type(e).__name__}")
        await ctx.send(f"Error: {str(e)}")
        logger.error(f"Raw test exception: {e}")

if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    logger.info("Starting final diagnosis bot...")
    bot.run(token)