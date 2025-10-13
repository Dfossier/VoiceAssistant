#!/usr/bin/env python3
"""
Kokoro TTS Service
Proper implementation using the official kokoro Python package
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

class KokoroTTSService:
    """Service for Kokoro text-to-speech synthesis"""
    
    def __init__(self, model_path: Path = None, eager_init: bool = True):
        self.model_path = model_path or Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        self._pipeline = None
        self._model = None
        self._use_low_level_api = False
        self._initialized = False
        
        # Disable eager initialization by default to prevent redundant inits
        if eager_init:
            self._eager_initialize()
    
    def _eager_initialize(self):
        """Synchronously initialize the pipeline at startup"""
        try:
            logger.info("🚀 Starting eager Kokoro TTS initialization...")
            
            # Run the async initialization in a synchronous context
            import asyncio
            try:
                # Try to use existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, schedule for later
                    logger.info("Scheduling Kokoro TTS initialization for later...")
                    loop.create_task(self._initialize_async())
                    return
                else:
                    loop.run_until_complete(self._initialize_async())
            except RuntimeError:
                # No event loop running, create a new one
                asyncio.run(self._initialize_async())
                
        except Exception as e:
            logger.error(f"❌ Error during eager Kokoro TTS initialization: {e}")
    
    async def _initialize_async(self):
        """Async helper for initialization"""
        success = await self.initialize()
        if success:
            logger.info("✅ Eager Kokoro TTS initialization completed successfully!")
        else:
            logger.error("❌ Eager Kokoro TTS initialization failed")
        
    async def initialize(self):
        """Initialize the Kokoro TTS pipeline with essential compatibility fixes"""
        if self._initialized:
            return True
            
        try:
            logger.info("🚀 Fast Kokoro TTS initialization...")
            
            # Apply essential phonemizer compatibility fix BEFORE importing Kokoro
            try:
                from phonemizer.backend.espeak.wrapper import EspeakWrapper
                if not hasattr(EspeakWrapper, 'set_data_path'):
                    logger.info("🔧 Applying phonemizer compatibility fix...")
                    @staticmethod
                    def set_data_path(path):
                        """Compatibility method for misaki package"""
                        import os
                        os.environ['ESPEAK_DATA_PATH'] = str(path)
                    EspeakWrapper.set_data_path = set_data_path
                    logger.info("✅ Phonemizer compatibility fix applied")
            except Exception as e:
                logger.warning(f"Could not apply phonemizer fix: {e}")
                
            # Import Kokoro after the fix is applied
            try:
                from kokoro import KPipeline
                logger.info("✅ Kokoro package found")
            except ImportError:
                logger.error("❌ Kokoro package not installed. Install with: pip install kokoro>=0.9.2")
                return False
                
            # Initialize with minimal configuration for speed
            try:
                # Set environment variables that might help with espeak
                import os
                os.environ.setdefault('ESPEAK_DATA_PATH', '/usr/share/espeak-ng-data')
                
                self._pipeline = KPipeline(lang_code='a')  # American English
                logger.info("✅ Kokoro TTS pipeline initialized successfully")
                    
            except Exception as e:
                logger.error(f"❌ Kokoro initialization failed: {e}")
                return False
                    
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kokoro TTS: {e}")
            return False
            
    async def synthesize(self, text: str, voice: str = 'af_heart') -> Optional[bytes]:
        """Synthesize speech from text using Kokoro"""
        if not self._initialized:
            logger.warning("❌ Kokoro TTS not initialized - attempting initialization now...")
            if not await self.initialize():
                logger.error("❌ Kokoro TTS initialization failed")
                return None
                
        try:
            logger.info(f"🔊 Synthesizing with Kokoro TTS: '{text[:50]}...' using voice '{voice}'")
            
            # Generate audio using Kokoro pipeline
            # The pipeline returns a generator with (grapheme_string, phoneme_string, audio_array) tuples
            audio_arrays = []
            
            # Run synthesis in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            def _synthesize():
                """Synchronous synthesis function"""
                if self._use_low_level_api and self._model:
                    # Use low-level API approach
                    try:
                        # This would need to be implemented based on actual Kokoro low-level API
                        # For now, return None to trigger fallback
                        logger.warning("Low-level API synthesis not fully implemented yet")
                        return None
                    except Exception as e:
                        logger.error(f"Low-level synthesis failed: {e}")
                        return None
                else:
                    # Use high-level pipeline API
                    generator = self._pipeline(text, voice=voice)
                    audio_parts = []
                    
                    for i, (gs, ps, audio) in enumerate(generator):
                        logger.debug(f"Generated part {i}: graphemes='{gs[:30]}...' phonemes='{ps[:30]}...'")
                        audio_parts.append(audio)
                        
                    # Concatenate all audio parts
                    if audio_parts:
                        return np.concatenate(audio_parts)
                    return None
                
            audio_array = await loop.run_in_executor(None, _synthesize)
            
            if audio_array is None or len(audio_array) == 0:
                logger.warning("⚠️ Kokoro generated empty audio")
                return None
                
            # Convert float32 numpy array to int16 PCM bytes
            # Kokoro outputs at 24kHz sample rate
            # Check audio range
            logger.info(f"Audio array stats - min: {audio_array.min():.3f}, max: {audio_array.max():.3f}, shape: {audio_array.shape}")
            
            # Normalize audio if needed (Kokoro might output in -1 to 1 range)
            if audio_array.max() <= 1.0 and audio_array.min() >= -1.0:
                # Audio is normalized, scale to int16 range with slight boost
                # Increase volume by 1.5x to ensure it's audible
                audio_int16 = (audio_array * 32767 * 1.5).clip(-32768, 32767).astype(np.int16)
            else:
                # Audio might already be in a different range
                audio_int16 = audio_array.astype(np.int16)
                
            audio_bytes = audio_int16.tobytes()
            
            logger.info(f"✅ Kokoro TTS generated {len(audio_bytes)} bytes of audio at 24kHz")
            
            # Debug: Check if audio is too quiet
            import wave
            import io
            debug_wav = io.BytesIO()
            with wave.open(debug_wav, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(audio_bytes)
            debug_wav_bytes = debug_wav.getvalue()
            logger.info(f"📊 Debug: WAV file size would be {len(debug_wav_bytes)} bytes (PCM was {len(audio_bytes)} bytes)")
            
            # Check audio volume
            audio_max = np.abs(audio_int16).max()
            logger.info(f"📊 Debug: Max audio value: {audio_max} (out of 32768)")
            
            return audio_bytes
            
        except ImportError:
            logger.error("❌ Kokoro package not available. Install with: pip install kokoro>=0.9.2")
            return None
        except Exception as e:
            logger.error(f"❌ Kokoro TTS synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def get_available_voices(self):
        """Get list of available voices"""
        # Based on VOICES.md, Kokoro v1.0 has 54 voices
        # Here are some common ones:
        return {
            'af_heart': 'American Female (Heart)',
            'af_alloy': 'American Female (Alloy)',
            'am_hero': 'American Male (Hero)',
            'am_onyx': 'American Male (Onyx)',
            'af_echo': 'American Female (Echo)',
            'am_nova': 'American Male (Nova)',
            'bf_emma': 'British Female (Emma)',
            'bm_george': 'British Male (George)'
        }

# Global instance - initialized eagerly by default
kokoro_service = KokoroTTSService(eager_init=True)