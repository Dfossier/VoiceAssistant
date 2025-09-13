#!/bin/bash
# Install Kokoro TTS package

echo "🔧 Installing Kokoro TTS package..."

# Activate virtual environment
source venv/bin/activate

# Install Kokoro package
pip install kokoro>=0.9.2

# Check installation
if pip show kokoro > /dev/null 2>&1; then
    echo "✅ Kokoro TTS package installed successfully!"
    echo "📦 Package details:"
    pip show kokoro
else
    echo "❌ Failed to install Kokoro TTS package"
    exit 1
fi

echo ""
echo "💡 To use Kokoro TTS, make sure you have:"
echo "   1. espeak-ng installed (already installed: $(which espeak-ng))"
echo "   2. The Kokoro model files in: /mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts/"
echo "   3. Sufficient GPU memory for the model (approximately 327MB)"
echo ""
echo "🎤 Available voices: af_heart, af_alloy, am_hero, am_onyx, af_echo, am_nova, bf_emma, bm_george"
echo "   See full list: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md"