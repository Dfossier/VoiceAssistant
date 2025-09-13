#!/usr/bin/env python3
"""
Download correct Opus DLL for Discord voice support
"""

import urllib.request
import os
import zipfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpusDownloader")

def download_opus_dll():
    """Download and extract proper Opus DLL"""
    
    # URL for pre-compiled Opus libraries for Windows
    opus_url = "https://archive.mozilla.org/pub/opus/win64/opus_win64.zip"
    zip_filename = "opus_win64.zip"
    
    logger.info("📥 Downloading pre-compiled Opus library for Windows x64...")
    
    try:
        # Download
        urllib.request.urlretrieve(opus_url, zip_filename)
        logger.info(f"✅ Downloaded {zip_filename}")
        
        # Extract
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            # Look for DLL files
            dll_files = [f for f in zip_ref.namelist() if f.endswith('.dll')]
            logger.info(f"📋 Found DLL files: {dll_files}")
            
            for dll_file in dll_files:
                if 'opus' in dll_file.lower():
                    # Extract to current directory
                    zip_ref.extract(dll_file, '.')
                    
                    # Rename to standard name
                    extracted_name = os.path.basename(dll_file)
                    if extracted_name != 'opus.dll':
                        os.rename(extracted_name, 'opus.dll')
                        logger.info(f"✅ Extracted and renamed {extracted_name} to opus.dll")
                    else:
                        logger.info(f"✅ Extracted {extracted_name}")
                    
                    # Clean up
                    os.remove(zip_filename)
                    return True
                    
        logger.error("❌ No Opus DLL found in archive")
        os.remove(zip_filename)
        return False
        
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        
        # Alternative approach - try a different source
        logger.info("🔄 Trying alternative download source...")
        try:
            # Direct DLL download
            dll_url = "https://www.dll-files.com/download/c8fa4d1f6a2b0a7a7e8c2e3d4b5a6c7d/opus.dll"
            urllib.request.urlretrieve(dll_url, "opus.dll")
            logger.info("✅ Downloaded opus.dll from alternative source")
            return True
        except:
            logger.error("❌ Alternative download also failed")
            
        return False

def manual_instructions():
    """Print manual installation instructions"""
    logger.info("💡 Manual installation steps:")
    logger.info("1. Go to: https://www.dll-files.com/opus.dll.html")
    logger.info("2. Download opus.dll (64-bit version)")
    logger.info("3. Place it in this directory:")
    logger.info(f"   {os.getcwd()}")
    logger.info("4. Make sure it's named exactly: opus.dll")

if __name__ == "__main__":
    logger.info("🚀 Starting Opus DLL download...")
    
    if download_opus_dll():
        logger.info("🎉 Opus DLL installed successfully!")
        if os.path.exists("opus.dll"):
            size = os.path.getsize("opus.dll")
            logger.info(f"📁 File size: {size} bytes")
            logger.info("✅ Ready to run Discord voice bot!")
        else:
            logger.error("❌ File not found after download")
    else:
        logger.error("❌ Automatic download failed")
        manual_instructions()