"""System Control API endpoints for web dashboard"""

import asyncio
import subprocess
import psutil
import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from loguru import logger

router = APIRouter(prefix="/api/system", tags=["system"])

class ServiceStatus(BaseModel):
    """Status of a service"""
    name: str
    status: str  # running, stopped, error
    pid: Optional[int] = None
    uptime: Optional[float] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    error: Optional[str] = None

class SystemStatus(BaseModel):
    """Overall system status"""
    backend: ServiceStatus
    discord_bot: ServiceStatus
    claude_code_active: bool
    terminals_active: int
    timestamp: datetime

class ServiceControl(BaseModel):
    """Service control request"""
    action: str  # start, stop, restart
    service: str  # backend, bot, all

class SystemMetrics(BaseModel):
    """Real-time system metrics"""
    cpu_percent: float
    memory_percent: float
    gpu_utilization: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    network_connections: int
    audio_level: Optional[float] = None
    vad_confidence: Optional[float] = None
    pipeline_latency_ms: Optional[float] = None

# Global state for metrics streaming
connected_websockets: List[WebSocket] = []
metrics_task: Optional[asyncio.Task] = None

async def get_backend_status() -> ServiceStatus:
    """Get backend server status"""
    try:
        # Check if backend is running
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']):
                    # Backend is running
                    p = psutil.Process(proc.info['pid'])
                    return ServiceStatus(
                        name="backend",
                        status="running",
                        pid=proc.info['pid'],
                        uptime=datetime.now().timestamp() - p.create_time(),
                        cpu_percent=p.cpu_percent(interval=0.1),
                        memory_mb=p.memory_info().rss / 1024 / 1024
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return ServiceStatus(name="backend", status="stopped")
    except Exception as e:
        logger.error(f"Error checking backend status: {e}")
        return ServiceStatus(name="backend", status="error", error=str(e))

async def get_discord_bot_status() -> ServiceStatus:
    """Get Discord bot status"""
    try:
        # Check Windows for Discord bot
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if "direct_audio_bot" in result.stdout:
            # Bot is running - extract PID
            for line in result.stdout.splitlines():
                if "python.exe" in line and "direct_audio_bot" in line:
                    parts = line.split(',')
                    if len(parts) > 1:
                        pid = int(parts[1].strip('"'))
                        return ServiceStatus(
                            name="discord_bot",
                            status="running",
                            pid=pid
                        )
        
        return ServiceStatus(name="discord_bot", status="stopped")
    except Exception as e:
        logger.error(f"Error checking Discord bot status: {e}")
        return ServiceStatus(name="discord_bot", status="error", error=str(e))

async def start_backend():
    """Start the backend server"""
    try:
        # Start in WSL
        subprocess.Popen(
            ["bash", "-c", "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && source venv/bin/activate && python main.py > startup.log 2>&1 &"],
            shell=False
        )
        await asyncio.sleep(3)  # Give it time to start
        return True
    except Exception as e:
        logger.error(f"Failed to start backend: {e}")
        return False

async def stop_backend():
    """Stop the backend server"""
    try:
        subprocess.run(["pkill", "-f", "python main.py"], shell=False)
        return True
    except Exception as e:
        logger.error(f"Failed to stop backend: {e}")
        return False

async def start_discord_bot():
    """Start the Discord bot on Windows"""
    try:
        # Use Windows command to start bot
        bot_dir = "C:\\users\\dfoss\\desktop\\localaimodels\\assistant\\WindowsDiscordBot"
        cmd = f'cd /d "{bot_dir}" && bot_venv_windows\\Scripts\\activate && python direct_audio_bot_working.py'
        
        subprocess.Popen(
            ["cmd", "/c", f"start /b {cmd}"],
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {e}")
        return False

async def stop_discord_bot():
    """Stop the Discord bot on Windows"""
    try:
        # Kill Python processes running the bot
        subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq direct_audio_bot*"],
            shell=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to stop Discord bot: {e}")
        return False

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current system status"""
    backend = await get_backend_status()
    discord_bot = await get_discord_bot_status()
    
    # Check Claude Code integration
    claude_active = False
    terminals = 0
    
    try:
        # Import if available
        from ..core.terminal_detector import terminal_detector
        sessions = terminal_detector.detect_sessions()
        claude_active = len(sessions.get("claude_code_sessions", [])) > 0
        terminals = len(sessions.get("terminals", []))
    except:
        pass
    
    return SystemStatus(
        backend=backend,
        discord_bot=discord_bot,
        claude_code_active=claude_active,
        terminals_active=terminals,
        timestamp=datetime.now()
    )

@router.post("/control")
async def control_service(request: ServiceControl):
    """Control system services"""
    success = False
    
    if request.service == "backend":
        if request.action == "start":
            success = await start_backend()
        elif request.action == "stop":
            success = await stop_backend()
        elif request.action == "restart":
            await stop_backend()
            await asyncio.sleep(2)
            success = await start_backend()
    
    elif request.service == "bot":
        if request.action == "start":
            success = await start_discord_bot()
        elif request.action == "stop":
            success = await stop_discord_bot()
        elif request.action == "restart":
            await stop_discord_bot()
            await asyncio.sleep(2)
            success = await start_discord_bot()
    
    elif request.service == "all":
        if request.action == "start":
            b1 = await start_backend()
            await asyncio.sleep(5)  # Backend needs time to initialize
            b2 = await start_discord_bot()
            success = b1 and b2
        elif request.action == "stop":
            b1 = await stop_discord_bot()
            b2 = await stop_backend()
            success = b1 and b2
        elif request.action == "restart":
            await stop_discord_bot()
            await stop_backend()
            await asyncio.sleep(3)
            b1 = await start_backend()
            await asyncio.sleep(5)
            b2 = await start_discord_bot()
            success = b1 and b2
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to {request.action} {request.service}")
    
    return {"status": "success", "action": request.action, "service": request.service}

@router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics"""
    await websocket.accept()
    connected_websockets.append(websocket)
    
    try:
        # Start metrics broadcasting if not running
        global metrics_task
        if not metrics_task or metrics_task.done():
            metrics_task = asyncio.create_task(broadcast_metrics())
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
    
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

async def get_current_metrics() -> SystemMetrics:
    """Get current system metrics"""
    metrics = SystemMetrics(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        network_connections=len(psutil.net_connections())
    )
    
    # Try to get GPU metrics
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        metrics.gpu_utilization = utilization.gpu
        metrics.gpu_memory_mb = memory_info.used / 1024 / 1024
        pynvml.nvmlShutdown()
    except:
        pass
    
    # Try to get pipeline metrics
    try:
        from ..core.pipeline_metrics import pipeline_metrics
        if hasattr(pipeline_metrics, 'get_current_stats'):
            stats = pipeline_metrics.get_current_stats()
            if 'latency' in stats:
                metrics.pipeline_latency_ms = stats['latency']['mean']
    except:
        pass
    
    return metrics

async def broadcast_metrics():
    """Broadcast metrics to all connected WebSocket clients"""
    while True:
        if connected_websockets:
            try:
                metrics = await get_current_metrics()
                message = json.dumps(metrics.dict())
                
                # Send to all connected clients
                disconnected = []
                for ws in connected_websockets:
                    try:
                        await ws.send_text(message)
                    except:
                        disconnected.append(ws)
                
                # Remove disconnected clients
                for ws in disconnected:
                    connected_websockets.remove(ws)
            
            except Exception as e:
                logger.error(f"Error broadcasting metrics: {e}")
        
        await asyncio.sleep(1)  # Update every second