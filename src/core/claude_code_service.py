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
        
    async def initialize(self) -> bool:
        """Initialize the Claude Code service and find active log files"""
        try:
            # Find the most recent Claude Code log file
            log_file = await self._find_active_log_file()
            if log_file:
                self.current_session_log = log_file
                logger.info(f"✅ Found Claude Code session log: {log_file}")
                return True
            else:
                logger.warning("⚠️ No active Claude Code session logs found")
                # Create a mock log for testing
                await self._create_test_log()
                return True
                
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
        """Create a test log file for development"""
        test_log_dir = Path("/tmp/claude-code-test")
        test_log_dir.mkdir(exist_ok=True)
        
        test_log_file = test_log_dir / "claude-session.log"
        
        # Create sample log entries
        sample_entries = [
            f"{datetime.now().isoformat()} INFO User opened file: /home/user/project/main.py",
            f"{datetime.now().isoformat()} INFO Tool used: Read - /home/user/project/config.json", 
            f"{datetime.now().isoformat()} INFO Command executed: npm install",
            f"{datetime.now().isoformat()} ERROR Python syntax error in main.py line 42",
            f"{datetime.now().isoformat()} INFO Tool used: Edit - Fixed syntax error",
            f"{datetime.now().isoformat()} INFO Command executed: python main.py",
            f"{datetime.now().isoformat()} INFO User asked: How do I optimize this function?",
        ]
        
        with open(test_log_file, 'w') as f:
            f.write('\n'.join(sample_entries))
            
        self.current_session_log = str(test_log_file)
        logger.info(f"✅ Created test Claude Code log: {test_log_file}")
    
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
    """Service for interacting with Claude Code terminal"""
    
    def __init__(self):
        self.terminal_processes = {}
        
    async def add_text_to_terminal(self, text: str, terminal_id: str = "default") -> bool:
        """Add text to Claude Code terminal (simulates typing)"""
        try:
            # For now, we'll use a file-based approach to communicate with Claude Code
            # In a real implementation, this would use Claude Code's API
            
            terminal_input_file = f"/tmp/claude-terminal-input-{terminal_id}.txt"
            
            with open(terminal_input_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()}: {text}\n")
                
            logger.info(f"✅ Added text to terminal {terminal_id}: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add text to terminal: {e}")
            return False
    
    async def send_terminal_input(self, command: str, terminal_id: str = "default") -> bool:
        """Send input to Claude Code terminal (simulates pressing Enter)"""
        try:
            # Add the command first
            await self.add_text_to_terminal(command, terminal_id)
            
            # Then simulate pressing Enter
            await self.add_text_to_terminal("[ENTER]", terminal_id)
            
            logger.info(f"✅ Sent command to terminal {terminal_id}: {command}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send terminal input: {e}")
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
            
            # Format for LLM consumption
            return {
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


# Global instance
claude_code_integration = ClaudeCodeIntegration()