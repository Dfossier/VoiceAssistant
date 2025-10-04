#!/usr/bin/env python3
"""
AI Assistant Web Launcher
Simple web interface to start/stop backend and Discord bot
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import subprocess
import os
import sys
import signal
import time
import asyncio
import psutil
from pathlib import Path
import threading
import json

class ServiceManager:
    def __init__(self):
        self.backend_process = None
        self.bot_process = None
        self.backend_path = Path(__file__).parent
        self.bot_path = Path(__file__).parent / "discordbot"
        self.logs = []
        
    def log(self, message, service="system"):
        """Add log entry"""
        timestamp = time.strftime('%H:%M:%S')
        entry = {
            "time": timestamp,
            "service": service,
            "message": message
        }
        self.logs.append(entry)
        if len(self.logs) > 100:  # Keep last 100 logs
            self.logs.pop(0)
        print(f"[{timestamp}] [{service}] {message}")
    
    def is_port_in_use(self, port):
        """Check if port is in use"""
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False
    
    def is_discord_bot_running(self):
        """Check if Discord bot is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'bot.py' in ' '.join(cmdline):
                    return True
            except:
                pass
        return False
    
    def get_status(self):
        """Get service status"""
        return {
            "backend": {
                "running": self.is_port_in_use(8000),
                "port": 8000
            },
            "bot": {
                "running": self.is_discord_bot_running(),
                "status": "Connected" if self.is_discord_bot_running() else "Disconnected"
            }
        }
    
    def start_backend(self):
        """Start backend service"""
        self.log("Starting backend API...", "backend")
        
        def run():
            try:
                os.chdir(self.backend_path)
                self.backend_process = subprocess.Popen(
                    [sys.executable, "discord_main.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    env={**os.environ, 'PORT': '8000'}
                )
                
                for line in iter(self.backend_process.stdout.readline, ''):
                    if line:
                        self.log(line.strip(), "backend")
                        
            except Exception as e:
                self.log(f"Error: {str(e)}", "backend")
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return True
    
    def start_bot(self):
        """Start Discord bot"""
        if not self.bot_path.exists():
            self.log(f"Error: Bot directory not found at {self.bot_path}", "bot")
            return False
            
        self.log("Starting Discord bot...", "bot")
        
        def run():
            try:
                os.chdir(self.bot_path)
                self.bot_process = subprocess.Popen(
                    [sys.executable, "bot.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in iter(self.bot_process.stdout.readline, ''):
                    if line:
                        self.log(line.strip(), "bot")
                        
            except Exception as e:
                self.log(f"Error: {str(e)}", "bot")
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return True
    
    def stop_backend(self):
        """Stop backend service"""
        self.log("Stopping backend...", "backend")
        
        if self.backend_process:
            self.backend_process.terminate()
            self.backend_process = None
        
        # Kill any process on port 8000
        for proc in psutil.process_iter():
            try:
                for conn in proc.connections():
                    if conn.laddr.port == 8000:
                        proc.kill()
                        self.log("Backend stopped", "backend")
                        break
            except:
                pass
    
    def stop_bot(self):
        """Stop Discord bot"""
        self.log("Stopping Discord bot...", "bot")
        
        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process = None
        
        # Kill any bot.py processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'bot.py' in ' '.join(cmdline):
                    proc.kill()
                    self.log("Bot stopped", "bot")
                    break
            except:
                pass

# Create service manager
manager = ServiceManager()

# Create FastAPI app
app = FastAPI(title="AI Assistant Launcher")

@app.get("/", response_class=HTMLResponse)
async def launcher_ui():
    """Main launcher interface"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 AI Assistant Launcher</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #1e1e1e, #2d2d2d); 
            color: #e0e0e0; 
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #60a5fa; font-size: 2.5rem; margin-bottom: 10px; }
        .header p { color: #9ca3af; font-size: 1.1rem; }
        
        .services { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        
        .service-card {
            background: #374151;
            border-radius: 12px;
            padding: 20px;
            border: 2px solid #4b5563;
        }
        
        .service-title { 
            font-size: 1.4rem; 
            font-weight: bold; 
            margin-bottom: 10px; 
            color: #60a5fa;
        }
        
        .service-status { 
            font-size: 1.1rem; 
            margin-bottom: 15px; 
            padding: 8px 12px; 
            border-radius: 6px; 
        }
        
        .status-running { background: #065f46; color: #10b981; }
        .status-stopped { background: #7f1d1d; color: #ef4444; }
        
        .controls { text-align: center; margin-bottom: 30px; }
        
        .btn {
            padding: 12px 24px;
            margin: 0 10px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 140px;
        }
        
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #059669; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-secondary { background: #6b7280; color: white; }
        .btn-secondary:hover { background: #4b5563; }
        .btn:disabled { background: #374151; color: #9ca3af; cursor: not-allowed; }
        
        .logs {
            background: #111827;
            border-radius: 8px;
            padding: 20px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }
        
        .log-entry { margin-bottom: 5px; }
        .log-backend { color: #60a5fa; }
        .log-bot { color: #10b981; }
        .log-system { color: #f59e0b; }
        
        .footer { text-align: center; margin-top: 20px; color: #6b7280; }
        
        @media (max-width: 768px) {
            .services { grid-template-columns: 1fr; }
            .controls { text-align: center; }
            .btn { margin: 5px; min-width: auto; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Assistant Launcher</h1>
            <p>Manage your Discord AI Assistant services</p>
        </div>
        
        <div class="services">
            <div class="service-card">
                <div class="service-title">🔧 Backend API</div>
                <div id="backend-status" class="service-status">⚫ Checking...</div>
                <div>Port: 8000</div>
                <div>Handles AI processing, file operations, commands</div>
            </div>
            
            <div class="service-card">
                <div class="service-title">🤖 Discord Bot</div>
                <div id="bot-status" class="service-status">⚫ Checking...</div>
                <div id="bot-info">Connecting to Discord...</div>
                <div>Provides Discord interface for the AI assistant</div>
            </div>
        </div>
        
        <div class="controls">
            <button id="start-all" class="btn btn-success">🚀 Start All</button>
            <button id="stop-all" class="btn btn-danger">⏹️ Stop All</button>
            <button id="start-backend" class="btn btn-primary">Start Backend</button>
            <button id="stop-backend" class="btn btn-secondary">Stop Backend</button>
            <button id="start-bot" class="btn btn-primary">Start Bot</button>
            <button id="stop-bot" class="btn btn-secondary">Stop Bot</button>
            <button id="refresh" class="btn btn-secondary">🔄 Refresh</button>
        </div>
        
        <div>
            <h3 style="margin-bottom: 10px; color: #e0e0e0;">📋 Service Logs</h3>
            <div id="logs" class="logs"></div>
        </div>
        
        <div class="footer">
            <p>💡 Keep this page open to monitor your services</p>
        </div>
    </div>

    <script>
        // Service control functions
        async function callAPI(endpoint, method = 'GET') {
            try {
                const response = await fetch(endpoint, { method });
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                return { error: error.message };
            }
        }
        
        async function updateStatus() {
            const status = await callAPI('/status');
            if (status.error) return;
            
            // Update backend status
            const backendEl = document.getElementById('backend-status');
            if (status.backend.running) {
                backendEl.textContent = '🟢 Running';
                backendEl.className = 'service-status status-running';
            } else {
                backendEl.textContent = '⚫ Stopped';
                backendEl.className = 'service-status status-stopped';
            }
            
            // Update bot status
            const botEl = document.getElementById('bot-status');
            const botInfo = document.getElementById('bot-info');
            if (status.bot.running) {
                botEl.textContent = '🟢 Running';
                botEl.className = 'service-status status-running';
                botInfo.textContent = 'Connected to Discord';
            } else {
                botEl.textContent = '⚫ Stopped';
                botEl.className = 'service-status status-stopped';
                botInfo.textContent = 'Not connected';
            }
            
            // Update button states
            const bothRunning = status.backend.running && status.bot.running;
            const noneRunning = !status.backend.running && !status.bot.running;
            
            document.getElementById('start-all').disabled = bothRunning;
            document.getElementById('stop-all').disabled = noneRunning;
            document.getElementById('start-backend').disabled = status.backend.running;
            document.getElementById('stop-backend').disabled = !status.backend.running;
            document.getElementById('start-bot').disabled = status.bot.running;
            document.getElementById('stop-bot').disabled = !status.bot.running;
        }
        
        async function updateLogs() {
            const logs = await callAPI('/logs');
            if (logs.error) return;
            
            const logsEl = document.getElementById('logs');
            logsEl.innerHTML = '';
            
            logs.forEach(log => {
                const entry = document.createElement('div');
                entry.className = `log-entry log-${log.service}`;
                entry.textContent = `[${log.time}] [${log.service}] ${log.message}`;
                logsEl.appendChild(entry);
            });
            
            logsEl.scrollTop = logsEl.scrollHeight;
        }
        
        // Button event listeners
        document.getElementById('start-all').onclick = () => callAPI('/start-all', 'POST');
        document.getElementById('stop-all').onclick = () => callAPI('/stop-all', 'POST');
        document.getElementById('start-backend').onclick = () => callAPI('/start-backend', 'POST');
        document.getElementById('stop-backend').onclick = () => callAPI('/stop-backend', 'POST');
        document.getElementById('start-bot').onclick = () => callAPI('/start-bot', 'POST');
        document.getElementById('stop-bot').onclick = () => callAPI('/stop-bot', 'POST');
        document.getElementById('refresh').onclick = () => { updateStatus(); updateLogs(); };
        
        // Auto-update every 3 seconds
        setInterval(() => {
            updateStatus();
            updateLogs();
        }, 3000);
        
        // Initial load
        updateStatus();
        updateLogs();
    </script>
</body>
</html>""")

@app.get("/status")
async def get_status():
    """Get service status"""
    return manager.get_status()

@app.get("/logs")
async def get_logs(limit: int = 50):
    """Get service logs with pagination"""
    try:
        if not hasattr(manager, 'logs') or not isinstance(manager.logs, list):
            return {"logs": [], "error": "Logs not available"}
        
        # Validate and filter logs
        valid_logs = []
        for log in manager.logs:
            if isinstance(log, dict) and all(k in log for k in ['time', 'service', 'message']):
                valid_logs.append(log)
        
        # Return most recent logs up to limit
        recent_logs = valid_logs[-limit:] if len(valid_logs) > limit else valid_logs
        
        return {
            "logs": recent_logs,
            "total": len(valid_logs),
            "returned": len(recent_logs),
            "limit": limit
        }
    except Exception as e:
        return {"logs": [], "error": f"Failed to retrieve logs: {str(e)}"}

@app.post("/start-all")
async def start_all():
    """Start all services"""
    try:
        # Start backend first, then wait, then start bot
        manager.start_backend()
        await asyncio.sleep(2)
        manager.start_bot()
        return {"message": "Starting all services"}
    except Exception as e:
        return {"error": f"Failed to start services: {str(e)}"}
