#!/usr/bin/env python3
"""
Hybrid serializer that can handle both manual format and Pipecat Protobuf format
This enables Windows compatibility while maintaining full Pipecat support
"""

import asyncio
import json
import struct
import logging
from typing import Optional

from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, TextFrame, Frame
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType

logger = logging.getLogger(__name__)

class HybridFrameSerializer(FrameSerializer):
    """Serializer that handles both manual format and Pipecat Protobuf format"""
    
    def __init__(self):
        super().__init__()
        self.protobuf_serializer = ProtobufFrameSerializer()
        self.setup_completed = False
        
    @property
    def type(self) -> FrameSerializerType:
        """Return binary type to match protobuf"""
        return FrameSerializerType.BINARY
        
    async def setup(self, start_frame: StartFrame):
        """Setup the Protobuf serializer"""
        if not self.setup_completed:
            await self.protobuf_serializer.setup(start_frame)
            self.setup_completed = True
            logger.debug("✅ Protobuf serializer setup completed")
    
    async def serialize(self, frame: Frame) -> Optional[bytes]:
        """Serialize outgoing frame to Protobuf format"""
        try:
            if not self.setup_completed and isinstance(frame, StartFrame):
                await self.setup(frame)
            
            return await self.protobuf_serializer.serialize(frame)
            
        except Exception as e:
            logger.error(f"❌ Failed to serialize frame: {e}")
            return None
    
    async def deserialize(self, data: bytes) -> Optional[Frame]:
        """Deserialize incoming data, trying both formats"""
        logger.info(f"🔍 HybridSerializer: Received {len(data)} bytes")
        
        try:
            # First, try manual format
            manual_frame = await self.parse_manual_format(data)
            if manual_frame:
                logger.info(f"📥 Parsed manual frame: {type(manual_frame).__name__}")
                return manual_frame
                
        except Exception as e:
            logger.debug(f"Manual format parsing failed: {e}")
        
        try:
            # Then try Pipecat Protobuf format
            if self.setup_completed:
                protobuf_frame = await self.protobuf_serializer.deserialize(data)
                if protobuf_frame:
                    logger.info(f"📥 Parsed Protobuf frame: {type(protobuf_frame).__name__}")
                    return protobuf_frame
                    
        except Exception as e:
            logger.debug(f"Protobuf format parsing failed: {e}")
        
        # If neither works, return None
        logger.warning(f"❌ Could not parse message: {len(data)} bytes - showing first 50 bytes: {data[:50]}")
        return None
    
    async def parse_manual_format(self, message: bytes) -> Optional[Frame]:
        """Parse manual format: [frame_type_len][frame_type][data_len][data_json]"""
        if len(message) < 8:  # Minimum size for headers
            return None
            
        try:
            offset = 0
            
            # Read frame type length
            frame_type_len = struct.unpack('!I', message[offset:offset+4])[0]
            offset += 4
            
            if offset + frame_type_len > len(message):
                return None
                
            # Read frame type
            frame_type = message[offset:offset+frame_type_len].decode('utf-8')
            offset += frame_type_len
            
            if offset + 4 > len(message):
                return None
                
            # Read data length
            data_len = struct.unpack('!I', message[offset:offset+4])[0]
            offset += 4
            
            if offset + data_len != len(message):
                return None
                
            # Read and parse data
            data_json = message[offset:offset+data_len].decode('utf-8')
            data = json.loads(data_json)
            
            # Convert to Pipecat frame
            return await self.dict_to_frame(data, frame_type)
            
        except Exception as e:
            logger.debug(f"Manual format parsing error: {e}")
            return None
    
    async def dict_to_frame(self, data: dict, frame_type: str) -> Optional[Frame]:
        """Convert dict data to Pipecat frame"""
        try:
            if 'StartFrame' in frame_type:
                frame = StartFrame(
                    allow_interruptions=data.get('allow_interruptions', False),
                    audio_in_sample_rate=data.get('audio_in_sample_rate', 16000),
                    audio_out_sample_rate=data.get('audio_out_sample_rate', 16000),
                    enable_metrics=data.get('enable_metrics', False),
                    enable_usage_metrics=data.get('enable_usage_metrics', False)
                )
                
                # Setup serializer now that we have a StartFrame
                if not self.setup_completed:
                    await self.setup(frame)
                
                return frame
                
            elif 'InputAudioRawFrame' in frame_type:
                audio_data = data.get('audio', [])
                
                # Handle different audio data formats
                if isinstance(audio_data, list):
                    audio_bytes = bytes(audio_data)
                elif isinstance(audio_data, str):
                    # Base64 encoded audio
                    import base64
                    audio_bytes = base64.b64decode(audio_data)
                else:
                    audio_bytes = audio_data if isinstance(audio_data, bytes) else b''
                
                return InputAudioRawFrame(
                    audio=audio_bytes,
                    sample_rate=data.get('sample_rate', 16000),
                    num_channels=data.get('num_channels', 1)
                )
                
            elif 'TextFrame' in frame_type:
                return TextFrame(text=data.get('text', ''))
                
            else:
                logger.warning(f"⚠️ Unknown manual frame type: {frame_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to convert dict to frame: {e}")
            return None