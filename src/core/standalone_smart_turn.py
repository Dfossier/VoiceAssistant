"""
Standalone Smart Turn VAD v3 Wrapper
Standalone implementation based on Smart Turn V3 algorithm
Works independently without Pipecat dependencies
"""

import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Optional, Union, Dict
from transformers import WhisperFeatureExtractor

class StandaloneSmartTurn:
    """Standalone Smart Turn VAD v3 implementation using actual model"""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = Path(model_path) if model_path else Path("models/smart_turn")
        self.session = None
        self.feature_extractor = None
        self.sample_rate = 16000
        self.model_initialized = False
        
    def initialize(self) -> bool:
        """Initialize the ONNX model and feature extractor"""
        try:
            # Check for the actual Smart Turn model file
            model_file = self.model_path / "smart-turn-v3.0.onnx"
            if not model_file.exists():
                print(f"❌ Smart Turn model file not found: {model_file}")
                return False
            
            # Initialize Whisper feature extractor (same as Smart Turn uses)
            self.feature_extractor = WhisperFeatureExtractor(chunk_length=8)
            
            # Create ONNX runtime session with optimization settings
            session_options = ort.SessionOptions()
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session_options.inter_op_num_threads = 1
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            self.session = ort.InferenceSession(
                str(model_file),
                sess_options=session_options,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
            )
            
            self.model_initialized = True
            print(f"✅ Smart Turn v3 model loaded from {model_file}")
            print(f"   Providers: {self.session.get_providers()}")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing Smart Turn: {e}")
            return False
    
    def _truncate_audio_to_last_n_seconds(self, audio_array: np.ndarray, n_seconds: int = 8) -> np.ndarray:
        """Truncate audio to last n seconds or pad with zeros to meet n seconds."""
        max_samples = n_seconds * self.sample_rate
        if len(audio_array) > max_samples:
            return audio_array[-max_samples:]
        elif len(audio_array) < max_samples:
            # Pad with zeros at the beginning
            padding = max_samples - len(audio_array)
            return np.pad(audio_array, (padding, 0), mode='constant', constant_values=0)
        return audio_array
    
    def analyze(self, audio_data: Union[bytes, np.ndarray]) -> Dict[str, Union[float, int]]:
        """
        Analyze audio for turn detection using Smart Turn v3 model
        
        Args:
            audio_data: Raw PCM audio data (bytes) or numpy array
            
        Returns:
            Dict with 'prediction' (0/1) and 'probability' (0.0-1.0)
        """
        if not self.model_initialized:
            raise RuntimeError("Model not initialized - call initialize() first")
            
        # Convert bytes to numpy array if needed
        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_data.astype(np.float32)
            
        if len(audio_array) == 0:
            return {"prediction": 0, "probability": 0.0}
        
        try:
            # Truncate to 8 seconds (keeping the end) or pad to 8 seconds
            audio_array = self._truncate_audio_to_last_n_seconds(audio_array, n_seconds=8)
            
            # Process audio using Whisper's feature extractor (same as Smart Turn)
            inputs = self.feature_extractor(
                audio_array,
                sampling_rate=16000,
                return_tensors="pt",
                padding="max_length",
                max_length=8 * 16000,
                truncation=True,
                do_normalize=True,
            )
            
            # Convert to numpy and ensure correct shape for ONNX
            input_features = inputs.input_features.squeeze(0).numpy().astype(np.float32)
            input_features = np.expand_dims(input_features, axis=0)  # Add batch dimension
            
            # Run ONNX inference
            outputs = self.session.run(None, {"input_features": input_features})
            
            # Extract probability (ONNX model returns sigmoid probabilities)
            probability = float(outputs[0][0].item())
            
            # Make prediction (1 for Complete, 0 for Incomplete)
            prediction = 1 if probability > 0.5 else 0
            
            return {
                "prediction": prediction,
                "probability": probability,
            }
            
        except Exception as e:
            print(f"❌ Error during Smart Turn inference: {e}")
            return {"prediction": 0, "probability": 0.0}

# Global instance
smart_turn_model = StandaloneSmartTurn()
