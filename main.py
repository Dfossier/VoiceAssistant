#!/usr/bin/env python3
"""
Local AI Assistant - Main Entry Point
"""
import asyncio
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from loguru import logger

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Debug patch disabled for now
# try:
# except ImportError:
#     logger.warning("Debug WebSocket patch not available")

from core.server import create_app, run_server
from core.config import Settings
from utils.setup import check_environment, setup_directories


@click.command()
@click.option('--dev', is_flag=True, help='Run in development mode')
@click.option('--host', default=None, help='Override host from .env')
@click.option('--port', default=None, type=int, help='Override port from .env')
@click.option('--workers', default=None, type=int, help='Number of workers')
def main(dev: bool, host: str, port: int, workers: int):
    """Launch the Local AI Assistant"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize settings
    settings = Settings()
    
    # Override settings from CLI
    if host:
        settings.server_host = host
    if port:
        settings.server_port = port
    if workers:
        settings.max_workers = workers
    if dev:
        settings.dev_mode = True
        settings.server_reload = True
        
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.server_log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    if settings.log_file_path:
        logger.add(
            settings.log_file_path,
            rotation=f"{settings.log_max_size_mb} MB",
            retention=settings.log_backup_count,
            level=settings.server_log_level
        )
    
    logger.info("Starting Local AI Assistant")
    logger.info(f"Development mode: {settings.dev_mode}")
    
    # Check environment
    if not check_environment():
        logger.error("Environment check failed. Please install required dependencies.")
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    # Create and run the application
    try:
        global app
        app = create_app(settings)
        run_server(app, settings)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


# Create app instance for uvicorn import
load_dotenv()
settings = Settings()
app = create_app(settings)


if __name__ == "__main__":
    main()