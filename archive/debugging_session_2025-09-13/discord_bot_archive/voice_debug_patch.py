"""Deep voice connection debugging patch"""
import discord.voice_client
import discord.gateway
import logging

logger = logging.getLogger('voice_debug')

# Store originals
_original_connect_websocket = discord.voice_client.VoiceClient.connect_websocket

async def debug_connect_websocket(self):
    """Debug websocket connection"""
    logger.info(f"[VOICE] Starting websocket connection to endpoint: {self.endpoint}")
    logger.info(f"[VOICE] Token: {self.token[:20]}... (truncated)")
    logger.info(f"[VOICE] Session ID: {self.session_id}")
    logger.info(f"[VOICE] Server ID: {self.server_id}")
    logger.info(f"[VOICE] User ID: {self.user.id}")
    
    try:
        result = await _original_connect_websocket(self)
        logger.info(f"[VOICE] Websocket created successfully")
        
        # Log websocket state
        if hasattr(result, 'ws') and result.ws:
            logger.info(f"[VOICE] WebSocket state: {result.ws.state}")
        
        return result
    except discord.ConnectionClosed as e:
        logger.error(f"[VOICE] Connection closed during setup: Code {e.code}")
        if e.code == 4006:
            logger.error("[VOICE] Error 4006: Session no longer valid")
            logger.error("[VOICE] Possible causes:")
            logger.error("  - Multiple bots with same token")
            logger.error("  - Invalid voice session data")  
            logger.error("  - Token permissions issue")
        raise
    except Exception as e:
        logger.error(f"[VOICE] Websocket creation failed: {type(e).__name__}: {e}")
        raise

# Apply patches
discord.voice_client.VoiceClient.connect_websocket = debug_connect_websocket

logger.info("[PATCH] Voice debug patches applied")