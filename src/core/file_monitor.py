"""File system monitoring and analysis"""
import asyncio
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Set, Any
from dataclasses import dataclass
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
import aiofiles
from loguru import logger

@dataclass
class FileChange:
    """Represents a file system change"""
    path: Path
    event_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    file_size: Optional[int] = None
    is_directory: bool = False


@dataclass
class FileAnalysis:
    """Analysis of a file's content"""
    path: Path
    file_type: str
    content_preview: str
    line_count: int
    has_errors: bool
    error_lines: List[int]
    last_modified: datetime
    size_bytes: int


class CodeAnalyzer:
    """Analyze code files for errors and context"""
    
    ERROR_PATTERNS = {
        'python': [
            r'Traceback \(most recent call last\)',
            r'^\s*File ".*", line \d+',
            r'SyntaxError:', r'NameError:', r'TypeError:', r'ValueError:',
            r'ImportError:', r'AttributeError:', r'KeyError:', r'IndexError:'
        ],
        'cpp': [
            r'error:', r'Error:', r'ERROR:',
            r'fatal error:', r'compilation terminated',
            r'undefined reference', r'undefined symbol'
        ],
        'javascript': [
            r'Error:', r'TypeError:', r'ReferenceError:',
            r'SyntaxError:', r'RangeError:', r'URIError:'
        ],
        'log': [
            r'\[ERROR\]', r'\[FATAL\]', r'\[CRITICAL\]',
            r'ERROR:', r'FATAL:', r'CRITICAL:',
            r'Exception:', r'Stack trace:', r'Caused by:'
        ]
    }
    
    @staticmethod
    def detect_file_type(path: Path) -> str:
        """Detect file type from extension and content"""
        suffix = path.suffix.lower()
        
        type_mapping = {
            '.py': 'python',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c': 'cpp',
            '.h': 'cpp', '.hpp': 'cpp', '.hxx': 'cpp',
            '.js': 'javascript', '.ts': 'javascript', '.jsx': 'javascript',
            '.log': 'log', '.txt': 'log'
        }
        
        return type_mapping.get(suffix, 'text')
    
    @staticmethod
    async def analyze_file(path: Path, max_size_mb: int = 10) -> Optional[FileAnalysis]:
        """Analyze a file for content and errors"""
        try:
            stat = path.stat()
            
            # Check file size
            if stat.st_size > max_size_mb * 1024 * 1024:
                logger.warning(f"Skipping large file: {path} ({stat.st_size / 1024 / 1024:.1f}MB)")
                return None
                
            file_type = CodeAnalyzer.detect_file_type(path)
            
            # Read file content
            async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()
                
            lines = content.split('\n')
            error_lines = CodeAnalyzer._find_error_lines(content, file_type)
            
            return FileAnalysis(
                path=path,
                file_type=file_type,
                content_preview=content[:1000] + ("..." if len(content) > 1000 else ""),
                line_count=len(lines),
                has_errors=len(error_lines) > 0,
                error_lines=error_lines,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=stat.st_size
            )
            
        except Exception as e:
            logger.error(f"Error analyzing file {path}: {e}")
            return None
    
    @staticmethod
    def _find_error_lines(content: str, file_type: str) -> List[int]:
        """Find lines containing potential errors"""
        import re
        
        patterns = CodeAnalyzer.ERROR_PATTERNS.get(file_type, [])
        if not patterns:
            return []
            
        error_lines = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    error_lines.append(i)
                    break
                    
        return error_lines
    
    @staticmethod
    def extract_error_context(path: Path, error_line: int, context_lines: int = 5) -> str:
        """Extract context around an error line"""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            start = max(0, error_line - context_lines - 1)
            end = min(len(lines), error_line + context_lines)
            
            context = []
            for i in range(start, end):
                marker = " -> " if i == error_line - 1 else "    "
                context.append(f"{i+1:4d}{marker}{lines[i].rstrip()}")
                
            return '\n'.join(context)
            
        except Exception as e:
            logger.error(f"Error extracting context from {path}: {e}")
            return ""


class FileSystemEventHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self, callback: Callable[[FileChange], None], ignore_patterns: List[str]):
        super().__init__()
        self.callback = callback
        self.ignore_patterns = [pattern.lower() for pattern in ignore_patterns]
        self.last_events = {}  # Debounce duplicate events
        
    def _should_ignore(self, path: str) -> bool:
        """Check if file should be ignored based on patterns"""
        path_lower = path.lower()
        
        for pattern in self.ignore_patterns:
            if pattern.startswith('*'):
                if path_lower.endswith(pattern[1:]):
                    return True
            elif pattern in path_lower:
                return True
                
        return False
    
    def _debounce_event(self, event) -> bool:
        """Debounce rapid file events (like save operations)"""
        now = time.time()
        key = (event.src_path, event.event_type)
        
        if key in self.last_events:
            if now - self.last_events[key] < 0.5:  # 500ms debounce
                return False
                
        self.last_events[key] = now
        return True
    
    def on_modified(self, event):
        if not self._should_ignore(event.src_path) and self._debounce_event(event):
            change = FileChange(
                path=Path(event.src_path),
                event_type='modified',
                timestamp=datetime.now(),
                is_directory=event.is_directory
            )
            self.callback(change)
            
    def on_created(self, event):
        if not self._should_ignore(event.src_path):
            change = FileChange(
                path=Path(event.src_path),
                event_type='created', 
                timestamp=datetime.now(),
                is_directory=event.is_directory
            )
            self.callback(change)
            
    def on_deleted(self, event):
        if not self._should_ignore(event.src_path):
            change = FileChange(
                path=Path(event.src_path),
                event_type='deleted',
                timestamp=datetime.now(),
                is_directory=event.is_directory
            )
            self.callback(change)


class FileMonitor:
    """Monitor file system changes and provide analysis"""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.observers = []
        self.change_callbacks = []
        self.recent_changes = []
        self.max_recent_changes = 100
        self.watched_directories = {}  # user_id -> list of directories
        self.ignore_patterns = ['*.pyc', '__pycache__', '*.tmp', '.git', 'node_modules', 'venv']
        
    async def start_monitoring(self):
        """Start monitoring configured directories"""
        logger.info("Starting file system monitoring...")
        
        # Only monitor current directory for faster startup
        current_dir = str(Path.cwd())
        await self._watch_directory(current_dir)
            
        logger.info(f"Monitoring {len(self.observers)} directories")
        
    async def stop_monitoring(self):
        """Stop monitoring all directories"""
        logger.info("Stopping file system monitoring...")
        
        for observer in self.observers:
            try:
                observer.stop()
                observer.join()
            except Exception as e:
                logger.error(f"Error stopping observer: {e}")
                
        self.observers.clear()
        logger.info("File system monitoring stopped")
    
    async def watch_directory(self, directory: str, patterns: List[str] = None, user_id: str = None) -> bool:
        """Add directory to monitoring for specific user"""
        try:
            success = await self._watch_directory(directory)
            if success and user_id:
                if user_id not in self.watched_directories:
                    self.watched_directories[user_id] = []
                self.watched_directories[user_id].append({
                    "directory": directory,
                    "patterns": patterns or ["*"],
                    "added_at": datetime.now()
                })
            return success
        except Exception as e:
            logger.error(f"Error watching directory {directory}: {e}")
            return False
    
    async def add_watch_directory(self, user_id: str, directory: str, patterns: List[str] = None) -> bool:
        """Add directory to monitoring for specific user"""
        return await self.watch_directory(directory, patterns, user_id)
        
    async def _watch_directory(self, directory: str) -> bool:
        """Watch a single directory"""
        path = Path(directory)
        
        if not path.exists():
            logger.warning(f"Watch directory does not exist: {directory}")
            return False
            
        observer = Observer()
        event_handler = FileSystemEventHandler(
            callback=self._handle_file_change,
            ignore_patterns=self.ignore_patterns
        )
        
        observer.schedule(event_handler, str(path), recursive=True)
        observer.start()
        self.observers.append(observer)
        
        logger.info(f"Watching directory: {directory}")
        return True
        
    def _handle_file_change(self, change: FileChange):
        """Handle a file system change"""
        logger.debug(f"File {change.event_type}: {change.path}")
        
        # Add to recent changes
        self.recent_changes.append(change)
        if len(self.recent_changes) > self.max_recent_changes:
            self.recent_changes.pop(0)
            
        # Notify callbacks
        for callback in self.change_callbacks:
            try:
                # Check if there's a running event loop
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(callback(change))
                except RuntimeError:
                    # No running event loop, skip silently
                    continue
            except Exception as e:
                # Only log non-asyncio errors
                if "no running event loop" not in str(e).lower():
                    logger.error(f"Error in change callback: {e}")
                
    def add_change_callback(self, callback: Callable[[FileChange], None]):
        """Add a callback for file changes"""
        self.change_callbacks.append(callback)
        
    async def get_recent_changes(self, user_id: str = None, limit: int = 20) -> List[Dict]:
        """Get recent file changes"""
        changes = self.recent_changes[-limit:]
        
        # Convert to dict format for JSON serialization
        return [
            {
                "path": str(change.path),
                "event_type": change.event_type,
                "timestamp": change.timestamp.isoformat(),
                "is_directory": change.is_directory,
                "file_size": change.file_size
            }
            for change in changes
        ]
        
    async def analyze_recent_errors(self) -> List[FileAnalysis]:
        """Analyze recent changes for errors"""
        error_files = []
        
        for change in self.recent_changes[-10:]:  # Last 10 changes
            if change.event_type in ['modified', 'created'] and not change.is_directory:
                max_file_size = self.settings.max_file_size_mb if self.settings else 10
                analysis = await CodeAnalyzer.analyze_file(
                    change.path, 
                    max_file_size
                )
                
                if analysis and analysis.has_errors:
                    error_files.append(analysis)
                    
        return error_files
        
    async def get_file_content(self, file_path: str, max_lines: int = None) -> Optional[str]:
        """Get file content with optional line limit"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                if max_lines:
                    lines = []
                    async for line in f:
                        lines.append(line)
                        if len(lines) >= max_lines:
                            break
                    return ''.join(lines)
                else:
                    return await f.read()
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
            
    async def search_files(self, pattern: str, file_types: List[str] = None) -> List[Path]:
        """Search for files matching a pattern"""
        import re
        from pathlib import Path
        
        matching_files = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        for directory in self.settings.get_watch_directories():
            path = Path(directory)
            if not path.exists():
                continue
                
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    # Check file type filter
                    if file_types:
                        file_type = CodeAnalyzer.detect_file_type(file_path)
                        if file_type not in file_types:
                            continue
                            
                    # Check pattern match (filename or content)
                    if regex.search(str(file_path.name)):
                        matching_files.append(file_path)
                        continue
                        
                    # Search in content for small files
                    try:
                        if file_path.stat().st_size < 1024 * 1024:  # 1MB limit
                            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = await f.read()
                                if regex.search(content):
                                    matching_files.append(file_path)
                    except:
                        pass
                        
        return matching_files[:50]  # Limit results
        
    async def get_directory_structure(self, path: str, max_depth: int = 3) -> Dict:
        """Get directory structure as a tree"""
        try:
            root_path = Path(path)
            if not root_path.exists():
                return {"error": "Directory does not exist"}
            
            def build_tree(current_path: Path, current_depth: int = 0) -> Dict:
                if current_depth >= max_depth:
                    return {"...": "max_depth_reached"}
                
                tree = {}
                try:
                    for item in sorted(current_path.iterdir()):
                        if item.name.startswith('.'):  # Skip hidden files
                            continue
                        
                        if item.is_directory():
                            tree[f"{item.name}/"] = build_tree(item, current_depth + 1)
                        else:
                            tree[item.name] = {
                                "size": item.stat().st_size,
                                "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                            }
                except PermissionError:
                    tree["error"] = "Permission denied"
                
                return tree
            
            return {
                "name": root_path.name,
                "path": str(root_path),
                "tree": build_tree(root_path)
            }
            
        except Exception as e:
            logger.error(f"Error getting directory structure: {e}")
            return {"error": str(e)}
    
    async def scan_for_errors(self, path: str = None) -> List[Dict]:
        """Scan for errors in files"""
        try:
            errors = []
            scan_path = Path(path) if path else Path.cwd()
            
            for file_path in scan_path.rglob("*.py"):  # Focus on Python files for now
                if any(pattern in str(file_path) for pattern in self.ignore_patterns):
                    continue
                
                analysis = await CodeAnalyzer.analyze_file(file_path, max_size_mb=5)
                if analysis and analysis.has_errors:
                    errors.append({
                        "path": str(analysis.path),
                        "file_type": analysis.file_type,
                        "error_lines": analysis.error_lines,
                        "line_count": analysis.line_count,
                        "last_modified": analysis.last_modified.isoformat()
                    })
                
                if len(errors) >= 20:  # Limit results
                    break
            
            return errors
            
        except Exception as e:
            logger.error(f"Error scanning for errors: {e}")
            return []

    async def stop(self):
        """Stop all file monitoring (renamed from stop_monitoring)"""
        logger.info("Stopping file system monitoring...")
        
        for observer in self.observers:
            observer.stop()
            observer.join()
            
        self.observers.clear()
        logger.info("File monitoring stopped")