"""FastAPI server setup and configuration"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn

from .config import Settings
from .llm_handler import LLMHandler
from .file_monitor import FileMonitor
from .command_executor import CommandExecutor
from .local_models import local_model_manager

# Import utils with try/except for flexible import
try:
    from utils.websocket_manager import WebSocketManager
except ImportError:
    try:
        from ..utils.websocket_manager import WebSocketManager
    except ImportError:
        from src.utils.websocket_manager import WebSocketManager


# Global components
ws_manager = WebSocketManager()
llm_handler = None
file_monitor = None
command_executor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global llm_handler, file_monitor, command_executor
    
    logger.info("Starting up Local AI Assistant...")
    
    # Get settings from app state
    settings = app.state.settings
    
    try:
        # Import local model manager first
        from core.local_models import local_model_manager
        
        # Initialize local models with proper error handling
        logger.info("🚀 Initializing local model manager with eager loading...")
        try:
            await local_model_manager.initialize()
            logger.info("✅ Local model manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing local model manager: {e}")
            logger.info("⚠️ Continuing without local models - API fallbacks will be used")
        
        # Check which models were successfully loaded
        model_status = local_model_manager.get_model_status()
        logger.info("📊 Model loading status:")
        logger.info(f"   STT: {'✅' if model_status['stt']['loaded'] else '❌'} ({model_status['stt']['model']})")
        logger.info(f"   LLM: {'✅' if model_status['llm']['loaded'] else '❌'} (phi3_mini)")
        logger.info(f"   TTS: {'✅' if model_status['tts']['loaded'] else '❌'} (kokoro_tts)")
        
        # Initialize LLM handler (for fallback to API if needed)
        logger.info("Initializing LLM handler...")
        try:
            llm_handler = LLMHandler()
            logger.info("✅ LLM handler initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing LLM handler: {e}")
            llm_handler = None
        
        # Initialize command executor
        logger.info("Initializing command executor...")
        try:
            command_executor = CommandExecutor()
            logger.info("✅ Command executor initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing command executor: {e}")
            command_executor = None
        
        # Test Phi-3 model if it was loaded
        if model_status['llm']['loaded'] and hasattr(local_model_manager, '_llama_model') and local_model_manager._llama_model:
            logger.info("🧪 Testing pre-loaded Phi-3 model...")
            try:
                # Simple test to verify the model works
                test_response = await local_model_manager.generate_response("Hello", "You are a helpful AI assistant.")
                if test_response and not test_response.startswith("Error"):
                    logger.info("✅ Phi-3 model test successful!")
                else:
                    logger.warning(f"⚠️ Phi-3 test returned: {test_response}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to test Phi-3 model: {e}")
        elif model_status['llm']['loaded']:
            logger.info("ℹ️ Phi-3 model configured but not pre-loaded (will load on first use)")
        else:
            logger.warning("⚠️ Phi-3 model not available - will use API fallback")
        
        # Initialize file monitor (temporarily disabled)
        logger.info("File monitoring disabled to prevent async callback errors")
        file_monitor = FileMonitor(settings)
        
        # Disabled until proper restart - prevents log spam
        # Add file change callback to send updates via WebSocket
        # async def on_file_change(change):
        #     await ws_manager.broadcast({
        #         "type": "file_change",
        #         "path": str(change.path),
        #         "event": change.event_type,
        #         "timestamp": change.timestamp.isoformat()
        #     })
        # 
        # file_monitor.add_change_callback(on_file_change)
        # 
        # # Start file monitoring
        # await file_monitor.start_monitoring()
        
        # Start voice pipeline for real-time streaming
        logger.info("🚀 Starting voice pipeline...")
        voice_pipeline_started = False
        
        # Start BOTH handlers for testing
        logger.info("🔧 Starting both SimpleAudioWebSocketHandler (port 8002) and Pipecat pipeline (port 8001)")
        
        # Start SimpleAudioWebSocketHandler first (proven working)
        try:
            from .simple_websocket_handler import start_simple_audio_server
            simple_started = await start_simple_audio_server()
            if simple_started:
                logger.info("✅ SimpleAudioWebSocketHandler started on ws://0.0.0.0:8002")
                voice_pipeline_started = True
            else:
                logger.error("❌ Failed to start SimpleAudioWebSocketHandler")
        except Exception as e:
            logger.error(f"❌ Failed to start SimpleAudioWebSocketHandler: {e}")
            
        # Pipecat pipeline disabled - using SimpleAudioWebSocketHandler with Faster-Whisper instead
        logger.info("⏭️  Skipping Pipecat pipeline - using SimpleAudioWebSocketHandler with Faster-Whisper STT")
        logger.info("🔧 JSON Discord bot should connect to ws://localhost:8002 (SimpleAudioWebSocketHandler)")
        
        if not voice_pipeline_started:
            logger.warning("⚠️ No voice pipeline available - voice features disabled")
        
        logger.info("✅ All components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down Local AI Assistant...")
    
    try:
        if file_monitor:
            await file_monitor.stop_monitoring()
        await ws_manager.disconnect_all()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        
    logger.info("Shutdown complete")


def create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title="Local AI Assistant",
        description="A high-performance local assistant for development and debugging",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Store settings in app state
    app.state.settings = settings
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app: FastAPI):
    """Register all application routes"""
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {"message": "Local AI Assistant is running"}
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": "0.1.0"
        }
    
    @app.post("/api/audio/transcribe")
    async def transcribe_audio(data: dict):
        """Transcribe audio to text"""
        try:
            audio_data = data.get("audio_data")
            audio_format = data.get("format", "base64_pcm")
            language = data.get("language", "en")  # Allow language override
            
            if not audio_data:
                return {"error": "No audio data provided"}
            
            import base64
            
            # Decode audio data - support multiple formats
            if audio_format in ["base64_pcm", "base64", "base64_wav", "base64_webm"]:
                try:
                    audio_bytes = base64.b64decode(audio_data)
                except Exception as e:
                    return {"error": f"Invalid base64 audio data: {e}"}
            else:
                return {"error": f"Unsupported audio format: {audio_format}. Supported: base64_pcm, base64_wav, base64_webm"}
            
            # Validate audio data size
            if len(audio_bytes) < 1000:  # Less than 1KB is likely invalid
                return {"error": "Audio data too small - may be corrupted or empty"}
            
            if len(audio_bytes) > 25 * 1024 * 1024:  # Larger than 25MB
                return {"error": "Audio data too large - maximum 25MB supported"}
            
            # Try local Parakeet model first
            if local_model_manager.models['stt']:
                logger.info("Using local Parakeet-TDT for transcription")
                transcript = await local_model_manager.transcribe_audio(audio_bytes)
                
                if transcript:
                    logger.info(f"Local transcription successful: '{transcript[:100]}...'")
                    return {
                        "text": transcript,
                        "success": True,
                        "model": "parakeet_tdt",
                        "audio_duration": len(audio_bytes) / (48000 * 2)
                    }
                else:
                    logger.warning("Local transcription failed, falling back to OpenAI")
            
            # Fallback to OpenAI Whisper
            logger.info("Using OpenAI Whisper for transcription")
            import tempfile
            import os
            from openai import OpenAI
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            try:
                # Initialize OpenAI client
                client = OpenAI()
                
                # Transcribe audio with enhanced settings for better accuracy
                with open(temp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text",
                        language=language,  # Use language from request (default: "en")
                        prompt="This is a voice conversation with an AI assistant about programming, debugging, and technical topics. Common terms: Python, JavaScript, code, debug, error, function, variable, API, Discord, bot.",  # Enhanced context hint
                        temperature=0.0  # Use deterministic output for consistency
                    )
                
                logger.info(f"OpenAI transcription successful: '{transcript[:100]}...'")
                return {
                    "text": transcript,
                    "success": True,
                    "model": "whisper-1",
                    "audio_duration": len(audio_bytes) / (48000 * 2)
                }
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return {"error": str(e), "success": False}
    
    @app.post("/api/audio/tts")
    async def text_to_speech(data: dict):
        """Convert text to speech"""
        try:
            text = data.get("text")
            voice_id = data.get("voice_id", "default")
            audio_format = data.get("format", "mp3")
            
            if not text:
                return {"error": "No text provided"}
            
            # Extract text if it's a JSON response object
            if isinstance(text, dict):
                if "response" in text:
                    text = text["response"]
                elif "text" in text:
                    text = text["text"]
                else:
                    text = str(text)
            
            # Try local Kokoro TTS first
            if local_model_manager.models['tts']:
                logger.info("Using local Kokoro TTS for synthesis")
                audio_data = await local_model_manager.synthesize_speech(text, voice_id)
                
                if audio_data and len(audio_data) > 0:
                    import base64
                    audio_base64 = base64.b64encode(audio_data).decode()
                    logger.info(f"Local TTS successful for: '{text[:100]}...' (voice: {voice_id})")
                    return {
                        "audio_data": audio_base64,
                        "format": "mp3",
                        "voice": voice_id,
                        "success": True,
                        "model": "kokoro_tts",
                        "text": text
                    }
                else:
                    logger.warning("Local TTS failed, falling back to OpenAI")
            
            # Fallback to OpenAI TTS
            logger.info("Using OpenAI TTS for synthesis")
            import base64
            from openai import OpenAI
            
            # Initialize OpenAI client
            client = OpenAI()
            
            # Map voice names to OpenAI voices
            voice_map = {
                "default": "alloy",
                "alloy": "alloy",
                "echo": "echo", 
                "fable": "fable",
                "onyx": "onyx",
                "nova": "nova",
                "shimmer": "shimmer"
            }
            
            voice = voice_map.get(voice_id, "alloy")
            
            # Generate speech
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            # Convert audio to base64
            audio_data = response.content
            audio_base64 = base64.b64encode(audio_data).decode()
            
            logger.info(f"OpenAI TTS successful for: '{text[:100]}...' (voice: {voice})")
            return {
                "audio_data": audio_base64,
                "format": "mp3",
                "voice": voice,
                "success": True,
                "model": "openai_tts",
                "text": text
            }
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return {"error": str(e), "success": False}

    @app.post("/api/conversation/message")
    async def conversation_message(data: dict):
        """Handle conversation messages from Discord bot"""
        try:
            user_id = data.get("user_id")
            message = data.get("message")
            context = data.get("context", {})
            
            if not message:
                return {"error": "Message is required"}
            
            # Try local Phi-3 model first
            if local_model_manager.models['llm']:
                logger.info("Using local Phi-3 Mini for conversation")
                
                # Create system prompt
                system_prompt = "You are a helpful AI assistant integrated with Discord. Provide concise, helpful responses."
                if context.get('source') == 'voice':
                    system_prompt += " You're in a voice conversation, so keep responses brief and conversational."
                
                response = await local_model_manager.generate_response(message, system_prompt)
                
                if response and not response.startswith("Error"):
                    logger.info(f"Local LLM response: '{response[:100]}...'")
                    return {"response": response, "model": "phi3_mini"}
                else:
                    logger.warning("Local LLM failed, falling back to API models")
            
            # Fallback to LLM handler (API models)
            logger.info("Using API LLM models")
            # Combine user_id into context for the LLM handler
            context["user_id"] = user_id
            
            # Provide empty conversation history if not present
            conversation_history = []
            
            response = await llm_handler.process_message(
                message=message,
                conversation_history=conversation_history,
                context=context
            )
            
            return {"response": response.response if hasattr(response, 'response') else str(response), "model": "api_fallback"}
            
        except Exception as e:
            logger.error(f"Error processing conversation message: {e}")
            return {"error": str(e)}
    
    @app.get("/api/conversation/history/{user_id}")
    async def get_conversation_history(user_id: str, limit: int = 10):
        """Get conversation history for a user"""
        try:
            # For now, return empty history since we don't have persistent storage yet
            return {"history": [], "user_id": user_id, "limit": limit}
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {"error": str(e)}
    
    @app.post("/api/exec/command")
    async def execute_command(data: dict):
        """Execute command and return job ID"""
        try:
            command = data.get("command")
            working_dir = data.get("working_dir", ".")
            
            if not command:
                return {"error": "Command is required"}
            
            job_id = await command_executor.execute_async(command, working_dir)
            return {"job_id": job_id}
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {"error": str(e)}
    
    @app.get("/api/exec/output/{job_id}")
    async def get_command_output(job_id: str):
        """Get command execution output"""
        try:
            output = await command_executor.get_output(job_id)
            return output
            
        except Exception as e:
            logger.error(f"Error getting command output: {e}")
            return {"error": str(e)}
    
    @app.post("/api/files/analyze")
    async def analyze_file(data: dict):
        """Analyze file content"""
        try:
            file_path = data.get("file_path")
            
            if not file_path:
                return {"error": "File path is required"}
            
            content = await file_monitor.get_file_content(file_path)
            if content is None:
                return {"error": "File not found or cannot be read"}
            
            return {"content": content, "path": file_path}
            
        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
            return {"error": str(e)}
    
    @app.post("/api/files/watch")
    async def watch_directory(data: dict):
        """Add directory to file monitoring"""
        try:
            directory = data.get("directory")
            user_id = data.get("user_id", "default")
            
            if not directory:
                return {"error": "Directory is required"}
            
            await file_monitor.add_watch_directory(user_id, directory)
            return {"message": f"Watching directory: {directory}"}
            
        except Exception as e:
            logger.error(f"Error watching directory: {e}")
            return {"error": str(e)}
    
    @app.get("/api/status")
    async def get_api_status():
        """Get API status and information"""
        try:
            return {
                "status": "running",
                "version": "1.0.0",
                "components": {
                    "llm_handler": llm_handler is not None,
                    "file_monitor": file_monitor is not None,
                    "command_executor": command_executor is not None
                },
                "monitored_directories": len(file_monitor.watched_directories) if file_monitor else 0
            }
        except Exception as e:
            logger.error(f"Error getting API status: {e}")
            return {"error": str(e)}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time communication"""
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                
                # Process different message types
                message_type = data.get("type")
                
                if message_type == "chat":
                    # Handle chat messages
                    response = await handle_chat_message(data)
                    await websocket.send_json(response)
                    
                elif message_type == "command":
                    # Handle command execution
                    response = await handle_command(data)
                    await websocket.send_json(response)
                    
                elif message_type == "file_operation":
                    # Handle file operations
                    response = await handle_file_operation(data)
                    await websocket.send_json(response)
                    
                elif message_type == "voice":
                    # Handle voice chat requests
                    response = await handle_voice_request(data)
                    await websocket.send_json(response)
                    
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })
                    
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
            logger.info("Client disconnected")


async def handle_chat_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle chat messages"""
    try:
        message = data.get("message", "")
        if not message:
            return {
                "type": "error",
                "message": "No message provided"
            }
        
        # Check for special commands
        if message.startswith("/"):
            return await handle_special_command(message)
        
        # Get available models
        models = await llm_handler.get_available_models()
        logger.info(f"Available models: {models}")
        
        # Generate response using LLM
        response = await llm_handler.generate_response(
            prompt=message,
            system_prompt="You are a helpful AI assistant specialized in debugging and development. Provide concise, actionable responses."
        )
        
        return {
            "type": "chat_response",
            "message": response,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"Error handling chat message: {e}")
        return {
            "type": "error", 
            "message": f"Error processing message: {str(e)}"
        }


async def handle_command(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle command execution"""
    try:
        command = data.get("command")
        action = data.get("action")
        working_dir = data.get("working_directory")
        
        if command:
            # Execute custom command
            result = await command_executor.execute_command(
                command=command,
                working_directory=working_dir,
                timeout=60
            )
            
            return {
                "type": "command_response",
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.return_code,
                "execution_time": result.execution_time,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif action:
            # Handle predefined actions
            if action == "run_tests":
                # Try common test commands
                test_commands = ["pytest", "python -m pytest", "npm test", "make test"]
                
                for cmd in test_commands:
                    if await command_executor.check_command_availability(cmd.split()[0]):
                        result = await command_executor.execute_command(cmd, working_dir)
                        return {
                            "type": "command_response",
                            "output": result.stdout,
                            "error": result.stderr,
                            "return_code": result.return_code,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        
                return {
                    "type": "command_response", 
                    "output": "No test framework detected",
                    "timestamp": asyncio.get_event_loop().time()
                }
                
            elif action == "check_logs":
                # Find and analyze recent log files
                error_files = await file_monitor.analyze_recent_errors()
                if error_files:
                    summary = f"Found {len(error_files)} files with errors:\n"
                    for file_analysis in error_files[:5]:
                        summary += f"- {file_analysis.path}: {len(file_analysis.error_lines)} errors\n"
                else:
                    summary = "No recent errors detected in monitored files"
                    
                return {
                    "type": "command_response",
                    "output": summary,
                    "timestamp": asyncio.get_event_loop().time()
                }
                
            elif action == "browse_web":
                return {
                    "type": "command_response",
                    "output": "Web browsing functionality coming soon",
                    "timestamp": asyncio.get_event_loop().time()
                }
                
        return {
            "type": "error",
            "message": "No valid command or action specified"
        }
        
    except Exception as e:
        logger.error(f"Error handling command: {e}")
        return {
            "type": "error",
            "message": f"Command execution error: {str(e)}"
        }


async def handle_file_operation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle file operations"""
    try:
        operation = data.get("operation")
        file_path = data.get("path")
        
        if operation == "read":
            content = await file_monitor.get_file_content(file_path)
            if content is not None:
                return {
                    "type": "file_response",
                    "operation": "read",
                    "path": file_path,
                    "content": content[:5000],  # Limit content size
                    "truncated": len(content) > 5000,
                    "timestamp": asyncio.get_event_loop().time()
                }
            else:
                return {
                    "type": "error",
                    "message": f"Could not read file: {file_path}"
                }
                
        elif operation == "list":
            # List recent file changes
            changes = file_monitor.get_recent_changes(20)
            file_list = []
            
            for change in changes:
                file_list.append({
                    "path": str(change.path),
                    "event": change.event_type,
                    "timestamp": change.timestamp.isoformat(),
                    "is_directory": change.is_directory
                })
                
            return {
                "type": "file_response",
                "operation": "list",
                "files": file_list,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif operation == "analyze":
            # Analyze file for errors
            from pathlib import Path
            from .file_monitor import CodeAnalyzer
            
            analysis = await CodeAnalyzer.analyze_file(Path(file_path))
            if analysis:
                return {
                    "type": "file_response",
                    "operation": "analyze", 
                    "path": file_path,
                    "file_type": analysis.file_type,
                    "line_count": analysis.line_count,
                    "has_errors": analysis.has_errors,
                    "error_lines": analysis.error_lines,
                    "size_bytes": analysis.size_bytes,
                    "timestamp": asyncio.get_event_loop().time()
                }
            else:
                return {
                    "type": "error",
                    "message": f"Could not analyze file: {file_path}"
                }
                
        return {
            "type": "error",
            "message": f"Unknown file operation: {operation}"
        }
        
    except Exception as e:
        logger.error(f"Error handling file operation: {e}")
        return {
            "type": "error",
            "message": f"File operation error: {str(e)}"
        }


async def handle_special_command(command: str) -> Dict[str, Any]:
    """Handle special chat commands"""
    try:
        if command == "/help":
            help_text = """Available commands:
/help - Show this help message
/status - Show system status
/models - List available AI models
/files - List recent file changes
/processes - Show running processes
/clear - Clear chat history (frontend only)"""
            
            return {
                "type": "chat_response",
                "message": help_text,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif command == "/status":
            models = await llm_handler.get_available_models()
            processes = await command_executor.get_running_processes()
            changes = file_monitor.get_recent_changes(5)
            
            status = f"""System Status:
• Available models: {len(models['api_models'])} API + {len(models['local_models'])} local
• Running processes: {len(processes)}
• Recent file changes: {len(changes)}
• WebSocket connections: {ws_manager.get_connection_count()}"""
            
            return {
                "type": "chat_response",
                "message": status,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif command == "/models":
            models = await llm_handler.get_available_models()
            model_text = "Available AI Models:\n\nAPI Models:\n"
            for model in models['api_models']:
                model_text += f"• {model}\n"
            model_text += "\nLocal Models:\n"
            for model in models['local_models']:
                model_text += f"• {model}\n"
                
            return {
                "type": "chat_response", 
                "message": model_text,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif command == "/files":
            changes = file_monitor.get_recent_changes(10)
            if changes:
                files_text = "Recent file changes:\n"
                for change in changes:
                    files_text += f"• {change.event_type}: {change.path.name} ({change.timestamp.strftime('%H:%M:%S')})\n"
            else:
                files_text = "No recent file changes"
                
            return {
                "type": "chat_response",
                "message": files_text,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        elif command == "/processes":
            processes = await command_executor.get_running_processes()
            if processes:
                proc_text = f"Running processes ({len(processes)}):\n"
                for proc in processes:
                    runtime = (datetime.now() - proc.start_time).total_seconds()
                    proc_text += f"• PID {proc.pid}: {proc.command[:50]}... ({runtime:.1f}s)\n"
            else:
                proc_text = "No running processes"
                
            return {
                "type": "chat_response",
                "message": proc_text,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        else:
            return {
                "type": "error",
                "message": f"Unknown command: {command}. Type /help for available commands."
            }
            
    except Exception as e:
        logger.error(f"Error handling special command {command}: {e}")
        return {
            "type": "error", 
            "message": f"Command error: {str(e)}"
        }


async def handle_voice_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle voice chat requests"""
    try:
        action = data.get("action")
        text = data.get("text")
        audio = data.get("audio")
        
        if action == "transcribe" and audio:
            # Real audio transcription
            try:
                # Try local Whisper installation first
                from .local_whisper import LocalWhisperHandler
                
                local_whisper = LocalWhisperHandler()
                result = await local_whisper.transcribe_audio(audio)
                
                # If that fails, try simple speech recognition
                if not result.get("success", False):
                    try:
                        from .simple_speech import SimpleSpeechHandler
                        speech_handler = SimpleSpeechHandler()
                        result = await speech_handler.transcribe_audio(audio)
                    except ImportError:
                        pass
                
                if result["success"]:
                    # Process the transcribed text
                    text = result["text"]
                    response = await llm_handler.generate_response(
                        prompt=text,
                        system_prompt="You are in a voice conversation. Keep responses brief and conversational."
                    )
                    
                    return {
                        "type": "voice_response",
                        "transcribed_text": text,
                        "text": response,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                else:
                    return {
                        "type": "error",
                        "message": f"Transcription failed: {result.get('error', 'Unknown error')}"
                    }
                    
            except ImportError:
                return {
                    "type": "error",
                    "message": "Whisper not installed. Run: pip install openai-whisper"
                }
                
        elif action == "process" and text:
            # Process voice input text
            try:
                from .browser_voice import BrowserVoiceHandler
                
                # Create voice handler
                voice_handler = BrowserVoiceHandler(llm_handler)
                
                # Process the voice input
                response = await voice_handler.process_voice_input(text)
                return response
                
            except ImportError:
                # Fallback to regular text processing
                response = await llm_handler.generate_response(
                    prompt=text,
                    system_prompt="You are in a voice conversation. Keep responses brief and conversational."
                )
                
                return {
                    "type": "voice_response",
                    "text": response,
                    "audio": None,
                    "has_audio": False,
                    "timestamp": asyncio.get_event_loop().time()
                }
                
        elif action == "start":
            return {
                "type": "voice_response",
                "status": "browser_mode",
                "mode": "browser",
                "message": "🎤 Browser voice chat ready! Click the microphone button to speak."
            }
            
        elif action == "stop":
            return {
                "type": "voice_response",
                "status": "stopped",
                "message": "Voice chat stopped"
            }
            
        elif action == "status":
            return {
                "type": "voice_response",
                "status": "available",
                "features": {
                    "browser_speech_api": True,
                    "text_to_speech": TTS_AVAILABLE if 'TTS_AVAILABLE' in globals() else False,
                    "pipecat_mode": False  # TODO: Check actual Pipecat availability
                }
            }
            
        return {
            "type": "error",
            "message": f"Unknown voice action: {action}"
        }
        
    except Exception as e:
        logger.error(f"Error handling voice request: {e}")
        return {
            "type": "error",
            "message": f"Voice request error: {str(e)}"
        }


def run_server(app: FastAPI, settings: Settings):
    """Run the FastAPI server"""
    if settings.server_reload:
        # For reload mode, pass the module path instead of the app instance
        uvicorn.run(
            "main:app",
            host=settings.server_host,
            port=settings.server_port,
            reload=True,
            log_level=settings.server_log_level.lower()
        )
    else:
        uvicorn.run(
            app,
            host=settings.server_host,
            port=settings.server_port,
            workers=settings.server_workers,
            log_level=settings.server_log_level.lower()
        )