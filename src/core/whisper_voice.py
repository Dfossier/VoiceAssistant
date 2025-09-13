"""Real voice recognition using Whisper for all browsers"""
import asyncio
import base64
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available - install with: pip install openai-whisper")

try:
    import soundfile as sf
    import numpy as np
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logger.warning("Audio libraries not available - install with: pip install soundfile numpy")


class WhisperVoiceHandler:
    """Handle real voice recognition using Whisper"""
    
    def __init__(self, model_size: str = "base"):
        self.model = None
        self.model_size = model_size
        self.initialized = False
        
        if WHISPER_AVAILABLE and AUDIO_LIBS_AVAILABLE:
            try:
                logger.info(f"Loading Whisper model: {model_size}")
                self.model = whisper.load_model(model_size)
                self.initialized = True
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
    
    async def transcribe_audio(self, audio_data: str) -> Dict[str, Any]:
        """Transcribe base64 audio data to text"""
        if not self.initialized:
            return {
                "success": False,
                "error": "Whisper not initialized",
                "text": ""
            }
        
        temp_file = None
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
            temp_file.write(audio_bytes)
            temp_file.close()
            
            # Transcribe with Whisper
            result = self.model.transcribe(temp_file.name)
            text = result["text"].strip()
            
            logger.info(f"Transcribed: {text}")
            
            return {
                "success": True,
                "text": text,
                "language": result.get("language", "en")
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get Whisper status"""
        return {
            "available": self.initialized,
            "model_size": self.model_size,
            "whisper_installed": WHISPER_AVAILABLE,
            "audio_libs_installed": AUDIO_LIBS_AVAILABLE
        }


# JavaScript for real audio recording in Firefox
FIREFOX_AUDIO_RECORDER = """
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }
    
    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                const audioBase64 = await this.blobToBase64(audioBlob);
                
                // Send to server for transcription
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'voice',
                        action: 'transcribe',
                        audio: audioBase64,
                        timestamp: Date.now()
                    }));
                }
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            return true;
        } catch (err) {
            console.error('Failed to start recording:', err);
            addChatMessage('error', 'Microphone access denied or not available');
            return false;
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }
    }
    
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result.split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
}
"""