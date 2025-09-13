"""WebSocket connection management"""
from typing import List, Dict, Any
import json
import asyncio

from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_data[websocket] = {
            "connected_at": asyncio.get_event_loop().time(),
            "client_id": id(websocket)
        }
        logger.info(f"New WebSocket connection: {id(websocket)}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_data.pop(websocket, None)
            logger.info(f"WebSocket disconnected: {id(websocket)}")
            
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            self.disconnect(websocket)
            
    async def broadcast(self, message: Dict[str, Any], exclude: WebSocket = None):
        """Broadcast a message to all connected clients"""
        disconnected = []
        
        for connection in self.active_connections:
            if connection != exclude:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    disconnected.append(connection)
                    
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
            
    async def disconnect_all(self):
        """Disconnect all active connections"""
        for connection in self.active_connections[:]:
            try:
                await connection.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self.disconnect(connection)
                
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)
        
    def get_connection_info(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get information about a specific connection"""
        return self.connection_data.get(websocket, {})