"""Simple speech recognition using SpeechRecognition library (faster than Whisper)"""
import asyncio
import base64
import tempfile
import os
from typing import Dict, Any
from loguru import logger

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    logger.warning("SpeechRecognition not available - install with: pip install SpeechRecognition")


class SimpleSpeechHandler:
    """Handle speech recognition using Google's free API"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer() if SR_AVAILABLE else None
        self.initialized = SR_AVAILABLE
        
    async def transcribe_audio(self, audio_data: str) -> Dict[str, Any]:
        """Transcribe base64 audio data to text using Google Speech Recognition"""
        if not self.initialized:
            return {
                "success": False,
                "error": "SpeechRecognition not installed. Run: pip install SpeechRecognition",
                "text": ""
            }
        
        temp_file = None
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Save to temporary file
            temp_webm = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
            temp_webm.write(audio_bytes)
            temp_webm.close()
            
            # Convert webm to wav using pydub
            try:
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(temp_webm.name, format="webm")
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                audio_segment.export(temp_file.name, format="wav")
                
                # Clean up webm file
                os.unlink(temp_webm.name)
            except Exception as e:
                logger.error(f"Audio conversion error: {e}")
                # Try direct recognition anyway
                temp_file = temp_webm
            
            # Load audio file
            with sr.AudioFile(temp_file.name) as source:
                audio = self.recognizer.record(source)
            
            # Recognize speech using Google Speech Recognition
            try:
                text = self.recognizer.recognize_google(audio)
                logger.info(f"Transcribed: {text}")
                
                return {
                    "success": True,
                    "text": text,
                    "language": "en"
                }
            except sr.UnknownValueError:
                return {
                    "success": False,
                    "error": "Could not understand audio",
                    "text": ""
                }
            except sr.RequestError as e:
                return {
                    "success": False,
                    "error": f"Google Speech Recognition error: {e}",
                    "text": ""
                }
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)