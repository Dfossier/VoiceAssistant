#!/usr/bin/env python3
"""
Custom JSON Frame Serializer for Pipecat WebSocket Transport

Since Pipecat doesn't have a built-in JSONFrameSerializer, we implement our own
based on the ProtobufFrameSerializer pattern. This allows Discord bots to send
JSON-formatted audio data instead of binary Protobuf.
"""

import json
import base64
import logging
from typing import Any, Dict, Optional

# Import with fallback to avoid dependency issues
try:
    from pipecat.frames.frames import (
        Frame, AudioRawFrame, TextFrame, TranscriptionFrame, 
        LLMMessagesFrame, EndFrame, StartFrame,
        SystemFrame, 
        DataFrame, BotInterruptionFrame,
        CancelFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame,
        TTSSpeakFrame, InputAudioRawFrame, OutputAudioRawFrame,
        TransportMessageFrame, TransportMessageUrgentFrame
    )
    from pipecat.serializers.base_serializer import FrameSerializer
    PIPECAT_AVAILABLE = True
except ImportError as e:
    # Create minimal frame interface for testing
    class Frame:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class AudioRawFrame(Frame):
        def __init__(self, audio, sample_rate=16000, num_channels=1, **kwargs):
            super().__init__(**kwargs)
            self.audio = audio
            self.sample_rate = sample_rate
            self.num_channels = num_channels
    
    class FrameSerializer:
        def serialize(self, frame): pass
        def deserialize(self, data): pass
        async def setup(self): pass
    
    PIPECAT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Pipecat not fully available: {e}")
    
    # Create placeholder classes for all needed frame types
    TextFrame = TranscriptionFrame = Frame
    LLMMessagesFrame = TransportMessageFrame = TransportMessageUrgentFrame = Frame
    StartFrame = EndFrame = SystemFrame = Frame
    InputAudioRawFrame = OutputAudioRawFrame = DataFrame = Frame
    BotInterruptionFrame = CancelFrame = Frame
    UserStartedSpeakingFrame = UserStoppedSpeakingFrame = Frame
    TTSSpeakFrame = Frame

logger = logging.getLogger(__name__)

class JSONFrameSerializer(FrameSerializer):
    """
    Custom JSON serializer for Pipecat frames
    
    Handles conversion between Pipecat frames and JSON format for WebSocket transport.
    Supports audio frames with base64 encoding for binary data.
    """
    
    # Map frame types to JSON message types
    SERIALIZABLE_TYPES = {
        TextFrame: "text",
        AudioRawFrame: "audio_input",
        InputAudioRawFrame: "audio_input",
        OutputAudioRawFrame: "audio_output",
        TTSSpeakFrame: "audio_output",
        TranscriptionFrame: "transcription",
        LLMMessagesFrame: "llm_messages",
        StartFrame: "start",
        EndFrame: "end",
        BotInterruptionFrame: "bot_interruption",
        UserStartedSpeakingFrame: "user_started_speaking",
        UserStoppedSpeakingFrame: "user_stopped_speaking",
        CancelFrame: "cancel"
    }
    
    def __init__(self):
        super().__init__()
        logger.info("✅ JSONFrameSerializer initialized")
        self._deserialization_count = 0
        self._serialization_count = 0
    
    @property
    def type(self) -> str:
        """Return the serializer type (TEXT for JSON)"""
        return "text"
    
    async def setup(self, frame: StartFrame):
        """Setup the serializer (called by transport)"""
        logger.info("🔧 Setting up JSON serializer")
        pass
    
    async def serialize(self, frame: Frame) -> str:
        """
        Serialize a Pipecat frame to JSON string
        
        Args:
            frame: Pipecat frame to serialize
            
        Returns:
            JSON string representation of the frame
        """
        try:
            frame_type = type(frame)
            
            if frame_type not in self.SERIALIZABLE_TYPES:
                logger.warning(f"⚠️ Unsupported frame type for serialization: {frame_type}")
                return json.dumps({"type": "unsupported", "error": f"Unsupported frame type: {frame_type.__name__}"})
            
            message_type = self.SERIALIZABLE_TYPES[frame_type]
            
            # Base message structure
            message = {
                "type": message_type,
                "timestamp": getattr(frame, 'timestamp', None),
                "id": getattr(frame, 'id', None)
            }
            
            # Handle different frame types
            if isinstance(frame, AudioRawFrame):
                # Encode audio data as base64
                audio_b64 = base64.b64encode(frame.audio).decode('utf-8')
                message.update({
                    "data": audio_b64,
                    "sample_rate": getattr(frame, 'sample_rate', 16000),
                    "num_channels": getattr(frame, 'num_channels', 1),
                    "format": "pcm16"  # Assume 16-bit PCM
                })
                
            elif isinstance(frame, TTSSpeakFrame):
                # Handle TTS speak frame (text to be spoken)
                message.update({
                    "text": getattr(frame, 'text', ''),
                    "voice": getattr(frame, 'voice', 'default')
                })
                
            elif isinstance(frame, TextFrame):
                message["text"] = frame.text
                logger.info(f"📤 Serializing TextFrame: '{frame.text[:50]}...'")
                
            elif isinstance(frame, TranscriptionFrame):
                message.update({
                    "text": frame.text,
                    "user_id": getattr(frame, 'user_id', None),
                    "timestamp": getattr(frame, 'timestamp', None)
                })
                
            elif isinstance(frame, LLMMessagesFrame):
                message["messages"] = frame.messages
                
            elif isinstance(frame, TransportMessageFrame):
                # Convert TransportMessageFrame to transport message format
                message.update({
                    "message": frame.message,
                    "urgent": getattr(frame, 'urgent', False)
                })
                
            elif isinstance(frame, (StartFrame, EndFrame)):
                # Control frames - just the type is enough
                pass
            
            result = json.dumps(message)
            logger.debug(f"📤 Serialized {frame_type.__name__} → {len(result)} bytes JSON")
            return result
            
        except Exception as e:
            logger.error(f"❌ Serialization error: {e}")
            return json.dumps({"type": "error", "error": str(e)})
    
    async def deserialize(self, data: str) -> Optional[Frame]:
        """
        Deserialize JSON string to Pipecat frame
        
        Args:
            data: JSON string to deserialize
            
        Returns:
            Pipecat frame instance or None if failed
        """
        self._deserialization_count += 1
        logger.info(f"🔍 Deserialize call #{self._deserialization_count}")
        
        try:
            # More detailed logging
            if isinstance(data, bytes):
                logger.info(f"   → Received bytes: {len(data)} bytes")
                data = data.decode('utf-8')
            else:
                logger.info(f"   → Received string: {len(data)} chars")
                
            # Always show preview regardless of length
            preview = data[:200] + ('...' if len(data) > 200 else '')
            logger.info(f"   → Raw data preview: {preview}")
            
            message = json.loads(data)
            message_type = message.get("type")
            logger.info(f"🔍 Parsed message type: '{message_type}'")
            
            if not message_type:
                logger.warning("⚠️ Message missing 'type' field")
                return None
            
            # Create frame based on message type
            if message_type == "audio_input":
                logger.info("🎤 Processing audio_input message!")
                # Decode base64 audio data - Discord bot sends it as "data"
                audio_b64 = message.get("data", "")
                if not audio_b64:
                    logger.warning("⚠️ Audio message missing 'data' field")
                    logger.warning(f"   → Message keys: {list(message.keys())}")
                    return None
                    
                try:
                    audio_data = base64.b64decode(audio_b64)
                    logger.info(f"🔊 Decoded audio: {len(audio_data)} bytes, sample_rate={message.get('sample_rate', 16000)}")
                except Exception as e:
                    logger.error(f"❌ Failed to decode base64 audio: {e}")
                    logger.error(f"   → Base64 data length: {len(audio_b64)}")
                    logger.error(f"   → Base64 preview: {audio_b64[:50]}...")
                    return None
                
                # Use AudioRawFrame for audio coming from Discord
                # Discord bot sends "channels", but Pipecat expects "num_channels"
                sample_rate = message.get("sample_rate", 16000)
                num_channels = message.get("channels", message.get("num_channels", 1))
                
                frame = InputAudioRawFrame(
                    audio=audio_data,
                    sample_rate=sample_rate,
                    num_channels=num_channels
                )
                logger.info(f"✅ Created InputAudioRawFrame: {len(audio_data)} bytes, {sample_rate}Hz, {num_channels}ch")
                logger.info(f"🔊 Audio data preview: first 10 bytes = {list(audio_data[:10])}")
                return frame
                
            elif message_type == "audio_output":
                # Handle TTS speak command
                text = message.get("text", "")
                if text:
                    frame = TTSSpeakFrame(
                        text=text,
                        voice=message.get("voice", "default")
                    )
                    return frame
                    
            elif message_type == "text":
                text = message.get("text", "")
                if text:
                    return TextFrame(text=text)
                    
            elif message_type == "transcription":
                text = message.get("text", "")
                if text:
                    frame = TranscriptionFrame(text=text)
                    if "user_id" in message:
                        frame.user_id = message["user_id"]
                    return frame
                    
            elif message_type == "llm_messages":
                messages = message.get("messages", [])
                if messages:
                    return LLMMessagesFrame(messages=messages)
                    
            elif message_type == "message":
                msg_content = message.get("message", "")
                urgent = message.get("urgent", False)
                # For now, just return None for transport messages
                # TODO: Handle transport messages when needed
                return None
                    
            elif message_type == "start":
                # Don't create a StartFrame - these are internal pipeline frames
                # The WebSocket transport will handle initialization automatically
                logger.info("📥 Received start message - ignoring (handled by transport)")
                logger.info(f"   → Start message contents: {json.dumps(message, indent=2)}")
                return None
                
            elif message_type == "end":
                return EndFrame()
            
            else:
                logger.warning(f"⚠️ Unknown message type: '{message_type}'")
                logger.warning(f"   → Available message types: audio_input, audio_output, text, transcription, llm_messages, message, start, end")
                logger.warning(f"   → Full message: {json.dumps(message, indent=2)}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            logger.error(f"   → Raw data that failed to parse: {data[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Deserialization error: {e}")
            logger.error(f"   → Error occurred with data type {type(data)}: {str(data)[:500]}")
            return None
            
        logger.warning(f"⚠️ Deserialize fell through to None return for message type: '{message_type}'")
        return None
    
    def frame_to_bytes(self, frame: Frame) -> bytes:
        """Convert frame to bytes (required by FrameSerializer interface)"""
        json_str = self.serialize(frame)
        return json_str.encode('utf-8')
    
    async def bytes_to_frame(self, data: bytes) -> Optional[Frame]:
        """Convert bytes to frame (required by FrameSerializer interface)"""
        try:
            json_str = data.decode('utf-8')
            return await self.deserialize(json_str)
        except UnicodeDecodeError as e:
            logger.error(f"❌ UTF-8 decode error: {e}")
            return None