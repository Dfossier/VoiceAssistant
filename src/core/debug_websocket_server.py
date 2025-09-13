#!/usr/bin/env python3
"""
Debug WebSocket server to understand what messages are being received
"""

import logging
import asyncio
from pipecat.transports.websocket.server import WebsocketServerInputTransport, WebsocketServerCallbacks
from pipecat.frames.frames import InputAudioRawFrame
import websockets

logger = logging.getLogger(__name__)

class DebugWebsocketServerInputTransport(WebsocketServerInputTransport):
    """Debug version of WebSocket server input transport"""
    
    async def _client_handler(self, websocket: websockets.WebSocketServerProtocol):
        """Handle individual client connections with detailed logging"""
        logger.info(f"🔌 DEBUG: New client connection from {websocket.remote_address}")
        
        if self._websocket:
            await self._websocket.close()
            logger.warning("Only one client connected, using new connection")

        self._websocket = websocket

        # Notify
        await self._callbacks.on_client_connected(websocket)

        # Create a task to monitor the websocket connection
        if not self._monitor_task and self._params.session_timeout:
            self._monitor_task = self.create_task(
                self._monitor_websocket(websocket, self._params.session_timeout)
            )

        # Handle incoming messages with detailed logging
        try:
            message_count = 0
            async for message in websocket:
                message_count += 1
                logger.info(f"📨 DEBUG: Received message #{message_count}")
                logger.info(f"📨 DEBUG: Message type: {type(message)}")
                logger.info(f"📨 DEBUG: Message length: {len(message) if hasattr(message, '__len__') else 'N/A'}")
                
                # Log first bytes if it's bytes
                if isinstance(message, bytes):
                    logger.info(f"📨 DEBUG: First 50 bytes: {message[:50]}")
                elif isinstance(message, str):
                    logger.info(f"📨 DEBUG: Text message preview: {message[:100]}")
                else:
                    logger.info(f"📨 DEBUG: Unknown message type: {message}")
                
                if not self._params.serializer:
                    logger.warning(f"⚠️  DEBUG: No serializer configured, skipping message #{message_count}")
                    continue

                logger.info(f"🔄 DEBUG: Attempting to deserialize message #{message_count}")
                
                try:
                    frame = await self._params.serializer.deserialize(message)
                    
                    if not frame:
                        logger.warning(f"❌ DEBUG: Deserialization returned None for message #{message_count}")
                        continue

                    logger.info(f"✅ DEBUG: Successfully deserialized message #{message_count} to {type(frame).__name__}")

                    if isinstance(frame, InputAudioRawFrame):
                        logger.info(f"🎵 DEBUG: Pushing audio frame from message #{message_count}")
                        await self.push_audio_frame(frame)
                    else:
                        logger.info(f"🔄 DEBUG: Pushing frame {type(frame).__name__} from message #{message_count}")
                        await self.push_frame(frame)
                        
                except Exception as e:
                    logger.error(f"💥 DEBUG: Exception deserializing message #{message_count}: {e}")
                    import traceback
                    logger.error(f"💥 DEBUG: Traceback: {traceback.format_exc()}")
                    
        except Exception as e:
            logger.error(f"💥 DEBUG: Exception in client handler: {e.__class__.__name__} ({e})")
            import traceback
            logger.error(f"💥 DEBUG: Traceback: {traceback.format_exc()}")

        # Notify disconnection
        await self._callbacks.on_client_disconnected(websocket)

        await self._websocket.close()
        self._websocket = None

        logger.info(f"👋 DEBUG: Client {websocket.remote_address} disconnected after {message_count} messages")