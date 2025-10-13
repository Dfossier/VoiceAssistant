# Discord Bot Migration to Windows

This guide covers migrating the Discord bot from WSL to native Windows to resolve voice connection issues.

## New Architecture

```
Windows Host:
├── WindowsDiscordBot/        # Native Windows Discord bot
│   ├── bot.py               # Main bot file
│   ├── voice_handler.py     # Windows-optimized voice handling
│   ├── backend_client.py    # API client for WSL backend
│   ├── config.py           # Configuration
│   └── requirements.txt    # Python dependencies
│
├── service_manager.py       # Central management GUI
├── start_all.bat           # Start all services
├── stop_all.bat            # Stop all services
│
WSL (Ubuntu):
└── [Existing Backend]      # LLM API, File Monitor, etc.
    ├── src/                # Backend source code
    ├── main.py            # Backend entry point
    └── requirements.txt   # Backend dependencies
```

## Setup Instructions

### 1. Stop Current Services

```bash
# Stop the WSL Discord bot
pkill -f "python.*bot.py"

# Keep the backend running or restart it
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
python3 main.py
```

### 2. Set Up Windows Discord Bot

**Option A: Quick Setup (Batch File)**
```cmd
cd C:\Users\dfoss\Desktop\localaimodels\assistant\WindowsDiscordBot
setup_windows.bat
```

**Option B: Manual Setup**
```cmd
cd C:\Users\dfoss\Desktop\localaimodels\assistant\WindowsDiscordBot

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create logs directory
mkdir logs
```

### 3. Configure Environment

Ensure your `.env` file in the root directory contains:
```env
# Discord Bot
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Backend API
API_KEY=your_secure_api_key
BACKEND_API_URL=http://localhost:8000

# Optional: Logging
BOT_LOG_LEVEL=INFO
```

### 4. Start Services

**Option A: Use Service Manager (Recommended)**
```cmd
cd C:\Users\dfoss\Desktop\localaimodels\assistant
python service_manager.py
```

**Option B: Use Batch Scripts**
```cmd
cd C:\Users\dfoss\Desktop\localaimodels\assistant
start_all.bat
```

**Option C: Manual Start**
```cmd
# Terminal 1: Start Backend (if not running)
wsl -d Ubuntu bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"

# Terminal 2: Start Windows Discord Bot
cd C:\Users\dfoss\Desktop\localaimodels\assistant\WindowsDiscordBot
venv\Scripts\activate
python bot.py
```

## Key Improvements

### ✅ Voice Connection Fixes
- **Native Windows networking** - No more WSL network translation issues
- **Proper Opus codec support** - Windows-native audio libraries
- **Stable WebSocket connections** - Direct Discord API communication
- **Enhanced error handling** - Better voice connection diagnostics

### ✅ Service Management
- **Central GUI interface** - Monitor and control both services
- **Real-time status updates** - CPU, memory, uptime tracking
- **Integrated log viewer** - View logs from both services
- **One-click start/stop/restart** - Easy service management

### ✅ Enhanced Features
- **Windows-optimized voice handler** - Better audio processing
- **Improved backend client** - More robust API communication
- **Better error reporting** - Detailed error messages and logs
- **Graceful shutdown handling** - Clean service termination

## Testing Voice Functionality

1. **Start both services** using the Service Manager
2. **Join a voice channel** in Discord
3. **Use `!join`** to connect the bot
4. **Test with `!voice_test Hello world`** to verify functionality
5. **Try actual voice input** (if transcription is implemented)

## Commands Available

### Voice Commands
- `!join` - Join your voice channel
- `!leave` - Leave voice channel  
- `!voice_test <message>` - Test voice input simulation

### Chat Commands
- `!ask <question>` - Ask AI a question
- `!run <command>` - Execute system command
- `!debug` - Analyze recent file changes
- `!status` - Show system status
- `!help` - Show command help

## Troubleshooting

### Voice Connection Issues
- **Error 4006**: Should be resolved with Windows migration
- **Opus not loaded**: Ensure `discord.py[voice]` is installed
- **FFmpeg not found**: Install FFmpeg and add to PATH

### Backend Connection Issues
- **Connection refused**: Ensure WSL backend is running on port 8000
- **API key errors**: Check `.env` file has correct `API_KEY`
- **Health check fails**: Verify `curl http://localhost:8000/health` works

### Service Manager Issues
- **Python not found**: Ensure Python 3.11+ is installed on Windows
- **Permission errors**: Run as administrator if needed
- **WSL commands fail**: Ensure WSL is properly configured

## Migration Verification

After migration, verify:

1. **✅ Backend API running** - `curl http://localhost:8000/health`
2. **✅ Discord bot connected** - Bot shows online in Discord
3. **✅ Voice connection works** - `!join` succeeds without 4006 errors
4. **✅ Commands work** - `!ask`, `!run`, `!status` respond correctly
5. **✅ Service manager shows both running** - GUI displays green status

## File Structure

```
assistant/
├── WindowsDiscordBot/           # New Windows Discord bot
│   ├── bot.py                  # Main bot (Windows-optimized)
│   ├── voice_handler.py        # Windows voice handling
│   ├── backend_client.py       # API client
│   ├── config.py              # Configuration
│   ├── requirements.txt       # Dependencies
│   ├── setup_windows.bat      # Setup script
│   ├── venv/                  # Virtual environment
│   └── logs/                  # Bot logs
│
├── DiscordBot/                 # Old WSL bot (can be archived)
├── src/                       # Backend source (unchanged)
├── service_manager.py         # Central management GUI
├── start_all.bat             # Start all services
├── stop_all.bat              # Stop all services
└── MIGRATION_GUIDE.md        # This file
```

## Next Steps

1. **Test voice functionality thoroughly** 
2. **Archive old WSL bot** once migration is confirmed working
3. **Set up automated startup** (Windows startup scripts if desired)
4. **Configure firewall rules** if needed for backend API
5. **Monitor performance** and tune settings as needed

The migration resolves the core WSL voice issues while maintaining all existing functionality with a improved management interface.