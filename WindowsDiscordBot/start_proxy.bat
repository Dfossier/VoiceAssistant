@echo off
echo Starting WebSocket proxy (Windows localhost:8003 to WSL2 172.20.104.13:8002)...
bot_venv_windows\Scripts\python websocket_proxy.py
pause