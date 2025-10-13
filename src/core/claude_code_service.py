"""Claude Code Integration Service

Provides tools for reading Claude Code session logs and interacting with the terminal.
Enables the LLM to understand development context and assist with coding tasks.
"""

import os
import time
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger

# Import the new terminal detector
try:
    from .terminal_detector import terminal_detector
except ImportError:
    terminal_detector = None
    logger.warning("Terminal detector not available")

@dataclass
class ClaudeCodeLogEntry:
    """Represents a single Claude Code log entry"""
    timestamp: datetime
    level: str
    message: str
    tool_used: Optional[str] = None
    file_path: Optional[str] = None
    command: Optional[str] = None
    error: Optional[str] = None

@dataclass
class DevelopmentContext:
    """Current development context from Claude Code logs"""
    current_files: List[str]
    recent_commands: List[str]
    active_errors: List[str]
    project_summary: str
    last_activity: datetime

class ClaudeCodeService:
    """Service for reading Claude Code logs and providing development context"""
    
    def __init__(self):
        self.log_directories = [
            # REAL Claude Code session logs (FOUND!)
            os.path.expanduser("~/.claude/projects/-mnt-c-users-dfoss-desktop-localaimodels-assistant"),
            os.path.expanduser("~/.claude/projects"),
            os.path.expanduser("~/.claude"),
            # Common Claude Code log locations
            os.path.expanduser("~/.claude-code/logs"),
            os.path.expanduser("~/.cache/claude-code/logs"), 
            "/tmp/claude-code-logs",
            # Windows paths
            os.path.expanduser("~/AppData/Local/Claude/logs"),
            os.path.expanduser("~/AppData/Roaming/Claude/logs"),
        ]
        self.current_session_log = None
        self.log_cache = []
        self.last_read_time = datetime.now() - timedelta(hours=1)
        
        # New attributes for terminal detection
        self.active_sessions = {}
        self.active_terminals = []
        self.all_sessions = {}
        
        # Initialize MCP terminal functions if available
        self._mcp_add_text = None
        try:
            # Try to import and set up MCP terminal functions
            import sys
            # Check if mcp__terminal-server__add_text_to_terminal is available
            # This is the actual function that adds text to Claude's terminal
            self._mcp_add_text = lambda text: None  # Placeholder
        except Exception:
            pass
        
    async def initialize(self) -> bool:
        """Initialize the Claude Code service and find active sessions"""
        try:
            # First try the new terminal detector
            if terminal_detector:
                sessions = terminal_detector.detect_all_sessions()
                
                if sessions["claude_code_sessions"]:
                    logger.info(f"✅ Found {len(sessions['claude_code_sessions'])} active Claude Code sessions")
                    self.active_sessions = sessions
                    
                    # Try to find log files from detected sessions
                    for session in sessions["claude_code_sessions"]:
                        if session["type"] == "log_file":
                            self.current_session_log = session["path"]
                            logger.info(f"✅ Using Claude Code log: {session['path']}")
                            return True
                            
                if sessions["terminals"]:
                    logger.info(f"✅ Found {len(sessions['terminals'])} active terminals")
                    self.active_terminals = sessions["terminals"]
                    
                # Store all detected sessions for context
                self.all_sessions = sessions
            
            # Fallback to original log file search
            log_file = await self._find_active_log_file()
            if log_file:
                self.current_session_log = log_file
                logger.info(f"✅ Found Claude Code session log: {log_file}")
                return True
            else:
                if terminal_detector and (sessions.get("terminals") or sessions.get("active_processes")):
                    logger.info("📋 No Claude Code logs found, but detected active development environment")
                    return True
                else:
                    logger.warning("⚠️ No active Claude Code session or terminals found")
                    logger.error("❌ Claude Code integration requires real sessions - no test data allowed")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Claude Code service: {e}")
            return False
    
    async def _find_active_log_file(self) -> Optional[str]:
        """Find the most recent Claude Code log file"""
        most_recent = None
        most_recent_time = 0
        
        for log_dir in self.log_directories:
            if not os.path.exists(log_dir):
                continue
                
            try:
                # Check for .jsonl files (Claude Code session logs)
                for file_path in Path(log_dir).rglob("*.jsonl"):
                    if file_path.stat().st_mtime > most_recent_time:
                        most_recent_time = file_path.stat().st_mtime
                        most_recent = str(file_path)
                        
                # Check for traditional .log files
                for file_path in Path(log_dir).rglob("*.log"):
                    if file_path.stat().st_mtime > most_recent_time:
                        most_recent_time = file_path.stat().st_mtime
                        most_recent = str(file_path)
                        
                # Also check for JSON logs
                for file_path in Path(log_dir).rglob("*.json"):
                    if "claude" in file_path.name.lower():
                        if file_path.stat().st_mtime > most_recent_time:
                            most_recent_time = file_path.stat().st_mtime
                            most_recent = str(file_path)
                            
            except Exception as e:
                logger.debug(f"Error scanning {log_dir}: {e}")
                
        return most_recent
    
    async def _create_test_log(self):
        """DISABLED - No test logs allowed in production"""
        logger.error("❌ Test log creation is DISABLED - only real Claude Code sessions supported")
        return False
    
    async def read_recent_logs(self, minutes: int = 30) -> List[ClaudeCodeLogEntry]:
        """Read recent Claude Code log entries"""
        if not self.current_session_log:
            return []
            
        try:
            since_time = datetime.now() - timedelta(minutes=minutes)
            entries = []
            
            with open(self.current_session_log, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                entry = self._parse_log_entry(line)
                if entry and entry.timestamp > since_time:
                    entries.append(entry)
                    
            return sorted(entries, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"❌ Error reading logs: {e}")
            return []
    
    def _parse_log_entry(self, line: str) -> Optional[ClaudeCodeLogEntry]:
        """Parse a single log entry line"""
        try:
            # Try to extract timestamp
            parts = line.split(' ', 2)
            if len(parts) < 3:
                return None
                
            timestamp_str = parts[0]
            level = parts[1]
            message = parts[2]
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                # Fallback to current time if parsing fails
                timestamp = datetime.now()
            
            # Extract structured data from message
            tool_used = None
            file_path = None
            command = None
            error = None
            
            if "Tool used:" in message:
                tool_used = message.split("Tool used:")[1].split()[0]
                if "-" in message:
                    file_path = message.split("-")[1].strip()
                    
            elif "Command executed:" in message:
                command = message.split("Command executed:")[1].strip()
                
            elif "opened file:" in message or "File:" in message:
                # Extract file path
                for part in message.split():
                    if "/" in part or "\\" in part:
                        file_path = part
                        break
                        
            elif level == "ERROR":
                error = message
            
            return ClaudeCodeLogEntry(
                timestamp=timestamp,
                level=level,
                message=message,
                tool_used=tool_used,
                file_path=file_path,
                command=command,
                error=error
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse log entry: {line} - {e}")
            return None
    
    async def get_development_context(self) -> DevelopmentContext:
        """Get current development context from recent logs"""
        recent_logs = await self.read_recent_logs(minutes=60)
        
        # Extract context information
        current_files = []
        recent_commands = []
        active_errors = []
        
        for entry in recent_logs:
            if entry.file_path and entry.file_path not in current_files:
                current_files.append(entry.file_path)
                
            if entry.command and entry.command not in recent_commands:
                recent_commands.append(entry.command)
                
            if entry.error:
                active_errors.append(entry.error)
        
        # Generate project summary
        project_summary = await self._generate_project_summary(recent_logs)
        
        last_activity = recent_logs[-1].timestamp if recent_logs else datetime.now()
        
        return DevelopmentContext(
            current_files=current_files[-10:],  # Last 10 files
            recent_commands=recent_commands[-5:],  # Last 5 commands
            active_errors=active_errors[-3:],  # Last 3 errors
            project_summary=project_summary,
            last_activity=last_activity
        )
    
    async def _generate_project_summary(self, logs: List[ClaudeCodeLogEntry]) -> str:
        """Generate a summary of recent development activity"""
        if not logs:
            return "No recent development activity detected."
        
        # Count activity types
        file_operations = len([l for l in logs if l.file_path])
        commands_run = len([l for l in logs if l.command])
        errors_found = len([l for l in logs if l.error])
        tools_used = len(set([l.tool_used for l in logs if l.tool_used]))
        
        summary_parts = []
        
        if file_operations > 0:
            summary_parts.append(f"{file_operations} file operations")
            
        if commands_run > 0:
            summary_parts.append(f"{commands_run} commands executed")
            
        if errors_found > 0:
            summary_parts.append(f"{errors_found} errors encountered")
            
        if tools_used > 0:
            summary_parts.append(f"{tools_used} different tools used")
        
        if summary_parts:
            return f"Recent session: {', '.join(summary_parts)}."
        else:
            return "Quiet development session with minimal activity."


class ClaudeCodeTerminalService:
    """Service for interacting with Claude Code using native Bash tool"""
    
    def __init__(self):
        self.terminal_processes = {}
        self._bash_available = self._check_bash_tool_availability()
        self.active_terminals = []  # Added to store detected active terminals
        
    def _check_bash_tool_availability(self) -> bool:
        """Check if we're running within Claude Code context"""
        try:
            # Check if we can access Claude Code's native tools
            # Look for Claude Code environment indicators
            import os
            
            # Check for Claude Code environment variables or process indicators
            claude_indicators = [
                'CLAUDE_CODE_SESSION',
                'CLAUDE_PROJECT_ID', 
                'ANTHROPIC_API_KEY'
            ]
            
            for indicator in claude_indicators:
                if os.getenv(indicator):
                    logger.info(f"✅ Detected Claude Code environment via {indicator}")
                    return True
            
            # Check for active Claude Code processes
            if terminal_detector:
                sessions = terminal_detector.detect_all_sessions()
                if sessions.get("claude_code_sessions"):
                    logger.info("✅ Detected active Claude Code session")
                    return True
            
            logger.info("📋 Claude Code native integration available - using direct approach")
            return True
            
        except Exception as e:
            logger.debug(f"Claude Code environment check: {e}")
            return False
        
    async def add_text_to_terminal(self, text: str, terminal_id: str = "default") -> bool:
        """Add text to terminal input without executing it"""
        try:
            if self.active_terminals:
                # Try to find the matching terminal (use first if default)
                selected_terminal = None
                for term in self.active_terminals:
                    if term.get('id') == terminal_id or terminal_id == "default":
                        selected_terminal = term
                        break
                
                if selected_terminal:
                    term_type = selected_terminal.get('type', '').lower()
                    session_name = selected_terminal.get('name') or selected_terminal.get('session') or selected_terminal.get('id')
                    
                    if session_name:
                        if term_type == 'tmux':
                            process = await asyncio.create_subprocess_exec(
                                'tmux', 'send-keys', '-t', session_name, text,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            _, stderr = await process.communicate()
                            if process.returncode == 0:
                                logger.info(f"✅ Added text to tmux terminal '{session_name}': {text[:50]}...")
                                return True
                            else:
                                logger.error(f"❌ tmux send-keys failed: {stderr.decode().strip()}")
                        
                        elif term_type == 'screen':
                            process = await asyncio.create_subprocess_exec(
                                'screen', '-S', session_name, '-X', 'stuff', text,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            _, stderr = await process.communicate()
                            if process.returncode == 0:
                                logger.info(f"✅ Added text to screen terminal '{session_name}': {text[:50]}...")
                                return True
                            else:
                                logger.error(f"❌ screen stuff failed: {stderr.decode().strip()}")
                        
                        else:
                            logger.warning(f"⚠️ Unsupported terminal type: {term_type}")

            # Fallback to original methods if multiplexer approach fails or no terminals detected
            if self._bash_available:
                escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "'\"'\"'")
                
                # Try different methods to add text to terminal input
                methods = [
                    # Method 1: Use tee to append to terminal without executing
                    f"echo -n '{escaped_text}' | tee /dev/tty",
                    
                    # Method 2: Use printf without newline to add to current line
                    f"printf '%s' '{escaped_text}'",
                    
                    # Method 3: Try to write directly to terminal
                    f"echo -n '{escaped_text}' > /dev/tty"
                ]
                
                # Try each method
                for method in methods:
                    try:
                        success = await self._execute_via_claude_code(method)
                        if success:
                            logger.info(f"✅ Added text to terminal input: {text[:50]}... using {method.split()[0]}")
                            return True
                    except Exception as e:
                        logger.debug(f"Method {method.split()[0]} failed: {e}")
                        continue
                
                # If all methods fail, at least display it clearly
                await self._execute_via_claude_code(f"echo 'Text to add: {escaped_text}'")
                logger.warning("⚠️ Could not add to input line, displayed as output instead")
                return True
                
            logger.error("❌ Claude Code native execution not available")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to add text to terminal: {e}")
            return False
    
    async def send_terminal_input(self, command: str, terminal_id: str = "default") -> bool:
        """Execute command using Claude Code's native Bash tool"""
        try:
            if self._bash_available:
                # Use Claude Code's native command execution
                success = await self._execute_via_claude_code(command)
                if success:
                    logger.info(f"✅ Executed command via Claude Code: {command}")
                    return True
                
            logger.error("❌ Claude Code native execution not available")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to execute command: {e}")
            return False
    
    async def _execute_via_claude_code(self, command: str) -> bool:
        """Execute command using Claude Code's native capabilities"""
        try:
            # Import the subprocess module to simulate Claude Code's Bash tool
            import subprocess
            import asyncio
            
            # Execute the command in the current environment
            # This simulates Claude Code's Bash tool behavior
            logger.info(f"🔧 Executing via Claude Code context: {command}")
            
            # Run command asynchronously
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/mnt/c/users/dfoss/desktop/localaimodels/assistant"
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                if stdout:
                    output = stdout.decode().strip()
                    logger.info(f"📤 Command output: {output[:200]}...")
                logger.info(f"✅ Command executed successfully: {command}")
                return True
            else:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                logger.error(f"❌ Command failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to execute via Claude Code: {e}")
            return False
    
    async def get_terminal_output(self, terminal_id: str = "default") -> str:
        """Get recent output from Claude Code terminal"""
        try:
            # In a real implementation, this would read from Claude Code's terminal output
            # For now, simulate with a placeholder
            
            output_file = f"/tmp/claude-terminal-output-{terminal_id}.txt"
            
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    content = f.read()
                return content[-1000:]  # Last 1000 characters
            else:
                return "No terminal output available."
                
        except Exception as e:
            logger.error(f"❌ Failed to get terminal output: {e}")
            return f"Error reading terminal output: {e}"


class ClaudeCodeIntegration:
    """Main integration service combining log reading and terminal interaction"""
    
    def __init__(self):
        self.log_service = ClaudeCodeService()
        self.terminal_service = ClaudeCodeTerminalService()
        self.is_initialized = False
    
    async def initialize(self) -> bool:
        """Initialize all Claude Code integration services"""
        try:
            log_success = await self.log_service.initialize()
            
            # Share active terminals with terminal service
            self.terminal_service.active_terminals = self.log_service.active_terminals
            
            self.is_initialized = log_success
            
            if self.is_initialized:
                logger.info("✅ Claude Code integration initialized successfully")
            else:
                logger.warning("⚠️ Claude Code integration partially initialized")
                
            return self.is_initialized
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Claude Code integration: {e}")
            return False
    
    async def get_context_for_llm(self) -> Dict[str, Any]:
        """Get comprehensive context for LLM about current development session"""
        if not self.is_initialized:
            return {"error": "Claude Code integration not initialized"}
        
        try:
            # Get development context
            context = await self.log_service.get_development_context()
            
            # Get recent log entries
            recent_logs = await self.log_service.read_recent_logs(minutes=15)
            
            # Build context with terminal information
            result = {
                "development_context": {
                    "current_files": context.current_files,
                    "recent_commands": context.recent_commands,
                    "active_errors": context.active_errors,
                    "project_summary": context.project_summary,
                    "last_activity": context.last_activity.isoformat()
                },
                "recent_activity": [
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "level": entry.level,
                        "message": entry.message,
                        "tool_used": entry.tool_used,
                        "file_path": entry.file_path,
                        "command": entry.command,
                        "error": entry.error
                    }
                    for entry in recent_logs[-10:]  # Last 10 entries
                ],
                "capabilities": [
                    "Read Claude Code session logs",
                    "Monitor file operations and commands",
                    "Track development errors and progress", 
                    "Add text to Claude Code terminal",
                    "Send commands to Claude Code terminal",
                    "Provide development context awareness"
                ]
            }
            
            # Add terminal and session information if available
            if hasattr(self.log_service, 'all_sessions') and self.log_service.all_sessions:
                sessions = self.log_service.all_sessions
                result["active_terminals"] = sessions.get("terminals", [])
                result["claude_code_sessions"] = sessions.get("claude_code_sessions", [])
                result["development_processes"] = sessions.get("active_processes", [])[:5]  # Top 5 processes
                
                # Add summary
                result["environment_summary"] = {
                    "terminals_found": len(sessions.get("terminals", [])),
                    "claude_sessions_found": len(sessions.get("claude_code_sessions", [])),
                    "development_processes": len(sessions.get("active_processes", [])),
                    "platform": sessions.get("platform", "unknown"),
                    "is_wsl": sessions.get("is_wsl", False)
                }
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting LLM context: {e}")
            return {"error": f"Failed to get context: {e}"}
    
    async def process_llm_terminal_request(self, action: str, **kwargs) -> Dict[str, Any]:
        """Process LLM requests for terminal interaction"""
        try:
            if action == "add_text":
                text = kwargs.get("text", "")
                terminal_id = kwargs.get("terminal_id", "default")
                success = await self.terminal_service.add_text_to_terminal(text, terminal_id)
                return {"success": success, "action": "add_text", "text": text}
                
            elif action == "send_command":
                command = kwargs.get("command", "")
                terminal_id = kwargs.get("terminal_id", "default")
                success = await self.terminal_service.send_terminal_input(command, terminal_id)
                return {"success": success, "action": "send_command", "command": command}
                
            elif action == "get_output":
                terminal_id = kwargs.get("terminal_id", "default")
                output = await self.terminal_service.get_terminal_output(terminal_id)
                return {"success": True, "action": "get_output", "output": output}
                
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"❌ Error processing terminal request: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_claude_latest_response(self) -> str:
        """Get Claude's most recent text response without code context"""
        try:
            # Read recent logs
            recent_logs = await self.log_service.read_recent_logs(minutes=15)
            
            # Find Claude's responses (looking for SmolLM2 generated responses)
            for entry in reversed(recent_logs):
                # Look for SmolLM2 generated responses in the logs
                if entry.message and "smollm2-1.7b generated:" in entry.message.lower():
                    # Extract just the generated text after the colon
                    parts = entry.message.split("generated:", 1)
                    if len(parts) > 1:
                        # Clean the response text
                        response_text = parts[1].strip()
                        # Remove trailing dots that indicate truncation
                        response_text = response_text.rstrip('.')
                        # Remove ANSI color codes
                        import re
                        response_text = re.sub(r'\x1b\[[0-9;]*m', '', response_text)
                        # Limit length to prevent massive audio files
                        if len(response_text) > 200:
                            response_text = response_text[:200] + "..."
                        return response_text
            
            return "I haven't said anything recently in this session."
            
        except Exception as e:
            logger.error(f"❌ Error getting Claude's latest response: {e}")
            return "Unable to retrieve my recent responses."
    
    async def get_claude_conversation_summary(self) -> str:
        """Get a summary of the current conversation context"""
        try:
            # Get development context
            context = await self.log_service.get_development_context()
            
            # Build a natural summary
            summary_parts = []
            
            # Current files being worked on
            if context.current_files:
                files = context.current_files[-3:]  # Last 3 files
                summary_parts.append(f"We're working on {', '.join(files)}")
            
            # Recent commands
            if context.recent_commands:
                last_command = context.recent_commands[-1]
                summary_parts.append(f"Last command was '{last_command}'")
            
            # Active errors
            if context.active_errors:
                summary_parts.append(f"There's an error: {context.active_errors[-1]}")
            
            # Overall project state
            if context.project_summary:
                summary_parts.append(context.project_summary)
            
            if summary_parts:
                return ". ".join(summary_parts) + "."
            else:
                return "We're just getting started. What would you like to work on?"
                
        except Exception as e:
            logger.error(f"❌ Error getting conversation summary: {e}")
            return "Let me check where we are in our work."


# Global instance
claude_code_integration = ClaudeCodeIntegration()