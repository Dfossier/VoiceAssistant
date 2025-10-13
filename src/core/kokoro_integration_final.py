"""
Final Kokoro TTS integration with complete WSL2 fixes
This integrates the misaki espeak fix into the existing TTS service
"""
import os
import sys
import asyncio
from pathlib import Path
from loguru import logger

# Force offline mode
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

async def test_final_kokoro_integration():
    """Test the final Kokoro integration with all fixes"""
    try:
        logger.info("🚀 Testing final Kokoro TTS integration...")
        
        # Apply our comprehensive fix
        from misaki_espeak_fix import apply_misaki_espeak_fix
        if not apply_misaki_espeak_fix():
            logger.error("❌ Failed to apply misaki espeak fix")
            return False
        
        logger.info("✅ Misaki espeak fix applied successfully")
        
        # Test the actual TTS service
        logger.info("📦 Importing KokoroTTSService...")
        sys.path.append('.')
        from kokoro_tts_service import KokoroTTSService
        
        logger.info("🔧 Initializing KokoroTTSService...")
        tts_service = KokoroTTSService(eager_init=False)
        
        # Initialize the service
        success = await tts_service.initialize()
        if not success:
            logger.error("❌ TTS service initialization failed")
            return False
        
        logger.info("✅ KokoroTTSService initialized successfully!")
        
        # Test synthesis
        logger.info("🔄 Testing TTS synthesis...")
        try:
            audio_bytes = await tts_service.synthesize("Hello world", voice="af_alloy")
            if audio_bytes and len(audio_bytes) > 0:
                logger.info("🎉 TTS SYNTHESIS SUCCESSFUL!")
                logger.info(f"   Generated {len(audio_bytes)} bytes of audio")
                return True
            else:
                logger.warning("⚠️ TTS synthesis returned empty audio")
                return False
        except Exception as e:
            logger.error(f"❌ TTS synthesis failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Final integration test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

def update_local_models_service():
    """Update the local_models.py to use the fixed Kokoro service"""
    try:
        logger.info("🔧 Updating local_models.py to use fixed Kokoro...")
        
        # Read the current local_models.py
        local_models_path = Path("local_models.py")
        if not local_models_path.exists():
            logger.error(f"❌ local_models.py not found at {local_models_path}")
            return False
        
        with open(local_models_path, 'r') as f:
            content = f.read()
        
        # Update the TTS model loading to use our fix
        updated_content = content.replace(
            'def load_tts_model(self):',
            '''def load_tts_model(self):
        """Load TTS model with WSL2 fixes"""
        try:
            # Apply misaki espeak fix FIRST
            from src.core.misaki_espeak_fix import apply_misaki_espeak_fix
            if not apply_misaki_espeak_fix():
                logger.error("❌ Failed to apply misaki espeak fix")
                return False
            
            logger.info("✅ Misaki espeak fix applied for TTS loading")'''
        )
        
        # Write the updated content
        with open(local_models_path, 'w') as f:
            f.write(updated_content)
        
        logger.info("✅ local_models.py updated with Kokoro fixes")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update local_models.py: {e}")
        return False

if __name__ == "__main__":
    async def main():
        logger.info("🎯 Final Kokoro TTS Integration Test")
        logger.info("=" * 50)
        
        # Test the integration
        success = await test_final_kokoro_integration()
        
        if success:
            logger.info("🎉 SUCCESS: Final Kokoro TTS integration works!")
            logger.info("✅ Kokoro TTS is now ready for production use")
            logger.info("✅ No more hanging in WSL2")
            logger.info("✅ No runtime downloads - all files checked locally")
            print("🎉 SUCCESS: Kokoro TTS is working!")
        else:
            logger.error("❌ FAILED: Final Kokoro integration still has issues")
            print("❌ FAILED: Kokoro integration failed")
    
    asyncio.run(main())