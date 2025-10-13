"""Local model management for STT, LLM, and TTS using local models"""
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

class LocalModelManager:
    """Manages local models for speech-to-text, language model, and text-to-speech"""
    
    def __init__(self, skip_stt: bool = True, eager_load: bool = True):  # Skip STT - Pipecat handles Whisper
        self.models_dir = Path("/mnt/c/users/dfoss/desktop/localaimodels")
        self.skip_stt = skip_stt  # Flag to skip STT model loading (use Pipecat's Whisper instead)
        self.eager_load = eager_load  # Flag to enable eager loading
        self.models = {
            'stt': None,  # Parakeet-TDT (skipped when using Pipecat)
            'llm': None,  # Phi-3 Mini
            'tts': None   # Kokoro TTS
        }
        
        # Check for optional dependencies once at initialization
        self.has_whisper = self._check_whisper()
        if not self.has_whisper:
            logger.info("Whisper not available - transcription may be limited")
        self.model_configs = {
            # 'phi3_mini': {
            #     'type': 'llm', 
            #     'path': self.models_dir / 'phi3-mini',
            #     'model_type': 'gguf',
            #     'description': 'Microsoft Phi-3 Mini for language generation (disabled - using SmolLM2 instead)'
            # },
            'smollm2_1.7b': {
                'type': 'llm',
                'path': self.models_dir / 'smollm2-1.7b',
                'model_type': 'gguf',
                'description': 'SmolLM2 1.7B - Fast conversational model'
            },
            'kokoro_tts': {
                'type': 'tts',
                'path': self.models_dir / 'kokoro-tts',
                'model_type': 'pytorch',
                'description': 'Kokoro TTS for speech synthesis'
            }
        }
        
    def _check_whisper(self):
        """Check if Whisper is available"""
        try:
            import faster_whisper
            return True
        except ImportError:
            try:
                import whisper
                return True
            except ImportError:
                return False
        
    async def initialize(self):
        """Initialize and verify local models"""
        logger.info("Initializing local model manager...")
        
        # Check GPU availability
        try:
            import torch
            logger.info(f"🔧 PyTorch version: {torch.__version__}")
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"🚀 GPU detected: {gpu_name} ({gpu_count} device(s))")
                logger.info(f"🚀 CUDA version: {torch.version.cuda}")
            else:
                logger.info("🖥️  No GPU detected - using CPU only")
        except ImportError as e:
            logger.info(f"🖥️  PyTorch not available - CPU only (ImportError: {e})")
        except Exception as e:
            logger.warning(f"⚠️  Error checking GPU: {e}")
        
        for model_name, config in self.model_configs.items():
            if config['path'].exists():
                logger.info(f"✅ Found {config['type'].upper()} model: {model_name} at {config['path']}")
                
                # Check for model files
                model_files = list(config['path'].glob("*.onnx")) + \
                             list(config['path'].glob("*.pt")) + \
                             list(config['path'].glob("*.pth")) + \
                             list(config['path'].glob("*.gguf")) + \
                             list(config['path'].glob("*.nemo")) + \
                             list(config['path'].glob("*.bin"))
                
                if model_files:
                    logger.info(f"   Model files found: {len(model_files)}")
                    for f in model_files[:3]:  # Show first 3 files
                        logger.info(f"   - {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")
                else:
                    logger.warning(f"   No model files found in {config['path']}")
            else:
                logger.warning(f"❌ {config['type'].upper()} model not found: {config['path']}")
        
        # Eagerly load all models if requested
        if self.eager_load:
            logger.info("🚀 Starting eager model loading...")
            
            # STT handled by Faster-Whisper
            logger.info("📢 STT will be handled by Faster-Whisper model")
                
            # Load LLM model
            try:
                llm_loaded = await self.load_llm_model()
                logger.info(f"LLM model loading: {'✅ Success' if llm_loaded else '❌ Failed'}")
            except Exception as e:
                logger.error(f"❌ Error loading LLM model: {e}")
                
            # Load TTS model
            try:
                tts_loaded = await self.load_tts_model()
                logger.info(f"TTS model loading: {'✅ Success' if tts_loaded else '❌ Failed'}")
            except Exception as e:
                logger.error(f"❌ Error loading TTS model: {e}")
            
            # Load Faster-Whisper model for STT with performance optimizations
            try:
                logger.info("🎤 Loading Faster-Whisper model for STT...")
                from faster_whisper import WhisperModel
                import torch
                import os
                
                # Create local model cache directory
                model_cache_dir = Path("./models/faster-whisper")
                model_cache_dir.mkdir(parents=True, exist_ok=True)
                
                self._faster_whisper_model = WhisperModel(
                    "small.en",   # Use small model for better accuracy
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    compute_type="float16" if torch.cuda.is_available() else "int8",
                    # Performance optimizations with CUDA acceleration
                    num_workers=2 if torch.cuda.is_available() else 1,  # More workers for GPU
                    download_root=str(model_cache_dir),  # Local cache to avoid re-downloads
                    local_files_only=False  # Allow downloads but cache locally
                )
                
                device_info = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
                logger.info(f"✅ Faster-Whisper Small model loaded with {device_info} acceleration")
                
                # Model warming: Run a small test transcription to initialize GPU kernels
                await self._warm_whisper_model()
                
            except Exception as e:
                logger.error(f"❌ Error loading Faster-Whisper model: {e}")
                self._faster_whisper_model = None
                    
            logger.info("🏁 Eager model loading completed")
    
    async def _warm_whisper_model(self):
        """Warm up Faster-Whisper model with a test transcription to initialize GPU kernels"""
        if not self._faster_whisper_model:
            return
            
        try:
            logger.info("🔥 Warming up Faster-Whisper model...")
            import numpy as np
            import time
            
            # Generate 1 second of silence for warming
            sample_rate = 16000
            warmup_audio = np.zeros(sample_rate, dtype=np.float32)
            
            start_time = time.time()
            # Use same optimized parameters as main transcription
            segments, info = self._faster_whisper_model.transcribe(
                warmup_audio,
                language="en",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5,
                    max_speech_duration_s=30
                )
            )
            
            warmup_time = (time.time() - start_time) * 1000
            logger.info(f"✅ Faster-Whisper model warmed up in {warmup_time:.1f}ms")
            
        except Exception as e:
            logger.warning(f"⚠️ Model warmup failed (not critical): {e}")
    
    def _is_whisper_model_ready(self) -> bool:
        """Check if Faster-Whisper model is properly loaded and ready for use"""
        try:
            return (hasattr(self, '_faster_whisper_model') and 
                    self._faster_whisper_model is not None and
                    hasattr(self._faster_whisper_model, 'transcribe'))
        except Exception:
            return False
                
    # Removed load_stt_model - using Faster-Whisper instead
            
    async def load_llm_model(self):
        """Load LLM model - prefer SmolLM2 for speed, fallback to Phi-3"""
        try:
            # First try SmolLM2 for faster performance
            smollm2_path = self.model_configs['smollm2_1.7b']['path']
            if smollm2_path.exists():
                logger.info("🚀 SmolLM2 directory found, checking for model...")
                return await self._load_smollm2_model(smollm2_path)
            
            # Fallback to Phi-3 if SmolLM2 not found
            logger.info("SmolLM2 not found, falling back to Phi-3 Mini...")
            phi3_path = self.model_configs['phi3_mini']['path']
            
            # Look for GGUF format (llama.cpp compatible)
            gguf_files = list(phi3_path.glob("*.gguf"))
            if gguf_files:
                model_file = gguf_files[0]
                logger.info(f"Found Phi-3 GGUF model: {model_file.name}")
                
                # Eagerly load the actual model
                if self.eager_load:
                    try:
                        from llama_cpp import Llama
                        
                        logger.info("🔄 Loading Phi-3 GGUF model...")
                        gpu_layers = -1  # Use all GPU layers if available
                        logger.info(f"🚀 Loading Phi-3 with {'ALL GPU layers' if gpu_layers == -1 else f'{gpu_layers} GPU layers'}...")
                        
                        self._llama_model = Llama(
                            model_path=str(model_file),
                            n_ctx=2048,      # Reduced from 4096 for faster processing
                            n_batch=1024,    # Increased from 512 for better GPU utilization
                            n_gpu_layers=gpu_layers,
                            n_threads=4,     # Optimize CPU threads
                            verbose=False
                        )
                        
                        logger.info("✅ Phi-3 GGUF model loaded successfully!")
                        
                    except ImportError:
                        logger.error("❌ llama-cpp-python not installed. Install with: pip install llama-cpp-python")
                        self._llama_model = None
                    except Exception as e:
                        logger.error(f"❌ Error loading Phi-3 GGUF model: {e}")
                        self._llama_model = None
                else:
                    self._llama_model = None
                
                # Configuration for Phi-3
                self.models['llm'] = {
                    'model_path': str(model_file),
                    'model_type': 'gguf',
                    'context_length': 4096,
                    'model_params': {
                        'n_ctx': 2048,       # Reduced context for speed
                        'n_batch': 1024,     # Increased batch for efficiency
                        'n_gpu_layers': -1,  # Use all GPU layers if available
                        'temperature': 0.4,  # Lower temperature for faster, more focused responses
                        'top_p': 0.8         # Slightly lower top_p for speed
                    },
                    'prompt_template': "<|system|>\n{system}<|end|>\n<|user|>\n{user}<|end|>\n<|assistant|>\n",
                    'loaded': self._llama_model is not None
                }
                logger.info("✅ Phi-3 Mini model configured")
                return True
                
            # Check for PyTorch format
            pt_files = list(phi3_path.glob("*.pt")) + list(phi3_path.glob("*.pth"))
            if pt_files:
                logger.info("Found PyTorch format Phi-3 model")
                self.models['llm'] = {
                    'model_path': str(phi3_path),
                    'model_type': 'pytorch',
                    'model_name': 'microsoft/Phi-3-mini-4k-instruct'
                }
                return True
                
            logger.warning("Phi-3 model format not recognized")
            return False
            
        except Exception as e:
            logger.error(f"Failed to load Phi-3: {e}")
            return False
    
    async def _load_smollm2_model(self, smollm2_path):
        """Load SmolLM2 1.7B model optimized for fast conversations"""
        try:
            # Look for GGUF format
            gguf_files = list(smollm2_path.glob("*.gguf"))
            if not gguf_files:
                logger.warning("No SmolLM2 GGUF files found")
                return False
                
            model_file = gguf_files[0]
            logger.info(f"✅ Found SmolLM2 GGUF model: {model_file.name}")
            
            # Eagerly load the model
            if self.eager_load:
                try:
                    from llama_cpp import Llama
                    
                    logger.info("🔄 Loading SmolLM2 1.7B model (optimized for speed)...")
                    gpu_layers = -1  # Use all GPU layers
                    
                    self._llama_model = Llama(
                        model_path=str(model_file),
                        n_ctx=2048,      # Optimal context for conversations
                        n_batch=2048,    # Large batch for efficiency
                        n_gpu_layers=gpu_layers,
                        n_threads=8,     # More threads for faster inference
                        verbose=False
                    )
                    
                    logger.info("✅ SmolLM2 1.7B loaded successfully!")
                    
                except ImportError:
                    logger.error("❌ llama-cpp-python not installed")
                    self._llama_model = None
                    return False
                except Exception as e:
                    logger.error(f"❌ Error loading SmolLM2: {e}")
                    self._llama_model = None
                    return False
            else:
                self._llama_model = None
            
            # Configuration for SmolLM2
            self.models['llm'] = {
                'model_path': str(model_file),
                'model_type': 'gguf',
                'model_name': 'smollm2-1.7b',
                'context_length': 2048,
                'model_params': {
                    'n_ctx': 2048,
                    'n_batch': 2048,
                    'n_gpu_layers': -1,
                    'temperature': 0.3,  # Lower for focused responses
                    'top_p': 0.7,        # Optimized for speed
                    'repeat_penalty': 1.1
                },
                'prompt_template': "Human: {user}\n\nAssistant:",  # Simple format for SmolLM2
                'loaded': self._llama_model is not None
            }
            logger.info("✅ SmolLM2 1.7B configured for fast voice conversations")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load SmolLM2: {e}")
            return False
            
    async def load_tts_model(self):
        """Load Kokoro TTS for text-to-speech"""
        try:
            kokoro_path = self.model_configs['kokoro_tts']['path']
            
            # Check for model config
            config_file = kokoro_path / 'config.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Kokoro TTS config loaded: {config.get('model_type', 'unknown')}")
                
            # Look for model files
            model_files = list(kokoro_path.glob("*.pt")) + \
                         list(kokoro_path.glob("*.pth")) + \
                         list(kokoro_path.glob("*.onnx"))
                         
            if model_files:
                logger.info(f"Found Kokoro TTS model files: {[f.name for f in model_files[:3]]}")
                
                # Eagerly initialize the Kokoro TTS service for fast synthesis
                if self.eager_load and not os.environ.get('DISABLE_KOKORO'):
                    try:
                        # Apply phonemizer fix BEFORE importing Kokoro service
                        from .phonemizer_fix import apply_phonemizer_fix
                        apply_phonemizer_fix()
                        
                        from .kokoro_tts_service import KokoroTTSService
                        logger.info("🔄 Initializing Kokoro TTS service...")
                        
                        self._kokoro_service = KokoroTTSService(kokoro_path, eager_init=True)
                        tts_initialized = await self._kokoro_service.initialize()
                        
                        if tts_initialized:
                            logger.info("✅ Kokoro TTS service initialized successfully!")
                            logger.info("🎵 Kokoro TTS ready for voice synthesis")
                        else:
                            logger.error("❌ Failed to initialize Kokoro TTS service")
                            self._kokoro_service = None
                            
                    except Exception as e:
                        logger.error(f"❌ Error initializing Kokoro TTS service: {e}")
                        self._kokoro_service = None
                else:
                    self._kokoro_service = None
                
                self.models['tts'] = {
                    'model_path': str(kokoro_path),
                    'model_files': [str(f) for f in model_files],
                    'model_type': 'kokoro',
                    'sample_rate': 24000,  # Common for TTS models
                    'voice_configs': {
                        'default': {'speed': 1.0, 'pitch': 1.0},
                        'female': {'speed': 1.1, 'pitch': 1.2},
                        'male': {'speed': 0.9, 'pitch': 0.8}
                    },
                    'loaded': self._kokoro_service is not None if self.eager_load else None
                }
                logger.info("✅ Kokoro TTS model configured")
                return True
                
            logger.warning("Kokoro TTS model files not found")
            return False
            
        except Exception as e:
            logger.error(f"Failed to load Kokoro TTS: {e}")
            return False
            
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio using Whisper or Parakeet-TDT"""
        
        # If STT is skipped, only use Whisper (for Pipecat compatibility)
        if self.skip_stt:
            logger.info("Using Whisper for transcription (Parakeet-TDT skipped)")
            if not self.has_whisper:
                logger.warning("Neither Parakeet-TDT nor Whisper available for transcription")
                return ""
        
        # Try Faster-Whisper first (more efficient), then fallback to Whisper
        try:
            # Try Faster-Whisper (more efficient)
            from faster_whisper import WhisperModel
            logger.info(f"Transcribing {len(audio_data)} bytes of audio with Faster-Whisper")
            
            # Optimized audio preprocessing - single operation instead of multiple conversions
            import numpy as np
            import torch
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Improved model persistence checking
            if not self._is_whisper_model_ready():
                if self.eager_load:
                    logger.warning("❌ Faster-Whisper model was supposed to be loaded at startup but is missing")
                
                logger.info("Loading Faster-Whisper Small model with CUDA acceleration...")
                # Use same optimized configuration as startup
                model_cache_dir = Path("./models/faster-whisper")
                model_cache_dir.mkdir(parents=True, exist_ok=True)
                
                self._faster_whisper_model = WhisperModel(
                    "small.en",             # Use small model for better accuracy
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    compute_type="float16" if torch.cuda.is_available() else "int8",
                    num_workers=2 if torch.cuda.is_available() else 1,  # More workers for GPU
                    download_root=str(model_cache_dir),
                    local_files_only=False
                )
                
                device_info = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
                logger.info(f"✅ Faster-Whisper Small model loaded with {device_info} acceleration")
            
            # Transcribe with Faster-Whisper using real-time optimizations
            segments, info = self._faster_whisper_model.transcribe(
                audio_array, 
                language="en",
                # Aggressive real-time optimizations
                beam_size=1,           # Fastest beam search
                best_of=1,             # Single pass only  
                temperature=0.0,       # Deterministic output
                vad_filter=False,      # Disable VAD - we handle chunking
                without_timestamps=True,  # Skip timestamp computation for speed
                word_timestamps=False     # Skip word-level timestamps
            )
            text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"✅ Faster-Whisper transcribed: {text}")
            
            # Echo prevention is now handled by exact-match detection in enhanced_websocket_handler
            # This allows all user speech through, including legitimate "thank you" messages
            
            return text
            
        except ImportError:
            logger.info("Faster-Whisper not available, trying regular Whisper...")
            # Fallback to regular Whisper
            if self.has_whisper:
                try:
                    import whisper
                    logger.info(f"Transcribing {len(audio_data)} bytes of audio with Whisper")
                    
                    # Convert bytes to numpy array
                    import numpy as np
                    import torch
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # Load Whisper model if not already loaded
                    if not hasattr(self, '_whisper_model') or self._whisper_model is None:
                        if self.eager_load:
                            logger.warning("❌ Whisper model was supposed to be loaded at startup but is missing")
                        
                        logger.info("Loading Whisper model...")
                        self._whisper_model = whisper.load_model("base", device="cuda" if torch.cuda.is_available() else "cpu")
                        logger.info("✅ Whisper model loaded")
                    
                    # Transcribe
                    result = self._whisper_model.transcribe(audio_array, fp16=False)
                    text = result["text"].strip()
                    logger.info(f"✅ Whisper transcribed: {text}")
                    return text
                    
                except Exception as e:
                    logger.warning(f"Whisper transcription failed: {e}, falling back to Parakeet")
        
        # Skip Parakeet-TDT if STT is disabled
        if self.skip_stt:
            logger.warning("STT model skipped and Whisper failed/unavailable")
            return ""
        
        if not self.models['stt']:
            logger.warning("STT model not loaded, using fallback")
            return ""
            
        # Parakeet-TDT removed - using Faster-Whisper instead
        logger.error("❌ Parakeet-TDT has been removed. Please use Faster-Whisper for transcription.")
        return ""
            
    async def generate_response(self, prompt: str, system_prompt: str = None) -> str:
        """Generate response using Phi-3 Mini"""
        if not self.models['llm']:
            logger.warning("LLM model not loaded")
            return "LLM model not available"
            
        # Filter out empty or blocked prompts
        if not prompt or not prompt.strip():
            logger.debug("🔇 Skipping empty prompt")
            return ""
            
        try:
            model_info = self.models['llm']
            
            # Format prompt based on model type
            model_name = model_info.get('model_name', 'LLM')
            
            if 'smollm2' in model_name.lower():
                # SmolLM2 uses simpler format
                if system_prompt:
                    formatted_prompt = f"{system_prompt}\n\n{model_info['prompt_template'].format(user=prompt)}"
                else:
                    formatted_prompt = model_info['prompt_template'].format(user=prompt)
            else:
                # Phi-3 format
                if system_prompt:
                    formatted_prompt = model_info['prompt_template'].format(
                        system=system_prompt,
                        user=prompt
                    )
                else:
                    formatted_prompt = model_info['prompt_template'].format(
                        system="You are a helpful AI assistant.",
                        user=prompt
                    )
                
            logger.info(f"Generating response with {model_name} for prompt: {prompt[:50]}...")
            
            # Actually load and use the Phi-3 model
            if model_info['model_type'] == 'gguf':
                # Use llama-cpp-python for GGUF models
                try:
                    from llama_cpp import Llama
                    
                    # Check if we have an active model instance
                    if not hasattr(self, '_llama_model') or self._llama_model is None:
                        if self.eager_load:
                            logger.warning("❌ Model was supposed to be loaded at startup but is missing - attempting load now...")
                        
                        gpu_layers = model_info['model_params']['n_gpu_layers']
                        model_name = model_info.get('model_name', 'GGUF model')
                        if gpu_layers == -1:
                            logger.info(f"🚀 Loading {model_name} with ALL GPU layers...")
                        elif gpu_layers > 0:
                            logger.info(f"🚀 Loading {model_name} with {gpu_layers} GPU layers...")
                        else:
                            logger.info(f"🖥️  Loading {model_name} on CPU...")
                            
                        self._llama_model = Llama(
                            model_path=model_info['model_path'],
                            n_ctx=model_info['model_params']['n_ctx'],
                            n_batch=model_info['model_params']['n_batch'],
                            n_gpu_layers=model_info['model_params']['n_gpu_layers'],
                            n_threads=model_info['model_params'].get('n_threads', 4),
                            verbose=False
                        )
                        logger.info(f"✅ {model_name} loaded successfully!")
                    
                    # Determine stop tokens based on model
                    if 'smollm2' in model_info.get('model_name', '').lower():
                        stop_tokens = ["Human:", "Assistant:", "\n\n"]
                    else:
                        stop_tokens = ["<|end|>", "<|user|>", "<|system|>"]
                    
                    # Generate response
                    response = self._llama_model(
                        formatted_prompt,
                        max_tokens=128,  # Reduced from 512 for voice conversations
                        temperature=model_info['model_params']['temperature'],
                        top_p=model_info['model_params']['top_p'],
                        stop=stop_tokens,
                        echo=False,
                        repeat_penalty=model_info['model_params'].get('repeat_penalty', 1.0)
                    )
                    
                    generated_text = response['choices'][0]['text'].strip()
                    model_name = model_info.get('model_name', 'LLM')
                    logger.info(f"✅ {model_name} generated: {generated_text[:100]}...")
                    return generated_text
                    
                except ImportError:
                    logger.error("❌ llama-cpp-python not installed. Install with: pip install llama-cpp-python")
                    return "Error: llama-cpp-python not installed. Install with: pip install llama-cpp-python"
                except Exception as e:
                    logger.error(f"❌ Error loading/running Phi-3 GGUF model: {e}")
                    return f"Error running Phi-3: {e}"
                    
            elif model_info['model_type'] == 'pytorch':
                # Use transformers for PyTorch models
                try:
                    from transformers import AutoTokenizer, AutoModelForCausalLM
                    import torch
                    
                    # Check if we have active model instances
                    if not hasattr(self, '_hf_tokenizer') or self._hf_tokenizer is None:
                        logger.info("Loading Phi-3 PyTorch model...")
                        self._hf_tokenizer = AutoTokenizer.from_pretrained(model_info['model_name'])
                        self._hf_model = AutoModelForCausalLM.from_pretrained(
                            model_info['model_name'],
                            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                            device_map="auto" if torch.cuda.is_available() else "cpu"
                        )
                        logger.info("✅ Phi-3 PyTorch model loaded successfully!")
                    
                    # Tokenize and generate
                    inputs = self._hf_tokenizer.encode(formatted_prompt, return_tensors="pt")
                    
                    with torch.no_grad():
                        outputs = self._hf_model.generate(
                            inputs,
                            max_length=inputs.shape[1] + 512,
                            temperature=0.7,
                            do_sample=True,
                            pad_token_id=self._hf_tokenizer.eos_token_id
                        )
                    
                    response = self._hf_tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)
                    generated_text = response.strip()
                    logger.info(f"✅ Phi-3 generated: {generated_text[:100]}...")
                    return generated_text
                    
                except ImportError:
                    logger.error("❌ transformers not installed. Install with: pip install transformers torch")
                    return "Error: transformers not installed. Install with: pip install transformers torch"
                except Exception as e:
                    logger.error(f"❌ Error loading/running Phi-3 PyTorch model: {e}")
                    return f"Error running Phi-3: {e}"
            
            else:
                logger.error(f"❌ Unknown model type: {model_info['model_type']}")
                return f"Error: Unknown model type {model_info['model_type']}"
            
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return f"Error generating response: {e}"
            
    async def synthesize_speech(self, text: str, voice: str = "default") -> bytes:
        """Synthesize speech using Kokoro TTS"""
        if not self.models['tts']:
            logger.warning("TTS model not loaded")
            return b""
            
        try:
            # Limit text length to prevent massive audio files (WebSocket has 1MB limit)
            max_chars = 400  # ~400 chars = ~200KB audio (well under 1MB limit)
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
                logger.info(f"🔧 Truncated long text to {max_chars} characters for TTS")
            
            logger.info(f"Synthesizing speech with Kokoro TTS: '{text[:50]}...'")
            
            # Re-enable Kokoro with debugging
            use_kokoro = True
            
            if use_kokoro and self._kokoro_service:
                # Use the eagerly loaded Kokoro service for fastest synthesis
                try:
                    # Map voice config to Kokoro voice names
                    voice_map = {
                        'default': 'af_heart',
                        'female': 'af_alloy', 
                        'male': 'am_hero'
                    }
                    kokoro_voice = voice_map.get(voice, 'af_heart')
                    
                    # Fast synthesis using pre-initialized service
                    audio_data = await self._kokoro_service.synthesize(text, voice=kokoro_voice)
                    
                    if audio_data and len(audio_data) > 0:
                        logger.info(f"🚀 Fast Kokoro TTS: {len(audio_data)} bytes")
                        return audio_data
                    else:
                        logger.warning("⚠️ Kokoro TTS returned empty audio")
                        
                except Exception as e:
                    logger.error(f"❌ Fast Kokoro TTS failed: {e}")
                
            # If Kokoro fails, try fallback TTS
            try:
                # Try to use pyttsx3 or espeak as fallback
                audio_data = await self._generate_fallback_tts(text)
                if audio_data:
                    logger.info(f"✅ Generated fallback TTS audio: {len(audio_data)} bytes")
                    return audio_data
            except Exception as e:
                logger.warning(f"Fallback TTS failed: {e}")
            
            # If all fails, generate silent audio to prevent pipeline errors
            # Generate 1 second of silence at 24kHz mono 16-bit
            silence_duration = 1.0
            sample_rate = 24000
            num_samples = int(silence_duration * sample_rate)
            silence_audio = bytes(num_samples * 2)  # 16-bit = 2 bytes per sample
            
            logger.info(f"✅ Generated {len(silence_audio)} bytes of silence audio")
            return silence_audio
            
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return b""
            
    async def _generate_fallback_tts(self, text: str) -> bytes:
        """Generate TTS using fallback methods"""
        try:
            # Try using espeak (common on Linux)
            import subprocess
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
            try:
                # Use espeak to generate audio
                cmd = [
                    'espeak', 
                    '-s', '150',  # Speed
                    '-v', 'en',   # Voice
                    '-w', tmp_path,  # Output WAV file
                    text
                ]
                
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                
                if result.returncode == 0 and os.path.exists(tmp_path):
                    with open(tmp_path, 'rb') as f:
                        # Skip WAV header (44 bytes) to get raw PCM
                        f.seek(44)
                        audio_data = f.read()
                        
                    logger.info(f"✅ espeak generated {len(audio_data)} bytes")
                    return audio_data
                    
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.debug(f"espeak failed: {e}")
                
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.debug(f"Fallback TTS error: {e}")
            
        return b""
            
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models"""
        return {
            'stt': {
                'loaded': True,  # STT is always available via Faster-Whisper or Whisper
                'skipped': False,  # STT is not skipped, just using Faster-Whisper instead of NeMo
                'model': 'faster-whisper' if not self.models['stt'] else 'parakeet_tdt',
                'path': 'built-in faster-whisper' if not self.models['stt'] else str(self.model_configs['parakeet_tdt']['path'])
            },
            'llm': {
                'loaded': self.models['llm'] is not None,
                'model': 'smollm2_1.7b',
                'path': str(self.model_configs['smollm2_1.7b']['path'])
            },
            'tts': {
                'loaded': self.models['tts'] is not None,
                'model': 'kokoro_tts',
                'path': str(self.model_configs['kokoro_tts']['path'])
            }
        }


# Global instance with eager loading enabled by default
# Don't skip STT - we need it for the Simple WebSocket Handler
local_model_manager = LocalModelManager(skip_stt=False, eager_load=True)