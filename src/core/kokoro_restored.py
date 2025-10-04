"""
Restored Kokoro TTS Wrapper - Fixed version
"""

import torch
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

class RestoredKokoroService:
    """Fixed Kokoro implementation"""

    def __init__(self, model_path: str = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts"):
        self.model_path = Path(model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_state = None
        self.voice_embeddings = {}
        self.config = {}
        self.sample_rate = 24000
        self._initialized = False
        self.inference_pipeline = None

    async def initialize(self, eager_init: bool = True) -> bool:
        try:
            logger.info("🔊 Initializing Restored Kokoro TTS (no dependencies)...")

            # Check for model files
            model_file = self.model_path / "kokoro-v1_0.pth"
            if not model_file.exists():
                logger.error(f"❌ Model file not found: {model_file}")
                return False

            # Load config
            config_file = self.model_path / "config.json"
            if config_file.exists():
                import json
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"✅ Config loaded: {len(self.config.get('vocab', {}))} phonemes")
            else:
                # Default config
                self.config = {
                    "sample_rate": 24000,
                    "n_mels": 80,
                    "n_fft": 1024,
                    "hop_length": 256,
                    "win_length": 1024
                }
                logger.warning("⚠️ No config found, using defaults")

            # Load voice embeddings
            voices_dir = self.model_path / "voices"
            if voices_dir.exists():
                voice_files = list(voices_dir.glob("*.pt"))
                logger.info(f"✅ Found {len(voice_files)} voice files")

                for voice_file in voice_files[:3]:  # Load first few voices
                    voice_name = voice_file.stem
                    try:
                        embedding = torch.load(voice_file, map_location=self.device)
                        self.voice_embeddings[voice_name] = embedding
                        logger.info(f"   - {voice_name}: {embedding.shape}")
                    except Exception as e:
                        logger.warning(f"   - Failed to load {voice_name}: {e}")
            else:
                logger.warning("⚠️ No voices directory found")

            if eager_init:
                # Load the model state dict
                logger.info("🔄 Loading model state dict...")
                self.model_state = torch.load(model_file, map_location=self.device)
                logger.info(f"✅ Model loaded with components: {list(self.model_state.keys())}")

                # Initialize inference pipeline
                logger.info("🔄 Initializing inference pipeline...")
                from .kokoro_inference import kokoro_inference_service
                self.inference_pipeline = kokoro_inference_service

                pipeline_success = await self.inference_pipeline.initialize(
                    model_state=self.model_state,
                    config=self.config,
                    voice_embeddings=self.voice_embeddings
                )

                if pipeline_success:
                    logger.info("✅ Inference pipeline initialized successfully")
                    self._initialized = True
                    return True
                else:
                    logger.error("❌ Inference pipeline initialization failed")
                    self._initialized = False
                    return False
            else:
                self._initialized = True
                return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize restored Kokoro: {e}")
            return False

    async def synthesize(self, text: str, voice: str = 'af_alloy') -> Tuple[Optional[bytes], int]:
        """Synthesize speech using the inference pipeline"""
        if not self._initialized:
            logger.warning("Kokoro not initialized, attempting now...")
            if not await self.initialize():
                return None, 24000

        try:
            # Try real synthesis first
            from .kokoro_real_synthesis import get_real_kokoro_service
            real_service = await get_real_kokoro_service()
            result = await real_service.synthesize(text, voice)
            if result and result[0]:
                return result
            logger.warning("Real synthesis failed, falling back to inference pipeline")

            # Fallback: Use inference pipeline directly
            if self.inference_pipeline:
                logger.info("🔄 Using inference pipeline fallback...")
                audio_bytes = await self.inference_pipeline.synthesize(text, voice)
                if audio_bytes:
                    return audio_bytes, self.sample_rate

            logger.error("All synthesis methods failed")
            return None, self.sample_rate

        except Exception as e:
            logger.error(f"❌ Synthesis failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None, 24000

# Global instance
restored_kokoro_service = RestoredKokoroService()