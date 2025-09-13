"""
Central Service Management Interface
Manages both WSL Backend and Windows Discord Bot
"""
import asyncio
import subprocess
import psutil
import json
import time
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ServiceStatus:
    """Service status information"""
    name: str
    status: str  # "running", "stopped", "error", "unknown"
    pid: Optional[int] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    uptime: Optional[str] = None
    last_updated: str = ""
    log_file: Optional[str] = None
    port: Optional[int] = None
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().strftime("%H:%M:%S")

class ServiceManager:
    """Manages WSL Backend and Windows Discord Bot services"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.services = {}
        self.update_interval = 5  # seconds
        
        # Service definitions
        self.service_configs = {
            "wsl_backend": {
                "name": "WSL Backend API",
                "command": ["wsl", "-d", "Ubuntu", "bash", "-c", "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"],
                "cwd": str(self.project_root),
                "log_file": str(self.project_root / "backend.log"),
                "port": 8000,
                "health_url": "http://localhost:8000/health"
            },
            "windows_discord_bot": {
                "name": "Windows Discord Bot",
                "command": ["python", "bot.py"],
                "cwd": str(self.project_root / "WindowsDiscordBot"),
                "log_file": str(self.project_root / "WindowsDiscordBot" / "logs" / "discord_bot.log"),
                "port": None,
                "health_url": None
            }
        }
        
        # Tracked processes
        self.processes = {}
        self.process_start_times = {}
    
    async def get_service_status(self, service_id: str) -> ServiceStatus:
        """Get current status of a service"""
        config = self.service_configs.get(service_id)
        if not config:
            return ServiceStatus(service_id, "unknown")
        
        process = self.processes.get(service_id)
        
        if process and process.poll() is None:
            # Process is running
            try:
                # Get process info
                ps_process = psutil.Process(process.pid)
                cpu_percent = ps_process.cpu_percent()
                memory_mb = ps_process.memory_info().rss / 1024 / 1024
                
                # Calculate uptime
                start_time = self.process_start_times.get(service_id)
                uptime = None
                if start_time:
                    uptime_seconds = time.time() - start_time
                    uptime = f"{int(uptime_seconds // 60)}m {int(uptime_seconds % 60)}s"
                
                return ServiceStatus(
                    name=config["name"],
                    status="running",
                    pid=process.pid,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    uptime=uptime,
                    log_file=config.get("log_file"),
                    port=config.get("port")
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process died
                self.processes[service_id] = None
                return ServiceStatus(
                    name=config["name"],
                    status="stopped",
                    log_file=config.get("log_file"),
                    port=config.get("port")
                )
        else:
            return ServiceStatus(
                name=config["name"],
                status="stopped",
                log_file=config.get("log_file"),
                port=config.get("port")
            )
    
    async def start_service(self, service_id: str) -> bool:
        """Start a service"""
        config = self.service_configs.get(service_id)
        if not config:
            logger.error(f"Unknown service: {service_id}")
            return False
        
        # Check if already running
        status = await self.get_service_status(service_id)
        if status.status == "running":
            logger.info(f"Service {service_id} is already running")
            return True
        
        try:
            logger.info(f"Starting service: {config['name']}")
            
            # Ensure log directory exists
            log_file = config.get("log_file")
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Start process
            process = subprocess.Popen(
                config["command"],
                cwd=config.get("cwd"),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            self.processes[service_id] = process
            self.process_start_times[service_id] = time.time()
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if it's still running
            if process.poll() is None:
                logger.info(f"Successfully started {config['name']} (PID: {process.pid})")
                return True
            else:
                logger.error(f"Failed to start {config['name']} - process exited immediately")
                return False
                
        except Exception as e:
            logger.error(f"Error starting {config['name']}: {e}")
            return False
    
    async def stop_service(self, service_id: str) -> bool:
        """Stop a service"""
        config = self.service_configs.get(service_id)
        if not config:
            logger.error(f"Unknown service: {service_id}")
            return False
        
        process = self.processes.get(service_id)
        if not process or process.poll() is not None:
            logger.info(f"Service {service_id} is not running")
            return True
        
        try:
            logger.info(f"Stopping service: {config['name']}")
            
            # Try graceful shutdown first
            process.terminate()
            
            # Wait up to 10 seconds for graceful shutdown
            try:
                process.wait(timeout=10)
                logger.info(f"Successfully stopped {config['name']}")
            except subprocess.TimeoutExpired:
                # Force kill
                logger.warning(f"Force killing {config['name']}")
                process.kill()
                process.wait()
                logger.info(f"Force killed {config['name']}")
            
            self.processes[service_id] = None
            if service_id in self.process_start_times:
                del self.process_start_times[service_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping {config['name']}: {e}")
            return False
    
    async def restart_service(self, service_id: str) -> bool:
        """Restart a service"""
        logger.info(f"Restarting service: {service_id}")
        if await self.stop_service(service_id):
            await asyncio.sleep(2)
            return await self.start_service(service_id)
        return False
    
    async def get_all_statuses(self) -> Dict[str, ServiceStatus]:
        """Get status of all services"""
        statuses = {}
        for service_id in self.service_configs:
            statuses[service_id] = await self.get_service_status(service_id)
        return statuses
    
    def get_log_tail(self, service_id: str, lines: int = 50) -> List[str]:
        """Get last N lines from service log"""
        config = self.service_configs.get(service_id)
        if not config or not config.get("log_file"):
            return []
        
        log_file = Path(config["log_file"])
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines_list = f.readlines()
                return lines_list[-lines:]
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return [f"Error reading log: {e}"]


class ServiceManagerGUI:
    """GUI for Service Manager"""
    
    def __init__(self):
        self.service_manager = ServiceManager()
        self.root = tk.Tk()
        self.root.title("AI Assistant Service Manager")
        self.root.geometry("1000x700")
        
        # Update queue for thread-safe GUI updates
        self.update_queue = queue.Queue()
        
        # Create GUI
        self.create_widgets()
        
        # Start update thread
        self.running = True
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="AI Assistant Service Manager", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Services frame
        services_frame = ttk.LabelFrame(main_frame, text="Services", padding="10")
        services_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        services_frame.columnconfigure(0, weight=1)
        
        # Service status display
        self.service_tree = ttk.Treeview(services_frame, columns=("status", "pid", "cpu", "memory", "uptime", "port"), 
                                        show="tree headings", height=4)
        self.service_tree.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Configure columns
        self.service_tree.heading("#0", text="Service")
        self.service_tree.heading("status", text="Status")
        self.service_tree.heading("pid", text="PID")
        self.service_tree.heading("cpu", text="CPU %")
        self.service_tree.heading("memory", text="Memory MB")
        self.service_tree.heading("uptime", text="Uptime")
        self.service_tree.heading("port", text="Port")
        
        self.service_tree.column("#0", width=200)
        self.service_tree.column("status", width=80)
        self.service_tree.column("pid", width=60)
        self.service_tree.column("cpu", width=60)
        self.service_tree.column("memory", width=80)
        self.service_tree.column("uptime", width=80)
        self.service_tree.column("port", width=60)
        
        # Control buttons
        button_frame = ttk.Frame(services_frame)
        button_frame.grid(row=1, column=0, columnspan=4, pady=(0, 10))
        
        self.start_btn = ttk.Button(button_frame, text="Start", command=self.start_selected)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_selected)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.restart_btn = ttk.Button(button_frame, text="Restart", command=self.restart_selected)
        self.restart_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        self.start_all_btn = ttk.Button(button_frame, text="Start All", command=self.start_all)
        self.start_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_all_btn = ttk.Button(button_frame, text="Stop All", command=self.stop_all)
        self.stop_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Log viewer
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # Log service selector
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(log_control_frame, text="Service:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.log_service_var = tk.StringVar()
        self.log_service_combo = ttk.Combobox(log_control_frame, textvariable=self.log_service_var, 
                                             values=list(self.service_manager.service_configs.keys()))
        self.log_service_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.log_service_combo.bind("<<ComboboxSelected>>", self.on_log_service_changed)
        
        ttk.Button(log_control_frame, text="Refresh Logs", command=self.refresh_logs).pack(side=tk.LEFT)
        
        # Log display
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Initialize
        self.update_service_display()
        if self.service_manager.service_configs:
            self.log_service_var.set(list(self.service_manager.service_configs.keys())[0])
            self.refresh_logs()
    
    def update_loop(self):
        """Background update loop"""
        while self.running:
            try:
                # Get current statuses
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                statuses = loop.run_until_complete(self.service_manager.get_all_statuses())
                loop.close()
                
                # Queue update
                self.update_queue.put(("status_update", statuses))
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(10)  # Wait longer on error
    
    def process_updates(self):
        """Process queued updates"""
        try:
            while True:
                update_type, data = self.update_queue.get_nowait()
                
                if update_type == "status_update":
                    self.update_service_display(data)
                elif update_type == "status_message":
                    self.status_var.set(data)
                    
        except queue.Empty:
            pass
        
        # Schedule next update
        self.root.after(1000, self.process_updates)
    
    def update_service_display(self, statuses=None):
        """Update the service display"""
        if statuses is None:
            # Get current statuses synchronously for initial display
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            statuses = loop.run_until_complete(self.service_manager.get_all_statuses())
            loop.close()
        
        # Clear existing items
        for item in self.service_tree.get_children():
            self.service_tree.delete(item)
        
        # Add services
        for service_id, status in statuses.items():
            # Color coding based on status
            tag = "running" if status.status == "running" else "stopped"
            
            self.service_tree.insert("", "end", 
                                   text=status.name,
                                   values=(
                                       status.status,
                                       status.pid or "",
                                       f"{status.cpu_percent:.1f}" if status.cpu_percent else "",
                                       f"{status.memory_mb:.1f}" if status.memory_mb else "",
                                       status.uptime or "",
                                       status.port or ""
                                   ),
                                   tags=(tag,))
        
        # Configure tags
        self.service_tree.tag_configure("running", foreground="green")
        self.service_tree.tag_configure("stopped", foreground="red")
    
    def get_selected_service(self):
        """Get currently selected service ID"""
        selection = self.service_tree.selection()
        if not selection:
            return None
        
        item = self.service_tree.item(selection[0])
        service_name = item["text"]
        
        # Find service ID by name
        for service_id, config in self.service_manager.service_configs.items():
            if config["name"] == service_name:
                return service_id
        return None
    
    def start_selected(self):
        """Start selected service"""
        service_id = self.get_selected_service()
        if service_id:
            threading.Thread(target=self.async_start_service, args=(service_id,), daemon=True).start()
    
    def stop_selected(self):
        """Stop selected service"""
        service_id = self.get_selected_service()
        if service_id:
            threading.Thread(target=self.async_stop_service, args=(service_id,), daemon=True).start()
    
    def restart_selected(self):
        """Restart selected service"""
        service_id = self.get_selected_service()
        if service_id:
            threading.Thread(target=self.async_restart_service, args=(service_id,), daemon=True).start()
    
    def start_all(self):
        """Start all services"""
        threading.Thread(target=self.async_start_all, daemon=True).start()
    
    def stop_all(self):
        """Stop all services"""
        if messagebox.askyesno("Confirm", "Stop all services?"):
            threading.Thread(target=self.async_stop_all, daemon=True).start()
    
    def async_start_service(self, service_id):
        """Async start service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.update_queue.put(("status_message", f"Starting {service_id}..."))
        success = loop.run_until_complete(self.service_manager.start_service(service_id))
        
        if success:
            self.update_queue.put(("status_message", f"Started {service_id}"))
        else:
            self.update_queue.put(("status_message", f"Failed to start {service_id}"))
        
        loop.close()
    
    def async_stop_service(self, service_id):
        """Async stop service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.update_queue.put(("status_message", f"Stopping {service_id}..."))
        success = loop.run_until_complete(self.service_manager.stop_service(service_id))
        
        if success:
            self.update_queue.put(("status_message", f"Stopped {service_id}"))
        else:
            self.update_queue.put(("status_message", f"Failed to stop {service_id}"))
        
        loop.close()
    
    def async_restart_service(self, service_id):
        """Async restart service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.update_queue.put(("status_message", f"Restarting {service_id}..."))
        success = loop.run_until_complete(self.service_manager.restart_service(service_id))
        
        if success:
            self.update_queue.put(("status_message", f"Restarted {service_id}"))
        else:
            self.update_queue.put(("status_message", f"Failed to restart {service_id}"))
        
        loop.close()
    
    def async_start_all(self):
        """Async start all services"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.update_queue.put(("status_message", "Starting all services..."))
        
        for service_id in self.service_manager.service_configs:
            success = loop.run_until_complete(self.service_manager.start_service(service_id))
            if not success:
                self.update_queue.put(("status_message", f"Failed to start {service_id}"))
                break
        else:
            self.update_queue.put(("status_message", "All services started"))
        
        loop.close()
    
    def async_stop_all(self):
        """Async stop all services"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.update_queue.put(("status_message", "Stopping all services..."))
        
        for service_id in self.service_manager.service_configs:
            success = loop.run_until_complete(self.service_manager.stop_service(service_id))
            if not success:
                self.update_queue.put(("status_message", f"Failed to stop {service_id}"))
        
        self.update_queue.put(("status_message", "All services stopped"))
        loop.close()
    
    def on_log_service_changed(self, event=None):
        """Called when log service selection changes"""
        self.refresh_logs()
    
    def refresh_logs(self):
        """Refresh log display"""
        service_id = self.log_service_var.get()
        if not service_id:
            return
        
        lines = self.service_manager.get_log_tail(service_id, 100)
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        for line in lines:
            self.log_text.insert(tk.END, line)
        
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
    
    def on_closing(self):
        """Handle window closing"""
        if messagebox.askyesno("Quit", "Stop all services and quit?"):
            self.running = False
            
            # Stop all services
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            for service_id in self.service_manager.service_configs:
                loop.run_until_complete(self.service_manager.stop_service(service_id))
            loop.close()
            
            self.root.destroy()
    
    def run(self):
        """Start the GUI"""
        self.process_updates()  # Start update processing
        self.root.mainloop()


if __name__ == "__main__":
    try:
        gui = ServiceManagerGUI()
        gui.run()
    except KeyboardInterrupt:
        logger.info("Service manager interrupted")
    except Exception as e:
        logger.error(f"Service manager error: {e}")
        messagebox.showerror("Error", f"Service manager error: {e}")