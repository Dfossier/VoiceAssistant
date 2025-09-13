#!/usr/bin/env python3
"""
Discord AI Assistant Backend API Server
Provides REST API endpoints for Discord bot integration
"""
import os
import sys
import asyncio
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.responses import JSONResponse
    import uvicorn
    from pydantic import BaseModel, Field
    from loguru import logger
    import aiofiles
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Run: source venv/bin/activate && pip install -r requirements.txt")
    sys.exit(1)

# Import our services
from core.llm_handler import LLMHandler
from core.file_monitor import FileMonitor
from core.command_executor import CommandExecutor

# Configuration
API_KEY = os.getenv("API_KEY", "your-secure-api-key-here")
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")

# Global services
llm_handler = None
file_monitor = None
command_executor = None

# In-memory storage for development (replace with Redis/DB in production)
conversations: Dict[str, List[Dict]] = {}
active_jobs: Dict[str, Dict] = {}

# Pydantic Models
class ConversationMessage(BaseModel):
    user_id: str
    message: str
    context: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseModel):
    response: str
    suggestions: List[str] = []
    files_referenced: List[str] = []

class CommandRequest(BaseModel):
    user_id: str
    command: str
    working_directory: Optional[str] = None
    timeout: int = 30

class CommandResponse(BaseModel):
    job_id: str
    status: str

class FileContentRequest(BaseModel):
    path: str
    lines: Optional[str] = None  # e.g., "50-100"

class WatchDirectoryRequest(BaseModel):
    user_id: str
    directory: str
    patterns: List[str] = ["*"]

# Security
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials.credentials

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global llm_handler, file_monitor, command_executor
    
    logger.info("🚀 Starting Discord AI Assistant Backend...")
    
    # Initialize services
    llm_handler = LLMHandler()
    file_monitor = FileMonitor()
    command_executor = CommandExecutor()
    
    logger.info("✅ All services initialized")
    yield
    
    # Cleanup
    if file_monitor:
        await file_monitor.stop()
    logger.info("🔄 Backend shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Discord AI Assistant Backend",
    description="Backend API for Discord bot integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "llm": llm_handler is not None,
            "file_monitor": file_monitor is not None,
            "command_executor": command_executor is not None
        }
    }

# Conversation Management Endpoints
@app.post("/api/conversation/message", response_model=ConversationResponse)
async def process_message(
    request: ConversationMessage,
    api_key: str = Depends(verify_api_key)
):
    """Process a message from Discord bot"""
    try:
        # Initialize conversation history if needed
        if request.user_id not in conversations:
            conversations[request.user_id] = []
        
        # Add user message to history
        conversations[request.user_id].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat(),
            "context": request.context
        })
        
        # Get AI response
        response = await llm_handler.process_message(
            message=request.message,
            conversation_history=conversations[request.user_id],
            context=request.context
        )
        
        # Add assistant response to history
        conversations[request.user_id].append({
            "role": "assistant", 
            "content": response.response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limit conversation history to last 50 messages
        if len(conversations[request.user_id]) > 50:
            conversations[request.user_id] = conversations[request.user_id][-50:]
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversation/{user_id}/history")
async def get_conversation_history(
    user_id: str,
    limit: int = 10,
    api_key: str = Depends(verify_api_key)
):
    """Get conversation history for a user"""
    history = conversations.get(user_id, [])
    return {
        "user_id": user_id,
        "history": history[-limit:] if limit > 0 else history,
        "total_messages": len(history)
    }

@app.delete("/api/conversation/{user_id}")
async def clear_conversation(
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Clear conversation history for a user"""
    if user_id in conversations:
        del conversations[user_id]
    return {"message": f"Conversation cleared for user {user_id}"}

# File Operations Endpoints
@app.get("/api/files/content")
async def get_file_content(
    path: str,
    lines: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Read file content with optional line range"""
    try:
        if not Path(path).exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        # Handle line range if specified
        if lines:
            try:
                if '-' in lines:
                    start, end = map(int, lines.split('-'))
                    content_lines = content.split('\n')
                    content = '\n'.join(content_lines[start-1:end])
                else:
                    line_num = int(lines)
                    content_lines = content.split('\n')
                    content = content_lines[line_num-1] if line_num <= len(content_lines) else ""
            except (ValueError, IndexError):
                pass  # Return full content if line parsing fails
        
        return {
            "path": path,
            "content": content,
            "size": len(content),
            "lines": len(content.split('\n'))
        }
        
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/watch")
async def watch_directory(
    request: WatchDirectoryRequest,
    api_key: str = Depends(verify_api_key)
):
    """Add directory to file monitoring"""
    try:
        success = await file_monitor.watch_directory(
            directory=request.directory,
            patterns=request.patterns,
            user_id=request.user_id
        )
        
        if success:
            return {"message": f"Now watching {request.directory}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to watch directory")
            
    except Exception as e:
        logger.error(f"Error watching directory {request.directory}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/changes")
async def get_recent_changes(
    user_id: Optional[str] = None,
    limit: int = 20,
    api_key: str = Depends(verify_api_key)
):
    """Get recent file changes"""
    changes = await file_monitor.get_recent_changes(user_id=user_id, limit=limit)
    return {"changes": changes}

# Command Execution Endpoints
@app.post("/api/exec/command", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Execute a shell command"""
    job_id = str(uuid.uuid4())
    
    # Store job info
    active_jobs[job_id] = {
        "user_id": request.user_id,
        "command": request.command,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "working_directory": request.working_directory
    }
    
    # Execute command in background
    background_tasks.add_task(
        command_executor.execute_async,
        job_id=job_id,
        command=request.command,
        working_directory=request.working_directory,
        timeout=request.timeout,
        job_storage=active_jobs
    )
    
    return CommandResponse(job_id=job_id, status="queued")

@app.get("/api/exec/status/{job_id}")
async def get_command_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get command execution status"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return active_jobs[job_id]

@app.get("/api/exec/output/{job_id}")
async def get_command_output(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get command output"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = active_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "stdout": job.get("stdout", ""),
        "stderr": job.get("stderr", ""),
        "return_code": job.get("return_code"),
        "duration": job.get("duration")
    }

# Project Analysis Endpoints
@app.get("/api/project/structure")
async def get_project_structure(
    path: str,
    max_depth: int = 3,
    api_key: str = Depends(verify_api_key)
):
    """Get project file tree structure"""
    try:
        structure = await file_monitor.get_directory_structure(path, max_depth)
        return {"path": path, "structure": structure}
    except Exception as e:
        logger.error(f"Error getting project structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/project/errors")
async def get_project_errors(
    path: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Get current errors across project"""
    try:
        errors = await file_monitor.scan_for_errors(path)
        return {"errors": errors}
    except Exception as e:
        logger.error(f"Error scanning for errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/project/analyze")
async def analyze_project(
    path: str,
    api_key: str = Depends(verify_api_key)
):
    """Analyze project for issues"""
    try:
        analysis = await llm_handler.analyze_project(path)
        return {"path": path, "analysis": analysis}
    except Exception as e:
        logger.error(f"Error analyzing project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "default"

@app.post("/api/audio/tts")
async def text_to_speech(
    request: TTSRequest,
    api_key: str = Depends(verify_api_key)
):
    """Convert text to speech (placeholder - returns simple response)"""
    try:
        # For now, return a simple acknowledgment
        # In a full implementation, this would generate actual audio
        logger.info(f"TTS request for text: {request.text[:50]}...")
        
        return {
            "status": "success", 
            "message": "TTS not fully implemented yet",
            "text": request.text,
            "voice": request.voice,
            "audio_url": None  # Would contain audio file URL in full implementation
        }
    except Exception as e:
        logger.error(f"Error in TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info(f"🔥 Starting Discord AI Assistant Backend on {HOST}:{PORT}")
    logger.info(f"🔑 API Key required: {API_KEY[:8]}...")
    logger.info("📚 API Documentation: http://localhost:8000/docs")
    
    uvicorn.run(
        "discord_main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )