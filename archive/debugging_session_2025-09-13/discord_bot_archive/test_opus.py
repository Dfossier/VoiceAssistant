#!/usr/bin/env python3
"""
Test Opus codec availability for Discord audio
"""

import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpusTest")

def test_opus_availability():
    """Test if Opus codec is available"""
    logger.info("🔍 Testing Opus codec availability...")
    
    # Test py-cord's opus support
    try:
        import discord
        logger.info(f"✅ Discord.py version: {discord.__version__}")
        
        # Check if opus is loaded
        if hasattr(discord, 'opus'):
            if discord.opus.is_loaded():
                logger.info("✅ Opus library is loaded")
                opus_info = {
                    'version': getattr(discord.opus, '_lib', 'unknown'),
                    'encoder_available': hasattr(discord.opus, 'Encoder'),
                    'decoder_available': hasattr(discord.opus, 'Decoder')
                }
                logger.info(f"📋 Opus info: {opus_info}")
            else:
                logger.error("❌ Opus library is NOT loaded")
                logger.info("🔧 Trying to load Opus...")
                try:
                    discord.opus.load_opus()
                    if discord.opus.is_loaded():
                        logger.info("✅ Opus loaded successfully after manual load")
                    else:
                        logger.error("❌ Failed to load Opus even after manual attempt")
                except Exception as e:
                    logger.error(f"❌ Opus load error: {e}")
        else:
            logger.error("❌ No opus module found in discord library")
            
    except ImportError as e:
        logger.error(f"❌ Failed to import discord: {e}")
        return False
        
    # Test if FFmpeg is available (needed for audio processing)
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            logger.info(f"✅ FFmpeg available: {version_line}")
        else:
            logger.warning("⚠️ FFmpeg found but returned error")
    except FileNotFoundError:
        logger.error("❌ FFmpeg not found in PATH")
        logger.info("💡 Install FFmpeg: https://ffmpeg.org/download.html")
    except Exception as e:
        logger.error(f"❌ FFmpeg test error: {e}")
        
    # Test PyNaCl (required for voice)
    try:
        import nacl
        logger.info(f"✅ PyNaCl available: {nacl.__version__}")
        
        # Test if we can create opus encoder/decoder
        try:
            import nacl.secret
            logger.info("✅ NaCl secret module available")
        except Exception as e:
            logger.error(f"❌ NaCl components error: {e}")
            
    except ImportError:
        logger.error("❌ PyNaCl not available")
        logger.info("💡 Install: pip install PyNaCl")
        
    return True

if __name__ == "__main__":
    logger.info("🚀 Starting Opus codec test...")
    test_opus_availability()
    logger.info("✅ Opus test complete")