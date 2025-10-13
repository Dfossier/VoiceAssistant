# Quick Start Guide

Since your core functionality works perfectly, here's the streamlined approach:

## Method 1: Two Terminal Approach (Recommended)

### Terminal 1 (WSL2): Start Backend
```bash
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
./start_backend_only.sh
```

### Terminal 2 (Windows): Start Discord Bot
```cmd
cd C:\Users\dfoss\Desktop\LocalAIModels\Assistant
start_discord_only.bat
```

## Method 2: Just Commands

### WSL2 Terminal:
```bash
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
source venv/bin/activate
python main.py
```

### Windows Terminal:
```cmd
cd C:\Users\dfoss\Desktop\LocalAIModels\Assistant\WindowsDiscordBot
bot_venv_windows\Scripts\python.exe direct_audio_bot_working.py
```

## Why This Works Better

1. **No complex orchestration** - just start what you need
2. **Clear separation** - backend in WSL2, Discord bot in Windows  
3. **Easy debugging** - see logs directly in terminals
4. **GPU working** - models load on GPU as confirmed
5. **Voice pipeline working** - ws://localhost:8002 is active

The web dashboard complexity isn't worth the debugging time since your core voice system works perfectly.