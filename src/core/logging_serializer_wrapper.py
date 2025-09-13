#!/usr/bin/env python3
"""
Logging wrapper for serializers to debug what's happening
"""

import logging
from typing import Optional
from pipecat.frames.frames import Frame
from pipecat.serializers.base_serializer import FrameSerializer, FrameSerializerType

logger = logging.getLogger(__name__)

class LoggingSerializerWrapper(FrameSerializer):
    """Wrapper that logs all serializer calls"""
    
    def __init__(self, inner_serializer: FrameSerializer):
        super().__init__()
        self.inner_serializer = inner_serializer
        logger.info(f"🔧 LoggingSerializerWrapper created with inner serializer: {type(inner_serializer).__name__}")
        
    @property
    def type(self) -> FrameSerializerType:
        """Return the type of the inner serializer"""
        return self.inner_serializer.type
        
    async def setup(self, frame: Frame):
        """Setup the inner serializer"""
        logger.info(f"📝 LoggingWrapper: setup() called with {type(frame).__name__}")
        await self.inner_serializer.setup(frame)
        
    async def serialize(self, frame: Frame):
        """Serialize a frame"""
        logger.info(f"📤 LoggingWrapper: serialize() called with {type(frame).__name__}")
        result = await self.inner_serializer.serialize(frame)
        if result:
            result_type = type(result).__name__
            result_len = len(result) if hasattr(result, '__len__') else 'unknown'
            logger.info(f"✅ LoggingWrapper: Serialized to {result_len} {result_type}")
        else:
            logger.warning(f"❌ LoggingWrapper: Serialization returned None")
        return result
        
    async def deserialize(self, data) -> Optional[Frame]:
        """Deserialize data to a frame"""
        data_type = type(data).__name__
        data_len = len(data) if hasattr(data, '__len__') else 'unknown'
        logger.info(f"📥 LoggingWrapper: deserialize() called with {data_len} {data_type}")
        
        if isinstance(data, (str, bytes)):
            preview = str(data[:100]) if len(str(data)) > 100 else str(data)
            logger.info(f"📥 LoggingWrapper: Data preview: {preview}")
        else:
            logger.info(f"📥 LoggingWrapper: Unexpected data type: {type(data)}")
        
        try:
            result = await self.inner_serializer.deserialize(data)
            if result:
                logger.info(f"✅ LoggingWrapper: Deserialized to {type(result).__name__}")
            else:
                logger.warning(f"❌ LoggingWrapper: Deserialization returned None")
            return result
        except Exception as e:
            logger.error(f"💥 LoggingWrapper: Exception during deserialization: {e}")
            import traceback
            traceback.print_exc()
            raise