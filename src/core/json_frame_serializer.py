#!/usr/bin/env python3
"""
JSON Frame Serializer for Pipecat
Handles our proven JSON protocol that was working with SimpleAudioWebSocketHandler
"""

import json
import base64
import logging
from typing import Optional, Union
from datetime import datetime

from pipecat.frames.frames import (
    Frame, 
    AudioRawFrame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    TextFrame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    LLMMessagesFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
    ErrorFrame
)
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType

logger = logging.getLogger(__name__)

class JSONFrameSerializer(FrameSerializer):
    """
    JSON-based frame serializer that works with our proven Discord bot protocol
    
    Message format:
    {
        "type": "audio_input|text_input|transcription|audio_output|...",
        "data": "base64_encoded_for_audio_or_text",
        "sample_rate": 16000,
        "channels": 1,
        "format": "pcm|wav",
        "timestamp": 1234567890.123,
        "metadata": {...}
    }
    """
    
    @property
    def type(self) -> FrameSerializerType:
        """Return TEXT type since we use JSON"""
        return FrameSerializerType.TEXT
        
    async def serialize(self, frame: Frame) -> Optional[str]:
        """Convert Pipecat frames to JSON messages"""
        try:
            message = {}
            
            # Audio frames
            if isinstance(frame, OutputAudioRawFrame):
                message = {
                    "type": "audio_output",
                    "data": base64.b64encode(frame.audio).decode('utf-8'),
                    "sample_rate": frame.sample_rate,
                    "channels": frame.num_channels,
                    "format": "pcm",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, TranscriptionFrame):
                message = {
                    "type": "transcription",
                    "text": frame.text,
                    "user_id": frame.user_id,
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, InterimTranscriptionFrame):
                message = {
                    "type": "interim_transcription",
                    "text": frame.text,
                    "user_id": frame.user_id,
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, TextFrame):
                message = {
                    "type": "text_output",
                    "text": frame.text,
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, TTSStartedFrame):
                message = {
                    "type": "tts_started",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, TTSStoppedFrame):
                message = {
                    "type": "tts_stopped", 
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, UserStartedSpeakingFrame):
                message = {
                    "type": "user_started_speaking",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, UserStoppedSpeakingFrame):
                message = {
                    "type": "user_stopped_speaking",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, StartFrame):
                message = {
                    "type": "start",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, EndFrame):
                message = {
                    "type": "end",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, CancelFrame):
                message = {
                    "type": "cancel",
                    "timestamp": datetime.utcnow().timestamp()
                }
                
            elif isinstance(frame, ErrorFrame):
                message = {
                    "type": "error",
                    "error": frame.error,
                    "timestamp": datetime.utcnow().timestamp()
                }
            else:
                logger.warning(f"Unknown frame type for serialization: {type(frame).__name__}")
                return None
                
            serialized = json.dumps(message)
            logger.debug(f"Serialized {type(frame).__name__} to JSON: {len(serialized)} bytes")
            return serialized
            
        except Exception as e:
            logger.error(f"Error serializing frame: {e}")
            return None
            
    async def deserialize(self, data: Union[str, bytes]) -> Optional[Frame]:
        """Convert JSON messages to Pipecat frames"""
        try:
            # Handle both string and bytes input
            if isinstance(data, bytes):
                data = data.decode('utf-8')
                
            message = json.loads(data)
            msg_type = message.get("type")
            
            logger.debug(f"Deserializing JSON message type: {msg_type}")
            
            # Audio input from Discord bot
            if msg_type == "audio_input":
                audio_data = base64.b64decode(message["data"])
                frame = InputAudioRawFrame(
                    audio=audio_data,
                    sample_rate=message.get("sample_rate", 16000),
                    num_channels=message.get("channels", 1)
                )
                logger.info(f"✅ Deserialized audio input: {len(audio_data)} bytes")
                return frame
                
            # Text input from Discord bot
            elif msg_type == "text_input":
                frame = TextFrame(text=message["text"])
                logger.info(f"✅ Deserialized text input: {message['text']}")
                return frame
                
            # Control messages
            elif msg_type == "start":
                return StartFrame()
                
            elif msg_type == "end":
                return EndFrame()
                
            elif msg_type == "cancel":
                return CancelFrame()
                
            else:
                logger.warning(f"Unknown message type for deserialization: {msg_type}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, data: {data[:100] if isinstance(data, str) else data[:100].decode('utf-8', errors='ignore')}")
            return None
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            return None