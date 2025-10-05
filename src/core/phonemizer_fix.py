"""
Phonemizer compatibility fix for Kokoro/Misaki
This must be imported BEFORE any kokoro imports
"""

import logging

logger = logging.getLogger(__name__)

def apply_phonemizer_fix():
    """Apply phonemizer compatibility fix for misaki package"""
    try:
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        
        if not hasattr(EspeakWrapper, 'set_data_path'):
            logger.info("🔧 Applying phonemizer compatibility fix...")
            
            @staticmethod
            def set_data_path(path):
                """Compatibility method for misaki package"""
                import os
                os.environ['ESPEAK_DATA_PATH'] = str(path)
                # Also set the data_path attribute if it exists
                if hasattr(EspeakWrapper, 'data_path'):
                    EspeakWrapper.data_path = path
            
            EspeakWrapper.set_data_path = set_data_path
            logger.info("✅ Phonemizer compatibility fix applied")
            return True
    except Exception as e:
        logger.warning(f"Could not apply phonemizer fix: {e}")
        return False
    
    return True

# Apply the fix immediately on import
apply_phonemizer_fix()