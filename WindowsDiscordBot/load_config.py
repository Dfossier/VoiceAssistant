#!/usr/bin/env python3
"""
Load centralized configuration for Discord bot
"""

import json
from pathlib import Path

def load_services_config():
    """Load the centralized services configuration"""
    config_path = Path(__file__).parent.parent / "config" / "services.json"
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Extract Discord bot specific config
    return {
        'websocket_url': config['websocket_service']['url'],
        'audio': config['discord_bot']['audio_capture'],
        'connection': config['discord_bot']['connection'],
        'startup_timeout': config['websocket_service']['startup_timeout']
    }

# Make config available as module attribute
config = load_services_config()