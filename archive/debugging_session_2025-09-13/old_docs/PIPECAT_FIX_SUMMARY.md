# Pipecat Pipeline Fix Summary

## Problem
The Pipecat pipeline was failing with:
```
AttributeError: 'AudioRawFrame' object has no attribute 'id'
```

This was caused by the TurnTrackingObserver trying to access an `id` attribute on AudioRawFrame objects, but AudioRawFrame doesn't have this attribute.

## Root Cause Analysis

1. **Frame Type Mismatch**: The default ProtobufFrameSerializer was creating `AudioRawFrame` objects instead of `InputAudioRawFrame` objects
2. **Missing ID Attribute**: Only `SystemFrame` and its subclasses have the `id` attribute
3. **InputAudioRawFrame** inherits from both `SystemFrame` and `AudioRawFrame`, giving it the required `id` attribute

## Solution

Created a custom JSON frame serializer that:
1. Properly deserializes Discord bot JSON messages to `InputAudioRawFrame` (not `AudioRawFrame`)
2. Maintains compatibility with the Discord bot's existing message format
3. Handles both audio and text input/output

### Key Changes

1. **Custom Serializer** (`DiscordJSONFrameSerializer`):
   - Deserializes `{"type": "audio_input", ...}` → `InputAudioRawFrame`
   - Deserializes `{"type": "text_input", ...}` → `TextFrame`
   - Serializes `OutputAudioRawFrame` → `{"type": "audio_output", ...}`
   - Serializes `TextFrame` → `{"type": "text", ...}`

2. **Pipeline Configuration**:
   - Disabled metrics to avoid observer issues
   - Used custom serializer instead of default ProtobufFrameSerializer

3. **File Structure**:
   - `/src/core/pipecat_pipeline_fixed.py` - Fixed pipeline implementation
   - `run_fixed_pipeline.py` - Script to run the fixed pipeline
   - `test_complete_pipeline.py` - Test script for the complete flow

## How to Use

### 1. Start the Fixed Pipeline (WSL2)
```bash
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
source venv/bin/activate
python run_fixed_pipeline.py
```

### 2. Run Discord Bot (Windows)
```cmd
cd C:\users\dfoss\desktop\localaimodels\assistant\WindowsDiscordBot
bot_venv_windows\Scripts\activate
python direct_audio_bot.py
```

### 3. Test the Pipeline
```bash
# In WSL2
python test_complete_pipeline.py
```

## Message Format

### From Discord Bot → Pipeline
```json
// Audio input
{
    "type": "audio_input",
    "data": "<base64-encoded-pcm16>",
    "sample_rate": 16000,
    "channels": 1,
    "format": "pcm16"
}

// Text input (for testing)
{
    "type": "text_input",
    "text": "Hello, can you hear me?"
}
```

### From Pipeline → Discord Bot
```json
// Audio output (TTS response)
{
    "type": "audio_output",
    "data": "<base64-encoded-pcm16>",
    "sample_rate": 16000,
    "channels": 1,
    "format": "pcm16"
}

// Text output (transcriptions, etc.)
{
    "type": "text",
    "text": "Transcribed or generated text"
}
```

## Benefits

1. **No More AttributeError**: Proper frame types prevent the observer error
2. **JSON Compatibility**: Works with Discord bot's existing WebSocket format
3. **Cleaner Architecture**: No need to modify Pipecat internals
4. **Full Pipeline Support**: Audio → STT → LLM → TTS → Audio

## Next Steps

1. Ensure Whisper STT service is properly initialized
2. Ensure Phi-3 LLM is running on port 5001
3. Ensure Kokoro TTS service is properly initialized
4. Test end-to-end voice conversation through Discord