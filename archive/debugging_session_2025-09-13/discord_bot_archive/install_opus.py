#!/usr/bin/env python3
"""
Download and install Opus library for Discord voice support
"""

import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpusInstaller")

def download_opus_dll():
    """Download Opus DLL for Windows"""
    logger.info("🔄 Downloading Opus DLL for Windows...")
    
    # Direct link to Opus DLL (from a reliable source)
    opus_url = "https://github.com/discord/opus/releases/download/v1.3.1/libopus-0.x64.dll"
    opus_filename = "libopus-0.dll"
    
    try:
        # Download the file
        logger.info(f"📥 Downloading from: {opus_url}")
        urllib.request.urlretrieve(opus_url, opus_filename)
        
        # Check if file was downloaded
        if os.path.exists(opus_filename):
            file_size = os.path.getsize(opus_filename)
            logger.info(f"✅ Downloaded {opus_filename} ({file_size} bytes)")
            return True
        else:
            logger.error("❌ Download failed - file not found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        logger.info("💡 Manual installation:")
        logger.info("   1. Go to: https://github.com/xiph/opus/releases")
        logger.info("   2. Download opus-1.3.1-win32.zip or opus-1.3.1-win64.zip")
        logger.info("   3. Extract opus.dll or libopus-0.dll to this directory")
        return False

if __name__ == "__main__":
    if download_opus_dll():
        logger.info("🎉 Opus DLL installed successfully!")
        logger.info("💡 You can now run the Discord voice bot")
    else:
        logger.error("❌ Failed to install Opus DLL")
        logger.info("💡 Please install manually or try using conda install opus")