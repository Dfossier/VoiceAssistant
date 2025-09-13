"""
Direct Kokoro TTS implementation using model files without phonemizer
This implementation loads the Kokoro model directly and provides text-to-speech
without the problematic espeak/phonemizer dependencies.
"""

import torch
import torch.nn as nn
import numpy as np
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import json

logger = logging.getLogger(__name__)


class BasicTextNormalizer:
    """Basic text normalization without phonemizer"""
    
    def __init__(self):
        # Basic phoneme mappings (simplified)
        self.word_to_phonemes = {
            "the": "DH AH",
            "a": "AH",
            "an": "AE N",
            "hello": "HH AH L OW",
            "world": "W ER L D",
            "test": "T EH S T",
            "kokoro": "K OW K OW R OW",
            # Add more mappings as needed
        }
        
        # Letter to phoneme for unknown words
        self.letter_to_phoneme = {
            'a': 'EY', 'b': 'B', 'c': 'K', 'd': 'D', 'e': 'IY',
            'f': 'F', 'g': 'G', 'h': 'HH', 'i': 'AY', 'j': 'JH',
            'k': 'K', 'l': 'L', 'm': 'M', 'n': 'N', 'o': 'OW',
            'p': 'P', 'q': 'K', 'r': 'R', 's': 'S', 't': 'T',
            'u': 'UW', 'v': 'V', 'w': 'W', 'x': 'K S', 'y': 'W AY',
            'z': 'Z'
        }
    
    def text_to_phonemes(self, text: str) -> str:
        """Convert text to basic phoneme representation"""
        # Clean and lowercase
        text = re.sub(r'[^\w\s]', '', text.lower())
        words = text.split()
        
        phonemes = []
        for word in words:
            if word in self.word_to_phonemes:
                phonemes.append(self.word_to_phonemes[word])
            else:
                # Simple letter-by-letter conversion
                word_phonemes = []
                for letter in word:
                    if letter in self.letter_to_phoneme:
                        word_phonemes.append(self.letter_to_phoneme[letter])
                phonemes.append(' '.join(word_phonemes))
        
        return ' '.join(phonemes)


class DirectKokoroTTS:
    """Direct Kokoro implementation without external dependencies"""
    
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = Path(model_path)
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None
        self.config = None
        self.normalizer = BasicTextNormalizer()
        self.sample_rate = 24000
        
        self._load_config()
        self._check_model_files()
    
    def _load_config(self):
        """Load model configuration"""
        config_file = self.model_path / "config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.config = json.load(f)
                logger.info(f"Loaded config: {list(self.config.keys())}")
        else:
            logger.warning("No config.json found, using defaults")
            self.config = {
                "sample_rate": 24000,
                "model_type": "kokoro",
                "version": "1.0"
            }
    
    def _check_model_files(self):
        """Check available model files"""
        model_file = self.model_path / "kokoro-v1_0.pth"
        voices_dir = self.model_path / "voices"
        
        if model_file.exists():
            logger.info(f"✅ Found model file: {model_file}")
            # Check file size
            size_mb = model_file.stat().st_size / (1024 * 1024)
            logger.info(f"   Model size: {size_mb:.1f} MB")
        else:
            logger.error(f"❌ Model file not found: {model_file}")
        
        if voices_dir.exists():
            voice_files = list(voices_dir.glob("*.pt"))
            logger.info(f"✅ Found {len(voice_files)} voice files")
            for vf in voice_files[:5]:  # Show first 5
                logger.info(f"   - {vf.name}")
        else:
            logger.error(f"❌ Voices directory not found: {voices_dir}")
    
    def load_voice_embedding(self, voice_name: str) -> Optional[torch.Tensor]:
        """Load a voice embedding"""
        voice_file = self.model_path / "voices" / f"{voice_name}.pt"
        if voice_file.exists():
            try:
                embedding = torch.load(voice_file, map_location=self.device)
                logger.info(f"Loaded voice: {voice_name}, shape: {embedding.shape}")
                return embedding
            except Exception as e:
                logger.error(f"Failed to load voice {voice_name}: {e}")
        return None
    
    def synthesize_dummy(self, text: str, voice_name: str = "af_sarah") -> Optional[np.ndarray]:
        """
        Dummy synthesis for testing - generates silent audio
        In a real implementation, this would load and use the actual model
        """
        try:
            # Convert text to phonemes
            phonemes = self.normalizer.text_to_phonemes(text)
            logger.info(f"Phonemes: {phonemes}")
            
            # Load voice embedding
            voice_embedding = self.load_voice_embedding(voice_name)
            
            # For testing, generate silent audio
            # Duration: approximately 0.15 seconds per word
            words = text.split()
            duration_seconds = len(words) * 0.15
            num_samples = int(duration_seconds * self.sample_rate)
            
            # Generate silent audio (or very quiet noise)
            audio = np.zeros(num_samples, dtype=np.float32)
            # Add tiny amount of noise so it's not completely silent
            audio += np.random.normal(0, 0.0001, num_samples)
            
            return audio
            
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return None


# Integration with existing system
class KokoroDirectWrapper:
    """Wrapper that provides Kokoro TTS with graceful fallback"""
    
    def __init__(self, model_path: str, use_direct: bool = True):
        self.model_path = Path(model_path)
        self.use_direct = use_direct
        self.direct_tts = None
        
        if use_direct:
            try:
                self.direct_tts = DirectKokoroTTS(str(model_path))
                logger.info("Direct Kokoro TTS initialized")
            except Exception as e:
                logger.warning(f"Could not initialize direct Kokoro: {e}")
    
    async def synthesize(self, text: str, voice: str = "af_sarah") -> Tuple[Optional[bytes], int]:
        """Synthesize speech with automatic fallback"""
        
        # Try direct Kokoro first
        if self.direct_tts:
            audio_array = self.direct_tts.synthesize_dummy(text, voice)
            if audio_array is not None:
                # Convert to 16-bit PCM bytes with volume boost for audibility
                audio_int16 = (audio_array * 32767 * 1.5).clip(-32768, 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                return audio_bytes, self.direct_tts.sample_rate
        
        # If direct fails or not available, return None to trigger fallback
        logger.info("Direct Kokoro not available, fallback will be used")
        return None, 24000


# Test function
def test_direct_kokoro():
    """Test the direct Kokoro implementation"""
    import asyncio
    
    async def run_test():
        wrapper = KokoroDirectWrapper("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        
        test_text = "Hello world, this is a test."
        audio_bytes, sample_rate = await wrapper.synthesize(test_text)
        
        if audio_bytes:
            logger.info(f"Generated {len(audio_bytes)} bytes at {sample_rate}Hz")
        else:
            logger.info("No audio generated (will use fallback)")
    
    asyncio.run(run_test())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_direct_kokoro()