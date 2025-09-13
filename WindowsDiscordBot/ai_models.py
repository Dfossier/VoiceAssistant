#!/usr/bin/env python3
"""
Local AI Models Handler
Integrates Parakeet ASR, Phi-3 LLM, and Kokoro TTS
"""

import asyncio
import logging
import os
import tempfile
import json
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class LocalModelHandler:
    """Handler for local AI models"""
    
    def __init__(self, eager_load=True):
        self.models_base = Path("/mnt/c/users/dfoss/desktop/localaimodels")
        
        # Model paths
        self.parakeet_path = self.models_base / "parakeet-tdt" / "parakeet-tdt-0.6b-v2.nemo"
        self.phi3_path = self.models_base / "phi3-mini" / "Phi-3-mini-4k-instruct-Q4_K_M.gguf"
        self.kokoro_path = self.models_base / "kokoro-tts" / "kokoro-v1_0.pth"
        self.kokoro_voices = self.models_base / "kokoro-tts" / "voices"
        
        # Model instances
        self._parakeet_model = None
        self._phi3_model = None
        self._kokoro_model = None
        
        # Check model availability
        self._check_models()
        
        # Eagerly load models at startup if requested
        if eager_load:
            self._eager_load_models()
    
    def _eager_load_models(self):
        """Load all models eagerly at startup"""
        logger.info("🚀 Starting eager model loading...")
        
        # Load Parakeet model
        try:
            if self.parakeet_path.exists():
                logger.info("Loading Parakeet ASR model...")
                self._parakeet_model = asyncio.run(self._load_parakeet())
                if self._parakeet_model:
                    logger.info("✅ Parakeet model loaded successfully")
                else:
                    logger.error("❌ Failed to load Parakeet model")
            else:
                logger.warning("⚠️ Parakeet model not found")
        except Exception as e:
            logger.error(f"❌ Error loading Parakeet model: {e}")
            
        # Load Phi-3 model
        try:
            if self.phi3_path.exists():
                logger.info("Loading Phi-3 model...")
                self._phi3_model = asyncio.run(self._load_phi3())
                if self._phi3_model:
                    logger.info("✅ Phi-3 model loaded successfully")
                else:
                    logger.error("❌ Failed to load Phi-3 model")
            else:
                logger.warning("⚠️ Phi-3 model not found")
        except Exception as e:
            logger.error(f"❌ Error loading Phi-3 model: {e}")
            
        # Load Kokoro model
        try:
            if self.kokoro_path.exists():
                logger.info("Loading Kokoro TTS model...")
                self._kokoro_model = asyncio.run(self._load_kokoro())
                if self._kokoro_model:
                    logger.info("✅ Kokoro model loaded successfully")
                else:
                    logger.error("❌ Failed to load Kokoro model")
            else:
                logger.warning("⚠️ Kokoro model not found")
        except Exception as e:
            logger.error(f"❌ Error loading Kokoro model: {e}")
            
        logger.info("🏁 Eager model loading completed")
        
    def _check_models(self):
        """Check which models are available"""
        models_status = {
            "Parakeet": self.parakeet_path.exists(),
            "Phi-3": self.phi3_path.exists(), 
            "Kokoro": self.kokoro_path.exists()
        }
        
        available = [name for name, status in models_status.items() if status]
        missing = [name for name, status in models_status.items() if not status]
        
        if available:
            logger.info(f"✅ Available models: {', '.join(available)}")
        if missing:
            logger.warning(f"⚠️ Missing models: {', '.join(missing)}")
    
    async def transcribe_parakeet(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Parakeet ASR model"""
        try:
            if not self.parakeet_path.exists():
                logger.warning("⚠️ Parakeet model not found")
                return None
            
            # Load model if not already loaded (fallback for lazy loading disabled)
            if self._parakeet_model is None:
                logger.warning("Model not loaded, attempting to load now...")
                self._parakeet_model = await self._load_parakeet()
            
            if self._parakeet_model is None:
                return None
            
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Run inference
                text = await self._run_parakeet_inference(temp_path)
                return text
            finally:
                # Clean up temp file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"❌ Parakeet transcription error: {e}")
            return None
    
    async def _load_parakeet(self):
        """Load Parakeet model (NeMo)"""
        try:
            logger.info("🔄 Loading Parakeet ASR model...")
            
            # Try NeMo toolkit
            try:
                import nemo.collections.asr as nemo_asr
                model = nemo_asr.models.EncDecRNNTBPEModel.restore_from(str(self.parakeet_path))
                logger.info("✅ Parakeet model loaded with NeMo")
                return model
            except ImportError:
                logger.warning("⚠️ NeMo toolkit not available")
            
            # Try ONNX runtime if available
            try:
                import onnxruntime as ort
                # Look for ONNX version
                onnx_path = self.parakeet_path.with_suffix('.onnx')
                if onnx_path.exists():
                    session = ort.InferenceSession(str(onnx_path))
                    logger.info("✅ Parakeet model loaded with ONNX")
                    return {'type': 'onnx', 'session': session}
            except ImportError:
                logger.warning("⚠️ ONNX runtime not available")
            
            logger.warning("⚠️ Could not load Parakeet model")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading Parakeet: {e}")
            return None
    
    async def _run_parakeet_inference(self, audio_path: str) -> Optional[str]:
        """Run Parakeet inference on audio file"""
        try:
            if self._parakeet_model is None:
                return None
            
            # Handle different model types
            if hasattr(self._parakeet_model, 'transcribe'):
                # NeMo model
                transcription = self._parakeet_model.transcribe([audio_path])
                if transcription and len(transcription) > 0:
                    return transcription[0].strip()
            
            elif isinstance(self._parakeet_model, dict) and self._parakeet_model.get('type') == 'onnx':
                # ONNX model - would need preprocessing
                logger.warning("⚠️ ONNX Parakeet inference not implemented yet")
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Parakeet inference error: {e}")
            return None
    
    async def generate_phi3(self, text: str, user_name: str = "User") -> Optional[str]:
        """Generate response using Phi-3 model"""
        try:
            if not self.phi3_path.exists():
                logger.warning("⚠️ Phi-3 model not found")
                return None
            
            # Load model if not already loaded (fallback for lazy loading disabled)
            if self._phi3_model is None:
                logger.warning("Model not loaded, attempting to load now...")
                self._phi3_model = await self._load_phi3()
            
            if self._phi3_model is None:
                return None
            
            # Generate response
            response = await self._run_phi3_inference(text, user_name)
            return response
            
        except Exception as e:
            logger.error(f"❌ Phi-3 generation error: {e}")
            return None
    
    async def _load_phi3(self):
        """Load Phi-3 model using llama-cpp-python"""
        try:
            logger.info("🔄 Loading Phi-3 model...")
            
            try:
                from llama_cpp import Llama
                
                model = Llama(
                    model_path=str(self.phi3_path),
                    n_ctx=4096,  # Context window
                    n_batch=512,
                    n_threads=4,
                    verbose=False
                )
                
                logger.info("✅ Phi-3 model loaded with llama-cpp")
                return model
                
            except ImportError:
                logger.warning("⚠️ llama-cpp-python not available")
            
            # Try transformers as fallback
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                
                # This would require a HuggingFace version of Phi-3
                model_name = "microsoft/Phi-3-mini-4k-instruct"
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype="auto",
                    device_map="auto"
                )
                
                logger.info("✅ Phi-3 model loaded with transformers")
                return {'type': 'transformers', 'model': model, 'tokenizer': tokenizer}
                
            except ImportError:
                logger.warning("⚠️ transformers not available")
            
            logger.warning("⚠️ Could not load Phi-3 model")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading Phi-3: {e}")
            return None
    
    async def _run_phi3_inference(self, text: str, user_name: str) -> Optional[str]:
        """Run Phi-3 inference"""
        try:
            if self._phi3_model is None:
                return None
            
            # Create prompt
            prompt = f"""<|system|>
You are a helpful AI assistant in a Discord voice chat. Keep responses concise (1-2 sentences), conversational, and friendly. The user's name is {user_name}.
<|end|>
<|user|>
{text}
<|end|>
<|assistant|>
"""
            
            # Handle different model types
            if hasattr(self._phi3_model, 'create_completion'):
                # llama-cpp model
                response = self._phi3_model.create_completion(
                    prompt,
                    max_tokens=150,
                    temperature=0.7,
                    stop=["<|end|>", "<|user|>", "<|system|>"],
                    echo=False
                )
                
                return response['choices'][0]['text'].strip()
            
            elif isinstance(self._phi3_model, dict) and self._phi3_model.get('type') == 'transformers':
                # Transformers model
                model = self._phi3_model['model']
                tokenizer = self._phi3_model['tokenizer']
                
                inputs = tokenizer(prompt, return_tensors="pt")
                outputs = model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + 150,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
                
                response = tokenizer.decode(outputs[0], skip_special_tokens=True)
                # Extract just the assistant response
                response = response.split("<|assistant|>")[-1].strip()
                
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Phi-3 inference error: {e}")
            return None
    
    async def synthesize_kokoro(self, text: str, voice: str = "af_heart") -> Optional[bytes]:
        """Synthesize speech using Kokoro TTS"""
        try:
            if not self.kokoro_path.exists():
                logger.warning("⚠️ Kokoro model not found")
                return None
            
            # Load model if not already loaded (fallback for lazy loading disabled)
            if self._kokoro_model is None:
                logger.warning("Model not loaded, attempting to load now...")
                self._kokoro_model = await self._load_kokoro()
            
            if self._kokoro_model is None:
                return None
            
            # Generate speech
            audio_data = await self._run_kokoro_inference(text, voice)
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ Kokoro synthesis error: {e}")
            return None
    
    async def _load_kokoro(self):
        """Load Kokoro TTS model"""
        try:
            logger.info("🔄 Loading Kokoro TTS model...")
            
            try:
                import torch
                import torchaudio
                
                # Load main model
                model = torch.load(str(self.kokoro_path), map_location='cpu')
                
                # Load voice embeddings
                voices = {}
                if self.kokoro_voices.exists():
                    for voice_file in self.kokoro_voices.glob("*.pt"):
                        voice_name = voice_file.stem
                        voices[voice_name] = torch.load(voice_file, map_location='cpu')
                
                logger.info(f"✅ Kokoro model loaded with {len(voices)} voices")
                return {
                    'model': model,
                    'voices': voices
                }
                
            except ImportError:
                logger.warning("⚠️ PyTorch not available for Kokoro")
            
            logger.warning("⚠️ Could not load Kokoro model")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error loading Kokoro: {e}")
            return None
    
    async def _run_kokoro_inference(self, text: str, voice: str) -> Optional[bytes]:
        """Run Kokoro TTS inference"""
        try:
            if self._kokoro_model is None:
                return None
            
            model = self._kokoro_model['model']
            voices = self._kokoro_model['voices']
            
            if voice not in voices:
                # Use default voice
                voice = list(voices.keys())[0] if voices else None
                if voice is None:
                    logger.warning("⚠️ No voices available for Kokoro")
                    return None
            
            # This is a simplified version - actual Kokoro inference
            # would require understanding the specific model architecture
            logger.info(f"🗣️ Synthesizing with Kokoro voice: {voice}")
            
            # Placeholder for actual Kokoro inference
            # In reality, this would:
            # 1. Tokenize text
            # 2. Run through the model with voice embedding
            # 3. Convert output to audio waveform
            # 4. Return as WAV bytes
            
            logger.warning("⚠️ Kokoro inference implementation needed")
            return None
            
        except Exception as e:
            logger.error(f"❌ Kokoro inference error: {e}")
            return None
    
    def get_available_models(self) -> Dict[str, bool]:
        """Get status of all models"""
        return {
            "parakeet": self.parakeet_path.exists(),
            "phi3": self.phi3_path.exists(),
            "kokoro": self.kokoro_path.exists()
        }
    
    def get_kokoro_voices(self) -> list:
        """Get available Kokoro voices"""
        if not self.kokoro_voices.exists():
            return []
        
        return [f.stem for f in self.kokoro_voices.glob("*.pt")]

# Utility functions for audio processing
def convert_audio_format(input_data: bytes, target_format: str = "wav") -> bytes:
    """Convert audio between formats"""
    try:
        import tempfile
        import subprocess
        
        with tempfile.NamedTemporaryFile(suffix=".raw") as input_file:
            input_file.write(input_data)
            input_file.flush()
            
            with tempfile.NamedTemporaryFile(suffix=f".{target_format}") as output_file:
                # Use ffmpeg to convert
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "s16le",
                    "-ar", "48000",
                    "-ac", "2",
                    "-i", input_file.name,
                    output_file.name
                ], capture_output=True, check=True)
                
                return output_file.read()
                
    except Exception as e:
        logger.error(f"❌ Audio conversion error: {e}")
        return input_data  # Return original if conversion fails

def normalize_audio(audio_data: bytes, target_volume: float = 0.5) -> bytes:
    """Normalize audio volume"""
    try:
        import numpy as np
        
        # Convert to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        
        # Normalize
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = audio_np / max_val * target_volume * 32767
        
        # Convert back to bytes
        return audio_np.astype(np.int16).tobytes()
        
    except Exception as e:
        logger.error(f"❌ Audio normalization error: {e}")
        return audio_data