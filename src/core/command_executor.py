"""Command execution with output capture and error handling"""
import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, AsyncIterator, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import shlex

from loguru import logger

@dataclass
class CommandResult:
    """Result of command execution"""
    command: str
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    working_directory: str
    environment: Dict[str, str]
    timestamp: datetime
    pid: Optional[int] = None


@dataclass
class RunningProcess:
    """Represents a running process"""
    pid: int
    command: str
    process: asyncio.subprocess.Process
    start_time: datetime
    working_directory: str


class CommandExecutor:
    """Execute commands with proper error handling and monitoring"""
    
    def __init__(self):
        self.running_processes: Dict[int, RunningProcess] = {}
        self.command_history: List[CommandResult] = []
        self.max_history = 100
        self.default_timeout = 30  # seconds
        
    async def execute_command(
        self,
        command: str,
        working_directory: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
        shell: bool = True
    ) -> CommandResult:
        """Execute a command and return the result"""
        
        start_time = datetime.now()
        start_timestamp = asyncio.get_event_loop().time()
        
        # Prepare environment
        env = os.environ.copy()
        if environment:
            env.update(environment)
            
        # Set working directory
        if working_directory:
            work_dir = Path(working_directory)
            if not work_dir.exists():
                raise ValueError(f"Working directory does not exist: {working_directory}")
        else:
            work_dir = Path.cwd()
            
        logger.info(f"Executing command: {command}")
        logger.debug(f"Working directory: {work_dir}")
        
        try:
            if shell:
                # Use shell execution for complex commands
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    cwd=str(work_dir),
                    env=env
                )
            else:
                # Parse command for subprocess
                cmd_parts = shlex.split(command)
                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    cwd=str(work_dir),
                    env=env
                )
            
            # Track running process
            if process.pid:
                running_proc = RunningProcess(
                    pid=process.pid,
                    command=command,
                    process=process,
                    start_time=start_time,
                    working_directory=str(work_dir)
                )
                self.running_processes[process.pid] = running_proc
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout or self.default_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Command timed out: {command}")
                if process.pid:
                    await self._terminate_process(process.pid)
                raise asyncio.TimeoutError(f"Command timed out after {timeout}s")
            
            # Calculate execution time
            execution_time = asyncio.get_event_loop().time() - start_timestamp
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            # Create result
            result = CommandResult(
                command=command,
                return_code=process.returncode or 0,
                stdout=stdout_text,
                stderr=stderr_text,
                execution_time=execution_time,
                working_directory=str(work_dir),
                environment=env,
                timestamp=start_time,
                pid=process.pid
            )
            
            # Add to history
            self.command_history.append(result)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
                
            # Clean up running process tracking
            if process.pid in self.running_processes:
                del self.running_processes[process.pid]
                
            logger.info(f"Command completed: {command} (exit code: {result.return_code})")
            
            return result
            
        except Exception as e:
            # Clean up on error
            if process and process.pid in self.running_processes:
                del self.running_processes[process.pid]
                
            logger.error(f"Error executing command '{command}': {e}")
            
            # Return error result
            execution_time = asyncio.get_event_loop().time() - start_timestamp
            return CommandResult(
                command=command,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                working_directory=str(work_dir),
                environment=env,
                timestamp=start_time,
                pid=getattr(process, 'pid', None)
            )
    
    async def execute_interactive_command(
        self,
        command: str,
        inputs: List[str],
        working_directory: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute an interactive command with predefined inputs"""
        
        start_time = datetime.now()
        start_timestamp = asyncio.get_event_loop().time()
        
        work_dir = Path(working_directory) if working_directory else Path.cwd()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(work_dir)
            )
            
            # Send inputs
            stdin_data = '\n'.join(inputs) + '\n'
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin_data.encode()),
                timeout=timeout or self.default_timeout
            )
            
            execution_time = asyncio.get_event_loop().time() - start_timestamp
            
            result = CommandResult(
                command=f"{command} (interactive)",
                return_code=process.returncode or 0,
                stdout=stdout.decode('utf-8', errors='replace'),
                stderr=stderr.decode('utf-8', errors='replace'),
                execution_time=execution_time,
                working_directory=str(work_dir),
                environment=os.environ.copy(),
                timestamp=start_time,
                pid=process.pid
            )
            
            self.command_history.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Error executing interactive command '{command}': {e}")
            return CommandResult(
                command=f"{command} (interactive)",
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=0,
                working_directory=str(work_dir),
                environment=os.environ.copy(),
                timestamp=start_time
            )
    
    async def stream_command_output(
        self,
        command: str,
        working_directory: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> AsyncIterator[Tuple[str, str]]:  # (stream_type, content)
        """Stream command output in real-time"""
        
        env = os.environ.copy()
        if environment:
            env.update(environment)
            
        work_dir = Path(working_directory) if working_directory else Path.cwd()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(work_dir),
                env=env
            )
            
            if process.pid:
                running_proc = RunningProcess(
                    pid=process.pid,
                    command=command,
                    process=process,
                    start_time=datetime.now(),
                    working_directory=str(work_dir)
                )
                self.running_processes[process.pid] = running_proc
            
            # Stream stdout and stderr concurrently
            async def read_stream(stream, stream_name):
                while True:
                    try:
                        line = await stream.readline()
                        if not line:
                            break
                        yield (stream_name, line.decode('utf-8', errors='replace').rstrip())
                    except Exception as e:
                        yield (stream_name, f"Error reading stream: {e}")
                        break
            
            # Use asyncio.gather to read both streams simultaneously
            tasks = []
            if process.stdout:
                tasks.append(read_stream(process.stdout, 'stdout'))
            if process.stderr:
                tasks.append(read_stream(process.stderr, 'stderr'))
            
            # Yield output as it comes
            if tasks:
                async def stream_merger():
                    try:
                        async for stream_name, line in self._merge_streams(tasks):
                            yield (stream_name, line)
                    finally:
                        await process.wait()
                        if process.pid in self.running_processes:
                            del self.running_processes[process.pid]
                
                async for item in stream_merger():
                    yield item
            else:
                await process.wait()
                if process.pid in self.running_processes:
                    del self.running_processes[process.pid]
                    
        except Exception as e:
            logger.error(f"Error streaming command '{command}': {e}")
            yield ('stderr', f"Error: {str(e)}")
    
    async def _merge_streams(self, stream_generators):
        """Merge multiple async generators"""
        import asyncio
        from asyncio import Queue
        
        queue = Queue()
        
        async def pump_stream(stream_gen):
            async for item in stream_gen:
                await queue.put(item)
            await queue.put(None)  # Sentinel
        
        # Start all stream pumps
        tasks = [asyncio.create_task(pump_stream(stream)) for stream in stream_generators]
        active_streams = len(tasks)
        
        try:
            while active_streams > 0:
                item = await queue.get()
                if item is None:
                    active_streams -= 1
                else:
                    yield item
        finally:
            # Clean up tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
    
    async def terminate_process(self, pid: int) -> bool:
        """Terminate a running process"""
        return await self._terminate_process(pid)
    
    async def _terminate_process(self, pid: int) -> bool:
        """Internal method to terminate a process"""
        if pid not in self.running_processes:
            logger.warning(f"Process {pid} not found in running processes")
            return False
            
        try:
            running_proc = self.running_processes[pid]
            process = running_proc.process
            
            # Try graceful termination first
            process.terminate()
            
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if graceful termination fails
                logger.warning(f"Force killing process {pid}")
                process.kill()
                await process.wait()
            
            del self.running_processes[pid]
            logger.info(f"Terminated process {pid}")
            return True
            
        except Exception as e:
            logger.error(f"Error terminating process {pid}: {e}")
            return False
    
    async def get_running_processes(self) -> List[RunningProcess]:
        """Get list of currently running processes"""
        return list(self.running_processes.values())
    
    async def get_command_history(self, limit: int = 20) -> List[CommandResult]:
        """Get recent command history"""
        return self.command_history[-limit:]
    
    async def find_virtual_env(self, directory: str) -> Optional[str]:
        """Find Python virtual environment in directory"""
        search_paths = [
            Path(directory) / "venv",
            Path(directory) / ".venv", 
            Path(directory) / "env",
            Path(directory) / ".env",
            Path(directory).parent / "venv"
        ]
        
        for venv_path in search_paths:
            if venv_path.exists():
                # Check for activation script
                activate_script = venv_path / "bin" / "activate"
                if activate_script.exists():
                    return str(venv_path)
                    
                # Windows path
                activate_script = venv_path / "Scripts" / "activate.bat"
                if activate_script.exists():
                    return str(venv_path)
        
        return None
    
    async def execute_python_with_venv(
        self,
        script_or_command: str,
        working_directory: str,
        is_file: bool = True
    ) -> CommandResult:
        """Execute Python script/command with virtual environment if available"""
        
        venv_path = await self.find_virtual_env(working_directory)
        
        if venv_path:
            # Use virtual environment
            if os.name == 'nt':  # Windows
                python_cmd = f'"{venv_path}\\Scripts\\python.exe"'
            else:  # Unix-like
                python_cmd = f'source "{venv_path}/bin/activate" && python'
                
            if is_file:
                command = f'{python_cmd} "{script_or_command}"'
            else:
                command = f'{python_cmd} -c "{script_or_command}"'
        else:
            # Use system Python
            if is_file:
                command = f'python3 "{script_or_command}"'
            else:
                command = f'python3 -c "{script_or_command}"'
        
        return await self.execute_command(
            command=command,
            working_directory=working_directory,
            shell=True
        )
    
    async def check_command_availability(self, command: str) -> bool:
        """Check if a command is available in the system"""
        try:
            result = await self.execute_command(
                f"which {command}" if os.name != 'nt' else f"where {command}",
                capture_output=True,
                timeout=5
            )
            return result.return_code == 0
        except:
            return False
    
    async def execute_async(self, job_id: str, command: str, working_directory: str = None, 
                          timeout: int = 30, job_storage: Dict = None):
        """Execute command asynchronously and store results in job storage"""
        try:
            if job_storage:
                job_storage[job_id]["status"] = "running"
                job_storage[job_id]["started_at"] = datetime.now().isoformat()
            
            result = await self.execute_command(
                command=command,
                working_directory=working_directory,
                timeout=timeout
            )
            
            if job_storage:
                job_storage[job_id].update({
                    "status": "completed" if result.return_code == 0 else "failed",
                    "completed_at": datetime.now().isoformat(),
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.return_code,
                    "duration": result.execution_time
                })
                
        except Exception as e:
            logger.error(f"Error in async execution {job_id}: {e}")
            if job_storage:
                job_storage[job_id].update({
                    "status": "error",
                    "completed_at": datetime.now().isoformat(),
                    "stderr": str(e),
                    "return_code": -1
                })