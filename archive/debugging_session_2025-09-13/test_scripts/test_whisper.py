#!/usr/bin/env python3
"""Test Whisper directly"""
import tempfile
import base64
import subprocess
import os

# Create a test audio file (silence)
def create_test_audio():
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir='/mnt/c/temp')
    temp_file.close()
    
    # Create 1 second of silence in WAV format
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=16000",
        "-t", "1", "-y", temp_file.name
    ]
    subprocess.run(cmd, capture_output=True)
    return temp_file.name

def test_whisper():
    audio_file = create_test_audio()
    print(f"Created test audio: {audio_file}")
    
    # Convert to Windows path
    windows_path = "C:" + audio_file[6:].replace("/", "\\") if audio_file.startswith("/mnt/c/") else audio_file
    print(f"Windows path: {windows_path}")
    
    # Test Whisper
    whisper_python = "/mnt/c/users/dfoss/desktop/localaimodels/Whisper/whisper-env/Scripts/python.exe"
    
    whisper_code = f'''
import whisper
import json

try:
    model = whisper.load_model("base")
    result = model.transcribe(r"{windows_path}")
    print(json.dumps({{"text": result["text"], "language": result.get("language", "en")}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
'''
    
    try:
        result = subprocess.run(
            [whisper_python, "-c", whisper_code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        os.unlink(audio_file)

if __name__ == "__main__":
    test_whisper()