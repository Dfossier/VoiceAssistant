# Running Local AI Models on Windows

Since WSL has PyTorch compatibility issues, the best approach is to run your AI models on Windows and let the Discord backend connect to them. Here are your options:

## Option 1: vLLM (Recommended - Best Performance)

Open Windows Command Prompt and run:

```cmd
cd C:\Users\dfoss\Desktop\LocalAIModels

# Install vLLM if not already installed
pip install vllm

# Start vLLM server with your model
python -m vllm.entrypoints.openai.api_server --model deepseek-coder-1.3b-instruct-AWQ --port 8001 --host 0.0.0.0

# Or use the provided batch file:
windows_vllm_server.bat
```

**Benefits:**
- ✅ OpenAI-compatible API
- ✅ Fast inference with AWQ quantization
- ✅ Supports your DeepSeek models
- ✅ Battle-tested in production

## Option 2: Ollama (Easiest Setup)

1. Download Ollama from https://ollama.com/download/windows
2. Install and run Ollama
3. In Command Prompt:
```cmd
# Pull a model
ollama pull deepseek-coder:1.3b

# The server runs automatically on port 11434
# Update backend to use: VLLM_BASE_URL=http://localhost:11434/api
```

**Benefits:**
- ✅ One-click install
- ✅ Automatic model management
- ✅ No Python environment needed

## Option 3: LM Studio (GUI Option)

1. Download from https://lmstudio.ai/
2. Install and launch LM Studio
3. Load your model through the UI
4. Start the server (usually on port 1234)
5. Update backend: `VLLM_BASE_URL=http://localhost:1234/v1`

**Benefits:**
- ✅ User-friendly GUI
- ✅ Built-in model browser
- ✅ No command line needed

## Option 4: Text Generation WebUI (Oobabooga)

```cmd
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui
start_windows.bat

# Then enable API mode in the interface
# Update backend: VLLM_BASE_URL=http://localhost:5000/api/v1
```

**Benefits:**
- ✅ Web interface
- ✅ Supports many formats
- ✅ Active community

## Option 5: llama.cpp (Lightweight)

```cmd
# Download latest release from GitHub
# https://github.com/ggerganov/llama.cpp/releases

# Run server
server.exe -m deepseek-coder-1.3b.gguf -c 2048 --host 0.0.0.0 --port 8080
```

**Benefits:**
- ✅ Very lightweight
- ✅ CPU optimized
- ✅ Minimal dependencies

## Connecting Your Backend

Once your Windows AI server is running, the Discord backend will automatically detect and use it. You'll see in the logs:

```
✅ vLLM server available at http://localhost:8001/v1
```

Then your Discord bot will use the full AI model instead of fallback responses!

## Quick Test

After starting your AI server:

1. Check in browser: http://localhost:8001/v1/models
2. Try in Discord: `!ask How do you work?`
3. You should get intelligent AI responses!

## Troubleshooting

- **Port already in use**: Change port with `--port 8002`
- **Model not loading**: Check model path and format
- **Slow responses**: Try smaller model or add `--gpu-memory-utilization 0.5`
- **Connection refused**: Check Windows Firewall settings

## Environment Variables (Optional)

In your WSL backend, you can set:

```bash
export VLLM_BASE_URL="http://localhost:8001/v1"
export PREFERRED_LLM_PROVIDER="vllm"
```