#!/usr/bin/env python3
"""
Robust WebSocket client for Discord bot with proper close frame handling
"""

import asyncio
import websockets
import websockets.exceptions
import json
import logging
from typing import Optional, Callable, Any
import traceback

logger = logging.getLogger(__name__)

class RobustWebSocketClient:
    """WebSocket client that handles disconnections gracefully with proper close frames"""
    
    def __init__(self, url: str, on_message: Optional[Callable] = None):
        self.url = url
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.on_message_callback = on_message
        self.is_connected = False
        self.should_reconnect = True
        self.connection_task = None
        self.reconnect_delay = 2.0
        self.max_reconnect_delay = 30.0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
    async def connect(self) -> bool:
        """Connect to WebSocket server with retry logic"""
        if self.is_connected:
            logger.warning("⚠️ Already connected to WebSocket")
            return True
            
        logger.info(f"🔌 Connecting to {self.url}...")
        
        for attempt in range(3):  # Initial connection attempts
            try:
                # Connect with proper WebSocket parameters
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        self.url,
                        ping_interval=20,      # Keep connection alive
                        ping_timeout=10,       # Ping response timeout
                        close_timeout=10,      # Close handshake timeout
                        max_size=2**20,        # 1MB max message size
                        compression=None       # Disable compression for audio
                    ), 
                    timeout=30.0  # 30 second connection timeout
                )
                
                # Test the connection
                await self.websocket.ping()
                self.is_connected = True
                self.reconnect_attempts = 0
                logger.info("✅ Connected to backend WebSocket")
                
                # Start message handler
                if self.on_message_callback:
                    self.connection_task = asyncio.create_task(self._handle_messages())
                
                return True
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Connection attempt {attempt + 1} timed out")
                if attempt < 2:
                    await asyncio.sleep(2)
            except websockets.exceptions.WebSocketException as e:
                logger.warning(f"❌ WebSocket connection attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                        
        logger.error("❌ All initial connection attempts failed")
        return False
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages with reconnection logic"""
        while self.should_reconnect:
            try:
                if not self.websocket:
                    logger.error("❌ WebSocket connection lost, attempting reconnect...")
                    await self._reconnect()
                    continue
                
                # Listen for messages
                async for message in self.websocket:
                    if self.on_message_callback:
                        try:
                            await self.on_message_callback(message)
                        except Exception as e:
                            logger.error(f"❌ Error in message callback: {e}")
                            
            except websockets.exceptions.ConnectionClosedOK:
                logger.info("✅ WebSocket connection closed normally")
                self.is_connected = False
                if self.should_reconnect:
                    await self._reconnect()
                else:
                    break
                    
            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f"⚠️ WebSocket connection closed with error: {e}")
                self.is_connected = False
                if self.should_reconnect:
                    await self._reconnect()
                else:
                    break
                    
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"❌ WebSocket error: {e}")
                self.is_connected = False
                if self.should_reconnect:
                    await self._reconnect()
                else:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error in message handler: {e}")
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                self.is_connected = False
                if self.should_reconnect:
                    await self._reconnect()
                else:
                    break
    
    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Maximum reconnection attempts ({self.max_reconnect_attempts}) reached")
            self.should_reconnect = False
            return
            
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), self.max_reconnect_delay)
        
        logger.info(f"🔄 Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        await asyncio.sleep(delay)
        
        try:
            # Clean up old connection
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass  # Ignore errors during cleanup
                self.websocket = None
            
            # Attempt new connection
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20,
                    compression=None
                ), 
                timeout=30.0
            )
            
            await self.websocket.ping()
            self.is_connected = True
            logger.info(f"✅ Reconnected successfully (attempt {self.reconnect_attempts})")
            
        except Exception as e:
            logger.error(f"❌ Reconnection attempt {self.reconnect_attempts} failed: {e}")
            self.is_connected = False
    
    async def send(self, message: Any) -> bool:
        """Send message with error handling"""
        if not self.is_connected or not self.websocket:
            logger.error("❌ Cannot send message - not connected")
            return False
            
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            elif not isinstance(message, (str, bytes)):
                message = str(message)
                
            await self.websocket.send(message)
            return True
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ Connection closed during send, will reconnect")
            self.is_connected = False
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return False
    
    async def send_binary(self, data: bytes) -> bool:
        """Send binary data"""
        if not self.is_connected or not self.websocket:
            logger.error("❌ Cannot send binary data - not connected")
            return False
            
        try:
            await self.websocket.send(data)
            return True
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ Connection closed during binary send, will reconnect")
            self.is_connected = False
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to send binary data: {e}")
            return False
    
    async def ping(self) -> bool:
        """Ping the WebSocket server"""
        if not self.is_connected or not self.websocket:
            return False
            
        try:
            await self.websocket.ping()
            return True
        except Exception as e:
            logger.error(f"❌ Ping failed: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect gracefully with proper close frame"""
        logger.info("🛑 Disconnecting from WebSocket...")
        
        self.should_reconnect = False
        self.is_connected = False
        
        # Cancel message handler
        if self.connection_task:
            self.connection_task.cancel()
            try:
                await self.connection_task
            except asyncio.CancelledError:
                pass
            
        # Close WebSocket connection properly
        if self.websocket:
            try:
                # Send close frame with proper code
                await self.websocket.close(code=1000, reason="Client disconnecting")
                logger.info("✅ WebSocket connection closed gracefully")
            except Exception as e:
                logger.warning(f"⚠️ Error during WebSocket close: {e}")
            finally:
                self.websocket = None
    
    @property
    def connected(self) -> bool:
        """Check if currently connected"""
        return self.is_connected and self.websocket is not None
        
    def set_reconnect_enabled(self, enabled: bool):
        """Enable/disable automatic reconnection"""
        self.should_reconnect = enabled