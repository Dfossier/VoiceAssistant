# Claude Code Integration Features

## Overview

The Claude Code integration branch adds powerful development assistance capabilities to the voice assistant. The LLM can now read Claude Code session logs, understand development context, and interact with the Claude Code terminal to assist with coding tasks.

## Key Features

### 📊 Development Context Awareness
- **Log Reading**: Automatically reads Claude Code session logs to understand what you're working on
- **File Tracking**: Monitors recently accessed files and ongoing development tasks
- **Error Detection**: Identifies and tracks development errors for debugging assistance
- **Project Analysis**: Provides intelligent summaries of recent development activity

### 🎤 Voice Commands for Development

#### Terminal Interaction
- **"Run command [command]"** - Execute commands in Claude Code terminal
- **"Type in terminal [text]"** - Add text to terminal without executing
- **"Show terminal output"** - Get recent terminal output

#### Development Assistance
- **"Debug this"** - Analyze current errors and provide debugging help
- **"Project summary"** - Get overview of recent development activity
- **"Run tests"** - Execute project tests
- **"Git status"** - Check repository status
- **"Recent files"** - List recently accessed files

#### File Operations
- **"Read file [filename]"** - Read and analyze specific files
- **"Edit file [filename]"** - Open files for editing
- **"Explain code"** - Get explanations of current code

### 🛡️ Safety Features
- **Command Filtering**: Blocks dangerous commands (rm -rf, del /s, etc.)
- **Confirmation Required**: Prompts for confirmation on risky operations
- **Context Validation**: Ensures commands are appropriate for current context

## Architecture

### Core Components

#### 1. Claude Code Service (`claude_code_service.py`)
- **ClaudeCodeService**: Reads and parses Claude Code session logs
- **ClaudeCodeTerminalService**: Handles terminal text injection and command execution
- **ClaudeCodeIntegration**: Main integration service combining all features

#### 2. Voice Command Processor (`voice_command_processor.py`)
- **VoiceCommandProcessor**: Recognizes and processes development-specific voice commands
- **Command Recognition**: Uses trigger phrases and parameter extraction
- **Safety Validation**: Checks commands for safety before execution

#### 3. Enhanced WebSocket Handler
- **Context Integration**: Incorporates Claude Code context into LLM responses
- **Command Routing**: Routes voice commands to appropriate handlers
- **Development Mode**: Provides specialized responses for coding tasks

### Configuration

#### Voice Commands (`config/voice_commands.json`)
```json
{
  "development_commands": {
    "terminal_commands": [...],
    "development_helpers": [...],
    "project_analysis": [...]
  },
  "safety_filters": {
    "dangerous_commands": ["rm -rf", "del /s", ...],
    "require_confirmation": ["git push", "npm publish", ...]
  }
}
```

## Usage Examples

### Basic Voice Commands

```
👤 "Run command npm install"
🤖 "✅ Executed: npm install"

👤 "Show me recent files" 
🤖 "Recent files: main.py, config.json, package.json"

👤 "Debug this error"
🤖 "🐛 Recent errors found: Python syntax error in main.py line 42. I can help analyze this issue."

👤 "Project summary"
🤖 "Recent session: 5 file operations, 3 commands executed, 1 error encountered."
```

### Development Context Integration

The LLM automatically provides enhanced responses when it detects development-related queries:

```
👤 "How do I fix this function?"
🤖 "Based on your recent work in main.py and the syntax error on line 42, you likely need to check your indentation and function definition syntax."
```

### Terminal Integration

```
👤 "Type in terminal console.log hello world"
🤖 "📝 Added to terminal: console.log hello world"

👤 "Run command python main.py"
🤖 "✅ Executed: python main.py"
```

## Implementation Details

### Log File Detection
The system automatically searches for Claude Code logs in common locations:
- `~/.claude-code/logs`
- `~/.cache/claude-code/logs`
- `~/AppData/Local/Claude/logs` (Windows)
- `/tmp/claude-code-logs`

### Context Data Structure
```json
{
  "development_context": {
    "current_files": ["main.py", "config.json"],
    "recent_commands": ["npm install", "python main.py"],
    "active_errors": ["Syntax error in main.py line 42"],
    "project_summary": "Recent session: 5 file operations, 3 commands executed",
    "last_activity": "2025-09-15T10:30:00"
  },
  "recent_activity": [...],
  "capabilities": [...]
}
```

### Command Recognition Pipeline
1. **Text Analysis**: Parse voice input for development keywords
2. **Trigger Matching**: Match against configured trigger phrases
3. **Parameter Extraction**: Extract command parameters (files, commands, etc.)
4. **Safety Validation**: Check for dangerous operations
5. **Action Execution**: Route to appropriate handler
6. **Response Formatting**: Format success/error responses

## Security Considerations

### Command Safety
- **Dangerous Command Blocking**: Automatically blocks destructive commands
- **Confirmation Requirements**: Requires explicit confirmation for risky operations
- **Parameter Validation**: Validates command parameters for safety
- **Context Checking**: Ensures commands are appropriate for current context

### Log Access
- **Read-Only Access**: Only reads Claude Code logs, never modifies them
- **Privacy Preservation**: Processes only development-related information
- **Error Handling**: Graceful fallback when logs are unavailable

## Development Mode Features

### Enhanced System Prompts
When development context is detected, the LLM receives enhanced prompts:

```
"You are a development assistant with access to the user's Claude Code session. 
Provide brief, helpful responses about coding, debugging, and development tasks. 
Current context: Recent files: main.py, config.json | Recent commands: npm install | Recent error: Syntax error in main.py"
```

### Intelligent Response Routing
- **Development Queries**: Automatically enhanced with context
- **Terminal Requests**: Routed to terminal integration
- **File Operations**: Handled with appropriate file context
- **Error Analysis**: Provided with current error information

## Configuration Options

### Environment Variables
```bash
# Enable Claude Code integration
CLAUDE_CODE_INTEGRATION=true

# Log file locations (optional)
CLAUDE_CODE_LOG_DIR=/custom/log/path

# Safety settings
VOICE_COMMAND_SAFETY=strict
```

### Voice Command Customization
Edit `config/voice_commands.json` to:
- Add new trigger phrases
- Customize response templates
- Modify safety filters
- Add project-specific commands

## Future Enhancements

### Planned Features
- **Real-time Log Streaming**: Live monitoring of Claude Code activity
- **File Content Analysis**: Direct integration with Claude Code file operations
- **IDE Integration**: Extended support for popular IDEs
- **Custom Command Macros**: User-defined command sequences
- **Team Collaboration**: Shared context for team development

### API Extensions
- **WebSocket Events**: Real-time development events
- **REST API**: Direct Claude Code interaction endpoints
- **Plugin System**: Extensible command processing
- **Integration Hooks**: Custom development workflow integration

## Troubleshooting

### Common Issues

#### No Claude Code Logs Found
```
⚠️ No active Claude Code session logs found
```
**Solution**: Ensure Claude Code is running and generating logs in standard locations.

#### Terminal Integration Unavailable
```
❌ Terminal integration not available
```
**Solution**: Check that Claude Code integration is properly initialized.

#### Command Safety Blocks
```
❌ Unsafe command blocked: rm -rf
```
**Solution**: Use safer alternatives or modify safety filters if appropriate.

### Debug Mode
Enable verbose logging:
```python
import logging
logging.getLogger('claude_code_service').setLevel(logging.DEBUG)
```

## Contributing

### Adding New Voice Commands
1. Edit `config/voice_commands.json`
2. Add trigger phrases and actions
3. Implement handler in `voice_command_processor.py`
4. Test with voice input

### Extending Context Awareness
1. Modify `claude_code_service.py` log parsing
2. Update context data structure
3. Enhance LLM prompt generation
4. Test context integration

## License

Same as main project - MIT License