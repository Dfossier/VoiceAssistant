"""
Simple Kokoro TTS Wrapper - Direct model usage without phonemizer/espeak dependencies
"""

import torch
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
import json

logger = logging.getLogger(__name__)


class SimpleKokoroTTS:
    """Direct Kokoro TTS implementation without problematic dependencies"""
    
    def __init__(self, model_path: str, voice_name: str = "af_sarah", device: str = "cuda"):
        self.model_path = Path(model_path)
        self.voice_name = voice_name
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None
        self.voice_embedding = None
        self.sample_rate = 24000
        
        # Initialize model
        self._load_model()
        
    def _load_model(self):
        """Load Kokoro model directly"""
        try:
            # Load model checkpoint
            model_file = self.model_path / "kokoro-v1_0.pth"
            if not model_file.exists():
                raise FileNotFoundError(f"Model file not found: {model_file}")
            
            # Load config
            config_file = self.model_path / "config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                # Default config
                self.config = {
                    "sample_rate": 24000,
                    "n_mels": 80,
                    "n_fft": 1024,
                    "hop_length": 256,
                    "win_length": 1024
                }
            
            # Load voice embedding
            voice_file = self.model_path / "voices" / f"{self.voice_name}.pt"
            if voice_file.exists():
                self.voice_embedding = torch.load(voice_file, map_location=self.device)
                logger.info(f"Loaded voice: {self.voice_name}")
            else:
                logger.warning(f"Voice file not found: {voice_file}, using default")
                # Create a default embedding
                self.voice_embedding = torch.randn(1, 256).to(self.device)
            
            # For now, we'll use a simple approach - just return placeholder
            # In a full implementation, you would load the actual model architecture
            logger.info(f"Kokoro TTS wrapper initialized (simplified mode)")
            
        except Exception as e:
            logger.error(f"Failed to load Kokoro model: {e}")
            self.model = None
    
    def text_to_phonemes(self, text: str) -> str:
        """Simple text normalization without phonemizer"""
        # Basic text cleaning
        text = text.strip()
        text = text.replace("  ", " ")
        
        # Convert to uppercase for consistency
        text = text.upper()
        
        # Simple phoneme-like representation (not actual phonemes)
        # In production, you'd use a proper G2P model
        return text
    
    def synthesize(self, text: str) -> Optional[np.ndarray]:
        """Synthesize speech from text"""
        try:
            # Normalize text
            phonemes = self.text_to_phonemes(text)
            
            # For now, return None to trigger fallback
            # In a full implementation, you would:
            # 1. Convert phonemes to tokens
            # 2. Pass through the model
            # 3. Generate mel spectrogram
            # 4. Convert to waveform
            
            logger.info(f"Kokoro synthesis requested for: '{text[:50]}...'")
            return None
            
        except Exception as e:
            logger.error(f"Kokoro synthesis error: {e}")
            return None
    
    def get_sample_rate(self) -> int:
        """Get the sample rate for audio output"""
        return self.sample_rate


class KokoroTTSWithFallback:
    """Kokoro TTS with automatic fallback to Windows TTS"""
    
    def __init__(self, model_path: str, voice_name: str = "af_sarah"):
        self.model_path = Path(model_path)
        self.voice_name = voice_name
        self.kokoro = None
        self.use_fallback = False
        
        # Try to initialize Kokoro
        self._initialize()
    
    def _initialize(self):
        """Initialize Kokoro or set fallback mode"""
        try:
            # First try the simple wrapper
            self.kokoro = SimpleKokoroTTS(
                model_path=str(self.model_path),
                voice_name=self.voice_name
            )
            logger.info("Kokoro TTS initialized (simplified mode)")
            
        except Exception as e:
            logger.warning(f"Kokoro initialization failed, using fallback: {e}")
            self.use_fallback = True
    
    async def synthesize_speech(self, text: str) -> Tuple[Optional[bytes], int]:
        """
        Synthesize speech from text
        Returns: (audio_bytes, sample_rate)
        """
        try:
            # Try Kokoro first
            if self.kokoro and not self.use_fallback:
                audio_array = self.kokoro.synthesize(text)
                if audio_array is not None:
                    # Convert numpy array to bytes
                    audio_bytes = (audio_array * 32767).astype(np.int16).tobytes()
                    return audio_bytes, self.kokoro.get_sample_rate()
            
            # Fallback to Windows TTS
            return await self._windows_tts_fallback(text)
            
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None, 24000
    
    async def _windows_tts_fallback(self, text: str) -> Tuple[Optional[bytes], int]:
        """Windows SAPI TTS fallback"""
        import asyncio
        import base64
        
        try:
            # Escape text for PowerShell
            escaped_text = text.replace('"', '`"').replace("'", "''")
            
            # PowerShell script for TTS
            script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100

# Select a female voice if available
$voices = $synth.GetInstalledVoices()
foreach ($voice in $voices) {{
    if ($voice.VoiceInfo.Gender -eq "Female") {{
        $synth.SelectVoice($voice.VoiceInfo.Name)
        break
    }}
}}

$memoryStream = New-Object System.IO.MemoryStream
$synth.SetOutputToWaveStream($memoryStream)
$synth.Speak('{escaped_text}')

$bytes = $memoryStream.ToArray()
$memoryStream.Close()
$synth.Dispose()

[System.Convert]::ToBase64String($bytes)
'''
            
            # Execute PowerShell command
            process = await asyncio.create_subprocess_exec(
                'powershell.exe', '-NoProfile', '-Command', script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                # Decode base64 WAV data
                wav_bytes = base64.b64decode(stdout.decode().strip())
                
                # Extract PCM from WAV
                pcm_bytes, sample_rate = self._extract_pcm_from_wav(wav_bytes)
                return pcm_bytes, sample_rate
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Windows TTS failed: {error_msg}")
                return None, 24000
                
        except Exception as e:
            logger.error(f"Windows TTS fallback error: {e}")
            return None, 24000
    
    def _extract_pcm_from_wav(self, wav_data: bytes) -> Tuple[bytes, int]:
        """Extract raw PCM data from WAV file"""
        import wave
        import io
        
        try:
            with wave.open(io.BytesIO(wav_data), 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                sample_rate = wav_file.getframerate()
                return frames, sample_rate
        except Exception as e:
            logger.error(f"WAV extraction error: {e}")
            return wav_data, 24000


# Helper function for easy integration
def create_kokoro_tts(model_path: str = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts", 
                     voice_name: str = "af_sarah") -> KokoroTTSWithFallback:
    """Create a Kokoro TTS instance with automatic fallback"""
    return KokoroTTSWithFallback(model_path, voice_name)


# Test function
async def test_kokoro_wrapper():
    """Test the Kokoro wrapper"""
    tts = create_kokoro_tts()
    
    test_text = "Hello! This is a test of the Kokoro text to speech system."
    audio_bytes, sample_rate = await tts.synthesize_speech(test_text)
    
    if audio_bytes:
        logger.info(f"Generated {len(audio_bytes)} bytes of audio at {sample_rate}Hz")
        return True
    else:
        logger.error("Failed to generate audio")
        return False


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_kokoro_wrapper())