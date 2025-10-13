#!/usr/bin/env python3
"""
Phonemizer compatibility fix for Kokoro TTS
Adds the missing set_data_path method that misaki expects
"""

import logging

logger = logging.getLogger(__name__)

def patch_espeak_wrapper():
    """Add missing set_data_path method to EspeakWrapper for misaki compatibility"""
    try:
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        
        if not hasattr(EspeakWrapper, 'set_data_path'):
            logger.info("🔧 Applying EspeakWrapper.set_data_path compatibility patch...")
            
            @staticmethod
            def set_data_path(path):
                """Compatibility method for misaki package - sets ESPEAK_DATA_PATH environment variable"""
                import os
                logger.debug(f"Setting ESPEAK_DATA_PATH to: {path}")
                os.environ['ESPEAK_DATA_PATH'] = str(path)
                
            # Add the missing method to the class
            EspeakWrapper.set_data_path = set_data_path
            logger.info("✅ EspeakWrapper.set_data_path compatibility patch applied successfully")
            return True
        else:
            logger.info("✅ EspeakWrapper.set_data_path method already exists")
            return True
            
    except ImportError as e:
        logger.error(f"❌ Cannot import EspeakWrapper: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to patch EspeakWrapper: {e}")
        return False

if __name__ == "__main__":
    # Test the patch
    logging.basicConfig(level=logging.INFO)
    success = patch_espeak_wrapper()
    
    if success:
        print("Testing the patch...")
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        print(f"set_data_path method exists: {hasattr(EspeakWrapper, 'set_data_path')}")
        
        # Test calling the method
        try:
            EspeakWrapper.set_data_path('/usr/share/espeak-ng-data')
            print("✅ Successfully called set_data_path method")
        except Exception as e:
            print(f"❌ Error calling set_data_path: {e}")
    else:
        print("❌ Failed to apply patch")