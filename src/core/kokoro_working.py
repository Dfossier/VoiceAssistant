#!/usr/bin/env python3
"""
Working Kokoro TTS implementation using the official package
This version applies the phonemizer fix and uses the proper API
"""

import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

# CRITICAL: Apply phonemizer fix BEFORE importing kokoro
try:
    from .phonemizer_fix import apply_phonemizer_fix
    apply_phonemizer_fix()
except ImportError:
    from phonemizer_fix import apply_phonemizer_fix
    apply_phonemizer_fix()

class WorkingKokoroService:
    """Kokoro TTS service using the official package with proper initialization"""
    
    def __init__(self, model_path: str = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts"):
        self.model_path = Path(model_path)
        self._initialized = False
        self._pipeline = None
        
    async def initialize(self, eager_init: bool = True) -> bool:
        """Initialize Kokoro TTS with the official API"""
        try:
            logger.info("🔊 Initializing Kokoro TTS with official API...")
            
            # Import Kokoro AFTER applying the fix
            try:
                from kokoro import KModel, KPipeline
                logger.info("✅ Kokoro package imported successfully")
            except ImportError as e:
                logger.error(f"❌ Failed to import Kokoro: {e}")
                return False
                
            # Check if model file exists
            model_file = self.model_path / "kokoro-v1_0.pth"
            voices_dir = self.model_path / "voices"
            
            if not model_file.exists():
                logger.error(f"❌ Model file not found: {model_file}")
                return False
                
            if not voices_dir.exists():
                logger.error(f"❌ Voices directory not found: {voices_dir}")
                return False
                
            logger.info(f"✅ Found model file: {model_file} ({model_file.stat().st_size / 1024 / 1024:.1f} MB)")
            logger.info(f"✅ Found voices directory with {len(list(voices_dir.glob('*.pt')))} voices")
            
            if eager_init:
                # Create the model and pipeline with local files only
                try:
                    logger.info("🔄 Creating KModel with local files...")
                    config_file = self.model_path / "config.json"
                    
                    # Use local files to prevent HuggingFace downloads
                    model = KModel(
                        repo_id='hexgrad/Kokoro-82M',  # Required but not used when local files provided
                        config=str(config_file),       # Local config.json path
                        model=str(model_file)          # Local .pth file path
                    )
                    logger.info("✅ KModel created successfully with local files")
                    
                    logger.info("🔄 Creating KPipeline...")
                    self._pipeline = KPipeline(model)
                    logger.info("✅ KPipeline created successfully")
                    
                    # Test the pipeline
                    logger.info("🧪 Testing Kokoro synthesis...")
                    test_result = list(self._pipeline("Hello world", voice='af_heart'))
                    if test_result and len(test_result) > 0:
                        logger.info("✅ Kokoro test successful!")
                        self._initialized = True
                        return True
                    else:
                        logger.error("❌ Kokoro test returned empty result")
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ Failed to create Kokoro pipeline: {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                    return False
            else:
                # Lazy initialization - just check files exist
                self._initialized = True
                logger.info("✅ Kokoro configured for lazy initialization")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kokoro: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
            
    async def synthesize(self, text: str, voice: str = 'af_heart') -> Tuple[Optional[bytes], int]:
        """Synthesize speech using Kokoro"""
        if not self._initialized:
            logger.warning("Kokoro not initialized, attempting now...")
            if not await self.initialize():
                return None, 24000
                
        try:
            if not self._pipeline:
                # Lazy initialization with local files
                from kokoro import KModel, KPipeline
                model_file = self.model_path / "kokoro-v1_0.pth"
                config_file = self.model_path / "config.json"
                
                # Use local files to prevent HuggingFace downloads
                model = KModel(
                    repo_id='hexgrad/Kokoro-82M',  # Required but not used when local files provided
                    config=str(config_file),       # Local config.json path
                    model=str(model_file)          # Local .pth file path
                )
                self._pipeline = KPipeline(model)
                
            logger.info(f"🔊 Synthesizing with Kokoro: '{text[:50]}...' using voice '{voice}'")
            
            # Run synthesis
            loop = asyncio.get_event_loop()
            
            def _synthesize():
                audio_arrays = []
                for grapheme_str, phoneme_str, audio_array in self._pipeline(text, voice=voice):
                    logger.debug(f"Generated segment: '{grapheme_str}' -> '{phoneme_str}'")
                    audio_arrays.append(audio_array)
                    
                if audio_arrays:
                    # Concatenate all audio segments
                    full_audio = np.concatenate(audio_arrays)
                    # Convert to int16 for standard audio format
                    audio_int16 = (full_audio * 32767).astype(np.int16)
                    return audio_int16.tobytes()
                return None
                
            audio_bytes = await loop.run_in_executor(None, _synthesize)
            
            if audio_bytes:
                logger.info(f"✅ Kokoro synthesis successful: {len(audio_bytes)} bytes")
                return audio_bytes, 24000
            else:
                logger.error("❌ Kokoro synthesis returned no audio")
                return None, 24000
                
        except Exception as e:
            logger.error(f"❌ Kokoro synthesis failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None, 24000

# Global instance
working_kokoro_service = WorkingKokoroService()