"""
MCP Client for Terminal Operations
Provides a client interface to the MCP terminal server for reliable tool execution
"""

import asyncio
import json
import subprocess
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger

class MCPTerminalClient:
    """Client for communicating with the MCP terminal server"""
    
    def __init__(self, server_path: str = None):
        self.server_path = server_path or "/mnt/c/users/dfoss/desktop/localaimodels/assistant/mcp-terminal-server/terminal_server.py"
        self.python_path = "/mnt/c/users/dfoss/desktop/localaimodels/assistant/venv/bin/python"
        self.working_dir = "/mnt/c/users/dfoss/desktop/localaimodels/assistant"
        self._process = None
        self._request_id = 0
    
    async def _get_next_id(self) -> int:
        """Get next request ID"""
        self._request_id += 1
        return self._request_id
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server and get response"""
        try:
            # Start server process if not running
            if not self._process or self._process.returncode is not None:
                await self._start_server()
            
            # Prepare JSON-RPC request
            request = {
                "jsonrpc": "2.0",
                "id": await self._get_next_id(),
                "method": method,
                "params": params
            }
            
            # Send request
            request_json = json.dumps(request) + "\n"
            self._process.stdin.write(request_json.encode())
            await self._process.stdin.drain()
            
            # Read response
            response_line = await self._process.stdout.readline()
            if not response_line:
                raise Exception("No response from MCP server")
            
            response = json.loads(response_line.decode().strip())
            
            if "error" in response:
                raise Exception(f"MCP server error: {response['error']}")
            
            return response.get("result", {})
            
        except Exception as e:
            logger.error(f"❌ MCP client error: {e}")
            # Fallback to direct subprocess execution
            return await self._fallback_execution(method, params)
    
    async def _start_server(self):
        """Start the MCP server process"""
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.python_path,
                self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir
            )
            logger.info("🔌 MCP terminal server started")
            
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "voice-assistant",
                        "version": "1.0.0"
                    }
                }
            }
            
            init_json = json.dumps(init_request) + "\n"
            self._process.stdin.write(init_json.encode())
            await self._process.stdin.drain()
            
            # Read initialization response
            response_line = await self._process.stdout.readline()
            if response_line:
                response = json.loads(response_line.decode().strip())
                logger.info("✅ MCP server initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MCP server: {e}")
            self._process = None
    
    async def _fallback_execution(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to direct subprocess execution if MCP fails"""
        logger.warning(f"🔄 Using fallback execution for {method}")
        
        if method == "tools/call" and params.get("name") == "execute_command":
            command = params.get("arguments", {}).get("command", "")
            working_dir = params.get("arguments", {}).get("working_directory", self.working_dir)
            
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=working_dir,
                    timeout=30
                )
                
                output = f"Command: {command}\n"
                output += f"Exit code: {result.returncode}\n"
                if result.stdout:
                    output += f"\nOutput:\n{result.stdout}"
                if result.stderr:
                    output += f"\nErrors:\n{result.stderr}"
                
                return {"content": [{"type": "text", "text": output}]}
                
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Failed to execute command: {str(e)}"}]}
        
        elif method == "tools/call" and params.get("name") == "add_text_to_terminal":
            text = params.get("arguments", {}).get("text", "")
            # This would require platform-specific implementation
            return {"content": [{"type": "text", "text": f"Fallback: Would add text '{text}' to terminal"}]}
        
        elif method == "tools/call" and params.get("name") == "get_development_summary":
            # Fallback development summary using basic commands
            try:
                import os
                import time
                from pathlib import Path
                
                summary = "Development Summary (Fallback)\n==================\n\n"
                summary += f"Current directory: {os.getcwd()}\n\n"
                
                # Get recently modified files
                files = []
                for root, _, filenames in os.walk(".", topdown=True):
                    if '/.' in root:
                        continue
                    for filename in filenames[:5]:
                        filepath = Path(root) / filename
                        try:
                            stat = filepath.stat()
                            if (time.time() - stat.st_mtime) < 3600:  # Last hour
                                files.append(str(filepath))
                        except:
                            pass
                
                if files:
                    summary += f"Recently modified files:\n"
                    for f in files[:5]:
                        summary += f"  - {f}\n"
                else:
                    summary += "No recently modified files found.\n"
                
                return {"content": [{"type": "text", "text": summary}]}
                
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Fallback development summary failed: {str(e)}"}]}
        
        return {"content": [{"type": "text", "text": f"Unsupported fallback method: {method}"}]}
    
    async def execute_command(self, command: str, working_directory: Optional[str] = None) -> str:
        """Execute a command via MCP server"""
        try:
            params = {
                "name": "execute_command",
                "arguments": {
                    "command": command,
                    "working_directory": working_directory or self.working_dir
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "No output")
            
            return "Command executed successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to execute command via MCP: {e}")
            return f"Error executing command: {str(e)}"
    
    async def add_text_to_terminal(self, text: str) -> str:
        """Add text to terminal via MCP server"""
        try:
            params = {
                "name": "add_text_to_terminal",
                "arguments": {
                    "text": text
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "Text added successfully")
            
            return "Text added to terminal successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to add text to terminal via MCP: {e}")
            return f"Error adding text to terminal: {str(e)}"
    
    async def read_file(self, path: str) -> str:
        """Read file contents via MCP server"""
        try:
            params = {
                "name": "read_file",
                "arguments": {
                    "path": path
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "File content unavailable")
            
            return "File read successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to read file via MCP: {e}")
            return f"Error reading file: {str(e)}"
    
    async def write_file(self, path: str, content: str) -> str:
        """Write file contents via MCP server"""
        try:
            params = {
                "name": "write_file",
                "arguments": {
                    "path": path,
                    "content": content
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "File written successfully")
            
            return "File written successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to write file via MCP: {e}")
            return f"Error writing file: {str(e)}"
    
    async def get_development_summary(self, include_files: bool = True, include_commands: bool = True) -> str:
        """Get development summary via MCP server"""
        try:
            params = {
                "name": "get_development_summary",
                "arguments": {
                    "include_files": include_files,
                    "include_commands": include_commands
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "Development summary unavailable")
            
            return "Development summary generated successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to get development summary via MCP: {e}")
            return f"Error getting development summary: {str(e)}"
    
    async def list_directory(self, path: str) -> str:
        """List directory contents via MCP server"""
        try:
            params = {
                "name": "list_directory",
                "arguments": {
                    "path": path
                }
            }
            
            result = await self._send_request("tools/call", params)
            
            # Extract text content from MCP response
            if "content" in result and result["content"]:
                return result["content"][0].get("text", "Directory listing unavailable")
            
            return "Directory listed successfully"
            
        except Exception as e:
            logger.error(f"❌ Failed to list directory via MCP: {e}")
            return f"Error listing directory: {str(e)}"
    
    async def close(self):
        """Close the MCP client and server process"""
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
                logger.info("🔌 MCP terminal server closed")
            except asyncio.TimeoutError:
                self._process.kill()
                logger.warning("⚠️ MCP terminal server forcefully killed")
            except Exception as e:
                logger.error(f"❌ Error closing MCP server: {e}")

# Singleton instance
mcp_client = MCPTerminalClient()