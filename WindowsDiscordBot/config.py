"""Configuration for Windows Discord Bot"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory
parent_dir = Path(__file__).parent.parent
env_path = parent_dir / ".env"
load_dotenv(env_path)

class Config:
    """Configuration settings for the Discord bot"""
    
    # Discord Settings
    DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    COMMAND_PREFIX = "!"
    
    # Backend API Settings  
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://10.2.0.2:8000")
    BACKEND_API_KEY = os.getenv("API_KEY")
    
    # Logging Settings
    LOG_LEVEL = os.getenv("BOT_LOG_LEVEL", "INFO")
    LOG_FILE = Path(__file__).parent / "logs" / "discord_bot.log"
    LOG_MAX_SIZE = "50 MB"
    LOG_BACKUP_COUNT = 5
    
    # Voice Settings
    VOICE_TIMEOUT = 300  # 5 minutes
    AUDIO_BITRATE = 96000
    
    # Validation
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        
        if not cls.DISCORD_TOKEN:
            missing.append("DISCORD_BOT_TOKEN")
        if not cls.BACKEND_API_KEY:
            missing.append("API_KEY")
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

# Create logs directory
Config.LOG_FILE.parent.mkdir(exist_ok=True)