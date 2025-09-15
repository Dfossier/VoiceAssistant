"""
Optimized Smart Turn VAD v3 Implementation
Includes object pooling, async inference, and performance optimizations
"""

import asyncio
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from transformers import WhisperFeatureExtractor
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import time
from loguru import logger


class ObjectPool:
    """Generic object pool for reusing expensive objects"""
    
    def __init__(self, create_func, reset_func=None, max_size=10):
        self.create_func = create_func
        self.reset_func = reset_func
        self.pool = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
        
        # Pre-populate pool
        for _ in range(max_size // 2):
            self.pool.put(create_func())
    
    def acquire(self):
        """Get an object from the pool or create a new one"""
        try:
            return self.pool.get_nowait()
        except queue.Empty:
            return self.create_func()
    
    def release(self, obj):
        """Return an object to the pool"""
        if self.reset_func:
            self.reset_func(obj)
        try:
            self.pool.put_nowait(obj)
        except queue.Full:
            pass  # Pool is full, let object be garbage collected


class OptimizedSmartTurn:
    """Optimized Smart Turn VAD v3 with performance enhancements"""
    
    def __init__(self, 
                 model_path: Optional[str] = None,
                 max_workers: int = 2,
                 enable_profiling: bool = True):
        self.model_path = Path(model_path) if model_path else Path("models/smart_turn")
        self.session = None
        self.feature_extractor = None
        self.sample_rate = 16000
        self.model_initialized = False
        
        # Performance optimization
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.enable_profiling = enable_profiling
        
        # Object pools
        self.audio_buffer_pool = None
        self.feature_buffer_pool = None
        
        # Timing metrics
        self.timing_metrics = {
            "feature_extraction": [],
            "onnx_inference": [],
            "total_processing": [],
            "buffer_acquisition": []
        }
        
        # Pre-allocated buffers
        self.max_audio_samples = 8 * self.sample_rate  # 8 seconds
        
    def _create_audio_buffer(self):
        """Create a new audio buffer"""
        return np.zeros(self.max_audio_samples, dtype=np.float32)
    
    def _reset_audio_buffer(self, buffer):
        """Reset audio buffer for reuse"""
        buffer.fill(0)
        
    def _create_feature_buffer(self):
        """Create a new feature buffer"""
        # Whisper features are typically (80, frames) for mel spectrogram
        return np.zeros((1, 80, 3000), dtype=np.float32)  # Max ~30s of audio
        
    def initialize(self) -> bool:
        """Initialize the ONNX model and feature extractor with optimizations"""
        try:
            # Check for model file
            model_file = self.model_path / "smart-turn-v3.0.onnx"
            if not model_file.exists():
                logger.error(f"❌ Smart Turn model file not found: {model_file}")
                return False
            
            # Initialize object pools
            self.audio_buffer_pool = ObjectPool(
                self._create_audio_buffer,
                self._reset_audio_buffer,
                max_size=5
            )
            self.feature_buffer_pool = ObjectPool(
                self._create_feature_buffer,
                max_size=3
            )
            
            # Initialize Whisper feature extractor
            self.feature_extractor = WhisperFeatureExtractor(chunk_length=8)
            
            # Create ONNX runtime session with optimizations
            session_options = ort.SessionOptions()
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session_options.inter_op_num_threads = 1
            session_options.intra_op_num_threads = 2  # Use 2 threads for ops
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # Enable profiling if requested
            if self.enable_profiling:
                session_options.enable_profiling = True
            
            # Add execution provider options for better performance
            providers = []
            if ort.get_device() == 'GPU':
                providers.append(('CUDAExecutionProvider', {
                    'device_id': 0,
                    'arena_extend_strategy': 'kNextPowerOfTwo',
                    'gpu_mem_limit': 2 * 1024 * 1024 * 1024,  # 2GB
                    'cudnn_conv_algo_search': 'EXHAUSTIVE',
                }))
            providers.append('CPUExecutionProvider')
            
            self.session = ort.InferenceSession(
                str(model_file),
                sess_options=session_options,
                providers=providers
            )
            
            # Warm up the model with a test inference
            self._warmup_model()
            
            self.model_initialized = True
            logger.info(f"✅ Optimized Smart Turn v3 model loaded")
            logger.info(f"   Providers: {self.session.get_providers()}")
            logger.info(f"   Thread pool workers: {self.executor._max_workers}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing Optimized Smart Turn: {e}")
            return False
    
    def _warmup_model(self):
        """Warm up the model with dummy inference"""
        logger.info("🔄 Warming up Smart Turn model...")
        
        # Create dummy audio
        dummy_audio = np.zeros(int(self.sample_rate * 2), dtype=np.int16)
        
        # Run a few inferences to warm up
        for i in range(3):
            start = time.time()
            self._sync_analyze(dummy_audio.tobytes())
            warmup_time = (time.time() - start) * 1000
            logger.info(f"   Warmup {i+1}: {warmup_time:.1f}ms")
    
    def _truncate_audio_optimized(self, audio_array: np.ndarray, buffer: np.ndarray) -> np.ndarray:
        """Optimized audio truncation using pre-allocated buffer"""
        audio_len = len(audio_array)
        
        if audio_len > self.max_audio_samples:
            # Copy last 8 seconds into buffer
            np.copyto(buffer, audio_array[-self.max_audio_samples:])
        elif audio_len < self.max_audio_samples:
            # Reset buffer and copy audio to end
            buffer.fill(0)
            buffer[-audio_len:] = audio_array
        else:
            # Exact size, just copy
            np.copyto(buffer, audio_array)
            
        return buffer
    
    def _sync_analyze(self, audio_data: Union[bytes, np.ndarray]) -> Dict[str, Any]:
        """Synchronous analysis method with optimizations"""
        start_time = time.time()
        timing = {}
        
        # Get buffer from pool
        buffer_start = time.time()
        audio_buffer = self.audio_buffer_pool.acquire()
        timing['buffer_acquisition'] = (time.time() - buffer_start) * 1000
        
        try:
            # Convert bytes to numpy array if needed
            if isinstance(audio_data, bytes):
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_array = audio_data.astype(np.float32)
                
            if len(audio_array) == 0:
                return {"prediction": 0, "probability": 0.0, "timing": timing}
            
            # Truncate using optimized method
            truncate_start = time.time()
            audio_ready = self._truncate_audio_optimized(audio_array, audio_buffer)
            timing['truncation'] = (time.time() - truncate_start) * 1000
            
            # Feature extraction
            feature_start = time.time()
            inputs = self.feature_extractor(
                audio_ready[:self.max_audio_samples],  # Ensure we don't exceed max
                sampling_rate=16000,
                return_tensors="pt",
                padding="max_length",
                max_length=8 * 16000,
                truncation=True,
                do_normalize=True,
            )
            timing['feature_extraction'] = (time.time() - feature_start) * 1000
            
            # Prepare input for ONNX
            input_features = inputs.input_features.squeeze(0).numpy().astype(np.float32)
            input_features = np.expand_dims(input_features, axis=0)
            
            # Run ONNX inference
            inference_start = time.time()
            outputs = self.session.run(None, {"input_features": input_features})
            timing['onnx_inference'] = (time.time() - inference_start) * 1000
            
            # Extract results
            probability = float(outputs[0][0].item())
            prediction = 1 if probability > 0.5 else 0
            
            timing['total_processing'] = (time.time() - start_time) * 1000
            
            # Store timing metrics
            if self.enable_profiling:
                for key, value in timing.items():
                    if key in self.timing_metrics:
                        self.timing_metrics[key].append(value)
            
            return {
                "prediction": prediction,
                "probability": probability,
                "timing": timing
            }
            
        finally:
            # Always return buffer to pool
            self.audio_buffer_pool.release(audio_buffer)
    
    async def analyze_async(self, audio_data: Union[bytes, np.ndarray]) -> Dict[str, Any]:
        """Async analysis using thread pool executor"""
        if not self.model_initialized:
            raise RuntimeError("Model not initialized - call initialize() first")
        
        # Run synchronous analysis in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._sync_analyze,
            audio_data
        )
        
        return result
    
    def analyze(self, audio_data: Union[bytes, np.ndarray]) -> Dict[str, Any]:
        """Synchronous analyze method for backward compatibility"""
        if not self.model_initialized:
            raise RuntimeError("Model not initialized - call initialize() first")
        
        return self._sync_analyze(audio_data)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {}
        
        for metric_name, values in self.timing_metrics.items():
            if values:
                stats[metric_name] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "min": np.min(values),
                    "max": np.max(values),
                    "count": len(values)
                }
        
        return stats
    
    def reset_metrics(self):
        """Reset timing metrics"""
        for key in self.timing_metrics:
            self.timing_metrics[key].clear()
    
    def shutdown(self):
        """Clean shutdown of resources"""
        self.executor.shutdown(wait=True)
        if self.session:
            # Get profiling data if enabled
            if self.enable_profiling:
                prof_file = self.session.end_profiling()
                logger.info(f"📊 ONNX profiling data saved to: {prof_file}")


# Global instance with optimizations enabled
optimized_smart_turn = OptimizedSmartTurn(enable_profiling=True)