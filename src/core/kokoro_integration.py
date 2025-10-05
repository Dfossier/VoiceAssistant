"""
Kokoro TTS Integration - Final implementation without espeak dependencies
Provides seamless TTS with automatic fallback to Windows SAPI
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.kokoro_wrapper import KokoroTTSWithFallback
from src.core.kokoro_direct import KokoroDirectWrapper

logger = logging.getLogger(__name__)


class KokoroTTSIntegration:
    """
    Main Kokoro TTS integration class
    Tries multiple approaches in order:
    1. Direct Kokoro (without phonemizer)
    2. Windows SAPI fallback
    """
    
    def __init__(self, model_path: str = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts", 
                 voice_name: str = "af_sarah"):
        self.model_path = Path(model_path)
        self.voice_name = voice_name
        self.wrapper = None
        self.direct = None
        
        self._initialize()
    
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    def _initialize(self):
        """Initialize TTS backends"""
        try:
            # Try real Kokoro implementation first
            from .kokoro_real_synthesis import get_real_kokoro_service
            self.real_kokoro = get_real_kokoro_service
            logger.info("Real Kokoro synthesis initialized")
        except Exception as e:
            logger.warning(f"Real Kokoro not available: {e}")
            self.real_kokoro = None
        
        # Fallback to Windows TTS if real Kokoro fails
        logger.info("Windows TTS fallback available")
    
    async def synthesize(self, text: str, voice: str = None) -> Tuple[Optional[bytes], int]:
        """
        Synthesize speech from text
        Returns: (audio_bytes, sample_rate) or (None, 24000) on failure
        """
        # Set voice if provided
        if voice:
            self.set_voice(voice)
            
        if not text or not text.strip():
            logger.warning("Empty text provided for synthesis")
            return None, 24000
        
        # Try real Kokoro first
        if self.real_kokoro:
            try:
                real_service = await self.real_kokoro()
                audio_bytes, sample_rate = await real_service.synthesize(text, self.voice_name)
                if audio_bytes:
                    logger.info(f"Generated audio using real Kokoro: {len(audio_bytes)} bytes")
                    return audio_bytes, sample_rate
            except Exception as e:
                logger.warning(f"Real Kokoro failed: {e}")
        
        # Fallback to Windows TTS
        try:
            audio_bytes, sample_rate = await self._windows_tts_fallback(text)
            if audio_bytes:
                logger.info(f"Generated audio using Windows TTS fallback: {len(audio_bytes)} bytes")
                return audio_bytes, sample_rate
        except Exception as e:
            logger.error(f"All TTS methods failed: {e}")
        
        return None, 24000
    
    def get_available_voices(self) -> list:
        """Get list of available voice names"""
        voices_dir = self.model_path / "voices"
        if voices_dir.exists():
            return [f.stem for f in voices_dir.glob("*.pt")]
        return ["af_sarah"]  # Default voice
    
    def set_voice(self, voice_name: str):
        """Change the active voice"""
        if voice_name in self.get_available_voices():
            self.voice_name = voice_name
            logger.info(f"Voice changed to: {voice_name}")
        else:
            logger.warning(f"Voice not found: {voice_name}")


# Helper function for easy integration
def create_kokoro_tts_integration(model_path: Optional[str] = None, 
                                 voice_name: str = "af_sarah") -> KokoroTTSIntegration:
    """Create a Kokoro TTS integration instance"""
    if model_path is None:
        model_path = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts"
    
    return KokoroTTSIntegration(model_path, voice_name)


# Test the integration
async def test_integration():
    """Test the complete Kokoro integration"""
    tts = create_kokoro_tts_integration()
    
    # List available voices
    voices = tts.get_available_voices()
    logger.info(f"Available voices: {', '.join(voices[:10])}...")  # Show first 10
    
    # Test synthesis
    test_texts = [
        "Hello! This is the Kokoro text to speech system.",
        "It works without espeak or phonemizer dependencies.",
        "The system automatically falls back to Windows TTS if needed."
    ]
    
    for text in test_texts:
        logger.info(f"\nSynthesizing: '{text}'")
        audio_bytes, sample_rate = await tts.synthesize(text)
        
        if audio_bytes:
            logger.info(f"✅ Success: {len(audio_bytes)} bytes at {sample_rate}Hz")
        else:
            logger.error("❌ Failed to synthesize")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(test_integration())
    async def _windows_tts_fallback(self, text: str) -> Tuple[Optional[bytes], int]:
        """Windows SAPI TTS fallback for when Kokoro fails"""
        try:
            import subprocess
            import tempfile
            import os
            
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Escape text for PowerShell
            escaped_text = text.replace('"', '\\"').replace("'", "\\'")
            
            # PowerShell command for TTS
            ps_command = f'''
            Add-Type -AssemblyName System.Speech;
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
            $synth.SetOutputToWaveFile("{temp_path}");
            $synth.Speak("{escaped_text}");
            $synth.Dispose();
            '''
            
            # Run PowerShell command
            result = await asyncio.create_subprocess_exec(
                "powershell.exe", "-Command", ps_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await result.wait()
            
            if result.returncode == 0 and os.path.exists(temp_path):
                # Read the WAV file and extract PCM data
                with open(temp_path, "rb") as f:
                    wav_data = f.read()
                
                # Remove WAV header (44 bytes) and return PCM data
                if len(wav_data) > 44:
                    pcm_data = wav_data[44:]
                    os.unlink(temp_path)
                    return pcm_data, 22050  # Windows TTS typically uses 22kHz
            
            os.unlink(temp_path) if os.path.exists(temp_path) else None
            
        except Exception as e:
            logger.error(f"Windows TTS fallback failed: {e}")
        
        return None, 22050
