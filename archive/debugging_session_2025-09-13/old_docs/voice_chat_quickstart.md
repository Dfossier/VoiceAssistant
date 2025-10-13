# 🎙️ Voice Chat for Local AI Assistant

## Overview

Your assistant can support **real-time voice conversations** using Pipecat - allowing you to talk naturally instead of typing.

## Two Options for Voice Chat

### Option 1: Simple Voice Chat (Easy Setup)
Uses your computer's microphone and speakers with basic speech recognition.

**Install:**
```bash
pip install SpeechRecognition pyttsx3 pyaudio
```

**Features:**
- ✅ Works immediately
- ✅ No API keys needed  
- ✅ Runs locally
- ❌ Basic voice quality
- ❌ Desktop only

### Option 2: Advanced Voice Chat with Pipecat (Professional Quality)
Real-time streaming voice with high-quality voices and WebRTC support.

**Install:**
```bash
pip install pipecat-ai
# Plus one of: deepgram-sdk (for STT) or openai-whisper
# Plus one of: elevenlabs (for TTS) or pyttsx3
```

**Features:**
- ✅ Professional voice quality
- ✅ Works in browser (WebRTC)
- ✅ Phone support
- ✅ Multiple voice options
- ✅ Interrupt handling
- ❌ Requires API keys for best quality

## Quick Implementation

### 1. Add Voice Button to Web Interface
```javascript
// Add to static/js/main.js
async function startVoiceChat() {
    const response = await fetch('/api/voice/start', {
        method: 'POST'
    });
    const data = await response.json();
    
    if (data.mode === 'simple') {
        // Simple voice mode - instructions shown
        addChatMessage('assistant', 'Voice chat started! Say "exit" to stop.');
    } else {
        // WebRTC mode - establish connection
        await setupWebRTC(data.offer);
    }
}
```

### 2. Simple Voice Mode (No Pipecat)
```python
# Already implemented in voice_handler.py
simple_voice = SimpleVoiceChat(llm_handler)
await simple_voice.start_local_voice_chat()
```

### 3. Advanced Pipecat Mode
```python
# Configure in .env:
DEEPGRAM_API_KEY=your_key  # For speech-to-text
ELEVENLABS_API_KEY=your_key  # For natural voices

# Or use free alternatives:
# - OpenAI Whisper (local STT)
# - pyttsx3 (local TTS)
```

## How It Works

### Simple Mode Flow:
1. **You speak** → Microphone captures audio
2. **Google Speech Recognition** → Converts to text
3. **Your LLM** → Processes the text
4. **pyttsx3** → Speaks the response

### Pipecat Mode Flow:
1. **You speak** → WebRTC/Microphone stream
2. **Deepgram/Whisper** → Real-time transcription
3. **Your LLM** → Processes with context
4. **ElevenLabs/Local TTS** → Natural voice response
5. **VAD** → Handles interruptions smoothly

## Usage Examples

### Desktop Voice Chat:
```
You: "Hey assistant, I'm getting a TypeError in my Python code"
Assistant: "I can help with that. Can you tell me what line the error is on?"
You: "Line 42, something about NoneType"
Assistant: "That means you're trying to use a variable that's None..."
```

### Browser Voice Chat (with Pipecat):
- Click microphone button in web interface
- Green indicator shows when listening
- Natural conversation with interruption support
- Works on phone browsers too

## Current Status

The voice handler is ready but needs:
1. **Simple mode**: Just install `SpeechRecognition pyttsx3 pyaudio`
2. **Pipecat mode**: Install `pipecat-ai` and configure API keys
3. **Web UI**: Add microphone button (I can add this)

## Benefits

- **Hands-free debugging** - Talk while coding
- **Natural conversation** - Like talking to a colleague  
- **Mobile friendly** - Voice chat from your phone
- **Context aware** - Maintains conversation history

Would you like me to:
1. Add the microphone button to your web interface?
2. Set up simple voice mode first?
3. Configure full Pipecat integration?