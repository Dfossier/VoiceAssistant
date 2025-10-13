#!/usr/bin/env python3
"""Debug Pipecat component creation"""

import asyncio
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_component_creation():
    """Test creating Pipecat components step by step"""
    
    logger.info("🔍 Starting component creation debug...")
    
    # Test 1: Import check
    try:
        logger.info("📦 Testing imports...")
        from src.core.local_pipecat_services import FasterWhisperSTTService, LocalPhi3LLM, LocalKokoroTTS
        logger.info("✅ Local services imported successfully")
        
        from src.core.json_frame_serializer import JSONFrameSerializer  
        logger.info("✅ JSONFrameSerializer imported successfully")
        
        from src.core.logging_serializer_wrapper import LoggingSerializerWrapper
        logger.info("✅ LoggingSerializerWrapper imported successfully")
        
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams
        logger.info("✅ Pipecat VAD imports successful")
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        traceback.print_exc()
        return
    
    # Test 2: VAD creation
    try:
        logger.info("🔧 Creating VAD...")
        vad_params = VADParams(confidence=0.6, start_secs=0.3, stop_secs=0.5, min_volume=0.6)
        vad = SileroVADAnalyzer(sample_rate=16000, params=vad_params)
        logger.info("✅ VAD created successfully")
    except Exception as e:
        logger.error(f"❌ VAD creation failed: {e}")
        traceback.print_exc()
        return
    
    # Test 3: STT service creation
    try:
        logger.info("🔧 Creating STT service...")
        stt = FasterWhisperSTTService(model="small")
        logger.info("✅ STT service created successfully")
    except Exception as e:
        logger.error(f"❌ STT creation failed: {e}")
        logger.info("🔧 Trying without parameters...")
        try:
            stt = FasterWhisperSTTService()
            logger.info("✅ STT service created without model parameter")
        except Exception as e2:
            logger.error(f"❌ STT creation failed completely: {e2}")
            traceback.print_exc()
            stt = None
    
    # Test 4: Serializer creation
    try:
        logger.info("🔧 Creating serializers...")
        json_serializer = JSONFrameSerializer()
        logger.info("✅ JSON serializer created")
        
        logging_wrapper = LoggingSerializerWrapper(json_serializer)
        logger.info("✅ Logging wrapper created")
        
    except Exception as e:
        logger.error(f"❌ Serializer creation failed: {e}")
        traceback.print_exc()
        return
    
    logger.info("🎉 All core components created successfully!")

if __name__ == "__main__":
    asyncio.run(debug_component_creation())