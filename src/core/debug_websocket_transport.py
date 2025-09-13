#!/usr/bin/env python3
"""
Debug WebSocket transport using our custom debug input transport
"""

from typing import Optional
from pipecat.transports.websocket.server import WebsocketServerTransport, WebsocketServerParams
from .debug_websocket_server import DebugWebsocketServerInputTransport

class DebugWebsocketServerTransport(WebsocketServerTransport):
    """Debug WebSocket server transport that uses our debug input transport"""
    
    def input(self):
        """Get the debug input transport for receiving client data"""
        if not self._input:
            self._input = DebugWebsocketServerInputTransport(
                self, self._host, self._port, self._params, self._callbacks, name=self._input_name
            )
        return self._input