#!/usr/bin/env python3
"""
Hybrid Audio Manager - Handles both local microphone and remote Discord audio capture
"""

import asyncio
import logging
import sounddevice as sd
import numpy as np
import time
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AudioMode(Enum):
    LOCAL = "local"          # User at computer, use microphone
    REMOTE = "remote"        # User calling in, use Discord audio
    MIXED = "mixed"          # Both local and remote users
    AUTO = "auto"            # Auto-detect mode

@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    local_device: Optional[int] = None      # Microphone device
    remote_device: Optional[int] = None     # System audio loopback device

class HybridAudioManager:
    """Manages audio capture for both local and remote Discord usage"""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.current_mode = AudioMode.AUTO
        self.is_capturing = False
        
        # Discord state tracking
        self.voice_channel_users: Set[str] = set()
        self.local_user_id: Optional[str] = None
        self.last_mode_switch = 0
        self.mode_switch_cooldown = 2.0  # Prevent rapid switching
        
        # Audio callback
        self.audio_callback: Optional[Callable] = None
        
        # Current audio stream
        self.current_stream = None
        
        # Echo prevention for remote mode
        self.echo_prevention = AdvancedEchoPrevention()
        
    def set_audio_callback(self, callback: Callable):
        """Set the callback function for audio data"""
        self.audio_callback = callback
        
    def update_discord_state(self, users_in_channel: Set[str], local_user: str):
        """Update Discord voice channel state"""
        self.voice_channel_users = users_in_channel.copy()
        self.local_user_id = local_user
        
        # Auto-detect mode if enabled
        if self.current_mode == AudioMode.AUTO:
            self._auto_detect_mode()
    
    def _auto_detect_mode(self):
        """Automatically detect which audio mode to use"""
        current_time = time.time()
        
        # Prevent rapid mode switching
        if current_time - self.last_mode_switch < self.mode_switch_cooldown:
            return
            
        remote_users = self.voice_channel_users - {self.local_user_id} if self.local_user_id else self.voice_channel_users
        
        if len(remote_users) == 0:
            # No remote users, use local microphone
            target_mode = AudioMode.LOCAL
        elif len(remote_users) > 0:
            # Remote users present, use Discord audio
            target_mode = AudioMode.REMOTE
        else:
            # Default to local
            target_mode = AudioMode.LOCAL
            
        if target_mode != self._get_actual_mode():
            logger.info(f"🔄 Auto-switching from {self._get_actual_mode().value} to {target_mode.value} mode")
            self._switch_mode(target_mode)
    
    def _get_actual_mode(self) -> AudioMode:
        """Get the actual operational mode (not AUTO)"""
        if self.current_mode == AudioMode.AUTO:
            remote_users = self.voice_channel_users - {self.local_user_id} if self.local_user_id else self.voice_channel_users
            return AudioMode.REMOTE if len(remote_users) > 0 else AudioMode.LOCAL
        return self.current_mode
    
    def _switch_mode(self, new_mode: AudioMode):
        """Switch audio capture mode"""
        if self.is_capturing:
            # Stop current capture
            asyncio.create_task(self.stop_capture())
            # Start with new mode
            asyncio.create_task(self.start_capture())
        
        self.current_mode = new_mode
        self.last_mode_switch = time.time()
        
    async def start_capture(self) -> bool:
        """Start audio capture based on current mode"""
        if self.is_capturing:
            await self.stop_capture()
            
        actual_mode = self._get_actual_mode()
        
        if actual_mode == AudioMode.LOCAL:
            return await self._start_local_capture()
        elif actual_mode == AudioMode.REMOTE:
            return await self._start_remote_capture()
        else:
            logger.error(f"❌ Unsupported mode: {actual_mode}")
            return False
    
    async def _start_local_capture(self) -> bool:
        """Start local microphone capture"""
        try:
            logger.info("🎤 Starting local microphone capture...")
            
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"⚠️ Audio callback status: {status}")
                
                if self.is_capturing and len(indata) > 0:
                    # Convert to int16 and send
                    audio_int16 = (indata.flatten() * 32767).astype(np.int16)
                    if self.audio_callback:
                        self.audio_callback(audio_int16.tobytes())
            
            self.current_stream = sd.InputStream(
                device=self.config.local_device,
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                callback=audio_callback,
                blocksize=self.config.chunk_size,
                dtype=np.float32
            )
            
            self.current_stream.start()
            self.is_capturing = True
            logger.info("✅ Local microphone capture started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start local capture: {e}")
            return False
    
    async def _start_remote_capture(self) -> bool:
        """Start remote Discord audio capture (system audio)"""
        try:
            logger.info("📡 Starting remote Discord audio capture...")
            
            # Find system audio loopback device
            if self.config.remote_device is None:
                loopback_device = self._find_loopback_device()
                if loopback_device is None:
                    logger.error("❌ No system audio loopback device found")
                    return False
                self.config.remote_device = loopback_device
            
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"⚠️ Audio callback status: {status}")
                
                if self.is_capturing and len(indata) > 0:
                    # Enhanced echo prevention for remote mode
                    audio_data = indata.flatten()
                    
                    if self.echo_prevention.should_process_audio(audio_data):
                        audio_int16 = (audio_data * 32767).astype(np.int16)
                        if self.audio_callback:
                            self.audio_callback(audio_int16.tobytes())
                    else:
                        logger.debug("🔇 Audio blocked by echo prevention")
            
            self.current_stream = sd.InputStream(
                device=self.config.remote_device,
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                callback=audio_callback,
                blocksize=self.config.chunk_size,
                dtype=np.float32
            )
            
            self.current_stream.start()
            self.is_capturing = True
            logger.info("✅ Remote Discord audio capture started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start remote capture: {e}")
            return False
    
    def _find_loopback_device(self) -> Optional[int]:
        """Find system audio loopback device"""
        try:
            devices = sd.query_devices()
            
            for i, device in enumerate(devices):
                device_name = device['name'].lower()
                # Look for common loopback device names
                if any(keyword in device_name for keyword in [
                    'stereo mix', 'what u hear', 'loopback', 'wave out mix'
                ]):
                    if device['max_input_channels'] > 0:
                        logger.info(f"📡 Found loopback device: [{i}] {device['name']}")
                        return i
            
            logger.warning("⚠️ No loopback device found - you may need to enable 'Stereo Mix' in Windows")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding loopback device: {e}")
            return None
    
    async def stop_capture(self):
        """Stop audio capture"""
        self.is_capturing = False
        
        if self.current_stream:
            try:
                self.current_stream.stop()
                self.current_stream.close()
                self.current_stream = None
                logger.info("🛑 Audio capture stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping audio capture: {e}")
    
    def set_tts_output(self, audio_data: bytes):
        """Notify echo prevention of TTS output"""
        self.echo_prevention.track_tts_output(audio_data)


class AdvancedEchoPrevention:
    """Advanced echo prevention for remote Discord audio"""
    
    def __init__(self):
        self.recent_tts_outputs = []  # List of recent TTS audio
        self.tts_window = 5.0  # Keep last 5 seconds
        self.correlation_threshold = 0.75
        self.gate_until = 0  # Timing-based gating
        
    def track_tts_output(self, audio_data: bytes):
        """Track TTS output for echo detection"""
        current_time = time.time()
        
        # Convert bytes to numpy array for processing
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
        
        self.recent_tts_outputs.append({
            'audio': audio_array,
            'timestamp': current_time
        })
        
        # Clean up old entries
        cutoff_time = current_time - self.tts_window
        self.recent_tts_outputs = [
            entry for entry in self.recent_tts_outputs 
            if entry['timestamp'] > cutoff_time
        ]
        
        # Set timing gate
        duration = len(audio_array) / 16000  # Assuming 16kHz
        self.gate_until = current_time + duration + 0.5  # Audio duration + buffer
        
        logger.debug(f"🔇 TTS output tracked: {duration:.1f}s, gate until {self.gate_until:.1f}")
    
    def should_process_audio(self, audio_data: np.ndarray) -> bool:
        """Determine if audio should be processed or blocked as echo"""
        current_time = time.time()
        
        # Timing-based gating
        if current_time < self.gate_until:
            return False
        
        # Cross-correlation with recent TTS outputs
        for tts_entry in self.recent_tts_outputs:
            correlation = self._cross_correlate(audio_data, tts_entry['audio'])
            if correlation > self.correlation_threshold:
                logger.debug(f"🔇 Audio blocked: correlation {correlation:.3f} with recent TTS")
                return False
        
        return True
    
    def _cross_correlate(self, audio1: np.ndarray, audio2: np.ndarray) -> float:
        """Calculate cross-correlation between two audio signals"""
        try:
            # Ensure same length for comparison
            min_len = min(len(audio1), len(audio2))
            if min_len < 100:  # Too short for meaningful correlation
                return 0.0
                
            a1 = audio1[:min_len]
            a2 = audio2[:min_len]
            
            # Normalize
            a1 = a1 / (np.linalg.norm(a1) + 1e-10)
            a2 = a2 / (np.linalg.norm(a2) + 1e-10)
            
            # Cross-correlation
            correlation = np.correlate(a1, a2, mode='valid')[0]
            return abs(correlation)
            
        except Exception as e:
            logger.debug(f"Cross-correlation error: {e}")
            return 0.0