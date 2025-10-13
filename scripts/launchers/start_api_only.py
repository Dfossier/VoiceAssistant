#!/usr/bin/env python3
"""
Start only the API server without the voice pipeline
This allows testing the dashboard without voice pipeline blocking
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
import uvicorn

# Load environment
load_dotenv()

if __name__ == "__main__":
    # Run the API server without blocking voice pipeline
    uvicorn.run(
        "src.core.server:create_app",
        host="0.0.0.0",
        port=8000,
        factory=True,
        reload=True,
        log_level="info"
    )