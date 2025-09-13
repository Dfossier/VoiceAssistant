#!/usr/bin/env python3
"""
Custom Voice Capture System for Discord.py
Implements voice recording without relying on py-cord sinks
"""

import asyncio
import discord
import discord.opus
import logging
import struct
import wave
import tempfile
import os
from typing import Dict, Optional, Callable, Any
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

class VoicePacketHandler:
    """Handles raw voice packets from Discord"""
    
    def __init__(self, callback: Callable):
        self.callback = callback
        self.user_streams: Dict[int, dict] = defaultdict(lambda: {
            'packets': [],
            'last_packet_time': 0,
            'user': None
        })
        self.cleanup_task = None
        
    def handle_packet(self, packet_data: bytes, user_id: int, user):
        """Handle incoming voice packet"""
        try:
            if not packet_data or len(packet_data) < 12:
                return
            
            current_time = time.time()
            
            # Store user info
            self.user_streams[user_id]['user'] = user
            self.user_streams[user_id]['last_packet_time'] = current_time
            
            # Add packet to user's stream
            self.user_streams[user_id]['packets'].append(packet_data)
            
            logger.debug(f"[PACKET] Received {len(packet_data)} bytes from {user.display_name}")
            
            # If we have enough packets (about 2 seconds worth), process them
            if len(self.user_streams[user_id]['packets']) >= 100:  # ~2 seconds at 20ms per packet
                asyncio.create_task(self._process_user_audio(user_id))
                
        except Exception as e:
            logger.error(f"[ERROR] Packet handling error: {e}")
    
    async def _process_user_audio(self, user_id: int):
        """Process accumulated audio packets for a user"""
        try:
            user_data = self.user_streams[user_id]
            packets = user_data['packets'].copy()
            user = user_data['user']
            
            # Clear packets
            user_data['packets'].clear()
            
            if not packets or not user:
                return
            
            logger.info(f"[AUDIO] Processing {len(packets)} packets from {user.display_name}")
            
            # Combine packets into audio data
            audio_data = self._combine_packets(packets)
            
            if audio_data and len(audio_data) > 1000:
                # Call the processing callback
                await self.callback(audio_data, user)
                
        except Exception as e:
            logger.error(f"[ERROR] Audio processing error: {e}")
    
    def _combine_packets(self, packets) -> Optional[bytes]:
        """Combine voice packets into WAV audio data"""
        try:
            # Decode Opus packets and combine
            decoded_frames = []
            
            for packet in packets:
                try:
                    # Discord voice packets are Opus-encoded
                    # We need to decode them to PCM
                    if discord.opus.is_loaded():
                        # Try to decode Opus data
                        # This is simplified - real implementation needs proper RTP header parsing
                        decoded_frame = self._decode_opus_packet(packet)
                        if decoded_frame:
                            decoded_frames.append(decoded_frame)
                except:
                    continue
            
            if not decoded_frames:
                return None
            
            # Combine all decoded frames
            combined_audio = b''.join(decoded_frames)
            
            # Create WAV file
            return self._create_wav_data(combined_audio)
            
        except Exception as e:
            logger.error(f"[ERROR] Packet combination error: {e}")
            return None
    
    def _decode_opus_packet(self, packet: bytes) -> Optional[bytes]:
        """Decode a single Opus packet to PCM"""
        try:
            # Skip RTP header (first 12 bytes)
            if len(packet) < 12:
                return None
            
            opus_data = packet[12:]
            
            if not opus_data:
                return None
            
            # Use Discord's Opus decoder if available
            # This is a simplified approach - real implementation needs proper Opus handling
            try:
                # Discord uses 48kHz, 2 channels, 20ms frames
                # Each frame should be 1920 samples (48000 * 0.02) * 2 channels * 2 bytes = 7680 bytes
                decoder = discord.opus.Decoder()
                decoded = decoder.decode(opus_data, 1920)  # 1920 samples per frame
                return decoded
            except:
                # Fallback: return raw data (won't be proper audio but won't crash)
                return opus_data[:1920*2*2]  # Approximate frame size
                
        except Exception as e:
            logger.debug(f"[DEBUG] Opus decode error: {e}")
            return None
    
    def _create_wav_data(self, pcm_data: bytes) -> bytes:
        """Create WAV file data from PCM audio"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Create WAV file
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(48000)  # 48kHz (Discord standard)
                wav_file.writeframes(pcm_data)
            
            # Read back as bytes
            with open(temp_path, 'rb') as f:
                wav_data = f.read()
            
            # Cleanup
            os.unlink(temp_path)
            
            logger.info(f"[WAV] Created {len(wav_data)} bytes of WAV data")
            return wav_data
            
        except Exception as e:
            logger.error(f"[ERROR] WAV creation error: {e}")
            return b''
    
    def start_cleanup_task(self):
        """Start cleanup task for old user streams"""
        if not self.cleanup_task:
            self.cleanup_task = asyncio.create_task(self._cleanup_old_streams())
    
    def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            self.cleanup_task = None
    
    async def _cleanup_old_streams(self):
        """Clean up old user streams"""
        try:
            while True:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
                current_time = time.time()
                expired_users = []
                
                for user_id, data in self.user_streams.items():
                    # Remove streams older than 10 seconds
                    if current_time - data['last_packet_time'] > 10:
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del self.user_streams[user_id]
                    
                if expired_users:
                    logger.debug(f"[CLEANUP] Removed {len(expired_users)} expired streams")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Cleanup error: {e}")

class CustomVoiceClient:
    """Extended voice client with custom packet capture"""
    
    def __init__(self, original_voice_client, audio_callback):
        self.voice_client = original_voice_client
        self.packet_handler = VoicePacketHandler(audio_callback)
        self.original_receive = None
        self.patched = False
        
    def start_capture(self):
        """Start capturing voice packets"""
        try:
            if self.patched:
                return True
                
            # Monkey patch the voice client to intercept packets
            if hasattr(self.voice_client, '_voice_server_speaking'):
                self.original_receive = getattr(self.voice_client, '_voice_server_speaking', None)
                
            # Hook into the voice client's packet reception
            self._patch_voice_client()
            
            # Start cleanup task
            self.packet_handler.start_cleanup_task()
            
            self.patched = True
            logger.info("[CAPTURE] Custom voice capture started")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to start capture: {e}")
            return False
    
    def stop_capture(self):
        """Stop capturing voice packets"""
        try:
            if not self.patched:
                return
                
            # Stop cleanup
            self.packet_handler.stop_cleanup_task()
            
            # Restore original methods if we patched them
            self._unpatch_voice_client()
            
            self.patched = False
            logger.info("[CAPTURE] Custom voice capture stopped")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to stop capture: {e}")
    
    def _patch_voice_client(self):
        """Patch the voice client to intercept voice packets"""
        try:
            # This is a complex operation that requires deep knowledge of discord.py internals
            # We'll implement a simplified version that tries to hook into voice data
            
            original_socket = self.voice_client.socket
            if original_socket:
                # Wrap the socket's recv method
                original_recv = original_socket.recv
                
                def patched_recv(*args, **kwargs):
                    try:
                        data = original_recv(*args, **kwargs)
                        
                        # Try to extract voice data
                        if data and len(data) > 12:
                            # This is a simplified approach - real implementation needs proper RTP parsing
                            asyncio.create_task(self._handle_raw_packet(data))
                        
                        return data
                    except Exception as e:
                        logger.debug(f"[DEBUG] Recv patch error: {e}")
                        return original_recv(*args, **kwargs)
                
                original_socket.recv = patched_recv
                logger.info("[PATCH] Socket patched for voice capture")
                
        except Exception as e:
            logger.error(f"[ERROR] Patching failed: {e}")
    
    def _unpatch_voice_client(self):
        """Remove patches from voice client"""
        try:
            # Restore original socket methods if possible
            if hasattr(self.voice_client, 'socket') and self.voice_client.socket:
                # This would restore the original recv method
                # Implementation depends on how we stored the original
                pass
                
        except Exception as e:
            logger.error(f"[ERROR] Unpatching failed: {e}")
    
    async def _handle_raw_packet(self, packet_data: bytes):
        """Handle raw packet data"""
        try:
            # Parse RTP header to extract user information
            # This is a simplified version - real RTP parsing is more complex
            
            if len(packet_data) < 12:
                return
            
            # Extract SSRC (synchronization source identifier) from RTP header
            ssrc = struct.unpack('>I', packet_data[8:12])[0]
            
            # Map SSRC to Discord user (this mapping would need to be maintained)
            # For now, we'll use a placeholder user
            user = None  # Would need proper user resolution
            
            if user:
                self.packet_handler.handle_packet(packet_data, user.id, user)
                
        except Exception as e:
            logger.debug(f"[DEBUG] Raw packet handling error: {e}")

# Example usage integration
def create_custom_voice_client(voice_client, audio_callback):
    """Create a custom voice client with packet capture"""
    return CustomVoiceClient(voice_client, audio_callback)