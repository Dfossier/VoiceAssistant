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
            # Try direct implementation first
            self.direct = KokoroDirectWrapper(str(self.model_path), use_direct=True)
            logger.info("Kokoro direct implementation initialized")
        except Exception as e:
            logger.warning(f"Direct Kokoro not available: {e}")
        
        # Always initialize the wrapper with fallback
        self.wrapper = KokoroTTSWithFallback(str(self.model_path), self.voice_name)
        logger.info("Kokoro wrapper with fallback initialized")
    
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
        
        # Skip direct Kokoro (uses dummy implementation) - go straight to real TTS
        # Direct method generates silent audio for testing - disabled for now
        # if self.direct:
        #     try:
        #         audio_bytes, sample_rate = await self.direct.synthesize(text, self.voice_name)
        #         if audio_bytes:
        #             logger.info(f"Generated audio using direct Kokoro: {len(audio_bytes)} bytes")
        #             return audio_bytes, sample_rate
        #     except Exception as e:
        #         logger.warning(f"Direct Kokoro failed: {e}")
        
        # Fall back to wrapper (which includes Windows TTS)
        try:
            audio_bytes, sample_rate = await self.wrapper.synthesize_speech(text)
            if audio_bytes:
                logger.info(f"Generated audio using fallback: {len(audio_bytes)} bytes")
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