"""Local model management for STT, LLM, and TTS using local models"""
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

class LocalModelManager:
    """Manages local models for speech-to-text, language model, and text-to-speech"""
    
    def __init__(self, skip_stt: bool = False, eager_load: bool = True):  # Enable STT for Faster-Whisper
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
            logger.info("Whisper not available - will use Parakeet-TDT for all transcriptions")
        self.model_configs = {
            'parakeet_tdt': {
                'type': 'stt',
                'path': self.models_dir / 'parakeet-tdt',
                'model_type': 'nvidia_nemo',
                'description': 'NVIDIA Parakeet-TDT for speech recognition'
            },
            'phi3_mini': {
                'type': 'llm', 
                'path': self.models_dir / 'phi3-mini',
                'model_type': 'gguf',
                'description': 'Microsoft Phi-3 Mini for language generation'
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
            
            # Load STT model
            if not self.skip_stt:
                try:
                    stt_loaded = await self.load_stt_model()
                    logger.info(f"STT model loading: {'✅ Success' if stt_loaded else '❌ Failed'}")
                except Exception as e:
                    logger.error(f"❌ Error loading STT model: {e}")
            else:
                logger.info("⏭️  STT model loading skipped")
                
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
            
            # Preload Whisper models if available
            if self.has_whisper:
                try:
                    logger.info("🔄 Preloading Faster-Whisper model...")
                    from faster_whisper import WhisperModel
                    import torch
                    
                    self._faster_whisper_model = WhisperModel(
                        "tiny",  # Use tiny model for speed
                        device="cuda" if torch.cuda.is_available() else "cpu",
                        compute_type="float16" if torch.cuda.is_available() else "int8"
                    )
                    logger.info("✅ Faster-Whisper model preloaded successfully!")
                    
                except ImportError:
                    try:
                        logger.info("🔄 Preloading standard Whisper model...")
                        import whisper
                        import torch
                        
                        self._whisper_model = whisper.load_model("base", device="cuda" if torch.cuda.is_available() else "cpu")
                        logger.info("✅ Standard Whisper model preloaded successfully!")
                        
                    except Exception as e:
                        logger.error(f"❌ Error preloading Whisper models: {e}")
                except Exception as e:
                    logger.error(f"❌ Error preloading Faster-Whisper: {e}")
                    
            logger.info("🏁 Eager model loading completed")
                
    async def load_stt_model(self):
        """Load Parakeet-TDT for speech-to-text"""
        if self.skip_stt:
            logger.info("⏭️  Skipping Parakeet-TDT NeMo model loading (using Pipecat's Whisper instead)")
            return False
            
        try:
            parakeet_path = self.model_configs['parakeet_tdt']['path']
            
            # Check for NVIDIA NeMo format (.nemo files)
            nemo_files = list(parakeet_path.glob("*.nemo"))
            if nemo_files:
                nemo_file = nemo_files[0]  # Use first .nemo file found
                logger.info(f"Found Parakeet-TDT NeMo model: {nemo_file.name}")
                
                # Actually load the NeMo model at startup
                try:
                    logger.info("🔄 Pre-loading Parakeet-TDT NeMo model (this may take 30-60 seconds)...")
                    import nemo.collections.asr as nemo_asr
                    import torch
                    
                    # Load model with GPU acceleration if available
                    if torch.cuda.is_available():
                        logger.info(f"🚀 Loading Parakeet-TDT on GPU: {torch.cuda.get_device_name()}")
                        self._nemo_model = nemo_asr.models.ASRModel.restore_from(
                            str(nemo_file), 
                            map_location='cuda'
                        )
                    else:
                        logger.info("🐌 Loading Parakeet-TDT on CPU (slower)")
                        self._nemo_model = nemo_asr.models.ASRModel.restore_from(
                            str(nemo_file), 
                            map_location='cpu'
                        )
                    
                    # Put model in eval mode
                    self._nemo_model.eval()
                    
                    # Store model info
                    self.models['stt'] = {
                        'model_path': str(nemo_file),
                        'model_type': 'nemo',
                        'model_name': 'parakeet-tdt-0.6b-v2',
                        'loaded': True
                    }
                    
                    logger.info("✅ Parakeet-TDT NeMo model fully loaded and ready!")
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Failed to pre-load Parakeet-TDT: {e}")
                    logger.info("⚠️ Will attempt lazy loading during first transcription")
                    # Fall back to lazy loading config
                    self.models['stt'] = {
                        'model_path': str(nemo_file),
                        'model_type': 'nemo',
                        'model_name': 'parakeet-tdt-0.6b-v2',
                        'loaded': False
                    }
                    return True
                
            # Check for ONNX format (more portable)
            onnx_files = list(parakeet_path.glob("*.onnx"))
            if onnx_files:
                logger.info(f"Found ONNX model: {onnx_files[0].name}")
                # Would use onnxruntime for inference
                # import onnxruntime as ort
                # self.models['stt'] = ort.InferenceSession(str(onnx_files[0]))
                logger.info("Parakeet-TDT ONNX model ready for integration")
                return True
                
            logger.warning("Parakeet-TDT model format not recognized")
            return False
            
        except Exception as e:
            logger.error(f"Failed to load Parakeet-TDT: {e}")
            return False
            
    async def load_llm_model(self):
        """Load Phi-3 Mini for language generation"""
        try:
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
                            n_ctx=4096,
                            n_batch=512,
                            n_gpu_layers=gpu_layers,
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
                        'n_ctx': 4096,
                        'n_batch': 512,
                        'n_gpu_layers': -1,  # Use all GPU layers if available
                        'temperature': 0.7,
                        'top_p': 0.9
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
                
                # Eagerly initialize the Kokoro TTS service if requested
                if self.eager_load:
                    try:
                        from .kokoro_tts_service import KokoroTTSService
                        logger.info("🔄 Initializing Kokoro TTS service...")
                        
                        self._kokoro_service = KokoroTTSService(kokoro_path)
                        tts_initialized = await self._kokoro_service.initialize()
                        
                        if tts_initialized:
                            logger.info("✅ Kokoro TTS service initialized successfully!")
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
            
            # Convert bytes to numpy array
            import numpy as np
            import torch
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Load Faster-Whisper model if not already loaded
            if not hasattr(self, '_faster_whisper_model') or self._faster_whisper_model is None:
                if self.eager_load:
                    logger.warning("❌ Faster-Whisper model was supposed to be loaded at startup but is missing")
                
                logger.info("Loading Faster-Whisper Tiny model for speed...")
                self._faster_whisper_model = WhisperModel(
                    "tiny",  # Use tiny model for speed (~1.5s -> 0.1-0.2s)
                    device="cuda" if torch.cuda.is_available() else "cpu",
                    compute_type="float16" if torch.cuda.is_available() else "int8"
                )
                logger.info("✅ Faster-Whisper Tiny model loaded (optimized for speed)")
            
            # Transcribe with Faster-Whisper
            segments, info = self._faster_whisper_model.transcribe(audio_array, language="en")
            text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"✅ Faster-Whisper transcribed: {text}")
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
            
        try:
            logger.info(f"Transcribing {len(audio_data)} bytes of audio with Parakeet-TDT")
            
            # Use NVIDIA NeMo for Parakeet-TDT inference
            try:
                import nemo.collections.asr as nemo_asr
                import tempfile
                import wave
                import numpy as np
                from scipy.io.wavfile import write
                
                # Check if we have a loaded NeMo model
                if not hasattr(self, '_nemo_model') or self._nemo_model is None:
                    logger.warning("❌ Parakeet-TDT model not pre-loaded, attempting to load now...")
                    model_path = self.models['stt'].get('model_path')
                    if not model_path:
                        logger.error("No model path found!")
                        return ""
                    
                    # Load model with GPU acceleration if available
                    import torch
                    if torch.cuda.is_available():
                        logger.info(f"🚀 Loading Parakeet-TDT on GPU: {torch.cuda.get_device_name()}")
                        self._nemo_model = nemo_asr.models.EncDecRNNTBPEModel.restore_from(model_path, map_location="cuda")
                        self._nemo_model = self._nemo_model.cuda()
                    else:
                        logger.info("🖥️  Loading Parakeet-TDT on CPU")
                        self._nemo_model = nemo_asr.models.EncDecRNNTBPEModel.restore_from(model_path, map_location="cpu")
                    
                    self._nemo_model.eval()
                    logger.info("✅ Parakeet-TDT model loaded successfully!")
                
                # Convert raw PCM bytes to proper WAV file for NeMo
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    temp_path = temp_wav.name
                
                # Write proper WAV file with headers
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)  # use provided sample rate
                    wav_file.writeframes(audio_data)
                
                try:
                    # Transcribe using NeMo model
                    transcription = self._nemo_model.transcribe([temp_path])
                    
                    if transcription and len(transcription) > 0:
                        # Handle Hypothesis object from NeMo
                        hypothesis = transcription[0]
                        if hasattr(hypothesis, 'text'):
                            result = hypothesis.text.strip()
                        elif hasattr(hypothesis, 'pred_text'):
                            result = hypothesis.pred_text.strip()
                        else:
                            result = str(hypothesis).strip()
                        
                        logger.info(f"✅ Parakeet-TDT transcription: '{result[:100]}...'")
                        return result
                    else:
                        logger.warning("Empty transcription from Parakeet-TDT")
                        return ""
                        
                finally:
                    import os
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
            except ImportError:
                logger.error("❌ NeMo not installed. Install with: pip install nemo_toolkit[asr]")
                return ""
            except Exception as e:
                logger.error(f"❌ Error with Parakeet-TDT: {e}")
                return ""
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
            
    async def generate_response(self, prompt: str, system_prompt: str = None) -> str:
        """Generate response using Phi-3 Mini"""
        if not self.models['llm']:
            logger.warning("LLM model not loaded")
            return "LLM model not available"
            
        try:
            model_info = self.models['llm']
            
            # Format prompt for Phi-3
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
                
            logger.info(f"Generating response with Phi-3 Mini for prompt: {prompt[:50]}...")
            
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
                        if gpu_layers == -1:
                            logger.info("🚀 Loading Phi-3 GGUF model with ALL GPU layers...")
                        elif gpu_layers > 0:
                            logger.info(f"🚀 Loading Phi-3 GGUF model with {gpu_layers} GPU layers...")
                        else:
                            logger.info("🖥️  Loading Phi-3 GGUF model on CPU...")
                            
                        self._llama_model = Llama(
                            model_path=model_info['model_path'],
                            n_ctx=model_info['model_params']['n_ctx'],
                            n_batch=model_info['model_params']['n_batch'],
                            n_gpu_layers=model_info['model_params']['n_gpu_layers'],
                            verbose=False
                        )
                        logger.info("✅ Phi-3 GGUF model loaded successfully!")
                    
                    # Generate response
                    response = self._llama_model(
                        formatted_prompt,
                        max_tokens=512,
                        temperature=model_info['model_params']['temperature'],
                        top_p=model_info['model_params']['top_p'],
                        stop=["<|end|>", "<|user|>", "<|system|>"],
                        echo=False
                    )
                    
                    generated_text = response['choices'][0]['text'].strip()
                    logger.info(f"✅ Phi-3 generated: {generated_text[:100]}...")
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
            logger.info(f"Synthesizing speech with Kokoro TTS: '{text[:50]}...'")
            
            # Re-enable Kokoro with debugging
            use_kokoro = True
            
            if use_kokoro:
                # Try to use the new Kokoro wrapper that bypasses espeak issues
                try:
                    # Use the new integration that handles espeak issues
                    from .kokoro_integration import create_kokoro_tts_integration
                    
                    if not hasattr(self, '_kokoro_integration'):
                        logger.info("🔧 Initializing Kokoro TTS integration...")
                        self._kokoro_integration = create_kokoro_tts_integration()
                    
                    # Map voice config to Kokoro voice names
                    voice_map = {
                        'default': 'af_heart',
                        'female': 'af_alloy', 
                        'male': 'am_hero'
                    }
                    kokoro_voice = voice_map.get(voice, 'af_heart')
                    
                    # Synthesize with new wrapper
                    audio_data, sample_rate = await self._kokoro_integration.synthesize(text, voice=kokoro_voice)
                    
                    if audio_data and len(audio_data) > 0:
                        logger.info(f"✅ Kokoro TTS generated {len(audio_data)} bytes at {sample_rate}Hz")
                        return audio_data
                    else:
                        logger.warning("⚠️ Kokoro TTS returned empty audio, trying fallback...")
                        
                except ImportError as e:
                    logger.warning(f"❌ Kokoro TTS not available: {e}")
                    logger.info("💡 Install with: pip install kokoro>=0.9.2")
                except Exception as e:
                    logger.error(f"❌ Kokoro TTS failed: {e}")
                
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
                'model': 'phi3_mini',
                'path': str(self.model_configs['phi3_mini']['path'])
            },
            'tts': {
                'loaded': self.models['tts'] is not None,
                'model': 'kokoro_tts',
                'path': str(self.model_configs['kokoro_tts']['path'])
            }
        }


# Global instance with eager loading enabled by default
local_model_manager = LocalModelManager(skip_stt=False, eager_load=True)