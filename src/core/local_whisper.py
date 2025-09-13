"""Use the local Whisper installation from Windows"""
import asyncio
import base64
import tempfile
import os
import subprocess
import json
from typing import Dict, Any
from loguru import logger


class LocalWhisperHandler:
    """Use the existing Whisper installation"""
    
    def __init__(self):
        # Path to the Windows Whisper Python
        self.whisper_python = "/mnt/c/users/dfoss/desktop/localaimodels/Whisper/whisper-env/Scripts/python.exe"
        self.whisper_script = "/mnt/c/users/dfoss/desktop/localaimodels/Whisper/trans.py"
        
    async def transcribe_audio(self, audio_data: str) -> Dict[str, Any]:
        """Transcribe audio using local Whisper installation"""
        temp_audio = None
        temp_output = None
        
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Save audio to temp file in Windows accessible location
            temp_dir = "/mnt/c/temp" if os.path.exists("/mnt/c/temp") else "/tmp"
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.webm', dir=temp_dir)
            temp_audio.write(audio_bytes)
            temp_audio.close()
            
            # Convert webm to wav using ffmpeg
            temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=temp_dir)
            temp_wav.close()
            
            # Convert audio format with better error handling
            convert_cmd = [
                "ffmpeg", "-i", temp_audio.name,
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",      # Mono
                "-c:a", "pcm_s16le",  # PCM format
                "-y",  # Overwrite output
                temp_wav.name
            ]
            
            convert_result = subprocess.run(convert_cmd, capture_output=True, text=True)
            
            if convert_result.returncode != 0:
                logger.error(f"FFmpeg conversion failed: {convert_result.stderr}")
                # Try direct transcription with original file
                temp_wav = temp_audio
            
            # Get the actual file to transcribe
            audio_file = temp_wav.name if hasattr(temp_wav, 'name') else temp_audio.name
            
            # Convert Linux path to Windows path for the Python script
            if audio_file.startswith("/mnt/c/"):
                windows_path = "C:" + audio_file[6:].replace("/", "\\")
            else:
                windows_path = audio_file
                
            logger.info(f"Transcribing audio file: {audio_file}")
            logger.info(f"Windows path: {windows_path}")
            logger.info(f"File size: {os.path.getsize(audio_file)} bytes")
            
            # Create a simple Python script to run Whisper
            # Use raw string to avoid escape issues
            whisper_code = f'''
import whisper
import sys
import json
import os

audio_file = r"{windows_path}"
if not os.path.exists(audio_file):
    print(json.dumps({{"error": "Audio file not found: " + audio_file}}))
    sys.exit(1)

try:
    model = whisper.load_model("base")
    result = model.transcribe(audio_file)
    print(json.dumps({{"text": result["text"], "language": result.get("language", "en")}}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)
'''
            
            # Run Whisper in the Windows environment
            result = subprocess.run(
                [self.whisper_python, "-c", whisper_code],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            logger.info(f"Whisper command output: {result.stdout}")
            logger.info(f"Whisper command stderr: {result.stderr}")
            
            if result.returncode == 0 and result.stdout:
                try:
                    output = json.loads(result.stdout.strip())
                    
                    if "error" in output:
                        return {
                            "success": False,
                            "error": output["error"],
                            "text": ""
                        }
                    
                    text = output.get("text", "").strip()
                    if text:
                        logger.info(f"Successfully transcribed: {text}")
                        return {
                            "success": True,
                            "text": text,
                            "language": output.get("language", "en")
                        }
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    # Try to extract text from output
                    text = result.stdout.strip()
                    if text and not text.startswith("{"):
                        return {
                            "success": True,
                            "text": text,
                            "language": "en"
                        }
            
            error_msg = result.stderr if result.stderr else "Unknown error"
            logger.error(f"Whisper transcription failed: {error_msg}")
            
            return {
                "success": False,
                "error": f"Whisper error: {error_msg}",
                "text": ""
            }
            
        except Exception as e:
            logger.error(f"Local Whisper error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
        finally:
            # Cleanup
            for f in [temp_audio, temp_wav]:
                if f and hasattr(f, 'name') and os.path.exists(f.name):
                    try:
                        os.unlink(f.name)
                    except:
                        pass