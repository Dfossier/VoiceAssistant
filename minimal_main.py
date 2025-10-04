# Minimal Local AI Assistant - Runs with basic dependencies only
# For testing and development without heavy ML dependencies
import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, Response
    import uvicorn
    from loguru import logger
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Please run: pip install fastapi uvicorn pydantic-settings python-dotenv loguru")
    sys.exit(1)

# Load environment
load_dotenv()

# Optional imports (may not be available in minimal mode)
OPTIONAL_IMPORTS = {}

try:
    
    from core.local_whisper import LocalWhisperHandler
    OPTIONAL_IMPORTS["whisper"] = LocalWhisperHandler
except ImportError:
    OPTIONAL_IMPORTS["whisper"] = None
    logger.warning("LocalWhisper not available in minimal mode")

try:
    
    from core.natural_conversation import NaturalConversation
    OPTIONAL_IMPORTS["conversation"] = NaturalConversation
except ImportError:
    OPTIONAL_IMPORTS["conversation"] = None
    logger.warning("NaturalConversation not available in minimal mode")
# Optional imports (may not be available in minimal mode)

sys.path.insert(0, str(Path(__file__).parent / "src"))
# Optional imports (may not be available in minimal mode)


# Optional imports (may not be available in minimal mode)

try:
    
# Optional imports (may not be available in minimal mode)

    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
# Optional imports (may not be available in minimal mode)

    from fastapi.middleware.cors import CORSMiddleware
# Optional imports (may not be available in minimal mode)

    from fastapi.staticfiles import StaticFiles
# Optional imports (may not be available in minimal mode)

    from fastapi.responses import HTMLResponse, Response
# Optional imports (may not be available in minimal mode)

    import uvicorn
# Optional imports (may not be available in minimal mode)

    from loguru import logger
# Optional imports (may not be available in minimal mode)

    from dotenv import load_dotenv
# Optional imports (may not be available in minimal mode)

except ImportError as e:
# Optional imports (may not be available in minimal mode)

    print(f"❌ Missing dependency: {e}")
# Optional imports (may not be available in minimal mode)

    print("Please run: pip install fastapi uvicorn pydantic-settings python-dotenv loguru")
# Optional imports (may not be available in minimal mode)

    sys.exit(1)
# Optional imports (may not be available in minimal mode)


# Optional imports (may not be available in minimal mode)

# Load environment
# Optional imports (may not be available in minimal mode)
load_dotenv()

# Optional imports (may not be available in minimal mode)
OPTIONAL_IMPORTS = {}

try:
    from core.local_whisper import LocalWhisperHandler
    OPTIONAL_IMPORTS["whisper"] = LocalWhisperHandler
except ImportError:
    OPTIONAL_IMPORTS["whisper"] = None
    logger.warning("LocalWhisper not available in minimal mode")

try:
    from core.natural_conversation import NaturalConversation
    OPTIONAL_IMPORTS["conversation"] = NaturalConversation
except ImportError:
    OPTIONAL_IMPORTS["conversation"] = None
    logger.warning("NaturalConversation not available in minimal mode")
# Optional imports (may not be available in minimal mode)


# Optional imports (may not be available in minimal mode)

# Simple WebSocket manager
# Optional imports (may not be available in minimal mode)

class SimpleWebSocketManager:
    def __init__(self):
        self.connections = []
    
    async def connect(self, websocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info("WebSocket client connected")
    
    def disconnect(self, websocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info("WebSocket client disconnected")
    
    async def broadcast(self, message):
        for connection in self.connections[:]:
            try:
    
                await connection.send_json(message)
            except:
                self.disconnect(connection)

ws_manager = SimpleWebSocketManager()

async def check_recent_logs():
    """Check recent log files for errors and activity"""
    try:
        log_files = ["backend_production.log", "backend.log", "backend_debug.log"]
        found_logs = []
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r") as f:
                        lines = f.readlines()[-20:]  # Last 20 lines
                        
                    error_lines = [line for line in lines if "ERROR" in line or "error" in line.lower()]
                    if error_lines:
                        found_logs.append(f"{log_file}: {len(error_lines)} recent errors")
                        found_logs.extend([f"  {line.strip()}" for line in error_lines[-3:]])  # Last 3 errors
                    else:
                        found_logs.append(f"{log_file}: No recent errors (healthy)")
                except Exception as e:
                    found_logs.append(f"{log_file}: Could not read ({e})")
        
        if found_logs:
            return "Recent Log Analysis:\n" + "\n".join(found_logs)
        else:
            return "No log files found to analyze"
    except Exception as e:
        return f"Log analysis failed: {e}"

# Global manager
ws_manager = SimpleWebSocketManager()

conversation_handler = None
conversation_handler = None

# Create FastAPI app
app = FastAPI(title="Local AI Assistant (Minimal)", version="0.1.0-minimal")

# Configure CORS - More permissive for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to avoid opaque responses
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page"""
    try:
    
        with open("static/index.html") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(content="""
<!DOCTYPE html>
<html><head><title>Local AI Assistant</title></head>
<body><h1>Local AI Assistant</h1><p>Interface loading... Please check static/index.html</p></body>
</html>""")

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "minimal"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with minimal functionality"""
    await ws_manager.connect(websocket)
    try:
    
        while True:
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "chat":
                # Simple echo response for testing
                message = data.get("message", "")
                
                if message.startswith("/"):
                    # Handle commands
                    if message == "/help":
                        response = """Minimal Assistant Commands:
/help - Show this help
/status - Show system status
/test - Test connection"""
                    elif message == "/status":
                        response = f"Status: Running in minimal mode\nConnections: {len(ws_manager.connections)}"
                    elif message == "/test":
                        response = "✅ Connection test successful!"
                    response = f"I received: '{message}'. This is the minimal version. Configure API keys and install full dependencies for AI responses."
                
                await websocket.send_json({
                    "type": "chat_response",
                    "message": response
                })
                
            elif message_type == "command":
                action = data.get("action")
                if action == "run_tests":
                    output = "Minimal version - no test execution available"
                elif action == "check_logs":
                    output = await check_recent_logs()
                elif action == "browse_web":
                    output = "Minimal version - no web browsing available"
                elif action.startswith("start_") or action.startswith("stop_"):
                    service = action.split("_", 1)[1]
                    output = f"Service control not available in minimal version. To control {service}, use the full version with all dependencies."
                    available_commands = ["run_tests", "check_logs", "browse_web", "start_backend", "stop_backend", "start_bot", "stop_bot"]
                    output = f"Command '{action}' not recognized. Available: {', '.join(available_commands)}"
                
                await websocket.send_json({
                    "type": "command_response",
                    "output": output
                })
                
            elif message_type == "voice":
                action = data.get("action")
                if action == "conversation":
                    # Natural conversation mode
                    audio = data.get("audio")
                    if audio and OPTIONAL_IMPORTS["whisper"]:
                        try:
    
                            from core.natural_conversation import NaturalConversation
                            
                            # Initialize conversation handler if needed  
                            if not conversation_handler and OPTIONAL_IMPORTS["conversation"] and OPTIONAL_IMPORTS["whisper"]:
                                whisper = OPTIONAL_IMPORTS["whisper"]()
                                # Mock LLM handler for minimal version
                                class MinimalLLM:
                                    async def generate_response(self, prompt, system_prompt=""):
                                        return f"I heard you say: '{prompt}'. In natural conversation mode!"
                                
                                globals()['conversation_handler'] = NaturalConversation(MinimalLLM(), whisper)
                            
                            # Process conversation turn with streaming
                            result = await globals()['conversation_handler'].process_conversation_turn(
                                audio, websocket
                            )
                            
                            # Only send final result if streaming failed
                            if result.get("streaming_failed"):
                                await websocket.send_json(result)
                            continue
                            
                        except Exception as e:
                            logger.error(f"Conversation error: {e}")
                            response = f"Conversation error: {str(e)}"
                        
                elif action == "start_conversation" and OPTIONAL_IMPORTS["conversation"] and OPTIONAL_IMPORTS["whisper"]:
                    # Start new conversation
                    try:
    
                        
                        whisper = OPTIONAL_IMPORTS["whisper"]()
                        
                        class MinimalLLM:
                            async def generate_response(self, prompt, system_prompt=""):
                                return f"Thanks for saying '{prompt}'. I'm listening and remembering our conversation!"
                        
                        globals()['conversation_handler'] = NaturalConversation(MinimalLLM(), whisper)
                        result = globals()['conversation_handler'].start_new_conversation()
                        
                        await websocket.send_json(result)
                        continue
                        
                    except Exception as e:
                        logger.error(f"Start conversation error: {e}")
                        response = f"Error starting conversation: {str(e)}"
                        
                elif action == "transcribe":
                    # Single transcription mode (original)
                    audio = data.get("audio")
                    if audio and OPTIONAL_IMPORTS["whisper"]:
                        try:
    
                            
                            whisper = OPTIONAL_IMPORTS["whisper"]()
                            result = await whisper.transcribe_audio(audio)
                            
                            if result["success"]:
                                text = result["text"]
                                response = f"You said: '{text}'. This is single transcription mode."
                                
                            await websocket.send_json({
                                    "type": "voice_response",
                                    "transcribed_text": text,
                                    "text": response,
                                    "message": response
                                })
                            continue
                        except Exception as e:
                            logger.error(f"Transcription error: {e}")
                        
                        response = f"Transcription in progress. Audio size: {len(audio)} bytes"
                    
                await websocket.send_json({
                    "type": "voice_response",
                    "text": response,
                    "message": response
                })
                
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

def main():
    """Run the minimal assistant"""
    print("🤖 Starting Local AI Assistant (Minimal Mode)")
    print("=" * 50)
    print("This is a minimal version for testing and development.")
    print("For full functionality, install all dependencies with:")
    print("pip install -r requirements.txt")
    print("=" * 50)
    
    logger.info("Starting minimal Local AI Assistant")
    
    # Check configuration
    api_keys = [
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("GEMINI_API_KEY")
    ]
    
    if any(api_keys):
        logger.info("✅ At least one API key configured")
    
    # Run server
    try:
    
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    main()