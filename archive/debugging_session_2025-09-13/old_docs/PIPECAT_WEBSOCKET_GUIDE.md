# Pipecat WebSocket Server Guide (v0.0.83)

## Overview

This guide explains how to properly set up and use `WebsocketServerTransport` in Pipecat 0.0.83. The WebSocket transport enables real-time bidirectional communication between clients and your Pipecat pipeline.

## Key Components

### 1. WebsocketServerTransport

The main transport class that manages WebSocket connections:

```python
from pipecat.transports.websocket.server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

transport = WebsocketServerTransport(
    params=WebsocketServerParams(...),
    host="0.0.0.0",  # Listen on all interfaces
    port=8765,       # WebSocket port
)
```

### 2. WebsocketServerParams

Configuration parameters for the WebSocket server:

```python
params = WebsocketServerParams(
    audio_in_enabled=True,           # Enable audio input from clients
    audio_out_enabled=True,          # Enable audio output to clients
    vad_enabled=True,                # Enable Voice Activity Detection
    vad_analyzer=SileroVADAnalyzer(), # VAD implementation
    vad_audio_passthrough=True,      # Pass audio through VAD
    serializer=ProtobufFrameSerializer(), # Frame serializer
    session_timeout=180,             # Timeout in seconds
    add_wav_header=False,            # Add WAV headers to audio
)
```

### 3. Pipeline Setup

The transport provides `input()` and `output()` methods for the pipeline:

```python
pipeline = Pipeline([
    transport.input(),    # Receives frames from WebSocket clients
    # ... your processors ...
    transport.output(),   # Sends frames to WebSocket clients
])
```

### 4. Event Handlers

WebsocketServerTransport supports four event handlers:

```python
@transport.event_handler("on_client_connected")
async def on_client_connected(transport, websocket):
    """Called when a client connects"""
    logger.info(f"Client connected: {websocket.remote_address}")

@transport.event_handler("on_client_disconnected")
async def on_client_disconnected(transport, websocket):
    """Called when a client disconnects"""
    logger.info(f"Client disconnected: {websocket.remote_address}")

@transport.event_handler("on_session_timeout")
async def on_session_timeout(transport, websocket):
    """Called when a client session times out"""
    logger.info(f"Session timeout: {websocket.remote_address}")

@transport.event_handler("on_websocket_ready")
async def on_websocket_ready(transport):
    """Called when the server is ready to accept connections"""
    logger.info("WebSocket server is ready!")
```

## Complete Working Example

```python
import asyncio
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

async def main():
    # Create transport
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=ProtobufFrameSerializer(),
        ),
        host="0.0.0.0",
        port=8765,
    )
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),
        # Add your processors here
        transport.output(),
    ])
    
    # Create task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True)
    )
    
    # Add event handlers
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, websocket):
        logger.info(f"Client connected: {websocket.remote_address}")
    
    # Run
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())
```

## Important Notes

1. **Module Location Change**: In Pipecat 0.0.83, the import path changed from:
   - OLD: `pipecat.transports.network.websocket_server`
   - NEW: `pipecat.transports.websocket.server`

2. **Frame Serialization**: You must provide a serializer (e.g., `ProtobufFrameSerializer`) for the transport to encode/decode frames.

3. **Single Client Limitation**: The current implementation supports only one client at a time. When a new client connects, the previous one is disconnected.

4. **Audio Format**: Audio is expected as raw PCM data. Use `add_wav_header=True` if clients expect WAV format.

5. **VAD Integration**: Voice Activity Detection can be enabled to automatically detect speech boundaries in audio streams.

## Testing the Server

1. Start the server:
   ```bash
   python test_pipecat_websocket.py
   ```

2. Connect with a WebSocket client:
   ```javascript
   const ws = new WebSocket('ws://localhost:8765');
   ws.on('open', () => console.log('Connected'));
   ws.on('message', (data) => console.log('Received:', data));
   ```

## Debugging Tips

1. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Monitor frame flow:
   ```python
   class DebugProcessor(FrameProcessor):
       async def process_frame(self, frame, direction):
           logger.debug(f"Frame: {type(frame).__name__}")
           yield frame
   ```

3. Check transport state:
   - Verify `transport.input()` and `transport.output()` are both in the pipeline
   - Ensure event handlers are registered before running the pipeline
   - Monitor WebSocket connection state in event handlers

## Common Issues

1. **"Missing module" error**: Install WebSocket support:
   ```bash
   pip install pipecat-ai[websocket]
   ```

2. **No client connection**: Ensure firewall allows the port and host is accessible

3. **Serialization errors**: Verify your serializer supports all frame types in your pipeline

4. **Audio issues**: Check sample rate and channel configuration matches client expectations