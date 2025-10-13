"""
Voice connection fix for py-cord Error 4006
Based on discord.py PR #10210
"""
import discord
from discord.ext import commands
import asyncio
import logging

logger = logging.getLogger(__name__)

class FixedVoiceClient(discord.VoiceClient):
    """Custom VoiceClient that handles Error 4006 better"""
    
    async def connect_websocket(self):
        """Override to add better error handling"""
        ws = await super().connect_websocket()
        # Add small delay after websocket creation
        await asyncio.sleep(0.1)
        return ws
    
    async def connect(self, *, reconnect=True, timeout=30.0):
        """Override connect to handle 4006 errors gracefully"""
        try:
            # Set reconnect to False to prevent infinite loops
            return await super().connect(reconnect=False, timeout=timeout)
        except discord.errors.ConnectionClosed as e:
            if e.code == 4006:
                logger.error("Error 4006 detected - voice connection rejected by Discord")
                # Clean up properly
                await self.disconnect(force=True)
                raise
            else:
                raise

async def safe_voice_connect(channel, *, timeout=30.0, cls=None):
    """
    Safely connect to a voice channel with proper error handling
    """
    # Use our fixed client
    if cls is None:
        cls = FixedVoiceClient
        
    # Ensure clean state first
    if channel.guild.voice_client:
        await channel.guild.voice_client.disconnect(force=True)
        await asyncio.sleep(1)
    
    try:
        # Connect with no auto-reconnect
        voice_client = await channel.connect(
            timeout=timeout,
            reconnect=False,
            cls=cls
        )
        
        # Verify connection
        await asyncio.sleep(0.5)
        if voice_client.is_connected():
            return voice_client
        else:
            await voice_client.disconnect(force=True)
            raise Exception("Connection verification failed")
            
    except discord.errors.ConnectionClosed as e:
        if e.code == 4006:
            # Known issue - don't retry
            raise Exception("Discord Error 4006: Voice connection rejected. This is a known Discord/py-cord issue.")
        else:
            raise
    except Exception as e:
        logger.error(f"Voice connection failed: {e}")
        raise