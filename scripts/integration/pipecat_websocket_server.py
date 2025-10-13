"""
Pipecat WebSocket Server Example
Based on Pipecat 0.0.83 documentation and implementation
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from loguru import logger

# Pipecat imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.frames.frames import Frame, TextFrame, LLMMessagesFrame, EndFrame
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.ai_services import STTService, TTSService
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

# Import our local services from windows_pipecat_integration
# We'll use simplified versions that work with Pipecat's architecture
from pipecat.services.openai import WhisperSTTService
from pipecat.services.openai_api_llm import OpenAIApiLLMService
from pipecat.services.ai_services import AIService


class LocalWhisperSTTService(STTService):
    """Local Whisper STT service for Pipecat"""
    
    def __init__(self, model: str = "tiny.en", **kwargs):
        super().__init__(**kwargs)
        self.model_name = model
        logger.info(f"Initializing Local Whisper with model: {model}")
    
    async def run_stt(self, audio: bytes) -> str:
        """Convert audio to text using local Whisper"""
        # For now, return a test response
        # In production, this would use the actual Whisper model
        return "Test transcription from local Whisper"


class LocalPhi3LLMService(AIService):
    """Local Phi-3 LLM service for Pipecat"""
    
    def __init__(self, model_path: str, **kwargs):
        super().__init__(**kwargs)
        self.model_path = Path(model_path)
        logger.info(f"Initializing Phi-3 from: {model_path}")
    
    async def process_frame(self, frame: Frame, direction) -> Frame:
        """Process LLM frames"""
        if isinstance(frame, LLMMessagesFrame):
            # Extract the last user message
            messages = frame.messages
            if messages:
                last_message = messages[-1]
                if last_message.get('role') == 'user':
                    user_text = last_message.get('content', '')
                    
                    # Generate a response (simplified for testing)
                    response = f"Phi-3 response to: {user_text}"
                    
                    # Add assistant response to context
                    messages.append({
                        'role': 'assistant',
                        'content': response
                    })
                    
                    # Return updated frame with response
                    return LLMMessagesFrame(messages=messages)
        
        return frame


class LocalKokoroTTSService(TTSService):
    """Local Kokoro TTS service for Pipecat"""
    
    def __init__(self, voice: str = "af_sarah", **kwargs):
        super().__init__(**kwargs)
        self.voice = voice
        logger.info(f"Initializing Kokoro TTS with voice: {voice}")
    
    async def run_tts(self, text: str) -> bytes:
        """Convert text to speech using local Kokoro"""
        # For now, return empty audio bytes
        # In production, this would use the actual Kokoro model
        return b""


async def main():
    """Main function to run the Pipecat WebSocket server"""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Model paths
    models_path = Path("/mnt/c/users/dfoss/desktop/localaimodels")
    
    # Initialize services
    stt_service = LocalWhisperSTTService(model="tiny.en")
    
    llm_service = LocalPhi3LLMService(
        model_path=str(models_path / "phi3-mini")
    )
    
    tts_service = LocalKokoroTTSService(voice="af_sarah")
    
    # Create WebSocket server transport with proper parameters
    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=ProtobufFrameSerializer(),
            session_timeout=180,  # 3 minutes
        ),
        host="0.0.0.0",  # Listen on all interfaces
        port=8765,
    )
    
    # Create the pipeline with proper frame flow
    pipeline = Pipeline([
        transport.input(),              # Receive from WebSocket
        stt_service,                    # Speech to text
        OpenAILLMContext(),            # Context aggregation
        llm_service,                   # Language model
        tts_service,                   # Text to speech
        transport.output(),            # Send to WebSocket
    ])
    
    # Create pipeline task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )
    
    # Event handlers
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, websocket):
        logger.info(f"Client connected from {websocket.remote_address}")
        # You can send an initial message or trigger the conversation start here
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant connected via WebSocket."
            }
        ]
        await task.queue_frames([LLMMessagesFrame(messages=messages)])
    
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, websocket):
        logger.info(f"Client disconnected: {websocket.remote_address}")
        # Clean up any resources or state for this client
        await task.queue_frames([EndFrame()])
    
    @transport.event_handler("on_session_timeout")
    async def on_session_timeout(transport, websocket):
        logger.info(f"Session timeout for {websocket.remote_address}")
        await task.cancel()
    
    @transport.event_handler("on_websocket_ready")
    async def on_websocket_ready(transport):
        logger.info("WebSocket server is ready and listening!")
    
    # Run the pipeline
    runner = PipelineRunner()
    
    try:
        logger.info("Starting Pipecat WebSocket server on ws://0.0.0.0:8765")
        await runner.run(task)
    except KeyboardInterrupt:
        logger.info("Shutting down WebSocket server...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())