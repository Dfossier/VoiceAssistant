import asyncio
import logging
import httpx
from typing import Dict, Any, Optional
import json

from config import Config

logger = logging.getLogger(__name__)

class BackendClient:
    """Client for communicating with the existing LLM backend API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        
        # Initialize HTTP client with timeout and retry settings
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "WindowsDiscordBot/1.0"
            },
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
    
    async def health_check(self) -> bool:
        """Check if the backend API is healthy"""
        try:
            # Try the health endpoint first
            response = await self.client.get("/health")
            if response.status_code == 200:
                return True
                
            # If no /health endpoint, try /docs (FastAPI default)
            response = await self.client.get("/docs")
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Backend health check failed: {e}")
            return False
    
    async def send_message(self, user_id: str, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Send a message to the LLM backend and get response"""
        try:
            payload = {
                "user_id": user_id,
                "message": message,
                "context": context or {}
            }
            
            logger.debug(f"Sending message to backend: {message[:100]}...")
            
            response = await self.client.post("/api/conversation/message", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for error in response
            if 'error' in data:
                logger.error(f"Backend returned error: {data['error']}")
                return f"Error: {data['error']}"
            
            ai_response = data.get('response', '')
            if not ai_response:
                logger.warning("Backend returned empty response")
                return "I'm sorry, I couldn't generate a response."
            
            logger.debug(f"Received response: {str(ai_response)[:100]}...")
            return str(ai_response)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from backend: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Backend API error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Request error to backend: {e}")
            raise Exception("Failed to connect to backend API")
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            raise
    
    async def execute_command(self, user_id: str, command: str, timeout: int = 30) -> str:
        """Execute a command through the backend"""
        try:
            payload = {
                "user_id": user_id,
                "command": command,
                "timeout": timeout
            }
            
            logger.debug(f"Executing command: {command}")
            
            response = await self.client.post("/api/exec/command", json=payload)
            response.raise_for_status()
            
            data = response.json()
            job_id = data.get('job_id')
            
            if not job_id:
                return "Error: Failed to get job ID from command execution"
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            raise
    
    async def get_command_output(self, job_id: str) -> Dict[str, Any]:
        """Get output from a command execution job"""
        try:
            response = await self.client.get(f"/api/exec/output/{job_id}")
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error getting command output: {e}")
            raise
    
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio to text"""
        try:
            # Convert bytes to base64 for JSON transmission
            import base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            payload = {
                "audio_data": audio_b64
            }
            
            response = await self.client.post("/api/audio/transcribe", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                logger.warning(f"Transcription error: {data['error']}")
                return ""
            
            # Backend returns transcription in 'text' field
            transcription = data.get('text', data.get('transcription', ''))
            if transcription:
                logger.info(f"Transcription successful: '{transcription[:50]}...'")
            return transcription
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return ""
    
    async def text_to_speech(self, text: str, voice: str = "default") -> bytes:
        """Convert text to speech"""
        try:
            payload = {
                "text": text,
                "voice": voice
            }
            
            response = await self.client.post("/api/audio/tts", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                logger.warning(f"TTS error: {data['error']}")
                return b""
            
            # Convert base64 back to bytes
            import base64
            audio_data = data.get('audio_data', '')
            if audio_data:
                decoded_audio = base64.b64decode(audio_data)
                logger.info(f"Decoded {len(decoded_audio)} bytes from base64, format: {data.get('format', 'unknown')}")
                # Check MP3 header - MP3 can start with various sync bytes
                if (decoded_audio[:3] == b'ID3' or  # ID3 tag
                    decoded_audio[:2] == b'\xff\xfb' or  # MP3 sync frame
                    decoded_audio[:2] == b'\xff\xf3' or  # MP3 sync frame  
                    decoded_audio[:2] == b'\xff\xf2'):   # MP3 sync frame
                    logger.info("Backend returned valid MP3 data")
                else:
                    logger.warning(f"Backend returned non-MP3 data. First 10 bytes: {decoded_audio[:10]}")
                return decoded_audio
            
            logger.warning("No audio_data in backend response")
            return b""
            
        except Exception as e:
            logger.error(f"Error with text-to-speech: {e}")
            return b""
    
    async def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a file through the backend"""
        try:
            payload = {
                "file_path": file_path
            }
            
            response = await self.client.post("/api/files/analyze", json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
            raise
    
    async def watch_directory(self, directory: str, user_id: str = "discord_bot") -> Dict[str, Any]:
        """Start watching a directory for changes"""
        try:
            payload = {
                "directory": directory,
                "user_id": user_id
            }
            
            response = await self.client.post("/api/files/watch", json=payload)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error watching directory: {e}")
            raise
    
    async def get_conversation_history(self, user_id: str, limit: int = 10) -> list:
        """Get conversation history for a user"""
        try:
            params = {"limit": limit}
            response = await self.client.get(f"/api/conversation/history/{user_id}", params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('history', [])
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def get_api_status(self) -> Dict[str, Any]:
        """Get backend API status and information"""
        try:
            response = await self.client.get("/api/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting API status: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close the HTTP client"""
        try:
            await self.client.aclose()
            logger.info("Backend client closed successfully")
        except Exception as e:
            logger.error(f"Error closing backend client: {e}")