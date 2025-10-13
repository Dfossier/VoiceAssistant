#!/usr/bin/env python3
"""
AI Assistant Web Launcher - Service Management API

SECURE REST API for manual service management with authentication.
NOT the main user interface - see web-dashboard/ for the React UI.

Architecture:
- web-dashboard/ (port 3000): React UI → main backend (port 8000) via WebSocket/REST
- web_launcher.py (port 9000): SECURE REST API for service management

Authentication: Set WEB_LAUNCHER_API_KEY environment variable
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from loguru import logger
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Authentication setup
API_KEY = os.getenv("WEB_LAUNCHER_API_KEY", "dev-key-change-in-production")
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for protected endpoints"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

# Simple service manager (placeholder - replace with real implementation)
class ServiceManager:
    """Service manager for backend and bot control"""
    
    def __init__(self):
        self.services = {"backend": False, "bot": False}
        self.logs = []
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "backend": {"running": self.services["backend"], "port": 8000},
            "bot": {"running": self.services["bot"], "status": "Connected" if self.services["bot"] else "Disconnected"}
        }
    
    async def start_backend(self) -> bool:
        """Start backend service"""
        # Placeholder implementation
        logger.info("Backend start requested")
        self.services["backend"] = True
        return True
    
    async def stop_backend(self) -> bool:
        """Stop backend service"""
        # Placeholder implementation
        logger.info("Backend stop requested")
        self.services["backend"] = False
        return True
    
    async def start_bot(self) -> bool:
        """Start bot service"""
        # Placeholder implementation
        logger.info("Bot start requested")
        self.services["bot"] = True
        return True
    
    async def stop_bot(self) -> bool:
        """Stop bot service"""
        # Placeholder implementation
        logger.info("Bot stop requested")
        self.services["bot"] = False
        return True

# Create service manager
manager = ServiceManager()

# Create FastAPI app
app = FastAPI(
    title="AI Assistant Service Manager",
    version="1.0.0",
    description="Secure REST API for managing AI Assistant services"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:9000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Serve informational page"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>AI Assistant Service Manager</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        .warning { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .info { background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>🤖 AI Assistant Service Manager</h1>
    
    <div class="warning">
        <strong>⚠️ This is the SERVICE MANAGEMENT API</strong><br>
        For the main user interface, visit: <a href="http://localhost:3000">http://localhost:3000</a>
    </div>
    
    <div class="info">
        <strong>🔐 Authentication Required</strong><br>
        All service management endpoints require API key authentication.<br>
        Set environment variable: <code>WEB_LAUNCHER_API_KEY</code>
    </div>
    
    <h2>Available Endpoints:</h2>
    <ul>
        <li><code>GET /status</code> - Get service status</li>
        <li><code>GET /logs</code> - Get service logs (paginated)</li>
        <li><code>POST /start-all</code> - Start all services</li>
        <li><code>POST /stop-all</code> - Stop all services</li>
        <li><code>POST /start-backend</code> - Start backend only</li>
        <li><code>POST /stop-backend</code> - Stop backend only</li>
        <li><code>POST /start-bot</code> - Start bot only</li>
        <li><code>POST /stop-bot</code> - Stop bot only</li>
    </ul>
    
    <h2>Architecture:</h2>
    <ul>
        <li><strong>Main UI:</strong> React dashboard at localhost:3000</li>
        <li><strong>Backend API:</strong> FastAPI at localhost:8000</li>
        <li><strong>Service Manager:</strong> This API at localhost:9000</li>
    </ul>
</body>
</html>""")

@app.get("/status")
async def get_status():
    """Get current service status (no auth required for status)"""
    return manager.get_status()

@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get service logs with pagination (no auth required for logs)"""
    try:
        logs = manager.logs[-limit:] if len(manager.logs) > limit else manager.logs
        return {
            "logs": logs,
            "total": len(manager.logs),
            "returned": len(logs),
            "limit": limit
        }
    except Exception as e:
        return {"logs": [], "error": f"Failed to retrieve logs: {str(e)}"}

@app.post("/start-all")
async def start_all(api_key: str = Depends(verify_api_key)):
    """Start all services with validation and confirmation"""
    try:
        status = manager.get_status()
        
        # Check if already running
        if status["backend"]["running"] and status["bot"]["running"]:
            return {"message": "All services are already running", "status": status}
        
        # Start services with proper sequencing
        backend_started = await manager.start_backend()
        await asyncio.sleep(2)  # Non-blocking delay
        bot_started = await manager.start_bot()
        
        # Verify startup
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Service startup initiated",
            "backend_started": backend_started,
            "bot_started": bot_started,
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Start all services failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start services: {str(e)}")

@app.post("/stop-all")
async def stop_all(api_key: str = Depends(verify_api_key)):
    """Stop all services with proper sequencing"""
    try:
        status = manager.get_status()
        
        # Check if any running
        if not status["backend"]["running"] and not status["bot"]["running"]:
            return {"message": "No services are currently running", "status": status}
        
        # Stop in reverse order: bot first, then backend
        await manager.stop_bot()
        await asyncio.sleep(1)
        await manager.stop_backend()
        
        # Verify shutdown
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Service shutdown initiated",
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Stop all services failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop services: {str(e)}")

@app.post("/start-backend")
async def start_backend(api_key: str = Depends(verify_api_key)):
    """Start backend service with validation"""
    try:
        status = manager.get_status()
        if status["backend"]["running"]:
            return {"message": "Backend is already running", "status": status}
        
        started = await manager.start_backend()
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Backend startup initiated",
            "started": started,
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Start backend failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start backend: {str(e)}")

@app.post("/stop-backend")
async def stop_backend(api_key: str = Depends(verify_api_key)):
    """Stop backend service with validation"""
    try:
        status = manager.get_status()
        if not status["backend"]["running"]:
            return {"message": "Backend is not running", "status": status}
        
        await manager.stop_backend()
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Backend shutdown initiated",
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Stop backend failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop backend: {str(e)}")

@app.post("/start-bot")
async def start_bot(api_key: str = Depends(verify_api_key)):
    """Start bot service with validation"""
    try:
        status = manager.get_status()
        if status["bot"]["running"]:
            return {"message": "Bot is already running", "status": status}
        
        started = await manager.start_bot()
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Bot startup initiated",
            "started": started,
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Start bot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start bot: {str(e)}")

@app.post("/stop-bot")
async def stop_bot(api_key: str = Depends(verify_api_key)):
    """Stop bot service with validation"""
    try:
        status = manager.get_status()
        if not status["bot"]["running"]:
            return {"message": "Bot is not running", "status": status}
        
        await manager.stop_bot()
        await asyncio.sleep(1)
        final_status = manager.get_status()
        
        return {
            "message": "Bot shutdown initiated",
            "final_status": final_status
        }
    except Exception as e:
        logger.error(f"Stop bot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop bot: {str(e)}")

if __name__ == "__main__":
    if API_KEY == "dev-key-change-in-production":
        logger.warning("⚠️ Using default API key. Set WEB_LAUNCHER_API_KEY environment variable for security.")
    
    print("🚀 Starting AI Assistant Service Manager...")
    print("🔐 Authentication required - set WEB_LAUNCHER_API_KEY")
    print("📱 Access at: http://localhost:9000")
    print("📊 Main UI at: http://localhost:3000")
    
    uvicorn.run(app, host="0.0.0.0", port=9000)
