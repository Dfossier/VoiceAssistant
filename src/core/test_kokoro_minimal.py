"""
Minimal test to verify Kokoro works with our phonemizer fix
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger

async def test_minimal_kokoro():
    """Minimal Kokoro test with timeout protection"""
    try:
        logger.info("🧪 Testing minimal Kokoro with WSL2 fix...")
        
        # Apply our phonemizer fix
        sys.path.append('src')
        from src.core.phonemizer_wsl2_fix import apply_complete_phonemizer_fix
        
        logger.info("Applying phonemizer fix...")
        if not apply_complete_phonemizer_fix():
            return False
        
        # Set offline mode
        import os
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        
        logger.info("Testing Kokoro import with timeout...")
        
        # Import with asyncio timeout
        def import_kokoro():
            from kokoro import KModel, KPipeline
            return KModel, KPipeline
        
        # Run import in executor with timeout
        loop = asyncio.get_event_loop()
        KModel, KPipeline = await asyncio.wait_for(
            loop.run_in_executor(None, import_kokoro),
            timeout=30.0
        )
        logger.info("✅ Kokoro imported successfully!")
        
        # Test KModel creation with timeout
        def create_model():
            model_path = Path('/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts')
            config_file = model_path / 'config.json'
            model_file = model_path / 'kokoro-v1_0.pth'
            
            model = KModel(
                repo_id='hexgrad/Kokoro-82M',
                config=str(config_file),
                model=str(model_file)
            )
            return model
        
        logger.info("Creating KModel with timeout...")
        model = await asyncio.wait_for(
            loop.run_in_executor(None, create_model),
            timeout=60.0
        )
        logger.info("✅ KModel created successfully!")
        
        # Test KPipeline creation with timeout
        def create_pipeline():
            return KPipeline(model)
        
        logger.info("Creating KPipeline with timeout...")
        pipeline = await asyncio.wait_for(
            loop.run_in_executor(None, create_pipeline),
            timeout=30.0
        )
        logger.info("✅ KPipeline created successfully!")
        
        # Test synthesis with timeout
        def test_synthesis():
            result = list(pipeline("Hello world", voice='af_alloy'))
            return result
        
        logger.info("Testing synthesis with timeout...")
        result = await asyncio.wait_for(
            loop.run_in_executor(None, test_synthesis),
            timeout=30.0
        )
        
        if result and len(result) > 0:
            grapheme, phoneme, audio = result[0]
            logger.info("🎉 KOKORO TTS SYNTHESIS SUCCESSFUL!")
            logger.info(f"   Text: '{grapheme}'")
            logger.info(f"   Phonemes: '{phoneme}'")
            logger.info(f"   Audio shape: {audio.shape}")
            logger.info(f"   Audio samples: {audio.shape[0]} ({audio.shape[0]/24000:.2f}s)")
            return True
        else:
            logger.error("❌ Synthesis returned no results")
            return False
            
    except asyncio.TimeoutError:
        logger.error("❌ Kokoro test timed out - likely hanging in WSL2")
        return False
    except Exception as e:
        logger.error(f"❌ Kokoro test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_minimal_kokoro())
    if success:
        print("🎉 SUCCESS: Kokoro TTS is working with the WSL2 fix!")
    else:
        print("❌ FAILED: Kokoro still not working in WSL2")