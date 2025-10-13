#!/usr/bin/env python3
"""
Run ONLY the API server without voice pipeline
This provides a clean API for the dashboard without blocking
"""

import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger
import uvicorn

# Load environment
load_dotenv()

# Configure minimal logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {message}")

def create_api_app():
    """Create FastAPI app with only API endpoints (no voice pipeline)"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    # Import routers (use fixed version)
    from src.api.system_control import router as system_router
    
    app = FastAPI(
        title="Local AI Assistant API",
        description="Control API for Local AI Assistant",
        version="0.1.0"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(system_router)
    
    # Add health endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "api"}
    
    @app.get("/")
    async def root():
        return {
            "message": "Local AI Assistant API",
            "endpoints": {
                "health": "/health",
                "status": "/api/system/status",
                "control": "/api/system/control",
                "metrics": "/api/system/ws/metrics"
            }
        }
    
    return app

if __name__ == "__main__":
    logger.info("🚀 Starting API-only server (no voice pipeline)")
    logger.info("📝 This provides clean API endpoints for the dashboard")
    
    # Create the app
    app = create_api_app()
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )