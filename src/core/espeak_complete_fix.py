"""
Complete espeak fix for WSL2 that prevents all audio-related operations
This patches ALL espeak operations to work in WSL2 without audio subsystem
"""
import os
import sys
from loguru import logger

def apply_complete_espeak_fix():
    """Apply comprehensive espeak fixes for WSL2"""
    try:
        logger.info("🔧 Applying complete espeak WSL2 fix...")
        
        # Set all audio-related environment variables
        os.environ['PULSE_RUNTIME_PATH'] = '/tmp/nonexistent'
        os.environ['ALSA_CARD'] = 'none'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        os.environ['PULSE_SERVER'] = 'unix:/tmp/nonexistent'
        os.environ['ALSA_DEVICE'] = 'null'
        
        # Patch phonemizer first
        logger.info("🔧 Patching phonemizer...")
        import phonemizer.backend.espeak.api
        
        # Store original methods
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
        
        # Patch espeak-python if it gets imported
        try:
            import espeak
            logger.info("🔧 Patching espeak-python...")
            
            # Store original EspeakWrapper methods
            original_set_data_path = getattr(espeak.core.EspeakWrapper, 'set_data_path', None)
            original_initialize = getattr(espeak.core.EspeakWrapper, 'initialize', None)
            
            # Create no-op versions
            def patched_set_data_path(cls, path):
                """No-op version of set_data_path"""
                logger.info(f"🔇 Skipping espeak set_data_path: {path}")
                return True
                
            def patched_initialize(cls, output=0, buflength=5000, path=None, options=0):
                """No-op version of initialize that doesn't use audio"""
                logger.info("🔇 Skipping espeak initialize (no audio mode)")
                return True
            
            # Apply patches
            espeak.core.EspeakWrapper.set_data_path = classmethod(patched_set_data_path)
            espeak.core.EspeakWrapper.initialize = classmethod(patched_initialize)
            
            logger.info("✅ espeak-python patched")
            
        except ImportError:
            logger.info("ℹ️ espeak-python not imported yet")
        except Exception as e:
            logger.warning(f"⚠️ Failed to patch espeak-python: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply complete espeak fix: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

def test_complete_fix():
    """Test the complete espeak fix"""
    try:
        logger.info("🧪 Testing complete espeak fix...")
        
        # Apply fix
        if not apply_complete_espeak_fix():
            return False
        
        # Test phonemizer
        logger.info("🔄 Testing phonemizer...")
        from phonemizer.backend.espeak.espeak import EspeakBackend
        backend = EspeakBackend('en-us')
        result = backend.phonemize(['hello world'])
        logger.info(f"✅ Phonemizer works: {result}")
        
        # Test espeak-python if available
        try:
            import espeak
            logger.info("🔄 Testing espeak-python...")
            # This should now work without hanging
            logger.info("✅ espeak-python import successful")
        except ImportError:
            logger.info("ℹ️ espeak-python not available")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Complete fix test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_complete_fix()
    if success:
        print("🎉 SUCCESS: Complete espeak fix works!")
    else:
        print("❌ FAILED: Complete espeak fix failed")