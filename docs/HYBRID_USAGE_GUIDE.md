# Hybrid Discord Bot Usage Guide

## 🎯 What's New: Remote Calling Support

The hybrid Discord bot now supports **both** use cases:

### **Local Usage** 🏠
- You're at your computer
- Bot captures your microphone directly
- Same as before - fast and reliable

### **Remote Usage** 📱
- You call into Discord from phone/mobile
- Bot captures Discord audio (system audio)
- Advanced echo prevention prevents feedback loops

## 🚀 Quick Start

### 1. Start the System
```bash
# From WSL/Linux terminal
./scripts/startup/start_complete_system.sh
```

### 2. Start Hybrid Bot
```bash
# From Windows (in WindowsDiscordBot folder)
start_hybrid_bot.bat
```

### 3. Use Discord Commands

#### `/hybrid` - Start Audio Session
- Auto-detects whether you're local or calling in remotely
- Switches audio capture mode automatically
- Shows current mode and source in response

#### `/mode [local|remote|auto]` - Change Audio Mode
- `local`: Force microphone capture
- `remote`: Force Discord audio capture
- `auto`: Auto-detect (default)

#### `/status` - Check Status
- Shows current audio mode
- Channel information
- Connection status

#### `/stop` - Stop Session
- Ends audio capture
- Disconnects from voice channel

## 📋 Setup Requirements

### For Remote Calling (System Audio)

You need to enable **Stereo Mix** or similar loopback device:

1. **Right-click speaker icon** → **Sounds**
2. **Recording tab** → **Right-click** → **Show Disabled Devices**
3. **Enable "Stereo Mix"** or **"What U Hear"**
4. **Set as Default Device** (optional)

### Test Audio Devices
```bash
# From WindowsDiscordBot folder
python test_audio_loopback.py
```

## 🎤 How It Works

### Auto-Detection Logic

```
No other users in channel → LOCAL MODE (microphone)
Other users in channel    → REMOTE MODE (Discord audio)
```

### Echo Prevention (Remote Mode)

1. **Timing Gates**: Blocks audio during TTS playback
2. **Cross-Correlation**: Compares incoming audio with recent TTS output
3. **Audio Fingerprinting**: Identifies bot's own voice patterns
4. **Adaptive Thresholds**: Learns and improves over time

## 📱 Usage Scenarios

### Scenario 1: Working at Computer
```
1. Join Discord voice channel on computer
2. Use /hybrid command
3. Bot detects: 0 remote users → LOCAL mode
4. Speak into your microphone
5. Bot responds through Discord voice
```

### Scenario 2: Calling from Phone
```
1. Call into Discord voice channel from phone
2. Someone at computer uses /hybrid command
3. Bot detects: 1 remote user → REMOTE mode
4. Speak from phone
5. Bot responds through Discord (you hear on phone)
```

### Scenario 3: Mixed Usage
```
1. Both computer user and phone caller in channel
2. Bot detects: mixed usage → REMOTE mode
3. Captures all Discord audio
4. Advanced echo prevention active
```

## 🔧 Configuration

Edit `config/services.json`:

```json
{
  "discord_bot": {
    "hybrid_mode": {
      "enabled": true,
      "auto_detect": true,
      "mode_switch_cooldown": 2.0,
      "echo_prevention": {
        "correlation_threshold": 0.75,
        "timing_gate_multiplier": 1.2,
        "tts_window_seconds": 5.0
      }
    }
  }
}
```

### Settings Explained

- **`auto_detect`**: Automatically switch between local/remote modes
- **`mode_switch_cooldown`**: Prevent rapid mode switching (seconds)
- **`correlation_threshold`**: Echo detection sensitivity (0.0-1.0)
- **`timing_gate_multiplier`**: TTS blocking duration multiplier
- **`tts_window_seconds`**: How long to remember TTS output for echo detection

## 🐛 Troubleshooting

### "No loopback device found"
- Enable Stereo Mix in Windows Sound settings
- Run `test_audio_loopback.py` to find devices
- Manually set `remote_device` index in config

### Echo/Feedback Issues
- Increase `correlation_threshold` (more strict)
- Increase `timing_gate_multiplier` (longer blocking)
- Check Discord audio levels

### Mode Not Switching
- Check `mode_switch_cooldown` setting
- Verify user detection in Discord channel
- Use `/status` to see current detection

### Audio Quality Issues
- Check Discord voice codec settings
- Verify sample rate compatibility (16kHz)
- Test with `/mode local` vs `/mode remote`

## 📊 Monitoring

### Real-time Status
```
/status - Shows current mode, users, connection status
```

### Log Files
```
WindowsDiscordBot/hybrid_discord_bot.log - Bot logs
websocket_service.log                    - Backend logs
```

### Debug Information
- Mode switching events
- Echo prevention actions
- Audio device selection
- User detection changes

## 🎯 Best Practices

1. **Start with Auto Mode**: Let the bot detect usage patterns
2. **Test Audio Setup**: Use `/status` and `/mode` commands to verify
3. **Monitor Logs**: Check for echo prevention and mode switching
4. **Adjust Thresholds**: Fine-tune echo prevention if needed
5. **Use Local Mode**: When possible (better audio quality, simpler processing)

## 🔄 Migration from Old Bot

The hybrid bot is **backward compatible**:

- All existing functionality works the same
- Local microphone usage unchanged
- New remote calling is additional capability
- Same Discord commands (with new `/hybrid` replacing `/direct`)

## ⚡ Performance Impact

### Local Mode (Microphone)
- **CPU**: Same as before (minimal)
- **Memory**: Same as before
- **Latency**: Same as before (~100ms)

### Remote Mode (Discord Audio)
- **CPU**: +15-25% (echo prevention)
- **Memory**: +50MB (audio buffers)
- **Latency**: +50-100ms (processing overhead)

Auto-detection ensures you only pay the performance cost when needed!