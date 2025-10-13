"""Patch for empty modes list in voice gateway"""
import discord.gateway
import logging

logger = logging.getLogger(__name__)

# More direct patch - monkey patch the exact location
_original_initial_connection = discord.gateway.DiscordVoiceWebSocket.initial_connection

async def patched_initial_connection(self, data):
    """Patched version that handles empty modes list"""
    logger.info(f"Voice gateway data received: {data}")
    
    d = data['d']
    modes = d.get('modes', [])
    
    logger.info(f"Available voice modes: {modes}")
    
    # Check if modes is empty - this is the bug
    if not modes:
        logger.warning("Discord sent empty modes list! Using fallback modes.")
        # Common Discord voice modes as fallback
        modes = [
            'xsalsa20_poly1305_lite',
            'xsalsa20_poly1305_suffix', 
            'xsalsa20_poly1305'
        ]
        d['modes'] = modes
        logger.info(f"Using fallback modes: {modes}")
    
    # Now proceed with original logic but with guaranteed non-empty modes
    mode = modes[0]  # This should now be safe
    logger.info(f"Selected voice mode: {mode}")
    
    # Continue with original method logic
    self.mode = mode
    await self.initial_handshake(d)

# Apply the patch
discord.gateway.DiscordVoiceWebSocket.initial_connection = patched_initial_connection

print("[PATCH] Voice gateway patch applied - empty modes list handled")