"""
Complete fix for phonemizer/espeak hanging in WSL2
This properly initializes espeak without audio output to prevent WSL2 hangs
"""

import os
import sys
from loguru import logger

def apply_complete_phonemizer_fix():
    """Apply comprehensive phonemizer/espeak fix for WSL2"""
    try:
        logger.info("🔧 Applying comprehensive phonemizer WSL2 fix...")
        
        # Set environment variables to disable audio
        os.environ['PULSE_RUNTIME_PATH'] = '/tmp/nonexistent'
        os.environ['ALSA_CARD'] = 'none' 
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        
        # Import phonemizer components before patching
        import phonemizer.backend.espeak.api
        
        # Store original EspeakAPI.__init__
        original_init = phonemizer.backend.espeak.api.EspeakAPI.__init__
        
        def patched_espeak_api_init(self, library):
            """Patched EspeakAPI that forces no audio output mode"""
            import ctypes
            import tempfile
            import shutil
            import weakref
            import atexit
            from pathlib import Path
            
            # Set to None to avoid AttributeError in _delete if __init__ raises
            self._library = None
            
            try:
                # Load the original library to get its path
                espeak = ctypes.cdll.LoadLibrary(str(library))
                library_path = self._shared_library_path(espeak)
                del espeak
            except OSError as error:
                raise RuntimeError(f'failed to load espeak library: {str(error)}') from None
            
            # Create temporary directory for library copy
            self._tempdir = tempfile.mkdtemp()
            
            # Set up cleanup
            if sys.platform == 'win32':  # pragma: nocover
                atexit.register(self._delete_win32)
            else:
                weakref.finalize(self, self._delete, self._library, self._tempdir)
            
            # Copy library to temp location
            espeak_copy = Path(self._tempdir) / library_path.name
            shutil.copy(library_path, espeak_copy, follow_symlinks=False)
            
            # Load the library copy
            self._library = ctypes.cdll.LoadLibrary(str(espeak_copy))
            
            try:
                # CRITICAL FIX: Use 0x00 (no audio) instead of 0x02 (synchronous audio)
                result = self._library.espeak_Initialize(0x00, 0, None, 0)
                if result <= 0:
                    logger.warning(f"⚠️ espeak_Initialize returned {result}, but continuing...")
                else:
                    logger.info(f"✅ espeak initialized successfully (no audio mode): {result}Hz")
            except AttributeError:  # pragma: nocover
                raise RuntimeError('failed to load espeak library') from None
            
            # Store the original library path
            self._library_path = library_path
        
        # Apply the patch
        phonemizer.backend.espeak.api.EspeakAPI.__init__ = patched_espeak_api_init
        logger.info("✅ EspeakAPI patched for WSL2 compatibility")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply phonemizer fix: {e}")
        return False

def test_phonemizer_fix():
    """Test if the phonemizer fix works"""
    try:
        logger.info("🧪 Testing phonemizer fix...")
        
        # Apply the fix
        if not apply_complete_phonemizer_fix():
            return False
        
        # Test phonemizer import and usage
        from phonemizer.backend.espeak.espeak import EspeakBackend
        logger.info("✅ EspeakBackend imported successfully")
        
        # Create backend
        backend = EspeakBackend('en-us')
        logger.info("✅ EspeakBackend created successfully")
        
        # Test phonemization
        result = backend.phonemize(['hello world'])
        logger.info(f"✅ Phonemization successful: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Phonemizer test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

def test_kokoro_with_fix():
    """Test Kokoro with the phonemizer fix"""
    try:
        logger.info("🚀 Testing Kokoro with phonemizer fix...")
        
        # Apply fix first
        if not apply_complete_phonemizer_fix():
            return False
        
        # Set offline mode
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_DATASETS_OFFLINE'] = '1'
        
        # Import Kokoro
        from kokoro import KModel, KPipeline
        logger.info("✅ Kokoro imported successfully!")
        
        # Test with local files
        from pathlib import Path
        model_path = Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        model_file = model_path / "kokoro-v1_0.pth"
        config_file = model_path / "config.json"
        
        if model_file.exists() and config_file.exists():
            logger.info("🔄 Creating KModel...")
            model = KModel(
                repo_id='hexgrad/Kokoro-82M',
                config=str(config_file),
                model=str(model_file)
            )
            logger.info("✅ KModel created successfully!")
            
            logger.info("🔄 Creating KPipeline...")
            pipeline = KPipeline(model)
            logger.info("✅ KPipeline created successfully!")
            
            # Test synthesis
            logger.info("🔄 Testing synthesis...")
            result = list(pipeline("Hello world", voice='af_alloy'))
            if result and len(result) > 0:
                grapheme, phoneme, audio = result[0]
                logger.info(f"✅ Synthesis successful!")
                logger.info(f"   Text: '{grapheme}'")
                logger.info(f"   Phonemes: '{phoneme}'") 
                logger.info(f"   Audio shape: {audio.shape}")
                return True
            else:
                logger.error("❌ Synthesis returned no results")
                return False
        else:
            logger.error(f"❌ Model files not found at {model_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Kokoro test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test phonemizer fix first
        if test_phonemizer_fix():
            logger.info("🎉 Phonemizer fix works!")
            
            # Test full Kokoro integration
            if test_kokoro_with_fix():
                logger.info("🎉 Kokoro TTS is working with the fix!")
            else:
                logger.error("❌ Kokoro still not working")
        else:
            logger.error("❌ Phonemizer fix failed")
    
    asyncio.run(main())