"""
VAD Configuration and Parameter Tuning
Allows easy adjustment of VAD parameters for optimal performance
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class VADConfig:
    """Configuration for Voice Activity Detection"""
    
    # Smart Turn VAD parameters
    confidence_threshold: float = 0.7  # Lowered from 0.8 to reduce cutoffs
    min_audio_length: float = 0.3      # Lowered from 0.5s for faster response
    max_audio_length: float = 8.0      # Maximum audio to analyze
    
    # Turn detection sensitivity
    turn_probability_threshold: float = 0.6  # When to consider turn complete
    continuation_threshold: float = 0.4      # Below this, assume user stopped
    
    # Audio preprocessing
    sample_rate: int = 16000
    normalize_audio: bool = True
    remove_silence: bool = False  # Keep silence for context
    
    # Buffering behavior
    use_adaptive_buffering: bool = True
    initial_buffer_ms: int = 300      # Start with 300ms
    max_buffer_ms: int = 1000         # Max 1 second buffer
    buffer_step_ms: int = 100         # Increment by 100ms
    
    # Performance tuning
    enable_gpu: bool = True
    num_threads: int = 2
    batch_inference: bool = False
    prefetch_features: bool = True
    
    # Fallback behavior
    fallback_to_silence_vad: bool = True
    silence_threshold_db: float = -40.0
    silence_duration_ms: int = 700  # Reduced from 1000ms
    
    # Experimental features
    use_contextual_vad: bool = True  # Consider conversation context
    enable_interruption_detection: bool = True
    multi_speaker_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VADConfig':
        """Create from dictionary"""
        return cls(**data)
    
    def save(self, path: Path):
        """Save configuration to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"💾 VAD config saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> 'VADConfig':
        """Load configuration from file"""
        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        config = cls.from_dict(data)
        logger.info(f"📂 VAD config loaded from {path}")
        return config


@dataclass
class VADPreset:
    """Predefined VAD presets for different scenarios"""
    name: str
    description: str
    config: VADConfig


class VADPresets:
    """Collection of VAD presets"""
    
    FAST_RESPONSE = VADPreset(
        name="fast_response",
        description="Optimized for quick responses, may have more false positives",
        config=VADConfig(
            confidence_threshold=0.6,
            min_audio_length=0.2,
            turn_probability_threshold=0.5,
            initial_buffer_ms=200,
            silence_duration_ms=500
        )
    )
    
    BALANCED = VADPreset(
        name="balanced",
        description="Balanced between speed and accuracy",
        config=VADConfig(
            confidence_threshold=0.7,
            min_audio_length=0.3,
            turn_probability_threshold=0.6,
            initial_buffer_ms=300,
            silence_duration_ms=700
        )
    )
    
    HIGH_ACCURACY = VADPreset(
        name="high_accuracy",
        description="Optimized for accuracy, may be slightly slower",
        config=VADConfig(
            confidence_threshold=0.8,
            min_audio_length=0.5,
            turn_probability_threshold=0.7,
            initial_buffer_ms=400,
            silence_duration_ms=1000
        )
    )
    
    CONVERSATION = VADPreset(
        name="conversation",
        description="Optimized for natural conversation flow",
        config=VADConfig(
            confidence_threshold=0.65,
            min_audio_length=0.3,
            turn_probability_threshold=0.55,
            use_contextual_vad=True,
            enable_interruption_detection=True,
            initial_buffer_ms=250,
            silence_duration_ms=600
        )
    )
    
    LOW_LATENCY = VADPreset(
        name="low_latency",
        description="Minimum latency for real-time applications",
        config=VADConfig(
            confidence_threshold=0.55,
            min_audio_length=0.15,
            turn_probability_threshold=0.5,
            use_adaptive_buffering=False,
            initial_buffer_ms=150,
            max_buffer_ms=300,
            enable_gpu=True,
            prefetch_features=True
        )
    )
    
    @classmethod
    def get_preset(cls, name: str) -> Optional[VADPreset]:
        """Get a preset by name"""
        presets = {
            "fast_response": cls.FAST_RESPONSE,
            "balanced": cls.BALANCED,
            "high_accuracy": cls.HIGH_ACCURACY,
            "conversation": cls.CONVERSATION,
            "low_latency": cls.LOW_LATENCY
        }
        return presets.get(name)
    
    @classmethod
    def list_presets(cls) -> Dict[str, str]:
        """List all available presets"""
        return {
            "fast_response": cls.FAST_RESPONSE.description,
            "balanced": cls.BALANCED.description,
            "high_accuracy": cls.HIGH_ACCURACY.description,
            "conversation": cls.CONVERSATION.description,
            "low_latency": cls.LOW_LATENCY.description
        }


class VADTuner:
    """Dynamic VAD parameter tuning based on performance metrics"""
    
    def __init__(self, config: VADConfig):
        self.config = config
        self.performance_history = []
        self.false_positive_rate = 0.0
        self.false_negative_rate = 0.0
        self.avg_latency_ms = 0.0
        
    def record_detection(self, 
                        was_correct: bool, 
                        confidence: float, 
                        latency_ms: float,
                        audio_duration_ms: float):
        """Record a detection result for tuning"""
        self.performance_history.append({
            "correct": was_correct,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "audio_duration_ms": audio_duration_ms,
            "threshold": self.config.confidence_threshold
        })
        
        # Keep only recent history
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)
        
        # Update metrics
        self._update_metrics()
        
        # Auto-tune if needed
        if len(self.performance_history) >= 20:
            self._auto_tune()
    
    def _update_metrics(self):
        """Update performance metrics"""
        if not self.performance_history:
            return
        
        correct_count = sum(1 for h in self.performance_history if h["correct"])
        total_count = len(self.performance_history)
        
        # Calculate error rates
        self.false_positive_rate = 1.0 - (correct_count / total_count)
        
        # Calculate average latency
        latencies = [h["latency_ms"] for h in self.performance_history]
        self.avg_latency_ms = sum(latencies) / len(latencies)
    
    def _auto_tune(self):
        """Automatically tune parameters based on performance"""
        logger.info("🔧 Auto-tuning VAD parameters...")
        
        # If too many false positives, increase threshold
        if self.false_positive_rate > 0.2:
            old_threshold = self.config.confidence_threshold
            self.config.confidence_threshold = min(0.9, self.config.confidence_threshold + 0.05)
            logger.info(f"   Increased confidence threshold: {old_threshold:.2f} → {self.config.confidence_threshold:.2f}")
        
        # If latency is too high, reduce buffer
        if self.avg_latency_ms > 100:
            old_buffer = self.config.initial_buffer_ms
            self.config.initial_buffer_ms = max(150, self.config.initial_buffer_ms - 50)
            logger.info(f"   Reduced initial buffer: {old_buffer}ms → {self.config.initial_buffer_ms}ms")
        
        # If accuracy is good and latency is low, we can be more aggressive
        if self.false_positive_rate < 0.1 and self.avg_latency_ms < 50:
            old_min_length = self.config.min_audio_length
            self.config.min_audio_length = max(0.15, self.config.min_audio_length - 0.05)
            logger.info(f"   Reduced min audio length: {old_min_length:.2f}s → {self.config.min_audio_length:.2f}s")
    
    def get_tuning_report(self) -> Dict[str, Any]:
        """Get a report of current tuning status"""
        return {
            "current_config": self.config.to_dict(),
            "performance_metrics": {
                "false_positive_rate": self.false_positive_rate,
                "avg_latency_ms": self.avg_latency_ms,
                "sample_count": len(self.performance_history)
            },
            "recommendations": self._get_recommendations()
        }
    
    def _get_recommendations(self) -> list:
        """Get tuning recommendations"""
        recommendations = []
        
        if self.false_positive_rate > 0.15:
            recommendations.append("Consider increasing confidence_threshold to reduce false positives")
        
        if self.avg_latency_ms > 80:
            recommendations.append("Consider reducing min_audio_length or initial_buffer_ms for lower latency")
        
        if self.false_positive_rate < 0.05 and self.avg_latency_ms > 50:
            recommendations.append("System is accurate but slow - consider using 'low_latency' preset")
        
        return recommendations


# Global configuration instance
vad_config = VADConfig()

# Load from file if exists
config_path = Path("config/vad_config.json")
if config_path.exists():
    vad_config = VADConfig.load(config_path)
else:
    # Save default config
    vad_config.save(config_path)