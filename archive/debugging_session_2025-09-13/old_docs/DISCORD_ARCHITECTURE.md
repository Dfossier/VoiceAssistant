# Discord AI Assistant Architecture

## Overview
A Discord-based AI assistant that provides intelligent help through voice and text channels, with backend services for file monitoring, command execution, and context-aware assistance.

## Architecture Components

### 1. Discord Bot (Separate Project)
- Runs independently, connects to Discord
- Communicates with backend via REST API and WebSockets
- Handles voice transcription locally or via API

### 2. Backend API Server (This Project)
Main orchestration server providing services to the Discord bot.

## Backend Functionality

### Core Services

#### 1. Conversation Management API
- **POST /api/conversation/message** - Process a message from Discord
- **GET /api/conversation/{user_id}/history** - Retrieve conversation history
- **DELETE /api/conversation/{user_id}** - Clear conversation memory
- **POST /api/conversation/{user_id}/context** - Add file/error context

#### 2. File Monitoring Service
- Watches configured directories for changes
- Detects errors in log files
- Provides code context for debugging
- **GET /api/files/changes** - Recent file changes
- **POST /api/files/watch** - Add directory to watch list
- **GET /api/files/content** - Read file with syntax highlighting

#### 3. Command Execution API
- **POST /api/exec/command** - Execute shell command
- **GET /api/exec/status/{job_id}** - Check command status
- **GET /api/exec/output/{job_id}** - Get command output
- **WebSocket /ws/exec/{job_id}** - Stream command output

#### 4. Project Context Service
- **GET /api/project/structure** - Get project file tree
- **GET /api/project/errors** - Current errors across project
- **POST /api/project/analyze** - Analyze code for issues

#### 5. LLM Processing Service
- Handles all AI model interactions
- Supports multiple models (OpenAI, Anthropic, local)
- Context-aware responses with file/error information
- **POST /api/llm/complete** - Get AI completion
- **POST /api/llm/stream** - Stream AI response

## Communication Modes

### 1. REST API (Primary)
- JSON-based request/response
- Authentication via API key
- Rate limiting per Discord user

### 2. WebSocket (Real-time)
- For streaming responses
- Command output streaming
- File change notifications

### 3. Message Queue (Optional)
- Redis or RabbitMQ for async tasks
- Handle long-running operations
- Prevent timeout issues

## Discord Bot Requirements

### Core Requirements
1. **Authentication**
   - API key for backend communication
   - Discord bot token
   - User ID tracking

2. **Voice Capabilities**
   - Join/leave voice channels
   - Voice activity detection
   - Audio streaming to backend or local transcription

3. **Text Processing**
   - Command parsing (e.g., !help, !debug, !run)
   - Code block formatting
   - Error message detection

4. **Context Management**
   - Track current working directory per user
   - Remember active project/files
   - Maintain conversation state

### API Integration Requirements
1. **HTTP Client**
   - Async requests to backend
   - Proper error handling
   - Retry logic with exponential backoff

2. **WebSocket Client**
   - Maintain persistent connection
   - Handle reconnection
   - Process streaming data

3. **File Handling**
   - Upload files to backend
   - Display file contents with syntax highlighting
   - Handle large files with pagination

### Command Examples
```
!ask How do I fix this Python error?
!debug error.log
!run python main.py
!watch /path/to/project
!explain function_name
!fix "error message"
!status
!clear
```

## Data Flow

### Voice Conversation Flow
```
1. User speaks in Discord voice channel
2. Bot captures audio
3. Bot transcribes (local Whisper or API)
4. Bot sends text to backend API
5. Backend processes with context
6. Backend returns AI response
7. Bot sends response to Discord (text or TTS)
```

### Error Debugging Flow
```
1. File monitor detects error in log
2. Backend analyzes error context
3. Notification sent via WebSocket
4. Bot alerts user in Discord
5. User requests help with !debug
6. Backend provides contextual solution
```

## Backend API Endpoints

### Authentication
All endpoints require header: `X-API-Key: {api_key}`

### Endpoints

#### Conversation
```
POST /api/conversation/message
{
  "user_id": "discord_user_id",
  "message": "user message",
  "context": {
    "channel_id": "discord_channel_id",
    "current_directory": "/path/to/project",
    "active_files": ["file1.py", "file2.py"]
  }
}

Response:
{
  "response": "AI response",
  "suggestions": ["command1", "command2"],
  "files_referenced": ["file.py:125"]
}
```

#### Command Execution
```
POST /api/exec/command
{
  "user_id": "discord_user_id",
  "command": "python main.py",
  "working_directory": "/path/to/project",
  "timeout": 30000
}

Response:
{
  "job_id": "uuid",
  "status": "running"
}
```

#### File Operations
```
GET /api/files/content?path=/path/to/file&lines=50-100

POST /api/files/watch
{
  "user_id": "discord_user_id",
  "directory": "/path/to/watch",
  "patterns": ["*.py", "*.log"]
}
```

## Configuration

### Backend Configuration (.env)
```env
# API Settings
API_KEY=your_secure_api_key
PORT=8000
HOST=0.0.0.0

# LLM Configuration
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
LOCAL_MODEL_PATH=/path/to/model

# File Monitoring
MAX_WATCH_DIRECTORIES=10
FILE_CHANGE_DEBOUNCE_MS=1000

# Security
ALLOWED_DIRECTORIES=/home/user/projects,/mnt/c/users
MAX_FILE_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=60

# Redis (optional)
REDIS_URL=redis://localhost:6379
```

### Discord Bot Requirements Configuration
```env
# Discord
DISCORD_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_client_id

# Backend API
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=your_secure_api_key

# Voice Settings
VOICE_ACTIVATION_THRESHOLD=0.1
SILENCE_DURATION_MS=1500
MAX_RECORDING_DURATION_MS=30000

# Features
ENABLE_VOICE=true
ENABLE_FILE_UPLOAD=true
ENABLE_CODE_EXECUTION=true
```

## Security Considerations

1. **API Authentication**
   - Strong API keys
   - Rate limiting per user
   - IP whitelist option

2. **File Access**
   - Restricted to allowed directories
   - No access to sensitive files
   - File size limits

3. **Command Execution**
   - Sandboxed environment
   - Timeout limits
   - Resource restrictions
   - Command whitelist option

4. **Data Privacy**
   - User data isolation
   - Conversation history retention limits
   - No logging of sensitive content

## Development Phases

### Phase 1: Core API (Week 1)
- Basic FastAPI structure
- Conversation endpoint
- LLM integration
- Simple authentication

### Phase 2: File Services (Week 2)  
- File monitoring with watchdog
- File content API
- Error detection

### Phase 3: Execution Engine (Week 3)
- Command execution API
- Output streaming
- Job management

### Phase 4: Advanced Features (Week 4)
- WebSocket support
- Redis integration
- Performance optimization
- Security hardening

## Benefits Over Browser Approach

1. **No HTTPS/certificate issues**
2. **Native voice chat support**
3. **Works on all devices with Discord**
4. **Better mobile experience**
5. **Built-in authentication**
6. **Persistent connection**
7. **Rich formatting support**
8. **File uploads built-in**
9. **Screen sharing capability**
10. **No firewall/port forwarding needed**