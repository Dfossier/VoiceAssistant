"""FastAPI server setup and configuration"""
import asyncio
import os
import subprocess
import re
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

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
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global llm_handler, file_monitor, command_executor
    
    logger.info("Starting up Local AI Assistant...")
    
    # Get settings from app state
    settings = app.state.settings
    
    # Initialize components
    logger.info("🔄 Initializing components...")
    
    # Import and initialize model manager
    from .local_models import local_model_manager
    app.state.model_manager = local_model_manager
    
    # Initialize model manager
    await local_model_manager.initialize()
    
    # Load LLM and TTS models at startup (STT uses Whisper on-demand)
    logger.info("🧠 Loading LLM model...")
    await local_model_manager.load_llm_model()
    
    logger.info("🔊 Loading TTS model...")
    await local_model_manager.load_tts_model()
    
    app.state.startup_complete = True
    logger.info("✅ All models loaded successfully")
    
    logger.info("✅ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Local AI Assistant...")
    try:
        if llm_handler:
            await llm_handler.cleanup()
        if file_monitor:
            await file_monitor.stop()
        if command_executor:
            await command_executor.cleanup()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        if llm_handler:
            await llm_handler.cleanup()
        if file_monitor:
            await file_monitor.stop()
        if command_executor:
            await command_executor.cleanup()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(lifespan=lifespan, 
        title="Local AI Assistant",
        description="A high-performance local assistant for Windows/WSL",
        version="1.0.0",
        
    )
    
    # Store settings in app state
    app.state.settings = settings
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app: FastAPI):
    """Register all API routes"""
    
    @app.get("/")
    async def root():
        """Serve the web dashboard"""
        return {
            "message": "Local AI Assistant API",
            "version": "1.0.0",
            "docs": "/docs",
            "dashboard": "/dashboard"
        }
    
    @app.get("/api/system/status")
    async def get_system_status():
        """Get system status"""
        import psutil
        import os
        import time
        
        # Get current process info
        backend_pid = os.getpid()
        backend_process = psutil.Process(backend_pid)
        backend_uptime = time.time() - backend_process.create_time()
        
        # Check for WebSocket service (port 8002)
        websocket_running = False
        websocket_pid = None
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == 8002 and conn.status == 'LISTEN':
                    websocket_running = True
                    websocket_pid = conn.pid
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        
        # Check for Discord bot process (approximate)
        discord_running = False
        discord_pid = None
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['cmdline'] and any('direct_audio_bot' in str(cmd) for cmd in proc.info['cmdline']):
                    discord_running = True
                    discord_pid = proc.info['pid']
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        
        return {
            "backend": {
                "name": "Backend API",
                "status": "running",
                "pid": backend_pid,
                "uptime": int(backend_uptime),
                "cpu_percent": backend_process.cpu_percent(),
                "memory_mb": backend_process.memory_info().rss / 1024 / 1024
            },
            "discord_bot": {
                "name": "Discord Bot",
                "status": "running" if discord_running else "stopped",
                "pid": discord_pid,
                "uptime": 0,  # Would need to track this separately
                "cpu_percent": 0,
                "memory_mb": 0
            },
            "voice_pipeline": {
                "name": "Voice Pipeline WebSocket",
                "status": "running" if websocket_running else "stopped", 
                "pid": websocket_pid,
                "uptime": 0,  # Would need to track this separately
                "cpu_percent": 0,
                "memory_mb": 0
            },
            "claude_code_active": False,  # Not implemented
            "terminals_active": 0,  # Not implemented
            "timestamp": datetime.now().isoformat()
        }
    
    @app.get("/api/system/logs/sources")
    async def get_log_sources():
        """Get available log sources"""
        return ["backend", "discord", "voice", "system"]
    
    @app.get("/api/system/logs")
    async def get_logs(source: str = "backend", lines: int = 100):
        """Get logs from specified source"""
        from pathlib import Path
        
        log_files = {
            "backend": "minimal_server.log",
            "discord": "WindowsDiscordBot/discord_bot_windows.log", 
            "voice": "websocket_service.log",
            "system": "system.log"
        }
        
        log_file = log_files.get(source)
        if not log_file:
            return {"logs": []}
        
        log_path = Path(log_file)
        if not log_path.exists():
            return {"logs": []}
        
        try:
            # Read last N lines from log file
            import collections
            with open(log_path, "r") as f:
                lines_deque = collections.deque(f, maxlen=lines)
            
            return {"logs": list(lines_deque)}
        except Exception as e:
            logger.error(f"Failed to read log file {log_file}: {e}")
            return {"logs": []}
    
    @app.post("/api/voice/transcribe")
    async def transcribe_audio(audio_data: bytes):
        """Transcribe audio using Faster-Whisper"""
        # Placeholder - needs implementation
        return {"transcription": "Voice transcription not yet implemented"}
    
    @app.post("/api/voice/generate-response")
    async def generate_response(text: str):
        """Generate AI response using SmolLM2"""
        # Placeholder - needs implementation
        return {"response": f"Response to: {text}"}
    
    @app.post("/api/voice/synthesize")
    async def synthesize_speech(text: str):
        """Synthesize speech using Kokoro TTS"""
        # Placeholder - needs implementation
        return {"audio_base64": "base64_encoded_audio_placeholder"}
    
    # Register WebSocket endpoint
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
                    response = {"type": "chat_response", "message": "Chat functionality not yet implemented"}
                    await websocket.send_json(response)
                    
                elif message_type == "command":
                    # Handle command execution
                    response = {"type": "command_response", "message": "Command functionality not yet implemented"}
                    await websocket.send_json(response)
                    
                elif message_type == "audio_input":
                    # Handle audio input from Discord bot
                    response = {"type": "audio_ack", "message": "Audio received"}
                    await websocket.send_json(response)
                    logger.info("🎤 Received audio chunk from Discord bot")
                    
                elif message_type == "start":
                    # Handle connection start
                    response = {"type": "started", "message": "Voice session started"}
                    await websocket.send_json(response)
                    logger.info("🎤 Voice session started with Discord bot")
                    
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })
                    
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
            logger.info("Client disconnected")
            ws_manager.disconnect(websocket)
            logger.info("Client disconnected")
            ws_manager.disconnect(websocket)
            logger.info("Client disconnected")


def run_server(app: FastAPI, settings: Settings):
    """Run the FastAPI server"""
    if settings.dev_mode:
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
