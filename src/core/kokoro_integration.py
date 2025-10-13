"""
Kokoro TTS Integration - Optimized implementation for fast synthesis
Provides streamlined TTS without redundant initialization layers
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class KokoroTTSIntegration:
    """
    Optimized Kokoro TTS integration class for fast synthesis
    Single initialization path, no redundant layers
    """
    
    def __init__(self, model_path: str = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts", 
                 voice_name: str = "af_sarah"):
        self.model_path = Path(model_path)
        self.voice_name = voice_name
        self.real_kokoro = None
        self._initialized = False
        
        # Single initialization call
        self._initialize()
    
    def _initialize(self):
        """Single, optimized initialization"""
        try:
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            self._initialized = True
            logger.info("✅ Optimized Kokoro synthesis ready")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
            self._initialized = True
    
    async def synthesize(self, text: str, voice: str = None) -> Tuple[Optional[bytes], int]:
        """
        Fast synthesis with minimal overhead
        Returns: (audio_bytes, sample_rate) or (None, 24000) on failure
        """
        if not text or not text.strip():
            return None, 24000
        
        # Set voice if provided
        if voice:
            self.voice_name = voice
            
        # Try real Kokoro with fast path
        if self.real_kokoro:
            try:
                real_service = await self.real_kokoro()
                audio_bytes, sample_rate = await real_service.synthesize(text, self.voice_name)
                if audio_bytes:
                    return audio_bytes, sample_rate
            except Exception as e:
                logger.warning(f"Kokoro synthesis failed: {e}")
        
        # Fast Windows TTS fallback
        return await self._windows_tts_fallback(text)
    
    async def _windows_tts_fallback(self, text: str) -> Tuple[Optional[bytes], int]:
        """Optimized Windows SAPI TTS fallback"""
        try:
            import subprocess
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            escaped_text = text.replace('"', '\\"').replace("'", "\\'")
            
            # Optimized PowerShell command
            ps_command = f'''
            Add-Type -AssemblyName System.Speech;
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
            $synth.Rate = 1; $synth.Volume = 100;
            $synth.SetOutputToWaveFile("{temp_path}");
            $synth.Speak("{escaped_text}");
            $synth.Dispose();
            '''
            
            # Fast subprocess execution
            result = await asyncio.create_subprocess_exec(
                "powershell.exe", "-Command", ps_command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            await result.wait()
            
            if result.returncode == 0 and os.path.exists(temp_path):
                with open(temp_path, "rb") as f:
                    wav_data = f.read()
                
                if len(wav_data) > 44:
                    pcm_data = wav_data[44:]  # Skip WAV header
                    os.unlink(temp_path)
                    return pcm_data, 22050
            
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Windows TTS fallback failed: {e}")
        
        return None, 22050
    
    def get_available_voices(self) -> list:
        """Get available voices"""
        return ["af_sarah", "af_heart", "af_alloy", "am_hero"]
    
    def set_voice(self, voice_name: str):
        """Change active voice"""
        self.voice_name = voice_name


# Optimized factory function
def create_kokoro_tts_integration(model_path: Optional[str] = None, 
                                 voice_name: str = "af_sarah") -> KokoroTTSIntegration:
    """Create optimized Kokoro TTS integration instance"""
    if model_path is None:
        model_path = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts"
    
    return KokoroTTSIntegration(model_path, voice_name)