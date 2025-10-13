# Hybrid Audio Architecture for Local + Remote Discord Usage

## Use Cases

### **Local Usage** (Current)
```
User (at computer) → Microphone → Bot → AI → Discord Voice → User
```

### **Remote Usage** (New)
```
User (phone) → Discord Voice → Computer → Bot → AI → Discord Voice → User (phone)
```

## Technical Architecture

### **Audio Source Detection**
The bot automatically detects audio source and switches modes:

1. **Local Mode**: No other users in voice channel + microphone activity
2. **Remote Mode**: Other users detected in voice channel + Discord audio activity
3. **Mixed Mode**: Both local and remote users present

### **Audio Capture Sources**

#### **Local Mode** ✅ (Current)
- **Source**: Default microphone (`sounddevice` default input)
- **Echo Prevention**: Current 3-layer system (timing + conversation states + content filtering)

#### **Remote Mode** (New)
- **Source**: Discord audio output (system audio loopback)
- **Echo Prevention**: Advanced multi-layer system (see below)

#### **Mixed Mode** (Future)
- **Source**: Audio mixing of both sources
- **Echo Prevention**: Combined approach

## Advanced Echo Prevention for Remote Mode

### **Layer 1: Audio Source Separation**
```python
class AudioSourceSeparator:
    def __init__(self):
        self.bot_voice_signature = None  # Learn bot's voice characteristics
        self.user_voice_signatures = {}  # Learn user voice patterns
        
    async def separate_sources(self, audio_data):
        # Use ML-based source separation
        # Identify bot voice vs user voices
        # Return only non-bot audio
```

### **Layer 2: Enhanced Timing Gates**
```python
class AdvancedAudioGate:
    def __init__(self):
        self.tts_playback_buffer = []  # Exact audio bot is outputting
        self.cross_correlation_threshold = 0.85
        
    def is_bot_echo(self, incoming_audio):
        # Cross-correlate incoming audio with recent TTS output
        # Account for Discord compression/delay
        # Block if correlation > threshold
```

### **Layer 3: Discord State Awareness**
```python
class DiscordVoiceState:
    def __init__(self):
        self.users_speaking = set()  # Who's currently speaking
        self.bot_speaking = False   # Is bot currently outputting audio
        
    async def should_process_audio(self):
        # Only process if:
        # - Bot is not speaking AND
        # - At least one user is speaking AND
        # - Audio doesn't match recent bot output
```

### **Layer 4: Adaptive Learning**
```python
class EchoPrevention:
    def __init__(self):
        self.false_positive_rate = 0.0
        self.missed_echo_rate = 0.0
        
    def adapt_thresholds(self):
        # Monitor performance and adapt
        # Reduce false positives (blocking user speech)
        # Reduce missed echoes (bot responding to itself)
```

## Implementation Strategy

### **Phase 1: Add Audio Source Detection**
1. Detect other users in voice channel
2. Add system audio capture capability
3. Simple mode switching

### **Phase 2: Basic Echo Prevention**
1. Enhanced timing gates for system audio
2. Audio fingerprinting
3. Cross-correlation filtering

### **Phase 3: Advanced Features**
1. ML-based source separation
2. Voice biometrics
3. Adaptive learning

## Configuration Example

```json
{
  "audio_modes": {
    "local": {
      "source": "microphone",
      "device_index": null,
      "echo_prevention": "basic"
    },
    "remote": {
      "source": "system_audio",
      "device_index": 2,
      "echo_prevention": "advanced"
    },
    "auto_detect": true,
    "fallback_mode": "local"
  },
  "echo_prevention": {
    "timing_gate_multiplier": 1.5,
    "cross_correlation_threshold": 0.85,
    "voice_learning_enabled": true,
    "adaptive_thresholds": true
  }
}
```

## Benefits

1. **Backward Compatible**: Current local usage still works
2. **Automatic**: No manual mode switching required
3. **Robust**: Multiple echo prevention layers
4. **Scalable**: Can handle multiple remote users
5. **Adaptive**: Learns and improves over time

## Risks & Mitigation

### **Risk**: False Positives (blocking real user speech)
**Mitigation**: Conservative thresholds, user feedback, adaptive learning

### **Risk**: Echo Loops
**Mitigation**: Multiple detection layers, fail-safe timeouts

### **Risk**: Complex Configuration
**Mitigation**: Auto-detection, sensible defaults, simple fallbacks