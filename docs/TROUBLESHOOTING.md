# Voice Assistant Troubleshooting Guide

## Current System Status (as of 17:30)

### ✅ Working Components:
- **Backend API**: Running on port 8000 with all models loaded
- **WebSocket Server**: Active on port 8002 (ws://172.20.104.13:8002)
- **Web Dashboard**: Accessible at http://172.20.104.13:3000/
- **Models**: STT (Faster-Whisper), LLM (SmolLM2), TTS (Kokoro) all loaded

### ❌ Issue: Discord Bot Not Connecting to WebSocket

The Discord bot joins the voice channel but is not connecting to the backend WebSocket, which prevents audio processing.

## To Fix the Discord Bot Connection:

1. **On Windows (where Discord bot runs):**
   ```cmd
   cd C:\Users\dfoss\Desktop\LocalAIModels\Assistant\WindowsDiscordBot
   ```

2. **Kill any existing bot processes:**
   ```powershell
   Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Where-Object {$_.CommandLine -like "*discord*"} | Stop-Process -Force
   ```

3. **Start the bot with the batch file created:**
   ```cmd
   start_direct_audio_bot.bat
   ```

4. **In the bot console window, you should see:**
   - Bot logging in
   - "Connected to backend WebSocket" message
   - If you see connection errors, the WebSocket URL might be wrong

5. **In Discord:**
   - Join a voice channel
   - Type `!direct` to start audio capture
   - Bot should respond with "🟢 **Speak now** - I'm capturing directly!"

## Monitoring the Connection:

**In WSL2 terminal, monitor backend logs:**
```bash
tail -f backend.log | grep -E "(Client connected|WebSocket|audio)"
```

When the bot connects properly, you should see:
```
Client connected from 172.20.96.1:xxxxx
New WebSocket connection established
```

## If Bot Still Doesn't Connect:

1. **Check Windows Firewall** - ensure Python is allowed
2. **Verify IP address** hasn't changed:
   ```bash
   hostname -I | awk '{print $1}'
   ```
3. **Test WebSocket manually** from Windows:
   ```powershell
   python -c "import websockets; import asyncio; asyncio.run(websockets.connect('ws://172.20.104.13:8002'))"
   ```

## Web Dashboard Access:

The dashboard is now accessible at: **http://172.20.104.13:3000/**

You should see:
- System status
- Real-time logs
- Voice pipeline metrics

## Quick Diagnostic Command:

Run from WSL2:
```bash
source venv/bin/activate && python diagnose_system.py
```

This will verify all components are running correctly.