"""Configuration management for Local AI Assistant"""
from typing import List, Optional
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # LLM API Keys
    openai_api_key: Optional[str] = Field(None, env='OPENAI_API_KEY')
    anthropic_api_key: Optional[str] = Field(None, env='ANTHROPIC_API_KEY')
    gemini_api_key: Optional[str] = Field(None, env='GEMINI_API_KEY')
    
    # Server Configuration
    server_host: str = Field('127.0.0.1', env='SERVER_HOST')
    server_port: int = Field(8000, env='SERVER_PORT')
    server_reload: bool = Field(False, env='SERVER_RELOAD')
    server_log_level: str = Field('INFO', env='SERVER_LOG_LEVEL')
    server_workers: int = Field(1, env='SERVER_WORKERS')
    
    # Windows Agent (disabled in WSL)
    windows_pipe_name: str = Field('LocalAssistantPipe', env='WINDOWS_PIPE_NAME')
    windows_agent_port: int = Field(8001, env='WINDOWS_AGENT_PORT')
    windows_agent_enabled: bool = Field(False, env='WINDOWS_AGENT_ENABLED')  # Default to False in WSL
    
    # File System
    watch_directories: str = Field('/mnt/c/users/dfoss/projects', env='WATCH_DIRECTORIES')
    ignore_patterns: str = Field('*.pyc,__pycache__,*.tmp', env='IGNORE_PATTERNS')
    max_file_size_mb: int = Field(10, env='MAX_FILE_SIZE_MB')
    
    # Security
    secret_key: str = Field(..., env='SECRET_KEY')
    allowed_origins: str = Field('http://127.0.0.1:8000,http://localhost:3000', env='ALLOWED_ORIGINS')
    auth_enabled: bool = Field(False, env='AUTH_ENABLED')
    auth_username: Optional[str] = Field(None, env='AUTH_USERNAME')
    auth_password: Optional[str] = Field(None, env='AUTH_PASSWORD')
    
    # Performance
    max_workers: int = Field(4, env='MAX_WORKERS')
    cache_enabled: bool = Field(True, env='CACHE_ENABLED')
    cache_size_mb: int = Field(100, env='CACHE_SIZE_MB')
    cache_ttl_seconds: int = Field(3600, env='CACHE_TTL_SECONDS')
    
    # Database
    database_path: str = Field('./assistant.db', env='DATABASE_PATH')
    database_pool_size: int = Field(5, env='DATABASE_POOL_SIZE')
    
    # LLM Settings
    preferred_llm_provider: str = Field('anthropic', env='PREFERRED_LLM_PROVIDER')
    llm_model_name: str = Field('claude-3-opus-20240229', env='LLM_MODEL_NAME')
    llm_temperature: float = Field(0.7, env='LLM_TEMPERATURE')
    llm_max_tokens: int = Field(4096, env='LLM_MAX_TOKENS')
    
    # Logging
    log_file_path: Optional[str] = Field('./logs/assistant.log', env='LOG_FILE_PATH')
    log_max_size_mb: int = Field(50, env='LOG_MAX_SIZE_MB')
    log_backup_count: int = Field(5, env='LOG_BACKUP_COUNT')
    
    # Development
    dev_mode: bool = Field(False, env='DEV_MODE')
    
    # Performance (added missing field)
    process_timeout: int = Field(300, env='PROCESS_TIMEOUT')
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': False,
        'extra': 'allow'  # Allow extra fields from .env
    }
        
    def get_watch_directories(self) -> List[str]:
        """Get watch directories as a list"""
        return [item.strip() for item in self.watch_directories.split(',') if item.strip()]
        
    def get_ignore_patterns(self) -> List[str]:
        """Get ignore patterns as a list"""
        return [item.strip() for item in self.ignore_patterns.split(',') if item.strip()]
        
    def get_allowed_origins(self) -> List[str]:
        """Get allowed origins as a list"""
        return [item.strip() for item in self.allowed_origins.split(',') if item.strip()]
        
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if v == 'CHANGE_THIS_TO_A_SECURE_SECRET_KEY':
            raise ValueError("Please set a secure SECRET_KEY in .env file")
        return v
        
    def get_llm_api_key(self) -> Optional[str]:
        """Get the API key for the preferred LLM provider"""
        if self.preferred_llm_provider == 'openai':
            return self.openai_api_key
        elif self.preferred_llm_provider == 'anthropic':
            return self.anthropic_api_key
        elif self.preferred_llm_provider == 'gemini':
            return self.gemini_api_key
        return None
        
    def has_valid_llm_key(self) -> bool:
        """Check if at least one LLM API key is configured"""
        return bool(self.openai_api_key or self.anthropic_api_key or self.gemini_api_key)