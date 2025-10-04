"""
Real Kokoro TTS synthesis implementation with misaki fix
This provides actual neural TTS synthesis, not synthetic audio
"""
import os
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

# Force offline mode
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_EVALUATE_OFFLINE"] = "1"
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

class RealKokoroSynthesis:
    """Real Kokoro TTS synthesis without any synthetic audio"""
    
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.model = None
        self.pipeline = None
        self._initialized = False
        self.sample_rate = 24000
        
    async def initialize(self) -> bool:
        """Initialize Kokoro with misaki fix"""
        if self._initialized:
            return True
            
        try:
            logger.info("🚀 Initializing real Kokoro synthesis...")
            
            # Apply misaki fix FIRST
            from .misaki_espeak_fix import apply_misaki_espeak_fix
            if not apply_misaki_espeak_fix():
                logger.error("❌ Failed to apply misaki fix")
                return False
                
            # Import Kokoro
            from kokoro import KModel, KPipeline
            
            # Check local files
            config_file = self.model_path / "config.json"
            model_file = self.model_path / "kokoro-v1_0.pth"
            
            if not config_file.exists() or not model_file.exists():
                logger.error(f"❌ Model files not found at {self.model_path}")
                return False
                
            # Initialize KModel
            logger.info("🔄 Creating KModel...")
            self.model = KModel(
                repo_id='hexgrad/Kokoro-82M',
                config=str(config_file),
                model=str(model_file)
            )
            logger.info("✅ KModel created")
            
            # Initialize KPipeline
            logger.info("🔄 Creating KPipeline...")
            self.pipeline = KPipeline(lang_code='en-us', model=self.model)
            logger.info("✅ KPipeline created")
            
            # Check for local voice data (skip download)
            # Load local voice embeddings
            self.voice_embeddings = {}
            voices_dir = self.model_path / "voices"
            if voices_dir.exists():
                import torch
                voice_files = list(voices_dir.glob("*.pt"))
                for voice_file in voice_files:
                    voice_name = voice_file.stem
                    try:
                        embedding = torch.load(voice_file, map_location='cpu')
                        self.voice_embeddings[voice_name] = embedding
                        logger.info(f"   - Loaded {voice_name}: {embedding.shape}")
                    except Exception as e:
                        logger.warning(f"   - Failed to load {voice_name}: {e}")
            logger.info("🔄 Checking voice data...")
            try:
                # Just verify voices directory exists
                voices_dir = self.model_path / "voices"
                if voices_dir.exists():
                    voice_files = list(voices_dir.glob("*.pt"))
                    logger.info(f"✅ Found {len(voice_files)} local voice files")
                else:
                    logger.warning("⚠️ No voices directory - synthesis may fail")
            except Exception as e:
                logger.warning(f"⚠️ Voice check failed: {e}")
                logger.warning(f"⚠️ Voice check failed: {e}")
            
            self._initialized = True
            logger.info("🎉 Real Kokoro synthesis initialized!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def synthesize(self, text: str, voice: str = 'af_alloy') -> Tuple[Optional[bytes], int]:
        """Synthesize speech using real Kokoro neural TTS"""
        if not self._initialized:
            if not await self.initialize():
                logger.error("❌ Failed to initialize Kokoro")
                return None, self.sample_rate
        
        try:
            logger.info(f"🎤 Synthesizing with real Kokoro: '{text[:50]}...'")
            
            # Use the pipeline to synthesize
            # Monkey patch KPipeline to use local voices
            import torch
            original_load_voice = self.pipeline.load_voice
            def patched_load_voice(voice):
                if voice in self.voice_embeddings:
                    return self.voice_embeddings[voice]
                else:
                    logger.warning(f"Voice {voice} not found locally, falling back to original")
                    return original_load_voice(voice)
            self.pipeline.load_voice = patched_load_voice
            results = list(self.pipeline(text, voice=voice, speed=1.0, split_pattern=None))
            
            if not results:
                logger.error("❌ Pipeline returned no results")
                return None, self.sample_rate
            
            # Get the audio from results
            grapheme, phoneme, audio = results[0]
            
            logger.info(f"✅ Synthesis successful:")
            logger.info(f"   Text: '{grapheme}'")
            logger.info(f"   Phonemes: '{phoneme}'")
            logger.info(f"   Audio shape: {audio.shape}")
            
            # Convert to int16 PCM
            audio_numpy = audio.detach().cpu().numpy()
            audio_int16 = (audio_numpy * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            logger.info(f"✅ Generated {len(audio_bytes)} bytes of real audio")
            return audio_bytes, self.sample_rate
            
        except Exception as e:
            logger.error(f"❌ Real synthesis failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None, self.sample_rate

# Global instance for reuse
real_kokoro_service = None

async def get_real_kokoro_service():
    """Get or create the global real Kokoro service"""
    global real_kokoro_service
    
    if real_kokoro_service is None:
        model_path = Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        real_kokoro_service = RealKokoroSynthesis(model_path)
        await real_kokoro_service.initialize()
    
    return real_kokoro_service

# Test function
async def test_real_synthesis():
    """Test the real Kokoro synthesis"""
    service = await get_real_kokoro_service()
    
    test_text = "Hello! This is real Kokoro neural text to speech, not synthetic audio."
    audio_bytes, sample_rate = await service.synthesize(test_text)
    
    if audio_bytes:
        logger.info(f"🎉 SUCCESS: Generated {len(audio_bytes)} bytes at {sample_rate}Hz")
        return True
    else:
        logger.error("❌ FAILED: No audio generated")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_real_synthesis())