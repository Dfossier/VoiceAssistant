#!/usr/bin/env python3
"""
Fixed Pipecat pipeline with custom JSON serializer for Discord bot WebSocket communication
"""
import asyncio
import base64
import json
from typing import Optional
from loguru import logger

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.network.websocket_server import WebsocketServerTransport, WebsocketServerParams
from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame, TextFrame
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.services.openai import OpenAILLMService

# Import local services
try:
    from src.core.whisper_pipecat_stt import LocalWhisperSTTService
    from src.core.kokoro_tts import LocalKokoroTTSService
except ImportError:
    logger.warning("Local services not found, using fallback imports")
    LocalWhisperSTTService = None
    LocalKokoroTTSService = None


class DiscordJSONFrameSerializer(FrameSerializer):
    """Custom JSON serializer for Discord bot WebSocket messages"""
    
    @property
    def type(self) -> FrameSerializerType:
        return FrameSerializerType.TEXT
    
    def serialize(self, frame: Frame) -> str | None:
        """Serialize frames to JSON for Discord bot"""
        if isinstance(frame, OutputAudioRawFrame):
            # Send audio back to Discord bot
            return json.dumps({
                "type": "audio_output",
                "data": base64.b64encode(frame.audio).decode('utf-8'),
                "sample_rate": frame.sample_rate,
                "channels": frame.num_channels,
                "format": "pcm16"
            })
        elif isinstance(frame, TextFrame):
            # Send transcriptions/text
            return json.dumps({
                "type": "text",
                "text": frame.text
            })
        return None
    
    def deserialize(self, data: str | bytes) -> Frame | None:
        """Deserialize JSON messages from Discord bot to frames"""
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            message = json.loads(data)
            
            # Handle audio input from Discord bot
            if message.get("type") == "audio_input":
                audio_data = base64.b64decode(message["data"])
                # IMPORTANT: Use InputAudioRawFrame, not AudioRawFrame
                return InputAudioRawFrame(
                    audio=audio_data,
                    sample_rate=message.get("sample_rate", 16000),
                    num_channels=message.get("channels", 1)
                )
            
            # Handle text input (for testing)
            elif message.get("type") == "text_input":
                return TextFrame(text=message["text"])
                
        except Exception as e:
            logger.error(f"Failed to deserialize message: {e}")
            return None


class LocalVoicePipelineFixed:
    """Fixed Local voice pipeline with Pipecat and custom serializer"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.task: Optional[PipelineTask] = None
        self.runner: Optional[PipelineRunner] = None
        
        # Services
        self.stt = None
        self.llm = None
        self.tts = None
        
    async def _initialize_services(self):
        """Initialize services on demand"""
        try:
            # Initialize STT (Whisper)
            if LocalWhisperSTTService and not self.stt:
                logger.info("🎤 Initializing Whisper STT...")
                self.stt = LocalWhisperSTTService()
                
            # Initialize LLM (Phi-3)
            if not self.llm:
                logger.info("🤖 Initializing Phi-3 LLM...")
                self.llm = OpenAILLMService(
                    api_key="dummy",  # Not used for local models
                    base_url="http://localhost:5001/v1",
                    model="phi-3"
                )
                
            # Initialize TTS (Kokoro)
            if LocalKokoroTTSService and not self.tts:
                logger.info("🔊 Initializing Kokoro TTS...")
                self.tts = LocalKokoroTTSService()
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    def create_pipeline(self) -> tuple:
        """Create the Pipecat pipeline with custom serializer"""
        # Create WebSocket transport with custom serializer
        transport_params = WebsocketServerParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=DiscordJSONFrameSerializer()  # Use our custom serializer
        )
        
        transport = WebsocketServerTransport(
            host=self.host,
            port=self.port,
            params=transport_params
        )
        
        # Build pipeline
        pipeline_components = [
            transport.input(),  # WebSocket input
        ]
        
        # Add STT if available
        if self.stt:
            pipeline_components.append(self.stt)
            
        # Add LLM
        if self.llm:
            # Create context aggregator for LLM
            from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
            
            context = OpenAILLMContext(
                messages=[{
                    "role": "system",
                    "content": "You are a helpful AI assistant in a voice conversation. Keep responses concise and natural."
                }]
            )
            
            context_aggregator = self.llm.create_context_aggregator(context)
            pipeline_components.extend([context_aggregator, self.llm])
        
        # Add TTS if available
        if self.tts:
            pipeline_components.append(self.tts)
            
        # Add output
        pipeline_components.append(transport.output())
        
        pipeline = Pipeline(pipeline_components)
        
        return (transport, pipeline)
    
    async def start(self):
        """Start the voice pipeline"""
        logger.info("🚀 Starting Fixed Local Voice Pipeline...")
        
        # Initialize services
        await self._initialize_services()
        
        # Create pipeline
        try:
            transport, pipeline = self.create_pipeline()
            logger.info("✅ Pipeline created successfully")
        except Exception as e:
            logger.error(f"❌ Pipeline creation failed: {e}")
            return False
        
        # Create pipeline task without observers
        self.task = PipelineTask(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=False,  # Disable metrics to avoid observer issues
                enable_usage_metrics=False
            )
        )
        
        # Create runner
        self.runner = PipelineRunner()
        
        logger.info(f"✅ Voice pipeline ready on ws://{self.host}:{self.port}")
        logger.info("📝 Using custom JSON serializer for Discord bot compatibility")
        
        # Start the pipeline
        asyncio.create_task(self.runner.run(self.task))
        
        # Small delay to ensure WebSocket server is listening
        await asyncio.sleep(1)
        
        return True
    
    async def stop(self):
        """Stop the voice pipeline"""
        logger.info("Stopping voice pipeline...")
        if self.task:
            await self.task.cancel()
        logger.info("Voice pipeline stopped")


# Test the pipeline
if __name__ == "__main__":
    async def main():
        pipeline = LocalVoicePipelineFixed()
        await pipeline.start()
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await pipeline.stop()
    
    asyncio.run(main())