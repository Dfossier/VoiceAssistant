#!/usr/bin/env python3
"""
Enhanced WebSocket Handler with Smart Turn VAD Integration
Includes pipeline metrics and optimized audio processing
"""

import asyncio
import json
import base64
import logging
import websockets
from typing import Dict, Any, Optional, Set
import threading
import numpy as np
import io
import wave
import time
import uuid

from .smart_turn_vad import SmartTurnVAD
from .pipeline_metrics import pipeline_metrics, MetricsContext
from .vad_config import vad_config, VADTuner

logger = logging.getLogger(__name__)


class EnhancedAudioWebSocketHandler:
    """
    Enhanced WebSocket server with Smart Turn VAD and performance metrics
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8002):
        self.host = host
        self.port = port
        self.server = None
        self.is_running = False
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # Audio buffering with Smart Turn VAD
        self.audio_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Smart Turn VAD
        self.vad = SmartTurnVAD(
            confidence_threshold=vad_config.confidence_threshold,
            min_audio_length=vad_config.min_audio_length,
            sample_rate=vad_config.sample_rate,
            use_optimized=True
        )
        
        # VAD tuner for dynamic optimization
        self.vad_tuner = VADTuner(vad_config)
        
        # Import local models
        try:
            from .local_models import local_model_manager
            self.model_manager = local_model_manager
            logger.info("✅ Local model manager imported")
        except ImportError as e:
            logger.error(f"❌ Failed to import local models: {e}")
            self.model_manager = None
            
        # Import Claude Code integration
        try:
            from .claude_code_service import claude_code_integration
            self.claude_code = claude_code_integration
            logger.info("✅ Claude Code integration imported")
        except ImportError as e:
            logger.error(f"❌ Failed to import Claude Code service: {e}")
            self.claude_code = None
            
        # Import voice command processor
        try:
            from .voice_command_processor import voice_command_processor
            self.voice_commands = voice_command_processor
            logger.info("✅ Voice command processor imported")
        except ImportError as e:
            logger.error(f"❌ Failed to import voice command processor: {e}")
            self.voice_commands = None
    
    async def initialize(self):
        """Initialize all components"""
        # Initialize Smart Turn VAD
        logger.info("🔄 Initializing Smart Turn VAD...")
        vad_initialized = await self.vad.initialize()
        if vad_initialized:
            logger.info("✅ Smart Turn VAD initialized successfully")
        else:
            logger.error("❌ Failed to initialize Smart Turn VAD")
            
        # Initialize Claude Code integration
        if self.claude_code:
            logger.info("🔄 Initializing Claude Code integration...")
            claude_initialized = await self.claude_code.initialize()
            if claude_initialized:
                logger.info("✅ Claude Code integration initialized successfully")
            else:
                logger.warning("⚠️ Claude Code integration failed to initialize")
        
        # Ensure models are loaded
        models_loaded = await self.ensure_models_loaded()
        if not models_loaded:
            logger.error("❌ Failed to load required models")
            return False
        
        return True
    
    async def ensure_models_loaded(self):
        """Ensure STT, LLM, and TTS models are loaded"""
        if not self.model_manager:
            return False
        
        try:
            status = self.model_manager.get_model_status()
            
            # Load STT if needed
            if not status['stt']['loaded'] and not status['stt'].get('skipped', False):
                logger.info("📢 Loading STT model...")
                if not await self.model_manager.load_stt_model():
                    return False
            
            # Load LLM if needed
            if not status['llm']['loaded']:
                logger.info("🧠 Loading LLM model...")
                if not await self.model_manager.load_llm_model():
                    return False
            
            # Load TTS if needed
            if not status['tts']['loaded']:
                logger.info("🔊 Loading TTS model...")
                if not await self.model_manager.load_tts_model():
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Model loading error: {e}")
            return False
    
    def _is_valid_transcription(self, text: str) -> bool:
        """Check if transcription is valid and should be processed"""
        if not text or not isinstance(text, str):
            return False
            
        # Remove whitespace and check length
        cleaned = text.strip()
        if len(cleaned) < 2:  # Filter very short transcriptions
            return False
            
        # Filter common noise patterns (case insensitive)
        noise_patterns = [
            "um", "uh", "hmm", "ah", "oh", "eh", 
            "yeah", "yes", "no", "ok", "okay",
            "hello", "hi", "hey",  # Common echo patterns
            "thanks", "thank you",  # Short responses that might be echo
            "sure", "right", "good",
            ".", ",", "?", "!",  # Punctuation only
        ]
        
        if cleaned.lower() in noise_patterns:
            return False
            
        # Filter repetitive patterns (like "hello hello hello")
        words = cleaned.lower().split()
        if len(words) > 1 and len(set(words)) == 1:  # All words are the same
            return False
            
        return True
    
    async def start_server(self):
        """Start the enhanced WebSocket server"""
        try:
            # Initialize components first
            if not await self.initialize():
                logger.error("❌ Failed to initialize components")
                return
            
            logger.info(f"🚀 Starting enhanced audio WebSocket server on {self.host}:{self.port}")
            
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=10 * 1024 * 1024  # 10MB max message size
            )
            
            self.is_running = True
            logger.info(f"✅ Enhanced WebSocket server listening on ws://{self.host}:{self.port}")
            
            # Start metrics reporting task
            asyncio.create_task(self.periodic_metrics_report())
            
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            raise
    
    async def periodic_metrics_report(self):
        """Periodically report pipeline metrics"""
        while self.is_running:
            await asyncio.sleep(60)  # Report every minute
            pipeline_metrics.print_summary()
    
    async def handle_client(self, websocket, path):
        """Handle a WebSocket client connection with metrics"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"✅ New client connected: {client_id}")
        
        # Create session
        session_id = str(uuid.uuid4())
        self.audio_sessions[client_id] = {
            "session_id": session_id,
            "audio_buffer": bytearray(),
            "last_activity": time.time(),
            "total_audio_processed": 0,
            "turn_count": 0
        }
        
        # Add to connected clients
        self.connected_clients.add(websocket)
        
        try:
            # Send enhanced welcome message
            await self.send_welcome_message(websocket, session_id)
            
            # Handle messages
            async for message in websocket:
                await self.process_message(websocket, message, client_id)
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📴 Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_id}: {e}")
        finally:
            # Cleanup
            self.connected_clients.discard(websocket)
            if client_id in self.audio_sessions:
                session = self.audio_sessions.pop(client_id)
                # Complete any active trace
                if "trace_id" in session:
                    pipeline_metrics.complete_trace(session["trace_id"])
    
    async def send_welcome_message(self, websocket, session_id: str):
        """Send enhanced welcome message"""
        welcome = {
            "type": "welcome",
            "message": "Enhanced Audio WebSocket server with Smart Turn VAD",
            "session_id": session_id,
            "features": {
                "smart_turn_vad": True,
                "pipeline_metrics": True,
                "adaptive_tuning": True,
                "optimized_inference": True
            },
            "vad_config": {
                "confidence_threshold": self.vad.confidence_threshold,
                "min_audio_length": self.vad.min_audio_length,
                "model": "smart-turn-v3"
            },
            "supported_formats": ["wav", "pcm16"],
            "expected_sample_rate": 16000,
            "expected_channels": 1
        }
        await websocket.send(json.dumps(welcome))
    
    async def process_message(self, websocket, message: str, client_id: str):
        """Process incoming message with metrics tracking"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            # Start trace for this message
            trace_id = f"{client_id}_{time.time()}"
            trace = pipeline_metrics.start_trace(
                trace_id,
                client_id=client_id,
                message_type=message_type
            )
            
            # Store trace ID in session
            if client_id in self.audio_sessions:
                self.audio_sessions[client_id]["trace_id"] = trace_id
            
            logger.debug(f"📨 Received message type: {message_type}")
            
            if message_type == "audio_input":
                await self.process_audio_input_enhanced(websocket, data, client_id, trace_id)
            elif message_type == "ping":
                await self.send_pong(websocket)
            elif message_type == "start":
                await self.handle_session_start(websocket, client_id)
            elif message_type == "end":
                await self.handle_session_end(websocket, client_id)
            elif message_type == "get_metrics":
                await self.send_metrics(websocket)
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")
                await self.send_error(websocket, f"Unknown message type: {message_type}")
            
        except json.JSONDecodeError as e:
            await self.send_error(websocket, f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            await self.send_error(websocket, f"Processing error: {e}")
    
    async def process_audio_input_enhanced(self, websocket, data: Dict[str, Any], 
                                         client_id: str, trace_id: str):
        """Enhanced audio processing with Smart Turn VAD and metrics"""
        try:
            session = self.audio_sessions.get(client_id)
            if not session:
                await self.send_error(websocket, "No active session")
                return
            
            # Extract and decode audio
            with MetricsContext(trace_id, "audio", "decode") as ctx:
                audio_b64 = data.get("data", "")
                if not audio_b64:
                    await self.send_error(websocket, "Missing audio data")
                    return
                
                audio_data = base64.b64decode(audio_b64)
                logger.debug(f"🎵 Received audio: {len(audio_data)} bytes")
            
            # Get audio parameters
            sample_rate = data.get("sample_rate", 16000)
            channels = data.get("channels", 1)
            audio_format = data.get("format", "pcm")
            chunk_id = data.get("chunk_id", "unknown")
            
            # Convert format if needed
            if audio_format == "wav":
                with MetricsContext(trace_id, "audio", "wav_conversion"):
                    audio_data = await self.wav_to_pcm(audio_data)
            
            # Add to VAD buffer
            with MetricsContext(trace_id, "vad", "buffer_processing"):
                buffer_ready = self.vad.add_audio_chunk(audio_data)
                session["audio_buffer"].extend(audio_data)
                session["total_audio_processed"] += len(audio_data)
            
            # Check for turn end if buffer is ready
            if buffer_ready:
                with MetricsContext(trace_id, "vad", "inference") as vad_ctx:
                    is_turn_end, confidence, vad_metadata = await self.vad.detect_turn_end()
                    
                    # Record for tuning
                    self.vad_tuner.record_detection(
                        was_correct=True,  # We'll validate this later
                        confidence=confidence,
                        latency_ms=vad_metadata.get("inference_time_ms", 0),
                        audio_duration_ms=len(session["audio_buffer"]) / (sample_rate * 2) * 1000
                    )
                
                if is_turn_end:
                    logger.info(f"🎯 Turn end detected! Confidence: {confidence:.2f}")
                    session["turn_count"] += 1
                    
                    # Process the complete utterance
                    await self.process_complete_utterance(
                        websocket, session["audio_buffer"], 
                        sample_rate, client_id, trace_id
                    )
                    
                    # Clear buffer for next turn
                    session["audio_buffer"] = bytearray()
                else:
                    # Send intermediate status
                    await self.send_vad_status(websocket, False, confidence, vad_metadata)
            else:
                # Not enough audio yet
                buffer_duration = len(session["audio_buffer"]) / (sample_rate * 2)
                await self.send_vad_status(websocket, False, 0.0, {
                    "waiting": True,
                    "buffer_duration": buffer_duration,
                    "min_required": self.vad.min_audio_length
                })
            
            # Update last activity
            session["last_activity"] = time.time()
            
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}")
            await self.send_error(websocket, f"Audio processing failed: {e}")
    
    async def process_complete_utterance(self, websocket, audio_buffer: bytearray, 
                                       sample_rate: int, client_id: str, trace_id: str):
        """Process a complete utterance through STT → LLM → TTS pipeline"""
        try:
            # Convert buffer to proper format
            audio_array = np.frombuffer(audio_buffer, dtype=np.int16)
            
            # STT Processing
            with MetricsContext(trace_id, "stt", "transcription"):
                transcription = await self.transcribe_audio(audio_array, sample_rate)
                
            if not transcription:
                await self.send_error(websocket, "Transcription failed")
                return
            
            # Filter empty or minimal transcriptions to prevent processing noise/echo
            if not self._is_valid_transcription(transcription):
                logger.debug(f"🔇 Filtered transcription (too short/empty): '{transcription}'")
                return
            
            logger.info(f"📝 Transcription: {transcription}")
            
            # Send transcription event
            await self.send_transcription(websocket, transcription)
            
            # LLM Processing
            with MetricsContext(trace_id, "llm", "generation"):
                response = await self.generate_response(transcription, client_id)
            
            if not response:
                await self.send_error(websocket, "Response generation failed")
                return
            
            logger.info(f"💬 Response: {response}")
            
            # TTS Processing
            with MetricsContext(trace_id, "tts", "synthesis"):
                audio_response = await self.synthesize_speech(response)
            
            if audio_response:
                # Send audio response
                with MetricsContext(trace_id, "websocket", "send"):
                    await self.send_audio_response(websocket, audio_response)
            
            # Complete the trace
            pipeline_metrics.complete_trace(trace_id)
            
            # Log end-to-end metrics
            trace = pipeline_metrics.get_trace(trace_id)
            if trace and trace.total_duration_ms:
                logger.info(f"⏱️ End-to-end latency: {trace.total_duration_ms:.1f}ms")
                
        except Exception as e:
            logger.error(f"❌ Utterance processing error: {e}")
            await self.send_error(websocket, f"Processing failed: {e}")
    
    async def transcribe_audio(self, audio_array: np.ndarray, sample_rate: int) -> Optional[str]:
        """Transcribe audio using STT model"""
        if not self.model_manager:
            return None
        
        try:
            # Convert to bytes for the model
            audio_bytes = audio_array.tobytes()
            
            # Use local STT model (it's already async)
            result = await self.model_manager.transcribe_audio(
                audio_bytes,
                sample_rate
            )
            
            return result.strip() if result else None
            
        except Exception as e:
            logger.error(f"❌ STT error: {e}")
            return None
    
    async def generate_response(self, text: str, client_id: str) -> Optional[str]:
        """Generate response using LLM with Claude Code context awareness"""
        if not self.model_manager:
            return None
        
        try:
            # Check if this is a development-related query
            dev_keywords = [
                "code", "debug", "error", "file", "terminal", "command", "run", "fix", 
                "edit", "python", "javascript", "npm", "git", "test", "build",
                "function", "variable", "class", "method", "syntax", "import"
            ]
            
            is_dev_query = any(keyword in text.lower() for keyword in dev_keywords)
            
            # Get Claude Code context if available and relevant
            claude_context = ""
            if self.claude_code and is_dev_query:
                try:
                    context_data = await self.claude_code.get_context_for_llm()
                    if not context_data.get("error"):
                        dev_ctx = context_data.get("development_context", {})
                        recent_activity = context_data.get("recent_activity", [])
                        
                        # Build context summary
                        context_parts = []
                        
                        if dev_ctx.get("current_files"):
                            files = ", ".join(dev_ctx["current_files"][-3:])  # Last 3 files
                            context_parts.append(f"Recent files: {files}")
                            
                        if dev_ctx.get("recent_commands"):
                            commands = ", ".join(dev_ctx["recent_commands"][-2:])  # Last 2 commands
                            context_parts.append(f"Recent commands: {commands}")
                            
                        if dev_ctx.get("active_errors"):
                            errors = "; ".join(dev_ctx["active_errors"][-1:])  # Last error
                            context_parts.append(f"Recent error: {errors}")
                            
                        if context_parts:
                            claude_context = f"\n\nDevelopment context: {' | '.join(context_parts)}"
                            
                except Exception as e:
                    logger.debug(f"Failed to get Claude Code context: {e}")
            
            # Enhanced system prompt with development awareness
            if is_dev_query and claude_context:
                system_message = (
                    "You are a development assistant with access to the user's Claude Code session. "
                    "Provide brief, helpful responses about coding, debugging, and development tasks. "
                    f"Current context: {claude_context.strip()}"
                )
            else:
                system_message = "Voice assistant. Brief, natural responses. Max 2 sentences."
            
            # First check for structured voice commands
            if self.voice_commands:
                voice_command = await self.voice_commands.process_voice_input(text)
                if voice_command and voice_command.confidence > 0.7:
                    result = await self._handle_voice_command(voice_command)
                    return result
            
            # Fallback to simple terminal interaction checks
            terminal_action = await self._check_terminal_request(text)
            if terminal_action:
                result = await self._handle_terminal_action(terminal_action)
                return result
            
            # Generate response using LLM
            response = await self.model_manager.generate_response(text, system_message)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ LLM error: {e}")
            return None
    
    async def _check_terminal_request(self, text: str) -> Optional[Dict[str, str]]:
        """Check if the user is requesting terminal interaction"""
        text_lower = text.lower()
        
        # Terminal command patterns
        if any(phrase in text_lower for phrase in [
            "run command", "execute", "type in terminal", "send to terminal",
            "run in terminal", "terminal command"
        ]):
            # Extract command from text
            for trigger in ["run", "execute", "type"]:
                if trigger in text_lower:
                    parts = text_lower.split(trigger, 1)
                    if len(parts) > 1:
                        command = parts[1].strip()
                        # Clean up command
                        command = command.replace("in terminal", "").replace("in the terminal", "").strip()
                        if command:
                            return {"action": "send_command", "command": command}
        
        # Text addition patterns
        if any(phrase in text_lower for phrase in [
            "add text", "type", "write in terminal", "input"
        ]):
            # Extract text to add
            for trigger in ["add", "type", "write", "input"]:
                if trigger in text_lower:
                    parts = text_lower.split(trigger, 1)
                    if len(parts) > 1:
                        text_to_add = parts[1].strip()
                        text_to_add = text_to_add.replace("in terminal", "").replace("in the terminal", "").strip()
                        if text_to_add:
                            return {"action": "add_text", "text": text_to_add}
        
        return None
    
    async def _handle_terminal_action(self, action: Dict[str, str]) -> str:
        """Handle terminal interaction requests"""
        if not self.claude_code:
            return "Terminal interaction not available - Claude Code integration not initialized."
        
        try:
            result = await self.claude_code.process_llm_terminal_request(**action)
            
            if result.get("success"):
                action_type = result.get("action")
                if action_type == "send_command":
                    command = result.get("command")
                    return f"Executed command: {command}"
                elif action_type == "add_text":
                    text = result.get("text")
                    return f"Added text to terminal: {text[:50]}..."
                elif action_type == "get_output":
                    output = result.get("output", "")
                    return f"Terminal output: {output[-200:]}"  # Last 200 chars
                else:
                    return "Terminal action completed successfully."
            else:
                error = result.get("error", "Unknown error")
                return f"Terminal action failed: {error}"
                
        except Exception as e:
            logger.error(f"❌ Terminal action error: {e}")
            return f"Error executing terminal action: {e}"
    
    async def _handle_voice_command(self, command) -> str:
        """Handle structured voice commands"""
        try:
            action = command.action
            params = command.parameters
            
            logger.info(f"🎤 Processing voice command: {action} with params: {params}")
            
            # Terminal commands
            if action == "send_command":
                if "command" in params:
                    cmd = params["command"]
                    # Safety check
                    if self.voice_commands:
                        safe, warning = self.voice_commands.check_safety(cmd)
                        if not safe:
                            return f"❌ Unsafe command blocked: {warning}"
                        elif warning:
                            return f"⚠️ {warning}. Say 'confirm' to proceed."
                    
                    if self.claude_code:
                        result = await self.claude_code.process_llm_terminal_request(
                            action="send_command", command=cmd
                        )
                        if result.get("success"):
                            return self.voice_commands.format_response(
                                "command_executed", command=cmd
                            ) if self.voice_commands else f"✅ Executed: {cmd}"
                        else:
                            return f"❌ Command failed: {result.get('error', 'Unknown error')}"
                    else:
                        return "❌ Terminal integration not available"
                        
            elif action == "add_text":
                if "text" in params:
                    text = params["text"]
                    if self.claude_code:
                        result = await self.claude_code.process_llm_terminal_request(
                            action="add_text", text=text
                        )
                        if result.get("success"):
                            return self.voice_commands.format_response(
                                "text_added", text=text[:50]
                            ) if self.voice_commands else f"📝 Added: {text[:50]}..."
                        else:
                            return f"❌ Failed to add text: {result.get('error', 'Unknown error')}"
                    else:
                        return "❌ Terminal integration not available"
                        
            elif action == "get_output":
                if self.claude_code:
                    result = await self.claude_code.process_llm_terminal_request(action="get_output")
                    if result.get("success"):
                        output = result.get("output", "")
                        return f"📺 Terminal output: {output[-200:]}" if output else "📺 No recent terminal output"
                    else:
                        return f"❌ Failed to get output: {result.get('error', 'Unknown error')}"
                else:
                    return "❌ Terminal integration not available"
                    
            elif action == "debug_assistance":
                # Get current development context
                if self.claude_code:
                    context_data = await self.claude_code.get_context_for_llm()
                    if not context_data.get("error"):
                        dev_ctx = context_data.get("development_context", {})
                        errors = dev_ctx.get("active_errors", [])
                        
                        if errors:
                            error_summary = "; ".join(errors[-2:])  # Last 2 errors
                            return f"🐛 Recent errors found: {error_summary}. I can help analyze these issues."
                        else:
                            return "✅ No recent errors detected in your development session."
                    else:
                        return "❌ Unable to access development context"
                else:
                    return "❌ Development context not available"
                    
            elif action == "project_summary":
                if self.claude_code:
                    context_data = await self.claude_code.get_context_for_llm()
                    if not context_data.get("error"):
                        dev_ctx = context_data.get("development_context", {})
                        summary = dev_ctx.get("project_summary", "")
                        files = dev_ctx.get("current_files", [])
                        commands = dev_ctx.get("recent_commands", [])
                        
                        response_parts = []
                        if summary:
                            response_parts.append(summary)
                        if files:
                            response_parts.append(f"Recent files: {', '.join(files[-3:])}")
                        if commands:
                            response_parts.append(f"Recent commands: {', '.join(commands[-2:])}")
                            
                        return " | ".join(response_parts) if response_parts else "No recent development activity"
                    else:
                        return "❌ Unable to access project information"
                else:
                    return "❌ Project analysis not available"
                    
            elif action == "run_tests":
                test_cmd = "npm test"  # Default test command
                if "test_spec" in params:
                    test_cmd = f"npm test {params['test_spec']}"
                    
                if self.claude_code:
                    result = await self.claude_code.process_llm_terminal_request(
                        action="send_command", command=test_cmd
                    )
                    if result.get("success"):
                        return f"🧪 Running tests: {test_cmd}"
                    else:
                        return f"❌ Failed to run tests: {result.get('error', 'Unknown error')}"
                else:
                    return "❌ Cannot run tests - terminal integration not available"
                    
            elif action == "git_status":
                if self.claude_code:
                    result = await self.claude_code.process_llm_terminal_request(
                        action="send_command", command="git status"
                    )
                    if result.get("success"):
                        return "📝 Checking git status..."
                    else:
                        return f"❌ Failed to check git status: {result.get('error', 'Unknown error')}"
                else:
                    return "❌ Cannot check git - terminal integration not available"
                    
            else:
                return f"❓ Unknown voice command action: {action}"
                
        except Exception as e:
            logger.error(f"❌ Voice command error: {e}")
            return f"Error processing voice command: {e}"
    
    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """Synthesize speech using TTS"""
        if not self.model_manager:
            return None
        
        try:
            # Synthesize audio (check if it's async)
            synthesize_method = self.model_manager.synthesize_speech
            if asyncio.iscoroutinefunction(synthesize_method):
                audio_data = await synthesize_method(text)
            else:
                audio_data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    synthesize_method,
                    text
                )
            
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return None
    
    async def send_vad_status(self, websocket, is_turn_end: bool, 
                            confidence: float, metadata: Dict[str, Any]):
        """Send VAD status update"""
        status = {
            "type": "vad_status",
            "is_turn_end": is_turn_end,
            "confidence": confidence,
            "metadata": metadata,
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(status))
    
    async def send_transcription(self, websocket, text: str):
        """Send transcription result"""
        result = {
            "type": "transcription",
            "text": text,
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(result))
    
    async def send_audio_response(self, websocket, audio_data: bytes):
        """Send audio response"""
        # Encode audio as base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        response = {
            "type": "audio_output",
            "data": audio_b64,
            "format": "pcm16",
            "sample_rate": 22050,  # Kokoro TTS actual output rate
            "channels": 1,
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(response))
    
    async def send_metrics(self, websocket):
        """Send current metrics to client"""
        stats = pipeline_metrics.get_statistics()
        tuning_report = self.vad_tuner.get_tuning_report()
        
        metrics_response = {
            "type": "metrics",
            "pipeline_stats": stats,
            "vad_tuning": tuning_report,
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(metrics_response))
    
    async def send_error(self, websocket, error_message: str):
        """Send error message"""
        error = {
            "type": "error",
            "error": error_message,
            "timestamp": time.time()
        }
        try:
            await websocket.send(json.dumps(error))
        except:
            pass
    
    async def send_pong(self, websocket):
        """Send pong response"""
        pong = {
            "type": "pong",
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(pong))
    
    async def handle_session_start(self, websocket, client_id: str):
        """Handle session start"""
        session = self.audio_sessions.get(client_id)
        if session:
            session["audio_buffer"] = bytearray()
            session["last_activity"] = time.time()
        
        ack = {
            "type": "session_started",
            "vad_config": {
                "model": "smart-turn-v3",
                "confidence_threshold": self.vad.confidence_threshold,
                "min_audio_length": self.vad.min_audio_length
            },
            "timestamp": time.time()
        }
        await websocket.send(json.dumps(ack))
    
    async def handle_session_end(self, websocket, client_id: str):
        """Handle session end"""
        session = self.audio_sessions.get(client_id)
        if session:
            # Process any remaining audio
            if session["audio_buffer"]:
                await self.vad.detect_turn_end(force_analysis=True)
            
            # Send session summary
            summary = {
                "type": "session_ended",
                "summary": {
                    "total_audio_processed": session["total_audio_processed"],
                    "turn_count": session["turn_count"],
                    "duration": time.time() - session.get("start_time", time.time())
                },
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(summary))
    
    async def wav_to_pcm(self, wav_data: bytes) -> Optional[bytes]:
        """Convert WAV to raw PCM"""
        try:
            with io.BytesIO(wav_data) as wav_buffer:
                with wave.open(wav_buffer, 'rb') as wav_file:
                    return wav_file.readframes(wav_file.getnframes())
        except Exception as e:
            logger.error(f"WAV conversion error: {e}")
            return None
    
    async def stop_server(self):
        """Stop the server gracefully"""
        self.is_running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Print final metrics
        pipeline_metrics.print_summary()
        
        logger.info("🛑 Enhanced WebSocket server stopped")