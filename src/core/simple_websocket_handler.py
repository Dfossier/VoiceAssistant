#!/usr/bin/env python3
"""
Simple WebSocket Handler for Audio Processing

Handles JSON-formatted audio data from Discord bot without requiring
full Pipecat pipeline. Processes audio through local STT and provides
responses via TTS.
"""

import asyncio
import json
import base64
import logging
import websockets
from typing import Dict, Any, Optional
import threading
import numpy as np
import io
import wave

logger = logging.getLogger(__name__)

class SimpleAudioWebSocketHandler:
    """
    Simple WebSocket server for handling JSON audio data from Discord bot
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8002):
        self.host = host
        self.port = port
        self.server = None
        self.is_running = False
        self.connected_clients = set()
        
        # Audio buffering for better STT
        self.audio_buffers = {}  # client_id -> audio buffer
        
        # Import local models and initialize them
        try:
            from .local_models import local_model_manager
            self.model_manager = local_model_manager
            logger.info("✅ Local model manager imported")
        except ImportError as e:
            logger.error(f"❌ Failed to import local models: {e}")
            self.model_manager = None
            
    async def ensure_models_loaded(self):
        """Ensure STT and LLM models are loaded"""
        if not self.model_manager:
            return False
            
        try:
            # Check model status (sync call)
            status = self.model_manager.get_model_status()
            
            # Check if STT is skipped
            if status['stt'].get('skipped', False):
                logger.info("⏭️  STT model is skipped - using Pipecat's Whisper instead")
            else:
                # Load STT model if not loaded
                if not status['stt']['loaded']:
                    logger.info("📢 Loading STT model...")
                    stt_loaded = await self.model_manager.load_stt_model()
                    if stt_loaded:
                        logger.info("✅ STT model loaded successfully")
                    else:
                        logger.error("❌ Failed to load STT model")
                        return False
            
            # Load LLM model if not loaded  
            if not status['llm']['loaded']:
                logger.info("🧠 Loading LLM model...")
                llm_loaded = await self.model_manager.load_llm_model()
                if llm_loaded:
                    logger.info("✅ LLM model loaded successfully")
                else:
                    logger.error("❌ Failed to load LLM model")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Model loading error: {e}")
            return False
    
    async def start_server(self):
        """Start the WebSocket server"""
        try:
            logger.info(f"🚀 Starting simple audio WebSocket server on {self.host}:{self.port}")
            
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_running = True
            logger.info(f"✅ WebSocket server listening on ws://{self.host}:{self.port}")
            logger.info("🎤 Ready to receive JSON audio data from Discord bot")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            return False
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        try:
            self.is_running = False
            if self.server:
                self.server.close()
                await self.server.wait_closed()
                logger.info("✅ WebSocket server stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping server: {e}")
    
    async def handle_client(self, websocket, path):
        """Handle individual client connections"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔌 Client connected: {client_id}")
        
        self.connected_clients.add(websocket)
        
        try:
            await self.send_welcome_message(websocket)
            
            async for message in websocket:
                try:
                    await self.process_message(websocket, message)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON from {client_id}: {e}")
                    await self.send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.error(f"❌ Error processing message from {client_id}: {e}")
                    await self.send_error(websocket, str(e))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"❌ Client error {client_id}: {e}")
        finally:
            self.connected_clients.discard(websocket)
            # Clean up audio buffer for this client
            if client_id in self.audio_buffers:
                del self.audio_buffers[client_id]
    
    async def send_welcome_message(self, websocket):
        """Send welcome message to connected client"""
        welcome = {
            "type": "welcome",
            "message": "Simple Audio WebSocket server ready",
            "supported_formats": ["wav", "pcm16"],
            "expected_sample_rate": 16000,
            "expected_channels": 1,
            "audio_format": "base64_encoded"
        }
        await websocket.send(json.dumps(welcome))
    
    async def send_error(self, websocket, error_message: str):
        """Send error message to client"""
        error = {
            "type": "error",
            "error": error_message,
            "timestamp": asyncio.get_event_loop().time()
        }
        try:
            await websocket.send(json.dumps(error))
        except:
            pass  # Client might be disconnected
    
    async def process_message(self, websocket, message: str):
        """Process incoming JSON message"""
        data = json.loads(message)
        message_type = data.get("type")
        
        logger.debug(f"📨 Received message type: {message_type}")
        
        if message_type == "audio_input":
            await self.process_audio_input(websocket, data)
        elif message_type == "ping":
            await self.send_pong(websocket)
        elif message_type == "start":
            logger.info("📤 Received start message - ready for audio")
            await self.send_ack(websocket, "Session started")
        elif message_type == "end":
            logger.info("📤 Received end message - session ended")
            await self.send_ack(websocket, "Session ended")
        else:
            logger.warning(f"⚠️ Unknown message type: {message_type}")
            await self.send_error(websocket, f"Unknown message type: {message_type}")
    
    async def send_pong(self, websocket):
        """Respond to ping"""
        pong = {
            "type": "pong",
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send(json.dumps(pong))
    
    async def send_ack(self, websocket, message: str):
        """Send acknowledgment message"""
        ack = {
            "type": "ack",
            "message": message,
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send(json.dumps(ack))
    
    async def process_audio_input(self, websocket, data: Dict[str, Any]):
        """Process audio input from Discord bot"""
        try:
            # Get client identifier
            client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            
            # Extract audio data
            audio_b64 = data.get("data", "")
            if not audio_b64:
                await self.send_error(websocket, "Missing audio data")
                return
            
            # Decode base64 audio
            try:
                audio_data = base64.b64decode(audio_b64)
                logger.debug(f"🎵 Received audio: {len(audio_data)} bytes")
            except Exception as e:
                await self.send_error(websocket, f"Failed to decode audio: {e}")
                return
            
            # Get audio parameters
            sample_rate = data.get("sample_rate", 16000)
            channels = data.get("channels", 1)
            audio_format = data.get("format", "wav")
            chunk_id = data.get("chunk_id", "unknown")
            
            logger.info(f"🎤 Processing audio chunk #{chunk_id}: {sample_rate}Hz, {channels}ch, {audio_format}")
            
            # Handle different audio formats
            if audio_format == "wav":
                audio_data = await self.wav_to_pcm(audio_data)
                if not audio_data:
                    await self.send_error(websocket, "Failed to convert WAV to PCM")
                    return
            elif audio_format == "pcm":
                # Discord bot sends raw PCM - validate and potentially fix format
                logger.debug(f"📡 Raw PCM audio: {len(audio_data)} bytes")
                
                # Validate audio size (should be multiple of 2 for 16-bit samples)
                if len(audio_data) % 2 != 0:
                    logger.warning(f"⚠️ Audio data size {len(audio_data)} is not even - truncating")
                    audio_data = audio_data[:-1]
                
                # Calculate expected duration
                samples = len(audio_data) // 2  # 16-bit = 2 bytes per sample
                duration_ms = (samples / sample_rate) * 1000
                logger.debug(f"📊 Audio info: {samples} samples, {duration_ms:.1f}ms duration")
                
                # Check if this is likely silence/noise (very low amplitude)
                import struct
                try:
                    # Convert to numpy array to check amplitude
                    samples_array = np.frombuffer(audio_data, dtype=np.int16)
                    max_amplitude = np.max(np.abs(samples_array))
                    rms = np.sqrt(np.mean(samples_array.astype(np.float32) ** 2))
                    
                    logger.debug(f"📊 Audio stats: max_amp={max_amplitude}, rms={rms:.1f}")
                    
                    # Skip processing if audio is too quiet (likely silence)
                    if max_amplitude < 100 or rms < 50:
                        logger.debug(f"🔇 Skipping silent audio chunk (max={max_amplitude}, rms={rms:.1f})")
                        return
                        
                except Exception as e:
                    logger.warning(f"⚠️ Audio analysis failed: {e}")
            
            # Buffer audio for better transcription
            if client_id not in self.audio_buffers:
                self.audio_buffers[client_id] = {
                    'buffer': bytearray(),
                    'last_activity': asyncio.get_event_loop().time(),
                    'sample_rate': sample_rate
                }
            
            buffer_info = self.audio_buffers[client_id]
            buffer_info['buffer'].extend(audio_data)
            buffer_info['last_activity'] = asyncio.get_event_loop().time()
            
            # Process when buffer reaches ~2 seconds of audio or after silence
            buffer_size = len(buffer_info['buffer'])
            target_size = sample_rate * 2 * 2  # 2 seconds of 16-bit mono
            time_since_last = asyncio.get_event_loop().time() - buffer_info['last_activity']
            
            should_process = (
                buffer_size >= target_size or  # Buffer is full
                (buffer_size > sample_rate and time_since_last > 1.0)  # 1+ second and 1s silence
            )
            
            if not should_process:
                logger.debug(f"📦 Buffering audio: {buffer_size}/{target_size} bytes")
                return
            
            # Use buffered audio for transcription
            buffered_audio = bytes(buffer_info['buffer'])
            buffer_info['buffer'] = bytearray()  # Clear buffer
            
            logger.info(f"🎤 Processing buffered audio: {len(buffered_audio)} bytes ({len(buffered_audio)/(sample_rate*2):.1f}s)")
            
            # Send to STT for transcription
            if self.model_manager:
                transcription = await self.transcribe_audio(buffered_audio, sample_rate)
                
                # Check if STT is skipped
                status = self.model_manager.get_model_status()
                is_stt_skipped = status['stt'].get('skipped', False)
                
                if transcription and transcription.strip():
                    logger.info(f"🗣️ Transcribed: {transcription}")
                    
                    # Send transcription back to client
                    response = {
                        "type": "transcription",
                        "text": transcription,
                        "chunk_id": chunk_id,
                        "confidence": 1.0,  # Placeholder
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await websocket.send(json.dumps(response))
                    
                    # Generate AI response for successful transcription
                    logger.info(f"🔄 Generating AI response for: {transcription[:50]}...")
                    ai_response = await self.generate_ai_response(transcription)
                    if ai_response:
                        logger.info(f"🤖 AI response: {ai_response[:100]}...")
                        
                        # Send text response
                        text_response = {
                            "type": "text_output", 
                            "text": ai_response,
                            "chunk_id": chunk_id,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        await websocket.send(json.dumps(text_response))
                        
                        # Generate TTS audio response
                        logger.info("🔊 Generating TTS audio response...")
                        audio_response = await self.generate_tts_audio(ai_response)
                        if audio_response:
                            logger.info(f"✅ Generated {len(audio_response)} bytes of TTS audio")
                            
                            # Convert PCM to WAV format
                            wav_audio = await self.pcm_to_wav(audio_response, sample_rate=24000)
                            if wav_audio:
                                # Send audio response  
                                audio_msg = {
                                    "type": "audio_output",
                                    "data": base64.b64encode(wav_audio).decode('utf-8'),
                                    "format": "wav",
                                    "chunk_id": chunk_id,
                                    "timestamp": asyncio.get_event_loop().time()
                                }
                                await websocket.send(json.dumps(audio_msg))
                            else:
                                logger.warning("⚠️ Failed to convert TTS audio to WAV")
                        else:
                            logger.warning("⚠️ TTS audio generation failed")
                    else:
                        logger.warning("⚠️ AI response generation failed")
                        
                elif is_stt_skipped and len(buffered_audio) > 1000:
                    # If STT is skipped but we have audio, acknowledge it
                    logger.info("🎤 Audio received - STT is disabled, using fallback response")
                    
                    # Send a placeholder transcription
                    response = {
                        "type": "transcription",
                        "text": "[Audio received - STT disabled]",
                        "chunk_id": chunk_id,
                        "confidence": 0.5,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await websocket.send(json.dumps(response))
                    
                    # Set a default transcription for AI response
                    transcription = "Hello, I can hear you but speech recognition is currently disabled. Please use port 8001 for full voice capabilities with Whisper STT."
                    
                    # Generate AI response
                    ai_response = await self.generate_ai_response(transcription)
                    if ai_response:
                        logger.info(f"🤖 AI response: {ai_response[:100]}...")
                        
                        # Send text response
                        text_response = {
                            "type": "text_output", 
                            "text": ai_response,
                            "chunk_id": chunk_id,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        await websocket.send(json.dumps(text_response))
                        
                        # Generate TTS audio
                        audio_response = await self.generate_tts_audio(ai_response)
                        if audio_response:
                            logger.info(f"🔊 Generated TTS audio: {len(audio_response)} bytes")
                            
                            # Convert PCM to WAV format
                            wav_audio = await self.pcm_to_wav(audio_response, sample_rate=24000)
                            if wav_audio:
                                # Send audio response
                                audio_msg = {
                                    "type": "audio_output",
                                    "data": base64.b64encode(wav_audio).decode('utf-8'),
                                    "format": "wav",
                                    "chunk_id": chunk_id,
                                    "timestamp": asyncio.get_event_loop().time()
                                }
                                await websocket.send(json.dumps(audio_msg))
                            else:
                                logger.warning("⚠️ Failed to convert TTS audio to WAV")
                        else:
                            logger.warning("⚠️ TTS generation failed")
                else:
                    logger.debug(f"🔇 No speech detected in chunk #{chunk_id}")
            else:
                await self.send_error(websocket, "Model manager not available")
                
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}")
            await self.send_error(websocket, f"Audio processing failed: {e}")
    
    async def wav_to_pcm(self, wav_data: bytes) -> Optional[bytes]:
        """Convert WAV data to raw PCM"""
        try:
            # Use BytesIO to read WAV data
            wav_io = io.BytesIO(wav_data)
            
            with wave.open(wav_io, 'rb') as wav_file:
                # Read all frames
                frames = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                
                logger.debug(f"WAV info: {sample_rate}Hz, {channels}ch, {len(frames)} bytes")
                return frames
                
        except Exception as e:
            logger.error(f"❌ WAV conversion error: {e}")
            return None
    
    async def pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> Optional[bytes]:
        """Convert raw PCM data to WAV format"""
        try:
            # Create a BytesIO buffer for WAV output
            wav_buffer = io.BytesIO()
            
            # Open WAV file for writing
            with wave.open(wav_buffer, 'wb') as wav_file:
                # Set WAV parameters
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit audio
                wav_file.setframerate(sample_rate)
                
                # Write PCM data
                wav_file.writeframes(pcm_data)
            
            # Get WAV data from buffer
            wav_data = wav_buffer.getvalue()
            logger.debug(f"📦 Created WAV: {len(wav_data)} bytes from {len(pcm_data)} bytes PCM")
            return wav_data
            
        except Exception as e:
            logger.error(f"❌ PCM to WAV conversion error: {e}")
            return None
    
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int) -> Optional[str]:
        """Transcribe audio using local STT model or fallback"""
        try:
            if not self.model_manager:
                return None
            
            # Check if STT is skipped
            status = self.model_manager.get_model_status()
            if status['stt'].get('skipped', False):
                logger.info("⏭️  STT skipped - using simple fallback response")
                # Since we don't have STT, just return a simple response
                # In production, this should use Pipecat's Whisper
                return None  # Return None to skip transcription
            
            # Ensure models are loaded before transcription
            models_ready = await self.ensure_models_loaded()
            if not models_ready:
                logger.error("❌ Models not ready for transcription")
                return None
            
            # The local model manager expects bytes directly
            # Check if transcribe_audio is async
            transcribe_func = self.model_manager.transcribe_audio
            if asyncio.iscoroutinefunction(transcribe_func):
                # Call directly if async
                transcription = await transcribe_func(audio_data, sample_rate)
            else:
                # Run in thread pool if sync
                loop = asyncio.get_event_loop()
                transcription = await loop.run_in_executor(
                    None,
                    transcribe_func,
                    audio_data,
                    sample_rate
                )
            
            return transcription
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return None
    
    async def generate_ai_response(self, text: str) -> Optional[str]:
        """Generate AI response using local LLM"""
        try:
            if not self.model_manager:
                return None
            
            # Create user message and system prompt for voice conversation
            user_message = text.strip()
            system_prompt = "You are a helpful AI assistant in a voice conversation. Keep responses brief, conversational, and helpful. Respond in 1-2 sentences maximum."
            
            logger.info(f"🧠 Generating response for: '{user_message}'")
            
            # Check if generate_response is async
            generate_func = self.model_manager.generate_response
            if asyncio.iscoroutinefunction(generate_func):
                # Call directly if async with correct parameters
                response = await generate_func(user_message, system_prompt)
            else:
                # Run in thread pool if sync
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    generate_func,
                    user_message,
                    system_prompt
                )
            
            if response and not response.startswith("Error"):
                logger.info(f"✅ Generated response: '{response[:50]}...'")
                return response
            else:
                logger.warning(f"⚠️ LLM returned error or empty response: {response}")
                return None
            
        except Exception as e:
            logger.error(f"❌ AI response error: {e}")
            return None

    async def generate_tts_audio(self, text: str) -> Optional[bytes]:
        """Generate TTS audio using local TTS model"""
        try:
            if not self.model_manager:
                return None
            
            logger.info(f"🔊 Generating TTS for: '{text[:50]}...'")
            
            # Check if synthesize_speech is async
            synthesize_func = self.model_manager.synthesize_speech
            if asyncio.iscoroutinefunction(synthesize_func):
                # Call directly if async
                audio_data = await synthesize_func(text, "default")
            else:
                # Run in thread pool if sync
                loop = asyncio.get_event_loop()
                audio_data = await loop.run_in_executor(
                    None,
                    synthesize_func,
                    text,
                    "default"
                )
            
            if audio_data and len(audio_data) > 0:
                logger.info(f"✅ TTS generated: {len(audio_data)} bytes")
                return audio_data
            else:
                logger.warning("⚠️ TTS returned empty audio")
                return None
                
        except Exception as e:
            logger.error(f"❌ TTS generation error: {e}")
            return None

# Global instance
simple_audio_handler = SimpleAudioWebSocketHandler()

async def start_simple_audio_server():
    """Start the simple audio WebSocket server"""
    return await simple_audio_handler.start_server()

async def stop_simple_audio_server():
    """Stop the simple audio WebSocket server"""
    await simple_audio_handler.stop_server()