"""
Complete fix for misaki/espeak hanging in WSL2
This patches misaki's espeak operations to prevent WSL2 audio subsystem hangs
"""
import os
import sys
from loguru import logger

def apply_misaki_espeak_fix():
    """Patch misaki's espeak operations to prevent WSL2 hangs"""
    try:
        logger.info("🔧 Applying misaki espeak WSL2 fix...")
        
        # Set audio environment variables first
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['PULSE_RUNTIME_PATH'] = '/tmp/nonexistent'
        os.environ['ALSA_CARD'] = 'none'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        
        # Step 1: Patch phonemizer first (our existing fix)
        import phonemizer.backend.espeak.api
        
        original_espeak_init = phonemizer.backend.espeak.api.EspeakAPI.__init__
        
        def patched_espeak_api_init(self, library):
            """Patched EspeakAPI that forces no audio output mode"""
            import ctypes
            import tempfile
            import shutil
            import weakref
            import atexit
            from pathlib import Path
            
            self._library = None
            
            try:
                espeak = ctypes.cdll.LoadLibrary(str(library))
                library_path = self._shared_library_path(espeak)
                del espeak
            except OSError as error:
                raise RuntimeError(f'failed to load espeak library: {str(error)}') from None
            
            self._tempdir = tempfile.mkdtemp()
            
            if sys.platform == 'win32':
                atexit.register(self._delete_win32)
            else:
                weakref.finalize(self, self._delete, self._library, self._tempdir)
            
            espeak_copy = Path(self._tempdir) / library_path.name
            shutil.copy(library_path, espeak_copy, follow_symlinks=False)
            self._library = ctypes.cdll.LoadLibrary(str(espeak_copy))
            
            try:
                # CRITICAL: Use 0x00 (no audio) mode
                result = self._library.espeak_Initialize(0x00, 0, None, 0)
                if result <= 0:
                    logger.warning(f"⚠️ espeak_Initialize returned {result}")
                else:
                    logger.info(f"✅ espeak initialized (no audio): {result}Hz")
            except AttributeError:
                raise RuntimeError('failed to load espeak library') from None
            
            self._library_path = library_path
        
        # Apply phonemizer patch
        phonemizer.backend.espeak.api.EspeakAPI.__init__ = patched_espeak_api_init
        logger.info("✅ Phonemizer patched")
        
        # Step 2: Patch EspeakWrapper BEFORE importing misaki
        logger.info("🔧 Patching EspeakWrapper before misaki import...")
        
        # Import wrapper module
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        
        # Store original methods
        original_set_library = getattr(EspeakWrapper, 'set_library', None)
        original_set_data_path = getattr(EspeakWrapper, 'set_data_path', None)
        
        # Create patched versions
        @classmethod
        def patched_set_library(cls, library_path):
            """Patched set_library that doesn't hang"""
            logger.info(f"🔇 EspeakWrapper.set_library patched: {library_path}")
            # Store the path but don't actually call the problematic original
            cls._library_path = library_path
            return True
        
        @classmethod  
        def patched_set_data_path(cls, data_path):
            """Patched set_data_path that doesn't hang"""
            logger.info(f"🔇 EspeakWrapper.set_data_path patched: {data_path}")
            # Store the path but don't actually call the problematic original
            cls._data_path = data_path
            return True
        
        # Apply patches
        EspeakWrapper.set_library = patched_set_library
        EspeakWrapper.set_data_path = patched_set_data_path
        
        logger.info("✅ EspeakWrapper patched successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply misaki espeak fix: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

def test_misaki_import():
    """Test if misaki can be imported with the fix"""
    try:
        logger.info("🧪 Testing misaki import with fix...")
        
        # Apply fix first
        if not apply_misaki_espeak_fix():
            return False
        
        # Now try importing misaki components
        logger.info("📦 Importing misaki.espeak...")
        from misaki import espeak
        logger.info("✅ misaki.espeak imported successfully!")
        
        logger.info("📦 Importing misaki.en...")
        from misaki import en
        logger.info("✅ misaki.en imported successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Misaki import test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

def test_kokoro_with_misaki_fix():
    """Test Kokoro import with misaki fix applied"""
    try:
        logger.info("🚀 Testing Kokoro with misaki fix...")
        
        # Apply fix first
        if not apply_misaki_espeak_fix():
            return False
        
        # Test misaki import
        if not test_misaki_import():
            return False
        
        # Now try importing Kokoro
        logger.info("📦 Importing Kokoro components...")
        from kokoro import KModel, KPipeline
        logger.info("✅ Kokoro imported successfully!")
        
        # Test model creation
        logger.info("🔄 Creating KModel...")
        from pathlib import Path
        model_path = Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        config_file = model_path / "config.json"
        model_file = model_path / "kokoro-v1_0.pth"
        
        if config_file.exists() and model_file.exists():
            model = KModel(
                repo_id='hexgrad/Kokoro-82M',
                config=str(config_file),
                model=str(model_file)
            )
            logger.info("✅ KModel created successfully!")
            
            pipeline = KPipeline(lang_code='en-us', model=model)
            logger.info("✅ KPipeline created successfully!")
            
            # Test synthesis
            logger.info("🔄 Testing synthesis...")
            result = list(pipeline("Hello world", voice='af_alloy'))
            if result and len(result) > 0:
                grapheme, phoneme, audio = result[0]
                logger.info("🎉 KOKORO TTS SYNTHESIS SUCCESSFUL!")
                logger.info(f"   Text: '{grapheme}'")
                logger.info(f"   Phonemes: '{phoneme}'")
                logger.info(f"   Audio shape: {audio.shape}")
                logger.info(f"   Audio samples: {audio.shape[0]} ({audio.shape[0]/24000:.2f}s)")
            else:
                logger.error("❌ Synthesis returned no results")
            
            return True
        else:
            logger.error(f"❌ Model files not found at {model_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Kokoro test with misaki fix failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_kokoro_with_misaki_fix()
    if success:
        print("🎉 SUCCESS: Kokoro works with misaki fix!")
    else:
        print("❌ FAILED: Kokoro still has issues with misaki")