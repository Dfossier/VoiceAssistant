"""Browser-based voice chat using Web Speech API (no PyAudio needed)"""
import asyncio
import json
from typing import Optional, Dict, Any
from loguru import logger

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("pyttsx3 not available - TTS disabled")


class BrowserVoiceHandler:
    """Handle voice chat through browser Web Speech API"""
    
    def __init__(self, llm_handler):
        self.llm_handler = llm_handler
        self.tts_engine = None
        self.voice_enabled = False
        
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 0.8)
                
                # Get available voices
                voices = self.tts_engine.getProperty('voices')
                if voices and len(voices) > 0:
                    # Try to find a good English voice
                    for voice in voices:
                        if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                            self.tts_engine.setProperty('voice', voice.id)
                            break
                
                self.voice_enabled = True
                logger.info("TTS engine initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize TTS: {e}")
                self.voice_enabled = False
    
    async def process_voice_input(self, text: str) -> Dict[str, Any]:
        """Process voice input text and generate response"""
        try:
            # Get AI response
            response = await self.llm_handler.generate_response(
                prompt=text,
                system_prompt="""You are having a voice conversation. Keep responses:
- Conversational and natural
- Under 2-3 sentences 
- Easy to understand when spoken
- Focused on helping with debugging and development"""
            )
            
            # Generate audio response if TTS is available
            audio_response = None
            if self.voice_enabled and self.tts_engine:
                try:
                    # Save audio to temporary file for web playback
                    import tempfile
                    import os
                    
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                    temp_file.close()
                    
                    self.tts_engine.save_to_file(response, temp_file.name)
                    self.tts_engine.runAndWait()
                    
                    # Read audio file as base64 for web transfer
                    import base64
                    with open(temp_file.name, 'rb') as f:
                        audio_data = base64.b64encode(f.read()).decode()
                    
                    os.unlink(temp_file.name)
                    audio_response = audio_data
                    
                except Exception as e:
                    logger.error(f"TTS generation failed: {e}")
            
            return {
                "type": "voice_response",
                "text": response,
                "audio": audio_response,
                "has_audio": audio_response is not None,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"Error processing voice input: {e}")
            return {
                "type": "error",
                "message": f"Voice processing error: {str(e)}"
            }
    
    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return {
            "tts_available": self.voice_enabled,
            "supported_features": {
                "speech_recognition": "web_api",  # Browser Web Speech API
                "text_to_speech": "local" if self.voice_enabled else "none",
                "real_time_streaming": False,
                "interrupt_support": False
            },
            "requirements": {
                "browser_support": "Chrome, Edge, Safari (with microphone permission)",
                "system_audio": "Speakers/headphones for TTS responses"
            }
        }


# JavaScript code for browser voice integration
BROWSER_VOICE_JS = """
// Browser voice chat integration
class VoiceChat {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.audioContext = null;
        
        // Check for browser support
        if ('webkitSpeechRecognition' in window) {
            this.recognition = new webkitSpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.sendVoiceMessage(transcript);
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.stopListening();
            };
            
            this.recognition.onend = () => {
                this.isListening = false;
                this.updateVoiceButton();
            };
        }
    }
    
    startListening() {
        if (!this.recognition) {
            alert('Speech recognition not supported in this browser');
            return;
        }
        
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(() => {
                this.recognition.start();
                this.isListening = true;
                this.updateVoiceButton();
            })
            .catch((err) => {
                console.error('Microphone access denied:', err);
                alert('Please allow microphone access for voice chat');
            });
    }
    
    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
            this.updateVoiceButton();
        }
    }
    
    sendVoiceMessage(text) {
        // Add voice input to chat
        addChatMessage('user', `🎤 ${text}`);
        
        // Send to server for processing
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'voice',
                action: 'process',
                text: text,
                timestamp: Date.now()
            }));
        }
    }
    
    playAudioResponse(audioData) {
        if (!audioData) return;
        
        try {
            // Convert base64 to audio blob
            const audioBytes = atob(audioData);
            const arrayBuffer = new ArrayBuffer(audioBytes.length);
            const uint8Array = new Uint8Array(arrayBuffer);
            for (let i = 0; i < audioBytes.length; i++) {
                uint8Array[i] = audioBytes.charCodeAt(i);
            }
            
            const audioBlob = new Blob([arrayBuffer], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            audio.play().catch(err => {
                console.error('Audio playback failed:', err);
            });
            
        } catch (err) {
            console.error('Error processing audio response:', err);
        }
    }
    
    updateVoiceButton() {
        const button = document.getElementById('voice-button');
        if (button) {
            if (this.isListening) {
                button.textContent = '🔴 Stop';
                button.className = 'bg-red-500 hover:bg-red-600 px-4 py-2 rounded font-medium transition';
            } else {
                button.textContent = '🎤 Voice';
                button.className = 'bg-green-500 hover:bg-green-600 px-4 py-2 rounded font-medium transition';
            }
        }
    }
}

// Initialize voice chat
const voiceChat = new VoiceChat();
"""