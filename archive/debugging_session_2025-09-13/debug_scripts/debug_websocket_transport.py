#!/usr/bin/env python3
"""
Debug WebSocket transport - patch to see incoming messages
"""
import json
import logging

logger = logging.getLogger("WebSocketDebug")

# Monkey patch Pipecat's WebSocket transport to add debug logging
def patch_pipecat_websocket():
    """Add debug logging to Pipecat WebSocket transport"""
    try:
        from pipecat.transports.network.websocket_server import WebsocketServerTransport
        
        # Store original method
        original_handle_message = WebsocketServerTransport._handle_message
        
        async def debug_handle_message(self, message):
            """Debug wrapper for message handling"""
            logger.info(f"🔍 Received WebSocket message: {type(message)} - {len(str(message))} chars")
            
            try:
                if isinstance(message, str):
                    data = json.loads(message)
                    msg_type = data.get('type', 'unknown')
                    logger.info(f"📨 Message type: {msg_type}")
                    
                    if msg_type == 'audio_input':
                        audio_data = data.get('data', '')
                        sample_rate = data.get('sample_rate', 'unknown')
                        channels = data.get('channels', 'unknown')
                        format_type = data.get('format', 'unknown')
                        
                        logger.info(f"🎵 Audio message: {len(audio_data)} base64 chars, {sample_rate}Hz, {channels}ch, {format_type}")
                    else:
                        logger.info(f"📋 Message content keys: {list(data.keys())}")
                        
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse message: {e}")
            
            # Call original method
            return await original_handle_message(self, message)
        
        # Apply patch
        WebsocketServerTransport._handle_message = debug_handle_message
        logger.info("✅ Pipecat WebSocket transport patched for debugging")
        
    except ImportError as e:
        logger.error(f"❌ Failed to patch WebSocket transport: {e}")

if __name__ == "__main__":
    patch_pipecat_websocket()