#!/usr/bin/env python3
"""
Download the correct architecture Opus DLL
"""
import urllib.request
import os
import struct

def get_correct_opus():
    # Remove existing opus.dll (wrong architecture)
    if os.path.exists('opus.dll'):
        os.remove('opus.dll')
        print("🗑️ Removed incorrect opus.dll")
    
    # Check architecture
    is_64bit = struct.calcsize('P') == 8
    
    if is_64bit:
        print("📥 Downloading 64-bit Opus DLL...")
        # URL for 64-bit Opus DLL
        opus_url = "https://github.com/discord/discord-api-docs/files/4031616/libopus-0.x64.dll.zip"
        
        try:
            # Download zip
            urllib.request.urlretrieve(opus_url, "opus_x64.zip")
            
            # Extract
            import zipfile
            with zipfile.ZipFile("opus_x64.zip", 'r') as z:
                for filename in z.namelist():
                    if filename.endswith('.dll'):
                        z.extract(filename)
                        # Rename to opus.dll
                        os.rename(filename, 'opus.dll')
                        print(f"✅ Extracted {filename} as opus.dll")
                        break
            
            # Clean up
            os.remove("opus_x64.zip")
            return True
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    else:
        print("📥 Downloading 32-bit Opus DLL...")
        # 32-bit version
        return False

if __name__ == "__main__":
    if get_correct_opus():
        print("🎉 Correct Opus DLL installed!")
    else:
        print("❌ Please manually download the correct opus.dll:")
        if struct.calcsize('P') == 8:
            print("   Need: 64-bit opus.dll")
        else:
            print("   Need: 32-bit opus.dll")
        print("   From: https://www.dll-files.com/opus.dll.html")