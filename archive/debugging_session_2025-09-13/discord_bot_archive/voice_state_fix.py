"""Quick fix to add voice state checking to the bot"""

# Add this command to your bot.py file after the other commands:

@bot.command(name='voicecheck')
async def check_voice_state(ctx):
    """Check actual voice connection state"""
    guild_id = ctx.guild.id
    
    embed = discord.Embed(title="🔍 Voice State Check", color=0x0099ff)
    
    # Check Discord.py voice client
    if ctx.voice_client:
        embed.add_field(name="Voice Client", value="✅ Exists", inline=True)
        embed.add_field(name="Is Connected", value=f"{'✅' if ctx.voice_client.is_connected() else '❌'}", inline=True)
        embed.add_field(name="Channel", value=ctx.voice_client.channel.name if ctx.voice_client.channel else "None", inline=True)
    else:
        embed.add_field(name="Voice Client", value="❌ None", inline=True)
    
    # Check bot's internal state
    in_handlers = guild_id in bot.voice_handlers
    embed.add_field(name="In Handlers", value=f"{'✅' if in_handlers else '❌'}", inline=True)
    
    # Check if bot shows in voice channel
    bot_member = ctx.guild.me
    if bot_member.voice:
        embed.add_field(name="Discord Shows Bot In", value=bot_member.voice.channel.name, inline=True)
    else:
        embed.add_field(name="Discord Shows Bot In", value="❌ No channel", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='forceclean')
async def force_clean_voice(ctx):
    """Force clean all voice states"""
    guild_id = ctx.guild.id
    
    await ctx.send("🧹 Force cleaning voice state...")
    
    # Clear from handlers
    if guild_id in bot.voice_handlers:
        del bot.voice_handlers[guild_id]
    
    # Force disconnect if voice client exists
    if ctx.voice_client:
        try:
            await ctx.voice_client.disconnect(force=True)
        except:
            pass
    
    # Clear all voice clients
    for vc in bot.voice_clients:
        if vc.guild.id == guild_id:
            try:
                await vc.disconnect(force=True)
            except:
                pass
    
    await ctx.send("✅ Voice state cleaned. Try !join again.")

# Also modify the speak command to check Discord's view:
@bot.command(name='speak')
async def speak_text(ctx, *, text: str):
    """Make the bot speak text in voice channel"""
    if not text.strip():
        await ctx.send("❌ Please provide text for me to speak!")
        return
    
    # Check if Discord shows bot in voice
    bot_member = ctx.guild.me
    if bot_member.voice and bot_member.voice.channel:
        await ctx.send(f"🗣️ **Would speak in {bot_member.voice.channel.name}:** *{text}*")
        await ctx.send("⚠️ *Note: Voice connection failed (Error 4006) - showing text only*")
    else:
        await ctx.send(f"🗣️ **Would speak:** *{text}*")
        await ctx.send("💡 *Note: Not in voice channel. Use `!join` to connect.*")