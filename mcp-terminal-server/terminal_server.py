#!/usr/bin/env python3
"""
MCP Terminal Server - Provides terminal and file operations for voice commands
"""

import os
import sys
import subprocess
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-terminal-server")

# Create MCP server
mcp = FastMCP("terminal-server")

@mcp.tool()
def execute_command(command: str, working_directory: Optional[str] = None) -> str:
    """Execute a command in the terminal"""
    try:
        logger.info(f"Executing command: {command}")
        
        # Use the provided working directory or current directory
        cwd = working_directory or os.getcwd()
        
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30
        )
        
        # Format output
        output = f"Command: {command}\n"
        output += f"Exit code: {result.returncode}\n"
        if result.stdout:
            output += f"\nOutput:\n{result.stdout}"
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Command timed out after 30 seconds: {command}"
    except Exception as e:
        return f"Failed to execute command: {str(e)}"

@mcp.tool()
def add_text_to_terminal(text: str) -> str:
    """Add text to terminal - simulates typing without executing"""
    try:
        # On Windows, we'll use a different approach
        if sys.platform == "win32":
            # Use PowerShell to send keys to the active window
            script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('{text}')
"""
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return f"Successfully added text to terminal: {text}"
            else:
                return f"Failed to add text: {result.stderr}"
        else:
            # On Unix-like systems, try to write to the active terminal
            try:
                # Get the current tty
                result = subprocess.run(
                    ["tty"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    tty = result.stdout.strip()
                    
                    # Write to the terminal
                    with open(tty, 'w') as f:
                        f.write(text)
                    
                    return f"Added text to terminal {tty}: {text}"
                else:
                    return "Could not determine active terminal"
                    
            except Exception as e:
                return f"Failed to add text to terminal: {str(e)}"
                
    except Exception as e:
        return f"Error adding text to terminal: {str(e)}"

@mcp.tool()
def read_file(path: str) -> str:
    """Read contents of a file"""
    try:
        file_path = Path(path).expanduser().resolve()
        
        if not file_path.exists():
            return f"File not found: {path}"
        
        if not file_path.is_file():
            return f"Not a file: {path}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return f"File: {path}\n\n{content}"
        
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file"""
    try:
        file_path = Path(path).expanduser().resolve()
        
        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"Successfully wrote {len(content)} characters to {path}"
        
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
def get_development_summary(include_files: bool = True, include_commands: bool = True) -> str:
    """Get summary of recent development activity"""
    summary = "Development Summary\n==================\n\n"
    
    try:
        # Get current directory info
        cwd = os.getcwd()
        summary += f"Current directory: {cwd}\n\n"
        
        if include_files:
            # Get recently modified files
            summary += "Recently Modified Files:\n"
            files = []
            
            # Look for files modified in the last hour
            for root, _, filenames in os.walk(".", topdown=True):
                # Skip hidden directories
                if '/.' in root:
                    continue
                
                for filename in filenames[:10]:  # Limit files per directory
                    filepath = Path(root) / filename
                    try:
                        stat = filepath.stat()
                        mtime = stat.st_mtime
                        # Files modified in last hour
                        if (time.time() - mtime) < 3600:
                            files.append((filepath, mtime))
                    except:
                        pass
            
            # Sort by modification time
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Show top 10 files
            for filepath, _ in files[:10]:
                summary += f"  - {filepath}\n"
            
            if not files:
                summary += "  No recently modified files found.\n"
            
            summary += "\n"
        
        if include_commands:
            # Try to get command history (platform-specific)
            summary += "Recent Commands:\n"
            
            # Try to read bash history
            history_file = Path.home() / ".bash_history"
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        lines = f.readlines()
                        recent_commands = lines[-10:] if len(lines) > 10 else lines
                        for cmd in recent_commands:
                            summary += f"  - {cmd.strip()}\n"
                except:
                    summary += "  Could not read command history.\n"
            else:
                summary += "  No command history found.\n"
        
        # Get git status if in a git repo
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout:
                summary += "\nGit Status:\n"
                summary += result.stdout
        except:
            pass
        
        return summary
        
    except Exception as e:
        return f"Error generating development summary: {str(e)}"

@mcp.tool()
def list_directory(path: str) -> str:
    """List contents of a directory"""
    try:
        dir_path = Path(path).expanduser().resolve()
        
        if not dir_path.exists():
            return f"Directory not found: {path}"
        
        if not dir_path.is_dir():
            return f"Not a directory: {path}"
        
        output = f"Directory: {path}\n\n"
        
        # Get directory contents
        items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        
        for item in items:
            if item.is_dir():
                output += f"[DIR]  {item.name}/\n"
            else:
                try:
                    size = item.stat().st_size
                    output += f"[FILE] {item.name} ({size} bytes)\n"
                except:
                    output += f"[FILE] {item.name}\n"
        
        return output
        
    except Exception as e:
        return f"Error listing directory: {str(e)}"

if __name__ == "__main__":
    # Run the server using stdio transport
    mcp.run(transport="stdio")