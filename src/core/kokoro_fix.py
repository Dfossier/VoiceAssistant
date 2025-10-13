"""
Fix for Kokoro TTS hanging issue by patching espeak initialization
"""

import os
import ctypes
from pathlib import Path
from loguru import logger

def patch_espeak_initialization():
    """Patch espeak to prevent hanging on initialization"""
    try:
        logger.info("🔧 Applying espeak initialization patch...")
        
        # Set environment variables to prevent audio system issues
        os.environ['PULSE_RUNTIME_PATH'] = '/tmp/nonexistent'  # Disable PulseAudio
        os.environ['ALSA_CARD'] = 'none'  # Disable ALSA
        os.environ['SDL_AUDIODRIVER'] = 'dummy'  # Use dummy audio driver
        
        # Monkey patch the EspeakAPI initialization
        from phonemizer.backend.espeak.api import EspeakAPI
        
        # Store original __init__
        original_init = EspeakAPI.__init__
        
        def patched_init(self, library):
            """Patched EspeakAPI initialization that uses no audio output"""
            # set to None to avoid an AttributeError in _delete if the __init__
            # method raises, will be properly initialized below
            self._library = None
            
            # Load the original library
            try:
                espeak = ctypes.cdll.LoadLibrary(str(library))
                library_path = self._shared_library_path(espeak)
                del espeak
            except OSError as error:
                raise RuntimeError(
                    f'failed to load espeak library: {str(error)}') from None
            
            # Create temp directory
            import tempfile
            import shutil
            import weakref
            import atexit
            import sys
            
            self._tempdir = tempfile.mkdtemp()
            
            if sys.platform == 'win32':  # pragma: nocover
                atexit.register(self._delete_win32)
            else:
                weakref.finalize(self, self._delete, self._library, self._tempdir)
            
            espeak_copy = Path(self._tempdir) / library_path.name
            shutil.copy(library_path, espeak_copy, follow_symlinks=False)
            
            # Load the library copy
            self._library = ctypes.cdll.LoadLibrary(str(espeak_copy))
            
            # CRITICAL CHANGE: Use AUDIO_OUTPUT_PLAYBACK (0x00) instead of SYNCHRONOUS (0x02)
            # This prevents espeak from trying to initialize audio output
            try:
                result = self._library.espeak_Initialize(0x00, 0, None, 0)  # No audio output
                if result <= 0:
                    logger.warning("⚠️ espeak_Initialize returned error, but continuing...")
                else:
                    logger.info("✅ espeak initialized successfully with no audio")
            except AttributeError:  # pragma: nocover
                raise RuntimeError(
                    'failed to load espeak library') from None
            
            # Store the library path
            self._library_path = library_path
        
        # Apply the patch
        EspeakAPI.__init__ = patched_init
        logger.info("✅ EspeakAPI initialization patched successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to patch espeak initialization: {e}")
        return False

def test_kokoro_with_patch():
    """Test if Kokoro works after applying the patch"""
    try:
        logger.info("🧪 Testing Kokoro with espeak patch...")
        
        # Apply the patch first
        if not patch_espeak_initialization():
            return False
        
        # Now try to import and use Kokoro
        from kokoro import KModel, KPipeline
        logger.info("✅ Kokoro imported successfully!")
        
        # Test with local files
        model_path = Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        model_file = model_path / "kokoro-v1_0.pth"
        config_file = model_path / "config.json"
        
        if model_file.exists() and config_file.exists():
            logger.info("🔄 Creating KModel with local files...")
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
            if result:
                logger.info(f"✅ Synthesis successful! Generated {len(result)} segments")
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
        success = test_kokoro_with_patch()
        if success:
            print("🎉 Kokoro is working with the patch!")
        else:
            print("❌ Kokoro still not working")
    
    asyncio.run(main())