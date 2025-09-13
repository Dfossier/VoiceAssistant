# Local AI Assistant Project (Discord-Based)

## Overview
A Discord-integrated AI assistant providing intelligent debugging and development assistance through voice and text channels. The backend API handles file monitoring, command execution, and context-aware AI responses.

## Core Features
- **Discord Integration**: Native voice and text chat support
- **File System Access**: Monitor and analyze project files
- **Command Execution**: Run and monitor processes
- **Context-Aware AI**: Intelligent responses with project context
- **Error Detection**: Automatic error monitoring and analysis
- **Multi-Model Support**: OpenAI, Anthropic, and local models
- **Async Processing**: High-performance async architecture

## System Architecture

### Voice Assistant Architecture (Final - Updated 2025-09-01)
```
┌─────────────────────────────────────────────────────┐
│          Discord Bot (Windows Native)               │
│  - Direct microphone capture (sounddevice/PyAudio)  │
│  - Bypasses Discord Opus codec completely          │  
│  - Real-time 16kHz mono PCM via WebSocket          │
│  - Commands: !direct, !stop                        │
└───────────────────┬─────────────────────────────────┘
                    │ WebSocket (ws://172.20.104.13:8001)
┌───────────────────▼─────────────────────────────────┐
│          Pipecat Voice Pipeline (WSL2)              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐│
│  │   Whisper   │  │    Phi-3     │  │  Kokoro    ││
│  │ SMALL STT   │  │ Mini GGUF    │  │    TTS     ││
│  │ (800MB-1.2GB│  │  (2.39GB)    │  │ (327MB)    ││
│  │ int8 quant) │  │ Q4_K_M quant │  │ Local .pth ││
│  └─────────────┘  └──────────────┘  └────────────┘│
│  ┌─────────────────────────────────────────────────┐│
│  │      Silero VAD + WebSocket Transport           ││
│  │  • Voice activity detection (auto start/stop)  ││
│  │  • Real-time interruption support              ││
│  │  • Streaming STT → LLM → TTS pipeline          ││
│  │  • All GPU-accelerated where possible          ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Key Architectural Decisions & Lessons Learned

#### **Critical Discovery: Discord Opus Incompatibility**
- **Problem**: Discord's py-cord WaveSink only captures ~15KB then stops (not true continuous streaming)
- **Root Cause**: Opus codec library architecture mismatches (32-bit vs 64-bit DLL issues)
- **Solution**: Completely bypass Discord audio system with direct microphone capture

#### **Final Working Architecture**
1. **Hybrid Windows/WSL2**: Discord bot runs natively on Windows for proper audio support, Pipecat backend in WSL2 for ML libraries
2. **Direct Audio Capture**: Uses sounddevice/PyAudio to capture system microphone, sending PCM directly to Pipecat
3. **Pipecat Integration**: Full Pipecat-compatible pipeline with native Whisper STT and OpenAI-compatible LLM services  
4. **Memory Optimized**: Total VRAM usage ~3.3GB (within constraint), all models pre-downloaded locally
5. **WSL2 Networking**: Uses WSL2 IP address (172.20.104.13) instead of localhost for reliable connection

#### **Technical Specifications**
- **Discord Bot**: Python 3.x, py-cord[voice], sounddevice, runs in `bot_venv_windows`
- **Backend**: Python 3.12.3, Pipecat 0.0.82.dev59, runs in WSL2 venv
- **Models**: All locally stored in `/mnt/c/users/dfoss/desktop/localaimodels/`
  - Parakeet-TDT: 2.47GB .nemo file (fallback STT)
  - Phi-3-Mini: 2.39GB .gguf Q4_K_M quantized (LLM with ALL GPU layers)
  - Kokoro TTS: 327MB .pth file (local TTS)
  - Whisper SMALL: Downloaded automatically by Pipecat (~800MB-1.2GB)

#### **Pipeline Flow**
1. User types `!direct` in Discord voice channel
2. Bot connects to voice channel, starts direct microphone capture
3. 16kHz mono PCM audio streamed to WebSocket server
4. Silero VAD detects speech boundaries automatically
5. Whisper STT transcribes audio to text
6. OpenAI-compatible service processes text through local Phi-3 model  
7. Local Kokoro TTS synthesizes response audio
8. Audio response streamed back through WebSocket to Discord

## API Endpoints

### Core Endpoints

#### Conversation Management
- `POST /api/conversation/message` - Process Discord message
- `GET /api/conversation/{user_id}/history` - Get conversation history
- `DELETE /api/conversation/{user_id}` - Clear conversation

#### File Operations
- `GET /api/files/content` - Read file content
- `POST /api/files/watch` - Add directory to watch
- `GET /api/files/changes` - Get recent file changes

#### Command Execution
- `POST /api/exec/command` - Execute command
- `GET /api/exec/status/{job_id}` - Check execution status
- `WebSocket /ws/exec/{job_id}` - Stream command output

## Configuration

### Environment Variables (.env)
```env
# API Configuration
API_KEY=your_secure_api_key
PORT=8000

# LLM Configuration
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# File Monitoring
WATCH_DIRECTORIES=/home/user/projects
MAX_FILE_SIZE_MB=10

# Security
ALLOWED_DIRECTORIES=/home/user/projects,/mnt/c/users
RATE_LIMIT_PER_MINUTE=60
```

## Discord Bot Requirements

The Discord bot (separate project) must support:

1. **Voice Handling**
   - Join/leave voice channels
   - Audio capture and transcription
   - Voice activity detection

2. **API Communication**
   - REST client for backend API
   - WebSocket for streaming
   - Proper error handling

3. **Commands**
   - `!ask` - Ask questions
   - `!debug` - Debug errors
   - `!run` - Execute commands
   - `!watch` - Monitor directories

## Development Principles

### Critical Guidelines
- **Never use fallback simulated responses** - Always explore and fix root cause issues
- **Real functionality only** - Simulated responses are misleading and should be avoided  
- **Fix dependencies properly** - Don't mask issues with workarounds
- **Debug systematically** - Identify and resolve actual problems, not symptoms

### Available Just Commands

The project includes a Justfile with helpful commands for managing the system:

#### Discord Bot Management
- `just discord-start-bg` - Start Discord bot in background on Windows
- `just discord-stop-bg` - Stop Discord bot background processes

#### Backend Management  
- `just backend-start` - Start backend server in background
- `just backend-stop` - Stop backend server
- `just backend-logs` - Show backend logs in real-time

#### Full System Control
- `just start-all` - Start both backend and Discord bot
- `just stop-all` - Stop all services
- `just status` - Check if services are running
- `just clean-logs` - Clean up log files

**Example Usage:**
```bash
# Start everything
just start-all

# Check status
just status

# Monitor backend logs
just backend-logs

# Stop everything
just stop-all
```

### PRIMARY SYSTEM RULES

#### **Rule 1: Discord Bot Environment**
- **MUST run Discord bot natively on Windows** - NOT in WSL2
- WSL2 causes Discord voice connection Error 4006 due to network/audio subsystem limitations
- Backend API runs in WSL2, Discord bot runs in native Windows
- Use Windows Python installation for Discord bot

#### **Rule 2: No Simulated Data**
- **NEVER use simulated, mock, or fake functionality**
- Always implement real functionality or clearly state limitations
- If a feature cannot be implemented, explain why and propose alternatives
- Remove any existing simulated components immediately when detected

#### **Rule 3: Root Cause Solutions Only**
- Address fundamental issues, not symptoms
- Change system architecture when necessary for proper functionality
- Don't use workarounds that mask underlying problems
- Investigate and resolve compatibility issues at their source

## Development Setup

### Prerequisites
- **Backend API**: Python 3.11+ in WSL2 (for file system access)
- **Discord Bot**: Python 3.11+ on native Windows (for voice support)
- Git (both environments)
- FFmpeg (for audio processing)

### Hybrid Architecture Setup

#### Backend API (WSL2)
```bash
# In WSL2 terminal
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Start backend server
python main.py
```

#### Discord Bot (Native Windows)
```cmd
# In Windows Command Prompt or PowerShell
cd C:\users\dfoss\desktop\localaimodels\assistant\WindowsDiscordBot

# Create virtual environment (if not exists)
python -m venv bot_venv_windows
bot_venv_windows\Scripts\activate

# Install Discord library with voice support and audio libraries
pip install py-cord[voice] python-dotenv httpx aiohttp loguru sounddevice pyaudio

# Copy environment file
copy .env.example .env
# Edit .env with Discord token

# Start Discord bot with direct audio capture
bot_venv_windows\Scripts\python direct_audio_bot.py
```

### Voice Assistant Commands

#### **Discord Commands**
- `!direct` - Start direct audio capture and voice conversation
- `!stop` - Stop audio capture and disconnect

#### **Usage Example**
1. Join a Discord voice channel
2. Type `!direct` in chat  
3. Bot will connect and show status: "🟢 **Speak now** - I'm capturing directly!"
4. Speak naturally - the system will:
   - Capture your voice directly from microphone
   - Transcribe with Whisper STT
   - Process through local Phi-3 model
   - Generate voice response with Kokoro TTS
5. Type `!stop` to end the conversation

### **Final Working Configuration (Updated 2025-09-13)**

#### **Kokoro TTS - High-Quality Neural Voice Synthesis**
The system now successfully uses **Kokoro neural TTS** instead of espeak fallback:

**Key Configuration:**
- **Model**: Kokoro-v1.0 (312MB, StyleTTS2-based, 82M parameters)  
- **Audio Quality**: 24kHz mono, 16-bit PCM with 1.5x volume boost
- **Integration**: Direct service bypass (dummy implementation disabled)
- **Phonemizer**: Version 3.1.1 with compatibility patches for misaki

**Working Components:**
```
┌─── Kokoro TTS Service (src/core/kokoro_tts_service.py) ───┐
│  ✅ Real neural synthesis with KPipeline                 │
│  ✅ 1.5x volume scaling for Discord compatibility        │
│  ✅ 24kHz output with proper amplitude (>1000/32767)     │
│  ✅ Eager loading at startup (no lazy initialization)    │
└─────────────────────────────────────────────────────────┘
            ↓
┌─── Integration Layer (src/core/kokoro_integration.py) ───┐
│  ✅ Dummy direct method disabled (was generating silence)│
│  ✅ Forces fallback to real Kokoro service               │
│  ✅ Proper error handling and logging                    │
└─────────────────────────────────────────────────────────┘
            ↓
┌─── Local Models Manager (src/core/local_models.py) ──────┐
│  ✅ Eager loading enabled (eager_load=True)              │
│  ✅ Kokoro integration persistence fixed                 │
│  ✅ All models loaded at startup for performance         │
└─────────────────────────────────────────────────────────┘
```

**Critical Fixes Applied:**
1. **Phonemizer Compatibility**: Downgraded from 3.3.0 to 3.1.1, added monkey patch for missing `EspeakWrapper.set_data_path`
2. **Volume Scaling**: Fixed direct wrapper volume boost (0.0001 → proper 1.5x scaling)
3. **Integration Path**: Disabled dummy synthesis, forces real Kokoro service usage
4. **Model Loading**: Removed all lazy loading, implements eager initialization
5. **Error Handling**: Proper fallback chain with detailed logging

**Audio Quality Verification:**
- **Kokoro Output**: 144KB+ files, max amplitude >15,000/32767 (50%+), RMS >2000
- **Previous espeak**: 571KB files (uncompressed WAV headers)
- **Failed dummy**: 57KB files, max amplitude <100/32767 (<1%)

**Environment Dependencies:**
```bash
# Critical package versions
phonemizer==3.1.1          # Downgraded for misaki compatibility  
numpy==2.2.6               # Downgraded for Parakeet compatibility
kokoro>=0.9.2              # Neural TTS with KPipeline support
torch>=2.3.1+cu121         # GPU acceleration for all models
```

### Debugging & Management Commands

#### **Backend Management**
```bash
# Check if backend is running
ps aux | grep python | grep main.py

# Start backend
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
source venv/bin/activate
python main.py > backend.log 2>&1 &

# Stop backend
pkill -f "python main.py"

# Check backend logs
tail -f backend.log
```

#### **Model Status Check**
```bash
# Check model files
ls -la /mnt/c/users/dfoss/desktop/localaimodels/

# Verify Pipecat installation
pip list | grep pipecat

# Test WebSocket connection
python test_pipecat_format.py
```

### Why This Architecture?
- **WSL2 Backend**: Excellent for file system monitoring, command execution
- **Windows Discord Bot**: Required for proper voice connections and audio processing
- **Communication**: Discord bot connects to WSL2 backend via HTTP API

## Benefits of Discord Integration

1. **Native Voice Support** - No browser microphone issues
2. **Cross-Platform** - Works on all devices with Discord
3. **No HTTPS/Certificates** - Discord handles security
4. **Rich Formatting** - Code blocks, embeds, reactions
5. **File Uploads** - Built-in file sharing
6. **Persistent Connection** - No timeout issues
7. **User Authentication** - Discord handles user management

## Security Considerations

- API key authentication required
- File access restricted to allowed directories
- Command execution sandboxed
- Rate limiting per Discord user
- No sensitive data in logs

## License
MIT License - See LICENSE file for details