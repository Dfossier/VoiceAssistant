#!/usr/bin/env python3
"""
AI Assistant Service Launcher
Simple GUI to start/stop backend and Discord bot
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import os
import sys
import threading
import signal
import time
from pathlib import Path
import psutil

class ServiceLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Assistant Launcher")
        self.root.geometry("800x600")
        self.root.configure(bg='#2b2b2b')
        
        # Process references
        self.backend_process = None
        self.bot_process = None
        
        # Paths
        self.backend_path = Path(__file__).parent
        self.bot_path = Path(__file__).parent / "discordbot"
        
        # Create UI
        self.setup_ui()
        
        # Check initial status
        self.check_status()
        
    def setup_ui(self):
        """Create the user interface"""
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#2b2b2b', foreground='#60a5fa')
        style.configure('Status.TLabel', font=('Arial', 12), background='#2b2b2b', foreground='white')
        
        # Title
        title = ttk.Label(self.root, text="🤖 AI Assistant Service Manager", style='Title.TLabel')
        title.pack(pady=10)
        
        # Status Frame
        status_frame = tk.Frame(self.root, bg='#2b2b2b')
        status_frame.pack(fill='x', padx=20, pady=10)
        
        # Backend Status
        backend_frame = tk.Frame(status_frame, bg='#1a1a1a', relief='groove', bd=2)
        backend_frame.pack(side='left', expand=True, fill='both', padx=5)
        
        tk.Label(backend_frame, text="Backend API", font=('Arial', 14, 'bold'), 
                bg='#1a1a1a', fg='#60a5fa').pack(pady=5)
        
        self.backend_status = tk.Label(backend_frame, text="⚫ Stopped", font=('Arial', 12),
                                     bg='#1a1a1a', fg='#ef4444')
        self.backend_status.pack()
        
        self.backend_port = tk.Label(backend_frame, text="Port: 8000", font=('Arial', 10),
                                   bg='#1a1a1a', fg='gray')
        self.backend_port.pack()
        
        # Bot Status
        bot_frame = tk.Frame(status_frame, bg='#1a1a1a', relief='groove', bd=2)
        bot_frame.pack(side='right', expand=True, fill='both', padx=5)
        
        tk.Label(bot_frame, text="Discord Bot", font=('Arial', 14, 'bold'),
                bg='#1a1a1a', fg='#60a5fa').pack(pady=5)
        
        self.bot_status = tk.Label(bot_frame, text="⚫ Stopped", font=('Arial', 12),
                                 bg='#1a1a1a', fg='#ef4444')
        self.bot_status.pack()
        
        self.bot_info = tk.Label(bot_frame, text="Not connected", font=('Arial', 10),
                               bg='#1a1a1a', fg='gray')
        self.bot_info.pack()
        
        # Control Buttons
        button_frame = tk.Frame(self.root, bg='#2b2b2b')
        button_frame.pack(pady=20)
        
        self.start_all_btn = tk.Button(button_frame, text="🚀 Start All Services",
                                      command=self.start_all, font=('Arial', 12, 'bold'),
                                      bg='#10b981', fg='white', padx=20, pady=10)
        self.start_all_btn.grid(row=0, column=0, padx=5)
        
        self.stop_all_btn = tk.Button(button_frame, text="⏹️ Stop All Services",
                                     command=self.stop_all, font=('Arial', 12, 'bold'),
                                     bg='#ef4444', fg='white', padx=20, pady=10,
                                     state='disabled')
        self.stop_all_btn.grid(row=0, column=1, padx=5)
        
        # Individual controls
        individual_frame = tk.Frame(self.root, bg='#2b2b2b')
        individual_frame.pack()
        
        self.start_backend_btn = tk.Button(individual_frame, text="Start Backend",
                                         command=self.start_backend, font=('Arial', 10),
                                         bg='#3b82f6', fg='white', padx=10, pady=5)
        self.start_backend_btn.grid(row=0, column=0, padx=5)
        
        self.stop_backend_btn = tk.Button(individual_frame, text="Stop Backend",
                                        command=self.stop_backend, font=('Arial', 10),
                                        bg='#dc2626', fg='white', padx=10, pady=5,
                                        state='disabled')
        self.stop_backend_btn.grid(row=0, column=1, padx=5)
        
        self.start_bot_btn = tk.Button(individual_frame, text="Start Bot",
                                      command=self.start_bot, font=('Arial', 10),
                                      bg='#3b82f6', fg='white', padx=10, pady=5)
        self.start_bot_btn.grid(row=0, column=2, padx=5)
        
        self.stop_bot_btn = tk.Button(individual_frame, text="Stop Bot",
                                     command=self.stop_bot, font=('Arial', 10),
                                     bg='#dc2626', fg='white', padx=10, pady=5,
                                     state='disabled')
        self.stop_bot_btn.grid(row=0, column=3, padx=5)
        
        # Log output
        log_frame = tk.Frame(self.root, bg='#2b2b2b')
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        tk.Label(log_frame, text="📋 Service Logs", font=('Arial', 12, 'bold'),
                bg='#2b2b2b', fg='white').pack(anchor='w')
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, bg='#0a0a0a', 
                                                 fg='#10b981', font=('Consolas', 10))
        self.log_text.pack(fill='both', expand=True)
        
        # Footer
        footer_frame = tk.Frame(self.root, bg='#2b2b2b')
        footer_frame.pack(fill='x', padx=20, pady=5)
        
        self.refresh_btn = tk.Button(footer_frame, text="🔄 Refresh Status",
                                   command=self.check_status, font=('Arial', 10),
                                   bg='#6366f1', fg='white', padx=10, pady=5)
        self.refresh_btn.pack(side='right')
        
        tk.Label(footer_frame, text="💡 Tip: Check logs for any errors",
                font=('Arial', 10), bg='#2b2b2b', fg='gray').pack(side='left')
    
    def log(self, message, level='info'):
        """Add message to log display"""
        timestamp = time.strftime('%H:%M:%S')
        
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
        # Color coding
        if 'error' in message.lower() or 'failed' in message.lower():
            self.log_text.tag_add('error', f'end-2l linestart', 'end-1l')
            self.log_text.tag_config('error', foreground='#ef4444')
        elif 'success' in message.lower() or 'started' in message.lower():
            self.log_text.tag_add('success', f'end-2l linestart', 'end-1l')
            self.log_text.tag_config('success', foreground='#10b981')
            
    def check_status(self):
        """Check if services are running"""
        # Check backend
        backend_running = self.is_port_in_use(8000)
        if backend_running:
            self.backend_status.config(text="🟢 Running", fg='#10b981')
            self.start_backend_btn.config(state='disabled')
            self.stop_backend_btn.config(state='normal')
        else:
            self.backend_status.config(text="⚫ Stopped", fg='#ef4444')
            self.start_backend_btn.config(state='normal')
            self.stop_backend_btn.config(state='disabled')
        
        # Check bot
        bot_running = self.is_discord_bot_running()
        if bot_running:
            self.bot_status.config(text="🟢 Running", fg='#10b981')
            self.bot_info.config(text="Connected to Discord")
            self.start_bot_btn.config(state='disabled')
            self.stop_bot_btn.config(state='normal')
        else:
            self.bot_status.config(text="⚫ Stopped", fg='#ef4444')
            self.bot_info.config(text="Not connected")
            self.start_bot_btn.config(state='normal')
            self.stop_bot_btn.config(state='disabled')
        
        # Update main buttons
        if backend_running and bot_running:
            self.start_all_btn.config(state='disabled')
            self.stop_all_btn.config(state='normal')
        elif not backend_running and not bot_running:
            self.start_all_btn.config(state='normal')
            self.stop_all_btn.config(state='disabled')
    
    def is_port_in_use(self, port):
        """Check if a port is in use"""
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
    
    def start_backend(self):
        """Start the backend service"""
        self.log("Starting backend API...")
        
        def run_backend():
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
                        self.log(f"[Backend] {line.strip()}")
                        if "Uvicorn running on" in line:
                            self.root.after(0, self.check_status)
                            
            except Exception as e:
                self.log(f"Backend error: {str(e)}", 'error')
        
        thread = threading.Thread(target=run_backend, daemon=True)
        thread.start()
        
    def start_bot(self):
        """Start the Discord bot"""
        if not self.bot_path.exists():
            self.log(f"Error: Bot directory not found at {self.bot_path}", 'error')
            return
            
        self.log("Starting Discord bot...")
        
        def run_bot():
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
                        self.log(f"[Bot] {line.strip()}")
                        if "is now online" in line:
                            self.root.after(0, self.check_status)
                            
            except Exception as e:
                self.log(f"Bot error: {str(e)}", 'error')
        
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
    
    def stop_backend(self):
        """Stop the backend service"""
        self.log("Stopping backend...")
        
        if self.backend_process:
            self.backend_process.terminate()
            self.backend_process = None
        
        # Kill any process on port 8000
        for proc in psutil.process_iter():
            try:
                for conn in proc.connections():
                    if conn.laddr.port == 8000:
                        proc.kill()
                        self.log("Backend stopped successfully")
                        break
            except:
                pass
        
        self.check_status()
    
    def stop_bot(self):
        """Stop the Discord bot"""
        self.log("Stopping Discord bot...")
        
        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process = None
        
        # Kill any bot.py processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'bot.py' in ' '.join(cmdline):
                    proc.kill()
                    self.log("Bot stopped successfully")
                    break
            except:
                pass
        
        self.check_status()
    
    def start_all(self):
        """Start all services"""
        self.log("Starting all services...")
        self.start_backend()
        time.sleep(2)  # Give backend time to start
        self.start_bot()
    
    def stop_all(self):
        """Stop all services"""
        self.log("Stopping all services...")
        self.stop_bot()
        self.stop_backend()
    
    def run(self):
        """Run the launcher"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close"""
        if self.backend_process or self.bot_process:
            if tk.messagebox.askyesno("Quit", "Services are running. Stop them before exiting?"):
                self.stop_all()
        self.root.destroy()

if __name__ == "__main__":
    # Check if tkinter is available
    try:
        import tkinter
        launcher = ServiceLauncher()
        launcher.run()
    except ImportError:
        print("❌ Tkinter not available. Creating command-line launcher instead...")
        # Fallback to CLI launcher
        import subprocess
        print("AI Assistant Launcher (CLI Mode)")
        print("1. Start Backend")
        print("2. Start Bot") 
        print("3. Start All")
        print("4. Stop All")
        choice = input("Enter choice: ")
        
        if choice in ['1', '3']:
            subprocess.Popen([sys.executable, "discord_main.py"])
        if choice in ['2', '3']:
            subprocess.Popen([sys.executable, "discordbot/bot.py"])
        if choice == '4':
            os.system("pkill -f discord_main.py")
            os.system("pkill -f bot.py")