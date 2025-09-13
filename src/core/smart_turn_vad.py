"""
Smart Turn VAD Service
Semantic Voice Activity Detection using Smart Turn v3 model
"""

import asyncio
import time
import numpy as np
from typing import Optional, Tuple, Dict, Any
from loguru import logger


class SmartTurnVAD:
    """Smart Turn semantic VAD integration for voice assistant"""
    
    def __init__(self, 
                 confidence_threshold: float = 0.8,
                 min_audio_length: float = 0.5,
                 sample_rate: int = 16000):
        """
        Initialize Smart Turn VAD
        
        Args:
            confidence_threshold: Minimum confidence for turn detection (0.0-1.0)
            min_audio_length: Minimum audio length before turn detection (seconds)
            sample_rate: Expected audio sample rate (Smart Turn requires 16kHz)
        """
        self.confidence_threshold = confidence_threshold
        self.min_audio_length = min_audio_length
        self.sample_rate = sample_rate
        
        # Model components
        self.analyzer = None
        self.is_initialized = False
        self.initialization_error = None
        
        # Performance tracking
        self.inference_times = []
        self.detection_count = 0
        self.false_positive_count = 0
        
        # Audio buffering for minimum length requirement
        self.audio_buffer = bytearray()
        self.buffer_start_time = None
        
        logger.info(f"🤖 Smart Turn VAD initialized with:")
        logger.info(f"   Confidence threshold: {confidence_threshold}")
        logger.info(f"   Min audio length: {min_audio_length}s")
        logger.info(f"   Sample rate: {sample_rate}Hz")

    async def initialize(self) -> bool:
        """Initialize Smart Turn model"""
        if self.is_initialized:
            return True
            
        try:
            logger.info("🔄 Loading Smart Turn v3 model...")
            
            # Import Smart Turn analyzer
            from pipecat.analyzers.smart_turn import LocalSmartTurnAnalyzerV3
            
            # Initialize analyzer
            self.analyzer = LocalSmartTurnAnalyzerV3()
            
            # Test with dummy audio to ensure it works
            test_audio = np.zeros(int(self.sample_rate * 0.1), dtype=np.int16).tobytes()  # 100ms silence
            start_time = time.time()
            
            try:
                test_result = await self.analyzer.analyze(test_audio)
                init_time = (time.time() - start_time) * 1000
                
                self.is_initialized = True
                logger.info(f"✅ Smart Turn v3 loaded successfully")
                logger.info(f"   Initialization test: {init_time:.1f}ms")
                logger.info(f"   Test result: {test_result}")
                
                return True
                
            except Exception as test_error:
                logger.error(f"❌ Smart Turn test inference failed: {test_error}")
                self.initialization_error = f"Test inference failed: {test_error}"
                return False
                
        except ImportError as e:
            error_msg = f"Smart Turn import failed: {e}"
            logger.error(f"❌ {error_msg}")
            logger.info("💡 Install with: pip install 'pipecat-ai[local-smart-turn-v3]==0.0.85'")
            self.initialization_error = error_msg
            return False
            
        except Exception as e:
            error_msg = f"Smart Turn initialization failed: {e}"
            logger.error(f"❌ {error_msg}")
            self.initialization_error = error_msg
            return False

    def add_audio_chunk(self, audio_data: bytes) -> bool:
        """
        Add audio chunk to buffer and check if minimum length is reached
        
        Args:
            audio_data: Raw PCM audio data (16-bit, 16kHz, mono)
            
        Returns:
            True if minimum audio length is reached and ready for turn detection
        """
        if not audio_data:
            return False
            
        # Initialize buffer timing
        if not self.audio_buffer:
            self.buffer_start_time = time.time()
            
        # Add to buffer
        self.audio_buffer.extend(audio_data)
        
        # Check if we have minimum required audio length
        buffer_duration = len(self.audio_buffer) / (self.sample_rate * 2)  # 16-bit = 2 bytes per sample
        
        return buffer_duration >= self.min_audio_length

    async def detect_turn_end(self, force_analysis: bool = False) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Detect if user has finished speaking and expects a response
        
        Args:
            force_analysis: Force analysis even if minimum length not reached
            
        Returns:
            Tuple of (is_turn_end, confidence, metadata)
        """
        if not self.is_initialized:
            logger.warning("⚠️ Smart Turn not initialized - using fallback")
            return False, 0.0, {"error": "not_initialized", "fallback": True}
            
        if not self.audio_buffer:
            return False, 0.0, {"error": "no_audio", "buffer_size": 0}
            
        # Check minimum audio length unless forced
        buffer_duration = len(self.audio_buffer) / (self.sample_rate * 2)
        if not force_analysis and buffer_duration < self.min_audio_length:
            return False, 0.0, {
                "waiting": True,
                "buffer_duration": buffer_duration,
                "min_required": self.min_audio_length
            }
        
        try:
            # Perform Smart Turn analysis
            start_time = time.time()
            audio_bytes = bytes(self.audio_buffer)
            
            # Smart Turn inference
            result = await self.analyzer.analyze(audio_bytes)
            
            inference_time = (time.time() - start_time) * 1000  # ms
            self.inference_times.append(inference_time)
            
            # Parse result (format may vary based on Smart Turn implementation)
            is_turn_end = self._parse_turn_result(result)
            confidence = self._extract_confidence(result)
            
            # Apply confidence threshold
            turn_detected = is_turn_end and confidence >= self.confidence_threshold
            
            if turn_detected:
                self.detection_count += 1
                logger.info(f"🎯 Turn end detected! Confidence: {confidence:.2f}")
            
            # Create metadata
            metadata = {
                "inference_time_ms": inference_time,
                "buffer_duration": buffer_duration,
                "confidence": confidence,
                "raw_result": str(result),
                "threshold_met": confidence >= self.confidence_threshold,
                "buffer_size_bytes": len(audio_bytes)
            }
            
            # Clear buffer after analysis
            self._clear_buffer()
            
            return turn_detected, confidence, metadata
            
        except Exception as e:
            logger.error(f"❌ Smart Turn detection error: {e}")
            self._clear_buffer()  # Clear buffer on error
            
            return False, 0.0, {
                "error": str(e),
                "buffer_duration": buffer_duration,
                "inference_time_ms": 0
            }

    def _parse_turn_result(self, result: Any) -> bool:
        """Parse Smart Turn result to determine if turn ended"""
        # Smart Turn v3 result format may vary - adapt based on actual implementation
        if result is None:
            return False
            
        # Common patterns for turn detection results:
        if isinstance(result, bool):
            return result
        elif isinstance(result, (int, float)):
            return result > 0.5  # Threshold for numeric results
        elif hasattr(result, 'turn_ended'):
            return bool(result.turn_ended)
        elif hasattr(result, 'is_complete'):
            return bool(result.is_complete)
        elif isinstance(result, dict):
            return result.get('turn_ended', result.get('is_complete', False))
        else:
            # Default: treat any non-None result as turn detection
            logger.debug(f"Unknown result format: {type(result)} - {result}")
            return True

    def _extract_confidence(self, result: Any) -> float:
        """Extract confidence score from Smart Turn result"""
        if result is None:
            return 0.0
            
        # Common confidence extraction patterns:
        if isinstance(result, (int, float)):
            return float(result)
        elif hasattr(result, 'confidence'):
            return float(result.confidence)
        elif hasattr(result, 'score'):
            return float(result.score)
        elif isinstance(result, dict):
            return float(result.get('confidence', result.get('score', 1.0)))
        else:
            # Default confidence if result exists
            return 1.0

    def _clear_buffer(self):
        """Clear audio buffer and reset timing"""
        self.audio_buffer = bytearray()
        self.buffer_start_time = None

    def should_fallback_to_buffering(self) -> bool:
        """Determine if system should fallback to traditional buffering"""
        if not self.is_initialized:
            return True
            
        # Fallback if Smart Turn is consistently slow
        if len(self.inference_times) >= 10:
            avg_time = np.mean(self.inference_times[-10:])
            if avg_time > 100:  # >100ms is too slow for real-time
                logger.warning(f"⚠️ Smart Turn averaging {avg_time:.1f}ms - consider fallback")
                return True
                
        return False

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {
            "is_initialized": self.is_initialized,
            "initialization_error": self.initialization_error,
            "detection_count": self.detection_count,
            "false_positive_count": self.false_positive_count,
            "total_inferences": len(self.inference_times)
        }
        
        if self.inference_times:
            stats.update({
                "avg_inference_time_ms": np.mean(self.inference_times),
                "min_inference_time_ms": np.min(self.inference_times),
                "max_inference_time_ms": np.max(self.inference_times),
                "recent_avg_ms": np.mean(self.inference_times[-10:]) if len(self.inference_times) >= 10 else None
            })
            
        return stats

    def reset_stats(self):
        """Reset performance statistics"""
        self.inference_times = []
        self.detection_count = 0
        self.false_positive_count = 0
        logger.info("📊 Smart Turn performance stats reset")

    async def cleanup(self):
        """Cleanup resources"""
        self._clear_buffer()
        if hasattr(self.analyzer, 'cleanup'):
            await self.analyzer.cleanup()
        
        logger.info("🧹 Smart Turn VAD cleaned up")


# Global instance for easy access (similar to local_model_manager pattern)
smart_turn_vad = SmartTurnVAD()


async def initialize_smart_turn_vad(
    confidence_threshold: float = 0.8,
    min_audio_length: float = 0.5
) -> bool:
    """Initialize global Smart Turn VAD instance"""
    global smart_turn_vad
    
    smart_turn_vad = SmartTurnVAD(
        confidence_threshold=confidence_threshold,
        min_audio_length=min_audio_length
    )
    
    return await smart_turn_vad.initialize()


# Example usage and testing functions
async def test_smart_turn_vad():
    """Test Smart Turn VAD functionality"""
    logger.info("🧪 Testing Smart Turn VAD...")
    
    vad = SmartTurnVAD(confidence_threshold=0.7)
    
    if not await vad.initialize():
        logger.error("❌ Failed to initialize Smart Turn VAD")
        return False
    
    # Create test audio
    sample_rate = 16000
    duration = 2.0
    samples = int(sample_rate * duration)
    
    # Generate speech-like audio
    t = np.linspace(0, duration, samples)
    audio = np.sin(2 * np.pi * 180 * t) * 0.3
    audio += np.random.normal(0, 0.05, samples)
    
    # Add silence at end
    silence_samples = int(0.5 * sample_rate)
    audio = np.concatenate([audio, np.zeros(silence_samples)])
    
    audio_bytes = (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    
    # Test turn detection
    chunk_size = int(sample_rate * 0.5 * 2)  # 500ms chunks
    
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i:i+chunk_size]
        ready = vad.add_audio_chunk(chunk)
        
        if ready:
            is_turn_end, confidence, metadata = await vad.detect_turn_end()
            logger.info(f"Turn detection: {is_turn_end}, confidence: {confidence:.2f}")
            logger.info(f"Metadata: {metadata}")
            
            if is_turn_end:
                break
    
    # Print performance stats
    stats = vad.get_performance_stats()
    logger.info(f"Performance stats: {stats}")
    
    await vad.cleanup()
    logger.info("✅ Smart Turn VAD test completed")
    
    return True


if __name__ == "__main__":
    asyncio.run(test_smart_turn_vad())