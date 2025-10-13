#!/usr/bin/env python3
"""
Simple, stable API server - no complex WebSocket, just basic control
"""

import os
import sys
from pathlib import Path
import asyncio
import subprocess
import psutil
from datetime import datetime
from typing import Optional

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment
load_dotenv()

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {message}")

class ServiceStatus(BaseModel):
    name: str
    status: str
    pid: Optional[int] = None
    uptime: Optional[float] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    error: Optional[str] = None

class SystemStatus(BaseModel):
    backend: ServiceStatus
    discord_bot: ServiceStatus
    voice_pipeline: ServiceStatus
    claude_code_active: bool = False
    terminals_active: int = 0
    timestamp: str

class ServiceControl(BaseModel):
    action: str
    service: str

def check_process_running(pattern: str) -> Optional[dict]:
    """Check if process is running"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_info']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if pattern in cmdline:
                    uptime = datetime.now().timestamp() - proc.info['create_time']
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    
                    return {
                        "pid": proc.info['pid'],
                        "uptime": uptime,
                        "cpu_percent": proc.info['cpu_percent'],
                        "memory_mb": memory_mb
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None
    except Exception:
        return None

def get_service_status(service: str) -> ServiceStatus:
    """Get service status"""
    patterns = {
        "backend": "run_api",
        "voice": "run_voice_simple.py",  # Updated to match the actual script
        "bot": "direct_audio_bot"
    }
    
    pattern = patterns.get(service, service)
    proc_info = check_process_running(pattern)
    
    if proc_info:
        return ServiceStatus(
            name=service,
            status="running",
            pid=proc_info["pid"],
            uptime=proc_info["uptime"],
            cpu_percent=proc_info["cpu_percent"],
            memory_mb=proc_info["memory_mb"]
        )
    else:
        return ServiceStatus(name=service, status="stopped")

app = FastAPI(title="Simple AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "simple_api"}

@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status():
    """Get system status"""
    logger.info("Status request received")
    
    backend = get_service_status("backend")
    voice_pipeline = get_service_status("voice") 
    discord_bot = get_service_status("bot")
    
    # Simple Claude Code check
    claude_code_active = False
    terminals_active = 0
    
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            cmdline = ' '.join(proc.info['cmdline'] or []).lower()
            if 'claude' in cmdline:
                claude_code_active = True
            if proc.info['name'] in ['bash', 'zsh', 'cmd.exe']:
                terminals_active += 1
    except:
        pass
    
    return SystemStatus(
        backend=backend,
        discord_bot=discord_bot,
        voice_pipeline=voice_pipeline,
        claude_code_active=claude_code_active,
        terminals_active=terminals_active,
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/system/logs")
async def get_system_logs():
    """Get recent system logs from actual files"""
    logs = []
    current_time = datetime.now().isoformat()
    
    # Define log sources to read
    log_sources = [
        ("voice_pipeline_running.log", "Voice"),
        ("voice_simple.log", "Voice"),
        ("WindowsDiscordBot/bot_output.log", "Discord"),
        ("WindowsDiscordBot/logs/discord_bot.log", "Discord"),
        ("api_simple_fixed.log", "API"),
        ("backend.log", "Backend")
    ]
    
    for log_file, component in log_sources:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-30:]  # Last 30 lines
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 10:  # Skip very short lines
                            # Extract level from line
                            level = "INFO"
                            if any(term in line.upper() for term in ["ERROR", "FAILED", "EXCEPTION", "TRACEBACK"]):
                                level = "ERROR"
                            elif any(term in line.upper() for term in ["WARNING", "WARN"]):
                                level = "WARNING"
                            elif "DEBUG" in line.upper():
                                level = "DEBUG"
                            
                            # Extract timestamp if present or use current time
                            timestamp = current_time
                            if " - " in line and ":" in line:
                                parts = line.split(" - ", 1)
                                if len(parts) > 1:
                                    timestamp_part = parts[0]
                                    if "," in timestamp_part:
                                        timestamp = timestamp_part.split(",")[0]
                            
                            logs.append({
                                "timestamp": timestamp,
                                "level": level,
                                "component": component,
                                "message": line[:300]  # Limit message length
                            })
            except Exception as e:
                logs.append({
                    "timestamp": current_time,
                    "level": "ERROR",
                    "component": "LogReader",
                    "message": f"Failed to read {log_file}: {str(e)[:100]}"
                })
    
    # Add system status
    logs.append({
        "timestamp": current_time,
        "level": "INFO",
        "component": "System",
        "message": f"Dashboard API running - {len(connected_websockets)} connections - {len(logs)} log entries collected"
    })
    
    # Sort by timestamp (most recent first) and limit
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {"logs": logs[-100:]}

@app.post("/api/system/control")
async def control_service(request: ServiceControl):
    """Control services - simplified version"""
    logger.info(f"Control request: {request.action} {request.service}")
    
    try:
        if request.service == "voice":
            if request.action == "start":
                logger.info("Starting voice pipeline...")
                subprocess.Popen([
                    "bash", "-c",
                    f"cd {os.path.dirname(__file__)} && "
                    "source venv/bin/activate && "
                    "python run_voice_simple.py > voice_simple.log 2>&1 &"
                ])
                await asyncio.sleep(2)
                
            elif request.action == "stop":
                logger.info("Stopping voice pipeline...")
                subprocess.run(["pkill", "-f", "run_voice_simple.py"])
                await asyncio.sleep(1)
                
            elif request.action == "restart":
                logger.info("Restarting voice pipeline...")
                subprocess.run(["pkill", "-f", "run_voice_simple.py"])
                await asyncio.sleep(2)
                subprocess.Popen([
                    "bash", "-c",
                    f"cd {os.path.dirname(__file__)} && "
                    "source venv/bin/activate && "
                    "python run_voice_simple.py > voice_simple.log 2>&1 &"
                ])
                await asyncio.sleep(2)
                
        elif request.service == "bot":
            if request.action == "start":
                logger.info("Starting Discord bot...")
                # Try to start Discord bot
                subprocess.Popen([
                    "cmd.exe", "/c",
                    "cd C:\\users\\dfoss\\desktop\\localaimodels\\assistant\\WindowsDiscordBot && "
                    "bot_venv_windows\\Scripts\\python direct_audio_bot_working.py"
                ])
                await asyncio.sleep(2)
                
            elif request.action == "stop":
                logger.info("Stopping Discord bot...")
                subprocess.run([
                    "cmd.exe", "/c",
                    "taskkill /F /IM python.exe /FI \"WINDOWTITLE eq *direct_audio*\""
                ])
                await asyncio.sleep(1)
                
        elif request.service == "backend":
            logger.warning("Cannot control backend from itself")
            
        return {"status": "success", "action": request.action, "service": request.service}
        
    except Exception as e:
        logger.error(f"Control error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

connected_websockets = []

@app.websocket("/api/system/ws/metrics")
async def simple_metrics_websocket(websocket: WebSocket):
    """Simple WebSocket that won't crash"""
    try:
        await websocket.accept()
        connected_websockets.append(websocket)
        logger.info("WebSocket connected")
        
        # Send basic data every few seconds
        while True:
            await asyncio.sleep(3)
            
            # Send simple metrics - using real system data only
            metrics = {
                "type": "metrics",
                "payload": {
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "network_connections": len(psutil.net_connections()),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            try:
                await websocket.send_json(metrics)
            except:
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    logger.info("🚀 Starting Simple API Server")
    logger.info("📝 No complex WebSocket - just basic HTTP API")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )