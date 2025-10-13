"""
Test Pipecat WebSocket Server with proper frame handling
Compatible with Pipecat 0.0.83
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from loguru import logger

# Pipecat imports
from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    TextFrame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.transports.websocket.server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

# Simple frame serializer for testing
class SimpleFrameSerializer:
    """Simple JSON-based frame serializer for testing"""
    
    async def setup(self, frame):
        """Setup the serializer"""
        pass
    
    async def serialize(self, frame: Frame) -> Optional[str]:
        """Serialize frame to JSON string"""
        if isinstance(frame, TextFrame):
            return json.dumps({
                "type": "text",
                "text": frame.text
            })
        elif isinstance(frame, AudioRawFrame):
            return json.dumps({
                "type": "audio",
                "length": len(frame.audio),
                "sample_rate": frame.sample_rate,
                "channels": frame.num_channels
            })
        elif isinstance(frame, TranscriptionFrame):
            return json.dumps({
                "type": "transcription",
                "text": frame.text,
                "user_id": frame.user_id,
                "timestamp": frame.timestamp
            })
        elif isinstance(frame, TTSStartedFrame):
            return json.dumps({"type": "tts_started"})
        elif isinstance(frame, TTSStoppedFrame):
            return json.dumps({"type": "tts_stopped"})
        elif isinstance(frame, UserStartedSpeakingFrame):
            return json.dumps({"type": "user_started_speaking"})
        elif isinstance(frame, UserStoppedSpeakingFrame):
            return json.dumps({"type": "user_stopped_speaking"})
        else:
            # Log unknown frame types
            logger.debug(f"Unknown frame type: {type(frame).__name__}")
            return None
    
    async def deserialize(self, data: str) -> Optional[Frame]:
        """Deserialize JSON string to frame"""
        try:
            msg = json.loads(data)
            msg_type = msg.get("type")
            
            if msg_type == "text":
                return TextFrame(text=msg.get("text", ""))
            elif msg_type == "audio":
                # In real implementation, would include actual audio data
                return AudioRawFrame(
                    audio=b"",  # Placeholder
                    sample_rate=msg.get("sample_rate", 16000),
                    num_channels=msg.get("channels", 1)
                )
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize message: {e}")
            return None


class EchoProcessor(FrameProcessor):
    """Simple echo processor for testing"""
    
    async def process_frame(self, frame: Frame, direction: FrameDirection) -> AsyncGenerator[Frame, None]:
        """Process frames - echo text frames back"""
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame):
            # Echo the text back
            echo_text = f"Echo: {frame.text}"
            yield TextFrame(text=echo_text)
            
            # Also log it
            logger.info(f"Received text: {frame.text}")
        else:
            # Pass through other frames
            yield frame


class AudioProcessor(FrameProcessor):
    """Process audio frames and simulate STT"""
    
    def __init__(self):
        super().__init__()
        self._audio_buffer = bytearray()
    
    async def process_frame(self, frame: Frame, direction: FrameDirection) -> AsyncGenerator[Frame, None]:
        """Process audio frames"""
        await super().process_frame(frame, direction)
        
        if isinstance(frame, AudioRawFrame):
            # Accumulate audio
            self._audio_buffer.extend(frame.audio)
            
            # Simulate STT after accumulating some audio
            if len(self._audio_buffer) > 16000 * 2:  # ~1 second at 16kHz
                # Clear buffer and generate transcription
                self._audio_buffer.clear()
                
                # Simulate transcription
                yield TranscriptionFrame(
                    text="This is a simulated transcription",
                    user_id="test_user",
                    timestamp=None
                )
            
            # Pass through the audio frame
            yield frame
        else:
            # Pass through other frames
            yield frame


async def main():
    """Run the test WebSocket server"""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create WebSocket transport
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                min_speech_duration=0.1,
                max_speech_duration=30.0,
                sample_rate=16000
            ),
            vad_audio_passthrough=True,
            serializer=SimpleFrameSerializer(),
            session_timeout=180,
        ),
        host="0.0.0.0",
        port=8765,
    )
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),      # WebSocket input
        AudioProcessor(),       # Process audio frames
        EchoProcessor(),       # Echo text frames
        transport.output(),    # WebSocket output
    ])
    
    # Create task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )
    
    # Event handlers
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, websocket):
        logger.info(f"Client connected: {websocket.remote_address}")
        # Send welcome message
        welcome_frame = TextFrame(text="Welcome to Pipecat WebSocket Server!")
        await task.queue_frames([welcome_frame])
    
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, websocket):
        logger.info(f"Client disconnected: {websocket.remote_address}")
    
    @transport.event_handler("on_websocket_ready")
    async def on_websocket_ready(transport):
        logger.info("WebSocket server ready on ws://0.0.0.0:8765")
        logger.info("Connect with a WebSocket client to test")
    
    # Run the pipeline
    runner = PipelineRunner()
    
    try:
        await runner.run(task)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())