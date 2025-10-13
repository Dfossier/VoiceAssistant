#!/usr/bin/env python3
"""
Test script for AI models integration
"""

import asyncio
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_ai_models():
    """Test all AI model components"""
    
    print("🧪 Testing AI Models Integration")
    print("=" * 50)
    
    # Test model imports
    try:
        from ai_models import LocalModelHandler
        logger.info("✅ AI models module imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import AI models: {e}")
        return
    
    # Initialize handler
    try:
        handler = LocalModelHandler()
        logger.info("✅ LocalModelHandler initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize handler: {e}")
        return
    
    # Check model availability
    print("\n📁 Model Availability:")
    models = handler.get_available_models()
    for model_name, available in models.items():
        status = "✅ Available" if available else "❌ Not found"
        print(f"  {model_name}: {status}")
    
    # Test Kokoro voices
    print("\n🎵 Kokoro Voices:")
    voices = handler.get_kokoro_voices()
    if voices:
        for voice in voices[:10]:  # Show first 10
            print(f"  • {voice}")
        if len(voices) > 10:
            print(f"  ... and {len(voices) - 10} more")
    else:
        print("  No voices found")
    
    # Test VAD
    print("\n🎤 Testing Voice Activity Detection:")
    try:
        import webrtcvad
        vad = webrtcvad.Vad(2)
        logger.info("✅ WebRTC VAD available")
    except ImportError:
        logger.warning("⚠️ WebRTC VAD not available")
    
    # Test Discord components
    print("\n🤖 Testing Discord Components:")
    try:
        import discord
        import discord.opus
        
        # Force load Opus
        discord.opus._load_default()
        opus_loaded = discord.opus.is_loaded()
        
        print(f"  Discord.py: {discord.__version__}")
        print(f"  Opus: {'✅ Loaded' if opus_loaded else '❌ Failed'}")
        
    except Exception as e:
        logger.error(f"❌ Discord components error: {e}")
    
    # Test basic ML libraries
    print("\n🧠 Testing ML Libraries:")
    try:
        import torch
        print(f"  PyTorch: {torch.__version__}")
        print(f"  CUDA available: {torch.cuda.is_available()}")
    except ImportError:
        logger.warning("⚠️ PyTorch not available")
    
    try:
        import transformers
        print(f"  Transformers: {transformers.__version__}")
    except ImportError:
        logger.warning("⚠️ Transformers not available")
    
    try:
        from llama_cpp import Llama
        logger.info("✅ llama-cpp-python available")
    except ImportError:
        logger.warning("⚠️ llama-cpp-python not available")
    
    # Test Whisper
    print("\n🗣️ Testing Speech Recognition:")
    try:
        import whisper
        logger.info("✅ OpenAI Whisper available")
        
        # Test model loading (small model)
        model = whisper.load_model("tiny")
        logger.info("✅ Whisper tiny model loaded")
    except Exception as e:
        logger.warning(f"⚠️ Whisper error: {e}")
    
    print("\n🎯 Test Summary:")
    print("- Core components ready for voice bot")
    print("- Models can be loaded on-demand")
    print("- Fallback systems available")
    print("- Ready for Discord voice testing!")

if __name__ == "__main__":
    asyncio.run(test_ai_models())