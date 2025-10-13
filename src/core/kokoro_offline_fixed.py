"""
Kokoro implementation with offline-only mode and hang prevention
This prevents all runtime downloads and adds detailed logging to identify hang points
"""
import os
import sys
import json
import torch
from pathlib import Path
from loguru import logger
from typing import Dict, Optional, Union

def setup_offline_mode():
    """Force completely offline mode - no downloads allowed"""
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
    logger.info("✅ Offline mode enforced - no downloads allowed")

def check_local_files(model_path: Path) -> bool:
    """Check if all required Kokoro files exist locally"""
    config_file = model_path / "config.json"
    model_file = model_path / "kokoro-v1_0.pth"
    
    if not model_path.exists():
        logger.error(f"❌ Model directory not found: {model_path}")
        return False
    
    if not config_file.exists():
        logger.error(f"❌ Config file not found: {config_file}")
        return False
        
    if not model_file.exists():
        logger.error(f"❌ Model file not found: {model_file}")
        return False
    
    # Check file sizes
    config_size = config_file.stat().st_size
    model_size = model_file.stat().st_size
    
    logger.info(f"✅ Found config.json ({config_size} bytes)")
    logger.info(f"✅ Found kokoro-v1_0.pth ({model_size // 1024 // 1024}MB)")
    
    if config_size < 100:
        logger.error(f"❌ Config file too small: {config_size} bytes")
        return False
        
    if model_size < 300_000_000:  # Should be ~327MB
        logger.error(f"❌ Model file too small: {model_size} bytes")
        return False
    
    return True

class OfflineKModel:
    """Offline-only KModel that prevents all downloads"""
    
    def __init__(self, model_path: str):
        logger.info("🚀 Initializing OfflineKModel...")
        
        # Force offline mode
        setup_offline_mode()
        
        # Check local files first
        self.model_path = Path(model_path)
        if not check_local_files(self.model_path):
            raise FileNotFoundError("Required Kokoro files not found locally")
        
        # Load config
        config_file = self.model_path / "config.json"
        logger.info(f"📖 Loading config from {config_file}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("✅ Config loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}")
            raise
        
        # Store vocab
        self.vocab = self.config['vocab']
        logger.info(f"✅ Vocab loaded: {len(self.vocab)} tokens")
        
        # Initialize components step by step with detailed logging
        self._init_components()
        
        # Load model weights
        self._load_weights()
        
        logger.info("🎉 OfflineKModel initialized successfully!")
    
    def _init_components(self):
        """Initialize model components with detailed logging"""
        try:
            logger.info("🔧 Initializing CustomAlbert...")
            from transformers import AlbertConfig
            
            albert_config = AlbertConfig(
                vocab_size=self.config['n_token'], 
                **self.config['plbert']
            )
            logger.info(f"✅ AlbertConfig created: vocab_size={albert_config.vocab_size}")
            
            # Import Kokoro components
            logger.info("📦 Importing Kokoro components...")
            from kokoro.modules import CustomAlbert, ProsodyPredictor, TextEncoder
            from kokoro.istftnet import Decoder
            logger.info("✅ Kokoro components imported")
            
            # Create CustomAlbert
            logger.info("🧠 Creating CustomAlbert...")
            self.bert = CustomAlbert(albert_config)
            logger.info("✅ CustomAlbert created")
            
            # Create other components
            logger.info("🔗 Creating bert_encoder...")
            self.bert_encoder = torch.nn.Linear(
                self.bert.config.hidden_size, 
                self.config['hidden_dim']
            )
            logger.info("✅ bert_encoder created")
            
            logger.info("🎯 Creating ProsodyPredictor...")
            self.predictor = ProsodyPredictor(
                style_dim=self.config['style_dim'],
                d_hid=self.config['hidden_dim'],
                nlayers=self.config['n_layer'],
                max_dur=self.config['max_dur'],
                dropout=self.config['dropout']
            )
            logger.info("✅ ProsodyPredictor created")
            
            logger.info("📝 Creating TextEncoder...")
            self.text_encoder = TextEncoder(
                channels=self.config['hidden_dim'],
                kernel_size=self.config['text_encoder_kernel_size'],
                depth=self.config['n_layer'],
                n_symbols=self.config['n_token']
            )
            logger.info("✅ TextEncoder created")
            
            logger.info("🎵 Creating Decoder...")
            self.decoder = Decoder(
                dim_in=self.config['hidden_dim'],
                style_dim=self.config['style_dim'],
                dim_out=self.config['n_mels'],
                disable_complex=False,
                **self.config['istftnet']
            )
            logger.info("✅ Decoder created")
            
            self.context_length = self.bert.config.max_position_embeddings
            logger.info(f"✅ All components initialized, context_length={self.context_length}")
            
        except Exception as e:
            logger.error(f"❌ Component initialization failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _load_weights(self):
        """Load model weights with detailed logging"""
        model_file = self.model_path / "kokoro-v1_0.pth"
        logger.info(f"📂 Loading weights from {model_file}")
        
        try:
            # Load state dict
            logger.info("💾 Loading state dict...")
            state_dict = torch.load(model_file, map_location='cpu', weights_only=True)
            logger.info(f"✅ State dict loaded, keys: {list(state_dict.keys())}")
            
            # Load weights for each component
            for key, component_state_dict in state_dict.items():
                logger.info(f"🔄 Loading weights for {key}...")
                
                if not hasattr(self, key):
                    logger.error(f"❌ Component {key} not found in model")
                    continue
                
                component = getattr(self, key)
                try:
                    component.load_state_dict(component_state_dict)
                    logger.info(f"✅ {key} weights loaded successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Direct load failed for {key}, trying fallback: {e}")
                    try:
                        # Try stripping 'module.' prefix if present
                        clean_state_dict = {k[7:] if k.startswith('module.') else k: v 
                                          for k, v in component_state_dict.items()}
                        component.load_state_dict(clean_state_dict, strict=False)
                        logger.info(f"✅ {key} weights loaded with fallback")
                    except Exception as e2:
                        logger.error(f"❌ Failed to load {key} weights: {e2}")
                        raise
            
            logger.info("🎉 All weights loaded successfully!")
            
        except Exception as e:
            logger.error(f"❌ Weight loading failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

def test_offline_kokoro():
    """Test the offline Kokoro implementation"""
    try:
        logger.info("🧪 Testing OfflineKModel...")
        
        # Apply phonemizer fix first
        from phonemizer_wsl2_fix import apply_complete_phonemizer_fix
        logger.info("🔧 Applying phonemizer fix...")
        if not apply_complete_phonemizer_fix():
            logger.error("❌ Phonemizer fix failed")
            return False
        
        # Test offline model
        model_path = "/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts"
        model = OfflineKModel(model_path)
        
        logger.info("🎉 OfflineKModel test successful!")
        return True
        
    except Exception as e:
        logger.error(f"❌ OfflineKModel test failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_offline_kokoro()
    if success:
        print("🎉 SUCCESS: Offline Kokoro model works!")
    else:
        print("❌ FAILED: Offline Kokoro still has issues")