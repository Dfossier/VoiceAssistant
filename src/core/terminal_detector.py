"""Terminal and Claude Code Session Detector

Detects active terminal windows, Claude Code sessions, and command line interfaces
across WSL2 and Windows environments for better integration.
"""

import os
import subprocess
import json
import psutil
import platform
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from loguru import logger


class TerminalDetector:
    """Detects active terminal sessions and Claude Code instances"""
    
    def __init__(self):
        self.platform = platform.system()
        self.is_wsl = os.path.exists("/proc/version") and "microsoft" in open("/proc/version").read().lower()
        self.terminals_found = []
        self.claude_sessions = []
        
    def detect_all_sessions(self) -> Dict[str, Any]:
        """Detect all active terminal and Claude Code sessions"""
        result = {
            "platform": self.platform,
            "is_wsl": self.is_wsl,
            "terminals": [],
            "claude_code_sessions": [],
            "active_processes": [],
            "detection_time": datetime.now().isoformat()
        }
        
        try:
            # Detect terminals
            result["terminals"] = self._detect_terminals()
            
            # Detect Claude Code sessions
            result["claude_code_sessions"] = self._detect_claude_code()
            
            # Detect relevant processes
            result["active_processes"] = self._detect_relevant_processes()
            
            logger.info(f"✅ Detected {len(result['terminals'])} terminals, {len(result['claude_code_sessions'])} Claude Code sessions")
            
        except Exception as e:
            logger.error(f"❌ Error detecting sessions: {e}")
            
        return result
    
    def _detect_terminals(self) -> List[Dict[str, Any]]:
        """Detect active terminal windows"""
        terminals = []
        
        try:
            # Detect WSL terminals
            if self.is_wsl:
                # Check for Windows Terminal sessions via PowerShell
                ps_command = """
                Get-Process | Where-Object {$_.ProcessName -match 'WindowsTerminal|wt|cmd|powershell|pwsh'} | 
                Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json
                """
                
                try:
                    result = subprocess.run(
                        ["powershell.exe", "-Command", ps_command],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        windows_terminals = json.loads(result.stdout)
                        if isinstance(windows_terminals, dict):
                            windows_terminals = [windows_terminals]
                            
                        for term in windows_terminals:
                            if term.get("MainWindowTitle"):
                                terminals.append({
                                    "type": "windows_terminal",
                                    "pid": term["Id"],
                                    "name": term["ProcessName"],
                                    "title": term["MainWindowTitle"],
                                    "platform": "windows"
                                })
                except Exception as e:
                    logger.debug(f"Could not detect Windows terminals: {e}")
            
            # Detect Linux/WSL terminals using process scanning
            seen_ppids = set()
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'environ']):
                try:
                    pinfo = proc.info
                    name = pinfo['name'].lower()
                    ppid = pinfo.get('ppid', None)
                    
                    # Common terminal emulators and shells
                    terminal_names = ['gnome-terminal', 'konsole', 'xterm', 'urxvt', 'alacritty', 
                                    'kitty', 'terminator', 'tilix']
                    shell_names = ['bash', 'zsh', 'fish', 'sh']
                    
                    # Detect terminal emulators
                    if any(term in name for term in terminal_names):
                        terminals.append({
                            "type": "linux_terminal",
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "title": ' '.join(pinfo['cmdline'] or [])[:50],
                            "platform": "linux"
                        })
                    # Detect shells, but only top-level ones (not subshells)
                    elif any(shell in name for shell in shell_names):
                        # Skip if this is a subshell of an already seen shell
                        if ppid not in seen_ppids:
                            # Check if this is a top-level shell (parent is not another shell)
                            try:
                                parent = psutil.Process(ppid)
                                parent_name = parent.name().lower()
                                if not any(shell in parent_name for shell in shell_names):
                                    terminals.append({
                                        "type": "linux_terminal",
                                        "pid": pinfo['pid'],
                                        "name": pinfo['name'],
                                        "title": ' '.join(pinfo['cmdline'] or [])[:50],
                                        "platform": "linux"
                                    })
                                    seen_ppids.add(pinfo['pid'])
                            except:
                                # If we can't check parent, include it to be safe
                                terminals.append({
                                    "type": "linux_terminal",
                                    "pid": pinfo['pid'],
                                    "name": pinfo['name'],
                                    "title": ' '.join(pinfo['cmdline'] or [])[:50],
                                    "platform": "linux"
                                })
                                seen_ppids.add(pinfo['pid'])
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Error detecting terminals: {e}")
            
        return terminals
    
    def _detect_claude_code(self) -> List[Dict[str, Any]]:
        """Detect active Claude Code sessions"""
        sessions = []
        
        try:
            # Method 1: Look for Claude Code processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    pinfo = proc.info
                    name = pinfo['name'].lower()
                    
                    if 'claude' in name:  # Only match 'claude' specifically, not 'code'
                        cmdline = ' '.join(pinfo['cmdline'] or [])
                        sessions.append({
                                "type": "process",
                                "pid": pinfo['pid'],
                                "name": pinfo['name'],
                                "command": cmdline,
                                "start_time": datetime.fromtimestamp(pinfo['create_time']).isoformat()
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Method 2: Look for Claude Code log files with recent activity
            log_paths = [
                Path.home() / ".claude-code" / "logs",
                Path.home() / ".cache" / "claude-code" / "logs",
                Path("/tmp") / "claude-code",
                Path.home() / "AppData" / "Local" / "Claude" / "logs",
            ]
            
            for log_dir in log_paths:
                if log_dir.exists():
                    for log_file in log_dir.rglob("*.log"):
                        try:
                            # Check if file was modified in last hour
                            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                            if (datetime.now() - mtime).total_seconds() < 3600:
                                sessions.append({
                                    "type": "log_file",
                                    "path": str(log_file),
                                    "last_modified": mtime.isoformat(),
                                    "size": log_file.stat().st_size
                                })
                        except Exception:
                            continue
            
            # Method 3: Check for Claude Code WebSocket connections
            try:
                connections = psutil.net_connections()
                for conn in connections:
                    if conn.status == 'ESTABLISHED' and conn.laddr:
                        # Look for typical Claude Code ports or WebSocket connections
                        if conn.laddr.port in [3000, 3001, 8080, 8081] or \
                           (conn.raddr and 'anthropic' in str(conn.raddr)):
                            try:
                                proc = psutil.Process(conn.pid)
                                sessions.append({
                                    "type": "network_connection",
                                    "pid": conn.pid,
                                    "process": proc.name(),
                                    "local_port": conn.laddr.port,
                                    "remote": str(conn.raddr) if conn.raddr else "Unknown"
                                })
                            except:
                                continue
            except psutil.AccessDenied:
                logger.debug("Could not access network connections")
                
        except Exception as e:
            logger.error(f"Error detecting Claude Code sessions: {e}")
            
        return sessions
    
    def _detect_relevant_processes(self) -> List[Dict[str, Any]]:
        """Detect other relevant development processes"""
        processes = []
        relevant_names = ['python', 'node', 'npm', 'code', 'vim', 'nvim', 'emacs', 'git']
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
                try:
                    pinfo = proc.info
                    name = pinfo['name'].lower()
                    
                    if any(rel in name for rel in relevant_names):
                        cmdline = ' '.join(pinfo['cmdline'] or [])[:200]
                        processes.append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "command": cmdline,
                            "cwd": pinfo.get('cwd', 'Unknown')
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Error detecting processes: {e}")
            
        return processes[:10]  # Limit to 10 most relevant
    
    def inject_to_terminal(self, terminal_pid: int, text: str) -> bool:
        """Inject text into a specific terminal"""
        try:
            if self.is_wsl:
                # Use Windows automation for Windows terminals
                ps_command = f"""
                Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {{
                    [DllImport("user32.dll")]
                    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
                    [DllImport("user32.dll")]
                    public static extern bool SetForegroundWindow(IntPtr hWnd);
                    [DllImport("user32.dll")]
                    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
                }}
"@
                
                $process = Get-Process -Id {terminal_pid} -ErrorAction SilentlyContinue
                if ($process) {{
                    $hwnd = $process.MainWindowHandle
                    [Win32]::SetForegroundWindow($hwnd)
                    Start-Sleep -Milliseconds 100
                    
                    # Send the text
                    Add-Type -AssemblyName System.Windows.Forms
                    [System.Windows.Forms.SendKeys]::SendWait("{text}")
                    
                    # If text doesn't end with [ENTER], add a short delay for review
                    # If it ends with [ENTER], simulate pressing Enter
                    if ("{text}".EndsWith("[ENTER]")) {{
                        Start-Sleep -Milliseconds 200
                        [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
                    }}
                    
                    Write-Output "Success"
                }} else {{
                    Write-Output "Process not found"
                }}
                """
                
                result = subprocess.run(
                    ["powershell.exe", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                return result.returncode == 0 and "Success" in result.stdout
                
            else:
                # Linux terminal injection (requires different approach)
                # This is more complex and system-dependent
                logger.warning("Linux terminal injection not implemented yet")
                return False
                
        except Exception as e:
            logger.error(f"Failed to inject text to terminal: {e}")
            return False


# Singleton instance
terminal_detector = TerminalDetector()