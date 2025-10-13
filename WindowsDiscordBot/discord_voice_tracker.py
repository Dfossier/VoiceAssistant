#!/usr/bin/env python3
"""
Discord Voice Channel State Tracker
Monitors who's in voice channels to enable hybrid audio mode detection
"""

import discord
import logging
from typing import Set, Dict, Optional, Callable
import asyncio

logger = logging.getLogger(__name__)

class DiscordVoiceTracker:
    """Tracks Discord voice channel state for hybrid audio mode detection"""
    
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.current_voice_channel: Optional[discord.VoiceChannel] = None
        self.users_in_channel: Set[str] = set()
        self.local_user_id: Optional[str] = None
        
        # Callbacks
        self.state_change_callback: Optional[Callable] = None
        
        # Set up event listeners
        self.bot.add_listener(self.on_voice_state_update, 'on_voice_state_update')
        self.bot.add_listener(self.on_ready, 'on_ready')
    
    def set_state_change_callback(self, callback: Callable):
        """Set callback for when voice channel state changes"""
        self.state_change_callback = callback
    
    async def on_ready(self):
        """Bot is ready - store local user ID"""
        self.local_user_id = str(self.bot.user.id)
        logger.info(f"👤 Local bot user ID: {self.local_user_id}")
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state changes"""
        # Only track if we're in a voice channel
        if not self.current_voice_channel:
            return
            
        # Check if this affects our current channel
        channel_affected = False
        
        if before.channel == self.current_voice_channel:
            # Someone left our channel
            channel_affected = True
            if str(member.id) in self.users_in_channel:
                self.users_in_channel.remove(str(member.id))
                logger.info(f"👋 {member.display_name} left voice channel")
        
        if after.channel == self.current_voice_channel:
            # Someone joined our channel
            channel_affected = True
            self.users_in_channel.add(str(member.id))
            logger.info(f"👋 {member.display_name} joined voice channel")
        
        if channel_affected:
            await self._notify_state_change()
    
    async def join_voice_channel(self, channel: discord.VoiceChannel):
        """Join a voice channel and start tracking"""
        self.current_voice_channel = channel
        
        # Get current users in channel
        self.users_in_channel = {str(member.id) for member in channel.members}
        
        logger.info(f"🔊 Joined voice channel: {channel.name}")
        logger.info(f"👥 Users in channel: {len(self.users_in_channel)}")
        
        for member in channel.members:
            logger.info(f"  - {member.display_name} ({member.id})")
        
        await self._notify_state_change()
    
    async def leave_voice_channel(self):
        """Leave voice channel and stop tracking"""
        if self.current_voice_channel:
            logger.info(f"👋 Left voice channel: {self.current_voice_channel.name}")
        
        self.current_voice_channel = None
        self.users_in_channel.clear()
        
        await self._notify_state_change()
    
    async def _notify_state_change(self):
        """Notify callback of state change"""
        if self.state_change_callback:
            try:
                await self.state_change_callback(
                    users_in_channel=self.users_in_channel.copy(),
                    local_user_id=self.local_user_id
                )
            except Exception as e:
                logger.error(f"❌ Error in state change callback: {e}")
    
    def get_remote_users(self) -> Set[str]:
        """Get set of remote users (excluding the bot)"""
        if self.local_user_id:
            return self.users_in_channel - {self.local_user_id}
        return self.users_in_channel.copy()
    
    def has_remote_users(self) -> bool:
        """Check if there are remote users in the channel"""
        return len(self.get_remote_users()) > 0
    
    def get_channel_info(self) -> Dict:
        """Get current channel information"""
        return {
            'channel_name': self.current_voice_channel.name if self.current_voice_channel else None,
            'total_users': len(self.users_in_channel),
            'remote_users': len(self.get_remote_users()),
            'users': list(self.users_in_channel)
        }