#!/bin/bash
# Linux/WSL script to launch AI Assistant Backend
cd "$(dirname "$0")"

echo "Starting AI Assistant Backend..."
source venv/bin/activate
python3 main.py