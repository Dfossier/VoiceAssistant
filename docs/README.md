# Local AI Assistant

A high-performance local assistant for Windows/WSL that helps with error handling, debugging, and development automation.

## Quick Start
## 🔧 Networking Setup (Important!)



For Discord bot connectivity, enable **WSL2 Mirrored Networking Mode**:



1. **Run PowerShell as Administrator:**

   ```powershell

   .\enable_mirrored_networking.ps1

   ```



2. **Restart WSL:**

   ```bash

   wsl --shutdown && wsl

   ```



3. **Test:** `./test_networking.sh`



This allows Windows applications to connect to WSL services via `localhost`.



---


## Directory Structure



```

project/

├── src/                    # Main source code

│   ├── core/              # Core application modules

│   ├── api/               # API endpoints and routes

│   ├── services/          # Background services

│   └── utils/             # Utility functions

├── scripts/               # All scripts organized by type

│   ├── install/          # Installation scripts

│   ├── launchers/        # Startup and launcher scripts

│   ├── services/         # Service management scripts

│   ├── integration/      # Third-party integration scripts

│   ├── runners/          # Application runners

│   ├── system/           # System management scripts

│   ├── startup/          # Startup/shutdown scripts

│   └── maintenance/      # Maintenance and cleanup scripts

├── config/               # Configuration files

│   ├── env/             # Environment files

│   └── requirements/    # Python requirements

├── docs/                # Documentation

├── examples/            # Example and test scripts

├── logs/                # All log files

├── assets/              # Static assets (images, audio, data)

├── web-dashboard/       # React dashboard

├── mcp-terminal-server/ # MCP server

├── WindowsDiscordBot/   # Discord bot (Windows specific)

├── main.py              # Main application entry point

└── minimal_main.py      # Minimal version entry point

```



### Prerequisites
- Windows 11 with WSL2
- Python 3.11+
- At least one LLM API key (OpenAI, Anthropic, or Gemini)

### Installation

1. **Clone the repository** (in WSL):
```bash
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
```

2. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment**:
```bash
# Copy the .env file and edit it
nano .env

# Add your API keys:
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here
# GEMINI_API_KEY=your_key_here

# Set a secure SECRET_KEY:
# SECRET_KEY=your_secure_secret_key_here
```

5. **Install Playwright browsers** (for web automation):
```bash
playwright install chromium
```

6. **Run the assistant**:
```bash
python main.py
```

7. **Access the web interface**:
   - Open browser: http://localhost:8000
   - Or from phone: http://[your-ip]:8000

## Features

- 🤖 **AI-Powered Assistance**: Integrates with OpenAI, Anthropic, and Gemini
- 🪟 **Windows Automation**: Control windows and command prompts
- 📁 **File Management**: Read/write files, monitor changes
- 🌐 **Web Browsing**: Automated research and information gathering
- 🐛 **Error Handling**: Intelligent debugging with context awareness
- 📱 **Cross-Device Access**: Web interface works on desktop and mobile

## Basic Usage

### Chat Commands
- Ask questions about your code
- Request error analysis
- Get debugging suggestions
- Execute commands

### Quick Actions
- **Run Tests**: Execute your project's test suite
- **Check Logs**: View recent log entries
- **Browse Web**: Search for solutions online

### Example Workflows

1. **Debug Python Error**:
   ```
   User: I'm getting a TypeError in my script.py
   Assistant: [Reads file, analyzes error, suggests fix]
   ```

2. **Monitor Build Process**:
   ```
   User: Run npm build and fix any errors
   Assistant: [Executes build, captures errors, provides solutions]
   ```

3. **Code Review**:
   ```
   User: Review the changes in my feature branch
   Assistant: [Analyzes git diff, provides feedback]
   ```

## Development Mode

Run with hot-reload for development:
```bash
python main.py --dev
```

## Configuration

Key settings in `.env`:
- `WATCH_DIRECTORIES`: Directories to monitor
- `PREFERRED_LLM_PROVIDER`: Default AI provider
- `SERVER_PORT`: Change default port (8000)
- `AUTH_ENABLED`: Enable authentication

## Troubleshooting

### Connection Issues
- Check firewall settings
- Ensure port 8000 is available
- Verify WebSocket support

### Performance
- Reduce `CACHE_SIZE_MB` if memory constrained
- Limit `WATCH_DIRECTORIES` scope
- Adjust `MAX_WORKERS` based on CPU

### Windows Integration
- Run Windows-specific features require proper WSL setup
- Some automation features need admin privileges

## Architecture

See [CLAUDE.MD](CLAUDE.MD) for detailed architecture and development documentation.

## License

MIT License - See LICENSE file

## Support

- Check [CLAUDE.MD](CLAUDE.MD) for detailed documentation
- Report issues on GitHub
- Join community discussions

---

Built with ❤️ for developers who appreciate good error messages