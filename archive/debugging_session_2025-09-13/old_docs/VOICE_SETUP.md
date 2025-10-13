# Voice Chat Setup

## Current Status
Voice chat works differently based on your browser:

### Chrome/Edge (Recommended)
- ✅ Native Web Speech API support
- ✅ Real-time speech recognition
- ✅ No additional setup needed

### Firefox/Safari
- 🎤 Real audio recording support
- ⚠️ Requires Whisper for transcription
- 📦 Installing: `pip install openai-whisper`

## How Voice Chat Works

1. **Chrome/Edge**: 
   - Click 🎤 Voice → Speak → Automatic transcription
   - Uses browser's built-in speech recognition

2. **Firefox** (after Whisper installed):
   - Click 🎤 Voice → Records audio → Sends to server
   - Server transcribes with Whisper → AI responds

## Quick Test
1. Open http://localhost:8000 in Chrome/Edge
2. Click 🎤 Voice button
3. Allow microphone access
4. Say "Hello, how are you?"
5. See transcribed text and AI response

## Troubleshooting

### Firefox shows "Microphone access denied"
- Check Firefox permissions: Settings → Privacy → Permissions → Microphone
- Ensure localhost is allowed

### "Whisper not installed" error
- Run: `pip install openai-whisper soundfile`
- This downloads ~2GB of models (one-time)
- Alternative: Use Chrome/Edge for instant voice chat

### No audio playback
- WSL audio requires PulseAudio setup
- Text responses work without audio configuration