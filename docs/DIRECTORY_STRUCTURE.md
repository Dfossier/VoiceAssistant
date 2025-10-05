# Local AI Assistant - Directory Structure

This document outlines the organized directory structure of the Local AI Assistant project after cleanup and reorganization.

## 📁 Root Directory Structure

```
assistant/
├── 📄 Core Files
│   ├── main.py                    # Primary backend server entry point
│   ├── justfile                   # System management commands (just start-all, just stop-all, etc.)
│   ├── start_production_system.sh # Production startup script (recommended)
│   ├── stop_production_system.sh  # Production shutdown script
│   ├── requirements.txt           # Python dependencies
│   ├── .env                      # Environment configuration (API keys, settings)
│   ├── CLAUDE.md                 # Project documentation and instructions
│   └── backend_production.log    # Current backend logs
│
├── 📂 src/                       # Source code
│   ├── api/                      # REST API endpoints
│   │   ├── system_control.py     # System control endpoints
│   │   └── __init__.py
│   ├── core/                     # Core application logic (18 essential files)
│   │   ├── server.py             # FastAPI server configuration
│   │   ├── local_models.py       # SmolLM2, Kokoro TTS, Faster-Whisper management
│   │   ├── enhanced_websocket_handler.py  # Voice pipeline WebSocket handler (port 8002)
│   │   ├── smart_turn_vad.py     # Voice Activity Detection (Smart Turn VAD v3)
│   │   ├── claude_code_service.py # Claude Code integration and detection
│   │   ├── terminal_detector.py  # Terminal window detection
│   │   ├── kokoro_tts_service.py # Kokoro neural TTS service
│   │   ├── llm_handler.py        # LLM processing and fallbacks
│   │   ├── file_monitor.py       # File system monitoring
│   │   ├── command_executor.py   # Command execution service
│   │   ├── config.py             # Configuration management
│   │   ├── vad_config.py         # VAD configuration loader
│   │   └── voice_command_processor.py # Voice command parsing
│   ├── services/                 # Additional services
│   └── utils/                    # Utility functions
│       ├── websocket_manager.py  # WebSocket connection management
│       └── setup.py              # Environment setup utilities
│
├── 📂 scripts/                   # Organized execution scripts
│   ├── launchers/                # Application launchers
│   │   ├── run_api_only.py       # API-only server (no voice pipeline)
│   │   └── run_voice_only.py     # Voice pipeline only
│   ├── services/                 # Service management scripts
│   └── install/                  # Installation and setup scripts
│
├── 📂 config/                    # Configuration files
│   ├── vad_config.json          # Voice Activity Detection settings
│   └── voice_commands.json      # Voice command mappings
│
├── 📂 WindowsDiscordBot/         # Discord bot (runs on native Windows)
│   ├── direct_audio_bot_working.py  # Main Discord bot with direct audio capture
│   ├── .env.example             # Discord bot environment template
│   └── logs/                    # Discord bot logs
│
├── 📂 web-dashboard/            # React-based web dashboard
│   ├── src/                     # React source code
│   ├── dist/                    # Built dashboard files
│   ├── package.json             # Node.js dependencies
│   └── node_modules/            # Node.js packages
│
├── 📂 models/                   # Local AI model storage
│   ├── faster-whisper/          # Faster-Whisper STT model cache
│   └── smart_turn/              # Smart Turn VAD model cache
│
├── 📂 static/                   # Static web assets
│   ├── css/                     # Stylesheets
│   ├── js/                      # JavaScript files
│   ├── images/                  # Images and icons
│   └── uploads/                 # File upload storage
│
├── 📂 data/                     # Application data
├── 📂 logs/                     # System logs
│   └── metrics/                 # Performance metrics logs
│
└── 📂 docs/                     # Documentation
    └── DIRECTORY_STRUCTURE.md   # This file
```

## 🗄️ Archive Structure

Archived materials are organized in clean subdirectories:

```
├── 📂 old_files/               # Archived files (organized cleanup)
│   ├── docs/                   # Old documentation
│   ├── logs/                   # Historical log files  
│   ├── test_files/             # Moved test scripts
│   ├── temp_files/             # Temporary development files
│   ├── runtime/                # Runtime artifacts
│   └── src_archive/            # Archived source files
│
└── 📂 archive/                 # Historical debugging sessions
    └── debugging_session_2025-09-13/  # Discord integration debugging
        ├── debug_scripts/      # Debugging tools
        ├── discord_bot_archive/ # Old Discord bot versions
        ├── old_docs/           # Historical documentation
        ├── test_scripts/       # Test and diagnostic scripts
        └── temp_files/         # Session temporary files
```

## 🚀 Key System Components

### Active Voice Pipeline
- **Enhanced WebSocket Handler**: `src/core/enhanced_websocket_handler.py` (port 8002)
- **Smart Turn VAD v3**: `src/core/smart_turn_vad.py` (96.8% optimized)
- **Local Models**: `src/core/local_models.py` (SmolLM2 1.7B, Kokoro TTS, Faster-Whisper)

### Discord Integration
- **Native Windows Bot**: `WindowsDiscordBot/direct_audio_bot_working.py`
- **Direct Audio Capture**: Bypasses Discord Opus codec issues
- **WSL2 Backend Communication**: Connects to `ws://172.20.104.13:8002`

### Development Tools
- **Just Commands**: `justfile` provides `start-all`, `stop-all`, `status`, `backend-logs`
- **API-Only Mode**: `scripts/launchers/run_api_only.py` for dashboard development
- **Web Dashboard**: React-based interface in `web-dashboard/`

## 📊 System Status (Current)
- **Root Directory**: 15 essential files (reduced from 75+)
- **src/core**: 18 essential files (reduced from 40+) 
- **Archived Files**: ~200+ files moved to organized archive structure
- **All Models**: ✅ SmolLM2 1.7B, Kokoro TTS, Faster-Whisper loaded
- **Voice Pipeline**: ✅ Enhanced WebSocket Handler operational
- **Terminal Detection**: ✅ 3 terminals, 1 Claude Code session detected

## 🔧 Quick Commands

### Production (Recommended)
```bash
# System Management
./start_production_system.sh    # Start complete production system
./stop_production_system.sh     # Stop all services
tail -f backend_production.log   # Monitor backend logs
```

### Development (Alternative)
```bash
# Just Commands
just start-all          # Start backend + Discord bot
just stop-all           # Stop all services  
just status             # Check system status
just backend-logs       # Monitor backend logs

# Specialized Development
python scripts/launchers/run_api_only.py  # API server only
cd web-dashboard && npm run dev           # Start dashboard
```

## 📝 Notes
- Backend logs to `backend_production.log` in production mode
- Discord bot requires native Windows environment
- WSL2 backend handles all ML models and file operations
- Web dashboard provides real-time system monitoring
- All configuration via `.env` and `config/*.json` files