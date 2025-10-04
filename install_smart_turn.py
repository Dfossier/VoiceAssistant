#!/usr/bin/env python3
"""
Smart Turn VAD v3 Standalone Installation
Installs Smart Turn independently without Pipecat dependencies
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from loguru import logger

def run_command(command: str, description: str = ""):
    """Run a command and handle errors"""
    logger.info(f"🔧 {description or command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout.strip():
            logger.info(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Command failed: {command}")
        logger.error(f"   Error: {e.stderr.strip()}")
        return False

def check_dependencies():
    """Check if required dependencies are available"""
    logger.info("📋 Checking dependencies...")
    
    try:
        import torch
        logger.info(f"✅ PyTorch: {torch.__version__}")
        if torch.cuda.is_available():
            logger.info(f"   GPU: {torch.cuda.get_device_name()}")
        else:
            logger.info("   Using CPU (GPU recommended for <10ms inference)")
    except ImportError:
        logger.error("❌ PyTorch not found - required for Smart Turn")
        return False
        
    try:
        import transformers
        logger.info(f"✅ Transformers: {transformers.__version__}")
    except ImportError:
        logger.error("❌ Transformers not found - required for Smart Turn")
        return False
        
    try:
        import onnxruntime
        logger.info(f"✅ ONNX Runtime: {onnxruntime.__version__}")
    except ImportError:
        logger.error("❌ ONNX Runtime not found - required for Smart Turn")
        return False
        
    return True

def clone_smart_turn_repo():
    """Clone Smart Turn repository"""
    logger.info("📦 Installing Smart Turn VAD v3...")
    
    # Create models directory
    models_dir = Path("models/smart_turn")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Clone repository to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        repo_path = temp_path / "smart-turn"
        
        logger.info("   Cloning Smart Turn repository...")
        if not run_command(
            f"git clone https://github.com/snakers4/silero-vad.git {repo_path}",
            "Cloning Smart Turn repository"
        ):
            return False
            
        # Copy essential files to our models directory
        essential_files = [
            "model.py",
            "inference.py", 
            "predict.py",
            "record_and_predict.py"
        ]
        
        logger.info("   Copying Smart Turn files...")
        for file_name in essential_files:
            src_file = repo_path / file_name
            dst_file = models_dir / file_name
            
            if src_file.exists():
                shutil.copy2(src_file, dst_file)
                logger.info(f"   ✅ Copied {file_name}")
            else:
                logger.warning(f"   ⚠️ {file_name} not found in repository")
    
    logger.info(f"✅ Smart Turn files installed to {models_dir}")
    return True

def download_model_weights():
    """Download Smart Turn v3 model weights from HuggingFace"""
    logger.info("⬇️  Downloading Smart Turn v3 model weights...")
    
    try:
        from huggingface_hub import hf_hub_download
        
        # Create models directory
        models_dir = Path("models/smart_turn")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Download model files
        model_files = [
            "config.json",
            "model.onnx",
            "tokenizer.json", 
            "tokenizer_config.json"
        ]
        
        for file_name in model_files:
            try:
                logger.info(f"   Downloading {file_name}...")
                downloaded_path = hf_hub_download(
                    repo_id="snakers4/silero-vad",
                    filename=file_name,
                    cache_dir=str(models_dir / "cache"),
                    local_dir=str(models_dir),
                    local_dir_use_symlinks=False
                )
                logger.info(f"   ✅ Downloaded {file_name}")
                
            except Exception as e:
                logger.warning(f"   ⚠️ Could not download {file_name}: {e}")
        
        logger.info("✅ Model weights download completed")
        return True
        
    except ImportError:
        logger.error("❌ huggingface_hub not available")
        logger.info("💡 Install with: pip install huggingface_hub>=0.10.0")
        return False
    except Exception as e:
        logger.error(f"❌ Error downloading model weights: {e}")
        return False

def create_smart_turn_wrapper():
    """Create our own Smart Turn wrapper class"""
    logger.info("🔧 Creating Smart Turn wrapper...")
    
    wrapper_code = '''"""
Standalone Smart Turn VAD Wrapper
Works independently without Pipecat dependencies
"""

import os
import sys
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Optional, Union
import json

class StandaloneSmartTurn:
    """Standalone Smart Turn VAD implementation"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = Path(model_path) if model_path else Path("models/smart_turn")
        self.session = None
        self.sample_rate = 16000
        
    def initialize(self) -> bool:
        """Initialize the ONNX model"""
        try:
            model_file = self.model_path / "model.onnx"
            if not model_file.exists():
                print(f"❌ Model file not found: {model_file}")
                return False
                
            # Create ONNX runtime session
            self.session = ort.InferenceSession(
                str(model_file),
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            
            print(f"✅ Smart Turn model loaded from {model_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing Smart Turn: {e}")
            return False
    
    def analyze(self, audio_data: Union[bytes, np.ndarray]) -> float:
        """Analyze audio for turn detection"""
        if self.session is None:
            raise RuntimeError("Model not initialized")
            
        # Convert bytes to numpy array if needed
        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_data.astype(np.float32)
            
        # Ensure correct shape and length for model input
        # Smart Turn typically expects specific input format
        if len(audio_array) == 0:
            return 0.0
            
        # Pad or truncate to expected length (model-dependent)
        max_length = 8 * self.sample_rate  # 8 seconds max
        if len(audio_array) > max_length:
            audio_array = audio_array[:max_length]
        elif len(audio_array) < max_length:
            audio_array = np.pad(audio_array, (0, max_length - len(audio_array)))
            
        # Reshape for model input (batch_size=1)
        input_array = audio_array.reshape(1, -1).astype(np.float32)
        
        try:
            # Run inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: input_array})
            
            # Extract turn detection score (model output format dependent)
            score = float(outputs[0][0]) if outputs and len(outputs[0]) > 0 else 0.0
            
            return score
            
        except Exception as e:
            print(f"❌ Error during inference: {e}")
            return 0.0

# Global instance
smart_turn_model = StandaloneSmartTurn()
'''

    wrapper_file = Path("src/core/standalone_smart_turn.py")
    wrapper_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(wrapper_file, 'w') as f:
        f.write(wrapper_code)
    
    logger.info(f"✅ Smart Turn wrapper created: {wrapper_file}")
    return True

def test_installation():
    """Test the Smart Turn installation"""
    logger.info("🧪 Testing Smart Turn installation...")
    
    try:
        sys.path.insert(0, "src")
        from core.standalone_smart_turn import smart_turn_model
        
        if not smart_turn_model.initialize():
            logger.error("❌ Smart Turn initialization failed")
            return False
            
        # Create test audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)
        test_audio = np.random.normal(0, 0.1, samples).astype(np.float32)
        
        # Test inference
        result = smart_turn_model.analyze(test_audio)
        logger.info(f"✅ Smart Turn test result: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Installation test failed: {e}")
        return False

def main():
    """Main installation function"""
    logger.info("🎯 Smart Turn VAD v3 Standalone Installation")
    logger.info("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        logger.error("❌ Missing dependencies - install requirements.txt first")
        return False
    
    # Clone repository and get code
    if not clone_smart_turn_repo():
        logger.error("❌ Failed to clone Smart Turn repository")
        return False
    
    # Download model weights
    if not download_model_weights():
        logger.warning("⚠️ Model weights download failed - you may need to download manually")
        logger.info("💡 Manual download: https://huggingface.co/snakers4/silero-vad")
    
    # Create wrapper
    if not create_smart_turn_wrapper():
        logger.error("❌ Failed to create Smart Turn wrapper")
        return False
    
    # Test installation
    if test_installation():
        logger.info("✅ Smart Turn installation completed successfully!")
        logger.info("🔧 Next steps:")
        logger.info("   1. Run: python test_smart_turn_basic.py")
        logger.info("   2. Run: python test_smart_turn_comparison.py") 
        logger.info("   3. Integration testing with voice assistant")
        return True
    else:
        logger.error("❌ Installation test failed")
        logger.info("🔧 Troubleshooting:")
        logger.info("   1. Check model files in models/smart_turn/")
        logger.info("   2. Verify ONNX Runtime installation")
        logger.info("   3. Check GPU drivers if using CUDA")
        return False

if __name__ == "__main__":
    main()